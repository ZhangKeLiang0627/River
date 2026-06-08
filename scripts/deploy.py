"""Package the River PySide6 application with Nuitka.

Usage:
    conda activate pyside6
    python scripts/deploy.py

Output:
    dist/RIVER/  — standalone distribution directory

Customize:
    Modify build_args() to add/remove Nuitka flags as needed.
"""

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = PROJECT_ROOT / "main.py"

# Import runtime metadata from the app's config module.
sys.path.insert(0, str(PROJECT_ROOT))
from app.common.config import cfg  # noqa: E402

APP_NAME = cfg.appName
VERSION = cfg.appVersion
# Construct a minimal metadata dict for the packager
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


def build_args() -> list[str]:
    nuitka = f'"{sys.executable}" -m nuitka'
    args = [nuitka, "--standalone"]

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
        # args.append("--msvc=latest") # Use latest MSVC
        args.append("--mingw64")  # Use MinGW
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
        args.append(f"--macos-app-version={META['version']}")
    else:
        # Linux
        args.append("--include-qt-plugins=platforms")
        icon = _icon_path()
        if icon:
            args.append(f"--linux-icon={icon}")

    args.append(f"--output-dir={PROJECT_ROOT / 'dist'}")
    args.append(str(MAIN_SCRIPT))
    return args


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_args()
    command = " ".join(args)

    print(f"--- Nuitka build command ---\n{command}\n")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        return result.returncode

    print(f"\nDone.  Artifact: {PROJECT_ROOT / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
