import sys

from PySide6.QtCore import QUrl, Qt, QProcess, QStandardPaths
from PySide6.QtGui import QDesktopServices

def bringWindowToTop(window) -> None:
    window.show()
    window.setWindowState(
        (window.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
    )
    window.raise_()
    window.activateWindow()

