# Golden Sun Ukrainian Localization Tools

## Ukrainian translation is included in this repo for Golden Sun The Lost Age
If you'd like to just make a ROM with translations just run main.py and pick option 7.
As the result you'll get a ready to play ROM

This repository contains two standalone workspaces for building Ukrainian-localized ROMs:

- `GS1/` — Golden Sun 1
- `GS2/` — Golden Sun 2: The Lost Age

Both workspaces use the same layout and menu-driven workflow. They start from a clean English ROM, inject bundled Cyrillic-capable font resources, apply translations from editable JSON, verify the result, and write final ROMs into an output folder.

> ROM files are not included. You must provide your own clean English GBA ROMs.

## Folder layout

Each game folder has the same structure:

```text
GS1/ or GS2/
├── input/   clean user-provided ROM only
├── code/    scripts, compiler, verifier, font tools, bundled resources
└── output/  editable translations, editable fonts, generated reports, final ROMs
```

Important output locations:

- `output/ukrainian_translation.json` — main editable translation file.
- `output/Rom/` — timestamped final ROMs for testing or playing.
- `output/missing_glyphs/` — editable font `.bin` files and width/header JSON files.
- `output/json_splitter_parts/` — split translation chunks, useful for editing large JSON files.
- `output/temp/` — intermediate ROMs, reports, dumps, and generated helper files. Users normally do not need to edit this folder.

Legacy research code may exist outside `GS1/` and `GS2/`, but normal users should use only the `GS1/` and `GS2/` folders.

## Requirements

- Python 3.10+ recommended.
- A clean English Golden Sun ROM for the game you want to build.

Required input file names:

| Game | Required file |
| --- | --- |
| GS1 | `GS1/input/golden_sun_1_eng.gba` |
| GS2 | `GS2/input/golden_sun_2_eng.gba` |

The scripts never modify files in `input/` in place.

## Quick start

From the repository root:

```bash
python3 GS1/code/main.py
```

or:

```bash
python3 GS2/code/main.py
```

On Windows, use `python` instead of `python3` if that is how Python is installed:

```bat
python GS1\code\main.py
python GS2\code\main.py
```

## Recommended workflow

Use the menu in each workspace:

1. `Check required files/resources` — confirms the clean ROM and bundled build resources are present.
2. `Generate Ukrainian translation JSON` — creates `output/ukrainian_translation.json` if it does not already exist. It does not overwrite an existing translation file.
3. Edit `output/ukrainian_translation.json`, filling `text_ukr` values.
4. `Build final ROM` — builds, verifies, injects edited fonts, and writes a timestamped final ROM to `output/Rom/`.
5. `Run verifier for final ROM` — verifies the latest final ROM again if needed.

Menu options are intentionally the same for GS1 and GS2:

| Option | Action |
| --- | --- |
| 1 | Check required files/resources |
| 2 | Generate Ukrainian translation JSON |
| 4 | Run verifier for final ROM |
| 5 | Open output folder |
| 6 | Show status |
| 7 | Build final ROM |
| 8 | Split translations JSON |
| 9 | Merge translation parts |
| 0 | Exit |

Option `3` is intentionally removed. Use option `7` for final ROM builds.

## Translation JSON

The active translation file is:

```text
output/ukrainian_translation.json
```

Each entry contains English source text and an editable Ukrainian field, usually `text_ukr`:

```json
{
  "id": 123,
  "text_eng": "Example English text[MESSAGE_END]",
  "text_ukr": "Приклад українського тексту[MESSAGE_END]"
}
```

Keep control tokens such as `[LINE_BREAK]`, `[TEXTBOX_BREAK]`, `[MESSAGE_END]`, `[PAUSE]`, and `<CTRL_XX>` intact unless you know what they do. These tokens are part of the game text format.

For easier editing, use:

- option `8` to split the large JSON into `output/json_splitter_parts/`
- option `9` to merge edited parts back into `output/ukrainian_translation.json`

## Fonts and Ukrainian characters

The build uses Cyrillic-capable font resources so Ukrainian text can be displayed from a clean English ROM.

There are two font systems:

