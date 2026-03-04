from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Sequence

from .source_import import (
    SourceImportError,
    payload_from_manual_text,
    payload_from_subtitle,
)
from .transcription import (
    UserFacingError,
    build_transcription_options,
    transcribe_to_payload,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_words",
        description=(
            "Offline word-level timestamps generator for DaVinci Resolve "
            "Kinetic Captions."
        ),
    )
    parser.add_argument(
        "--input",
        help="Input WAV file path (audio transcription mode).",
    )
    parser.add_argument(
        "--subtitle",
        help="Subtitle file input (.srt or .ass) for direct conversion mode.",
    )
    parser.add_argument(
        "--manual-text",
        default="",
        help="Manual text input (no audio needed).",
    )
    parser.add_argument(
        "--manual-text-file",
        default="",
        help="Path to a UTF-8 text file for manual text mode.",
    )
    parser.add_argument(
        "--manual-start-sec",
        type=float,
        default=0.0,
        help="Manual mode start timestamp in seconds.",
    )
    parser.add_argument(
        "--manual-duration-sec",
        type=float,
        default=0.0,
        help="Manual mode total duration in seconds. 0 means auto by WPM.",
    )
    parser.add_argument(
        "--manual-wpm",
        type=float,
        default=150.0,
        help="Manual mode words-per-minute when duration is auto.",
    )
    parser.add_argument(
        "--output",
        help="Output words.json path. Default: <input_dir>/words.json",
    )
    parser.add_argument(
        "--lang",
        default="auto",
        choices=["auto", "cs", "en"],
        help="Transcription language mode.",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["small", "medium", "large"],
        help="Whisper model size.",
    )
    parser.add_argument(
        "--model-path",
        default="",
        help="Optional explicit local path to CTranslate2 whisper model.",
    )
    parser.add_argument(
        "--models-dir",
        default="",
        help="Optional model cache directory for faster-whisper downloads.",
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Disable model network download and use local cache only.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Execution device. CUDA automatically falls back to CPU if unavailable.",
    )
    parser.add_argument(
        "--vad",
        default="on",
        choices=["on", "off"],
        help="Voice activity detection.",
    )
    parser.add_argument(
        "--vad_min_silence_ms",
        "--vad-min-silence-ms",
        dest="vad_min_silence_ms",
        type=int,
        default=500,
        help="Minimum silence duration for VAD splitting in milliseconds.",
    )
    parser.add_argument(
        "--vad_speech_pad_ms",
        "--vad-speech-pad-ms",
        dest="vad_speech_pad_ms",
        type=int,
        default=80,
        help="Speech padding around VAD segments in milliseconds.",
    )
    parser.add_argument(
        "--max_line_chars",
        "--max-line-chars",
        dest="max_line_chars",
        type=int,
        default=32,
        help="Layout hint for max characters per line in the title.",
    )
    parser.add_argument(
        "--max_words_per_line",
        "--max-words-per-line",
        dest="max_words_per_line",
        type=int,
        default=7,
        help="Layout hint for max words per line in the title.",
    )
    parser.add_argument(
        "--transcript-out",
        help="Optional full transcript text output path.",
    )
    parser.add_argument(
        "--log",
        help="Optional log file path.",
    )
    parser.add_argument(
        "--diarization",
        default="off",
        choices=["on", "off"],
        help="Enable optional speaker diarization (V2).",
    )
    parser.add_argument(
        "--diarization-model",
        default="pyannote/speaker-diarization-3.1",
        help="Diarization model ID/path used by pyannote.",
    )
    parser.add_argument(
        "--hf-token",
        default="",
        help="Optional HuggingFace token for gated diarization models.",
    )
    return parser


def _build_logger(log_path: Path | None) -> logging.Logger:
    logger = logging.getLogger("generate_words")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).expanduser().resolve()
    return input_path.parent / "words.json"


