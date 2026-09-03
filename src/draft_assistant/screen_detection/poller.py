"""Non-blocking periodic capture and portrait recognition for the GUI."""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from .capture import ScreenCaptureError


class _JobSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class _DetectionJob(QRunnable):
    def __init__(self, detector, stabilizer, image):
        super().__init__()
        self.detector, self.stabilizer, self.image = detector, stabilizer, image
        self.signals = _JobSignals()

    def run(self):
        try:
            result = self.stabilizer.observe(self.detector.detect(self.image))
            if result is not None:
                self.signals.result.emit(result)
        except Exception as error:
            self.signals.error.emit(str(error))
        finally:
            self.signals.finished.emit()


class DetectionPoller(QObject):
    """Captures quickly on the UI thread and matches portraits in a worker thread."""
    result = Signal(object)
    status = Signal(str)

    def __init__(self, capture=None, detector=None, stabilizer=None, interval_ms=350, parent=None):
        super().__init__(parent)
        self.capture, self.detector, self.stabilizer = capture, detector, stabilizer
        self.busy = False
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.poll)

    @property
    def configured(self):
        return self.capture is not None and self.detector is not None and self.stabilizer is not None

    def start(self):
        if not self.configured:
            self.status.emit("Waiting for draft screen calibration")
            return False
        self.timer.start()
        self.poll()
        return True

    def stop(self):
        self.timer.stop()

    def poll(self):
        if self.busy or not self.configured:
            return
        try:
            image = self.capture.capture()
        except ScreenCaptureError as error:
            self.status.emit(str(error))
            return
        self.busy = True
        job = _DetectionJob(self.detector, self.stabilizer, image)
        job.signals.result.connect(self.result)
        job.signals.error.connect(self.status)
        job.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(job)

    def _finished(self):
        self.busy = False
