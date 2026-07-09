"""Recognise cracker / demo group names so they are not mistaken for titles.

C64 disk images very often carry the *cracking group's* name (in the disk
name or an intro file) rather than the game's name -- e.g. "FAIRLIGHT",
"THE OUG-TEAM", "TRIAD". Treating those as the game title produces nonsense
names, so we detect and drop them.

Detection is deliberately conservative (exact normalised match against a known
list, plus a few unambiguous markers like "cracking") to avoid dropping real
titles such as "The A-Team".
"""

from __future__ import annotations

from . import matching

# Well-known C64 cracking / demo / release groups. Add freely -- matching is
# on the whole normalised name, so entries here only ever affect names that
# are exactly a group name.
_RAW_GROUPS = (
    "fairlight", "flt", "triad", "ikari", "zargon", "hokuto force",
    "genesis project", "gp", "eagle soft incorporated", "esi",
    "dynamic duo", "1001 crew", "radwar enterprises", "radwar",
    "german cracking service", "gcs", "software cracking anonymous",
    "sca", "paradize", "remember", "nostalgia", "laxity", "onslaught",
    "hitmen", "legion of doom", "lod", "f4cg", "fantastic 4 cracking group",
    "excess", "avatar", "beastie boys", "chromance", "crest", "censor design",
    "censor", "danish gold", "dominators", "flash cracking group",
    "hotline", "legend", "mean team", "papillons", "sharks", "talent",
    "the oug team", "oug team", "oug", "triangle", "vision", "wow",
    "wizax", "x rated", "zenith", "abnormal", "antic", "quartex",
    "vandalism", "megastyle", "motiv8", "padua", "success", "the shadows",
    "the force", "amok", "arcadia", "digital design", "empire cracking service",
    "atlantis", "bonzai", "booze design", "camelot", "cosine", "damage",
    "fire eagle", "hackersoft", "manikin", "oneway", "plush", "razor 1911",
    "rob", "role", "sceptic", "science 451", "starion", "the supply team",
    "transcom", "trilogy", "trsi", "tristar", "warriors of the wasteland",
    "yeti factories", "epsilon", "the corner",
)

KNOWN_GROUPS = {matching.normalize(g) for g in _RAW_GROUPS if matching.normalize(g)}

# Substrings that unambiguously mark crack/release credits rather than a title.
_MARKERS = (
    "cracking service", "cracking group", "cracked by", "hacked by",
    "trained by", "supplied by", "a cracking", "crack intro",
)


def is_group(name: str) -> bool:
    """True if ``name`` looks like a group/credit rather than a game title."""
    norm = matching.normalize(name)
    if not norm:
        return False
    if norm in KNOWN_GROUPS:
        return True
    if "cracking" in norm.split():  # e.g. "xyz cracking" / "... cracking ..."
        return True
    lowered = name.lower()
    return any(marker in lowered for marker in _MARKERS)
