from kinetic_captions.diarization import SpeakerTurn, attach_speakers_to_words


def test_attach_speakers_to_words() -> None:
    words = [
        {"i": 0, "w": "Ahoj", "s": 0.1, "e": 0.4},
        {"i": 1, "w": "svete", "s": 0.41, "e": 0.8},
        {"i": 2, "w": "test", "s": 1.0, "e": 1.3},
    ]
    turns = [
        SpeakerTurn("SPEAKER_00", 0.0, 0.85),
        SpeakerTurn("SPEAKER_01", 0.9, 1.4),
    ]
    labeled_words, speaker_segments = attach_speakers_to_words(words, turns)
    assert [w["sp"] for w in labeled_words] == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]
    assert speaker_segments[0]["speaker"] == "SPEAKER_00"
    assert speaker_segments[1]["speaker"] == "SPEAKER_01"
