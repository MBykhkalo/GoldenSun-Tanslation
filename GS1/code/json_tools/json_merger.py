#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_DIR / "output" / "json_splitter_parts"
DEFAULT_OUTPUT = PROJECT_DIR / "output" / "ukrainian_translation.json"


def part_number(path: Path) -> int:
    match = re.search(r"part_(\d+)\.json", path.name)
    return int(match.group(1)) if match else 0


def merge_json(input_dir: Path = DEFAULT_INPUT_DIR, output_file: Path = DEFAULT_OUTPUT) -> bool:
    if not input_dir.exists():
        print(f"[ERROR] Input folder not found: {input_dir}")
        return False

    files = sorted(input_dir.glob("part_*.json"), key=part_number)
    if not files:
        print(f"[ERROR] No part_*.json files found in: {input_dir}")
        return False

    merged_data = []
    for path in files:
        chunk_data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(chunk_data, list):
            print(f"[ERROR] Part file must contain an array: {path}")
            return False
        merged_data.extend(chunk_data)
        print(f"[OK] Read: {path.name} ({len(chunk_data)} entries)")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(merged_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Merged {len(files)} file(s), {len(merged_data)} total entries.")
    print(f"[OK] Wrote: {output_file}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge GS1 translation part_*.json chunks.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not merge_json(args.input_dir, args.output):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
