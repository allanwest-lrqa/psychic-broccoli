"""c64.com provider (best-effort scraper).

c64.com hosts a large C64 games database with screenshots. It has no formal
API, so this provider scrapes its public pages. As with the gb64 provider, the
URL and extraction patterns are kept as clearly-labelled constants and every
network step fails soft (returns nothing rather than raising) so a site change
can never break the pipeline -- adjust the constants below if the markup moves.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import List

from .. import http
from .base import ArtworkAsset, GameHit

_BASE = "https://www.c64.com"
# Site search. c64.com's search takes a text query and returns game links.
_SEARCH_URL = _BASE + "/search/?searchtext={query}"

# Links to a game page, e.g. /games/1234.html or /game/1234.
_GAME_LINK_RE = re.compile(
    r'href="(?P<url>/?(?:games?/)[^"]*?(?P<id>\d+)[^"]*)"[^>]*>(?P<title>[^<]+)</a>',
    re.IGNORECASE,
)
# Screenshot / cover images on a game page.
_IMAGE_RE = re.compile(
    r'(?:src|href)="(?P<url>[^"]+\.(?:png|gif|jpg|jpeg))"',
    re.IGNORECASE,
)
_IMG_HINT = re.compile(r"(screenshot|screen|cover|box|title)", re.IGNORECASE)


def _absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return _BASE + "/" + url.lstrip("/")


class C64ComProvider:
    name = "c64com"

    def available(self) -> bool:
        return True

    def search(self, query: str) -> List[GameHit]:
        try:
            page = http.get_text(_SEARCH_URL.format(query=urllib.parse.quote(query)))
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
            if title:
                hits.append(GameHit(title=title, game_id=gid,
                                    url=_absolute(m.group("url"))))
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
            url = _absolute(html.unescape(m.group("url")))
            if url in seen or not _IMG_HINT.search(url):
                continue
            seen.add(url)
            kind = "cover" if re.search(r"cover|box", url, re.IGNORECASE) else "screenshot"
            hint = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            assets.append(ArtworkAsset(url, kind, hint))
        return assets
