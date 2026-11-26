"""Thin wrappers around each hosted API. Stages call these through common.call_model,
which adds retries and the runs.jsonl line. Swap a provider here without touching stages."""
from __future__ import annotations

import base64
import io
import re
import wave
from pathlib import Path

import requests

from .common import check_response, env

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CF = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"


def _gemini_headers():
    return {"x-goog-api-key": env("GEMINI_API_KEY", required=True), "Content-Type": "application/json"}


def _first_parts(j: dict) -> list:
    try:
        return j["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Gemini returned no content: {str(j)[:600]}")


# ---------------------------------------------------------------- text
def gemini_text(prompt: str, model: str, json_mode: bool = True, temperature: float = 0.7) -> str:
    cfg = {"temperature": temperature}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
    r = requests.post(GEMINI.format(model=model), headers=_gemini_headers(), json=body, timeout=90)
    check_response(r)
    return "".join(p.get("text", "") for p in _first_parts(r.json()))


# ----------------------------------------------------------------- TTS
def gemini_tts(text: str, model: str, voice: str, style: str, language_name: str) -> bytes:
    """Returns WAV bytes. The API returns raw 16-bit PCM (or WAV on newer models)."""
    # Send ONLY the words to speak. An earlier version put an English instruction before
    # the text and the model read that instruction aloud (see FAILURES.md).
    prompt = text
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    r = requests.post(GEMINI.format(model=model), headers=_gemini_headers(), json=body, timeout=180)
    check_response(r)
    part = next((p["inlineData"] for p in _first_parts(r.json()) if "inlineData" in p), None)
    if not part:
        raise RuntimeError("TTS response had no audio part")
    data = base64.b64decode(part["data"])
    if data[:4] == b"RIFF":
        return data
    m = re.search(r"rate=(\d+)", part.get("mimeType", ""))
    rate = int(m.group(1)) if m else 24000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return buf.getvalue()


# --------------------------------------------------------------- image
def flux_image(prompt: str, model: str, width: int, height: int, seed: int | None, refs: list[Path] = ()) -> bytes:
    """Cloudflare Workers AI. FLUX.2 models take multipart form data (and up to 4
    reference images); FLUX.1 schnell takes JSON and no references."""
    url = CF.format(acct=env("CLOUDFLARE_ACCOUNT_ID", required=True), model=model)
    headers = {"Authorization": f"Bearer {env('CLOUDFLARE_API_TOKEN', required=True)}"}
    if "flux-2" in model:
        files = {"prompt": (None, prompt), "width": (None, str(width)), "height": (None, str(height))}
        if seed is not None:
            files["seed"] = (None, str(seed))
        for i, p in enumerate(list(refs)[:4]):
            files[f"input_image_{i}"] = (Path(p).name, Path(p).read_bytes(), "image/png")
        r = requests.post(url, headers=headers, files=files, timeout=180)
    else:
        body = {"prompt": prompt, "steps": 4}
        if seed is not None:
            body["seed"] = seed
        r = requests.post(url, headers=headers, json=body, timeout=180)
    check_response(r)
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    j = r.json()
    img = (j.get("result") or {}).get("image") or j.get("image")
    if not img:
        raise RuntimeError(f"No image in Cloudflare response: {str(j)[:400]}")
    return base64.b64decode(img)
