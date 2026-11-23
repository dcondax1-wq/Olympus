"""Account B (owner 2026-10-22): the second strategies on their OWN prop account, next to LIT's eval. OFF by default.

Where the block lives (2026-10-26): data/account_b.json on the PC (local, gitignored: {"account_b": {...} | null}); the
tracked second_model.json ships "account_b": null and is never written for it (a dirty tracked file blocked every update).
raw_cfg() reads the local file first, else second_model.json's block; migrate_local() moves an older version's block.
The block: "account_b": null (default = off, the bot is exactly today's) or
  {"account": "<NinjaTrader account Name>", "plan": "builder25k" | "builder50k", "eval_start": "yyyy-mm-dd",
   "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need" | "safe"}
  optional (ATLAS v2, research/writeups/atlas-v2.md, BUILT BUT OFF: absent = exactly today's behaviour):
    "weights": {"<key>": w}  per-member size weight: micros = max(1, int(need micros x w)), then the soft-daily-loss guard
                             (= tools/atlas.q_variant); a member not listed trades at 1.0
    "min_room": 200          stuck = room under this many $ (replaces MIN_ROOM = $100 for this account): no new trade,
                             push "buy a new one"
  zombie-eval rule (research/writeups/2026-11-15-atlas-deep.md; ON since the owner's "Fix atlas" 2026-11-15: absent = ON at
  the values below; "eval_min_room": null / "last_bullet": null in the block turns each off = the old behaviour):
    "eval_min_room": 200     the EVAL stage's stuck line only (the funded stage keeps min_room / $100): an eval with
                             less room than this is given up ("buy a new one", $43) instead of idling for weeks
    "last_bullet": 0.8       eval "need" size says 0 micros because one micro's stop-out does not fit its share of a
                             low room: 1 micro when that full stop-out (stop + 2 ticks, $1.90) fits this share of the
                             room, then the soft-daily-loss guard (= tools/atlas_deep.py "last_bullet")
  optional: "prior_pnl" ($ on the account before the bot traded it), "armed": false (a REAL, non-Sim account also needs
  "armed": true, the LIVE phrase typed at the bot's start and NINJATRADER_LIVE=1: engine/ninjatrader._live_gate; the bot
  never sets any of that).
Owner switch: python -m engine.second --account-b "<Name>" --plan builder25k --start <day>  |  --account-b off
(refused when engine.ninjatrader --selftest fails; research/writeups/second-account-b.md, docs/DAILY_CHECKLIST.md).

What it does (engine/live.py calls it after LIT's routing and state save; any exception is logged and never touches LIT):
  * its own adapter (NinjaTrader OIF route to that account, own order-file tag "acctb_", own NinjaTrader state file; paper
    when the bot is on paper), own ledger, own state file (live_state_acctb.json next to the bot's), own guards;
  * its own eval: balance, EOD trailing floor (the plan's max loss, locked at start + $100), room, session count from
    eval_start, pass ($1,500 / $3,000 target reached: no new trade, push "Account B EVAL PASSED"), fail (room <= 0: no
    trade, push), stuck (room under $100: 1 micro no longer fits a stop, push "buy a new one"), the plan's soft daily loss
    ($600 / $1,000: no new entry for the rest of the day);
  * its own size per the plan (engine/sizing.py):
      need  LIT's two_week "one winner passes" on the plan (micros so the trade's target covers what is left to the target,
            capped at 60% (50K) / 50% (25K) of the room and the soft daily loss, max 40 / 20 micros, for 10 sessions; then
            safe_eval 60% / 30%) = engine/multi_account.sizing_cfg of the plan's preset + sizing.lit_qty, exactly what
            tools/second_account_b.py scores;
      safe  $300 (50K) / $150 (25K) risk, capped at 60% of the room and the soft daily loss (sizing.second_qty);
  * the strategies' own trades (engine/second.run: the research code on closed bars), entered at market at the 5m open
    after the signal close (probe with the bar's real open, as LiveBot._second_entry), checked once the fill bar closed,
    breakeven moves / 15-minute cuts / 15:55 flat / model exits routed; one position at a time on B, max 2 entries a day;
  * NEVER opposite to LIT (MFFU bans long + short on one underlying, also across your own accounts,
    research/lit/mffu_rules.json "hedging"): a B entry is blocked while LIT's account holds, enters or has an armed setup
    (limit / waiting for its 1m CISD) in the other direction, or an extra account (engine/multi_account.py) holds the other
    side; when LIT enters opposite while B is open (or B's entry is pending), B is closed at market FIRST (reason HEDGE) and
    LIT's order goes out only once that close is CONFIRMED flat (2026-10-25; unconfirmed by LIT's entry deadline -> LIT's
    entry skipped, critical "HEDGE BLOCKED: ATLAS close not confirmed"; B is never marked flat on an unconfirmed close)
    (second-mix.md no_hedge rule: skip / close at LIT's opposite entry; the armed-setup block is stricter than the research).
    Same direction as LIT is allowed (two accounts, two positions).
  * strategies on account B are never also routed on LIT's account (LiveBot._second_cfg drops them there).

FUNDED (2026-10-26, owner: "when its eval passes the bot keeps trading it under the funded rules"; research/writeups/
atlas-funded.md, tests/test_account_b_funded.py). Never automatic: a pass only stops the eval and pushes "EVAL PASSED: run
the funded switch". The switch (MFFU gives the funded account its OWN new Name):
    python -X utf8 -m engine.account_b --to-funded --account "<funded Name>" --start <first funded day> [--balance 25000]
  (or the Start page: Accounts > ATLAS's 25K > "Passed → funded") writes the local block's funded stage, DISARMED:
    "stage": "funded", "funded_start": "yyyy-mm-dd", "funded_balance": $ (the funded account's balance on that day as MFFU
    shows it, default the plan start; above / below it counts as P&L before the bot), "payouts": {day: $ requested},
    "eval_account": the passed eval's Name (history), "funded_set": the day of the switch
  + the funded Name on the NinjaTrader allowlist; the eval's state file is kept as live_state_acctb.eval_<Name>.json.
  A real funded account trades only after the owner arms it himself (the Start page's typed phrase: engine/go.arm_b).
  Every other switch (arm_b, launch prep, set_account_b on the same Name) keeps the funded stage.
  What changes on B in the funded stage (engine/multi_account PRESETS <plan>.sizing.funded, research/writeups/uprisk.md):
    size   engine/sizing.funded_qty on the plan's funded preset: 25K = risk 60% of the room to the floor, at most $750
           (x20/stop past a 20-pt stop), a winner pays at most $1,000 (one max payout request), the $600 soft daily loss,
           20 micros, no trade when 1 micro's full stop-out (stop + 2 ticks, $1.90) could reach the floor (skip_breach);
           then the soft daily loss guard (dll_guard) as in the eval. The member weights never raise it.
    state  balance / EOD trailing floor (the plan's max loss, locked at start + $100; after the first payout the floor sits at
           start + $100) from B's closes since funded_start + the payouts (engine/multi_account.sizing_state "funded");
    stops  lost (room <= 0), stuck (room under $100 = min_room, as a funded extra account: 1 micro no longer fits most
           stops; push "buy a new eval") and graduated (5 sim payouts: MFFU moves it to live, you must be present) = no new
           trade;
    payout the MFFU payout tracker (engine/funded_life.track): buffer ($1,100 on the 25K, it stays in the account), the 50%
           consistency rule per cycle (it limits payouts, not trading), 2 traded days a cycle, the first request 48 h
           after the first funded trade, request $250-$1,000, 80% to you, payouts n of 5; pushes "PAYOUT READY: request $X"
           (with the record line), consistency, lost, graduated. The bot never requests a payout:
    python -X utf8 -m engine.account_b --payout <day>=<$>      record one after MFFU paid it
    python -X utf8 -m engine.account_b --funded-status          the tracker now
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time as _time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS = {
    "builder50k": {"preset": "mffu_builder_50k", "label": "MFFU Builder 50K", "safe_usd": 300.0, "price": 91.80},
    "builder25k": {"preset": "mffu_builder_25k", "label": "MFFU Builder 25K", "safe_usd": 150.0, "price": 63.00},
    # ATLAS on the MFFU Rapid EOD 50K next to LIT (engine/rapid.py RapidAtlas sizes it: $500 / 30% of the room)
    "rapideod50k": {"preset": "mffu_rapid_eod_50k", "label": "MFFU Rapid EOD 50K", "safe_usd": 500.0, "price": 94.00},
    "rapideod25k": {"preset": "mffu_rapid_eod_25k", "label": "MFFU Rapid EOD 25K", "safe_usd": 250.0, "price": 97.20},
}
SIZINGS = ("need", "safe")
MAX_PER_DAY = 2
MAX_AGE_S = 45                  # a 5m open seen later than this is not probed (the research fills at the open)
MIN_ROOM = 100.0
ZOMBIE_ON = {"eval_min_room": 200.0, "last_bullet": 0.8}      # owner "Fix atlas" 2026-11-15 (atlas-deep.md)
# ATLAS funded-stage switches (2026-11-20), OFF = None. The lead flips one value after the owner's YES on its Decide card:
#   "funded_room_pct": 0.4   card atlas-funded-room-40     (risk 40% of the room a trade instead of the preset's 60%)
#   "streak_shrink": 2       card atlas-funded-streak-1micro (after 2 losing trades in a row, 1 micro until a winner)
# A key in the account_b block overrides this (null there = off for that account). Funded stage only.
FUNDED_ON = {"funded_room_pct": 0.4, "streak_shrink": 2}   # owner YES 2026-11-20 ~08:00 ET in chat (both cards; skeptic code review: research/writeups/skeptic-live-patches-2026-11-20.md)
CLOSE_RETRY_S = 10              # an unconfirmed close of B's position is re-sent at most this often (pre-launch audit A4)
TICK, PV, COMM = 0.25, 2.0, 1.90
ADAPTER_FACTORY = None          # tests: (spec, adapter cfg) -> adapter; None = engine/live.ADAPTERS
PROBLEM_SENDER = None           # tests: (problem payload) -> why; None = engine/notify.instant_problem in a thread (AccountB.no_start)
VERSION = 1
STAGES = ("eval", "funded")
# the funded stage's keys in the block (kept by every other switch on the same account Name: set_account_b)
FUNDED_KEYS = ("stage", "funded_start", "funded_balance", "payouts", "eval_account", "funded_set")
PAYOUT_CMD = "python -X utf8 -m engine.account_b --payout {day}={amount}"
FUNDED_CMD = 'python -X utf8 -m engine.account_b --to-funded --account "<funded Name>" --start <first funded day>'
STOP_STATUSES = ("passed", "failed", "stuck", "lost", "graduated")   # eval / funded statuses: no new entry on B
IDLE_LIMIT, IDLE_WARN = 7, 5      # MFFU inactivity: 7 calendar days without a trade; warn from day 5 (rules audit 2026-11-17)


def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _tick(px, d=1, target=False):
    from .live import tick_px
    return tick_px(px, d, target=target)


# ---------------------------------------------------------------------------------------------------------------- config
# Where the block lives (owner 2026-10-25, "unblock updates"): the PC's own account B is LOCAL, data/account_b.json next to
# second_model.json (gitignored) = {"account_b": {...} | null}. The tracked second_model.json keeps shipping
# "account_b": null, so a block written on the PC (launch prep, arming the 25K) never makes the tracked file dirty again:
# a dirty second_model.json blocked every auto-update and the phone's "update" (heartbeat 2026-10-25). Read order: the
# local file when it is there (also when it says null = off), else second_model.json's "account_b" (the cloud, tests,
# a PC that never wrote one). migrate_local() moves a block an older version wrote into the tracked file.
LOCAL_REL = os.path.join("data", "account_b.json")


def cfg_path(path: str | None = None) -> str:
    from . import second
    return path or second.CFG_PATH


def local_path(path: str | None = None) -> str:
    """The local file for this second_model.json: <its folder>/data/account_b.json (repo root -> data/account_b.json; a
    test's temp copy -> <temp>/data/account_b.json, never the real one)."""
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path(path))), LOCAL_REL)


def read_local(path: str | None = None) -> tuple:
    """(found, block): found False when the local file is missing or unreadable (then second_model.json's block counts)."""
    try:
        with open(local_path(path), encoding="utf-8") as fh:
            c = json.load(fh)
        if not isinstance(c, dict) or "account_b" not in c:
            return False, None
        ab = c.get("account_b")
        return True, (ab if isinstance(ab, dict) and ab else None)
    except Exception:
        return False, None


def write_local(block, path: str | None = None, why: str = "") -> str:
    """data/account_b.json = {"account_b": block} (atomic). Returns the file path."""
    p = local_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rec = {"account_b": block if isinstance(block, dict) and block else None, "saved_at": int(_time.time()),
           "note": "ATLAS's account on this PC (engine/account_b.py). Local, gitignored: second_model.json ships account_b null."
           + (f" {why}" if why else "")}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, ensure_ascii=False)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, p)
    return p


def tracked_cfg(path: str | None = None):
    """second_model.json's own "account_b" (None = off / unreadable)."""
    try:
        with open(cfg_path(path), encoding="utf-8") as fh:
            c = json.load(fh)
        ab = c.get("account_b") if isinstance(c, dict) else None
        return ab if isinstance(ab, dict) and ab else None
    except Exception:
        return None


def raw_cfg(path: str | None = None):
    """The account_b block (None = off): data/account_b.json when it is there, else second_model.json's. Never raises."""
    found, ab = read_local(path)
    if found:
        return ab
    return tracked_cfg(path)


