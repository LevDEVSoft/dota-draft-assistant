import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from draft_assistant.gui.app import Window
from draft_assistant.gui.animated_background import AnimatedBackground


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def add(window, value, side):
    input_box = window.enemy if side == "enemy" else window.ally
    input_box.setText(value)
    window.add_hero(input_box, side)


def test_chip_add_remove_and_cross_team_status(app):
    window = Window()
    window.show()
    add(window, "sf", "enemy")
    assert window.state.enemies == ["shadow_fiend"]
    assert window.enemy_chips.count() == 1

    add(window, "sf", "ally")
    assert window.status.text() == "Shadow Fiend is already on the enemy side."
    assert window.state.allies == []

    close = window.enemy_chips.itemAt(0).widget().findChild(QToolButton)
    close.click()
    QTest.qWait(200)
    assert window.state.enemies == []
    assert window.enemy_chips.count() == 0


def test_success_clears_status_and_explanation_toggles(app):
    window = Window()
    window.show()
    add(window, "not-a-hero", "enemy")
    assert window.status.text() == "Unknown hero: not-a-hero"
    add(window, "ds", "enemy")
    assert window.status.text() == ""
    assert window.enemy.text() == ""

    window.show_explain()
    assert window.explanation_panel.isVisible()
    window.toggle_explanation()
    assert not window.explanation_panel.isVisible()


def test_animated_background_can_pause_and_resume(app):
    background = AnimatedBackground()
    before = [(particle.x, particle.y) for particle in background.particles]
    background.advance()
    assert [(particle.x, particle.y) for particle in background.particles] != before
    background.set_animation_enabled(False)
    assert not background.animation_enabled
    background.set_animation_enabled(True)
    assert background.animation_enabled


def test_window_background_toggle_stops_and_starts_timer(app):
    window = Window()
    window.background_toggle.setChecked(False)
    assert not window.background.animation_enabled
    window.background_toggle.setChecked(True)
    assert window.background.animation_enabled
