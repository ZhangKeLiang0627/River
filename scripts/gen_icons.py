"""Generate .ico and .icns icon files from SVG.

Usage:
    conda activate pyside6
    python scripts/gen_icons.py

Output:
    river.ico (sizes: 16, 24, 32, 48, 64, 128, 256)
    river.icns (sizes: 16, 32, 48, 64, 128, 256, 512, 1024)

Customize:
    Modify SVG_PATH to point to your own SVG file, and change
    OUT_DIR to set where the .ico / .icns files are written.

Dependencies: PySide6 (for SVG rendering), Pillow (for icon writing).
"""
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QImage
from PySide6.QtCore import QByteArray

SVG_PATH = Path(__file__).resolve().parent.parent / "app" / "resources" / "images" / "river.svg"
OUT_DIR = SVG_PATH.parent

# ICO needs sizes <= 256; ICNS goes up to 1024
ICO_SIZES = [256]
ICNS_SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]

# Render SVG once at high resolution, then downsample for sharpness
BASE_SIZE = 1024
_RESIZE_CACHE: dict[int, Image.Image] = {}


def _render_svg(svg_path: Path) -> Image.Image:
    """Render SVG at BASE_SIZE and return a PIL RGBA Image."""
    renderer = QSvgRenderer(str(svg_path))
    img = QImage(BASE_SIZE, BASE_SIZE, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    data = img.constBits().tobytes()
    return Image.frombuffer("RGBA", (BASE_SIZE, BASE_SIZE), data, "raw", "BGRA", 0, 1)


def get_icon(svg_path: Path, size: int) -> Image.Image:
    """Return the icon at *size* from the shared high-res render cache."""
    if size not in _RESIZE_CACHE:
        if not _RESIZE_CACHE:
            _RESIZE_CACHE["_src"] = _render_svg(svg_path)
        src = _RESIZE_CACHE["_src"]
        if size == BASE_SIZE:
            _RESIZE_CACHE[size] = src
        else:
            _RESIZE_CACHE[size] = src.resize((size, size), Image.LANCZOS)
    return _RESIZE_CACHE[size]


def main():
    svg = SVG_PATH
    if not svg.exists():
        print(f"SVG not found: {svg}", file=sys.stderr)
        return 1

    print(f"Rendering {svg} at {BASE_SIZE}×{BASE_SIZE} …")

    # --- ICO ---
    ico_images = [get_icon(svg, s) for s in ICO_SIZES]
    ico_path = OUT_DIR / "river.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=ico_images[1:],
    )
    print(f"Created {ico_path}  ({len(ico_images)} sizes: {ICO_SIZES})")

    # --- ICNS ---
    icns_images = [get_icon(svg, s) for s in ICNS_SIZES]
    icns_path = OUT_DIR / "river.icns"
    icns_images[0].save(
        icns_path,
        format="ICNS",
        sizes=[(s, s) for s in ICNS_SIZES],
        append_images=icns_images[1:],
    )
    print(f"Created {icns_path}  ({len(icns_images)} sizes: {ICNS_SIZES})")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
