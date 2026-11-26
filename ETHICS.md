# Ethics: consent, labelling, licences

## Consent

Real people shown or voiced in the film (face, likeness, voice, or words put in their mouth):

**No real person appears or is voiced in this film.** The film is about a place (Ambo), not a person.

- `storyboard.json` has no characters; every person in the pictures is small, in the distance, or seen from behind
  (passengers in the minibus, students in the street, a farmer far away), and generated from text only, never from a photo.
- Shot s08 shows only two hands.
- Narration uses the stock Gemini TTS voice "Charon". No voice was cloned; the first-person lines are mine.
- The schema enforces this for future edits: a character marked `real_person: true` cannot validate without a `consent_ref`.

## Labelling

- AI end card in the film: "Made with AI" + tools (from `storyboard.json` → `end_card`).
- Platform AI disclosure switched on when posting: (platform, screenshot link)
- Provenance metadata (SynthID / C2PA) left intact; no watermark removed.

## Licences

| Component | Licence | Output use |
|---|---|---|
| FLUX.2 [klein] 4B | Apache 2.0 | |
| Wan 2.2 TI2V-5B | Apache 2.0 | |
| ACE-Step 1.5 | MIT; outputs usable commercially | |
| Gemini API (text, TTS) | Gemini API terms | free tier may use inputs to improve products |
| FFmpeg | LGPL/GPL | tool only |

## Private data

What I kept out of free endpoints that may train on inputs: no private family details were sent; the prompts describe public places and generic scenes only.
