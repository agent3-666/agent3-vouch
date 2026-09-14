"""Render the demo video from the page, frame by frame, without recording anyone's screen.

Each beat is a still taken by headless Chrome at 1280x720; the terminal beat is a series of stills
that scroll. ffmpeg holds each frame for its share of the running time. The result is a silent mp4.

    python scripts/record_demo.py --data data/sepolia-seeded.json
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_demo import BEATS, build  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FRAMES = ROOT / "frames"
OUT = ROOT / "media" / "vouch-demo.mp4"

TERMINAL_FRAMES = 14
TERMINAL_SCROLL_TO = 2400


def shot(url: str, target: Path, profile: Path) -> None:
    """Take one frame.

    Headless Chrome on this machine writes the file and then hangs on the way out, so the timeout is
    expected and means nothing by itself. The frame on disk is what decides success.
    """
    command = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-extensions",
        f"--user-data-dir={profile}",
        "--window-size=1280,720",
        "--hide-scrollbars",
        f"--screenshot={target}",
        url,
    ]
    try:
        subprocess.run(command, capture_output=True, timeout=25)
    except subprocess.TimeoutExpired:
        subprocess.run(["pkill", "-f", str(profile)], capture_output=True)

    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"no frame produced for {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "sepolia-seeded.json"))
    parser.add_argument("--budget", type=float, default=120.0)
    args = parser.parse_args()

    demo, storyboard = build(Path(args.data), args.budget)
    page = f"file://{demo}"

    shutil.rmtree(FRAMES, ignore_errors=True)
    FRAMES.mkdir(parents=True)
    profile = FRAMES / "chrome-profile"

    plan: list[tuple[Path, float]] = []
    index = 0
    for name, seconds, _ in BEATS:
        if name == "terminal":
            per = seconds / TERMINAL_FRAMES
            for step in range(TERMINAL_FRAMES):
                scroll = round(TERMINAL_SCROLL_TO * step / (TERMINAL_FRAMES - 1))
                frame = FRAMES / f"{index:03d}.png"
                shot(f"{page}?beat=terminal&scroll={scroll}", frame, profile)
                plan.append((frame, per))
                index += 1
                print(f"  terminal frame {step + 1}/{TERMINAL_FRAMES}", flush=True)
        else:
            frame = FRAMES / f"{index:03d}.png"
            shot(f"{page}?beat={name}", frame, profile)
            plan.append((frame, float(seconds)))
            index += 1
            print(f"  {name}", flush=True)

    concat = FRAMES / "concat.txt"
    lines = []
    for frame, seconds in plan:
        lines.append(f"file '{frame.name}'")
        lines.append(f"duration {seconds:.3f}")
    lines.append(f"file '{plan[-1][0].name}'")  # ffmpeg needs the last frame repeated
    concat.write_text("\n".join(lines) + "\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-an",
            str(OUT),
        ],
        check=True,
    )
    total = sum(seconds for _, seconds in plan)
    print(f"\nwrote {OUT} ({total:.0f}s, {len(plan)} frames)\nwrote {storyboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
