from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any


def _import_resolve_api():
    try:
        import DaVinciResolveScript as dvr  # type: ignore

        return dvr
    except Exception:
        resolve_api = os.environ.get("RESOLVE_SCRIPT_API")
        if resolve_api:
            candidate = Path(resolve_api) / "Modules"
            if candidate.exists():
                sys.path.append(str(candidate))
        import DaVinciResolveScript as dvr  # type: ignore

        return dvr


def connect_resolve() -> tuple[Any, Any, Any]:
    dvr = _import_resolve_api()
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Could not connect to Resolve scripting API.")
    manager = resolve.GetProjectManager()
    if not manager:
        raise RuntimeError("Could not access Resolve project manager.")
    project = manager.GetCurrentProject()
    if not project:
        raise RuntimeError("No active Resolve project.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("No active timeline.")
    return resolve, project, timeline


def _timeline_fps(project: Any, timeline: Any) -> float:
    fps = timeline.GetSetting("timelineFrameRate") or project.GetSetting("timelineFrameRate")
    try:
        return float(fps)
    except Exception:
        return 25.0


def _timeline_start_frame(timeline: Any) -> int:
    value = 0
    if hasattr(timeline, "GetStartFrame"):
        try:
            value = int(timeline.GetStartFrame())
        except Exception:
            value = 0
    return value


def _wait_for_render(project: Any, timeout_sec: int = 3600) -> None:
    start = time.time()
    while project.IsRenderingInProgress():
        if time.time() - start > timeout_sec:
            raise TimeoutError("Resolve render timed out.")
        time.sleep(0.5)


def export_timeline_audio(project: Any, output_wav: Path) -> Path:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        "SelectAllFrames": True,
        "TargetDir": str(output_wav.parent),
        "CustomName": output_wav.stem,
        "ExportVideo": False,
        "ExportAudio": True,
        "Format": "wav",
        "AudioCodec": "LinearPCM",
        "AudioSampleRate": 48000,
    }
    if not project.SetRenderSettings(settings):
        raise RuntimeError("Resolve refused render settings for audio export.")

    job_id = project.AddRenderJob()
    if not job_id:
        raise RuntimeError("Failed to add Resolve render job.")

    try:
        if not project.StartRendering(job_id):
            raise RuntimeError("Resolve failed to start render job.")
        _wait_for_render(project)
    finally:
        try:
            project.DeleteRenderJob(job_id)
        except Exception:
            pass

    if output_wav.exists():
        return output_wav

    # Some Resolve versions append extension automatically.
    fallback = output_wav.parent / f"{output_wav.stem}.wav"
    if fallback.exists():
        return fallback

    candidates = sorted(output_wav.parent.glob(f"{output_wav.stem}*"))
    if candidates:
        return candidates[0]
    raise RuntimeError(f"Audio export did not produce expected file: {output_wav}")


def run_generate_words(
    *,
    wav_path: Path,
    json_path: Path,
    lang: str,
    model: str,
    device: str,
    generator_cmd: str,
    model_path: str,
    models_dir: str,
    offline_only: bool,
) -> Path:
    json_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = shlex.split(generator_cmd, posix=os.name != "nt")
    if not cmd:
        raise RuntimeError("Invalid --generator-cmd")
    cmd += [
        "--input",
        str(wav_path),
        "--output",
        str(json_path),
        "--lang",
        lang,
        "--model",
        model,
        "--device",
        device,
        "--vad",
        "on",
        "--max_line_chars",
        "32",
        "--max_words_per_line",
        "7",
    ]
    if model_path:
        cmd += ["--model-path", model_path]
    if models_dir:
        cmd += ["--models-dir", models_dir]
    if offline_only:
        cmd += ["--offline-only"]

    print("Running:", " ".join(cmd))
    try:
        completed = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        completed = subprocess.run(
            " ".join(shlex.quote(part) for part in cmd), shell=True, check=False
        )
    if completed.returncode != 0:
        raise RuntimeError(f"generate_words failed with code {completed.returncode}")
    if not json_path.exists():
        raise RuntimeError(f"Missing output JSON: {json_path}")
    return json_path


def _find_item_recursive(folder: Any, name: str) -> Any:
    for item in folder.GetClipList() or []:
        clip_name = item.GetName() if hasattr(item, "GetName") else ""
        if clip_name == name:
            return item
    for sub in folder.GetSubFolderList() or []:
        found = _find_item_recursive(sub, name)
        if found:
            return found
    return None


def find_title_item(project: Any, title_name: str) -> Any:
    media_pool = project.GetMediaPool()
    root = media_pool.GetRootFolder()
    return _find_item_recursive(root, title_name)


