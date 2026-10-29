"""The playbook as data (docs/PLAYBOOK.md): every written rule of Zlarior (LIT), ATLAS and BLITZ with an id, its phase, the
plain text and the name of the check that tells whether it is the rule the bot is on right now.

READ-ONLY. The bots' own code decides (engine/lit.py, engine/second.py, engine/blitz.py); this module only NAMES the rule a
bot is applying, so the dashboards and the narrator can say "Z6: limit working ..." and the advisor can tie each piece of
structure advice to a written rule. Nothing here sizes, routes or changes an order.

  RULES                  list of dicts {id, strategy, phase, title, text, check}
  rule(id)               one rule
  now(strategy, ctx)     the rule the bot is applying now + why, from what the bot already shows:
                           lit    ctx = {"brain": bot.brain, "position": the open position (or None)}
                           atlas  ctx = {"members": {key: {"stage", "text"}}, "position": ...}
                           scalp  ctx = {"stage": BLITZ state_text stage, "text": ...}
  checks(strategy, ctx)  every rule of the strategy with its state (now / done / wait / n/a)

    python -X utf8 -m tests.test_playbook
"""
from __future__ import annotations

PHASES = ("setup", "invalid", "manage", "structure")

RULES = [
    # ---- Zlarior (LIT)
    {"id": "Z1", "strategy": "lit", "phase": "setup", "title": "Know the liquidity",
     "text": "Mark the session boxes (Asia, London, NY, premarket), previous day / week / month high and low, opening gaps and equal "
             "highs / lows; a box is a level only after it closed.", "check": "lit_stage_levels"},
    {"id": "Z2", "strategy": "lit", "phase": "setup", "title": "The sweep",
     "text": "A new 2-hour extreme takes out an untraded level and runs at least half an ATR past it.", "check": "lit_stage_sweep"},
    {"id": "Z3", "strategy": "lit", "phase": "setup", "title": "The trap (inducement)",
     "text": "A small 5m swing between the level and the extreme (<= 1 ATR, <= 3 hours old) was run by the final push.",
     "check": "lit_stage_inducement"},
    {"id": "Z4", "strategy": "lit", "phase": "setup", "title": "The shove (displacement)",
     "text": "One 5m candle body of 0.8 ATR or more between the extreme and the shift.", "check": "lit_stage_displacement"},
    {"id": "Z5", "strategy": "lit", "phase": "setup", "title": "The shift (5m CISD)",
     "text": "A 5m close back through the open of the last run of candles into the extreme.", "check": "lit_stage_cisd5"},
    {"id": "Z6", "strategy": "lit", "phase": "setup", "title": "Entry at our price",
     "text": "Limit at the CISD level for 30 minutes; after the tap up to 20 one-minute candles for a 1m CISD, then the next 1m open.",
     "check": "lit_stage_entry"},
    {"id": "Z7", "strategy": "lit", "phase": "setup", "title": "Time and count",
     "text": "Entries 02:00-15:30 ET, one trade a day, the Monday rule (Friday's high taken: shorts only; low: longs only).",
     "check": "lit_day_free"},
    {"id": "Z8", "strategy": "lit", "phase": "invalid", "title": "The extreme breaks",
     "text": "The sweep extreme breaks before the fill: the trap was not the turn.", "check": "lit_expired"},
    {"id": "Z9", "strategy": "lit", "phase": "invalid", "title": "Too late",
     "text": "The target trades before the tap, 30 minutes without a tap, or 20 minutes without the 1m confirmation.",
     "check": "lit_expired"},
    {"id": "Z10", "strategy": "lit", "phase": "invalid", "title": "Bad geometry",
     "text": "A stop under 8 or over 80 points, or a target under 1.5R away.", "check": "lit_rejected"},
    {"id": "Z11", "strategy": "lit", "phase": "invalid", "title": "Closed for the day",
     "text": "15:55, a trade already filled today, or the NinjaTrader feed is stale.", "check": "lit_done"},
    {"id": "Z12", "strategy": "lit", "phase": "manage", "title": "Stop at the protected extreme",
     "text": "1 tick beyond the sweep extreme, never a fixed distance.", "check": "pos_open"},
    {"id": "Z13", "strategy": "lit", "phase": "manage", "title": "Size follows the stop",
     "text": "A wide stop buys fewer micros; on the eval one winner passes, inside 80% of the room and the $1,000 soft daily loss.",
     "check": "pos_open"},
    {"id": "Z14", "strategy": "lit", "phase": "manage", "title": "One clear target",
     "text": "The 18:00 open +/- one VIX day move, banked at 8R. No second target.", "check": "pos_be_done"},
    {"id": "Z15", "strategy": "lit", "phase": "manage", "title": "Protect at +1R",
     "text": "At +1R the stop goes to entry + 1.25 (costs covered).", "check": "pos_before_be"},
    {"id": "Z16", "strategy": "lit", "phase": "manage", "title": "Cut the dead trade",
     "text": "15 minutes after the fill: never +0.5R and more than 0.3R under water = out at the next 1m open.",
     "check": "pos_first_15"},
    {"id": "Z17", "strategy": "lit", "phase": "manage", "title": "Flat by 15:55", "text": "Always flat by 15:55 ET.",
     "check": "pos_open"},
    {"id": "Z18", "strategy": "lit", "phase": "manage", "title": "No improvising",
     "text": "No trailing, no early exit on a scary candle, no tighter stop: each was tested on the real trades and cost money.",
     "check": "pos_open"},
    {"id": "Z-S1", "strategy": "lit", "phase": "structure", "title": "1h trend and premium / discount",
     "text": "A long from discount with the 1h up fits the structure; against it the bot says so (advice).", "check": "structure"},
    {"id": "Z-S2", "strategy": "lit", "phase": "structure", "title": "The pool in front",
     "text": "The nearest opposing liquidity pool in front of the trade, where price may slow down (advice).", "check": "structure"},
    {"id": "Z-S3", "strategy": "lit", "phase": "structure", "title": "CHoCH against after +1R",
     "text": "A 5m CHoCH against an open trade after +1R: a person might protect; the advisor scores it (advice).",
     "check": "structure"},
    {"id": "Z-S4", "strategy": "lit", "phase": "structure", "title": "BOS in favour",
     "text": "A 5m BOS in the trade's favour: the new protected swing is where a structure trader would trail (advice).",
     "check": "structure"},
    # ---- ATLAS
    {"id": "A1", "strategy": "atlas", "phase": "setup", "title": "EMA trend pullback",
     "text": "London 03:00-09:30 ET, no Mondays: 15m and 1h EMA 21 vs 50 agree, a pullback to the 5m EMA 50 sweeps a swing, a 5m "
             "CISD closes back.", "check": "member_ema"},
    {"id": "A2", "strategy": "atlas", "phase": "setup", "title": "MACD divergence at a sweep",
     "text": "02:00-05:00 and 09:30-11:00 ET: a LIT level swept by 0.5 ATR, a 5m CISD close with MACD-line divergence.",
     "check": "member_macd"},
    {"id": "A3", "strategy": "atlas", "phase": "setup", "title": "S/R sweep-and-reclaim",
     "text": "NY 09:30-12:00 ET: a level of the day swept after an inducement, a strong 5m close reclaims it; one a day.",
     "check": "member_sr"},
    {"id": "A4", "strategy": "atlas", "phase": "invalid", "title": "Not its time",
     "text": "Outside the member's hours, Monday for EMA, trends disagree, no divergence, no reclaim close.", "check": "members_off"},
    {"id": "A5", "strategy": "atlas", "phase": "invalid", "title": "LIT first, no hedge",
     "text": "No entry while LIT holds the other side or has an opposite setup armed; LIT entering closes ATLAS; one position, "
             "max 2 a day, $600 soft daily loss.", "check": "members_off"},
    {"id": "A6", "strategy": "atlas", "phase": "manage", "title": "Stop beyond the sweep wick",
     "text": "The stop sits beyond the wick that took the liquidity; size follows the stop.", "check": "pos_open"},
    {"id": "A7", "strategy": "atlas", "phase": "manage", "title": "Targets",
     "text": "VIX band for EMA and MACD, 2R for S/R.", "check": "pos_open"},
    {"id": "A8", "strategy": "atlas", "phase": "manage", "title": "Protect / cut",
     "text": "EMA: breakeven + 1.25 at 1R; MACD and S/R: the 15-minute check; flat 15:55.", "check": "pos_open"},
    {"id": "A-S1", "strategy": "atlas", "phase": "structure", "title": "15m + 1h agreement",
     "text": "ATLAS follows the trend: both up fits longs, both down shorts (advice).", "check": "structure"},
    {"id": "A-S2", "strategy": "atlas", "phase": "structure", "title": "The protected swing",
     "text": "Where a structure trader's stop would sit (shown, not used).", "check": "structure"},
    # ---- BLITZ
    {"id": "B1", "strategy": "scalp", "phase": "setup", "title": "Only on lively days",
     "text": "Yesterday's 09:30-16:00 range at least 0.8 x its 14-day mean.", "check": "blitz_filtered"},
    {"id": "B2", "strategy": "scalp", "phase": "setup", "title": "The noise band",
     "text": "09:30 open x (1 +/- sigma), sigma = the 14-session mean move at that minute.", "check": "blitz_waiting"},
    {"id": "B3", "strategy": "scalp", "phase": "setup", "title": "Checks on the half hour",
     "text": "At the 1m closes 11:00 ... 15:30: above the band = long, below = short, market at the next open.",
     "check": "blitz_watching"},
    {"id": "B4", "strategy": "scalp", "phase": "invalid", "title": "Enough for today",
     "text": "Six trades, the day down 3R, or no clean 1m bars.", "check": "blitz_done"},
    {"id": "B5", "strategy": "scalp", "phase": "manage", "title": "Stop 1.5 ATR",
     "text": "Stop 1.5 x ATR(14) of 5m from the signal close.", "check": "blitz_trade"},
    {"id": "B6", "strategy": "scalp", "phase": "manage", "title": "Trail after +1R",
     "text": "After +1R the stop trails 1.5R behind the best price.", "check": "blitz_trade"},
    {"id": "B7", "strategy": "scalp", "phase": "manage", "title": "Time stop",
     "text": "Out after 30 bars or at 15:55; no fixed target.", "check": "blitz_trade"},
    {"id": "B8", "strategy": "scalp", "phase": "invalid", "title": "LIT first",
     "text": "Next to LIT: never while LIT holds a trade or has a setup armed; closed when LIT enters.", "check": "blitz_done"},
    {"id": "B-S1", "strategy": "scalp", "phase": "structure", "title": "5m trend",
     "text": "A breakout in the 5m trend's direction goes with it (advice).", "check": "structure"},
]
_BY_ID = {r["id"]: r for r in RULES}
STRATEGIES = ("lit", "atlas", "scalp")

