"""File-format parsers for C64 disk, tape and cartridge images."""

from __future__ import annotations

from pathlib import Path

from . import crt, d64, t64
from .base import NameCandidate, ParsedFile, ParseError

# Map lowercase extension -> parser module.
_PARSERS = {
    ".d64": d64,
    ".t64": t64,
    ".crt": crt,
}

SUPPORTED_EXTENSIONS = tuple(_PARSERS.keys())


def parse(path: Path) -> ParsedFile:
    """Parse ``path`` according to its extension.

    Raises ParseError if the extension is not one we support.
    """
    parser = _PARSERS.get(path.suffix.lower())
    if parser is None:
        raise ParseError(f"unsupported extension: {path.suffix!r}")
    return parser.parse(path)


__all__ = [
    "NameCandidate",
    "ParsedFile",
    "ParseError",
    "SUPPORTED_EXTENSIONS",
    "parse",
]