@dataclass(frozen=True)
class TitleSpan:
    start_sec: float
    end_sec: float


def build_title_spans(payload: dict[str, Any], min_duration_sec: float = 1.0) -> list[TitleSpan]:
    spans: list[TitleSpan] = []
    segments = payload.get("segments") or []
    if isinstance(segments, list) and segments:
        for item in segments:
            if not isinstance(item, dict):
                continue
            s = float(item.get("s", 0.0))
            e = float(item.get("e", 0.0))
            if e - s >= 0.05:
                spans.append(TitleSpan(s, max(e, s + min_duration_sec)))
    if spans:
        return spans

    words = payload.get("words") or []
    if not words:
        return []
    first = float(words[0].get("s", 0.0))
    last = float(words[-1].get("e", first + min_duration_sec))
    spans.append(TitleSpan(first, max(last, first + min_duration_sec)))
    return spans


def append_title_clips(
    project: Any,
    timeline: Any,
    title_item: Any,
    spans: list[TitleSpan],
    track_index: int,
) -> list[Any]:
    fps = _timeline_fps(project, timeline)
    base = _timeline_start_frame(timeline)
    media_pool = project.GetMediaPool()

    created: list[Any] = []
    for span in spans:
        start_frame = base + int(round(span.start_sec * fps))
        end_frame = base + int(round(span.end_sec * fps))
        duration = max(1, end_frame - start_frame)

        clip_info = {
            "mediaPoolItem": title_item,
            "recordFrame": start_frame,
            "trackIndex": int(track_index),
            "mediaType": 1,
            "startFrame": 0,
            "endFrame": duration,
        }
        result = media_pool.AppendToTimeline([clip_info])
        if isinstance(result, list) and result:
            created.extend(result)
        elif result:
            created.append(result)
    return created


def try_set_title_data_source(item: Any, json_path: Path) -> bool:
    try:
        comp = item.GetFusionCompByIndex(1)
    except Exception:
        return False
    if not comp:
        return False

    for tool_name in ("KineticCaptionsBase", "KineticCaptions"):
        try:
            tool = comp.FindTool(tool_name)
        except Exception:
            tool = None
        if not tool:
            continue
        try:
            tool.SetInput("DataMode", 0)
            tool.SetInput("DataSource", str(json_path))
            return True
        except Exception:
            continue
    return False


def run_pipeline(args: argparse.Namespace) -> int:
    _, project, timeline = connect_resolve()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = output_dir / args.audio_name
    json_path = output_dir / args.words_name

    exported = export_timeline_audio(project, wav_path)
    words_json = run_generate_words(
        wav_path=exported,
        json_path=json_path,
        lang=args.lang,
        model=args.model,
        device=args.device,
        generator_cmd=args.generator_cmd,
        model_path=args.model_path,
        models_dir=args.models_dir,
        offline_only=args.offline_only,
    )

    payload = json.loads(words_json.read_text(encoding="utf-8"))
    spans = build_title_spans(payload, min_duration_sec=args.min_title_duration)

    title_item = find_title_item(project, args.title_name)
    if not title_item:
        raise RuntimeError(
            f"Title '{args.title_name}' not found in Media Pool. "
            "Install .drfx and import title into the project first."
        )

    created = append_title_clips(
        project,
        timeline,
        title_item,
        spans,
        track_index=args.title_track,
    )

    bound = 0
    for item in created:
        if try_set_title_data_source(item, words_json):
            bound += 1

    print(f"Audio exported: {exported}")
    print(f"words.json: {words_json}")
    print(f"Title clips inserted: {len(created)}")
    print(f"Title clips with DataSource bound: {bound}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve automation pipeline for Kinetic Captions.")
    parser.add_argument("--output-dir", default="./out", help="Output folder for WAV and words.json.")
    parser.add_argument("--audio-name", default="timeline_audio.wav")
    parser.add_argument("--words-name", default="words.json")
    parser.add_argument("--title-name", default="Kinetic Captions")
    parser.add_argument("--title-track", type=int, default=3)
    parser.add_argument("--min-title-duration", type=float, default=1.0)

    parser.add_argument("--lang", default="auto", choices=["auto", "cs", "en"])
    parser.add_argument("--model", default="small", choices=["small", "medium", "large"])
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--model-path", default="")
    parser.add_argument("--models-dir", default="")
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument(
        "--generator-cmd",
        default="generate_words",
        help="Command used to run generate_words (for example: 'generate_words' or 'python -m kinetic_captions.cli').",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
