# QA checklist (MVP)

1. CZ audio 10-30s
- `generate_words` finishes without error.
- `words.json` has non-empty `words`.
- Start/end word timing is reasonable.

2. EN audio 10-30s
- `--lang auto` resolves correctly.

3. CZ/EN mixed audio
- Transcript stays coherent and time-aligned.

4. Long audio 10-30 min
- No crash, memory use stays stable.
- `words.json` validation still passes.

5. Silent sections
- No negative/invalid timestamps.
- VAD on/off behavior is deterministic.

6. Invalid input
- Missing input file: readable error.
- Invalid WAV: readable error.

7. JSON integrity
- `words` indices continuous (`i=0..N-1`).
- `s < e` for all words and segments.
- Monotonic word start times.

8. Fusion import
- `dist/KineticCaptions.drfx` imports in Resolve.
- Title appears in Edit page > Titles.
