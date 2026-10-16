# osu-autogen

Generate an osu!standard beatmap (`.osu` + importable `.osz`) from an MP3/MP4, aiming at a **target star rating**.

## Install & run
```bash
pip install -r requirements.txt          # needs ffmpeg on PATH, or imageio-ffmpeg (included)
python -m osu_autogen song.mp3 --stars 5.0 --title "Song" --artist "Artist" -o output/
python -m osu_autogen clip.mp4 -s 2.5            # MP4 works too (audio is extracted)
```
Double-click the resulting `.osz` to import it into osu!. Useful flags: `--bpm 174` (override detected tempo),
`--offset-ms -12` (nudge timing), `--seed 7` (different layout), `--tolerance 0.1`, `--no-measure`.

## Background video (MP4 input)
If the input has a video track, the tool re-encodes it to H.264 720p (no audio), grabs a still frame as the fallback
background, and bundles both into the `.osz` with the right `[Events]` lines. Flags: `--no-video` to skip it,
`--video-offset-ms 300` to shift the video later (negative = earlier) if it's out of sync with the audio.

## Pipeline
| Step | File | What it does |
|---|---|---|
| 1 | `audio.py` | ffmpeg: MP3/MP4 -> 44.1 kHz stereo MP3 (what osu! plays). The *converted* file is what gets analysed, so encoder delay can't skew timing. |
| 2 | `analysis.py` | Onset-strength envelope (full band + kick band). BPM = librosa estimate refined by a fine scan that folds onsets modulo the beat; beat phase = strongest fold peak; downbeat guess from per-beat energy. |
| 3 | `rhythm.py` | Builds a 1/4-beat grid, scores each slot (onset strength + metrical position), then binary-searches a threshold to hit the target notes/second, respecting min gap and max stream length. Silence is never mapped. |
| 4 | `layout.py` | Positions in the 512x384 field: distance snap, smooth flow vs random jumps, constant-spacing streams, centre pull, and sliders (line / circular arc / bezier, repeats) that *replace* the notes beneath them. |
| 5 | `difficulty.py` | Piecewise tables: star -> AR/CS/OD/HP/slider speed (from the target) and -> density, spacing, stream/jump/slider rates (from an effective difficulty `d`). |
| 6 | `stars.py`, `pipeline.py` | **Feedback loop**: generate -> measure real star rating with `rosu-pp-py` -> move `d` (secant/bracketing) until within `--tolerance`. |
| 7 | `osu_writer.py` | osu file format v14 + `.osz` bundle. |

## Verified so far (synthetic 128 BPM track, `tests/test_pipeline.py`)
BPM 127.997-128.001; objects within ~1.5 ms of the true 1/4-beat grid; no off-screen points; star ratings land
within ~0.15* of the target from 1.5* to 6.5*, ~7.7* at the generator's current ceiling.

## Known limitations / next milestones
- Constant BPM only (no tempo changes, no 1/3 triplets, no kiai/breaks/spinners/combo colours).
- Tempo can land on an octave (e.g. 85 instead of 170): use `--bpm`. Downbeat is a heuristic (affects combo/bar lines only).
- Timing was calibrated on synthetic audio (`ANALYSIS_LATENCY_S`); check a real song in the editor and use `--offset-ms` if it's off.
- Very high targets depend on song tempo/onsets; the loop stops and tells you when a target is out of reach.
- Rhythm is onset-based, not melody/vocal aware; patterns are random-flow, not hand-crafted. Ideas: pattern templates,
  hitsounds from drum/low-band classification, sliders from sustained notes, per-section difficulty curves.
