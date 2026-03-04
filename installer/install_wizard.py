from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable


APP_NAME = "Kinetic Captions"
MANIFEST_NAME = "install_manifest.json"


@dataclass(frozen=True)
class InstallResult:
    install_dir: Path
    app_dir: Path
    venv_python: Path
    resolve_files: list[Path]
    model_dir: Path


def _print(msg: str) -> None:
    print(msg, flush=True)


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False


def _prompt_path(prompt: str, default: Path) -> Path:
    answer = input(f"{prompt} [{default}]: ").strip()
    if not answer:
        return default
    return Path(answer).expanduser().resolve()


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    _print(f"[RUN] {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")


def _copy_payload(source_root: Path, app_dir: Path) -> None:
    payload_paths: list[str] = [
        "src",
        "resolve",
        "fusion",
        "samples",
        "scripts",
        "installer",
        "docs",
        "pyproject.toml",
        "README.md",
        "generate_words.bat",
        "install_whisper_model.bat",
        "run_resolve_pipeline.bat",
        "dist/KineticCaptions.drfx",
    ]
    if app_dir.exists():
        shutil.rmtree(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)

    for rel in payload_paths:
        src = source_root / rel
        if not src.exists():
            continue
        dst = app_dir / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _venv_python(install_dir: Path) -> Path:
    return install_dir / "venv" / "Scripts" / "python.exe"


def _create_venv(install_dir: Path) -> Path:
    venv_dir = install_dir / "venv"
    if not venv_dir.exists():
        _run([sys.executable, "-m", "venv", str(venv_dir)])
    python_exe = _venv_python(install_dir)
    if not python_exe.exists():
        raise RuntimeError(f"Missing venv python executable: {python_exe}")
    return python_exe


def _install_runtime(venv_python: Path, app_dir: Path) -> None:
    wheels_dir = app_dir / "wheels"
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    if wheels_dir.exists() and any(wheels_dir.glob("*.whl")):
        req_file = app_dir / "installer" / "runtime-requirements.txt"
        if req_file.exists():
            _run(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--find-links",
                    str(wheels_dir),
                    "-r",
                    str(req_file),
                ]
            )
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                str(app_dir),
            ]
        )
    else:
        _run([str(venv_python), "-m", "pip", "install", str(app_dir)])


def _write_launcher(path: Path, lines: Iterable[str]) -> None:
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _create_launchers(install_dir: Path) -> None:
    _write_launcher(
        install_dir / "generate_words.bat",
        [
            "@echo off",
            "setlocal",
            "set \"ROOT_DIR=%~dp0\"",
            "\"%ROOT_DIR%venv\\Scripts\\python.exe\" -m kinetic_captions.cli %*",
            "set \"EXIT_CODE=%ERRORLEVEL%\"",
            "endlocal",
            "exit /b %EXIT_CODE%",
        ],
    )
    _write_launcher(
        install_dir / "install_whisper_model.bat",
        [
            "@echo off",
            "setlocal",
            "set \"ROOT_DIR=%~dp0\"",
            "\"%ROOT_DIR%venv\\Scripts\\python.exe\" -m kinetic_captions.model_manager %*",
            "set \"EXIT_CODE=%ERRORLEVEL%\"",
            "endlocal",
            "exit /b %EXIT_CODE%",
        ],
    )
    _write_launcher(
        install_dir / "run_resolve_pipeline.bat",
        [
            "@echo off",
            "setlocal",
            "set \"ROOT_DIR=%~dp0\"",
            "set \"PYTHONPATH=%ROOT_DIR%app;%ROOT_DIR%app\\src;%PYTHONPATH%\"",
            "\"%ROOT_DIR%venv\\Scripts\\python.exe\" \"%ROOT_DIR%app\\resolve\\auto_kinetic_captions.py\" %*",
            "set \"EXIT_CODE=%ERRORLEVEL%\"",
            "endlocal",
            "exit /b %EXIT_CODE%",
        ],
    )
    _write_launcher(
        install_dir / "Uninstall_Kinetic_Captions.bat",
        [
            "@echo off",
            "setlocal",
            "set \"ROOT_DIR=%~dp0\"",
            "\"%ROOT_DIR%venv\\Scripts\\python.exe\" \"%ROOT_DIR%app\\installer\\uninstall_wizard.py\" --install-dir \"%ROOT_DIR%\"",
            "set \"EXIT_CODE=%ERRORLEVEL%\"",
            "endlocal",
            "exit /b %EXIT_CODE%",
        ],
    )


