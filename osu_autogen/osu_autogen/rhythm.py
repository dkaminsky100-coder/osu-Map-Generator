"""Rhythm selection: choose which 1/4-beat grid slots become hit objects."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import maximum_filter1d

from .analysis import AudioAnalysis
from .difficulty import Style


@dataclass
class Note:
    slot: int        # grid index relative to the downbeat offset (4 slots per beat)
    time_ms: int
    score: float


def _chain_len(sel: list[int]) -> int:
    n = 1
    for a, b in zip(reversed(sel[:-1]), reversed(sel[1:])):
        if b - a == 1:
            n += 1
        else:
            break
    return n


def _sweep(scores: np.ndarray, tau: float, min_gap: int, max_run: int) -> list[int]:
    sel: list[int] = []
    for i, s in enumerate(scores):
        if s < tau:
            continue
        if not sel:
            sel.append(i)
            continue
        gap = i - sel[-1]
        if gap < min_gap:                        # too close: keep the stronger of the two
            if s > scores[sel[-1]] and (len(sel) < 2 or i - sel[-2] >= min_gap):
                sel[-1] = i
            continue
        if gap == 1 and _chain_len(sel) + 1 > max_run:
            continue
        sel.append(i)
    return sel


def _position_bonus(slot: int, beats_per_bar: int = 4) -> float:
    sub = slot % 4
    if sub == 0:
        return 0.32 if (slot // 4) % beats_per_bar == 0 else 0.22
    return 0.12 if sub == 2 else 0.0


def select_notes(an: AudioAnalysis, style: Style, density_scale: float = 1.0) -> list[Note]:
    slot_s = an.beat_len / 4.0
    k_lo = int(np.ceil(-an.offset / slot_s))
    k_hi = int(np.floor((an.duration - 0.25 - an.offset) / slot_s))
    ks = np.arange(k_lo, k_hi + 1)
    times = an.offset + ks * slot_s

    env_max = maximum_filter1d(an.env, size=5)
    frames = np.array([an.frame(t) for t in times])
    env = np.minimum(env_max[frames], 1.5)
    loud = maximum_filter1d(an.rms, size=9)[frames]
    bonus = np.array([_position_bonus(int(k)) for k in ks])

    scores = 0.85 * env + bonus
    scores[loud < 0.06] = -9.0                   # silence: never place notes

    valid = np.where(scores > -5)[0]
    if len(valid) < 2:
        return []
    active_s = (valid[-1] - valid[0]) * slot_s
    target = max(4, int(style.nps * density_scale * active_s))

    min_gap = max(1, int(round(style.min_gap_beats * 4)))
    lo, hi = -0.5, 2.5
    best = _sweep(scores, hi, min_gap, style.stream_max_len)
    for _ in range(18):                         # binary-search the threshold to hit target density
        mid = (lo + hi) / 2
        sel = _sweep(scores, mid, min_gap, style.stream_max_len)
        best = sel
        if len(sel) > target:
            lo = mid
        else:
            hi = mid
    return [Note(int(ks[i]), int(round(times[i] * 1000)), float(scores[i])) for i in best]
