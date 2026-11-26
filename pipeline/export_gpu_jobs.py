"""Write job files for the GPU stages that run outside this machine.

  jobs/wan/jobs.json + keyframes  -> upload the folder as a Kaggle dataset, run gpu/kaggle_wan22.py
  jobs/music_job.json             -> caption/settings to paste into ACE-Step (see gpu/ACESTEP.md)
"""
from __future__ import annotations

import json
import shutil

from .common import ROOT, keyframe_path, load_storyboard, wan_inputs, wan_path

CAMERA = {"static": "the camera is fixed", "push_in": "the camera pushes in slowly", "pull_out": "the camera pulls back slowly",
          "pan_left": "the camera pans slowly to the left", "pan_right": "the camera pans slowly to the right",
          "tilt_up": "the camera tilts up slowly", "tilt_down": "the camera tilts down slowly"}


def main():
    sb = load_storyboard()
    jd = ROOT / "jobs" / "wan"
    jd.mkdir(parents=True, exist_ok=True)
    jobs = []
    for s in sb["shots"]:
        if s["motion"] != "wan":
            continue
        kf = keyframe_path(sb, s)
        if not kf.exists():
            print(f"skip {s['id']}: no keyframe yet")
            continue
        shutil.copy2(kf, jd / kf.name)
        inp = wan_inputs(sb, s)
        jobs.append({"shot_id": s["id"], "wan_hash": wan_path(sb, s).stem.split("_")[-1], "keyframe": kf.name,
                     "output": wan_path(sb, s).name, "prompt": f"{s['motion_prompt'].rstrip('.')}. {CAMERA[s['camera']]}.",
                     "seed": inp["seed"], "frame_num": inp["frames"]})
    (jd / "jobs.json").write_text(json.dumps(jobs, indent=2, ensure_ascii=False))
    print(f"{len(jobs)} Wan jobs -> {jd.relative_to(ROOT)}/ (upload this folder as a Kaggle dataset)")
    m = sb["music"]
    job = {"caption": m["caption"], "lyrics": "[Instrumental]" if m.get("instrumental", True) else "",
           "bpm": m["bpm"], "key": m["key"], "duration_s": m["duration_s"], "seeds": [11, 22, 33],
           "cues": m.get("cues", [])}
    (ROOT / "jobs" / "music_job.json").write_text(json.dumps(job, indent=2, ensure_ascii=False))
    print("music job -> jobs/music_job.json")


if __name__ == "__main__":
    main()
