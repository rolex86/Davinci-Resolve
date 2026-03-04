# Distribution guide (client-ready package)

## Goal

Deliver package so recipient performs only:
1. extract package
2. double click installer
3. restart DaVinci Resolve

No manual venv / pip / PowerShell workflow required from end user.

## Build package

```bash
python scripts/build_windows_bundle.py --output-dir dist/distribution
```

Artifacts:
- `dist/distribution/release/KineticCaptionsRelease/`
- `dist/distribution/KineticCaptions_Windows_Package.zip`

## Recipient flow

1. Extract `KineticCaptions_Windows_Package.zip`
2. Run `Install_Kinetic_Captions.bat`
3. Installer creates runtime in `%LOCALAPPDATA%\\KineticCaptions`
4. Installer asks whether to install into DaVinci now
5. Restart DaVinci and use title `Kinetic Captions` from Edit -> Titles

If Python is missing, installer can offer automatic install using `winget`.

Recipient can then generate `words.json` from:
- audio (`--input`)
- subtitles (`--subtitle` for `.srt` / `.ass`)
- manual text (`--manual-text` or `--manual-text-file`)

## What installer does

- copies app payload into local install directory
- creates Python virtual environment
- installs dependencies + package
- creates launcher scripts in install dir:
  - `generate_words.bat`
  - `install_whisper_model.bat`
  - `run_resolve_pipeline.bat`
- optionally installs Fusion template/runtime to:
  - `%APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Templates\\Edit\\Titles`
  - `%APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Comp`
- writes install manifest for uninstaller

## Single EXE option

Use Inno Setup script:
- `installer/inno/KineticCaptionsSetup.iss`

Compile with:
```bash
ISCC installer\\inno\\KineticCaptionsSetup.iss
```

This creates a single setup executable containing the full package.
