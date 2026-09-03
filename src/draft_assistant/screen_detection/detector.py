"""Phase 1 draft portrait-slot recognition using relative calibrated regions."""

from dataclasses import dataclass

from PySide6.QtCore import QRect


@dataclass(frozen=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float

    def to_rect(self, image):
        return QRect(round(self.x * image.width()), round(self.y * image.height()), round(self.width * image.width()), round(self.height * image.height()))


@dataclass(frozen=True)
class DraftLayout:
    allied_slots: tuple[NormalizedRect, ...]
    enemy_slots: tuple[NormalizedRect, ...]
    # Phase 2 can add hero-grid cells and banned/grayscale classification here.


@dataclass(frozen=True)
class SlotDetection:
    slot: int
    hero_id: str | None
    confidence: float


@dataclass(frozen=True)
class DetectionResult:
    allied_slots: tuple[SlotDetection, ...]
    enemy_slots: tuple[SlotDetection, ...]
    unavailable_heroes: tuple[str, ...] = ()

    @property
    def allied_picks(self): return tuple(item.hero_id for item in self.allied_slots if item.hero_id)
    @property
    def enemy_picks(self): return tuple(item.hero_id for item in self.enemy_slots if item.hero_id)


class DraftPickDetector:
    def __init__(self, layout, matcher):
        self.layout = layout
        self.matcher = matcher

    def detect(self, draft_image):
        return DetectionResult(
            self._detect_slots(draft_image, self.layout.allied_slots),
            self._detect_slots(draft_image, self.layout.enemy_slots),
        )

    def _detect_slots(self, image, slots):
        detected = []
        for index, slot in enumerate(slots):
            portrait = image.copy(slot.to_rect(image))
            hero_id, confidence = self.matcher.match(portrait)
            detected.append(SlotDetection(index, hero_id, confidence))
        return tuple(detected)
