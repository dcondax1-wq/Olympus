"""ATLAS + Zlarior on ONE account: the Builder 50K Zlarior (LIT) trades (owner 2026-11-19, Decide card zlarior-atlas-50k).
BUILT, OFF BY DEFAULT. Study: research/writeups/one-account-combo-2026-11-19.md (tools/money/combo_account.py = the reference
simulator); red team: research/writeups/one-account-combo-redteam-2026-11-19.md section 6 (what the live build must do).

Two files:
  research/lab/combo_50k.json  the RULE VALUES (tracked; absent = DEFAULTS below):
      {"conflict": "first" (= first_in) | "lit_priority" (= the study's zfull) | "close_on_opposite" (= zprio),
       "atlas_size_factor": x | {"eval": 0.5, "funded": 1.0}, "guards": {... null = off ...}, "variant": ...}
      night-comboplus's pick (a50_eval, tier B): first in keeps the account, ATLAS at 50% of its own size in the eval and
      100% once funded, every eval guard off (null), one position, $1,000 soft day for both bots, 40 micros, flat by 16:10.
  data/combo_50k.json          the OWNER'S SWITCH (local, gitignored; absent / {"on": false} = OFF = the bot is exactly today's):
      {"on": true, "account": "<the NinjaTrader Name of Zlarior's 50K, or Sim101 for the Sim test>", "set": "yyyy-mm-dd", ...}
      Written only by the owner's step (the typed phrase, like every live switch):
        python -X utf8 -m engine.combo50k --status
        python -X utf8 -m engine.combo50k --on --account "Sim101"            Sim test first (NinjaTrader's Sim101)
        python -X utf8 -m engine.combo50k --on --account "<the 50K Name>"    the real 50K: needs the Decide card
                                                                             zlarior-atlas-50k answered yes
        python -X utf8 -m engine.combo50k --off
      --on is refused unless the owner types I ACCEPT LIVE RISK, engine.ninjatrader --selftest passes and (real account) the
      Decide card says yes. Claude never writes this file; test harnesses use the start cfg "combo_50k" (never the real bot).
      The bot picks a change up at its next poll once the 50K holds no ATLAS trade (an open one is managed to its exit).

What the switch does when ON (engine/live.py, LiveBot._combo_*; every hook is `self.combo is None` = today's code path):
  * ATLAS's entries (its EMA > MACD > S/R members, the raw member trades with ATLAS's own rules: one ATLAS trade at a time,
    max 2 a day, member order on a tie = tools/money/combo_account._atlas_rows) ALSO go to the 50K Zlarior trades, at market
    at the 5m open, through Zlarior's own NinjaTrader adapter (one adapter, one bracket = one stop + target OCO per account),
    booked in Zlarior's ledger (so its eval room, the $1,000 soft daily loss, the guards, the kill switch, the phone pause,
    the remote flatten and the reconcile see BOTH bots). ATLAS's own account (account B, its 25K) is untouched.
  * ONE POSITION on the 50K: while the account holds a position, has an entry going out (Zlarior entering / its 1m CISD
    entry pending / an order still working at the broker), the other bot's entry waits. The conflict rule decides who:
      first_in / first   (default, the study's main rule) the first bot in keeps the account; every later signal of either
                         bot is skipped until it is flat (Zlarior's armed setups are dropped while ATLAS holds)
      lit_priority       (the simulator's zfull) any Zlarior entry while ATLAS holds closes ATLAS at market first, then
                         Zlarior enters; ATLAS never enters while Zlarior holds / is entering
      close_on_opposite  (zprio) Zlarior entering the OTHER way closes ATLAS first (the red team's "+$484"); a same-side
                         Zlarior signal while ATLAS holds is skipped
  * ONE DIRECTION across every MFFU account (no hedging, research/lit/mffu_rules.json): ATLAS's 50K entry is skipped while
    ATLAS's 25K (account B, incl. a close not confirmed), an extra account (engine/multi_account), ATLAS on the Rapid or a
    fleet follower holds the other side; BLITZ (account C) the other way is closed first (LIT > ATLAS > BLITZ, as today);
    the other accounts already see the 50K's position (LiveBot._open_routed + its ledger row): account B / C / extra
    accounts / followers never open against it. Optional guard "atlas_lit_armed_block" (OFF: not in the research rules;
    on = ATLAS never enters while Zlarior has a setup armed the other way, ATLAS's 25K rule; it is not needed for the
    no-hedge rule: Zlarior's later entry on the 50K is skipped / closes ATLAS, the other accounts refuse the other side).
  * SIZE from the 50K's ONE shared room (balance + today's closed P&L of BOTH bots - the trailing floor = LiveBot.eval_state):
    Zlarior unchanged (live_model.json lit_sizing two_week, room_f 0.4, kept to session 80); ATLAS = engine/account_b.qty on
    the builder50k preset (need size, the zombie-eval last bullet, the soft-daily-loss guard; funded: funded_qty) x
    atlas_size_factor of the 50K's stage (eval / funded = Zlarior's lit_sizing mode), rounded down, min 1 micro (= the
    simulator), capped at 40 micros; no ATLAS entry under ATLAS's $200 eval stop line ($100 funded). Guards from the file:
    atlas_in_eval, atlas_eval_min_room_usd, eval_day_stop_usd (both bots), soft_day_usd_both_bots, max_micros (null = off).
  * Alerts / board: the entry push and the Board say which bot traded ("ATLAS on Zlarior 50K: LONG opened", "Zlarior on its
    50K: SHORT opened"); heartbeat second.route "combo".

Parity proof: tests/test_combo_50k.py replays 2026 days through the REAL LiveBot (fake NinjaTrader, one Sim 50K) and checks
the trade list (entries taken / skipped, micros, exits, $) == tools/money/combo_account.Eval on the same days.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_REL = os.path.join("research", "lab", "combo_50k.json")
SWITCH_REL = os.path.join("data", "combo_50k.json")
DECIDE_ID = "zlarior-atlas-50k"
DECISIONS_REL = os.path.join("tools", "web_public", "business", "decisions.json")
LABEL = "ATLAS on Zlarior 50K"           # who traded, in every alert / board line / log line of the combo
ZLABEL = "Zlarior on its 50K"
CONFLICTS = ("first_in", "lit_priority", "close_on_opposite")
MEMBERS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")   # ATLAS's member order (a tie: EMA > MACD > S/R)
PLAN = "builder50k"
MAX_PER_DAY = 2                          # ATLAS's own limit (its raw stream); Zlarior keeps its 1
MAX_AGE_S = 45                           # a 5m open seen later than this is not probed (= engine/account_b.MAX_AGE_S)
# the research file's guards (night-comboplus research/lab/combo_50k.json; null = off) + this build's own (absent = default)
GUARD_DEFAULTS = {
    "atlas_in_eval": True,                # false = ATLAS trades the 50K only once it is funded
    "atlas_eval_min_room_usd": None,      # eval: ATLAS only while the room is >= this ($; null = off)
    "eval_day_stop_usd": None,            # eval: no new entry of EITHER bot once today's closed P&L <= -this (null = off)
    "one_position": True,                 # must stay true (same-side adds are not built)
    "soft_day_usd_both_bots": 1000.0,     # the soft daily loss both bots count against (<= the guards' $1,000; null = the guards')
    "max_micros": 40,                     # ATLAS's micros cap on the 50K (<= the plan's 40)
    "flat_by": "16:10 ET",                # MFFU's flat time (both bots are out by 15:55 ET already; information)
    "atlas_lit_armed_block": False,       # this build: true = ATLAS never enters while Zlarior has a setup armed the other way
    "atlas_max_per_day": MAX_PER_DAY,     # this build: ATLAS's entries a day on the 50K (its own stream already has <= 2)
    "atlas_min_room": 200.0,              # this build: ATLAS's own eval stop line (engine/account_b zombie-eval rule) ...
    "atlas_min_room_funded": 100.0,       # ... and funded (the study's min_room lines)
    "atlas_max_risk_usd": None,           # this build: ATLAS's worst-case $ a trade (stop + 2 ticks + $1.90; null = off)
}
DEFAULTS = {"conflict": "first_in", "atlas_size_factor": {"eval": 1.0, "funded": 1.0}, "guards": {}}
ALIASES = {"first": "first_in", "first_in": "first_in", "zprio": "close_on_opposite", "close_on_opposite": "close_on_opposite",
           "zfull": "lit_priority", "lit_priority": "lit_priority"}       # the simulator's names (tools/money/combo_account)
INFO_KEYS = ("version", "account", "bots", "variant", "pick_tier", "sizes", "evidence", "post_hoc_not_active", "note", "notes",
             "built", "source")
ON_CMD = 'python -X utf8 -m engine.combo50k --on --account "<Name>"'


def _path(rel: str, root: str | None = None) -> str:
    return os.path.join(root or ROOT, rel)


def _read(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


# ------------------------------------------------------------------------------------------------ the rule values
def factor_of(rules: dict, stage: str) -> float:
    """ATLAS's size share on the 50K for the account's stage ("eval" / "funded")."""
    f = (rules or {}).get("atlas_size_factor", (rules or {}).get("factor"))
    if isinstance(f, dict):
        return float(f.get("funded" if stage == "funded" else "eval", 1.0))
    return float(f if f is not None else 1.0)


def normalize(raw, plan: str = PLAN) -> dict:
    """The rule values (research/lab/combo_50k.json, or a harness dict) -> {"conflict", "atlas_size_factor": {"eval",
    "funded"}, "guards", "problem": why it cannot run or None, "unknown": [keys ignored]}. A "rules" sub-dict is read too.
    conflict "first" (the research file) = first_in; atlas_size_factor a number or {"eval": x, "funded": y}; a null guard =
    off (its default where a default exists)."""
    src = raw if isinstance(raw, dict) else {}
    if isinstance(src.get("rules"), dict):
        src = {**src, **src["rules"]}
    out = {"conflict": DEFAULTS["conflict"], "atlas_size_factor": dict(DEFAULTS["atlas_size_factor"]), "guards": dict(GUARD_DEFAULTS),
           "problem": None, "unknown": [], "variant": src.get("variant")}
    c = str(src.get("conflict") or DEFAULTS["conflict"]).strip().lower()
    if c not in ALIASES:
        out["problem"] = f"conflict {src.get('conflict')!r} unknown ({' | '.join(CONFLICTS)}, or first / zprio / zfull)"
    out["conflict"] = ALIASES.get(c, c)
    acct = str(src.get("account") or PLAN).strip().lower().replace(" ", "").replace("_", "")
    if acct not in (PLAN, plan):        # the research file is the 50K's; the 25K #2 (engine/combo25.py) reads the same values
        out["problem"] = out["problem"] or f"account {src.get('account')!r}: this build is the Builder 50K / 25K (builder50k)"
    bots = src.get("bots")
    if bots is not None and (not isinstance(bots, (list, tuple)) or not {"lit", "atlas"} <= {str(b).lower() for b in bots}):
        out["problem"] = out["problem"] or f"bots {bots!r}: this build is Zlarior (lit) + ATLAS (atlas)"
    f = src.get("atlas_size_factor", 1.0)
    fd = f if isinstance(f, dict) else {"eval": f, "funded": f}
    for st in ("eval", "funded"):
        v = fd.get(st, 1.0)
        n = 1.0 if v is None else _num(v)
        if n is None or not 0.0 <= n <= 2.0:
            out["problem"] = out["problem"] or f"atlas_size_factor {f!r} must be a number in [0, 2] or {{\"eval\": x, \"funded\": y}}"
            n = 1.0
        out["atlas_size_factor"][st] = float(n)
    g = src.get("guards") if isinstance(src.get("guards"), dict) else {}
    for k, v in g.items():
        if k not in GUARD_DEFAULTS:
            out["unknown"].append(str(k))
            continue
        if k in ("atlas_lit_armed_block", "atlas_in_eval", "one_position"):
            out["guards"][k] = GUARD_DEFAULTS[k] if v is None else bool(v)
        elif k == "flat_by":
            txt = None if v is None else str(v).strip()
            if txt is not None:
                import re
                m = re.match(r"^(\d{1,2}):(\d{2})(\s*ET)?$", txt)
                if not m or not (0 <= int(m.group(1)) < 24 and 0 <= int(m.group(2)) < 60):
                    out["problem"] = out["problem"] or f"guards.flat_by {v!r} must look like 16:10 ET"
                elif int(m.group(1)) * 60 + int(m.group(2)) < 955:
                    out["problem"] = out["problem"] or f"guards.flat_by {v!r} is before 15:55 ET: an earlier flat time is not built"
            out["guards"][k] = txt
        elif k in ("atlas_max_per_day", "max_micros"):
            if v is None:
                continue                                     # null = the default (2 a day / 40 micros)
            n = _num(v)
            hi = MAX_PER_DAY if k == "atlas_max_per_day" else 40
            if n is None or not (0 if k == "atlas_max_per_day" else 1) <= int(n) <= hi:
                out["problem"] = out["problem"] or f"guards.{k} {v!r} must be a whole number up to {hi}"
            else:
                out["guards"][k] = int(n)
        elif v is None:
            out["guards"][k] = None if k not in ("atlas_min_room", "atlas_min_room_funded") else GUARD_DEFAULTS[k]
        else:
            n = _num(v)
            if n is None or n < 0 or n > 5000:
                out["problem"] = out["problem"] or f"guards.{k} {v!r} must be a number of $ (0-5000)"
            else:
                out["guards"][k] = float(n)
    if out["guards"].get("one_position") is not True:
        out["problem"] = out["problem"] or "guards.one_position false: same-side adds on the 50K are not built (one position only)"
    for k in src:
        if k not in ("conflict", "atlas_size_factor", "guards", "rules") and k not in INFO_KEYS:
            out["unknown"].append(str(k))
    return out


def load_rules(root: str | None = None, plan: str = PLAN) -> dict:
    """research/lab/combo_50k.json (the rule values another helper finalises), else DEFAULTS. Never raises."""
    raw = _read(_path(RULES_REL, root))
    out = normalize(raw if isinstance(raw, dict) else {}, plan=plan)
    out["file"] = RULES_REL if isinstance(raw, dict) else None
    return out


# ------------------------------------------------------------------------------------------------ the owner's switch
def read_switch(root: str | None = None) -> dict:
    """data/combo_50k.json -> {"on": bool, "account": str, "accounts": [str], ...}; absent / unreadable = {"on": False}.
    "accounts" (owner 2026-11-23: the 50K AND the Builder 25K #2) = every NinjaTrader Name the combo is on for; a file of
    the first build (one "account") reads as that one Name."""
    j = _read(_path(SWITCH_REL, root))
    if not isinstance(j, dict):
        return {"on": False}
    one = str(j.get("account") or "").strip()
    many = j.get("accounts")
    names = [str(x).strip() for x in many if str(x or "").strip()] if isinstance(many, list) else ([one] if one else [])
    return {**j, "on": j.get("on") is True, "account": one or (names[0] if names else ""),
            "accounts": list(dict.fromkeys(names)) if j.get("on") is True else []}


def switch_on_for(name: str, root: str | None = None) -> bool:
    """The owner's switch is on for this NinjaTrader account Name (data/combo_50k.json)."""
    nm = str(name or "").strip()
    return bool(nm) and nm in read_switch(root).get("accounts", [])


def _is_sim(name: str) -> bool:
    try:
        from .ninjatrader import is_sim
        return is_sim(name)
    except Exception:
        return str(name or "").strip().lower().startswith("sim")


def decide_yes(root: str | None = None) -> bool:
    """The Decide card zlarior-atlas-50k answered yes (tools/web_public/business/decisions.json; Claude marks it after the
    owner's tap)."""
    j = _read(_path(DECISIONS_REL, root)) or {}
    for d in j.get("items") or []:
        if isinstance(d, dict) and str(d.get("id")) == DECIDE_ID:
            return str(d.get("status") or "").lower() in ("yes", "approved") or str(d.get("answer") or "").lower() == "yes"
    return False


def build(bot):
    """The combo spec this bot runs with, or None = OFF (today's bot). Test harnesses: the start cfg "combo_50k" (a dict of
    rule values or True), honoured only when the bot is not the real one. The real bot: data/combo_50k.json "on" AND its
    "account" is this bot's own NinjaTrader account (a Sim101 test switch never turns the real 50K on)."""
    cfg = getattr(bot, "cfg", None) or {}
    try:
        from .live import STATE_PATH
        real = getattr(bot, "state_path", None) == STATE_PATH
    except Exception:
        real = True
    own = str(cfg.get("nt_account") or getattr(getattr(bot, "adapter", None), "account", "") or "").strip()
    over = cfg.get("combo_50k")
    if not real:
        # a test harness / Sim rehearsal with its own state file: ONLY its start cfg counts (never the PC's switch file)
        if not over:
            return None
        rules = normalize({k: v for k, v in over.items() if k != "time_size"} if isinstance(over, dict) else {})
        src = "start cfg (test harness)"
        from .account_b import time_size_norm
        tsz = time_size_norm(over.get("time_size")) if isinstance(over, dict) else None
    else:
        sw = read_switch()
        if not sw.get("on"):
            return None
        if not own or own not in sw.get("accounts", []):
            return {"off_why": f"the switch is for {', '.join(sw.get('accounts') or []) or '?'}, this bot trades {own or 'paper'}: OFF"}
        rules = load_rules()
        src = SWITCH_REL
        from .account_b import read_time_size
        tsz = read_time_size()
    if rules.get("problem"):
        return {"off_why": f"combo rules not usable ({rules['problem']}): OFF"}
    out = {"on": True, "account": own, "conflict": rules["conflict"], "atlas_size_factor": dict(rules["atlas_size_factor"]),
           "guards": dict(rules["guards"]), "unknown": list(rules.get("unknown") or []), "keys": list(MEMBERS),
           "label": LABEL, "src": src, "max_micros": 40}
    if tsz:
        out["time_size"] = tsz                         # absent = OFF = today's spec byte for byte
    return out


def ab_spec(combo: dict, eval_start: str | None, stage: str = "eval", funded: dict | None = None) -> dict:
    """engine/account_b's sizing spec on the combo's plan preset (builder50k; the 25K #2 = builder25k, engine/combo25.py):
    the same rules the study sized ATLAS with."""
    from . import account_b as AB
    blk = {"account": combo.get("account") or "combo50k", "plan": combo.get("plan") or PLAN, "eval_start": eval_start or "",
           "strategies": list(MEMBERS)}
    spec = AB.normalize(blk, lit_account=None)
    if stage == "funded":
        spec = {**spec, "stage": "funded", "funded": funded or {"start": eval_start or "", "balance": float(spec["rules"]["start"]),
                                                                "prior": 0.0, "payouts": {}}}
    return spec


def atlas_qty(combo: dict, trade: dict, state: dict | None, eval_start: str | None, base: dict | None = None,
              stage: str = "eval", funded: dict | None = None, key: str | None = None) -> dict:
    """Micros for ATLAS's entry on the 50K: engine/account_b.qty (eval need size + last bullet + soft-daily-loss guard) /
    funded_qty on the builder50k preset from the 50K's shared state, then x atlas_size_factor of the 50K's stage (the
    research file: eval 0.5, funded 1.0) rounded DOWN, never under 1 micro while the base size is >= 1 (exactly
    tools/money/combo_account's a_f rule: max(1, floor(f x q))); a factor of 0 = no trade; above 1x the soft-daily-loss
    guard and 60% of the room still cap it. Then guards.max_micros (<= the plan's 40) and atlas_max_risk_usd. Fails closed."""
    from . import account_b as AB
    from . import sizing as SZ
    if state is None:
        return {"qty": 0, "reasons": ["the 50K's eval state is unknown (eval_start missing?): not traded"]}
    spec = ab_spec(combo, eval_start, stage, funded)
    r = AB.qty(spec, trade, dict(state), base=base, key=key) if stage != "funded" else AB.funded_qty(spec, trade, dict(state), base=base, key=key)
    q0 = int(r.get("qty") or 0)
    g = combo.get("guards") or {}
    maxq = int(min(int(g.get("max_micros") or combo.get("max_micros") or 40), int(spec["rules"]["max_micros"])))   # 25K: 20
    reasons = list(r.get("reasons") or [])
    f = factor_of(combo, stage)
    q = q0
    risk = float(_num(trade.get("risk_pts"), 0.0) or 0.0)
    loss1 = (risk + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    if q0 > 0 and f <= 0.0:
        q = 0
        reasons.append(f"atlas_size_factor {stage} 0: ATLAS does not trade the 50K in this stage")
    elif q0 > 0 and f < 1.0 - 1e-12:
        q = max(1, int(math.floor(f * q0 + 1e-9)))      # = tools/money/combo_account (night-comboplus) ATLAS's share
        reasons.append(f"atlas_size_factor {stage} {f:g}: {q0} -> {q}")
    elif q0 > 0 and f > 1.0 + 1e-12:
        q = int(math.floor(f * q0 + 1e-9))
        room = float(_num(state.get("room"), 0.0) or 0.0)
        q = min(q, int(max(0.0, 0.6 * room) / loss1 + 1e-9) if loss1 > 0 else 0)
        q = int(AB.dll_guard({"qty": q, "reasons": []}, risk, spec["rules"], state).get("qty") or 0)
        q = max(q, q0)                                   # never below the base size, never above the caps it passed
        reasons.append(f"atlas_size_factor {stage} {f:g}: {q0} -> {q}")
    ts = combo.get("time_size")
    if stage == "eval" and ts and q > 0:             # owner switch (engine/account_b time_size, OFF = absent): eval only
        q, why = AB.apply_time_size(q, ts, trade.get("entry_t"))
        if why:
            reasons.append(why)
    if q > maxq:
        reasons.append(f"max {maxq} micros")
        q = maxq
    cap = g.get("atlas_max_risk_usd")
    if q > 0 and cap is not None and loss1 > 0 and q * loss1 > float(cap):
        q2 = int(float(cap) / loss1 + 1e-9)
        reasons.append(f"guard atlas_max_risk_usd ${float(cap):,.0f}: {q} -> {q2}")
        q = q2
    return {"qty": int(max(0, q)), "reasons": reasons, "lock": r.get("lock")}


# ------------------------------------------------------------------------------------------------ ATLAS's own stream
def atlas_pick(run: dict, keys, tb: int, day: str):
    """ATLAS's raw stream at the 5m open tb (tools/money/combo_account._atlas_rows on live data): every member's trades of
    trading day `day` in entry order (member order on a tie); a trade is ATLAS's when ATLAS's previous trade of the day is
    over by its entry (its model exit_t <= entry_t; still OPEN = busy) and it is one of the day's first MAX_PER_DAY. Returns
    (pick | None, why | None, signals): pick = (key, trade) of the signal at tb, signals = [(key, trade)] at tb."""
    order = {k: i for i, k in enumerate(keys)}
    rows = []
    for k in keys:
        s = ((run or {}).get("strategies") or {}).get(k) or {}
        if s.get("error"):
            continue
        for t in s.get("trades") or []:
            try:
                et_ = int(t["entry_t"])
            except (KeyError, TypeError, ValueError):
                continue
            if str(t.get("day") or "") != day or et_ > int(tb):
                continue
            rows.append((et_, order[k], k, t))
    rows.sort(key=lambda x: (x[0], x[1]))
    sigs = [(k, t) for et_, _, k, t in rows if et_ == int(tb) and t.get("exit_kind") == "OPEN" and t.get("target") is not None]
    busy, n, last = -1, 0, None
    for et_, _, k, t in rows:
        if et_ == int(tb):
            break
        if et_ < busy or n >= MAX_PER_DAY:
            continue
        n += 1
        last = (k, t)
        busy = 10 ** 12 if t.get("exit_kind") == "OPEN" else int(t.get("exit_t") or 10 ** 12)
    if not sigs:
        return None, None, []
    if int(tb) < busy:
        lk, lt = last
        return None, f"ATLAS's own {lk} trade from {_hm(int(lt['entry_t']))} ET is still open (one ATLAS trade at a time)", sigs
    if n >= MAX_PER_DAY:
        return None, f"ATLAS already had {MAX_PER_DAY} trades today (its own max {MAX_PER_DAY} a day)", sigs
    return sigs[0], None, sigs


def _hm(t: int) -> str:
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York")).strftime("%H:%M")


def entry_text(who: str, side: str, qty=None, what: str | None = None) -> str:
    """The one line every alert / board row uses: "ATLAS on Zlarior 50K: LONG opened (4 MNQ, EMA)"."""
    extra = ", ".join(x for x in ((f"{int(qty)} MNQ" if qty else None), what) if x)
    return f"{who}: {str(side).upper()} opened" + (f" ({extra})" if extra else "")


def board_note(who: str, side: str, qty=None, what: str | None = None, data: dict | None = None):
    """One Board line (engine/board_events kind combo_trade) for a trade on the 50K while the combo is on. Never raises."""
    try:
        from . import board_events
        board_events.emit("combo_trade", "zlarior", entry_text(who, side, qty, what), data or {})
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------ the owner's step (CLI)
def _selftest_ok():
    from .second import _selftest_ok as st
    return st()


def _write_switch(block: dict, root: str | None = None) -> str:
    p = _path(SWITCH_REL, root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(block, fh, indent=1)
    # red team 2026-11-23: the rename AFTER the file is closed. Inside the `with` it renamed a file still open for writing:
    # Windows refuses that (PermissionError, retried, then raised), so the owner's --on / --off never wrote the switch
    from .fsutil import replace as _rep
    _rep(tmp, p)
    return p


def set_on(account: str, phrase: str, root: str | None = None, selftest=None, today: str | None = None) -> dict:
    """The owner's switch ON for one NinjaTrader account Name. Refused: no / wrong typed phrase, a bad Name, the rule file
    unusable, ATLAS's own 25K Name, (a real account) the Decide card not answered yes, a failing NinjaTrader self-test."""
    from .go import LIVE_PHRASE, typed_phrase
    nm = str(account or "").strip()
    if typed_phrase(phrase) != LIVE_PHRASE:
        return {"ok": False, "error": "the live phrase was not typed: nothing switched on"}
    if not nm or any(c in nm for c in ";\r\n|\"'"):
        return {"ok": False, "error": "account Name missing or invalid"}
    rules = load_rules(root)
    if rules.get("problem"):
        return {"ok": False, "error": f"research/lab/combo_50k.json not usable: {rules['problem']}"}
    try:
        from . import account_b as AB
        ab = AB.raw_cfg() or {}
        if isinstance(ab, dict) and str(ab.get("account") or "").strip() == nm:
            return {"ok": False, "error": f"{nm} is ATLAS's own account (account B): the combo is ATLAS on Zlarior's 50K"}
    except Exception:
        pass
    rapid = _rapid_name(nm, root)
    if rapid:
        return {"ok": False, "error": f"{nm} is {rapid}: ATLAS already trades it in its own lane (engine/rapid.py)"}
    sim = _is_sim(nm)
    if not sim and not decide_yes(root):
        return {"ok": False, "error": f"the Decide card {DECIDE_ID} is not answered yes yet: test on Sim101 first, then decide"}
    ok, line = (selftest or _selftest_ok)()
    if not ok:
        return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): nothing switched on"}
    day = today or _dt.date.today().isoformat()
    old = read_switch(root)
    names = list(dict.fromkeys(list(old.get("accounts") or []) + [nm]))     # the 50K AND the 25K #2: one Name each time
    blk = {"on": True, "account": names[0], "accounts": names, "sim": bool(sim), "set": day, "phrase_typed": day,
           "conflict": rules["conflict"], "atlas_size_factor": rules["atlas_size_factor"],
           "set_by_account": {**(old.get("set_by_account") or {}), nm: day}}
    p = _write_switch(blk, root)
    return {"ok": True, "path": p, "block": blk,
            "say": f"ATLAS + Zlarior on ONE account: ON for {nm} ({'Sim' if sim else 'REAL'}), conflict {rules['conflict']}, "
                   f"ATLAS size x{rules['atlas_size_factor']['eval']:g} in the eval, x{rules['atlas_size_factor']['funded']:g} funded"
                   + (f" (now on for: {', '.join(names)})" if len(names) > 1 else "") + ". The running bot picks it up at its next poll."}


def _rapid_name(nm: str, root: str | None = None):
    """A Rapid EOD's Name (data/rapid.json / data/rapid2.json): its own ATLAS lane, never this combo. None = not a Rapid."""
    for rel, lab in ((os.path.join("data", "rapid.json"), "the Rapid EOD"), (os.path.join("data", "rapid2.json"), "the 2nd Rapid EOD")):
        j = _read(_path(rel, root))
        if isinstance(j, dict) and str(j.get("account") or "").strip() == nm:
            return lab
    return None


def set_off(root: str | None = None, today: str | None = None, account: str | None = None) -> dict:
    """OFF for every account, or (account) for that one Name only (the others stay on)."""
    old = read_switch(root)
    day = today or _dt.date.today().isoformat()
    nm = str(account or "").strip()
    left = [a for a in (old.get("accounts") or []) if a != nm] if nm else []
    if nm and left:
        blk = {**{k: v for k, v in old.items() if k not in ("on", "account", "accounts")}, "on": True, "account": left[0],
               "accounts": left, "off_set_by_account": {**(old.get("off_set_by_account") or {}), nm: day}}
        p = _write_switch(blk, root)
        return {"ok": True, "path": p, "say": f"ATLAS + Zlarior on ONE account: OFF for {nm} (still on for {', '.join(left)}; an "
                                              "ATLAS trade open there is managed to its exit)"}
    blk = {"on": False, "account": old.get("account") or "", "accounts": [], "off_set": day}
    p = _write_switch(blk, root)
    return {"ok": True, "path": p, "say": "ATLAS + Zlarior on ONE account: OFF (an ATLAS trade open on the account is managed to its exit)"}


def status(root: str | None = None) -> dict:
    sw, rules = read_switch(root), load_rules(root)
    return {"on": bool(sw.get("on")), "account": sw.get("account") or None, "accounts": sw.get("accounts") or [],
            "set": sw.get("set"), "rules": rules, "decide_yes": decide_yes(root), "label": LABEL}


OWNER_STEPS = (
    '1. Sim first: python -X utf8 -m engine.combo50k --on --account "Sim101"  (type I ACCEPT LIVE RISK when asked), then '
    "START BOT with Zlarior's account set to Sim101 in NinjaTrader for one or two days.",
    "2. Watch one or two days: the phone / Board say \"ATLAS on Zlarior 50K: LONG opened\" or \"Zlarior on its 50K: ...\"; "
    "never two positions on Sim101, never long on one account and short on another.",
    "3. Tap yes on the Decide card zlarior-atlas-50k, then: python -X utf8 -m engine.combo50k --on --account \"<your 50K Name>\" "
    "(the phrase again). Off any time: python -X utf8 -m engine.combo50k --off",
    "4. The Builder 25K #2 too (engine/combo25.py): python -X utf8 -m engine.combo50k --on --account \"<your 25K #2 Name>\" "
    "(the phrase again). Off for that one only: python -X utf8 -m engine.combo50k --off --account \"<your 25K #2 Name>\"",
)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ATLAS + Zlarior on ONE account (the Builder 50K): the owner's switch")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--on", action="store_true")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--account", default=None)
    ap.add_argument("--steps", action="store_true", help="print the owner's three steps")
    a = ap.parse_args(argv)
    if a.on:
        print(f" ATLAS will ALSO trade {a.account or '?'} (Zlarior's account), one position at a time.")
        try:
            phrase = input(" Type  I ACCEPT LIVE RISK  then Enter (anything else stops here, nothing switched on): ")
        except EOFError:
            phrase = ""
        r = set_on(a.account or "", phrase)
        print(" " + (r.get("say") if r.get("ok") else "NOT switched on: " + str(r.get("error"))))
        return 0 if r.get("ok") else 1
    if a.off:
        print(" " + set_off(account=a.account)["say"])
        return 0
    if a.steps:
        print("\n".join(OWNER_STEPS))
        return 0
    s = status()
    print(json.dumps(s, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
