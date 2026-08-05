#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
RESOURCES_DIR = CODE_DIR / "resources"
TEMP_DIR = OUTPUT_DIR / "temp"
STATE_FILE = TEMP_DIR / "gs2_project_state.json"

GS2_ENG_ROM = INPUT_DIR / "golden_sun_2_eng.gba"
TRANSLATION_JSON = OUTPUT_DIR / "ukrainian_translation.json"

BASELINE_JSON = RESOURCES_DIR / "baseline" / "gs2_plaintext_hook_baseline.json"
FONT_TILES = RESOURCES_DIR / "fonts" / "main" / "font_tiles_cyrillic.bin"
FONT_WIDTHS = RESOURCES_DIR / "fonts" / "main" / "font_widths_cyrillic.json"
SECONDARY_FONT_RESOURCE = RESOURCES_DIR / "fonts" / "secondary" / "secondary_menu_font_4bpp_16x16.bin"
SECONDARY_FONT_RESOURCE_JSON = RESOURCES_DIR / "fonts" / "secondary" / "secondary_menu_font_4bpp_16x16.json"

LOCALIZER = CODE_DIR / "compiler" / "gs2_localizer.py"
VERIFIER = CODE_DIR / "verifier" / "gs2_verifier.py"
JSON_SPLITTER = CODE_DIR / "json_tools" / "json_splitter.py"
JSON_MERGER = CODE_DIR / "json_tools" / "json_merger.py"
TEMPLATE_JSON = TEMP_DIR / "ukrainian_translation_template.json"
OUTPUT_ROM = TEMP_DIR / "golden_sun_2_ukr.gba"
STRUCTURE_REPORT = TEMP_DIR / "gs2_structure_report.json"
VERIFY_REPORT = TEMP_DIR / "verification_report.json"
FINAL_OUTPUT_DIR = OUTPUT_DIR / "Rom"
JSON_PARTS_DIR = OUTPUT_DIR / "json_splitter_parts"

