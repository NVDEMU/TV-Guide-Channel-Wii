#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOL="${TV_GUIDE_DOL:-$ROOT/wii/tv-guide-usa.dol}"
EXPLICIT_BASE_WAD="${TV_GUIDE_BASE_WAD:-}"
EXPLICIT_BANNER="${TV_GUIDE_BANNER_BIN:-}"
EXPLICIT_ICON="${TV_GUIDE_ICON_BIN:-}"
OUTPUT="${TV_GUIDE_WAD_OUTPUT:-$ROOT/build/TV-Guide-USA.wad}"
WADPAKK_DIR="${WADPAKK_DIR:-$ROOT/.tools/WadPakk}"
ASSET_DIR="$ROOT/build/base-assets"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ -s "$DOL" ]] || die "Missing Wii DOL: $DOL. Build it first with make -C wii."
command -v python3 >/dev/null 2>&1 || die "Python 3 is required for WAD validation."
command -v dotnet >/dev/null 2>&1 || die ".NET 8 SDK is required to build WadPakk."
command -v git >/dev/null 2>&1 || die "Git is required to fetch the open-source packager."

if [[ ! -f "$WADPAKK_DIR/WadPakk.csproj" ]]; then
  mkdir -p "$(dirname "$WADPAKK_DIR")"
  git clone --depth 1 https://github.com/davi-x86/WadPakk.git "$WADPAKK_DIR"
fi

# No Japanese TV no Tomo WAD is required. Use WadPakk's bundled generic
# homebrew-channel template by default. A private base can be overridden for
# development, but public CI does not require it and never stores it.
BASE_WAD="$EXPLICIT_BASE_WAD"
if [[ -z "$BASE_WAD" ]]; then BASE_WAD="$WADPAKK_DIR/Resources/base.wad"; fi
[[ -s "$BASE_WAD" ]] || die "WAD template not found: $BASE_WAD."
python3 "$ROOT/tools/inspect_wad.py" "$BASE_WAD" >/dev/null || die "WAD template structure validation failed."

python3 "$ROOT/tools/prepare_wad_tool.py" "$WADPAKK_DIR"
mkdir -p "$(dirname "$OUTPUT")"
BANNER_BIN="$EXPLICIT_BANNER"
ICON_BIN="$EXPLICIT_ICON"

# Use valid banner/icon archive containers from the generic template until
# the channel gets its own authored Wii-style English graphics.
if [[ -z "$BANNER_BIN" || ! -s "$BANNER_BIN" || -z "$ICON_BIN" || ! -s "$ICON_BIN" ]]; then
  mkdir -p "$ASSET_DIR"
  dotnet run --project "$ROOT/tools/wad-assets/WadAssetExtractor.csproj" \
    --configuration Release -p:WADPAKK_DIR="$WADPAKK_DIR" -- "$BASE_WAD" "$ASSET_DIR"
  [[ -n "$BANNER_BIN" && -s "$BANNER_BIN" ]] || BANNER_BIN="$ASSET_DIR/banner.bin"
  [[ -n "$ICON_BIN" && -s "$ICON_BIN" ]] || ICON_BIN="$ASSET_DIR/icon.bin"
  printf 'NOTE: Using generic template banner/icon archives; metadata will say TV Guide USA.\n'
fi

[[ -s "$BANNER_BIN" ]] || die "Missing banner archive: $BANNER_BIN."
[[ -s "$ICON_BIN" ]] || die "Missing icon archive: $ICON_BIN."

printf 'Building TV Guide USA WAD\n'
printf '  DOL: %s\n  Template: %s\n  Banner: %s\n  Icon: %s\n  Output: %s\n' \
  "$DOL" "$BASE_WAD" "$BANNER_BIN" "$ICON_BIN" "$OUTPUT"

dotnet run --project "$WADPAKK_DIR/WadPakk.csproj" --configuration Release -- \
  pack -base "$BASE_WAD" -banner "$BANNER_BIN" -icon "$ICON_BIN" \
  -dol "$DOL" -id TVG1 -name "TV Guide USA" -ios 58 -o "$OUTPUT"

[[ -s "$OUTPUT" ]] || die "WAD packager did not create the expected output."
python3 "$ROOT/tools/inspect_wad.py" "$OUTPUT" >/dev/null || die "Generated WAD failed structural validation."
printf '\nWAD created and structurally validated: %s\n' "$OUTPUT"
printf 'Note: this standalone prototype is not yet a translation of the original TV no Tomo UI/assets. Test in Dolphin before using a real Wii.\n'
