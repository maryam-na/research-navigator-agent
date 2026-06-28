"""Local PDF corpus setup helpers for the Streamlit dashboard."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CORPUS_MIN_PDFS = 5
CORPUS_MAX_PDFS = 10
DEFAULT_PAPERS_DIR = Path("data/papers")
DEFAULT_MANIFEST_PATH = DEFAULT_PAPERS_DIR / "manifest.json"
DEFAULT_LICENSE_REQUIREMENT = (
    "Use only synthetic, sample, open-access, or otherwise permitted papers. "
    "Verify source rights before adding new PDFs."
)
DEFAULT_UPLOAD_LICENSE_NOTES = (
    "User confirmed this local PDF is synthetic, sample, open-access, or otherwise permitted."
)


@dataclass(frozen=True)
class CorpusUploadValidation:
    """Deterministic validation result for a proposed PDF upload batch."""

    ok: bool
    errors: list[str]
    warnings: list[str]
    existing_count: int
    upload_count: int
    final_count: int


@dataclass(frozen=True)
class SavedPdf:
    """Metadata for one PDF saved into the local corpus directory."""

    original_filename: str
    filename: str
    path: str
    bytes_written: int


def list_pdf_filenames(papers_dir: str | Path = DEFAULT_PAPERS_DIR) -> list[str]:
    """Return local PDF filenames sorted by display order."""

    root = Path(papers_dir)
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_file() and _is_pdf_filename(path.name)
    )


def load_paper_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    """Load the local paper manifest, returning a default structure when missing."""

    path = Path(manifest_path)
    if not path.exists():
        return {
            "corpus_scope": "MVP local corpus for ResearchNavigator Agent",
            "license_requirement": DEFAULT_LICENSE_REQUIREMENT,
            "papers": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def describe_pdf_corpus(
    papers_dir: str | Path = DEFAULT_PAPERS_DIR,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    min_pdfs: int = CORPUS_MIN_PDFS,
    max_pdfs: int = CORPUS_MAX_PDFS,
) -> dict[str, Any]:
    """Summarize local PDF corpus and manifest consistency."""

    pdf_files = list_pdf_filenames(papers_dir)
    manifest = load_paper_manifest(manifest_path)
    manifest_files = sorted(
        str(item.get("filename", ""))
        for item in manifest.get("papers", [])
        if item.get("filename")
    )
    missing_from_manifest = sorted(set(pdf_files) - set(manifest_files))
    missing_from_disk = sorted(set(manifest_files) - set(pdf_files))
    pdf_count = len(pdf_files)
    if pdf_count == 0:
        status = "empty"
    elif pdf_count > max_pdfs:
        status = "over_limit"
    elif missing_from_manifest or missing_from_disk:
        status = "manifest_mismatch"
    elif pdf_count < min_pdfs:
        status = "below_minimum"
    else:
        status = "ready"
    return {
        "status": status,
        "pdf_count": pdf_count,
        "manifest_count": len(manifest_files),
        "pdf_files": pdf_files,
        "manifest_files": manifest_files,
        "missing_from_manifest": missing_from_manifest,
        "missing_from_disk": missing_from_disk,
        "papers_dir": str(Path(papers_dir)),
        "manifest_path": str(Path(manifest_path)),
        "min_pdfs": min_pdfs,
        "max_pdfs": max_pdfs,
    }


def validate_pdf_upload_selection(
    filenames: Iterable[str],
    existing_filenames: Iterable[str] = (),
    replace_existing: bool = False,
    min_pdfs: int = CORPUS_MIN_PDFS,
    max_pdfs: int = CORPUS_MAX_PDFS,
) -> CorpusUploadValidation:
    """Validate a local PDF upload selection before writing files."""

    upload_names = [str(name) for name in filenames if str(name).strip()]
    existing_names = {str(name) for name in existing_filenames if str(name).strip()}
    errors: list[str] = []
    warnings: list[str] = []
    if not upload_names:
        errors.append("Select at least one PDF file.")

    non_pdf_names = [name for name in upload_names if not _is_pdf_filename(name)]
    if non_pdf_names:
        errors.append("Only PDF files are supported: " + ", ".join(sorted(non_pdf_names)))

    valid_upload_count = len(upload_names) - len(non_pdf_names)
    existing_count = 0 if replace_existing else len(existing_names)
    final_count = existing_count + valid_upload_count
    if final_count > max_pdfs:
        errors.append(
            f"MVP corpus limit is {max_pdfs} PDFs; this selection would create {final_count}."
        )
    if 0 < final_count < min_pdfs:
        warnings.append(
            f"MVP corpus target is {min_pdfs}-{max_pdfs} PDFs; "
            f"this selection would create {final_count}."
        )
    return CorpusUploadValidation(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        existing_count=existing_count,
        upload_count=valid_upload_count,
        final_count=final_count,
    )


def save_uploaded_pdfs(
    uploaded_files: Iterable[Any],
    papers_dir: str | Path = DEFAULT_PAPERS_DIR,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    confirmed_permission: bool = False,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Save uploaded PDFs locally and synchronize the manifest.

    The caller must gate this function behind explicit user confirmation that each paper is
    synthetic, sample, open-access, or otherwise permitted.
    """

    uploads = list(uploaded_files)
    filenames = [_uploaded_filename(upload) for upload in uploads]
    validation = validate_pdf_upload_selection(
        filenames,
        existing_filenames=list_pdf_filenames(papers_dir),
        replace_existing=replace_existing,
    )
    if not confirmed_permission:
        raise ValueError("Confirm the local paper permission checklist before saving PDFs.")
    if not validation.ok:
        raise ValueError(" ".join(validation.errors))

    pending_files = []
    for upload, original_filename in zip(uploads, filenames, strict=True):
        payload = _uploaded_bytes(upload)
        if not payload:
            raise ValueError(f"{original_filename} is empty and was not saved.")
        pending_files.append((original_filename, payload))

    root = Path(papers_dir)
    root.mkdir(parents=True, exist_ok=True)
    if replace_existing:
        for pdf_path in root.iterdir():
            if pdf_path.is_file() and _is_pdf_filename(pdf_path.name):
                pdf_path.unlink()

    reserved_names = set(list_pdf_filenames(root))
    saved_files: list[SavedPdf] = []
    for original_filename, payload in pending_files:
        filename = unique_pdf_filename(sanitize_pdf_filename(original_filename), reserved_names)
        target_path = safe_pdf_output_path(root, filename)
        target_path.write_bytes(payload)
        reserved_names.add(filename)
        saved_files.append(
            SavedPdf(
                original_filename=original_filename,
                filename=filename,
                path=str(target_path),
                bytes_written=len(payload),
            )
        )

    manifest = write_paper_manifest(
        papers_dir=root,
        manifest_path=manifest_path,
        uploaded_filenames=[saved.filename for saved in saved_files],
    )
    return {
        "saved_files": [saved.__dict__ for saved in saved_files],
        "manifest": manifest,
        "corpus": describe_pdf_corpus(root, manifest_path),
    }


