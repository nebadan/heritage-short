"""Stage: script. Pre-production helpers using Gemini text models.

  python -m pipeline.script draft --notes story/notes.md   -> storyboard.draft.json (validated, never overwrites)
  python -m pipeline.script translate [--force]            -> fills shots[].narration from narration_en
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import providers
import os

import requests

from .common import (ROOT, SCHEMA, Retryable, call_model, load_storyboard, save_storyboard, stable_hash,
                     validate_storyboard)

# If the main text model is overloaded (503) or unknown (404), try these in order.
FALLBACKS = [m.strip() for m in os.environ.get(
    "GEMINI_TEXT_FALLBACKS",
    "gemini-3.8-flash-lite,gemini-flash-latest,gemini-flash-lite-latest,gemini-2.5-flash,gemini-2.5-flash-lite"
).split(",") if m.strip()]


def text_with_fallback(prompt: str, model: str, shot_id: str, params: dict, **kw) -> str:
    chain = [model] + [m for m in FALLBACKS if m != model]
    last = None
    for m in chain:
        try:
            return call_model(stage="script", shot_id=shot_id, provider="gemini-api", model=m,
                              params={**params, "fallback_from": model if m != model else None}, seed=None,
                              input_hash=stable_hash(prompt), tries=3,
                              fn=lambda: providers.gemini_text(prompt, m, **kw))
        except (Retryable, requests.ConnectionError, requests.Timeout) as e:
            last = e
            print(f"  {m} overloaded or timed out, trying next model", file=sys.stderr)
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "HTTP 400" in str(e):
                last = e
                print(f"  {m} not available ({str(e)[:60]}), trying next model", file=sys.stderr)
            else:
                raise
    raise SystemExit(f"all text models failed; last error: {last}")


def draft(a):
    notes = Path(a.notes).read_text(encoding="utf-8")
    sb_model = a.model
    schema = SCHEMA.read_text(encoding="utf-8")
    prompt = f"""You are a film director's assistant. Write a storyboard for a 60-90 second heritage short film.
Return ONLY a JSON object that validates against this JSON Schema:
{schema}

Rules: 8-10 shots; total narration about 130-180 English words (narration_en); one idea and one gentle
movement per shot; vary shot sizes; few characters; every shot has a concrete `reason`; image prompts describe
subject, setting and light but never ask for text in the image; leave `narration` empty (it is translated later);
motion "kenburns" for every shot except at most two "wan" shots that have a motion_prompt describing only motion and camera.
Use these models: text={sb_model}, tts=gemini-3.8-flash-tts, image=@cf/black-forest-labs/flux-2-klein-4b,
video=wan2.2-ti2v-5b, music=ace-step-1.5.

The filmmaker's notes (story, audience, intent, language):
{notes}"""
    errs, text = None, None
    for attempt in range(3):
        p = prompt if not errs else (prompt + "\n\nYour previous answer failed validation with these errors; "
                                     "fix them and return the full JSON again:\n- " + "\n- ".join(errs[:20]))
        text = text_with_fallback(p, sb_model, "draft", {"task": "draft", "attempt": attempt + 1}, json_mode=True)
        try:
            sb = json.loads(text)
            errs = validate_storyboard(sb)
        except json.JSONDecodeError as e:
            errs = [f"not JSON: {e}"]
        if not errs:
            break
        print(f"  draft attempt {attempt + 1} invalid ({len(errs)} errors), asking for a fix", file=sys.stderr)
    out = ROOT / "storyboard.draft.json"
    out.write_text(text if errs else json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errs:
        sys.exit(f"draft still invalid after 3 attempts; raw output in {out.name}:\n- " + "\n- ".join(errs[:10]))
    print(f"wrote {out.name}. Review it, then copy what you keep into storyboard.json.")


def translate(a):
    sb = load_storyboard()
    todo = [s for s in sb["shots"] if s.get("narration_en") and (a.force or not s.get("narration"))]
    if not todo:
        print("nothing to translate")
        return
    lines = [{"id": s["id"], "en": s["narration_en"]} for s in todo]
    model = sb["models"]["text"]
    prompt = (f"Translate these narration lines for a short family film into natural, spoken {sb['language_name']} "
              f"({sb['language']}). Keep it warm and simple, as an elder would tell it; keep names and places; "
              f"write in the language's own script. Return ONLY a JSON array of objects "
              f'{{"id": ..., "text": ...}} in the same order.\n\n{json.dumps(lines, ensure_ascii=False)}')
    text = text_with_fallback(prompt, model, "translate",
                              {"task": "translate", "lines": len(lines), "language": sb["language"]}, temperature=0.3)
    got = {d["id"]: d["text"] for d in json.loads(text)}
    for s in todo:
        if s["id"] in got:
            s["narration"] = got[s["id"]].strip()
            print(f"  {s['id']}: {s['narration']}")
    save_storyboard(sb)
    print("storyboard.json updated. Have a native speaker read these lines before you generate narration.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("--notes", default=str(ROOT / "story" / "notes.md"))
    d.add_argument("--model", default="gemini-3.8-flash")
    t = sub.add_parser("translate")
    t.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    {"draft": draft, "translate": translate}[a.cmd](a)


if __name__ == "__main__":
    main()
