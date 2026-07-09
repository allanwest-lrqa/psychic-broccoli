"""Parser for D64 (1541 disk image) files.

A D64 is a raw dump of a 5.25" 1541 floppy. We read:
  * the disk name from the BAM (track 18, sector 0)
  * the program names from the directory (track 18, sector 1 onwards)

Layout reference: https://vice-emu.sourceforge.io/vice_17.html (D64 appendix).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Tuple

from .. import petscii
from .base import NameCandidate, ParsedFile

# Sectors per track for a standard 1541 disk. Index by 1-based track number.
_SECTORS_PER_TRACK = (
    [0]
    + [21] * 17   # tracks 1-17
    + [19] * 7    # tracks 18-24
    + [18] * 6    # tracks 25-30
    + [17] * 10   # tracks 31-40
)

# Recognised image sizes (bytes) -> whether an error-info block is appended.
_KNOWN_SIZES = {
    174848: 35,   # 35 tracks, no errors
    175531: 35,   # 35 tracks + error bytes
    196608: 40,   # 40 tracks, no errors
    197376: 40,   # 40 tracks + error bytes
}

_BLOCK_SIZE = 256
_DIR_TRACK = 18
_BAM_SECTOR = 0
_FIRST_DIR_SECTOR = 1
_ENTRIES_PER_SECTOR = 8
_ENTRY_SIZE = 32


def _block_offset(track: int, sector: int) -> int:
    """Byte offset of a (track, sector) block within the image."""
    if track < 1 or track >= len(_SECTORS_PER_TRACK):
        raise IndexError(f"track {track} out of range")
    preceding = sum(_SECTORS_PER_TRACK[1:track])
    return (preceding + sector) * _BLOCK_SIZE


def _iter_dir_entries(data: bytes) -> Iterator[bytes]:
    """Yield each 32-byte directory entry, following the sector chain."""
    track, sector = _DIR_TRACK, _FIRST_DIR_SECTOR
    visited: set[Tuple[int, int]] = set()
    while track != 0:
        if (track, sector) in visited:  # guard against corrupt loops
            break
        visited.add((track, sector))
        try:
            offset = _block_offset(track, sector)
        except IndexError:
            break
        block = data[offset:offset + _BLOCK_SIZE]
        if len(block) < _BLOCK_SIZE:
            break
        for i in range(_ENTRIES_PER_SECTOR):
            start = i * _ENTRY_SIZE
            yield block[start:start + _ENTRY_SIZE]
        # First two bytes of the block point at the next directory block.
        track, sector = block[0], block[1]


def parse(path: Path) -> ParsedFile:
    result = ParsedFile(path=path, fmt="d64")
    data = path.read_bytes()

    if len(data) not in _KNOWN_SIZES:
        # Be lenient: unusual sizes still often parse, but flag it.
        result.error = f"unexpected D64 size {len(data)} bytes"

    # --- Disk name from the BAM ---------------------------------------
    try:
        bam_off = _block_offset(_DIR_TRACK, _BAM_SECTOR)
        disk_name = petscii.decode(data[bam_off + 0x90:bam_off + 0x90 + 16])
        if disk_name:
            result.candidates.append(
                NameCandidate(disk_name, "disk-name", weight=2.0)
            )
    except (IndexError, ValueError):
        pass

    # --- Program names from the directory -----------------------------
    prg_names: List[str] = []
    for entry in _iter_dir_entries(data):
        if len(entry) < _ENTRY_SIZE:
            continue
        file_type = entry[2]
        # Low nibble 0..5 = DEL/SEQ/PRG/USR/REL/CBM; only closed (bit 7 set)
        # files are real. Skip scratched (type 0) and unclosed entries.
        if (file_type & 0x0F) == 0 or (file_type & 0x80) == 0:
            continue
        name = petscii.decode(entry[0x05:0x05 + 16])
        if name:
            prg_names.append(name)

    # The first program is the most likely to be the game's own name.
    for idx, name in enumerate(prg_names):
        weight = 1.5 if idx == 0 else 1.0
        result.candidates.append(NameCandidate(name, "dir-entry", weight=weight))

    return result
