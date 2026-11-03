"""The Council of the Gods: the council gods' votes combined into one risk-on / risk-off gauge (context, never an order).

score  the mean of the available council votes (each -1 risk-off .. +1 risk-on), per session; at least 3 voices
gauge  0-100 (50 = balanced): (score + 1) x 50
label  RISK-ON at score >= +0.20, RISK-OFF at <= -0.20, else MIXED
ATHENA does not vote (the calendar has no direction); an event today or next session adds a caution line.
ARTEMIS (crypto) never votes: it is not futures data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ON, OFF = 0.20, -0.20
MIN_VOICES = 3


def label(score: float | None) -> str:
    if score is None or not np.isfinite(score):
        return "SILENT"
    return "RISK-ON" if score >= ON else "RISK-OFF" if score <= OFF else "MIXED"


def history(votes: dict) -> pd.Series:
    """{god key: session vote series} -> the council score per session (NaN with fewer than MIN_VOICES voices)."""
    if not votes:
        return pd.Series(dtype=float)
    df = pd.concat(votes, axis=1)
    n = df.notna().sum(axis=1)
    return df.mean(axis=1).where(n >= MIN_VOICES)


def verdict(today: dict, caution: str = "") -> dict:
    """today = {god key: (name, vote or None)} for the council gods -> the verdict object of pantheon.json."""
    live = {k: v for k, (_, v) in today.items() if v is not None and np.isfinite(v)}
    if len(live) < MIN_VOICES:
        return {"score": None, "gauge": None, "label": "SILENT", "voices": len(live), "on": [], "off": [], "neutral": [],
                "text": "Too few gods are reachable right now to call a verdict.", "caution": caution}
    score = float(np.mean(list(live.values())))
    on = [today[k][0] for k, v in live.items() if v >= 0.25]
    off = [today[k][0] for k, v in live.items() if v <= -0.25]
    mid = [today[k][0] for k, v in live.items() if -0.25 < v < 0.25]
    lab = label(score)
    parts = []
    if on:
        parts.append(f"{', '.join(on)} lean risk-on")
    if off:
        parts.append(f"{', '.join(off)} lean risk-off")
    if mid:
        parts.append(f"{', '.join(mid)} {'is' if len(mid) == 1 else 'are'} neutral")
    head = {"RISK-ON": "The council leans risk-on", "RISK-OFF": "The council leans risk-off", "MIXED": "The council is split"}[lab]
    return {"score": round(score, 3), "gauge": int(round((score + 1) * 50)), "label": lab, "voices": len(live),
            "on": on, "off": off, "neutral": mid, "text": f"{head}: {'; '.join(parts)}.", "caution": caution}
