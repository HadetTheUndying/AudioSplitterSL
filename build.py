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
ICON_PNG    = Path("icon.png")
ICON_ICO    = Path("icon.ico")
ICON_ICNS   = Path("icon.icns")


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
    else:
        log("→ Installing PyInstaller…", "yellow")
        run([sys.executable, "-m", "pip", "install", "pyinstaller", "--break-system-packages"],
            "Failed to install PyInstaller.")
        log("✓ PyInstaller installed", "green")

    # Pillow is required by PyInstaller for icon processing
    try:
        from PIL import Image  # noqa: F401
        log("✓ Pillow already installed", "green")
    except ImportError:
        log("→ Installing Pillow…", "yellow")
        run([sys.executable, "-m", "pip", "install", "Pillow", "--break-system-packages"],
            "Failed to install Pillow.")
        log("✓ Pillow installed", "green")


def _draw_icon(SIZE=512):
    """Render the AudioSplitter icon and return a Pillow Image."""
    from PIL import Image, ImageDraw

    img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    BG     = (29,  32,  33,  255)
    BORDER = (80,  73,  69,  180)
    ACCENT = (215, 153, 33,  255)
    BLUE   = (131, 165, 152, 255)
    TEXT   = (235, 219, 178, 200)

    cx, cy = SIZE // 2, SIZE // 2

    draw.rounded_rectangle([20, 20, SIZE-20, SIZE-20], radius=90, fill=BG, outline=BORDER, width=5)

    bar_heights = [40, 80, 140, 200, 140, 80, 40]
    bar_w, gap  = 34, 14
    total_w     = len(bar_heights) * bar_w + (len(bar_heights) - 1) * gap
    start_x     = cx - total_w // 2

    for i, h in enumerate(bar_heights):
        bx = start_x + i * (bar_w + gap)
        draw.rounded_rectangle([bx, cy - h//2, bx + bar_w, cy + h//2],
                                radius=bar_w//2, fill=ACCENT if i == 3 else BLUE)

    sx0, sy0, sx1, sy1 = cx-160, cy+100, cx+160, cy-100
    for i in range(0, 12, 2):
        t0, t1 = i/12, (i+0.85)/12
        draw.line([int(sx0+(sx1-sx0)*t0), int(sy0+(sy1-sy0)*t0),
                   int(sx0+(sx1-sx0)*t1), int(sy0+(sy1-sy0)*t1)], fill=TEXT, width=6)

    hr = 22
    draw.ellipse([sx0-hr-10, sy0-hr, sx0+hr-10, sy0+hr], outline=TEXT, width=5)
    draw.ellipse([sx1-hr+10, sy1-hr, sx1+hr+10, sy1+hr], outline=TEXT, width=5)

    return img


def _make_icns_macos(img):
    """Use macOS iconutil to produce a genuine .icns file."""
    import tempfile
    from PIL import Image

    iconset = Path(tempfile.mkdtemp()) / "AppIcon.iconset"
    iconset.mkdir()

    specs = [
        (16,   "16x16"),    (32,   "16x16@2x"),
        (32,   "32x32"),    (64,   "32x32@2x"),
        (128,  "128x128"),  (256,  "128x128@2x"),
        (256,  "256x256"),  (512,  "256x256@2x"),
        (512,  "512x512"),  (1024, "512x512@2x"),
    ]
    for px, name in specs:
        img.resize((px, px), Image.LANCZOS).save(
            str(iconset / f"icon_{name}.png"), "PNG"
        )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(ICON_ICNS)],
        check=True
    )
    shutil.rmtree(str(iconset.parent))
    log(f"✓ Real .icns generated via iconutil", "green")


