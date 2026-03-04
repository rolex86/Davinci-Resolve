from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Sequence

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
    parser.add_argument("--input", required=True, help="Input WAV file path.")
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file does not exist: {input_path}", file=sys.stderr)
        return 2

    output_path = _resolve_output_path(input_path, args.output)
    log_path = Path(args.log).expanduser().resolve() if args.log else None
    transcript_path = (
        Path(args.transcript_out).expanduser().resolve() if args.transcript_out else None
    )
    logger = _build_logger(log_path)

    try:
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
        payload = transcribe_to_payload(input_path, options, logger)
        _write_json(output_path, payload)

        if transcript_path:
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(str(payload["text"]).strip() + "\n", encoding="utf-8")

        logger.info("Saved words.json to %s", output_path)
        if transcript_path:
            logger.info("Saved transcript to %s", transcript_path)
        return 0
    except UserFacingError as exc:
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