def normalize(ab: dict | None, scfg: dict | None = None, lit_account: str | None = None) -> dict | None:
    """The account_b block -> a spec {"account", "plan", "preset", "rules", "eval_start", "strategies", "sizing", "label",
    "problem": why it cannot trade or None}; None when off."""
    if not isinstance(ab, dict) or not ab:
        return None
    from . import multi_account as MA
    from . import second
    scfg = scfg or second.load_cfg()
    plan = str(ab.get("plan") or "builder50k").lower().replace(" ", "").replace("_", "")
    P = PLANS.get(plan)
    keys = ab.get("strategies")
    keys = [str(k) for k in keys] if isinstance(keys, (list, tuple)) else ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]
    out = {"account": str(ab.get("account") or "").strip(), "plan": plan, "eval_start": str(ab.get("eval_start") or ""),
           "strategies": keys, "sizing": str(ab.get("sizing") or "need"), "prior_pnl": float(_num(ab.get("prior_pnl"), 0.0)),
           "eval_anchor": ab.get("eval_anchor"),
           "armed": ab.get("armed") is True, "problem": None}
    out["preset"] = (P or {}).get("preset") or "mffu_builder_50k"
    out["plan_label"] = (P or {}).get("label") or plan
    out["rules"] = MA.rules_of({"preset": out["preset"]})
    out["label"] = f"ATLAS {out['account'] or '?'}"      # ATLAS = the second strategy's account (was "Account B")
    S = scfg.get("strategies") or {}
    bad = [k for k in keys if not isinstance(S.get(k), dict)]
    co = [k for k in keys if isinstance(S.get(k), dict) and S[k].get("cloud_only")]
    nm = out["account"]
    if P is None:
        out["problem"] = f"unknown plan {plan!r} (builder25k or builder50k)"
    elif not nm or any(c in nm for c in ";\r\n|"):
        out["problem"] = "account name missing or invalid"
    elif lit_account and nm == str(lit_account).strip():
        out["problem"] = f"{nm} is LIT's own account: account B must be a different account"
    elif out["sizing"] not in SIZINGS:
        out["problem"] = f"unknown sizing {out['sizing']!r} (need or safe)"
    elif not keys:
        out["problem"] = "no strategies listed"
    elif bad:
        out["problem"] = f"unknown strategies {', '.join(bad)}"
    elif co:
        out["problem"] = f"{', '.join(co)} is cloud only (a paper shadow): never routed"
    elif out["eval_start"]:
        try:
            _dt.date.fromisoformat(out["eval_start"])
        except ValueError:
            out["problem"] = f"eval_start {out['eval_start']!r} is not yyyy-mm-dd"
    # ATLAS v2 keys (built but off): only in the spec when in the block (absent = today's spec, unchanged)
    if "weights" in ab:
        W = ab.get("weights")
        okw = isinstance(W, dict) and all(isinstance(k, str) and _num(v) is not None and 0.0 < float(v) <= 2.0 for k, v in W.items())
        if not okw:
            out["problem"] = out["problem"] or 'weights must be {"<strategy key>": number in (0, 2]}'
        else:
            out["weights"] = {str(k): float(v) for k, v in W.items()}
            unk = [k for k in out["weights"] if k not in keys]
            if unk:
                out["problem"] = out["problem"] or f"weights for strategies not on account B: {', '.join(unk)}"
    if "min_room" in ab:
        mr = _num(ab.get("min_room"))
        if mr is None or not 0.0 <= mr <= 1000.0:
            out["problem"] = out["problem"] or f"min_room {ab.get('min_room')!r} must be a number of $ (0-1000)"
        else:
            out["min_room"] = float(mr)
    if "eval_min_room" not in ab:
        out["eval_min_room"] = ZOMBIE_ON["eval_min_room"]        # owner "Fix atlas" 2026-11-15: ON unless the block says null
    elif ab.get("eval_min_room") is None or ab.get("eval_min_room") is False:
        pass
    else:
        mr = _num(ab.get("eval_min_room"))
        if mr is None or not 0.0 <= mr <= 1000.0:
            out["problem"] = out["problem"] or f"eval_min_room {ab.get('eval_min_room')!r} must be a number of $ (0-1000)"
        else:
            out["eval_min_room"] = float(mr)
    if "last_bullet" not in ab:
        out["last_bullet"] = ZOMBIE_ON["last_bullet"]
    elif ab.get("last_bullet") is not None and ab.get("last_bullet") is not False:
        lb = _num(ab.get("last_bullet"))
        if lb is None or not 0.0 < lb <= 1.0:
            out["problem"] = out["problem"] or f"last_bullet {ab.get('last_bullet')!r} must be a share of the room in (0, 1]"
        else:
            out["last_bullet"] = float(lb)
    # funded-stage switches (2026-11-20, research/writeups/atlas-edge-2026-11-20.md / atlas-risk-real-fills-2026-11-20.md):
    # FUNDED_ON (repo default, None = OFF) unless the block has the key; OFF = today's behaviour, unchanged
    # repo defaults apply to the Builder 25K funded account only (day-newstrat skeptic 2026-11-20: never a funded combo 50K via
    # engine/combo50k.ab_spec, which no card covers); a key in the block still overrides for any plan
    sw = {k: (ab.get(k) if k in ab else (FUNDED_ON.get(k) if plan == "builder25k" else None)) for k in FUNDED_ON}
    if sw["funded_room_pct"] is not None:                  # "room 40%": share of the room a funded trade may risk
        fp = _num(sw["funded_room_pct"])
        if fp is None or not 0.1 <= fp <= 0.6:
            out["problem"] = out["problem"] or f"funded_room_pct {sw['funded_room_pct']!r} must be a share of the room in [0.1, 0.6]"
        else:
            out["funded_room_pct"] = float(fp)
    if sw["streak_shrink"] is not None:                    # after N losing closed trades in a row: 1 micro until a winner
        ss = _num(sw["streak_shrink"])
        if ss is None or int(ss) != ss or not 1 <= int(ss) <= 10:
            out["problem"] = out["problem"] or f"streak_shrink {sw['streak_shrink']!r} must be a whole number of losses (1-10)"
        else:
            out["streak_shrink"] = int(ss)
    out["keys"] = [k for k in keys if isinstance(S.get(k), dict) and S[k].get("on", True) and not S[k].get("cloud_only")]
    # the stage (2026-10-26): "eval" (absent = the eval, exactly as before) or "funded" (python -m engine.account_b --to-funded)
    stage = str(ab.get("stage") or "eval").strip().lower()
    out["stage"] = stage
    if stage not in STAGES:
        out["problem"] = out["problem"] or f"unknown stage {ab.get('stage')!r} (eval or funded)"
    elif stage == "funded":
        F, why = funded_block(ab, out["rules"])
        out["funded"] = F
        out["plan_label"] = f"{out['plan_label']} funded"
        if why:
            out["problem"] = out["problem"] or why
    return out


def funded_block(ab: dict, rules: dict) -> tuple:
    """The funded stage's keys of an account_b block -> ({"start", "balance", "prior", "payouts", "eval_account", "set"},
    problem or None). balance = the funded account's balance on funded_start (default the plan start); prior = balance -
    the plan start ($ before the bot, counted as one day before the start)."""
    start = str(ab.get("funded_start") or "")
    R0 = float(rules["start"])
    bal = R0 if ab.get("funded_balance") in (None, "") else _num(ab.get("funded_balance"))
    pays, bad_pay = {}, None
    for d, v in ((ab.get("payouts") or {}) if isinstance(ab.get("payouts"), dict) else {}).items():
        try:
            _dt.date.fromisoformat(str(d))
            x = float(v)
            if not x > 0:
                raise ValueError
            pays[str(d)] = round(x, 2)
        except (TypeError, ValueError):
            bad_pay = f"payout {d!r}: {v!r} is not yyyy-mm-dd = $ above 0"
    if ab.get("payouts") is not None and not isinstance(ab.get("payouts"), dict):
        bad_pay = 'payouts must be {"yyyy-mm-dd": $}'
    F = {"start": start, "balance": float(bal) if bal is not None else R0, "prior": round((float(bal) if bal is not None else R0) - R0, 2),
         "payouts": dict(sorted(pays.items())), "eval_account": str(ab.get("eval_account") or "") or None,
         "set": str(ab.get("funded_set") or "") or None}
    why = None
    try:
        _dt.date.fromisoformat(start)
    except ValueError:
        why = f"funded_start {start!r} is not yyyy-mm-dd ({FUNDED_CMD})"
    lo, hi = R0 - float(rules["mll"]), R0 + 5.0 * float(rules["mll"])
    if not why and (bal is None or not lo < float(bal) <= hi):
        why = f"funded_balance {ab.get('funded_balance')!r} is not a funded balance for this plan (above ${lo:,.0f}, up to ${hi:,.0f})"
    if not why and bad_pay:
        why = bad_pay
    if not why and pays and min(pays) < start:
        why = f"payout on {min(pays)} is before the funded start {start}"
    return F, why


def is_funded(spec: dict | None) -> bool:
    return bool(spec) and spec.get("stage") == "funded" and isinstance(spec.get("funded"), dict)


def min_room(spec: dict | None) -> float:
    """The stuck threshold of this account: in the eval stage spec "eval_min_room" (zombie-eval rule, off by default) if
    set, else spec "min_room" (account_b "min_room", ATLAS v2, off by default), else MIN_ROOM."""
    s = spec or {}
    if s.get("eval_min_room") is not None and not is_funded(s):
        return float(s["eval_min_room"])
    v = s.get("min_room")
    return float(v) if v is not None else MIN_ROOM


def weight(spec: dict | None, key: str | None) -> float:
    """The member's size weight (account_b "weights", ATLAS v2, off by default): 1.0 when absent / not listed."""
    W = (spec or {}).get("weights") or {}
    return float(W.get(key, 1.0)) if key is not None else 1.0


def _weighted(r: dict, w: float) -> dict:
    """micros x the member's weight (min 1 while the base size is >= 1; = tools/atlas.q_variant). w == 1.0: r unchanged."""
    q = int(r.get("qty") or 0)
    if w == 1.0 or q <= 0:
        return r
    q2 = max(1, int(q * w + 1e-9)) if w > 0 else 0
    return {**r, "qty": q2, "reasons": list(r.get("reasons") or []) + [f"member weight {w:g}: {q} -> {q2}"]}


def keys_on_b(ab: dict | None = None) -> list:
    """The strategies account B trades (never also routed on LIT's account)."""
    ab = raw_cfg() if ab is None else ab
    if not isinstance(ab, dict) or not ab:
        return []
    k = ab.get("strategies")
    return [str(x) for x in k] if isinstance(k, (list, tuple)) else ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]


def sizing_cfg(spec: dict, base: dict | None = None) -> dict:
    """live_model.json lit_sizing + the plan preset's sizing in two_week mode (engine/multi_account.sizing_cfg): the
    sizer config of a "need" trade on account B (tools/second_account_b.sizing_cfg). The day guard of the 25K preset
    allows 2 entries a day (account B's own limit)."""
    from . import multi_account as MA
    if base is None:
        try:
            base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
        except Exception:
            base = {}
    s = MA.normalize({"id": "acctb", "preset": spec["preset"], "mode": "two_week", "adapter": "paper", "eval_start": spec.get("eval_start")})
    c = MA.sizing_cfg(base, s)
    c["mode"] = "two_week"
    c["eval_start"] = spec.get("eval_start") or ""
    if c.get("guard") is not None:
        c["guard"] = {**c["guard"], "max_per_day": MAX_PER_DAY}
    c.setdefault("two_week", {})["dll"] = float(spec["rules"]["dll"])
    c.pop("wk_loss_usd", None)
    return c


def qty(spec: dict, trade: dict, state: dict | None, base: dict | None = None, key: str | None = None) -> dict:
    """Micros for one account B entry: {"qty", "reasons", "lock"}. trade = {"risk_pts", "tgt_pts", ...}; state =
    the account's eval state (multi_account.sizing_state). Fails closed (0) on any error / unknown state. key = the member
    (its spec "weights" entry, ATLAS v2: absent = 1.0 = today's size)."""
    from . import lit as _lit
    from . import sizing as SZ
    if is_funded(spec):
        return funded_qty(spec, trade, state, base=base, key=key)
    R = spec["rules"]
    maxq = int(R["max_micros"])
    if state is None:
        return {"qty": 0, "reasons": ["eval state unknown (eval_start missing?): not traded"], "lock": None}
    risk = _num(trade.get("risk_pts"))
    if not risk or risk <= 0:
        return {"qty": 0, "reasons": ["no stop distance"], "lock": None}
    c = sizing_cfg(spec, base)
    if spec.get("sizing") == "safe":
        r = SZ.second_qty(float(risk), PLANS[spec["plan"]]["safe_usd"], c, state=dict(state), max_micros=maxq)
        r = _weighted({"qty": min(maxq, int(r["qty"])), "reasons": list(r["reasons"]), "lock": r.get("lock")}, weight(spec, key))
        return dll_guard(r, float(risk), R, state)
    m0 = _lit.qty_for(float(risk))
    if not m0:
        return {"qty": 0, "reasons": ["no size"], "lock": None}
    r = SZ.lit_qty(m0, {"risk_pts": float(risk), "tgt_pts": _num(trade.get("tgt_pts")), "size_mult": 1.0}, c, room=state.get("room"),
                   state=dict(state), max_micros=maxq, learning=None)
    r = _weighted({"qty": min(maxq, int(r.get("qty") or 0)), "reasons": list(r.get("reasons") or []), "lock": r.get("lock")},
                  weight(spec, key))
    if int(r.get("qty") or 0) <= 0 and spec.get("last_bullet") is not None:
        r = last_bullet(r, float(risk), float(spec["last_bullet"]), state)
    return dll_guard(r, float(risk), R, state)


