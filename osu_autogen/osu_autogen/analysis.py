"""Audio analysis: BPM, beat phase (offset), downbeat guess, onset strength envelope."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import gaussian_filter1d, maximum_filter1d

SR = 22050
HOP = 256
N_FFT = 1024
# Spectral-flux peaks show up slightly before/after the true transient depending on
# window size. Calibrated on synthetic percussive audio; nudge with --offset-ms if needed.
ANALYSIS_LATENCY_S = 0.008


@dataclass
class AudioAnalysis:
    duration: float          # seconds
    bpm: float
    offset: float            # seconds; time of a downbeat (bar line)
    beat_len: float          # seconds
    env: np.ndarray          # normalised onset strength per frame (~1.0 = strong hit)
    rms: np.ndarray          # normalised loudness per frame
    onset_times: np.ndarray  # detected onsets (s)

    def frame(self, t: float) -> int:
        return int(np.clip(round((t + ANALYSIS_LATENCY_S) * SR / HOP), 0, len(self.env) - 1))


def _fold_bpm(bpm: float, lo: float = 75.0, hi: float = 190.0) -> float:
    while bpm < lo:
        bpm *= 2
    while bpm >= hi:
        bpm /= 2
    return bpm


def _fold_hist(times: np.ndarray, w: np.ndarray, period: float, bins: int = 256) -> np.ndarray:
    """Fold onsets modulo `period` into a circular histogram, smoothed with a ~8 ms kernel."""
    h, _ = np.histogram((times % period) / period, bins=bins, range=(0, 1), weights=w)
    sigma_bins = max(1.0, 0.008 / period * bins)
    return gaussian_filter1d(h, sigma_bins, mode="wrap")


def _grid_score(times: np.ndarray, w: np.ndarray, period: float) -> float:
    return float(_fold_hist(times, w, period).max())


def refine_bpm(onsets: np.ndarray, w: np.ndarray, bpm0: float) -> float:
    """Two-stage scan (coarse then fine) for the tempo whose beat grid lines up with the most
    onset energy. Sharper than a first-harmonic phase estimate, so off-beat hats/arps can't drag it."""
    def scan(centre: float, span: float, step: float) -> float:
        cands = np.arange(centre - span, centre + span + step / 2, step)
        return float(cands[int(np.argmax([_grid_score(onsets, w, 60.0 / b) for b in cands]))])

    coarse = scan(bpm0, 3.0, 0.02)
    return scan(coarse, 0.04, 0.002)


def grid_phase(onsets: np.ndarray, w: np.ndarray, period: float) -> float:
    """Time (s, in [0, period)) of the beat grid that captures the most onset energy."""
    h = _fold_hist(onsets, w, period)
    return (int(np.argmax(h)) + 0.5) / len(h) * period


def analyse(wav_path: Path, bpm_override: float | None = None, offset_override_ms: float | None = None) -> AudioAnalysis:
    y, _ = librosa.load(str(wav_path), sr=SR, mono=True)
    duration = len(y) / SR

    env_raw = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP, n_fft=N_FFT)
    env = env_raw / (np.percentile(env_raw, 98) + 1e-9)
    rms_raw = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP)[0]
    rms = rms_raw / (np.percentile(rms_raw, 95) + 1e-9)

    frames = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP, backtrack=False)
    onset_times = librosa.frames_to_time(frames, sr=SR, hop_length=HOP) - ANALYSIS_LATENCY_S
    # Low band (kick/bass) onsets are the most reliable bar/beat anchor; hats and arps are not.
    env_low_raw = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP, n_fft=N_FFT, fmax=200, n_mels=8)
    env_low = env_low_raw / (np.percentile(env_low_raw, 98) + 1e-9)
    onset_w = env[frames] + 1.2 * maximum_filter1d(env_low, size=3)[frames]

    if bpm_override:
        bpm = float(bpm_override)
    else:
        tempo, _ = librosa.beat.beat_track(onset_envelope=env, sr=SR, hop_length=HOP)
        bpm0 = _fold_bpm(float(np.atleast_1d(tempo)[0]))
        bpm = refine_bpm(onset_times, onset_w, bpm0) if len(onset_times) > 8 else bpm0

    beat_len = 60.0 / bpm
    # Beat phase = position of the strongest peak when onsets are folded modulo one beat.
    offset = grid_phase(onset_times, onset_w, beat_len)

    # Downbeat guess: which of the 4 beats in a bar carries the most onset energy?
    beat_times = offset + beat_len * np.arange(int((duration - offset) / beat_len))
    if len(beat_times) >= 16:
        idx = np.clip(np.round((beat_times + ANALYSIS_LATENCY_S) * SR / HOP).astype(int), 0, len(env) - 1)
        mx = maximum_filter1d(env, size=3)[idx]
        sums = np.array([mx[p::4].sum() for p in range(4)])
        p = int(np.argmax(sums))
        if sums[p] > 1.1 * np.mean(sums):       # only trust a clear winner
            offset += p * beat_len
    if offset_override_ms is not None:
        offset += offset_override_ms / 1000.0

    return AudioAnalysis(duration, bpm, offset, beat_len, env, rms, onset_times)
