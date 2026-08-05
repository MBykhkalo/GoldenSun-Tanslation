# GS1 Code

This folder contains all scripts and Python modules.

Entry point:

```bash
python3 code/main.py
```

Code folders:

- `compiler/` — builds intermediate ROMs/reports in `output/temp/`.
- `verifier/` — verifies the rebuilt plaintext table and dumps decoded strings.
- `missing_glyphs/` — extracts/injects editable main and secondary font graphics.
- `json_tools/` — splits and merges `output/ukrainian_translation.json`.
- `extraction/` — helper for generating the translation template.
- `common/` — shared ROM/string/patch helper modules.
- `resources/` — bundled GS1 baseline, Cyrillic fonts, and reference data used by the compiler.

The project root intentionally has only three top-level folders:

- `input/`
- `output/`
- `code/`
