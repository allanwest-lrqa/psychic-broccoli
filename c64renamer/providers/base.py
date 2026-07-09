"""Provider interface: search for a title and fetch its artwork."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


@dataclass
class GameHit:
    """A single game returned by a provider's search."""

    title: str
    game_id: Optional[str] = None
    url: Optional[str] = None
    extra: Dict = field(default_factory=dict)


@dataclass
class ArtworkAsset:
    """A downloadable artwork image."""

    url: str
    kind: str  # "cover" | "screenshot"
    filename_hint: str = ""


class Provider(Protocol):
    """Every artwork/metadata source implements this."""

    name: str

    def available(self) -> bool:
        """Whether this provider is usable (e.g. API key present)."""

    def search(self, query: str) -> List[GameHit]:
        """Return candidate games matching ``query``."""

    def artwork(self, hit: GameHit) -> List[ArtworkAsset]:
        """Return downloadable artwork for a specific game hit."""
