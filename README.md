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

## Windows app (just run it)

There is a desktop version with a window — pick a folder, click a button, watch
progress. You can run it two ways:

### Option A — standalone `.exe` (no Python needed)

A GitHub Actions workflow builds a single-file `c64renamer.exe` on a Windows
runner. To get it:

1. Open the **Actions** tab of this repository on GitHub.
2. Click the latest **"Build Windows executable"** run (or press **Run
   workflow** to start one).
3. Download the **`c64renamer-windows`** artifact from that run and unzip it.
4. Double-click **`c64renamer.exe`**.

To build it yourself on a Windows PC instead:

```bat
pip install pyinstaller
pyinstaller --clean --noconfirm c64renamer.spec
rem result: dist\c64renamer.exe
```

### Option B — run from source (if you have Python 3)

Install Python 3 from <https://www.python.org/downloads/> (tick *Add to PATH*),
then double-click **`Run C64 Renamer.bat`**, or run:

```bat
python c64renamer_app.py
```

### Using the window

Enter your MobyGames API key (optional — gb64.com works without one), pick the
games folder, then click **Preview (dry run)** to see what would happen.
**Rename + Download** performs the changes after a confirmation prompt.

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
| `--sources` | Comma-separated providers: `mobygames`, `gb64`, `c64com`, `retrocollector`. |
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

## Organize for TheC64 / PCUAE (USB build)

Instead of renaming files in place, the tool can build a ready-to-copy USB
folder tree for TheC64 (full-size / Maxi) using the PCUAE-style layout: files
sorted into `Disks`, `Tapes` and `Cartridges`, each split into `0-9` and
single-letter `A`–`Z` buckets by title.

```bash
# Preview the tree that would be built (safe):
c64renamer /path/to/games --organize /path/to/USB_build

# Actually build it (copies by default, leaving your originals intact):
c64renamer /path/to/games --organize /path/to/USB_build --apply
```

Resulting structure:

```
USB_build/
  Disks/
    C/Commando.d64
    M/Maniac Mansion (Disk 1 of 2).d64
    M/Maniac Mansion (Disk 2 of 2).d64
  Tapes/
    B/Bruce Lee.t64
  Cartridges/
    0-9/1942.crt
    I/International Karate.crt
  Compilations/        <- multi-game images, set aside
  Unidentified/        <- files that could not be named
```

What it handles:

- **Compilations** (multi-game images) are detected by name keywords
  ("compilation", "collection", "4 in 1", "megamix", …) — including the
  filename, since a D64 disk name is capped at 16 characters — and moved to a
  separate `Compilations/` folder so they are excluded from the clean set.
  Detection favours precision, so genuine single games are not wrongly removed.
- **Multi-disk games** ("(Disk 1 of 2)", "[Side A]", " d2", …) are detected,
  grouped, and named consistently so a set stays together in one bucket.
- **No duplicates** — the same game is copied only once. Duplicates are caught
  both by final name and by identical file content (so `commando.d64` and a
  byte-identical `cmd.d64` collapse to one). Multi-disk members are never
  treated as duplicates. Use `--allow-duplicates` to keep them all.
- **Artwork** — cover art and screenshots for each identified game are
  downloaded into `<output>/Artwork/<Title>/` as part of the build (needs
  online providers). Disable with `--no-artwork`.
- **Copy vs move** — copies by default (`--move` to move).
- Works **offline**: with no online providers it titles files from the name
  embedded in each image; with providers it prefers the confident canonical
  title.

### Organize options

| Option | Description |
| --- | --- |
| `--organize DIR` | Build the USB tree into `DIR` (enables organize mode). |
| `--apply` | Actually write files (default is a dry-run preview). |
| `--move` | Move files into the tree instead of copying. |
| `--keep-compilations` | Do not set compilations aside. |
| `--compilation-entry-threshold N` | Also treat a disk with ≥ N distinct programs as a compilation (0 = keyword-only, default). |
| `--name-source` | `prefer-matched` (default), `matched`, or `internal`. |
| `--allow-duplicates` | Keep duplicate games (default: skip by name and by content). |
| `--no-artwork` | Do not download cover art / screenshots during the build. |
| `--max-screenshots N` | Cap screenshots per game (default `8`). |

In the **Windows app**, set the *Output (USB) folder* and click **Build USB
Folder**.

### Data sources

Matching and artwork can use **MobyGames**, **gb64.com**, **c64.com** and
**retrocollector.org**. MobyGames uses its official API (needs a key); the
others are best-effort scrapers that fail soft.

> **PCUAE Manager database:** importing a generated database into PCUAE Manager
> is planned but not yet implemented — the Manager's exact import format still
> needs to be confirmed. The folder structure above is the deliverable for now.

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
  providers/      mobygames.py, gb64.py, c64com.py, retrocollector.py
  petscii.py      PETSCII/ASCII name decoding
  matching.py     name cleaning + fuzzy confidence scoring
  compilation.py  multi-game compilation detection
  multidisk.py    multi-disk / multi-side detection + naming
  organize.py     build the TheC64/PCUAE USB folder tree
  artwork.py      artwork download + filename sanitising
  renamer.py      orchestration (parse -> match -> rename -> artwork)
  cli.py          command-line interface
  gui.py          Tkinter desktop window
c64renamer_app.py entry point for the GUI and the packaged .exe
c64renamer.spec   PyInstaller build recipe for c64renamer.exe
Run C64 Renamer.bat  double-click launcher (runs from source)
.github/workflows/build-windows.yml  CI that builds the Windows .exe
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
