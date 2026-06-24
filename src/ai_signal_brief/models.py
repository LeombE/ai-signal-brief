from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceRef:
    """Minimal source reference used by early skeleton tests and examples."""

    id: str
    title: str
    publisher: str
    url: str
    source_type: str


@dataclass(frozen=True)
class Claim:
    """Minimal claim record with explicit source mapping."""

    id: str
    text: str
    source_ids: list[str]
    verification_status: str
    confidence: str


@dataclass(frozen=True)
class Story:
    """Minimal story record for the initial canonical report shape."""

    id: str
    rank: int
    title: str
    status: str
    source_ids: list[str]
    claims: list[Claim] = field(default_factory=list)