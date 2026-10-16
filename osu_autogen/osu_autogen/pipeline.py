"""End-to-end pipeline: audio -> analysis -> notes -> layout -> star-targeting loop -> .osu/.osz"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio, stars
from .analysis import AudioAnalysis, analyse
from .difficulty import MAX_D, global_settings, style_for
from .layout import build_objects
from .osu_writer import Metadata, render, write_osz
from .rhythm import select_notes


@dataclass
class Result:
    osu_path: Path
    osz_path: Path
    mp3_path: Path
    bpm: float
    offset_ms: float
    n_objects: int
    n_sliders: int
    target_star: float
    measured_star: float | None
    ar: float
    cs: float
    od: float
    hp: float
    history: list[tuple[float, float]]   # (effective difficulty d, measured stars)


def _slug(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip() or "map"


def _build(an: AudioAnalysis, target: float, d: float, seed: int, meta: Metadata, audio_name: str, version: str,
           media: dict | None = None):
    glob = global_settings(target)
    style = style_for(d)
    rng = np.random.default_rng(seed)
    notes = select_notes(an, style)
    objs = build_objects(notes, an.beat_len * 1000.0, an.offset * 1000.0, glob, style, rng)
    meta.version = version
    text = render(objs, glob, meta, audio_name, an.bpm, an.offset * 1000.0,
                  preview_ms=int(an.duration * 400), **(media or {}))
    return text, objs, glob


def generate(src: Path, target_star: float, out_dir: Path, *, title: str | None = None,
             artist: str | None = None, creator: str = "osu-autogen", seed: int = 1,
             bpm: float | None = None, offset_nudge_ms: float | None = None,
             tolerance: float = 0.15, max_iters: int = 12, measure: bool = True,
             video: bool = True, video_offset_ms: int = 0, log=print) -> Result:
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    title = title or src.stem
    artist = artist or "Unknown Artist"
    base = _slug(f"{artist} - {title}")

    mp3 = out_dir / f"{base}.mp3"
    log(f"[1/4] converting {src.name} -> {mp3.name}")
    audio.convert_to_mp3(src, mp3)

    media: dict = {}
    extras: list[Path] = []
    if video and audio.has_video_stream(src):
        log("      video detected: preparing background video + still image (can take a minute)")
        vid = audio.make_video(src, out_dir / f"{base}.mp4")
        img = audio.extract_frame(src, out_dir / f"{base}.jpg")
        extras = [vid, img]
        media = {"video": vid.name, "background": img.name, "video_offset_ms": video_offset_ms}

    log("[2/4] analysing audio")
    with tempfile.TemporaryDirectory() as tmp:
        wav = audio.decode_for_analysis(mp3, Path(tmp) / "a.wav")
        an = analyse(wav, bpm_override=bpm, offset_override_ms=offset_nudge_ms)
    log(f"      BPM {an.bpm:.2f}, first bar line at {an.offset * 1000:.0f} ms, length {an.duration:.1f}s")

    meta = Metadata(title=title, artist=artist, creator=creator)
    do_measure = measure and stars.available()
    if measure and not do_measure:
        log("      (rosu-pp-py not installed: skipping star measurement, one-shot generation)")

    log(f"[3/4] generating map for target {target_star:.2f}*")
    history: list[tuple[float, float]] = []
    best = None                                   # (error, text, objs, glob, d, star)
    d = float(target_star)
    lo = hi = None
    for it in range(max_iters if do_measure else 1):
        text, objs, glob = _build(an, target_star, d, seed, meta, mp3.name, f"Target {target_star:.1f}*", media)
        s = stars.measure(text) if do_measure else None
        if s is not None:
            history.append((d, s))
            log(f"      iter {it + 1}: d={d:.2f} -> {s:.2f}*  ({len(objs)} objects)")
        err = abs(s - target_star) if s is not None else 0.0
        if best is None or err < best[0]:
            best = (err, text, objs, glob, d, s)
        if s is None or err <= tolerance:
            break
        if s < target_star:
            lo = (d, s)
        else:
            hi = (d, s)
        if lo and hi and hi[1] > lo[1]:           # bracketed: interpolate
            d = lo[0] + (target_star - lo[1]) * (hi[0] - lo[0]) / (hi[1] - lo[1])
        else:                                    # not yet bracketed: step proportionally
            d = d + (target_star - s) * 1.1
        d_new = float(np.clip(d, 0.3, MAX_D))
        if abs(d_new - history[-1][0]) < 0.02:      # pinned at the limit: target unreachable for this song
            log("      target star rating is beyond what this song's tempo/onsets allow; using closest")
            break
        d = d_new

    _, text, objs, glob, d_best, s_best = best
    if s_best is not None:                        # stamp the real rating into the difficulty name
        text = text.replace(f"Version:Target {target_star:.1f}*", f"Version:Auto {s_best:.2f}* (target {target_star:.1f})")

    log("[4/4] writing files")
    osu_name = f"{base} [{_slug('Auto ' + (f'{s_best:.2f}' if s_best else f'{target_star:.1f}'))}].osu"
    osu_path = out_dir / osu_name
    osu_path.write_text(text, encoding="utf-8")
    osz_path = write_osz(out_dir / f"{base}.osz", text, osu_name, mp3, extras)
    n_sliders = sum(1 for o in objs if o.slider)
    return Result(osu_path, osz_path, mp3, an.bpm, an.offset * 1000, len(objs), n_sliders, target_star,
                  s_best, glob.ar, glob.cs, glob.od, glob.hp, history)
