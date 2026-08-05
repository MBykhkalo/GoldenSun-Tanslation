# GS2 Code

This folder contains all scripts and bundled compiler resources.

Entry point:

```bash
python3 code/main.py
```

Code folders:

- `compiler/` — builds intermediate ROMs/reports in `output/temp/`.
- `verifier/` — verifies the rebuilt plaintext table and dumps decoded strings.
- `missing_glyphs/` — extracts/injects editable main and secondary font graphics.
- `json_tools/` — splits and merges `output/ukrainian_translation.json`.
- `common/` — shared ROM/string/patch helper modules.
- `resources/` — bundled GS2 baseline, Cyrillic fonts, and secondary metric blocks used by the compiler.

The project root intentionally has only three top-level folders:

- `input/`
- `output/`
- `code/`
