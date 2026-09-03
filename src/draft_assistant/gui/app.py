"""PySide6 desktop application entry point."""
import sys

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget)

from draft_assistant.aliases import normalize_hero
from draft_assistant.cli import format_explanation
from .autocomplete import HeroAutocomplete
from .animated_background import AnimatedBackground
from .state import DraftState


class FlowLayout(QLayout):
    """A compact wrapping layout for drafted hero chips."""
    def __init__(self, parent=None):
        super().__init__(parent); self.items = []
        self.setContentsMargins(0, 0, 0, 0); self.setSpacing(6)
    def addItem(self, item): self.items.append(item)
    def count(self): return len(self.items)
    def itemAt(self, index): return self.items[index] if 0 <= index < len(self.items) else None
    def takeAt(self, index): return self.items.pop(index) if 0 <= index < len(self.items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._layout(QRect(0, 0, width, 0), True)
    def setGeometry(self, rect): super().setGeometry(rect); self._layout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self.items: size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
    def _layout(self, rect, test_only):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self.items:
            if not item.widget() or item.widget().isHidden(): continue
            next_x = x + item.sizeHint().width() + self.spacing()
            if next_x - self.spacing() > rect.right() and line_height:
                x, y, next_x, line_height = rect.x(), y + line_height + self.spacing(), rect.x() + item.sizeHint().width() + self.spacing(), 0
            if not test_only: item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x, line_height = next_x, max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


class HeroChip(QFrame):
    def __init__(self, name, remove):
        super().__init__(); self.setObjectName("heroChip")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self); row.setContentsMargins(10, 4, 5, 4); row.setSpacing(5)
        label = QLabel(name); label.setObjectName("chipLabel")
        close = QToolButton(); close.setObjectName("chipClose"); close.setText("×"); close.setToolTip(f"Remove {name}")
        close.clicked.connect(remove); row.addWidget(label); row.addWidget(close)


class RecommendationCard(QWidget):
    def __init__(self, rank, recommendation):
        super().__init__(); row = QHBoxLayout(self); row.setContentsMargins(12, 7, 12, 7)
        rank_label = QLabel(f"{rank:02d}"); rank_label.setObjectName("rank")
        name = QLabel(recommendation.hero.display_name); name.setObjectName("recommendationName")
        score = QLabel(f"{recommendation.score:+.2f}"); score.setObjectName("score")
        row.addWidget(rank_label); row.addWidget(name, 1); row.addWidget(score)


