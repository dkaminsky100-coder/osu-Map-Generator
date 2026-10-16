"""Star rating -> global difficulty settings + placement style.

All curves are piecewise-linear tables of (star, value) in the style of typical ranked maps.
Tune them freely: they are the main "taste" knobs of the generator.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


MAX_D = 16.0


def _interp(table: list[tuple[float, float]], x: float) -> float:
    xs, ys = zip(*table)
    return float(np.interp(x, xs, ys))


@dataclass
class GlobalSettings:
    ar: float
    cs: float
    od: float
    hp: float
    slider_multiplier: float

    @property
    def circle_radius(self) -> float:           # osu! pixels
        return 54.4 - 4.48 * self.cs


@dataclass
class Style:
    """Placement parameters. `d` is the *effective* difficulty fed to the tables; the
    star-targeting loop moves `d` up/down until the measured star rating hits the target."""
    d: float
    nps: float               # target notes per second
    min_gap_beats: float     # smallest allowed gap between objects
    spacing: float           # distance-snap multiplier (1.0 = one beat == SM*100 px)
    stream_spacing: float    # stream distance, in circle diameters
    stream_max_len: int      # longest run of 1/4-beat notes
    jump_prob: float         # chance of a random-angle jump instead of smooth flow
    angle_std: float         # radians; how sharply flow direction wanders
    slider_prob: float
    slider_complexity: float # 0 = straight lines, 1 = bezier-heavy
    repeat_prob: float


# ----- global settings follow the *target* star rating (conventional pairings) -----
_AR = [(0.5, 2.0), (1, 3.0), (2, 4.5), (2.7, 6.0), (4, 7.5), (5.3, 8.5), (6.5, 9.3), (8, 9.7), (10, 10.0)]
_CS = [(0.5, 2.5), (1, 2.5), (2, 3.0), (3, 3.8), (4, 4.0), (6, 4.2), (8, 4.4), (10, 4.5)]
_OD = [(0.5, 2.0), (1, 3.0), (2, 4.5), (3, 6.0), (4, 7.0), (5, 8.0), (6, 8.5), (8, 9.0), (10, 9.5)]
_HP = [(0.5, 3.0), (1, 3.0), (2, 4.0), (3, 5.0), (4, 6.0), (5, 6.5), (7, 7.0), (10, 7.5)]
_SM = [(0.5, 1.2), (2, 1.3), (3, 1.4), (5, 1.6), (8, 1.8), (10, 1.9)]


def global_settings(star: float) -> GlobalSettings:
    r1 = lambda v: round(float(np.clip(v, 0, 10)), 1)
    return GlobalSettings(
        ar=r1(_interp(_AR, star)), cs=r1(_interp(_CS, star)), od=r1(_interp(_OD, star)),
        hp=r1(_interp(_HP, star)), slider_multiplier=round(_interp(_SM, star), 2),
    )


# ----- placement style follows the effective difficulty d -----
_NPS = [(0.3, 0.5), (1, 0.9), (2, 1.6), (3, 2.6), (4, 3.6), (5, 4.6), (6, 5.6), (7, 6.6), (8, 7.6), (10, 9.5), (12, 11.5), (14, 13.5), (16, 15.5)]
_SPACING = [(0.3, 0.8), (2, 1.0), (3, 1.1), (4, 1.2), (5, 1.3), (6, 1.45), (8, 1.65), (10, 1.85), (12, 2.0), (14, 2.2), (16, 2.4)]
_STREAM_SP = [(0.3, 1.2), (4, 1.1), (6, 1.3), (8, 1.6), (10, 1.9), (12, 2.1), (14, 2.3), (16, 2.5)]
_STREAM_LEN = [(3.4, 2), (3.5, 3), (5, 6), (6, 10), (8, 24), (10, 48)]
_JUMP = [(0.3, 0.0), (3, 0.05), (5, 0.15), (7, 0.28), (10, 0.4), (16, 0.55)]
_ANGLE = [(0.3, 0.35), (3, 0.6), (6, 0.9), (10, 1.3), (16, 1.6)]
_SLIDER = [(0.3, 0.12), (1.5, 0.30), (3, 0.35), (5, 0.30), (8, 0.24), (10, 0.2)]
_COMPLEX = [(0.3, 0.0), (2, 0.15), (4, 0.4), (6, 0.65), (9, 0.9)]
_REPEAT = [(0.3, 0.05), (3, 0.15), (6, 0.3), (9, 0.4)]


def style_for(d: float) -> Style:
    d = float(np.clip(d, 0.3, MAX_D))
    min_gap = 1.0 if d < 1.5 else 0.5 if d < 2.8 else 0.25
    return Style(
        d=d,
        nps=_interp(_NPS, d),
        min_gap_beats=min_gap,
        spacing=_interp(_SPACING, d),
        stream_spacing=_interp(_STREAM_SP, d),
        stream_max_len=int(round(_interp(_STREAM_LEN, d))) if d >= 3.4 else 1,
        jump_prob=_interp(_JUMP, d),
        angle_std=_interp(_ANGLE, d),
        slider_prob=_interp(_SLIDER, d),
        slider_complexity=_interp(_COMPLEX, d),
        repeat_prob=_interp(_REPEAT, d),
    )
