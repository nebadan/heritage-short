"""Stage: assembly. Pure FFmpeg, deterministic. Builds from the storyboard:
voice track -> music ducked under voice -> loudness -14 LUFS / -1 dBTP ->
English subtitles (burned in + .srt) -> AI end card -> 16:9 and 9:16 exports.

  python -m pipeline.assemble           final film (needs shot clips)
  python -m pipeline.assemble --radio   radio cut: narration + music on black
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import music
from .common import (FPS, H, LEAD_S, OUT, VH, VW, W, X264, cached, ffmpeg, keyframe_path, load_storyboard, log_render,
                     probe_duration, rel, timeline)

FINAL = OUT / "final"
TMP = OUT / "tmp"
FONTS = ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]


# ------------------------------------------------------------ end card
def _font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def endcard_png(sb, out: Path) -> None:
    img = Image.new("RGB", (W, H), (14, 12, 10))
    d = ImageDraw.Draw(img)
    lines = [(sb["title"], _font(52), (240, 230, 210)), ("", _font(20), None),
             (sb["end_card"]["text"], _font(34), (240, 230, 210))]
    if sb["end_card"].get("subtext"):
        for ln in textwrap.wrap(sb["end_card"]["subtext"], 70):
            lines.append((ln, _font(22), (170, 160, 145)))
    heights = [(d.textbbox((0, 0), t or " ", font=f)[3] + 14) for t, f, _ in lines]
    y = (H - sum(heights)) // 2
    for (t, f, c), hh in zip(lines, heights):
        if t:
            w = d.textbbox((0, 0), t, font=f)[2]
            d.text(((W - w) // 2, y), t, font=f, fill=c)
        y += hh
    img.save(out)


# ----------------------------------------------------------- subtitles
def _chunks(text: str, start: float, end: float, width: int = 42):
    """At most 2 lines of ~42 chars per subtitle; long lines split over time by length."""
    lines = textwrap.wrap(text, width)
    groups = [lines[i:i + 2] for i in range(0, len(lines), 2)] or [[]]
    total = sum(len(" ".join(g)) for g in groups) or 1
    t = start
    for g in groups:
        d = (end - start) * len(" ".join(g)) / total
        yield t, t + d, g
        t += d


def subtitle_events(rows, width: int = 42):
    for r in rows:
        if not r["text_en"]:
            continue
        s = r["start"] + LEAD_S
        e = s + (r["narr_dur"] or max(1.5, r["dur"] - LEAD_S - 0.3))
        yield from _chunks(r["text_en"], s, e, width)


def _ts(t, sep):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    if sep == ",":
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{h}:{m:02d}:{s:05.2f}"


def write_srt(rows, path: Path):
    out = []
    for i, (s, e, g) in enumerate(subtitle_events(rows), 1):
        out += [str(i), f"{_ts(s, ',')} --> {_ts(e, ',')}", *g, ""]
    path.write_text("\n".join(out), encoding="utf-8")


def write_ass(rows, path: Path, w: int, h: int, size: int, margin_v: int, width: int = 42):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{size},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,{max(2, size // 16)},1,2,{w // 14},{w // 14},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    nl = r"\N"
    ev = [f"Dialogue: 0,{_ts(s, '.')},{_ts(e, '.')},Default,,0,0,0,,{nl.join(g)}"
          for s, e, g in subtitle_events(rows, width)]
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


# --------------------------------------------------------------- audio
def voice_track(sb, rows, total: float, out: Path):
    TMP.mkdir(parents=True, exist_ok=True)
    segs = []
    for r in rows + [{"id": "endcard", "dur": sb["end_card"]["duration_s"], "narr": None}]:
        seg = TMP / f"voice_{r['id']}.wav"
        if r["narr"]:
            ms = int(LEAD_S * 1000)
            ffmpeg(["-i", r["narr"], "-af", f"aresample=48000,adelay={ms}:all=1,apad,atrim=0:{r['dur']}",
                    "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", seg])
        else:
            ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{r['dur']:.3f}", "-c:a", "pcm_s16le", seg])
        segs.append(seg)
    lst = TMP / "voice_list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
    raw = TMP / "voice_raw.wav"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw])
    # bring the voice to a consistent level before mixing, so balance is a creative choice
    ffmpeg(["-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-ac", "1", "-c:a", "pcm_s16le", out])


def mix(sb, voice: Path, score: Path, total: float, out: Path):
    m, d = sb["music"], sb["music"]["duck"]
    fade_out = max(0.0, total - 3.0)
    fc = (f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={m['gain_db']}dB,atrim=0:{total:.3f},"
          f"afade=t=in:d=1.5,afade=t=out:st={fade_out:.3f}:d=3[m];"
          f"[0:a]aformat=channel_layouts=stereo,asplit=2[vk][vm];"
          f"[m][vk]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:"
          f"attack={d['attack_ms']}:release={d['release_ms']}[md];"
          f"[vm][md]amix=inputs=2:duration=first:normalize=0,"
          f"loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[out]")
    ffmpeg(["-i", voice, "-stream_loop", "-1", "-i", score, "-filter_complex", fc, "-map", "[out]",
            "-t", f"{total:.3f}", "-c:a", "pcm_s16le", out])


# --------------------------------------------------------------- video
def shot_clip(sb, s, dur):
    """Find the clip the shots stage built for this shot's current inputs."""
    from .common import file_hash, wan_path  # noqa
    kf = keyframe_path(sb, s)
    source = "kenburns"
    if s["motion"] == "wan" and wan_path(sb, s).exists():
        source = f"wan:{file_hash(wan_path(sb, s))}"
    inputs = {"keyframe": kf.name, "camera": s["camera"], "dur": dur, "source": source, "fps": FPS, "size": [W, H], "kb_v": 2}
    return cached("shots", s["id"], inputs, "mp4")[0]


