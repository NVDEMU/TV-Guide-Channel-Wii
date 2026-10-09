#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOL="${TV_GUIDE_DOL:-$ROOT/wii/tv-guide-usa.dol}"
BASE_WAD="${TV_GUIDE_BASE_WAD:-}"
BANNER_BIN="${TV_GUIDE_BANNER_BIN:-$ROOT/channel-assets/banner.bin}"
ICON_BIN="${TV_GUIDE_ICON_BIN:-$ROOT/channel-assets/icon.bin}"
OUTPUT="${TV_GUIDE_WAD_OUTPUT:-$ROOT/build/TV-Guide-USA.wad}"
WADPAKK_DIR="${WADPAKK_DIR:-$ROOT/.tools/WadPakk}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -s "$DOL" ]] || die "Missing Wii DOL: $DOL. Build it first with make -C wii."
[[ -n "$BASE_WAD" && -s "$BASE_WAD" ]] || die "Set TV_GUIDE_BASE_WAD to a WAD file you are authorized to use. Do not commit it to this repository."
[[ -s "$BANNER_BIN" ]] || die "Missing U8 banner archive: $BANNER_BIN. See channel-assets/README.md."
[[ -s "$ICON_BIN" ]] || die "Missing U8 icon archive: $ICON_BIN. See channel-assets/README.md."
command -v dotnet >/dev/null 2>&1 || die ".NET 8 SDK is required to build WadPakk."

if [[ ! -f "$WADPAKK_DIR/WadPakk.csproj" ]]; then
  mkdir -p "$(dirname "$WADPAKK_DIR")"
  git clone --depth 1 https://github.com/davi-x86/WadPakk.git "$WADPAKK_DIR"
fi

mkdir -p "$(dirname "$OUTPUT")"
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
printf '\nWAD created: %s\n' "$OUTPUT"
printf 'Test the DOL in Dolphin and Homebrew Channel before installing the WAD.\n'