def last_bullet(r: dict, risk: float, share: float, state: dict) -> dict:
    """Zombie-eval rule (account_b "last_bullet", off by default): the need size said 0 micros on a low room; 1 micro when
    its full stop-out (stop + 2 ticks of slippage, $1.90 round trip, as dll_guard) fits `share` x the room. The soft daily
    loss guard runs after it. Never more than 1 micro."""
    from . import sizing as SZ
    room = _num(state.get("room"))
    if room is None or room <= 0:
        return r
    # only when the 0 came from the room share (the "skip: ... room" line), never over a deliberate stop: a passed eval's
    # target-reached / pass lock, a lock, the daily loss (found by the funded-account test, 2026-11-15)
    why = [str(x) for x in (r.get("reasons") or [])]
    if r.get("lock") or not any("skip:" in x and "room" in x for x in why) or \
            any("already reached" in x or "lock" in x for x in why):
        return r
    loss1 = (float(risk) + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    if loss1 > float(share) * float(room):
        return r
    return {**r, "qty": 1, "reasons": list(r.get("reasons") or []) +
            [f"last bullet: 1 micro, its full stop-out ${loss1:,.0f} fits {share:.0%} of the ${float(room):,.0f} room"]}


def funded_cfg(spec: dict, base: dict | None = None) -> dict:
    """live_model.json lit_sizing + the plan preset's sizing in mode funded (engine/multi_account.sizing_cfg): "funded" =
    the preset's funded rule (25K: pct 0.6, $50-$750, ref 20, max_win $1,000, slip 2 ticks, skip_breach), "acct" = the
    plan's $ limits (dll, mll, lock, max micros; absolute, no scale)."""
    from . import multi_account as MA
    if base is None:
        try:
            base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
        except Exception:
            base = {}
    s = MA.normalize({"id": "acctb", "preset": spec["preset"], "mode": "funded", "adapter": "paper"})
    c = MA.sizing_cfg(base, s)
    c["mode"] = "funded"
    if spec.get("funded_room_pct") is not None:            # OFF by default: the preset's own share (25K: 0.6)
        c["funded"] = {**(c.get("funded") or {}), "pct": min(float((c.get("funded") or {}).get("pct", 0.6)), float(spec["funded_room_pct"]))}
    return c


def loss_streak(closes, start: str | None = None) -> int:
    """Losing closed trades in a row at the end of account B's own closes ([day, exit_t, pnl, entry_t], this account
    only: _load drops another account's file), since the funded start; a close with pnl >= 0 ends the streak."""
    n = 0
    rows = sorted((c for c in closes or [] if len(c) >= 3 and c[1] is not None and c[2] is not None
                   and (not start or str(c[0]) >= str(start))), key=lambda c: int(c[1]))
    for c in reversed(rows):
        if float(c[2]) < 0:
            n += 1
        else:
            break
    return n


def streak_cap(r: dict, spec: dict, state: dict) -> dict:
    """streak_shrink (OFF by default): after N losing trades in a row, 1 micro until the next winner. Only lowers a size of
    2+ to 1: never below 1 micro, never above the size it was given."""
    n = spec.get("streak_shrink")
    q = int(r.get("qty") or 0)
    ls = int((state or {}).get("loss_streak") or 0)
    if not n or q <= 1 or ls < int(n):
        return r
    return {**r, "qty": 1, "reasons": list(r.get("reasons") or []) + [f"loss streak: {ls} losing trades in a row (>= {int(n)}): 1 micro until a winner"]}


def funded_qty(spec: dict, trade: dict, state: dict | None, base: dict | None = None, key: str | None = None) -> dict:
    """Micros for one account B entry in the FUNDED stage: engine/sizing.funded_qty on the plan's funded preset (the same
    rule as a funded extra account, engine/multi_account), never above the plan's max micros, then the learned cost reserve
    (lit_sizing learn_costs, off by default; never more), the member weight (never above the funded caps) and the soft daily
    loss guard. state = funded state {room, cum, locked, ...} (AccountB.eval_state). Fails closed (0)."""
    from . import sizing as SZ
    R = spec["rules"]
    maxq = int(R["max_micros"])
    if state is None:
        return {"qty": 0, "reasons": ["funded state unknown (funded_start missing?): not traded"], "lock": None}
    risk = _num(trade.get("risk_pts"))
    if not risk or risk <= 0:
        return {"qty": 0, "reasons": ["no stop distance"], "lock": None}
    room = _num(state.get("room"))
    if room is not None and room <= 0:
        return {"qty": 0, "reasons": [f"funded account lost: room ${room:,.0f} to the max-loss floor: no new trade"], "lock": "lost"}
    c = funded_cfg(spec, base)
    why: list = []
    q = SZ.funded_qty({"risk_pts": float(risk), "tgt_pts": _num(trade.get("tgt_pts")), "size_mult": 1.0}, dict(state),
                      c.get("funded") or {}, acct={**(c.get("acct") or {}), "max_micros": maxq}, why=why)
    r = {"qty": min(maxq, int(q or 0)), "reasons": [f"funded: {w}" for w in why], "lock": None}
    if c.get("learn_costs") and r["qty"] > 0:
        r = SZ.cost_reserve(r, {"risk_pts": float(risk)}, c, state=dict(state), bot="atlas")
    q0 = int(r.get("qty") or 0)
    r = _weighted(r, weight(spec, key))
    if int(r.get("qty") or 0) > q0:
        r = {**r, "qty": q0, "reasons": list(r.get("reasons") or []) + [f"member weight: never above the funded caps -> {q0}"]}
    r = streak_cap(r, spec, state)
    return dll_guard(r, float(risk), R, state)


def dll_guard(r: dict, risk: float, rules: dict, state: dict) -> dict:
    """The plan's soft daily loss, on EVERY account B trade (2026-10-22 fix: after session 10 safe_eval had no daily check,
    and the 50K preset had no day guard at all: one stop-out could cost $628 on the 25K / $1,255 on the 50K against a
    $600 / $1,000 limit). One trade's full stop-out, as the research models it (stop + 2 ticks of slippage, $1.90 a micro
    round trip = engine/sizing.TW_DLL_SLIP / TW_COMM), never exceeds what is left of today's soft daily loss
    (dll + today's closed P&L state["cum"]); when not even 1 micro fits: no trade."""
    from . import sizing as SZ
    q = int(r.get("qty") or 0)
    if q <= 0:
        return r
    dll = _num(rules.get("dll"))
    if not dll:
        return r
    left = float(dll) + float(_num(state.get("cum"), 0.0))
    loss1 = (float(risk) + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    cap = int(max(0.0, left) / loss1 + 1e-9)
    if cap >= q:
        return r
    out = {**r, "reasons": list(r.get("reasons") or [])}
    if cap < 1:
        out["qty"] = 0
        out["reasons"].append(f"soft daily loss: 1 micro's full stop-out ${loss1:,.0f} > ${left:,.0f} left of today's ${float(dll):,.0f}: no trade")
    else:
        out["qty"] = cap
        out["reasons"].append(f"soft daily loss: {cap} x ${loss1:,.0f} full stop-out fits the ${left:,.0f} left of today's ${float(dll):,.0f} -> {cap}")
    return out


# ---------------------------------------------------------------------------------------------------------------- account
class AccountB:
    """Account B on one PC bot (engine/live.py LiveBot.acct_b)."""

    def __init__(self, bot, spec: dict, state_path: str | None = None, adapter_factory=None):
        self.bot = bot
        self.spec = spec
        self.rules = spec["rules"]
        self.name = spec["account"]
        self.label = spec["label"]
        self.problem = spec.get("problem")
        self.state_path = state_path or _state_path_for(getattr(bot, "state_path", None))
        self.adapter_factory = adapter_factory if adapter_factory is not None else ADAPTER_FACTORY
        self.adapter = None
        self.ledger: list = []
        self.closes: list = []            # [day, exit_t, pnl, entry_t]
        self.prov: dict = {}              # entry_t -> what was routed (key, dir, qty, entry, stop, target, ...)
        self.open_t = None                # entry_t of the open position on B
        self.seen: set = set()
        self.lock = None                  # {"day", "reason"}: no new entry today
        self.notified: list = []          # push keys already sent (pass / fail / stuck)
        self.held: dict = {}              # str(5m open) -> {"key", "why"}: a member's signal B saw and did not route, and why
                                          # (tools/trade_watch.py: a twin entry with a reason here is not a mismatch)
        self.notes: dict = {}
        self.view = None
        self.view_key = None
        self.last_size = None
        self._startup_ok = None           # startup_block: set once B's own NinjaTrader account reconciled (entries allowed)
        self.start_missing = False        # start(): stopped for no start day (no_start); LiveBot applies a fixed block at once
        self.mx = threading.RLock()

    # ---- plumbing
    def clock(self):
        return self.bot.clock()

    def log(self, kind, text):
        try:
            self.bot._log(kind, f"[{self.label}] {text}")
        except Exception:
            print(f"[{self.label}] {kind}: {text}")

    def note(self, key, kind, text):
        if self.notes.get(key) == text:
            return
        self.notes[key] = text
        self.log(kind, text)

    def kind(self) -> str:
        ad = (self.bot.cfg or {}).get("adapter") or "paper"
        if ad != "ninjatrader":
            return "PAPER"
        from .ninjatrader import is_sim
        return "SIM" if is_sim(self.name) else "LIVE"

    def adapter_cfg(self) -> dict:
        """The bot's cfg (instrument, folder, params) WITHOUT LIT's account and arming, then account B's own name, arming,
        order-file tag and state files. A real account needs "armed": true in account_b AND the phrase typed at start AND
        NINJATRADER_LIVE=1 (the adapter's _live_gate); the bot's own arming is never inherited."""
        b = self.bot.cfg or {}
        base = {k: v for k, v in b.items() if k not in ("accounts", "armed", "confirm", "nt_account", "nt_state_path", "nt_audit_log",
                                                       "eval_start", "eval_prior_pnl", "eval_anchor", "lit_sizing", "funded",
                                                       "webhook_url", "account_b")}
        p = dict(base.get("params") or {})
        p["max_micros"] = min(int(p.get("max_micros", 40) or 40), int(self.rules["max_micros"]))
        d = os.path.dirname(self.state_path)
        real = self.real_bot()
        return {**base, "adapter": "ninjatrader" if b.get("adapter") == "ninjatrader" else "paper", "nt_account": self.name,
                "armed": bool(self.spec.get("armed")), "confirm": (b.get("confirm") or "") if self.spec.get("armed") else "",
                "params": p, "nt_file_tag": "acctb_", "nt_state_path": os.path.join(d, "ninjatrader_state_acctb.json"),
                "nt_audit_log": os.path.join(os.path.join(ROOT, "logs") if real else d, "ninjatrader_oif_acctb.log")}

    def real_bot(self) -> bool:
        try:
            from .live import STATE_PATH
            return getattr(self.bot, "state_path", None) == STATE_PATH
        except Exception:
            return False

    # code review 2026-11-20 (day-speed helper): start() raised TypeError on an eval block without "eval_start" (the start log
    # formatted the view's room None), LiveBot._sync_account_b caught it and ATLAS silently did not start. Now no start day = a
    # plain problem (logged, one push a day), never an adapter, never a trade; LIT and the other accounts are not touched.
    # The fix the owner runs, per stage ({name} / {plan} filled in; engine/rapid.RapidAtlas has its own):
    START_CMDS = {"eval": 'python -X utf8 -m engine.second --account-b "{name}" --plan {plan} --start <first eval day yyyy-mm-dd>',
                  "funded": 'python -X utf8 -m engine.account_b --to-funded --account "{name}" --start <first funded day yyyy-mm-dd>'}

    def no_start(self) -> str | None:
        """The plain problem when this account's stage has no start day (eval: "eval_start", funded: "funded_start"), else None.
        Without one its eval / funded state is unknown (eval_view status "no eval_start" / "no funded_start"): never traded."""
        funded = str(self.spec.get("stage") or "eval").strip().lower() == "funded"
        day = (self.spec.get("funded") or {}).get("start") if funded else self.spec.get("eval_start")
        if str(day or "").strip():
            return None
        plan = self.spec.get("plan") if self.spec.get("plan") in ("builder25k", "builder50k") else "builder25k"
        nm = self.name if self.name and not any(c in self.name for c in ';\r\n|"') else "<Name>"
        cmd = self.START_CMDS["funded" if funded else "eval"].format(name=nm, plan=plan)
        return (f"its account block has no {'funded' if funded else 'eval'} start day "
                f"({'funded_start' if funded else 'eval_start'}): run {cmd}")

    def _push_no_start(self, text):
        """One push a day per account for a start without a start day: the app notice (as every ATLAS notice) and, on the real
        NinjaTrader bot, the private alert topic's "problems" push (engine/notify.instant_problem, soft: no sound in quiet hours).
        Never raises, never blocks the bot's start (the alert goes in a thread)."""
        try:
            now = int(self.clock())
            key = f"{self.PUSH_SUFFIX.strip(':')}:nostart:{trading_day(now)}:{self.name}"
            if key in self.notified:
                return
            self.notified.append(key)
            title = f"{self.label} did not start"
            body = f"{text[:1].upper()}{text[1:]}. No trade on this account until then; LIT and the other accounts are not affected."
            self._push_text(title, body, key)
            send = PROBLEM_SENDER
            if send is None:
                if not (self.real_bot() and (self.bot.cfg or {}).get("adapter") == "ninjatrader"):
                    return                     # a harness / paper bot: the log and the app notice only
                from . import notify

                def send(p):
                    threading.Thread(target=notify.instant_problem, args=(p,), name="atlas_nostart", daemon=True).start()
                    return "queued"
            send({"key": key, "code": "atlas_no_start", "bot": "atlas", "soft": True, "tags": "warning",
                  "title": title, "body": body})
        except Exception:
            pass

    def start(self):
        self._load()
        miss = self.no_start()
        if miss:
            self.problem, self.start_missing = miss, True
            try:
                self.bot._note_error(f"{self.label} did not start: {miss}")
            except Exception:
                self.log("risk", f"did not start: {miss}")
            self._push_no_start(miss)
            return self
        if self.problem:
            self.log("risk", f"NOT trading: {self.problem}")
            return self
        try:
            cfg = self.adapter_cfg()
            if self.adapter_factory is not None:
                self.adapter = self.adapter_factory(self.spec, cfg)
            else:
                from .live import ADAPTERS
                self.adapter = ADAPTERS[cfg["adapter"]](cfg)
        except Exception as e:
            self.problem = f"adapter failed: {e.__class__.__name__}: {e}"
        self._wire_push()
        dis = self.disabled_reason()
        ev = self.eval_view()
        if self.funded():
            F = self.spec["funded"]
            self.log("system" if not dis else "risk",
                     f"{self.kind()} {self.name} {self.spec['plan_label']}, strategies {', '.join(self.spec['keys'])}, FUNDED sizing "
                     f"(the plan's funded rule) from {F['start']} (balance ${ev.get('balance') or 0:,.0f}, room ${ev.get('room') or 0:,.0f}, "
                     f"payouts {len(F['payouts'])}" + (f"; passed eval {F['eval_account']}" if F.get("eval_account") else "") + "): "
                     + (f"DISABLED ({dis})" if dis else "ready"))
            self.save()
            return self
        self.log("system" if not dis else "risk",
                 f"{self.kind()} {self.name} {self.spec['plan_label']}, strategies {', '.join(self.spec['keys'])}, size {self.spec['sizing']}, "
                 f"eval from {self.spec['eval_start'] or '?'} (balance ${ev.get('balance') or 0:,.0f}, room ${ev.get('room') or 0:,.0f}): "
                 + (f"DISABLED ({dis})" if dis else "ready"))
        self.save()
        return self

    def disabled_reason(self):
        if self.problem:
            return self.problem
        if self.adapter is None:
            return "adapter not created"
        return getattr(self.adapter, "disabled", None)

    def route(self, action: dict) -> dict:
        try:
            ka = self._keepalive_yield(action)             # an open keep-alive on this account / the other way closes first
            res = {"ok": False, "error": "REFUSED: " + ka} if ka else \
                self.adapter.send(action) if self.adapter is not None else {"ok": False, "error": "no adapter"}
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        with self.mx:
            self.ledger.append({"t": int(self.clock()), **action, "result": res})
            self.ledger = self.ledger[-400:]
        self.log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}"
                 + (f" ({res.get('error')})" if res.get("ok") is False and res.get("error") else ""))
        self._life_routed(action, res)
        self.save()
        return res

    def _keepalive_yield(self, action):
        """engine/keepalive.before_entry (OFF by default = None at once): a keep-alive trade open on this NinjaTrader account
        (any side) or the other way on any account is closed at market before this entry goes out. Never raises."""
        if action.get("side") not in ("buy", "sell"):
            return None
        try:
            from . import keepalive as _ka
            return _ka.before_entry(self.bot, 1 if action.get("side") == "buy" else -1, self)
        except Exception:
            return None

    # ---- MFFU lifecycle (engine/lifecycle.py): passed / failed / locked = stand down, the other accounts keep trading
    def life_key(self) -> str:
        from . import lifecycle
        return lifecycle.key_of(self)

    def life_block(self, now):
        from . import lifecycle
        return lifecycle.block(self.bot, self.life_key(), now)

    def _life_routed(self, action, res):
        try:
            from . import lifecycle
            ev = lifecycle.after_route(self.bot, self.life_key(), lifecycle.label_of(self.life_key(), self), self.adapter, action,
                                       res, acct=self.name)
            if ev:
                self.log("risk", f"{ev['title']}: {ev['body']}")
        except Exception:
            pass

    def adapter_tick(self):
        ad = self.adapter
        if ad is None or self.problem or not getattr(ad, "loop_tick", False) or not callable(getattr(ad, "tick", None)):
            return
        try:
            ad.tick()
        except Exception as e:
            self.log("error", f"adapter tick failed: {e.__class__.__name__}: {e}")

    # ---- eval
    def day_pnl(self, day) -> float:
        return round(sum(float(p) for d, _, p, *_ in self.closes if d == day), 2)

    def entries_today(self, day) -> int:
        void = {int(r["entry_t"]) for r in self.ledger if r.get("side") == "exit" and r.get("reason") == "NO TRADE" and r.get("entry_t")}
        return len({int(r["entry_t"]) for r in self.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t")
                    and trading_day(int(r["entry_t"])) == day and int(r["entry_t"]) not in void
                    and (r.get("result") or {}).get("ok") is not False})

    def anchor(self):
        """Account B's eval anchor (engine/sizing.eval_anchor): data/eval_anchor.json "accounts" by its NinjaTrader Name
        next to the bot's state file (`python -m engine.eval_life --anchor --account "<Name>"`), or account_b "eval_anchor";
        the newest as_of wins. None = no anchor (as before)."""
        from . import eval_life as EL
        from . import sizing as SZ
        try:
            f = EL.load_anchor(self.name, state_path=getattr(self.bot, "state_path", None), main=False) if self.name else None
        except Exception:
            f = None
        return SZ.newest_anchor(f, self.spec.get("eval_anchor"), self._broker_anchor())

    # ---- real balance from NinjaTrader (engine/broker_balance.py): account B reads ITS OWN accounts.csv row (self.name)
    def _broker(self):
        if not self.name or not self.spec.get("eval_start") or self.kind() == "PAPER" or self.funded():
            return None                    # the funded stage books from its own closes (as a funded extra account)
        from . import broker_balance as BB
        return BB.for_bot(self.bot)

    def _broker_anchor(self):
        try:
            b = self._broker()
            return b.anchor(self.name, self.spec.get("eval_start")) if b else None
        except Exception:
            return None

    def funded(self) -> bool:
        return is_funded(self.spec)

    def funded_days(self, today=None) -> dict:
        """Closed P&L per trading day since the funded start (today's included)."""
        F = (self.spec.get("funded") or {})
        days = {}
        for d, _, p, *_ in self.closes:
            if F.get("start") and str(d) >= F["start"] and (today is None or str(d) <= today):
                days[str(d)] = round(days.get(str(d), 0.0) + float(p), 2)
        return days

    def _funded_state(self, today):
        """engine/multi_account.sizing_state "funded" on B's closes since funded_start (+ the balance before the bot, the
        payouts): {balance, cum, room, floor, locked, cycle...}. After the first payout the floor sits at start + $100."""
        from . import multi_account as MA
        F = self.spec["funded"]
        if not F.get("start"):
            return None
        st = MA.sizing_state("funded", [(d, t, p) for d, t, p, *_ in self.closes], today, F["start"], self.rules,
                             prior=float(F.get("prior") or 0.0), payouts=dict(F.get("payouts") or {}), n_today=self.entries_today(today))
        if F.get("payouts"):
            lock = float(self.rules["lock"])
            if float(st["floor"]) < lock:
                st["floor"] = lock
                st["room"] = round(float(st["balance"]) + float(st["cum"]) - lock, 2)
                st["locked"] = True
        st["n_today"] = self.entries_today(today)
        if self.spec.get("streak_shrink"):
            st["loss_streak"] = loss_streak(self.closes, F["start"])
        return st

    def _state_raw(self, now=None):
        from . import multi_account as MA
        today = trading_day(now if now is not None else self.clock())
        if self.funded():
            return self._funded_state(today)
        if not self.spec.get("eval_start"):
            return None
        return MA.sizing_state("two_week", [(d, t, p) for d, t, p, *_ in self.closes], today, self.spec["eval_start"], self.rules,
                               prior=float(self.spec.get("prior_pnl") or 0.0), n_today=self.entries_today(today),
                               anchor=self.anchor())

    def eval_state(self, now=None):
        st = self._state_raw(now)
        try:
            b = self._broker()
            if b is not None and st is not None:      # min(ledger room, real room of B's own account)
                st = b.cap_state(st, self.name, self.rules, now=int(now if now is not None else self.clock()))
        except Exception:
            pass
        return st

    def broker_tick(self, now):
        """Day-close auto-anchor of account B's own NinjaTrader account + one "balance differs" push a day. Never raises."""
        try:
            b = self._broker()
            if b is None:
                return
            start = float(self.rules["start"])

            def book_floor():
                st = self._state_raw(now)
                return start + float(st["profit"]) + float(st["cum"]) - float(st["room"])
            a = b.observe(self.name, self.spec.get("eval_start"), self.rules, book_floor=book_floor, now=int(now))
            if a:
                self.log("risk", f"real balance from NinjaTrader at the {a['as_of']} close: ${a['balance']:,.2f}, floor ${a['floor']:,.2f}")
            st = self._state_raw(now)
            if st is None:
                return
            d = b.drift(self.name, start + float(st["profit"]) + float(st["cum"]), self.rules, now=int(now))
            if d:
                from . import broker_balance as BB
                self.log("risk", f"balance differs: NinjaTrader ${d['real']:,.2f}, ledger ${d['ledger']:,.2f}")
                self._send(BB.drift_payload(self.label, self.name, d, now))
        except Exception as e:
            self.log("error", f"real balance check failed: {e.__class__.__name__}: {e}")

    def funded_view(self, now=None) -> dict:
        """The MFFU sim funded tracker of B (engine/funded_life.track): balance, floor, buffer, cycle, best day vs 50%,
        the first-request date, eligibility, the max request (x 80% to you), payouts n of 5, status, one plain line."""
        from . import funded_life as FL
        now = int(now if now is not None else self.clock())
        today = trading_day(now)
        F = self.spec["funded"]
        P = FL.plan_of(self.spec["plan"])
        t = FL.track(self.funded_days(today), dict(F.get("payouts") or {}), P, today=today, start=F.get("start"), name=self.label,
                     prior=float(F.get("prior") or 0.0))
        t["buffer_reached"] = bool(t["balance"] >= t["buffer_balance"] - 1e-9)
        t["record_cmd"] = PAYOUT_CMD
        t["payouts"] = dict(F.get("payouts") or {})
        t["eval_account"] = F.get("eval_account")
        return t

    def eval_view(self, now=None) -> dict:
        """Balance, trailing floor, room, pass target, session, status (open / passed / failed / stuck). Funded stage: the
        same keys on the funded account (target = the payout line, status funded / lost / graduated) + "funded" = the
        payout tracker (funded_view)."""
        if self.funded():
            return self._funded_eval_view(now)
        R = self.rules
        try:
            st = self.eval_state(now)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {e}"}
        start = float(R["start"])
        if st is None:
            return {"start_balance": start, "balance": start, "target": start + float(R["target"]), "status": "no eval_start",
                    "session": None, "room": None}
        prof = float(st["profit"]) + float(st["cum"])
        bal = start + prof
        floor = bal - float(st["room"])
        status = "passed" if prof >= float(R["target"]) else "failed" if st["room"] <= 0 else "stuck" if st["room"] < min_room(self.spec) else "open"
        return {**({"anchor": st["anchor"]} if st.get("anchor") else {}), "start_balance": start, "balance": round(bal, 2), "profit": round(prof, 2), "today": round(float(st["cum"]), 2),
                "floor": round(floor, 2), "room": round(float(st["room"]), 2), "target": start + float(R["target"]),
                "to_target": round(max(0.0, float(R["target"]) - prof), 2), "session": st.get("session"), "status": status,
                "start": self.spec.get("eval_start"), "days_traded": st.get("days_traded"), "dll": float(R["dll"]),
                "max_micros": int(R["max_micros"]), "plan": self.spec["plan_label"], "price": PLANS[self.spec["plan"]]["price"]}

    def _funded_eval_view(self, now=None) -> dict:
        from . import sizing as SZ
        R = self.rules
        F = self.spec["funded"]
        now = int(now if now is not None else self.clock())
        try:
            st = self.eval_state(now)
            t = self.funded_view(now)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {e}", "stage": "funded"}
        start = float(R["start"])
        if st is None:
            return {"stage": "funded", "start_balance": float(F.get("balance") or start), "balance": float(F.get("balance") or start),
                    "status": "no funded_start", "session": None, "room": None, "funded": t}
        prof = float(st["balance"]) + float(st["cum"])        # since the plan start: the balance before the bot + P&L - payouts
        bal = start + prof
        floor = start + float(st["floor"])
        room = float(st["room"])
        # stuck as a funded extra account (engine/multi_account Account.entry_block, the preset's min_room): under $100 of
        # room 1 micro no longer fits most stops and no payout can come back: no new trade, push "buy a new eval"
        status = ("lost" if room <= 0 else "graduated" if t.get("graduated") else "stuck" if room < min_room(self.spec)
                  else "funded")
        today = trading_day(now)
        return {"stage": "funded", "start_balance": float(F.get("balance") or start), "plan_start": start, "balance": round(bal, 2),
                "profit": round(prof, 2), "today": round(float(st["cum"]), 2), "floor": round(floor, 2), "room": round(room, 2),
                "locked": bool(st.get("locked")), "target": t.get("ask_at_balance"), "target_label": "payout line",
                "to_target": t.get("to_ask"), "session": SZ.eval_session(F.get("start"), today), "status": status,
                "start": F.get("start"), "days_traded": len([d for d, v in self.funded_days(today).items() if abs(v) > 1e-9 and d < today]),
                "dll": float(R["dll"]), "max_micros": int(R["max_micros"]), "plan": self.spec["plan_label"],
                "price": PLANS[self.spec["plan"]]["price"], "eval_account": F.get("eval_account"), "funded": t}

    def all_closes(self) -> list:
        """Every routed close on this NinjaTrader account ([day, exit_t, pnl, entry_t]); engine/rapid adds LIT's lane."""
        return list(self.closes)

    def idle_days(self, now) -> int | None:
        """Calendar days (ET) since the last traded day on this account (or since the eval / funded start without one)."""
        start = (self.spec.get("funded") or {}).get("start") if self.funded() else self.spec.get("eval_start")
        days = [str(c[0]) for c in self.all_closes() if c and (not start or str(c[0]) >= str(start))]
        try:                                # a keep-alive trade / a hand trade noted (engine/keepalive.py) restarts the clock too
            from . import keepalive as KA      # (the keep-alive's OWN key of this account: "atlas" for acct_b, never the Rapid's)
            k = KA.last_day(self.bot, KA.key_for(self.bot, self) or ("rapid" if self is getattr(self.bot, "acct_r", None) else "atlas"))
            if k and (not start or k >= str(start)):
                days.append(k)
        except Exception:
            pass
        last = max(days) if days else start
        if not last:
            return None
        try:
            return max(0, (_et(now).date() - _dt.date.fromisoformat(str(last)[:10])).days)
        except ValueError:
            return None

    def _idle_check(self, now, status=None):
        """MFFU inactivity (help center 2026-11-17): no trade for 7 calendar days -> the account can be closed; on a sim-funded
        account ALL its profits are forfeited. One push a day from day IDLE_WARN on (rules audit 2026-11-17)."""
        n = self.idle_days(now)
        sq = None
        if n is not None and n < IDLE_WARN:     # a holiday week: at most 1 CME session left before day 7 (cme_calendar.idle_plan)
            try:
                from . import cme_calendar as CC
                sq = CC.idle_plan(_et(now).date() - _dt.timedelta(days=int(n)), now, IDLE_LIMIT)
                sq = sq if sq["squeeze"] else None
            except Exception:
                sq = None
        if n is None or (n < IDLE_WARN and not sq):
            return
        key = f"acctb:idle:{trading_day(now)}:{self.name}"
        if key in self.notified:
            return
        try:                                    # the bot's keep-alive sends this account's ONE inactivity warning a day itself
            from . import keepalive as KA
            if KA.covered(KA.key_for(self.bot, self) or "atlas", now, bot=self.bot):
                return
        except Exception:
            pass
        if status is None:
            status = self.eval_view(now).get("status")
        if status in STOP_STATUSES:
            return
        self.notified.append(key)
        left = IDLE_LIMIT - n
        title = f"{self.label}: no trade for {n} days"
        body = (f"MFFU can close an account after {IDLE_LIMIT} days without a trade" + (" and a funded one loses ALL its profits"
                if self.funded() else "") + ". Place 1 MNQ by hand on this account (in and out, a few dollars) "
                + (f"within {left} day{'s' if left != 1 else ''}." if left > 0 else "TODAY.")
                + (f" Holiday week: the last CME session before day {IDLE_LIMIT} is {sq['last_session']}." if sq and sq.get("last_session") else ""))
        self.log("risk", f"{title}: {body}")
        self._push_text(title, body, key)

    def _lifecycle(self, now):
        """Pass / fail / stuck: one push each (key per eval start). Funded stage: the payout tracker's pushes (PAYOUT READY,
        consistency, lost, 5 payouts), each once. Both: the 7-day inactivity warning."""
        try:
            self._idle_check(now)                         # cheap until day 5 (the eval view only then)
        except Exception as e:
            self.log("error", f"inactivity check failed: {e.__class__.__name__}: {e}")
        if self.funded():
            return self._funded_lifecycle(now)
        ev = self.eval_view(now)
        stt = ev.get("status")
        if stt not in ("passed", "failed", "stuck"):
            return
        key = f"acctb:{stt}:{self.spec.get('eval_start') or '?'}:{self.name}"
        if key in self.notified:
            return
        self.notified.append(key)
        txt = {"passed": (f"{self.label} EVAL PASSED \U0001F389", f"balance ${ev['balance']:,.0f} (target ${ev['target']:,.0f}): no new "
                                                                   "trade on this eval. MFFU locks it until the funded account is "
                                                                   "issued: send Claude the new account name. Request the funded account in the MFFU dashboard, "
                                                                   "then run the funded switch with its new Name: Start page > Accounts > "
                                                                   f"Passed → funded, or {FUNDED_CMD}. The bot never switches by itself."),
               "failed": (f"{self.label} EVAL FAILED", f"balance ${ev['balance']:,.0f} reached the max-loss floor ${ev['floor']:,.0f}: no "
                                                      "new trade on this account"),
               "stuck": (f"{self.label} stuck: drawdown left ${ev['room']:,.0f}", f"the drawdown left is under ${min_room(self.spec):,.0f}: 1 micro "
                                                                       "no longer fits a stop, the bot stops trading this account; buy a new one")}[stt]
        self.log("risk", f"{txt[0]}: {txt[1]}")
        self._push_text(txt[0], txt[1], key)

    def _funded_lifecycle(self, now):
        from . import funded_life as FL
        try:
            t = self.funded_view(now)
            ev = self._funded_eval_view(now)
        except Exception as e:
            self.log("error", f"funded tracker failed: {e.__class__.__name__}: {e}")
            return
        for p in FL.notices(t, now):
            if p["key"] in self.notified:
                continue
            self.notified.append(p["key"])
            self.log("risk", f"{p['title']}: {t['text']}")
            if str(p["key"]).endswith(":ready") and _autopilot_on():
                continue                # engine/payout_autopilot sends the ONE "Payout ready" (after the close, the MFFU clicks)
            self._send(p)
        if ev.get("status") == "stuck":
            key = f"acctb:fstuck:{(self.spec.get('funded') or {}).get('start') or '?'}:{self.name}"
            if key not in self.notified:
                self.notified.append(key)
                title = f"{self.label} funded account stuck: room ${ev.get('room') or 0:,.0f}"
                body = (f"the room to the max-loss floor is under ${min_room(self.spec):,.0f}: 1 micro no longer fits a stop, the bot "
                        f"stops trading this funded account (balance ${ev.get('balance') or 0:,.0f}, floor ${ev.get('floor') or 0:,.0f}). "
                        f"Paid so far {FL._money(t.get('paid_to_you'))} to you. Buy a new 25K eval for ATLAS.")
                self.log("risk", f"{title}: {body}")
                self._push_text(title, body, key)

    def check_lock(self, now):
        today = trading_day(now)
        pnl = self.day_pnl(today)
        lim = float(self.rules["dll"])
        if pnl <= -lim and not (self.lock and self.lock.get("day") == today):
            self.lock = {"day": today, "reason": f"soft daily loss: today ${pnl:,.0f} (limit ${lim:,.0f})"}
            self.log("risk", f"DAILY LOSS LOCK-OUT: {self.lock['reason']}: no new entry on account B today (LIT is not affected)")
            self._push_text(f"{self.label}: locked out today", self.lock["reason"], f"acctb:lock:{today}")

    # ---- LIT's side (the no-opposite rule)
    def lit_opposite(self, d: int):
        """Why a B entry in direction d would be opposite to LIT (None = not): LIT's open position, entry in progress, armed
        setup (limit / waiting for its 1m CISD), its routed position, an extra account's position."""
        b = self.bot
        st = getattr(b, "state", None) or {}
        side = lambda x: "LONG" if x == 1 else "SHORT"
        pos = st.get("position")
        if pos and int(pos.get("dir") or 0) == -d:
            return f"LIT is in a {side(-d)} trade"
        en = st.get("enter_now")
        if en and int(en.get("dir") or 0) == -d:
            return f"LIT is entering {side(-d)}"
        su = st.get("setups") or {}
        opp = "short" if d == 1 else "long"
        if su.get(opp):
            return f"LIT has a {side(-d)} setup armed" + (" (waiting for its 1m CISD)" if su[opp].get("tapped_t") else " (limit working)")
        ot = getattr(b, "_open_routed", None)
        if ot is not None:
            e = next((r for r in reversed(getattr(b, "ledger", None) or []) if r.get("side") in ("buy", "sell") and r.get("entry_t") == ot), None)
            if e and (1 if e["side"] == "buy" else -1) == -d:
                return f"LIT's account holds a {side(-d)} position"
        ac = getattr(b, "accts", None)
        if ac is not None:
            try:
                h = ac.opposite_open(d, exclude=object())
                if h:
                    return h
            except Exception:
                pass
        else:                                          # no extra accounts: the hand-trade check still runs (fix-trade 2026-11-21)
            try:
                from . import hand_hedge
                h = hand_hedge.opposite_hand(d, b, None, own=self.name, now=self.clock())
                if h:
                    return h
            except Exception:
                pass
        for ar in (getattr(b, "acct_r", None), getattr(b, "acct_r2", None)):   # engine/rapid.py (off = None): ATLAS on a Rapid EOD
            if ar is not None and ar is not self and ar.open_t is not None:
                pv = ar.prov.get(int(ar.open_t)) or {}
                if int(pv.get("dir") or 0) == -d:
                    return f"ATLAS on the Rapid EOD holds a {side(-d)} position"
        fl = getattr(b, "fleet", None)                 # engine/fleet.py (off = None): a Zlarior follower holds the other side
        if fl is not None:
            try:
                h = fl.opposite_open(d, max_rank=0)
                if h:
                    return h
            except Exception:
                return "fleet state unreadable (fails closed)"
        return None

    def lit_entering(self, ent: dict, sym: str, now: int) -> bool:
        """engine/live.py, right before LIT's entry order: B open (or its entry sent / pending) in the OTHER direction ->
        closed at market first (HEDGE). Returns True = LIT may route (B is not opposite, or B's close is CONFIRMED flat);
        False = B's close was refused / is not confirmed yet: LIT must NOT route its opposite entry now (it retries on the
        next poll until its own entry deadline). B stays managed and is never marked flat on an unconfirmed close.
        Pre-launch audit A4 (2026-10-25)."""
        try:
            self.reconcile_unplaced(now)                  # an entry the broker never took is nothing to close
        except Exception as e:
            self.log("error", f"not-placed check failed: {e.__class__.__name__}: {e}")
        if self.open_t is None:
            return True
        et_ = int(self.open_t)
        pv = self.prov.get(et_) or {}
        d = 1 if int(ent.get("dir") or 1) == 1 else -1
        if int(pv.get("dir") or 0) != -d:
            return True
        cl = pv.get("closing")
        if cl and not cl.get("done"):
            self.settle_closing(sym, now)                 # a close already sent: confirmed now? (else re-sent)
        else:
            self.log("risk", f"no hedging: LIT enters {'LONG' if d == 1 else 'SHORT'} at {_et(ent['entry_t']):%H:%M} ET while account B "
                             f"holds the {pv.get('short') or pv.get('key')} {'SHORT' if d == 1 else 'LONG'}: B is closed at market before LIT's order")
            if self.flatten(et_, "HEDGE", sym, now, px=_num(ent.get("entry"))):
                pv["final"] = True
        return self.open_t is None or int(self.open_t) != et_

    # ---- one poll
    def _price_limit(self, now) -> str | None:
        """MFFU's 2% price-limit rule (engine/price_limit.py): this account's FUNDED stage only. None = may trade."""
        try:
            if not self.funded():
                return None
            from . import price_limit as _pl
            return _pl.blocked(int(now))
        except Exception:
            return None

    def tick(self, df5, df1, sym, now):
        """After LIT's routing and state save: manage B's open position, then maybe a new entry. Never raises."""
        if self.problem or self.adapter is None:
            return
        try:                                              # MFFU's 2% price-limit rule, funded only: an open position is closed
            pl = self._price_limit(now) if self.open_t is not None else None
            if pl:
                pv = self.prov.get(int(self.open_t)) or {}
                if not ((pv.get("closing") or {}) and not pv["closing"].get("done")):
                    self.log("risk", f"{pl}: flattening")
                    self.flatten(int(self.open_t), "PRICE LIMIT", sym, now)
        except Exception as e:
            self.log("error", f"price-limit flatten failed: {e.__class__.__name__}: {e}")
        try:
            from . import second as _second
            self.reconcile_unplaced(now)                  # an entry the broker never took is not a position
            scfg = _second.load_cfg()
            keys = [k for k in self.spec["keys"] if isinstance((scfg.get("strategies") or {}).get(k), dict)]
            live_prov = [p.get("key") for p in self.prov.values() if not p.get("final")]
            mk = list(dict.fromkeys(keys + [k for k in live_prov if k]))
            sub = {**scfg, "strategies": {k: {**scfg["strategies"][k], "route": True} for k in mk if k in (scfg.get("strategies") or {})}}
            last5 = int(df5["time"].max())
            self.settle_closing(sym, now)                 # unconfirmed closes first (re-sent / confirmed)
            # the strategies' view is only needed while a B trade is live (fill check, stop moves, cuts, exits); a flat
            # account B only probes at each 5m open (entry below)
            if live_prov:
                vk = (last5, int(df1["time"].max()) if df1 is not None and len(df1) else 0, tuple(mk))
                if vk != self.view_key or self.view is None:
                    sub_v = {**sub, "strategies": {k: v for k, v in sub["strategies"].items() if k in live_prov}}
                    self.view = _second.run(df5, one_min=df1, now=now, cfg=sub_v, lit=[])
                    self.view_key = vk
                self.manage(self.view, sym, now, last5)
            self._lifecycle(now)
            self.broker_tick(now)
            if keys:
                self.entry(df5, df1, {**sub, "strategies": {k: sub["strategies"][k] for k in keys}}, keys, sym, now)
        except Exception as e:
            self.log("error", f"account B failed this poll: {e.__class__.__name__}: {e} (LIT is not affected)")
            try:
                self.bot._note_error(f"account B failed: {e.__class__.__name__}: {e}")
            except Exception:
                pass
        finally:
            self.save()

    def mark(self, sym, now, bar_t=None):
        t = int(bar_t if bar_t is not None else now - now % 60)
        fo = (getattr(self.bot, "_forming", None) or {}).get((sym, 60))
        if fo and int(fo[0]) == t and fo[1]:
            return float(fo[1]), False
        px = (getattr(self.bot, "state", None) or {}).get("price")
        return (float(px) if px else None), True

    def entry(self, df5, df1, sub, keys, sym, now):
        import pandas as pd
        from . import second as _second
        tb = int(df5["time"].max()) + 300
        age = int(now) - tb
        if age < 0 or age > MAX_AGE_S:
            return
        if self.open_t is not None or ("probe", tb) in self.seen or getattr(self.bot, "kill", False):
            return
        self.seen.add(("probe", tb))
        px, est = self.mark(sym, now, bar_t=tb)
        if px is None:
            self._hold(tb, None, "no price for the open")
            return
        cols = ["time", "open", "high", "low", "close", "volume"]
        bar = pd.DataFrame([{"time": tb, "open": px, "high": px, "low": px, "close": px, "volume": 1.0}])
        df5x = pd.concat([df5[cols], bar], ignore_index=True)
        df1x = df1
        if df1 is not None and len(df1) and int(df1["time"].max()) < tb:
            df1x = pd.concat([df1[cols], bar], ignore_index=True)
        pr = _second.run(df5x, one_min=df1x, now=now, cfg=sub, lit=[])
        # every member's signal on this 5m open, in the configured member order (spec "strategies": EMA > MACD > S/R)
        sigs = []
        for k in keys:
            s = (pr.get("strategies") or {}).get(k) or {}
            if s.get("error"):
                self.note(("err", k), "warn", f"{k}: {s['error']} (no entry from it this bar)")
                continue
            t = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == tb and t.get("exit_kind") == "OPEN"
                      and t.get("target") is not None), None)
            if t:
                sigs.append((k, t))
        if not sigs:
            return
        day = trading_day(tb)
        # account-level blocks (the same for every member on this bar)
        why_bar = None
        if self.entries_today(day) >= MAX_PER_DAY:
            why_bar = f"{MAX_PER_DAY} entries on account B today already (max {MAX_PER_DAY} a day)"
        if not why_bar and (self.bot.health or {}).get("entries_blocked"):
            why_bar = "feed stale"
        if not why_bar:
            why_bar = self.startup_block(now)
        if not why_bar and getattr(self.bot, "_no_entries_day", None) == trading_day(now):
            why_bar = "the owner flattened remotely today"
        if not why_bar:
            why_bar = self.life_block(now)                # engine/lifecycle.py: passed / failed / locked / MFFU flat time
        if not why_bar and self.lock and self.lock.get("day") == day:
            why_bar = f"locked out today: {self.lock['reason']}"
        ev = self.eval_view(now) if not why_bar else {}
        if not why_bar and ev.get("status") in STOP_STATUSES:
            why_bar = (f"{'funded account' if self.funded() else 'eval'} {ev['status']} (balance ${ev.get('balance', 0):,.0f}, "
                       f"room ${(ev.get('room') or 0):,.0f})")
        # member priority (pre-launch audit A4 2026-10-25, = tools/atlas research executor): the FIRST member in the
        # configured order whose own signal passes the no-hedging rule, the size and the guards is routed; a blocked member
        # hands the bar to the next one; at most ONE order per bar (one position on B)
        chosen = None
        for k, t in sigs:
            sc = sub["strategies"][k]
            nm = sc.get("short") or k
            d = 1 if int(t["dir"]) == 1 else -1
            head = f"{nm} {'LONG' if d == 1 else 'SHORT'} at the {_et(tb):%H:%M} ET open"
            why = why_bar
            if not why:
                why = self.lit_opposite(d)
                if why:
                    why = f"no hedging: {why}"
            risk = abs(float(t["entry"]) - float(t["stop"]))
            tgt = abs(float(t["target"]) - float(t["entry"]))
            sz = {"qty": 0, "reasons": []}
            if not why:
                try:
                    sz = self.size({"risk_pts": risk, "tgt_pts": tgt}, self.eval_state(now), k)
                except Exception as e:
                    sz = {"qty": 0, "reasons": [f"sizing failed ({e.__class__.__name__}: {e}): not traded"]}
                self.last_size = {"qty": sz["qty"], "key": k, "reasons": [str(x)[:120] for x in sz["reasons"]][-6:], "t": int(now)}
                if sz["qty"] < 1:
                    why = "size 0 (" + "; ".join(sz["reasons"][-3:]) + ")"
            act = {"sym": sym, "side": "buy" if d == 1 else "sell", "qty": int(sz["qty"]), "stop": _tick(float(t["stop"]), d),
                   "target": _tick(float(t["target"]), d, target=True), "entry": float(t["entry"]), "entry_t": tb, "src": k, "strategy": nm}
            if not why:
                why = self.guard(act, tb, now)
            if why:
                self.log("risk", f"{head} NOT routed on account B: {why}")
                self._hold(tb, k, why)
                if why_bar:
                    return                                # an account-level block: no member trades this bar
                continue
            chosen = (k, t, nm, d, head, risk, sz, act)
            break
        if chosen is None:
            return
        k, t, nm, d, head, risk, sz, act = chosen
        why_c = self._c_yield(d, tb, sym, now, act.get("entry"))
        if why_c:
            # BLITZ's close is in flight: B waits for it (probed again at the next poll while this open is fresh, MAX_AGE_S)
            self.seen.discard(("probe", tb))
            self.log("risk", f"{head} NOT routed on account B yet: {why_c} (tried again at the next poll while the open is fresh)")
            return
        q = int(sz["qty"])
        self.open_t = tb
        self.prov[tb] = {"key": k, "short": nm, "qty": q, "model_qty": int(t.get("qty") or 0), "dir": d, "est": est,
                         "entry": float(t["entry"]), "stop": act["stop"], "target": act["target"], "t": int(self.clock()),
                         "risk_pts": risk, "day": day}
        self.seen.add(("entry", k, tb))
        self.log("system", f"{head}: ROUTED MARKET {q} MNQ on {self.name} ({int(self.clock()) - tb} s after the open), stop {act['stop']:,.2f}, "
                           f"target {act['target']:,.2f}; size {'; '.join(sz['reasons'][-3:])}")
        rr = self.route(act)
        if rr.get("ok") is not False:
            self._push_entry(act, q)
        elif self.never_placed(tb, rr):
            self._drop_unplaced(tb, rr, now)
        else:
            self._unconfirmed(tb, rr)

    def size(self, trade: dict, state, key=None) -> dict:
        """Micros for one entry (module qty(); engine/rapid.RapidAtlas sizes its own way)."""
        return qty(self.spec, trade, state, base=getattr(self.bot, "_lit_sizing", None), key=key)

    def _hold(self, tb, key, why):
        """Remember why a signal at this 5m open was not routed (read-only for tools/trade_watch.py; never affects trading)."""
        try:
            with self.mx:
                self.held.setdefault(str(int(tb)), {"key": key, "why": str(why)[:160]})
                if len(self.held) > 200:
                    for k in sorted(self.held, key=int)[:-200]:
                        self.held.pop(k, None)
        except Exception:
            pass

    def _c_yield(self, d, tb, sym, now, px=None):
        """Account C (BLITZ, engine/account_c.py; priority LIT > ATLAS > BLITZ): C holding the other side is closed at market
        FIRST; B's entry goes out only once that close is CONFIRMED flat. None = route (C off / flat / same side)."""
        ac = getattr(self.bot, "acct_c", None)
        if ac is None:
            return self._fleet_yield(d, sym, now)
        try:
            if ac.yield_to(d, "ATLAS", sym, now, px=px, entry_t=tb) is not False:
                return self._fleet_yield(d, sym, now)
        except Exception as e:
            self.log("error", f"account C hedge close failed: {e.__class__.__name__}: {e}")
            if getattr(ac, "open_t", None) is None:
                return self._fleet_yield(d, sym, now)
        return "no hedging: BLITZ's (account C) opposite close is not confirmed yet"

    def _fleet_yield(self, d, sym, now):
        """The fleet (engine/fleet.py, off = None): ATLAS's / BLITZ's followers holding the other side are closed at market
        first. None = route."""
        fl = getattr(self.bot, "fleet", None)
        if fl is None:
            return None
        try:
            if fl.yield_to(d, 1, sym, now, who="ATLAS") is not False:
                return None
        except Exception as e:
            self.log("error", f"fleet hedge close failed: {e.__class__.__name__}: {e}")
        return "no hedging: a fleet follower's opposite close is not confirmed yet"

    # ---- an entry the broker never took (2026-10-27: the 03:30 MACD LONG 3 on the 25K was refused, yet B kept it "open"
    # to its exit: B's other entries blocked all day, its paper P&L booked on B's eval, the phone showed a trade that
    # never existed)
    def entry_result(self, et_):
        """The broker's answer to B's entry order of et_ (the last buy / sell ledger row for it), or None."""
        r = next((r for r in reversed(self.ledger) if r.get("side") in ("buy", "sell") and r.get("entry_t") == int(et_)), None)
        return (r or {}).get("result") if r else None

    def never_placed(self, et_, res=None) -> bool:
        """True only when B's entry et_ provably never became a position (engine/ninjatrader.entry_never_placed: answer NOT
        OK, no leg filled / open / pending, no position shown on B's contracts; anything unclear = False, kept as before)."""
        from .ninjatrader import entry_never_placed
        return entry_never_placed(self.adapter, et_, res if isinstance(res, dict) else self.entry_result(et_), now=self.clock())

    def _drop_unplaced(self, et_, res, now):
        """B's entry et_ never went in: B is flat (no position kept, no exit routed or booked for it, a close booked by an
        older version voided), the entry does not count toward the 2 a day, one push with NinjaTrader's reason."""
        from .accounts import clean_text
        et_ = int(et_)
        pv = self.prov.setdefault(et_, {})
        err = clean_text((res or {}).get("error") or "no OK from NinjaTrader", 200)
        pv["final"] = True
        pv["not_placed"] = {"t": int(now), "error": err}
        if self.open_t is not None and int(self.open_t) == et_:
            self.open_t = None
        with self.mx:
            self.closes = [c for c in self.closes if not (len(c) > 3 and int(c[3]) == et_)]
            for r in self.ledger:
                if r.get("side") == "exit" and r.get("entry_t") == et_:
                    r["void"] = "not placed"
        side = "LONG" if pv.get("dir") == 1 else "SHORT"
        what = f"{pv.get('short') or pv.get('key') or 'ATLAS'} {side} {pv.get('qty') or ''} MNQ at {_et(et_):%H:%M} ET"
        self.log("risk", f"{what} was NOT PLACED on {self.name}: {err}. Nothing is open on account B; it keeps looking for "
                         "its next setup.")
        key = f"acctb:notplaced:{et_}"
        from . import lifecycle
        if key not in self.notified and not lifecycle.is_stood_down(self.bot, self.life_key()):   # LOCKED: its own push
            self.notified.append(key)
            self._push_text(f"{self.label}: order NOT placed",
                            f"{what} did not go in ({err}). Nothing is open on {self.name}, no money at risk. ATLAS keeps "
                            "looking for its next setup.", key)
        self.save()

    def _unconfirmed(self, et_, res):
        """The entry answered NOT OK but NinjaTrader may hold it (a leg working / filled): kept and managed, one push."""
        from .accounts import clean_text
        et_ = int(et_)
        err = clean_text((res or {}).get("error") or "no OK from NinjaTrader", 200)
        self.log("risk", f"entry at {_et(et_):%H:%M} ET NOT CONFIRMED on {self.name}: {err}. It may be open: account B keeps it "
                         "and manages it to its exit.")
        key = f"acctb:unconfirmed:{et_}"
        if key not in self.notified:
            self.notified.append(key)
            self._push_text(f"{self.label}: order NOT confirmed",
                            f"Entry at {_et(et_):%H:%M} ET on {self.name}: {err}. It may be open: check NinjaTrader.", key)

    def void_refused_days(self, now) -> list:
        """Once per process (2026-10-29; the 50K has LiveBot._void_refused_days): B's closes booked on an EARLIER trading day
        whose NinjaTrader Log proves nothing was filled (engine/eval_fix.void_days: every PLACE refused "account does not
        exist", no Execution on any account) are removed from B's eval (their exits marked void "refused day"), one push.
        Covers a close whose entry is no longer in B's provisional book (the per-entry check above cannot see it).
        NinjaTrader accounts only; a day with any fill or without its log file stays booked. Never raises."""
        try:
            if ((self.adapter_cfg() or {}).get("adapter")) != "ninjatrader":
                return []
            from . import eval_fix
            today = trading_day(int(now))
            by = {}
            for c in self.closes:
                if str(c[0]) < today:
                    by[str(c[0])] = by.get(str(c[0]), 0.0) + float(c[2])
            days = eval_fix.void_days(by, (self.bot.cfg or {}).get("nt_folder"))
            if not days:
                return []
            gone = [c for c in self.closes if str(c[0]) in days]
            ets = {int(c[3]) for c in gone if len(c) > 3}
            with self.mx:
                self.closes = [c for c in self.closes if str(c[0]) not in days]
                for r in self.ledger:
                    if r.get("side") == "exit" and r.get("entry_t") in ets and not r.get("void"):
                        r["void"] = "refused day"
            txt = ", ".join(f"{d} {by[d]:+,.2f}" for d in days)
            self.log("risk", f"Voided account B's booked P&L of {txt}: NinjaTrader refused every order that day (account does "
                             "not exist) and filled nothing")
            key = f"acctb:voidday:{days[-1]}"
            if key not in self.notified:
                self.notified.append(key)
                self._push_text(f"{self.label}: fake P&L removed",
                                f"{txt} was booked on {self.name} for days NinjaTrader filled nothing (every order refused). "
                                "Removed: ATLAS's balance and sizing are back to the real account.", key)
            self.save()
            return days
        except Exception as e:
            self.log("error", f"refused-day check failed: {e.__class__.__name__}: {e}")
            return []

    def reconcile_unplaced(self, now):
        """Each poll: a position B holds whose entry provably never went in is dropped (a refused order, a working leg that
        NinjaTrader retired unfilled, or a state saved by an older version that kept such an entry open). Once per process,
        the closes an older version booked for such entries are voided too (their paper P&L never happened on B)."""
        if not getattr(self, "_unplaced_scanned", False):
            self._unplaced_scanned = True
            self.void_refused_days(now)
            booked = {int(c[3]) for c in self.closes if len(c) > 3}
            for et_, pv in sorted(self.prov.items()):
                if int(et_) in booked and not pv.get("not_placed"):
                    r = self.entry_result(et_)
                    if isinstance(r, dict) and r.get("ok") is False and self.never_placed(et_, r):
                        self._drop_unplaced(et_, r, now)
        if self.open_t is None:
            return
        et_ = int(self.open_t)
        r = self.entry_result(et_)
        if isinstance(r, dict) and r.get("ok") is False and self.never_placed(et_, r):
            self._drop_unplaced(et_, r, now)

    def startup_block(self, now):
        """Startup reconcile for account B (bug hunt 2026-10-25): LIT's entries wait for guards.startup_problems, B's did
        not. B routes no entry until, once, its OWN NinjaTrader account reconciles (engine/ninjatrader startup_problems on
        B's adapter: folders, process lock, allowlist, no reset / unreadable state, a connection up, the chart on the order
        contract, every open bracket's reports present, no position on B that no bracket explains). Latched once it passes.
        Paper bot / guards "startup_reconcile" off / an adapter without the check: no gate. A bug fails CLOSED."""
        if getattr(self, "_startup_ok", None) or (self.bot.cfg or {}).get("adapter") != "ninjatrader":
            return None
        try:
            from . import guards as G
            if not G.config(self.bot).get("startup_reconcile"):
                return None
            fn = getattr(self.adapter, "startup_problems", None)
            if not callable(fn):
                return None
            probs = [str(p) for p in (fn() or [])]
        except Exception as e:
            probs = [f"account B startup check failed ({e.__class__.__name__}: {e})"]
        if probs:
            self.note(("startup",), "risk", "STARTUP DISARMED on account B (no new entries yet): " + "; ".join(probs))
            return "STARTUP DISARMED until reconciled: " + "; ".join(probs)
        self._startup_ok = int(now)
        self.log("system", f"STARTUP RECONCILED on {self.name}: NinjaTrader positions / orders and contract check out; entries allowed")
        return None

    def guard(self, act, entry_t, now):
        """Account B's own guards: CME calendar / session, order sanity (the plan's max micros), the bot's clock check,
        Tier-1 news (when on), the owner's pause. None = route."""
        try:
            from . import guards as G
            c = G.config(self.bot)
            out = []
            if c.get("calendar"):
                out += G.calendar(int(entry_t), int(now), session_from=120, flat_mod=955)
            if c.get("order_sanity"):
                out += G.sanity(act, act["qty"], int(self.rules["max_micros"]), c)
            p = G.clock_problem(self.bot, c)
            if p:
                out.append(p)
            if c.get("news"):
                h = G.news_hit(int(now), int(c.get("news_min") or 2))
                if h:
                    out.append(f"Tier-1 news within {int(c.get('news_min') or 2)} min: {h}")
            out += G._owner_blocks(self.bot, c, int(now))
            pl = self._price_limit(now)
            if pl:
                out.append(pl)
            return "GUARD " + "; ".join(out) if out else None
        except Exception as e:
            self.log("error", f"guards failed ({e.__class__.__name__}: {e}): entry NOT routed (account B fails closed)")
            return "guards failed"

    def manage(self, view, sym, now, last5):
        for et_, pv in sorted(self.prov.items()):
            if pv.get("final") or ((pv.get("closing") or {}) and not pv["closing"].get("done")):
                continue                                  # a close in flight is handled by settle_closing
            k = pv.get("key")
            is_open = self.open_t is not None and int(self.open_t) == int(et_)
            if is_open and self._past_flat(pv, now):
                self.flatten(et_, "TIME", sym, now)
                continue
            s = ((view or {}).get("strategies") or {}).get(k)
            if s is None or s.get("error"):
                if is_open:
                    self.note(("err", k), "warn", f"{k}: {(s or {}).get('error') or 'not computed'} - the open position keeps its "
                                                  "broker stop / target (15:55 flat still routed)")
                continue
            tr = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == int(et_)), None)
            if tr is None:
                if is_open and int(last5) >= int(et_):
                    self.log("risk", f"{pv.get('short')} entry {_et(et_):%H:%M} ET is not the strategy's trade once its fill bar closed: "
                                     "flattening account B")
                    if self.flatten(et_, "NO TRADE", sym, now):
                        pv["final"] = True
                elif not is_open and trading_day(now) != pv.get("day"):
                    pv["final"] = True
                continue
            if not pv.get("checked"):
                pv["checked"] = True
                pv["fill"] = float(tr["entry"])
            if tr["exit_kind"] == "OPEN":
                if is_open:
                    pv["stop_now"] = tr.get("stop_now")
                    if tr.get("cut_now"):
                        self.flatten(et_, str(tr["cut_now"]), sym, now)
                    elif getattr(self.adapter, "route_stop_moves", False) and tr.get("stop_now") is not None:
                        self._stop_move(int(et_), pv, float(tr["stop_now"]), sym)
                continue
            kind = str(tr["exit_kind"]).upper()
            reason = "TIME" if kind in ("FLAT", "EOD") else kind
            qm = int(tr.get("qty") or 0)
            if is_open:
                q = int(pv.get("qty") or 0)
                pnl = round(float(tr.get("usd") or 0) * q / qm, 2) if qm else 0.0
                self.seen.add(("exit", k, int(et_)))
                if (self.bot.cfg or {}).get("adapter") == "paper" or reason == "TIME" or getattr(self.adapter, "route_all_exits", False):
                    self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "pnl": pnl, "entry_t": int(et_),
                                "exit_t": tr.get("exit_t"), "src": k, "strategy": pv.get("short")})
                self.open_t = None
                self._close(int(et_), int(tr.get("exit_t") or now), pnl, now)
                self._push_outcome(pv, reason, pnl, tr.get("exit_t"), q, int(et_))
            else:
                fl = pv.get("flat") or {}
                same = (fl.get("reason") in ("CUT", "T15") and kind in ("CUT", "T15")) or (fl.get("reason") == "TIME" and reason == "TIME")
                if same and qm:
                    pnl = round(float(tr.get("usd") or 0) * int(pv.get("qty") or 0) / qm, 2)
                    for r in reversed(self.ledger):
                        if r.get("side") == "exit" and r.get("entry_t") == int(et_) and r.get("pnl_est"):
                            r["pnl"], r["pnl_est"], r["pnl_model"] = pnl, False, True
                            break
                    for c in self.closes:
                        if len(c) > 3 and int(c[3]) == int(et_):
                            c[2] = pnl
            pv["final"] = True

    def _past_flat(self, pv, now):
        """15:55 ET of the trade's day, or 5 min before a CME early close (Thanksgiving 12:55, the day after / Christmas Eve
        13:10 ET: engine/cme_calendar.flat_cut, the time the NinjaTrader adapter flattens at), so B books its own TIME exit."""
        try:
            from .cme_calendar import flat_ts
            return int(now) >= flat_ts(pv["day"], 955)
        except Exception:
            return False

    def broker_stop(self, entry_t):
        stop = None
        for r in self.ledger:
            if r.get("entry_t") != entry_t:
                continue
            if r.get("side") in ("buy", "sell"):
                stop = r.get("stop")
            elif r.get("side") == "modify" and (r.get("result") or {}).get("ok"):
                stop = r.get("stop")
        return stop

    def _stop_move(self, et_, pv, stop_now, sym):
        d = int(pv.get("dir") or 1)
        new, last = _tick(stop_now, d), self.broker_stop(et_)
        if new is None or last is None or abs(float(new) - float(last)) < 1e-9 or (float(new) - float(last)) * d < 0:
            return
        if ("gaveup", et_, new) in self.seen:
            return
        ready = getattr(self.adapter, "has_open_bracket", None)
        if callable(ready) and not ready(et_):
            return
        tries = sum(1 for r in self.ledger if r.get("entry_t") == et_ and r.get("side") == "modify" and r.get("stop") == new)
        if tries >= 3:
            self.seen.add(("gaveup", et_, new))
            self.log("risk", f"broker refused the stop move to {new:.2f} three times: check account B's stop by hand")
            return
        reason = "BE" if (float(new) - float(pv.get("entry") or new)) * d >= 0 else "STOP MOVE"
        self.route({"sym": sym, "side": "modify", "qty": int(pv.get("qty") or 0), "stop": new, "reason": reason, "entry_t": et_,
                    "src": pv.get("key")})

    def flatten(self, et_, reason, sym, now, px=None):
        """Close B's position at market now (15-minute cut, 15:55, HEDGE, NO TRADE, kill, remote flatten); $ booked from the
        market now and corrected to the strategy's own exit when that is known (cut / 15:55)."""
        pv = self.prov.get(int(et_)) or {}
        q = int(pv.get("qty") or 0)
        if px is None:
            px, _ = self.mark(sym, now)
        d = int(pv.get("dir") or 1)
        e = pv.get("fill") or pv.get("entry")
        pnl = round(q * (d * (float(px) - d * TICK - float(e)) * PV - COMM), 2) if px is not None and e is not None else 0.0
        self.seen.add(("exit", pv.get("key"), int(et_)))
        self.log("risk" if reason in ("HEDGE", "NO TRADE", "KILL SWITCH") else "system",
                 f"{pv.get('short')} {_et(int(et_)):%H:%M} ET: {reason} - flatten {q} MNQ at market" + (f" (~{px:,.2f})" if px is not None else ""))
        res = self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "entry_t": int(et_), "exit_t": int(now), "pnl": pnl,
                          "pnl_est": True, "src": pv.get("key"), "strategy": pv.get("short")})
        if not self._close_ok(res, et_):
            # pre-launch audit A4 (2026-10-25): a refused / unconfirmed close never marks B flat - the position stays B's
            # (open_t kept, still managed, no new B entry, LIT's opposite entry held back) and the close is re-sent
            first = not pv.get("closing")
            pv["closing"] = {"reason": reason, "t": int(now), "last": int(now), "px": px, "pnl": pnl, "q": q, "done": False,
                             "tries": int((pv.get("closing") or {}).get("tries") or 0) + 1,
                             "error": str((res or {}).get("error") or "no flat confirmation")[:160]}
            self.log("risk", f"CLOSE NOT CONFIRMED ({reason}): {pv.get('short')} {q} MNQ on {self.name}: {pv['closing']['error']} - "
                             "B is NOT marked flat, the close is re-sent")
            if first:
                self._push_text(f"{self.label}: CLOSE NOT CONFIRMED ({reason})",
                                f"{q} MNQ on {self.name} may still be open ({pv['closing']['error']}). The bot re-sends the close "
                                "and holds LIT's opposite entry; check NinjaTrader.", f"acctb:closing:{int(et_)}")
            self.save()
            return False
        self._finish_close(int(et_), pv, reason, px, pnl, q, now)
        return True

    def _close_ok(self, res, et_) -> bool:
        """The close of B's entry et_ is confirmed: the order was not refused, NinjaTrader did not report it unconfirmed,
        and (when the adapter can tell) no leg of that entry is still open / closing."""
        r = res if isinstance(res, dict) else {}
        if r.get("ok") is False or r.get("flat_confirmed") is False:
            return False
        return self.flat_confirmed(et_) is not False

    def flat_confirmed(self, et_):
        """True / False = the adapter's own book (NinjaTrader legs, confirmed by its position file) says B's entry et_ is
        flat / still open or closing; None = the adapter can not tell (paper): the close order's answer decides."""
        legs = getattr(self.adapter, "legs", None)
        if not isinstance(legs, list):
            return None
        from .ninjatrader import OPEN_STATUSES
        return not any(int(lg.get("entry_t") or 0) == int(et_) and lg.get("status") in OPEN_STATUSES for lg in legs)

    def _finish_close(self, et_, pv, reason, px, pnl, q, now):
        pv["flat"] = {"reason": reason, "t": int(now), "px": px}
        if pv.get("closing"):
            pv["closing"]["done"] = True
        if self.open_t is not None and int(self.open_t) == int(et_):
            self.open_t = None
        self._close(int(et_), int(now), pnl, now)
        self._push_outcome(pv, reason, pnl, int(now), q, int(et_))

    def settle_closing(self, sym, now):
        """Every close of B not confirmed yet: flat now (the NinjaTrader adapter retries its own CLOSEPOSITION and confirms
        from the position file) -> booked, B is free; else the close is re-sent every CLOSE_RETRY_S. Never raises."""
        for et_, pv in sorted(self.prov.items()):
            cl = pv.get("closing")
            if not cl or cl.get("done"):
                continue
            try:
                ok = self.flat_confirmed(et_) is True
                if not ok and int(now) - int(cl.get("last") or 0) >= CLOSE_RETRY_S:
                    cl["last"] = int(now)
                    cl["tries"] = int(cl.get("tries") or 0) + 1
                    res = self.route({"sym": sym, "side": "exit", "qty": int(cl.get("q") or pv.get("qty") or 0), "reason": cl["reason"],
                                      "entry_t": int(et_), "exit_t": int(now), "pnl": cl.get("pnl"), "pnl_est": True,
                                      "src": pv.get("key"), "strategy": pv.get("short"), "retry": cl["tries"]})
                    ok = self._close_ok(res, et_)
                    if not ok:
                        cl["error"] = str((res or {}).get("error") or "no flat confirmation")[:160]
                if ok:
                    self.log("risk", f"close confirmed ({cl['reason']}): {pv.get('short')} on {self.name} is flat after "
                                     f"{int(cl.get('tries') or 1)} tries")
                    self._finish_close(int(et_), pv, cl["reason"], cl.get("px"), float(cl.get("pnl") or 0.0), int(cl.get("q") or 0), now)
                    if cl["reason"] in ("HEDGE", "NO TRADE", "KILL SWITCH"):
                        pv["final"] = True
                    self.save()
            except Exception as e:
                self.log("error", f"close settle failed: {e.__class__.__name__}: {e}")

    def closing_open(self) -> list:
        """B's closes not confirmed yet [(entry_t, pv)] (the PC's critical alert, engine/alerts_plus.pc_conditions)."""
        return [(et_, pv) for et_, pv in sorted(self.prov.items()) if (pv.get("closing") or {}) and not pv["closing"].get("done")]

    def _close(self, entry_t, exit_t, pnl, now):
        with self.mx:
            if any(len(c) > 3 and int(c[3]) == int(entry_t) for c in self.closes):
                return
            self.closes.append([trading_day(exit_t), int(exit_t), float(pnl), int(entry_t)])
            self.closes = self.closes[-1500:]
        self.check_lock(now)
        self.save()

    def kill(self, sym):
        """Flatten B (NinjaTrader: the adapter's kill = FLATTENEVERYTHING on this account)."""
        try:
            if self.adapter is None:
                return {"ok": False, "error": "no adapter"}
            if self.open_t is not None:
                self.flatten(int(self.open_t), "KILL SWITCH", sym, int(self.clock()))
                return (self.ledger[-1].get("result") or {"ok": True}) if self.ledger else {"ok": True}
            if getattr(self.adapter, "kill_flattens_all", False):
                return self.route({"sym": sym, "side": "exit", "reason": "KILL SWITCH", "entry_t": None})
            return {"ok": True, "note": "flat"}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    # ---- pushes (the real bot only: LiveBot._push_send)
    PUSH_SUFFIX = ":acctb"                # the trade notices' key suffix (engine/rapid.RapidAtlas: ":acctr"): one alert per account

    def _wire_push(self):
        """Owner 2026-11-20 (entry + exit alerts on every account, at the fill): this account's NinjaTrader adapter notifies its own
        entry fill and bracket exit under this account's name and key (engine/ninjatrader push_as). Before, account B skipped its own
        notice because the adapter "reports fills", while the adapter (its own state file) never sent one: ATLAS's entries and stop /
        target exits reached the phone only with the 15-minute report. The real bot only. Never raises."""
        try:
            if self.adapter is not None and hasattr(self.adapter, "push_as") and self.real_bot():
                self.adapter.push_as = {"account": self.label, "suffix": self.PUSH_SUFFIX, "url": "#nq"}
        except Exception:
            pass

    def _adapter_pushes(self) -> bool:
        return bool(getattr(self.adapter, "reports_fills", False) and getattr(self.adapter, "push_as", None))

    def _send(self, p):
        try:
            self.bot._push_send(p)
        except Exception:
            pass

    def _push_text(self, title, body, key):
        try:
            from . import push
            self._send(push.text_payload("PC", "risk", title, body, key=key, t=int(self.clock()), url="#/second"))
        except Exception:
            pass

    def _push_entry(self, act, q):
        try:
            from . import push
            if self._adapter_pushes():         # NinjaTrader notifies the real fill (price, micros) under this account's key
                return
            p = push.entry_payload(self.label, "LONG" if act["side"] == "buy" else "SHORT", q, act["entry_t"], src="pc",
                                   entry=act.get("entry"), stop=act.get("stop"), target=act.get("target"), strategy=act.get("strategy"))
            p["body"] = f"{p['body']} ({act.get('strategy')})"
            p["key"] = f"{p['key']}{self.PUSH_SUFFIX}"
            self._send(p)
        except Exception:
            pass

    def _push_outcome(self, pv, reason, usd, exit_t, q, et_):
        try:
            from . import push
            # a bracket exit: NinjaTrader's own notice (push_as) is usually first; this one, the same key, is then a duplicate that
            # engine/push drops; it still goes when the adapter never sent one (no push_as: a non-NinjaTrader adapter, a harness)
            if getattr(self.adapter, "reports_fills", False) and reason not in ("HEDGE", "NO TRADE", "TIME", "CUT", "T15", "KILL SWITCH") \
                    and not self._adapter_pushes():
                return
            p = push.outcome_payload(self.label, "LONG" if pv.get("dir") == 1 else "SHORT", reason, usd, int(et_), exit_t, src="pc",
                                     qty=q, strategy=pv.get("short"))
            p["body"] = f"{p['body']} ({pv.get('short')})"
            p["key"] = f"{p['key']}{self.PUSH_SUFFIX}"
            self._send(p)
        except Exception:
            pass

    # ---- views
    def position(self):
        if self.open_t is None:
            return None
        pv = self.prov.get(int(self.open_t)) or {}
        return {"entry_t": int(self.open_t), "dir": pv.get("dir"), "side": "LONG" if pv.get("dir") == 1 else "SHORT",
                "qty": pv.get("qty"), "entry": pv.get("fill") or pv.get("entry"), "stop": pv.get("stop_now") or pv.get("stop"),
                "target": pv.get("target"), "strategy": pv.get("short"), "key": pv.get("key")}

    def info(self, now=None) -> dict:
        """Heartbeat / live.json / dashboards / Bot Brain: "Account B <name>" with its eval tracker."""
        now = int(now if now is not None else self.clock())
        today = trading_day(now)
        rows = [{**{k: r.get(k) for k in ("t", "side", "qty", "reason", "pnl", "entry_t", "src", "strategy", "stop", "target")},
                 **_answer(r), **_fill_of(r)} for r in self.ledger if r.get("side") in ("buy", "sell", "exit")][-8:]
        out = {"label": self.label, "account": self.name, "plan": self.spec["plan"], "plan_label": self.spec["plan_label"],
               "kind": self.kind(), "sizing": self.spec["sizing"], "keys": list(self.spec["keys"]), "enabled": not self.disabled_reason(),
               "disabled": self.disabled_reason(), "eval": self.eval_view(now), "open": self.position(), "routed": rows,
               "day_pnl": self.day_pnl(today), "entries_today": self.entries_today(today),
               "locked": (self.lock or {}).get("reason") if (self.lock or {}).get("day") == today else None, "size": self.last_size,
               "note": "own account: max 2 trades a day, one position, never opposite to LIT"}
        if self.funded():                 # the funded stage only (the eval's info is exactly as before)
            ev = out["eval"] if isinstance(out["eval"], dict) else {}
            pct = min(0.6, float(self.spec.get("funded_room_pct") or 0.6))      # the 25K preset's 60%, or the owner's lower share
            n_ls = self.spec.get("streak_shrink")
            out.update(stage="funded", sizing="funded", funded=compact_tracker(ev.get("funded")),
                       eval_account=(self.spec.get("funded") or {}).get("eval_account"),
                       note=f"funded: max 2 trades a day, one position, never opposite to LIT; {pct * 100:.0f}% of the room"
                            + (f", 1 micro after {int(n_ls)} losing trades in a row until a winner" if n_ls else "")
                            + ", a winner <= one max payout request; the bot never requests a payout")
            if isinstance(out["eval"], dict):
                out["eval"] = {k: v for k, v in out["eval"].items() if k != "funded"}
        return out

    # ---- persistence
    def blob(self) -> dict:
        with self.mx:
            out = {"v": VERSION, "account": self.name, "plan": self.spec["plan"], "eval_start": self.spec.get("eval_start"),
                   "saved_at": int(self.clock()), "ledger": self.ledger[-400:], "closes": list(self.closes),
                   "prov": {str(k): v for k, v in self.prov.items()}, "open_t": self.open_t,
                   "seen": [list(x) for x in sorted(self.seen, key=_seen_t)[-600:]], "lock": self.lock, "notified": self.notified[-50:],
                   "held": dict(self.held)}
            if self.funded():
                out.update(stage="funded", funded_start=(self.spec.get("funded") or {}).get("start"))
            return out

    def save(self):
        if not self.state_path:
            return
        try:
            b = self.blob()
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(b, fh, default=str)
            from .fsutil import replace as _replace
            _replace(tmp, self.state_path)            # retried: Windows refuses a replace while a reader has it open
        except Exception as e:
            self.log("warn", f"state save failed: {e.__class__.__name__}: {e}")

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                b = json.load(fh)
        except Exception:
            return
        if not isinstance(b, dict) or b.get("account") != self.name:
            return                         # another account's file: start clean (the old one stays on disk)
        self.closes = [list(c) for c in (b.get("closes") or []) if isinstance(c, (list, tuple)) and len(c) >= 3]
        self.ledger = list(b.get("ledger") or [])
        self.prov = {int(k): v for k, v in (b.get("prov") or {}).items() if isinstance(v, dict)}
        self.open_t = b.get("open_t")
        self.seen = {tuple(x) for x in b.get("seen") or []}
        self.notified = list(b.get("notified") or [])
        self.held = dict(b.get("held") or {}) if isinstance(b.get("held"), dict) else {}
        lk = b.get("lock")
        self.lock = lk if lk and lk.get("day") == trading_day(self.clock()) else None
        if self.open_t is not None:
            pv = self.prov.get(int(self.open_t)) or {}
            self.log("system", f"restored: open {pv.get('short') or pv.get('key')} {'LONG' if pv.get('dir') == 1 else 'SHORT'} "
                               f"{pv.get('qty')} MNQ from {_et(int(self.open_t)):%H:%M} ET (managed to its exit)")


