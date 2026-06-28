import pytest

from tools.pdf_tools import chunk_text, extract_pdf_text


def test_chunk_text_returns_empty_list_for_empty_text():
    assert chunk_text("") == []


def test_chunk_text_creates_deterministic_overlapping_chunks():
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_text(text, chunk_size=10, overlap=3)

    assert chunks == [
        {
            "chunk_id": "chunk_0000",
            "text": "abcdefghij",
            "start_char": 0,
            "end_char": 10,
        },
        {
            "chunk_id": "chunk_0001",
            "text": "hijklmnopq",
            "start_char": 7,
            "end_char": 17,
        },
        {
            "chunk_id": "chunk_0002",
            "text": "opqrstuvwx",
            "start_char": 14,
            "end_char": 24,
        },
        {
            "chunk_id": "chunk_0003",
            "text": "vwxyz",
            "start_char": 21,
            "end_char": 26,
        },
    ]


def test_chunk_text_rejects_invalid_parameters():
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("abc", chunk_size=0)

    with pytest.raises(ValueError, match="overlap"):
        chunk_text("abc", chunk_size=5, overlap=-1)

    with pytest.raises(ValueError, match="overlap"):
        chunk_text("abc", chunk_size=5, overlap=5)


def test_chunk_text_requires_string_input():
    with pytest.raises(TypeError, match="text must be a string"):
        chunk_text(None)  # type: ignore[arg-type]


def test_extract_pdf_text_rejects_missing_file(tmp_path):
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(FileNotFoundError, match="PDF file does not exist"):
        extract_pdf_text(str(missing_pdf))


def test_extract_pdf_text_rejects_non_pdf_file(tmp_path):
    text_file = tmp_path / "sample.txt"
    text_file.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a .pdf file"):
        extract_pdf_text(str(text_file))


def test_extract_pdf_text_rejects_remote_paths():
    with pytest.raises(ValueError, match="Only local file paths"):
        extract_pdf_text("https://example.com/paper.pdf")

