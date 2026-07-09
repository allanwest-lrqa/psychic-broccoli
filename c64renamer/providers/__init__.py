"""Metadata / artwork providers."""

from __future__ import annotations

from typing import List

from pathlib import Path
from typing import Optional

from .base import ArtworkAsset, GameHit, Provider
from .c64com import C64ComProvider
from .gb64 import GB64Provider
from .localgb64 import LocalGB64Provider
from .mobygames import MobyGamesProvider
from .retrocollector import RetroCollectorProvider


def make_localgb64(db_path, screenshots_dir=None) -> Optional[LocalGB64Provider]:
    """Build a local GameBase64 provider if the .mdb path looks usable."""
    if not db_path:
        return None
    scr = screenshots_dir
    if scr is None:
        # Default to a sibling "Screenshots" folder next to the .mdb.
        sibling = Path(db_path).parent / "Screenshots"
        scr = sibling if sibling.is_dir() else None
    return LocalGB64Provider(db_path=Path(db_path), screenshots_dir=scr)


def default_providers() -> List[Provider]:
    """Return the providers enabled by default, best-first.

    MobyGames is preferred for matching (structured data, clean titles) but is
    only usable when an API key is configured; gb64 needs no key. Both are
    used for artwork.
    """
    providers: List[Provider] = []
    moby = MobyGamesProvider()
    if moby.available():
        providers.append(moby)
    providers.append(GB64Provider())
    providers.append(C64ComProvider())
    providers.append(RetroCollectorProvider())
    return providers


# Registry used by the CLI/GUI to build providers by name.
REGISTRY = {
    "mobygames": MobyGamesProvider,
    "gb64": GB64Provider,
    "c64com": C64ComProvider,
    "retrocollector": RetroCollectorProvider,
}


__all__ = [
    "ArtworkAsset",
    "GameHit",
    "Provider",
    "GB64Provider",
    "MobyGamesProvider",
    "C64ComProvider",
    "RetroCollectorProvider",
    "LocalGB64Provider",
    "make_localgb64",
    "REGISTRY",
    "default_providers",
]
