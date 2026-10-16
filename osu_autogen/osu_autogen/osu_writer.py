"""Serialise hit objects + settings to osu! file format v14 and bundle an .osz."""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .difficulty import GlobalSettings
from .layout import HitObject


@dataclass
class Metadata:
    title: str = "Untitled"
    artist: str = "Unknown Artist"
    creator: str = "osu-autogen"
    version: str = "Auto"
    tags: str = "autogen"


def _safe(s: str) -> str:
    return re.sub(r"[\r\n]+", " ", s).strip()


def object_line(o: HitObject) -> str:
    combo = 4 if o.new_combo else 0
    if o.slider is None:
        return f"{o.x},{o.y},{o.time_ms},{1 | combo},0,0:0:0:0:"
    s = o.slider
    pts = "|".join(f"{x}:{y}" for x, y in s.points)
    edges = "|".join(["0"] * (s.slides + 1))
    sets = "|".join(["0:0"] * (s.slides + 1))
    return f"{o.x},{o.y},{o.time_ms},{2 | combo},0,{s.curve}|{pts},{s.slides},{s.length},{edges},{sets},0:0:0:0:"


def render(objects: list[HitObject], glob: GlobalSettings, meta: Metadata, audio_filename: str,
           bpm: float, offset_ms: float, preview_ms: int = -1, video: str | None = None,
           background: str | None = None, video_offset_ms: int = 0) -> str:
    beat_len = 60000.0 / bpm
    lines = [
        "osu file format v14", "",
        "[General]",
        f"AudioFilename: {audio_filename}", "AudioLeadIn: 0", f"PreviewTime: {preview_ms}",
        "Countdown: 0", "SampleSet: Normal", "StackLeniency: 0.7", "Mode: 0",
        "LetterboxInBreaks: 0", "WidescreenStoryboard: 0", "",
        "[Editor]", "DistanceSpacing: 1", "BeatDivisor: 4", "GridSize: 32", "TimelineZoom: 1", "",
        "[Metadata]",
        f"Title:{_safe(meta.title)}", f"TitleUnicode:{_safe(meta.title)}",
        f"Artist:{_safe(meta.artist)}", f"ArtistUnicode:{_safe(meta.artist)}",
        f"Creator:{_safe(meta.creator)}", f"Version:{_safe(meta.version)}",
        "Source:", f"Tags:{_safe(meta.tags)}", "BeatmapID:0", "BeatmapSetID:-1", "",
        "[Difficulty]",
        f"HPDrainRate:{glob.hp}", f"CircleSize:{glob.cs}", f"OverallDifficulty:{glob.od}",
        f"ApproachRate:{glob.ar}", f"SliderMultiplier:{glob.slider_multiplier}", "SliderTickRate:1", "",
        "[Events]", "//Background and Video events",
        *([f'0,0,"{background}",0,0'] if background else []),
        *([f'Video,{int(video_offset_ms)},"{video}"'] if video else []),
        "//Break Periods",
        "//Storyboard Layer 0 (Background)", "//Storyboard Layer 1 (Fail)",
        "//Storyboard Layer 2 (Pass)", "//Storyboard Layer 3 (Foreground)",
        "//Storyboard Sound Samples", "",
        "[TimingPoints]",
        f"{round(offset_ms)},{beat_len:.12g},4,1,0,70,1,0", "",
        "[HitObjects]",
    ]
    lines += [object_line(o) for o in objects]
    return "\n".join(lines) + "\n"


def write_osz(out_path: Path, osu_text: str, osu_name: str, audio_path: Path,
              extra_files: list[Path] | None = None) -> Path:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(osu_name, osu_text)
        z.write(audio_path, audio_path.name)
        for f in extra_files or []:                     # background video / still image
            z.write(f, f.name)
    return out_path
