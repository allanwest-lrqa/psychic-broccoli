"""GameBase64 (gb64.com) provider -- the definitive C64 games database.

gb64.com does not publish a formal API, so this provider scrapes its public
search and game pages. The site's markup can change over time, so the URL and
extraction patterns are kept as clearly-labelled constants that are easy to
update, and every network step degrades gracefully (returns empty rather than
raising) so a markup change can never break the rename pipeline.

If you need rock-solid matching you can also download the full GameBase64
dataset from https://gb64.com/ and point a custom provider at it; this scraper
targets the convenient online lookups (search + screenshots).
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import List

from .. import http
from .base import ArtworkAsset, GameHit

_BASE = "https://gb64.com"
# Search endpoint. gb64 accepts a game-name query; we ask for an exact-ish
# name search and parse the returned links.
_SEARCH_URL = _BASE + "/search.php?" + urllib.parse.urlencode(
    {"searchtype": "name", "searchoption": "contains"}
) + "&search={query}"

# Links to individual game pages look like game.php?id=NNNN.
_GAME_LINK_RE = re.compile(
    r'href="(?P<url>(?:https?://[^"]+)?/?game\.php\?id=(?P<id>\d+)[^"]*)"'
    r'[^>]*>(?P<title>[^<]+)</a>',
    re.IGNORECASE,
)

# Screenshot / cover images referenced from a game page. gb64 serves these from
# /Screenshots/ and /Covers/ trees.
_IMAGE_RE = re.compile(
    r'(?:src|href)="(?P<url>[^"]*/(?:Screenshots|Covers)/[^"]+\.(?:png|gif|jpg|jpeg))"',
    re.IGNORECASE,
)


def _absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return _BASE + "/" + url.lstrip("/")


class GB64Provider:
    name = "gb64"

    def available(self) -> bool:
        # No API key required; assume reachable and fail soft at request time.
        return True

    def search(self, query: str) -> List[GameHit]:
        url = _SEARCH_URL.format(query=urllib.parse.quote(query))
        try:
            page = http.get_text(url)
        except Exception:
            return []

        hits: List[GameHit] = []
        seen = set()
        for m in _GAME_LINK_RE.finditer(page):
            gid = m.group("id")
            if gid in seen:
                continue
            seen.add(gid)
            title = html.unescape(m.group("title")).strip()
            if not title:
                continue
            hits.append(
                GameHit(
                    title=title,
                    game_id=gid,
                    url=_absolute(m.group("url")),
                )
            )
        return hits

    def artwork(self, hit: GameHit) -> List[ArtworkAsset]:
        if not hit.url:
            return []
        try:
            page = http.get_text(hit.url)
        except Exception:
            return []

        assets: List[ArtworkAsset] = []
        seen = set()
        for m in _IMAGE_RE.finditer(page):
            raw = m.group("url")
            full = _absolute(html.unescape(raw))
            if full in seen:
                continue
            seen.add(full)
            kind = "cover" if "/Covers/" in full else "screenshot"
            hint = full.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            assets.append(ArtworkAsset(full, kind, hint))
        return assets
