"""Name normalisation and fuzzy matching with confidence scoring.

The names we extract from files are messy: uppercase, abbreviated, decorated
with cracker tags ("COMMANDO/H", "GIANA +3", "ZAK MCKRACKEN [E]"). This module
cleans them up and scores how well a candidate name matches a database title so
we only rename when we are confident.

Pure standard library -- no third-party fuzzy-matching dependency required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Optional

# Tokens frequently appended by crackers / release groups that are not part of
# the real title. Stripped before matching.
_NOISE_TOKENS = {
    "cr", "crk", "crack", "cracked", "trained", "trainer", "docs", "doc",
    "preview", "demo", "final", "fixed", "ntsc", "pal", "side", "disk",
    "tape", "budget", "reissue", "v1", "v2", "h", "e", "s", "t", "m", "b",
}

# Anything after one of these separators is usually a group/version tag.
_TAG_SPLIT = re.compile(r"[/\\]|\s[-+]\s|\s\+\d+")
_BRACKETS = re.compile(r"[\[(<{].*?[\]) >}]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Trailing cracker/hack tags, often glued to the last word:
#   "5th Gear17h" -> "5th Gear", "Game +3" -> "Game", "Thing 100%" -> "Thing".
_TRAILING_TAG = re.compile(r"\s*(?:\d{1,3}h|\d{1,3}%|\+\d+|v\d+)$", re.IGNORECASE)
# Single trailing words that are cracker noise rather than part of the title.
_JUNK_TRAILING_WORDS = {
    "cr", "crk", "crack", "cracked", "docs", "doc", "intro", "final", "note",
    "notes", "trained", "trainer", "fix", "fixed", "ntsc", "pal", "plus",
}


def strip_junk(text: str) -> str:
    """Remove trailing cracker/hack tags such as '17h', '+3', '100%', 'cr'."""
    prev = None
    while text != prev:
        prev = text
        text = _TRAILING_TAG.sub("", text).strip(" .-_+")
        parts = text.split()
        if len(parts) > 1 and parts[-1].lower() in _JUNK_TRAILING_WORDS:
            text = " ".join(parts[:-1])
    return text.strip()


@dataclass
class MatchResult:
    """A scored match between an extracted name and a database title."""

    title: str            # canonical title from the provider
    score: float          # confidence 0.0 - 1.0
    query: str            # the candidate name that produced this match
    provider: str = ""
    game_id: Optional[str] = None
    url: Optional[str] = None


def clean_title(raw: str) -> str:
    """Turn a raw extracted name into a human-friendly title.

    Removes bracketed tags and cracker suffixes, then title-cases the result.
    Used for display and as the basis for the renamed filename when no
    canonical database title is available.
    """
    text = _BRACKETS.sub(" ", raw)
    text = _TAG_SPLIT.split(text)[0]
    text = re.sub(r"\s+", " ", text).strip(" .-_+")
    text = strip_junk(text)
    if not text:
        return raw.strip()
    # Preserve short all-caps acronyms (<= 2 chars, e.g. "IK"), title-case
    # everything else.
    words = []
    for w in text.split():
        if len(w) <= 2 and w.isupper():
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join(words)


def normalize(raw: str) -> str:
    """Aggressively normalise a name for comparison only (not for display)."""
    text = raw.lower()
    text = _BRACKETS.sub(" ", text)
    text = _TAG_SPLIT.split(text)[0]
    text = strip_junk(text)
    tokens = [t for t in _NON_ALNUM.split(text) if t]
    tokens = [t for t in tokens if t not in _NOISE_TOKENS]
    # Drop a leading article which databases often move to the end.
    if tokens and tokens[0] in ("the", "a", "an"):
        tokens = tokens[1:]
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity between two names.

    Blends a character-level ratio with a token-overlap ratio so that both
    "IMPOSSIBLE MISSION" vs "Impossible Mission" and word-reordered titles
    score highly, while unrelated names stay low.
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0

    # Character-level ratio on the space-stripped forms so that spacing
    # differences ("BOULDERDASH" vs "Boulder Dash") do not hurt the score.
    seq = SequenceMatcher(None, na.replace(" ", ""), nb.replace(" ", "")).ratio()

    ta, tb = set(na.split()), set(nb.split())
    overlap = len(ta & tb) / max(len(ta), len(tb)) if ta and tb else 0.0

    # A full token-subset (one title contains all of the other's words) is a
    # strong signal, e.g. "Giana Sisters" vs "The Great Giana Sisters".
    subset_bonus = 1.0 if (ta <= tb or tb <= ta) else 0.0
    token_score = max(overlap, 0.5 * overlap + 0.5 * subset_bonus)

    return max(seq, token_score)


def best_match(
    candidates: Iterable[str],
    titles: Iterable[str],
    provider: str = "",
) -> Optional[MatchResult]:
    """Find the best (candidate, title) pairing across all combinations."""
    title_list = list(titles)
    best: Optional[MatchResult] = None
    for cand in candidates:
        for title in title_list:
            score = similarity(cand, title)
            if best is None or score > best.score:
                best = MatchResult(title=title, score=score, query=cand,
                                   provider=provider)
    return best


def rank_titles(candidate: str, titles: Iterable[str]) -> List[tuple]:
    """Return (title, score) pairs sorted best-first for a single candidate."""
    scored = [(t, similarity(candidate, t)) for t in titles]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
