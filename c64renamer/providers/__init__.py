"""Metadata / artwork providers."""

from __future__ import annotations

from typing import List

from .base import ArtworkAsset, GameHit, Provider
from .gb64 import GB64Provider
from .mobygames import MobyGamesProvider


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
    return providers


__all__ = [
    "ArtworkAsset",
    "GameHit",
    "Provider",
    "GB64Provider",
    "MobyGamesProvider",
    "default_providers",
]
