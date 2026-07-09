"""Metadata / artwork providers."""

from __future__ import annotations

from typing import List

from .base import ArtworkAsset, GameHit, Provider
from .c64com import C64ComProvider
from .gb64 import GB64Provider
from .mobygames import MobyGamesProvider
from .retrocollector import RetroCollectorProvider


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
    "REGISTRY",
    "default_providers",
]