class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.state = DraftState(); self.animations = []; self.autocompleters = {}
        self.setWindowTitle("Dota Draft Assistant"); self.resize(720, 760); self.setMinimumSize(560, 620)
        self.setFont(QFont("Segoe UI", 10)); self.setStyleSheet(self.theme())
        self.background = AnimatedBackground(); self.background.setObjectName("root"); self.setCentralWidget(self.background)
        content = QWidget(); content.setObjectName("content")
        root_layout = QVBoxLayout(self.background); root_layout.setContentsMargins(0, 0, 0, 0); root_layout.addWidget(content)
        layout = QVBoxLayout(content); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(12)
        layout.addLayout(self.header())
        self.enemy, self.enemy_chips = self.team_section(layout, "Enemy heroes", "enemy")
        self.ally, self.ally_chips = self.team_section(layout, "Allied heroes", "ally")
        layout.addWidget(self.recommendations_panel()); layout.addWidget(self.explanation())
        layout.addLayout(self.actions())
        self.status = QLabel(); self.status.setObjectName("status"); self.status.setMinimumHeight(20); layout.addWidget(self.status)
        self.role.currentTextChanged.connect(self.refresh); self.mode.currentTextChanged.connect(self.refresh); self.count.currentTextChanged.connect(self.refresh)
        self.pin.toggled.connect(self.set_always_on_top); self.clear_button.clicked.connect(self.clear_draft)
        self.save_button.clicked.connect(lambda: self.show_status("Draft saving is not configured yet."))
        self.explain_button.clicked.connect(self.toggle_explanation); self.recs.itemSelectionChanged.connect(self.show_explain)
        self.refresh()

    @staticmethod
    def theme():
        return """
        QWidget#root { color:#e9edf5; } QWidget#content { background:transparent; }
        QLabel#appTitle { color:#f7f9fc; font-size:19px; font-weight:700; }
        QLabel#sectionTitle { color:#c7d2e5; font-size:11px; font-weight:700; letter-spacing:.5px; }
        QFrame#panel,QFrame#explanationPanel { background:#1b2230; border:1px solid #2b3548; border-radius:10px; }
        QLineEdit,QComboBox { background:#202938; border:1px solid #36435a; border-radius:7px; padding:7px 9px; min-height:18px; }
        QLineEdit:focus,QComboBox:focus { border:1px solid #6b96e6; } QComboBox::drop-down { border:0; width:22px; }
        QCheckBox { color:#c9d3e5; spacing:7px; } QCheckBox::indicator { width:15px; height:15px; border:1px solid #53627c; border-radius:4px; background:#202938; } QCheckBox::indicator:checked { background:#5e8de2; border-color:#78a5f5; }
        QFrame#heroChip { background:#27354c; border:1px solid #405777; border-radius:13px; } QLabel#chipLabel { color:#edf3ff; font-weight:600; }
        QToolButton#chipClose { color:#aebed8; border:0; border-radius:9px; font-size:16px; font-weight:700; min-width:18px; max-width:18px; min-height:18px; max-height:18px; padding:0; } QToolButton#chipClose:hover { background:#425b80; color:white; }
        QListWidget { background:#1b2230; border:1px solid #2b3548; border-radius:10px; padding:4px; outline:none; } QListWidget::item { border-radius:7px; margin:2px; } QListWidget::item:hover { background:#26354d; } QListWidget::item:selected { background:#304b73; }
        QFrame#autocomplete { background:#1c2637; border:1px solid #5775a0; border-radius:8px; } QListWidget#autocompleteList { background:transparent; border:0; border-radius:5px; padding:0; } QListWidget#autocompleteList::item { padding:7px 10px; margin:0; } QListWidget#autocompleteList::item:selected { background:#35557f; } QListWidget#autocompleteList::item:hover { background:#2b4262; }
        QLabel#rank { color:#8fa9d0; font-family:Consolas; font-weight:700; } QLabel#recommendationName { color:#f2f5fb; font-size:12px; font-weight:600; } QLabel#score { color:#9bc4ff; font-family:Consolas; font-weight:700; }
        QPushButton { background:#29364a; border:1px solid #3b4c66; border-radius:7px; color:#edf2fa; min-height:30px; padding:3px 12px; font-weight:600; } QPushButton:hover { background:#354862; border-color:#5775a0; } QPushButton:pressed { background:#223046; } QPushButton#primaryButton { background:#416cad; border-color:#5d8ed9; } QPushButton#primaryButton:hover { background:#4d7cc4; }
        QLabel#explanation { color:#cdd7e7; padding:4px; } QLabel#status { color:#91a4c3; padding-left:3px; } QLabel#status[error="true"] { color:#ffaaa5; }
        """

    def header(self):
        row = QHBoxLayout(); title = QLabel("Dota Draft Assistant"); title.setObjectName("appTitle"); row.addWidget(title, 1)
        self.role = QComboBox(); self.role.addItems(["carry", "mid", "offlane", "support", "hard_support"])
        self.mode = QComboBox(); self.mode.addItems(["manual", "stats", "hybrid"]); self.mode.setCurrentText("hybrid")
        self.count = QComboBox(); self.count.addItems(["3", "5", "10"]); self.count.setCurrentText("5")
        self.pin = QCheckBox("Always on top")
        for label, control in (("Role", self.role), ("Mode", self.mode), ("Top", self.count)): row.addWidget(QLabel(label)); row.addWidget(control)
        row.addWidget(self.pin); return row

    def team_section(self, parent, title, side):
        panel = QFrame(); panel.setObjectName("panel"); box = QVBoxLayout(panel); box.setContentsMargins(12, 10, 12, 12); box.setSpacing(8)
        heading = QLabel(title.upper()); heading.setObjectName("sectionTitle"); box.addWidget(heading)
        host = QWidget(); chips = FlowLayout(host); host.setLayout(chips); box.addWidget(host)
        input_box = QLineEdit(); input_box.setPlaceholderText("Type hero alias and press Enter"); input_box.returnPressed.connect(lambda: self.add_hero(input_box, side)); box.addWidget(input_box)
        parent.addWidget(panel)
        self.autocompleters[input_box] = HeroAutocomplete(
            input_box, self.state.heroes, self.state.aliases,
            lambda: self.state.enemies if side == "enemy" else self.state.allies,
            lambda hero_id: self.accept_suggestion(input_box, side, hero_id),
        )
        return input_box, chips

    def recommendations_panel(self):
        panel = QFrame(); panel.setObjectName("panel"); box = QVBoxLayout(panel); box.setContentsMargins(12, 10, 12, 12); box.setSpacing(7)
        title = QLabel("RECOMMENDATIONS"); title.setObjectName("sectionTitle"); box.addWidget(title)
        self.recs = QListWidget(); self.recs.setMinimumHeight(160); box.addWidget(self.recs); return panel

    def explanation(self):
        self.explanation_panel = QFrame(); self.explanation_panel.setObjectName("explanationPanel"); box = QVBoxLayout(self.explanation_panel); box.setContentsMargins(12, 8, 12, 10)
        heading = QLabel("SCORE BREAKDOWN"); heading.setObjectName("sectionTitle"); self.detail = QLabel(); self.detail.setObjectName("explanation"); self.detail.setWordWrap(True)
        box.addWidget(heading); box.addWidget(self.detail); self.explanation_panel.setVisible(False); return self.explanation_panel

    def actions(self):
        row = QHBoxLayout(); self.explain_button = QPushButton("Explain selected"); self.explain_button.setObjectName("primaryButton")
        self.clear_button = QPushButton("Clear draft"); self.save_button = QPushButton("Save draft")
        self.background_toggle = QCheckBox("Animated background"); self.background_toggle.setChecked(True)
        self.background_toggle.toggled.connect(self.background.set_animation_enabled)
        row.addWidget(self.explain_button); row.addStretch(1); row.addWidget(self.background_toggle); row.addWidget(self.clear_button); row.addWidget(self.save_button); return row

    def add_hero(self, input_box, side):
        try: hero_id = self.state.add(input_box.text(), side)
        except ValueError as error:
            self.show_status(self.friendly_error(str(error), input_box, side), error=True); input_box.setFocus(); return
        input_box.clear(); self.autocompleters[input_box].hide(); self.show_status(""); self.animate_chip(self.add_chip(hero_id, side), True); self.refresh(False); input_box.setFocus()

    def accept_suggestion(self, input_box, side, hero_id):
        input_box.setText(self.state.heroes[hero_id].display_name)
        self.add_hero(input_box, side)

    def friendly_error(self, error, input_box, side):
        if error == "Hero is already drafted":
            try:
                hero_id = normalize_hero(input_box.text(), set(self.state.heroes), self.state.aliases)
                other_side = "allied" if side == "enemy" else "enemy"
                return f"{self.state.heroes[hero_id].display_name} is already on the {other_side} side."
            except ValueError: pass
        return error

    def show_status(self, message, error=False):
        self.status.setText(message); self.status.setProperty("error", error); self.status.style().unpolish(self.status); self.status.style().polish(self.status)

    def add_chip(self, hero_id, side):
        layout = self.enemy_chips if side == "enemy" else self.ally_chips
        chip = HeroChip(self.state.heroes[hero_id].display_name, lambda: self.remove_hero(hero_id, side, chip)); layout.addWidget(chip); return chip

    def rebuild_chips(self):
        for layout, hero_ids, side in ((self.enemy_chips, self.state.enemies, "enemy"), (self.ally_chips, self.state.allies, "ally")):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for hero_id in hero_ids: self.add_chip(hero_id, side)

    def remove_hero(self, hero_id, side, chip):
        self.animate_chip(chip, False, lambda: self.finish_removal(hero_id, side, chip))

    def finish_removal(self, hero_id, side, chip):
        layout = self.enemy_chips if side == "enemy" else self.ally_chips
        for index in range(layout.count()):
            if layout.itemAt(index).widget() is chip: layout.takeAt(index); break
        chip.deleteLater(); self.state.remove(hero_id); self.show_status(""); self.refresh(False)

    def animate_chip(self, chip, entering, finished=None):
        effect = QGraphicsOpacityEffect(chip); chip.setGraphicsEffect(effect); width = chip.sizeHint().width()
        fade = QPropertyAnimation(effect, b"opacity", chip); grow = QPropertyAnimation(chip, b"maximumWidth", chip)
        for animation in (fade, grow): animation.setDuration(150); animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        if entering:
            chip.setMaximumWidth(0); fade.setStartValue(0.0); fade.setEndValue(1.0); grow.setStartValue(0); grow.setEndValue(width)
        else: fade.setStartValue(1.0); fade.setEndValue(0.0); grow.setStartValue(width); grow.setEndValue(0)
        def done():
            chip.setGraphicsEffect(None)
            if entering: chip.setMaximumWidth(16777215)
            if finished: finished()
        fade.finished.connect(done); self.animations.extend((fade, grow)); fade.start(); grow.start()

    def set_always_on_top(self, enabled): self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled); self.show()
    def refresh(self, rebuild=True):
        self.state.role, self.state.mode, self.state.top = self.role.currentText(), self.mode.currentText(), int(self.count.currentText())
        self.current = self.state.recommendations(); self.recs.clear()
        for rank, recommendation in enumerate(self.current, 1):
            item = QListWidgetItem(); item.setSizeHint(QSize(0, 40)); self.recs.addItem(item); self.recs.setItemWidget(item, RecommendationCard(rank, recommendation))
        if rebuild: self.rebuild_chips()
        self.recs.setCurrentRow(0)
    def toggle_explanation(self):
        if self.explanation_panel.isVisible(): self.explanation_panel.setVisible(False); self.explain_button.setText("Explain selected")
        else: self.show_explain()
    def show_explain(self):
        row = self.recs.currentRow()
        if 0 <= row < len(self.current):
            self.detail.setText(format_explanation(self.current[row], self.state.heroes)); self.explanation_panel.setVisible(True); self.explain_button.setText("Hide explanation")
    def clear_draft(self):
        self.state.clear(); self.explanation_panel.setVisible(False); self.explain_button.setText("Explain selected"); self.show_status(""); self.refresh(); self.enemy.setFocus()


def main():
    app = QApplication(sys.argv); window = Window(); window.show(); return app.exec()

if __name__ == "__main__": raise SystemExit(main())
