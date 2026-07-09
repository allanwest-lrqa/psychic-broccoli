"""Builders that synthesise minimal-but-valid C64 files for tests."""

from __future__ import annotations

import struct


def _petscii_pad(name: str, length: int, pad: int = 0xA0) -> bytes:
    raw = name.encode("ascii", errors="replace")[:length]
    return raw + bytes([pad]) * (length - len(raw))


# --- D64 -------------------------------------------------------------
_SECTORS = [0] + [21] * 17 + [19] * 7 + [18] * 6 + [17] * 10


def _d64_offset(track: int, sector: int) -> int:
    return (sum(_SECTORS[1:track]) + sector) * 256


def make_d64(disk_name: str, programs: list[str]) -> bytes:
    image = bytearray(174848)

    # BAM: disk name at track 18 sector 0, offset 0x90.
    bam = _d64_offset(18, 0)
    image[bam + 0x90:bam + 0x90 + 16] = _petscii_pad(disk_name, 16)

    # Directory block at track 18 sector 1.
    dir_off = _d64_offset(18, 1)
    image[dir_off] = 0        # no next directory track
    image[dir_off + 1] = 0xFF
    for i, prog in enumerate(programs[:8]):
        slot = dir_off + i * 32
        image[slot + 2] = 0x82           # closed PRG
        image[slot + 3] = 17             # first data track
        image[slot + 4] = 0              # first data sector
        image[slot + 5:slot + 5 + 16] = _petscii_pad(prog, 16)
    return bytes(image)


# --- T64 -------------------------------------------------------------
def make_t64(container: str, entries: list[str]) -> bytes:
    data = bytearray(64 + 32 * max(len(entries), 1))
    sig = b"C64 tape image file"
    data[0:len(sig)] = sig
    struct.pack_into("<H", data, 0x20, 0x0100)         # version
    struct.pack_into("<H", data, 0x24, len(entries))   # max entries
    struct.pack_into("<H", data, 0x26, len(entries))   # used entries
    data[0x28:0x28 + 24] = _petscii_pad(container, 24, pad=0x20)
    for i, name in enumerate(entries):
        base = 64 + i * 32
        data[base] = 1                                 # normal file
        data[base + 0x10:base + 0x10 + 16] = _petscii_pad(name, 16, pad=0x20)
    return bytes(data)


# --- CRT -------------------------------------------------------------
def make_crt(name: str) -> bytes:
    data = bytearray(0x40 + 16)
    data[0:16] = b"C64 CARTRIDGE   "
    struct.pack_into(">I", data, 0x10, 0x40)           # header length
    struct.pack_into(">H", data, 0x14, 0x0100)         # version
    data[0x20:0x20 + 32] = _petscii_pad(name, 32, pad=0x00)
    return bytes(data)
