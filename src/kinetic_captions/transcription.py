from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import Any
import wave

from .diarization import DiarizationError, attach_speakers_to_words, run_diarization
from .model_manager import MODEL_NAME_MAP
from .text_norm import RawWord, coalesce_words, compose_transcript, normalize_text_blob
from .validation import ValidationError, validate_words_payload

_TOKEN_RE = re.compile(r"\S+")
_SUPPORTED_LANGS = {"auto", "cs", "en"}
_SUPPORTED_MODELS = {"small", "medium", "large"}


class UserFacingError(RuntimeError):
    """An error safe to print directly to CLI users."""


@dataclass(frozen=True)
class TranscriptionOptions:
    lang: str = "auto"
    model: str = "small"
    device: str = "cpu"
    model_path: str = ""
    models_dir: str = ""
    offline_only: bool = False
    vad_enabled: bool = True
    vad_min_silence_ms: int = 500
    vad_speech_pad_ms: int = 80
    max_line_chars: int = 32
    max_words_per_line: int = 7
    diarization: bool = False
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: str = ""


def read_audio_meta(path: Path) -> dict[str, int]:
    try:
        with wave.open(str(path), "rb") as wav_file:
            return {"sr": wav_file.getframerate(), "channels": wav_file.getnchannels()}
    except wave.Error as exc:
        raise UserFacingError(
            f"Input must be a readable WAV file: {path}. Details: {exc}"
        ) from exc


def _fallback_words_for_segment(text: str, start: float, end: float) -> list[RawWord]:
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return []
    segment_duration = max(end - start, 0.001)
    step = segment_duration / len(tokens)
    out: list[RawWord] = []
    for idx, token in enumerate(tokens):
        s = start + (idx * step)
        e = start + ((idx + 1) * step)
        out.append(RawWord(token=token, start=s, end=max(s + 0.001, e)))
    return out


def _collect_raw_words(segment: Any, seg_text: str, seg_start: float, seg_end: float) -> list[RawWord]:
    raw_words: list[RawWord] = []
    words = list(getattr(segment, "words", []) or [])
    if not words:
        return _fallback_words_for_segment(seg_text, seg_start, seg_end)

    for item in words:
        token = str(getattr(item, "word", ""))
        start = getattr(item, "start", seg_start)
        end = getattr(item, "end", seg_end)
        start_value = float(seg_start if start is None else start)
        end_value = float(seg_end if end is None else end)
        raw_words.append(RawWord(token=token, start=start_value, end=end_value))
    return raw_words