# Bot Brain stage key -> the LIT rule being worked on (engine/brain.py stages)
LIT_STAGE = {"levels": "Z1", "sweep": "Z2", "inducement": "Z3", "displacement": "Z4", "cisd5": "Z5", "limit": "Z6",
             "cisd1m": "Z6", "trade": "Z15", "done": "Z11", "closed": "Z11", "window": "Z7"}
BLITZ_STAGE = {"filtered": "B1", "waiting": "B2", "warming": "B2", "watching": "B3", "done": "B4", "closed": "B4",
               "stale": "B4", "trade": "B6", "off": "B2", "error": "B4"}
ATLAS_MEMBER = {"ema_lon_vix": "A1", "macd_sweep": "A2", "sr_nyreclaim": "A3"}


def rule(rid: str) -> dict | None:
    return _BY_ID.get(rid)


def of(strategy: str, phase: str | None = None) -> list:
    return [r for r in RULES if r["strategy"] == strategy and (phase is None or r["phase"] == phase)]


def _pick(rid, why) -> dict:
    r = _BY_ID[rid]
    return {"id": rid, "title": r["title"], "text": r["text"], "phase": r["phase"], "why": why}


# ------------------------------------------------------------------------------------------------ the checks
def _lit_pos(ctx):
    p = ctx.get("position") or (ctx.get("brain") or {}).get("trade")
    return p if isinstance(p, dict) and p.get("entry") is not None else None


