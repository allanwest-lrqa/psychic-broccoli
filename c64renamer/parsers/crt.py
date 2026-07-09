"""Parser for CRT (cartridge) files.

The CRT header carries a 32-byte cartridge name. This is by far the most
reliable of the three formats because the name field is set deliberately by
whoever created the cartridge image.

Layout reference: https://vice-emu.sourceforge.io/vice_17.html (CRT appendix).
"""

from __future__ import annotations

from pathlib import Path

from .. import petscii
from .base import NameCandidate, ParsedFile

_SIGNATURE = b"C64 CARTRIDGE   "  # 16 bytes, space-padded
_NAME_OFFSET = 0x20
_NAME_LEN = 32


def parse(path: Path) -> ParsedFile:
    result = ParsedFile(path=path, fmt="crt")
    data = path.read_bytes()

    if len(data) < _NAME_OFFSET + _NAME_LEN:
        result.error = "file too small to be a CRT"
        return result

    if data[:16] != _SIGNATURE:
        result.error = "missing CRT signature"

    # The cartridge name is plain ASCII (0x00 padded) rather than PETSCII, but
    # our decoder handles both fine.
    name = petscii.decode(data[_NAME_OFFSET:_NAME_OFFSET + _NAME_LEN])
    if name:
        result.candidates.append(NameCandidate(name, "cart-name", weight=2.0))

    return result
