"""Parser for T64 (tape archive) files.

T64 is a container used by C64 emulators. It has a 64-byte header followed by
32-byte file records. We read the container ("tape") name and each record name.

Layout reference: https://vice-emu.sourceforge.io/vice_17.html (T64 appendix).
"""

from __future__ import annotations

import struct
from pathlib import Path

from .. import petscii
from .base import NameCandidate, ParsedFile

_HEADER_SIZE = 64
_RECORD_SIZE = 32
# The signature field is 32 bytes; real files start with one of these strings.
_SIGNATURES = (b"C64 tape image file", b"C64S tape file", b"C64 tape file")


def parse(path: Path) -> ParsedFile:
    result = ParsedFile(path=path, fmt="t64")
    data = path.read_bytes()

    if len(data) < _HEADER_SIZE:
        result.error = "file too small to be a T64"
        return result

    signature = data[:32]
    if not any(signature.startswith(sig) for sig in _SIGNATURES):
        result.error = "missing T64 signature"

    # used-entries count lives at offset 0x26 (little-endian 16-bit).
    max_entries = struct.unpack_from("<H", data, 0x24)[0]
    used_entries = struct.unpack_from("<H", data, 0x26)[0]
    # Some writers set used == 0 but still list entries; fall back to max.
    entry_count = used_entries or max_entries

    # Container name: 24 bytes at offset 0x28 (0x28..0x3F), usually padded with
    # spaces rather than 0xA0.
    container = petscii.decode(data[0x28:0x28 + 24])
    if container:
        result.candidates.append(
            NameCandidate(container, "container-name", weight=1.5)
        )

    # File records follow the header.
    for i in range(entry_count):
        base = _HEADER_SIZE + i * _RECORD_SIZE
        record = data[base:base + _RECORD_SIZE]
        if len(record) < _RECORD_SIZE:
            break
        entry_type = record[0]
        if entry_type == 0:  # free / unused slot
            continue
        name = petscii.decode(record[0x10:0x10 + 16])
        if name:
            weight = 1.5 if i == 0 else 1.0
            result.candidates.append(NameCandidate(name, "tape-entry", weight=weight))

    return result
