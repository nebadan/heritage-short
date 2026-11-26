# Wan 2.2 TI2V-5B image-to-video on Kaggle.
# 1. `make gpu-jobs` locally, then upload the jobs/wan/ folder as a private Kaggle dataset.
# 2. New Kaggle notebook: Accelerator = GPU T4 x2, Internet = on, add your dataset.
# 3. Paste this file into one cell and run it. Clips and timings.json land in /kaggle/working/clips.
# 4. Download /kaggle/working/clips, then locally:
#      python -m pipeline.shots register-wan path/to/clips/timings.json
#      make film
# Notes: T4 has 16 GB and no native bf16, so expect it to be slow (many minutes per clip) or
# to fail; that is a FAILURES.md entry, and the pipeline falls back to Ken Burns for that shot.
import json
import pathlib
import subprocess
import time

W = pathlib.Path("/kaggle/working")
jobs_file = next(pathlib.Path("/kaggle/input").rglob("jobs.json"))
jobs = json.loads(jobs_file.read_text())
out_dir = W / "clips"
out_dir.mkdir(exist_ok=True)


def sh(cmd):
    print("$", cmd)
    subprocess.run(cmd, shell=True, check=True)


if not (W / "Wan2.2").exists():
    sh(f"git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git {W}/Wan2.2")
    # flash_attn usually fails to build on Kaggle; Wan falls back to PyTorch attention without it
    sh(f"grep -v flash_attn {W}/Wan2.2/requirements.txt > {W}/req.txt && pip install -q -r {W}/req.txt")
if not (W / "Wan2.2-TI2V-5B").exists():
    sh(f"huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir {W}/Wan2.2-TI2V-5B")

gpu = subprocess.run("nvidia-smi --query-gpu=name --format=csv,noheader", shell=True, capture_output=True,
                     text=True).stdout.strip().splitlines()[0]
timings = []
for j in jobs:
    out = out_dir / j["output"]
    if out.exists():
        print("exists", out.name)
        continue
    img = jobs_file.parent / j["keyframe"]
    cmd = (f"cd {W}/Wan2.2 && python generate.py --task ti2v-5B --size 1280*704 "
           f"--ckpt_dir {W}/Wan2.2-TI2V-5B --offload_model True --convert_model_dtype --t5_cpu "
           f"--image '{img}' --prompt {json.dumps(j['prompt'])} --base_seed {j['seed']} "
           f"--frame_num {j['frame_num']} --save_file '{out}'")
    t0 = time.time()
    rec = {"shot_id": j["shot_id"], "wan_hash": j["wan_hash"], "output": j["output"], "seed": j["seed"],
           "model": "wan2.2-ti2v-5b", "gpu": gpu,
           "params": {"size": "1280*704", "frame_num": j["frame_num"], "prompt": j["prompt"], "offload": True}}
    try:
        sh(cmd)
        rec.update(status="ok", seconds=round(time.time() - t0, 1))
    except subprocess.CalledProcessError as e:
        rec.update(status="error", seconds=round(time.time() - t0, 1), error=str(e))
    timings.append(rec)
    (out_dir / "timings.json").write_text(json.dumps(timings, indent=2))  # save as we go: sessions time out
    print(rec)
print("done:", [t["status"] for t in timings])
