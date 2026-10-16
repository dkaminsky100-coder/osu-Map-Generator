"""Star-rating measurement via rosu-pp-py (a port of osu!'s difficulty calculator)."""
from __future__ import annotations


def available() -> bool:
    try:
        import rosu_pp_py  # noqa: F401
        return True
    except ImportError:
        return False


def measure(osu_text: str) -> float:
    import rosu_pp_py as rosu

    try:
        bm = rosu.Beatmap(content=osu_text)
    except TypeError:
        bm = rosu.Beatmap(bytes=osu_text.encode("utf-8"))
    return float(rosu.Difficulty().calculate(bm).stars)