def _resolve_support_root() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        raise RuntimeError("Missing APPDATA environment variable.")
    return (
        Path(appdata)
        / "Blackmagic Design"
        / "DaVinci Resolve"
        / "Support"
        / "Fusion"
    )


def _install_to_resolve(app_dir: Path) -> list[Path]:
    support_root = _resolve_support_root()
    title_src = app_dir / "fusion" / "Templates" / "Edit" / "Titles" / "Kinetic Captions.setting"
    runtime_src = app_dir / "fusion" / "Scripts" / "Comp" / "KineticCaptionsRuntime.lua"
    if not title_src.exists() or not runtime_src.exists():
        raise RuntimeError("Missing Fusion template/runtime files in package.")

    title_dst_dir = support_root / "Templates" / "Edit" / "Titles"
    runtime_dst_dir = support_root / "Scripts" / "Comp"
    title_dst_dir.mkdir(parents=True, exist_ok=True)
    runtime_dst_dir.mkdir(parents=True, exist_ok=True)

    title_dst = title_dst_dir / title_src.name
    runtime_dst = runtime_dst_dir / runtime_src.name
    shutil.copy2(title_src, title_dst)
    shutil.copy2(runtime_src, runtime_dst)
    return [title_dst, runtime_dst]


def _write_manifest(result: InstallResult) -> None:
    manifest_path = result.install_dir / MANIFEST_NAME
    payload = {
        "app_name": APP_NAME,
        "install_dir": str(result.install_dir),
        "app_dir": str(result.app_dir),
        "venv_python": str(result.venv_python),
        "model_dir": str(result.model_dir),
        "resolve_files": [str(path) for path in result.resolve_files],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _install_model_now(install_dir: Path) -> None:
    if not _prompt_yes_no("Install Whisper model 'small' now?", default=False):
        return
    cmd = [
        str(_venv_python(install_dir)),
        "-m",
        "kinetic_captions.model_manager",
        "--model",
        "small",
        "--models-dir",
        str(install_dir / "models"),
    ]
    _run(cmd)


def run_install(source_root: Path, install_dir: Path, install_resolve_now: bool) -> InstallResult:
    install_dir.mkdir(parents=True, exist_ok=True)
    app_dir = install_dir / "app"
    _copy_payload(source_root, app_dir)
    venv_python = _create_venv(install_dir)
    _install_runtime(venv_python, app_dir)
    _create_launchers(install_dir)

    resolve_files: list[Path] = []
    if install_resolve_now:
        resolve_files = _install_to_resolve(app_dir)
    return InstallResult(
        install_dir=install_dir,
        app_dir=app_dir,
        venv_python=venv_python,
        resolve_files=resolve_files,
        model_dir=install_dir / "models",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kinetic Captions interactive installer.")
    parser.add_argument(
        "--install-dir",
        default="",
        help="Optional installation directory (defaults to %%LOCALAPPDATA%%\\KineticCaptions).",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts using defaults.",
    )
    parser.add_argument(
        "--install-resolve",
        action="store_true",
        help="Install Fusion template/runtime into DaVinci Resolve support folders.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_root = Path(__file__).resolve().parents[1]
    default_dir = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "KineticCaptions"
    ).resolve()

    _print("========================================")
    _print(f"{APP_NAME} Installer")
    _print("========================================")
    _print(f"Package source: {source_root}")

    if args.install_dir:
        install_dir = Path(args.install_dir).expanduser().resolve()
    elif args.non_interactive:
        install_dir = default_dir
    else:
        install_dir = _prompt_path("Installation directory", default=default_dir)

    if args.non_interactive:
        install_resolve_now = bool(args.install_resolve)
    else:
        install_resolve_now = _prompt_yes_no(
            "Install template/runtime into DaVinci Resolve now?", default=True
        )

    result = run_install(source_root, install_dir, install_resolve_now)
    _write_manifest(result)

    _print("")
    _print("Installation completed.")
    _print(f"Install directory: {result.install_dir}")
    _print(f"Generator launcher: {result.install_dir / 'generate_words.bat'}")
    _print(f"Model installer: {result.install_dir / 'install_whisper_model.bat'}")
    _print(f"Resolve pipeline launcher: {result.install_dir / 'run_resolve_pipeline.bat'}")
    if result.resolve_files:
        _print("DaVinci files installed:")
        for path in result.resolve_files:
            _print(f"  - {path}")
        _print("Restart DaVinci Resolve to load the new title template.")
    else:
        _print("DaVinci template install was skipped.")

    if not args.non_interactive:
        _install_model_now(result.install_dir)

    _print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
