"""Audio handling: locate ffmpeg, convert MP3/MP4 -> osu!-friendly MP3, decode for analysis."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED = {".mp3", ".mp4", ".m4a", ".wav", ".flac", ".ogg", ".mkv", ".webm", ".mov"}


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # bundled binary shipped with imageio-ffmpeg / moviepy
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "ffmpeg not found. Install it (https://ffmpeg.org) or `pip install imageio-ffmpeg`."
        ) from exc


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-1500:]}")


def convert_to_mp3(src: Path, dst: Path, bitrate: str = "192k") -> Path:
    """Extract/convert audio from any ffmpeg-readable file into a 44.1 kHz stereo MP3."""
    src, dst = Path(src), Path(dst)
    if src.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported input type {src.suffix!r}; try one of {sorted(SUPPORTED)}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([
        find_ffmpeg(), "-y", "-i", str(src),
        "-vn",                       # drop any video stream (MP4 input)
        "-ac", "2", "-ar", "44100",
        "-codec:a", "libmp3lame", "-b:a", bitrate,
        str(dst),
    ])
    return dst


def decode_for_analysis(audio: Path, wav_out: Path, sr: int = 22050) -> Path:
    """Decode the *final* MP3 to mono WAV so we analyse exactly what osu! will play
    (this keeps encoder delay/padding out of the timing)."""
    _run([find_ffmpeg(), "-y", "-i", str(audio), "-ac", "1", "-ar", str(sr), str(wav_out)])
    return wav_out


VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm"}


def has_video_stream(src: Path) -> bool:
    """True if the file really contains a video track (not just cover art)."""
    if Path(src).suffix.lower() not in VIDEO_EXT:
        return False
    proc = subprocess.run([find_ffmpeg(), "-i", str(src)], capture_output=True, text=True)
    return any("Video:" in ln and "attached pic" not in ln for ln in proc.stderr.splitlines())


def make_video(src: Path, dst: Path, max_height: int = 720) -> Path:
    """Re-encode to a standard H.264 MP4 (no audio; osu! plays the MP3 instead)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([
        find_ffmpeg(), "-y", "-i", str(src), "-an",
        "-vf", f"scale=-2:'min({max_height},ih)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst),
    ])
    return dst


def extract_frame(src: Path, dst: Path, max_height: int = 720) -> Path:
    """Grab one still frame as the fallback background for players who disable videos."""
    for t in ("5", "1", "0"):
        try:
            _run([find_ffmpeg(), "-y", "-ss", t, "-i", str(src), "-frames:v", "1",
                  "-vf", f"scale=-2:'min({max_height},ih)'", "-q:v", "3", str(dst)])
            if dst.exists() and dst.stat().st_size > 0:
                return dst
        except RuntimeError:
            continue
    raise RuntimeError("could not extract a background frame")
