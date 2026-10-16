"""Smoke test: synthesise a 128 BPM track, run the whole pipeline, check timing/bounds/stars.
Run:  python -m pytest -q   (or)   python tests/test_pipeline.py"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import make_test_song  # noqa: E402
from osu_autogen.pipeline import generate  # noqa: E402


def _parse_objects(osu_text):
    return [o.split(",") for o in osu_text.split("[HitObjects]\n")[1].strip().splitlines()]


def test_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "t.wav"
        make_test_song.main(str(wav), 128.0, 0.35, 40.0)
        r = generate(wav, 4.0, Path(tmp) / "out", title="T", artist="A", log=lambda *_: None)
        assert abs(r.bpm - 128.0) < 0.1
        assert r.measured_star is not None and abs(r.measured_star - 4.0) < 0.4
        text = r.osu_path.read_text(encoding="utf-8")
        beat = 60000 / 128
        for p in _parse_objects(text):
            x, y, t = int(p[0]), int(p[1]), int(p[2])
            assert 0 <= x <= 512 and 0 <= y <= 384
            if int(p[3]) & 2:
                for pt in p[5].split("|")[1:]:
                    px, py = map(int, pt.split(":"))
                    assert 0 <= px <= 512 and 0 <= py <= 384
            err = (t - 350) % (beat / 4)
            err = min(err, beat / 4 - err)
            assert err < 6, f"object at {t} ms is {err:.1f} ms off the true grid"


if __name__ == "__main__":
    test_end_to_end()
    print("ok")
