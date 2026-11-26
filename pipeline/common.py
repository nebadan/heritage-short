"""Shared helpers: paths, env, storyboard loading + validation, hashing/caching,
run logging, retries and ffmpeg. Every stage imports from here so the cache keys
and the timeline are computed in exactly one place."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
STORYBOARD = Path(os.environ.get("STORYBOARD", ROOT / "storyboard.json"))

FPS = 24
W, H = 1280, 720            # master frame (16:9)
VW, VH = 1080, 1920         # vertical export (9:16)
LEAD_S = 0.4                # silence before each narration line
TAIL_S = 0.7                # breathing room after each line


# ---------------------------------------------------------------- env
def _load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
RUN_ID = os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def env(name: str, required: bool = False, default: str | None = None) -> str | None:
    v = os.environ.get(name, default)
    if required and not v:
        sys.exit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return v


def rel(p) -> str | None:
    if p is None:
        return None
    p = Path(p)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# ---------------------------------------------------------- storyboard
def validate_storyboard(sb: dict) -> list[str]:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    errs = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in v.iter_errors(sb)]
    if errs:
        return errs
    ids = [s["id"] for s in sb["shots"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append(f"duplicate shot ids: {dup}")
    chars = {c["id"] for c in sb.get("characters", [])}
    for s in sb["shots"]:
        for c in s.get("characters", []):
            if c not in chars:
                errs.append(f"shot {s['id']}: unknown character '{c}'")
    return errs


def load_storyboard(path: Path = STORYBOARD, check: bool = True) -> dict:
    sb = json.loads(Path(path).read_text(encoding="utf-8"))
    if check:
        errs = validate_storyboard(sb)
        if errs:
            sys.exit("storyboard.json is invalid:\n  - " + "\n  - ".join(errs))
    return sb


def save_storyboard(sb: dict, path: Path = STORYBOARD) -> None:
    Path(path).write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def selected_shots(sb: dict, only: str | None):
    """--only s03,s05 limits a stage to some shots (the cache makes this optional)."""
    if not only:
        return sb["shots"]
    want = set(only.split(","))
    return [s for s in sb["shots"] if s["id"] in want]


# ------------------------------------------------------------- hashing
def stable_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def file_hash(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]


def cached(stage: str, key: str, inputs: dict, ext: str) -> tuple[Path, str]:
    """Output path is <stage>/<key>_<hash(inputs)>.<ext>. Same inputs -> same file -> skip."""
    h = stable_hash(inputs)
    p = OUT / stage / f"{key}_{h}.{ext}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p, h


# --- cache keys: the one place that defines what each artifact depends on
def narration_text(sb: dict, shot: dict) -> str:
    return (shot.get("narration") or "").strip() or (shot.get("narration_en") or "").strip()


def narration_inputs(sb: dict, shot: dict) -> dict:
    return {
        "text": narration_text(sb, shot),
        "language": sb["language"],
        "model": sb["models"]["tts"],
        "voice": sb["voice"]["voice_name"],
        "style": sb["voice"]["style"],
        "prompt_v": 2,  # v2: text only, no spoken instruction
    }


def narration_path(sb: dict, shot: dict) -> Path | None:
    if not narration_text(sb, shot):
        return None
    return cached("narration", shot["id"], narration_inputs(sb, shot), "wav")[0]


def voice_fx(sb: dict) -> dict:
    v = sb["voice"]
    return {"speed": float(v.get("speed", 1.0)), "max_pause_s": float(v.get("max_pause_s", 0.5))}


def narration_fx_path(sb: dict, shot: dict) -> Path | None:
    """Edited narration: leading/trailing silence trimmed, long pauses shortened, tempo adjusted."""
    raw = narration_path(sb, shot)
    if raw is None:
        return None
    inputs = {"raw": raw.name, **voice_fx(sb)}
    return cached("narration_fx", shot["id"], inputs, "wav")[0]


def make_narration_fx(sb: dict, shot: dict) -> Path | None:
    raw, out = narration_path(sb, shot), narration_fx_path(sb, shot)
    if raw is None or not raw.exists():
        return None
    if not out.exists():
        fx = voice_fx(sb)
        th = "-45dB"
        af = (f"silenceremove=start_periods=1:start_threshold={th},"
              f"silenceremove=stop_periods=-1:stop_duration={fx['max_pause_s']}:stop_threshold={th}:"
              f"stop_silence={fx['max_pause_s']},"
              f"areverse,silenceremove=start_periods=1:start_threshold={th},areverse")
        if abs(fx["speed"] - 1.0) > 1e-3:
            af += f",atempo={fx['speed']}"
        ffmpeg(["-i", raw, "-af", af, "-c:a", "pcm_s16le", out])
    return out


def character(sb: dict, cid: str) -> dict:
    return next(c for c in sb.get("characters", []) if c["id"] == cid)


def ref_inputs(sb: dict, cid: str) -> dict:
    c = character(sb, cid)
    return {"description": c["description"], "style": sb["style_block"], "seed": c.get("seed", 0),
            "model": sb["models"]["image"], "size": [W, H], "kind": "reference_sheet"}


def ref_path(sb: dict, cid: str) -> Path:
    return cached("refs", cid, ref_inputs(sb, cid), "png")[0]


def keyframe_inputs(sb: dict, shot: dict) -> dict:
    return {
        "image_prompt": shot["image_prompt"],
        "shot_size": shot["shot_size"],
        "characters": {cid: stable_hash(ref_inputs(sb, cid)) for cid in shot.get("characters", [])},
        "style": sb["style_block"],
        "seed": shot.get("seed", 0),
        "model": sb["models"]["image"],
        "size": [W, H],
    }


def keyframe_path(sb: dict, shot: dict) -> Path:
    return cached("keyframes", shot["id"], keyframe_inputs(sb, shot), "png")[0]


WAN_FRAMES = int(os.environ.get("WAN_FRAMES", "73"))  # 4n+1; 73 frames ~ 3 s at 24 fps


def wan_inputs(sb: dict, shot: dict) -> dict:
    return {"keyframe": stable_hash(keyframe_inputs(sb, shot)), "motion_prompt": shot.get("motion_prompt", ""),
            "camera": shot["camera"], "seed": shot.get("seed", 0), "frames": WAN_FRAMES,
            "model": sb["models"].get("video", "wan2.2-ti2v-5b")}


def wan_path(sb: dict, shot: dict) -> Path:
    return cached("clips_wan", shot["id"], wan_inputs(sb, shot), "mp4")[0]


# ------------------------------------------------------------ timeline
def timeline(sb: dict) -> list[dict]:
    """Shot start/duration. A shot lasts its storyboard duration, or longer if its
    narration needs it. Picture is cut to the voice, as editors do."""
    rows, t = [], 0.0
    for s in sb["shots"]:
        n = make_narration_fx(sb, s)
        nd = probe_duration(n) if n and n.exists() else 0.0
        d = max(float(s["duration_s"]), nd + LEAD_S + TAIL_S)
        d = math.ceil(d * FPS) / FPS
        rows.append({"id": s["id"], "start": round(t, 3), "dur": round(d, 3), "narr": n if n and n.exists() else None,
                     "narr_dur": round(nd, 3), "text_en": s.get("narration_en", "")})
        t += d
    return rows


# ------------------------------------------------------------- logging
def log(record: dict) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": RUN_ID, **record}
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def log_cache_hit(stage: str, shot_id: str, input_hash: str, output) -> None:
    log({"event": "cache_hit", "stage": stage, "shot_id": shot_id, "input_hash": input_hash, "output": rel(output)})
    print(f"  [{stage}/{shot_id}] cached -> {rel(output)}")


class Retryable(Exception):
    """Quota, rate limit or server error: worth waiting and trying again."""


def check_response(r):
    if r.status_code == 429 or r.status_code >= 500:
        raise Retryable(f"HTTP {r.status_code}: {r.text[:300]}")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:800]}")
    return r


def call_model(*, stage, shot_id, provider, model, params, seed, input_hash, fn, output=None,
               tries: int = 4, list_price_usd=None, gpu_seconds=None):
    """Run fn() with retries and exponential backoff; log exactly one line per call."""
    import requests

    t0, attempt = time.time(), 0
    base = {"event": "model_call", "stage": stage, "shot_id": shot_id, "provider": provider, "model": model,
            "params": params, "seed": seed, "input_hash": input_hash}
    while True:
        attempt += 1
        try:
            result = fn()
            log({**base, "status": "ok", "attempts": attempt, "latency_s": round(time.time() - t0, 2),
                 "cost_usd": 0.0, "list_price_usd": list_price_usd, "gpu_seconds": gpu_seconds, "output": rel(output)})
            print(f"  [{stage}/{shot_id}] {model} ok in {time.time() - t0:.1f}s")
            return result
        except (Retryable, requests.ConnectionError, requests.Timeout) as e:
            if attempt >= tries:
                log({**base, "status": "error", "attempts": attempt, "latency_s": round(time.time() - t0, 2), "error": str(e)[:500]})
                raise
            wait = min(60.0, 3 * 2 ** attempt + random.random())  # 6, 12, 24 s: demand spikes need time
            print(f"  [{stage}/{shot_id}] retry {attempt}/{tries - 1} in {wait:.0f}s: {str(e)[:120]}", file=sys.stderr)
            time.sleep(wait)
        except Exception as e:
            log({**base, "status": "error", "attempts": attempt, "latency_s": round(time.time() - t0, 2), "error": str(e)[:500]})
            raise


def log_render(stage: str, shot_id: str, input_hash: str, output, seconds: float, tool: str = "ffmpeg") -> None:
    log({"event": "render", "stage": stage, "shot_id": shot_id, "tool": tool, "input_hash": input_hash,
         "latency_s": round(seconds, 2), "output": rel(output)})


# -------------------------------------------------------------- ffmpeg
def ffmpeg(args, cwd=None) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *map(str, args)]
    subprocess.run(cmd, check=True, cwd=cwd)


def probe_duration(p) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         check=True, capture_output=True, text=True).stdout.strip()
    return float(out or 0)


X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS)]
