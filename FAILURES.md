# Failures

Real blockers hit while making the film on 26 Nov 2026, in the order they happened. Evidence for each is in
`runs.jsonl` (every failed call is logged with its error) and in the git history of the files named.

## F1: Gemini text model overloaded, and the fallback chain itself had bugs
- **Stage:** script (`make translate`), ~18:55–19:07
- **What happened:** `gemini-3.8-flash` returned HTTP 503 UNAVAILABLE ("experiencing high demand") on every call. The
  pipeline retried 3 times with backoff (3, 4, 8 s) and stopped. The smoke test earlier had already taken 60 s for a
  one-word reply, which was the first sign.
- **What I tried, in order:**
  1. Reran after a short wait: same 503.
  2. Added an automatic **fallback chain** (`pipeline/script.py: text_with_fallback`): on 503 or 404, try
     `gemini-3.8-flash-lite → gemini-flash-latest → gemini-flash-lite-latest → gemini-2.5-flash → gemini-2.5-flash-lite`,
     and lengthened backoff to 6/12/24 s. Each attempt is logged with the model that actually ran and `fallback_from`.
  3. The chain found that `gemini-3.8-flash-lite` does not exist (404), then `gemini-flash-latest` was also 503,
     and then the run **crashed with a ReadTimeout** after 180 s: my fallback only caught 503/404, not timeouts.
     Fixed: timeouts and connection errors now also move to the next model, and text timeout is 90 s.
  4. Next run: 503 → 404 → 429 → 503, then **`gemini-flash-lite-latest` answered in 7.4 s**.
- **What fixed it:** the fallback chain (after fixing its timeout bug).
- **Lesson:** a single hard-coded model name is a single point of failure on a free tier. Fallbacks must cover every
  transient failure type (503, 429, timeouts), not just the one you saw first.

## F2: My own retries used up the free quota (429)
- **Stage:** smoke test, ~19:05
- **What happened:** after F1, `make smoke` returned HTTP 429 "You exceeded your current quota" on the text model.
  The repeated retries on 503s had spent the free-tier requests. TTS and Cloudflare still passed (separate quotas).
- **What I did:** stopped running the smoke test, since it also spends a TTS call I needed for narration.
- **Lesson:** retrying without a budget makes an outage worse. Next time: cap total retries per provider per run,
  back off much longer on 429 than on 503, and keep smoke tests out of the main loop once a provider is known to work.

## F3: Machine translation errors in Amharic
- **Stage:** script (translate)
- **What happened:** the Amharic from `gemini-flash-lite-latest` was understandable but not film-ready:
  - spelled the town **"አንቦ"** instead of the usual **"አምቦ"** (risked TTS mispronouncing the title place)
  - used **ለስላሳ** (soft drink) for sparkling water
  - wrong person: **ይሰጠናል** ("gives us") in a first-person line, should be **ይሰጠኛል** ("gives me")
  - typo **ሆኄ** for **ሆኜ**, stray spaces inside words (**ባሕር ዛፍ ዎች**, **በ ቀይ**), an English comma
  - s06 started with **ከንጋት በኋላ** ("after dawn"), which changed the meaning of "Then the town appears"
- **What fixed it:** corrected by hand (native speaker); final lines are in `storyboard.json` → `shots[].narration`.
- **Lesson:** for a lower-resource language, a model translation is a draft. A native reader is part of the pipeline.

## F4: Keyframe flagged by Cloudflare's content filter (false positive)
- **Stage:** keyframes, s02
- **What happened:** HTTP 400, code 3030, "Your output has been flagged. Please choose another prompt". The prompt was
  an innocent scene: a minibus station in Addis Ababa at dawn with people carrying bags.
- **What fixed it:** reworded the prompt (parked minibus taxis, travellers small in the distance) and changed the
  seed from 202 to 212. Recorded in the shot's `changed_by` field. The other 8 shots were cached and not re-generated.
- **Lesson:** stage-level isolation paid off: one failed shot did not stop the rest, and the rerun touched only s02.

## F5: The TTS model read my prompt instructions aloud; the radio cut was 186 s
- **Stage:** narration → assemble (`make radio`), ~19:12
- **What happened:** assembly warned "film is 186.2s; the brief asks for 60-90s". Listening to one line showed why: the
  voice first spoke the English instruction ("Read the following aloud in Amharic. Delivery: …") and then the Amharic.
  The TTS model treats everything in the prompt as words to speak.
- **What fixed it:** `providers.gemini_tts` now sends **only the words to speak**. I added `"prompt_v": 2` to the
  narration cache key in `common.py`, so all 9 lines were regenerated (and old, wrong audio could not be reused).
  I also added a narration edit step (`narration_fx`): trims leading/trailing silence, caps pauses at 0.35 s, and
  speeds the voice up 10% with `atempo` (pitch kept). Result: 77.9 s.
- **Lesson:** the length check in assembly caught it, but only listening explained it. Changing a prompt template
  must change the cache key, or the cache will happily serve the old, wrong output.

## F6: TTS quota nearly exhausted
- **Stage:** narration. s09 got HTTP 429 once and succeeded on retry.
- **What I did:** added a TTS fallback chain (`gemini-3.1-flash-tts-preview`, `gemini-2.5-flash-preview-tts`, …) so a
  quota error on one model moves to the next instead of failing the shot.

## F7: Getting an original score: four routes
- **Stage:** music
- **What happened:**
  1. acemusic.ai (hosted ACE-Step 1.5, linked from the ACE-Step README) generates for free but asks for a paid
     upgrade to download.
  2. The official Hugging Face Space (ACE-Step/Ace-Step-v1.5, ZeroGPU) did not work for me.
  3. Colab T4 with the official repo: `uv` installed to `/usr/local/bin`, not `~/.local/bin` (fixed the path); then
     `acestep` crashed on import because Colab sets `MPLBACKEND=module://matplotlib_inline…`, which matplotlib inside
     the uv virtualenv rejects (fixed with `MPLBACKEND=Agg`). The UI then ran, but generation **timed out after 600 s**
     twice: first an 85 s track with batch size 2, then a 30 s track with batch size 1. ACE-Step's own message
     suggests VRAM or a stalled diffusion loop on the 16 GB T4.
  4. **What fixed it:** I added `pipeline/score.py`, a small original score composed in code (Karplus-Strong plucked
     string on a D major pentatonic melody, a soft drum pulse at 84 BPM, a slow pad; deterministic from a seed, ~8 s on
     a laptop CPU). The music stage now uses it automatically when no ACE-Step candidate is chosen.
- **Lesson:** a GPU stage on free hardware needs a fallback that produces something usable without the GPU. The end
  card was changed to say "Music: composed in code" so the credits stay true.

## F8: Wan 2.2 motion shot not generated
- **Stage:** shots, s04
- **What happened:** skipped for time: after ACE-Step timed out twice on a Colab T4, a 5B video model on a Kaggle T4 was not realistic before the deadline. The shots stage logged a `fallback` event and used
  a slow Ken Burns move over the keyframe, so `make film` still finished.
