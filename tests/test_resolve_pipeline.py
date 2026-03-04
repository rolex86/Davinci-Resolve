from resolve.auto_kinetic_captions import build_title_spans


def test_build_title_spans_prefers_segments() -> None:
    payload = {
        "segments": [
            {"s": 0.2, "e": 0.6, "text": "Ahoj"},
            {"s": 0.7, "e": 1.0, "text": "svete"},
        ],
        "words": [],
    }
    spans = build_title_spans(payload, min_duration_sec=1.0)
    assert len(spans) == 2
    assert spans[0].start_sec == 0.2
    assert spans[0].end_sec == 1.2


def test_build_title_spans_fallback_to_words() -> None:
    payload = {
        "segments": [],
        "words": [
            {"s": 0.1, "e": 0.3},
            {"s": 0.4, "e": 1.2},
        ],
    }
    spans = build_title_spans(payload, min_duration_sec=1.0)
    assert len(spans) == 1
    assert spans[0].start_sec == 0.1
    assert spans[0].end_sec == 1.2
