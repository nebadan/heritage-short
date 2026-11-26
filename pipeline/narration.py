"""Stage: narration. One WAV per shot from Gemini TTS, cached by text+voice+model."""
from __future__ import annotations

import argparse
import os
import sys

import requests

from . import providers
from .common import (Retryable, call_model, cached, load_storyboard, log_cache_hit, narration_inputs, narration_text,
                     selected_shots)


# Tried in order if the main TTS model is out of quota (429) or overloaded (503).
FALLBACKS = [m.strip() for m in os.environ.get(
    "GEMINI_TTS_FALLBACKS", "gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts,gemini-2.5-flash-tts").split(",")
    if m.strip()]


def tts_with_fallback(sb, s, text, inputs, h, out):
    chain = [inputs["model"]] + [m for m in FALLBACKS if m != inputs["model"]]
    last = None
    for m in chain:
        try:
            return call_model(stage="narration", shot_id=s["id"], provider="gemini-api", model=m,
                              params={"voice": inputs["voice"], "chars": len(text),
                                      "fallback_from": inputs["model"] if m != inputs["model"] else None},
                              seed=None, input_hash=h, output=out, tries=3,
                              fn=lambda: providers.gemini_tts(text, m, inputs["voice"], inputs["style"],
                                                              sb["language_name"]))
        except (Retryable, requests.ConnectionError, requests.Timeout) as e:
            last = e
            print(f"  [narration/{s['id']}] {m} unavailable, trying next model", file=sys.stderr)
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "HTTP 400" in str(e):
                last = e
                print(f"  [narration/{s['id']}] {m} not available, trying next model", file=sys.stderr)
            else:
                raise
    raise RuntimeError(f"all TTS models failed: {last}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated shot ids")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    failed = []
    print("narration:")
    for s in selected_shots(sb, a.only):
        text = narration_text(sb, s)
        if not text:
            print(f"  [narration/{s['id']}] no narration, skipped")
            continue
        if not s.get("narration") and sb["language"] != "en":
            print(f"  [narration/{s['id']}] WARNING: no {sb['language_name']} narration; speaking English. "
                  f"Run `make translate` first.", file=sys.stderr)
        inputs = narration_inputs(sb, s)
        out, h = cached("narration", s["id"], inputs, "wav")
        if out.exists():
            log_cache_hit("narration", s["id"], h, out)
            continue
        try:
            wav = tts_with_fallback(sb, s, text, inputs, h, out)
            out.write_bytes(wav)
        except Exception as e:
            print(f"  [narration/{s['id']}] FAILED: {e}", file=sys.stderr)
            failed.append(s["id"])
    if failed:
        sys.exit(f"narration failed for {failed} (see runs.jsonl); rerun to retry only those")


if __name__ == "__main__":
    main()
