"""c64renamer -- identify and rename Commodore 64 disk/tape/cartridge files.

Parses the game name embedded in .d64/.t64/.crt files, matches it against
online databases (MobyGames, gb64.com) with a confidence threshold, renames
files that match with high confidence, and downloads cover art + screenshots.
"""

from __future__ import annotations

__version__ = "1.0.0"
