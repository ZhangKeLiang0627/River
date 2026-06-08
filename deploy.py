"""
deploy.py — Nuitka build script for River

Compiles River (PySide6 app) into a standalone distribution.
Run:  python deploy.py

Platform-specific outputs (after build):
    Windows : dist/RIVER.dist/   (contains RIVER.exe)
    macOS   : dist/RIVER.app/    (macOS app bundle)
    Linux   : dist/RIVER.dist/   (contains RIVER.bin)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ------------------------------------------------------------
# Metadata
# ------------------------------------------------------------
APP_NAME = "RIVER"
PROJECT_NAME = "River"

# Read VERSION from app config
VERSION = "0.0.1"
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.common.config import Config
    VERSION = getattr(Config, "appVersion", VERSION)
except ImportError:
    pass

SYSTEM = sys.platform
ROOT = Path(__file__).parent
DIST = ROOT / "dist"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _clean_old():
    """Remove leftovers from previous builds."""
    for d in DIST.glob("RIVER.*"):
        if d.is_dir():
            shutil.rmtree(d)
    # Also clean old main.* artifacts
    for d in DIST.glob("main.*"):
        if d.is_dir():
            shutil.rmtree(d)


def _rename_output(src_name: str, dst_name: str, kind: str) -> Path:
    """Rename Nuitka output dir from src_name to dst_name.

    kind is the suffix: "dist" or "app"
    """
    src = DIST / f"{src_name}.{kind}"
    dst = DIST / f"{dst_name}.{kind}"
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))
        print(f"  → Renamed {src.name} → {dst.name}")
    elif dst.exists():
        print(f"  ✓ Already exists: {dst.name}")
    else:
        print(f"  ⚠️  Not found: {src.name} — output may have a different name")
    return dst


# ------------------------------------------------------------
# Nuitka flags
# ------------------------------------------------------------
def _common_flags() -> list[str]:
    return [
        sys.executable, "-m", "nuitka",
        "--standalone",
        f"--output-dir={DIST}",
        f"--output-filename={APP_NAME}",
        "--enable-plugin=pyside6",
        "--include-package=app",
        "--include-package=PIL",
        "--include-package=numpy",
        "--follow-imports",
        "--show-memory",
        "--show-progress",
        "--warn-implicit-exceptions",
        "--warn-unusual-code",
    ]


# ------------------------------------------------------------
# Platform builds
# ------------------------------------------------------------
def build_windows():
    flags = _common_flags()

    # App icon
    logo = ROOT / "app" / "resources" / "images" / "logo.png"
    if logo.exists():
        flags.append(f"--windows-icon-from-ico={logo}")

    flags += [
        f"--windows-company-name=kkl",
        f"--windows-product-name={PROJECT_NAME}",
        f"--windows-file-version={VERSION}",
        f"--windows-product-version={VERSION}",
        f"--windows-file-description={PROJECT_NAME} - Image Processing Tool",
        "--disable-ccache",
    ]

    print(f"\nBuilding {PROJECT_NAME} v{VERSION} for Windows ...")
    subprocess.run(flags + ["main.py"], check=True)
    _rename_output("main", APP_NAME, "dist")
    print(f"✅ Output: {DIST / f'{APP_NAME}.dist' / APP_NAME}.exe")


def build_macos():
    flags = _common_flags()

    # macOS app icon (.icns) — optional
    icns = ROOT / "app" / "assets" / "logo.icns"
    if icns.exists():
        flags.append(f"--macos-app-icon={icns}")

    flags += [
        f"--macos-app-name={PROJECT_NAME}",
        f"--macos-app-version={VERSION}",
    ]

    print(f"\nBuilding {PROJECT_NAME} v{VERSION} for macOS ...")
    subprocess.run(flags + ["main.py"], check=True)

    # Nuitka may produce main.app (app bundle) or main.dist (standalone dir)
    # depending on version and flags. Handle both.
    app_bundle = _rename_output("main", APP_NAME, "app")

    # If no .app was created, check for .dist
    if not app_bundle.exists():
        dist_dir = _rename_output("main", APP_NAME, "dist")
        if dist_dir.exists():
            print("  ⚠️  macOS created .dist instead of .app — this is unusual for a GUI app.")
    else:
        # Remove build cache folder
        build_dir = DIST / f"{APP_NAME}.build"
        if build_dir.exists():
            shutil.rmtree(build_dir)
        # Remove stray .dist folder if Nuitka also created one
        stray_dist = DIST / f"{APP_NAME}.dist"
        if stray_dist.exists():
            shutil.rmtree(stray_dist)

    print(f"✅ Output: {app_bundle}")


def build_linux():
    flags = _common_flags()

    print(f"\nBuilding {PROJECT_NAME} v{VERSION} for Linux ...")
    subprocess.run(flags + ["main.py"], check=True)

    dist_dir = _rename_output("main", APP_NAME, "dist")

    # Standardise binary name to APP_NAME.bin (Nuitka may omit the .bin
    # on some platforms / versions).
    bin_src = dist_dir / APP_NAME          # without .bin
    bin_dst = dist_dir / f"{APP_NAME}.bin"  # with .bin
    if bin_src.exists() and not bin_dst.exists():
        shutil.move(str(bin_src), str(bin_dst))
    if bin_dst.exists():
        bin_dst.chmod(0o755)
        print(f"✅ Output: {bin_dst}")
    else:
        print(f"⚠️  Binary not found inside {dist_dir}")

    # Remove build folder
    build_dir = DIST / f"{APP_NAME}.build"
    if build_dir.exists():
        shutil.rmtree(build_dir)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
def main():
    _clean_old()

    if SYSTEM == "win32":
        build_windows()
    elif SYSTEM == "darwin":
        build_macos()
    elif SYSTEM == "linux":
        build_linux()
    else:
        print(f"Unsupported platform: {SYSTEM}")
        sys.exit(1)

    print("\n=== Build finished ===")


if __name__ == "__main__":
    main()
