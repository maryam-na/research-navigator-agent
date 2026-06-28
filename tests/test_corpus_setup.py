import json

import pytest

from ui.corpus_setup import (
    describe_pdf_corpus,
    safe_pdf_output_path,
    sanitize_pdf_filename,
    save_uploaded_pdfs,
    validate_pdf_upload_selection,
    write_paper_manifest,
)


class FakeUpload:
    def __init__(self, name: str, payload: bytes = b"%PDF-1.4\nsample\n"):
        self.name = name
        self._payload = payload

    def getbuffer(self):
        return memoryview(self._payload)


def test_validate_pdf_upload_selection_enforces_type_and_limit():
    non_pdf = validate_pdf_upload_selection(["paper.pdf", "notes.txt"], [])
    too_many = validate_pdf_upload_selection(
        ["extra.pdf"],
        [f"paper_{index}.pdf" for index in range(10)],
    )

    assert non_pdf.ok is False
    assert "Only PDF files are supported: notes.txt" in non_pdf.errors
    assert too_many.ok is False
    assert "MVP corpus limit is 10 PDFs" in too_many.errors[0]


def test_save_uploaded_pdfs_requires_permission(tmp_path):
    with pytest.raises(ValueError, match="Confirm the local paper permission checklist"):
        save_uploaded_pdfs(
            [FakeUpload("paper.pdf")],
            papers_dir=tmp_path / "papers",
            manifest_path=tmp_path / "papers" / "manifest.json",
            confirmed_permission=False,
        )


def test_save_uploaded_pdfs_sanitizes_names_and_updates_manifest(tmp_path):
    papers_dir = tmp_path / "papers"
    manifest_path = papers_dir / "manifest.json"

    result = save_uploaded_pdfs(
        [FakeUpload("../My Paper!.PDF"), FakeUpload("My Paper!.pdf")],
        papers_dir=papers_dir,
        manifest_path=manifest_path,
        confirmed_permission=True,
    )

    saved_names = [item["filename"] for item in result["saved_files"]]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert saved_names == ["My_Paper.pdf", "My_Paper_2.pdf"]
    assert (papers_dir / "My_Paper.pdf").read_bytes().startswith(b"%PDF")
    assert [item["filename"] for item in manifest["papers"]] == saved_names
    assert all(item["permission_confirmed"] for item in manifest["papers"])
    assert sanitize_pdf_filename("../../bad path.pdf") == "bad_path.pdf"
    assert safe_pdf_output_path(papers_dir, "../bad.pdf").parent == papers_dir.resolve()


def test_save_uploaded_pdfs_can_replace_existing_pdf_corpus(tmp_path):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "old.PDF").write_bytes(b"%PDF old")
    (papers_dir / ".gitkeep").write_text("", encoding="utf-8")
    write_paper_manifest(papers_dir, papers_dir / "manifest.json")

    result = save_uploaded_pdfs(
        [FakeUpload("new.pdf")],
        papers_dir=papers_dir,
        manifest_path=papers_dir / "manifest.json",
        confirmed_permission=True,
        replace_existing=True,
    )

    assert not (papers_dir / "old.PDF").exists()
    assert (papers_dir / ".gitkeep").exists()
    assert [item["filename"] for item in result["manifest"]["papers"]] == ["new.pdf"]


def test_describe_pdf_corpus_reports_manifest_mismatch(tmp_path):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "on_disk.pdf").write_bytes(b"%PDF")
    (papers_dir / "manifest.json").write_text(
        json.dumps({"papers": [{"filename": "missing.pdf"}]}),
        encoding="utf-8",
    )

    status = describe_pdf_corpus(papers_dir, papers_dir / "manifest.json")

    assert status["status"] == "manifest_mismatch"
    assert status["missing_from_manifest"] == ["on_disk.pdf"]
    assert status["missing_from_disk"] == ["missing.pdf"]
