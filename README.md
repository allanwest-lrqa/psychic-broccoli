# c64renamer

Identify Commodore 64 disk, tape and cartridge images by the **game inside
them**, rename the files with the real game title — but only when the match is
confident — and download **cover art and screenshots** from
[MobyGames](https://www.mobygames.com/) and [gb64.com](https://gb64.com/)
(GameBase64).

Supports `.d64` (1541 disk images), `.t64` (tape archives) and `.crt`
(cartridges).

## How it works

1. **Parse** each file and read the game name(s) embedded inside it:
   - `.d64` — the disk name from the BAM (track 18, sector 0) plus every
     program name in the directory.
   - `.t64` — the container ("tape") name plus every file record name.
   - `.crt` — the 32-byte cartridge name from the CRT header.
   PETSCII names and padding are decoded and cleaned automatically.
2. **Match** the extracted names against the online databases. Names are
   normalised (cracker tags like `COMMANDO/H`, `+3`, `[E]` are stripped) and
   compared with a fuzzy similarity score.
3. **Rename** a file to the canonical title **only** when the best match meets
   the confidence threshold (default **0.85**). Anything below is left
   untouched and reported, so a bad guess never mangles your collection.
4. **Download** the matched game's cover art and screenshots into an `artwork/`
   folder.

The tool is **dry-run by default** — it shows you exactly what it would do.
Add `--apply` to actually rename files and download artwork.

## Requirements

- Python 3.8 or newer. **No third-party packages** — the core uses only the
  standard library.
- Network access to `mobygames.com` and/or `gb64.com`.
- A **MobyGames API key** to use MobyGames (free — register at
  <https://www.mobygames.com/info/api/>). gb64.com needs no key.

## Install

```bash
# From a clone of this repo
pip install .
# or run without installing:
python -m c64renamer --help
```

## Configuration

Set your MobyGames API key (needed for the MobyGames source):

```bash
export MOBYGAMES_API_KEY="your-key-here"
```

## Usage

```bash
# Preview what would happen (safe, no changes):
c64renamer /path/to/games

# Actually rename files and download artwork:
c64renamer /path/to/games --apply

# Only use gb64.com (no API key needed):
c64renamer /path/to/games --sources gb64 --apply

# Recurse into subfolders, require a higher confidence, skip artwork:
c64renamer /path/to/games -r --min-confidence 0.9 --no-artwork --apply
```

### Options

| Option | Description |
| --- | --- |
| `--apply` | Actually rename + download (default is a dry-run preview). |
| `-r`, `--recursive` | Descend into subfolders. |
| `--min-confidence 0..1` | Confidence required to rename (default `0.85`). |
| `--sources` | Comma-separated providers: `mobygames`, `gb64` (default both). |
| `--no-artwork` | Skip downloading cover art and screenshots. |
| `--max-screenshots N` | Cap screenshots per game (default `8`, `0` = unlimited). |
| `--artwork-dir DIR` | Where to save artwork (default `<folder>/artwork`). |
| `-q`, `--quiet` | Only print the final summary. |

### Example output

```
DRY RUN -- no files will be changed. Re-run with --apply to rename and download.

DISK001.d64: candidates -> ['COMMANDO', 'HISCORE']
  would rename -> Commando.d64 (100% via mobygames)
  would download artwork to /games/artwork/Commando

=== Summary ===
  would-rename : 1
```

Artwork is saved as:

```
<folder>/artwork/<Game Title>/mobygames-cover-01-front.jpg
<folder>/artwork/<Game Title>/mobygames-shot-01.jpg
<folder>/artwork/<Game Title>/gb64-screenshot-01-....png
```

## Confidence & safety

- Files are **never** renamed below the confidence threshold — they are listed
  under "Unmatched (left untouched)" with the best guess and its score.
- Filename collisions get a ` (2)`, ` (3)` … suffix rather than overwriting.
- A file already named correctly is skipped.
- Artwork download failures for a single asset are skipped, never fatal.

## Notes on the providers

- **MobyGames** is accessed through its official JSON API (scraping is not
  permitted). It gives the cleanest canonical titles, so it is preferred for
  matching. The free tier is rate-limited (~1 request/second), which the tool
  respects automatically.
- **gb64.com** has no formal API, so this provider scrapes its public search
  and game pages. The site's markup can change; the extraction patterns live in
  `c64renamer/providers/gb64.py` as clearly-labelled constants and every
  network step fails soft (returns nothing rather than raising) so a markup
  change can never corrupt your collection. For fully offline, rock-solid
  matching you can download the complete GameBase64 dataset from gb64.com and
  back a custom provider with it.

## Project layout

```
c64renamer/
  parsers/        d64.py, t64.py, crt.py  -- read names out of each format
  providers/      mobygames.py, gb64.py   -- search + artwork sources
  petscii.py      PETSCII/ASCII name decoding
  matching.py     name cleaning + fuzzy confidence scoring
  artwork.py      artwork download + filename sanitising
  renamer.py      orchestration (parse -> match -> rename -> artwork)
  cli.py          command-line interface
tests/            offline tests with synthetic .d64/.t64/.crt fixtures
```

## Development

```bash
python -m unittest discover -s tests -v
```

The parsers, matcher and rename logic are fully tested offline using
synthetically generated files — no network required.

## License

MIT
