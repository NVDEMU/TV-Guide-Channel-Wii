#!/usr/bin/env python3
"""Prepare a local WadPakk checkout for TV Guide USA packaging.

This changes only the ignored, local third-party tool checkout. It removes the
upstream Windows-x86 runtime pins so .NET can run on macOS/Linux, and sets the
generated channel TMD region to USA.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


class PreparationError(RuntimeError):
    """Raised if the expected upstream WadPakk source cannot be patched."""


def prepare_wadpakk(directory: str | Path) -> None:
    root = Path(directory)
    project = root / "WadPakk.csproj"
    program = root / "Program.cs"
    if not project.is_file() or not program.is_file():
        raise PreparationError(f"Expected WadPakk.csproj and Program.cs in {root}")

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
            raise PreparationError(
                "Cannot set the USA title region: WadPakk's source layout changed."
            )
        program_text = program_text.replace(marker, marker + "\n" + region_line, 1)
    program.write_text(program_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wadpakk_directory", type=Path)
    args = parser.parse_args()
    try:
        prepare_wadpakk(args.wadpakk_directory)
    except (OSError, PreparationError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Prepared local WadPakk source for TV Guide USA: {args.wadpakk_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
