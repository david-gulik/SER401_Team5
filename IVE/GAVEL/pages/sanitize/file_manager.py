from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


def show_in_file_manager(path: Path) -> None:
    """Open the system file manager at a folder, or at a file's folder with the file selected."""
    if path.is_file() and sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
        return
    folder = path if path.is_dir() else path.parent
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
