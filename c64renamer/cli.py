"""Command-line interface for the C64 file renamer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .config import Config
from .providers import REGISTRY
from .providers.base import Provider
from . import organize as organize_mod
from . import renamer


def _build_providers(sources: List[str]) -> List[Provider]:
    providers: List[Provider] = []
    for name in sources:
        cls = REGISTRY.get(name)
        if cls is None:
            print(f"warning: unknown source '{name}' ignored.", file=sys.stderr)
            continue
        provider = cls()
        if not provider.available():
            print(
                f"warning: source '{name}' selected but not usable "
                "(MobyGames needs MOBYGAMES_API_KEY); skipping it.",
                file=sys.stderr,
            )
            continue
        providers.append(provider)
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
        "--sources", default="mobygames,gb64,c64com,retrocollector",
        help="comma-separated providers for matching + artwork "
             "(mobygames, gb64, c64com, retrocollector)",
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

    org = parser.add_argument_group(
        "organize mode",
        "Build a TheC64/PCUAE-style USB folder tree instead of renaming "
        "in place.",
    )
    org.add_argument(
        "--organize", type=Path, metavar="OUTPUT_DIR", default=None,
        help="organize files into this output folder "
             "(Disks/Tapes/Cartridges + 0-9,A-Z buckets)",
    )
    org.add_argument(
        "--move", action="store_true",
        help="move files into the tree instead of copying (default: copy)",
    )
    org.add_argument(
        "--keep-compilations", action="store_true",
        help="do NOT set multi-game compilations aside",
    )
    org.add_argument(
        "--compilation-entry-threshold", type=int, default=0, metavar="N",
        help="also treat a disk with >= N distinct programs as a compilation "
             "(0 = keyword detection only, the default)",
    )
    org.add_argument(
        "--name-source", choices=["prefer-matched", "matched", "internal"],
        default="prefer-matched",
        help="how to title files: prefer-matched (default), matched-only, "
             "or the name embedded in the file",
    )
    org.add_argument(
        "--allow-duplicates", action="store_true",
        help="keep duplicate games (default: skip duplicates by name and "
             "by identical content)",
    )
    org.add_argument(
        "--verify-names", action="store_true",
        help="only trust names confirmed by a database match; unconfirmed "
             "files go to the Unidentified folder",
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


def _print_organize_summary(outcomes, output_dir: Path) -> None:
    from . import organize as om
    counts: dict = {}
    for o in outcomes:
        counts[o.category] = counts.get(o.category, 0) + 1
    print("\n=== Summary ===")
    for cat in (om.GAME, om.COMPILATION, om.UNIDENTIFIED, om.ERROR):
        if counts.get(cat):
            print(f"  {cat:<13}: {counts[cat]}")
    dupes = sum(1 for o in outcomes if o.action == om.DUPLICATE)
    if dupes:
        print(f"  duplicates skipped: {dupes}")
    art = sum(o.artwork_count for o in outcomes)
    if art:
        print(f"  artwork files: {art}")

    placed = [o for o in outcomes if o.dest and o.action != om.DUPLICATE]
    if placed:
        print(f"\nPlanned into {output_dir}:")
        for o in placed:
            rel = o.dest.relative_to(output_dir)
            tag = f"[{o.confidence:.0%} via {o.provider}]" if o.provider else ""
            art_tag = f" (+{o.artwork_count} art)" if o.artwork_count else ""
            print(f"  {o.src.name}  ->  {rel}  {tag}{art_tag}")
    errors = [o for o in outcomes if o.category == om.ERROR]
    for o in errors:
        print(f"  ERROR {o.src.name}: {o.message}")


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a directory", file=sys.stderr)
        return 2

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    providers = _build_providers(sources)

    # --- Organize mode -------------------------------------------------
    if args.organize is not None:
        cfg = organize_mod.OrganizeConfig(
            output_dir=args.organize,
            action="move" if args.move else "copy",
            apply=args.apply,
            min_confidence=args.min_confidence,
            exclude_compilations=not args.keep_compilations,
            compilation_entry_threshold=args.compilation_entry_threshold,
            name_source=args.name_source,
            verify_names=args.verify_names,
            dedupe=not args.allow_duplicates,
            download_artwork=not args.no_artwork,
            max_screenshots=args.max_screenshots,
        )
        if not args.apply:
            print("DRY RUN -- no files will be written. Re-run with --apply "
                  "to build the folder.\n")
        elif not providers and not args.no_artwork:
            print("note: no online providers active; using names embedded in "
                  "the files, and no artwork can be downloaded.\n")
        progress = None if args.quiet else (lambda msg: print(msg))
        outcomes = organize_mod.organize_directory(
            args.folder, providers, cfg,
            recursive=args.recursive, progress=progress,
        )
        _print_organize_summary(outcomes, args.organize)
        return 0

    # --- Rename-in-place mode -----------------------------------------
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
