from __future__ import annotations

from pathlib import Path
import zipfile


def build_drfx() -> Path:
    root = Path(__file__).resolve().parents[1]
    fusion_root = root / "fusion"
    if not fusion_root.exists():
        raise FileNotFoundError(f"Missing fusion source folder: {fusion_root}")

    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_path = dist_dir / "KineticCaptions.drfx"

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(fusion_root.rglob("*")):
            if not file_path.is_file():
                continue
            archive_name = file_path.relative_to(fusion_root).as_posix()
            archive.write(file_path, arcname=archive_name)
    return out_path


def main() -> int:
    out_path = build_drfx()
    print(f"Built: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
