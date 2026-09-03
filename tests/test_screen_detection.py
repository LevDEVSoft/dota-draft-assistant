from PySide6.QtGui import QColor, QImage

from draft_assistant.gui.state import DraftState
from draft_assistant.screen_detection.capture import CaptureRegion, DotaWindowCapture
from draft_assistant.screen_detection.detector import DetectionResult, DraftLayout, DraftPickDetector, NormalizedRect, SlotDetection
from draft_assistant.screen_detection.poller import DetectionPoller
from draft_assistant.screen_detection.portraits import PortraitReferenceLibrary, TemplateMatcher
from draft_assistant.screen_detection.stabilizer import TemporalStabilizer


def solid(color, width=40, height=40):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    return image


def prepared_detector():
    references = PortraitReferenceLibrary({"zeus": solid("#3f7fd7"), "dark_seer": solid("#8c4ac2")})
    layout = DraftLayout((NormalizedRect(0, 0, .5, 1),), (NormalizedRect(.5, 0, .5, 1),))
    return DraftPickDetector(layout, TemplateMatcher(references, minimum_confidence=.95))


def prepared_frame(left="#3f7fd7", right="#8c4ac2"):
    image = solid("#111111", 80, 40)
    image.fill(QColor("#111111"))
    for x, color in ((0, left), (40, right)):
        for column in range(x, x + 40):
            for row in range(40):
                image.setPixelColor(column, row, QColor(color))
    return image


def test_prepared_portrait_fixture_maps_to_canonical_ids_and_empty_slots():
    result = prepared_detector().detect(prepared_frame(right="#1e1e1e"))
    assert result.allied_picks == ("zeus",)
    assert result.enemy_picks == ()
    assert result.enemy_slots[0].hero_id is None


def test_poor_portrait_match_is_rejected_with_confidence():
    result = prepared_detector().detect(prepared_frame(left="#f4d03f", right="#1e1e1e"))
    assert result.allied_slots[0].hero_id is None
    assert result.allied_slots[0].confidence < .95


def test_capture_abstraction_accepts_a_configured_relative_dota_region():
    class FakeCapture:
        def __init__(self): self.region = None
        def capture(self, region): self.region = region; return solid("black")
    fake = FakeCapture()
    region = CaptureRegion(100, 200, 800, 600)
    assert not DotaWindowCapture(fake, region=region).capture().isNull()
    assert fake.region == region


def result(hero="zeus", confidence=.99):
    return DetectionResult((SlotDetection(0, hero, confidence),), (SlotDetection(0, None, 0.0),))


def test_temporal_stabilizer_requires_repeated_frames_and_emits_one_change():
    stabilizer = TemporalStabilizer(required_frames=2)
    frame = result()
    assert stabilizer.observe(frame) is None
    assert stabilizer.observe(frame) == frame
    assert stabilizer.observe(frame) is None
    assert stabilizer.observe(result("dark_seer")) is None
    assert stabilizer.observe(result("dark_seer")).allied_picks == ("dark_seer",)


def test_manual_state_remains_functional_without_auto_detection():
    state = DraftState()
    assert state.add("sf", "enemy") == "shadow_fiend"
    poller = DetectionPoller()
    assert not poller.start()
    assert state.draft().enemies == ("shadow_fiend",)
    assert state.apply_detected_picks(["zeus"], [])
    state.remove("zeus")
    assert "zeus" not in state.draft().allies
