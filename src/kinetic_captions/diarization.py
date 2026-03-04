from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SpeakerTurn:
    speaker: str
    start: float
    end: float


class DiarizationError(RuntimeError):
    """Raised when speaker diarization could not be executed."""


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def run_diarization(
    *,
    audio_path: Path,
    model: str,
    hf_token: str | None,
    logger: logging.Logger,
) -> list[SpeakerTurn]:
    try:
        from pyannote.audio import Pipeline
    except Exception as exc:
        raise DiarizationError(
            "Speaker diarization requested, but pyannote.audio is not installed. "
            "Install optional extras: pip install '.[diarization]'"
        ) from exc

    logger.info("Running diarization model=%s", model)
    try:
        pipeline = Pipeline.from_pretrained(model, use_auth_token=hf_token)
        diarization = pipeline(str(audio_path))
    except Exception as exc:
        raise DiarizationError(f"Diarization pipeline failed: {exc}") from exc

    turns: list[SpeakerTurn] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append(
            SpeakerTurn(
                speaker=str(speaker),
                start=round(float(turn.start), 3),
                end=round(float(turn.end), 3),
            )
        )
    logger.info("Diarization done: %s turns", len(turns))
    return turns


def attach_speakers_to_words(
    words: list[dict[str, Any]],
    turns: list[SpeakerTurn],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not turns:
        return words, []

    labeled_words: list[dict[str, Any]] = []
    for word in words:
        s = float(word["s"])
        e = float(word["e"])
        best_label = None
        best_overlap = 0.0

        for turn in turns:
            ol = _overlap(s, e, turn.start, turn.end)
            if ol > best_overlap:
                best_overlap = ol
                best_label = turn.speaker

        if best_label is None:
            # Fallback: nearest turn by start time
            nearest = min(turns, key=lambda t: abs(t.start - s))
            best_label = nearest.speaker

        enriched = dict(word)
        enriched["sp"] = best_label
        labeled_words.append(enriched)

    speaker_segments = _build_speaker_segments(labeled_words)
    return labeled_words, speaker_segments


def _build_speaker_segments(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []

    segments: list[dict[str, Any]] = []
    current_sp = str(words[0].get("sp", "unknown"))
    current_start = float(words[0]["s"])
    current_end = float(words[0]["e"])
    tokens = [str(words[0]["w"])]

    for word in words[1:]:
        speaker = str(word.get("sp", "unknown"))
        s = float(word["s"])
        e = float(word["e"])
        token = str(word["w"])

        if speaker == current_sp:
            current_end = max(current_end, e)
            tokens.append(token)
            continue

        segments.append(
            {
                "speaker": current_sp,
                "s": round(current_start, 3),
                "e": round(current_end, 3),
                "text": " ".join(tokens).strip(),
            }
        )
        current_sp = speaker
        current_start = s
        current_end = e
        tokens = [token]

    segments.append(
        {
            "speaker": current_sp,
            "s": round(current_start, 3),
            "e": round(current_end, 3),
            "text": " ".join(tokens).strip(),
        }
    )
    return segments
