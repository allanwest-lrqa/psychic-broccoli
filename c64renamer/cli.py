"""Command-line interface for the C64 file renamer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .config import Config
from .providers import GB64Provider, MobyGamesProvider
from .providers.base import Provider
from . import renamer


def _build_providers(sources: List[str]) -> List[Provider]:
    providers: List[Provider] = []
    if "mobygames" in sources:
        moby = MobyGamesProvider()
        if moby.available():
            providers.append(moby)
        else:
            print(
                "warning: mobygames selected but MOBYGAMES_API_KEY is not set; "
                "skipping it.",
                file=sys.stderr,
            )
    if "gb64" in sources:
        providers.append(GB64Provider())
    return providers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c64renamer",
        description=(
            "Identify Commodore 64 .d64/.t64/.crt files by the game inside "
            "them, rename them with high confidence, and download cover art "
            "and screenshots from MobyGames and gb64.com."
        ),
    )
    parser.add_argument("folder", type=Path, help="folder containing C64 files")
    parser.add_argument(
        "--apply", action="store_true",
        help="actually rename files and download artwork "
             "(default is a dry-run preview)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="descend into subfolders",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=Config.min_confidence,
        metavar="0..1",
        help="minimum match confidence required to rename "
             f"(default {Config.min_confidence})",
    )
    parser.add_argument(
        "--sources", default="mobygames,gb64",
        help="comma-separated providers to use for matching + artwork "
             "(default: mobygames,gb64)",
    )
    parser.add_argument(
        "--no-artwork", action="store_true",
        help="skip downloading cover art and screenshots",
    )
    parser.add_argument(
        "--max-screenshots", type=int, default=Config.max_screenshots,
        help=f"max screenshots to download per game "
             f"(default {Config.max_screenshots}, 0 = unlimited)",
    )
    parser.add_argument(
        "--artwork-dir", type=Path, default=None,
        help="where to save artwork (default: <folder>/artwork)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="only print the final summary",
    )
    return parser


def _print_summary(outcomes: List[renamer.Outcome]) -> None:
    counts: dict = {}
    for o in outcomes:
        counts[o.status] = counts.get(o.status, 0) + 1

    print("\n=== Summary ===")
    for status in (
        renamer.RENAMED, renamer.WOULD_RENAME, renamer.UNMATCHED,
        renamer.SKIPPED, renamer.ERROR,
    ):
        if counts.get(status):
            print(f"  {status:<13}: {counts[status]}")

    interesting = [
        o for o in outcomes
        if o.status in (renamer.RENAMED, renamer.WOULD_RENAME)
    ]
    if interesting:
        print("\nMatches:")
        for o in interesting:
            arrow = "->"
            print(
                f"  {o.path.name} {arrow} {o.new_path.name}  "
                f"[{o.confidence:.0%} via {o.provider}]"
            )

    unmatched = [o for o in outcomes if o.status == renamer.UNMATCHED]
    if unmatched:
        print("\nUnmatched (left untouched):")
        for o in unmatched:
            print(f"  {o.path.name}: {o.message}")


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a directory", file=sys.stderr)
        return 2

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    providers = _build_providers(sources)
    if not providers:
        print(
            "error: no usable providers. Set MOBYGAMES_API_KEY for MobyGames, "
            "or include gb64 in --sources.",
            file=sys.stderr,
        )
        return 2

    config = Config(
        min_confidence=args.min_confidence,
        max_screenshots=args.max_screenshots,
        download_artwork=not args.no_artwork,
        apply=args.apply,
    )

    if not args.apply:
        print("DRY RUN -- no files will be changed. Re-run with --apply to "
              "rename and download.\n")

    progress = None if args.quiet else (lambda msg: print(msg))

    outcomes = renamer.process_directory(
        args.folder,
        providers,
        config,
        recursive=args.recursive,
        artwork_dir=args.artwork_dir,
        progress=progress,
    )

    _print_summary(outcomes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
