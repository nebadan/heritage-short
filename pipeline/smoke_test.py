"""Call each provider once and log latency, so you learn early what works."""
from __future__ import annotations

import subprocess
import sys

from . import providers
from .common import OUT, call_model, load_storyboard

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def ffmpeg():
    v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    return v


@test
def gemini_text(sb):
    m = sb["models"]["text"]
    return call_model(stage="smoke", shot_id="text", provider="gemini-api", model=m, params={}, seed=None,
                      input_hash="smoke", fn=lambda: providers.gemini_text("Reply with the single word OK.", m,
                                                                           json_mode=False)).strip()


@test
def gemini_tts(sb):
    m = sb["models"]["tts"]
    out = OUT / "smoke" / "tts.wav"
    wav = call_model(stage="smoke", shot_id="tts", provider="gemini-api", model=m, params={}, seed=None,
                     input_hash="smoke", output=out,
                     fn=lambda: providers.gemini_tts("ሰላም፣ እንኳን ደህና መጣችሁ።", m, sb["voice"]["voice_name"],
                                                     "calm and warm", "Amharic"))
    out.write_bytes(wav)
    return f"{len(wav)} bytes -> {out}"


@test
def cloudflare_image(sb):
    m = sb["models"]["image"]
    out = OUT / "smoke" / "image.png"
    data = call_model(stage="smoke", shot_id="image", provider="cloudflare-workers-ai", model=m, params={"size": 512},
                      seed=1, input_hash="smoke", output=out,
                      fn=lambda: providers.flux_image("a clay coffee pot on a wooden table, soft window light", m,
                                                      512, 512, 1))
    out.write_bytes(data)
    return f"{len(data)} bytes -> {out}"


def main():
    sb = load_storyboard()
    (OUT / "smoke").mkdir(parents=True, exist_ok=True)
    bad = 0
    for t in TESTS:
        try:
            r = t() if t.__name__ == "ffmpeg" else t(sb)
            print(f"PASS {t.__name__}: {r}")
        except Exception as e:
            bad += 1
            print(f"FAIL {t.__name__}: {e}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
