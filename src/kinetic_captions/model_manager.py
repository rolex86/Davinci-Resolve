from __future__ import annotations

import argparse
from pathlib import Path
import sys


MODEL_CHOICES = ("small", "medium", "large")
MODEL_NAME_MAP = {
    "small": "small",
    "medium": "medium",
    "large": "large-v3",
}


class ModelInstallError(RuntimeError):
    """Raised when whisper model installation fails."""


def resolve_model_name(model: str) -> str:
    if model not in MODEL_NAME_MAP:
        raise ModelInstallError(
            f"Unsupported model '{model}'. Supported values: {', '.join(MODEL_CHOICES)}"
        )
    return MODEL_NAME_MAP[model]


def install_model(
    *,
    model: str,
    models_dir: Path,
    local_files_only: bool = False,
) -> Path:
    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        raise ModelInstallError(
            "Missing dependency 'faster-whisper'. Install dependencies first."
        ) from exc

    resolved = resolve_model_name(model)
    models_dir.mkdir(parents=True, exist_ok=True)
    try:
        model_path = download_model(
            size_or_id=resolved,
            output_dir=str(models_dir),
            local_files_only=local_files_only,
        )
    except Exception as exc:
        mode = "offline-only" if local_files_only else "online-or-cache"
        raise ModelInstallError(
            f"Failed to install model '{resolved}' in {mode} mode: {exc}"
        ) from exc

    return Path(model_path).resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install_whisper_model",
        description="Install and cache faster-whisper model into a local folder.",
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=list(MODEL_CHOICES),
        help="Model size alias.",
    )
    parser.add_argument(
        "--models-dir",
        default="models",
        help="Target directory for cached models.",
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Do not use network, only resolve from local cache.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        path = install_model(
            model=args.model,
            models_dir=Path(args.models_dir).expanduser().resolve(),
            local_files_only=bool(args.offline_only),
        )
    except ModelInstallError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
