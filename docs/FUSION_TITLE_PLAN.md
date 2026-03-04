# Fusion Title implementation plan

This repository currently ships a base template:
- `fusion/Templates/Edit/Titles/Kinetic Captions.setting`

It already exposes inspector pages and key controls:
- Data
- Timing
- Layout
- Style
- Highlight
- Animation
- Presets
- Advanced

Next iteration tasks:
1. Add JSON load/cache logic (File + optional Inline mode).
2. Implement timeline `t = (time - clip_start) + offset`.
3. Implement `Mode`: Reveal / Highlight / Reveal+Highlight.
4. Implement rolling window (`Window Words`, `Trailing` first).
5. Connect style/highlight controls to Text+ and highlight layer.
6. Add error placeholders for missing/invalid JSON.
7. Optimize parsing so JSON is not reloaded every frame.
