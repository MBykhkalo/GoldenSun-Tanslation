# Missing Ukrainian glyph graphics

This folder mirrors the GS1 `missing_glyphs` workflow for GS2. It lists and
extracts Ukrainian characters whose byte encoding is correct CP1251, but whose
graphics should be checked or redrawn for the Ukrainian localization.

Target ROM:

`output/temp/golden_sun_2_ukr.gba`

## Regenerate report

```bash
python3 code/missing_glyphs/build_missing_glyphs.py
```

## Editing scripts

Main dialogue font:

```bash
python3 code/missing_glyphs/main_dialog_font_table/extract_main_font.py
python3 code/missing_glyphs/main_dialog_font_table/inject_main_font.py
```

Edit `output/missing_glyphs/main_dialog_font_table/main_dialog_font_4bpp.json`
to change per-character `width_pixels`; injection writes those values to the
main width table.

Secondary menu/save-screen font:

```bash
python3 code/missing_glyphs/secondary_menu_save_font_table/extract_secondary_font.py
python3 code/missing_glyphs/secondary_menu_save_font_table/inject_secondary_font.py
```

Edit `output/missing_glyphs/secondary_menu_save_font_table/secondary_menu_font_4bpp_16x16.json`
to change per-character `width_pixels`; injection writes those values to each
secondary record's width byte.
