from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import generate


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="osu_autogen", description="Generate an osu!standard beatmap from MP3/MP4 audio.")
    p.add_argument("input", type=Path, help="MP3 or MP4 (or any ffmpeg-readable) file")
    p.add_argument("-s", "--stars", type=float, default=4.0, help="target star rating (default 4.0)")
    p.add_argument("-o", "--out", type=Path, default=Path("output"), help="output folder")
    p.add_argument("--title"), p.add_argument("--artist")
    p.add_argument("--creator", default="osu-autogen")
    p.add_argument("--bpm", type=float, help="override detected BPM")
    p.add_argument("--offset-ms", type=float, help="nudge the detected timing offset (ms, +/-)")
    p.add_argument("--seed", type=int, default=1, help="random seed (different seed = different layout)")
    p.add_argument("--tolerance", type=float, default=0.15, help="acceptable star error")
    p.add_argument("--no-video", action="store_true", help="don't include a background video even for MP4 input")
    p.add_argument("--video-offset-ms", type=int, default=0, help="shift the video vs the audio (ms, +/-)")
    p.add_argument("--no-measure", action="store_true", help="skip star measurement / feedback loop")
    a = p.parse_args(argv)

    r = generate(a.input, a.stars, a.out, title=a.title, artist=a.artist, creator=a.creator, seed=a.seed,
                 bpm=a.bpm, offset_nudge_ms=a.offset_ms, tolerance=a.tolerance, measure=not a.no_measure,
                 video=not a.no_video, video_offset_ms=a.video_offset_ms)
    got = f"{r.measured_star:.2f}*" if r.measured_star is not None else "not measured"
    print(f"\nDone: {r.n_objects} objects ({r.n_sliders} sliders), star rating {got} (target {r.target_star:.2f}*)")
    print(f"AR {r.ar}  CS {r.cs}  OD {r.od}  HP {r.hp}   BPM {r.bpm:.2f}")
    print(f"Double-click to import in osu!: {r.osz_path}")
    return 0
