#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_DIR / "output"
TEMP_OUTPUT_DIR = OUTPUT_DIR / "temp"
DEFAULT_ROM = TEMP_OUTPUT_DIR / "golden_sun_2_ukr.gba"
STAGE4_STRUCTURE = TEMP_OUTPUT_DIR / "gs2_structure_report.json"
VERIFIED_DUMP = TEMP_OUTPUT_DIR / "verified_dump_ukr.json"
REPORT_JSON = TEMP_OUTPUT_DIR / "verification_report.json"

ALLOWED_CONTROL_CODES = {
    0x01: "TEXTBOX_BREAK",
    0x02: "MESSAGE_END",
    0x03: "LINE_BREAK",
    0x04: "CTRL_04",
    0x05: "PAUSE",
    0x06: "CTRL_06",
    0x07: "PAUSE_OR_SOUND",
    0x08: "ICON",
    0x09: "CTRL_09",
    0x0A: "CTRL_0A",
    0x0B: "CTRL_0B",
    0x0C: "CTRL_0C",
    0x0D: "CTRL_0D",
    0x0E: "CTRL_0E",
    0x0F: "CTRL_0F",
    0x10: "CTRL_10",
    0x11: "CTRL_11",
    0x12: "CTRL_12",
    0x13: "CTRL_13",
    0x14: "CTRL_14",
    0x15: "CTRL_15",
    0x16: "CTRL_16",
    0x17: "CTRL_17",
    0x18: "CTRL_18",
    0x19: "CTRL_19",
    0x1A: "CTRL_1A",
    0x1B: "CTRL_1B",
    0x1C: "CTRL_1C",
    0x1D: "CTRL_1D",
    0x1E: "YES_NO_PROMPT",
}


def parse_hex_int(value: str) -> int:
    return int(value, 16)


def decode_string(raw: bytes) -> tuple[str, list[int]]:
    chars: list[str] = []
    unknown_controls: list[int] = []
    for byte in raw:
        if byte in ALLOWED_CONTROL_CODES:
            chars.append(f"[{ALLOWED_CONTROL_CODES[byte]}]")
        elif byte < 0x20:
            chars.append(f"<CTRL_{byte:02X}>")
            unknown_controls.append(byte)
        else:
            try:
                chars.append(bytes([byte]).decode("cp1251"))
            except UnicodeDecodeError:
                # CP1251 leaves a few byte values undefined (for example 0x81).
                # Golden Sun can still use them as raw engine byte values, so
                # preserve them visibly instead of treating the string as
                # structurally invalid.
                chars.append(f"<UNMAPPED_{byte:02X}>")
    return "".join(chars), unknown_controls


def read_c_string(rom: bytes, offset: int, max_len: int) -> tuple[bytes, bool]:
    end = offset
    limit = min(len(rom), offset + max_len)
    while end < limit:
        if rom[end] == 0:
            return rom[offset:end], True
        end += 1
    return rom[offset:limit], False


def printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad_markers = text.count("<BAD_")
    return max(0.0, 1.0 - bad_markers / max(1, len(text)))