def _resolve_source(args: argparse.Namespace) -> tuple[str, Path | None, str]:
    audio_path = Path(args.input).expanduser().resolve() if args.input else None
    subtitle_path = Path(args.subtitle).expanduser().resolve() if args.subtitle else None
    manual_text_file = (
        Path(args.manual_text_file).expanduser().resolve() if args.manual_text_file else None
    )
    manual_text_inline = str(args.manual_text or "").strip()
    manual_selected = bool(manual_text_inline) or (manual_text_file is not None)

    if manual_text_file and manual_text_inline:
        raise UserFacingError("Use either --manual-text or --manual-text-file, not both.")

    manual_text_value = manual_text_inline
    if manual_text_file:
        if not manual_text_file.exists():
            raise UserFacingError(f"Manual text file does not exist: {manual_text_file}")
        manual_text_value = manual_text_file.read_text(encoding="utf-8", errors="replace").strip()

    selected = [
        ("audio", audio_path is not None),
        ("subtitle", subtitle_path is not None),
        ("manual", manual_selected),
    ]
    selected_count = sum(1 for _, is_on in selected if is_on)
    if selected_count != 1:
        raise UserFacingError(
            "Select exactly one source: --input <audio.wav> OR --subtitle <file.srt|file.ass> "
            "OR --manual-text/--manual-text-file."
        )

    if audio_path:
        if not audio_path.exists():
            raise UserFacingError(f"Input audio file does not exist: {audio_path}")
        return "audio", audio_path, ""

    if subtitle_path:
        if not subtitle_path.exists():
            raise UserFacingError(f"Subtitle file does not exist: {subtitle_path}")
        return "subtitle", subtitle_path, ""

    if not manual_text_value:
        raise UserFacingError("Manual text mode selected, but provided text is empty.")
    return "manual", manual_text_file, manual_text_value


def _resolve_output_base(source_kind: str, source_path: Path | None) -> Path:
    if source_path:
        return source_path
    if source_kind == "manual":
        return Path.cwd() / "manual_text_source.txt"
    return Path.cwd() / "input.wav"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    log_path = Path(args.log).expanduser().resolve() if args.log else None

    try:
        source_kind, source_path, manual_text = _resolve_source(args)
        source_base = _resolve_output_base(source_kind, source_path)
        output_path = _resolve_output_path(source_base, args.output)
        transcript_path = (
            Path(args.transcript_out).expanduser().resolve() if args.transcript_out else None
        )
        logger = _build_logger(log_path)

        if source_kind == "audio":
            assert source_path is not None
            options = build_transcription_options(
                lang=args.lang,
                model=args.model,
                device=args.device,
                model_path=args.model_path,
                models_dir=args.models_dir,
                offline_only=bool(args.offline_only),
                vad=args.vad,
                vad_min_silence_ms=args.vad_min_silence_ms,
                vad_speech_pad_ms=args.vad_speech_pad_ms,
                max_line_chars=args.max_line_chars,
                max_words_per_line=args.max_words_per_line,
                diarization=args.diarization,
                diarization_model=args.diarization_model,
                hf_token=args.hf_token,
            )
            payload = transcribe_to_payload(source_path, options, logger)
        elif source_kind == "subtitle":
            assert source_path is not None
            payload = payload_from_subtitle(
                subtitle_path=source_path,
                lang=args.lang,
                max_line_chars=args.max_line_chars,
                max_words_per_line=args.max_words_per_line,
                logger=logger,
            )
        else:
            payload = payload_from_manual_text(
                manual_text=manual_text,
                lang=args.lang,
                max_line_chars=args.max_line_chars,
                max_words_per_line=args.max_words_per_line,
                start_sec=float(args.manual_start_sec),
                duration_sec=float(args.manual_duration_sec),
                wpm=float(args.manual_wpm),
                logger=logger,
            )

        _write_json(output_path, payload)

        if transcript_path:
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(str(payload["text"]).strip() + "\n", encoding="utf-8")

        logger.info("Saved words.json to %s", output_path)
        if transcript_path:
            logger.info("Saved transcript to %s", transcript_path)
        return 0
    except (UserFacingError, SourceImportError) as exc:
        logger = _build_logger(log_path)
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
        return 130
    except Exception as exc:  # pragma: no cover - defensive runtime boundary
        logger.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
