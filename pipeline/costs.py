"""Summarise runs.jsonl per stage: calls, cache hits, latency, GPU minutes, list-price
equivalent. Paste the output into COSTS.md.

List prices: fill PRICES with what you find on each provider's pricing page (and the
date you checked). Units: usd per call, or per GPU-hour for GPU stages."""
from __future__ import annotations

import json
from collections import defaultdict

from .common import RUNS

# (model, unit, price_usd). Leave None until you have checked the provider's page.
PRICES = {
    "gemini-3.8-flash-tts": ("call", None),
    "@cf/black-forest-labs/flux-2-klein-4b": ("call", None),
    "wan2.2-ti2v-5b": ("gpu_hour", None),     # e.g. a cloud T4/L4 hourly rate
    "ace-step-1.5-turbo": ("gpu_hour", None),
}


def main():
    if not RUNS.exists():
        print("no runs.jsonl yet")
        return
    st = defaultdict(lambda: {"calls": 0, "ok": 0, "errors": 0, "hits": 0, "lat": [], "gpu": 0.0, "price": 0.0,
                              "priced": True, "renders": 0, "render_s": 0.0, "models": set()})
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        s = st[r.get("stage", "?")]
        ev = r.get("event")
        if ev == "cache_hit":
            s["hits"] += 1
        elif ev == "render":
            s["renders"] += 1
            s["render_s"] += r.get("latency_s") or 0
        elif ev == "model_call":
            s["calls"] += 1
            s["models"].add(r.get("model"))
            if r.get("status") == "ok":
                s["ok"] += 1
                s["lat"].append(r.get("latency_s") or 0)
            else:
                s["errors"] += 1
            g = r.get("gpu_seconds") or 0
            s["gpu"] += g
            unit, price = PRICES.get(r.get("model"), (None, None))
            if price is None:
                s["priced"] = False
            elif unit == "call":
                s["price"] += price
            elif unit == "gpu_hour":
                s["price"] += price * g / 3600
    print("| Stage | Models | Calls (ok/err) | Cache hits | Mean latency s | Total latency s | GPU min | FFmpeg renders (s) | List-price equiv. USD |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, s in st.items():
        lat = s["lat"]
        mean = f"{sum(lat) / len(lat):.1f}" if lat else "-"
        price = f"{s['price']:.4f}" if s["priced"] and s["calls"] else ("fill PRICES" if s["calls"] else "-")
        print(f"| {name} | {', '.join(sorted(m for m in s['models'] if m)) or '-'} | {s['calls']} ({s['ok']}/{s['errors']}) "
              f"| {s['hits']} | {mean} | {sum(lat):.1f} | {s['gpu'] / 60:.1f} | {s['renders']} ({s['render_s']:.0f}) | {price} |")


if __name__ == "__main__":
    main()
