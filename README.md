# AudioSplitter

A cross-platform desktop GUI for downloading, converting, and splitting audio from URLs or local files.

Built with Python + tkinter. Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for URL downloads and [ffmpeg](https://ffmpeg.org) for all audio processing.

---

> **AI Notice:** This software was developed with the assistance of [Claude](https://claude.ai) by Anthropic. All code has been reviewed and tested by a human developer.

---

## Features

- **Split** — download from a URL or open a local file and split the audio into fixed-length WAV chunks
- **Convert (Audio)** — download from a URL and convert directly to a chosen audio format
- **Convert (Video)** — download from a URL or open a local file, scale to a target resolution, and optionally clip to a time range
- **Playlist** — download and convert every track in a playlist, album, or set to a chosen audio format
- **Output format selector** — WAV, MP3 (320/192/128 kbps), AAC, FLAC, OGG Vorbis, OPUS
- **Video scale presets** — Original, Half, Quarter, 1080p, 720p, 480p, 360p
- **Configurable chunk length** — type any duration in seconds or use presets (15, 29.9, 30, 60)
- **Gruvbox dark theme**
- **Collapsible Tool Paths panel** — manually set yt-dlp and ffmpeg paths if auto-detection fails
- **Log viewer** — pop-out log window accessible from the title bar
- **Persistent settings** — tool paths and output folder saved across sessions

---

## Releases

Pre-built executables for macOS and Windows are available on the [Releases](../../releases) page — no Python installation required.

ffmpeg and yt-dlp are **not** bundled and must be installed separately. See the setup instructions for your OS below.

### macOS — Pre-built binary requires executable permission

The macOS binary downloaded from Releases loses its executable bit during upload. Before running it for the first time:

```bash
chmod +x AudioSplitter-macOS
./AudioSplitter-macOS
```

You will also need to clear the Gatekeeper quarantine flag on first launch:

```bash
xattr -d com.apple.quarantine AudioSplitter-macOS
```

Or right-click the file → **Open** → **Open** in the dialog.

---

## Persistent Settings

AudioSplitter saves preferences to `~/.audiosplitter_config.json` automatically:

- **yt-dlp path** — saved when you click Verify & Save Paths
- **ffmpeg path** — saved when you click Verify & Save Paths
- **Output folder** — saved immediately when changed via Browse

The config file is OS-specific. Paths are stored as detected or entered on your system and will differ between macOS, Windows, and Linux. It is not intended to be shared across machines.

To reset to defaults, delete `~/.audiosplitter_config.json` and relaunch the app.

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
> yt-dlp is only required for URL, Convert, and Playlist modes. Local file modes work with just ffmpeg.

**2. Run from source**
```bash
python3 audio_splitter.py
```

**3. Build a standalone app**
```bash
python3 build.py
```
Output: `dist/AudioSplitter`

> **Gatekeeper warning:** macOS will block unsigned apps on first launch. Right-click the binary → Open, or run:
> ```bash
> xattr -d com.apple.quarantine dist/AudioSplitter
> ```

**Tool path note:** Homebrew binaries may not be detected when launching outside a terminal. If yt-dlp or ffmpeg are not found automatically, click **[ + ] Tool Paths** in the app and set them manually:
```
yt-dlp:  /opt/homebrew/bin/yt-dlp
ffmpeg:  /opt/homebrew/bin/ffmpeg
```
Click **Verify & Save Paths** — these will be remembered on next launch.

---

### Windows

**1. Install dependencies**
```bat
winget install ffmpeg
winget install yt-dlp
```

> yt-dlp is only required for URL, Convert, and Playlist modes. Local file modes work with just ffmpeg.

tkinter is bundled with the official Python installer from https://www.python.org/downloads/windows/ — ensure **tcl/tk and IDLE** is checked during setup.

The app will attempt to auto-detect ffmpeg and yt-dlp from common winget install locations. If they are not found, use the **[ + ] Tool Paths** panel to set the paths manually.

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

> yt-dlp is only required for URL, Convert, and Playlist modes. Local file modes work with just ffmpeg.

**2. Run from source**
```bash
python3 audio_splitter.py
```

**3. Build a standalone binary**
```bash
python3 build.py
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

### Split mode

Download from a URL or open a local file and split its audio into equal-length WAV chunks.

1. Click **Split**
2. Choose **URL** or **Local File**
3. Paste a URL or browse to a file
4. Set the chunk length (in seconds) and output folder
5. Press **DOWNLOAD & SPLIT**

Output: `<output_folder>/<title>_chunks/<title>_0000.wav`, `_0001.wav`, ...

Supported local input formats: `mp3` `wav` `aac` `flac` `ogg` `m4a` `opus` `wma` `mp4` `mkv` `mov` `avi` `webm` `m4v` `flv` `wmv`

---

### Convert mode — Audio

Download from a URL and save directly as a chosen audio format. No splitting.

1. Click **Convert**, then select **Audio**
2. Paste a URL
3. Pick an output format from the dropdown
4. Press **CONVERT**

Output: `<output_folder>/<title>.<ext>`

---

### Convert mode — Video

Download from a URL or open a local file, scale it to a target resolution, and optionally clip to a time range. Output is always MP4.

1. Click **Convert**, then select **Video**
2. Choose **URL** or **Local File**
3. Select a scale preset from the dropdown
4. Optionally enter a **Start** time and **Duration** in `HH:MM:SS` format to clip the output. Leave both blank to process the full file.
5. Press **CONVERT**

Output: `<output_folder>/<title>_converted.mp4`

Scale presets:

| Preset | ffmpeg filter |
|--------|--------------|
| Original size | no scaling |
| Half size | `scale=iw/2:ih/2` |
| Quarter size | `scale=iw/4:ih/4` |
| 1080p | `scale=1920:1080` |
| 720p | `scale=1280:720` |
| 480p | `scale=854:480` |
| 360p | `scale=640:360` |

---

### Playlist mode

Download and convert every track in a playlist, album, or channel to a chosen audio format.

1. Click **Playlist**
2. Paste a playlist URL
3. Pick an output format from the dropdown
4. Press **DOWNLOAD PLAYLIST**

Output: `<output_folder>/<playlist_title>/<track_title>.<ext>`

Each track is downloaded and converted sequentially. Failed tracks are logged and skipped — the rest of the playlist continues. Supports YouTube playlists, SoundCloud sets, Bandcamp albums, and [any source yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

---

### Output formats

| Format | Details |
|--------|---------|
| WAV | Lossless PCM, 44.1 kHz |
| MP3 320 kbps | Highest quality lossy |
| MP3 192 kbps | Good quality, smaller size |
| MP3 128 kbps | Smallest MP3 |
| AAC 256 kbps | Efficient lossy, broad device compatibility |
| FLAC | Lossless compressed |
| OGG Vorbis 192 kbps | Open format lossy |
| OPUS 128 kbps | Modern efficient lossy |

---

### Tool Paths

Click **[ + ] Tool Paths** to expand the panel. Enter full paths to yt-dlp and ffmpeg and click **Verify & Save Paths**. Paths are validated on save and persist across sessions in `~/.audiosplitter_config.json`.

The app attempts auto-detection on launch using `PATH` and common install locations for each platform. If both tools are found automatically the panel can stay collapsed.

---

### Log viewer

Click **Log** in the title bar to open the log in a separate resizable window. The log captures all activity including download progress, ffmpeg output, errors, and completion status. New entries appear in both the main app and the pop-out window simultaneously.

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
| `build.py` | Builds a standalone executable via PyInstaller, generates icons |
| `generate_icons.py` | Standalone icon generator (PNG, ICO, ICNS) |
| `icon.png` | Source icon — 512x512 RGBA |
| `icon.ico` | Windows icon — multi-size ICO |
| `icon.icns` | macOS icon — Apple ICNS format |
| `resources.txt` | Dependency and troubleshooting reference |
| `.github/workflows/build.yml` | CI workflow for automated macOS and Windows builds |

---

## License

[MIT](LICENSE)
