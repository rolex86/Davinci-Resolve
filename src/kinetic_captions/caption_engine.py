from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


MODE_REVEAL = 0
MODE_HIGHLIGHT = 1
MODE_COMBO = 2
WINDOW_TRAILING = 0
WINDOW_CENTERED = 1
LINES_AUTO = 0
LINES_SINGLE = 1
LINES_DOUBLE = 2


@dataclass(frozen=True)
class WordItem:
    i: int
    w: str
    s: float
    e: float
    sp: str = ""


@dataclass(frozen=True)
class CaptionData:
    words: tuple[WordItem, ...]
    text: str


@dataclass(frozen=True)
class CaptionSettings:
    mode: int = MODE_REVEAL
    timing_offset: float = 0.0
    lead_sec: float = 0.0
    lag_sec: float = 0.0
    rolling_window: bool = True
    window_words: int = 10
    window_mode: int = WINDOW_TRAILING
    lines: int = LINES_AUTO
    max_line_chars: int = 32
    max_words_per_line: int = 7


@dataclass(frozen=True)
class CaptionState:
    t: float
    display_text: str
    highlighted_word: str
    highlighted_index: int
    visible_indices: tuple[int, ...]
    error: str = ""


class CaptionDataCache:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, CaptionData]] = {}

    def from_file(self, path: Path) -> CaptionData:
        resolved = path.expanduser().resolve()
        key = str(resolved)
        mtime = resolved.stat().st_mtime
        hit = self._cache.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        data = load_caption_data_from_file(resolved)
        self._cache[key] = (mtime, data)
        return data

    def from_inline_json(self, json_text: str) -> CaptionData:
        key = f"inline:{hash(json_text)}"
        hit = self._cache.get(key)
        if hit:
            return hit[1]
        data = load_caption_data_from_inline(json_text)
        self._cache[key] = (0.0, data)
        return data


def load_caption_data_from_file(path: Path) -> CaptionData:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_caption_payload(payload)


def load_caption_data_from_inline(json_text: str) -> CaptionData:
    payload = json.loads(json_text)
    return parse_caption_payload(payload)


def parse_caption_payload(payload: dict[str, Any]) -> CaptionData:
    words_raw = payload.get("words")
    if not isinstance(words_raw, list) or not words_raw:
        raise ValueError("words.json is missing non-empty 'words' array.")

    words: list[WordItem] = []
    for index, item in enumerate(words_raw):
        if not isinstance(item, dict):
            raise ValueError(f"word[{index}] is not an object.")
        word = str(item.get("w", "")).strip()
        start = float(item.get("s", 0.0))
        end = float(item.get("e", 0.0))
        if not word:
            raise ValueError(f"word[{index}] has empty token.")
        if start < 0 or end < 0 or start >= end:
            raise ValueError(f"word[{index}] has invalid time range.")
        words.append(
            WordItem(
                i=int(item.get("i", index)),
                w=word,
                s=start,
                e=end,
                sp=str(item.get("sp", "")),
            )
        )
    words.sort(key=lambda item: (item.s, item.i))
    full_text = str(payload.get("text", "")).strip() or " ".join(word.w for word in words)
    return CaptionData(words=tuple(words), text=full_text)


def compute_caption_state(
    data: CaptionData,
    time_seconds: float,
    settings: CaptionSettings,
) -> CaptionState:
    words = data.words
    if not words:
        return CaptionState(
            t=time_seconds,
            display_text="Missing words",
            highlighted_word="",
            highlighted_index=-1,
            visible_indices=(),
            error="Missing words",
        )

    t = time_seconds + settings.timing_offset
    reveal_index = _find_reveal_index(words, t + settings.lead_sec)
    current_index = _find_highlight_index(words, t, settings.lead_sec, settings.lag_sec)
    if current_index < 0:
        current_index = reveal_index

    if settings.mode == MODE_HIGHLIGHT:
        visible_end = len(words) - 1
    else:
        visible_end = reveal_index

    if visible_end < 0:
        visible_indices: tuple[int, ...] = ()
    else:
        visible_indices = _window_indices(
            total=len(words),
            current=current_index if current_index >= 0 else visible_end,
            visible_end=visible_end,
            rolling=settings.rolling_window,
            window_words=max(1, settings.window_words),
            window_mode=settings.window_mode,
        )

    visible_words = [words[idx].w for idx in visible_indices]
    display_text = _render_lines(
        visible_words,
        lines=settings.lines,
        max_line_chars=max(4, settings.max_line_chars),
        max_words_per_line=max(1, settings.max_words_per_line),
    )

    highlighted_word = ""
    if settings.mode in (MODE_HIGHLIGHT, MODE_COMBO) and current_index >= 0:
        highlighted_word = words[current_index].w

    return CaptionState(
        t=t,
        display_text=display_text,
        highlighted_word=highlighted_word,
        highlighted_index=current_index,
        visible_indices=visible_indices,
    )


def _find_reveal_index(words: tuple[WordItem, ...], t: float) -> int:
    idx = -1
    for i, word in enumerate(words):
        if word.s <= t:
            idx = i
        else:
            break
    return idx


def _find_highlight_index(
    words: tuple[WordItem, ...], t: float, lead_sec: float, lag_sec: float
) -> int:
    hit = -1
    left = t + lead_sec
    right = t - lag_sec
    for i, word in enumerate(words):
        if word.s <= left and right < word.e:
            hit = i
            break
    if hit >= 0:
        return hit
    return _find_reveal_index(words, left)


def _window_indices(
    *,
    total: int,
    current: int,
    visible_end: int,
    rolling: bool,
    window_words: int,
    window_mode: int,
) -> tuple[int, ...]:
    if visible_end < 0:
        return ()
    if not rolling:
        return tuple(range(0, visible_end + 1))

    if window_mode == WINDOW_CENTERED:
        half = window_words // 2
        start = max(0, current - half)
        end = start + window_words - 1
        if end > visible_end:
            end = visible_end
            start = max(0, end - window_words + 1)
    else:
        end = visible_end
        start = max(0, end - window_words + 1)

    end = min(end, total - 1)
    if end < start:
        return ()
    return tuple(range(start, end + 1))


def _render_lines(
    words: list[str],
    *,
    lines: int,
    max_line_chars: int,
    max_words_per_line: int,
) -> str:
    if not words:
        return ""
    if lines == LINES_SINGLE:
        return " ".join(words)

    wrapped = _wrap_tokens(words, max_line_chars=max_line_chars, max_words=max_words_per_line)
    if lines == LINES_DOUBLE and len(wrapped) > 2:
        wrapped = [wrapped[0], " ".join(wrapped[1:])]
    return "\n".join(wrapped)


def _wrap_tokens(words: list[str], *, max_line_chars: int, max_words: int) -> list[str]:
    lines: list[list[str]] = [[]]
    for word in words:
        current = lines[-1]
        candidate = " ".join(current + [word]).strip()
        if current and (len(candidate) > max_line_chars or len(current) >= max_words):
            lines.append([word])
            continue
        current.append(word)
    return [" ".join(line).strip() for line in lines if line]