def master_video(sb, rows, out: Path):
    clips = []
    for s, r in zip(sb["shots"], rows):
        c = shot_clip(sb, s, r["dur"])
        if not c.exists():
            sys.exit(f"missing shot clip for {s['id']} ({rel(c)}); run `make shots`")
        clips.append(c)
    card_png = TMP / "endcard.png"
    endcard_png(sb, card_png)
    card = TMP / "endcard.mp4"
    cd = sb["end_card"]["duration_s"]
    ffmpeg(["-loop", "1", "-i", card_png, "-t", f"{cd:.3f}", "-vf",
            f"fps={FPS},format=yuv420p,fade=t=in:d=0.6,fade=t=out:st={cd - 0.8:.3f}:d=0.8", *X264, "-an", card])
    clips.append(card)
    lst = TMP / "video_list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in clips))
    ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])


def export(video: Path, audio: Path, total: float, base: str, vertical_too: bool = True):
    """Burn subtitles and mux. Run inside FINAL so the subtitles filter gets plain filenames."""
    common = ["-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt",
              "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}"]
    ffmpeg(["-i", video.resolve(), "-i", audio.resolve(), "-filter_complex",
            f"[0:v]subtitles={base}_16x9.ass[v]", *common, f"{base}_16x9.mp4"], cwd=FINAL)
    if vertical_too:
        fg_h = round(VW * H / W / 2) * 2
        fc = (f"[0:v]split[a][b];[a]scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},"
              f"boxblur=24:2,eq=brightness=-0.10[bg];[b]scale={VW}:{fg_h}[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,subtitles={base}_9x16.ass[v]")
        ffmpeg(["-i", video.resolve(), "-i", audio.resolve(), "-filter_complex", fc, *common, f"{base}_9x16.mp4"],
               cwd=FINAL)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--radio", action="store_true")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    FINAL.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows = timeline(sb)
    missing = [r["id"] for r in rows if r["text_en"] and not r["narr"]]
    if missing:
        print(f"WARNING: no narration audio for {missing}; run `make narration`", file=sys.stderr)
    total = round(sum(r["dur"] for r in rows) + sb["end_card"]["duration_s"], 3)
    base = "radio_cut" if a.radio else "film"
    print(f"assemble ({base}): {len(rows)} shots, {total:.1f}s")
    if not 60 <= total <= 90:
        print(f"WARNING: film is {total:.1f}s; the brief asks for 60-90s", file=sys.stderr)

    (FINAL / "timeline.json").write_text(json.dumps(
        [{**r, "narr": rel(r["narr"])} for r in rows], ensure_ascii=False, indent=2))
    write_srt(rows, FINAL / f"{base}.en.srt")
    write_ass(rows, FINAL / f"{base}_16x9.ass", W, H, 34, 42)
    # vertical: subtitles just below the picture band, clear of the platform buttons at the bottom
    write_ass(rows, FINAL / f"{base}_9x16.ass", VW, VH, 50, 470, width=30)

    voice = TMP / "voice.wav"
    voice_track(sb, rows, total, voice)
    score, is_ph = music.resolve(sb, total, allow_placeholder=True)
    mixed = FINAL / f"{base}_mix.wav"
    mix(sb, voice, score, total, mixed)

    if a.radio:
        black = TMP / "black.mp4"
        ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.3f}", *X264, black])
        export(black, mixed, total, base, vertical_too=False)
    else:
        if is_ph:
            print("WARNING: final film is using the placeholder score", file=sys.stderr)
        master = TMP / "master_nosubs.mp4"
        master_video(sb, rows, master)
        export(master, mixed, total, base)
    log_render("assemble", base, "", FINAL, time.time() - t0)
    for f in sorted(FINAL.glob(f"{base}*.mp4")):
        print(f"  -> {rel(f)}  ({probe_duration(f):.1f}s)")


if __name__ == "__main__":
    main()
