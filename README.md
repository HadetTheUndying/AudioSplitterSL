# AudioSplitter

A cross-platform desktop GUI for downloading or opening audio/video files, extracting their audio, and splitting it into configurable WAV chunks.

Built with Python + tkinter. Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for URL downloads and [ffmpeg](https://ffmpeg.org) for all audio processing.

---

> **AI Notice:** This software was developed with the assistance of [Claude](https://claude.ai) by Anthropic. All code has been reviewed and tested by a human developer.

---

## Features

- 🌐 **URL mode** — download from YouTube, Vimeo, Twitter/X, SoundCloud, and [1000+ sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- 📂 **Local file mode** — split any audio or video file directly, no download needed
- ✂️ **Configurable chunk length** — type any duration or use presets (15 s, 29.9 s, 30 s, 60 s)
- 🎨 **Gruvbox dark theme**
- 🔧 **Tool path configuration** — manually set yt-dlp and ffmpeg paths if auto-detection fails
- 💾 **Persistent settings** — tool paths saved across sessions

## Releases

Pre-built executables for macOS and Windows are available on the [Releases](../../releases) page — no Python installation required.

> ffmpeg and yt-dlp are **not** bundled and must be installed separately. See the setup instructions for your OS below.

---

## Setup & Build

### macOS

**1. Install dependencies**
```bash
brew install ffmpeg
brew install yt-dlp        # only needed for URL mode
brew install python-tk@3.14  # replace 3.14 with your Python version
pip install yt-dlp
```

> Check your Python version: `python3 --version`

**2. Run from source**
```bash
python3 audio_splitter.py
```

**3. Build a standalone app**
```bash
python3 build.py
```
Output: `dist/AudioSplitter`

> **First launch warning:** macOS Gatekeeper will block unsigned apps. Right-click → Open, or run:
> ```bash
> xattr -d com.apple.quarantine dist/AudioSplitter
> ```

**Tool path note:** Homebrew binaries may not be detected when launching outside a terminal. If yt-dlp or ffmpeg aren't found, open the **TOOL PATHS** section in the app and set them manually:
```
yt-dlp:  /opt/homebrew/bin/yt-dlp
ffmpeg:  /opt/homebrew/bin/ffmpeg
```

---

### Windows

**1. Install dependencies**
```bat
winget install ffmpeg
winget install yt-dlp
pip install yt-dlp
```

Or download ffmpeg from https://ffmpeg.org/download.html and add its `bin/` folder to your PATH.

tkinter is bundled with the official Python installer from https://www.python.org/downloads/windows/ — ensure **tcl/tk and IDLE** is checked during setup.

**2. Run from source**
```bat
python audio_splitter.py
```

**3. Build a standalone executable**
```bat
python build.py
```
Output: `dist\AudioSplitter.exe`

> **Defender warning:** Windows Defender may flag the `.exe` as suspicious — this is a known PyInstaller false positive. Right-click → **Run anyway**.

---

### Linux

**1. Install dependencies**

Debian / Ubuntu / Mint:
```bash
sudo apt install ffmpeg python3-tk
pip install yt-dlp
```

Fedora / RHEL:
```bash
sudo dnf install ffmpeg python3-tkinter
pip install yt-dlp
```

Arch / Manjaro:
```bash
sudo pacman -S ffmpeg tk
pip install yt-dlp
```

**2. Run from source**
```bash
python3 audio_splitter.py
```

**3. Build a standalone binary**
```bash
python3 build.py
```
Output: `dist/AudioSplitter`

```bash
chmod +x dist/AudioSplitter
./dist/AudioSplitter
```

> Linux builds are not included in automated CI due to display server requirements for tkinter. Build locally from source.

---

## CI / Automated Builds

Pushing a version tag triggers GitHub Actions to build macOS and Windows executables in parallel and attach them to a GitHub Release automatically.

```bash
git tag v1.0.0
git push --tags
```

You can also trigger a manual build (without creating a release) from the **Actions** tab → **Build AudioSplitter** → **Run workflow**.

---

## Usage

### URL mode
1. Click **🌐 URL**
2. Paste a supported URL
3. Set chunk length and output folder
4. Press **▶ DOWNLOAD & SPLIT**

### Local file mode
1. Click **📂 Local File**
2. Browse to your file — output folder auto-fills to the file's directory
3. Press **▶ SPLIT FILE**

Supported input formats: `mp3` `wav` `aac` `flac` `ogg` `m4a` `opus` `wma` `mp4` `mkv` `mov` `avi` `webm` `m4v` `flv` `wmv`

---

## ffmpeg Split Flags

```
ffmpeg -f segment -segment_time <chunk_length> -ac 1 -ar 44100 -reset_timestamps 1
```

| Flag | Effect |
|------|--------|
| `-ac 1` | Mono audio |
| `-ar 44100` | 44.1 kHz sample rate |
| `-reset_timestamps 1` | Each chunk starts at 0:00 |

---

## Output Structure

```
~/AudioSplitter/
└── My_Video_Title_chunks/
    ├── My_Video_Title_0000.wav
    ├── My_Video_Title_0001.wav
    └── ...
```

---

## Project Files

| File | Purpose |
|------|---------|
| `audio_splitter.py` | Main application |
| `build.py` | Builds a standalone executable via PyInstaller |
| `resources.txt` | Dependency & troubleshooting reference |
| `.github/workflows/build.yml` | CI workflow for automated macOS + Windows builds |

---

## License

[MIT](LICENSE)
