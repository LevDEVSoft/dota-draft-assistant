"""Local, testable building blocks for Dota draft screen recognition."""

from .capture import CaptureRegion, DotaWindowCapture, QtScreenCapture, ScreenCaptureError
from .detector import DraftLayout, DraftPickDetector, NormalizedRect, SlotDetection, DetectionResult
from .portraits import PortraitReferenceLibrary, TemplateMatcher
from .stabilizer import TemporalStabilizer
from .poller import DetectionPoller

__all__ = ["CaptureRegion", "DotaWindowCapture", "QtScreenCapture", "ScreenCaptureError", "DraftLayout", "DraftPickDetector", "NormalizedRect", "SlotDetection", "DetectionResult", "PortraitReferenceLibrary", "TemplateMatcher", "TemporalStabilizer", "DetectionPoller"]
