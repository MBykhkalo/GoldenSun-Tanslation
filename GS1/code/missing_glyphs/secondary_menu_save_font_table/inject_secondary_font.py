#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ROM = PROJECT_DIR / "output" / "temp" / "golden_sun_1_ukr.gba"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "missing_glyphs" / "secondary_menu_save_font_table"
DEFAULT_FONT = DEFAULT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.bin"
DEFAULT_META = DEFAULT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.json"
DEFAULT_OUT_ROM = DEFAULT_OUTPUT_DIR / "golden_sun_1_ukr_secondary_font_patched.gba"

FIRST_CODE = 0x25
LAST_CODE = 0xFF
FORMULA_BASE_OFFSET = 0x0322C4
FORMULA_BASE_CODE = 0x25
SLOT_BYTES = 32
LAST_SLOT_BYTES = 28
ROW_OFFSET = 4
WIDTH = 16
HEIGHT = 16
TILE_BYTES = 32
TILES_PER_GLYPH = 4
GLYPH_BYTES = TILE_BYTES * TILES_PER_GLYPH
EXPECTED_BYTES = (LAST_CODE - FIRST_CODE + 1) * GLYPH_BYTES


def load_metadata(metadata_path: Path) -> dict[int, tuple[int, bytes | None]]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata: dict[int, tuple[int, bytes | None]] = {}
    for item in payload.get("glyphs", []):
        code = int(str(item["code"]), 16)
        if not FIRST_CODE <= code <= LAST_CODE:
            raise ValueError(f"metadata has out-of-range secondary font code 0x{code:02X}")
        width = int(item["width_pixels"])
        if not 0 <= width <= 16:
            raise ValueError(f"metadata width for code 0x{code:02X} must be 0..16, got {width}")
        header_hex = item.get("record_header_hex")
        header = None
        if isinstance(header_hex, str) and header_hex:
            header = bytes.fromhex(header_hex)
            if len(header) != ROW_OFFSET:
                raise ValueError(f"metadata header for code 0x{code:02X} must be {ROW_OFFSET} bytes")
        metadata[code] = (width, header)
    missing = [code for code in range(FIRST_CODE, LAST_CODE + 1) if code not in metadata]
    if missing:
        raise ValueError(f"metadata is missing widths for {len(missing)} secondary font codes; first: 0x{missing[0]:02X}")
    return metadata


def record_offset(code: int) -> int:
    return FORMULA_BASE_OFFSET + (code - FORMULA_BASE_CODE) * SLOT_BYTES


def record_size(code: int) -> int:
    return LAST_SLOT_BYTES if code == LAST_CODE else SLOT_BYTES


def decode_tile(tile: bytes, bitmap: list[list[int]], tile_x: int, tile_y: int) -> None:
    if len(tile) != TILE_BYTES:
        raise ValueError("internal tile decode error: tile must be 32 bytes")
    for y in range(8):
        for x_pair in range(4):
            packed = tile[y * 4 + x_pair]
            x0 = tile_x * 8 + x_pair * 2
            x1 = x0 + 1
            y0 = tile_y * 8 + y
            bitmap[y0][x0] = 1 if (packed & 0x0F) else 0
            bitmap[y0][x1] = 1 if (packed >> 4) else 0


def glyph_to_bitmap(glyph: bytes) -> list[list[int]]:
    bitmap = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
    decode_tile(glyph[0:32], bitmap, 0, 0)
    decode_tile(glyph[32:64], bitmap, 1, 0)
    decode_tile(glyph[64:96], bitmap, 0, 1)
    decode_tile(glyph[96:128], bitmap, 1, 1)
    return bitmap


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


def normalized_glyph(glyph: bytes) -> bytes:
    bitmap = glyph_to_bitmap(glyph)
    return b"".join(
        [
            encode_tile(bitmap, 0, 0),
            encode_tile(bitmap, 1, 0),
            encode_tile(bitmap, 0, 1),
            encode_tile(bitmap, 1, 1),
        ]
    )


def bitmap_to_record(
    bitmap: list[list[int]],
    original: bytes,
    size: int,
    width_pixels: int,
    record_header: bytes | None,
) -> bytes:
    record = bytearray(original[:size])
    if len(record) < size:
        record.extend(b"\x00" * (size - len(record)))
    if record_header is not None:
        record[:ROW_OFFSET] = record_header
    row_count = min(HEIGHT, max(0, (size - ROW_OFFSET) // 2))
    for y in range(row_count):
        word = 0
        for x in range(WIDTH):
            if bitmap[y][x]:
                word |= 1 << (15 - x)
        record[ROW_OFFSET + y * 2 : ROW_OFFSET + y * 2 + 2] = word.to_bytes(2, "little")
    record[0] = width_pixels
    return bytes(record)


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
        description="Inject an edited GS1 secondary menu/save 4bpp conversion .bin back into a ROM copy."
    )
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help=f"Base ROM to copy/patch, default: {DEFAULT_ROM}")
    parser.add_argument("--font-bin", type=Path, default=DEFAULT_FONT, help=f"Edited converted .bin, default: {DEFAULT_FONT}")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META, help=f"Edited metadata/width JSON, default: {DEFAULT_META}")
    parser.add_argument("--out-rom", type=Path, default=DEFAULT_OUT_ROM, help=f"Patched ROM path, default: {DEFAULT_OUT_ROM}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font = args.font_bin.read_bytes()
    if len(font) != EXPECTED_BYTES:
        raise ValueError(f"{args.font_bin} has {len(font)} bytes; expected {EXPECTED_BYTES}")
    metadata = load_metadata(args.metadata)

    rom = bytearray(args.rom.read_bytes())
    normalized_input = bytearray()
    for glyph_index, code in enumerate(range(FIRST_CODE, LAST_CODE + 1)):
        glyph = font[glyph_index * GLYPH_BYTES : (glyph_index + 1) * GLYPH_BYTES]
        bitmap = glyph_to_bitmap(glyph)
        offset = record_offset(code)
        size = record_size(code)
        if len(rom) < offset + size:
            raise ValueError(f"{args.rom} is too small for secondary record 0x{code:02X} at 0x{offset:06X}")
        original = bytes(rom[offset : offset + size])
        width, header = metadata[code]
        record = bitmap_to_record(bitmap, original, size, width, header)
        rom[offset : offset + size] = record
        normalized_input.extend(normalized_glyph(glyph))

    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(rom)

    patched = args.out_rom.read_bytes()
    extracted = bytearray()
    for code in range(FIRST_CODE, LAST_CODE + 1):
        offset = record_offset(code)
        size = record_size(code)
        width, _ = metadata[code]
        if patched[offset] != width:
            raise RuntimeError(f"injection verification failed: width for code 0x{code:02X} was not written")
        extracted.extend(record_to_4bpp(patched[offset : offset + size]))

    if bytes(extracted) != bytes(normalized_input):
        raise RuntimeError(
            "injection verification failed: re-extracted secondary font differs from the input. "
            "For code 0xFF, only rows that fit in its 28-byte record can be preserved."
        )
    print(f"Injected secondary records for 0x{FIRST_CODE:02X}..0x{LAST_CODE:02X}")
    print(f"Wrote verified ROM to {args.out_rom}")


if __name__ == "__main__":
    main()
