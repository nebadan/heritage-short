"""Stage: moving shots. Each shot becomes a WxH 24 fps clip of exactly its timeline
duration. Source is a Wan 2.2 clip generated on Kaggle if one exists for the current
inputs, otherwise a slow pan/zoom (Ken Burns) over the keyframe.

  python -m pipeline.shots                      build all shot clips
  python -m pipeline.shots register-wan FILE    log Kaggle timings.json into runs.jsonl
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from .common import (FPS, H, OUT, W, X264, cached, ffmpeg, file_hash, keyframe_path, load_storyboard, log,
                     log_cache_hit, log_render, rel, selected_shots, timeline, wan_inputs, wan_path)


def zoompan_expr(camera: str, n: int) -> tuple[str, str, str]:
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return {
        "static": (f"1+0.03*on/{n}", cx, cy),
        "push_in": (f"1+0.18*on/{n}", cx, cy),
        "pull_out": (f"1.18-0.18*on/{n}", cx, cy),
        "pan_left": ("1.15", f"(iw-iw/zoom)*(1-on/{n})", cy),
        "pan_right": ("1.15", f"(iw-iw/zoom)*on/{n}", cy),
        "tilt_up": ("1.15", cx, f"(ih-ih/zoom)*(1-on/{n})"),
        "tilt_down": ("1.15", cx, f"(ih-ih/zoom)*on/{n}"),
    }[camera]


def kenburns(img: Path, out: Path, dur: float, camera: str) -> None:
    n = max(1, round(dur * FPS))
    z, x, y = zoompan_expr(camera, n)
    # upscale first: zoompan on a 2x image avoids the usual jitter
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    ffmpeg(["-i", img, "-vf", vf, "-frames:v", n, *X264, "-an", out])


def fit_clip(src: Path, out: Path, dur: float) -> None:
    """Scale/crop a generated clip to the frame, trim it, and hold the last frame if short.
    Also trims the weak first 0.25 s that many generated clips have."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
          f"trim=start=0.25,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=30,format=yuv420p")
    ffmpeg(["-i", src, "-vf", vf, "-t", f"{dur:.3f}", *X264, "-an", out])


def build(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    rows = {r["id"]: r for r in timeline(sb)}
    failed = []
    print("shots:")
    for s in selected_shots(sb, a.only):
        kf = keyframe_path(sb, s)
        if not kf.exists():
            print(f"  [shots/{s['id']}] missing keyframe, run `make keyframes`", file=sys.stderr)
            failed.append(s["id"])
            continue
        dur = rows[s["id"]]["dur"]
        source = "kenburns"
        if s["motion"] == "wan":
            wp = wan_path(sb, s)
            if wp.exists():
                source = f"wan:{file_hash(wp)}"
            else:
                print(f"  [shots/{s['id']}] no Wan clip for current inputs ({wp.name}); using Ken Burns fallback")
                log({"event": "fallback", "stage": "shots", "shot_id": s["id"], "wanted": "wan", "used": "kenburns",
                     "missing": rel(wp)})
        inputs = {"keyframe": kf.name, "camera": s["camera"], "dur": dur, "source": source, "fps": FPS, "size": [W, H], "kb_v": 2}
        out, h = cached("shots", s["id"], inputs, "mp4")
        if out.exists():
            log_cache_hit("shots", s["id"], h, out)
            continue
        t0 = time.time()
        if source.startswith("wan:"):
            fit_clip(wan_path(sb, s), out, dur)
        else:
            kenburns(kf, out, dur, s["camera"])
        log_render("shots", s["id"], h, out, time.time() - t0)
        print(f"  [shots/{s['id']}] {source} {dur:.2f}s -> {rel(out)}")
    if failed:
        sys.exit(f"shots failed for {failed}")


def register_wan(argv):
    """Import clips + timings produced by gpu/kaggle_wan22.py and log one line per clip."""
    ap = argparse.ArgumentParser()
    ap.add_argument("timings", help="timings.json from the Kaggle run")
    ap.add_argument("--clips-dir", help="folder with the downloaded clips (default: next to timings.json)")
    a = ap.parse_args(argv)
    tpath = Path(a.timings)
    clips_dir = Path(a.clips_dir) if a.clips_dir else tpath.parent
    dest = OUT / "clips_wan"
    dest.mkdir(parents=True, exist_ok=True)
    for t in json.loads(tpath.read_text()):
        src = clips_dir / t["output"]
        if t.get("status") != "ok" or not src.exists():
            log({"event": "model_call", "stage": "shots", "shot_id": t["shot_id"], "provider": "kaggle",
                 "model": t.get("model", "wan2.2-ti2v-5b"), "status": "error", "error": t.get("error", "missing clip"),
                 "latency_s": t.get("seconds"), "gpu_seconds": t.get("seconds"), "input_hash": t["wan_hash"]})
            print(f"  {t['shot_id']}: error logged")
            continue
        shutil.copy2(src, dest / t["output"])
        log({"event": "model_call", "stage": "shots", "shot_id": t["shot_id"], "provider": "kaggle",
             "model": t.get("model", "wan2.2-ti2v-5b"), "params": t.get("params", {}), "seed": t.get("seed"),
             "input_hash": t["wan_hash"], "status": "ok", "latency_s": t["seconds"], "gpu_seconds": t["seconds"],
             "gpu": t.get("gpu"), "cost_usd": 0.0, "output": rel(dest / t["output"])})
        print(f"  {t['shot_id']}: {t['seconds']:.0f}s on {t.get('gpu')} -> {rel(dest / t['output'])}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "register-wan":
        register_wan(argv[1:])
    else:
        build(argv)


if __name__ == "__main__":
    main()
