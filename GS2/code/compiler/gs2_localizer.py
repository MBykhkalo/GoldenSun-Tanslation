#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_DIR / "code"
INPUT_DIR = PROJECT_DIR / "input"
OUTPUT_DIR = PROJECT_DIR / "output"
RESOURCES_DIR = CODE_DIR / "resources"
TEMP_OUTPUT_DIR = OUTPUT_DIR / "temp"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from common.gs_string_codec import StringCodec
from common.rom import (
    detect_rom,
    font_table_offset,
    root_table,
    scan_string_groups,
    string_length_table,
    string_model_table,
)
from common.spacemanager_model import zero_runs
from common.tbl_builder import CONTROL_CODES, decode_bytes, glyph_char_for_code

GS2_ENG_ROM = INPUT_DIR / "golden_sun_2_eng.gba"
BASELINE_JSON = RESOURCES_DIR / "baseline" / "gs2_plaintext_hook_baseline.json"
FONT_BIN = RESOURCES_DIR / "fonts" / "main" / "font_tiles_cyrillic.bin"
WIDTHS_JSON = RESOURCES_DIR / "fonts" / "main" / "font_widths_cyrillic.json"
SECONDARY_FONT_BIN = RESOURCES_DIR / "fonts" / "secondary" / "secondary_menu_font_4bpp_16x16.bin"
SECONDARY_FONT_JSON = RESOURCES_DIR / "fonts" / "secondary" / "secondary_menu_font_4bpp_16x16.json"

UKRAINIAN_TRANSLATION_JSON = OUTPUT_DIR / "ukrainian_translation.json"
TMP_PARENT = TEMP_OUTPUT_DIR

OUTPUT_ROM = TEMP_OUTPUT_DIR / "golden_sun_2_ukr.gba"
STRUCTURE_REPORT = TEMP_OUTPUT_DIR / "gs2_structure_report.json"
COMPILE_REPORT = TEMP_OUTPUT_DIR / "gs2_compile_report.json"
UKRAINIAN_TBL = TEMP_OUTPUT_DIR / "ukrainian_cp1251.tbl"
TEMPLATE_JSON = TEMP_OUTPUT_DIR / "ukrainian_translation_template.json"

FONT_TILE_COUNT = 224
FONT_TILE_BYTES = 32
FONT_BASE_CODE = 0x20
GS2_WIDTH_TABLE_SIZE = 224
TARGET_ROM_SIZE = 24 * 1024 * 1024
SECONDARY_FIRST_CODE = 0x25
SECONDARY_LAST_CODE = 0xFF
SECONDARY_BASE_OFFSET = 0x05A580
SECONDARY_BASE_CODE = 0x25
SECONDARY_SLOT_BYTES = 32
SECONDARY_LAST_SLOT_BYTES = 28
SECONDARY_ROW_OFFSET = 4
SECONDARY_WIDTH = 16
SECONDARY_HEIGHT = 16
SECONDARY_TILE_BYTES = 32
SECONDARY_TILES_PER_GLYPH = 4
SECONDARY_GLYPH_BYTES = SECONDARY_TILE_BYTES * SECONDARY_TILES_PER_GLYPH

TOKEN_TO_BYTE = {f"[{name}]": code for code, name in CONTROL_CODES.items() if code != 0}
TOKEN_TO_BYTE.update({f"<{name}>": code for code, name in CONTROL_CODES.items() if code != 0})

@dataclass(frozen=True)
class PlaintextStructure:
    code_literal_offset: int
    table_offset: int
    text_base_offset: int
    slot_count: int
    effective_entry_count: int


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_DIR))
    except ValueError:
        return str(resolved)


def parse_hex_int(value: str) -> int:
    return int(value, 16)


