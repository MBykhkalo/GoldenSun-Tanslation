#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUT = PROJECT_DIR / "output" / "missing_glyphs" / "missing_glyphs.json"

ROM = "output/temp/golden_sun_1_ukr.gba"
ROM_PATH = PROJECT_DIR / "output" / "temp" / "golden_sun_1_ukr.gba"

MAIN_FONT_OFFSET = 0x3213D0
MAIN_TILE_BYTES = 32
MAIN_BASE_CODE = 0x20

SECONDARY_TABLE_OFFSET = 0x0322C4
SECONDARY_TABLE_BASE_CODE = 0x25
SECONDARY_RECORD_BYTES = 32
SECONDARY_LAST_RECORD_BYTES = 28
SECONDARY_ROW_OFFSET = 4

UKRAINIAN_CHARS = [
    ("Ґ", 0xA5, "Cyrillic cp1251 slot; verify/redraw as Ukrainian Ghe with upturn", 0xC3, "Г"),
    ("ґ", 0xB4, "Cyrillic cp1251 slot; verify/redraw as Ukrainian ghe with upturn", 0xE3, "г"),
    ("Є", 0xAA, "Cyrillic cp1251 slot; verify/redraw as Ukrainian Ye", 0xC5, "Е"),
    ("є", 0xBA, "Cyrillic cp1251 slot; verify/redraw as Ukrainian ye", 0xE5, "е"),
    ("І", 0xB2, "Cyrillic cp1251 slot; verify/redraw as Ukrainian I", 0x49, "I"),
    ("і", 0xB3, "Cyrillic cp1251 slot; verify/redraw as Ukrainian small i", 0x69, "i"),
    ("Ї", 0xAF, "Cyrillic cp1251 slot; redraw with diaeresis/dots", 0x49, "I"),
    ("ї", 0xBF, "Cyrillic cp1251 slot; redraw with diaeresis/dots", 0x69, "i"),
]


def hex6(value: int) -> str:
    return f"0x{value:06X}"


def secondary_record_size(code: int) -> int:
    return SECONDARY_LAST_RECORD_BYTES if code == 0xFF else SECONDARY_RECORD_BYTES


def ascii_preview(data: bytes, offset: int, size: int) -> list[str] | None:
    if offset < 0 or offset + size > len(data):
        return None
    record = data[offset : offset + size]
    rows = []
    row_count = min(16, max(0, (len(record) - SECONDARY_ROW_OFFSET) // 2))
    for i in range(row_count):
        word = int.from_bytes(record[SECONDARY_ROW_OFFSET + i * 2 : SECONDARY_ROW_OFFSET + i * 2 + 2], "little")
        line = "".join("#" if (word >> (15 - bit)) & 1 else "." for bit in range(16)).rstrip(".")
        rows.append(line or ".")
    return rows


def main_font_entry(char: str, code: int, note: str, source_code: int, source_char: str) -> dict:
    offset = MAIN_FONT_OFFSET + (code - MAIN_BASE_CODE) * MAIN_TILE_BYTES
    source_offset = MAIN_FONT_OFFSET + (source_code - MAIN_BASE_CODE) * MAIN_TILE_BYTES
    return {
        "char": char,
        "cp1251_code": f"0x{code:02X}",
        "rom_offset": hex6(offset),
        "tile_index_from_font_start": code - MAIN_BASE_CODE,
        "record_size_bytes": MAIN_TILE_BYTES,
        "current_default_mode_display": note,
        "suggested_reference_source_code": f"0x{source_code:02X}",
        "suggested_reference_source_char": source_char,
        "suggested_reference_source_rom_offset": hex6(source_offset),
    }


def secondary_entry(char: str, code: int, *_: object) -> dict:
    offset = SECONDARY_TABLE_OFFSET + (code - SECONDARY_TABLE_BASE_CODE) * SECONDARY_RECORD_BYTES
    size = secondary_record_size(code)
    preview = ascii_preview(ROM_PATH.read_bytes(), offset, size) if ROM_PATH.exists() else None
    return {
        "char": char,
        "cp1251_code": f"0x{code:02X}",
        "renderer": "menu/save-screen secondary font records",
        "rom_offset": hex6(offset),
        "address_formula": "rom_offset = 0x0322C4 + (cp1251_code - 0x25) * 32",
        "record_index_from_0x25": code - SECONDARY_TABLE_BASE_CODE,
        "record_size_bytes": size,
        "current_default_mode_display": "Cyrillic secondary glyph; verify/redraw for Ukrainian",
        "ascii_preview_from_current_output_rom": preview,
        "yy_chr_note": "Not standard GBA 4bpp tile data. Use extract_secondary_font.py for a YY-CHR-friendly conversion.",
    }


payload = {
    "rom": ROM,
    "categories": {
        "main_dialog_font_table": {
            "description": "Main GS1 dialogue/name font table.",
            "font_table_offset": hex6(MAIN_FONT_OFFSET),
            "font_format": "GBA 4bpp linear tiles, 8x8, 32 bytes per glyph tile",
            "compressed": False,
            "can_edit_directly_in_yy_chr": True,
            "yy_chr_settings": {
                "format": "4BPP GBA / GBA 4bpp linear",
                "tile_size": "8x8",
                "palette_note": "Use any high-contrast 4bpp palette while editing; final in-game colors come from the game palette.",
            },
            "address_formula": "rom_offset = 0x3213D0 + (cp1251_code - 0x20) * 32",
            "missing_or_placeholder_glyphs": [
                main_font_entry(*item) for item in UKRAINIAN_CHARS
            ],
        },
        "secondary_menu_save_font_table": {
            "description": "Secondary menu/save-screen font records.",
            "font_format": "renderer-specific width/header plus 1bpp-ish row records; not standard GBA 4bpp tiles",
            "compressed": False,
            "can_edit_directly_in_yy_chr": False,
            "address_formula": "rom_offset = 0x0322C4 + (cp1251_code - 0x25) * 32",
            "full_table_range": {
                "char_range": "0x25..0xFF",
                "rom_offset": hex6(SECONDARY_TABLE_OFFSET),
                "rom_end_offset": hex6(0x033E20),
                "record_size_bytes": "32 bytes per record, except 0xFF is 28 bytes",
            },
            "known_changed_records_from_gs1_cyrillic_font": [
                {
                    "char": "Ё",
                    "cp1251_code": "0xA8",
                    "rom_offset": hex6(0x033324),
                },
                {
                    "char": "ё",
                    "cp1251_code": "0xB8",
                    "rom_offset": hex6(0x033524),
                },
                {
                    "char_range": "0xBF..0xFF",
                    "rom_offset": hex6(0x033604),
                    "rom_end_offset": hex6(0x033E20),
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
