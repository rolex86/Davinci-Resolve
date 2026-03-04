from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


MANIFEST_NAME = "install_manifest.json"


def _print(msg: str) -> None:
    print(msg, flush=True)


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False


def _delete_file_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _load_manifest(install_dir: Path) -> dict:
    manifest_path = install_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _remove_resolve_files(manifest: dict) -> None:
    for item in manifest.get("resolve_files", []):
        path = Path(str(item))
        try:
            _delete_file_if_exists(path)
            _print(f"Removed: {path}")
        except Exception as exc:
            _print(f"Warning: could not remove {path}: {exc}")


def _remove_install_dir(install_dir: Path) -> None:
    if not install_dir.exists():
        return

    temp_self_delete = install_dir / "_cleanup_self_delete.bat"
    temp_self_delete.write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                "ping 127.0.0.1 -n 3 > nul",
                f'rmdir /s /q "{install_dir}"',
                'del "%~f0"',
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    os.startfile(str(temp_self_delete))  # type: ignore[attr-defined]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Uninstall Kinetic Captions.")
    parser.add_argument(
        "--install-dir",
        default="",
        help="Installation directory. Default is current script parent.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask for confirmation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    install_dir = (
        Path(args.install_dir).expanduser().resolve()
        if args.install_dir
        else script_dir.parent
    )

    _print("========================================")
    _print("Kinetic Captions Uninstaller")
    _print("========================================")
    _print(f"Install directory: {install_dir}")

    if not args.yes and not _prompt_yes_no("Proceed with uninstall?", default=False):
        _print("Uninstall canceled.")
        return 0

    manifest = _load_manifest(install_dir)
    if manifest:
        if args.yes or _prompt_yes_no("Also remove DaVinci installed template files?", default=True):
            _remove_resolve_files(manifest)

    _print("Removing installation directory...")
    _remove_install_dir(install_dir)
    _print("Uninstall scheduled. This window can be closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
