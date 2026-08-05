#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ROM = PROJECT_DIR / "output" / "temp" / "golden_sun_2_ukr.gba"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "missing_glyphs" / "main_dialog_font_table"
DEFAULT_FONT = DEFAULT_OUTPUT_DIR / "main_dialog_font_4bpp.bin"
DEFAULT_META = DEFAULT_OUTPUT_DIR / "main_dialog_font_4bpp.json"
DEFAULT_OUT_ROM = DEFAULT_OUTPUT_DIR / "golden_sun_2_ukr_main_font_patched.gba"

FONT_OFFSET = 0x682430
WIDTH_TABLE_OFFSET = 0x05F484
BASE_CODE = 0x20
TILE_COUNT = 224
TILE_BYTES = 32
FONT_BYTES = TILE_COUNT * TILE_BYTES


def load_widths(metadata_path: Path) -> dict[int, int]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    widths: dict[int, int] = {}
    for item in payload.get("glyphs", []):
        code = int(str(item["code"]), 16)
        if not BASE_CODE <= code < 0x100:
            raise ValueError(f"metadata has out-of-range main font code 0x{code:02X}")
        width = int(item["width_pixels"])
        if not 0 <= width <= 16:
            raise ValueError(f"metadata width for code 0x{code:02X} must be 0..16, got {width}")
        widths[code] = width
    missing = [code for code in range(BASE_CODE, 0x100) if code not in widths]
    if missing:
        raise ValueError(f"metadata is missing widths for {len(missing)} main font codes; first: 0x{missing[0]:02X}")
    return widths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject an edited main dialogue font .bin back into a copy of the ROM.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help=f"Base ROM to copy/patch, default: {DEFAULT_ROM}")
    parser.add_argument("--font-bin", type=Path, default=DEFAULT_FONT, help=f"Edited YY-CHR .bin, default: {DEFAULT_FONT}")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META, help=f"Edited metadata/width JSON, default: {DEFAULT_META}")
    parser.add_argument("--out-rom", type=Path, default=DEFAULT_OUT_ROM, help=f"Patched ROM path, default: {DEFAULT_OUT_ROM}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font = args.font_bin.read_bytes()
    if len(font) != FONT_BYTES:
        raise ValueError(f"{args.font_bin} has {len(font)} bytes; expected {FONT_BYTES}")
    widths = load_widths(args.metadata)

    rom = bytearray(args.rom.read_bytes())
    end = FONT_OFFSET + FONT_BYTES
    if len(rom) < end:
        raise ValueError(f"{args.rom} is too small for main font table at 0x{FONT_OFFSET:06X}")
    width_end = WIDTH_TABLE_OFFSET + TILE_COUNT
    if len(rom) < width_end:
        raise ValueError(f"{args.rom} is too small for main width table at 0x{WIDTH_TABLE_OFFSET:06X}")

    rom[FONT_OFFSET:end] = font
    for code in range(BASE_CODE, 0x100):
        rom[WIDTH_TABLE_OFFSET + (code - BASE_CODE)] = widths[code]
    args.out_rom.parent.mkdir(parents=True, exist_ok=True)
    args.out_rom.write_bytes(rom)

    patched = args.out_rom.read_bytes()
    if patched[FONT_OFFSET:end] != font:
        raise RuntimeError("injection verification failed: ROM font bytes do not match input .bin")
    for code in range(BASE_CODE, 0x100):
        if patched[WIDTH_TABLE_OFFSET + (code - BASE_CODE)] != widths[code]:
            raise RuntimeError(f"injection verification failed: width for code 0x{code:02X} was not written")
    print(f"Injected {FONT_BYTES} bytes at 0x{FONT_OFFSET:06X}")
    print(f"Injected {TILE_COUNT} widths at 0x{WIDTH_TABLE_OFFSET:06X}")
    print(f"Wrote verified ROM to {args.out_rom}")


if __name__ == "__main__":
    main()
