"""Package the River PySide6 application with Nuitka.

Usage:
    conda activate pyside6
    python scripts/deploy.py

Output (platform-dependent):
    dist/RIVER.dist/    — Windows / Linux standalone directory
    dist/RIVER.app/     — macOS application bundle

Customize:
    Modify build_args() to add/remove Nuitka flags as needed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
DIST_DIR = PROJECT_ROOT / "dist"

# Import runtime metadata from the app's config module.
sys.path.insert(0, str(PROJECT_ROOT))
from app.common.config import cfg  # noqa: E402

APP_NAME = cfg.appName
VERSION = cfg.appVersion
META = {
    "version": VERSION,
    "company": "kkl",
    "product": APP_NAME,
    "file_description": APP_NAME,
    "copyright": f"Copyright(C) 2026 kkl",
}

# ---------------------------------------------------------------------------
# Nuitka argument builders
# ---------------------------------------------------------------------------
PLATFORM_INCLUDE_PACKAGES: dict[str, list[str]] = {}


def build_include_args() -> list[str]:
    pkgs = list(PLATFORM_INCLUDE_PACKAGES.get(sys.platform, []))
    return [f"--include-package={pkg}" for pkg in pkgs]


def _icon_path() -> str | None:
    """Return the icon path for the current platform, or ``None``."""
    if sys.platform == "win32":
        p = PROJECT_ROOT / "app" / "resources" / "images" / "river.ico"
    elif sys.platform == "darwin":
        p = PROJECT_ROOT / "app" / "resources" / "images" / "river.icns"
    else:
        p = PROJECT_ROOT / "app" / "resources" / "images" / "river.png"
    return str(p) if p.is_file() else None


def _clean_old():
    """Remove leftovers from previous builds."""
    for pattern in ("RIVER.*", "main.*"):
        for d in DIST_DIR.glob(pattern):
            if d.is_dir():
                shutil.rmtree(d)


def build_args() -> list[str]:
    nuitka = f'"{sys.executable}" -m nuitka'
    args = [nuitka, "--standalone"]

    # Output naming — use APP_NAME so output dir is predictable
    args.append(f"--output-filename={APP_NAME}")

    # PySide6
    args.append("--plugin-enable=pyside6")

    # Extra packages the bundler might miss
    args.extend(build_include_args())

    # Convenience
    args.append("--assume-yes-for-downloads")

    # Platform-specific flags
    if sys.platform == "win32":
        args.append("--windows-console-mode=disable")
        icon = _icon_path()
        if icon:
            args.append(f'--windows-icon-from-ico={icon}')
        args.append("--disable-ccache")
        args.append(f"--company-name={META['company']}")
        args.append(f'--product-name="{META["product"]}"')
        args.append(f"--file-version={META['version']}")
        args.append(f"--product-version={META['version']}")
        args.append(f'--file-description="{META["file_description"]}"')
        args.append(f'--copyright="{META["copyright"]}"')
    elif sys.platform == "darwin":
        icon = _icon_path()
        if icon:
            args.append(f"--macos-app-icon={icon}")
        args.append("--static-libpython=no")
        args.append("--macos-create-app-bundle")
        args.append("--macos-app-mode=gui")
        args.append(f"--macos-app-name={META['product']}")
        args.append(f"--macos-app-version={META['version']}")
    else:
        # Linux
        args.append("--include-qt-plugins=platforms")
        icon = _icon_path()
        if icon:
            args.append(f"--linux-icon={icon}")

    args.append(f"--output-dir={DIST_DIR}")
    args.append(str(MAIN_SCRIPT))
    return args


def _rename_output(src_name: str, dst_name: str, kind: str) -> Path:
    """Rename Nuitka output directory from src_name to dst_name.

    ``kind`` is the suffix: ``"dist"`` or ``"app"``.
    Returns the resulting path.
    """
    src = DIST_DIR / f"{src_name}.{kind}"
    dst = DIST_DIR / f"{dst_name}.{kind}"
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))
        print(f"  + Renamed {src.name} -> {dst.name}")
    elif dst.exists():
        print(f"  + {dst.name} already exists")
    else:
        print(f"  + {src.name} not found -- Nuitka may have used a different name")
    return dst


def _post_build():
    """Post-build cleanup and standardisation across platforms.

    Nuitka names the output directory after the entry script (``main.py``),
    so we rename it to ``{APP_NAME}.dist`` (or ``.app`` on macOS) for
    predictable CI artifact paths.
    """
    if sys.platform == "darwin":
        # Rename main.app → RIVER.app
        _rename_output("main", APP_NAME, "app")
    else:
        # Rename main.dist → RIVER.dist
        _rename_output("main", APP_NAME, "dist")

    # Remove build cache directories
    for d in DIST_DIR.glob("*.build"):
        if d.is_dir():
            shutil.rmtree(d)

    if sys.platform == "linux":
        # Standardise Linux binary name to APP_NAME.bin
        dist_dir = DIST_DIR / f"{APP_NAME}.dist"
        if dist_dir.exists():
            bin_src = dist_dir / APP_NAME       # Nuitka omits .bin on some versions
            bin_dst = dist_dir / f"{APP_NAME}.bin"
            if bin_src.exists() and not bin_dst.exists():
                shutil.move(str(bin_src), str(bin_dst))
            if bin_dst.exists():
                bin_dst.chmod(0o755)


def _report_paths():
    """Print paths of built artifacts."""
    for pattern in (f"{APP_NAME}.dist", f"{APP_NAME}.app"):
        p = DIST_DIR / pattern
        if p.exists():
            print(f"  [OK] {p}")
            if p.is_dir():
                for child in sorted(p.iterdir()):
                    if child.is_file() and not child.name.endswith((".py", ".pyc")):
                        print(f"      - {child.name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    _clean_old()

    args = build_args()
    command = " ".join(args)

    print(f"--- Nuitka build command ---\n{command}\n")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        return result.returncode

    _post_build()
    print(f"\n--- Build finished ---")
    _report_paths()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