def verify(args: argparse.Namespace) -> tuple[list[dict], dict]:
    rom = args.rom.read_bytes()
    structure = json.loads(args.structure.read_text(encoding="utf-8"))["plaintext_table_signature"]
    table_offset = parse_hex_int(structure["table_offset"])
    text_base = parse_hex_int(structure["text_base_offset"])
    slot_count = int(structure["slot_count"])
    effective_count = int(structure["effective_entry_count"])

    if table_offset + slot_count * 4 > len(rom):
        raise ValueError("pointer table extends beyond ROM")
    if not (0 <= text_base < len(rom)):
        raise ValueError("text base is outside ROM")

    entries: list[dict] = []
    issues: list[dict] = []
    control_counter: Counter[str] = Counter()
    duplicate_offsets: Counter[int] = Counter()
    max_observed_len = 0

    for index in range(slot_count):
        pointer_offset = table_offset + index * 4
        relative = int.from_bytes(rom[pointer_offset : pointer_offset + 4], "little")
        text_offset = text_base + relative
        active = index < effective_count

        entry_issues: list[str] = []
        if not (0 <= relative < len(rom) - text_base):
            entry_issues.append("pointer_out_of_text_region")
            raw = b""
            terminated = False
            decoded = ""
            unknown_controls: list[int] = []
        else:
            duplicate_offsets[relative] += 1
            raw, terminated = read_c_string(rom, text_offset, args.max_string_bytes)
            decoded, unknown_controls = decode_string(raw)
            max_observed_len = max(max_observed_len, len(raw))
            if active and not terminated:
                entry_issues.append("unterminated_or_runaway")
            if active and len(raw) >= args.max_string_bytes:
                entry_issues.append("max_length_reached")
            if active and unknown_controls:
                entry_issues.append("unknown_control_code")
            if active and printable_ratio(decoded) < args.min_printable_ratio:
                entry_issues.append("low_printable_ratio")
            for byte in raw:
                if byte in ALLOWED_CONTROL_CODES:
                    control_counter[ALLOWED_CONTROL_CODES[byte]] += 1

        entry = {
            "id": index,
            "active": active,
            "pointer_offset": f"0x{pointer_offset:06x}",
            "relative_text_offset": f"0x{relative:x}",
            "text_offset": f"0x{text_offset:06x}",
            "terminated": terminated,
            "raw_length": len(raw),
            "raw_hex": raw[: args.raw_hex_preview_bytes].hex(" "),
            "text": decoded,
            "issues": entry_issues,
        }
        entries.append(entry)
        if entry_issues:
            issues.append({"id": index, "issues": entry_issues, "text_offset": entry["text_offset"], "preview": decoded[:160]})

    active_entries = [entry for entry in entries if entry["active"]]
    inactive_entries = [entry for entry in entries if not entry["active"]]
    nonzero_inactive = [
        entry for entry in inactive_entries if int(entry["relative_text_offset"], 16) != 0
    ]

    report = {
        "rom": str(args.rom),
        "structure_source": str(args.structure),
        "table_offset": f"0x{table_offset:06x}",
        "text_base_offset": f"0x{text_base:06x}",
        "slot_count": slot_count,
        "effective_entry_count": effective_count,
        "active_entry_count": len(active_entries),
        "inactive_entry_count": len(inactive_entries),
        "nonzero_inactive_pointer_count": len(nonzero_inactive),
        "issue_count": len(issues),
        "pass": len(issues) == 0 and len(nonzero_inactive) == 0,
        "max_observed_raw_length": max_observed_len,
        "duplicate_text_offset_count": sum(1 for _, count in duplicate_offsets.items() if count > 1),
        "control_code_counts": dict(control_counter),
        "issues": issues[: args.issue_report_limit],
        "issue_report_limit": args.issue_report_limit,
    }
    return entries, report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Blind verifier/dumper for Stage 4 GS2 localized plaintext table.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--structure", type=Path, default=STAGE4_STRUCTURE)
    parser.add_argument("--output-dir", type=Path, default=TEMP_OUTPUT_DIR)
    parser.add_argument("--max-string-bytes", type=int, default=4096)
    parser.add_argument("--min-printable-ratio", type=float, default=0.98)
    parser.add_argument("--raw-hex-preview-bytes", type=int, default=96)
    parser.add_argument("--issue-report-limit", type=int, default=200)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    entries, report = verify(args)
    dump_path = args.output_dir / VERIFIED_DUMP.name
    report_path = args.output_dir / REPORT_JSON.name
    dump_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Blind dump: {dump_path}")
    print(f"[OK] Verification report: {report_path}")
    if report["pass"]:
        print("[OK] Stage 5 verification passed.")
    else:
        print(f"[WARN] Stage 5 verification found {report['issue_count']} issue(s).")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
