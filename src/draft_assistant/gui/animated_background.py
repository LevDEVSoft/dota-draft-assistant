"""Quiet, native-drawn ambient background for the desktop UI."""

from dataclasses import dataclass
import math
import random

from PySide6.QtCore import QElapsedTimer, QTimer
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
    """A low-cost, calm field of drifting particles and a soft ribbon."""

    FPS = 30
    PARTICLE_COUNT = 42

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
        self.phase = (self.phase + seconds * 0.11) % (math.tau * 100)
        for particle in self.particles:
            particle.x = (particle.x + particle.speed_x * seconds) % 1.0
            particle.y = (particle.y + particle.speed_y * seconds) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#0a101b"))
        gradient.setColorAt(1, QColor("#111b2d"))
        painter.fillRect(self.rect(), gradient)
        self._draw_ribbon(painter)
        painter.setPen(QPen(QColor(154, 190, 255, 28), 1))
        painter.setBrush(QColor(159, 197, 255, 28))
        for particle in self.particles:
            color = QColor(165, 204, 255, particle.alpha)
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            painter.drawEllipse(particle.x * self.width(), particle.y * self.height(), particle.radius, particle.radius)

    def _draw_ribbon(self, painter):
        if not self.width() or not self.height():
            return
        path = QPainterPath()
        baseline = self.height() * 0.72
        path.moveTo(0, baseline)
        for x in range(0, self.width() + 1, 24):
            wave = math.sin(x / 155 + self.phase) * 18 + math.sin(x / 77 + self.phase * 0.6) * 7
            path.lineTo(x, baseline + wave)
        painter.setPen(QPen(QColor(94, 145, 231, 22), 2))
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawPath(path)
