# Secondary menu/save-screen font table scripts

This table is uncompressed, but it is **not** standard YY-CHR tile data in the ROM. The extractor converts each secondary record into a YY-CHR-friendly 16x16 glyph made of four GBA 4bpp 8x8 tiles.

Extract:

```bash
python3 code/missing_glyphs/secondary_menu_save_font_table/extract_secondary_font.py
```

Open `output/missing_glyphs/secondary_menu_save_font_table/secondary_menu_font_4bpp_16x16.bin` in YY-CHR with `4BPP GBA`. Each code from `0x25` through `0xFF` is four consecutive tiles. The first glyph starts at ROM offset `0x05A580`; `0xA5` is later in the same table at `0x05B580`.

1. top-left
2. top-right
3. bottom-left
4. bottom-right

Edit spacing in `output/missing_glyphs/secondary_menu_save_font_table/secondary_menu_font_4bpp_16x16.json` by changing each glyph's `width_pixels`. The injector writes those values to byte `0` of each secondary font record.

Inject into a new ROM copy:

```bash
python3 code/missing_glyphs/secondary_menu_save_font_table/inject_secondary_font.py
```

The injector converts non-zero YY-CHR pixels back to the game's secondary row-record format, writes a new ROM copy, then verifies both the converted glyph pixels and JSON width values.
