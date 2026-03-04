# Kinetic Captions (DaVinci Resolve Studio, offline-first)

MVP repository for:
- `generate_words` CLI (offline word-level timestamps from WAV)
- `Kinetic Captions` Fusion Title template packaging (`.drfx`)

## Current status

- Implemented: offline `generate_words` with deterministic token normalization and `words.json` validation.
- Implemented: Windows one-click wrapper `generate_words.bat`.
- Implemented: `.drfx` packer script (`scripts/build_drfx.py`) and base Fusion Title template.
- TODO: full per-word reveal/highlight runtime logic inside Fusion Title (expression/Lua graph) in next iteration.

## Requirements

- Windows 10/11 (target runtime)
- DaVinci Resolve Studio (recommended 18.6+)
- Python 3.10+

## Installation (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## CLI usage

```bash
generate_words --input "D:\project\audio.wav" --lang auto --model small --device cpu --vad on --max_line_chars 32 --max_words_per_line 7 --transcript-out "D:\project\transcript.txt" --log "D:\project\generate_words.log"
```

Arguments:
- `--input <path.wav>` (required)
- `--output <path>` (optional, default: `<input_dir>/words.json`)
- `--lang auto|cs|en`
- `--model small|medium|large`
- `--device cpu|cuda` (CUDA auto-falls back to CPU if unavailable)
- `--vad on|off`
- `--vad_min_silence_ms <int>`
- `--max_line_chars <int>`
- `--max_words_per_line <int>`
- `--transcript-out <path>` (optional)
- `--log <path>` (optional)

## `words.json` schema

Generator writes:

```json
{
  "version": "1.0",
  "lang": "cs",
  "text": "Ahoj tohle je test.",
  "words": [
    {"i": 0, "w": "Ahoj", "s": 0.52, "e": 0.92},
    {"i": 1, "w": "tohle", "s": 0.95, "e": 1.2}
  ],
  "segments": [
    {"s": 0.5, "e": 2.1, "text": "Ahoj tohle je test."}
  ],
  "meta": {
    "engine": "faster-whisper",
    "model": "small",
    "created_utc": "2026-03-04T11:30:00+00:00",
    "audio": {"sr": 48000, "channels": 1},
    "device": "cpu",
    "requested_lang": "auto",
    "detected_lang": "cs",
    "notes": ""
  },
  "layout_hints": {
    "max_line_chars": 32,
    "max_words_per_line": 7
  }
}
```

Validation rules:
- `words` must be non-empty
- `i` must be continuous `0..N-1`
- each word must satisfy `s >= 0`, `e >= 0`, `s < e`
- word starts must be non-decreasing

## Windows one-click runner

Use root file:

```bat
generate_words.bat --input "C:\path\audio.wav" --lang auto --model small
```

## Build `.drfx`

```bash
python scripts/build_drfx.py
```

Output:
- `dist/KineticCaptions.drfx`

## Sample files

- `samples/sample_words.json` (schema reference)
- `samples/sample_transcript.txt`
- `samples/sample.wav` (48kHz mono tone for I/O pipeline checks; not speech)

## Tests

```bash
pytest
```

## QA checklist

See [`docs/QA_CHECKLIST.md`](docs/QA_CHECKLIST.md).
