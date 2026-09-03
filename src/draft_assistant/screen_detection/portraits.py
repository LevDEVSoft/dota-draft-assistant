"""Canonical hero portrait references and lightweight local template matching."""

from pathlib import Path

from PySide6.QtGui import QImage


class PortraitReferenceLibrary:
    def __init__(self, templates):
        self.templates = dict(templates)

    @classmethod
    def from_directory(cls, directory, heroes):
        directory = Path(directory)
        templates = {}
        for hero_id in heroes:
            image = QImage(str(directory / f"{hero_id}.png"))
            if not image.isNull():
                templates[hero_id] = image
        return cls(templates)


class TemplateMatcher:
    """Compares small, evenly sampled RGB grids; no external image services needed."""
    def __init__(self, references, minimum_confidence=0.82, sample_size=16):
        self.references = references
        self.minimum_confidence = minimum_confidence
        self.sample_size = sample_size

    def match(self, image):
        if image.isNull() or not self.references.templates:
            return None, 0.0
        best_id, best_confidence = None, 0.0
        for hero_id, template in self.references.templates.items():
            confidence = self._confidence(image, template)
            if confidence > best_confidence:
                best_id, best_confidence = hero_id, confidence
        return (best_id, best_confidence) if best_confidence >= self.minimum_confidence else (None, best_confidence)

    def _confidence(self, image, template):
        error = 0.0
        for y in range(self.sample_size):
            for x in range(self.sample_size):
                source = image.pixelColor(int((x + 0.5) * image.width() / self.sample_size), int((y + 0.5) * image.height() / self.sample_size))
                reference = template.pixelColor(int((x + 0.5) * template.width() / self.sample_size), int((y + 0.5) * template.height() / self.sample_size))
                error += (source.red() - reference.red()) ** 2 + (source.green() - reference.green()) ** 2 + (source.blue() - reference.blue()) ** 2
        return max(0.0, 1.0 - error / (self.sample_size ** 2 * 3 * 255 ** 2))
