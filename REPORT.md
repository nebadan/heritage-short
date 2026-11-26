# The Road to Ambo: report

**Nebiyu Daniel Fantahun** · B2W0 AI-Content Generation · 26 November 2026

Repository: https://github.com/nebadan/heritage-short · Film 9:16: [link] · Film 16:9: [link] · Walkthrough: [link] · Post: [link]

## 1. What I set out to make, and for whom

Across Ethiopia, people ask for sparkling water by saying "Ambo". Most of them have never been to Ambo, the town west
of Addis Ababa whose spring the water comes from. *The Road to Ambo* is a 78-second film that follows the road from a
minibus station in Addis at dawn to the spring, narrated in Amharic with English subtitles, and ends on the line
"it is not just water. It is a place."

The audience is young Ethiopians (18–35) in Addis and the diaspora who use the word every week, watching on a phone,
vertical, often with the sound off, which is why the subtitles are burned in and the 9:16 version is the main one. I
wanted them to finish the film seeing Ambo as a real place with land, people and a source.

I chose a place rather than a person on purpose: no real face or voice is generated, so there was no consent risk, and
every person in the frame is distant or seen from behind (ETHICS.md).

The pipeline is one contract, `storyboard.json`, validated against a JSON Schema, and five stages that each read it:
narration (Gemini TTS), keyframes (FLUX.2 klein 4B on Cloudflare), shots (FFmpeg Ken Burns, with a Wan 2.2 slot),
music (ACE-Step 1.5 on Colab) and assembly (FFmpeg: ducking, loudness, subtitles, end card, both aspect ratios).
`make film` rebuilds everything; every artifact is cached by a hash of its inputs, so only what changed regenerates.

## 2. What I learned from my audience

**Test 1** (first cut, viewers on Telegram): Beti and Blen both said, unprompted, that the images were not very expressive.
The narration and the idea landed; the pictures did not. Looking again, they had even light, no focal point, and
nothing in the frame carried feeling.

**What changed:** I rewrote the style block (dramatic golden light, light rays through mist, strong foreground and
depth) and gave every shot one emotional focal point: sunlight through the green bottle, a hand on the minibus window,
a beam of light on the bubbling spring, water spilling through cupped hands, a lone traveller looking down at the
town. I also made the camera moves about 50% stronger. Every changed shot records this in its `changed_by` field.
Because only the style and prompts changed, the cache regenerated the 9 keyframes and reused all 9 narration lines.

**Test 2** (same viewers): Beti and Blen said "it's great now." That confirmed the direction, but the answer was too short to improve
anything further. Next time I would ask a sharper question ("which shot would you cut?").

## 3. The hardest problem and how I solved it

The hardest problem was keeping the pipeline running on free tiers that kept failing in different ways
(FAILURES F1, F2, F5, F6):

- The text model returned 503 "high demand" on every call. I added a fallback chain that tries several models in order.
  Its first version crashed on a read timeout I had not handled, and one model name in it did not exist (404).
  After fixing that, four models failed for four different reasons (503, 404, 429, 503) and the fifth answered in 7.4 s.
- My own retries then used up the text quota (429). Retrying without a budget made the outage worse.
- The worst one was silent: the first radio cut came out at **186 s instead of ~75 s**. The length check in assembly
  flagged it, and listening showed why: the TTS model was reading my English prompt instruction ("Read the following
  aloud in Amharic…") before every Amharic line. I changed the provider to send only the words to speak, and added a
  `prompt_v` field to the narration cache key so the cache could not serve the old, wrong audio. I also added an
  editing step that trims silence, caps pauses at 0.35 s and speeds the voice up 10% with FFmpeg, which brought the
  film to 77.9 s without spending more TTS quota. The same quota limits then pushed 6 of 9 lines onto a backup TTS model
  through a second fallback chain.

## 4. A suggested practice that beat my instinct

**Caching every stage by a hash of its inputs** (EXPERIMENTS E7). My instinct was to write one script that runs
everything top to bottom. With the free TTS quota running out, that would have made the film impossible to finish:
the cache saved 52 model calls tonight (27 narration, 25 keyframes, from `runs.jsonl`). When Cloudflare flagged one
prompt, the rerun made 1 image call and reused 8. When the audience asked for better pictures, only the pictures
were regenerated. Evidence: the `cache_hit` lines in runs.jsonl and the table in COSTS.md.

## 5. A suggested practice that did not work as expected

**Letting the model translate the narration** (EXPERIMENTS E2). The suggested pipeline uses Gemini for translation.
The translation was fluent, but 6 of 9 lines needed a native correction: it spelled the town "አንቦ" instead of "አምቦ"
(which would have changed how TTS says the title place), used "ለስላሳ" (soft drink) for sparkling water, used "us"
instead of "me" in a personal line, and changed the meaning of one line. For a lower-resource language, the model is
a first draft and the native speaker is part of the pipeline. Evidence: FAILURES F3, and the `narration` fields in
`storyboard.json` compared with the model output logged in runs.jsonl.

## 6. Curiosity beyond the floor

- **Fallback chains as a measured experiment:** text and TTS both fall back across models, and runs.jsonl records which
  model actually answered each call and why the others failed. This turned an outage into data about how the free
  tier behaves under load (COSTS.md).
- **Schema rules that enforce the brief:** the schema refuses an end card that doesn't say "AI", a `wan` shot without a
  motion prompt, and a real person without a consent record, so those rules can't be broken by accident.
- [If done: Afaan Oromo version. Ambo is an Oromo-speaking town; I tested whether the models handle Oromo and found …]

## 7. What I would build next

1. A retry **budget** per provider per run, with longer backoff on 429 than on 503, so retries can't use up the quota.
2. Generate the Wan 2.2 motion shot on Kaggle (the slot and the fallback are already in the pipeline) and compare it with
   the Ken Burns version in a blind test.
3. An Afaan Oromo narration track, since that is the language of Ambo itself, with a native speaker checking it.
4. A small web form so someone who doesn't code can write their own storyboard and get a film back.
