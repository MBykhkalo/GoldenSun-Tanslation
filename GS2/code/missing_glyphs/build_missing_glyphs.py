#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUT = PROJECT_DIR / "output" / "missing_glyphs" / "missing_glyphs.json"

ROM = "output/temp/golden_sun_2_ukr.gba"
ROM_PATH = PROJECT_DIR / "output" / "temp" / "golden_sun_2_ukr.gba"

MAIN_FONT_OFFSET = 0x682430
MAIN_TILE_BYTES = 32
MAIN_BASE_CODE = 0x20

SECONDARY_YO_UPPER_OFFSET = 0x05B5E0
SECONDARY_YO_LOWER_OFFSET = 0x05B7E0
SECONDARY_TABLE_OFFSET = 0x05A580
SECONDARY_TABLE_BASE_CODE = 0x25
SECONDARY_CYRILLIC_OFFSET = 0x05B8C0
SECONDARY_CYRILLIC_BASE_CODE = 0xBF
SECONDARY_RECORD_BYTES = 32

UKRAINIAN_CHARS = [
    ("Ґ", 0xA5, "blank/raw GS1 placeholder tile", 0xC3, "Г", "redraw as Ukrainian Ghe with upturn"),
    ("ґ", 0xB4, "blank/raw GS1 placeholder tile", 0xE3, "г", "redraw as Ukrainian ghe with upturn"),
    ("Є", 0xAA, "blank/raw GS1 placeholder tile", 0xC5, "Е", "redraw as Ukrainian Ye"),
    ("є", 0xBA, "blank/raw GS1 placeholder tile", 0xE5, "е", "redraw as Ukrainian ye"),
    ("І", 0xB2, "blank/raw GS1 placeholder tile", 0x49, "I", "redraw as Ukrainian I if needed"),
    ("і", 0xB3, "blank/raw GS1 placeholder tile", 0x69, "i", "redraw as Ukrainian small i if needed"),
    ("Ї", 0xAF, "blank/raw GS1 placeholder tile", 0x49, "I", "redraw with diaeresis/dots"),
    ("ї", 0xBF, "@-like/raw GS1 placeholder tile", 0x69, "i", "redraw with diaeresis/dots"),
]


def hex6(value: int) -> str:
    return f"0x{value:06X}"


def ascii_preview(data: bytes, offset: int) -> list[str] | None:
    if offset < 0 or offset + SECONDARY_RECORD_BYTES > len(data):
        return None
    record = data[offset : offset + SECONDARY_RECORD_BYTES]
    rows = []
    for i in range(8):
        word = int.from_bytes(record[8 + i * 2 : 10 + i * 2], "little")
        line = "".join("#" if (word >> (15 - bit)) & 1 else "." for bit in range(16)).rstrip(".")
        rows.append(line or ".")
    return rows


def main_font_entry(char: str, code: int, current: str, source_code: int, source_char: str, note: str) -> dict:
    offset = MAIN_FONT_OFFSET + (code - MAIN_BASE_CODE) * MAIN_TILE_BYTES
    source_offset = MAIN_FONT_OFFSET + (source_code - MAIN_BASE_CODE) * MAIN_TILE_BYTES
    return {
        "char": char,
        "cp1251_code": f"0x{code:02X}",
        "rom_offset": hex6(offset),
        "tile_index_from_font_start": code - MAIN_BASE_CODE,
        "record_size_bytes": MAIN_TILE_BYTES,
        "current_default_mode_display": current,
        "if_ukrainian_placeholders_enabled_displays_as": source_char,
        "placeholder_graphics_source_code": f"0x{source_code:02X}",
        "placeholder_graphics_source_rom_offset": hex6(source_offset),
        "note": note,
    }


