"""Small, optional Windows global activation hotkey adapter."""
import ctypes
import sys

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal
from PySide6.QtWidgets import QApplication


class WindowsHotkey(QObject, QAbstractNativeEventFilter):
    """Register Ctrl+Alt+D without hooks or simulated input."""
    activated = Signal()
    _id = 0x4441

    def __init__(self, parent=None):
        super().__init__(parent); self.registered = False
        if sys.platform == "win32":
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self._id, 0x0002 | 0x0001, ord("D")))
            if self.registered:
                QApplication.instance().installNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            # MSG.message is at offset 8 on 64-bit Windows; ctypes keeps this
            # deliberately tiny and avoids any keyboard hook.
            msg = ctypes.cast(int(message), ctypes.POINTER(ctypes.c_uint * 4)).contents
            if msg[1] == 0x0312 and msg[2] == self._id:
                self.activated.emit(); return True, 0
        return False, 0

    def close(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, self._id); self.registered = False
