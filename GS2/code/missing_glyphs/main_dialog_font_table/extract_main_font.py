#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ROM = PROJECT_DIR / "output" / "temp" / "golden_sun_2_ukr.gba"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "missing_glyphs" / "main_dialog_font_table"
DEFAULT_OUT = DEFAULT_OUTPUT_DIR / "main_dialog_font_4bpp.bin"
DEFAULT_META = DEFAULT_OUTPUT_DIR / "main_dialog_font_4bpp.json"

FONT_OFFSET = 0x682430
WIDTH_TABLE_OFFSET = 0x05F484
BASE_CODE = 0x20
TILE_COUNT = 224
TILE_BYTES = 32
FONT_BYTES = TILE_COUNT * TILE_BYTES


def cp1251_char(code: int) -> str:
    try:
        return bytes([code]).decode("cp1251")
    except UnicodeDecodeError:
        return f"<0x{code:02X}>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the main GS2 dialogue font table as a YY-CHR-friendly GBA 4bpp .bin."
    )
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help=f"ROM to read, default: {DEFAULT_ROM}")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output .bin, default: {DEFAULT_OUT}")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META, help=f"Output metadata JSON, default: {DEFAULT_META}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rom = args.rom.read_bytes()
    end = FONT_OFFSET + FONT_BYTES
    if len(rom) < end:
        raise ValueError(f"{args.rom} is too small for main font table at 0x{FONT_OFFSET:06X}")
    width_end = WIDTH_TABLE_OFFSET + TILE_COUNT
    if len(rom) < width_end:
        raise ValueError(f"{args.rom} is too small for main width table at 0x{WIDTH_TABLE_OFFSET:06X}")

    font = rom[FONT_OFFSET:end]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(font)

    glyphs = []
    for index, code in enumerate(range(BASE_CODE, 0x100)):
        glyphs.append(
            {
                "code": f"0x{code:02X}",
                "char_cp1251": cp1251_char(code),
                "tile_index": index,
                "bin_offset": f"0x{index * TILE_BYTES:04X}",
                "rom_offset": f"0x{FONT_OFFSET + index * TILE_BYTES:06X}",
                "width_pixels": rom[WIDTH_TABLE_OFFSET + index],
                "width_table_offset": f"0x{WIDTH_TABLE_OFFSET + index:06X}",
            }
        )

    metadata = {
        "source_rom": str(args.rom),
        "font_table_offset": f"0x{FONT_OFFSET:06X}",
        "width_table_offset": f"0x{WIDTH_TABLE_OFFSET:06X}",
        "format": "GBA 4bpp linear, 8x8, 32 bytes per glyph; open directly in YY-CHR as 4BPP GBA",
        "width_note": "Edit glyphs[*].width_pixels, then run inject_main_font.py. Values are written to the GS2 VWF width table.",
        "base_code": f"0x{BASE_CODE:02X}",
        "tile_count": TILE_COUNT,
        "tile_bytes": TILE_BYTES,
        "font_bin": str(args.out),
        "glyphs": glyphs,
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.out.read_bytes() != font:
        raise RuntimeError("extraction verification failed: written .bin does not match ROM bytes")
    print(f"Extracted {FONT_BYTES} bytes from 0x{FONT_OFFSET:06X} to {args.out}")
    print(f"Wrote metadata to {args.metadata}")


if __name__ == "__main__":
    main()
