"""Paper and chunk schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaperRecord(BaseModel):
    """SQLite-compatible paper metadata."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    authors: str | None = None
    year: int | None = Field(default=None, ge=0, le=9999)
    venue: str | None = None
    license_notes: str | None = None
    created_at: str | None = None

    @field_validator("paper_id", "title", "source_path", mode="after")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class ChunkRecord(BaseModel):
    """SQLite-compatible paper chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    paper_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    created_at: str | None = None

    @field_validator("end_char", mode="after")
    @classmethod
    def end_after_start(cls, value: int, info) -> int:
        start_char = info.data.get("start_char")
        if start_char is not None and value < start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        return value
