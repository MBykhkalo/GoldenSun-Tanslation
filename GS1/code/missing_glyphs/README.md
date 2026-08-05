# Missing Ukrainian glyph graphics

This folder mirrors the GS2 `missing_glyphs` workflow for GS1. It lists and
extracts Ukrainian characters whose **byte encoding is correct CP1251**, but
whose graphics should be checked or redrawn for the Ukrainian localization.

Target ROM:

`output/temp/golden_sun_1_ukr.gba`

## Category 1: main dialogue font table

Main font table starts at ROM offset `0x3213D0`. Each glyph is one 8x8 tile,
32 bytes, standard **GBA 4bpp linear** format. The graphics are **not
compressed**, so you can edit them directly in YY-CHR.

YY-CHR settings:

1. Open `output/temp/golden_sun_1_ukr.gba`.
2. Go to the listed ROM offset.
3. Use `4BPP GBA` / `GBA 4bpp linear` mode.
4. Each glyph offset is calculated as `0x3213D0 + (CP1251_CODE - 0x20) * 32`.

## Category 2: secondary menu/save-screen font records

The secondary menu/save font is also **not compressed**, but it is **not
standard GBA 4bpp tile data**. It is a renderer-specific width/header plus
row-record format, so YY-CHR will not show it as normal tiles directly.

Secondary slots use this address formula:

```text
rom_offset = 0x0322C4 + (CP1251_CODE - 0x25) * 32
```

The full extracted range is `0x25..0xFF`. Code `0xFF` is 28 bytes; all other
records are 32 bytes.

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

Edit `output/missing_glyphs/main_dialog_font_table/main_dialog_font_4bpp.json` to change
per-character `width_pixels`; injection writes those values to the main width
table.

Secondary menu/save-screen font:

```bash
python3 code/missing_glyphs/secondary_menu_save_font_table/extract_secondary_font.py
python3 code/missing_glyphs/secondary_menu_save_font_table/inject_secondary_font.py
```

Edit `output/missing_glyphs/secondary_menu_save_font_table/secondary_menu_font_4bpp_16x16.json`
to change per-character `width_pixels`; injection writes those values to each
secondary record's width byte.
