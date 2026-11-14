"""Shared sizing configs for the sizing tests (2026-10-25).

The sizing-math tests (test_sizing_caps, test_eval_anchor, test_funded_life, test_risk_invariants, test_eval_lifecycle)
used to read live_model.json directly, so every owner switch of a sizing number broke tests that test the math, not the
switch. They now size on an explicit config:

  PINNED   = live_model.json lit_sizing with the values the tests were written for (two_week room_f 0.55, the $1,200
             eval weekly loss stop, funded 40% of the room / <= $800 / a winner <= $1,500: the 2026-10-24 safe switches).
  LIVE     = live_model.json lit_sizing as it is today (the safety sweeps also run on it: every ceiling must hold on
             whatever the owner switched on).
  OWNER    = the owner's current values (2026-10-25, research/writeups/uprisk.md: "evals: one hit, make it quick"):
             two_week room_f 0.8, no eval weekly loss stop, funded 60% / <= $1,500 / a winner <= $2,000.

live_checks(check) asserts live_model.json carries OWNER and that live_model.json == live_model_lit.json, so a switch
change shows up as one clearly named failure here (update OWNER on purpose), not as a dozen math failures.
"""
from __future__ import annotations

import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


LIVE_MODEL = _load("live_model.json")
LIVE = LIVE_MODEL["lit_sizing"]

OLD_FUNDED = {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None,
              "max_win": 1500, "slip_ticks": 2, "skip_breach": True}
OLD_FUNDED_25K = {"pct": 0.4, "pct_min_usd": 50, "pct_max_usd": 400, "ref": 20, "wk": True, "room_f": None,
                  "max_win": 750, "slip_ticks": 2, "skip_breach": True}

PINNED = copy.deepcopy(LIVE)
PINNED.setdefault("two_week", {})["room_f"] = 0.55
PINNED["wk_loss_usd"] = 1200
PINNED["funded"] = dict(OLD_FUNDED)

# the owner's values today: change these (and the write-up) together with live_model.json
# 2026-11-14 owner "yes 40%" (research/writeups/eval-guard-2026-11-13.md): two_week room_f 0.8 -> 0.4, kept past session 10
OWNER = {"two_week.room_f": 0.4, "wk_loss_usd": None, "funded.pct": 0.6, "funded.pct_max_usd": 1500,
         "funded.max_win": 2000, "funded.skip_breach": True, "mode": "two_week", "two_week_until": 80,
         "after_mode": "safe_eval"}
OWNER_25K_FUNDED = {"pct": 0.6, "pct_max_usd": 750, "max_win": 1000, "skip_breach": True}


def _get(d, dotted):
    for k in dotted.split("."):
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def live_checks(check):
    """Named checks: live_model.json carries the owner's sizing values and agrees with live_model_lit.json."""
    lit_file = _load("live_model_lit.json")
    bad = {k: (_get(LIVE, k), v) for k, v in OWNER.items() if _get(LIVE, k) != v}
    check("live_model.json lit_sizing = the owner's 2026-10-25 values (two_week room_f 0.8, no eval weekly stop, "
          "funded 60% / <= $1,500 / winner <= $2,000)", not bad, bad)
    check("live_model.json == live_model_lit.json (lit + lit_sizing identical)",
          LIVE_MODEL.get("lit") == lit_file.get("lit") and LIVE == lit_file.get("lit_sizing"))
    from engine import multi_account as MA
    f50 = MA.PRESETS["mffu_builder_50k"]["sizing"]["funded"]
    f25 = MA.PRESETS["mffu_builder_25k"]["sizing"]["funded"]
    check("multi_account presets: 50K funded = live_model.json funded; 25K funded 60% / <= $750 / winner <= $1,000",
          f50 == LIVE["funded"] and all(f25.get(k) == v for k, v in OWNER_25K_FUNDED.items()), (f50, f25))
