# Architecture

## The contract

`storyboard.json` is the only thing stages share. It is validated against `schema/storyboard.schema.json`
(JSON Schema 2020-12) at the start of every stage, plus checks the schema can't express (unique shot ids,
characters that exist). The schema also encodes deliverable rules: 8–12 shots, every shot has a `reason`,
a `wan` shot must have a `motion_prompt`, a character marked `real_person` must have a `consent_ref`, and the
end card text must contain "AI".

## Stages

```
storyboard.json ──► narration ──► keyframes ──► shots ──► music ──► assemble ──► film_16x9.mp4 / film_9x16.mp4
 (validated)        Gemini TTS    FLUX.2 klein   Ken Burns or     ACE-Step     FFmpeg
                    one WAV/shot  ref sheet first  Wan 2.2 clip   (Colab)      duck, subs, loudness, end card
```

| Stage | Reads | Writes | Runs on |
|---|---|---|---|
| `script` (pre-production) | `story/notes.md`, storyboard | `storyboard.draft.json`, `narration` fields | Gemini API |
| `narration` | narration text, voice, TTS model | `outputs/narration/<shot>_<hash>.wav` | Gemini API |
| `keyframes` | characters, style block, image prompt, seed | `outputs/refs/…png`, `outputs/keyframes/…png` | Cloudflare Workers AI |
| `shots` | keyframe, camera, timeline duration, Wan clip if any | `outputs/shots/<shot>_<hash>.mp4` | local FFmpeg (+ Kaggle for Wan) |
| `music` | chosen ACE-Step candidate | `outputs/music/score_<hash>.wav` | Colab/Kaggle, registered locally |
| `assemble` | all of the above + timeline | `outputs/final/*` | local FFmpeg |

`providers.py` holds the API calls; stages hold the logic. Swapping a provider touches one function.

## Timing: picture is cut to the voice

`common.timeline()` gives each shot `max(storyboard duration, narration length + 0.4 s lead + 0.7 s tail)`,
rounded up to a whole frame. Narration therefore never gets cut off, and the storyboard duration acts as a
minimum. Subtitles are timed from the same numbers, so they can't drift from the voice.

## Caching

Every artifact is written as `<stage>/<shot>_<hash>.<ext>`. The hash is a SHA-256 of exactly the inputs that
artifact depends on, and those input sets are defined once, in `common.py`:

- narration: text, language, TTS model, voice, style
- reference sheet: character description, style block, seed, model, size
- keyframe: image prompt, shot size, style block, seed, model, size, **hash of each referenced character sheet**
- Wan clip: keyframe hash, motion prompt, camera, seed, frame count
- shot clip: keyframe file name (contains its hash), camera, timeline duration, source (Ken Burns or Wan clip hash)

If the file exists, the stage logs a `cache_hit` and skips the call. Dependencies flow through the hashes: edit
a character's description and that sheet, plus every keyframe using it, plus their shot clips, are regenerated;
nothing else is. Editing one narration line regenerates that WAV; its new length changes that shot's
duration, so only that shot clip is re-rendered (FFmpeg, no model call). Old files are never deleted, so
switching back to an earlier prompt is free.

The GPU stages that run off-machine (Wan, ACE-Step) feed the same cache. `make gpu-jobs` writes the expected
output file names into the job files; the Kaggle script produces files with exactly those names, and
`register-wan` copies them into `outputs/clips_wan/` and logs each call.

## Failure handling

- **Retries:** `call_model` retries HTTP 429/5xx, connection errors and timeouts up to 4 times with exponential
  backoff and jitter (2, 4, 8 s…). Other HTTP errors fail at once with the response body.
- **Partial failure:** a stage keeps going after a failed shot, then exits non-zero naming the failed shots.
  Rerunning retries only those, because the rest are cached.
- **Fallbacks:** a `wan` shot with no clip falls back to Ken Burns and logs a `fallback` event. A missing
  score uses a placeholder drone and warns. `make film` always produces a playable film.
- **Kaggle sessions:** `gpu/kaggle_wan22.py` saves `timings.json` after every clip and skips clips that already
  exist, so a timed-out session can resume.
- **Logging:** every model call writes one line to `runs.jsonl` (stage, shot, provider, model, params, seed,
  input hash, latency, attempts, status, cost, GPU seconds, output), including failed calls with the error.
  All stages in one `make` share a `run_id`.
- **Secrets:** keys only in `.env`, which is git-ignored; `.env.example` documents them.

## Assembly (all FFmpeg)

1. Each narration line is placed at its shot start + 0.4 s, padded to the shot length, concatenated, and
   normalised to −16 LUFS so the voice level is consistent before mixing.
2. Music: looped/trimmed to the film length, faded in and out, set to `music.gain_db`, then ducked under the
   voice with `sidechaincompress` (the voice is the sidechain; settings from `music.duck`).
3. Voice and ducked music are mixed and normalised to −14 LUFS integrated, −1 dBTP.
4. Shot clips + the end card are concatenated into a 1280×720 master without subtitles.
5. 16:9: subtitles burned from an ASS file sized for 1280×720. 9:16: the master is placed over a blurred,
   darkened copy of itself at 1080×1920, and subtitles go just below the picture, above the platform buttons.
   Both use ≤2 lines per subtitle; a `.srt` is also written for platform captions.