MISSING_GLYPHS_DIR = CODE_DIR / "missing_glyphs"
MAIN_FONT_INJECT_SCRIPT = MISSING_GLYPHS_DIR / "main_dialog_font_table" / "inject_main_font.py"
MAIN_FONT_OUTPUT_DIR = OUTPUT_DIR / "missing_glyphs" / "main_dialog_font_table"
MAIN_FONT_BIN = MAIN_FONT_OUTPUT_DIR / "main_dialog_font_4bpp.bin"
MAIN_FONT_JSON = MAIN_FONT_OUTPUT_DIR / "main_dialog_font_4bpp.json"
SECONDARY_FONT_INJECT_SCRIPT = MISSING_GLYPHS_DIR / "secondary_menu_save_font_table" / "inject_secondary_font.py"
SECONDARY_FONT_OUTPUT_DIR = OUTPUT_DIR / "missing_glyphs" / "secondary_menu_save_font_table"
SECONDARY_FONT_BIN = (
    SECONDARY_FONT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.bin"
)
SECONDARY_FONT_JSON = (
    SECONDARY_FONT_OUTPUT_DIR / "secondary_menu_font_4bpp_16x16.json"
)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def final_datetime_mark() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(**updates: object) -> None:
    state = load_state()
    state.update(updates)
    state["updated_at"] = now()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def run_python(script: Path, *args: str) -> bool:
    sys.stdout.flush()
    try:
        subprocess.run([sys.executable, str(script), *args], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Command failed with exit code {exc.returncode}: {display_path(script)}")
        return False
    return True


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError:
        print(f"[WARN] Could not open automatically. Please open manually: {display_path(path)}")


def split_translations() -> None:
    if not TRANSLATION_JSON.exists():
        print("Create ukrainian_translation.json first with option 2.")
        return
    if run_python(
        JSON_SPLITTER,
        "--input",
        str(TRANSLATION_JSON),
        "--output-dir",
        str(JSON_PARTS_DIR),
    ):
        save_state(split_translations={"path": display_path(JSON_PARTS_DIR), "at": now()})


def merge_translations() -> None:
    if run_python(
        JSON_MERGER,
        "--input-dir",
        str(JSON_PARTS_DIR),
        "--output",
        str(TRANSLATION_JSON),
    ):
        save_state(merge_translations={"path": display_path(TRANSLATION_JSON), "at": now()})


def required_files_ok(verbose: bool = True) -> bool:
    required = [
        GS2_ENG_ROM,
        BASELINE_JSON,
        FONT_TILES,
        FONT_WIDTHS,
        SECONDARY_FONT_RESOURCE,
        SECONDARY_FONT_RESOURCE_JSON,
        LOCALIZER,
        VERIFIER,
    ]
    missing = [path for path in required if not path.exists()]
    if verbose:
        if missing:
            print("Missing required files:")
            for path in missing:
                print(f"  - {display_path(path)}")
        else:
            print("All required GS2 files/resources are present.")
    return not missing


def generate_translation_json() -> None:
    print(f"[INFO] Translation JSON target: {display_path(TRANSLATION_JSON)}")
    if TRANSLATION_JSON.exists():
        print(f"[OK] Ukrainian translation JSON already exists: {display_path(TRANSLATION_JSON)}")
        print("[INFO] Existing file was not overwritten.")
        save_state(translation_json={"path": display_path(TRANSLATION_JSON), "at": now()})
        return
    if not required_files_ok(verbose=False):
        required_files_ok(verbose=True)
        return
    print("[INFO] Generating translation template from the clean GS2 ROM...")
    if not run_python(LOCALIZER, "--analysis-only"):
        return
    shutil.copy2(TEMPLATE_JSON, TRANSLATION_JSON)
    print(f"[OK] Created Ukrainian translation JSON: {display_path(TRANSLATION_JSON)}")
    print(f"[OK] File name: {TRANSLATION_JSON.name}")
    save_state(translation_json={"path": display_path(TRANSLATION_JSON), "at": now()})


def build_rom() -> bool:
    if not required_files_ok(verbose=False):
        required_files_ok(verbose=True)
        return False
    if not run_python(LOCALIZER):
        return False
    save_state(stage4_build={"path": display_path(OUTPUT_ROM), "at": now()})
    return True


def run_verifier(rom_path: Path | None = None, label: str = "intermediate ROM") -> bool:
    target_rom = rom_path or OUTPUT_ROM
    if not target_rom.exists():
        print(f"No {label} found: {display_path(target_rom)}")
        if rom_path is None:
            print("Run option 7 to build the final ROM.")
        return False
    if not STRUCTURE_REPORT.exists():
        print(f"Missing structure report: {display_path(STRUCTURE_REPORT)}")
        print("Run option 7 to rebuild the ROM and verifier inputs.")
        return False
    print(f"[INFO] Verifying {label}: {display_path(target_rom)}")
    if not run_python(
        VERIFIER,
        "--rom",
        str(target_rom),
        "--structure",
        str(STRUCTURE_REPORT),
        "--output-dir",
        str(TEMP_DIR),
    ):
        return False
    save_state(verification={"rom": display_path(target_rom), "path": display_path(VERIFY_REPORT), "at": now()})
    return True


def run_final_verifier() -> bool:
    final_rom = latest_final_rom()
    if final_rom is None:
        print("No final ROM found in output/Rom/. Run option 7 first.")
        return False
    return run_verifier(final_rom, "final ROM")


def open_output_folder() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Opening output folder: {display_path(OUTPUT_DIR)}")
    open_path(OUTPUT_DIR)


def latest_final_rom() -> Path | None:
    if not FINAL_OUTPUT_DIR.exists():
        return None
    roms = sorted(FINAL_OUTPUT_DIR.glob("Golden_Sun_2_UA_*.gba"), key=lambda path: path.stat().st_mtime)
    return roms[-1] if roms else None


def final_font_inputs_ok(verbose: bool = True) -> bool:
    required = [
        ("Main font injector", MAIN_FONT_INJECT_SCRIPT),
        ("Edited main font BIN", MAIN_FONT_BIN),
        ("Edited main font width JSON", MAIN_FONT_JSON),
        ("Secondary font injector", SECONDARY_FONT_INJECT_SCRIPT),
        ("Edited secondary font BIN", SECONDARY_FONT_BIN),
        ("Edited secondary font width JSON", SECONDARY_FONT_JSON),
    ]
    ok = True
    if verbose:
        print("\nFinal font inputs:")
    for label, path in required:
        exists = path.exists()
        ok = ok and exists
        if verbose:
            marker = "OK" if exists else "missing"
            print(f"  {marker:7} {label}: {display_path(path)}")
    return ok


def build_final_rom() -> None:
    if not required_files_ok(verbose=False):
        required_files_ok(verbose=True)
        return
    if not TRANSLATION_JSON.exists():
        print("Create ukrainian_translation.json first with option 2.")
        return
    if not final_font_inputs_ok(verbose=True):
        print("\n[ERROR] Final font inputs are missing.")
        print("Run the missing_glyphs extract scripts first, edit fonts/width JSONs, then rerun final build.")
        return
    if not build_rom():
        return
    if not run_verifier(OUTPUT_ROM, "intermediate ROM"):
        return

    FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="final_build_", dir=TEMP_DIR) as tmp_name:
        tmp_dir = Path(tmp_name)
        after_main_font = tmp_dir / "after_main_font.gba"
        after_secondary_font = tmp_dir / "after_secondary_font.gba"

        print("\nInjecting edited main dialogue font...")
        if not run_python(
            MAIN_FONT_INJECT_SCRIPT,
            "--rom",
            str(OUTPUT_ROM),
            "--font-bin",
            str(MAIN_FONT_BIN),
            "--metadata",
            str(MAIN_FONT_JSON),
            "--out-rom",
            str(after_main_font),
        ):
            return

        print("\nInjecting edited secondary menu/save font...")
        if not run_python(
            SECONDARY_FONT_INJECT_SCRIPT,
            "--rom",
            str(after_main_font),
            "--font-bin",
            str(SECONDARY_FONT_BIN),
            "--metadata",
            str(SECONDARY_FONT_JSON),
            "--out-rom",
            str(after_secondary_font),
        ):
            return

        final_rom = FINAL_OUTPUT_DIR / f"Golden_Sun_2_UA_{final_datetime_mark()}.gba"
        shutil.copy2(after_secondary_font, final_rom)

    save_state(final_build={"path": display_path(final_rom), "at": now()})
    print(f"[OK] Final ROM: {final_rom}")
    run_verifier(final_rom, "final ROM")
    open_path(FINAL_OUTPUT_DIR)


