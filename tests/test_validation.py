import pytest

from kinetic_captions.validation import ValidationError, validate_words_payload


def _valid_payload() -> dict:
    return {
        "version": "1.0",
        "lang": "cs",
        "text": "Ahoj test.",
        "words": [
            {"i": 0, "w": "Ahoj", "s": 0.1, "e": 0.4},
            {"i": 1, "w": "test.", "s": 0.42, "e": 0.7},
        ],
        "segments": [{"s": 0.1, "e": 0.7, "text": "Ahoj test."}],
        "speaker_segments": [{"speaker": "SPEAKER_00", "s": 0.1, "e": 0.7, "text": "Ahoj test."}],
        "meta": {},
    }


def test_validate_words_payload_accepts_valid_data() -> None:
    payload = _valid_payload()
    validate_words_payload(payload)


def test_validate_words_payload_rejects_decreasing_word_start() -> None:
    payload = _valid_payload()
    payload["words"][1]["s"] = 0.05
    with pytest.raises(ValidationError):
        validate_words_payload(payload)


def test_validate_words_payload_rejects_empty_words() -> None:
    payload = _valid_payload()
    payload["words"] = []
    with pytest.raises(ValidationError):
        validate_words_payload(payload)


def test_validate_words_payload_rejects_invalid_speaker_segment() -> None:
    payload = _valid_payload()
    payload["speaker_segments"][0]["speaker"] = ""
    with pytest.raises(ValidationError):
        validate_words_payload(payload)
