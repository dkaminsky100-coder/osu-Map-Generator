# osu_autogen

`osu_autogen` is a command-line tool that automatically generates playable, importable osu! standard beatmaps (`.osz`) from audio or video files. It analyzes the track's tempo, detects onsets, lays out rhythm-aware notes and sliders, and uses a feedback loop to target a specific star rating.

## Features

- **End-to-End Automation:** Takes an MP3 or MP4 file and outputs a fully structured `.osz` package ready to import into osu!.
- **Smart Timing & Audio Processing:** Extracts audio via `ffmpeg` to prevent encoder delays, refines BPM via fine-scan tempo detection, and snaps notes to a 1/4-beat grid.
- **Star Rating Targeter:** Uses a feedback loop with `rosu-pp-py` to measure generated maps and adjust density and spacing to match your target star rating.
- **Background Video Support:** Automatically packages video and background images into the map archive, with options to offset or disable video.
- **Flow & Layout Management:** Generates natural jumps, constant-spacing streams, and valid sliders (straight, arc, or bezier) entirely contained within the 512x384 playfield.

---

## Prerequisites

- **Python 3.8+** installed on your system.
- **FFmpeg** must be installed and available on your system's `PATH`. (Alternatively, you can install packages like `imageio-ffmpeg` to handle runtime binaries).

---

## Installation

1. Clone or download this repository.
2. Open a terminal in the project directory.
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the tool from your command line by passing the audio or video file along with your target parameters:

```bash
python -m osu_autogen path/to/song.mp3 --stars 5.0 --title "Song Title" --artist "Artist Name"

// in case this does not work try py instead of python :D
```

### Command-Line Arguments

| Flag / Option | Description | Default |
| :--- | :--- | :--- |
| `input_file` | Path to the input audio (`.mp3`) or video (`.mp4`, etc.) file. | *(Required)* |
| `--stars` | Target star rating for the generated map. | `4.0` |
| `--title` | Song title for the beatmap metadata. | `"Generated Song"` |
| `--artist` | Artist name for the metadata. | `"Unknown Artist"` |
| `--bpm` | Manually override detected BPM (useful if tempo detection locks onto an octave or double time). | `None` (Auto) |
| `--offset-ms` | Nudge the global timing offset in milliseconds (positive = later, negative = earlier). | `0` |
| `--no-video` | Exclude video and background assets from the output map package. | `False` |
| `--video-offset-ms` | Push the background video later (positive) or earlier (negative) relative to audio. | `0` |

### Example with Video

```bash
python -m osu_autogen "C:\Users\YourName\Downloads\opening.mp4" --stars 3.5 --title "Blue Box OP" --artist "Official HIGE DANdism" --video-offset-ms -200
```

---

## Importing into osu!

1. After running the script, look in your output folder for the newly created `.osz` file.
2. Double-click the `.osz` file, or drag and drop it directly into your open osu! game window to import it automatically.

---

## Current Limitations

- **Constant Tempo Only:** The current version assumes a steady, constant BPM throughout the track (no timing changes, breaks, or spinners).
- **Tempo Octave Issues:** Automated BPM detection can occasionally lock onto half or double tempo (e.g., 85 instead of 170). Use the `--bpm` override flag if this happens.
- **Rhythm Focus:** The rhythm follows audio onsets rather than complex vocal melodies, utilizing procedurally generated flow patterns.