def sanitize_pdf_filename(filename: str) -> str:
    """Return a safe PDF filename that cannot traverse outside `data/papers`."""

    raw_name = str(filename or "").replace("\\", "/").split("/")[-1]
    raw_path = Path(raw_name)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_path.stem).strip("._-")
    if not stem:
        stem = "paper"
    return f"{stem}.pdf"


def unique_pdf_filename(filename: str, reserved_names: set[str]) -> str:
    """Choose a filename that does not collide with existing local PDFs."""

    candidate = sanitize_pdf_filename(filename)
    if candidate not in reserved_names:
        return candidate
    stem = Path(candidate).stem
    counter = 2
    while True:
        numbered = f"{stem}_{counter}.pdf"
        if numbered not in reserved_names:
            return numbered
        counter += 1


def safe_pdf_output_path(papers_dir: str | Path, filename: str) -> Path:
    """Resolve an upload target and ensure it remains inside the local paper directory."""

    root = Path(papers_dir).resolve()
    target = (root / sanitize_pdf_filename(filename)).resolve()
    if target.parent != root:
        raise ValueError("PDF uploads must stay inside the local paper directory.")
    return target


def write_paper_manifest(
    papers_dir: str | Path = DEFAULT_PAPERS_DIR,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    uploaded_filenames: Iterable[str] = (),
) -> dict[str, Any]:
    """Synchronize `manifest.json` with PDFs currently present on disk."""

    root = Path(papers_dir)
    path = Path(manifest_path)
    manifest = load_paper_manifest(path)
    existing_entries = {
        str(item.get("filename", "")): dict(item)
        for item in manifest.get("papers", [])
        if item.get("filename")
    }
    uploaded_lookup = {str(filename) for filename in uploaded_filenames}
    papers = []
    for filename in list_pdf_filenames(root):
        if filename in uploaded_lookup or filename not in existing_entries:
            papers.append(_manifest_entry_for_pdf(filename, uploaded=filename in uploaded_lookup))
        else:
            papers.append(existing_entries[filename])
    payload = {
        "corpus_scope": manifest.get(
            "corpus_scope",
            "MVP local corpus for ResearchNavigator Agent",
        ),
        "license_requirement": manifest.get("license_requirement", DEFAULT_LICENSE_REQUIREMENT),
        "papers": papers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _manifest_entry_for_pdf(filename: str, uploaded: bool) -> dict[str, Any]:
    paper_id = Path(filename).stem.lower().replace(" ", "-")
    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return {
        "filename": filename,
        "paper_id": paper_id,
        "title": title or paper_id,
        "source_type": "local_upload" if uploaded else "local",
        "license_notes": DEFAULT_UPLOAD_LICENSE_NOTES if uploaded else DEFAULT_LICENSE_REQUIREMENT,
        "topic": "user uploaded" if uploaded else "research discovery",
        "permission_confirmed": uploaded,
    }


def _is_pdf_filename(filename: str) -> bool:
    raw_name = str(filename or "").replace("\\", "/").split("/")[-1]
    return Path(raw_name).suffix.lower() == ".pdf"


def _uploaded_filename(upload: Any) -> str:
    return str(getattr(upload, "name", "") or "")


def _uploaded_bytes(upload: Any) -> bytes:
    if hasattr(upload, "getbuffer"):
        return bytes(upload.getbuffer())
    if hasattr(upload, "read"):
        return bytes(upload.read())
    if isinstance(upload, bytes):
        return upload
    raise TypeError("Uploaded PDF must provide bytes.")
