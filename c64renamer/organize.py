"""Build a TheC64 / PCUAE-style USB folder tree from a pile of C64 files.

Layout produced (top-level folder names and buckets are configurable):

    <output>/Disks/A/Arkanoid.d64
    <output>/Disks/M/Maniac Mansion (Disk 1 of 2).d64
    <output>/Tapes/B/Bruce Lee.t64
    <output>/Cartridges/I/International Karate.crt
    <output>/Compilations/...        (excluded multi-game images)
    <output>/Unidentified/...        (files we could not name)

Originals are copied by default (move is opt-in), so the source folder is safe.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import artwork, compilation, groups, matching, parsers, renamer
from .artwork import safe_name
from .multidisk import DiskInfo, format_name, parse_disk_info
from .providers.base import GameHit, Provider

# Which top-level folder each extension lands in.
DEFAULT_TYPE_FOLDERS: Dict[str, str] = {
    ".d64": "Disks",
    ".t64": "Tapes",
    ".crt": "Cartridges",
}

_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)

# action / category constants
COPIED = "copied"
MOVED = "moved"
WOULD_COPY = "would-copy"
WOULD_MOVE = "would-move"
SKIPPED = "skipped"
DUPLICATE = "duplicate"
ERROR = "error"

GAME = "game"
COMPILATION = "compilation"
UNIDENTIFIED = "unidentified"


@dataclass
class OrganizeConfig:
    output_dir: Path
    action: str = "copy"                 # "copy" | "move"
    apply: bool = False                  # dry-run unless True
    min_confidence: float = 0.85
    max_candidates: int = 5
    exclude_compilations: bool = True
    compilation_entry_threshold: int = 0
    name_source: str = "prefer-matched"  # prefer-matched | matched | internal
    verify_names: bool = False           # require a database match to trust a name
    bucket_ignore_article: bool = True
    dedupe: bool = True                  # skip duplicate games
    dedupe_by_content: bool = True       # also skip byte-identical files
    download_artwork: bool = False       # fetch cover/screenshots per game
    max_screenshots: int = 8
    artwork_folder: str = "Artwork"
    type_folders: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_TYPE_FOLDERS))
    compilations_folder: str = "Compilations"
    unidentified_folder: str = "Unidentified"


@dataclass
class OrganizeOutcome:
    src: Path
    fmt: str = ""
    category: str = UNIDENTIFIED
    title: Optional[str] = None
    dest: Optional[Path] = None
    confidence: float = 0.0
    provider: Optional[str] = None
    disk_label: str = ""
    action: str = SKIPPED
    artwork_count: int = 0
    message: str = ""


# Intermediate record between the analysis pass and the placement pass.
@dataclass
class _Record:
    src: Path
    fmt: str
    ext: str
    category: str
    title: Optional[str]
    confidence: float
    provider: Optional[str]
    disk: DiskInfo
    provider_obj: Optional[Provider] = None
    hit: Optional[GameHit] = None
    message: str = ""


def _file_hash(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


ProgressFn = Callable[[str], None]


def bucket_for(title: str, ignore_article: bool = True) -> str:
    """Return the alphabetical bucket ("0-9" or "A".."Z") for a title."""
    text = title
    if ignore_article:
        text = _LEADING_ARTICLE.sub("", text)
    for ch in text:
        if ch.isalpha():
            return ch.upper()
        if ch.isdigit():
            return "0-9"
    return "0-9"


def _candidate_titles(path: Path, parsed: parsers.ParsedFile,
                      max_candidates: int) -> List[str]:
    """Cleaned, de-duplicated candidate titles, best first.

    Internal names first (they are usually the game's own name), then the
    filename stem as a fallback. Disk markers and cracker/hack tags are
    stripped, and names that are actually cracker/demo group names
    ("FAIRLIGHT", "THE OUG-TEAM") are dropped so they never become the title.
    """
    ordered = parsed.unique_names() + [path.stem]
    out: List[str] = []
    seen = set()
    for name in ordered:
        if groups.is_group(name):
            continue
        base = parse_disk_info(name).base
        title = matching.clean_title(base)
        key = matching.normalize(title)
        if not title or not key or groups.is_group(title) or key in seen:
            continue
        seen.add(key)
        out.append(title)
    return out[:max_candidates]


def _analyse(path: Path, providers: List[Provider],
             cfg: OrganizeConfig) -> _Record:
    ext = path.suffix.lower()
    try:
        parsed = parsers.parse(path)
    except Exception as exc:
        return _Record(path, "", ext, ERROR, None, 0.0, None,
                       DiskInfo(base=path.stem), f"parse failed: {exc}")

    raw_internal = parsed.unique_names()

    # Disk/side marker usually lives in the filename; fall back to the
    # internal name if the filename has none.
    disk = parse_disk_info(path.stem)
    if not disk.is_multi and raw_internal:
        alt = parse_disk_info(raw_internal[0])
        if alt.is_multi:
            disk = alt

    verdict = compilation.detect(parsed, cfg.compilation_entry_threshold,
                                 extra_names=[path.stem])

    candidates = _candidate_titles(path, parsed, cfg.max_candidates)

    match = provider_name = None
    provider_obj = hit = None
    confidence = 0.0
    canonical: Optional[str] = None
    if providers and candidates:
        match, prov, found = renamer.identify(candidates, providers,
                                              cfg.min_confidence)
        if match and match.score >= cfg.min_confidence:
            canonical = match.title
            confidence = match.score
            provider_name = match.provider
            provider_obj = prov
            hit = found

    # The fallback title is the best cleaned, non-group internal candidate.
    internal_title = candidates[0] if candidates else None

    if cfg.name_source == "matched":
        title = canonical
    elif cfg.name_source == "internal":
        title = internal_title
    else:  # prefer-matched
        title = canonical or internal_title

    category = GAME
    message = verdict.reason if verdict.is_compilation else ""
    if verdict.is_compilation and cfg.exclude_compilations:
        category = COMPILATION
    elif not title:
        category = UNIDENTIFIED
    elif cfg.verify_names and not canonical:
        # Strict mode: only trust names confirmed by a database match.
        category = UNIDENTIFIED
        message = "name not confirmed by a database"
    return _Record(path, parsed.fmt, ext, category, title, confidence,
                   provider_name, disk, provider_obj=provider_obj, hit=hit,
                   message=message)


def _place(rec: _Record, cfg: OrganizeConfig, total_by_group: Dict,
           state: Dict) -> OrganizeOutcome:
    out = OrganizeOutcome(
        src=rec.src, fmt=rec.fmt, category=rec.category, title=rec.title,
        confidence=rec.confidence, provider=rec.provider,
        disk_label=rec.disk.label, message=rec.message,
    )
    if rec.category == ERROR:
        out.action = ERROR
        return out

    # Work out the destination folder.
    if rec.category == COMPILATION:
        top = cfg.compilations_folder
    elif rec.category == UNIDENTIFIED:
        top = cfg.unidentified_folder
    else:
        top = cfg.type_folders.get(rec.ext, "Other")

    if rec.category == UNIDENTIFIED or not rec.title:
        # Keep the original name; bucket by it.
        display = rec.src.stem
    else:
        group_key = (rec.ext, matching.normalize(rec.title))
        total_override = total_by_group.get(group_key)
        display = format_name(rec.title, rec.disk, total_override)

    bucket = bucket_for(display, cfg.bucket_ignore_article)
    stem = safe_name(display)
    dest_dir = cfg.output_dir / top / bucket
    dest = dest_dir / f"{stem}{rec.ext}"
    dest_key = str(dest).lower()

    # --- De-duplication ------------------------------------------------
    if cfg.dedupe:
        # Byte-identical file already placed (even under a different name).
        # Skipped for multi-disk members: different disks can be identical
        # dumps yet must both be kept, so they rely on name-dedup instead.
        if cfg.dedupe_by_content and not rec.disk.is_multi:
            try:
                digest = _file_hash(rec.src)
            except OSError:
                digest = None
            if digest and digest in state["hashes"]:
                out.action = DUPLICATE
                out.message = "duplicate content already placed"
                return out
        else:
            digest = None
        # Same destination name already taken this run or present on the USB.
        if dest_key in state["names"] or (dest.exists() and dest != rec.src):
            out.action = DUPLICATE
            out.dest = dest
            out.message = "already present"
            return out
    else:
        digest = None
        counter = 2
        while dest_key in state["names"] or (dest.exists() and dest != rec.src):
            dest = dest_dir / f"{stem} ({counter}){rec.ext}"
            dest_key = str(dest).lower()
            counter += 1

    state["names"].add(dest_key)
    if digest:
        state["hashes"].add(digest)
    out.dest = dest

    if not cfg.apply:
        out.action = WOULD_MOVE if cfg.action == "move" else WOULD_COPY
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            if cfg.action == "move":
                shutil.move(str(rec.src), str(dest))
                out.action = MOVED
            else:
                shutil.copy2(str(rec.src), str(dest))
                out.action = COPIED
        except Exception as exc:
            out.action = ERROR
            out.message = f"{cfg.action} failed: {exc}"
            return out

    # --- Artwork -------------------------------------------------------
    if (cfg.download_artwork and cfg.apply and rec.category == GAME
            and rec.title and rec.provider_obj and rec.hit):
        title_key = matching.normalize(rec.title)
        if title_key not in state["arted"]:
            state["arted"].add(title_key)
            try:
                files = artwork.download_for_game(
                    rec.title, rec.provider_obj, rec.hit,
                    cfg.output_dir / cfg.artwork_folder,
                    max_screenshots=cfg.max_screenshots,
                )
                out.artwork_count = len(files)
            except Exception:
                out.artwork_count = 0
    return out


def organize_directory(
    folder: Path,
    providers: List[Provider],
    cfg: OrganizeConfig,
    recursive: bool = False,
    progress: Optional[ProgressFn] = None,
) -> List[OrganizeOutcome]:
    def say(msg: str) -> None:
        if progress:
            progress(msg)

    pattern = "**/*" if recursive else "*"
    files = sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in parsers.SUPPORTED_EXTENSIONS
    )

    # Pass 1: analyse every file.
    records: List[_Record] = []
    for path in files:
        rec = _analyse(path, providers, cfg)
        records.append(rec)
        say(f"{path.name}: {rec.category}"
            + (f" '{rec.title}'" if rec.title else "")
            + (f" [{rec.disk.label}]" if rec.disk.is_multi else ""))

    # Pass 2: for multi-disk sets, learn each group's disk count.
    total_by_group: Dict = {}
    for rec in records:
        if rec.category == GAME and rec.disk.is_multi and rec.title:
            key = (rec.ext, matching.normalize(rec.title))
            best = max(rec.disk.index or 0, rec.disk.total or 0)
            total_by_group[key] = max(total_by_group.get(key, 0), best)

    # Pass 3: place files. `state` carries de-dup memory across the batch.
    state: Dict = {"names": set(), "hashes": set(), "arted": set()}
    outcomes = []
    for rec in records:
        outcome = _place(rec, cfg, total_by_group, state)
        outcomes.append(outcome)
        if outcome.action == DUPLICATE:
            say(f"  duplicate skipped: {rec.src.name} ({outcome.message})")
        elif outcome.action == ERROR:
            say(f"  ERROR: {outcome.message}")
        elif outcome.dest:
            rel = outcome.dest.relative_to(cfg.output_dir)
            extra = (f"  (+{outcome.artwork_count} artwork)"
                     if outcome.artwork_count else "")
            say(f"  {outcome.action}: {rel}{extra}")
    return outcomes
