"""Temporal debounce for animated draft-screen transitions."""


class TemporalStabilizer:
    def __init__(self, required_frames=2, minimum_confidence=0.82):
        self.required_frames = required_frames
        self.minimum_confidence = minimum_confidence
        self.candidate = None
        self.frames = 0
        self.emitted = None

    def observe(self, result):
        fingerprint = self._fingerprint(result)
        if fingerprint != self.candidate:
            self.candidate, self.frames = fingerprint, 1
            return None
        self.frames += 1
        if self.frames < self.required_frames or fingerprint == self.emitted:
            return None
        self.emitted = fingerprint
        return result

    def _fingerprint(self, result):
        def side(slots):
            return tuple((slot.slot, slot.hero_id if slot.confidence >= self.minimum_confidence else None) for slot in slots)
        return side(result.allied_slots), side(result.enemy_slots)