def write_ukrainian_tbl(path: Path) -> None:
    lines = [
        "# Golden Sun 2 Ukrainian candidate table (CP1251).",
        "# Generated independently by Stage 4; existing .tbl files are not reused.",
        "# Ukrainian-specific CP1251 codes:",
        "#   A5=Ґ, B4=ґ, AA=Є, BA=є, B2=І, B3=і, AF=Ї, BF=ї",
        "",
    ]
    for code in range(0x00, 0x100):
        if code in CONTROL_CODES:
            lines.append(f"{code:02X}=<{CONTROL_CODES[code]}>")
        elif code < 0x20:
            continue
        else:
            lines.append(f"{code:02X}={glyph_char_for_code(code, 'cp1251')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def adapted_font(font_bin: Path) -> bytes:
    font = font_bin.read_bytes()
    expected = FONT_TILE_COUNT * FONT_TILE_BYTES
    if len(font) != expected:
        raise ValueError(f"{font_bin} has {len(font)} bytes; expected {expected}")
    return font


def adapted_widths(widths_json: Path) -> dict[int, int]:
    payload = json.loads(widths_json.read_text(encoding="utf-8"))
    return {code: int(payload["widths"][f"0x{code:02X}"]["width_pixels"]) for code in range(0x20, 0x100)}


def secondary_record_offset(code: int) -> int:
    return SECONDARY_BASE_OFFSET + (code - SECONDARY_BASE_CODE) * SECONDARY_SLOT_BYTES


def secondary_record_size(code: int) -> int:
    return SECONDARY_LAST_SLOT_BYTES if code == SECONDARY_LAST_CODE else SECONDARY_SLOT_BYTES


def load_secondary_metadata(metadata_path: Path) -> dict[int, tuple[int, bytes | None]]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata: dict[int, tuple[int, bytes | None]] = {}
    for item in payload.get("glyphs", []):
        code = int(str(item["code"]), 16)
        if not SECONDARY_FIRST_CODE <= code <= SECONDARY_LAST_CODE:
            raise ValueError(f"secondary metadata has out-of-range code 0x{code:02X}")
        width = int(item["width_pixels"])
        if not 0 <= width <= SECONDARY_WIDTH:
            raise ValueError(f"secondary metadata width for code 0x{code:02X} must be 0..16, got {width}")
        header_hex = item.get("record_header_hex")
        header = None
        if isinstance(header_hex, str) and header_hex:
            header = bytes.fromhex(header_hex)
            if len(header) != SECONDARY_ROW_OFFSET:
                raise ValueError(
                    f"secondary metadata header for code 0x{code:02X} must be {SECONDARY_ROW_OFFSET} bytes"
                )
        metadata[code] = (width, header)
    missing = [code for code in range(SECONDARY_FIRST_CODE, SECONDARY_LAST_CODE + 1) if code not in metadata]
    if missing:
        raise ValueError(f"secondary metadata is missing widths for {len(missing)} codes; first: 0x{missing[0]:02X}")
    return metadata


def decode_secondary_tile(tile: bytes, bitmap: list[list[int]], tile_x: int, tile_y: int) -> None:
    if len(tile) != SECONDARY_TILE_BYTES:
        raise ValueError("internal secondary tile decode error")
    for y in range(8):
        for x_pair in range(4):
            packed = tile[y * 4 + x_pair]
            x0 = tile_x * 8 + x_pair * 2
            x1 = x0 + 1
            y0 = tile_y * 8 + y
            bitmap[y0][x0] = 1 if (packed & 0x0F) else 0
            bitmap[y0][x1] = 1 if (packed >> 4) else 0


def secondary_glyph_to_bitmap(glyph: bytes) -> list[list[int]]:
    bitmap = [[0 for _ in range(SECONDARY_WIDTH)] for _ in range(SECONDARY_HEIGHT)]
    decode_secondary_tile(glyph[0:32], bitmap, 0, 0)
    decode_secondary_tile(glyph[32:64], bitmap, 1, 0)
    decode_secondary_tile(glyph[64:96], bitmap, 0, 1)
    decode_secondary_tile(glyph[96:128], bitmap, 1, 1)
    return bitmap


def secondary_bitmap_to_record(
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
        record[:SECONDARY_ROW_OFFSET] = record_header
    row_count = min(SECONDARY_HEIGHT, max(0, (size - SECONDARY_ROW_OFFSET) // 2))
    for y in range(row_count):
        word = 0
        for x in range(SECONDARY_WIDTH):
            if bitmap[y][x]:
                word |= 1 << (15 - x)
        record[SECONDARY_ROW_OFFSET + y * 2 : SECONDARY_ROW_OFFSET + y * 2 + 2] = word.to_bytes(2, "little")
    record[0] = width_pixels
    return bytes(record)


def inject_secondary_font(rom: bytearray, font_path: Path, metadata_path: Path) -> dict:
    font = font_path.read_bytes()
    expected = (SECONDARY_LAST_CODE - SECONDARY_FIRST_CODE + 1) * SECONDARY_GLYPH_BYTES
    if len(font) != expected:
        raise ValueError(f"{font_path} has {len(font)} bytes; expected {expected}")
    metadata = load_secondary_metadata(metadata_path)
    for glyph_index, code in enumerate(range(SECONDARY_FIRST_CODE, SECONDARY_LAST_CODE + 1)):
        glyph = font[glyph_index * SECONDARY_GLYPH_BYTES : (glyph_index + 1) * SECONDARY_GLYPH_BYTES]
        bitmap = secondary_glyph_to_bitmap(glyph)
        offset = secondary_record_offset(code)
        size = secondary_record_size(code)
        if len(rom) < offset + size:
            raise ValueError(f"ROM is too small for secondary record 0x{code:02X} at 0x{offset:06X}")
        original = bytes(rom[offset : offset + size])
        width, header = metadata[code]
        rom[offset : offset + size] = secondary_bitmap_to_record(bitmap, original, size, width, header)
    return {
        "font_bin": display_path(font_path),
        "metadata": display_path(metadata_path),
        "table_offset": f"0x{SECONDARY_BASE_OFFSET:06x}",
        "end_offset": f"0x{secondary_record_offset(SECONDARY_LAST_CODE) + SECONDARY_LAST_SLOT_BYTES:06x}",
        "first_code": f"0x{SECONDARY_FIRST_CODE:02x}",
        "last_code": f"0x{SECONDARY_LAST_CODE:02x}",
        "glyph_count": SECONDARY_LAST_CODE - SECONDARY_FIRST_CODE + 1,
    }


def safe_cp1251_char(char: str) -> bytes:
    replacements = {
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
    }
    char = replacements.get(char, char)
    try:
        return char.encode("cp1251")
    except UnicodeEncodeError:
        return b"?"


def encode_text(text: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "[":
            end = text.find("]", i + 1)
            if end != -1:
                token = text[i : end + 1]
                if token in TOKEN_TO_BYTE:
                    out.append(TOKEN_TO_BYTE[token])
                    i = end + 1
                    continue
        if text[i] == "<":
            end = text.find(">", i + 1)
            if end != -1:
                token = text[i : end + 1]
                if token in TOKEN_TO_BYTE:
                    out.append(TOKEN_TO_BYTE[token])
                    i = end + 1
                    continue
                if token.startswith("<CTRL_") and len(token) == 9:
                    out.append(int(token[6:8], 16))
                    i = end + 1
                    continue
        out.extend(safe_cp1251_char(text[i]))
        i += 1
    return bytes(out)


def text_from_entry(entry: dict) -> str | None:
    for key in ("text_ukr", "text_ua", "ua", "uk", "text"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def load_ukrainian_translations(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "entries" in data:
            data = data["entries"]
        else:
            data = [{"id": key, "text": value} for key, value in data.items()]
    translations: dict[int, str] = {}
    for entry in data:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        text = text_from_entry(entry)
        if text is None:
            continue
        translations[int(entry["id"])] = text
    return translations


def decode_english_fallbacks(clean: bytes, count: int) -> dict[int, str]:
    codec = StringCodec(clean, detect_rom(clean))
    out: dict[int, str] = {}
    for index in range(count):
        raw = codec.decode_bytes(index, max_chars=1024)
        out[index] = decode_bytes(raw[:-1] if raw.endswith(b"\x00") else raw, "cp1252")
    return out


def build_template_json(path: Path, fallbacks: dict[int, str]) -> None:
    payload = [
        {
            "id": index,
            "text_eng": fallbacks[index],
            "text_ukr": "",
        }
        for index in range(len(fallbacks))
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_baseline(path: Path) -> dict:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    required = ("clean_rom", "plaintext_table_signature", "system_patch_clusters")
    missing = [key for key in required if key not in baseline]
    if missing:
        raise ValueError(f"{path} is missing required keys: {', '.join(missing)}")
    for item in baseline["system_patch_clusters"]:
        if "data_hex" not in item:
            raise ValueError(f"{path} system patch cluster {item.get('start')} is missing data_hex")
    return baseline


def analyze_from_baseline(clean: bytes, args: argparse.Namespace, baseline: dict) -> dict:
    clean_info = detect_rom(clean)
    clean_sha = sha256(clean)
    expected_sha = baseline["clean_rom"].get("sha256")
    if expected_sha and clean_sha != expected_sha:
        raise ValueError(
            f"clean GS2 ROM sha256 mismatch: got {clean_sha}, expected {expected_sha} from {display_path(args.baseline_json)}"
        )

    width_offset = parse_hex_int(baseline["clean_rom"]["width_table_offset"])
    font_offset = parse_hex_int(baseline["clean_rom"]["font_table_offset"])
    free_blocks = zero_runs(clean, min_size=256)

    return {
        "inputs": {
            "gs2_clean": display_path(args.gs2_eng_rom),
            "baseline_resource": display_path(args.baseline_json),
            "font_tiles": display_path(args.font_bin),
            "widths": display_path(args.widths_json),
            "secondary_font": display_path(args.secondary_font_bin),
            "secondary_font_metadata": display_path(args.secondary_font_json),
        },
        "clean_rom": {
            "size": len(clean),
            "sha256": clean_sha,
            "title": clean_info.title,
            "game_code": clean_info.game_code,
            "engine_version": clean_info.version,
            "file_table": f"0x{clean_info.file_table:08x}",
            "root_table": f"0x{root_table(clean, clean_info):08x}",
            "string_length_table": f"0x{string_length_table(clean, clean_info):08x}",
            "string_model_table": f"0x{string_model_table(clean, clean_info):08x}",
            "native_string_group_count": len(scan_string_groups(clean, clean_info)),
            "font_table_offset": f"0x{font_offset:06x}",
            "width_table_offset": f"0x{width_offset:06x}",
        },
        "baseline_resource": {"path": display_path(args.baseline_json)},
        "plaintext_table_signature": baseline["plaintext_table_signature"],
        "diff_clusters": {
            "cluster_count": len(baseline["system_patch_clusters"]),
            "system_patch_clusters": baseline["system_patch_clusters"],
        },
        "free_space": {
            "zero_block_count_min256": len(free_blocks),
            "largest_zero_blocks": [
                {"start": f"0x{block.start:06x}", "end": f"0x{block.end:06x}", "size": block.size}
                for block in sorted(free_blocks, key=lambda b: b.size, reverse=True)[:20]
            ],
        },
    }


def compile_localized_rom(clean: bytes, args: argparse.Namespace, report: dict) -> dict:
    structure = PlaintextStructure(
        code_literal_offset=parse_hex_int(report["plaintext_table_signature"]["code_literal_offset"]),
        table_offset=parse_hex_int(report["plaintext_table_signature"]["table_offset"]),
        text_base_offset=parse_hex_int(report["plaintext_table_signature"]["text_base_offset"]),
        slot_count=int(report["plaintext_table_signature"]["slot_count"]),
        effective_entry_count=int(report["plaintext_table_signature"]["effective_entry_count"]),
    )
    width_offset = parse_hex_int(report["clean_rom"]["width_table_offset"])
    font_offset = parse_hex_int(report["clean_rom"]["font_table_offset"])
    system_clusters = report["diff_clusters"]["system_patch_clusters"]

    rom = bytearray(clean)
    if len(rom) < TARGET_ROM_SIZE:
        rom.extend(b"\x00" * (TARGET_ROM_SIZE - len(rom)))

    for cluster in system_clusters:
        start = parse_hex_int(cluster["start"])
        end = parse_hex_int(cluster["end"])
        data = bytes.fromhex(cluster["data_hex"])
        if len(data) != end - start:
            raise ValueError(f"system patch cluster size mismatch for {cluster['start']}..{cluster['end']}")
        rom[start:end] = data

    font = adapted_font(args.font_bin)
    rom[font_offset : font_offset + len(font)] = font

    widths = adapted_widths(args.widths_json)
    for code in range(0x20, 0x100):
        rom[width_offset + (code - 0x20)] = widths[code]

    secondary_font = inject_secondary_font(rom, args.secondary_font_bin, args.secondary_font_json)

    translations = load_ukrainian_translations(args.ukrainian_json)
    fallbacks = decode_english_fallbacks(clean, structure.effective_entry_count)
    build_template_json(args.template_json, fallbacks)

    rom[structure.table_offset : TARGET_ROM_SIZE] = b"\x00" * (TARGET_ROM_SIZE - structure.table_offset)
    cursor = 0
    reused: dict[bytes, int] = {}
    translation_ids_used = 0
    for index in range(structure.slot_count):
        if index >= structure.effective_entry_count:
            relative = 0
        else:
            text = translations.get(index, fallbacks[index])
            if index in translations:
                translation_ids_used += 1
            raw = encode_text(text) + b"\x00"
            if args.dedupe_text and raw in reused:
                relative = reused[raw]
            else:
                relative = cursor
                reused[raw] = relative
                start = structure.text_base_offset + relative
                end = start + len(raw)
                if end > TARGET_ROM_SIZE:
                    raise ValueError(
                        f"localized text exceeds target ROM size at id {index}; "
                        f"need 0x{end:x}, limit 0x{TARGET_ROM_SIZE:x}"
                    )
                rom[start:end] = raw
                cursor += len(raw)
        rom[structure.table_offset + index * 4 : structure.table_offset + index * 4 + 4] = relative.to_bytes(4, "little")

    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(bytes(rom))

    return {
        "output_rom": display_path(args.output_rom),
        "output_size": len(rom),
        "output_sha256": sha256(bytes(rom)),
        "system_patch_cluster_count": len(system_clusters),
        "font_injected": {"offset": f"0x{font_offset:06x}", "size": len(font)},
        "widths_injected": {"offset": f"0x{width_offset:06x}", "entry_count": len(widths)},
        "secondary_font_injected": secondary_font,
        "plaintext_table": {
            "table_offset": f"0x{structure.table_offset:06x}",
            "text_base_offset": f"0x{structure.text_base_offset:06x}",
            "slot_count": structure.slot_count,
            "effective_entry_count": structure.effective_entry_count,
            "text_blob_bytes_used": cursor,
            "unique_text_blobs": len(reused),
        },
        "ukrainian_translation_json": display_path(args.ukrainian_json) if args.ukrainian_json.exists() else None,
        "ukrainian_entries_used": translation_ids_used,
        "fallback_english_entries": structure.effective_entry_count - translation_ids_used,
        "template_json": display_path(args.template_json),
        "ukrainian_tbl": display_path(args.ukrainian_tbl),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independent GS2 Ukrainian localizer.")
    parser.add_argument("--gs2-eng-rom", type=Path, default=GS2_ENG_ROM)
    parser.add_argument("--baseline-json", type=Path, default=BASELINE_JSON)
    parser.add_argument("--font-bin", type=Path, default=FONT_BIN)
    parser.add_argument("--widths-json", type=Path, default=WIDTHS_JSON)
    parser.add_argument("--secondary-font-bin", type=Path, default=SECONDARY_FONT_BIN)
    parser.add_argument("--secondary-font-json", type=Path, default=SECONDARY_FONT_JSON)
    parser.add_argument("--ukrainian-json", type=Path, default=UKRAINIAN_TRANSLATION_JSON)
    parser.add_argument("--output-dir", type=Path, default=TEMP_OUTPUT_DIR)
    parser.add_argument("--output-rom", type=Path, default=OUTPUT_ROM)
    parser.add_argument("--analysis-only", action="store_true")
    parser.add_argument("--dedupe-text", action="store_true", default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    default_output_rom = args.output_rom == OUTPUT_ROM
    args.gs2_eng_rom = args.gs2_eng_rom.resolve()
    args.baseline_json = args.baseline_json.resolve()
    args.font_bin = args.font_bin.resolve()
    args.widths_json = args.widths_json.resolve()
    args.secondary_font_bin = args.secondary_font_bin.resolve()
    args.secondary_font_json = args.secondary_font_json.resolve()
    args.ukrainian_json = args.ukrainian_json.resolve()
    args.output_dir = args.output_dir.resolve()
    args.output_rom = args.output_rom.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if default_output_rom and args.output_dir != TEMP_OUTPUT_DIR:
        args.output_rom = args.output_dir / OUTPUT_ROM.name
    args.structure_report = args.output_dir / STRUCTURE_REPORT.name
    args.compile_report = args.output_dir / COMPILE_REPORT.name
    args.ukrainian_tbl = args.output_dir / UKRAINIAN_TBL.name
    args.template_json = args.output_dir / TEMPLATE_JSON.name
    TMP_PARENT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stage4_gs2_", dir=TMP_PARENT) as tmp_name:
        tmp = Path(tmp_name)
        work_eng = tmp / args.gs2_eng_rom.name
        shutil.copy2(args.gs2_eng_rom, work_eng)
        clean = work_eng.read_bytes()

        baseline = load_baseline(args.baseline_json)
        report = analyze_from_baseline(clean, args, baseline)
        write_ukrainian_tbl(args.ukrainian_tbl)
        args.structure_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Structure report: {args.structure_report}")

        if args.analysis_only:
            fallbacks = decode_english_fallbacks(clean, int(report["plaintext_table_signature"]["effective_entry_count"]))
            build_template_json(args.template_json, fallbacks)
            print(f"[OK] Translation template: {args.template_json}")
            return

        compile_report = compile_localized_rom(clean, args, report)
        args.compile_report.write_text(json.dumps(compile_report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Output ROM: {args.output_rom}")
        print(f"[OK] Compile report: {args.compile_report}")
        print(f"[OK] Ukrainian table: {args.ukrainian_tbl}")
        if compile_report["ukrainian_entries_used"] == 0:
            print("[WARN] No ukrainian_translation.json entries were applied; output uses English fallback text.")


if __name__ == "__main__":
    main()
