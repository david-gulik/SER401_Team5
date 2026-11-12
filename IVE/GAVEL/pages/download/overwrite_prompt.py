"""Ask whether to replace files a download found already in the course folder."""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtWidgets import QMessageBox, QWidget

from GAVEL.pages.download.viewmodel import OverwriteChoice

# A Download All can refuse dozens of files; past this many the prompt gives a count.
MAX_LISTED = 8

OVERWRITE_ONCE_LABEL = "Overwrite"
OVERWRITE_SESSION_LABEL = "Overwrite for this session"
SKIP_LABEL = "Skip"


def overwrite_prompt_text(paths: Sequence[str]) -> str:
    """The question for ``paths``, listing at most MAX_LISTED of them."""
    count = len(paths)
    if count == 1:
        head = "1 file is already in the course folder:"
        question = "Replace it with a fresh download?"
    else:
        head = f"{count} files are already in the course folder:"
        question = "Replace them with a fresh download?"
    listed = "\n".join(paths[:MAX_LISTED])
    if count > MAX_LISTED:
        listed += f"\nand {count - MAX_LISTED} more"
    return (
        f"{head}\n\n{listed}\n\n{question} "
        f"{OVERWRITE_SESSION_LABEL} also replaces files without asking until GAVEL closes. "
        f"{SKIP_LABEL} keeps them as they are."
    )


def ask_overwrite(parent: QWidget | None, paths: Sequence[str]) -> OverwriteChoice:
    """Show the prompt and wait for an answer; closing it counts as Skip."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Files already downloaded")
    box.setText(overwrite_prompt_text(paths))
    once = box.addButton(OVERWRITE_ONCE_LABEL, QMessageBox.ButtonRole.AcceptRole)
    session = box.addButton(OVERWRITE_SESSION_LABEL, QMessageBox.ButtonRole.AcceptRole)
    skip = box.addButton(SKIP_LABEL, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(skip)
    box.setEscapeButton(skip)
    box.exec()
    clicked = box.clickedButton()
    if clicked is once:
        return OverwriteChoice.ONCE
    if clicked is session:
        return OverwriteChoice.SESSION
    return OverwriteChoice.SKIP
