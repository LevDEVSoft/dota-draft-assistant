import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from draft_assistant.gui.app import Window
from draft_assistant.gui.animated_background import AnimatedBackground
from draft_assistant.gui.autocomplete import ranked_suggestions
from draft_assistant.gui.state import DraftState


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


@pytest.mark.parametrize(("query", "expected"), [
    ("z", "zeus"), ("ze", "zeus"), ("ds", "dark_seer"),
    ("dar", "dark_seer"), ("dw", "dark_willow"), ("db", "dawnbreaker"),
    ("lc", "legion_commander"), ("DS", "dark_seer"),
])
def test_ranked_suggestions_use_shared_aliases_case_insensitively(query, expected):
    state = DraftState()
    assert ranked_suggestions(query, state.heroes, state.aliases)[0] == expected


def test_exact_alias_is_ranked_before_weaker_name_match_and_selected_hero_is_hidden():
    state = DraftState()
    matches = ranked_suggestions("ds", state.heroes, state.aliases)
    assert matches[0] == "dark_seer"
    assert "dark_seer" not in ranked_suggestions("ds", state.heroes, state.aliases, ["dark_seer"])


def test_autocomplete_enter_navigation_and_escape(app):
    window = Window()
    window.show()
    window.enemy.setText("z")
    assert window.autocompleters[window.enemy].popup.isVisible()
    assert window.autocompleters[window.enemy].list.item(0).text() == "Zeus"
    QTest.keyClick(window.enemy, Qt.Key.Key_Return)
    assert window.state.enemies == ["zeus"]
    assert not window.autocompleters[window.enemy].popup.isVisible()

    window.ally.setText("d")
    completer = window.autocompleters[window.ally]
    assert completer.list.currentRow() == -1
    QTest.keyClick(window.ally, Qt.Key.Key_Down)
    first_row = completer.list.currentRow()
    QTest.keyClick(window.ally, Qt.Key.Key_Down)
    assert completer.list.currentRow() != first_row
    QTest.keyClick(window.ally, Qt.Key.Key_Escape)
    assert not completer.popup.isVisible()
