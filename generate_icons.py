#!/usr/bin/env python3
"""
Standalone icon generator for AudioSplitter.
Generates icon.png, icon.ico (Windows), and icon.icns (macOS real format).
Requires: Pillow
"""
import struct
from io import BytesIO
from PIL import Image, ImageDraw

SIZE = 512
img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Gruvbox colours
BG     = (29,  32,  33,  255)
BORDER = (80,  73,  69,  180)
ACCENT = (215, 153, 33,  255)
BLUE   = (131, 165, 152, 255)
TEXT   = (235, 219, 178, 200)

cx, cy = SIZE // 2, SIZE // 2

# Background rounded square
draw.rounded_rectangle([20, 20, SIZE-20, SIZE-20], radius=90, fill=BG, outline=BORDER, width=5)

# Waveform bars
bar_heights = [40, 80, 140, 200, 140, 80, 40]
bar_w, gap  = 34, 14
total_w     = len(bar_heights) * bar_w + (len(bar_heights) - 1) * gap
start_x     = cx - total_w // 2

for i, h in enumerate(bar_heights):
    bx = start_x + i * (bar_w + gap)
    draw.rounded_rectangle(
        [bx, cy - h // 2, bx + bar_w, cy + h // 2],
        radius=bar_w // 2,
        fill=ACCENT if i == 3 else BLUE
    )

# Scissors cut line (dashed diagonal)
sx0, sy0, sx1, sy1 = cx - 160, cy + 100, cx + 160, cy - 100
for i in range(0, 12, 2):
    t0, t1 = i / 12, (i + 0.85) / 12
    draw.line([
        int(sx0 + (sx1 - sx0) * t0), int(sy0 + (sy1 - sy0) * t0),
        int(sx0 + (sx1 - sx0) * t1), int(sy0 + (sy1 - sy0) * t1),
    ], fill=TEXT, width=6)

# Scissors handle rings
hr = 22
draw.ellipse([sx0 - hr - 10, sy0 - hr, sx0 + hr - 10, sy0 + hr], outline=TEXT, width=5)
draw.ellipse([sx1 - hr + 10, sy1 - hr, sx1 + hr + 10, sy1 + hr], outline=TEXT, width=5)

# ── Save PNG ──────────────────────────────────────────────────────────────────
img.save("icon.png", "PNG")
print("✓ icon.png")

# ── Save ICO (Windows multi-size) ─────────────────────────────────────────────
ico_sizes = [16, 32, 48, 64, 128, 256]
ico_imgs  = [img.resize((s, s), Image.LANCZOS) for s in ico_sizes]
ico_imgs[0].save("icon.ico", format="ICO",
                 sizes=[(s, s) for s in ico_sizes],
                 append_images=ico_imgs[1:])
print("✓ icon.ico")

# ── Save ICNS (macOS — real binary format, PNG-encoded chunks) ────────────────
# ICNS spec: magic 'icns' + total uint32 BE, then chunks of ostype + len + PNG
SIZE_TYPES = [
    (16,   b'icp4'),
    (32,   b'icp5'),
    (64,   b'icp6'),
    (128,  b'ic07'),
    (256,  b'ic08'),
    (512,  b'ic09'),
    (1024, b'ic10'),
]

chunks = b''
for size, ostype in SIZE_TYPES:
    resized  = img.resize((size, size), Image.LANCZOS)
    buf      = BytesIO()
    resized.save(buf, format='PNG')
    png_data = buf.getvalue()
    chunks  += ostype + struct.pack('>I', 8 + len(png_data)) + png_data

icns_data = b'icns' + struct.pack('>I', 8 + len(chunks)) + chunks
with open("icon.icns", "wb") as f:
    f.write(icns_data)
print("✓ icon.icns")
