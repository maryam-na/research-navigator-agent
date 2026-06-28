"""Local PDF parsing and deterministic text chunking utilities."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


def _resolve_local_path(path_value: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError("pdf_path must be a non-empty local file path.")

    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only local file paths are supported for PDF extraction.")

    path = Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"PDF path is not a file: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {path}")
    return path


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a local PDF file using pypdf.

    The function is intentionally deterministic and local-only. It does not
    fetch remote files or perform OCR.
    """

    path = _resolve_local_path(pdf_path)

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError("pypdf is required to extract PDF text.") from exc

    try:
        reader = PdfReader(str(path))
        page_text = []
        for page in reader.pages:
            page_text.append(page.extract_text() or "")
    except Exception as exc:  # pypdf raises several parser-specific exceptions
        raise ValueError(f"Could not extract text from PDF: {path}") from exc

    return "\n\n".join(text.strip() for text in page_text if text.strip()).strip()


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[dict]:
    """Split text into deterministic overlapping character chunks.

    Returns dictionaries with `chunk_id`, `text`, `start_char`, and `end_char`.
    Character offsets refer to the original input text.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")
    if not text:
        return []

    chunks: list[dict] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_id = f"chunk_{len(chunks):04d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": text[start:end],
                "start_char": start,
                "end_char": end,
            }
        )
        if end == text_length:
            break
        start = end - overlap

    return chunks

