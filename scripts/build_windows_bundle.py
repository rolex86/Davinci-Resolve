from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile

from package_release import package_release


def build_windows_bundle(root: Path, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    release_root = package_release(root, output_dir / "release")

    zip_path = output_dir / "KineticCaptions_Windows_Package.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(release_root.rglob("*")):
            if not file_path.is_file():
                continue
            archive_name = file_path.relative_to(release_root).as_posix()
            archive.write(file_path, archive_name)
    return release_root, zip_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build distributable Windows package (release folder + zip)."
    )
    parser.add_argument(
        "--output-dir",
        default="dist/distribution",
        help="Target output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir).expanduser().resolve()
    release_root, zip_path = build_windows_bundle(root, output_dir)
    print(f"Release folder: {release_root}")
    print(f"Zip package: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
