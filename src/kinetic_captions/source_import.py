from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import Iterable

from .text_norm import RawWord, coalesce_words, compose_transcript, normalize_text_blob
from .validation import ValidationError, validate_words_payload

_TOKEN_RE = re.compile(r"\S+")
_ASS_TAG_RE = re.compile(r"\{[^{}]*\}")
_HTML_TAG_RE = re.compile(r"</?[^>]+>")
_SRT_TIME_RE = re.compile(
    r"(?P<s>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<e>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


class SourceImportError(RuntimeError):
    """Raised for human-facing source parsing/import issues."""


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


def payload_from_subtitle(
    *,
    subtitle_path: Path,
    lang: str,
    max_line_chars: int,
    max_words_per_line: int,
    logger: logging.Logger,
) -> dict:
    if not subtitle_path.exists():
        raise SourceImportError(f"Subtitle file does not exist: {subtitle_path}")
    segments = _load_subtitle_segments(subtitle_path)
    if not segments:
        raise SourceImportError("Subtitle file did not contain usable dialogue lines.")
    return _build_payload(
        segments=segments,
        lang=lang,
        engine="subtitle-import",
        model="n/a",
        max_line_chars=max_line_chars,
        max_words_per_line=max_words_per_line,
        logger=logger,
        notes=f"source={subtitle_path.name}",
    )


def payload_from_manual_text(
    *,
    manual_text: str,
    lang: str,
    max_line_chars: int,
    max_words_per_line: int,
    start_sec: float,
    duration_sec: float,
    wpm: float,
    logger: logging.Logger,
) -> dict:
    normalized = manual_text.replace("\r", "\n").strip()
    if not normalized:
        raise SourceImportError("Manual text is empty.")
    if start_sec < 0:
        raise SourceImportError("--manual-start-sec must be >= 0.")
    if duration_sec < 0:
        raise SourceImportError("--manual-duration-sec must be >= 0.")
    if wpm <= 0:
        raise SourceImportError("--manual-wpm must be > 0.")

    segments = _segments_from_manual_text(
        text=normalized,
        start_sec=start_sec,
        duration_sec=duration_sec,
        wpm=wpm,
    )
    return _build_payload(
        segments=segments,
        lang=lang,
        engine="manual-text",
        model="n/a",
        max_line_chars=max_line_chars,
        max_words_per_line=max_words_per_line,
        logger=logger,
        notes="source=manual-text",
    )


def _build_payload(
    *,
    segments: list[SubtitleSegment],
    lang: str,
    engine: str,
    model: str,
    max_line_chars: int,
    max_words_per_line: int,
    logger: logging.Logger,
    notes: str,
) -> dict:
    raw_words = _segments_to_raw_words(segments)
    words = coalesce_words(raw_words)
    if not words:
        raise SourceImportError("Could not derive words from input text.")

    payload = {
        "version": "1.0",
        "lang": lang,
        "text": compose_transcript(words),
        "words": words,
        "segments": [
            {"s": round(seg.start, 3), "e": round(seg.end, 3), "text": seg.text}
            for seg in segments
        ],
        "meta": {
            "engine": engine,
            "model": model,
            "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "audio": {"sr": 0, "channels": 0},
            "notes": notes,
        },
        "layout_hints": {
            "max_line_chars": max_line_chars,
            "max_words_per_line": max_words_per_line,
        },
    }
    try:
        validate_words_payload(payload)
    except ValidationError as exc:
        raise SourceImportError(f"Generated JSON is invalid: {exc}") from exc
    logger.info(
        "Imported text source: %s segments, %s words.",
        len(segments),
        len(words),
    )
    return payload


def _load_subtitle_segments(path: Path) -> list[SubtitleSegment]:
    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    if suffix == ".srt":
        return _parse_srt(content)
    if suffix == ".ass":
        return _parse_ass(content)
    raise SourceImportError(
        f"Unsupported subtitle format '{suffix}'. Supported: .srt, .ass"
    )


def _parse_srt(content: str) -> list[SubtitleSegment]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    segments: list[SubtitleSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        time_line_index = next((i for i, line in enumerate(lines) if "-->" in line), -1)
        if time_line_index < 0:
            continue
        match = _SRT_TIME_RE.search(lines[time_line_index])
        if not match:
            continue
        try:
            start = _parse_srt_time(match.group("s"))
            end = _parse_srt_time(match.group("e"))
        except SourceImportError:
            continue
        if end <= start:
            continue
        text = normalize_text_blob(_strip_common_markup(" ".join(lines[time_line_index + 1 :])))
        if not text:
            continue
        segments.append(SubtitleSegment(start=start, end=end, text=text))
    return _merge_and_sort_segments(segments)


def _parse_ass(content: str) -> list[SubtitleSegment]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    in_events = False
    format_fields: list[str] = []
    segments: list[SubtitleSegment] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("["):
            in_events = line.lower() == "[events]"
            continue
        if not in_events:
            continue

        if line.lower().startswith("format:"):
            format_fields = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:"):
            continue

        payload = line.split(":", 1)[1].lstrip()
        fields = _split_ass_fields(payload, len(format_fields) if format_fields else 10)
        if not format_fields:
            format_fields = [
                "layer",
                "start",
                "end",
                "style",
                "name",
                "marginl",
                "marginr",
                "marginv",
                "effect",
                "text",
            ]
        field_map = {name: fields[idx] if idx < len(fields) else "" for idx, name in enumerate(format_fields)}
        if "start" not in field_map or "end" not in field_map:
            continue
        try:
            start = _parse_ass_time(field_map.get("start", ""))
            end = _parse_ass_time(field_map.get("end", ""))
        except SourceImportError:
            continue
        if end <= start:
            continue
        text = normalize_text_blob(_strip_ass_markup(field_map.get("text", "")))
        if not text:
            continue
        segments.append(SubtitleSegment(start=start, end=end, text=text))
    return _merge_and_sort_segments(segments)


def _split_ass_fields(value: str, expected_fields: int) -> list[str]:
    if expected_fields <= 1:
        return [value.strip()]
    out: list[str] = []
    current = value
    for _ in range(expected_fields - 1):
        if "," not in current:
            out.append(current.strip())
            current = ""
            continue
        head, current = current.split(",", 1)
        out.append(head.strip())
    out.append(current.strip())
    return out


def _parse_srt_time(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) != 3:
        raise SourceImportError(f"Invalid SRT time value: {value}")
    h = int(parts[0])
    m = int(parts[1])
    sec = float(parts[2])
    return round((h * 3600) + (m * 60) + sec, 3)


def _parse_ass_time(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) != 3:
        raise SourceImportError(f"Invalid ASS time value: {value}")
    h = int(parts[0])
    m = int(parts[1])
    sec_parts = parts[2].split(".")
    sec = int(sec_parts[0]) if sec_parts[0] else 0
    frac = sec_parts[1] if len(sec_parts) > 1 else ""
    frac_value = int(frac) / (10 ** len(frac)) if frac else 0.0
    return round((h * 3600) + (m * 60) + sec + frac_value, 3)


def _strip_common_markup(text: str) -> str:
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = cleaned.replace("\\N", " ").replace("\\n", " ")
    return cleaned


def _strip_ass_markup(text: str) -> str:
    cleaned = text.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
    cleaned = _ASS_TAG_RE.sub("", cleaned)
    return _strip_common_markup(cleaned)


def _merge_and_sort_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: (s.start, s.end))
    normalized: list[SubtitleSegment] = []
    last_start = -1.0
    for segment in ordered:
        s = max(0.0, float(segment.start))
        e = max(s + 0.001, float(segment.end))
        if s < last_start:
            shift = last_start - s
            s = last_start
            e = max(s + 0.001, e + shift)
        normalized.append(SubtitleSegment(start=s, end=e, text=segment.text))
        last_start = s
    return normalized


def _segments_to_raw_words(segments: Iterable[SubtitleSegment]) -> list[RawWord]:
    out: list[RawWord] = []
    for segment in segments:
        tokens = _TOKEN_RE.findall(segment.text)
        if not tokens:
            continue
        duration = max(0.001, segment.end - segment.start)
        weights = [_token_weight(token) for token in tokens]
        total_weight = float(sum(weights))
        cursor = segment.start
        for idx, token in enumerate(tokens):
            if idx == len(tokens) - 1:
                end = segment.end
            else:
                share = duration * (weights[idx] / total_weight)
                end = min(segment.end, cursor + share)
                end = max(cursor + 0.001, end)
            out.append(RawWord(token=token, start=cursor, end=end))
            cursor = end
    return out


def _token_weight(token: str) -> int:
    core = re.sub(r"[^\w\d]+", "", token, flags=re.UNICODE)
    return max(1, len(core))


def _segments_from_manual_text(
    *,
    text: str,
    start_sec: float,
    duration_sec: float,
    wpm: float,
) -> list[SubtitleSegment]:
    lines = [normalize_text_blob(line) for line in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        raise SourceImportError("Manual text has no visible words.")

    word_counts = [len(_TOKEN_RE.findall(line)) for line in lines]
    total_words = sum(word_counts)
    if total_words <= 0:
        raise SourceImportError("Manual text has no words.")

    total_duration = duration_sec
    if total_duration == 0:
        total_duration = max(1.0, (total_words / wpm) * 60.0)

    segments: list[SubtitleSegment] = []
    cursor = start_sec
    for idx, line in enumerate(lines):
        if idx == len(lines) - 1:
            end = start_sec + total_duration
        else:
            share = total_duration * (word_counts[idx] / total_words)
            end = cursor + max(0.05, share)
        end = max(cursor + 0.001, end)
        segments.append(SubtitleSegment(start=cursor, end=end, text=line))
        cursor = end
    return segments
