from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def _run(cmd: list[str], cwd: Path) -> None:
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree_clean(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.log",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
    )
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def package_release(root: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure fresh DRFX.
    _run([sys.executable, "scripts/build_drfx.py"], cwd=root)

    release_root = output_dir / "KineticCaptionsRelease"
    if release_root.exists():
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        root / "dist/KineticCaptions.drfx",
        root / "Install_Kinetic_Captions.bat",
        root / "Uninstall_Kinetic_Captions.bat",
        root / "generate_words.bat",
        root / "install_whisper_model.bat",
        root / "run_resolve_pipeline.bat",
        root / "README.md",
        root / "pyproject.toml",
        root / "samples/sample.wav",
        root / "samples/sample_words.json",
    ]
    for src in files_to_copy:
        rel = src.relative_to(root)
        _copy_file(src, release_root / rel)

    # Copy source scripts for environments without pip install.
    _copy_tree_clean(root / "src", release_root / "src")
    _copy_tree_clean(root / "resolve", release_root / "resolve")
    _copy_tree_clean(root / "docs", release_root / "docs")
    _copy_tree_clean(root / "fusion", release_root / "fusion")
    _copy_tree_clean(root / "scripts", release_root / "scripts")
    _copy_tree_clean(root / "installer", release_root / "installer")

    return release_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Windows offline release folder.")
    parser.add_argument(
        "--output-dir",
        default="dist/release",
        help="Target directory where release folder is created.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output_dir).expanduser().resolve()
    release_root = package_release(root, out)
    print(f"Release folder: {release_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
