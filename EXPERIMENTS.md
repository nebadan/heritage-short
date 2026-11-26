# Experiments

Hypothesis → change → result → decision. Evidence is in `runs.jsonl` (input hashes, latency) and the output files.
Entries marked TODO still need the result filled in.

## E1: Picture cut to the voice vs fixed shot durations
- **Hypothesis:** fixed storyboard durations will cut narration off or leave dead air, because spoken Amharic length
  is hard to predict from English text.
- **Change:** `timeline()` makes each shot `max(storyboard duration, narration + 0.4 s lead + 0.7 s tail)`.
- **Result:** with the final narration, s02, s06 and s09 stretched beyond their planned duration (8→8.88 s,
  8→9.96 s, 8→8.04 s); no line was cut off. Total 77.9 s against 75 s planned.
- **Decision:** keep. The storyboard duration is a minimum, the voice decides the rest.

## E2: Model translation vs native correction (Amharic)
- **Hypothesis:** a small fast model can translate simple narration lines well enough to use directly.
- **Change:** `gemini-flash-lite-latest` translated all 9 lines; I corrected them as a native speaker.
- **Result:** 6 of 9 lines needed a correction (see FAILURES F3): place-name spelling, a wrong word, wrong person,
  typos, a meaning change. The model was fluent but not reliable on names and pronouns.
- **Decision:** keep the model as a first draft and always have a native reader. Correct the place name everywhere.

## E3: TTS prompt with style instruction vs text only
- **Hypothesis:** a plain-language style instruction before the text ("Delivery: calm, warm…") gives better delivery.
- **Change:** v1 prompt = instruction + text; v2 = text only (`prompt_v` in the cache key).
- **Result:** v1 spoke the instruction aloud; the radio cut was 186 s. v2 speaks only the Amharic.
- **Decision:** text only. Style must come from the voice choice and post-processing, not from prompt text.

## E4: Trimming pauses and tempo in post vs regenerating the voice
- **Hypothesis:** I can reach the target length and a natural pace by editing the audio (deterministic, free), without
  spending more TTS quota.
- **Change:** `narration_fx`: trim edge silence, cap internal pauses at 0.35 s, `atempo=1.1`.
- **Result:** film 77.9 s, inside 60–90 s, with no extra model calls. TODO: note how natural 1.1× sounds to listeners.
- **Decision:** keep; speed and pause length are now storyboard fields (`voice.speed`, `voice.max_pause_s`).

## E5: Rewording a flagged prompt vs only changing the seed
- **Hypothesis:** the content filter reacts to the prompt wording, not the random seed.
- **Change:** s02 reworded (and seed 202→212).
- **Result:** passed on the first try in 6.3 s. (I changed both at once, so this does not isolate which one fixed it;
  next time change one variable at a time.)
- **Decision:** keep the reworded prompt.

## E6: Fallback model chain for text generation
- **Hypothesis:** trying several models in order turns a provider outage into a slower success instead of a failure.
- **Change:** `text_with_fallback` in `pipeline/script.py`.
- **Result:** 4 models failed in a row for 4 different reasons (503, 404, 429, 503) and the 5th succeeded in 7.4 s.
  Total time spent waiting was high (several minutes), and the first version crashed on a timeout (F1).
- **Decision:** keep, extended to TTS. Next: cap the total retry budget.

## E7: Caching by input hash (the regenerate-one-shot test)
- **Hypothesis:** if each artifact is named by a hash of its inputs, a rerun regenerates only what changed.
- **Change:** `cached()` in `common.py`.
- **Result:** after fixing s02's prompt, `make keyframes` made 1 call and 8 cache hits; `make film` after that made
  0 model calls (all narration and keyframes cached), only FFmpeg renders. TODO: the live walkthrough test
  (change one narration line → exactly one TTS call).
- **Decision:** keep.

## E8: Vertical 9:16 framing: blurred background vs centre crop
- **Hypothesis:** a centre crop of 16:9 keyframes to 9:16 loses too much of the landscape shots.
- **Change:** vertical export places the full 16:9 frame on a blurred, darkened copy, with subtitles below the picture.
- **Result:** TODO: compare one wide shot (s04 or s09) both ways and ask one viewer which they prefer.
- **Decision:** TODO

## E9: Music candidates
- **Hypothesis:** the candidate with the least busy melody in the first 20 s will sit best under the narration.
- **Change:** 3 ACE-Step seeds, same caption/BPM/key.
- **Result:** TODO
- **Decision:** TODO (also set `music.chosen_file` and `music.choice_reason`)

## E10: Ducking strength
- **Hypothesis:** threshold 0.02, ratio 6, attack 300 ms, release 1500 ms (the brief's starting point) will keep the
  voice clear without the music pumping.
- **Change / Result:** TODO: listen once at these settings; if the music is too loud under the voice, try ratio 10 or
  `gain_db` −10 and note which you kept.
