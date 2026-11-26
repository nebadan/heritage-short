# Design

## Audience and intent (written before generating anything)

- **Who watches:** young Ethiopians (18–35) in Addis Ababa and in the diaspora who drink "Ambo" every week but have never been there.
- **Where and how:** on their phones, mostly vertical, shared on Telegram and TikTok, often with the sound off at first (hence burned-in English subtitles).
- **What they should feel or understand at the end:** that Ambo is a real place with people, land and a source, and enough curiosity to visit, or to ask where the everyday things around them come from.
- **How might we…** help people who say "Ambo" every day see the town behind the word?

## Story

- Logline: Everyone in Ethiopia orders "Ambo" sparkling water, but few know it is a place. A journey from Addis Ababa to the town and the spring it is named after.
- Beats (one picture each): the bottle (hook) → it's a town (turn) → leaving Addis at dawn → the farmland → the mountains closer → arriving in Ambo → the spring → tasting at the source → "it is a place".
- Why this story, and who it belongs to (did you talk to them?):

## User test 1: first cut (narration, temporary music, first keyframes)

Shared on Telegram as a vertical MP4, ~19:40, 26 Nov. Question asked: "What did you feel at the end? Which moment was weakest?"

| Who (relation) | How | What they said | Where they reacted |
|---|---|---|---|
| Beti | Telegram | The images are not very expressive | the pictures overall |
| Blen | Telegram | The images are not very expressive | the pictures overall |
| [third viewer] | Telegram | [their words] | |

**Insight:** the story and narration worked, but the pictures were flat: even light, no clear focal point, nothing
in them carried feeling. Both Beti and Blen named the same problem without being prompted, so it was not taste.

**What changed in storyboard.json because of it** (every shot is marked `"changed_by": "user test 1 …"`):
- New `style_block`: dramatic golden light, light rays through mist, strong foreground and depth, saturated colour,
  "like a still from an animated feature film".
- All 9 `image_prompt`s rewritten around one emotional focal point each: sunlight through the green bottle (s01),
  a huge sun rising behind the minibuses (s02), a hand on the minibus window (s03), a beam of light on the bubbling
  spring (s07), backlit water spilling through cupped hands (s08), a lone traveller looking down at the town (s09).
- Ken Burns camera moves made ~50% stronger (zoom 12%→18%, pans over 15% of the frame), and cameras chosen per shot.
- Side effect: two of the new, more dramatic prompts (s04, and earlier s02) were flagged by Cloudflare's content filter
  and had to be reworded (FAILURES F4).

## User test 2: near-final cut (expressive keyframes)

Same people, same question, ~20:00, 26 Nov.

| Who (relation) | How | What they said | Where they reacted |
|---|---|---|---|
| Beti | Telegram | It's great now | |
| Blen | Telegram | It's great now | |
| [third viewer] | Telegram | [their words] | |

**Insight:** the change answered the complaint: the same viewers who called the pictures flat now called the film
great. The feedback was short, so it confirms the direction more than it tells me what to improve next.

**What changed:** nothing further in the pictures. Next time I would ask a more specific second question
("which shot would you cut?") to get feedback that can still change the film.

## Shot reasons

Each shot's reason is in `storyboard.json` (`shots[].reason`). Shots changed by a test say so in `changed_by`.
