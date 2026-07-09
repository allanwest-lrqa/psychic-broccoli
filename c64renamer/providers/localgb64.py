"""Local GameBase64 provider: read the downloaded GB64 database + screenshots.

GameBase64 (https://gb64.com/downloads.php) ships as a GameBase MS Access
``.mdb`` plus a ``Screenshots`` folder. Using it locally gives an authoritative,
offline list of ~28,000 legitimate C64 titles to validate against, and local
artwork with no rate limits or scraping.

The ``.mdb`` is read with the pure-Python ``access-parser`` package (no Access
or ODBC driver required), so it bundles into the standalone Windows exe. The
DB read is isolated in ``_load_games`` and column detection is tolerant, so
schema variations across GameBase versions are handled gracefully.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .. import matching
from .base import ArtworkAsset, GameHit

try:  # optional dependency; only needed to read a real .mdb
    from access_parser import AccessParser
except Exception:  # pragma: no cover - import guarded for environments without it
    AccessParser = None

# Candidate column names across GameBase versions (matched case-insensitively).
_TITLE_COLS = ("name", "ga_name", "title", "game", "gamename")
_FILE_COLS = ("filename", "ga_filename", "file")
_SCREENSHOT_COLS = ("scrnshotfilename", "screenshotfilename", "screenshot",
                    "scrnshot", "scrnshotfile")
_IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg", ".webp")


def _pick(cols: Dict[str, str], candidates) -> Optional[str]:
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    return None


def _load_games(db_path: Path) -> List[dict]:
    """Read the Games table from a GameBase .mdb into simple dict records."""
    if AccessParser is None:
        raise RuntimeError(
            "access-parser is not installed; cannot read the GameBase64 .mdb. "
            "Install it with: pip install access-parser")
    db = AccessParser(str(db_path))
    catalog = getattr(db, "catalog", {}) or {}
    table = next((t for t in catalog if t.lower() == "games"), None)
    if table is None:
        table = "Games"  # last resort; parse_table will raise if truly absent
    data = db.parse_table(table)  # dict: column-name -> list of values

    cols = {c.lower(): c for c in data.keys()}
    title_col = _pick(cols, _TITLE_COLS)
    if not title_col:
        raise RuntimeError(
            "could not find a title column in the Games table; columns are: "
            + ", ".join(data.keys()))
    file_col = _pick(cols, _FILE_COLS)
    scr_col = _pick(cols, _SCREENSHOT_COLS)

    titles = data[title_col]
    files = data.get(file_col, []) if file_col else []
    shots = data.get(scr_col, []) if scr_col else []

    records: List[dict] = []
    for i, raw_title in enumerate(titles):
        if raw_title is None:
            continue
        title = str(raw_title).strip()
        if not title:
            continue
        records.append({
            "title": title,
            "filename": str(files[i]).strip() if i < len(files) and files[i] else "",
            "screenshot": str(shots[i]).strip() if i < len(shots) and shots[i] else "",
        })
    return records


class LocalGB64Provider:
    name = "localgb64"

    def __init__(self, db_path: Optional[Path] = None,
                 screenshots_dir: Optional[Path] = None,
                 min_score: float = 0.55,
                 records: Optional[List[dict]] = None):
        self.db_path = Path(db_path) if db_path else None
        self.screenshots_dir = Path(screenshots_dir) if screenshots_dir else None
        self.min_score = min_score
        self._records = records          # may be injected (tests) or lazy-loaded
        self._titles: List[tuple] = []   # (normalised_title, record)
        self._by_token: Dict[str, set] = {}
        self._loaded = records is not None
        if self._loaded:
            self._build_index()

    # -- availability --------------------------------------------------
    def available(self) -> bool:
        if self._records is not None:
            return True
        return bool(self.db_path and self.db_path.is_file() and AccessParser)

    # -- indexing ------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._records = _load_games(self.db_path)
        self._build_index()
        self._loaded = True

    def _build_index(self) -> None:
        self._titles = []
        self._by_token = {}
        for rec in self._records or []:
            norm = matching.normalize(rec["title"])
            if not norm:
                continue
            idx = len(self._titles)
            self._titles.append((norm, rec))
            for tok in set(norm.split()):
                self._by_token.setdefault(tok, set()).add(idx)

    # -- Provider interface -------------------------------------------
    def search(self, query: str) -> List[GameHit]:
        try:
            self._ensure_loaded()
        except Exception:
            return []
        qn = matching.normalize(query)
        if not qn:
            return []
        # Narrow to titles sharing a token; fall back to a full scan.
        idxs: set = set()
        for tok in qn.split():
            idxs |= self._by_token.get(tok, set())
        if not idxs:
            idxs = set(range(len(self._titles)))

        scored = []
        for i in idxs:
            _norm, rec = self._titles[i]
            score = matching.similarity(query, rec["title"])
            if score >= self.min_score:
                scored.append((score, rec))
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            GameHit(title=rec["title"],
                    game_id=rec.get("filename") or None,
                    extra={"screenshot": rec.get("screenshot", "")})
            for _score, rec in scored[:10]
        ]

    def artwork(self, hit: GameHit) -> List[ArtworkAsset]:
        if not self.screenshots_dir or not self.screenshots_dir.is_dir():
            return []
        rel = (hit.extra or {}).get("screenshot", "")
        assets: List[ArtworkAsset] = []
        for path in self._resolve_screenshots(rel):
            assets.append(ArtworkAsset(url="", kind="screenshot",
                                       filename_hint=path.stem,
                                       local_path=str(path)))
        return assets

    def _resolve_screenshots(self, rel: str) -> List[Path]:
        base = self.screenshots_dir
        found: List[Path] = []
        if rel:
            rel_norm = rel.replace("\\", "/").lstrip("/")
            primary = base / rel_norm
            if primary.is_file():
                found.append(primary)
            else:
                # Match by basename anywhere under the screenshots tree.
                name = Path(rel_norm).name
                found.extend(p for p in base.rglob(name) if p.is_file())
        # Include obvious sibling shots (name_1, name-2, ...) of the primary.
        if found:
            stem = found[0].stem
            for sib in found[0].parent.glob(f"{stem}[ _-]*"):
                if sib.is_file() and sib.suffix.lower() in _IMAGE_EXTS \
                        and sib not in found:
                    found.append(sib)
        return found