def lit_now(ctx: dict) -> dict:
    """The LIT rule the bot is on, from the Bot Brain's stage and the open position."""
    b = ctx.get("brain") or {}
    pos = _lit_pos(ctx)
    now = ctx.get("now")
    if pos:
        be = pos.get("be") if isinstance(pos.get("be"), dict) else {}
        done = bool(be.get("done") or be.get("moved")) or (pos.get("stop") is not None and pos.get("entry") is not None
                                                            and (float(pos["stop"]) - float(pos["entry"])) * int(pos.get("dir") or 1) >= 0)
        et = pos.get("entry_t")
        if not done and now and et and int(now) - int(et) < 16 * 60:
            return _pick("Z16", "first 15 minutes of the trade: the dead-trade check is still to come")
        if not done:
            return _pick("Z15", "in the trade: waiting for +1R to move the stop to entry + 1.25")
        return _pick("Z14", "stop at breakeven + costs: holding for the one target (no trailing, Z18)")
    st = (b.get("stage") or {}).get("key")
    if st in LIT_STAGE:
        rid = LIT_STAGE[st]
        why = (b.get("stage") or {}).get("waiting") or (b.get("stage") or {}).get("label") or st
        return _pick(rid, str(why)[:200])
    if not b:
        return _pick("Z1", "the Bot Brain has nothing yet (fills after the bot's first poll)")
    return _pick("Z1", "marking the levels")