def generate_icons():
    """Generate icon.png, icon.ico, and icon.icns."""
    if ICON_PNG.exists() and ICON_ICO.exists() and ICON_ICNS.exists():
        log("✓ Icons already present", "green")
        return

    log("→ Generating icons…", "yellow")
    from PIL import Image

    img = _draw_icon(512)

    # PNG — source / reference
    img.save(str(ICON_PNG), "PNG")

    # ICO — Windows multi-size
    ico_sizes = [16, 32, 48, 64, 128, 256]
    ico_imgs  = [img.resize((s, s), Image.LANCZOS) for s in ico_sizes]
    ico_imgs[0].save(str(ICON_ICO), format="ICO",
                     sizes=[(s, s) for s in ico_sizes],
                     append_images=ico_imgs[1:])

    # ICNS — macOS: use iconutil for a real Apple ICNS file
    if platform.system() == "Darwin" and shutil.which("iconutil"):
        _make_icns_macos(img)
    else:
        # Fallback: build a real ICNS binary (PNG-encoded chunks per Apple spec)
        # This works on all platforms and is accepted by PyInstaller on macOS runners
        import struct
        from io import BytesIO
        SIZE_TYPES = [
            (16,   b'icp4'), (32,   b'icp5'), (64,   b'icp6'),
            (128,  b'ic07'), (256,  b'ic08'), (512,  b'ic09'), (1024, b'ic10'),
        ]
        chunks = b''
        for size, ostype in SIZE_TYPES:
            buf = BytesIO()
            img.resize((size, size), Image.LANCZOS).save(buf, format='PNG')
            png = buf.getvalue()
            chunks += ostype + struct.pack('>I', 8 + len(png)) + png
        ICON_ICNS.write_bytes(b'icns' + struct.pack('>I', 8 + len(chunks)) + chunks)

    log(f"✓ Icons saved: {ICON_PNG}, {ICON_ICO}, {ICON_ICNS}", "green")


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
        "--windowed",              # No terminal window
        "--name", APP_NAME,
        "--clean",
    ]

    if os_name == "Darwin":
        # onedir on macOS avoids the --onefile + .app bundle deprecation warning
        cmd += [
            "--onedir",
            "--icon", str(ICON_ICNS),
            "--osx-bundle-identifier", "com.audiosplitter.app",
        ]
    elif os_name == "Windows":
        cmd += [
            "--onefile",
            "--icon", str(ICON_ICO),
        ]
    else:
        cmd += ["--onefile"]

    cmd.append(ENTRY_POINT)
    run(cmd, "PyInstaller build failed.")


def report():
    os_name = platform.system()
    if os_name == "Darwin":
        output = DIST_DIR / f"{APP_NAME}.app"
        if not output.exists():
            output = DIST_DIR / APP_NAME  # fallback to binary
    elif os_name == "Windows":
        output = DIST_DIR / f"{APP_NAME}.exe"
    else:
        output = DIST_DIR / APP_NAME

    if output.exists():
        if output.is_dir():
            size_mb = sum(f.stat().st_size for f in output.rglob("*") if f.is_file()) / (1024*1024)
        else:
            size_mb = output.stat().st_size / (1024 * 1024)

        log(f"\n✓ Build complete!", "green")
        log(f"  Output:  {output}", "green")
        log(f"  Size:    {size_mb:.1f} MB", "green")

        log("\n── Distribution notes ──────────────────────────────────────────")
        if os_name == "Windows":
            log("  • Ship:  dist/AudioSplitter.exe")
            log("  • Windows Defender may flag the .exe — known PyInstaller")
            log("    false positive. Right-click → Run anyway.")
        elif os_name == "Darwin":
            log("  • Ship:  dist/AudioSplitter.app (zip it before distributing)")
            log("  • macOS may block unsigned apps on first launch.")
            log("    Right-click → Open, or run:")
            log("    xattr -dr com.apple.quarantine dist/AudioSplitter.app")
        else:
            log("  • Ship:  dist/AudioSplitter")
            log("  • Mark executable if needed:  chmod +x dist/AudioSplitter")

        log("\n── ffmpeg / yt-dlp reminder ────────────────────────────────────")
        log("  These are NOT bundled — users still need them installed.")
        log("  See resources.txt for installation instructions per platform.")
        log("────────────────────────────────────────────────────────────────")
    else:
        log(f"✗ Expected output not found at {output}", "red")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("\n== AudioSplitter Build Script ==================================\n")
    check_entry_point()
    install_pyinstaller()
    generate_icons()
    clean()
    build()
    report()
    log("\nDone.\n", "green")
