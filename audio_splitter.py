#!/usr/bin/env python3
"""
AudioSplitter - Download, convert, split audio/video
Requires: ffmpeg
Optional: yt-dlp (for URL modes)
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
BG          = "#1d2021"   # bg0_h  — darkest background
SURFACE     = "#282828"   # bg0    — main surface
SURFACE2    = "#3c3836"   # bg1    — raised elements / inputs
BORDER      = "#504945"   # bg2    — borders / dividers
ACCENT      = "#d79921"   # yellow — primary accent
ACCENT_DIM  = "#b57614"   # yellow dim — hover / active
BLUE        = "#83a598"   # blue — used for dropdowns / secondary UI
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

# Output format definitions: (label, extension, yt-dlp format, ffmpeg codec args)
OUTPUT_FORMATS = [
    ("WAV  — lossless PCM",      "wav",  "bestaudio/best", ["-acodec", "pcm_s16le", "-ar", "44100"]),
    ("MP3  — 320 kbps",          "mp3",  "bestaudio/best", ["-acodec", "libmp3lame", "-b:a", "320k"]),
    ("MP3  — 192 kbps",          "mp3",  "bestaudio/best", ["-acodec", "libmp3lame", "-b:a", "192k"]),
    ("MP3  — 128 kbps",          "mp3",  "bestaudio/best", ["-acodec", "libmp3lame", "-b:a", "128k"]),
    ("AAC  — 256 kbps",          "m4a",  "bestaudio/best", ["-acodec", "aac",        "-b:a", "256k"]),
    ("FLAC — lossless",          "flac", "bestaudio/best", ["-acodec", "flac"]),
    ("OGG  — Vorbis 192 kbps",   "ogg",  "bestaudio/best", ["-acodec", "libvorbis",  "-b:a", "192k"]),
    ("OPUS — 128 kbps",          "opus", "bestaudio/best", ["-acodec", "libopus",    "-b:a", "128k"]),
]
FORMAT_LABELS = [f[0] for f in OUTPUT_FORMATS]

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


def sanitise(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s)[:80]


# ─────────────────────────────────────────────────────────────────────────────

class AudioSplitterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AudioSplitter")
        self.geometry("820x860")
        self.minsize(660, 720)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._output_dir = Path.home() / "AudioSplitter"
        self._running    = False
        self._thread     = None
        # Modes: "split" | "convert" | "playlist"
        self._mode       = tk.StringVar(value="split")

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

        self.btn_split    = tk.Button(mode_row, text="✂️  Split",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("split"))
        self.btn_split.pack(side="left", padx=(0, 6))

        self.btn_convert  = tk.Button(mode_row, text="🔄  Convert",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("convert"))
        self.btn_convert.pack(side="left", padx=(0, 6))

        self.btn_playlist = tk.Button(mode_row, text="📋  Playlist",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("playlist"))
        self.btn_playlist.pack(side="left")

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # ── Split mode: URL + local file sub-toggle ───────────────────────────
        self.split_frame = tk.Frame(card, bg=SURFACE)

        split_src_row = tk.Frame(self.split_frame, bg=SURFACE)
        split_src_row.pack(fill="x", pady=(0, 10))
        self._split_src = tk.StringVar(value="url")
        self.btn_split_url  = tk.Button(split_src_row, text="🌐  URL",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_split_src("url"))
        self.btn_split_url.pack(side="left", padx=(0, 6))
        self.btn_split_file = tk.Button(split_src_row, text="📂  Local File",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_split_src("file"))
        self.btn_split_file.pack(side="left")

        # Split — URL input
        self.split_url_frame = tk.Frame(self.split_frame, bg=SURFACE)
        tk.Label(self.split_url_frame, text="VIDEO / AUDIO URL",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        su_row = tk.Frame(self.split_url_frame, bg=SURFACE)
        su_row.pack(fill="x", pady=(4, 0))
        self.split_url_var = tk.StringVar()
        tk.Entry(su_row, textvariable=self.split_url_var,
                 font=("Courier", 12), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        tk.Button(su_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.split_url_var.set(""), padx=10).pack(side="left")

        # Split — local file input
        self.split_file_frame = tk.Frame(self.split_frame, bg=SURFACE)
        tk.Label(self.split_file_frame, text="LOCAL FILE",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        sf_row = tk.Frame(self.split_file_frame, bg=SURFACE)
        sf_row.pack(fill="x", pady=(4, 0))
        self.split_file_var = tk.StringVar()
        tk.Entry(sf_row, textvariable=self.split_file_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT_DIM,
                 relief="flat", state="readonly",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(sf_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
                  command=self._browse_local_file, padx=12, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(sf_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.split_file_var.set(""), padx=10).pack(side="left")
        tk.Label(self.split_file_frame,
                 text="Supported: mp3 wav aac flac ogg m4a opus wma mp4 mkv mov avi webm…",
                 font=("Courier", 8), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(5, 0))

        # ── Convert mode ──────────────────────────────────────────────────────
        self.convert_frame = tk.Frame(card, bg=SURFACE)
        tk.Label(self.convert_frame, text="VIDEO / AUDIO URL",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        cv_row = tk.Frame(self.convert_frame, bg=SURFACE)
        cv_row.pack(fill="x", pady=(4, 0))
        self.convert_url_var = tk.StringVar()
        tk.Entry(cv_row, textvariable=self.convert_url_var,
                 font=("Courier", 12), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        tk.Button(cv_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.convert_url_var.set(""), padx=10).pack(side="left")

        # ── Playlist mode ─────────────────────────────────────────────────────
        self.playlist_frame = tk.Frame(card, bg=SURFACE)
        tk.Label(self.playlist_frame, text="PLAYLIST URL",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        pl_row = tk.Frame(self.playlist_frame, bg=SURFACE)
        pl_row.pack(fill="x", pady=(4, 0))
        self.playlist_url_var = tk.StringVar()
        tk.Entry(pl_row, textvariable=self.playlist_url_var,
                 font=("Courier", 12), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        tk.Button(pl_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.playlist_url_var.set(""), padx=10).pack(side="left")
        tk.Label(self.playlist_frame,
                 text="Supports YouTube playlists, SoundCloud sets, Bandcamp albums, and more.",
                 font=("Courier", 8), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(5, 0))

        # ── Output format dropdown (convert + playlist modes) ─────────────────
        self.format_frame = tk.Frame(card, bg=SURFACE)

        tk.Label(self.format_frame, text="OUTPUT FORMAT",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(14, 0))

        fmt_row = tk.Frame(self.format_frame, bg=SURFACE)
        fmt_row.pack(fill="x", pady=(4, 0))

        self.format_var = tk.StringVar(value=FORMAT_LABELS[1])  # default MP3 320k
        fmt_menu = ttk.Combobox(
            fmt_row, textvariable=self.format_var,
            values=FORMAT_LABELS, state="readonly",
            font=("Courier", 11), width=36
        )
        fmt_menu.pack(side="left", ipady=4)

        # Style the dropdown popup list (native Tk listbox underneath ttk)
        self.option_add("*TCombobox*Listbox.background",   SURFACE2)
        self.option_add("*TCombobox*Listbox.foreground",   BLUE)
        self.option_add("*TCombobox*Listbox.selectBackground", BORDER)
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        self.option_add("*TCombobox*Listbox.font",         ("Courier", 11))

        # Style the combobox to match gruvbox
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox",
                        fieldbackground=SURFACE2, background=SURFACE2,
                        foreground=BLUE, selectbackground=BORDER,
                        selectforeground=BLUE, borderwidth=0,
                        arrowcolor=BLUE)

        # ── Chunk length (split mode only) ────────────────────────────────────
        self.chunk_frame = tk.Frame(card, bg=SURFACE)

        tk.Label(self.chunk_frame, text="CHUNK LENGTH (seconds)",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(14, 0))

        chunk_row = tk.Frame(self.chunk_frame, bg=SURFACE)
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

        # ── Output folder ─────────────────────────────────────────────────────
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
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
                  command=self._browse_output, padx=12, pady=4).pack(side="left")

        # ── Tools config ──────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(14, 0))

        tools_header = tk.Frame(self, bg=BG, pady=6)
        tools_header.pack(fill="x", padx=30)
        tk.Label(tools_header, text="TOOL PATHS", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")

        tools_card = tk.Frame(self, bg=SURFACE, bd=0, padx=24, pady=16)
        tools_card.pack(fill="x", padx=30)

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
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
                  command=lambda: self._browse_binary(self.ytdlp_var),
                  padx=12, pady=4).pack(side="left", padx=(0, 6))
        self.ytdlp_status = tk.Label(ytdlp_row, text="", font=("Courier", 14), bg=SURFACE, width=2)
        self.ytdlp_status.pack(side="left")

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
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
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

        # ── Action buttons ────────────────────────────────────────────────────
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
                  font=("Courier", 10), bg=SURFACE, fg=BLUE,
                  relief="flat", cursor="hand2",
                  activebackground=SURFACE2, activeforeground=BLUE,
                  command=self._open_folder, padx=14, pady=10).pack(side="right")

        # ── Progress bar ──────────────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=30)
        style.configure("AS.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        self.progress = ttk.Progressbar(prog_frame, mode="indeterminate",
                                        length=300, style="AS.Horizontal.TProgressbar")
        self.progress.pack(fill="x")

        # ── Status label ──────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = tk.Label(self, textvariable=self.status_var,
                                     font=("Courier", 10), fg=TEXT_DIM, bg=BG, anchor="w")
        self.status_label.pack(fill="x", padx=32, pady=(6, 0))

        # ── Log console ───────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(10, 0))
        log_header = tk.Frame(self, bg=BG, pady=6)
        log_header.pack(fill="x", padx=30)
        tk.Label(log_header, text="LOG", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        tk.Button(log_header, text="Clear", font=("Courier", 9),
                  bg=BG, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=SURFACE, activeforeground=TEXT,
                  command=self._clear_log).pack(side="right")
        tk.Button(log_header, text="⤢  Pop Out", font=("Courier", 9),
                  bg=BG, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=SURFACE, activeforeground=BLUE,
                  command=self._detach_log).pack(side="right", padx=(0, 10))

        self.log = scrolledtext.ScrolledText(
            self, font=("Courier", 10), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            state="disabled", wrap="word", padx=12, pady=10
        )
        self.log.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        for tag, colour in [("info", TEXT), ("success", SUCCESS), ("warning", WARNING),
                             ("error", ERROR), ("dim", TEXT_DIM), ("accent", ACCENT)]:
            self.log.tag_config(tag, foreground=colour)

        # Apply initial mode
        self._set_mode("split")
        self._set_split_src("url")

    # ── Mode switching ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode.set(mode)

        # Reset all mode buttons to dim
        for btn in [self.btn_split, self.btn_convert, self.btn_playlist]:
            btn.config(bg=SURFACE2, fg=TEXT_DIM,
                       activebackground=BORDER, activeforeground=TEXT)

        # Hide all mode frames and optional panels
        for frame in [self.split_frame, self.convert_frame, self.playlist_frame,
                      self.format_frame, self.chunk_frame]:
            frame.pack_forget()

        if mode == "split":
            self.btn_split.config(bg=ACCENT, fg="#1d2021",
                                  activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.split_frame.pack(fill="x")
            self.chunk_frame.pack(fill="x")
            self.btn_start.config(text="▶  DOWNLOAD & SPLIT")

        elif mode == "convert":
            self.btn_convert.config(bg=ACCENT, fg="#1d2021",
                                    activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.convert_frame.pack(fill="x")
            self.format_frame.pack(fill="x")
            self.btn_start.config(text="▶  DOWNLOAD & CONVERT")

        elif mode == "playlist":
            self.btn_playlist.config(bg=ACCENT, fg="#1d2021",
                                     activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.playlist_frame.pack(fill="x")
            self.format_frame.pack(fill="x")
            self.btn_start.config(text="▶  DOWNLOAD PLAYLIST")

    def _set_split_src(self, src: str):
        self._split_src.set(src)
        self.split_url_frame.pack_forget()
        self.split_file_frame.pack_forget()

        for btn in [self.btn_split_url, self.btn_split_file]:
            btn.config(bg=SURFACE2, fg=TEXT_DIM,
                       activebackground=BORDER, activeforeground=TEXT)

        if src == "url":
            self.btn_split_url.config(bg=BORDER, fg=TEXT,
                                      activebackground=SURFACE2, activeforeground=TEXT)
            self.split_url_frame.pack(fill="x")
        else:
            self.btn_split_file.config(bg=BORDER, fg=TEXT,
                                       activebackground=SURFACE2, activeforeground=TEXT)
            self.split_file_frame.pack(fill="x")

    # ── Dependency check ──────────────────────────────────────────────────────

    def _check_deps(self):
        ytdlp_path = self.ytdlp_var.get().strip()
        ytdlp_ok   = YT_DLP_AVAILABLE or (bool(ytdlp_path) and Path(ytdlp_path).is_file())
        self._set_indicator(self.ytdlp_status, ytdlp_ok)
        if ytdlp_ok:
            self._log(f"✓ yt-dlp detected ({'Python lib' if YT_DLP_AVAILABLE else ytdlp_path})  [required for URL / Convert / Playlist modes]", "success")
        else:
            self._log("⚠ yt-dlp not found — URL, Convert and Playlist modes unavailable. Local file split still works.", "warning")

        ffmpeg_path = self.ffmpeg_var.get().strip()
        ffmpeg_ok   = bool(ffmpeg_path) and Path(ffmpeg_path).is_file()
        self._set_indicator(self.ffmpeg_status, ffmpeg_ok)
        if ffmpeg_ok:
            self._log(f"✓ ffmpeg detected ({ffmpeg_path})", "success")
        else:
            self._log("✗ ffmpeg not found. Set path in Tool Paths section.", "error")
            self._set_status("Missing dependencies — see log.", ERROR)
            self.btn_start.config(state="disabled")
            return

        self._log("Ready.", "dim")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_binary(self, var):
        initial = str(Path(var.get()).parent) if var.get() else "/opt/homebrew/bin"
        path = filedialog.askopenfilename(initialdir=initial, title="Select executable")
        if path:
            var.set(path)

    def _browse_local_file(self):
        exts = " ".join(f"*{e}" for e in sorted(ALL_EXTS))
        path = filedialog.askopenfilename(
            title="Select audio or video file",
            filetypes=[("Audio / Video files", exts), ("All files", "*.*")]
        )
        if path:
            self.split_file_var.set(path)
            self.dir_var.set(str(Path(path).parent))

    def _browse_output(self):
        d = filedialog.askdirectory(initialdir=str(self._output_dir))
        if d:
            self._output_dir = Path(d)
            self.dir_var.set(d)

    def _set_indicator(self, label, ok):
        self.after(0, lambda: label.config(text="✓" if ok else "✗",
                                           fg=SUCCESS if ok else ERROR))

    def _verify_and_save_paths(self):
        ytdlp  = self.ytdlp_var.get().strip()
        ffmpeg = self.ffmpeg_var.get().strip()
        all_ok = True

        ytdlp_ok = YT_DLP_AVAILABLE or (bool(ytdlp) and Path(ytdlp).is_file())
        self._set_indicator(self.ytdlp_status, ytdlp_ok)
        if ytdlp_ok:
            self._log(f"✓ yt-dlp verified: {ytdlp or 'Python lib'}", "success")
        else:
            self._log(f"⚠ yt-dlp not found at: {ytdlp}", "warning")

        ffmpeg_ok = bool(ffmpeg) and Path(ffmpeg).is_file() and os.access(ffmpeg, os.X_OK)
        self._set_indicator(self.ffmpeg_status, ffmpeg_ok)
        if ffmpeg_ok:
            self._log(f"✓ ffmpeg verified: {ffmpeg}", "success")
        else:
            self._log(f"✗ ffmpeg not found at: {ffmpeg}", "error")
            all_ok = False

        if all_ok:
            save_config({"ytdlp_path": ytdlp, "ffmpeg_path": ffmpeg})
            self._log("Paths saved to ~/.audiosplitter_config.json", "dim")
            self._set_status("Paths verified and saved.", SUCCESS)
            self.btn_start.config(state="normal")
        else:
            self._set_status("Fix tool paths before continuing.", ERROR)
            self.btn_start.config(state="disabled")

    def _log(self, msg, tag="info"):
        def _append():
            self.log.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log.insert("end", f"[{ts}] ", "dim")
            self.log.insert("end", msg + "\n", tag)
            self.log.see("end")
            self.log.config(state="disabled")
        self.after(0, _append)

    def _set_status(self, msg, colour=TEXT_DIM):
        self.after(0, lambda: (
            self.status_var.set(msg),
            self.status_label.config(fg=colour)
        ))

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _detach_log(self):
        """Open the log in a standalone resizable window, kept in sync with the main log."""
        # Only one detached window at a time
        if hasattr(self, "_log_window") and self._log_window.winfo_exists():
            self._log_window.lift()
            return

        win = tk.Toplevel(self)
        win.title("AudioSplitter — Log")
        win.geometry("900x500")
        win.configure(bg=BG)
        win.resizable(True, True)
        self._log_window = win

        # ── Header ──
        hdr = tk.Frame(win, bg=BG, pady=8)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="LOG", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        tk.Button(hdr, text="Clear", font=("Courier", 9),
                  bg=BG, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=SURFACE, activeforeground=TEXT,
                  command=self._clear_log).pack(side="right")

        # ── Mirrored log widget ──
        mirror = scrolledtext.ScrolledText(
            win, font=("Courier", 10), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            state="disabled", wrap="word", padx=12, pady=10
        )
        mirror.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        for tag, colour in [("info", TEXT), ("success", SUCCESS), ("warning", WARNING),
                             ("error", ERROR), ("dim", TEXT_DIM), ("accent", ACCENT)]:
            mirror.tag_config(tag, foreground=colour)

        # Copy current log contents into the mirror
        self.log.config(state="normal")
        content = self.log.get("1.0", "end-1c")
        self.log.config(state="disabled")
        if content:
            mirror.config(state="normal")
            mirror.insert("1.0", content)
            mirror.see("end")
            mirror.config(state="disabled")

        # Patch _log so new entries go to both widgets simultaneously
        original_log = self._log

        def dual_log(msg, tag="info"):
            original_log(msg, tag)
            def _append_mirror():
                if win.winfo_exists():
                    mirror.config(state="normal")
                    ts = datetime.now().strftime("%H:%M:%S")
                    mirror.insert("end", f"[{ts}] ", "dim")
                    mirror.insert("end", msg + "\n", tag)
                    mirror.see("end")
                    mirror.config(state="disabled")
            self.after(0, _append_mirror)

        self._log = dual_log

        # Restore original _log when window is closed
        def on_close():
            self._log = original_log
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _open_folder(self):
        p = Path(self.dir_var.get())
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])

    def _get_format(self):
        """Return the selected OUTPUT_FORMATS entry."""
        label = self.format_var.get()
        for fmt in OUTPUT_FORMATS:
            if fmt[0] == label:
                return fmt
        return OUTPUT_FORMATS[1]  # fallback MP3 320k

    # ── Start ─────────────────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return

        mode        = self._mode.get()
        ffmpeg_path = self.ffmpeg_var.get().strip()
        ytdlp_path  = self.ytdlp_var.get().strip()
        out_root    = Path(self.dir_var.get())

        if mode == "split":
            src = self._split_src.get()
            if src == "url":
                url = self.split_url_var.get().strip()
                if not url:
                    self._log("Please enter a URL.", "warning"); return
                local_file = None
            else:
                local_file = self.split_file_var.get().strip()
                if not local_file or not Path(local_file).exists():
                    self._log("Please select a valid local file.", "warning"); return
                url = None

            try:
                chunk_sec = float(self.chunk_var.get().strip())
                if chunk_sec <= 0: raise ValueError
            except ValueError:
                self._log("Invalid chunk length.", "error"); return

            args = (mode, url, local_file, None, chunk_sec, ffmpeg_path, ytdlp_path, out_root)

        elif mode == "convert":
            url = self.convert_url_var.get().strip()
            if not url:
                self._log("Please enter a URL.", "warning"); return
            args = (mode, url, None, self._get_format(), None, ffmpeg_path, ytdlp_path, out_root)

        elif mode == "playlist":
            url = self.playlist_url_var.get().strip()
            if not url:
                self._log("Please enter a playlist URL.", "warning"); return
            args = (mode, url, None, self._get_format(), None, ffmpeg_path, ytdlp_path, out_root)

        self._running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress.start(12)

        self._thread = threading.Thread(target=self._run, args=args, daemon=True)
        self._thread.start()

    def _stop(self):
        self._running = False
        self._log("Stop requested — will halt after current step.", "warning")

    def _finish(self, success):
        def _upd():
            self.progress.stop()
            self.progress["value"] = 0
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self._running = False
        self.after(0, _upd)

    # ── Worker ────────────────────────────────────────────────────────────────

    def _run(self, mode, url, local_file, fmt, chunk_sec, ffmpeg_path, ytdlp_path, out_root):
        out_root.mkdir(parents=True, exist_ok=True)

        if mode == "split":
            self._run_split(url, local_file, chunk_sec, ffmpeg_path, ytdlp_path, out_root)
        elif mode == "convert":
            self._run_convert(url, fmt, ffmpeg_path, ytdlp_path, out_root)
        elif mode == "playlist":
            self._run_playlist(url, fmt, ffmpeg_path, ytdlp_path, out_root)

    # ── Split pipeline ────────────────────────────────────────────────────────

    def _run_split(self, url, local_file, chunk_sec, ffmpeg_path, ytdlp_path, out_root):
        if local_file:
            source = Path(local_file)
            title  = sanitise(source.stem)
            self._log(f"Using local file: {source.name}", "accent")
            download_path = source
        else:
            download_path = self._download_single(url, ytdlp_path, out_root)
            if download_path is None:
                self._finish(False); return
            title = sanitise(download_path.stem)

        # Extract to WAV
        self._set_status("Extracting audio…")
        self._log("Extracting audio…", "accent")
        audio_file = out_root / f"{title}_audio.wav"
        ret = self._run_ffmpeg([
            ffmpeg_path, "-y", "-i", str(download_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(audio_file)
        ], ffmpeg_path)
        if ret != 0 or not self._running:
            self._finish(False); return
        self._log(f"Audio extracted → {audio_file.name}", "success")

        # Split
        self._set_status(f"Splitting into {chunk_sec}s chunks…")
        self._log(f"Splitting into {chunk_sec}s chunks…", "accent")
        chunks_dir = out_root / f"{title}_chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        ret = self._run_ffmpeg([
            ffmpeg_path, "-y", "-i", str(audio_file),
            "-f", "segment", "-segment_time", str(chunk_sec),
            "-ac", "1", "-ar", "44100", "-reset_timestamps", "1",
            str(chunks_dir / f"{title}_%04d.wav")
        ], ffmpeg_path)
        if ret != 0 or not self._running:
            self._finish(False); return

        chunks = sorted(chunks_dir.glob(f"{title}_*.wav"))
        self._log(f"Created {len(chunks)} chunks → {chunks_dir}", "success")
        self._set_status(f"Done! {len(chunks)} chunks saved.", SUCCESS)

        try: audio_file.unlink()
        except Exception: pass

        self._log("✓ All done.", "success")
        self._finish(True)

    # ── Convert pipeline ──────────────────────────────────────────────────────

    def _run_convert(self, url, fmt, ffmpeg_path, ytdlp_path, out_root):
        _, ext, ydl_fmt, codec_args = fmt
        self._log(f"Converting to {ext.upper()}…", "accent")

        download_path = self._download_single(url, ytdlp_path, out_root, ydl_fmt)
        if download_path is None:
            self._finish(False); return

        title   = sanitise(download_path.stem)
        out_file = out_root / f"{title}.{ext}"

        self._set_status(f"Converting to {ext.upper()}…")
        self._log(f"Encoding → {out_file.name}", "accent")

        ret = self._run_ffmpeg([
            ffmpeg_path, "-y", "-i", str(download_path),
            "-vn", *codec_args, str(out_file)
        ], ffmpeg_path)

        # Clean up source if it differs from output
        if download_path.exists() and download_path != out_file:
            try: download_path.unlink()
            except Exception: pass

        if ret != 0 or not self._running:
            self._finish(False); return

        self._log(f"✓ Saved → {out_file.name}", "success")
        self._set_status(f"Done! Saved as {out_file.name}", SUCCESS)
        self._finish(True)

    # ── Playlist pipeline ─────────────────────────────────────────────────────

    def _run_playlist(self, url, fmt, ffmpeg_path, ytdlp_path, out_root):
        _, ext, ydl_fmt, codec_args = fmt

        self._log(f"Fetching playlist info…", "accent")
        self._set_status("Fetching playlist…")

        if not YT_DLP_AVAILABLE and (not ytdlp_path or not Path(ytdlp_path).is_file()):
            self._log("yt-dlp not found. Set path in Tool Paths.", "error")
            self._finish(False); return

        # Fetch playlist entries first
        try:
            if YT_DLP_AVAILABLE:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                        "extract_flat": True}) as ydl:
                    info     = ydl.extract_info(url, download=False)
                    entries  = info.get("entries", [])
                    pl_title = sanitise(info.get("title", "playlist"))
            else:
                result = subprocess.run(
                    [ytdlp_path, "--flat-playlist", "-J", "--no-warnings", url],
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                if result.returncode != 0:
                    raise RuntimeError("yt-dlp exited with error fetching playlist info")
                info     = json.loads(result.stdout)
                entries  = info.get("entries", [])
                pl_title = sanitise(info.get("title", "playlist"))

            self._log(f"Playlist: {pl_title} — {len(entries)} tracks", "success")
        except Exception as e:
            self._log(f"Failed to fetch playlist: {e}", "error")
            self._finish(False); return

        pl_dir = out_root / pl_title
        pl_dir.mkdir(parents=True, exist_ok=True)
        self._log(f"Output folder: {pl_dir}", "dim")

        failed  = []
        success = 0

        for i, entry in enumerate(entries, 1):
            if not self._running:
                self._log("Stopped.", "warning"); break

            track_url   = entry.get("url") or entry.get("webpage_url")
            track_title = sanitise(entry.get("title") or f"track_{i:04d}")
            self._set_status(f"[{i}/{len(entries)}] {track_title[:50]}…")
            self._log(f"[{i}/{len(entries)}] {track_title}", "accent")

            if not track_url:
                self._log(f"  ✗ No URL for entry {i}, skipping.", "warning")
                failed.append(track_title)
                continue

            # Download
            dl_path = self._download_single(track_url, ytdlp_path, pl_dir, ydl_fmt)
            if dl_path is None:
                failed.append(track_title)
                continue

            # Convert
            out_file = pl_dir / f"{track_title}.{ext}"
            ret = self._run_ffmpeg([
                ffmpeg_path, "-y", "-i", str(dl_path),
                "-vn", *codec_args, str(out_file)
            ], ffmpeg_path)

            if dl_path.exists() and dl_path != out_file:
                try: dl_path.unlink()
                except Exception: pass

            if ret == 0:
                self._log(f"  ✓ {out_file.name}", "success")
                success += 1
            else:
                self._log(f"  ✗ Conversion failed for: {track_title}", "error")
                failed.append(track_title)

        self._log(f"✓ Playlist done. {success}/{len(entries)} tracks saved → {pl_dir}", "success")
        if failed:
            self._log(f"  Failed: {', '.join(failed)}", "warning")
        self._set_status(f"Done! {success}/{len(entries)} tracks saved.", SUCCESS)
        self._finish(True)

    # ── Shared download helper ────────────────────────────────────────────────

    def _download_single(self, url, ytdlp_path, out_dir, ydl_fmt="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"):
        """Download a single URL. Returns Path to downloaded file or None on failure."""
        self._set_status("Downloading…")
        self._log(f"Downloading: {url}", "dim")

        try:
            if YT_DLP_AVAILABLE:
                outtmpl = str(out_dir / "%(title)s.%(ext)s")
                ydl_opts = {
                    "outtmpl":        outtmpl,
                    "format":         ydl_fmt,
                    "quiet":          True,
                    "no_warnings":    True,
                    "progress_hooks": [self._ydl_hook],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # For playlists passed as single, grab first entry
                    if "entries" in info:
                        info = info["entries"][0]
                    return Path(ydl.prepare_filename(info))
            else:
                if not ytdlp_path or not Path(ytdlp_path).is_file():
                    self._log("yt-dlp not found. Set path in Tool Paths.", "error")
                    return None

                outtmpl = str(out_dir / "%(title)s.%(ext)s")
                proc = subprocess.Popen(
                    [ytdlp_path, "-o", outtmpl, "-f", ydl_fmt, "--no-warnings", url],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace"
                )
                dl_path = None
                for line in proc.stdout:
                    line = line.rstrip()
                    if "[download]" in line:
                        self.after(0, lambda l=line: self.status_var.set(l[:90]))
                    if "Destination:" in line:
                        m = re.search(r"Destination: (.+)$", line)
                        if m:
                            dl_path = Path(m.group(1).strip())
                proc.wait()
                if proc.returncode != 0:
                    raise RuntimeError("yt-dlp exited with error")

                if dl_path is None or not dl_path.exists():
                    candidates = [p for p in out_dir.glob("*.*")
                                  if p.suffix.lower() not in (".json",)]
                    if candidates:
                        dl_path = max(candidates, key=lambda p: p.stat().st_mtime)

                return dl_path

        except Exception as e:
            self._log(f"Download failed: {e}", "error")
            return None

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

    def _run_ffmpeg(self, cmd, ffmpeg_path):
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
