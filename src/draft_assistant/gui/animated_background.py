"""Quiet, native-drawn ambient background for the desktop UI."""

from dataclasses import dataclass
import math
import random

from PySide6.QtCore import QElapsedTimer, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


@dataclass
class Particle:
    x: float
    y: float
    radius: float
    alpha: int
    speed_x: float
    speed_y: float


class AnimatedBackground(QWidget):
    """A low-cost field of drifting particles and original flowing ribbons."""

    FPS = 36
    PARTICLE_COUNT = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        randomizer = random.Random(2407)
        self.particles = [
            Particle(
                randomizer.random(), randomizer.random(), randomizer.uniform(1.0, 3.2),
                randomizer.randint(12, 42), randomizer.uniform(-0.007, 0.007),
                randomizer.uniform(-0.012, -0.003),
            )
            for _ in range(self.PARTICLE_COUNT)
        ]
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(round(1000 / self.FPS))
        self.timer.timeout.connect(self.advance)
        self.elapsed = QElapsedTimer()
        self.elapsed.start()
        self.timer.start()

    @property
    def animation_enabled(self):
        return self.timer.isActive()

    def set_animation_enabled(self, enabled):
        if enabled:
            self.elapsed.restart()
            self.timer.start()
        else:
            self.timer.stop()

    def advance(self):
        milliseconds = max(1, self.elapsed.restart())
        seconds = min(milliseconds / 1000, 0.1)
        self.phase = (self.phase + seconds * 0.16) % (math.tau * 100)
        for particle in self.particles:
            particle.x = (particle.x + particle.speed_x * seconds) % 1.0
            particle.y = (particle.y + particle.speed_y * seconds) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#070c16"))
        gradient.setColorAt(.52, QColor("#0c1525"))
        gradient.setColorAt(1, QColor("#111d31"))
        painter.fillRect(self.rect(), gradient)
        self._draw_ribbons(painter)
        for particle in self.particles:
            color = QColor(180, 211, 255, particle.alpha)
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            painter.drawEllipse(particle.x * self.width(), particle.y * self.height(), particle.radius * 2, particle.radius * 2)

    def _draw_ribbons(self, painter):
        if not self.width() or not self.height():
            return
        self._draw_ribbon(painter, .30, 56, 96, .55, QColor(76, 126, 206, 26), QColor(116, 167, 239, 54))
        self._draw_ribbon(painter, .61, 72, 144, .34, QColor(63, 103, 178, 24), QColor(133, 183, 244, 42))
        self._draw_ribbon(painter, .84, 40, 72, .82, QColor(77, 117, 188, 20), QColor(153, 196, 249, 34))

    def _draw_ribbon(self, painter, vertical, amplitude, wavelength, speed, fill, highlight):
        baseline = self.height() * vertical
        path = QPainterPath()
        path.moveTo(-30, baseline)
        for x in range(-30, self.width() + 40, 20):
            wave = math.sin(x / wavelength + self.phase * speed) * amplitude
            wave += math.sin(x / (wavelength * .46) + self.phase * speed * 1.4) * amplitude * .22
            path.lineTo(x, baseline + wave)
        painter.setPen(QPen(highlight, 1.4))
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawPath(path)

        ribbon = QPainterPath(path)
        for x in range(self.width() + 30, -40, -20):
            wave = math.sin(x / wavelength + self.phase * speed + .42) * amplitude
            wave += math.sin(x / (wavelength * .46) + self.phase * speed * 1.4 + .42) * amplitude * .22
            ribbon.lineTo(x, baseline + wave + amplitude * .42)
        ribbon.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPath(ribbon)
