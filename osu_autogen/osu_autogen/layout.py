"""Spatial layout: positions, flow, jumps, streams and slider geometry in the 512x384 playfield."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .difficulty import GlobalSettings, Style
from .rhythm import Note

W, H = 512, 384
MARGIN = 14.0
Pt = tuple[float, float]


@dataclass
class SliderSpec:
    curve: str                  # 'L' | 'P' | 'B'
    points: list[Pt]            # control points after the start point
    slides: int
    length: float               # osu! pixels, one pass
    end_time_ms: int


@dataclass
class HitObject:
    time_ms: int
    x: int
    y: int
    new_combo: bool
    slider: SliderSpec | None = None


def _inside(p: Pt, m: float = MARGIN) -> bool:
    return m <= p[0] <= W - m and m <= p[1] <= H - m


def _all_inside(pts: list[Pt], m: float = 6.0) -> bool:
    return all(_inside(p, m) for p in pts)


def _bezier_points(ctrl: list[Pt], n: int = 40) -> list[Pt]:
    out = []
    for i in range(n + 1):
        t = i / n
        pts = list(ctrl)
        while len(pts) > 1:
            pts = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(pts, pts[1:])]
        out.append(pts[0])
    return out


def _polyline_len(pts: list[Pt]) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


# ---------------------------------------------------------------- slider shapes
def _slider_linear(start: Pt, heading: float, length: float):
    end = (start[0] + length * math.cos(heading), start[1] + length * math.sin(heading))
    if not _all_inside([start, end]):
        return None
    return "L", [end], end, heading


def _slider_arc(start: Pt, heading: float, length: float, rng: np.random.Generator):
    sweep = rng.uniform(0.8, 2.0)
    direction = 1 if rng.random() < 0.5 else -1
    r = length / sweep
    a0 = heading - direction * math.pi / 2          # tangent at start == heading
    cx, cy = start[0] - r * math.cos(a0), start[1] - r * math.sin(a0)
    at = lambda u: (cx + r * math.cos(a0 + direction * sweep * u), cy + r * math.sin(a0 + direction * sweep * u))
    samples = [at(i / 14) for i in range(15)]
    if not _all_inside(samples):
        return None
    end = at(1.0)
    end_heading = a0 + direction * sweep + direction * math.pi / 2
    return "P", [at(0.5), end], end, end_heading


def _slider_bezier(start: Pt, heading: float, length: float, rng: np.random.Generator, cubic: bool):
    f = (math.cos(heading), math.sin(heading))
    n = (-f[1], f[0])
    side = 1 if rng.random() < 0.5 else -1
    if cubic:   # S-curve or hook, defined in the local (forward, normal) frame
        local = [(0.0, 0.0), (0.35, 0.55 * side), (0.7, -0.5 * side * rng.uniform(0.4, 1.0)), (1.0, 0.1 * side)]
    else:       # gentle C-curve
        local = [(0.0, 0.0), (0.55, 0.7 * side), (1.0, 0.1 * side)]
    ctrl = [(start[0] + a * f[0] + b * n[0], start[1] + a * f[1] + b * n[1]) for a, b in local]
    scale = length / _polyline_len(_bezier_points(ctrl, 60))   # length scales linearly about the start
    ctrl = [(start[0] + (p[0] - start[0]) * scale, start[1] + (p[1] - start[1]) * scale) for p in ctrl]
    if not (_all_inside(_bezier_points(ctrl, 24)) and _all_inside(ctrl, 0.0)):   # curve AND anchors on-screen
        return None
    end = ctrl[-1]
    end_heading = math.atan2(ctrl[-1][1] - ctrl[-2][1], ctrl[-1][0] - ctrl[-2][0])
    return "B", ctrl[1:], end, end_heading


def make_slider(start: Pt, heading: float, length: float, complexity: float, rng: np.random.Generator):
    """Try shapes (biased by complexity) at several headings until one fits the playfield."""
    for attempt in range(14):
        h = heading + (0 if attempt == 0 else (1 if attempt % 2 else -1) * math.radians(25) * ((attempt + 1) // 2))
        r = rng.random()
        if r < complexity * 0.55:
            res = _slider_bezier(start, h, length, rng, cubic=complexity > 0.5 and rng.random() < 0.6)
        elif r < 0.25 + complexity * 0.6:
            res = _slider_arc(start, h, length, rng)
        else:
            res = _slider_linear(start, h, length)
        if res:
            return res
    return None


# ---------------------------------------------------------------- main layout pass
def build_objects(notes: list[Note], beat_ms: float, offset_ms: float, glob: GlobalSettings,
                  style: Style, rng: np.random.Generator) -> list[HitObject]:
    diameter = 2 * glob.circle_radius
    px_per_beat = glob.slider_multiplier * 100.0
    min_dist, max_dist = 0.9 * diameter, 380.0
    centre = (W / 2, H / 2)

    objs: list[HitObject] = []
    pos: Pt = centre
    heading = rng.uniform(0, 2 * math.pi)
    turn_sign = 1
    prev_end_ms: float | None = None
    last_bar = None
    slot_beats = lambda a, b: (b - a) / beat_ms

    i = 0
    while i < len(notes):
        note = notes[i]
        t = note.time_ms
        i += 1
        if prev_end_ms is not None and slot_beats(prev_end_ms, t) < style.min_gap_beats - 0.03:   # tolerance: slot times are rounded to whole ms
            continue                                  # swallowed by the previous slider's tail
        bar = math.floor((t - offset_ms) / (beat_ms * 4) + 1e-6)
        new_combo = (last_bar is None) or (bar != last_bar)
        last_bar = bar

        gap_prev = slot_beats(prev_end_ms, t) if prev_end_ms is not None else 1.0

        # ---- choose the next position ----
        if prev_end_ms is None:
            target = pos
        else:
            if gap_prev <= 0.27:                                  # stream
                dist = diameter * style.stream_spacing
                turn = turn_sign * 0.28
            else:
                dist = float(np.clip(style.spacing * px_per_beat * gap_prev, min_dist, max_dist))
                if gap_prev >= 0.5 and rng.random() < style.jump_prob:
                    dist = min(max_dist, dist * rng.uniform(1.0, 1.5))
                    turn = rng.uniform(-math.pi, math.pi)
                else:
                    turn = turn_sign * abs(rng.normal(0, style.angle_std))
                    if rng.random() < 0.3:
                        turn_sign = -turn_sign
            h = heading + turn
            # gentle pull toward the centre when drifting to an edge
            off = math.dist(pos, centre) / 220.0
            w = 0.4 * min(1.0, off * off)
            ch = math.atan2(centre[1] - pos[1], centre[0] - pos[0])
            vx = (1 - w) * math.cos(h) + w * math.cos(ch)
            vy = (1 - w) * math.sin(h) + w * math.sin(ch)
            h = math.atan2(vy, vx)
            target = None
            for k in range(13):                                   # rotate until it fits on screen
                hh = h + (0 if k == 0 else (1 if k % 2 else -1) * math.radians(30) * ((k + 1) // 2))
                cand = (pos[0] + dist * math.cos(hh), pos[1] + dist * math.sin(hh))
                if _inside(cand):
                    target, h = cand, hh
                    break
            if target is None:
                target = (float(np.clip(pos[0] + dist * math.cos(h), MARGIN, W - MARGIN)),
                          float(np.clip(pos[1] + dist * math.sin(h), MARGIN, H - MARGIN)))
            heading = h
        pos = target

        # ---- slider (spans and replaces the notes under it) or circle ----
        if i < len(notes) and rng.random() < style.slider_prob:
            # candidate end notes: 0.5..4 beats ahead, swallowing at most 3 notes
            cands = []
            for j in range(i, min(i + 4, len(notes))):
                dur = (notes[j].time_ms - t) / beat_ms
                if dur > 4.0 + 1e-6:
                    break
                if dur >= 0.5 - 1e-6:
                    cands.append((j, dur))
            if cands:
                j, dur = cands[0] if (len(cands) == 1 or rng.random() < 0.6) else cands[1]
                slides = 1
                if dur >= 1.0 and rng.random() < style.repeat_prob:
                    slides = 2
                while dur * px_per_beat / slides > 320 and slides < 4:
                    slides += 1
                pass_len = dur * px_per_beat / slides
                if pass_len >= 0.6 * diameter and dur / slides >= 0.25 - 1e-9:
                    shape = make_slider(pos, heading, pass_len, style.slider_complexity, rng)
                    if shape:
                        curve, pts, end, end_heading = shape
                        end_ms = notes[j].time_ms
                        slider = SliderSpec(curve, [(round(x), round(y)) for x, y in pts], slides,
                                            round(pass_len, 2), end_ms)
                        start_pos = pos
                        if slides % 2 == 1:
                            pos, heading = end, end_heading
                        else:
                            heading = end_heading + math.pi
                        objs.append(HitObject(t, round(start_pos[0]), round(start_pos[1]), new_combo, slider))
                        prev_end_ms = end_ms
                        i = j + 1
                        continue
        objs.append(HitObject(t, round(pos[0]), round(pos[1]), new_combo))
        prev_end_ms = t
    return objs