def _seen_t(x) -> int:
    """A seen entry's time (its first epoch-seconds field), so a save keeps the NEWEST 600 (a set's order is arbitrary)."""
    try:
        return next((int(v) for v in x[1:] if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1e9), 0)
    except Exception:
        return 0


def _answer(r: dict) -> dict:
    """A ledger row's broker answer for the heartbeat / dashboards: ok (False = refused / not confirmed), NinjaTrader's
    reason (paths removed), void (an exit of an entry that never went in)."""
    res = r.get("result") if isinstance(r.get("result"), dict) else {}
    out = {"ok": res.get("ok")} if res else {}
    if res.get("ok") is False and res.get("error"):
        from .accounts import clean_text
        out["error"] = clean_text(res["error"], 200)
    if r.get("void"):
        out["void"] = r["void"]
    return out


def _fill_of(r: dict) -> dict:
    """An entry row's NinjaTrader fill price ({"fill": px} from the result's legs, else {}): the narrator's FILLED line and
    the phone's entry notice (2026-10-29: the NinjaTrader adapter reports its own fills only for the bot's own account, so
    account B / C entries on NinjaTrader reached the phone as nothing; their info() rows dropped the legs)."""
    if r.get("side") not in ("buy", "sell"):
        return {}
    res = r.get("result") if isinstance(r.get("result"), dict) else {}
    if res.get("ok") is False:
        return {}
    for lg in res.get("legs") or []:
        try:
            if isinstance(lg, dict) and lg.get("fill_px") is not None and int(lg.get("filled") or 0) > 0:
                return {"fill": float(lg["fill_px"])}
        except (TypeError, ValueError):
            continue
    return {}


