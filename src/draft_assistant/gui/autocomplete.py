"""Reusable, alias-aware hero suggestions for GUI text inputs."""

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QVBoxLayout

from draft_assistant.aliases import normalize_key


def ranked_suggestions(query, heroes, aliases, selected=(), limit=5):
    """Return canonical ids ranked by exact, prefix, then substring matches."""
    needle = normalize_key(query)
    if not needle:
        return []
    selected = set(selected)
    name_keys = {hero_id: {normalize_key(hero_id), normalize_key(hero.display_name)} for hero_id, hero in heroes.items()}
    alias_keys = {hero_id: set() for hero_id in heroes}
    for alias, hero_id in aliases.items():
        alias_keys.setdefault(hero_id, set()).add(normalize_key(alias))
    ranked = []
    for hero_id, names in name_keys.items():
        if hero_id in selected:
            continue
        aliases_for_hero = alias_keys.get(hero_id, set())
        if needle in names or needle in aliases_for_hero:
            rank = 0
        elif any(key.startswith(needle) for key in names):
            rank = 1
        elif any(key.startswith(needle) for key in aliases_for_hero):
            rank = 2
        elif any(needle in key for key in names):
            rank = 3
        elif any(needle in key for key in aliases_for_hero):
            rank = 4
        else:
            continue
        ranked.append((rank, heroes[hero_id].display_name.casefold(), hero_id))
    return [hero_id for _, _, hero_id in sorted(ranked)[:limit]]


class HeroAutocomplete(QObject):
    """Popup list with keyboard and mouse selection for a single hero input."""
    def __init__(self, input_box, heroes, aliases, selected, accept):
        super().__init__(input_box)
        self.input_box, self.heroes, self.aliases = input_box, heroes, aliases
        self.selected, self.accept_callback = selected, accept
        self.matches = []
        self.popup = QFrame(input_box.window())
        self.popup.setObjectName("autocomplete")
        self.popup.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setObjectName("autocompleteList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self.accept_current)
        layout.addWidget(self.list)
        self.popup.hide()
        self.input_box.textChanged.connect(self.update_matches)
        self.input_box.installEventFilter(self)

    def update_matches(self, text):
        self.matches = ranked_suggestions(text, self.heroes, self.aliases, self.selected())
        self.list.clear()
        for hero_id in self.matches:
            item = QListWidgetItem(self.heroes[hero_id].display_name)
            item.setData(Qt.ItemDataRole.UserRole, hero_id)
            self.list.addItem(item)
        if not self.matches:
            self.hide()
            return
        self.list.setCurrentRow(-1)
        self.reposition()
        self.popup.show()
        self.popup.raise_()

    def reposition(self):
        position = self.input_box.mapTo(self.input_box.window(), QPoint(0, self.input_box.height() + 3))
        self.popup.move(position)
        self.popup.resize(self.input_box.width(), min(5, len(self.matches)) * 34 + 8)

    def hide(self):
        self.popup.hide()

    def accept_current(self, item=None):
        if item is None:
            row = self.list.currentRow()
            item = self.list.item(row if row >= 0 else 0)
        if item is None:
            return
        self.hide()
        self.accept_callback(item.data(Qt.ItemDataRole.UserRole))

    def eventFilter(self, watched, event):
        if watched is self.input_box and event.type() == QEvent.Type.KeyPress and self.popup.isVisible():
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide()
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                if self.matches:
                    direction = -1 if key == Qt.Key.Key_Up else 1
                    row = self.list.currentRow()
                    self.list.setCurrentRow((row + direction) % len(self.matches))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept_current()
                return True
        if watched is self.input_box and event.type() in (QEvent.Type.Move, QEvent.Type.Resize) and self.popup.isVisible():
            self.reposition()
        return super().eventFilter(watched, event)
