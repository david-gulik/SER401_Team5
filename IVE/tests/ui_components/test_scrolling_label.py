from __future__ import annotations

from PyQt6.QtCore import Qt

from GAVEL.ui_components.message_dialog import MESSAGE_MAX_HEIGHT, MessageDialog
from GAVEL.ui_components.scrolling_label import ScrollingLabel

LONG = "; ".join(f"Quiz Reports (Module {n} Quiz): 500 Server Error" for n in range(60))


def shown(qapp, widget):
    widget.show()
    for _ in range(5):
        qapp.processEvents()
    return widget


def test_short_text_takes_only_the_height_it_needs(qapp):
    label = ScrollingLabel(max_height=200)
    label.resize(400, 50)
    label.setText("Downloads complete.")

    height = label.sizeHint().height()
    assert 0 < height < 200
    assert height == label.content_height()


def test_long_text_stops_at_the_max_height_and_scrolls(qapp):
    label = ScrollingLabel(max_height=120)
    label.resize(400, 50)
    label.setText(LONG)
    shown(qapp, label)

    assert label.content_height() > 120
    assert label.sizeHint().height() == 120
    assert label.verticalScrollBar().maximum() > 0
    label.close()


def test_text_is_selectable_for_copying_by_hand(qapp):
    label = ScrollingLabel(max_height=120)

    assert label.label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_long_message_dialog_stays_a_reasonable_size(qapp):
    dialog = shown(qapp, MessageDialog(None, "Download failed", LONG, critical=True))

    assert dialog.windowTitle() == "Download failed"
    assert dialog.message.height() <= MESSAGE_MAX_HEIGHT
    assert dialog.height() < MESSAGE_MAX_HEIGHT + 150
    dialog.close()


def test_short_message_dialog_is_not_padded_to_the_max(qapp):
    dialog = shown(qapp, MessageDialog(None, "Download", "Roster saved."))

    assert dialog.message.height() < MESSAGE_MAX_HEIGHT / 2
    dialog.close()


def test_dialog_can_be_resized_and_the_text_area_grows_with_it(qapp):
    dialog = shown(qapp, MessageDialog(None, "Download failed", LONG, critical=True))
    assert dialog.isSizeGripEnabled()

    dialog.resize(dialog.width() + 200, dialog.height() + 300)
    for _ in range(5):
        qapp.processEvents()

    assert dialog.message.height() > MESSAGE_MAX_HEIGHT
    dialog.close()
