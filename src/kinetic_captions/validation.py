from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    """Raised when generated words.json does not match required constraints."""


def validate_words_payload(payload: dict[str, Any]) -> None:
    if payload.get("version") != "1.0":
        raise ValidationError("version must be '1.0'.")

    words = payload.get("words")
    if not isinstance(words, list) or not words:
        raise ValidationError("words must be a non-empty list.")

    prev_start = -1.0
    for idx, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValidationError(f"word[{idx}] must be an object.")

        i = word.get("i")
        w = word.get("w")
        s = word.get("s")
        e = word.get("e")

        if i != idx:
            raise ValidationError(f"word[{idx}] has invalid i={i}; expected {idx}.")
        if not isinstance(w, str) or not w.strip():
            raise ValidationError(f"word[{idx}] has empty token.")
        if "sp" in word and not isinstance(word.get("sp"), str):
            raise ValidationError(f"word[{idx}] has invalid speaker label.")

        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            raise ValidationError(f"word[{idx}] has non-numeric s/e.")
        if s < 0 or e < 0:
            raise ValidationError(f"word[{idx}] has negative s/e.")
        if s >= e:
            raise ValidationError(f"word[{idx}] must satisfy s < e.")
        if s < prev_start:
            raise ValidationError(
                f"word[{idx}] start time is decreasing ({s} < {prev_start})."
            )
        prev_start = float(s)

    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        raise ValidationError("segments must be a list.")

    for idx, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValidationError(f"segment[{idx}] must be an object.")
        s = segment.get("s")
        e = segment.get("e")
        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            raise ValidationError(f"segment[{idx}] has non-numeric s/e.")
        if s < 0 or e < 0:
            raise ValidationError(f"segment[{idx}] has negative s/e.")
        if s >= e:
            raise ValidationError(f"segment[{idx}] must satisfy s < e.")

    speaker_segments = payload.get("speaker_segments", [])
    if not isinstance(speaker_segments, list):
        raise ValidationError("speaker_segments must be a list.")
    for idx, segment in enumerate(speaker_segments):
        if not isinstance(segment, dict):
            raise ValidationError(f"speaker_segment[{idx}] must be an object.")
        speaker = segment.get("speaker")
        s = segment.get("s")
        e = segment.get("e")
        if not isinstance(speaker, str) or not speaker:
            raise ValidationError(f"speaker_segment[{idx}] has invalid speaker.")
        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            raise ValidationError(f"speaker_segment[{idx}] has non-numeric s/e.")
        if s < 0 or e < 0 or s >= e:
            raise ValidationError(f"speaker_segment[{idx}] must satisfy 0 <= s < e.")
