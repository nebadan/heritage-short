# Heritage Short: a storyboard-to-film pipeline

A 60–90 second short film about my family, narrated in Amharic with English subtitles and an original
score, generated from one file, `storyboard.json`, by a five-stage pipeline of free models and FFmpeg.

**Film:** _link to vertical and horizontal cuts_ · **Post:** _link_ · **Walkthrough:** _link_

## One command

```bash
make setup        # pip install, creates .env from .env.example
# fill in .env: GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
make film         # validate -> narration -> keyframes -> shots -> music -> assemble
```

Output: `outputs/final/film_16x9.mp4`, `outputs/final/film_9x16.mp4`, `outputs/final/film.en.srt`.

Everything is cached by a hash of its inputs. Change one shot's narration or image prompt in `storyboard.json`,
run `make film` again, and only that shot is regenerated. `runs.jsonl` shows one new model call and cache hits
for everything else.

Requirements: Python 3.10+, FFmpeg 4.4+ on PATH. No paid service is needed.

## Other commands

| Command | What it does |
|---|---|
| `make smoke` | calls each provider once, logs latency to `runs.jsonl` |
| `make radio` | radio cut: narration + temp music on black, for the first audience test |
| `make draft` | drafts `storyboard.draft.json` from `story/notes.md` with Gemini (validated, never overwrites) |
| `make translate` | fills `shots[].narration` (Amharic) from `narration_en` with Gemini |
| `make refs` | character reference sheets only |
| `make gpu-jobs` | writes job files for Wan 2.2 (Kaggle) and ACE-Step (Colab) |
| `make costs` | per-stage calls, cache hits, latency, GPU minutes from `runs.jsonl` |

GPU stages run on Kaggle/Colab and feed the cache: see `gpu/kaggle_wan22.py` and `gpu/ACESTEP.md`.
If a Wan clip is missing, that shot falls back to a slow pan/zoom over its keyframe, so `make film` always finishes.

## What it costs

$0 in money. Measured latency and GPU minutes per stage are in [COSTS.md](COSTS.md).

## Repository

```
storyboard.json      the contract: shots, durations, prompts, narration, music, end card
schema/              JSON Schema, validated before every stage
pipeline/            one module per stage + common.py (cache keys, timeline, logging, retries)
gpu/                 Kaggle (Wan 2.2) and Colab (ACE-Step) scripts
runs.jsonl           one line per model call, cache hit and render
outputs/             every generated file, named <shot>_<input-hash>
DESIGN.md  ARCHITECTURE.md  EXPERIMENTS.md  FAILURES.md  COSTS.md  ETHICS.md
```

## Models and licences

Gemini 3.8 Flash / Flash TTS (Gemini API free tier) · FLUX.2 [klein] 4B, Apache 2.0 (Cloudflare Workers AI) ·
Wan 2.2 TI2V-5B, Apache 2.0 · ACE-Step 1.5, MIT · FFmpeg. Details in [ETHICS.md](ETHICS.md).
The film carries an AI end card and was posted with the platform's AI label.
