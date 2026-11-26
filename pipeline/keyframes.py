"""Stage: keyframes. First a reference sheet per character, then one keyframe per
shot conditioned on the reference sheets (FLUX.2 klein supports reference images)."""
from __future__ import annotations

import argparse
import io
import sys

from PIL import Image

from . import providers
from .common import (H, W, call_model, cached, character, keyframe_inputs, load_storyboard, log_cache_hit,
                     ref_inputs, ref_path, selected_shots)

SIZE_WORDS = {
    "extreme_wide": "extreme wide shot, subject small in a large landscape",
    "wide": "wide shot, full figure and surroundings",
    "medium": "medium shot, from the waist up",
    "medium_close_up": "medium close-up, from the chest up",
    "close_up": "close-up",
    "extreme_close_up": "extreme close-up detail",
    "insert": "insert shot, close detail of an object or hands",
}


def to_png(data: bytes, out, w=W, h=H) -> None:
    """Normalise whatever the model returns to an exact WxH PNG (centre crop)."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - w) // 2, (im.height - h) // 2
    im.crop((left, top, left + w, top + h)).save(out)


def make_ref(sb, cid) -> bool:
    inputs = ref_inputs(sb, cid)
    out, h = cached("refs", cid, inputs, "png")
    if out.exists():
        log_cache_hit("refs", cid, h, out)
        return True
    c = character(sb, cid)
    prompt = (f"Character reference sheet of {c['description']}. The same person shown three times side by side: "
              f"front view, three-quarter view and profile, full body, neutral plain light background, even light. "
              f"Style: {sb['style_block']}. No text or lettering.")
    try:
        data = call_model(stage="refs", shot_id=cid, provider="cloudflare-workers-ai", model=inputs["model"],
                          params={"prompt": prompt, "size": inputs["size"]}, seed=inputs["seed"], input_hash=h, output=out,
                          fn=lambda: providers.flux_image(prompt, inputs["model"], W, H, inputs["seed"]))
        to_png(data, out)
        return True
    except Exception as e:
        print(f"  [refs/{cid}] FAILED: {e}", file=sys.stderr)
        return False


def make_keyframe(sb, s) -> bool:
    inputs = keyframe_inputs(sb, s)
    out, h = cached("keyframes", s["id"], inputs, "png")
    if out.exists():
        log_cache_hit("keyframes", s["id"], h, out)
        return True
    chars = s.get("characters", [])
    refs = [ref_path(sb, cid) for cid in chars if ref_path(sb, cid).exists()]
    who = "; ".join(character(sb, cid)["description"] for cid in chars)
    prompt = s["image_prompt"].rstrip(".") + "."
    if who:
        prompt += f" The character: {who}."
    if refs:
        prompt += " Keep the character's face, hair and clothing exactly as in the reference image."
    prompt += f" {SIZE_WORDS[s['shot_size']]}. Style: {sb['style_block']}. No text or lettering."
    model = inputs["model"]
    if refs and "flux-2" not in model:
        print(f"  [keyframes/{s['id']}] note: {model} ignores reference images", file=sys.stderr)
    try:
        data = call_model(stage="keyframes", shot_id=s["id"], provider="cloudflare-workers-ai", model=model,
                          params={"prompt": prompt, "size": inputs["size"], "refs": [r.name for r in refs]},
                          seed=inputs["seed"], input_hash=h, output=out,
                          fn=lambda: providers.flux_image(prompt, model, W, H, inputs["seed"], refs))
        to_png(data, out)
        return True
    except Exception as e:
        print(f"  [keyframes/{s['id']}] FAILED: {e}", file=sys.stderr)
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated shot ids")
    ap.add_argument("--refs-only", action="store_true", help="only generate character reference sheets")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    print("keyframes:")
    failed = [c["id"] for c in sb.get("characters", []) if not make_ref(sb, c["id"])]
    if not a.refs_only:
        failed += [s["id"] for s in selected_shots(sb, a.only) if not make_keyframe(sb, s)]
    if failed:
        sys.exit(f"keyframes failed for {failed} (see runs.jsonl); rerun to retry only those")


if __name__ == "__main__":
    main()
