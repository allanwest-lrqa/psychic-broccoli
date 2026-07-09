"""Tunable defaults for the renamer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    # Minimum similarity (0..1) required before a file is renamed.
    min_confidence: float = 0.85
    # How many extracted candidate names to try per file (highest weight first).
    max_candidates: int = 5
    # Cap on downloaded screenshots per game (0 = unlimited).
    max_screenshots: int = 8
    # Download artwork at all.
    download_artwork: bool = True
    # Actually rename (False = dry run / preview only).
    apply: bool = False
