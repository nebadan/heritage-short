"""Stage: music. The score is generated with ACE-Step 1.5 on a GPU outside this
machine (Colab/Kaggle, or the hosted ACE-Step demo). This stage:

  python -m pipeline.music                 prepare the chosen score (or a placeholder)
  python -m pipeline.music register FILE   log a generated candidate into runs.jsonl
        --seed 3 --seconds 14 --provider colab-t4 [--gpu]

Set music.chosen_file in storyboard.json to the candidate you picked, and write why
in music.choice_reason.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from .common import (OUT, ROOT, cached, ffmpeg, file_hash, load_storyboard, log, log_cache_hit, log_render, rel,
                     stable_hash, timeline)

CAND = OUT / "music" / "candidates"


def placeholder(total: float) -> Path:
    """Soft drone chord: the temp track for the radio cut."""
    inputs = {"kind": "placeholder", "dur": round(total, 1)}
    out, h = cached("music", "placeholder", inputs, "wav")
    if out.exists():
        return out
    expr = ("0.05*sin(2*PI*130.81*t)*(0.7+0.3*sin(2*PI*0.08*t))+0.035*sin(2*PI*196.00*t)"
            "+0.03*sin(2*PI*261.63*t)*(0.6+0.4*sin(2*PI*0.05*t))")
    ffmpeg(["-f", "lavfi", "-i", f"aevalsrc=exprs='{expr}|{expr}':s=48000:d={total:.2f}", "-c:a", "pcm_s16le", out])
    log_render("music", "placeholder", h, out, 0)
    return out


def resolve(sb: dict, total: float, allow_placeholder: bool = True) -> tuple[Path, bool]:
    """Returns (score_path, is_placeholder)."""
    chosen = sb["music"].get("chosen_file")
    if chosen and (ROOT / chosen).exists():
        src = ROOT / chosen
        inputs = {"file": file_hash(src)}
        out, h = cached("music", "score", inputs, "wav")
        if out.exists():
            log_cache_hit("music", "score", h, out)
        else:
            t0 = time.time()
            ffmpeg(["-i", src, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out])
            log_render("music", "score", h, out, time.time() - t0)
        return out, False
    if chosen:
        print(f"  [music] chosen_file {chosen} not found", file=sys.stderr)
    if not allow_placeholder:
        sys.exit("No chosen score. Generate candidates (see gpu/ACESTEP.md) and set music.chosen_file.")
    print("  [music] no chosen score yet: using placeholder drone")
    return placeholder(total), True


def register(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--seconds", type=float, required=True, help="generation time you measured")
    ap.add_argument("--provider", default="colab", help="colab-t4 | kaggle-t4 | acestep-hosted-demo ...")
    ap.add_argument("--gpu", action="store_true", help="count seconds as GPU seconds")
    ap.add_argument("--model", default="ace-step-1.5-turbo")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    src = Path(a.file)
    CAND.mkdir(parents=True, exist_ok=True)
    dest = CAND / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    m = sb["music"]
    params = {k: m.get(k) for k in ("caption", "bpm", "key", "duration_s", "instrumental")}
    log({"event": "model_call", "stage": "music", "shot_id": "score", "provider": a.provider, "model": a.model,
         "params": params, "seed": a.seed, "input_hash": stable_hash(params), "status": "ok",
         "latency_s": a.seconds, "gpu_seconds": a.seconds if a.gpu else None, "cost_usd": 0.0,
         "output": rel(dest), "note": a.note})
    print(f"registered {rel(dest)}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "register":
        return register(argv[1:])
    sb = load_storyboard()
    total = sum(r["dur"] for r in timeline(sb)) + sb["end_card"]["duration_s"]
    print("music:")
    path, ph = resolve(sb, total)
    print(f"  [music] {'placeholder' if ph else 'score'} -> {rel(path)}")


if __name__ == "__main__":
    main()
