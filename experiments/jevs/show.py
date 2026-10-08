import json, sys
sys.stdout.reconfigure(encoding="utf-8")
f = sys.argv[1] if len(sys.argv) > 1 else "results.json"
r = json.load(open(f, encoding="utf-8"))
print(r["config"])
for w in ("low", "high"):
    print("\n==", w)
    print(f"{'strategy':44s} {'tok/run':>9s} {'usd':>8s} {'recall':>6s} {'crit':>5s} {'compl':>5s} {'safe':>5s} {'fgnT':>5s} {'stlT':>5s} {'tok/need':>9s}")
    for k, v in r["main"][w].items():
        tpn = v["tokens"] / max(1e-9, v["recall"]) / r["config"]["n_needs"] * len(r["per_task_low"][k]) if v["recall"] else float("inf")
        print(f"{k:44s} {v['tokens']:9.0f} {v['usd']:8.4f} {v['recall']:6.2f} {v['crit']:5.2f} {v['complete']:5.2f} {v['safe']:5.2f} {v['foreign_tasks']:5.2f} {v['stale_tasks']:5.2f} {tpn:9.0f}")
print("\nrecall 95% CI (low):")
for k, v in r["main"]["low"].items():
    print(f"  {k:44s} {v['recall_ci'][0]:.2f}-{v['recall_ci'][1]:.2f}")
if "scale" in r:
    print("\nscale")
    for s in r["scale"]:
        print(f"  {s['strategy'][:10]:10s} store={s['store']:6d} tok={s['tokens']:7.0f} recall={s['recall']:.2f} safe={s['safe']:.2f} foreignT={s['foreign_tasks']:.2f} staleT={s['stale_tasks']:.2f}")
    print("\ncurve")
    for s in r["curve"]:
        print(f"  {s['version']} B={s['budget']:6d} tok={s['tokens']:7.0f} recall={s['recall']:.2f} complete={s['complete']:.2f}")
