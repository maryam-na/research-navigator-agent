"""Research statement schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


StatementType = Literal[
    "method",
    "result",
    "limitation",
    "future_work",
    "dataset",
    "background",
    "unknown",
]


class StatementRecord(BaseModel):
    """Extracted research statement with local evidence."""

    model_config = ConfigDict(extra="forbid")

    statement_id: str = Field(min_length=1)
    paper_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    statement_type: StatementType
    statement_text: str = Field(min_length=1, max_length=500)
    evidence_text: str = Field(min_length=1, max_length=320)
    confidence_rule: str = Field(min_length=1)
    sentence_index: int = Field(default=0, ge=0)
    created_at: str | None = None

    @field_validator(
        "statement_id",
        "paper_id",
        "chunk_id",
        "statement_text",
        "evidence_text",
        "confidence_rule",
        mode="after",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped
