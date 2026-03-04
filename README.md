# Kinetic Captions for DaVinci Resolve Studio (Windows, offline-first)

Complete project scaffold for offline kinetic captions:
- `generate_words` (offline transcription + word-level timing + JSON validation)
- Fusion Title template `Kinetic Captions` packaged as `.drfx`
- Resolve automation script (V2) for timeline audio export, generation, and title insertion

## Implemented feature map

### Core generator
- Offline transcription (CZ/EN + auto language detect)
- Word-level timestamps
- CLI `generate_words`
- Language select: `auto|cs|en`
- Model select: `small|medium|large`
- Device select: `cpu|cuda` (with CUDA fallback)
- VAD on/off + parameters (`vad_min_silence_ms`, `vad_speech_pad_ms`)
- Layout hints export (`max_line_chars`, `max_words_per_line`)
- `words.json` output
- optional `transcript.txt`
- optional log file
- pre-save JSON validation
- deterministic token normalization
- segment support (`segments`)

### Model management
- Offline-friendly model installer CLI: `install_whisper_model`
- Windows wrapper: `install_whisper_model.bat`
- Supports local-cache-only mode (`--offline-only`)

### Fusion Title (`.drfx`)
- Title name: `Kinetic Captions`
- Data source mode: File + Inline JSON fallback
- Missing file / invalid JSON placeholders
- Runtime caching + periodic source probing (no full parse each frame)
- Timeline sync + timing offset
- Modes: Reveal / Highlight / Reveal+Highlight
- Reveal definition: `s <= t`
- Highlight definition: `s <= t < e` with fallback
- Lead/Lag tolerance controls
- Layout controls: width, lines, alignment, XY, safe margins
- Rolling window: on/off + window words + trailing + centered
- Style controls: font/size/tracking/line spacing/color/opacity
- Outline controls: on/off, color, width
- Shadow controls: on/off, color, blur, offsets
- Highlight controls: color/pop/pill + combo controls
- Animation controls: word animation enum + duration/ease + global fade in/out
- Presets: Reels Pop / Clean Film / Minimal / Custom
- Advanced: precise highlight toggle (V2), debug toggle

### V2 modules
- Speaker diarization (optional): `--diarization on` (requires `pyannote.audio` extra)
- Resolve automation script for:
  - automatic timeline audio export
  - automatic `generate_words` run
  - automatic insertion of title clips (best-effort via Resolve API)

## Repository structure

- `src/kinetic_captions/` - generator + caption engine
- `fusion/Templates/Edit/Titles/Kinetic Captions.setting` - Fusion Title template
- `fusion/Scripts/Comp/KineticCaptionsRuntime.lua` - runtime logic used by title expressions
- `resolve/auto_kinetic_captions.py` - Resolve automation (V2)
- `scripts/build_drfx.py` - `.drfx` builder
- `scripts/package_release.py` - release folder packer

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional diarization extras:

```bash
pip install -e ".[diarization]"
```

Windows one-click wrappers:
- `generate_words.bat`
- `install_whisper_model.bat`
- `run_resolve_pipeline.bat`

## Install Whisper models (offline-friendly)

```bash
install_whisper_model --model small --models-dir ./models
```

Cache-only mode:

```bash
install_whisper_model --model small --models-dir ./models --offline-only
```

## Generate `words.json`

```bash
generate_words \
  --input "D:\project\audio.wav" \
  --output "D:\project\words.json" \
  --lang auto \
  --model small \
  --device cpu \
  --models-dir "D:\project\models" \
  --vad on \
  --vad_min_silence_ms 500 \
  --vad_speech_pad_ms 80 \
  --max_line_chars 32 \
  --max_words_per_line 7 \
  --transcript-out "D:\project\transcript.txt" \
  --log "D:\project\generate_words.log"
```

Optional diarization:

```bash
generate_words --input audio.wav --diarization on --diarization-model pyannote/speaker-diarization-3.1
```

## Build and install Fusion Title

Build:

```bash
python scripts/build_drfx.py
```

Result:
- `dist/KineticCaptions.drfx`

Install by double click in Resolve, then use title:
- Edit page -> Titles -> `Kinetic Captions`

## Resolve automation pipeline (V2)

Run from Resolve script environment:

```bash
python resolve/auto_kinetic_captions.py \
  --output-dir ./out \
  --title-name "Kinetic Captions" \
  --title-track 3 \
  --lang auto --model small --device cpu \
  --generator-cmd "generate_words"
```

Pipeline will:
1. Export current timeline audio to WAV
2. Generate `words.json`
3. Insert title clips based on `segments`
4. Attempt to bind `DataSource` to generated JSON

## Build release folder

```bash
python scripts/package_release.py --output-dir dist/release
```

## Samples

- `samples/sample.wav` (48kHz mono tone for I/O pipeline checks)
- `samples/sample_words.json`
- `samples/sample_transcript.txt`

## QA and planning docs

- `docs/QA_CHECKLIST.md`
- `docs/FUSION_TITLE_PLAN.md`
