"""Local screen-capture interfaces and Windows-friendly implementations."""

from dataclasses import dataclass
import sys
from typing import Protocol

from PySide6.QtGui import QGuiApplication, QImage


class ScreenCaptureError(RuntimeError):
    """Raised when no suitable local capture target is available."""


@dataclass(frozen=True)
class CaptureRegion:
    x: int
    y: int
    width: int
    height: int


class ScreenCapture(Protocol):
    def capture(self, region: CaptureRegion | None = None) -> QImage: ...


class QtScreenCapture:
    """Captures only a requested desktop region through Qt's native screen API."""
    def capture(self, region=None):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise ScreenCaptureError("No display is available for screen capture")
        if region is None:
            geometry = screen.availableGeometry()
            region = CaptureRegion(geometry.x(), geometry.y(), geometry.width(), geometry.height())
        image = screen.grabWindow(0, region.x, region.y, region.width, region.height).toImage()
        if image.isNull():
            raise ScreenCaptureError("Could not capture the configured Dota region")
        return image


class WindowsDotaWindowLocator:
    """Best-effort title lookup; callers can always supply a calibrated region instead."""
    def find_region(self):
        if sys.platform != "win32":
            return None
        import ctypes
        user32 = ctypes.windll.user32
        matches = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def visit(handle, _):
            if not user32.IsWindowVisible(handle):
                return True
            length = user32.GetWindowTextLengthW(handle)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(handle, title, length + 1)
            if "dota 2" in title.value.casefold():
                rect = ctypes.wintypes.RECT()
                user32.GetClientRect(handle, ctypes.byref(rect))
                point = ctypes.wintypes.POINT(rect.left, rect.top)
                user32.ClientToScreen(handle, ctypes.byref(point))
                matches.append(CaptureRegion(point.x, point.y, rect.right - rect.left, rect.bottom - rect.top))
                return False
            return True

        user32.EnumWindows(callback_type(visit), 0)
        return matches[0] if matches else None


class DotaWindowCapture:
    """Captures a configured region, or a discovered Dota client when available."""
    def __init__(self, capture=None, region=None, locator=None):
        self.capture_source = capture or QtScreenCapture()
        self.region = region
        self.locator = locator or WindowsDotaWindowLocator()

    def capture(self, region=None):
        target = region or self.region or self.locator.find_region()
        if target is None:
            raise ScreenCaptureError("Dota client was not found; configure a draft capture region")
        return self.capture_source.capture(target)
