#!/usr/bin/env python3
"""
build.py — Cross-platform PyInstaller build script for AudioSplitter.

Usage:
    python build.py

Output:
    dist/AudioSplitter          (macOS / Linux)
    dist/AudioSplitter.exe      (Windows)
"""

import subprocess
import sys
import shutil
import platform
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────────────

APP_NAME    = "AudioSplitter"
ENTRY_POINT = "audio_splitter.py"
DIST_DIR    = Path("dist")
BUILD_DIR   = Path("build")
SPEC_FILE   = Path(f"{APP_NAME}.spec")


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str, colour: str = ""):
    codes = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", "cyan": "\033[96m"}
    reset = "\033[0m"
    prefix = codes.get(colour, "")
    print(f"{prefix}{msg}{reset}")


def run(cmd: list, error_msg: str):
    log(f"  $ {' '.join(str(c) for c in cmd)}", "cyan")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log(f"\n✗ {error_msg}", "red")
        sys.exit(1)


# ── Steps ─────────────────────────────────────────────────────────────────────

def check_entry_point():
    if not Path(ENTRY_POINT).exists():
        log(f"✗ Entry point '{ENTRY_POINT}' not found. Run build.py from the project root.", "red")
        sys.exit(1)
    log(f"✓ Found {ENTRY_POINT}", "green")


def install_pyinstaller():
    if shutil.which("pyinstaller"):
        log("✓ PyInstaller already installed", "green")
        return
    log("→ Installing PyInstaller…", "yellow")
    run([sys.executable, "-m", "pip", "install", "pyinstaller", "--break-system-packages"],
        "Failed to install PyInstaller.")
    log("✓ PyInstaller installed", "green")


def clean():
    log("→ Cleaning previous build artifacts…", "yellow")
    for path in [DIST_DIR, BUILD_DIR, SPEC_FILE]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    log("✓ Clean", "green")


def build():
    os_name = platform.system()
    log(f"→ Building for {os_name}…", "yellow")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",               # Single executable file
        "--windowed",              # No terminal window (GUI app)
        "--name", APP_NAME,
        "--clean",                 # Clean PyInstaller cache before build
    ]

    # macOS: embed a minimal icon and mark as a proper app bundle
    if os_name == "Darwin":
        cmd += ["--osx-bundle-identifier", "com.audiosplitter.app"]

    cmd.append(ENTRY_POINT)

    run(cmd, "PyInstaller build failed.")


def report():
    os_name = platform.system()
    ext     = ".exe" if os_name == "Windows" else ""
    output  = DIST_DIR / f"{APP_NAME}{ext}"

    if output.exists():
        size_mb = output.stat().st_size / (1024 * 1024)
        log(f"\n✓ Build complete!", "green")
        log(f"  Output:  {output}", "green")
        log(f"  Size:    {size_mb:.1f} MB", "green")

        log("\n── Distribution notes ──────────────────────────────────────────")
        if os_name == "Windows":
            log("  • Ship:  dist/AudioSplitter.exe")
            log("  • Users need ffmpeg installed and on PATH, or they can set")
            log("    the path inside the app's TOOL PATHS section.")
            log("  • Windows Defender may flag the .exe — this is a known")
            log("    PyInstaller false positive. Right-click → Run anyway.")
        elif os_name == "Darwin":
            log("  • Ship:  dist/AudioSplitter")
            log("  • macOS may block unsigned apps. To allow, users can:")
            log("    right-click → Open, or run:")
            log("    xattr -d com.apple.quarantine dist/AudioSplitter")
        else:
            log("  • Ship:  dist/AudioSplitter")
            log("  • Make executable if needed:  chmod +x dist/AudioSplitter")

        log("\n── ffmpeg / yt-dlp reminder ────────────────────────────────────")
        log("  These are NOT bundled — users still need them installed.")
        log("  See resources.txt for installation instructions per platform.")
        log("────────────────────────────────────────────────────────────────")
    else:
        log(f"✗ Expected output not found at {output}", "red")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("\n══ AudioSplitter Build Script ══════════════════════════════════\n")
    check_entry_point()
    install_pyinstaller()
    clean()
    build()
    report()
    log("\nDone.\n", "green")
