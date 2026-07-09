"""Orchestration: parse files, match against providers, rename, fetch artwork."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import artwork, matching, parsers
from .artwork import safe_name
from .config import Config
from .providers.base import GameHit, Provider

# status values
RENAMED = "renamed"
WOULD_RENAME = "would-rename"
UNMATCHED = "unmatched"
SKIPPED = "skipped"
ERROR = "error"


@dataclass
class Outcome:
    path: Path
    fmt: str = ""
    status: str = SKIPPED
    new_path: Optional[Path] = None
    title: Optional[str] = None
    confidence: float = 0.0
    provider: Optional[str] = None
    candidates: List[str] = field(default_factory=list)
    artwork_files: List[Path] = field(default_factory=list)
    message: str = ""


ProgressFn = Callable[[str], None]


def _identify(
    candidates: List[str],
    providers: List[Provider],
    min_confidence: float,
) -> Tuple[Optional[matching.MatchResult], Optional[Provider], Optional[GameHit]]:
    """Find the best matching game across providers and candidate names.

    Tries candidates highest-weight first and short-circuits as soon as a
    match at or above ``min_confidence`` is found, to limit API calls against
    rate-limited providers.
    """
    best_match: Optional[matching.MatchResult] = None
    best_provider: Optional[Provider] = None
    best_hit: Optional[GameHit] = None

    for candidate in candidates:
        for provider in providers:
            try:
                hits = provider.search(candidate)
            except Exception:
                continue
            if not hits:
                continue

            titles = [h.title for h in hits]
            ranked = matching.rank_titles(candidate, titles)
            if not ranked:
                continue
            top_title, top_score = ranked[0]

            if best_match is None or top_score > best_match.score:
                hit = next((h for h in hits if h.title == top_title), hits[0])
                best_match = matching.MatchResult(
                    title=hit.title,
                    score=top_score,
                    query=candidate,
                    provider=provider.name,
                    game_id=hit.game_id,
                    url=hit.url,
                )
                best_provider = provider
                best_hit = hit

            if best_match and best_match.score >= min_confidence:
                return best_match, best_provider, best_hit

    return best_match, best_provider, best_hit


def _unique_destination(path: Path, title: str) -> Path:
    """Return a non-colliding destination path in ``path``'s directory."""
    ext = path.suffix.lower()
    base = safe_name(title)
    dest = path.with_name(f"{base}{ext}")
    if dest == path or not dest.exists():
        return dest
    counter = 2
    while True:
        dest = path.with_name(f"{base} ({counter}){ext}")
        if not dest.exists():
            return dest
        counter += 1


def process_file(
    path: Path,
    providers: List[Provider],
    config: Config,
    artwork_dir: Optional[Path] = None,
    progress: Optional[ProgressFn] = None,
) -> Outcome:
    def say(msg: str) -> None:
        if progress:
            progress(msg)

    outcome = Outcome(path=path)
    try:
        parsed = parsers.parse(path)
    except parsers.ParseError as exc:
        outcome.status = ERROR
        outcome.message = str(exc)
        return outcome
    except Exception as exc:  # unreadable / corrupt file
        outcome.status = ERROR
        outcome.message = f"failed to read: {exc}"
        return outcome

    outcome.fmt = parsed.fmt
    names = parsed.unique_names()[: config.max_candidates]
    outcome.candidates = names
    say(f"{path.name}: candidates -> {names or '(none)'}")

    if not names:
        outcome.status = UNMATCHED
        outcome.message = parsed.error or "no name found inside file"
        return outcome

    if not providers:
        # Nothing to establish confidence against.
        outcome.status = SKIPPED
        outcome.message = "no providers configured (need MOBYGAMES_API_KEY or gb64)"
        return outcome

    match, provider, hit = _identify(names, providers, config.min_confidence)

    if match is None or match.score < config.min_confidence:
        outcome.status = UNMATCHED
        outcome.confidence = match.score if match else 0.0
        best_title = match.title if match else "-"
        outcome.message = (
            f"best guess '{best_title}' at {outcome.confidence:.0%} "
            f"below threshold {config.min_confidence:.0%}"
        )
        return outcome

    outcome.title = match.title
    outcome.confidence = match.score
    outcome.provider = match.provider

    dest = _unique_destination(path, match.title)
    outcome.new_path = dest

    if dest == path:
        outcome.status = SKIPPED
        outcome.message = "already correctly named"
    elif config.apply:
        path.rename(dest)
        outcome.status = RENAMED
        say(f"  renamed -> {dest.name} ({match.score:.0%} via {match.provider})")
    else:
        outcome.status = WOULD_RENAME
        say(f"  would rename -> {dest.name} ({match.score:.0%} via {match.provider})")

    # --- Artwork -----------------------------------------------------
    if config.download_artwork and provider is not None and hit is not None:
        target_dir = artwork_dir or (path.parent / "artwork")
        if config.apply:
            files = artwork.download_for_game(
                match.title, provider, hit, target_dir,
                max_screenshots=config.max_screenshots,
            )
            outcome.artwork_files = files
            if files:
                say(f"  downloaded {len(files)} artwork file(s)")
        else:
            say(f"  would download artwork to {target_dir / safe_name(match.title)}")

    return outcome


def process_directory(
    folder: Path,
    providers: List[Provider],
    config: Config,
    recursive: bool = False,
    artwork_dir: Optional[Path] = None,
    progress: Optional[ProgressFn] = None,
) -> List[Outcome]:
    pattern = "**/*" if recursive else "*"
    files = sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in parsers.SUPPORTED_EXTENSIONS
    )
    return [
        process_file(p, providers, config, artwork_dir=artwork_dir, progress=progress)
        for p in files
    ]
