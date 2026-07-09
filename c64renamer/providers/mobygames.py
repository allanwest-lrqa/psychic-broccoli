"""MobyGames provider using the official MobyGames API.

MobyGames forbids scraping but offers a documented JSON API. A free API key is
required; set it via the ``MOBYGAMES_API_KEY`` environment variable or pass it
to the constructor. Docs: https://www.mobygames.com/info/api/

The free tier is rate-limited (roughly one request per second), so we throttle
between calls.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import List, Optional

from .. import http
from .base import ArtworkAsset, GameHit

_API_BASE = "https://api.mobygames.com/v1"
# MobyGames platform id for the Commodore 64.
_C64_PLATFORM_ID = 27
_MIN_INTERVAL = 1.1  # seconds between API calls (rate-limit friendly)


class MobyGamesProvider:
    name = "mobygames"

    def __init__(self, api_key: Optional[str] = None,
                 platform_id: int = _C64_PLATFORM_ID):
        self.api_key = api_key or os.environ.get("MOBYGAMES_API_KEY", "")
        self.platform_id = platform_id
        self._last_call = 0.0

    def available(self) -> bool:
        return bool(self.api_key)

    # -- internal helpers ---------------------------------------------
    def _throttle(self) -> None:
        # Cannot use time.monotonic guard on the very first call; that's fine.
        elapsed = time.time() - self._last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_call = time.time()

    def _get(self, path: str, **params) -> dict:
        params["api_key"] = self.api_key
        query = urllib.parse.urlencode(params)
        self._throttle()
        return http.get_json(f"{_API_BASE}{path}?{query}")

    # -- Provider interface -------------------------------------------
    def search(self, query: str) -> List[GameHit]:
        if not self.available():
            return []
        data = self._get(
            "/games",
            title=query,
            platform=self.platform_id,
            format="normal",
        )
        hits: List[GameHit] = []
        for game in data.get("games", []):
            hits.append(
                GameHit(
                    title=game.get("title", ""),
                    game_id=str(game.get("game_id")),
                    url=game.get("moby_url"),
                    extra={
                        "sample_cover": game.get("sample_cover"),
                        "sample_screenshots": game.get("sample_screenshots", []),
                    },
                )
            )
        return hits

    def artwork(self, hit: GameHit) -> List[ArtworkAsset]:
        assets: List[ArtworkAsset] = []
        if not self.available() or not hit.game_id:
            return assets

        # --- Covers ---------------------------------------------------
        try:
            covers = self._get(
                f"/games/{hit.game_id}/platforms/{self.platform_id}/covers"
            )
            for group in covers.get("cover_groups", []):
                for cover in group.get("covers", []):
                    url = cover.get("image")
                    if url:
                        scan = (cover.get("scan_of") or "cover").lower()
                        assets.append(ArtworkAsset(url, "cover", scan.replace(" ", "-")))
        except Exception:
            # Fall back to the sample cover from the search result.
            sample = (hit.extra or {}).get("sample_cover") or {}
            if sample.get("image"):
                assets.append(ArtworkAsset(sample["image"], "cover", "front"))

        # --- Screenshots ---------------------------------------------
        try:
            shots = self._get(
                f"/games/{hit.game_id}/platforms/{self.platform_id}/screenshots"
            )
            for idx, shot in enumerate(shots.get("screenshots", [])):
                url = shot.get("image")
                if url:
                    assets.append(ArtworkAsset(url, "screenshot", f"shot-{idx + 1:02d}"))
        except Exception:
            for idx, shot in enumerate((hit.extra or {}).get("sample_screenshots", [])):
                url = shot.get("image")
                if url:
                    assets.append(ArtworkAsset(url, "screenshot", f"shot-{idx + 1:02d}"))

        return assets
