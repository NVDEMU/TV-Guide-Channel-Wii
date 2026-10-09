#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOL="${TV_GUIDE_DOL:-$ROOT/wii/tv-guide-usa.dol}"
BASE_WAD="${TV_GUIDE_BASE_WAD:-}"
EXPLICIT_BANNER="${TV_GUIDE_BANNER_BIN:-}"
EXPLICIT_ICON="${TV_GUIDE_ICON_BIN:-}"
OUTPUT="${TV_GUIDE_WAD_OUTPUT:-$ROOT/build/TV-Guide-USA.wad}"
WADPAKK_DIR="${WADPAKK_DIR:-$ROOT/.tools/WadPakk}"
ASSET_DIR="$ROOT/build/base-assets"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

# Convenient local defaults if the user copies the uploaded WAD into the
# checkout root or ~/Wii. The private binary is never committed to GitHub.
if [[ -z "$BASE_WAD" ]]; then
  for candidate in \
    "$ROOT/TV no Toma (Japan) (Channel).wad" \
    "$ROOT/channel-assets/TV no Toma (Japan) (Channel).wad" \
    "$HOME/Wii/TV no Toma (Japan) (Channel).wad"; do
    if [[ -s "$candidate" ]]; then
      BASE_WAD="$candidate"
      break
    fi
  done
fi

[[ -s "$DOL" ]] || die "Missing Wii DOL: $DOL. Build it first with make -C wii."
[[ -n "$BASE_WAD" && -s "$BASE_WAD" ]] || die "Set TV_GUIDE_BASE_WAD to your local TV no Tomo/base WAD path. Do not commit it to this repository."
command -v python3 >/dev/null 2>&1 || die "Python 3 is required for WAD validation."
python3 "$ROOT/tools/inspect_wad.py" "$BASE_WAD" >/dev/null || die "Base WAD structure validation failed."
command -v dotnet >/dev/null 2>&1 || die ".NET 8 SDK is required to build WadPakk."
command -v git >/dev/null 2>&1 || die "Git is required to fetch the open-source packager."

if [[ ! -f "$WADPAKK_DIR/WadPakk.csproj" ]]; then
  mkdir -p "$(dirname "$WADPAKK_DIR")"
  git clone --depth 1 https://github.com/davi-x86/WadPakk.git "$WADPAKK_DIR"
fi

# WadPakk upstream pins Windows x86. Normalize the local clone for .NET on
# macOS/Linux and set the new channel's TMD region to the United States.
python3 - "$WADPAKK_DIR/WadPakk.csproj" "$WADPAKK_DIR/Program.cs" <<'PY'
from pathlib import Path
import re
import sys

project = Path(sys.argv[1])
program = Path(sys.argv[2])
if not project.is_file() or not program.is_file():
    raise SystemExit("The WadPakk source checkout is incomplete.")

project_text = project.read_text(encoding="utf-8-sig")
for tag in ("PlatformTarget", "RuntimeIdentifier"):
    project_text = re.sub(
        rf"\s*<{tag}>.*?</{tag}>", "", project_text, flags=re.DOTALL
    )
project.write_text(project_text, encoding="utf-8")

program_text = program.read_text(encoding="utf-8-sig")
marker = "WAD wad = WAD.Load(basePath);"
region_line = "        wad.Region = Region.USA; // TV Guide USA output region"
if region_line not in program_text:
    if marker not in program_text:
        raise SystemExit("Cannot patch WAD region: WadPakk source structure changed.")
    program_text = program_text.replace(marker, marker + "\n" + region_line, 1)
program.write_text(program_text, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT")"
BANNER_BIN="$EXPLICIT_BANNER"
ICON_BIN="$EXPLICIT_ICON"

# Reuse the base WAD's existing valid U8 banner/icon archives if custom
# US-English art has not been supplied. The channel title metadata and app UI
# become English; original imagery may still contain Japanese graphics.
if [[ -z "$BANNER_BIN" || ! -s "$BANNER_BIN" || -z "$ICON_BIN" || ! -s "$ICON_BIN" ]]; then
  mkdir -p "$ASSET_DIR"
  dotnet run --project "$ROOT/tools/wad-assets/WadAssetExtractor.csproj" \
    --configuration Release -p:WADPAKK_DIR="$WADPAKK_DIR" -- "$BASE_WAD" "$ASSET_DIR"
  [[ -n "$BANNER_BIN" && -s "$BANNER_BIN" ]] || BANNER_BIN="$ASSET_DIR/banner.bin"
  [[ -n "$ICON_BIN" && -s "$ICON_BIN" ]] || ICON_BIN="$ASSET_DIR/icon.bin"
  printf 'NOTE: Reusing original banner/icon art. Use TV_GUIDE_BANNER_BIN and TV_GUIDE_ICON_BIN for custom US-English art.\n'
fi

[[ -s "$BANNER_BIN" ]] || die "Missing banner archive: $BANNER_BIN."
[[ -s "$ICON_BIN" ]] || die "Missing icon archive: $ICON_BIN."

printf 'Building TV Guide USA WAD\n'
printf '  DOL:    %s\n  Base:   %s\n  Banner: %s\n  Icon:   %s\n  Output: %s\n' \
  "$DOL" "$BASE_WAD" "$BANNER_BIN" "$ICON_BIN" "$OUTPUT"

dotnet run --project "$WADPAKK_DIR/WadPakk.csproj" --configuration Release -- \
  pack \
  -base "$BASE_WAD" \
  -banner "$BANNER_BIN" \
  -icon "$ICON_BIN" \
  -dol "$DOL" \
  -id TVG1 \
  -name "TV Guide USA" \
  -ios 58 \
  -o "$OUTPUT"

[[ -s "$OUTPUT" ]] || die "WAD packager did not create the expected output."
python3 "$ROOT/tools/inspect_wad.py" "$OUTPUT" >/dev/null || die "Generated WAD failed structural validation."
printf '\nWAD created and structurally validated: %s\n' "$OUTPUT"
printf 'The current banner/icon may still contain Japanese imagery. Test in Dolphin before installing on a physical Wii.\n'
