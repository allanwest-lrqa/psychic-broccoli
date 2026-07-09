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

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import compilation, matching, parsers, renamer
from .artwork import safe_name
from .multidisk import DiskInfo, format_name, parse_disk_info
from .providers.base import Provider

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
    bucket_ignore_article: bool = True
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
    message: str = ""


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


def _match_candidates(path: Path, parsed: parsers.ParsedFile,
                      max_candidates: int) -> List[str]:
    """Disk-marker-stripped names to try when matching, filename stem first."""
    ordered = [path.stem] + parsed.unique_names()
    out: List[str] = []
    seen = set()
    for name in ordered:
        base = parse_disk_info(name).base
        key = base.lower()
        if base and key not in seen:
            seen.add(key)
            out.append(base)
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

    candidates = _match_candidates(path, parsed, cfg.max_candidates)

    match = provider_name = None
    confidence = 0.0
    canonical: Optional[str] = None
    if providers and candidates:
        match, prov, _hit = renamer.identify(candidates, providers,
                                              cfg.min_confidence)
        if match and match.score >= cfg.min_confidence:
            canonical = match.title
            confidence = match.score
            provider_name = match.provider

    # Decide the title according to the name-source policy. The fallback name
    # prefers the game's own internal name over the (often generic) filename.
    if raw_internal:
        internal_base = parse_disk_info(raw_internal[0]).base
    else:
        internal_base = disk.base or path.stem
    internal_title = matching.clean_title(internal_base)

    if cfg.name_source == "matched":
        title = canonical
    elif cfg.name_source == "internal":
        title = internal_title
    else:  # prefer-matched
        title = canonical or internal_title

    category = GAME
    if verdict.is_compilation and cfg.exclude_compilations:
        category = COMPILATION
    elif not title:
        category = UNIDENTIFIED

    message = verdict.reason if verdict.is_compilation else ""
    return _Record(path, parsed.fmt, ext, category, title, confidence,
                   provider_name, disk, message)


def _place(rec: _Record, cfg: OrganizeConfig, total_by_group: Dict,
           used: set) -> OrganizeOutcome:
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
    filename = safe_name(display) + rec.ext
    dest_dir = cfg.output_dir / top / bucket
    dest = dest_dir / filename

    # Avoid collisions with already-placed files this run and on disk.
    counter = 2
    stem = safe_name(display)
    while str(dest).lower() in used or (dest.exists() and dest != rec.src):
        dest = dest_dir / f"{stem} ({counter}){rec.ext}"
        counter += 1
    used.add(str(dest).lower())
    out.dest = dest

    if not cfg.apply:
        out.action = WOULD_MOVE if cfg.action == "move" else WOULD_COPY
        return out

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

    # Pass 3: place files.
    used: set = set()
    outcomes = []
    for rec in records:
        outcome = _place(rec, cfg, total_by_group, used)
        outcomes.append(outcome)
        if outcome.dest and outcome.action not in (ERROR,):
            rel = outcome.dest.relative_to(cfg.output_dir)
            say(f"  {outcome.action}: {rel}")
        elif outcome.action == ERROR:
            say(f"  ERROR: {outcome.message}")
    return outcomes