def show_status() -> None:
    print("\nStatus:")
    for label, path in [
        ("Clean GS2 ROM", GS2_ENG_ROM),
        ("Baseline", BASELINE_JSON),
        ("Font tiles", FONT_TILES),
        ("Font widths", FONT_WIDTHS),
        ("Secondary font BIN", SECONDARY_FONT_RESOURCE),
        ("Secondary font JSON", SECONDARY_FONT_RESOURCE_JSON),
        ("Translation JSON", TRANSLATION_JSON),
        ("Edited main font BIN", MAIN_FONT_BIN),
        ("Edited main font width JSON", MAIN_FONT_JSON),
        ("Edited secondary font BIN", SECONDARY_FONT_BIN),
        ("Edited secondary font width JSON", SECONDARY_FONT_JSON),
        ("Built ROM", OUTPUT_ROM),
        ("Verification report", VERIFY_REPORT),
    ]:
        marker = "OK" if path.exists() else "missing"
        print(f"  {marker:7} {label}: {display_path(path)}")
    final_rom = latest_final_rom()
    if final_rom:
        print(f"  OK      Latest final ROM: {display_path(final_rom)}")
    state = load_state()
    if state:
        print(f"\n  State file: {display_path(STATE_FILE)}")
        print(f"  Last state update: {state.get('updated_at', 'unknown')}")


def suggested_next_action() -> str:
    if not required_files_ok(verbose=False):
        return "Run option 1 and add missing GS2 files/resources."
    if not TRANSLATION_JSON.exists():
        return "Run option 2 to generate ukrainian_translation.json."
    final_rom = latest_final_rom()
    if final_rom is None:
        return "Run option 7 to build the final timestamped ROM."
    if not VERIFY_REPORT.exists():
        return "Run option 4 to verify the final ROM."
    try:
        report = json.loads(VERIFY_REPORT.read_text(encoding="utf-8"))
        if not report.get("pass"):
            return "Verifier has issues; inspect verification_report.json."
        if Path(report.get("rom", "")) != final_rom:
            return "Run option 4 to verify the latest final ROM."
    except json.JSONDecodeError:
        return "Verifier report is unreadable; rerun option 4."
    return "Everything is built and verified. Edit translations and rerun option 7 when needed."


def print_header() -> None:
    print("\nGolden Sun 2 Localization Helper")
    print("=" * 34)
    print("This helper builds a localized Golden Sun 2 ROM.")
    print("Required user-provided file in GS2/input/:")
    print("  - golden_sun_2_eng.gba  (clean English GS2 ROM)")
    print("\nBundled Cyrillic font and hook resources are stored in GS2/code/resources/.")
    print("Translations are edited in:")
    print(f"  - {display_path(TRANSLATION_JSON)}")
    print(f"\nSuggested next action: {suggested_next_action()}")


def menu() -> None:
    while True:
        print("\nMenu:")
        print("  1. Check required GS2 files/resources")
        print("  2. Generate Ukrainian translation JSON")
        print("  4. Run verifier for final ROM")
        print("  5. Open output folder")
        print("  6. Show status")
        print("  7. Build final ROM")
        print("  8. Split translations JSON")
        print("  9. Merge translation parts")
        print("  0. Exit")
        choice = input("> ").strip()
        if choice == "1":
            print("[INFO] Checking required files/resources...", flush=True)
            required_files_ok(verbose=True)
        elif choice == "2":
            print("[INFO] Generating Ukrainian translation JSON...", flush=True)
            generate_translation_json()
        elif choice == "3":
            print("[INFO] Option 3 was removed. Use option 7 to build the final ROM.", flush=True)
        elif choice == "4":
            print("[INFO] Running verifier for the latest final ROM...", flush=True)
            run_final_verifier()
        elif choice == "5":
            print("[INFO] Opening output folder...", flush=True)
            open_output_folder()
        elif choice == "6":
            print("[INFO] Showing project status...", flush=True)
            show_status()
        elif choice == "7":
            print("[INFO] Building final ROM...", flush=True)
            build_final_rom()
        elif choice == "8":
            print("[INFO] Splitting translations JSON...", flush=True)
            split_translations()
        elif choice == "9":
            print("[INFO] Merging translation parts...", flush=True)
            merge_translations()
        elif choice == "0":
            print("[INFO] Exiting.", flush=True)
            return
        else:
            print("Unknown option.")


def main() -> None:
    print_header()
    menu()


if __name__ == "__main__":
    main()
