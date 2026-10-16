"""Walk-forward confluence learner.

Every candidate signal the model produces - taken or not - becomes a *shadow trade* with a virtual outcome
(same stop / target / time-exit rules). At each new decision the learner refits a ridge regression of
R-multiple on the confluence features using ONLY shadows already resolved at that moment, then predicts
the expected R of the new candidate. No future information is ever used.
"""
from __future__ import annotations

import numpy as np

FEATURES = [
    "htf_trend", "protected", "lrl", "hrl", "amt", "smt", "quality", "m15_trend",
    "b_1D", "b_4H", "b_1H", "b_15m", "pd", "midnight", "keylevel", "trig_15m", "cisd", "pm",
    "dol_align", "tgt_major", "dol_room3", "shallow_raid", "deep_raid", "disp_strong", "fast_reclaim", "first_hour",
    "multi_sweep", "major_swept", "vol_climax", "vwap_disc", "rr_plan",
]


def vec(f: dict) -> np.ndarray:
    x = [float(f.get(k, 0.0)) for k in FEATURES]
    x[FEATURES.index("rr_plan")] = min(5.0, x[FEATURES.index("rr_plan")]) / 5.0
    return np.array(x)


class Ridge:
    def __init__(self, lam: float = 8.0):
        self.lam = lam
        self.beta = None
        self.mu = 0.0
        self.n = 0

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.n = len(y)
        if self.n == 0:
            return self
        self.mu = float(y.mean())
        Xc = X
        A = Xc.T @ Xc + self.lam * np.eye(X.shape[1])
        self.beta = np.linalg.solve(A, Xc.T @ (y - self.mu))
        return self

    def predict(self, x: np.ndarray) -> float:
        if self.beta is None:
            return 0.0
        return float(self.mu + x @ self.beta)

    def weights(self):
        if self.beta is None:
            return {}
        return {k: round(float(b), 3) for k, b in zip(FEATURES, self.beta)}


def feature_study(shadows: list, split: str | None = None) -> list:
    """Per-feature conditional performance of shadow trades: avg R when the feature favours the trade vs not."""
    rows = []
    sets = {"all": shadows}
    if split:
        sets = {"is": [s for s in shadows if s["day"] < split], "oos": [s for s in shadows if s["day"] >= split]}
    for k in FEATURES:
        if k == "rr_plan":
            continue
        row = {"feature": k}
        for name, S in sets.items():
            on = [s["r"] for s in S if s["f"].get(k, 0) > 0]
            off = [s["r"] for s in S if s["f"].get(k, 0) <= 0]
            row[f"{name}_n_on"] = len(on)
            row[f"{name}_r_on"] = round(float(np.mean(on)), 3) if on else None
            row[f"{name}_wr_on"] = round(float(np.mean([r > 0 for r in on]) * 100), 1) if on else None
            row[f"{name}_r_off"] = round(float(np.mean(off)), 3) if off else None
            row[f"{name}_edge"] = round(float(np.mean(on) - np.mean(off)), 3) if on and off else None
        rows.append(row)
    return rows