TRACKER_KEYS = ("name", "plan", "label", "status", "text", "start", "today", "balance", "profit", "floor", "room", "locked", "mll_after_payout", "buffer", "buffer_balance",
                "buffer_reached", "above_buffer", "ask_at_balance", "to_ask", "buffer_frac", "cycle_start", "cycle_profit",
                "cycle_days", "cycle_days_need", "best_day", "best_day_on", "best_day_pct", "cons_limit_pct", "cons_ok",
                "cons_need_profit", "cons_frac", "more_days", "first_trade", "eligible_from", "eligible", "ready", "max_request",
                "request_min", "request_max", "to_you", "split", "payouts_n", "payouts_max", "paid_gross", "paid_to_you",
                "graduated", "lost", "why", "payouts", "eval_account", "record_cmd", "ask_amount", "ask_goal", "stop4")


def _autopilot_on() -> bool:
    """engine/payout_autopilot.active(): it owns the phone's payout-ready alert (LE_PAYOUT_AUTOPILOT=0 = the old pushes)."""
    try:
        from . import payout_autopilot as PA
        return PA.active()
    except Exception:
        return False


def compact_tracker(t: dict | None) -> dict | None:
    """The funded tracker for the heartbeat / dashboards (engine/funded_life.track keys the cards read)."""
    if not isinstance(t, dict):
        return None
    out = {k: t.get(k) for k in TRACKER_KEYS if k in t}
    out["why"] = [str(w)[:160] for w in (t.get("why") or [])][:6]
    return out


