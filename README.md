# AudioSplitter

A cross-platform desktop GUI for downloading, converting, and splitting audio from URLs or local files.

Built with Python + tkinter. Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for URL downloads and [ffmpeg](https://ffmpeg.org) for all audio processing.

---

> **AI Notice:** This software was developed with the assistance of [Claude](https://claude.ai) by Anthropic. All code has been reviewed and tested by a human developer.

---

## Features

- **✂️ Split** — download from a URL or open a local file and split the audio into fixed-length chunks
- **🔄 Convert** — download from a URL and convert directly to a chosen audio format
- **📋 Playlist** — download and convert every track in a playlist, album, or set
- **Output format selector** — WAV, MP3 (320/192/128 kbps), AAC, FLAC, OGG, OPUS
- **Configurable chunk length** — type any duration or use presets (15 s, 29.9 s, 30 s, 60 s)
- **🎨 Gruvbox dark theme**
- **Tool path configuration** — manually set yt-dlp and ffmpeg paths if auto-detection fails
- **Persistent settings** — tool paths saved across sessions

## Releases

Pre-built executables for macOS and Windows are available on the [Releases](../../releases) page — no Python installation required.

> ffmpeg and yt-dlp are **not** bundled and must be installed separately. See the setup instructions for your OS below.

---

## Setup & Build

### macOS

**1. Install dependencies**
```bash
brew install ffmpeg
brew install yt-dlp
brew install python-tk@3.14
```

> Replace `3.14` with your Python version — check with `python3 --version`.
> yt-dlp is only required for URL, Convert, and Playlist modes. Local file Split works with just ffmpeg.

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
```

> yt-dlp is only required for URL, Convert, and Playlist modes. Local file Split works with just ffmpeg.

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

> **Defender warning:** Windows Defender may flag the `.exe` — this is a known PyInstaller false positive. Right-click → **Run anyway**.

---

### Linux

**1. Install dependencies**

Debian / Ubuntu / Mint:
```bash
sudo apt install ffmpeg python3-tk
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
```

Fedora / RHEL:
```bash
sudo dnf install ffmpeg python3-tkinter
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
```

Arch / Manjaro:
```bash
sudo pacman -S ffmpeg tk yt-dlp
```

> yt-dlp is only required for URL, Convert, and Playlist modes. Local file Split works with just ffmpeg.

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

### ✂️ Split mode
Download a URL or open a local file and split its audio into equal-length chunks.

1. Click **✂️ Split**
2. Choose **🌐 URL** or **📂 Local File**
3. Paste a URL or browse to a file
4. Set chunk length and output folder
5. Press **▶ DOWNLOAD & SPLIT**

Output: `<output_folder>/<title>_chunks/<title>_0000.wav`, `_0001.wav`, …

### 🔄 Convert mode
Download from a URL and save directly as a chosen audio format.

1. Click **🔄 Convert**
2. Paste a URL
3. Pick an output format from the dropdown
4. Press **▶ DOWNLOAD & CONVERT**

Output: `<output_folder>/<title>.<ext>`

### 📋 Playlist mode
Download and convert every track in a playlist, album, or channel.

1. Click **📋 Playlist**
2. Paste a playlist URL (YouTube, SoundCloud, Bandcamp, etc.)
3. Pick an output format from the dropdown
4. Press **▶ DOWNLOAD PLAYLIST**

Output: `<output_folder>/<playlist_title>/<track_title>.<ext>`

Supports YouTube playlists, SoundCloud sets, Bandcamp albums, and [any playlist source yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

### Output formats

| Format | Details |
|--------|---------|
| WAV | Lossless PCM, 44.1 kHz |
| MP3 320 kbps | Highest quality lossy |
| MP3 192 kbps | Good quality, smaller size |
| MP3 128 kbps | Smaller size |
| AAC 256 kbps | Efficient lossy, broad compatibility |
| FLAC | Lossless compressed |
| OGG Vorbis 192 kbps | Open format lossy |
| OPUS 128 kbps | Modern efficient lossy |

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
