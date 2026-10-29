"""Account C (owner 2026-10-28: "build the scalping bot as well ... the scalping on a 25"): BLITZ, the scalper, routed to its
OWN prop account, next to Zlarior / LIT (the 50K) and ATLAS (account B, a 25K). OFF by default; Sim only until the owner
himself arms it. The rule is engine/blitz.py's (BLITZ_STRATEGY.md in plain words, research/writeups/scalp-na-mffu.md).

Where the switch lives: data/account_c.json on the PC (local, gitignored) = {"account_c": {...} | null}. Absent / null =
off: the bot is exactly today's (no adapter, no state file, no heartbeat block, LIT / ATLAS untouched). The block:
  {"account": "<NinjaTrader account Name>", "plan": "builder25k", "eval_start": "yyyy-mm-dd", "armed": false}
  optional: "params": {...}    BLITZ rule parameters (engine/blitz.rule_params; absent = today's researched rule). A later
                               research pick plugs in here by config only (research/scalp/blitz_25k_pick.json is NOT read)
            "unfiltered": true the plain NA scalp without the prior-day range filter (off)
            "prior_pnl", "eval_anchor"  $ on the account before the bot traded it / the MFFU balance + floor on a day
            "resume_after": unix  set by `--resume` after a scorecard pause (the owner's own decision)
  A REAL (non-Sim) account also needs "armed": true (Start page: the owner types I ACCEPT LIVE RISK), the phrase typed at the
  bot's start and NINJATRADER_LIVE=1 (engine/ninjatrader._live_gate, the same gate as account B). The bot never sets any.

Owner switch:  python -X utf8 -m engine.account_c --account "<Name>" --plan builder25k --start <day>   |   off
               (refused when engine.ninjatrader --selftest fails), or the Start page's "BLITZ · 25K" slot.

What it does (engine/live.py LiveBot.acct_c, _account_c_tick after LIT's routing and account B; an exception is logged and
never touches LIT or ATLAS):
  * its own NinjaTrader account: own adapter (order-file tag "acctc_", own NinjaTrader state file), own ledger and state
    file (live_state_acctc.json next to the bot's), own guards, own startup reconcile; paper when the bot is on paper;
  * BLITZ's live Engine (engine/blitz.Engine) on the closed 1m bars, exactly the research rule: at the 1m closes 11:00,
    11:30 ... 15:30 a close outside the noise band (on days after a wide day) -> MARKET at once (the next bar's open, ~2 s
    after the signal close), the stop order at the signal close -/+ 1.5 x the 5m ATR, an OCO limit at 20R (never reached);
    after +1R the stop trails 1.5R behind the best price (stop CHANGE through the adapter, only ever tighter); out at market
    after 30 bars, by 15:55 (and 5 minutes before a CME early close: engine/lit_live.early_close; no entry in the last 15
    minutes before it); one position, at most 6 trades a day, no new entry after -3R on the day. A blocked signal still
    uses BLITZ's slot (the model trade runs on paper), as the research's eval does: the bot never chases;
  * size = the research's 25K eval size (engine/blitz.PLAN, tools/scalp_na_lib.qty "frac"): 40% of the room to the
    trailing floor, capped at $600 and 0.9 x the soft daily loss left, 20 micros, 1 micro while it fits half the room;
  * its own eval: balance, EOD trailing floor ($1,000, locked at start + $100), room, sessions from eval_start; pass
    (+$1,500: no new trade, push "EVAL PASSED: run the funded switch"; never automatic), fail (room <= 0), stuck (room under
    $249.56 = 2 x BLITZ's median stop-out: push "buy a new one"), the $600 soft daily loss (no new entry today);
  * the performance contract (BLITZ_STRATEGY.md "Kill switch"): after 20+ finished trades on account C, average R or PF(R)
    below the 2026 research's bootstrap 5th percentile for that many trades, or 6 losing days in a row -> PAUSED (no new
    entry on account C, one push); the owner resumes with `python -m engine.account_c --resume`;
  * NEVER opposite to another account of the owner (MFFU bans long + short on one underlying across your own accounts):
    no BLITZ entry while LIT's account holds / enters / has an armed setup (limit or waiting for its 1m CISD) the other way,
    account B (ATLAS) holds or closes the other way, or an extra account holds it. Priority LIT > ATLAS > BLITZ: when LIT or
    ATLAS enters the other way while C is open, C is closed at market FIRST (HEDGE) and their order goes out only once that
    close is CONFIRMED flat (LIT: engine/live._hedge_clear; ATLAS: engine/account_b.AccountB._c_yield); C is never marked
    flat on an unconfirmed close (re-sent every 10 s);
  * an entry NinjaTrader refused / never took (engine/ninjatrader.entry_never_placed) is never booked: C is flat, push
    "order NOT placed" with NinjaTrader's reason; a NOT OK answer that may still be open is kept and managed (push);
  * pushes "BLITZ <name> ..." (REAL / SIM) and narrator events labelled REAL (engine/narrator.py), next to the BLITZ PAPER
    shadow ledgers of engine/blitz.py (which keep running unchanged);
  * funded (never automatic): `--to-funded --account "<funded Name>" --start <day>` (or the Start page's "Passed → funded")
    = stage "funded", DISARMED; funded size = the research's 25K funded pick (10% of the room, at most $150 a trade, no new
    trade after +$400 on the day: research/scalp/na_life.json picks 25k fz), the MFFU payout tracker (engine/funded_life).

    python -X utf8 -m engine.account_c                         # the block now
    python -X utf8 -m engine.account_c --account "<Name>" --plan builder25k --start 2026-11-02
    python -X utf8 -m engine.account_c off
    python -X utf8 -m engine.account_c --status                # eval + scorecard from the state file
    python -X utf8 -m engine.account_c --resume                # after a scorecard pause (the owner's decision)
    python -X utf8 -m engine.account_c --to-funded --account "<funded Name>" --start <day>
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time as _time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_REL = os.path.join("data", "account_c.json")
PLANS = {"builder25k": {"preset": "mffu_builder_25k", "label": "MFFU Builder 25K", "price": 63.00}}
TAG = "acctc_"
VERSION = 1
MAX_AGE_S = 50                  # a signal first seen later than this after its entry bar opened is not chased
CLOSE_RETRY_S = 10              # an unconfirmed close is re-sent at most this often (as account B)
FLAT_GRACE_S = 60               # clock flatten 60 s after 15:55 when the model has not closed it yet (a late 1m bar)
EC_FLAT_MIN, EC_ENTRY_MIN = 5, 15   # CME early close: flat 5 min before the halt, no entry in the last 15 min (= engine/ninjatrader)
TICK, PV, COMM = 0.25, 2.0, 1.90
ADAPTER_FACTORY = None          # tests: (spec, adapter cfg) -> adapter; None = engine/live.ADAPTERS
STAGES = ("eval", "funded")
FUNDED_KEYS = ("stage", "funded_start", "funded_balance", "payouts", "eval_account", "funded_set")
STOP_STATUSES = ("passed", "failed", "stuck", "lost", "graduated")
# sizes (research): eval = engine/blitz.PLAN (na_sizing pick); funded = research/scalp/na_life.json picks["25k"]["fz"]
SIZE_EVAL = {"f": 0.4, "cap": 600.0, "dll_frac": 0.9, "day_tp": None}
SIZE_FUNDED = {"f": 0.1, "cap": 150.0, "dll_frac": 0.9, "day_tp": 400.0}
# the performance contract (BLITZ_STRATEGY.md): bands = bootstrap of the 330 research trades of 2026 (na_best_trades.json)
SCORE_MIN_TRADES = 20
SCORE_LOSE_DAYS = 6             # losing days in a row (2026 worst 3; p95 of a 40-traded-day stretch 6)
SCORE_NS = (20, 30, 40, 60, 100, 150, 200)
SCORE_FILE = os.path.join(ROOT, "research", "scalp", "na_best_trades.json")
FUNDED_CMD = 'python -X utf8 -m engine.account_c --to-funded --account "<funded Name>" --start <first funded day>'
RESUME_CMD = "python -X utf8 -m engine.account_c --resume"
PAYOUT_CMD = "python -X utf8 -m engine.account_c --payout {day}={amount}"
EXIT_REASON = {"stop": "STOP", "time": "TIME", "flat": "TIME", "target": "TARGET"}
# order sanity for BLITZ (engine/guards.sanity): its stop is 1.5 x the 5m ATR, not LIT's sweep stop: 37 of the 330 research
# trades of 2026 had stops over LIT's 100-pt cap (widest 202 pts; size follows the stop). A stop beyond 250 pts is refused.
MAX_STOP_PTS = 250.0


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


def _side(d) -> str:
    return "LONG" if int(d or 0) > 0 else "SHORT"


# ---------------------------------------------------------------------------------------------------------------- config
def local_path(root: str | None = None) -> str:
    return os.path.join(root or ROOT, LOCAL_REL)


def read_local(root: str | None = None) -> tuple:
    """(found, block): found False when data/account_c.json is missing or unreadable (= off)."""
    try:
        with open(local_path(root), encoding="utf-8") as fh:
            c = json.load(fh)
        if not isinstance(c, dict) or "account_c" not in c:
            return False, None
        blk = c.get("account_c")
        return True, (blk if isinstance(blk, dict) and blk else None)
    except Exception:
        return False, None


def write_local(block, root: str | None = None, why: str = "") -> str:
    p = local_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rec = {"account_c": block if isinstance(block, dict) and block else None, "saved_at": int(_time.time()),
           "note": "BLITZ's account on this PC (engine/account_c.py). Local, gitignored; null = off." + (f" {why}" if why else "")}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, p)
    return p


def raw_cfg(root: str | None = None):
    """The account_c block (None = off). Never raises."""
    return read_local(root)[1]


def normalize(blk: dict | None, lit_account: str | None = None, b_account: str | None = None) -> dict | None:
    """The account_c block -> a spec {"account", "plan", "preset", "rules", "eval_start", "armed", "params", "filtered",
    "stage", "label", "plan_label", "min_room", "problem": why it cannot trade or None}; None when off."""
    if not isinstance(blk, dict) or not blk:
        return None
    from . import blitz as BZ
    from . import multi_account as MA
    plan = str(blk.get("plan") or "builder25k").lower().replace(" ", "").replace("_", "")
    P = PLANS.get(plan)
    out = {"account": str(blk.get("account") or "").strip(), "plan": plan, "eval_start": str(blk.get("eval_start") or ""),
           "armed": blk.get("armed") is True, "prior_pnl": float(_num(blk.get("prior_pnl"), 0.0)), "eval_anchor": blk.get("eval_anchor"),
           "filtered": blk.get("unfiltered") is not True, "params": None, "problem": None,
           "resume_after": _num(blk.get("resume_after"))}
    out["preset"] = (P or PLANS["builder25k"])["preset"]
    out["plan_label"] = (P or {}).get("label") or plan
    out["rules"] = MA.rules_of({"preset": out["preset"]})
    out["label"] = f"BLITZ {out['account'] or '?'}"
    out["min_room"] = BZ.STUCK_ROOM if out["filtered"] else BZ.STUCK_ROOM_RAW
    nm = out["account"]
    if P is None:
        out["problem"] = f"unknown plan {plan!r} (BLITZ trades a builder25k: MFFU allows one funded 50K per person, that is LIT's)"
    elif not nm or any(c in nm for c in ";,\r\n|"):
        out["problem"] = "account name missing or invalid"
    elif lit_account and nm == str(lit_account).strip():
        out["problem"] = f"{nm} is Zlarior's (LIT's) own account: BLITZ needs its own account"
    elif b_account and nm == str(b_account).strip():
        out["problem"] = f"{nm} is ATLAS's account (account B): BLITZ needs its own account"
    elif out["eval_start"]:
        try:
            _dt.date.fromisoformat(out["eval_start"])
        except ValueError:
            out["problem"] = f"eval_start {out['eval_start']!r} is not yyyy-mm-dd"
    if blk.get("params") not in (None, {}):
        try:
            if not isinstance(blk["params"], dict):
                raise ValueError("params must be an object of BLITZ rule parameters")
            pp = BZ.rule_params(blk["params"])
            out["params"] = None if BZ.is_default(pp) else {k: v for k, v in pp.items() if v != BZ.DEFAULT_PARAMS[k]}
        except ValueError as e:
            out["problem"] = out["problem"] or f"params: {e}"
    stage = str(blk.get("stage") or "eval").strip().lower()
    out["stage"] = stage
    if stage not in STAGES:
        out["problem"] = out["problem"] or f"unknown stage {blk.get('stage')!r} (eval or funded)"
    elif stage == "funded":
        from .account_b import funded_block
        F, why = funded_block(blk, out["rules"])
        out["funded"] = F
        out["plan_label"] = f"{out['plan_label']} funded"
        if why:
            out["problem"] = out["problem"] or why.replace("engine.account_b", "engine.account_c")
    return out


def is_funded(spec: dict | None) -> bool:
    return bool(spec) and spec.get("stage") == "funded" and isinstance(spec.get("funded"), dict)


def size_rule(spec: dict | None) -> dict:
    return dict(SIZE_FUNDED if is_funded(spec) else SIZE_EVAL)


def frac_qty(risk_pm: float, room: float, cum: float, f: float, cap: float, dll: float, maxq: int, dll_frac: float = 0.9) -> int:
    """tools/scalp_na_lib.qty "frac" (= engine/blitz.qty on the plan's limits): f x the room, <= cap, <= dll_frac x the soft
    daily loss left (dll + today's closed P&L), max micros; 1 micro while it fits half the room and the daily loss left."""
    dll_left = float(dll) + float(cum)
    budget = min(float(cap), float(f) * float(room), dll_frac * dll_left)
    if budget <= 0:
        return 0
    q = int(min(int(maxq), budget // float(risk_pm)))
    if q == 0 and float(risk_pm) <= min(0.5 * float(room), dll_frac * dll_left):
        q = 1
    return q


def qty(spec: dict, risk_pts: float, state: dict | None) -> dict:
    """Micros for one BLITZ entry on account C: {"qty", "reasons"}. risk_pts = the estimated fill to the stop. Fails closed."""
    R = spec["rules"]
    S = size_rule(spec)
    if state is None:
        return {"qty": 0, "reasons": ["eval state unknown (eval_start missing?): not traded"]}
    risk = _num(risk_pts)
    if not risk or risk <= 0:
        return {"qty": 0, "reasons": ["no stop distance"]}
    room = _num(state.get("room"), 0.0)
    cum = _num(state.get("cum"), 0.0)
    if room <= 0:
        return {"qty": 0, "reasons": [f"room ${room:,.0f} to the max-loss floor: no new trade"]}
    if S.get("day_tp") is not None and cum >= float(S["day_tp"]):
        return {"qty": 0, "reasons": [f"day profit stop: +${cum:,.0f} today (no new trade after +${float(S['day_tp']):,.0f}: research funded pick)"]}
    risk_pm = (float(risk) + TICK) * PV + COMM
    q = frac_qty(risk_pm, room, cum, S["f"], S["cap"], float(R["dll"]), int(R["max_micros"]), S["dll_frac"])
    why = [f"{S['f']:.0%} of the ${room:,.0f} room, <= ${S['cap']:,.0f}, <= {S['dll_frac']:.0%} of the ${float(R['dll']) + cum:,.0f} "
           f"daily loss left: ${risk_pm:,.2f} a micro at a {float(risk):.2f}-pt stop -> {q}"]
    return {"qty": int(q), "reasons": why}


# ---------------------------------------------------------------------------------------------------------------- scorecard
_BANDS: dict = {}


def bands(path: str | None = None) -> dict:
    """{n: {"avg_r_p5", "pf_p5", "avg_r_p50", "pf_p50"}} for n in SCORE_NS: the 2026 research trades' bootstrap (seed 7,
    20,000 draws of n trades) = the floor of the performance contract. Cached."""
    p = path or SCORE_FILE
    if p in _BANDS:
        return _BANDS[p]
    import numpy as np
    with open(p, encoding="utf-8") as fh:
        r = np.array([float(t["r"]) for t in json.load(fh)["trades"]], dtype=np.float64)
    rng = np.random.default_rng(7)
    out = {}
    for n in SCORE_NS:
        s = r[rng.integers(0, len(r), size=(20000, n))]
        m = s.mean(axis=1)
        gw = np.where(s > 0, s, 0.0).sum(axis=1)
        gl = -np.where(s < 0, s, 0.0).sum(axis=1)
        pf = gw / np.maximum(gl, 1e-9)
        out[n] = {"avg_r_p5": round(float(np.percentile(m, 5)), 4), "pf_p5": round(float(np.percentile(pf, 5)), 3),
                  "avg_r_p50": round(float(np.percentile(m, 50)), 4), "pf_p50": round(float(np.percentile(pf, 50)), 3)}
    _BANDS[p] = out
    return out


def band_at(n: int, B: dict | None = None) -> dict | None:
    """The floor for n finished trades: linear between the SCORE_NS rows (beyond 200: the 200 row); None under 20."""
    if n < SCORE_MIN_TRADES:
        return None
    B = B or bands()
    ns = sorted(B)
    if n >= ns[-1]:
        return dict(B[ns[-1]])
    lo = max(k for k in ns if k <= n)
    hi = min(k for k in ns if k >= n)
    if lo == hi:
        return dict(B[lo])
    w = (n - lo) / (hi - lo)
    return {k: round(B[lo][k] + w * (B[hi][k] - B[lo][k]), 4) for k in B[lo]}


def score(trades: list, B: dict | None = None) -> dict:
    """The live scorecard of account C's finished trades [{"day", "r", "usd"}] (routed, booked, not voided): count, win %,
    avg R, PF (R and $), net $, losing days in a row now, the floor and the verdict ("warming" under 20 trades, "ok",
    "below": average R or PF(R) under the floor, or SCORE_LOSE_DAYS losing days in a row; a losing day = its trades' R sum
    under 0, the research's measure, so a smaller size after a loss does not count as a loss)."""
    rows = [t for t in trades or [] if isinstance(t, dict) and t.get("r") is not None]
    n = len(rows)
    rs = [float(t["r"]) for t in rows]
    us = [float(t.get("usd") or 0.0) for t in rows]
    gw, gl = sum(x for x in rs if x > 0), -sum(x for x in rs if x < 0)
    gwu, glu = sum(x for x in us if x > 0), -sum(x for x in us if x < 0)
    days = {}
    for t in rows:
        days[str(t.get("day"))] = days.get(str(t.get("day")), 0.0) + float(t["r"])   # a losing day = its trades' R sum < 0 (size-free)
    streak = 0
    for d in sorted(days, reverse=True):
        if days[d] < 0:
            streak += 1
        else:
            break
    out = {"n": n, "wins": sum(1 for x in rs if x > 0), "win_pct": round(100.0 * sum(1 for x in rs if x > 0) / n, 1) if n else None,
           "avg_r": round(sum(rs) / n, 4) if n else None, "pf_r": round(gw / gl, 3) if gl else None,
           "pf_usd": round(gwu / glu, 3) if glu else None, "usd": round(sum(us), 2), "lose_days": streak,
           "lose_days_cap": SCORE_LOSE_DAYS, "min_trades": SCORE_MIN_TRADES}
    fl = band_at(n, B) if n >= SCORE_MIN_TRADES else None
    out["floor"] = fl
    why = []
    if streak >= SCORE_LOSE_DAYS:
        why.append(f"{streak} losing days in a row (cap {SCORE_LOSE_DAYS}; 2026's worst was 3)")
    if fl:
        if out["avg_r"] is not None and out["avg_r"] < fl["avg_r_p5"]:
            why.append(f"average R {out['avg_r']:+.3f} after {n} trades is under the research floor {fl['avg_r_p5']:+.3f} "
                       f"(2026 bootstrap 5th percentile; expected about {fl['avg_r_p50']:+.3f})")
        pfr = out["pf_r"] if out["pf_r"] is not None else (99.0 if gw > 0 else 0.0)
        if pfr < fl["pf_p5"]:
            why.append(f"PF {pfr:.2f} after {n} trades is under the research floor {fl['pf_p5']:.2f} (expected about {fl['pf_p50']:.2f})")
    out["status"] = "below" if why else ("warming" if n < SCORE_MIN_TRADES else "ok")
    out["why"] = why
    return out


# ---------------------------------------------------------------------------------------------------------------- account
class AccountC:
    """BLITZ on its own account on one PC bot (engine/live.py LiveBot.acct_c)."""

    def __init__(self, bot, spec: dict, state_path: str | None = None, adapter_factory=None):
        self.bot = bot
        self.spec = spec
        self.rules = spec["rules"]
        self.name = spec["account"]
        self.label = spec["label"]
        self.problem = spec.get("problem")
        self.state_path = state_path if state_path is not None else _state_path_for(getattr(bot, "state_path", None))
        self.adapter_factory = adapter_factory if adapter_factory is not None else ADAPTER_FACTORY
        self.adapter = None
        self.ledger: list = []            # routed actions + the broker's answers
        self.closes: list = []            # [day, exit_t, pnl, entry_t, r]
        self.prov: dict = {}              # routed entry_t -> what was routed (dir, qty, stop, target, sig_t, model fill ...)
        self.open_t = None                # entry_t of the open position on C
        self.seen: set = set()
        self.lock = None                  # {"day", "reason"}: no new entry today (soft daily loss)
        self.paused = None                # {"t", "why"}: the performance contract paused BLITZ (owner resumes)
        self.notified: list = []
        self.notes: dict = {}
        self.eng = None                   # engine/blitz.Engine state (JSON)
        self.eng_sig = None               # the rule it runs (params / filter): a change starts the Engine over
        self.rows: list = []              # every BLITZ model trade since the start (routed or why not)
        self.signals: list = []           # today's / recent signals (display)
        self.last_size = None
        self.warm = None
        self._startup_ok = None
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

    def real_word(self) -> str:
        """REAL on a real account, SIM on a NinjaTrader Sim account, PAPER on the paper adapter (narrator / pushes)."""
        return {"LIVE": "REAL", "SIM": "SIM"}.get(self.kind(), "PAPER")

    def rule_sig(self) -> str:
        return json.dumps({"p": self.spec.get("params"), "f": bool(self.spec.get("filtered", True))}, sort_keys=True)

    def adapter_cfg(self) -> dict:
        """The bot's cfg WITHOUT LIT's account and arming, then account C's own name, arming, order-file tag and state
        files (= account B's adapter_cfg with the tag acctc_). A real account needs "armed": true in account_c AND the
        phrase typed at start AND NINJATRADER_LIVE=1 (the adapter's _live_gate); the bot's own arming is never inherited."""
        b = self.bot.cfg or {}
        base = {k: v for k, v in b.items() if k not in ("accounts", "armed", "confirm", "nt_account", "nt_state_path", "nt_audit_log",
                                                       "eval_start", "eval_prior_pnl", "eval_anchor", "lit_sizing", "funded",
                                                       "webhook_url", "account_b", "account_c")}
        p = dict(base.get("params") or {})
        p["max_micros"] = min(int(p.get("max_micros", 40) or 40), int(self.rules["max_micros"]))
        d = os.path.dirname(self.state_path) if self.state_path else os.path.join(ROOT, "data")
        real = self.real_bot()
        return {**base, "adapter": "ninjatrader" if b.get("adapter") == "ninjatrader" else "paper", "nt_account": self.name,
                "armed": bool(self.spec.get("armed")), "confirm": (b.get("confirm") or "") if self.spec.get("armed") else "",
                "params": p, "nt_file_tag": TAG, "nt_state_path": os.path.join(d, "ninjatrader_state_acctc.json"),
                "nt_audit_log": os.path.join(os.path.join(ROOT, "logs") if real else d, "ninjatrader_oif_acctc.log")}

    def real_bot(self) -> bool:
        try:
            from .live import STATE_PATH
            return getattr(self.bot, "state_path", None) == STATE_PATH
        except Exception:
            return False

    def start(self):
        self._load()
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
        dis = self.disabled_reason()
        ev = self.eval_view()
        self.log("system" if not dis else "risk",
                 f"{self.kind()} {self.name} {self.spec['plan_label']}, BLITZ scalper"
                 + (" (custom rule parameters)" if self.spec.get("params") else "")
                 + f", {'funded from ' + str(self.spec['funded'].get('start')) if self.funded() else 'eval from ' + (self.spec['eval_start'] or '?')}"
                 f" (balance ${ev.get('balance') or 0:,.0f}, room ${ev.get('room') or 0:,.0f}): " + (f"DISABLED ({dis})" if dis else "ready")
                 + (f"; PAUSED by the performance contract since {_et(self.paused['t']):%m-%d %H:%M} ET" if self.paused else ""))
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
            res = self.adapter.send(action) if self.adapter is not None else {"ok": False, "error": "no adapter"}
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        with self.mx:
            self.ledger.append({"t": int(self.clock()), **action, "result": res})
            self.ledger = self.ledger[-400:]
        self.log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}"
                 + (f" ({res.get('error')})" if res.get("ok") is False and res.get("error") else ""))
        self.save()
        return res

    def adapter_tick(self):
        ad = self.adapter
        if ad is None or self.problem or not getattr(ad, "loop_tick", False) or not callable(getattr(ad, "tick", None)):
            return
        try:
            ad.tick()
        except Exception as e:
            self.log("error", f"adapter tick failed: {e.__class__.__name__}: {e}")

    # ---- eval / funded state
    def funded(self) -> bool:
        return is_funded(self.spec)

    def day_pnl(self, day) -> float:
        return round(sum(float(c[2]) for c in self.closes if c[0] == day), 2)

    def entries_today(self, day) -> int:
        void = {int(r["entry_t"]) for r in self.ledger if r.get("side") == "exit" and r.get("reason") == "NO TRADE" and r.get("entry_t")}
        return len({int(r["entry_t"]) for r in self.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t")
                    and trading_day(int(r["entry_t"])) == day and int(r["entry_t"]) not in void
                    and (r.get("result") or {}).get("ok") is not False})

    def anchor(self):
        from . import eval_life as EL
        from . import sizing as SZ
        try:
            f = EL.load_anchor(self.name, state_path=getattr(self.bot, "state_path", None), main=False) if self.name else None
        except Exception:
            f = None
        return SZ.newest_anchor(f, self.spec.get("eval_anchor"), self._broker_anchor())

    def _broker(self):
        if not self.name or not self.spec.get("eval_start") or self.kind() == "PAPER" or self.funded():
            return None
        from . import broker_balance as BB
        return BB.for_bot(self.bot)

    def _broker_anchor(self):
        try:
            b = self._broker()
            return b.anchor(self.name, self.spec.get("eval_start")) if b else None
        except Exception:
            return None

    def funded_days(self, today=None) -> dict:
        F = self.spec.get("funded") or {}
        days = {}
        for c in self.closes:
            d = str(c[0])
            if F.get("start") and d >= F["start"] and (today is None or d <= today):
                days[d] = round(days.get(d, 0.0) + float(c[2]), 2)
        return days

    def _state_raw(self, now=None):
        from . import multi_account as MA
        today = trading_day(now if now is not None else self.clock())
        cl = [(c[0], c[1], c[2]) for c in self.closes]
        if self.funded():
            F = self.spec["funded"]
            if not F.get("start"):
                return None
            st = MA.sizing_state("funded", cl, today, F["start"], self.rules, prior=float(F.get("prior") or 0.0),
                                 payouts=dict(F.get("payouts") or {}), n_today=self.entries_today(today))
            if F.get("payouts"):
                lock = float(self.rules["lock"])
                if float(st["floor"]) < lock:
                    st["floor"] = lock
                    st["room"] = round(float(st["balance"]) + float(st["cum"]) - lock, 2)
                    st["locked"] = True
            return st
        if not self.spec.get("eval_start"):
            return None
        return MA.sizing_state("two_week", cl, today, self.spec["eval_start"], self.rules, prior=float(self.spec.get("prior_pnl") or 0.0),
                               n_today=self.entries_today(today), anchor=self.anchor())

    def eval_state(self, now=None):
        st = self._state_raw(now)
        try:
            b = self._broker()
            if b is not None and st is not None:
                st = b.cap_state(st, self.name, self.rules, now=int(now if now is not None else self.clock()))
        except Exception:
            pass
        return st

    def broker_tick(self, now):
        """Day-close auto-anchor of C's own NinjaTrader account + one "balance differs" push a day (as account B)."""
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
        from . import funded_life as FL
        now = int(now if now is not None else self.clock())
        today = trading_day(now)
        F = self.spec["funded"]
        t = FL.track(self.funded_days(today), dict(F.get("payouts") or {}), FL.plan_of(self.spec["plan"]), today=today, start=F.get("start"),
                     name=self.label, prior=float(F.get("prior") or 0.0))
        t["record_cmd"] = PAYOUT_CMD
        t["payouts"] = dict(F.get("payouts") or {})
        t["eval_account"] = F.get("eval_account")
        return t

    def eval_view(self, now=None) -> dict:
        """Balance, trailing floor, room, pass target, session, status (open / passed / failed / stuck; funded: funded / lost /
        stuck / graduated + the payout tracker)."""
        R = self.rules
        start = float(R["start"])
        try:
            st = self.eval_state(now)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {e}"}
        if self.funded():
            return self._funded_eval_view(st, now)
        if st is None:
            return {"start_balance": start, "balance": start, "target": start + float(R["target"]), "status": "no eval_start",
                    "session": None, "room": None}
        prof = float(st["profit"]) + float(st["cum"])
        bal = start + prof
        floor = bal - float(st["room"])
        status = ("passed" if prof >= float(R["target"]) else "failed" if st["room"] <= 0
                  else "stuck" if st["room"] < float(self.spec["min_room"]) else "open")
        return {**({"anchor": st["anchor"]} if st.get("anchor") else {}), "start_balance": start, "balance": round(bal, 2),
                "profit": round(prof, 2), "today": round(float(st["cum"]), 2), "floor": round(floor, 2), "room": round(float(st["room"]), 2),
                "target": start + float(R["target"]), "to_target": round(max(0.0, float(R["target"]) - prof), 2),
                "session": st.get("session"), "status": status, "start": self.spec.get("eval_start"), "days_traded": st.get("days_traded"),
                "dll": float(R["dll"]), "max_micros": int(R["max_micros"]), "plan": self.spec["plan_label"],
                "price": PLANS[self.spec["plan"]]["price"], "min_room": round(float(self.spec["min_room"]), 2)}

    def _funded_eval_view(self, st, now=None) -> dict:
        from . import sizing as SZ
        R = self.rules
        F = self.spec["funded"]
        now = int(now if now is not None else self.clock())
        start = float(R["start"])
        try:
            t = self.funded_view(now)
        except Exception as e:
            return {"error": f"{e.__class__.__name__}: {e}", "stage": "funded"}
        if st is None:
            return {"stage": "funded", "start_balance": float(F.get("balance") or start), "balance": float(F.get("balance") or start),
                    "status": "no funded_start", "session": None, "room": None, "funded": t}
        prof = float(st["balance"]) + float(st["cum"])
        room = float(st["room"])
        status = "lost" if room <= 0 else "graduated" if t.get("graduated") else "stuck" if room < float(self.spec["min_room"]) else "funded"
        today = trading_day(now)
        return {"stage": "funded", "start_balance": float(F.get("balance") or start), "plan_start": start, "balance": round(start + prof, 2),
                "profit": round(prof, 2), "today": round(float(st["cum"]), 2), "floor": round(start + float(st["floor"]), 2),
                "room": round(room, 2), "locked": bool(st.get("locked")), "target": t.get("ask_at_balance"), "target_label": "payout line",
                "to_target": t.get("to_ask"), "session": SZ.eval_session(F.get("start"), today), "status": status, "start": F.get("start"),
                "dll": float(R["dll"]), "max_micros": int(R["max_micros"]), "plan": self.spec["plan_label"],
                "price": PLANS[self.spec["plan"]]["price"], "eval_account": F.get("eval_account"), "funded": t}

    def _lifecycle(self, now):
        """Pass / fail / stuck: one push each (key per eval start). Funded: the payout tracker's pushes, each once."""
        ev = self.eval_view(now)
        stt = ev.get("status")
        if self.funded():
            try:
                from . import funded_life as FL
                t = ev.get("funded") or {}
                for p in FL.notices(t, now) if t else []:
                    if p["key"] in self.notified:
                        continue
                    self.notified.append(p["key"])
                    self.log("risk", f"{p['title']}: {t.get('text')}")
                    self._send(p)
            except Exception as e:
                self.log("error", f"funded tracker failed: {e.__class__.__name__}: {e}")
            if stt not in ("lost", "stuck"):
                return
            key = f"acctc:f{stt}:{(self.spec.get('funded') or {}).get('start') or '?'}:{self.name}"
            if key in self.notified:
                return
            self.notified.append(key)
            title = f"{self.label} funded account {stt}"
            body = (f"room ${ev.get('room') or 0:,.0f} to the max-loss floor: the bot stops trading this funded account. Buy a new 25K "
                    "eval for BLITZ when you want it back.")
            self.log("risk", f"{title}: {body}")
            self._push_text(title, body, key)
            return
        if stt not in ("passed", "failed", "stuck"):
            return
        key = f"acctc:{stt}:{self.spec.get('eval_start') or '?'}:{self.name}"
        if key in self.notified:
            return
        self.notified.append(key)
        txt = {"passed": (f"{self.label} EVAL PASSED \U0001F389", f"balance ${ev['balance']:,.0f} (target ${ev['target']:,.0f}): no new trade "
                                                                   "on this eval; request the funded account in the MFFU dashboard, then run "
                                                                   "the funded switch with its new Name: Start page > BLITZ · 25K > Passed → "
                                                                   f"funded, or {FUNDED_CMD}. The bot never switches by itself."),
               "failed": (f"{self.label} EVAL FAILED", f"balance ${ev['balance']:,.0f} reached the max-loss floor ${ev['floor']:,.0f}: no new "
                                                      "trade on this account"),
               "stuck": (f"{self.label} stuck: room ${ev['room']:,.0f}", f"the room to the max-loss floor is under ${float(self.spec['min_room']):,.0f} "
                                                                       "(2 x BLITZ's median stop-out): the bot stops trading this account; buy a new one")}[stt]
        self.log("risk", f"{txt[0]}: {txt[1]}")
        self._push_text(txt[0], txt[1], key)

    def check_lock(self, now):
        today = trading_day(now)
        pnl = self.day_pnl(today)
        lim = float(self.rules["dll"])
        if pnl <= -lim and not (self.lock and self.lock.get("day") == today):
            self.lock = {"day": today, "reason": f"soft daily loss: today ${pnl:,.0f} (limit ${lim:,.0f})"}
            self.log("risk", f"DAILY LOSS LOCK-OUT: {self.lock['reason']}: no new BLITZ entry on {self.name} today (LIT / ATLAS not affected)")
            self._push_text(f"{self.label}: locked out today", self.lock["reason"], f"acctc:lock:{today}")

    # ---- the performance contract (BLITZ_STRATEGY.md "Kill switch")
    def finished(self) -> list:
        """C's finished routed trades with their R and $ (voided / never-placed ones left out)."""
        return [{"day": c[0], "exit_t": c[1], "usd": float(c[2]), "r": float(c[4]), "entry_t": c[3]} for c in self.closes
                if len(c) > 4 and c[4] is not None]

    def scorecard(self) -> dict:
        try:
            s = score(self.finished())
        except Exception as e:
            s = {"status": "error", "why": [f"{e.__class__.__name__}: {e}"], "n": len(self.closes)}
        s["paused"] = self.paused
        s["resume_cmd"] = RESUME_CMD
        return s

    def _score_check(self, now):
        if self.paused:
            return
        s = self.scorecard()
        if s.get("status") != "below":
            return
        self.paused = {"t": int(now), "why": "; ".join(s["why"])[:300], "n": s.get("n"), "avg_r": s.get("avg_r"), "pf_r": s.get("pf_r")}
        key = f"acctc:pause:{int(now)}"
        self.notified.append(key)
        title = f"{self.label} PAUSED (performance contract)"
        body = (f"{self.paused['why']}. No new BLITZ entry on {self.name} until you resume it ({RESUME_CMD}); LIT and ATLAS keep trading. "
                f"{s.get('n')} trades, {s.get('win_pct')}% won, ${s.get('usd', 0):+,.0f}.")
        self.log("risk", f"{title}: {body}")
        self._push_text(title, body, key)
        self.save()

    def _resume_check(self, now):
        ra = self.spec.get("resume_after")
        if self.paused and ra is not None and float(ra) >= float(self.paused.get("t") or 0):
            self.log("system", f"performance-contract pause lifted by the owner ({RESUME_CMD}): BLITZ entries allowed again on {self.name}")
            self.paused = None
            self.save()

    # ---- the other accounts (no hedging; priority LIT > ATLAS > BLITZ)
    def opposite(self, d: int):
        """Why a C entry in direction d would be opposite to another account (None = not): LIT's open position, entry in
        progress, armed setup (limit / waiting for its 1m CISD), LIT's routed position, account B's position or close in
        flight, an extra account's position."""
        b = self.bot
        st = getattr(b, "state", None) or {}
        pos = st.get("position")
        if pos and int(pos.get("dir") or 0) == -d:
            return f"LIT is in a {_side(-d)} trade"
        en = st.get("enter_now")
        if en and int(en.get("dir") or 0) == -d:
            return f"LIT is entering {_side(-d)}"
        su = st.get("setups") or {}
        opp = "short" if d == 1 else "long"
        if su.get(opp):
            return f"LIT has a {_side(-d)} setup armed" + (" (waiting for its 1m CISD)" if su[opp].get("tapped_t") else " (limit working)")
        ot = getattr(b, "_open_routed", None)
        if ot is not None:
            e = next((r for r in reversed(getattr(b, "ledger", None) or []) if r.get("side") in ("buy", "sell") and r.get("entry_t") == ot), None)
            if e and (1 if e["side"] == "buy" else -1) == -d:
                return f"LIT's account holds a {_side(-d)} position"
        ab = getattr(b, "acct_b", None)
        if ab is not None:
            try:
                if ab.open_t is not None and int((ab.prov.get(int(ab.open_t)) or {}).get("dir") or 0) == -d:
                    return f"ATLAS (account B) holds a {_side(-d)} position"
                for _, pv in ab.closing_open():
                    if int(pv.get("dir") or 0) == -d:
                        return f"ATLAS (account B) is closing a {_side(-d)} position (not confirmed yet)"
            except Exception:
                return "account B state unreadable (fails closed)"
        ac = getattr(b, "accts", None)
        if ac is not None:
            try:
                h = ac.opposite_open(d, exclude=object())
                if h:
                    return h
            except Exception:
                pass
        return None

    def yield_to(self, d: int, who: str, sym: str, now: int, px=None, entry_t=None) -> bool:
        """LIT / ATLAS is about to enter in direction d: C open (or closing) the OTHER way -> closed at market FIRST (HEDGE).
        True = the other entry may route (C not opposite, or C's close CONFIRMED flat); False = not confirmed yet (it must
        not route now). C is never marked flat on an unconfirmed close."""
        try:
            self.reconcile_unplaced(now)
        except Exception as e:
            self.log("error", f"not-placed check failed: {e.__class__.__name__}: {e}")
        d = 1 if int(d or 1) == 1 else -1
        for et_, pv in self.closing_open():
            if int(pv.get("dir") or 0) == -d:
                self.settle_closing(sym, now)
        if any(int(pv.get("dir") or 0) == -d for _, pv in self.closing_open()):
            return False
        if self.open_t is None:
            return True
        et_ = int(self.open_t)
        pv = self.prov.get(et_) or {}
        if int(pv.get("dir") or 0) != -d:
            return True
        self.log("risk", f"no hedging: {who} enters {_side(d)}" + (f" at {_et(entry_t):%H:%M} ET" if entry_t else "")
                         + f" while BLITZ holds {_side(-d)} on {self.name}: BLITZ is closed at market before {who}'s order")
        if self.flatten(et_, "HEDGE", sym, now, px=px):
            pv["final"] = True
        return self.open_t is None or int(self.open_t) != et_

    # ---- the BLITZ engine
    def _engine(self):
        from . import blitz as BZ
        if self.eng_sig != self.rule_sig():
            self.eng, self.eng_sig = None, self.rule_sig()
        return BZ.Engine(self.eng, bool(self.spec.get("filtered", True)), self.spec.get("params"))

    def _warm(self, E, df1, now):
        """Cold start: the BLITZ paper shadow's own engine (same rule, kept since it started) when it is recent, else the
        last WARM_DAYS of 1m bars (the bot's 1m bars + data/NQ_1m.csv on the real bot). Nothing seen here is traded."""
        from . import blitz as BZ
        import pandas as pd
        if not self.spec.get("params") and self.spec.get("filtered", True) and getattr(self.bot, "state_path", None):
            try:
                with open(BZ.pc_path(self.bot.state_path), encoding="utf-8") as fh:
                    S = json.load(fh)
                e = (S or {}).get("eng")
                if isinstance(e, dict) and e.get("v") == BZ.VERSION and e.get("filter") is True and e.get("last_t") \
                        and int(now) - int(e["last_t"]) < 4 * 86400 and len(e.get("hist") or []) >= BZ.LOOKBACK:
                    E.s = json.loads(json.dumps(e))
                    self.warm = {"from": "the BLITZ paper shadow's engine", "last_t": int(e["last_t"])}
                    self.log("system", f"warmed from the BLITZ paper shadow's engine (last bar {_et(int(e['last_t'])):%m-%d %H:%M} ET)")
                    return
            except Exception:
                pass
        frames = []
        if self.real_bot() or (self.bot.cfg or {}).get("acct_c_history"):
            h = BZ.history_frame(since=int(now) - BZ.WARM_DAYS * 86400)
            if h is not None and len(h):
                frames.append(h[["time", "open", "high", "low", "close"]])
        if df1 is not None and len(df1):
            frames.append(df1[["time", "open", "high", "low", "close"]])
        if not frames:
            return
        m = pd.concat(frames).drop_duplicates("time", keep="last").sort_values("time")
        m = m[m["time"] >= int(now) - BZ.WARM_DAYS * 86400]
        bars = BZ._bars_of(m, None, int(now) - 120)          # up to the bar before the last closed one: that one is live
        n = 0
        if bars is not None:
            t, o, h, l, c = bars
            for i in range(len(t)):
                E.on_bar(int(t[i]), o[i], h[i], l[i], c[i])
            n = len(t)
        self.warm = {"from": "1m bars", "bars": n, "sessions": len(E.s.get("hist") or [])}
        self.log("system", f"warmed on {n} 1m bars ({len(E.s.get('hist') or [])} sessions of the noise band)")

    # ---- one poll
    def tick(self, df1, sym, now):
        """After LIT's routing and account B: C's poll. Feeds the closed 1m bars to BLITZ's Engine, routes its decisions,
        manages the open position. Never raises."""
        if self.problem or self.adapter is None:
            return
        try:
            now = int(now)
            self.reconcile_unplaced(now)
            self.settle_closing(sym, now)
            self._resume_check(now)
            if df1 is None or not len(df1):
                self.note(("bars",), "warn", "no 1m bars this poll: BLITZ waits (an open trade keeps its stop at NinjaTrader)")
            else:
                from . import blitz as BZ
                E = self._engine()
                if E.s.get("last_t") is None:
                    self._warm(E, df1, now)
                bars = BZ._bars_of(df1, int(E.s["last_t"]) if E.s.get("last_t") is not None else None, now - 60)
                if bars is not None and len(bars[0]):
                    t, o, h, l, c = bars
                    for i in range(len(t)):
                        self._events(E.on_bar(int(t[i]), o[i], h[i], l[i], c[i]), sym, now, bar=(int(t[i]), float(o[i])))
                self._events(E.on_clock(now), sym, now)
                self.eng = E.s
                self._trail(sym)
            self._clock_flat(sym, now)
            self._lifecycle(now)
            self.broker_tick(now)
        except Exception as e:
            self.log("error", f"account C failed this poll: {e.__class__.__name__}: {e} (LIT / ATLAS are not affected)")
            try:
                self.bot._note_error(f"account C (BLITZ) failed: {e.__class__.__name__}: {e}")
            except Exception:
                pass
        finally:
            self.save()

    def mark(self, sym, now, bar_t=None):
        """(price, estimated): the forming 1m bar's open at bar_t (NinjaTrader's feed), else the last price (estimated)."""
        t = int(bar_t if bar_t is not None else now - now % 60)
        fo = (getattr(self.bot, "_forming", None) or {}).get((sym, 60))
        if fo and int(fo[0]) == t and fo[1]:
            return float(fo[1]), False
        px = (getattr(self.bot, "state", None) or {}).get("price")
        return (float(px) if px else None), True

    def _row(self, et_=None, sig_t=None):
        for r in reversed(self.rows):
            if (et_ is not None and r.get("entry_t") == int(et_)) or (sig_t is not None and r.get("sig_t") == int(sig_t)):
                return r
        return None

    def _pv_of(self, sig_t):
        for et_, pv in self.prov.items():
            if int(pv.get("sig_t") or -1) == int(sig_t):
                return int(et_), pv
        return None, None

    def _events(self, evs, sym, now, bar=None):
        for x in evs or []:
            k = x.get("ev")
            if k == "signal":
                self.signals = (self.signals or [])[-39:] + [{kk: x.get(kk) for kk in ("t", "close_t", "date", "dir", "close", "band", "up", "lo",
                                                                                       "stop", "taken", "why")}]
                if x.get("taken"):
                    self._enter(x, sym, now)
            elif k == "entry":
                et_, pv = self._pv_of(x["sig_t"])
                r = self._row(sig_t=x["sig_t"])
                if r is not None:
                    r.update(model_entry_t=int(x["entry_t"]), entry=x["entry"], risk_pts=x["risk"], exit_kind=r.get("exit_kind") or "OPEN")
                if pv is not None:
                    pv.update(model_entry_t=int(x["entry_t"]), fill_model=float(x["entry"]), risk_model=float(x["risk"]), checked=True)
            elif k == "skip":
                et_, pv = self._pv_of(x["t"])
                r = self._row(sig_t=x["t"])
                if r is not None and r.get("exit_kind") in (None, "OPEN"):
                    r.update(exit_kind="NO TRADE", skip=r.get("skip") or x.get("why"))
                if pv is not None and not pv.get("final") and self.open_t is not None and int(self.open_t) == int(et_):
                    self.log("risk", f"BLITZ {_side(pv.get('dir'))} at {_et(et_):%H:%M} ET is not a model trade ({x.get('why')}): flattening")
                    if self.flatten(et_, "NO TRADE", sym, now):
                        pv["final"] = True
            elif k == "exit":
                self._on_exit(x, sym, now)
            elif k == "relabel":
                r = next((r for r in reversed(self.rows) if r.get("model_entry_t") == int(x["entry_t"])), None)
                if r is not None:
                    r["exit_kind"] = x["kind"]

    # ---- entries
    def _enter(self, x, sym, now):
        """A signal the Engine took at this bar's close: the entry is MARKET at the next bar's open = now. Routed unless an
        account rule, the no-hedging rule, the size or a guard blocks it (then the model trade still runs on paper)."""
        from . import blitz as BZ
        sig_t, D = int(x["t"]), (1 if int(x["dir"]) > 0 else -1)
        tb = sig_t + 60
        day = trading_day(tb)
        head = f"BLITZ {_side(D)} at the {_et(tb):%H:%M} ET open"
        row = {"id": f"BLZC:{tb}", "day": day, "sig_t": sig_t, "entry_t": tb, "dir": D, "side": _side(D), "close": x.get("close"),
               "band": x.get("band"), "stop": x.get("stop"), "qty": 0, "routed": False, "skip": None, "exit_kind": "OPEN", "decided_t": int(now)}
        self.rows = (self.rows + [row])[-400:]
        if ("entry", tb) in self.seen:
            return
        self.seen.add(("entry", tb))
        why = None
        age = int(now) - tb
        if age > MAX_AGE_S:
            why = f"seen {age} s after the entry bar opened (limit {MAX_AGE_S} s): not chasing"
        elif self.open_t is not None:
            why = "account C still holds a position"
        elif self.closing_open():
            why = "account C's last close is not confirmed yet"
        if not why and getattr(self.bot, "kill", False):
            why = "kill switch"
        if not why and (self.bot.health or {}).get("entries_blocked"):
            why = "feed stale"
        if not why:
            why = self.startup_block(now)
        if not why and getattr(self.bot, "_no_entries_day", None) == trading_day(now):
            why = "the owner flattened remotely today"
        if not why and self.paused:
            why = f"PAUSED by the performance contract ({self.paused.get('why')}); resume: {RESUME_CMD}"
        if not why and self.lock and self.lock.get("day") == day:
            why = f"locked out today: {self.lock['reason']}"
        if not why and self.entries_today(day) >= BZ.MAXDAY:
            why = f"{BZ.MAXDAY} BLITZ entries today already"
        if not why:
            ec = self._early_close(tb)
            if ec is not None and _et(tb).hour * 60 + _et(tb).minute >= ec - EC_ENTRY_MIN:
                why = f"CME early close at {ec // 60:02d}:{ec % 60:02d} ET: no entry in the last {EC_ENTRY_MIN} minutes"
        ev = self.eval_view(now) if not why else {}
        if not why and ev.get("status") in STOP_STATUSES:
            why = f"{'funded account' if self.funded() else 'eval'} {ev['status']} (balance ${ev.get('balance', 0):,.0f}, room ${(ev.get('room') or 0):,.0f})"
        if not why:
            h = self.opposite(D)
            if h:
                why = f"no hedging: {h}"
        px, est = self.mark(sym, now, bar_t=tb)
        ref = float(px) if px is not None else float(x["close"])
        fill = ref + D * TICK
        st = float(x["stop"])
        risk = D * (fill - st)
        if not why and risk < TICK:
            why = f"the open {ref:,.2f} is past the stop {st:,.2f}"
        sz = {"qty": 0, "reasons": []}
        if not why:
            try:
                sz = qty(self.spec, risk, self.eval_state(now))
            except Exception as e:
                sz = {"qty": 0, "reasons": [f"sizing failed ({e.__class__.__name__}: {e}): not traded"]}
            self.last_size = {"qty": sz["qty"], "reasons": [str(r)[:160] for r in sz["reasons"]][-4:], "t": int(now)}
            if sz["qty"] < 1:
                why = "size 0 (" + "; ".join(sz["reasons"][-2:]) + ")"
        tgr = float((self.spec.get("params") or {}).get("tgt_r", BZ.TGT_R))
        act = {"sym": sym, "side": "buy" if D == 1 else "sell", "qty": int(sz["qty"]), "stop": _tick(st, D),
               "target": _tick(fill + D * tgr * max(risk, TICK), D, target=True), "entry": fill, "entry_t": tb, "src": "blitz",
               "strategy": "BLITZ"}
        if not why:
            why = self.guard(act, tb, now)
        if why:
            row["skip"] = why
            self.log("risk", f"{head} NOT routed on {self.name}: {why} (the model trade runs on paper; BLITZ waits for it)")
            return
        q = int(sz["qty"])
        row.update(qty=q, routed=True, est=est, stop=act["stop"], target=act["target"])
        self.open_t = tb
        self.prov[tb] = {"key": "blitz", "short": "BLITZ", "qty": q, "dir": D, "est": est, "entry": fill, "stop": act["stop"],
                         "stop_now": act["stop"], "target": act["target"], "t": int(self.clock()), "risk_pts": risk, "day": day, "sig_t": sig_t}
        self.log("system", f"{head}: ROUTED MARKET {q} MNQ on {self.name} ({int(self.clock()) - tb} s after the open), stop {act['stop']:,.2f} "
                           f"(1.5 x 5m ATR), OCO limit {act['target']:,.2f} (20R); size {'; '.join(sz['reasons'][-1:])}")
        rr = self.route(act)
        if rr.get("ok") is not False:
            self._push_entry(act, q)
        elif self.never_placed(tb, rr):
            self._drop_unplaced(tb, rr, now)
        else:
            self._unconfirmed(tb, rr)

    @staticmethod
    def _early_close(t):
        try:
            from .lit_live import early_close
            return early_close(_et(t).date().isoformat())
        except Exception:
            return None

    # ---- the open position
    def _model_pv(self, model_entry_t):
        for et_, pv in self.prov.items():
            if int(pv.get("model_entry_t") or -1) == int(model_entry_t):
                return int(et_), pv
        return None, None

    def _on_exit(self, x, sym, now):
        et_, pv = self._model_pv(x["entry_t"])
        r = next((r for r in reversed(self.rows) if r.get("model_entry_t") == int(x["entry_t"])), None)
        if r is not None:
            r.update(exit_t=int(x["exit_t"]), exit=x["exit"], exit_kind=x["kind"], pts=round(float(x["pts"]), 2), r=round(float(x["r"]), 4),
                     risk_pts=x["risk"], bars=x.get("bars"))
        if pv is None or pv.get("final"):
            return
        q = int(pv.get("qty") or 0)
        pnl = round(q * float(x["pnl_pm"]), 2)
        reason = EXIT_REASON.get(str(x["kind"]), str(x["kind"]).upper())
        is_open = self.open_t is not None and int(self.open_t) == int(et_)
        cl = pv.get("closing") or {}
        if cl and not cl.get("done"):
            pv["model_done"] = True
            return                                       # a close in flight: settle_closing books it
        if is_open:
            self.seen.add(("exit", int(et_)))
            if (self.bot.cfg or {}).get("adapter") == "paper" or reason == "TIME" or getattr(self.adapter, "route_all_exits", False):
                res = self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "pnl": pnl, "entry_t": int(et_),
                                  "exit_t": int(x["exit_t"]), "src": "blitz", "strategy": "BLITZ"})
                if reason == "TIME" and not self._close_ok(res, et_):
                    pv["closing"] = {"reason": reason, "t": int(now), "last": int(now), "px": x["exit"], "pnl": pnl, "q": q, "done": False,
                                     "tries": 1, "error": str((res or {}).get("error") or "no flat confirmation")[:160], "r": float(x["r"])}
                    self.log("risk", f"CLOSE NOT CONFIRMED (TIME): BLITZ {q} MNQ on {self.name}: {pv['closing']['error']} - re-sent")
                    self._push_text(f"{self.label}: CLOSE NOT CONFIRMED (TIME)", f"{q} MNQ on {self.name} may still be open "
                                    f"({pv['closing']['error']}). The bot re-sends the close; check NinjaTrader.", f"acctc:closing:{int(et_)}")
                    return
            self.open_t = None
            pv["flat"] = {"reason": reason, "t": int(now), "px": x["exit"]}
            self._close(int(et_), int(x["exit_t"]), pnl, now, r=float(x["r"]))
            if r is not None:
                r["usd"] = pnl
            self._push_outcome(pv, reason, pnl, x["exit_t"], q, int(et_))
        else:
            fl = pv.get("flat") or {}
            if fl.get("reason") == "TIME" and reason == "TIME":   # the clock flattened it first: the model's own 15:55 price
                with self.mx:
                    for row in reversed(self.ledger):
                        if row.get("side") == "exit" and row.get("entry_t") == int(et_) and row.get("pnl_est"):
                            row["pnl"], row["pnl_est"], row["pnl_model"] = pnl, False, True
                            break
                    for c in self.closes:
                        if len(c) > 3 and int(c[3]) == int(et_):
                            c[2] = pnl
                            if len(c) > 4:
                                c[4] = float(x["r"])
                if r is not None:
                    r["usd"] = pnl
            elif r is not None:
                c = next((c for c in self.closes if len(c) > 3 and int(c[3]) == int(et_)), None)
                r["usd"] = float(c[2]) if c else 0.0
                r["closed_early"] = fl.get("reason")
        pv["final"] = True

    def _trail(self, sym):
        """The model's trailed stop -> a stop CHANGE at NinjaTrader (only ever tighter; 3 refusals = give up + push)."""
        E = self.eng or {}
        p = E.get("pos")
        if not p or self.open_t is None or not getattr(self.adapter, "route_stop_moves", False):
            return
        et_ = int(self.open_t)
        pv = self.prov.get(et_) or {}
        if pv.get("final") or int(pv.get("model_entry_t") or -1) != int(p.get("entry_t") or -2):
            return
        if (pv.get("closing") or {}) and not pv["closing"].get("done"):
            return
        self._stop_move(et_, pv, float(p["stp"]), sym)

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
            self.log("risk", f"broker refused the trail to {new:.2f} three times: check BLITZ's stop on {self.name} by hand")
            self._push_text(f"{self.label}: trail NOT accepted", f"NinjaTrader refused the stop move to {new:.2f} three times; the old stop "
                            "stays. Check the stop in NinjaTrader.", f"acctc:trail:{et_}:{new}")
            return
        reason = "BE" if (float(new) - float(pv.get("fill_model") or pv.get("entry") or new)) * d >= 0 else "STOP MOVE"
        res = self.route({"sym": sym, "side": "modify", "qty": int(pv.get("qty") or 0), "stop": new, "reason": reason, "entry_t": et_,
                          "src": "blitz"})
        if (res or {}).get("ok"):
            pv["stop_now"] = new

    def _flat_t(self, day):
        from zoneinfo import ZoneInfo
        d = _dt.date.fromisoformat(day)
        ec = self._early_close(int(_dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()))
        mod = 955 if ec is None else min(955, ec - EC_FLAT_MIN)
        t = int(_dt.datetime.combine(d, _dt.time(mod // 60, mod % 60), ZoneInfo("America/New_York")).timestamp())
        return t + (FLAT_GRACE_S if ec is None else 0)

    def _clock_flat(self, sym, now):
        """The clock's safety: 15:55 (+60 s for a late bar) or 5 minutes before a CME early close, C still open -> flat."""
        if self.open_t is None:
            return
        et_ = int(self.open_t)
        pv = self.prov.get(et_) or {}
        if (pv.get("closing") or {}) and not pv["closing"].get("done"):
            return
        try:
            if int(now) >= self._flat_t(pv.get("day") or trading_day(et_)):
                self.flatten(et_, "TIME", sym, now)
        except Exception as e:
            self.log("error", f"clock flatten check failed: {e.__class__.__name__}: {e}")

    # ---- an entry the broker never took (as account B, engine/ninjatrader.entry_never_placed)
    def entry_result(self, et_):
        r = next((r for r in reversed(self.ledger) if r.get("side") in ("buy", "sell") and r.get("entry_t") == int(et_)), None)
        return (r or {}).get("result") if r else None

    def never_placed(self, et_, res=None) -> bool:
        from .ninjatrader import entry_never_placed
        return entry_never_placed(self.adapter, et_, res if isinstance(res, dict) else self.entry_result(et_), now=self.clock())

    def _drop_unplaced(self, et_, res, now):
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
        row = self._row(et_=et_)
        if row is not None:
            row.update(routed=False, skip=f"order NOT placed: {err}", usd=0.0, not_placed=True)
        what = f"BLITZ {_side(pv.get('dir'))} {pv.get('qty') or ''} MNQ at {_et(et_):%H:%M} ET"
        self.log("risk", f"{what} was NOT PLACED on {self.name}: {err}. Nothing is open on account C; BLITZ waits for its next signal.")
        key = f"acctc:notplaced:{et_}"
        if key not in self.notified:
            self.notified.append(key)
            self._push_text(f"{self.label}: order NOT placed", f"{what} did not go in ({err}). Nothing is open on {self.name}, no money "
                            "at risk. BLITZ keeps looking for its next signal.", key)
        self.save()

    def _unconfirmed(self, et_, res):
        from .accounts import clean_text
        et_ = int(et_)
        err = clean_text((res or {}).get("error") or "no OK from NinjaTrader", 200)
        self.log("risk", f"entry at {_et(et_):%H:%M} ET NOT CONFIRMED on {self.name}: {err}. It may be open: account C keeps it and "
                         "manages it to its exit.")
        key = f"acctc:unconfirmed:{et_}"
        if key not in self.notified:
            self.notified.append(key)
            self._push_text(f"{self.label}: order NOT confirmed", f"Entry at {_et(et_):%H:%M} ET on {self.name}: {err}. It may be open: "
                            "check NinjaTrader.", key)

    def reconcile_unplaced(self, now):
        if not getattr(self, "_unplaced_scanned", False):
            self._unplaced_scanned = True
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
        """C routes no entry until, once, its OWN NinjaTrader account reconciles (as account B). Paper: no gate."""
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
            probs = [f"account C startup check failed ({e.__class__.__name__}: {e})"]
        if probs:
            self.note(("startup",), "risk", "STARTUP DISARMED on account C (no new entries yet): " + "; ".join(probs))
            return "STARTUP DISARMED until reconciled: " + "; ".join(probs)
        self._startup_ok = int(now)
        self.log("system", f"STARTUP RECONCILED on {self.name}: NinjaTrader positions / orders and contract check out; entries allowed")
        return None

    def guard(self, act, entry_t, now):
        """C's own guards: CME calendar / session, order sanity (20 micros), the bot's clock check, Tier-1 news (when on),
        the owner's pause. None = route. Fails closed."""
        try:
            from . import guards as G
            c = G.config(self.bot)
            out = []
            if c.get("calendar"):
                out += G.calendar(int(entry_t), int(now), session_from=120, flat_mod=955)
            if c.get("order_sanity"):
                out += G.sanity(act, act["qty"], int(self.rules["max_micros"]), {**c, "max_stop_pts": MAX_STOP_PTS})
            p = G.clock_problem(self.bot, c)
            if p:
                out.append(p)
            if c.get("news"):
                h = G.news_hit(int(now), int(c.get("news_min") or 2))
                if h:
                    out.append(f"Tier-1 news within {int(c.get('news_min') or 2)} min: {h}")
            out += G._owner_blocks(self.bot, c, int(now))
            return "GUARD " + "; ".join(out) if out else None
        except Exception as e:
            self.log("error", f"guards failed ({e.__class__.__name__}: {e}): entry NOT routed (account C fails closed)")
            return "guards failed"

    # ---- closing
    def flatten(self, et_, reason, sym, now, px=None):
        """Close C's position at market now (HEDGE, TIME clock, NO TRADE, kill, remote flatten); $ from the market now
        (the model's own exit price replaces it for a 15:55 flat)."""
        pv = self.prov.get(int(et_)) or {}
        q = int(pv.get("qty") or 0)
        if px is None:
            px, _ = self.mark(sym, now)
        d = int(pv.get("dir") or 1)
        e = pv.get("fill_model") or pv.get("entry")
        pnl = round(q * (d * (float(px) - d * TICK - float(e)) * PV - COMM), 2) if px is not None and e is not None else 0.0
        risk = _num(pv.get("risk_model") or pv.get("risk_pts"))
        r_ = None
        if px is not None and e is not None and risk:
            from . import blitz as BZ
            r_ = round(BZ.trade_r(d * (float(px) - d * TICK - float(e)), float(risk)), 4)
        self.seen.add(("exit", int(et_)))
        self.log("risk" if reason in ("HEDGE", "NO TRADE", "KILL SWITCH") else "system",
                 f"BLITZ {_et(int(et_)):%H:%M} ET: {reason} - flatten {q} MNQ at market" + (f" (~{px:,.2f})" if px is not None else ""))
        res = self.route({"sym": sym, "side": "exit", "qty": q, "reason": reason, "entry_t": int(et_), "exit_t": int(now), "pnl": pnl,
                          "pnl_est": True, "src": "blitz", "strategy": "BLITZ"})
        if not self._close_ok(res, et_):
            first = not pv.get("closing")
            pv["closing"] = {"reason": reason, "t": int(now), "last": int(now), "px": px, "pnl": pnl, "q": q, "done": False, "r": r_,
                             "tries": int((pv.get("closing") or {}).get("tries") or 0) + 1,
                             "error": str((res or {}).get("error") or "no flat confirmation")[:160]}
            self.log("risk", f"CLOSE NOT CONFIRMED ({reason}): BLITZ {q} MNQ on {self.name}: {pv['closing']['error']} - account C is NOT "
                             "marked flat, the close is re-sent")
            if first:
                self._push_text(f"{self.label}: CLOSE NOT CONFIRMED ({reason})", f"{q} MNQ on {self.name} may still be open "
                                f"({pv['closing']['error']}). The bot re-sends the close and holds the other account's opposite entry; "
                                "check NinjaTrader.", f"acctc:closing:{int(et_)}")
            self.save()
            return False
        self._finish_close(int(et_), pv, reason, px, pnl, q, now, r_)
        return True

    def _close_ok(self, res, et_) -> bool:
        r = res if isinstance(res, dict) else {}
        if r.get("ok") is False or r.get("flat_confirmed") is False:
            return False
        return self.flat_confirmed(et_) is not False

    def flat_confirmed(self, et_):
        legs = getattr(self.adapter, "legs", None)
        if not isinstance(legs, list):
            return None
        from .ninjatrader import OPEN_STATUSES
        return not any(int(lg.get("entry_t") or 0) == int(et_) and lg.get("status") in OPEN_STATUSES for lg in legs)

    def _finish_close(self, et_, pv, reason, px, pnl, q, now, r_=None):
        pv["flat"] = {"reason": reason, "t": int(now), "px": px}
        if pv.get("closing"):
            pv["closing"]["done"] = True
        if self.open_t is not None and int(self.open_t) == int(et_):
            self.open_t = None
        self._close(int(et_), int(now), pnl, now, r=r_)
        row = self._row(et_=et_)
        if row is not None:
            row["usd"] = pnl
            row["closed_early"] = reason
        self._push_outcome(pv, reason, pnl, int(now), q, int(et_))

    def settle_closing(self, sym, now):
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
                                      "entry_t": int(et_), "exit_t": int(now), "pnl": cl.get("pnl"), "pnl_est": True, "src": "blitz",
                                      "strategy": "BLITZ", "retry": cl["tries"]})
                    ok = self._close_ok(res, et_)
                    if not ok:
                        cl["error"] = str((res or {}).get("error") or "no flat confirmation")[:160]
                if ok:
                    self.log("risk", f"close confirmed ({cl['reason']}): BLITZ on {self.name} is flat after {int(cl.get('tries') or 1)} tries")
                    self._finish_close(int(et_), pv, cl["reason"], cl.get("px"), float(cl.get("pnl") or 0.0), int(cl.get("q") or 0), now,
                                       cl.get("r"))
                    if cl["reason"] in ("HEDGE", "NO TRADE", "KILL SWITCH") or pv.get("model_done"):
                        pv["final"] = True
                    self.save()
            except Exception as e:
                self.log("error", f"close settle failed: {e.__class__.__name__}: {e}")

    def closing_open(self) -> list:
        return [(et_, pv) for et_, pv in sorted(self.prov.items()) if (pv.get("closing") or {}) and not pv["closing"].get("done")]

    def _close(self, entry_t, exit_t, pnl, now, r=None):
        with self.mx:
            if any(len(c) > 3 and int(c[3]) == int(entry_t) for c in self.closes):
                return
            self.closes.append([trading_day(exit_t), int(exit_t), float(pnl), int(entry_t), None if r is None else float(r)])
            self.closes = self.closes[-1500:]
        self.check_lock(now)
        self._score_check(now)
        self.save()

    def kill(self, sym):
        try:
            if self.adapter is None:
                return {"ok": False, "error": "no adapter"}
            if self.open_t is not None:
                et_ = int(self.open_t)
                if self.flatten(et_, "KILL SWITCH", sym, int(self.clock())):
                    (self.prov.get(et_) or {})["final"] = True
                return (self.ledger[-1].get("result") or {"ok": True}) if self.ledger else {"ok": True}
            if getattr(self.adapter, "kill_flattens_all", False):
                return self.route({"sym": sym, "side": "exit", "reason": "KILL SWITCH", "entry_t": None})
            return {"ok": True, "note": "flat"}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    # ---- pushes (the real bot only: LiveBot._push_send)
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
            if getattr(self.adapter, "reports_fills", False):
                return
            p = push.entry_payload(f"{self.label} ({self.real_word()})", "LONG" if act["side"] == "buy" else "SHORT", q, act["entry_t"], src="pc",
                                   entry=act.get("entry"), stop=act.get("stop"), target=act.get("target"), strategy="BLITZ")
            p["body"] = f"{p['body']} (BLITZ scalp)"
            p["key"] = f"{p['key']}:acctc"
            self._send(p)
        except Exception:
            pass

    def _push_outcome(self, pv, reason, usd, exit_t, q, et_):
        try:
            from . import push
            if getattr(self.adapter, "reports_fills", False) and reason not in ("HEDGE", "NO TRADE", "TIME", "KILL SWITCH"):
                return
            p = push.outcome_payload(f"{self.label} ({self.real_word()})", _side(pv.get("dir")), reason, usd, int(et_), exit_t, src="pc",
                                     qty=q, strategy="BLITZ")
            p["body"] = f"{p['body']} (BLITZ scalp)"
            p["key"] = f"{p['key']}:acctc"
            self._send(p)
        except Exception:
            pass

    # ---- views
    def position(self):
        if self.open_t is None:
            return None
        pv = self.prov.get(int(self.open_t)) or {}
        return {"entry_t": int(self.open_t), "dir": pv.get("dir"), "side": _side(pv.get("dir")), "qty": pv.get("qty"),
                "entry": pv.get("fill_model") or pv.get("entry"), "stop": pv.get("stop_now") or pv.get("stop"), "target": pv.get("target"),
                "strategy": "BLITZ", "key": "blitz",
                "time_exit_t": int(self.open_t) + 60 * (int((self.spec.get("params") or {}).get("hold", 30)) + 1)}

    def state_text(self, now=None) -> dict:
        from . import blitz as BZ
        now = int(now if now is not None else self.clock())
        dis = self.disabled_reason()
        if dis:
            return {"stage": "off", "text": f"Account C off: {dis}"}
        if self.paused:
            return {"stage": "paused", "text": f"PAUSED by the performance contract: {self.paused.get('why')}. Resume: {RESUME_CMD}"}
        if self.open_t is not None:
            p = self.position() or {}
            return {"stage": "trade", "text": f"{self.real_word()} {p.get('side')} {p.get('qty')} MNQ from {p.get('entry') or 0:,.2f}, stop "
                                             f"{p.get('stop') or 0:,.2f}; out by {_et(p['time_exit_t']):%H:%M} ET at the latest."}
        E = self.eng or {}
        if E.get("last_t") is None:
            return {"stage": "waiting", "text": "Waiting for 1m bars (NinjaTrader feed) to warm up BLITZ's noise band."}
        try:
            S = {"eng": E, "t": now, "ledger": [], "ledger50": []}
            return BZ.state_text(S, now)
        except Exception:
            return {"stage": "waiting", "text": "BLITZ waits for its next check (11:00, 11:30 ... 15:30 ET)."}

    def info(self, now=None) -> dict:
        """Heartbeat / live.json / dashboards / narrator: "BLITZ <name>" with its eval tracker, scorecard and today's rows."""
        from . import account_b as AB
        now = int(now if now is not None else self.clock())
        today = trading_day(now)
        rows = [{**{k: r.get(k) for k in ("t", "side", "qty", "reason", "pnl", "entry_t", "src", "strategy", "stop", "target")},
                 **AB._answer(r)} for r in self.ledger if r.get("side") in ("buy", "sell", "exit", "modify")][-10:]
        tr = [{k: r.get(k) for k in ("id", "day", "entry_t", "dir", "side", "qty", "routed", "skip", "entry", "stop", "target", "exit_t",
                                      "exit", "exit_kind", "usd", "r", "not_placed", "closed_early")} for r in self.rows if r.get("day") == today][-8:]
        ev = self.eval_view(now)
        out = {"label": self.label, "account": self.name, "plan": self.spec["plan"], "plan_label": self.spec["plan_label"], "kind": self.kind(),
               "real": self.real_word(), "strategy": "BLITZ", "enabled": not self.disabled_reason(), "disabled": self.disabled_reason(),
               "armed": bool(self.spec.get("armed")), "eval": ev if not isinstance(ev, dict) else {k: v for k, v in ev.items() if k != "funded"},
               "open": self.position(), "routed": rows, "trades_today": tr, "day_pnl": self.day_pnl(today),
               "entries_today": self.entries_today(today), "locked": (self.lock or {}).get("reason") if (self.lock or {}).get("day") == today else None,
               "size": self.last_size, "paused": self.paused, "scorecard": self.scorecard(), "state": self.state_text(now),
               "params": self.spec.get("params"), "filtered": bool(self.spec.get("filtered", True)),
               "signals": [s for s in self.signals if s.get("date") == _et(now).date().isoformat()][-8:],
               "note": "own account: BLITZ only, one position, up to 6 trades a day, never opposite to LIT or ATLAS (LIT > ATLAS > BLITZ)"}
        if self.funded():
            out.update(stage="funded", funded=AB.compact_tracker((ev or {}).get("funded")),
                       eval_account=(self.spec.get("funded") or {}).get("eval_account"))
        return out

    def days(self, now=None) -> dict:
        """Closed P&L per trading day since the eval start (funded: the funded start); "0000-00-00" = $ before the bot."""
        now = int(now if now is not None else self.clock())
        start = (self.spec.get("funded") or {}).get("start") if self.funded() else self.spec.get("eval_start")
        out = {}
        for c in self.closes:
            if not start or str(c[0]) >= str(start):
                out[str(c[0])] = round(out.get(str(c[0]), 0.0) + float(c[2]), 2)
        if self.spec.get("prior_pnl") and not self.funded():
            out["0000-00-00"] = float(self.spec["prior_pnl"])
        return out

    def closed_rows(self, n: int = 60) -> list:
        """The last n closed routed trades (Accounts page / live board): day, entry / exit time, side, micros, $, R, reason."""
        out = []
        for c in self.closes[-n:]:
            et_ = int(c[3]) if len(c) > 3 and c[3] is not None else None
            pv = self.prov.get(et_) or {}
            fl = pv.get("flat") or {}
            row = self._row(et_=et_) or {}
            out.append({"day": c[0], "entry_t": et_, "exit_t": int(c[1]), "dir": pv.get("dir"), "side": _side(pv.get("dir")), "qty": pv.get("qty"),
                        "entry": pv.get("fill_model") or pv.get("entry"), "stop": pv.get("stop"), "target": pv.get("target"),
                        "exit": row.get("exit") if row.get("exit") is not None else fl.get("px"),
                        "exit_kind": fl.get("reason") or row.get("exit_kind"), "pnl": round(float(c[2]), 2), "usd": round(float(c[2]), 2),
                        "r": c[4] if len(c) > 4 else None, "strategy": "BLITZ", "src": "blitz"})
        return out

    def hb_block(self, now=None) -> dict:
        """The heartbeat / live.json "account_c" block (secret-free: no paths, no phrase)."""
        from .accounts import clean_text
        now = int(now if now is not None else self.clock())
        out = self.info(now)
        out["disabled"] = clean_text(out.get("disabled"), 200)
        out["days"] = self.days(now)
        out["closed"] = self.closed_rows(60)
        out["rules"] = {k: self.rules.get(k) for k in ("start", "target", "mll", "lock", "dll", "max_micros")}
        out["t"] = now
        st = out.get("state") or {}
        out["state"] = {"stage": st.get("stage"), "text": clean_text(st.get("text"), 240)}
        return out

    # ---- persistence
    def blob(self) -> dict:
        with self.mx:
            out = {"v": VERSION, "account": self.name, "plan": self.spec["plan"], "eval_start": self.spec.get("eval_start"),
                   "saved_at": int(self.clock()), "ledger": self.ledger[-400:], "closes": list(self.closes),
                   "prov": {str(k): v for k, v in self.prov.items()}, "open_t": self.open_t, "seen": [list(x) for x in list(self.seen)[-600:]],
                   "lock": self.lock, "paused": self.paused, "notified": self.notified[-80:], "eng": self.eng, "eng_sig": self.eng_sig,
                   "rows": self.rows[-400:], "signals": self.signals[-40:], "warm": self.warm}
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
            _replace(tmp, self.state_path)
        except Exception as e:
            self.log("warn", f"state save failed: {e.__class__.__name__}: {e}")

    def _load(self):
        if not self.state_path:
            return
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                b = json.load(fh)
        except Exception:
            return
        if not isinstance(b, dict) or b.get("account") != self.name:
            return
        self.closes = [list(c) + [None] * (5 - len(c)) for c in (b.get("closes") or []) if isinstance(c, (list, tuple)) and len(c) >= 3]
        self.ledger = list(b.get("ledger") or [])
        self.prov = {int(k): v for k, v in (b.get("prov") or {}).items() if isinstance(v, dict)}
        self.open_t = b.get("open_t")
        self.seen = {tuple(x) for x in b.get("seen") or []}
        self.notified = list(b.get("notified") or [])
        self.paused = b.get("paused") if isinstance(b.get("paused"), dict) else None
        self.rows = list(b.get("rows") or [])
        self.signals = list(b.get("signals") or [])
        self.warm = b.get("warm")
        if b.get("eng_sig") == self.rule_sig() and isinstance(b.get("eng"), dict):
            self.eng, self.eng_sig = b["eng"], b["eng_sig"]
        lk = b.get("lock")
        self.lock = lk if lk and lk.get("day") == trading_day(self.clock()) else None
        if self.open_t is not None:
            pv = self.prov.get(int(self.open_t)) or {}
            self.log("system", f"restored: open BLITZ {_side(pv.get('dir'))} {pv.get('qty')} MNQ from {_et(int(self.open_t)):%H:%M} ET "
                               "(managed to its exit)")


def _state_path_for(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_acctc" + (ext or ".json")


def build(bot, blk: dict | None, **kw):
    """LiveBot: account C from the account_c block (None when off)."""
    if not isinstance(blk, dict) or not blk:
        return None
    lit_acct = None
    try:
        if (bot.cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(bot.cfg)
    except Exception:
        lit_acct = None
    b_acct = getattr(getattr(bot, "acct_b", None), "name", None)
    spec = normalize(blk, lit_account=lit_acct, b_account=b_acct)
    return AccountC(bot, spec, **kw).start() if spec else None


# ---------------------------------------------------------------------------------------------------------------- switches
def _selftest_ok():
    from . import second
    return second._selftest_ok()


def _names_in_use(root: str | None = None) -> tuple:
    """(LIT's 50K Name, ATLAS's 25K Name) on this PC: data/start_bot.json / data/autostart.json and account B's block."""
    r = root or ROOT
    lit = atlas = None
    for f, k in (("start_bot.json", "lit"), ("autostart.json", "nt_account")):
        try:
            v = str(json.load(open(os.path.join(r, "data", f), encoding="utf-8")).get(k) or "").strip()
            if v and not lit:
                lit = v
        except Exception:
            pass
    try:
        atlas = str(json.load(open(os.path.join(r, "data", "start_bot.json"), encoding="utf-8")).get("atlas") or "").strip() or None
    except Exception:
        pass
    try:
        from . import account_b as AB
        b = AB.raw_cfg(os.path.join(r, "second_model.json")) if os.path.exists(os.path.join(r, "second_model.json")) else None
        atlas = str((b or {}).get("account") or "").strip() or atlas
    except Exception:
        pass
    return lit, atlas


def set_account_c(account: str | None, plan: str = "builder25k", start: str | None = None, root: str | None = None, selftest=None,
                  extra: dict | None = None, lit_account: str | None = None, b_account: str | None = None) -> dict:
    """data/account_c.json = {...} (account set) or null (account None / "off"). Switching on is refused when the block is
    invalid (unknown plan, LIT's or ATLAS's own account, a bad day / params) or engine.ninjatrader --selftest fails. The
    same account again keeps its funded stage, params and scorecard resume (arming, a new start day)."""
    old = raw_cfg(root)
    if account is None or str(account).strip().lower() in ("off", "none", ""):
        new = None
    else:
        new = {"account": str(account).strip(), "plan": plan or "builder25k", "eval_start": start or _dt.date.today().isoformat(),
               "armed": False}
        new.update({k: v for k, v in (extra or {}).items() if k not in ("account", "plan", "eval_start")})
        if isinstance(old, dict) and str(old.get("account") or "").strip() == new["account"]:
            for k in ("params", "unfiltered", "resume_after", "prior_pnl", "eval_anchor") + FUNDED_KEYS:
                if k in old and k not in new:
                    new[k] = old[k]
            if str(old.get("stage") or "").lower() == "funded":
                new["eval_start"] = old.get("eval_start") or new["eval_start"]
        lit, atlas = (lit_account, b_account) if (lit_account is not None or b_account is not None) else _names_in_use(root)
        spec = normalize(new, lit_account=lit, b_account=atlas)
        if spec["problem"]:
            return {"ok": False, "error": spec["problem"]}
        ok, line = (selftest or _selftest_ok)()
        if not ok:
            return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): account C NOT switched on"}
    write_local(new, root)
    if raw_cfg(root) != new:
        return {"ok": False, "error": f"{LOCAL_REL} write check failed: account C not changed"}
    sim = None
    if new:
        from .ninjatrader import is_sim
        sim = is_sim(new["account"])
    return {"ok": True, "from": old, "to": new, "sim": sim}


def arm(account: str, root: str | None = None, selftest=None) -> dict:
    """account_c "armed": true on the saved account (a real account C also needs it). Called ONLY after the owner typed the
    LIVE phrase (engine/go.py's arm step); every other field is kept."""
    blk = raw_cfg(root) or {}
    if str(blk.get("account") or "").strip() != str(account or "").strip():
        return {"ok": False, "error": f"account C is {blk.get('account')!r}, not {account!r}"}
    if blk.get("armed") is True:
        return {"ok": True, "already": True}
    keep = {k: v for k, v in blk.items() if k not in ("account", "plan", "eval_start")}
    return set_account_c(blk["account"], plan=blk.get("plan") or "builder25k", start=blk.get("eval_start"), root=root, selftest=selftest,
                         extra={**keep, "armed": True})


def resume(root: str | None = None) -> dict:
    """The owner's resume after a performance-contract pause: "resume_after" = now in the block (the bot lifts the pause
    at its next poll; nothing else changes)."""
    blk = raw_cfg(root)
    if not isinstance(blk, dict):
        return {"ok": False, "error": "account C is off: nothing to resume"}
    new = {**blk, "resume_after": int(_time.time())}
    write_local(new, root, why="Resumed by the owner after a performance-contract pause.")
    return {"ok": True, "say": f"BLITZ on {blk.get('account')}: the pause is lifted at the bot's next poll."}


def state_file(root: str | None = None) -> str:
    return os.path.join(root or ROOT, "data", "live_state_acctc.json")


def to_funded(account: str, start: str, balance=None, root: str | None = None, selftest=None, allow_path: str | None = None,
              lit_account: str | None = None, b_account: str | None = None, today: str | None = None, allow: bool = True) -> dict:
    """The funded switch (owner-run, never automatic): BLITZ's passed eval -> its NEW funded account (MFFU gives a new Name).
    The block becomes stage "funded" on the funded Name from `start`, DISARMED; the eval's Name kept as "eval_account" and
    its state file as live_state_acctc.eval_<Name>.json; the funded Name allowlisted."""
    old = raw_cfg(root)
    if not isinstance(old, dict) or not str(old.get("account") or "").strip():
        return {"ok": False, "error": "BLITZ has no account yet (account C is off): nothing to switch to funded"}
    name = str(account or "").strip()
    if not name or any(c in name for c in ";,\r\n|"):
        return {"ok": False, "error": "type the funded account's Name exactly as NinjaTrader's Accounts tab shows it"}
    cur = str(old.get("account")).strip()
    stage = str(old.get("stage") or "eval").strip().lower()
    if stage == "funded" and name != cur:
        return {"ok": False, "error": f"BLITZ is already funded on {cur}: a new funded account needs a new eval first"}
    if stage != "funded" and name == cur:
        return {"ok": False, "error": f"{name} is the eval account: MFFU gives the funded account its own new Name"}
    try:
        start = _dt.date.fromisoformat(str(start)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "the first funded day as yyyy-mm-dd"}
    from . import multi_account as MA
    R = MA.rules_of({"preset": PLANS["builder25k"]["preset"]})
    bal = float(R["start"]) if balance in (None, "") else _num(balance)
    if bal is None:
        return {"ok": False, "error": f"balance {balance!r} is not a number of $"}
    new = {k: v for k, v in old.items() if k not in ("armed", "confirm", "eval_anchor", "prior_pnl", "resume_after") + FUNDED_KEYS}
    new.update(account=name, stage="funded", funded_start=start, funded_balance=round(float(bal), 2),
               payouts=dict(old.get("payouts") or {}) if stage == "funded" else {},
               eval_account=(old.get("eval_account") if stage == "funded" else cur) or None, funded_set=today or _dt.date.today().isoformat(),
               armed=False)
    lit, atlas = (lit_account, b_account) if (lit_account is not None or b_account is not None) else _names_in_use(root)
    spec = normalize(new, lit_account=lit, b_account=atlas)
    if spec["problem"]:
        return {"ok": False, "error": spec["problem"]}
    ok, line = (selftest or _selftest_ok)()
    if not ok:
        return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): BLITZ NOT switched to funded"}
    archived = None
    if stage != "funded":
        sp = state_file(root)
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
    write_local(new, root, why=f"Funded on {name} from {start} (passed eval {new.get('eval_account') or cur}).")
    allowed = None
    if allow:
        from .ninjatrader import allow_account
        allowed = allow_account(name, path=allow_path)
    from .ninjatrader import is_sim
    return {"ok": True, "from": old, "to": new, "archived": archived, "allowlist": allowed, "sim": is_sim(name),
            "rule": "10% of the room to the floor, at most $150 a trade, no new trade after +$400 on the day, the $600 daily loss, 20 micros",
            "say": f"BLITZ -> funded {name} from {start} (balance ${float(bal):,.0f}; passed eval {new.get('eval_account') or cur}). NOT armed: "
                   "a real account trades only after you arm it (you type the phrase)."}


def record_payout(spec_s: str, root: str | None = None) -> dict:
    d, _, v = str(spec_s or "").partition("=")
    try:
        d = _dt.date.fromisoformat(d.strip()).isoformat()
        amt = round(float(v), 2)
        if not amt > 0:
            raise ValueError
    except (TypeError, ValueError):
        return {"ok": False, "error": "give the payout as yyyy-mm-dd=$ (e.g. 2026-12-01=1000)"}
    old = raw_cfg(root)
    if not isinstance(old, dict) or str(old.get("stage") or "").lower() != "funded":
        return {"ok": False, "error": f"BLITZ's account is not funded yet ({FUNDED_CMD})"}
    new = {**old, "payouts": {**dict(old.get("payouts") or {}), d: amt}}
    spec = normalize(new)
    if spec["problem"]:
        return {"ok": False, "error": spec["problem"]}
    write_local(new, root, why=f"Payout {d} ${amt:,.2f} recorded.")
    return {"ok": True, "say": f"Payout {d} ${amt:,.2f} recorded on {spec['account']}."}


def status(root: str | None = None) -> dict:
    """The block, the eval and the scorecard from the state file, without a running bot."""
    blk = raw_cfg(root)
    if not blk:
        return {"ok": True, "on": False, "say": "account C (BLITZ on its own account) is OFF"}
    spec = normalize(blk)
    closes = []
    try:
        with open(state_file(root), encoding="utf-8") as fh:
            b = json.load(fh)
        if isinstance(b, dict) and b.get("account") == spec["account"]:
            closes = [list(c) + [None] * (5 - len(c)) for c in b.get("closes") or [] if isinstance(c, (list, tuple)) and len(c) >= 3]
            paused = b.get("paused")
        else:
            paused = None
    except Exception:
        paused = None
    sc = score([{"day": c[0], "usd": c[2], "r": c[4]} for c in closes if c[4] is not None])
    return {"ok": True, "on": True, "account": spec["account"], "plan": spec["plan_label"], "eval_start": spec["eval_start"],
            "armed": spec["armed"], "problem": spec["problem"], "params": spec["params"], "closes": len(closes),
            "net": round(sum(float(c[2]) for c in closes), 2), "scorecard": sc, "paused": paused}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.account_c", description="BLITZ's own account (account C) on this PC")
    ap.add_argument("off", nargs="?", help="'off' switches account C off")
    ap.add_argument("--account", help="the NinjaTrader account Name exactly as NinjaTrader shows it")
    ap.add_argument("--plan", default="builder25k", help="builder25k (the only plan for BLITZ)")
    ap.add_argument("--start", help="the eval's first session (yyyy-mm-dd); --to-funded: the first funded day")
    ap.add_argument("--status", action="store_true", help="the block, the eval and the performance scorecard")
    ap.add_argument("--resume", action="store_true", help="lift a performance-contract pause (the owner's decision)")
    ap.add_argument("--to-funded", action="store_true", help="after a pass: trade the NEW funded account (--account, --start), disarmed")
    ap.add_argument("--balance", type=float, default=None, help="--to-funded: its balance that day (default $25,000)")
    ap.add_argument("--payout", help="record one payout MFFU paid on the funded account: yyyy-mm-dd=$")
    a = ap.parse_args(argv)
    if a.off is not None and a.off.lower() != "off":
        print(f"unknown argument {a.off!r} (only 'off')")
        return 2
    if a.off:
        r = set_account_c(None)
        print("  [OK]  account C (BLITZ) is OFF: the bot is exactly as before" if r["ok"] else f"  [FIX] {r['error']}")
        return 0 if r["ok"] else 1
    if a.resume:
        r = resume()
        print(f"  [{'OK' if r['ok'] else '..'}]  {r.get('say') or r.get('error')}")
        return 0 if r["ok"] else 1
    if a.payout:
        r = record_payout(a.payout)
        print(f"  [{'OK' if r['ok'] else 'FIX'}]  {r.get('say') or r.get('error')}")
        return 0 if r["ok"] else 1
    if a.to_funded:
        if not a.account or not a.start:
            print(f"--to-funded needs --account \"<funded Name>\" and --start yyyy-mm-dd ({FUNDED_CMD})")
            return 1
        r = to_funded(a.account, a.start, a.balance)
        print(f"  [{'OK' if r['ok'] else 'FIX'}]  {r.get('say') or r.get('error')}")
        if r.get("ok"):
            print(f"        Funded sizing: {r['rule']}. Restart the bot (or it switches once BLITZ is flat).")
        return 0 if r["ok"] else 1
    if a.account:
        r = set_account_c(a.account, plan=a.plan, start=a.start)
        if not r["ok"]:
            print(f"  [FIX] {r['error']}")
            return 1
        if not r["sim"]:
            from .ninjatrader import allow_account
            allow_account(r["to"]["account"])            # a real account must be on the NinjaTrader allowlist (still not armed)
        print(f"  [OK]  BLITZ -> {r['to']['account']} ({'Sim' if r['sim'] else 'REAL account: trades only after you arm it on the Start page'}), "
              f"eval from {r['to']['eval_start']}. It joins at the bot's next poll (once flat).")
        return 0
    print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