def _state_path_for(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_acctb" + (ext or ".json")


def build(bot, ab: dict | None, **kw):
    """LiveBot: account B from the account_b block (None when off)."""
    if not isinstance(ab, dict) or not ab:
        return None
    lit_acct = None
    try:
        if (bot.cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(bot.cfg)
    except Exception:
        lit_acct = None
    spec = normalize(ab, lit_account=lit_acct)
    cls = AccountB
    try:                                   # LIT's lane on this same funded account (engine/lit25.py, OFF by default)
        from . import lit25
        cls = lit25.atlas_class(bot, spec) or AccountB
    except Exception:
        cls = AccountB
    return cls(bot, spec, **kw).start() if spec else None


# ---------------------------------------------------------------------------------------------------------------- switch
def set_account_b(account: str | None, plan: str = "builder25k", start: str | None = None, sizing: str = "need",
                  strategies=None, path: str | None = None, selftest=None, extra: dict | None = None) -> dict:
    """The account_b block = {...} (account set) or null (account None / "off"), written to the LOCAL file
    data/account_b.json only (second_model.json is never edited for it: a dirty tracked file blocks every update).
    Switching on is refused when engine.ninjatrader --selftest fails or the block is invalid; the strategies on B get
    "route": false (engine.second.set_route: never also on LIT's account; second_model.json ships them all false)."""
    from . import second
    path = path or second.CFG_PATH
    with open(path, encoding="utf-8") as fh:
        c = json.loads(fh.read())
    old = raw_cfg(path)
    if account is None or str(account).strip().lower() in ("off", "none", ""):
        new = None
    else:
        new = {"account": str(account).strip(), "plan": plan, "eval_start": start or _dt.date.today().isoformat(),
               "strategies": list(strategies or ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]), "sizing": sizing}
        new.update({k: v for k, v in (extra or {}).items() if k not in new})   # e.g. "armed" (engine/go.py, owner-typed)
        if isinstance(old, dict) and str(old.get("account") or "").strip() == new["account"] \
                and str(old.get("stage") or "").lower() == "funded":
            # the same (funded) account again (arming it, launch prep): its funded stage is kept, never reset to an eval
            for k in FUNDED_KEYS:
                if k in old:
                    new.setdefault(k, old[k])
        spec = normalize(new, second.load_cfg(path))
        if spec["problem"]:
            return {"ok": False, "error": spec["problem"]}
        ok, line = (selftest or second._selftest_ok)()
        if not ok:
            return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): account B NOT switched on"}
    write_local(new, path)
    if raw_cfg(path) != new:
        return {"ok": False, "error": f"{LOCAL_REL} write check failed: account B not changed"}
    routed_off = []
    if new:
        for k in new["strategies"]:
            sc = (c.get("strategies") or {}).get(k)
            if isinstance(sc, dict) and sc.get("route"):
                r = second.set_route(k, False, path=path)
                if r.get("ok"):
                    routed_off.append(k)
    sim = None
    if new:
        from .ninjatrader import is_sim
        sim = is_sim(new["account"])
    return {"ok": True, "from": old, "to": new, "routed_off": routed_off, "sim": sim}


