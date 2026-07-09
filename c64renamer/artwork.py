"""Download cover art and screenshots for a matched game."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from . import http
from .providers.base import ArtworkAsset, GameHit, Provider

_SAFE = re.compile(r"[^A-Za-z0-9._ ()-]+")


def safe_name(name: str) -> str:
    """Make a string safe to use as a file/folder name on common filesystems."""
    cleaned = _SAFE.sub("", name).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "untitled"


def _extension_for(url: str) -> str:
    tail = url.rsplit("/", 1)[-1]
    if "." in tail:
        ext = "." + tail.rsplit(".", 1)[-1].split("?")[0].lower()
        if len(ext) <= 5:
            return ext
    return ".jpg"


def download_for_game(
    title: str,
    provider: Provider,
    hit: GameHit,
    dest_root: Path,
    max_screenshots: int = 8,
) -> List[Path]:
    """Fetch artwork for ``hit`` from ``provider`` into ``dest_root/<title>``.

    Returns the list of files written. Never raises for a single failed asset;
    it skips and continues so one dead URL cannot abort the batch.
    """
    try:
        assets: List[ArtworkAsset] = provider.artwork(hit)
    except Exception:
        return []

    game_dir = dest_root / safe_name(title)
    written: List[Path] = []
    shot_count = 0
    cover_count = 0

    for asset in assets:
        if asset.kind == "screenshot":
            if max_screenshots and shot_count >= max_screenshots:
                continue
            shot_count += 1
            index = shot_count
        else:
            cover_count += 1
            index = cover_count

        hint = safe_name(asset.filename_hint) if asset.filename_hint else ""
        stem = f"{asset.kind}-{index:02d}"
        if hint:
            stem = f"{asset.kind}-{index:02d}-{hint}"
        dest = game_dir / f"{provider.name}-{stem}{_extension_for(asset.url)}"

        if dest.exists():
            written.append(dest)
            continue
        try:
            http.download(asset.url, dest)
            written.append(dest)
        except Exception:
            continue

    return written
