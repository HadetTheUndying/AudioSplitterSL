#!/usr/bin/env python3
"""
AudioSplitter - Download/open audio or video, extract audio, split into chunks
Requires: ffmpeg
Optional: yt-dlp (for URL downloads)
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import subprocess
import sys
import os
import re
import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False

# ── Colours — Gruvbox Dark ────────────────────────────────────────────────────
# bg0_h / bg0 / bg1 / bg2 for depth layers
BG          = "#1d2021"   # bg0_h  — darkest background
SURFACE     = "#282828"   # bg0    — main surface
SURFACE2    = "#3c3836"   # bg1    — raised elements / inputs
BORDER      = "#504945"   # bg2    — borders / dividers
ACCENT      = "#d79921"   # yellow — primary accent
ACCENT_DIM  = "#b57614"   # yellow dim — hover / active
SUCCESS     = "#98971a"   # green
WARNING     = "#d65d0e"   # orange
ERROR       = "#cc241d"   # red
TEXT        = "#ebdbb2"   # fg1    — primary text
TEXT_DIM    = "#a89984"   # fg4    — muted text

DEFAULT_CHUNK_SEC = 29.9
CONFIG_FILE       = Path.home() / ".audiosplitter_config.json"

FALLBACK_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
]

# Supported local file extensions
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}
ALL_EXTS   = AUDIO_EXTS | VIDEO_EXTS


def probe_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for base in FALLBACK_PATHS:
        candidate = Path(base) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return ""


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(data: dict):
    try:
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────

class AudioSplitterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AudioSplitter")
        self.geometry("780x780")
        self.minsize(640, 660)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._output_dir = Path.home() / "AudioSplitter"
        self._running    = False
        self._thread     = None
        self._mode       = tk.StringVar(value="url")  # "url" or "file"

        cfg = load_config()
        self._ytdlp_path  = cfg.get("ytdlp_path",  probe_binary("yt-dlp"))
        self._ffmpeg_path = cfg.get("ffmpeg_path",  probe_binary("ffmpeg"))

        self._build_ui()
        self._check_deps()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Title bar ──
        header = tk.Frame(self, bg=BG, pady=18)
        header.pack(fill="x", padx=30)
        tk.Label(header, text="AUDIO",    font=("Courier", 22, "bold"), fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(header, text="SPLITTER", font=("Courier", 22, "bold"), fg=TEXT,   bg=BG).pack(side="left")
        tk.Label(header, text="  ·  yt-dlp + ffmpeg",
                 font=("Courier", 10), fg=TEXT_DIM, bg=BG).pack(side="left", padx=(8, 0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30)

        # ── Main card ──
        card = tk.Frame(self, bg=SURFACE, bd=0, padx=24, pady=20)
        card.pack(fill="x", padx=30, pady=(16, 0))

        # ── Mode toggle ──
        mode_row = tk.Frame(card, bg=SURFACE)
        mode_row.pack(fill="x", pady=(0, 14))

        self.btn_mode_url = tk.Button(
            mode_row, text="🌐  URL", font=("Courier", 10, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=6,
            command=lambda: self._set_mode("url")
        )
        self.btn_mode_url.pack(side="left", padx=(0, 6))

        self.btn_mode_file = tk.Button(
            mode_row, text="📂  Local File", font=("Courier", 10, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=6,
            command=lambda: self._set_mode("file")
        )
        self.btn_mode_file.pack(side="left")

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # ── URL input (shown in URL mode) ──
        self.url_frame = tk.Frame(card, bg=SURFACE)
        self.url_frame.pack(fill="x")

        tk.Label(self.url_frame, text="VIDEO URL", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")

        url_row = tk.Frame(self.url_frame, bg=SURFACE)
        url_row.pack(fill="x", pady=(4, 0))

        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(
            url_row, textvariable=self.url_var,
            font=("Courier", 12), bg=SURFACE2, fg=TEXT,
            insertbackground=ACCENT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT
        )
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        self.url_entry.bind("<Return>", lambda e: self._start())
        tk.Button(url_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.url_var.set(""), padx=10).pack(side="left")

        # ── Local file input (shown in file mode) ──
        self.file_frame = tk.Frame(card, bg=SURFACE)
        # Not packed yet — shown when mode switches

        tk.Label(self.file_frame, text="LOCAL FILE", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")

        file_row = tk.Frame(self.file_frame, bg=SURFACE)
        file_row.pack(fill="x", pady=(4, 0))

        self.file_var = tk.StringVar()
        self.file_entry = tk.Entry(
            file_row, textvariable=self.file_var,
            font=("Courier", 11), bg=SURFACE2, fg=TEXT_DIM,
            relief="flat", state="readonly",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT
        )
        self.file_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(file_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=TEXT, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=ACCENT,
                  command=self._browse_file, padx=12, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(file_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.file_var.set(""), padx=10).pack(side="left")

        tk.Label(self.file_frame,
                 text="Supported: mp3, wav, aac, flac, ogg, m4a, opus, mp4, mkv, mov, avi, webm…",
                 font=("Courier", 8), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(6, 0))

        # OUTPUT FOLDER
        tk.Label(card, text="OUTPUT FOLDER", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(14, 0))

        dir_row = tk.Frame(card, bg=SURFACE)
        dir_row.pack(fill="x", pady=(4, 0))

        self.dir_var = tk.StringVar(value=str(self._output_dir))
        tk.Entry(dir_row, textvariable=self.dir_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT_DIM,
                 relief="flat", state="readonly",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(dir_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=TEXT, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=ACCENT,
                  command=self._browse_output, padx=12, pady=4).pack(side="left")

        # CHUNK LENGTH
        tk.Label(card, text="CHUNK LENGTH (seconds)", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(14, 0))

        chunk_row = tk.Frame(card, bg=SURFACE)
        chunk_row.pack(fill="x", pady=(4, 0))

        self.chunk_var = tk.StringVar(value=str(DEFAULT_CHUNK_SEC))
        tk.Entry(chunk_row, textvariable=self.chunk_var,
                 font=("Courier", 12), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, width=10
                 ).pack(side="left", ipady=8, padx=(0, 14))

        for label, val in [("15 s", "15"), ("29.9 s", "29.9"), ("30 s", "30"), ("60 s", "60")]:
            tk.Button(chunk_row, text=label, font=("Courier", 10),
                      bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                      activebackground=BORDER, activeforeground=ACCENT,
                      command=lambda v=val: self.chunk_var.set(v),
                      padx=10, pady=4).pack(side="left", padx=(0, 6))

        tk.Label(chunk_row, text="seconds per chunk",
                 font=("Courier", 9), fg=TEXT_DIM, bg=SURFACE).pack(side="left", padx=(6, 0))

        # ── Tools config card ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(14, 0))

        tools_header = tk.Frame(self, bg=BG, pady=6)
        tools_header.pack(fill="x", padx=30)
        tk.Label(tools_header, text="TOOL PATHS", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")

        tools_card = tk.Frame(self, bg=SURFACE, bd=0, padx=24, pady=16)
        tools_card.pack(fill="x", padx=30)

        # yt-dlp path
        tk.Label(tools_card, text="YT-DLP PATH", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        ytdlp_row = tk.Frame(tools_card, bg=SURFACE)
        ytdlp_row.pack(fill="x", pady=(4, 0))
        self.ytdlp_var = tk.StringVar(value=self._ytdlp_path)
        tk.Entry(ytdlp_row, textvariable=self.ytdlp_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(ytdlp_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=TEXT, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=ACCENT,
                  command=lambda: self._browse_binary(self.ytdlp_var),
                  padx=12, pady=4).pack(side="left", padx=(0, 6))
        self.ytdlp_status = tk.Label(ytdlp_row, text="", font=("Courier", 14), bg=SURFACE, width=2)
        self.ytdlp_status.pack(side="left")

        # ffmpeg path
        tk.Label(tools_card, text="FFMPEG PATH", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(12, 0))
        ffmpeg_row = tk.Frame(tools_card, bg=SURFACE)
        ffmpeg_row.pack(fill="x", pady=(4, 0))
        self.ffmpeg_var = tk.StringVar(value=self._ffmpeg_path)
        tk.Entry(ffmpeg_row, textvariable=self.ffmpeg_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(ffmpeg_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=TEXT, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=ACCENT,
                  command=lambda: self._browse_binary(self.ffmpeg_var),
                  padx=12, pady=4).pack(side="left", padx=(0, 6))
        self.ffmpeg_status = tk.Label(ffmpeg_row, text="", font=("Courier", 14), bg=SURFACE, width=2)
        self.ffmpeg_status.pack(side="left")

        save_row = tk.Frame(tools_card, bg=SURFACE)
        save_row.pack(fill="x", pady=(10, 0))
        tk.Button(save_row, text="✓  Verify & Save Paths", font=("Courier", 10),
                  bg=SURFACE2, fg=ACCENT, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=ACCENT,
                  command=self._verify_and_save_paths,
                  padx=14, pady=6).pack(side="left")

        # ── Action buttons ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=30, pady=14)

        self.btn_start = tk.Button(
            btn_row, text="▶  DOWNLOAD & SPLIT",
            font=("Courier", 12, "bold"),
            bg=ACCENT, fg="#1d2021", relief="flat", cursor="hand2",
            activebackground=ACCENT_DIM, activeforeground="#1d2021",
            command=self._start, padx=20, pady=10
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = tk.Button(
            btn_row, text="■  STOP",
            font=("Courier", 12, "bold"),
            bg=SURFACE2, fg=ERROR, relief="flat", cursor="hand2",
            activebackground=BORDER, activeforeground=ERROR,
            command=self._stop, padx=20, pady=10, state="disabled"
        )
        self.btn_stop.pack(side="left")

        tk.Button(btn_row, text="📁  Open Folder",
                  font=("Courier", 10), bg=SURFACE, fg=TEXT_DIM,
                  relief="flat", cursor="hand2",
                  activebackground=SURFACE2, activeforeground=TEXT,
                  command=self._open_folder, padx=14, pady=10).pack(side="right")

        # ── Progress bar ──
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=30)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("AS.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        self.progress = ttk.Progressbar(prog_frame, mode="indeterminate",
                                        length=300, style="AS.Horizontal.TProgressbar")
        self.progress.pack(fill="x")

        # ── Status label ──
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = tk.Label(self, textvariable=self.status_var,
                                     font=("Courier", 10), fg=TEXT_DIM, bg=BG, anchor="w")
        self.status_label.pack(fill="x", padx=32, pady=(6, 0))

        # ── Log console ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(10, 0))
        log_header = tk.Frame(self, bg=BG, pady=6)
        log_header.pack(fill="x", padx=30)
        tk.Label(log_header, text="LOG", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        tk.Button(log_header, text="Clear", font=("Courier", 9),
                  bg=BG, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=SURFACE, activeforeground=TEXT,
                  command=self._clear_log).pack(side="right")

        self.log = scrolledtext.ScrolledText(
            self, font=("Courier", 10), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            state="disabled", wrap="word", padx=12, pady=10
        )
        self.log.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        for tag, colour in [("info", TEXT), ("success", SUCCESS), ("warning", WARNING),
                             ("error", ERROR), ("dim", TEXT_DIM), ("accent", ACCENT)]:
            self.log.tag_config(tag, foreground=colour)

        # Apply initial mode styling
        self._set_mode("url")

    # ── Mode toggle ───────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode.set(mode)
        if mode == "url":
            self.btn_mode_url.config(bg=ACCENT, fg="#1d2021",
                                     activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.btn_mode_file.config(bg=SURFACE2, fg=TEXT_DIM,
                                      activebackground=BORDER, activeforeground=TEXT)
            self.file_frame.pack_forget()
            self.url_frame.pack(fill="x")
            self.btn_start.config(text="▶  DOWNLOAD & SPLIT")
        else:
            self.btn_mode_file.config(bg=ACCENT, fg="#1d2021",
                                      activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.btn_mode_url.config(bg=SURFACE2, fg=TEXT_DIM,
                                     activebackground=BORDER, activeforeground=TEXT)
            self.url_frame.pack_forget()
            self.file_frame.pack(fill="x")
            self.btn_start.config(text="▶  SPLIT FILE")

    # ── Dependency check ─────────────────────────────────────────────────────

    def _check_deps(self):
        ok = True
        ytdlp_path = self.ytdlp_var.get().strip()
        ytdlp_ok = YT_DLP_AVAILABLE or (bool(ytdlp_path) and Path(ytdlp_path).is_file())
        self._set_indicator(self.ytdlp_status, ytdlp_ok)
        if ytdlp_ok:
            src = "Python lib" if YT_DLP_AVAILABLE else ytdlp_path
            self._log(f"✓ yt-dlp detected ({src})  [required for URL mode]", "success")
        else:
            self._log("⚠ yt-dlp not found — URL mode unavailable. Local file mode still works.", "warning")

        ffmpeg_path = self.ffmpeg_var.get().strip()
        ffmpeg_ok = bool(ffmpeg_path) and Path(ffmpeg_path).is_file()
        self._set_indicator(self.ffmpeg_status, ffmpeg_ok)
        if ffmpeg_ok:
            self._log(f"✓ ffmpeg detected ({ffmpeg_path})", "success")
        else:
            self._log("✗ ffmpeg not found. Set path in Tool Paths section below.", "error")
            ok = False

        if ok:
            self._log("Ready. Paste a URL or pick a local file, then press the button.", "dim")
        else:
            self._set_status("Missing dependencies — see log.", ERROR)
            self.btn_start.config(state="disabled")

    # ── Path helpers ──────────────────────────────────────────────────────────

    def _browse_binary(self, var: tk.StringVar):
        initial = str(Path(var.get()).parent) if var.get() else "/opt/homebrew/bin"
        path = filedialog.askopenfilename(initialdir=initial, title="Select executable")
        if path:
            var.set(path)

    def _browse_file(self):
        exts = " ".join(f"*{e}" for e in sorted(ALL_EXTS))
        path = filedialog.askopenfilename(
            title="Select audio or video file",
            filetypes=[("Audio / Video files", exts), ("All files", "*.*")]
        )
        if path:
            self.file_var.set(path)
            # Auto-set output folder to same directory as the file
            self.dir_var.set(str(Path(path).parent))

    def _set_indicator(self, label: tk.Label, ok: bool):
        self.after(0, lambda: label.config(text="✓" if ok else "✗",
                                           fg=SUCCESS if ok else ERROR))

    def _verify_and_save_paths(self):
        ytdlp  = self.ytdlp_var.get().strip()
        ffmpeg = self.ffmpeg_var.get().strip()
        all_ok = True

        ytdlp_ok = YT_DLP_AVAILABLE or (bool(ytdlp) and Path(ytdlp).is_file())
        self._set_indicator(self.ytdlp_status, ytdlp_ok)
        if ytdlp_ok:
            self._log(f"✓ yt-dlp path verified: {ytdlp or 'Python lib'}", "success")
        else:
            self._log(f"⚠ yt-dlp not found at: {ytdlp} — URL mode will be unavailable", "warning")

        ffmpeg_ok = bool(ffmpeg) and Path(ffmpeg).is_file() and os.access(ffmpeg, os.X_OK)
        self._set_indicator(self.ffmpeg_status, ffmpeg_ok)
        if ffmpeg_ok:
            self._log(f"✓ ffmpeg path verified: {ffmpeg}", "success")
        else:
            self._log(f"✗ ffmpeg not found or not executable at: {ffmpeg}", "error")
            all_ok = False

        if all_ok:
            save_config({"ytdlp_path": ytdlp, "ffmpeg_path": ffmpeg})
            self._log("Paths saved to ~/.audiosplitter_config.json", "dim")
            self._set_status("Paths verified and saved.", SUCCESS)
            self.btn_start.config(state="normal")
        else:
            self._set_status("Fix tool paths before continuing.", ERROR)
            self.btn_start.config(state="disabled")

    # ── General helpers ───────────────────────────────────────────────────────

    def _log(self, msg: str, tag: str = "info"):
        def _append():
            self.log.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log.insert("end", f"[{ts}] ", "dim")
            self.log.insert("end", msg + "\n", tag)
            self.log.see("end")
            self.log.config(state="disabled")
        self.after(0, _append)

    def _set_status(self, msg: str, colour: str = TEXT_DIM):
        self.after(0, lambda: (
            self.status_var.set(msg),
            self.status_label.config(fg=colour)
        ))

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _browse_output(self):
        d = filedialog.askdirectory(initialdir=str(self._output_dir))
        if d:
            self._output_dir = Path(d)
            self.dir_var.set(d)

    def _open_folder(self):
        p = Path(self.dir_var.get())
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])

    # ── Worker thread ─────────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return

        try:
            chunk_sec = float(self.chunk_var.get().strip())
            if chunk_sec <= 0:
                raise ValueError
        except ValueError:
            self._log("Invalid chunk length — please enter a positive number.", "error")
            return

        mode       = self._mode.get()
        ytdlp_path = self.ytdlp_var.get().strip()
        ffmpeg_path = self.ffmpeg_var.get().strip()

        if mode == "url":
            url = self.url_var.get().strip()
            if not url:
                self._log("Please enter a URL first.", "warning")
                return
            local_file = None
        else:
            local_file = self.file_var.get().strip()
            if not local_file:
                self._log("Please select a local file first.", "warning")
                return
            if not Path(local_file).exists():
                self._log(f"File not found: {local_file}", "error")
                return
            url = None

        self._running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress.start(12)

        self._thread = threading.Thread(
            target=self._run,
            args=(url, local_file, chunk_sec, ytdlp_path, ffmpeg_path),
            daemon=True
        )
        self._thread.start()

    def _stop(self):
        self._running = False
        self._log("Stop requested — will halt after current step.", "warning")

    def _finish(self, success: bool):
        def _upd():
            self.progress.stop()
            self.progress["value"] = 0
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self._running = False
        self.after(0, _upd)

    def _run(self, url, local_file, chunk_sec, ytdlp_path, ffmpeg_path):
        """Full pipeline. local_file skips download; url triggers yt-dlp."""
        out_root = Path(self.dir_var.get())
        out_root.mkdir(parents=True, exist_ok=True)

        def sanitise(s):
            return re.sub(r'[\\/*?:"<>|]', "_", s)[:80]

        # ── 1. Resolve source file ────────────────────────────────────────────
        if local_file:
            # Local file — skip download entirely
            source = Path(local_file)
            title  = sanitise(source.stem)
            self._log(f"Using local file: {source.name}", "accent")
            self._set_status("Using local file…")
            download_path = source
        else:
            # URL — download with yt-dlp
            self._log(f"Fetching info for: {url}", "accent")
            self._set_status("Downloading video…")
            download_path = None

            try:
                if YT_DLP_AVAILABLE:
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                        info  = ydl.extract_info(url, download=False)
                        title = sanitise(info.get("title", "audio"))

                    video_file = out_root / f"{title}.%(ext)s"
                    ydl_opts = {
                        "outtmpl":        str(video_file),
                        "format":         "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                        "quiet":          False,
                        "no_warnings":    True,
                        "progress_hooks": [self._ydl_hook],
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        download_path = Path(ydl.prepare_filename(info))
                else:
                    if not ytdlp_path or not Path(ytdlp_path).is_file():
                        self._log("yt-dlp binary not found. Set path in Tool Paths.", "error")
                        self._finish(False)
                        return

                    result = subprocess.run(
                        [ytdlp_path, "--get-title", "--no-warnings", url],
                        capture_output=True, text=True
                    )
                    title      = sanitise(result.stdout.strip() or "audio")
                    video_file = out_root / f"{title}.%(ext)s"

                    proc = subprocess.Popen(
                        [ytdlp_path, "-o", str(video_file),
                         "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                         "--no-warnings", url],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace"
                    )
                    for line in proc.stdout:
                        line = line.rstrip()
                        if "[download]" in line or "Destination" in line:
                            self.after(0, lambda l=line: self.status_var.set(l[:90]))
                        if "Destination:" in line:
                            m = re.search(r"Destination: (.+)$", line)
                            if m:
                                download_path = Path(m.group(1).strip())
                    proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError("yt-dlp exited with error")

                    if download_path is None or not download_path.exists():
                        candidates = [p for p in out_root.glob(f"{title}.*")
                                      if p.suffix not in (".wav", ".json")]
                        if candidates:
                            download_path = max(candidates, key=lambda p: p.stat().st_mtime)

                if not self._running:
                    self._log("Download cancelled.", "warning")
                    self._finish(False)
                    return

                if download_path is None or not download_path.exists():
                    raise RuntimeError(f"Downloaded file not found: {download_path}")

                self._log(f"Download complete → {download_path.name}", "success")

            except Exception as e:
                self._log(f"Download failed: {e}", "error")
                self._set_status("Download failed.", ERROR)
                self._finish(False)
                return

        # ── 2. Extract audio to WAV ───────────────────────────────────────────
        self._set_status("Extracting audio…")
        self._log("Extracting audio track…", "accent")

        audio_file = out_root / f"{title}_audio.wav"
        cmd = [
            ffmpeg_path, "-y", "-i", str(download_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(audio_file)
        ]
        ret = self._run_ffmpeg(cmd, ffmpeg_path)
        if ret != 0 or not self._running:
            if not self._running:
                self._log("Cancelled during audio extraction.", "warning")
            self._finish(False)
            return

        self._log(f"Audio extracted → {audio_file.name}", "success")

        # ── 3. Split into chunks ──────────────────────────────────────────────
        self._set_status(f"Splitting into {chunk_sec}s chunks…")
        self._log(f"Splitting into {chunk_sec}s chunks…", "accent")

        chunks_dir = out_root / f"{title}_chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        chunk_pattern = str(chunks_dir / f"{title}_%04d.wav")
        cmd = [
            ffmpeg_path, "-y", "-i", str(audio_file),
            "-f", "segment",
            "-segment_time", str(chunk_sec),
            "-ac", "1",
            "-ar", "44100",
            "-reset_timestamps", "1",
            chunk_pattern
        ]
        ret = self._run_ffmpeg(cmd, ffmpeg_path)
        if ret != 0 or not self._running:
            if not self._running:
                self._log("Cancelled during splitting.", "warning")
            self._finish(False)
            return

        chunks = sorted(chunks_dir.glob(f"{title}_*.wav"))
        self._log(f"Created {len(chunks)} chunks in: {chunks_dir}", "success")
        self._set_status(f"Done! {len(chunks)} chunks saved.", SUCCESS)

        try:
            audio_file.unlink()
            self._log(f"Removed intermediate file: {audio_file.name}", "dim")
        except Exception:
            pass

        self._log("✓ All done.", "success")
        self._finish(True)

    def _ydl_hook(self, d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "").strip()
            spd = d.get("_speed_str",   "").strip()
            eta = d.get("_eta_str",     "").strip()
            self.after(0, lambda: self.status_var.set(
                f"Downloading…  {pct}  {spd}  ETA {eta}"
            ))
        elif d["status"] == "finished":
            self._log("Download finished, processing…", "dim")

    def _run_ffmpeg(self, cmd: list, ffmpeg_path: str) -> int:
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    if any(k in line for k in ("Error", "error", "Invalid", "No such")):
                        self._log(line, "error")
                    elif "time=" in line:
                        self.after(0, lambda l=line: self.status_var.set(l.strip()))
            proc.wait()
            return proc.returncode
        except FileNotFoundError:
            self._log(f"ffmpeg not found at: {ffmpeg_path}", "error")
            return -1


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AudioSplitterApp()
    app.mainloop()
