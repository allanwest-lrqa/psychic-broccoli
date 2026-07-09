"""Entry point for the desktop app and the packaged Windows executable.

Double-clicking ``c64renamer.exe`` (or running this file with pythonw) opens
the GUI. This thin wrapper exists so PyInstaller has a single, import-safe
script to bundle.
"""

from c64renamer.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