def secondary_entry(char: str, code: int, *_: object) -> dict:
    offset = SECONDARY_TABLE_OFFSET + (code - SECONDARY_TABLE_BASE_CODE) * SECONDARY_RECORD_BYTES
    preview = ascii_preview(ROM_PATH.read_bytes(), offset) if ROM_PATH.exists() else None
    copied_from_gs1 = code in (0xA8, 0xB8) or code >= SECONDARY_CYRILLIC_BASE_CODE
    entry = {
        "char": char,
        "cp1251_code": f"0x{code:02X}",
        "renderer": "menu/save-screen secondary font records",
        "rom_offset": hex6(offset),
        "address_formula": "rom_offset = 0x05A580 + (cp1251_code - 0x25) * 32",
        "record_size_bytes": SECONDARY_RECORD_BYTES,
        "stage4_placeholder_toggle_effect": "none; the current toggle only copies placeholders in the main 4bpp font table",
        "patched_by_stage4": copied_from_gs1,
        "slot_source": (
            "bundled Cyrillic secondary record/range"
            if copied_from_gs1
            else "clean GS2 original secondary slot; Stage 4 does not currently replace this Ukrainian-specific byte"
        ),
        "current_default_mode_display": (
            "raw bundled Cyrillic secondary glyph for this byte; not a proper Ukrainian glyph"
            if copied_from_gs1
            else "raw clean-GS2 secondary glyph/blank slot for this byte; not a Ukrainian glyph"
        ),
        "ascii_preview_from_current_output_rom": preview,
        "yy_chr_note": "Not standard GBA 4bpp tile data. Edit with a custom renderer/hex workflow, not normal YY-CHR tile mode.",
    }
    entry["record_index_from_0x25"] = code - SECONDARY_TABLE_BASE_CODE
    return entry


payload = {
    "rom": ROM,
    "stage4_default": "Ukrainian placeholder glyph substitutions disabled; font stays on bundled Cyrillic CP1251 resources.",
    "categories": {
        "main_dialog_font_table": {
            "description": "Main GS2 dialogue/name font table patched from bundled Cyrillic font_tiles_cyrillic.bin.",
            "font_table_offset": hex6(MAIN_FONT_OFFSET),
            "font_format": "GBA 4bpp linear tiles, 8x8, 32 bytes per glyph tile",
            "compressed": False,
            "can_edit_directly_in_yy_chr": True,
            "yy_chr_settings": {
                "format": "4BPP GBA / GBA 4bpp linear",
                "tile_size": "8x8",
                "palette_note": "Use any high-contrast 4bpp palette while editing; final in-game colors come from the game palette.",
            },
            "address_formula": "rom_offset = 0x682430 + (cp1251_code - 0x20) * 32",
            "missing_or_placeholder_glyphs": [
                main_font_entry(*item) for item in UKRAINIAN_CHARS
            ],
        },
        "secondary_menu_save_font_table": {
            "description": "Secondary menu/save-screen font records. This was the separate table that caused menu text to differ from the original missing-glyph report.",
            "font_format": "renderer-specific width/header plus 1bpp-ish row records; not standard GBA 4bpp tiles",
            "compressed": False,
            "can_edit_directly_in_yy_chr": False,
            "address_formula": "rom_offset = 0x05A580 + (cp1251_code - 0x25) * 32",
            "full_table_range": {
                "char_range": "0x25..0xFF",
                "rom_offset": hex6(SECONDARY_TABLE_OFFSET),
                "rom_end_offset": hex6(0x05C0DC),
                "record_size_bytes": "32 bytes per record, except 0xFF is 28 bytes",
            },
            "stage4_copied_cyrillic_records": "0xA8, 0xB8, and 0xBF..0xFF; other Ukrainian-specific slots remain clean GS2 data unless edited manually.",
            "known_records": [
                {
                    "char": "Ё",
                    "cp1251_code": "0xA8",
                    "rom_offset": hex6(SECONDARY_YO_UPPER_OFFSET),
                    "record_size_bytes": 24,
                },
                {
                    "char": "ё",
                    "cp1251_code": "0xB8",
                    "rom_offset": hex6(SECONDARY_YO_LOWER_OFFSET),
                    "record_size_bytes": 30,
                },
                {
                    "char_range": "0xBF..0xFF",
                    "rom_offset": hex6(SECONDARY_CYRILLIC_OFFSET),
                    "rom_end_offset": hex6(0x05C0DC),
                    "record_size_bytes": "32 bytes per record, except 0xFF is 28 bytes",
                    "address_formula": "rom_offset = 0x05B8C0 + (cp1251_code - 0xBF) * 32 for 0xBF..0xFF",
                },
            ],
            "missing_or_placeholder_glyphs": [
                secondary_entry(*item) for item in UKRAINIAN_CHARS
            ],
        },
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {OUT}")
