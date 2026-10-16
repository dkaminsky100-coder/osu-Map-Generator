"""Synthesise a test track with known timing (default 128 BPM, first beat at 350 ms).
Usage: python tools/make_test_song.py out.wav [bpm] [offset_s] [seconds]"""
import sys
import wave

import numpy as np

SR = 44100


def main(out, bpm=128.0, offset=0.35, seconds=60.0):
    n = int(seconds * SR)
    y = np.zeros(n)
    L = 60.0 / bpm
    rng = np.random.default_rng(0)

    def add(t, sig):
        i = int(t * SR)
        if 0 <= i < n:
            m = min(len(sig), n - i)
            y[i:i + m] += sig[:m]

    tk = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 110 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 14)
    th = np.arange(int(0.08 * SR)) / SR
    hat = rng.standard_normal(len(th)) * np.exp(-th * 70) * 0.25
    ts = np.arange(int(0.2 * SR)) / SR
    snare = (rng.standard_normal(len(ts)) * 0.6 + np.sin(2 * np.pi * 190 * ts) * 0.4) * np.exp(-ts * 22)
    scale = [0, 3, 7, 10, 12, 15, 19, 22]

    nb = int((seconds - offset) / L)
    for b in range(nb):
        t = offset + b * L
        add(t, kick)
        if b % 4 in (1, 3):
            add(t, snare * 0.8)
        add(t + L / 2, hat)
        if b >= 16:                                   # melody enters after 4 bars
            for q in range(4):
                if (b + q) % 3 != 0 or q % 2 == 0:
                    f = 220 * 2 ** (scale[(b * 4 + q * 3) % 8] / 12)
                    tn = np.arange(int(0.12 * SR)) / SR
                    add(t + q * L / 4, np.sin(2 * np.pi * f * tn) * np.exp(-tn * 20) * 0.18)
    # sustained pad so the track isn't literally silent between hits (like real music)
    tt = np.arange(n) / SR
    chords = [(110, 138.6, 164.8), (98, 123.5, 146.8), (87.3, 110, 130.8), (98, 123.5, 146.8)]
    bar = np.minimum(((tt - offset).clip(0) / (4 * L)).astype(int), 10**6) % 4
    for k, ch in enumerate(chords):
        env_k = (bar == k).astype(float)
        for f in ch:
            y += 0.06 * np.sin(2 * np.pi * f * tt) * env_k
    y = y / (np.abs(y).max() * 1.1)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    print(f"wrote {out}: {bpm} BPM, first beat {offset * 1000:.0f} ms, bar lines at "
          f"{(offset * 1000) % (L * 4000):.0f} ms mod {L * 4000:.0f}")


if __name__ == "__main__":
    a = sys.argv
    main(a[1], *(float(x) for x in a[2:5]))
