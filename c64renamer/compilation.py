"""Detect compilation images (multiple games in one file).

The goal is high *precision*: we would rather let the occasional compilation
through than wrongly exclude a genuine single game from the USB build. So
detection is keyword-driven by default (very few false positives), with an
optional, opt-in heuristic based on how many distinct programs a disk holds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from .parsers.base import ParsedFile

# Words/phrases that reliably indicate a multi-game release.
_KEYWORDS = (
    "compilation", "collection", "anthology", "megamix", "mega mix",
    "hit pack", "hits pack", "games pack", "game pack", "gamepack",
    "best of", "greatest hits", "super games", "all stars", "allstars",
    "10 great games", "arcade classics", "bumper", "six pack", "6 pack",
    "triple pack", "double pack", "quattro", "10 pack", "sports pack",
)

# "<n> in 1" / "<n>-in-1" style, and "<n> games".
_N_IN_ONE = re.compile(r"\b\d{1,3}\s*[- ]?in[- ]?1\b", re.IGNORECASE)
_N_GAMES = re.compile(r"\b(\d{1,3})\s+games\b", re.IGNORECASE)


@dataclass
class CompilationVerdict:
    is_compilation: bool
    reason: str = ""


def detect(parsed: ParsedFile, entry_threshold: int = 0,
           extra_names: Sequence[str] = ()) -> CompilationVerdict:
    """Decide whether ``parsed`` looks like a compilation.

    ``extra_names`` lets the caller add context the parser can't see -- notably
    the filename, since a D64 disk name is capped at 16 characters and often
    truncates the tell-tale keyword.

    ``entry_threshold`` > 0 enables the secondary heuristic: a disk with at
    least that many distinct directory programs is treated as a compilation.
    It is disabled by default because many single games ship lots of files.
    """
    names = [c.name for c in parsed.candidates] + list(extra_names)
    haystack = "  ".join(names).lower()

    for kw in _KEYWORDS:
        if kw in haystack:
            return CompilationVerdict(True, f"name contains '{kw}'")

    m = _N_IN_ONE.search(haystack)
    if m:
        return CompilationVerdict(True, f"name contains '{m.group(0).strip()}'")

    m = _N_GAMES.search(haystack)
    if m and int(m.group(1)) >= 3:
        return CompilationVerdict(True, f"name contains '{m.group(0).strip()}'")

    if entry_threshold > 0:
        dir_entries = [c.name for c in parsed.candidates if c.source == "dir-entry"]
        distinct = {n.lower() for n in dir_entries}
        if len(distinct) >= entry_threshold:
            return CompilationVerdict(
                True, f"{len(distinct)} distinct programs on disk "
                      f"(>= {entry_threshold})")

    return CompilationVerdict(False)
