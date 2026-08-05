#!/usr/bin/env python3
"""Render assets/demo.gif: a terminal-style animation of the real demo run.

Captures a live `agent-report-card demo --judge none -v` (fixture bot,
ephemeral port) and replays it line by line. Needs Pillow, which is not a
package dependency; run with any interpreter that has it:

    python3 scripts/make_gif.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ARC = ROOT / ".venv" / "bin" / "agent-report-card"

BG = "#1a1a19"
FG = "#d6d5cd"
PROMPT = "#0ca30c"
MUTED = "#898781"
GOOD = "#3fb950"
BAD = "#f85149"
AMBER = "#e8a112"

W, PAD, LINE_H, FONT_SIZE = 860, 22, 19, 13


def load_font():
    for path in ("/System/Library/Fonts/Menlo.ttc",
                 "/System/Library/Fonts/Monaco.ttf"):
        try:
            return ImageFont.truetype(path, FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default()


def color_for(line):
    if line.startswith("$"):
        return PROMPT
    if "FAIL" in line:
        return BAD
    if re.search(r"\] q\d", line) and ": ok" in line:
        return GOOD
    if line.startswith("accuracy") or line.startswith("  ·"):
        return AMBER
    if line.startswith(("wrote", "fixture bot", "port 8000")):
        return MUTED
    return FG


def frame(lines, font, height):
    img = Image.new("RGB", (W, height), BG)
    draw = ImageDraw.Draw(img)
    y = PAD
    for text, color in lines:
        draw.text((PAD, y), text, fill=color, font=font)
        y += LINE_H
    return img


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            [str(ARC), "demo", "--judge", "none", "-v"],
            capture_output=True, text=True, cwd=tmp).stdout
    raw = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    # the ephemeral-port fallback lines vary by machine; show the canonical port
    raw = [re.sub(r"127\.0\.0\.1:\d+", "127.0.0.1:8000", ln)
           for ln in raw if not ln.startswith("port 8000 is in use")]
    body = []
    for ln in raw:  # wrap wide lines at a separator so nothing clips
        while len(ln) > 100 and " · " in ln[:100]:
            cut = ln[:100].rfind(" · ")
            body.append(ln[:cut])
            ln = "  · " + ln[cut + 3:]
        body.append(ln)
    font = load_font()
    height = PAD * 2 + LINE_H * (len(body) + 2)

    lines = [("$ agent-report-card demo --judge none", PROMPT)]
    frames = [frame(lines, font, height)]
    durations = [1100]
    for ln in body:
        lines.append((ln, color_for(ln)))
        frames.append(frame(lines, font, height))
        durations.append(90 if re.search(r"\] q\d", ln) else 350)
    durations[-1] = 5000  # hold the banner

    dest = ROOT / "assets" / "demo.gif"
    dest.parent.mkdir(exist_ok=True)
    frames[0].save(dest, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    print(f"wrote {dest} ({dest.stat().st_size // 1024} KB, "
          f"{len(frames)} frames)")


if __name__ == "__main__":
    sys.exit(main())
