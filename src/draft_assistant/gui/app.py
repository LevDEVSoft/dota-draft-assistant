"""PySide6 desktop application entry point."""
import html
import sys

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QSizePolicy,
    QSplitter, QTabWidget, QToolButton, QTextBrowser, QVBoxLayout, QWidget)

from draft_assistant.aliases import normalize_hero
from draft_assistant.screen_detection import DetectionPoller, TemporalStabilizer
from draft_assistant.item_knowledge import ITEMS
from .autocomplete import HeroAutocomplete
from .animated_background import AnimatedBackground
from .state import DraftState
from .native_hotkey import WindowsHotkey
from draft_assistant.auth.steam_openid import SteamOpenIDError, login as steam_login
from draft_assistant.profile.profile_state import default_store


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
        super().__init__(); self.setObjectName("recommendationCard"); row = QHBoxLayout(self); row.setContentsMargins(14, 8, 14, 8); row.setSpacing(10)
        rank_label = QLabel(f"{rank:02d}"); rank_label.setObjectName("rank")
        name = QLabel(recommendation.hero.display_name); name.setObjectName("recommendationName")
        score = QLabel(f"{recommendation.score:+.2f}"); score.setObjectName("score")
        row.addWidget(rank_label); row.addWidget(name, 1); row.addWidget(score)


def explanation_html(item, heroes):
    """Present the existing score breakdown as readable local rich text."""
    breakdown = item.breakdown
    matchup_sources = dict(breakdown.matchup_sources)
    synergy_sources = dict(breakdown.synergy_sources)
    reasons = []
    for enemy, score in breakdown.matchup_contributions:
        source = matchup_sources.get(enemy, "unavailable")
        detail = "data unavailable" + (" for selected role" if source == "unavailable-role" else "") if source.startswith("unavailable") else f"{score:+.1f} · {source}"
        reasons.append(f"<li><b>vs {html.escape(heroes.get(enemy).display_name if enemy in heroes else enemy.title())}</b><span>{html.escape(detail)}</span></li>")
    synergies = []
    for ally, score in breakdown.synergy_contributions:
        source = synergy_sources.get(ally, "unavailable")
        detail = "data unavailable" + (" for selected role" if source == "unavailable-role" else "") if source.startswith("unavailable") else f"{score:+.1f} · {source}"
        synergies.append(f"<li><b>with {html.escape(heroes.get(ally).display_name if ally in heroes else ally.title())}</b><span>{html.escape(detail)}</span></li>")
    return f"""
    <style>body{{font-family:'Segoe UI';color:#d7e1ef;margin:0}}h2{{color:#f4f7fc;margin:0;font-size:17px}}.score{{color:#aacdff;font-size:17px;font-weight:700;float:right}}.summary{{color:#9fb0c8;margin:5px 0 8px}}.pill{{background:#263a55;color:#cde0fa;border-radius:8px;padding:3px 7px;margin-right:5px}}h3{{color:#91add4;font-size:10px;letter-spacing:1px;margin:10px 0 3px}}ul{{margin:0;padding-left:15px}}li{{margin:2px 0}}li span{{color:#91a7c4;float:right}}</style>
    <h2>{html.escape(item.hero.display_name)} <span class='score'>{item.score:+.1f}</span></h2>
    <div class='summary'><span class='pill'>Base {breakdown.base:+.1f} · {html.escape(breakdown.base_source)}</span><span class='pill'>Role {breakdown.role:+.1f} · {html.escape(breakdown.role_source)}</span></div>
    <div class='summary'>{html.escape(breakdown.position_label)} sample: {breakdown.pos1_matches:,} · confidence: {breakdown.position_confidence:.3f} · total: <b>{breakdown.total:+.1f}</b></div>
    {"<h3>MATCHUPS</h3><ul>" + "".join(reasons) + "</ul>" if reasons else ""}
    {"<h3>SYNERGY</h3><ul>" + "".join(synergies) + "</ul>" if synergies else ""}
    """