def _load_model(
    *,
    model_name: str,
    model_path: str,
    models_dir: str,
    device: str,
    offline_only: bool,
    logger: logging.Logger,
) -> tuple[Any, str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise UserFacingError(
            "Missing dependency 'faster-whisper'. Install project dependencies first."
        ) from exc

    resolved = MODEL_NAME_MAP.get(model_name, model_name)
    load_target = model_path.strip() or resolved
    kwargs: dict[str, Any] = {}
    if models_dir.strip():
        kwargs["download_root"] = models_dir.strip()
    if offline_only:
        kwargs["local_files_only"] = True

    if device == "cuda":
        try:
            model = WhisperModel(
                load_target,
                device="cuda",
                compute_type="float16",
                **kwargs,
            )
            return model, "cuda", str(load_target)
        except Exception as exc:  # pragma: no cover - depends on host CUDA setup
            logger.warning("CUDA is not available (%s). Falling back to CPU int8.", exc)

    try:
        model = WhisperModel(load_target, device="cpu", compute_type="int8", **kwargs)
    except Exception as exc:
        mode = "offline-only" if offline_only else "online-or-cache"
        raise UserFacingError(
            f"Failed to load model '{load_target}' ({mode}). Details: {exc}"
        ) from exc
    return model, "cpu", str(load_target)


def transcribe_to_payload(
    input_path: Path, options: TranscriptionOptions, logger: logging.Logger
) -> dict[str, Any]:
    if options.lang not in _SUPPORTED_LANGS:
        raise UserFacingError(f"Unsupported --lang '{options.lang}'.")
    if options.model not in _SUPPORTED_MODELS:
        raise UserFacingError(f"Unsupported --model '{options.model}'.")
    if options.vad_min_silence_ms < 0 or options.vad_speech_pad_ms < 0:
        raise UserFacingError("--vad parameters must be >= 0.")
    if options.max_line_chars <= 0 or options.max_words_per_line <= 0:
        raise UserFacingError("--max_line_chars and --max_words_per_line must be > 0.")

    audio_meta = read_audio_meta(input_path)
    model, effective_device, loaded_model = _load_model(
        model_name=options.model,
        model_path=options.model_path,
        models_dir=options.models_dir,
        device=options.device,
        offline_only=options.offline_only,
        logger=logger,
    )

    transcribe_kwargs: dict[str, Any] = {
        "language": None if options.lang == "auto" else options.lang,
        "word_timestamps": True,
        "vad_filter": options.vad_enabled,
        "condition_on_previous_text": True,
    }
    if options.vad_enabled:
        transcribe_kwargs["vad_parameters"] = {
            "min_silence_duration_ms": options.vad_min_silence_ms,
            "speech_pad_ms": options.vad_speech_pad_ms,
        }

    logger.info(
        "Transcribing '%s' with model=%s lang=%s device=%s vad=%s",
        input_path,
        options.model,
        options.lang,
        effective_device,
        "on" if options.vad_enabled else "off",
    )
    segments_iterable, info = model.transcribe(str(input_path), **transcribe_kwargs)

    raw_words: list[RawWord] = []
    segments: list[dict[str, float | str]] = []
    for segment in segments_iterable:
        seg_start = max(0.0, float(getattr(segment, "start", 0.0)))
        seg_end = max(seg_start + 0.001, float(getattr(segment, "end", seg_start + 0.001)))
        seg_text = normalize_text_blob(str(getattr(segment, "text", "")))

        if seg_text:
            segments.append(
                {
                    "s": round(seg_start, 3),
                    "e": round(seg_end, 3),
                    "text": seg_text,
                }
            )
        raw_words.extend(_collect_raw_words(segment, seg_text, seg_start, seg_end))

    words = coalesce_words(raw_words)
    if not words:
        raise UserFacingError("No words recognized. Check if input audio contains speech.")

    detected = str(getattr(info, "language", "") or "").strip().lower()
    resolved_lang = options.lang
    if options.lang == "auto" and detected in {"cs", "en"}:
        resolved_lang = detected

    payload: dict[str, Any] = {
        "version": "1.0",
        "lang": resolved_lang,
        "text": compose_transcript(words),
        "words": words,
        "segments": segments,
        "meta": {
            "engine": "faster-whisper",
            "model": options.model,
            "model_loaded": loaded_model,
            "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "audio": audio_meta,
            "device": effective_device,
            "requested_lang": options.lang,
            "detected_lang": detected or "unknown",
            "notes": "",
        },
        "layout_hints": {
            "max_line_chars": options.max_line_chars,
            "max_words_per_line": options.max_words_per_line,
        },
    }

    if options.diarization:
        try:
            turns = run_diarization(
                audio_path=input_path,
                model=options.diarization_model,
                hf_token=options.hf_token or None,
                logger=logger,
            )
            labeled_words, speaker_segments = attach_speakers_to_words(words, turns)
            payload["words"] = labeled_words
            payload["speaker_segments"] = speaker_segments
            payload["meta"]["diarization"] = {
                "enabled": True,
                "model": options.diarization_model,
                "turns": len(turns),
            }
        except DiarizationError as exc:
            raise UserFacingError(str(exc)) from exc
    else:
        payload["meta"]["diarization"] = {"enabled": False}

    try:
        validate_words_payload(payload)
    except ValidationError as exc:
        raise UserFacingError(f"Generated JSON is invalid: {exc}") from exc

    logger.info(
        "Transcription done: %s words, %s segments.",
        len(words),
        len(segments),
    )
    return payload


def build_transcription_options(
    *,
    lang: str,
    model: str,
    device: str,
    model_path: str,
    models_dir: str,
    offline_only: bool,
    vad: str,
    vad_min_silence_ms: int,
    vad_speech_pad_ms: int,
    max_line_chars: int,
    max_words_per_line: int,
    diarization: str,
    diarization_model: str,
    hf_token: str,
) -> TranscriptionOptions:
    return TranscriptionOptions(
        lang=lang,
        model=model,
        device=device,
        model_path=model_path,
        models_dir=models_dir,
        offline_only=offline_only,
        vad_enabled=(vad == "on"),
        vad_min_silence_ms=vad_min_silence_ms,
        vad_speech_pad_ms=vad_speech_pad_ms,
        max_line_chars=max_line_chars,
        max_words_per_line=max_words_per_line,
        diarization=(diarization == "on"),
        diarization_model=diarization_model,
        hf_token=hf_token,
    )


def format_validation_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        validate_words_payload(payload)
    except ValidationError as exc:
        errors.append(str(exc))
    return errors
