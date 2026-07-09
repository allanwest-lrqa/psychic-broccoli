"""A simple desktop GUI for c64renamer, built on Tkinter.

Tkinter ships with the standard Python installer on Windows and macOS, so this
window runs with no extra dependencies. It is also what the packaged
``c64renamer.exe`` launches, giving a real "just double-click it" app.

The actual work runs on a background thread so the window stays responsive;
progress lines are handed back to the UI thread through a queue.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import Config
from .providers import REGISTRY
from .providers.base import Provider
from . import organize as organize_mod
from . import renamer


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("C64 Renamer")
        root.minsize(680, 520)

        self._msgs: "queue.Queue" = queue.Queue()
        self._worker: Optional[threading.Thread] = None

        self._build_widgets()
        self._poll_queue()

    # -- layout --------------------------------------------------------
    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(frm, text="Games folder:").grid(row=row, column=0, sticky="w", **pad)
        self.folder_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.folder_var).grid(
            row=row, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Browse…", command=self._browse).grid(
            row=row, column=2, **pad)

        row += 1
        ttk.Label(frm, text="MobyGames API key:").grid(
            row=row, column=0, sticky="w", **pad)
        self.apikey_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.apikey_var, show="•").grid(
            row=row, column=1, columnspan=2, sticky="ew", **pad)

        row += 1
        ttk.Label(frm, text="Output (USB) folder:").grid(
            row=row, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.output_var).grid(
            row=row, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Browse…", command=self._browse_output).grid(
            row=row, column=2, **pad)

        # Options row
        row += 1
        opts = ttk.LabelFrame(frm, text="Options", padding=8)
        opts.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        opts.columnconfigure(5, weight=1)

        self.use_moby = tk.BooleanVar(value=True)
        self.use_gb64 = tk.BooleanVar(value=True)
        self.use_c64com = tk.BooleanVar(value=True)
        self.use_retro = tk.BooleanVar(value=True)
        self.recursive = tk.BooleanVar(value=False)
        self.artwork = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="MobyGames", variable=self.use_moby).grid(
            row=0, column=0, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="gb64.com", variable=self.use_gb64).grid(
            row=0, column=1, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="c64.com", variable=self.use_c64com).grid(
            row=0, column=2, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="retrocollector", variable=self.use_retro).grid(
            row=0, column=3, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="Recursive", variable=self.recursive).grid(
            row=2, column=0, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="Download artwork", variable=self.artwork).grid(
            row=2, column=1, sticky="w", padx=4)

        ttk.Label(opts, text="Confidence:").grid(row=1, column=0, sticky="w", padx=4)
        self.confidence = tk.DoubleVar(value=Config.min_confidence)
        self.conf_label = ttk.Label(opts, text=f"{self.confidence.get():.0%}")
        scale = ttk.Scale(opts, from_=0.5, to=1.0, variable=self.confidence,
                          command=lambda _v: self.conf_label.config(
                              text=f"{self.confidence.get():.0%}"))
        scale.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
        self.conf_label.grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(opts, text="Max screenshots:").grid(
            row=1, column=4, sticky="e", padx=4)
        self.max_shots = tk.IntVar(value=Config.max_screenshots)
        ttk.Spinbox(opts, from_=0, to=50, width=5,
                    textvariable=self.max_shots).grid(row=1, column=5, sticky="w")

        self.exclude_comps = tk.BooleanVar(value=True)
        self.move_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Exclude compilations",
                        variable=self.exclude_comps).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=4)
        ttk.Checkbutton(opts, text="Move (not copy)",
                        variable=self.move_files).grid(
            row=2, column=4, sticky="w", padx=4)

        # Action buttons
        row += 1
        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=3, sticky="ew", **pad)
        self.preview_btn = ttk.Button(
            btns, text="Preview (dry run)",
            command=lambda: self._start(apply=False))
        self.preview_btn.pack(side="left", padx=4)
        self.apply_btn = ttk.Button(
            btns, text="Rename + Download", command=self._confirm_apply)
        self.apply_btn.pack(side="left", padx=4)
        self.organize_btn = ttk.Button(
            btns, text="Build USB Folder", command=self._confirm_organize)
        self.organize_btn.pack(side="left", padx=4)
        self.progress = ttk.Progressbar(btns, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=4)

        # Log
        row += 1
        frm.rowconfigure(row, weight=1)
        log_frame = ttk.Frame(frm)
        log_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", **pad)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=15, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(log_frame, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.config(yscrollcommand=sb.set)

        self._append("Pick a folder of .d64/.t64/.crt files, then Preview.\n")

    # -- helpers -------------------------------------------------------
    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Choose folder of C64 files")
        if folder:
            self.folder_var.set(folder)

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Choose output (USB) folder")
        if folder:
            self.output_var.set(folder)

    def _append(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text if text.endswith("\n") else text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _confirm_apply(self) -> None:
        if messagebox.askyesno(
            "Rename files?",
            "This will rename matching files and download artwork.\n"
            "Files below the confidence threshold are left untouched.\n\nContinue?",
        ):
            self._start(apply=True)

    def _build_providers(self) -> List[Provider]:
        providers: List[Provider] = []
        toggles = [
            ("mobygames", self.use_moby),
            ("gb64", self.use_gb64),
            ("c64com", self.use_c64com),
            ("retrocollector", self.use_retro),
        ]
        for name, var in toggles:
            if not var.get():
                continue
            if name == "mobygames":
                provider = REGISTRY[name](
                    api_key=self.apikey_var.get().strip() or None)
            else:
                provider = REGISTRY[name]()
            if provider.available():
                providers.append(provider)
            elif name == "mobygames":
                self._msgs.put(("log", "  (MobyGames skipped: no API key entered)"))
        return providers

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.preview_btn.config(state=state)
        self.apply_btn.config(state=state)
        self.organize_btn.config(state=state)
        if running:
            self.progress.start(12)
        else:
            self.progress.stop()

    # -- run -----------------------------------------------------------
    def _start(self, apply: bool) -> None:
        if self._worker and self._worker.is_alive():
            return
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("No folder", "Please choose a valid folder.")
            return

        providers = self._build_providers()
        if not providers:
            messagebox.showerror(
                "No providers",
                "Enable MobyGames (with an API key) and/or gb64.com.")
            return

        config = Config(
            min_confidence=float(self.confidence.get()),
            max_screenshots=int(self.max_shots.get()),
            download_artwork=bool(self.artwork.get()),
            apply=apply,
        )

        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self._append("APPLYING changes…" if apply else "DRY RUN — no changes.")
        self._set_running(True)

        self._worker = threading.Thread(
            target=self._work,
            args=(folder, providers, config),
            daemon=True,
        )
        self._worker.start()

    def _work(self, folder, providers, config) -> None:
        try:
            outcomes = renamer.process_directory(
                folder, providers, config,
                recursive=bool(self.recursive.get()),
                progress=lambda m: self._msgs.put(("log", m)),
            )
            self._msgs.put(("summary", outcomes))
        except Exception as exc:  # keep the UI alive on any failure
            self._msgs.put(("log", f"ERROR: {exc}"))
        finally:
            self._msgs.put(("done", None))

    # -- organize (build USB folder) -----------------------------------
    def _confirm_organize(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("No folder", "Please choose a valid games folder.")
            return
        output = Path(self.output_var.get().strip())
        if not self.output_var.get().strip():
            messagebox.showerror("No output", "Please choose an output (USB) folder.")
            return

        action = "move" if self.move_files.get() else "copy"
        verb = "MOVE" if action == "move" else "copy"
        if not messagebox.askyesno(
            "Build USB folder?",
            f"This will {verb} identified games into:\n{output}\n\n"
            "Structure: Disks / Tapes / Cartridges, bucketed 0-9 and A-Z.\n"
            + ("Compilations are set aside.\n" if self.exclude_comps.get() else "")
            + "\nContinue?",
        ):
            return

        cfg = organize_mod.OrganizeConfig(
            output_dir=output,
            action=action,
            apply=True,
            min_confidence=float(self.confidence.get()),
            exclude_compilations=bool(self.exclude_comps.get()),
        )
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self._append(f"Building USB folder at {output} …")
        self._set_running(True)

        self._worker = threading.Thread(
            target=self._work_organize,
            args=(folder, self._build_providers(), cfg),
            daemon=True,
        )
        self._worker.start()

    def _work_organize(self, folder, providers, cfg) -> None:
        try:
            outcomes = organize_mod.organize_directory(
                folder, providers, cfg,
                recursive=bool(self.recursive.get()),
                progress=lambda m: self._msgs.put(("log", m)),
            )
            self._msgs.put(("org_summary", outcomes))
        except Exception as exc:
            self._msgs.put(("log", f"ERROR: {exc}"))
        finally:
            self._msgs.put(("done", None))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._msgs.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "summary":
                    self._print_summary(payload)
                elif kind == "org_summary":
                    self._print_org_summary(payload)
                elif kind == "done":
                    self._set_running(False)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _print_summary(self, outcomes) -> None:
        counts: dict = {}
        for o in outcomes:
            counts[o.status] = counts.get(o.status, 0) + 1
        self._append("\n=== Summary ===")
        for status in (renamer.RENAMED, renamer.WOULD_RENAME, renamer.UNMATCHED,
                       renamer.SKIPPED, renamer.ERROR):
            if counts.get(status):
                self._append(f"  {status}: {counts[status]}")
        for o in outcomes:
            if o.status in (renamer.RENAMED, renamer.WOULD_RENAME):
                self._append(
                    f"  {o.path.name} -> {o.new_path.name} "
                    f"[{o.confidence:.0%} via {o.provider}]")

    def _print_org_summary(self, outcomes) -> None:
        counts: dict = {}
        for o in outcomes:
            counts[o.category] = counts.get(o.category, 0) + 1
        self._append("\n=== Summary ===")
        for cat in (organize_mod.GAME, organize_mod.COMPILATION,
                    organize_mod.UNIDENTIFIED, organize_mod.ERROR):
            if counts.get(cat):
                self._append(f"  {cat}: {counts[cat]}")
        self._append("Done. Copy the output folder's contents to your USB drive.")


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
