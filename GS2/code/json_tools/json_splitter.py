#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_DIR / "output" / "ukrainian_translation.json"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "json_splitter_parts"


def split_json(input_file: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT_DIR, chunk_size: int = 100) -> bool:
    if not input_file.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return False

    data = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("[ERROR] JSON structure must be an array.")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    for old_part in output_dir.glob("part_*.json"):
        old_part.unlink()

    part_number = 1
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        output_file = output_dir / f"part_{part_number}.json"
        output_file.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Created: {output_file} ({len(chunk)} entries)")
        part_number += 1

    print(f"[OK] Split {len(data)} entries into {part_number - 1} part(s).")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split GS2 ukrainian_translation.json into part_*.json chunks.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--chunk-size", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not split_json(args.input, args.output_dir, args.chunk_size):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
