"""Shared data types and helpers for the file-format parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class NameCandidate:
    """A single candidate game name extracted from a file.

    A file usually yields several candidates (e.g. a disk name plus the names
    of the programs on it). Each carries a ``weight`` hinting how likely it is
    to be the real game title, which the matcher uses to break ties.
    """

    name: str
    source: str  # e.g. "disk-name", "dir-entry", "container-name", "cart-name"
    weight: float = 1.0


@dataclass
class ParsedFile:
    """The result of parsing one C64 file."""

    path: Path
    fmt: str  # "d64" | "t64" | "crt"
    candidates: List[NameCandidate] = field(default_factory=list)
    error: Optional[str] = None

    def best_candidate(self) -> Optional[NameCandidate]:
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.weight)

    def unique_names(self) -> List[str]:
        """Distinct candidate names, highest weight first, de-duplicated."""
        seen = set()
        ordered = sorted(self.candidates, key=lambda c: c.weight, reverse=True)
        result = []
        for cand in ordered:
            key = cand.name.lower()
            if cand.name and key not in seen:
                seen.add(key)
                result.append(cand.name)
        return result


class ParseError(Exception):
    """Raised when a file cannot be parsed as its claimed format."""
