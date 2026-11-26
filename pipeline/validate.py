"""Validate storyboard.json against schema/storyboard.schema.json, plus sanity checks."""
from __future__ import annotations

import sys

from .common import load_storyboard


def main():
    sb = load_storyboard()  # exits on schema errors
    shots = sb["shots"]
    words = sum(len(s.get("narration_en", "").split()) for s in shots)
    est = sum(s["duration_s"] for s in shots) + sb["end_card"]["duration_s"]
    print(f"storyboard OK: '{sb['title']}', {len(shots)} shots, {words} English words, "
          f"~{est:.0f}s planned (narration may stretch shots), language={sb['language_name']}")
    warn = []
    if not 60 <= est <= 90:
        warn.append(f"planned length {est:.0f}s is outside 60-90s")
    if words > 220:
        warn.append(f"{words} words is a lot for 90s (aim for 130-220)")
    if sb["language"] != "en":
        n = [s["id"] for s in shots if s.get("narration_en") and not s.get("narration")]
        if n:
            warn.append(f"untranslated narration in {n}: run `make translate`")
    wan = [s["id"] for s in shots if s["motion"] == "wan"]
    if wan:
        print(f"  Wan shots (Kaggle): {wan}")
    for c in sb.get("characters", []):
        if c.get("real_person"):
            print(f"  real person '{c['id']}': consent record -> {c['consent_ref']}")
    for w in warn:
        print(f"  WARNING: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
