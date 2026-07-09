"""retrocollector.org provider (best-effort scraper).

retrocollector.org catalogues retro games with box/media images. No formal API
exists, so this scrapes public pages defensively: adjustable URL/regex
constants and fail-soft networking, identical in spirit to the gb64 and c64.com
providers. Tune the constants below if the site's markup differs.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import List

from .. import http
from .base import ArtworkAsset, GameHit

_BASE = "https://www.retrocollector.org"
_SEARCH_URL = _BASE + "/search?q={query}&platform=c64"

_GAME_LINK_RE = re.compile(
    r'href="(?P<url>/?[^"]*(?:game|item|title)[^"]*?(?P<id>\d+)[^"]*)"'
    r'[^>]*>(?P<title>[^<]+)</a>',
    re.IGNORECASE,
)
_IMAGE_RE = re.compile(
    r'(?:src|data-src|href)="(?P<url>[^"]+\.(?:png|gif|jpg|jpeg))"',
    re.IGNORECASE,
)
_IMG_HINT = re.compile(r"(cover|box|front|media|screenshot|screen)", re.IGNORECASE)


def _absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return _BASE + "/" + url.lstrip("/")


class RetroCollectorProvider:
    name = "retrocollector"

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
            kind = "cover" if re.search(r"cover|box|front", url, re.IGNORECASE) else "screenshot"
            hint = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            assets.append(ArtworkAsset(url, kind, hint))
        return assets
