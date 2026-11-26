# Costs

**Money spent: $0.** Every model ran on a free tier or free hosted GPU; assembly ran locally with FFmpeg.

## Measured per stage (from runs.jsonl, `make costs`, 26 Nov 2026)

| Stage | Models | Calls (ok/err) | Cache hits | Mean latency s | Total latency s | GPU min | FFmpeg renders (s) |
|---|---|---|---|---|---|---|---|
| smoke | flux-2-klein-4b, gemini-3.8-flash, gemini-3.8-flash-tts | 5 (4/1) | 0 | 20.3 | 81.3 | 0.0 | 0 (0) |
| script (translate) | gemini-3.8-flash, -3.8-flash-lite, flash-latest, flash-lite-latest | 9 (1/8) | 0 | 7.4 | 7.4 | 0.0 | 0 (0) |
| narration | gemini-3.8-flash-tts, gemini-3.1-flash-tts-preview | 24 (18/6) | 27 | 9.2 | 166.2 | 0.0 | 0 (0) |
| keyframes | @cf/black-forest-labs/flux-2-klein-4b | 20 (18/2) | 25 | 9.9 | 178.4 | 0.0 | 0 (0) |
| shots | FFmpeg Ken Burns (no Wan clip) | 0 | 0 | – | – | 0.0 | 18 (17) |
| music | placeholder / ACE-Step (see below) | 0 | 0 | – | – | 0.0 | 2 (0) |
| assemble | FFmpeg | 0 | 0 | – | – | 0.0 | 4 (184) |

## What the numbers say

- **Model calls: 58, of which 41 succeeded.** 17 failed: 503 overload, 429 quota, 404 unknown model, and 2
  content-filter flags (FAILURES F1, F2, F4, F6). On a free tier, failures are a normal part of the cost.
- **The cache saved 52 calls** (27 narration + 25 keyframes). Without it, every `make film` would have re-spent
  9 TTS and 9 image calls; with the TTS quota this tight, the film could not have been finished.
- **Narration was generated twice** (18 ok calls for 9 lines) because v1 spoke the prompt instruction aloud
  (FAILURES F5). Keyframes were generated twice (18 ok for 9 shots) because the first user test asked for more
  expressive pictures (DESIGN.md).
- **Latency:** an image takes ~10 s on Cloudflare; a TTS line ~6–9 s when the model is not overloaded, up to 26 s with
  retries. The whole pipeline from a warm cache runs in ~1.5 min, almost all of it FFmpeg (assembly 184 s summed over
  4 runs, i.e. ~45 s per film).
- **GPU minutes: 0.** No Wan 2.2 clip was generated (FAILURES F8). Music: see below.

## Free tiers as I found them

| Service | What I hit | Notes |
|---|---|---|
| Gemini API text (gemini-3.8-flash) | 503 overload, then 429 quota within ~15 min of retries | flash-lite-latest still had capacity |
| Gemini API TTS (gemini-3.8-flash-tts) | 429 after roughly 20 calls in the evening | gemini-3.1-flash-tts-preview had separate quota |
| Cloudflare Workers AI (FLUX.2 klein 4B) | no quota error after 20 calls | 2 content-filter rejections (false positives) |
| Colab T4 | used for ACE-Step 1.5 | <fill in: install time, generation time per track> |

## List-price equivalent

Not computed: I did not have time to check each provider's current paid prices. To fill in, put the price per call
(or per GPU-hour) in `PRICES` in `pipeline/costs.py` and rerun `make costs`.

## Frontier comparison

No frontier access this cohort, so no comparison.
