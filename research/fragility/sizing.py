"""Eval sizing under the haircut: MC on mixed trade pools (share w of 2026 trades, 1-w of 2021-25) x room fraction."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(os.path.dirname(os.path.dirname(HERE)))
import fragility as FR
M, S = FR.sessions(); T0 = FR.run({}, S)
p26 = [t for t in T0 if "2026-01-01" <= t["day"] <= "2026-10-16"]; p25 = [t for t in T0 if t["day"] <= "2025-12-31"]
def mc(pool, f, n=20000, seed=11, max_trades=40):
    rng = np.random.default_rng(seed)
    r = np.array([t["r"] for t in pool]); tr = np.array([max(1.0, abs(t["target_px"] - t["entry_px"]) / t["risk_pts"]) for t in pool])
    P = Fl = 0; med = []
    for _ in range(n):
        bal = peak = 0.0; floor = -2000.0
        for k in range(max_trades):
            i = rng.integers(len(r)); room = bal - floor
            risk = max(30.0, min(f * room, (3000 - bal) / tr[i]))
            bal += r[i] * risk; peak = max(peak, bal)
            if bal <= floor: Fl += 1; break
            floor = min(max(floor, peak - 2000.0), 100.0)
            if bal >= 3000: P += 1; med.append(k + 1); break
    return round(100 * P / n, 1), round(100 * Fl / n, 1), float(np.median(med)) if med else None
rng = np.random.default_rng(1); out = {}
for w in (1.0, 0.5, 0.25, 0.0):
    n26 = int(round(w * 400)); pool = [p26[i] for i in rng.integers(len(p26), size=n26)] + [p25[i] for i in rng.integers(len(p25), size=400 - n26)]
    for f in (0.25, 0.3, 0.4, 0.5, 0.6):
        out[f"w{w}_f{f}"] = mc(pool, f)
        print(f"2026 share {w:.2f} room_f {f}: pass/fail in 40 trades (~70 sessions) {out[f'w{w}_f{f}']}", flush=True)
json.dump(out, open(os.path.join(HERE, "sizing.json"), "w"), indent=1)
