#!/usr/bin/env python3
"""Verify SplitMergedScripts.py against a MergedScripts.txt fixture."""

from pathlib import Path
import shutil
import tempfile

from SplitMergedScripts import split_merged_scripts

LINE_A = (
    'for %%t in ("_input\\*.*") DO ffmpeg -y -i "%%t" -filter_complex '
    '"[0:v]hflip[v1];[0:v][v1]overlay=1:enable=\'gte(mod(t,5),3)\':x=0:y=0;'
    '[0:a]volume=6[a1];amovie=aud/bg2.mp4:loop=9999,volume=1[a2];'
    '[a1][a2]amix=duration=shortest" -vcodec libx264 '
    '"_output\\%%~nt.mp4"'
)
LINE_B = (
    'for %%t in ("_input\\*.*") DO ffmpeg -y -ss 4 -i "%%t" -i "%%t" '
    '-filter_complex "pan=stereo| FL < FL + 0.5*FC | FR < FR + 2*FC" '
    '"_output\\%%~nt.mp4"'
)

MERGED = "\n".join(
    [
        "Script 1  {2G Flipped Moving Repeat.bat}",
        "",
        "",
        "",
        LINE_A,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "Script 2  {2O Repeat _ Center Zoom In Out.bat}",
        "",
        "",
        "",
        LINE_B,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="split-bats-"))
    try:
        (tmp / "MergedScripts.txt").write_text(MERGED, encoding="utf-8")
        created = split_merged_scripts(tmp)
        assert created == [
            "2G Flipped Moving Repeat.bat",
            "2O Repeat _ Center Zoom In Out.bat",
        ], created
        a = (tmp / created[0]).read_text(encoding="utf-8").replace("\r\n", "\n")
        b = (tmp / created[1]).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert a == LINE_A + "\n", repr(a)
        assert b == LINE_B + "\n", repr(b)
        assert "Script " not in a and "Script " not in b
        print("ok: extracted", len(created), "files with original names")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
