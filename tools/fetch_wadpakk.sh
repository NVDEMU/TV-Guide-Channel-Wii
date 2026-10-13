#!/usr/bin/env bash
# Fetch a known-good WadPakk revision so CI does not break when upstream main moves.
set -euo pipefail

DEST="${1:-.tools/WadPakk}"
REPOSITORY="https://github.com/davi-x86/WadPakk.git"
PINNED_COMMIT="155a00d4b2180eab968cf5b2f5da68f3c3ebdafd"

if [[ -d "$DEST/.git" ]]; then
  git -C "$DEST" remote remove origin >/dev/null 2>&1 || true
else
  rm -rf "$DEST"
  mkdir -p "$(dirname "$DEST")"
  git init "$DEST" >/dev/null
fi

git -C "$DEST" remote add origin "$REPOSITORY"
git -C "$DEST" fetch --depth 1 origin "$PINNED_COMMIT"
git -C "$DEST" checkout --detach FETCH_HEAD
actual="$(git -C "$DEST" rev-parse HEAD)"
[[ "$actual" == "$PINNED_COMMIT" ]] || {
  echo "ERROR: expected WadPakk $PINNED_COMMIT, got $actual" >&2
  exit 1
}
[[ -s "$DEST/WadPakk.csproj" && -s "$DEST/Program.cs" ]] || {
  echo "ERROR: pinned WadPakk checkout is incomplete." >&2
  exit 1
}
echo "Using pinned WadPakk revision $actual"