# ---------------------------------------------------------------------------------------------------------------- funded
def _lit_name() -> str | None:
    """LIT's own NinjaTrader account Name on this PC (data/start_bot.json "lit", else data/autostart.json), best effort."""
    for f, k in (("start_bot.json", "lit"), ("autostart.json", "nt_account")):
        try:
            v = str(json.load(open(os.path.join(ROOT, "data", f), encoding="utf-8")).get(k) or "").strip()
            if v:
                return v
        except Exception:
            pass
    return None


def state_file(path: str | None = None) -> str:
    """Account B's state file next to this second_model.json: <its folder>/data/live_state_acctb.json (the PC bot's own,
    engine/live.STATE_PATH -> _state_path_for; a test's temp copy -> its own)."""
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path(path))), "data", "live_state_acctb.json")


def to_funded(account: str, start: str, balance=None, path: str | None = None, selftest=None, allow_path: str | None = None,
              lit_account: str | None = None, state_path: str | None = None, today: str | None = None, allow: bool = True) -> dict:
    """The funded switch (owner-run, never automatic): ATLAS's passed eval -> its NEW funded account. The local block
    (data/account_b.json) becomes stage "funded" on the funded Name from `start` (its balance that day: `balance`, default
    the plan start), DISARMED ("armed" / the eval's anchor and prior dropped; strategies, plan, sizing kept); the passed
    eval's Name is kept as "eval_account" and its state file as live_state_acctb.eval_<Name>.json; the funded Name goes on
    the NinjaTrader allowlist. Re-running it on the same funded Name updates the start / balance and keeps the payouts.
    Refused: no account B, the eval's own Name (MFFU gives a new one), LIT's account, another funded Name, a bad day /
    balance, or engine.ninjatrader --selftest failing. Returns {"ok", "error" | "say", "from", "to", "archived", ...}."""
    from . import second
    path = path or second.CFG_PATH
    old = raw_cfg(path)
    if not isinstance(old, dict) or not str(old.get("account") or "").strip():
        return {"ok": False, "error": "ATLAS has no account yet (account B is off): nothing to switch to funded"}
    name = str(account or "").strip()
    if not name or any(c in name for c in ";,\r\n|"):
        return {"ok": False, "error": "type the funded account's Name exactly as NinjaTrader's Accounts tab shows it"}
    cur = str(old.get("account")).strip()
    stage = str(old.get("stage") or "eval").strip().lower()
    if stage == "funded" and name != cur:
        return {"ok": False, "error": f"ATLAS is already funded on {cur}: a new funded account needs a new eval first"}
    if stage != "funded" and name == cur:
        return {"ok": False, "error": f"{name} is the eval account: MFFU gives the funded account its own new Name (NinjaTrader's "
                                      "Accounts tab after the funded agreement)"}
    lit = lit_account if lit_account is not None else _lit_name()
    if lit and name == str(lit).strip():
        return {"ok": False, "error": f"{name} is Zlarior's (LIT's) own account: ATLAS's funded account has its own Name"}
    try:
        start = _dt.date.fromisoformat(str(start)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "the first funded day as yyyy-mm-dd"}
    from . import multi_account as MA
    plan = str(old.get("plan") or "builder25k").lower().replace(" ", "").replace("_", "")
    R = MA.rules_of({"preset": (PLANS.get(plan) or PLANS["builder25k"])["preset"]})
    bal = float(R["start"]) if balance in (None, "") else _num(balance)
    if bal is None:
        return {"ok": False, "error": f"balance {balance!r} is not a number of $"}
    new = {k: v for k, v in old.items() if k not in ("armed", "confirm", "eval_anchor", "prior_pnl") + FUNDED_KEYS}
    new.update(account=name, stage="funded", funded_start=start, funded_balance=round(float(bal), 2),
               payouts=dict(old.get("payouts") or {}) if stage == "funded" else {},
               eval_account=(old.get("eval_account") if stage == "funded" else cur) or None,
               funded_set=today or _dt.date.today().isoformat())
    spec = normalize(new, second.load_cfg(path), lit)
    if spec["problem"]:
        return {"ok": False, "error": spec["problem"]}
    ok, line = (selftest or second._selftest_ok)()
    if not ok:
        return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): ATLAS NOT switched to funded"}
    archived = None
    if stage != "funded":
        sp = state_path or state_file(path)
        try:
            with open(sp, encoding="utf-8") as fh:
                b = json.load(fh)
            if isinstance(b, dict) and b.get("account") == cur:
                import re
                import shutil
                archived = os.path.splitext(sp)[0] + f".eval_{re.sub(r'[^A-Za-z0-9_-]', '_', cur)}.json"
                shutil.copyfile(sp, archived)
        except FileNotFoundError:
            pass
        except Exception as e:
            return {"ok": False, "error": f"the eval's state file could not be kept ({e.__class__.__name__}: {e}): not switched"}
    write_local(new, path, why=f"Funded on {name} from {start} (passed eval {new.get('eval_account') or cur}).")
    if raw_cfg(path) != new:
        return {"ok": False, "error": f"{LOCAL_REL} write check failed: ATLAS not switched"}
    allowed = None
    if allow:
        from .ninjatrader import allow_account
        allowed = allow_account(name, path=allow_path)
    from .ninjatrader import is_sim
    v = funded_cfg(spec)
    f = v.get("funded") or {}
    rule = (f"risk {float(f.get('pct') or 0) * 100:.0f}% of the room to the floor, at most ${float(f.get('pct_max_usd') or 0):,.0f} a "
            f"trade, a winner <= ${float(f.get('max_win') or 0):,.0f}, the ${float(R['dll']):,.0f} daily loss, {int(R['max_micros'])} micros, "
            "no trade when 1 micro could reach the floor")
    return {"ok": True, "from": old, "to": new, "archived": archived, "allowlist": allowed, "sim": is_sim(name), "rule": rule,
            "say": f"ATLAS -> funded {spec['plan_label'].replace(' funded', '')} {name} from {start} (balance ${float(bal):,.0f}; "
                   f"passed eval {new.get('eval_account') or cur}). NOT armed: a real account trades only after you arm it at "
                   "the start (you type the phrase)."}


