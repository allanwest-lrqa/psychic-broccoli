"""Helpers for turning raw Commodore 64 name bytes into readable text.

Names stored inside D64/T64/CRT files are encoded in PETSCII and padded with
either 0xA0 (shifted space, used on disk) or 0x00 / 0x20 (used elsewhere). This
module converts those bytes into plain ASCII/Unicode text that is safe to show,
compare and use in a filename.
"""

from __future__ import annotations

# Padding bytes that mark the end of a fixed-width name field.
_PADDING = (0x00, 0xA0)


def _translate_byte(b: int) -> str:
    """Translate a single PETSCII byte to a printable character.

    We only care about names, so anything that is not a sensible printable
    glyph is dropped rather than turned into mojibake.
    """
    # Printable ASCII maps 1:1. This covers the PETSCII space/digit/uppercase
    # range (0x20-0x5A) as well as lowercase letters, which appear in ASCII
    # name fields such as the CRT cartridge name.
    if 0x20 <= b <= 0x7E:
        return chr(b)
    # Shifted uppercase letters live at 0xC1-0xDA on the C64.
    if 0xC1 <= b <= 0xDA:
        return chr(b - 0x80)
    # Everything else (graphics chars, control codes, colours) is noise in a
    # game title, so we skip it.
    return ""


def decode(data: bytes) -> str:
    """Decode a fixed-width PETSCII name field into a trimmed string."""
    # Trim trailing padding first so we do not emit trailing spaces.
    end = len(data)
    while end > 0 and data[end - 1] in _PADDING:
        end -= 1
    trimmed = data[:end]

    out = [_translate_byte(b) for b in trimmed]
    text = "".join(out)
    # Collapse internal padding-runs that some tools leave mid-field, then
    # normalise whitespace.
    return " ".join(text.split()).strip()
