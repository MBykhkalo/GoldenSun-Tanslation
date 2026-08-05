#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ROM = PROJECT_DIR / "output" / "temp" / "golden_sun_2_ukr.gba"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "missing_glyphs" / "secondary_menu_save_font_table"
DEFAULT_OUT = DEFAULT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.bin"
DEFAULT_META = DEFAULT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.json"

FIRST_CODE = 0x25
LAST_CODE = 0xFF
FORMULA_BASE_OFFSET = 0x05A580
FORMULA_BASE_CODE = 0x25
SLOT_BYTES = 32
LAST_SLOT_BYTES = 28
ROW_OFFSET = 4
WIDTH = 16
HEIGHT = 16
TILE_BYTES = 32
TILES_PER_GLYPH = 4
GLYPH_BYTES = TILE_BYTES * TILES_PER_GLYPH


def record_offset(code: int) -> int:
    return FORMULA_BASE_OFFSET + (code - FORMULA_BASE_CODE) * SLOT_BYTES


def record_size(code: int) -> int:
    return LAST_SLOT_BYTES if code == LAST_CODE else SLOT_BYTES


def cp1251_char(code: int) -> str:
    try:
        return bytes([code]).decode("cp1251")
    except UnicodeDecodeError:
        return f"<0x{code:02X}>"


def encode_tile(bitmap: list[list[int]], tile_x: int, tile_y: int) -> bytes:
    out = bytearray(TILE_BYTES)
    for y in range(8):
        for x_pair in range(4):
            x0 = tile_x * 8 + x_pair * 2
            x1 = x0 + 1
            y0 = tile_y * 8 + y
            lo = 1 if bitmap[y0][x0] else 0
            hi = 1 if bitmap[y0][x1] else 0
            out[y * 4 + x_pair] = lo | (hi << 4)
    return bytes(out)


def record_to_4bpp(record: bytes) -> bytes:
    padded = record + b"\x00" * (SLOT_BYTES - len(record))
    bitmap = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
    row_count = min(HEIGHT, max(0, (len(record) - ROW_OFFSET) // 2))
    for y in range(row_count):
        word = int.from_bytes(padded[ROW_OFFSET + y * 2 : ROW_OFFSET + y * 2 + 2], "little")
        for x in range(WIDTH):
            bitmap[y][x] = 1 if (word >> (15 - x)) & 1 else 0
    return b"".join(
        [
            encode_tile(bitmap, 0, 0),
            encode_tile(bitmap, 1, 0),
            encode_tile(bitmap, 0, 1),
            encode_tile(bitmap, 1, 1),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the secondary menu/save font records as a YY-CHR-friendly 4bpp .bin. "
            "Each code from 0x25 through 0xFF becomes four 8x8 tiles arranged as a 16x16 glyph."
        )
    )
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help=f"ROM to read, default: {DEFAULT_ROM}")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output .bin, default: {DEFAULT_OUT}")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META, help=f"Output metadata JSON, default: {DEFAULT_META}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rom = args.rom.read_bytes()
    out = bytearray()
    glyphs = []

    for glyph_index, code in enumerate(range(FIRST_CODE, LAST_CODE + 1)):
        offset = record_offset(code)
        size = record_size(code)
        if len(rom) < offset + size:
            raise ValueError(f"{args.rom} is too small for secondary record 0x{code:02X} at 0x{offset:06X}")
        record = rom[offset : offset + size]
        out.extend(record_to_4bpp(record))
        glyphs.append(
            {
                "code": f"0x{code:02X}",
                "char_cp1251": cp1251_char(code),
                "glyph_index": glyph_index,
                "bin_offset": f"0x{glyph_index * GLYPH_BYTES:04X}",
                "rom_offset": f"0x{offset:06X}",
                "record_size_bytes": size,
                "record_header_hex": record[:ROW_OFFSET].hex(),
                "width_pixels": record[0],
                "width_offset_in_record": 0,
                "tile_layout": "four consecutive 8x8 tiles: top-left, top-right, bottom-left, bottom-right",
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bytes(out))
    metadata = {
        "source_rom": str(args.rom),
        "format": "YY-CHR-friendly conversion: 4bpp GBA, four 8x8 tiles per 16x16 secondary glyph",
        "source_format": "uncompressed custom secondary font records; row bitmaps start at byte 4",
        "width_note": "Edit glyphs[*].width_pixels, then run inject_secondary_font.py. Values are written to byte 0 of each secondary record.",
        "record_header_note": "record_header_hex preserves bytes 0..3 of each renderer-specific record; injectors restore bytes 1..3 and then apply width_pixels to byte 0.",
        "first_code": f"0x{FIRST_CODE:02X}",
        "last_code": f"0x{LAST_CODE:02X}",
        "glyph_count": LAST_CODE - FIRST_CODE + 1,
        "glyph_bytes": GLYPH_BYTES,
        "font_bin": str(args.out),
        "glyphs": glyphs,
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.out.read_bytes() != bytes(out):
        raise RuntimeError("extraction verification failed: written .bin does not match converted records")
    print(f"Extracted {len(out)} converted bytes to {args.out}")
    print(f"Wrote metadata to {args.metadata}")


if __name__ == "__main__":
    main()
