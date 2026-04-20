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
    # macOS — Homebrew
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    # Windows — winget and common install locations
    str(Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-7.1.1-full_build/bin"),
    str(Path.home() / "AppData/Local/Microsoft/WinGet/Links"),
    str(Path.home() / "AppData/Local/Programs/ffmpeg/bin"),
    str(Path.home() / "AppData/Local/Programs/yt-dlp"),
    "C:/ffmpeg/bin",
    "C:/Program Files/ffmpeg/bin",
    "C:/Program Files (x86)/ffmpeg/bin",
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
    """Return the full path to `name` by checking shutil.which then common fallbacks."""
    found = shutil.which(name)
    if found:
        return found

    # Check static fallback paths
    for base in FALLBACK_PATHS:
        candidate = Path(base) / name
        for suffix in ("", ".exe"):
            p = Path(str(candidate) + suffix)
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)

    # Windows: glob-search winget's versioned package tree for the binary
    if sys.platform == "win32":
        winget_root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        if winget_root.exists():
            # e.g. Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe
            for exe in winget_root.rglob(f"{name}.exe"):
                if exe.is_file():
                    return str(exe)

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
        self.geometry("820x680")
        self.minsize(660, 560)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._running    = False
        self._thread     = None
        # Modes: "split" | "convert" | "playlist"
        self._mode       = tk.StringVar(value="split")

        cfg = load_config()
        self._ytdlp_path  = cfg.get("ytdlp_path",  probe_binary("yt-dlp"))
        self._ffmpeg_path = cfg.get("ffmpeg_path",  probe_binary("ffmpeg"))
        self._output_dir  = Path(cfg.get("output_dir", str(Path.home() / "AudioSplitter")))

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
        tk.Button(header, text="Log", font=("Courier", 10),
                  bg=BG, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=SURFACE, activeforeground=BLUE,
                  command=self._detach_log, padx=12, pady=4).pack(side="right")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30)

        # ── Main card ──
        card = tk.Frame(self, bg=SURFACE, bd=0, padx=24, pady=20)
        card.pack(fill="x", padx=30, pady=(16, 0))

        # ── Mode toggle ──
        mode_row = tk.Frame(card, bg=SURFACE)
        mode_row.pack(fill="x", pady=(0, 14))

        self.btn_split    = tk.Button(mode_row, text="Split",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("split"))
        self.btn_split.pack(side="left", padx=(0, 6))

        self.btn_convert  = tk.Button(mode_row, text="Convert",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("convert"))
        self.btn_convert.pack(side="left", padx=(0, 6))

        self.btn_playlist = tk.Button(mode_row, text="Playlist",
            font=("Courier", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=lambda: self._set_mode("playlist"))
        self.btn_playlist.pack(side="left")

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # ── Split mode: URL + local file sub-toggle ───────────────────────────
        self.split_frame = tk.Frame(card, bg=SURFACE)

        split_src_row = tk.Frame(self.split_frame, bg=SURFACE)
        split_src_row.pack(fill="x", pady=(0, 10))
        self._split_src = tk.StringVar(value="url")
        self.btn_split_url  = tk.Button(split_src_row, text="URL",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_split_src("url"))
        self.btn_split_url.pack(side="left", padx=(0, 6))
        self.btn_split_file = tk.Button(split_src_row, text="Local File",
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

        # Audio / Video sub-toggle
        cv_src_row = tk.Frame(self.convert_frame, bg=SURFACE)
        cv_src_row.pack(fill="x", pady=(0, 10))
        self._convert_type = tk.StringVar(value="audio")
        self.btn_cv_audio = tk.Button(cv_src_row, text="Audio",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_convert_type("audio"))
        self.btn_cv_audio.pack(side="left", padx=(0, 6))
        self.btn_cv_video = tk.Button(cv_src_row, text="Video",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_convert_type("video"))
        self.btn_cv_video.pack(side="left")

        tk.Frame(self.convert_frame, bg=BORDER, height=1).pack(fill="x", pady=(0, 10))

        # URL / Local file sub-toggle (shown in video mode only for local)
        cv_input_row = tk.Frame(self.convert_frame, bg=SURFACE)
        cv_input_row.pack(fill="x", pady=(0, 8))
        self._convert_src = tk.StringVar(value="url")
        self.btn_cv_url  = tk.Button(cv_input_row, text="URL",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_convert_src("url"))
        self.btn_cv_url.pack(side="left", padx=(0, 6))
        self.btn_cv_local = tk.Button(cv_input_row, text="Local File",
            font=("Courier", 9, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=lambda: self._set_convert_src("local"))
        self.btn_cv_local.pack(side="left")

        # URL input
        self.cv_url_frame = tk.Frame(self.convert_frame, bg=SURFACE)
        tk.Label(self.cv_url_frame, text="VIDEO / AUDIO URL",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        cv_row = tk.Frame(self.cv_url_frame, bg=SURFACE)
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

        # Local file input
        self.cv_local_frame = tk.Frame(self.convert_frame, bg=SURFACE)
        tk.Label(self.cv_local_frame, text="LOCAL FILE",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        cv_lf_row = tk.Frame(self.cv_local_frame, bg=SURFACE)
        cv_lf_row.pack(fill="x", pady=(4, 0))
        self.convert_file_var = tk.StringVar()
        tk.Entry(cv_lf_row, textvariable=self.convert_file_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT_DIM,
                 relief="flat", state="readonly",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        tk.Button(cv_lf_row, text="Browse…", font=("Courier", 10),
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
                  command=self._browse_convert_file, padx=12, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(cv_lf_row, text="✕", font=("Courier", 11),
                  bg=SURFACE2, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=lambda: self.convert_file_var.set(""), padx=10).pack(side="left")
        tk.Label(self.cv_local_frame,
                 text="Supported: mp4 mkv mov avi webm m4v flv wmv mp3 wav aac flac ogg m4a…",
                 font=("Courier", 8), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(5, 0))

        # ── Video options panel (shown when video sub-mode active) ────────────
        self.video_opts_frame = tk.Frame(self.convert_frame, bg=SURFACE)

        # Scale
        tk.Label(self.video_opts_frame, text="SCALE",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(12, 0))
        scale_row = tk.Frame(self.video_opts_frame, bg=SURFACE)
        scale_row.pack(fill="x", pady=(4, 0))

        self.scale_var = tk.StringVar(value="1/2 — Half size")
        scale_options = [
            "1/1 — Original size",
            "1/2 — Half size",
            "1/4 — Quarter size",
            "1920:1080 — 1080p",
            "1280:720  — 720p",
            "854:480   — 480p",
            "640:360   — 360p",
        ]
        self.scale_menu = ttk.Combobox(
            scale_row, textvariable=self.scale_var,
            values=scale_options, state="readonly",
            font=("Courier", 11), width=28
        )
        self.scale_menu.pack(side="left", ipady=4)

        # Clip (optional)
        tk.Label(self.video_opts_frame, text="CLIP  (optional — leave blank to convert full file)",
                 font=("Courier", 9, "bold"), fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(12, 0))

        clip_row = tk.Frame(self.video_opts_frame, bg=SURFACE)
        clip_row.pack(fill="x", pady=(4, 0))

        tk.Label(clip_row, text="Start", font=("Courier", 9), fg=TEXT_DIM, bg=SURFACE).pack(side="left", padx=(0, 6))
        self.clip_start_var = tk.StringVar(value="")
        tk.Entry(clip_row, textvariable=self.clip_start_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, width=10
                 ).pack(side="left", ipady=5, padx=(0, 16))

        tk.Label(clip_row, text="Duration", font=("Courier", 9), fg=TEXT_DIM, bg=SURFACE).pack(side="left", padx=(0, 6))
        self.clip_dur_var = tk.StringVar(value="")
        tk.Entry(clip_row, textvariable=self.clip_dur_var,
                 font=("Courier", 11), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, width=10
                 ).pack(side="left", ipady=5)

        tk.Label(clip_row, text="  HH:MM:SS",
                 font=("Courier", 8), fg=TEXT_DIM, bg=SURFACE).pack(side="left", padx=(8, 0))

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
        self.option_add("*TCombobox*Listbox.background",      SURFACE2)
        self.option_add("*TCombobox*Listbox.foreground",      BLUE)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", BG)
        self.option_add("*TCombobox*Listbox.font",             ("Courier", 11))

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
                      bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                      activebackground=BORDER, activeforeground=BLUE,
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

        # Outer wrapper — both toggle row and collapsible card live inside this
        tools_wrapper = tk.Frame(self, bg=BG)
        tools_wrapper.pack(fill="x", padx=30)

        tools_header = tk.Frame(tools_wrapper, bg=BG, pady=6)
        tools_header.pack(fill="x")
        self._tools_expanded = tk.BooleanVar(value=False)
        self._tools_toggle_btn = tk.Button(
            tools_header, text="[ + ] Tool Paths",
            font=("Courier", 9, "bold"), fg=BLUE, bg=BG,
            relief="flat", cursor="hand2",
            activebackground=BG, activeforeground=BLUE,
            command=self._toggle_tools
        )
        self._tools_toggle_btn.pack(side="left")

        # tools_card is a child of tools_wrapper so it expands inline
        self.tools_card = tk.Frame(tools_wrapper, bg=SURFACE, bd=0, padx=24, pady=16)
        # Not packed yet — collapsed by default

        tk.Label(self.tools_card, text="YT-DLP PATH", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w")
        ytdlp_row = tk.Frame(self.tools_card, bg=SURFACE)
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

        tk.Label(self.tools_card, text="FFMPEG PATH", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=SURFACE).pack(anchor="w", pady=(12, 0))
        ffmpeg_row = tk.Frame(self.tools_card, bg=SURFACE)
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

        save_row = tk.Frame(self.tools_card, bg=SURFACE)
        save_row.pack(fill="x", pady=(10, 0))
        tk.Button(save_row, text="Verify & Save Paths", font=("Courier", 10),
                  bg=SURFACE2, fg=BLUE, relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=BLUE,
                  command=self._verify_and_save_paths,
                  padx=14, pady=6).pack(side="left")

        # ── Action buttons ────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(14, 0))

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=30, pady=12)

        self.btn_start = tk.Button(
            btn_row, text="DOWNLOAD & SPLIT",
            font=("Courier", 12, "bold"),
            bg=ACCENT, fg="#1d2021", relief="flat", cursor="hand2",
            activebackground=ACCENT_DIM, activeforeground="#1d2021",
            command=self._start, padx=20, pady=10
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = tk.Button(
            btn_row, text="STOP",
            font=("Courier", 12, "bold"),
            bg=SURFACE2, fg=ERROR, relief="flat", cursor="hand2",
            activebackground=BORDER, activeforeground=ERROR,
            command=self._stop, padx=20, pady=10, state="disabled"
        )
        self.btn_stop.pack(side="left")

        tk.Button(btn_row, text="Open Folder",
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
        self.status_label.pack(fill="x", padx=32, pady=(6, 10))

        # Hidden log widget — still exists for state, just not displayed inline
        self.log = scrolledtext.ScrolledText(
            self, font=("Courier", 10), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            state="disabled", wrap="word", padx=12, pady=10
        )
        # log is NOT packed — it lives in the pop-out window only

        for tag, colour in [("info", TEXT), ("success", SUCCESS), ("warning", WARNING),
                             ("error", ERROR), ("dim", TEXT_DIM), ("accent", ACCENT)]:
            self.log.tag_config(tag, foreground=colour)

        # Apply initial mode
        self._set_mode("split")
        self._set_split_src("url")
        self._set_convert_type("audio")

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
            self.btn_start.config(text="DOWNLOAD & SPLIT")

        elif mode == "convert":
            self.btn_convert.config(bg=ACCENT, fg="#1d2021",
                                    activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.convert_frame.pack(fill="x")
            self._set_convert_type(self._convert_type.get())
            self.btn_start.config(text="CONVERT")

        elif mode == "playlist":
            self.btn_playlist.config(bg=ACCENT, fg="#1d2021",
                                     activebackground=ACCENT_DIM, activeforeground="#1d2021")
            self.playlist_frame.pack(fill="x")
            self.format_frame.pack(fill="x")
            self.btn_start.config(text="DOWNLOAD PLAYLIST")

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

    def _set_convert_type(self, ctype: str):
        self._convert_type.set(ctype)
        for btn in [self.btn_cv_audio, self.btn_cv_video]:
            btn.config(bg=SURFACE2, fg=TEXT_DIM,
                       activebackground=BORDER, activeforeground=TEXT)
        if ctype == "audio":
            self.btn_cv_audio.config(bg=BORDER, fg=TEXT,
                                     activebackground=SURFACE2, activeforeground=TEXT)
            # Audio mode: URL only, no local toggle, no video opts
            self.btn_cv_local.pack_forget()
            self.btn_cv_url.pack_forget()
            self.video_opts_frame.pack_forget()
            self.cv_local_frame.pack_forget()
            self.cv_url_frame.pack(fill="x")
            self.format_frame.pack(fill="x")
        else:
            self.btn_cv_video.config(bg=BORDER, fg=TEXT,
                                     activebackground=SURFACE2, activeforeground=TEXT)
            # Video mode: show URL/local toggle, video opts, no format dropdown
            self.format_frame.pack_forget()
            self.btn_cv_url.pack(side="left", padx=(0, 6))
            self.btn_cv_local.pack(side="left")
            self._set_convert_src(self._convert_src.get())
            self.video_opts_frame.pack(fill="x")

    def _set_convert_src(self, src: str):
        self._convert_src.set(src)
        self.cv_url_frame.pack_forget()
        self.cv_local_frame.pack_forget()
        for btn in [self.btn_cv_url, self.btn_cv_local]:
            btn.config(bg=SURFACE2, fg=TEXT_DIM,
                       activebackground=BORDER, activeforeground=TEXT)
        if src == "url":
            self.btn_cv_url.config(bg=BORDER, fg=TEXT,
                                   activebackground=SURFACE2, activeforeground=TEXT)
            self.cv_url_frame.pack(fill="x")
        else:
            self.btn_cv_local.config(bg=BORDER, fg=TEXT,
                                     activebackground=SURFACE2, activeforeground=TEXT)
            self.cv_local_frame.pack(fill="x")

    def _browse_convert_file(self):
        exts = " ".join(f"*{e}" for e in sorted(ALL_EXTS))
        path = filedialog.askopenfilename(
            title="Select video or audio file",
            filetypes=[("Video / Audio files", exts), ("All files", "*.*")]
        )
        if path:
            self.convert_file_var.set(path)
            self.dir_var.set(str(Path(path).parent))

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

    def _toggle_tools(self):
        if self._tools_expanded.get():
            self.tools_card.pack_forget()
            self._tools_expanded.set(False)
            self._tools_toggle_btn.config(text="[ + ] Tool Paths")
        else:
            self.tools_card.pack(fill="x")
            self._tools_expanded.set(True)
            self._tools_toggle_btn.config(text="[ - ] Tool Paths")

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
            cfg = load_config()
            cfg["output_dir"] = d
            save_config(cfg)

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
            save_config({
                "ytdlp_path":  ytdlp,
                "ffmpeg_path": ffmpeg,
                "output_dir":  self.dir_var.get(),
            })
            self._log("Settings saved to ~/.audiosplitter_config.json", "dim")
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
                  bg=BG, fg=BLUE, relief="flat", cursor="hand2",
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
            if self._convert_type.get() == "audio":
                args = (mode, url, None, self._get_format(), None, ffmpeg_path, ytdlp_path, out_root)
            else:
                scale = self.scale_var.get().strip()
                start = self.clip_start_var.get().strip()
                dur   = self.clip_dur_var.get().strip()
                if self._convert_src.get() == "local":
                    local_path = self.convert_file_var.get().strip()
                    if not local_path or not Path(local_path).exists():
                        self._log("Please select a valid local file.", "warning"); return
                    args = ("video_convert", None, local_path, scale, (start, dur), ffmpeg_path, ytdlp_path, out_root)
                else:
                    if not url:
                        self._log("Please enter a URL.", "warning"); return
                    args = ("video_convert", url, None, scale, (start, dur), ffmpeg_path, ytdlp_path, out_root)

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

    def _run(self, mode, url, local_file, fmt_or_scale, chunk_or_clip, ffmpeg_path, ytdlp_path, out_root):
        out_root.mkdir(parents=True, exist_ok=True)

        if mode == "split":
            self._run_split(url, local_file, chunk_or_clip, ffmpeg_path, ytdlp_path, out_root)
        elif mode == "convert":
            self._run_convert(url, fmt_or_scale, ffmpeg_path, ytdlp_path, out_root)
        elif mode == "video_convert":
            self._run_video_convert(url, local_file, fmt_or_scale, chunk_or_clip, ffmpeg_path, ytdlp_path, out_root)
        elif mode == "playlist":
            self._run_playlist(url, fmt_or_scale, ffmpeg_path, ytdlp_path, out_root)

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

    # ── Video convert pipeline ────────────────────────────────────────────────

    def _run_video_convert(self, url, local_file, scale_label, clip, ffmpeg_path, ytdlp_path, out_root):
        start, dur = clip

        scale_map = {
            "1/1 — Original size": None,
            "1/2 — Half size":     "iw/2:ih/2",
            "1/4 — Quarter size":  "iw/4:ih/4",
            "1920:1080 — 1080p":   "1920:1080",
            "1280:720  — 720p":    "1280:720",
            "854:480   — 480p":    "854:480",
            "640:360   — 360p":    "640:360",
        }
        scale_val = scale_map.get(scale_label, "iw/2:ih/2")

        self._log(f"Video convert — scale: {scale_label}", "accent")
        if start or dur:
            self._log(f"  Clip — start: {start or '0'}, duration: {dur or 'full'}", "dim")

        if local_file:
            download_path = Path(local_file)
            self._log(f"Using local file: {download_path.name}", "accent")
        else:
            download_path = self._download_single(
                url, ytdlp_path, out_root,
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            )
            if download_path is None:
                self._finish(False); return

        title    = sanitise(download_path.stem)
        out_file = out_root / f"{title}_converted.mp4"

        self._set_status("Processing video…")
        self._log(f"Processing → {out_file.name}", "accent")

        cmd = [ffmpeg_path, "-y"]
        if start:
            cmd += ["-ss", start]
        cmd += ["-i", str(download_path)]
        if dur:
            cmd += ["-t", dur]
        if scale_val:
            cmd += ["-vf", f"scale={scale_val}"]
        else:
            cmd += ["-c:v", "copy"]
        cmd += ["-c:a", "aac", "-async", "1", str(out_file)]

        ret = self._run_ffmpeg(cmd, ffmpeg_path)

        # Only clean up downloaded files, never local source files
        if not local_file and download_path.exists() and download_path != out_file:
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
