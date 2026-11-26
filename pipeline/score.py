"""Procedural score: the fallback when no ACE-Step candidate is available.

A small original piece composed in code, deterministic from the storyboard's music
settings and a seed: Karplus-Strong plucked string (a lyre/krar-like timbre) playing a
D major pentatonic melody, a soft low drum on the beat, and a slow pad. Pure Python
(standard library only), so it runs anywhere the pipeline runs.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SR = 44100
# D major pentatonic (D E F# A B), two octaves, Hz
SCALE = [146.83, 164.81, 185.00, 220.00, 246.94, 293.66, 329.63, 369.99, 440.00, 493.88, 587.33]


def _pluck(freq: float, dur: float, rng: random.Random, bright: float = 0.996) -> list[float]:
    n = int(SR * dur)
    period = max(2, int(SR / freq))
    buf = [rng.uniform(-1, 1) for _ in range(period)]
    out = []
    for i in range(n):
        j = i % period
        nxt = buf[(j + 1) % period]
        buf[j] = bright * 0.5 * (buf[j] + nxt)
        out.append(buf[j])
    return out


def _drum(dur: float = 0.5) -> list[float]:
    n = int(SR * dur)
    return [math.sin(2 * math.pi * (70 - 30 * i / n) * i / SR) * math.exp(-7 * i / n) for i in range(n)]


def compose(out: Path, duration: float, bpm: int = 84, seed: int = 11) -> Path:
    rng = random.Random(seed)
    n = int(SR * duration)
    mix = [0.0] * n
    beat = 60.0 / bpm

    def add(sig, start_s, gain):
        s = int(start_s * SR)
        for i, v in enumerate(sig):
            k = s + i
            if k >= n:
                break
            mix[k] += v * gain

    # melody: phrases of 8 eighth-notes; sparse at first, fuller in the middle, sparse at the end
    motif = [5, 7, 8, 7, 5, 4, 3, 5]          # a short theme that returns
    t, bar = 0.0, 0
    while t < duration - 2:
        progress = t / duration
        density = 0.35 if progress < 0.2 or progress > 0.8 else 0.7
        for step in range(8):
            if rng.random() < density or step == 0:
                idx = motif[step] if bar % 4 == 0 else max(0, min(len(SCALE) - 1, motif[step] + rng.choice([-2, -1, 0, 1, 2])))
                add(_pluck(SCALE[idx], 1.6, rng), t + step * beat / 2, 0.28)
        # bass root on bar start
        add(_pluck(SCALE[0] / 2, 2.5, rng, 0.998), t, 0.22)
        t += 4 * beat
        bar += 1

    # drum pulse from 15% to 85% of the piece
    t = duration * 0.15
    d = _drum()
    while t < duration * 0.85:
        add(d, t, 0.18)
        t += beat

    # pad: slow D-A-F# chord swell
    for f, g in ((146.83, 0.05), (220.0, 0.035), (369.99, 0.025)):
        for i in range(n):
            env = min(1.0, i / (SR * 4)) * min(1.0, (n - i) / (SR * 4))
            mix[i] += g * env * math.sin(2 * math.pi * f * i / SR) * (0.8 + 0.2 * math.sin(2 * math.pi * 0.1 * i / SR))

    peak = max(1e-9, max(abs(v) for v in mix))
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(32767 * 0.9 * v / peak)) for v in mix))
    return out