class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.state = DraftState(); self.animations = []; self.autocompleters = {}; self.profile_store = default_store(); self.profile = self.profile_store.load()
        self.detection_poller = DetectionPoller(parent=self)
        self.detection_poller.result.connect(self.apply_detected_result)
        self.detection_poller.status.connect(lambda message: self.show_status(message))
        self.compact_overlay = False; self.full_geometry = None; self.overlay_geometry = None
        self.setWindowTitle("Dota Draft Assistant"); self.resize(1040, 700); self.setMinimumSize(620, 460)
        self.setFont(QFont("Segoe UI", 10)); self.setStyleSheet(self.theme())
        self.background = AnimatedBackground(); self.background.setObjectName("root"); self.setCentralWidget(self.background)
        self.content = QWidget(); self.content.setObjectName("content")
        root_layout = QVBoxLayout(self.background); root_layout.setContentsMargins(0, 0, 0, 0); root_layout.addWidget(self.content)
        layout = QVBoxLayout(self.content); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(10)
        layout.addLayout(self.header())
        self.enemy, self.enemy_chips = self.team_section(layout, "Enemy heroes", "enemy")
        self.ally, self.ally_chips = self.team_section(layout, "Allied heroes", "ally")
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal); self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.recommendations_panel())
        self.detail_tabs = QTabWidget(); self.detail_tabs.setObjectName("detailTabs")
        self.detail_tabs.addTab(self.explanation(), "Breakdown")
        self.detail_tabs.addTab(self.item_panel(), "Items")
        self.detail_tabs.addTab(self.role_plan_panel(), "Team / Game Plan")
        self.main_splitter.addWidget(self.detail_tabs); self.main_splitter.setSizes([590, 390]); layout.addWidget(self.main_splitter, 1)
        layout.addLayout(self.actions())
        self.status = QLabel(); self.status.setObjectName("status"); self.status.setMinimumHeight(20); layout.addWidget(self.status)
        self.role.currentTextChanged.connect(self.refresh); self.mode.currentTextChanged.connect(self.refresh); self.count.currentTextChanged.connect(self.refresh)
        self.pin.toggled.connect(self.set_always_on_top); self.clear_button.clicked.connect(self.clear_draft)
        self.save_button.clicked.connect(lambda: self.show_status("Draft saving is not configured yet."))
        self.explain_button.clicked.connect(self.show_explain); self.recs.itemSelectionChanged.connect(self.update_explanation)
        self.overlay_toggle.toggled.connect(self.set_overlay_mode)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self.enemy.setFocus); QShortcut(QKeySequence("Ctrl+2"), self, activated=self.ally.setFocus)
        self.hotkey = WindowsHotkey(self); self.hotkey.activated.connect(self.activate_overlay)
        self.refresh()

    @staticmethod
    def theme():
        return """
        QWidget#root { color:#e9edf5; } QWidget#content { background:transparent; }
        QLabel#appTitle { color:#f6f8fd; font-size:21px; font-weight:700; } QLabel#appSubtitle { color:#94a7c5; font-size:10px; }
        QFrame#controlStrip { background:rgba(16, 25, 40, 194); border:1px solid rgba(102, 130, 173, 100); border-radius:11px; }
        QLabel#controlLabel { color:#8398b8; font-size:9px; font-weight:700; letter-spacing:.5px; }
        QLabel#sectionTitle,QLabel#enemyTitle,QLabel#allyTitle { color:#c9d6ea; font-size:10px; font-weight:700; letter-spacing:1px; } QLabel#enemyTitle { color:#d7a9b2; } QLabel#allyTitle { color:#9fc5e5; }
        QFrame#panel,QFrame#explanationPanel { background:rgba(19, 28, 43, 224); border:1px solid rgba(84, 109, 145, 130); border-radius:12px; }
        QFrame#recommendationPanel { background:rgba(16, 26, 42, 234); border:1px solid rgba(102, 139, 193, 155); border-radius:14px; }
        QLineEdit,QComboBox { background:rgba(26, 38, 57, 235); border:1px solid #3a4e6e; border-radius:7px; padding:6px 9px; min-height:17px; }
        QLineEdit:focus,QComboBox:focus { border:1px solid #719be0; } QComboBox::drop-down { border:0; width:22px; }
        QCheckBox { color:#b8c7dd; spacing:6px; font-size:9px; } QCheckBox::indicator { width:14px; height:14px; border:1px solid #536782; border-radius:4px; background:#1d2a3d; } QCheckBox::indicator:checked { background:#6090dd; border-color:#85aff3; }
        QFrame#heroChip { background:rgba(40, 57, 82, 235); border:1px solid #49678e; border-radius:13px; } QLabel#chipLabel { color:#edf3ff; font-weight:600; }
        QToolButton#chipClose { color:#aebed8; border:0; border-radius:9px; font-size:16px; font-weight:700; min-width:18px; max-width:18px; min-height:18px; max-height:18px; padding:0; } QToolButton#chipClose:hover { background:#496989; color:white; }
        QListWidget { background:transparent; border:0; padding:2px; outline:none; } QListWidget::item { border-radius:9px; margin:2px; } QListWidget::item:hover { background:rgba(69, 96, 137, 135); } QListWidget::item:selected { background:rgba(63, 105, 163, 190); }
        QWidget#recommendationCard { background:transparent; } QLabel#rank { color:#8ba6cd; min-width:25px; font-family:Consolas; font-weight:700; } QLabel#recommendationName { color:#f4f7fc; font-size:13px; font-weight:600; } QLabel#score { color:#a9ccff; min-width:62px; font-family:Consolas; font-weight:700; qproperty-alignment:AlignRight; }
        QFrame#autocomplete { background:#1c293c; border:1px solid #6387bd; border-radius:8px; } QListWidget#autocompleteList { background:transparent; border:0; border-radius:5px; padding:0; } QListWidget#autocompleteList::item { padding:7px 10px; margin:0; } QListWidget#autocompleteList::item:selected { background:#35557f; } QListWidget#autocompleteList::item:hover { background:#2b4262; }
        QPushButton { background:rgba(42, 58, 80, 225); border:1px solid #3e5475; border-radius:7px; color:#dce6f4; min-height:28px; padding:2px 10px; font-size:9px; font-weight:600; } QPushButton:hover { background:#354c6a; border-color:#6689bb; } QPushButton:pressed { background:#24344c; } QPushButton#primaryButton { background:#416fae; border-color:#6b9be0; color:white; } QPushButton#primaryButton:hover { background:#5280c4; } QPushButton#quietButton { background:transparent; border-color:transparent; color:#9eafc8; } QPushButton#quietButton:hover { background:rgba(61, 83, 113, 155); border-color:rgba(92, 124, 165, 130); }
        QTextBrowser#explanation { background:transparent; border:0; color:#cdd7e7; padding:2px; } QLabel#status { color:#91a4c3; padding-left:3px; font-size:9px; } QLabel#status[error="true"] { color:#ffaaa5; }
        """

    def header(self):
        row = QHBoxLayout(); row.setSpacing(12)
        brand = QVBoxLayout(); brand.setSpacing(1); title = QLabel("Dota Draft Assistant"); title.setObjectName("appTitle"); subtitle = QLabel("Live draft companion · local recommendations"); subtitle.setObjectName("appSubtitle")
        brand.addWidget(title); brand.addWidget(subtitle); row.addLayout(brand, 1)
        strip = QFrame(); strip.setObjectName("controlStrip"); controls = QHBoxLayout(strip); controls.setContentsMargins(10, 6, 10, 6); controls.setSpacing(8)
        self.role = QComboBox(); self.role.addItems(["carry", "mid", "offlane", "support", "hard_support"])
        self.mode = QComboBox(); self.mode.addItems(["manual", "stats", "hybrid"]); self.mode.setCurrentText("hybrid")
        self.count = QComboBox(); self.count.addItems(["3", "5", "10"]); self.count.setCurrentText("5")
        self.pin = QCheckBox("Always on top"); self.overlay_toggle = QCheckBox("Overlay")
        for label, control in (("ROLE", self.role), ("MODE", self.mode), ("SHOW", self.count)):
            group = QVBoxLayout(); group.setSpacing(2); caption = QLabel(label); caption.setObjectName("controlLabel"); group.addWidget(caption); group.addWidget(control); controls.addLayout(group)
        controls.addWidget(self.pin); controls.addWidget(self.overlay_toggle)
        self.profile_button = QPushButton("Sign out Steam" if self.profile else "Sign in with Steam"); self.profile_button.setObjectName("quietButton"); self.profile_button.clicked.connect(self.sign_in_steam)
        controls.addWidget(self.profile_button); row.addWidget(strip); return row

    def team_section(self, parent, title, side):
        panel = QFrame(); panel.setObjectName("panel"); box = QVBoxLayout(panel); box.setContentsMargins(13, 9, 13, 10); box.setSpacing(6)
        heading = QLabel(title.upper()); heading.setObjectName(f"{side}Title"); box.addWidget(heading)
        host = QWidget(); chips = FlowLayout(host); host.setLayout(chips); box.addWidget(host)
        input_box = QLineEdit(); input_box.setPlaceholderText("Type hero alias and press Enter"); input_box.returnPressed.connect(lambda: self.add_hero(input_box, side)); box.addWidget(input_box)
        parent.addWidget(panel)
        self.autocompleters[input_box] = HeroAutocomplete(
            input_box, self.state.heroes, self.state.aliases,
            lambda: self.state.side_heroes(side),
            lambda hero_id: self.accept_suggestion(input_box, side, hero_id),
        )
        return input_box, chips

    def recommendations_panel(self):
        panel = QFrame(); panel.setObjectName("recommendationPanel"); box = QVBoxLayout(panel); box.setContentsMargins(14, 11, 14, 12); box.setSpacing(5)
        heading = QHBoxLayout(); title = QLabel("RECOMMENDATIONS"); title.setObjectName("sectionTitle"); note = QLabel("Best available picks"); note.setObjectName("appSubtitle"); heading.addWidget(title); heading.addStretch(1); heading.addWidget(note); box.addLayout(heading)
        self.recs = QListWidget(); self.recs.setMinimumHeight(180); self.recs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.recs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); box.addWidget(self.recs); return panel

    def role_plan_panel(self):
        panel = QFrame(); panel.setObjectName("panel"); box = QVBoxLayout(panel); box.setContentsMargins(13, 9, 13, 10); box.setSpacing(5)
        title = QLabel("ROLES & GAME PLAN"); title.setObjectName("sectionTitle"); box.addWidget(title)
        self.role_rows = QVBoxLayout(); self.role_rows.setSpacing(3); box.addLayout(self.role_rows)
        self.game_plan = QLabel(); self.game_plan.setObjectName("appSubtitle"); self.game_plan.setWordWrap(True); box.addWidget(self.game_plan)
        return panel

    def item_panel(self):
        panel=QFrame(); panel.setObjectName("panel"); box=QVBoxLayout(panel); box.setContentsMargins(13,9,13,10); box.setSpacing(5)
        title=QLabel("ITEM OPTIONS"); title.setObjectName("sectionTitle"); box.addWidget(title)
        row=QHBoxLayout(); self.player=QComboBox(); self.player.currentIndexChanged.connect(self.change_player); self.item_input=QLineEdit(); self.item_input.setPlaceholderText("Add owned item"); self.item_input.returnPressed.connect(self.add_owned_item); row.addWidget(self.player); row.addWidget(self.item_input,1); box.addLayout(row)
        self.item_list=QListWidget(); self.item_list.setMinimumHeight(130); self.item_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.item_list.itemSelectionChanged.connect(self.show_item_detail); box.addWidget(self.item_list,1)
        self.item_detail=QLabel(); self.item_detail.setObjectName("appSubtitle"); self.item_detail.setWordWrap(True); box.addWidget(self.item_detail)
        return panel

    def explanation(self):
        self.explanation_panel = QFrame(); self.explanation_panel.setObjectName("explanationPanel"); box = QVBoxLayout(self.explanation_panel); box.setContentsMargins(13, 9, 13, 10)
        heading = QLabel("SCORE BREAKDOWN"); heading.setObjectName("sectionTitle"); self.detail = QTextBrowser(); self.detail.setObjectName("explanation"); self.detail.setOpenExternalLinks(False); self.detail.setMinimumHeight(118); self.detail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        box.addWidget(heading); box.addWidget(self.detail,1); return self.explanation_panel

    def actions(self):
        row = QHBoxLayout(); self.explain_button = QPushButton("Show breakdown"); self.explain_button.setObjectName("primaryButton")
        self.clear_button = QPushButton("Clear"); self.clear_button.setObjectName("quietButton"); self.save_button = QPushButton("Save"); self.save_button.setObjectName("quietButton")
        self.background_toggle = QCheckBox("Animated background"); self.background_toggle.setChecked(True)
        self.background_toggle.toggled.connect(self.background.set_animation_enabled)
        self.screen_detection = QComboBox(); self.screen_detection.addItems(["Screen detection: OFF", "Screen detection: AUTO"])
        self.screen_detection.currentIndexChanged.connect(self.set_detection_mode)
        row.addWidget(self.explain_button); row.addStretch(1); row.addWidget(self.screen_detection); row.addWidget(self.background_toggle); row.addWidget(self.clear_button); row.addWidget(self.save_button); self.action_row=row; return row

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
        for layout, hero_ids, side in ((self.enemy_chips, self.state.side_heroes("enemy"), "enemy"), (self.ally_chips, self.state.side_heroes("ally"), "ally")):
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

    def set_always_on_top(self, enabled):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled); self.show(); self.raise_()

    def set_overlay_mode(self, enabled):
        if enabled == self.compact_overlay: return
        self.compact_overlay = enabled
        if enabled:
            self.full_geometry = self.saveGeometry(); self.detail_tabs.hide(); self.screen_detection.hide(); self.background_toggle.hide(); self.save_button.hide(); self.explain_button.hide()
            self.setMinimumSize(420, 340); self.resize(480, 570)
            self.show_status("Overlay works best with Dota in Borderless Window mode.")
        else:
            self.overlay_geometry = self.saveGeometry(); self.detail_tabs.show(); self.screen_detection.show(); self.background_toggle.show(); self.save_button.show(); self.explain_button.show()
            self.setMinimumSize(620, 460)
            if self.full_geometry: self.restoreGeometry(self.full_geometry)
        self.enemy.setFocus()

    def activate_overlay(self):
        self.showNormal(); self.show(); self.raise_(); self.activateWindow()
        (self.enemy if not self.enemy.text() else self.ally).setFocus()

    def sign_in_steam(self):
        if self.profile:
            self.profile_store.sign_out(); self.profile = None; self.profile_button.setText("Sign in with Steam"); self.show_status("Steam profile unlinked."); return
        try:
            self.show_status("Complete Steam sign-in in your default browser.")
            self.profile = self.profile_store.save(steam_login().steam_id64)
            self.profile_button.setText("Sign out Steam")
            self.show_status("Steam account linked. Use steam-login for access diagnostics.")
        except SteamOpenIDError as error:
            self.show_status(str(error), error=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.compact_overlay:
            if any(completer.popup.isVisible() for completer in self.autocompleters.values()):
                for completer in self.autocompleters.values(): completer.hide()
            else:
                self.hide()
            event.accept(); return
        super().keyPressEvent(event)
    def configure_screen_detection(self, capture, detector, stabilizer=None):
        self.detection_poller.capture = capture; self.detection_poller.detector = detector
        self.detection_poller.stabilizer = stabilizer or TemporalStabilizer()
    def set_detection_mode(self, index):
        if index:
            self.detection_poller.start()
        else:
            self.detection_poller.stop()
    def apply_detected_result(self, result):
        if self.state.apply_detected_picks(result.allied_picks, result.enemy_picks): self.refresh()
        count = len(result.allied_picks) + len(result.enemy_picks)
        self.show_status(f"Dota detected · {count} picks" if count else "Waiting for draft screen")
    def refresh(self, rebuild=True):
        selected_id = self.current[self.recs.currentRow()].hero.id if hasattr(self, "current") and 0 <= self.recs.currentRow() < len(self.current) else None
        self.state.role, self.state.mode, self.state.top = self.role.currentText(), self.mode.currentText(), int(self.count.currentText())
        self.current = self.state.recommendations(); self.recs.clear()
        for rank, recommendation in enumerate(self.current, 1):
            item = QListWidgetItem(); item.setSizeHint(QSize(0, 40)); self.recs.addItem(item); self.recs.setItemWidget(item, RecommendationCard(rank, recommendation))
        if rebuild: self.rebuild_chips()
        self.refresh_role_plan()
        selected_row = next((index for index, item in enumerate(self.current) if item.hero.id == selected_id), 0)
        self.recs.setCurrentRow(selected_row)
    def refresh_role_plan(self):
        while self.role_rows.count():
            item=self.role_rows.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        analysis=self.state.analysis
        if not analysis:
            self.game_plan.setText("Add allied heroes to inspect inferred roles and the local game plan.")
            self.player.blockSignals(True); self.player.clear(); self.player.blockSignals(False); self.refresh_items(); return
        profiles={p.hero_id:p for p in analysis.allied_profiles}
        for assignment in analysis.allies:
            row=QFrame(); layout=QHBoxLayout(row); layout.setContentsMargins(0,0,0,0); layout.setSpacing(7)
            hero=QLabel(self.state.heroes[assignment.hero_id].display_name); hero.setMinimumWidth(118)
            position=QComboBox(); position.addItems([f"P{x}" for x in range(1,6)]); position.setCurrentText(f"P{assignment.position}"); position.setMaximumWidth(58)
            position.currentIndexChanged.connect(lambda index, hero_id=assignment.hero_id: self.change_position(hero_id,index+1))
            profile=profiles[assignment.hero_id]; confidence="Manual" if assignment.manual else ("High" if assignment.confidence>=.8 else "Medium")
            detail=QLabel(f"{confidence} · {', '.join(profile.archetypes)}"); detail.setObjectName("appSubtitle")
            layout.addWidget(hero); layout.addWidget(position); layout.addWidget(detail,1); self.role_rows.addWidget(row)
        timing=lambda curve: ("early" if max(range(5),key=lambda i:curve[i])<2 else "mid game" if max(range(5),key=lambda i:curve[i])<3 else "late game")
        threats=" · ".join(x.replace("_"," ") for x in analysis.threats[:3]) or "none identified"
        needs=" · ".join(analysis.needs[:3]) or "balanced"
        self.game_plan.setText(f"Allied timing: likely {timing(analysis.allied_curve)} · Enemy timing: likely {timing(analysis.enemy_curve)}\nThreats: {threats} · Team needs: {needs}")
        current=self.state.selected_player; self.player.blockSignals(True); self.player.clear()
        for hero in self.state.side_heroes("ally"): self.player.addItem(self.state.heroes[hero].display_name,hero)
        if current:
            self.player.setCurrentIndex(self.player.findData(current))
        self.player.blockSignals(False); self.refresh_items()
    def change_position(self, hero_id, position):
        self.state.set_position(hero_id, position); self.refresh()
    def change_player(self,index):
        if index>=0: self.state.select_player(self.player.itemData(index)); self.refresh_items()
    def add_owned_item(self):
        key=self.item_input.text().casefold().replace(" ","_").replace("'","")
        matches=[item_id for item_id,spec in ITEMS.items() if key in item_id or key in spec.display_name.casefold()]
        if matches:
            self.state.add_item(matches[0]); self.item_input.clear(); self.refresh_items()
        else: self.show_status("Unknown item",True)
    def refresh_items(self):
        self.item_list.clear(); scores=self.state.item_scores()
        if not self.state.selected_player:
            self.item_detail.setText("Select an allied hero to view item options."); return
        for score in scores[:6]:
            spec=ITEMS[score.item_id]; item=QListWidgetItem(f"{spec.display_name}  {score.total:+.1f}"); item.setData(Qt.ItemDataRole.UserRole,score); self.item_list.addItem(item)
        owned=", ".join(ITEMS[x].display_name for x in self.state.inventories.get(self.state.selected_player,[])) or "No owned items"
        self.item_detail.setText(f"Owned: {owned}")
    def show_item_detail(self):
        item=self.item_list.currentItem()
        if item:
            score=item.data(Qt.ItemDataRole.UserRole); self.item_detail.setText(" · ".join((f"Matchup {score.matchup:+.1f}",f"Need {score.team_need:+.1f}",f"Role fit {score.role_fit:+.1f}",f"Redundancy {-score.redundancy:+.1f}",f"Poor fit {-score.poor_fit:+.1f}")))
    def toggle_explanation(self):
        self.detail_tabs.setVisible(not self.detail_tabs.isVisible())
        if self.detail_tabs.isVisible(): self.show_explain()
    def show_explain(self):
        self.detail_tabs.show(); self.detail_tabs.setCurrentWidget(self.explanation_panel); self.update_explanation()
    def update_explanation(self):
        row = self.recs.currentRow()
        if 0 <= row < len(self.current):
            self.detail.setHtml(explanation_html(self.current[row], self.state.heroes))
    def clear_draft(self):
        self.state.clear(); self.show_status(""); self.refresh(); self.enemy.setFocus()

    def closeEvent(self, event):
        self.hotkey.close(); super().closeEvent(event)


def main():
    app = QApplication(sys.argv); window = Window(); window.show(); return app.exec()

if __name__ == "__main__": raise SystemExit(main())