def atlas_now(ctx: dict) -> dict:
    mem = ctx.get("members") or {}
    for k, m in mem.items():
        if (m or {}).get("stage") == "in_trade":
            rid = "A8" if k in ("macd_sweep", "sr_nyreclaim") else "A6"
            return _pick(rid, f"{k}: {str((m or {}).get('text') or 'in a paper trade')[:160]}")
    for k, m in mem.items():
        if (m or {}).get("stage") == "armed" and k in ATLAS_MEMBER:
            return _pick(ATLAS_MEMBER[k], f"{k}: {str((m or {}).get('text') or 'signal')[:160]}")
    for k, m in mem.items():
        if (m or {}).get("stage") == "waiting" and k in ATLAS_MEMBER:
            return _pick(ATLAS_MEMBER[k], f"{k}: {str((m or {}).get('text') or 'waiting')[:160]}")
    return _pick("A4", "no member inside its hours right now")


def scalp_now(ctx: dict) -> dict:
    st = ctx.get("stage") or "waiting"
    rid = BLITZ_STAGE.get(st, "B2")
    return _pick(rid, str(ctx.get("text") or st)[:200])


def now(strategy: str, ctx: dict | None = None) -> dict:
    """{id, title, text, phase, why}: the written rule the bot is applying right now. Never raises."""
    ctx = ctx or {}
    try:
        if strategy == "lit":
            return lit_now(ctx)
        if strategy == "atlas":
            return atlas_now(ctx)
        if strategy == "scalp":
            return scalp_now(ctx)
    except Exception as e:
        return {"id": None, "title": "playbook", "text": "", "phase": None, "why": f"{e.__class__.__name__}: {e}"[:120]}
    return {"id": None, "title": "playbook", "text": "", "phase": None, "why": f"unknown strategy {strategy}"}


def checks(strategy: str, ctx: dict | None = None) -> list:
    """Every rule of the strategy with its state: "now" (the rule being applied), "done" (an earlier setup rule), "wait"."""
    cur = now(strategy, ctx)
    rs = of(strategy)
    out, seen = [], False
    for r in rs:
        if r["id"] == cur.get("id"):
            st, seen = "now", True
        elif r["phase"] == "setup" and not seen and cur.get("phase") in ("setup", "manage"):
            st = "done"
        elif r["phase"] == "structure":
            st = "advice"
        else:
            st = "wait"
        out.append({"id": r["id"], "title": r["title"], "phase": r["phase"], "state": st})
    return out


