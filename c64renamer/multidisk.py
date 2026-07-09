"""Detect and normalise multi-disk / multi-side game releases.

Many C64 games span several disks or tape sides. The filenames (and internal
names) encode this in lots of ways: "(Disk 1 of 2)", "[Side A]", " d2",
"- Part 1 -", etc. This module pulls that marker out, leaving a clean base
title plus an ordinal, so sets can be grouped and named consistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Full marker: (disk|side|part|tape) <n|letter> [of <m>]
_MARKER = re.compile(
    r"[\(\[\-]?\s*(?P<kind>disk|side|part|tape)\s*"
    r"(?P<ord>\d+|[a-h])"
    r"(?:\s*(?:of|/)\s*(?P<total>\d+))?"
    r"\s*[\)\]\-]?",
    re.IGNORECASE,
)

# Short trailing form: (d1) (s2) [d2] etc.
_SHORT = re.compile(r"[\(\[\s]\s*(?P<kind>[ds])\s*(?P<ord>\d+)\s*[\)\]]?\s*$",
                    re.IGNORECASE)

_KIND_WORD = {"d": "disk", "s": "side"}


@dataclass
class DiskInfo:
    base: str                 # title with the disk marker removed
    index: Optional[int] = None   # 1-based ordinal (Side A -> 1, B -> 2, ...)
    total: Optional[int] = None
    kind: str = ""            # "disk" | "side" | "part" | "tape"
    label: str = ""           # human label, e.g. "Disk 1 of 2"

    @property
    def is_multi(self) -> bool:
        return self.index is not None


def _ord_value(token: str) -> int:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return ord(token) - ord("a") + 1  # a->1, b->2, ...


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .-_([")


def parse_disk_info(name: str) -> DiskInfo:
    """Extract disk/side info from a title (extension should be stripped)."""
    for regex in (_MARKER, _SHORT):
        matches = list(regex.finditer(name))
        if not matches:
            continue
        m = matches[-1]  # markers sit at the end of a title
        kind = m.group("kind").lower()
        kind = _KIND_WORD.get(kind, kind)
        index = _ord_value(m.group("ord"))
        total = None
        if "total" in m.groupdict() and m.group("total"):
            total = int(m.group("total"))
        base = _clean(name[:m.start()] + " " + name[m.end():])
        label = f"{kind.capitalize()} {index}" + (f" of {total}" if total else "")
        return DiskInfo(base=base or name, index=index, total=total,
                        kind=kind, label=label)

    return DiskInfo(base=_clean(name))


def format_name(title: str, info: DiskInfo, total_override: Optional[int] = None) -> str:
    """Produce a consistent display name for a (possibly multi-disk) title."""
    if not info.is_multi:
        return title
    total = info.total or total_override
    kind = (info.kind or "disk").capitalize()
    if total and total > 1:
        return f"{title} ({kind} {info.index} of {total})"
    return f"{title} ({kind} {info.index})"
