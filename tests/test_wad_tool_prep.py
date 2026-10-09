from pathlib import Path

import pytest

from tools.prepare_wad_tool import PreparationError, prepare_wadpakk


def make_wadpakk(directory: Path) -> None:
    (directory / "WadPakk.csproj").write_text(
        """<Project><PropertyGroup>
<PlatformTarget>x86</PlatformTarget>
<RuntimeIdentifier>win-x86</RuntimeIdentifier>
<TargetFramework>net8.0</TargetFramework>
</PropertyGroup></Project>""",
        encoding="utf-8",
    )
    (directory / "Program.cs").write_text(
        """using libWiiSharp;
WAD wad = WAD.Load(basePath);
if (!wad.HasBanner) throw new Exception();
""",
        encoding="utf-8",
    )


def test_prepare_removes_windows_runtime_pins_and_sets_usa_region(tmp_path: Path) -> None:
    make_wadpakk(tmp_path)
    prepare_wadpakk(tmp_path)
    project = (tmp_path / "WadPakk.csproj").read_text(encoding="utf-8")
    program = (tmp_path / "Program.cs").read_text(encoding="utf-8")
    assert "PlatformTarget" not in project
    assert "RuntimeIdentifier" not in project
    assert "wad.Region = Region.USA;" in program
    prepare_wadpakk(tmp_path)
    assert program == (tmp_path / "Program.cs").read_text(encoding="utf-8")


def test_prepare_fails_if_source_layout_changed(tmp_path: Path) -> None:
    make_wadpakk(tmp_path)
    (tmp_path / "Program.cs").write_text("Console.WriteLine(\"different\");", encoding="utf-8")
    with pytest.raises(PreparationError, match="source layout changed"):
        prepare_wadpakk(tmp_path)
