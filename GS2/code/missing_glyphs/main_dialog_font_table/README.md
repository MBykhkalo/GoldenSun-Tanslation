# Main dialogue font table scripts

This table is already YY-CHR-friendly: uncompressed GBA 4bpp linear 8x8 tiles.

Extract:

```bash
python3 code/missing_glyphs/main_dialog_font_table/extract_main_font.py
```

Open `output/missing_glyphs/main_dialog_font_table/main_dialog_font_4bpp.bin` in YY-CHR with `4BPP GBA`.

Edit spacing in `output/missing_glyphs/main_dialog_font_table/main_dialog_font_4bpp.json` by changing each glyph's `width_pixels`. The injector writes those values to the GS2 VWF width table at `0x05F484`.

Inject into a new ROM copy:

```bash
python3 code/missing_glyphs/main_dialog_font_table/inject_main_font.py
```

The injector verifies that the patched ROM contains exactly the edited font bytes and JSON width values.
