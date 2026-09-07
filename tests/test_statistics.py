from draft_assistant import statistics


def test_item_evidence_keeps_delta_and_bounded_confidence(monkeypatch):
    monkeypatch.setattr(statistics, "_raw", lambda: {"hero_stats": [{"hero": "lifestealer", "role": "carry", "bracket": "HERALD_GUARDIAN", "matches": 10000, "wins": 5130}], "item_stats": [{"hero": "lifestealer", "role": "carry", "bracket": "HERALD_GUARDIAN", "item": "black_king_bar", "purchase_count": 20, "wins": 14, "purchase_rate": .184}]})
    evidence = statistics.item_statistics("lifestealer", "carry", "black_king_bar")
    assert evidence.win_rate == .7 and round(evidence.delta, 3) == .187
    assert evidence.confidence < .1 and statistics.confidence_label(evidence.purchases) == "low"


def test_missing_evidence_is_unavailable():
    assert statistics.item_statistics("missing", "carry", "item") is None