# ------------------------------------------------------------------------------------------------ one check per rule (the
# "check" name of each rule): True when that rule is the live one in ctx (same ctx as now()).
def _stage(ctx):
    return ((ctx.get("brain") or {}).get("stage") or {}).get("key")


def _setups(ctx):
    return [s for s in (ctx.get("brain") or {}).get("setups") or [] if isinstance(s, dict)]


def lit_stage_levels(ctx):
    return _stage(ctx) in (None, "levels") and not _lit_pos(ctx)


def lit_stage_sweep(ctx):
    return _stage(ctx) == "sweep"


def lit_stage_inducement(ctx):
    return _stage(ctx) == "inducement"


def lit_stage_displacement(ctx):
    return _stage(ctx) == "displacement"


def lit_stage_cisd5(ctx):
    return _stage(ctx) == "cisd5"


def lit_stage_entry(ctx):
    return _stage(ctx) in ("limit", "cisd1m")


def lit_day_free(ctx):
    return int((ctx.get("brain") or {}).get("day_trades") or 0) == 0 and not _lit_pos(ctx)


def lit_expired(ctx):
    return any(s.get("status") == "expired" for s in _setups(ctx))


def lit_rejected(ctx):
    return any(s.get("status") == "rejected" for s in _setups(ctx))


def lit_done(ctx):
    return _stage(ctx) in ("done", "closed")


def pos_open(ctx):
    if _lit_pos(ctx):
        return True
    return any((m or {}).get("stage") in ("in_trade", "trade") for m in (ctx.get("members") or {}).values()) or ctx.get("stage") == "trade"


def _be_done(p):
    try:
        return (float(p["stop"]) - float(p["entry"])) * int(p.get("dir") or 1) >= 0
    except (KeyError, TypeError, ValueError):
        return False


def pos_be_done(ctx):
    p = _lit_pos(ctx)
    return bool(p and _be_done(p))


def pos_before_be(ctx):
    p = _lit_pos(ctx)
    return bool(p and not _be_done(p))


def pos_first_15(ctx):
    p = _lit_pos(ctx)
    return bool(p and ctx.get("now") and p.get("entry_t") and int(ctx["now"]) - int(p["entry_t"]) < 16 * 60 and not _be_done(p))


def structure(ctx):
    return bool(ctx.get("structure"))


def _member(ctx, key):
    return (ctx.get("members") or {}).get(key) or {}


def member_ema(ctx):
    return _member(ctx, "ema_lon_vix").get("stage") in ("waiting", "armed", "in_trade")


def member_macd(ctx):
    return _member(ctx, "macd_sweep").get("stage") in ("waiting", "armed", "in_trade")


def member_sr(ctx):
    return _member(ctx, "sr_nyreclaim").get("stage") in ("waiting", "armed", "in_trade")


def members_off(ctx):
    M = ctx.get("members") or {}
    return bool(M) and all((m or {}).get("stage") in ("off", "done", None) for m in M.values())


def blitz_filtered(ctx):
    return ctx.get("stage") == "filtered"


def blitz_waiting(ctx):
    return ctx.get("stage") in ("waiting", "warming", "off")


def blitz_watching(ctx):
    return ctx.get("stage") == "watching"


def blitz_done(ctx):
    return ctx.get("stage") in ("done", "closed", "stale", "error")


def blitz_trade(ctx):
    return ctx.get("stage") == "trade"


def check_fn(name: str):
    """The check function of a rule's "check" name (None when it does not exist)."""
    f = globals().get(name)
    return f if callable(f) else None


def applying(strategy: str, ctx: dict | None = None) -> list:
    """Ids of every rule of the strategy whose check is True in ctx (several can hold at once)."""
    ctx = ctx or {}
    out = []
    for r in of(strategy):
        f = check_fn(r["check"])
        try:
            if f and f(ctx):
                out.append(r["id"])
        except Exception:
            pass
    return out
