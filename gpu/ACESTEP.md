# Generating the score with ACE-Step 1.5

The caption, BPM, key, duration and seeds come from `storyboard.json` via `make gpu-jobs`, which writes
`jobs/music_job.json`. Use the same values wherever you run the model so the run is reproducible.

## Option A: Colab or Kaggle GPU (open weights)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ACE-Step/ACE-Step-1.5.git && cd ACE-Step-1.5
uv sync
uv run acestep          # Gradio UI; check the repo README for the share/port flags and the Python API
```

## Option B: the official hosted demo (no GPU)

The ACE-Step README links a free hosted version and a Hugging Face Space. Use it if your GPU quota is
gone, and say so in COSTS.md (no GPU minutes, but the latency you measured).

## For each candidate (generate three)

1. Paste the caption. Put BPM and key in their own fields, not in the caption. Lyrics: `[Instrumental]`.
2. Set duration from the job file and one of the seeds (11, 22, 33).
3. Time the generation with a stopwatch or the log, download the file into `outputs/music/candidates/`.
4. Register it so it appears in runs.jsonl:

```bash
python -m pipeline.music register outputs/music/candidates/cand_seed11.wav --seed 11 --seconds 14 --provider colab-t4 --gpu
```

Then listen to each **at low volume under the radio cut**, pick one, and set in `storyboard.json`:

```json
"chosen_file": "outputs/music/candidates/cand_seed22.wav",
"choice_reason": "Seed 22 leaves space under the voice in the first 20s and its krar line returns at 55s, matching shot s08."
```

Write the comparison up as an EXPERIMENTS.md entry.
