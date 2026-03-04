from __future__ import annotations

import logging
from pathlib import Path

import pytest

from kinetic_captions.source_import import (
    SourceImportError,
    payload_from_manual_text,
    payload_from_subtitle,
)


LOGGER = logging.getLogger("test_source_import")


def test_payload_from_srt(tmp_path: Path) -> None:
    srt = tmp_path / "sample.srt"
    srt.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,600\n"
        "Ahoj svete!\n\n"
        "2\n"
        "00:00:01,700 --> 00:00:03,000\n"
        "Jak se mas?\n",
        encoding="utf-8",
    )
    payload = payload_from_subtitle(
        subtitle_path=srt,
        lang="cs",
        max_line_chars=32,
        max_words_per_line=7,
        logger=LOGGER,
    )
    assert payload["meta"]["engine"] == "subtitle-import"
    assert len(payload["segments"]) == 2
    assert payload["segments"][0]["text"] == "Ahoj svete!"
    assert payload["words"][0]["w"] == "Ahoj"
    assert payload["words"][1]["w"] == "svete!"


def test_payload_from_ass(tmp_path: Path) -> None:
    ass = tmp_path / "sample.ass"
    ass.write_text(
        "[Script Info]\n"
        "Title: Test\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,Ahoj\\Nsvete\n"
        "Dialogue: 0,0:00:01.60,0:00:03.00,Default,,0,0,0,,{\\i1}Test{\\i0}\n",
        encoding="utf-8",
    )
    payload = payload_from_subtitle(
        subtitle_path=ass,
        lang="auto",
        max_line_chars=32,
        max_words_per_line=7,
        logger=LOGGER,
    )
    assert len(payload["segments"]) == 2
    assert payload["segments"][0]["text"] == "Ahoj svete"
    assert payload["segments"][1]["text"] == "Test"
    assert payload["words"][-1]["w"] == "Test"


def test_payload_from_manual_text_auto_duration() -> None:
    payload = payload_from_manual_text(
        manual_text="Ahoj svete\nDruhy radek",
        lang="cs",
        max_line_chars=32,
        max_words_per_line=7,
        start_sec=1.5,
        duration_sec=0.0,
        wpm=120.0,
        logger=LOGGER,
    )
    assert payload["meta"]["engine"] == "manual-text"
    assert len(payload["segments"]) == 2
    assert payload["segments"][0]["s"] >= 1.5
    assert payload["words"][0]["s"] >= 1.5
    assert payload["words"][-1]["e"] > payload["words"][0]["s"]


def test_payload_from_manual_text_rejects_bad_duration() -> None:
    with pytest.raises(SourceImportError):
        payload_from_manual_text(
            manual_text="Ahoj",
            lang="cs",
            max_line_chars=32,
            max_words_per_line=7,
            start_sec=0.0,
            duration_sec=-1.0,
            wpm=120.0,
            logger=LOGGER,
        )