- Main dialogue/name font: `output/missing_glyphs/main_dialog_font_table/`
- Secondary menu/save-screen font: `output/missing_glyphs/secondary_menu_save_font_table/`

Font graphics are stored as `.bin` files intended for tile editors such as YY-CHR. Width and renderer metadata are stored in matching `.json` files.

For the secondary menu/save font, do not delete `record_header_hex` fields from JSON metadata. Those bytes are required by the game renderer; without them some Cyrillic letters, including `Г`, can display incorrectly.

## YY-CHR:

- secondary_menu_font Graphic format "4BPP GBA", Pattern "FC/NES x8"
- main_dialog_font Graphic format "4BPP GBA", Pattern "FC/NES x8"


## Final ROMs and verification

Final ROMs are written here:

```text
GS1/output/Rom/
GS2/output/Rom/
```

They use timestamped names such as:

```text
Golden_Sun_1_UA_YYYY-MM-DD-HH-MM.gba
Golden_Sun_2_UA_YYYY-MM-DD-HH-MM.gba
```

The final build process also runs the verifier. Verification reports and intermediate dumps are written to `output/temp/`.

## Troubleshooting

If option `1` reports missing files, check that the clean English ROM has the exact required file name in the correct `input/` folder.

If option `2` says the translation JSON already exists, that is expected. The script protects your edits and will not overwrite the existing file.

If Ukrainian text appears as wrong symbols, confirm the text is entered in `text_ukr` and that the final ROM was built with option `7`.

If a font glyph displays incorrectly, check the relevant files in `output/missing_glyphs/`. For secondary menu/save glyphs, preserve both `width_pixels` and `record_header_hex` in the JSON metadata.

If you are unsure what to edit, use option `6` to show current project status and paths.




# License & Legal Disclaimers

This repository contains a fan translation of the **Golden Sun** game series (including *Golden Sun* and/or *Golden Sun: The Lost Age*) for the Game Boy Advance (GBA) handheld console, as well as utilities and scripts for automating localization, extraction, and reverse-engineering workflows.

---

## 1. Legal Disclaimer & Trademarks

- **Trademarks & Intellectual Property:**
  All rights, titles, and intellectual property associated with *Golden Sun*, including registered trademarks, logos, characters, storyline, graphics, and audio assets, belong exclusively to **Nintendo Co., Ltd.** and **Camelot Software Planning**.
- **Non-Commercial & Educational Purpose:**
  This project is a non-commercial, non-profit fan-made effort created solely for educational purposes, digital preservation, and promoting the game series within the Ukrainian-speaking community.
- **No Original ROMs or Copyrighted Binary Distribution:**
  This repository **DOES NOT contain, host, or distribute**:
  - Original Game Boy Advance ROM images or cartridge dumps.
  - Copyrighted proprietary Nintendo system code.
  - Commercial game assets owned by Nintendo or Camelot.
- **User Requirements:**
  Patch files (e.g., IPS, BPS, UPS) and utilities provided in this repository are intended exclusively for use with legally acquired game backups owned by the end-user. The maintainer of this repository does not support or condone software piracy.

---

## 2. Tools & Source Code License

All original custom source code, utility scripts (e.g., Python extraction/repacking tools), and build automation scripts authored by the maintainers of this repository are distributed under the **MIT License**.

```text
MIT License

Copyright (c) 2026 MBykhkalo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 3. Translation Assets & Text License

The localized text files, translation scripts, and custom graphics assets created for this project are licensed under the **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)**.

**Under this license, you are free to:**
- **Share:** Copy and redistribute the material in any medium or format.
- **Adapt:** Remix, transform, and build upon the material for non-commercial purposes.

**Under the following terms:**
- **Attribution:** You must give appropriate credit to the author(s) and provide a link to the original repository.
- **NonCommercial:** You may not use the material for commercial purposes or monetize derivative releases.

---

## 4. Limitation of Liability

The materials, scripts, and patch files in this repository are provided on an **"AS IS"** basis, without warranties of any kind, either express or implied. In no event shall the authors or maintainers be held liable for any data loss, save-file corruption, hardware damage, or legal issues resulting from the use or misuse of the contents of this repository.

