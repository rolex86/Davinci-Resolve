from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_WS_RE = re.compile(r"\s+")
_ATTACH_PREV_RE = re.compile(r"^[,.;:!?%…)\]\}\"'»]+$")
_ATTACH_NEXT_RE = re.compile(r"^[\(\[\{„“\"'«]+$")

_CONTRACTION_SUFFIXES = {
    "'s",
    "'re",
    "'ve",
    "'m",
    "'ll",
    "'d",
    "n't",
    "’s",
    "’re",
    "’ve",
    "’m",
    "’ll",
    "’d",
    "n’t",
}


@dataclass(frozen=True)
class RawWord:
    token: str
    start: float
    end: float


def normalize_token(token: str) -> str:
    value = token.replace("\u00a0", " ").strip()
    if not value:
        return ""
    return _WS_RE.sub(" ", value)


def normalize_text_blob(text: str) -> str:
    return _WS_RE.sub(" ", text.replace("\u00a0", " ")).strip()


def should_attach_to_previous(token: str) -> bool:
    if not token:
        return False
    if token in _CONTRACTION_SUFFIXES:
        return True
    if _ATTACH_PREV_RE.match(token):
        return True
    if token in {"...", "…"}:
        return True
    return False


def should_attach_to_next(token: str) -> bool:
    if not token:
        return False
    return bool(_ATTACH_NEXT_RE.match(token))


def coalesce_words(raw_words: Iterable[RawWord]) -> list[dict[str, float | int | str]]:
    words: list[dict[str, float | str]] = []
    last_start = 0.0
    pending_prefix = ""

    for item in raw_words:
        token = normalize_token(item.token)
        if not token:
            continue

        start = max(0.0, float(item.start))
        end = max(start + 0.001, float(item.end))

        if start < last_start:
            shift = last_start - start
            start = last_start
            end = max(start + 0.001, end + shift)

        if should_attach_to_next(token):
            pending_prefix = f"{pending_prefix}{token}"
            continue

        token = f"{pending_prefix}{token}"
        pending_prefix = ""

        if should_attach_to_previous(token) and words:
            words[-1]["w"] = f"{words[-1]['w']}{token}"
            words[-1]["e"] = max(float(words[-1]["e"]), end)
            continue

        words.append({"w": token, "s": start, "e": end})
        last_start = start

    if pending_prefix and words:
        words[-1]["w"] = f"{words[-1]['w']}{pending_prefix}"

    normalized: list[dict[str, float | int | str]] = []
    for idx, word in enumerate(words):
        s = round(float(word["s"]), 3)
        e = round(float(word["e"]), 3)
        if e <= s:
            e = round(s + 0.001, 3)
        normalized.append({"i": idx, "w": str(word["w"]), "s": s, "e": e})
    return normalized


def compose_transcript(words: Iterable[dict[str, float | int | str]]) -> str:
    return " ".join(str(word["w"]) for word in words).strip()
