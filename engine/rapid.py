"""The MFFU Rapid EOD 50K (owner 2026-11-17: "I'll stick with 1 rapid"): LIT (Zlarior) + ATLAS on ONE account. OFF by default.

ON / OFF: data/rapid.json (local, gitignored, never the phrase). Missing, or no "account" in it = OFF: the bot is exactly
today's. The owner sets ONE value, the NinjaTrader account Name (docs/RAPID_EOD_SETUP.md):
    python -X utf8 -m engine.rapid --account "<NinjaTrader account Name>"      (eval from today's session, DISARMED)
Arming: only START BOT after the owner typed I ACCEPT LIVE RISK (engine/go.step_arm -> arm()); a real (non-Sim) account
also needs NINJATRADER_LIVE=1 and the allowlist (each adapter's own gate, engine/ninjatrader._live_gate). Nothing here arms.

What runs on that account (research/writeups/stack-one-account-2026-11-16.md, rapid-levers-2026-11-16.md):
  LIT lane    an extra account of engine/multi_account (preset mffu_rapid_eod_50k, id "rapid", lane "rapid"): LIT's live
              two_week eval size on the Rapid's numbers, then the 30% best-day cap (a winner keeps the day <= 0.3 x $3,000
              x 0.95 = $855 incl. ATLAS's closed $ today), the soft $1,000 day; funded: 60% of the room, <= $1,500, a winner
              <= $2,000; Tier-1 news flat -2/+2 min (funded only).
  ATLAS lane  RapidAtlas below (engine/account_b.AccountB on the same NinjaTrader account, its own order tag "acctr_"):
              $ risk = min($500, 30% of the room, the soft day left), micros = $ / one full stop-out (stop + 1 tick, $1.90),
              then the same 30% best-day cap (eval) and the funded news ban; one position, max 2 a day.
  One account, one book: both lanes size, lock out and pass / fail on the SUM of their closes (balance, EOD trailing floor,
  today's $). Never two positions at once on the account: ATLAS is blocked while LIT holds a trade, is entering one, or has
  a setup armed the other way (engine/account_b no-opposite rule + "LIT holds / enters any side"); LIT entering while
  ATLAS holds closes ATLAS at market first and routes only once that close is CONFIRMED flat (LIT has priority).
  Eval pass: profit >= $3,000, >= 4 traded days, best day <= 30% of the profit. Funded payouts (MFFU help center
  2026-11-16): daily, above the $2,100 buffer, $500 minimum, 90% to you; the bot keeps a $1,000 cushion above the buffer
  (rapid-levers lever 3b): it tells you to withdraw only what is above start + $3,100. The bot never requests a payout.

    python -X utf8 -m engine.rapid --status
    python -X utf8 -m engine.rapid --account "<Name>" [--start yyyy-mm-dd]
    python -X utf8 -m engine.rapid --to-funded --account "<funded Name>" --start <first funded day>
    python -X utf8 -m engine.rapid --payout 2026-12-20=600        (record one after MFFU paid it)
    python -X utf8 -m engine.rapid --off

The Rapid EOD 25K (owner 2026-11-18; still ONE Rapid at a time, data/rapid.json "plan": "mffu_rapid_eod_25k"; added with
python -X utf8 -m engine.accounts add --plan rapideod25 --name "<Name>" or engine.rapid --size 25k): the same lanes and
rules at the 25K's numbers (research/writeups/rapid-25k-vs-50k-2026-11-17.md, tools/money/rapid25.py "keep $500"): LIT's
live two_week on $1,500 / $1,000 EOD floor / 20 micros, soft day $500, best day 30% x $1,500 x 0.95 = $427; funded 60% of
the room <= $750, a winner <= $1,000; ATLAS min($250, 30% of the room); payouts above the $1,100 buffer + $500 kept in.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

from . import account_b as AB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_REL = os.path.join("data", "rapid.json")
PATH = None                     # tests: another file
PRESET = "mffu_rapid_eod_50k"
PLAN = "rapideod50k"
LANE_ID = "rapid"
ATLAS_USD, ATLAS_F = 500.0, 0.3     # stack_one_account Z(atlas=500): $500, 30% of the room
SLIP, PV, COMM = 0.25, 2.0, 1.90    # one full stop-out of 1 micro = (stop + 1 tick) x $2 + $1.90 (research stack_q)
BEST_DAY, MIN_DAYS, MARGIN = 0.3, 4, 0.95
BUFFER, PAY_MIN, CUSHION, SPLIT = 2100.0, 500.0, 1000.0, 0.9
STRATEGIES = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]
# The plan of the ONE Rapid (data/rapid.json "plan"; missing = the 50K). The 25K (owner 2026-11-18, buying it tonight):
# research/writeups/rapid-25k-vs-50k-2026-11-17.md / tools/money/rapid25.py "25K, keep $500" = the 50K's rules at the 25K's
# numbers: ATLAS $250 at 30% of the room, keep $500 above the $1,100 buffer, MFFU wants >= $250 net since the last payout.
PLANS = {
    "mffu_rapid_eod_50k": {"plan": "rapideod50k", "label": "Rapid EOD 50K", "start": 50000.0, "target": 3000.0,
                           "atlas_usd": ATLAS_USD, "buffer": BUFFER, "cushion": CUSHION, "since": 500.0, "eval_min_room": 200.0},
    "mffu_rapid_eod_25k": {"plan": "rapideod25k", "label": "Rapid EOD 25K", "start": 25000.0, "target": 1500.0,
                           "atlas_usd": 250.0, "buffer": 1100.0, "cushion": 500.0, "since": 250.0, "eval_min_room": 100.0},
}


def plan_info(x=None) -> dict:
    """The plan numbers of a block / spec / preset name ("plan" or "preset"); anything unknown = the 50K (as before)."""
    k = x.get("preset") or x.get("plan") if isinstance(x, dict) else x
    k = str(k or "")
    if k not in PLANS:
        k = next((pk for pk, v in PLANS.items() if v["plan"] == k), PRESET)
    return {**PLANS[k], "preset": k}


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def path(p: str | None = None) -> str:
    return p or PATH or os.path.join(ROOT, LOCAL_REL)


def _today() -> str:
    from .multi_account import trading_day
    import time
    return trading_day(time.time())


# ---------------------------------------------------------------------------------------------------------------- the file
def load(p: str | None = None) -> dict:
    try:
        with open(path(p), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def read(p: str | None = None) -> dict | None:
    """The block when ON (an account Name is set and "enabled" is not false), else None."""
    d = load(p)
    nm = str(d.get("account") or "").strip()
    if not nm or d.get("enabled") is False:
        return None
    return {**d, "account": nm}


def save(blk: dict, p: str | None = None) -> str:
    from .tradovate import LIVE_PHRASE
    clean = {k: v for k, v in blk.items() if k != "confirm" and not (isinstance(v, str) and v.strip() == LIVE_PHRASE)}
    fp = path(p)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried on a Windows / OneDrive lock
    _fs_replace(tmp, fp)
    return fp


def name_problem(name: str, others: dict | None = None) -> str | None:
    nm = str(name or "").strip()
    if not nm or any(c in nm for c in ";\r\n|") or len(nm) > 60:
        return "the account Name is missing or has ; | or a line break"
    for who, other in (others if others is not None else _other_names()).items():
        if other and nm == str(other).strip():
            return f"{nm} is already {who}'s account: the Rapid EOD needs its own"
    return None


def _other_names() -> dict:
    out = {}
    try:
        from . import go
        c = go._read(go.CFG) or {}
        out["Zlarior (50K)"], out["ATLAS (25K)"] = c.get("lit"), c.get("atlas")
    except Exception:
        pass
    try:
        out.setdefault("ATLAS (25K)", None)
        out["ATLAS (25K)"] = out["ATLAS (25K)"] or (AB.raw_cfg() or {}).get("account")
    except Exception:
        pass
    return out


def set_account(name: str, start: str | None = None, p: str | None = None, others: dict | None = None, allow=None,
                preset: str | None = None) -> dict:
    """The owner's one line: the Rapid's NinjaTrader Name, the eval from `start` (default today's session), DISARMED. The
    same Name again keeps everything (no reset); a new Name starts a new eval. A real Name goes on the allowlist (no arming).
    preset = "mffu_rapid_eod_25k" for the 25K (None = the same Name's plan, else the 50K)."""
    nm = str(name or "").strip()
    why = name_problem(nm, others)
    if why:
        return {"ok": False, "error": why}
    if start:
        try:
            _dt.date.fromisoformat(start)
        except ValueError:
            return {"ok": False, "error": f"--start {start!r} is not yyyy-mm-dd"}
    if preset is not None and preset not in PLANS:
        return {"ok": False, "error": f"unknown Rapid plan {preset!r}"}
    old = load(p)
    same = str(old.get("account") or "").strip() == nm and old.get("enabled") is not False
    want = preset or (str(old.get("plan") or PRESET) if same else PRESET)
    if same and str(old.get("plan") or PRESET) == want:
        blk = dict(old)
        if start:
            blk["eval_start"] = start
    else:
        blk = {"v": 1, "account": nm, "plan": want, "stage": "eval", "eval_start": start or _today(), "armed": False,
               "payouts": {}, "set": _today()}
        if old.get("account"):
            blk["previous"] = old.get("account")
    blk.pop("enabled", None)
    fp = save(blk, p)
    note = None
    from .ninjatrader import is_sim
    if not is_sim(nm):
        try:
            (allow or __import__("engine.ninjatrader", fromlist=["allow_account"]).allow_account)(nm)
            note = f"{nm} is on the account allowlist (still disarmed)"
        except Exception as e:
            note = f"allowlist NOT updated ({e}): python -m engine.ninjatrader --allow-account \"{nm}\""
    return {"ok": True, "path": fp, "block": blk, "note": note}


def arm(phrase: str, p: str | None = None) -> dict:
    """START BOT after the owner typed the live phrase (engine/go.step_arm): "armed": true. Nothing else ever arms it."""
    from .tradovate import LIVE_PHRASE
    if phrase != LIVE_PHRASE:
        return {"ok": False, "error": "the live phrase was not typed: nothing armed"}
    blk = read(p)
    if blk is None:
        return {"ok": True, "off": True}
    if blk.get("armed") is True:
        return {"ok": True, "already": True, "account": blk["account"]}
    blk["armed"] = True
    save(blk, p)
    return {"ok": True, "account": blk["account"]}


def off(p: str | None = None) -> dict:
    blk = load(p)
    if not blk:
        return {"ok": True, "already": True}
    blk["enabled"], blk["armed"] = False, False
    save(blk, p)
    return {"ok": True}


def to_funded(name: str, start: str, p: str | None = None, others: dict | None = None, allow=None) -> dict:
    blk = read(p)
    if blk is None:
        return {"ok": False, "error": "the Rapid EOD is off (no account set)"}
    try:
        _dt.date.fromisoformat(start)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"--start {start!r} is not yyyy-mm-dd"}
    nm = str(name or "").strip()
    why = name_problem(nm, others)
    if why:
        return {"ok": False, "error": why}
    blk.update({"eval_account": blk["account"], "account": nm, "stage": "funded", "funded_start": start, "payouts": {},
                "armed": False, "funded_set": _today()})
    save(blk, p)
    r = set_account(nm, p=p, others=others, allow=allow)
    return {"ok": True, "block": read(p), "note": r.get("note")}


def record_payout(spec_s: str, p: str | None = None) -> dict:
    blk = read(p)
    try:
        day, amt = str(spec_s).split("=", 1)
        _dt.date.fromisoformat(day.strip())
        amt = float(amt)
    except Exception:
        return {"ok": False, "error": "write it as yyyy-mm-dd=amount"}
    if blk is None or blk.get("stage") != "funded":
        return {"ok": False, "error": "the Rapid EOD is not in the funded stage"}
    blk.setdefault("payouts", {})[day.strip()] = round(amt, 2)
    save(blk, p)
    return {"ok": True, "payouts": blk["payouts"]}


# ---------------------------------------------------------------------------------------------------------------- the lanes
def lane_spec(blk: dict, cfg: dict | None = None) -> dict:
    """LIT's lane: one engine/multi_account extra account entry (data/accounts.json format)."""
    cfg = cfg or {}
    funded = blk.get("stage") == "funded"
    armed = blk.get("armed") is True
    P = plan_info(blk)
    s = {"id": LANE_ID, "name": P["label"], "preset": P["preset"], "mode": "funded" if funded else "two_week",
         "adapter": "ninjatrader" if cfg.get("adapter") == "ninjatrader" else "paper", "nt_account": blk["account"],
         "eval_start": blk.get("eval_start") or "", "enabled": True, "armed": armed, "lane": "rapid"}
    if armed and cfg.get("confirm"):
        s["confirm"] = cfg["confirm"]           # the phrase typed at this start, in memory only
    if funded:
        s["funded"] = {"start": blk.get("funded_start") or "", "payouts": dict(blk.get("payouts") or {})}
    if lit_bank_on(blk):
        s["lit_bank"] = True                    # the 25K's "bank at the room" option (OFF unless the owner said yes)
    return s


def atlas_block(blk: dict) -> dict:
    """ATLAS's lane: an engine/account_b block on the same account (sized by RapidAtlas.size)."""
    P = plan_info(blk)
    b = {"account": blk["account"], "plan": P["plan"], "eval_start": blk.get("eval_start") or "", "strategies": list(STRATEGIES),
         "sizing": "safe", "armed": blk.get("armed") is True, "eval_min_room": P["eval_min_room"]}
    if blk.get("stage") == "funded":
        b.update({"stage": "funded", "funded_start": blk.get("funded_start") or "", "payouts": dict(blk.get("payouts") or {})})
    return b


def stack_qty(risk: float, room, cum: float, maxq: int, dll: float = 1000.0, cap: float = ATLAS_USD) -> tuple:
    """research stack_q: $ = min($500 (the 25K: $250), 30% x room, the soft day left), micros = $ / one full stop-out of 1 micro."""
    loss1 = (float(risk) + SLIP) * PV + COMM
    usd = min(float(cap), ATLAS_F * max(0.0, float(room or 0.0)), float(dll) + min(0.0, float(cum or 0.0)))
    return max(0, min(int(maxq), int(usd // loss1))), usd, loss1


def best_day_cap(q: int, tgt_pts, risk: float, target: float, day_pnl: float) -> tuple:
    """A winner keeps today under 30% x target x 0.95 (engine/firms.BEST_DAY_MARGIN, the lane's own guard)."""
    win1 = (float(tgt_pts or 0.0) or 2.0 * float(risk)) * PV - COMM
    if q <= 0 or win1 <= 0:
        return q, None
    cap_usd = BEST_DAY * float(target) * MARGIN - max(0.0, float(day_pnl))
    return max(0, min(q, int(cap_usd // win1))), cap_usd


# The Rapid 25K's LIT "bank at the room" option (research/writeups/rapid25-lit-lane-2026-11-18.md, tools/money/rapid25_lit_lane.py
# lane b). OFF by default: data/rapid.json "lit_bank": true on a 25K turns it on (python -X utf8 -m engine.rapid --lit-bank on).
# Eval only: when the 30% best-day guard leaves < 1 micro, LIT's lane takes 1 micro with its exit limit at the day's remaining
# room instead of the target (taken only if that is >= 1R and nearer than the target); funded and the 50K are unchanged.
BANK_MIN_R, BANK_TICK = 1.0, 0.25


def lit_bank_on(blk: dict | None) -> bool:
    return bool(blk) and blk.get("lit_bank") is True and plan_info(blk)["preset"] == "mffu_rapid_eod_25k"


def lit_bank(entry, d: int, risk_pts, tgt_pts, cap_usd, comm: float = COMM, min_r: float = BANK_MIN_R) -> dict | None:
    """1 micro banked at the day's room: {"qty": 1, "pts", "px", "usd"} or None (no room, < min_r x the stop, or not nearer
    than the target). px = entry +/- pts, pts rounded DOWN to a tick so the fill pays <= cap $ after the commission."""
    try:
        e, risk, cap = float(entry), float(risk_pts), float(cap_usd)
        tgt = float(tgt_pts) if tgt_pts else None
    except (TypeError, ValueError):
        return None
    if cap <= 0 or risk <= 0:
        return None
    pts = int((cap + float(comm)) / PV / BANK_TICK) * BANK_TICK
    if pts <= 0 or pts < float(min_r) * risk - 1e-9 or (tgt and pts >= tgt - 1e-9):
        return None
    return {"qty": 1, "pts": round(pts, 2), "px": round(e + (1 if int(d) == 1 else -1) * pts, 2),
            "usd": round(pts * PV - float(comm), 2), "cap_usd": round(cap, 2)}


def bank_pnl(bank: dict, qty: int, mfe_r, risk_pts, model_pnl: float, comm: float = COMM) -> tuple:
    """-> ($ booked, banked?) at the model's exit: banked when the model's best excursion went 1 tick through the bank price
    (the broker's limit filled); else the model's own $, never above the bank."""
    q = max(1, int(qty or 1))
    usd = round(q * (float(bank["pts"]) * PV - float(comm)), 2)
    try:
        hit = float(mfe_r) * float(risk_pts) >= float(bank["pts"]) + BANK_TICK - 1e-9
    except (TypeError, ValueError):
        hit = False
    return (usd, True) if hit else (round(min(float(model_pnl), usd), 2), False)


def payout_advice(balance: float, start: float = 50000.0, paid_days=(), today: str | None = None,
                  buffer: float = BUFFER, cushion: float = CUSHION, since: float | None = None,
                  since_profit: float | None = None) -> dict:
    """Funded: what to withdraw today. MFFU pays above the $2,100 buffer ($500 min); the bot keeps $1,000 more in
    (the 25K: $1,100 buffer, keep $500 more, and MFFU's >= $250 net since the last payout: `since` / `since_profit`,
    checked only when both are given and a payout was already made)."""
    keep = start + float(buffer) + float(cushion)
    amt = round(max(0.0, float(balance) - keep), 2)
    amt = float(int(amt))
    ready = amt >= PAY_MIN and (today is None or today not in set(paid_days))
    short = None
    if ready and since is not None and since_profit is not None and list(paid_days) and float(since_profit) < float(since):
        ready, short = False, round(float(since) - float(since_profit), 2)
    out = {"keep_at": keep, "request": amt if ready else 0.0, "to_you": round(amt * SPLIT, 2) if ready else 0.0, "ready": ready,
            "to_next": round(max(0.0, keep + PAY_MIN - float(balance)), 2)}
    if short is not None:                 # MFFU's net-since-the-last-payout rule (the 25K's $250) not met yet
        out["to_next"], out["since_short"] = short, short
    return out


def _open_leg(ad, d=None):
    """The first NinjaTrader leg of adapter `ad` still open / pending / closing (direction d, any side when None); None =
    none (the paper adapter has no legs). Both lanes trade ONE account: a lane whose model already shows flat while its
    CLOSEPOSITION is not confirmed yet still holds that account (review 2026-11-17)."""
    legs = getattr(ad, "legs", None) if ad is not None else None
    if not isinstance(legs, list) or not legs:
        return None
    from .ninjatrader import OPEN_STATUSES
    for lg in legs:
        if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES:
            ld = int(lg.get("dir") or (1 if str(lg.get("side") or "").upper() == "BUY" else -1))
            if d is None or ld == d:
                return lg
    return None


class RapidAtlas(AB.AccountB):
    """ATLAS on the Rapid EOD (LiveBot.acct_r): account B's code on the SAME NinjaTrader account as LIT's lane."""

    def __init__(self, bot, spec, state_path=None, adapter_factory=None):
        super().__init__(bot, spec, state_path=state_path or _state_path(getattr(bot, "state_path", None)),
                         adapter_factory=adapter_factory)
        self.P = plan_info(self.spec)
        self.label = f"ATLAS Rapid {self.name}"
        self.spec["label"] = self.label

    # ---- the other lane
    def lane(self):
        ac = getattr(self.bot, "accts", None)
        return next((a for a in (getattr(ac, "accounts", None) or []) if a.spec.get("lane") == "rapid"), None)

    def all_closes(self) -> list:
        ln = self.lane()
        return list(self.closes) + [list(c) for c in (getattr(ln, "closes", None) or [])]

    def day_pnl(self, day) -> float:
        return round(sum(float(p) for d, _, p, *_ in self.all_closes() if d == day), 2)

    def adapter_cfg(self) -> dict:
        c = super().adapter_cfg()
        d = os.path.dirname(self.state_path)
        log_dir = os.path.join(ROOT, "logs") if self.real_bot() else d
        return {**c, "nt_file_tag": "acctr_", "nt_state_path": os.path.join(d, "ninjatrader_state_acctr.json"),
                "nt_audit_log": os.path.join(log_dir, "ninjatrader_oif_acctr.log")}

    # ---- one book for the account
    def _funded_state(self, today):
        from . import multi_account as MA
        F = self.spec["funded"]
        if not F.get("start"):
            return None
        st = MA.sizing_state("funded", [(d, t, p) for d, t, p, *_ in self.all_closes()], today, F["start"], self.rules,
                             prior=float(F.get("prior") or 0.0), payouts=dict(F.get("payouts") or {}))
        if F.get("payouts"):                          # after the first payout the floor sits at start + $100 (as account B)
            lock = float(self.rules["lock"])
            if float(st["floor"]) < lock:
                st["floor"] = lock
                st["room"] = round(float(st["balance"]) + float(st["cum"]) - lock, 2)
                st["locked"] = True
        st["n_today"] = self.entries_today(today)
        return st

    def _state_raw(self, now=None):
        from . import multi_account as MA
        today = AB.trading_day(now if now is not None else self.clock())
        if self.funded():
            return self._funded_state(today)
        if not self.spec.get("eval_start"):
            return None
        return MA.sizing_state("two_week", [(d, t, p) for d, t, p, *_ in self.all_closes()], today, self.spec["eval_start"],
                               self.rules, prior=float(self.spec.get("prior_pnl") or 0.0), n_today=self.entries_today(today),
                               anchor=self.anchor())

    def broker_tick(self, now):
        return None                       # the LIT lane reads the account's real balance (one account, one check)

    def days(self, today=None) -> dict:
        start = (self.spec.get("funded") or {}).get("start") if self.funded() else self.spec.get("eval_start")
        out = {}
        for d, _, p, *_ in self.all_closes():
            if start and str(d) >= str(start) and (today is None or str(d) <= today):
                out[str(d)] = round(out.get(str(d), 0.0) + float(p), 2)
        return out

    def eval_view(self, now=None) -> dict:
        ev = super().eval_view(now)
        if self.funded() or ev.get("status") != "passed":
            return ev
        today = AB.trading_day(now if now is not None else self.clock())
        dd = {d: v for d, v in self.days(today).items() if abs(v) > 1e-9}
        prof = float(ev.get("profit") or 0.0)
        best = max(dd.values()) if dd else 0.0
        if len(dd) < MIN_DAYS or best > BEST_DAY * prof + 1e-9:
            ev = {**ev, "status": "open", "pass_wait": f"{len(dd)} of {MIN_DAYS} days, best day ${best:,.0f} vs 30% ${BEST_DAY * prof:,.0f}"}
        return ev

    # ---- size: $500 / 30% of the room, the soft day, the 30% best-day cap (eval)
    def size(self, trade: dict, state, key=None) -> dict:
        R = self.rules
        if state is None:
            return {"qty": 0, "reasons": ["account state unknown (eval_start / funded_start missing?): not traded"], "lock": None}
        risk = _num(trade.get("risk_pts"))
        if not risk or risk <= 0:
            return {"qty": 0, "reasons": ["no stop distance"], "lock": None}
        room = _num(state.get("room"), 0.0)
        if room <= 0:
            return {"qty": 0, "reasons": [f"room ${room:,.0f} to the floor: no trade"], "lock": "failed"}
        if not self.funded() and float(state.get("profit") or 0.0) + float(state.get("cum") or 0.0) >= float(R["target"]):
            return {"qty": 0, "reasons": ["eval target reached: no new trade"], "lock": "passed"}
        cap = float(self.P["atlas_usd"])
        q, usd, loss1 = stack_qty(risk, room, float(state.get("cum") or 0.0), int(R["max_micros"]), float(R["dll"]), cap)
        why = [f"${usd:,.0f} risk (min ${cap:,.0f}, 30% of the ${room:,.0f} room, the day left) / ${loss1:,.0f} a micro -> {q}"]
        if q > 0 and not self.funded():
            today = AB.trading_day(self.clock())
            q2, cap = best_day_cap(q, trade.get("tgt_pts"), risk, float(R["target"]), self.day_pnl(today))
            if q2 < q:
                why.append(f"best-day rule 30%: a winner pays <= ${cap:,.0f} -> {q2}")
                q = q2
        return {"qty": int(q), "reasons": why, "lock": None}

    # ---- never two positions on the account; funded news ban
    def lit_opposite(self, d: int):
        b = self.bot
        st = getattr(b, "state", None) or {}
        ln = self.lane()
        if ln is not None and ln.open_t is not None:
            return "LIT holds a trade on this account"
        if ln is not None:
            try:
                lg = _open_leg(getattr(ln, "adapter", None))
            except Exception:
                return "LIT's lane: NinjaTrader state unreadable (fails closed)"
            if lg:
                return f"LIT's lane still shows a {lg.get('status')} bracket at NinjaTrader (not confirmed flat)"
        if st.get("position"):
            return "LIT is in a trade"
        if st.get("enter_now"):
            return "LIT is entering a trade"
        why = super().lit_opposite(d)
        if why:
            return why
        ab = getattr(b, "acct_b", None)
        if ab is not None and ab is not self and ab.open_t is not None:
            pv = ab.prov.get(int(ab.open_t)) or {}
            if int(pv.get("dir") or 0) == -d:
                return f"ATLAS's 25K holds a {'SHORT' if d == 1 else 'LONG'} position"
        return None

    def news_at(self, now, pre=None, post=None):
        """A Tier-1 release whose window holds `now` (funded only): flat from 3 min before, no entry until 2.5 min after
        (engine/multi_account NEWS_PRE_S / NEWS_POST_S: MFFU's -2/+2 min with a margin)."""
        if not self.funded():
            return None
        from . import multi_account as MA
        pre = MA.NEWS_PRE_S if pre is None else pre
        post = MA.NEWS_POST_S if post is None else post
        for r in MA.tier1_releases(AB.trading_day(now)):
            if r - pre <= now < r + post:
                return r
        return None

    def guard(self, act, entry_t, now):
        r = self.news_at(int(now))
        if r is not None:
            return f"GUARD funded news ban: Tier-1 release at {AB._et(r):%H:%M} ET (MFFU flat -2/+2 min; the bot -3/+2.5)"
        return super().guard(act, entry_t, now)

    def tick(self, df5, df1, sym, now):
        try:
            if self.open_t is not None and self.news_at(int(now)) is not None:      # -2 / +2 min (held into it: closed)
                pv = self.prov.get(int(self.open_t)) or {}
                if not ((pv.get("closing") or {}) and not pv["closing"].get("done")):
                    self.flatten(int(self.open_t), "NEWS FLAT", sym, now)
        except Exception as e:
            self.log("error", f"news flatten failed: {e.__class__.__name__}: {e}")
        return super().tick(df5, df1, sym, now)

    def yield_to_lit(self, d: int, sym: str, now: int, px=None, any_side: bool = False) -> bool:
        """LIT is about to enter direction d: ATLAS's position here (any side on this account; only the opposite side when
        LIT enters another account) is closed at market first. True = LIT may route now (flat, or the close CONFIRMED)."""
        with self.mx:
            try:
                self.reconcile_unplaced(now)
            except Exception:
                pass
            if self.open_t is None:
                return self._legs_clear(d, any_side)
            et_ = int(self.open_t)
            pv = self.prov.get(et_) or {}
            if not any_side and int(pv.get("dir") or 0) != -d:
                return self._legs_clear(d, any_side)
            cl = pv.get("closing")
            if cl and not cl.get("done"):
                self.settle_closing(sym, now)
            else:
                self.log("risk", f"LIT enters {'LONG' if d == 1 else 'SHORT'}: ATLAS's {pv.get('short') or pv.get('key')} on "
                                 f"{self.name} is closed at market first (LIT has priority)")
                if self.flatten(et_, "HEDGE", sym, now, px=_num(px)):
                    pv["final"] = True
            return (self.open_t is None or int(self.open_t) != et_) and self._legs_clear(d, any_side)

    def _legs_clear(self, d: int, any_side: bool) -> bool:
        """ATLAS's NinjaTrader book shows no leg still open / closing (any side on this account, else the side opposite d):
        a model exit whose CLOSEPOSITION is unconfirmed is still a position here. A read error fails closed."""
        try:
            return _open_leg(self.adapter, None if any_side else -d) is None
        except Exception:
            return False

    # ---- funded payouts (Rapid EOD: daily, above the buffer, $500 min, keep $1,000 more)
    def funded_view(self, now=None) -> dict:
        now = int(now if now is not None else self.clock())
        today = AB.trading_day(now)
        st = self._state_raw(now) or {}
        start = float(self.rules["start"])
        bal = start + float(st.get("balance") or 0.0) + float(st.get("cum") or 0.0)
        F = self.spec.get("funded") or {}
        pays = F.get("payouts") or {}
        since = since_profit = None
        if self.P["preset"] != PRESET and pays:       # the 25K: >= $250 net since the last payout (days after it)
            last = max(str(d) for d in pays)
            since = float(self.P["since"])
            since_profit = sum(v for d, v in self.days(today).items() if d > last)
        a = payout_advice(bal, start, pays.keys(), today, self.P["buffer"], self.P["cushion"], since, since_profit)
        paid = sum(float(v) for v in (F.get("payouts") or {}).values())
        text = (f"PAYOUT READY: request ${a['request']:,.0f} (${a['to_you']:,.0f} to you); keeps ${a['keep_at']:,.0f} in the account"
                if a["ready"] else
                f"next payout once ${a['since_short']:,.0f} more is made since the last one (MFFU: >= ${self.P['since']:,.0f})"
                if a.get("since_short") is not None else
                f"next payout once the balance passes ${a['keep_at'] + PAY_MIN:,.0f} (${a['to_next']:,.0f} to go)")
        out = {"name": self.label, "balance": round(bal, 2), "ask_at_balance": a["keep_at"] + PAY_MIN, "to_ask": a["to_next"],
                "request": a["request"], "to_you": a["to_you"], "ready": a["ready"], "paid": round(paid, 2),
                "paid_to_you": round(paid * SPLIT, 2), "graduated": False, "text": text,
                "record_cmd": "python -X utf8 -m engine.rapid --payout {day}={amount}", "payouts": dict(F.get("payouts") or {})}
        if a.get("since_short") is not None:
            out["since_short"] = a["since_short"]
        return out

    def _funded_lifecycle(self, now):
        try:
            t = self.funded_view(now)
            ev = self._funded_eval_view(now)
        except Exception as e:
            self.log("error", f"funded tracker failed: {e.__class__.__name__}: {e}")
            return
        today = AB.trading_day(now)
        if t["ready"]:
            key = f"rapidpay:{today}:{self.name}"
            if key not in self.notified:
                self.notified.append(key)
                self.log("risk", t["text"])
                self._push_text(f"Rapid EOD: request ${t['request']:,.0f}", t["text"] + ". Then: python -X utf8 -m engine.rapid "
                                f"--payout {today}={t['request']:.0f}", key)
        if ev.get("status") in ("lost", "stuck"):
            key = f"rapidf:{ev['status']}:{(self.spec.get('funded') or {}).get('start')}:{self.name}"
            if key not in self.notified:
                self.notified.append(key)
                self._push_text(f"Rapid EOD funded {ev['status']}", f"room ${ev.get('room') or 0:,.0f}: no new trade", key)

    def _push_text(self, title, body, key):
        return super()._push_text(title, body, f"rapid:{key}")


def _state_path(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_acctr" + (ext or ".json")


def build_atlas(bot, blk: dict | None, **kw):
    """LiveBot: ATLAS's lane of the Rapid (None when off)."""
    if not blk:
        return None
    lit_acct = None
    try:
        if (bot.cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(bot.cfg)
    except Exception:
        lit_acct = None
    spec = AB.normalize(atlas_block(blk), lit_account=lit_acct)
    return RapidAtlas(bot, spec, **kw).start() if spec else None


# ---------------------------------------------------------------------------------------------------------------- status
def status(p: str | None = None, state_path: str | None = None) -> dict:
    blk = read(p)
    if blk is None:
        return {"on": False, "text": "Rapid EOD: OFF (no account set: python -X utf8 -m engine.rapid --account \"<Name>\")"}
    sp = state_path or os.path.join(ROOT, "data")
    closes = []
    for fn, key in (("live_state_accounts.json", None), ("live_state_acctr.json", None)):
        try:
            with open(os.path.join(sp, fn), encoding="utf-8") as fh:
                b = json.load(fh)
            if fn.endswith("_accounts.json"):
                a = (b.get("accounts") or {}).get(LANE_ID) or {}
                if a.get("nt_account") == blk["account"]:
                    closes += a.get("closes") or []
            elif b.get("account") == blk["account"]:
                closes += b.get("closes") or []
        except Exception:
            pass
    funded = blk.get("stage") == "funded"
    P = plan_info(blk)
    nm = "Rapid EOD" if P["preset"] == PRESET else P["label"]
    start = blk.get("funded_start") if funded else blk.get("eval_start")
    days = {}
    for d, _, pnl, *_ in closes:
        if start and str(d) >= str(start):
            days[str(d)] = round(days.get(str(d), 0.0) + float(pnl), 2)
    paid = sum(float(v) for v in (blk.get("payouts") or {}).values()) if funded else 0.0
    bal = P["start"] + sum(days.values()) - paid
    out = {"on": True, "account": blk["account"], "stage": blk.get("stage") or "eval", "armed": blk.get("armed") is True,
           "start": start, "balance": round(bal, 2), "days_traded": len([v for v in days.values() if abs(v) > 1e-9])}
    if funded:
        pays = blk.get("payouts") or {}
        since = since_profit = None
        if P["preset"] != PRESET and pays:            # the 25K: >= $250 net since the last payout
            last = max(str(d) for d in pays)
            since, since_profit = float(P["since"]), sum(v for d, v in days.items() if d > last)
        a = payout_advice(bal, P["start"], pays.keys(), _today(), P["buffer"], P["cushion"], since, since_profit)
        out["payout"] = a
        out["text"] = (f"{nm} funded {blk['account']}: balance ${bal:,.0f}; "
                       + (f"request ${a['request']:,.0f} today (${a['to_you']:,.0f} to you)" if a["ready"] else
                          f"no payout yet (${a['to_next']:,.0f} to go; the bot keeps ${a['keep_at']:,.0f} in)"))
    else:
        best = max(days.values()) if days else 0.0
        out["text"] = (f"{nm} eval {blk['account']}: balance ${bal:,.0f} (target ${P['start'] + P['target']:,.0f}), {out['days_traded']} of 4 days, "
                       f"best day ${best:,.0f}; {'ARMED' if out['armed'] else 'not armed yet (START BOT + the phrase)'}")
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.rapid", description="the MFFU Rapid EOD 50K (LIT + ATLAS on one account)")
    ap.add_argument("--account")
    ap.add_argument("--start")
    ap.add_argument("--size", choices=("50k", "25k"), default=None, help="the Rapid EOD size (default: 50K / the same Name's)")
    ap.add_argument("--to-funded", action="store_true")
    ap.add_argument("--payout")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--lit-bank", choices=("on", "off"), help="the 25K only: LIT takes 1 micro banked at the day's 30%% room")
    a = ap.parse_args(argv)
    if a.lit_bank:
        b = load()
        if not b.get("account") or plan_info(b)["preset"] != "mffu_rapid_eod_25k":
            print("NOT set: --lit-bank is for the Rapid EOD 25K only (no 25K in data/rapid.json)")
            return 1
        b["lit_bank"] = a.lit_bank == "on"
        save(b)
        print(f"Rapid EOD 25K: LIT bank-at-the-room {a.lit_bank.upper()} (from the next bot start)")
        return 0
    if a.off:
        r = off()
        print("Rapid EOD: OFF (no new trades on it after the next bot start)")
        return 0 if r["ok"] else 1
    if a.payout:
        r = record_payout(a.payout)
        print("recorded" if r["ok"] else f"NOT recorded: {r['error']}")
        return 0 if r["ok"] else 1
    if a.to_funded:
        r = to_funded(a.account, a.start)
        print("Rapid EOD funded: set (disarmed: START BOT + the phrase arms it)" if r["ok"] else f"NOT set: {r['error']}")
        return 0 if r["ok"] else 1
    if a.account:
        r = set_account(a.account, a.start, preset=f"mffu_rapid_eod_{a.size}" if a.size else None)
        if not r["ok"]:
            print(f"NOT set: {r['error']}")
            return 1
        b = r["block"]
        print(f"[OK] Rapid EOD{'' if b.get('plan', PRESET) == PRESET else ' 25K'} = {b['account']}, eval from {b['eval_start']}, NOT armed. LIT + ATLAS trade it after START BOT "
              "(you type I ACCEPT LIVE RISK)." + (f" {r['note']}." if r.get("note") else ""))
        return 0
    print(status()["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