def record_payout(spec_s: str, path: str | None = None) -> dict:
    """Record one payout MFFU paid on B's funded account ("yyyy-mm-dd=$", the gross request): the tracker starts a new
    cycle after that day and the floor sits at start + $100. Never requests anything."""
    d, _, v = str(spec_s or "").partition("=")
    try:
        d = _dt.date.fromisoformat(d.strip()).isoformat()
        amt = round(float(v), 2)
        if not amt > 0:
            raise ValueError
    except (TypeError, ValueError):
        return {"ok": False, "error": "give the payout as yyyy-mm-dd=$ (e.g. 2026-12-01=1000)"}
    from . import second
    path = path or second.CFG_PATH
    old = raw_cfg(path)
    if not isinstance(old, dict) or str(old.get("stage") or "").lower() != "funded":
        return {"ok": False, "error": f"ATLAS's account is not funded yet ({FUNDED_CMD})"}
    new = {**old, "payouts": {**dict(old.get("payouts") or {}), d: amt}}
    spec = normalize(new, second.load_cfg(path))
    if spec["problem"]:
        return {"ok": False, "error": spec["problem"]}
    write_local(new, path, why=f"Payout {d} ${amt:,.2f} recorded.")
    from . import funded_life as FL
    P = FL.plan_of(spec["plan"])
    note = None if P["pay_min"] <= amt <= P["pay_max"] else \
        f"note: MFFU's request on this plan is ${P['pay_min']:,.0f}-${P['pay_max']:,.0f}; recorded as given"
    return {"ok": True, "payouts": spec["funded"]["payouts"], "note": note,
            "say": f"Payout {d} ${amt:,.2f} recorded on {spec['account']} ({len(spec['funded']['payouts'])} of {P['max_payouts']})."}


def funded_status(path: str | None = None, state_path: str | None = None, today: str | None = None) -> dict:
    """B's funded tracker from the local block and B's state file (its closes), without a running bot."""
    from . import funded_life as FL
    ab = raw_cfg(path)
    spec = normalize(ab) if ab else None
    if not is_funded(spec):
        return {"ok": False, "error": f"ATLAS's account is not funded yet ({FUNDED_CMD})"}
    F = spec["funded"]
    days = {}
    try:
        with open(state_path or state_file(path), encoding="utf-8") as fh:
            b = json.load(fh)
        if isinstance(b, dict) and b.get("account") == spec["account"]:
            for c in b.get("closes") or []:
                if isinstance(c, (list, tuple)) and len(c) >= 3 and str(c[0]) >= F["start"]:
                    days[str(c[0])] = round(days.get(str(c[0]), 0.0) + float(c[2]), 2)
    except Exception:
        pass
    t = FL.track(days, F["payouts"], FL.plan_of(spec["plan"]), today=today, start=F["start"], name=spec["label"], prior=F["prior"])
    t["record_cmd"] = PAYOUT_CMD
    return {"ok": True, "account": spec["account"], "eval_account": F.get("eval_account"), "tracker": compact_tracker(t)}


# ---------------------------------------------------------------------------------------------------------------- migration
def _set_tracked_block(path: str, block) -> bool:
    """second_model.json's one "account_b" line = block (the rest of the file untouched). True when written and checked."""
    import re
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    c = json.loads(raw)
    val = json.dumps(block, ensure_ascii=False)
    rx = re.compile(r'^ "account_b"\s*:.*?,(\r?\n)(?= "strategies")', re.M | re.S)
    if not rx.search(raw):
        return False
    out = rx.sub(lambda m: f' "account_b": {val},{m.group(1)}', raw, count=1)
    chk = json.loads(out)
    if chk.get("account_b") != block or json.dumps(chk.get("strategies"), sort_keys=True) != json.dumps(c.get("strategies"), sort_keys=True):
        return False
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)
    return True


def _git_in(root: str):
    from . import generated_files
    return lambda *a: generated_files._git(*a, cwd=root, timeout=60)


def migrate_local(root: str | None = None, git=None, log=None) -> dict:
    """Move an account_b block an older version wrote INTO the tracked second_model.json to data/account_b.json, then put
    the tracked file back to HEAD, so `git pull --ff-only` and the auto-update's dirty check pass again. Run by server.py
    at start, START BOT / the Start page, the auto-update and the phone's "update" before their dirty check, and
    UPDATE.bat (engine/autoupdate --pull). The block is never lost: the local file is written and read back before the
    tracked file is touched; a local file that is already there wins (it is what the bot reads). Other hand edits of
    second_model.json are kept (only its account_b goes back to HEAD's value).
    git(*args) -> (code, output) runs in `root` (tests pass a fake). Returns {"status": clean | migrated | no_git | error,
    "say": one plain line, ...}. Never raises."""
    log = log or (lambda t: None)
    root = root or os.path.dirname(os.path.abspath(cfg_path()))
    tracked = os.path.join(root, "second_model.json")
    try:
        git = git or _git_in(root)
        with open(tracked, encoding="utf-8") as fh:
            c = json.loads(fh.read())
        if not isinstance(c, dict):
            raise ValueError("not an object")
    except Exception as e:
        return {"status": "error", "say": f"second_model.json not read ({e.__class__.__name__}): nothing changed"}
    try:
        tb = c.get("account_b") if isinstance(c.get("account_b"), dict) and c.get("account_b") else None
        code, head = git("show", "HEAD:second_model.json")
        try:
            hc = json.loads(head) if code == 0 else None
        except Exception:
            hc = None
        if not isinstance(hc, dict):
            # no git here (or no HEAD copy): only make sure the block is in the local file (every read is the same either way)
            if tb is not None and not read_local(tracked)[0]:
                write_local(tb, tracked, why="Copied from second_model.json (git not available: that file is left as it is).")
                return {"status": "no_git", "copied": True, "block": tb,
                        "say": "ATLAS's account copied to data/account_b.json (git not found: second_model.json left as it is)"}
            return {"status": "no_git", "copied": False, "say": "git not available: nothing to do"}
        hb = hc.get("account_b") if isinstance(hc.get("account_b"), dict) and hc.get("account_b") else None
        if tb == hb:
            return {"status": "clean", "say": "second_model.json holds no local ATLAS block"}
        found, _lb = read_local(tracked)
        if not found:
            write_local(tb, tracked, why="Moved from second_model.json by engine/account_b.migrate_local.")
            f2, lb2 = read_local(tracked)
            if not f2 or lb2 != tb:
                return {"status": "error", "say": "data/account_b.json could not be written: second_model.json left as it is"}
            kept = "moved"
        else:
            kept = "local file kept"                 # the bot already reads the local file: the tracked copy is stale
        rest = {k: v for k, v in c.items() if k != "account_b"}
        hrest = {k: v for k, v in hc.items() if k != "account_b"}
        if rest == hrest:
            code, out = git("checkout", "HEAD", "--", "second_model.json")
            how = "back to HEAD"
            if code != 0:
                return {"status": "error", "kept": kept, "say": f"second_model.json not restored (git: {str(out).strip()[-120:]})"}
        else:
            if not _set_tracked_block(tracked, hb):
                return {"status": "error", "kept": kept, "say": "second_model.json's account_b line not restored (other local edits)"}
            how = "account_b back to HEAD's value (other local edits kept)"
        if tracked_cfg(tracked) != hb:
            return {"status": "error", "kept": kept, "say": "second_model.json still holds a local ATLAS block"}
        blk = raw_cfg(tracked)
        say = (f"ATLAS's account moved to data/account_b.json ({(blk or {}).get('account') or 'off'}"
               f"{', armed' if (blk or {}).get('armed') is True else ''}); second_model.json {how}")
        log(say)
        return {"status": "migrated", "kept": kept, "restored": how, "block": blk, "say": say}
    except Exception as e:
        return {"status": "error", "say": f"account B migration failed ({e.__class__.__name__}: {e})"[:200]}


MIN_ROOM_CMD = "python -X utf8 -m engine.account_b --min-room 0"


def set_min_room(value, path: str | None = None) -> dict:
    """The owner's switch for ATLAS's stuck line (Decide card atlas-funded-keep-trading, owner YES 2026-11-19): the account_b
    block's "min_room" in the PC-local data/account_b.json (never second_model.json). 0 = the funded account keeps trading 1
    micro while that micro's full stop-out still fits the room, instead of stopping for good under $100 (research/writeups/
    atlas-more-money-2026-11-19.md, A1). "default" removes the key (back to MIN_ROOM = $100). Every other key of the block
    (armed, account, stage, payouts ...) is kept exactly. The eval stage keeps its own eval_min_room line. Never arms, never
    routes. Returns {"ok", "say" | "error", "from", "to", "file"}."""
    old = raw_cfg(path)
    if not isinstance(old, dict) or not str(old.get("account") or "").strip():
        return {"ok": False, "error": "ATLAS has no account on this PC yet (account B is off): nothing to change"}
    raw = str(value).strip().lower() if value is not None else ""
    was = old.get("min_room")
    new = dict(old)
    if raw in ("default", "off", "none"):
        new.pop("min_room", None)
        to = None
    else:
        v = _num(raw.lstrip("$").replace(",", ""))
        if v is None or not 0.0 <= float(v) <= 1000.0:
            return {"ok": False, "error": f"--min-room {value!r}: a number of $ from 0 to 1000 (or default)"}
        to = float(v)
        new["min_room"] = to
    f = write_local(new, path, why=f"min_room {was if was is not None else 'default $100'} -> "
                                   f"{to if to is not None else 'default $100'} (owner, engine.account_b --min-room)")
    spec_stage = str(new.get("stage") or "eval").strip().lower()
    line = (f"${to:,.0f}" if to is not None else f"the default ${MIN_ROOM:,.0f}")
    say = (f"ATLAS {new.get('account')}: stops for good only when its room is under {line}"
           + (" (it keeps trading 1 micro while that micro's full stop-out fits the room)" if to == 0 else "")
           + (". Funded stage: in force once ATLAS is flat (or after a bot restart)." if spec_stage == "funded" else
              f". Note: the account is in its {spec_stage} stage; the eval's own stuck line (eval_min_room) still applies "
              "until it is funded."))
    return {"ok": True, "say": say, "from": was, "to": to, "file": f, "stage": spec_stage}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.account_b", description="ATLAS's account (account B) on this PC")
    ap.add_argument("--min-room", dest="min_room", default=None,
                    help="ATLAS's stuck line in $ (0 = keep trading 1 micro while it fits; 'default' = $100). Writes "
                         "data/account_b.json only (owner YES 2026-11-19, Decide atlas-funded-keep-trading)")
    ap.add_argument("--migrate", action="store_true", help="move a local account_b block out of second_model.json "
                                                            "into data/account_b.json")
    ap.add_argument("--to-funded", action="store_true", help="after ATLAS's eval passed: trade its NEW funded account "
                                                              "(--account, --start) under the funded rules, disarmed")
    ap.add_argument("--account", help="--to-funded: the funded account's Name exactly as NinjaTrader shows it")
    ap.add_argument("--start", help="--to-funded: the first funded session (yyyy-mm-dd)")
    ap.add_argument("--balance", type=float, default=None, help="--to-funded: its balance that day as MFFU shows it (default "
                                                                 "the plan start, $25,000)")
    ap.add_argument("--payout", help="record one payout MFFU paid on the funded account: yyyy-mm-dd=$")
    ap.add_argument("--funded-status", action="store_true", help="the funded payout tracker now")
    a = ap.parse_args(argv)
    if a.min_room is not None:
        r = set_min_room(a.min_room)
        print(f"  [{'OK' if r['ok'] else 'FIX'}]  {r.get('say') or r.get('error')}")
        return 0 if r["ok"] else 1
    if a.migrate:
        r = migrate_local()
        print(f"  [{'OK' if r['status'] in ('clean', 'migrated', 'no_git') else '..'}]  {r['say']}")
        return 0
    if a.to_funded:
        if not a.account or not a.start:
            print(f"--to-funded needs --account \"<funded Name>\" and --start yyyy-mm-dd ({FUNDED_CMD})")
            return 1
        r = to_funded(a.account, a.start, a.balance)
        if not r["ok"]:
            print(f"  [FIX] {r['error']}")
            return 1
        print(f"  [OK]  {r['say']}")
        print(f"        Funded sizing: {r['rule']}.")
        print("        Payout tracker: python -X utf8 -m engine.account_b --funded-status (push \"PAYOUT READY: request $X\" when "
              "every MFFU rule is met; the bot never requests a payout).")
        print(f"        Record each payout: {PAYOUT_CMD.format(day='<day>', amount='<$>')}")
        if r.get("archived"):
            print(f"        The eval's history is kept in {r['archived']}")
        print("        Restart the bot (or it switches by itself once ATLAS is flat).")
        return 0
    if a.payout:
        r = record_payout(a.payout)
        print(f"  [{'OK' if r['ok'] else 'FIX'}]  {r.get('say') or r.get('error')}" + (f" ({r['note']})" if r.get("note") else ""))
        return 0 if r["ok"] else 1
    if a.funded_status:
        r = funded_status()
        if not r["ok"]:
            print(f"  [..]  {r['error']}")
            return 0
        print(r["tracker"]["text"])
        print(json.dumps(r, indent=1))
        return 0
    found, _ = read_local()
    print(json.dumps({"source": LOCAL_REL if found else "second_model.json", "account_b": raw_cfg()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
