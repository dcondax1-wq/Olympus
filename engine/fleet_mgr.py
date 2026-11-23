"""FLEET MANAGER (night-fleetmgr 2026-11-23, lead: money discipline from research/writeups/fleet-plan-2026-11-22.md + fleet-v2).
ADVICE ONLY: it never buys, closes, arms, routes or sizes anything, and never requests a payout. The owner buys / closes on MFFU.

From the PC's own account states it keeps each account's stage (eval / passed / funded / payout n / failed / lost / closed) and,
on each CHANGE, sends ONE plain alert with the next money move under the plan the owner approved:
  * an eval failed / a funded account lost  -> the re-buy rule:
        - a plan with a re-buy card (Rapid EOD 50K: plan-rapid50k-max2-rebuys; FundedNext: plan-fundednext50k-max2-rebuys) and
          the owner's YES: "re-buy #k of 2 allowed: Rapid EOD 50K $165"; after 2 re-buys "stop this slot"
        - the card not answered: "decide card <id> first"
        - Builder / Rapid 25K (no card): tools/money/money_book.dead_eval (re-buy the same plan the same night at your price;
          card refill-25k-with-rapid50 offers the Rapid 50K instead of a dead Builder 25K, only on its yes)
        - 3 accounts dead in a row (the fleet plan's S3 stop): no more buy suggestions until an account is added again
        - MFFU's caps (5 sim funded in all; Builder 50K 1, Builder 25K 2, Rapid EOD 3 per size; 10 evals): no slot = no buy
  * a Builder took payout 4 -> "close it after today, buy the next account" (never payout #5: engine/payout_autopilot guards it)
  * a Rapid paid >= $6,500 in all -> the live-move risk (MFFU's risk team example: live at about $7,000 paid; the fleet plan's
    sensitivity: close near $6,500, the owner's call)
  * passed -> MFFU issues the funded account; one tap on the Start page when it shows in NinjaTrader
  * an account gone from the bot -> its slot is free; the next move
The owner's real prices (CLAUDE.md): Builder 50K $91.80, Builder 25K $63 ($43 once), Rapid EOD 25K $97.20, Rapid EOD 50K $165.
Cards: tools/web_public/business/decisions.json "items" (status "yes" / "answered" with answer yes = approved; anything else = not).

State: data/fleet_mgr.json (gitignored). Run: tools/pc_report.py every 15 minutes (tick()). Phone: tiny() -> the status post's
"fl" block -> Trading Home's "Fleet" line (tools/web_public/nq/trading_home_core.js).
    python -X utf8 -m engine.fleet_mgr          the fleet now + the next move (prints, sends nothing)
Tests: python -X utf8 -m tests.test_fleet_mgr
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
STATE_PATH = os.path.join(ROOT, "data", "fleet_mgr.json")                       # gitignored
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
PRICE = {"builder50k": 91.80, "builder25k": 63.0, "rapideod25": 97.20, "rapideod50": 165.0}
LABEL = {"builder50k": "Builder 50K", "builder25k": "Builder 25K", "rapideod25": "Rapid EOD 25K", "rapideod50": "Rapid EOD 50K"}
REBUY_CARD = {"rapideod50": "plan-rapid50k-max2-rebuys", "fn50": "plan-fundednext50k-max2-rebuys"}
REFILL_CARD = "refill-25k-with-rapid50"
BUY_CARD = "buy-rapid50-now"
MAX_REBUYS = 2                          # the cards' hard stop: at most 2 re-buys (3 evals in all)
DEAD_STOP = 3                           # the fleet plan's S3: stop all buying after 3 dead accounts in a row
BUILDER_LAST = 4                        # take payouts 1-4, then close (never #5)
RAPID_LIVE_WARN = 6500.0                # $ paid in all on one Rapid: MFFU's risk-team example is about $7,000
DEAD = ("failed", "lost")
ALIVE = ("eval", "passed", "funded", "locked")


def usd(x) -> str:
    v = float(x or 0)
    return f"${v:,.2f}" if abs(v - round(v)) > 0.004 else f"${v:,.0f}"


# ------------------------------------------------------------------------------------------------ cards
def cards(path: str | None = None) -> dict:
    """{card id: "yes" | "no" | "later" | "open"} from decisions.json. Never raises."""
    try:
        with open(path or DECISIONS, encoding="utf-8") as fh:
            d = json.load(fh)
        out = {}
        for c in d.get("items") or []:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            a = str(c.get("answer") or "").strip().lower()
            st = str(c.get("status") or "").strip().lower()
            # night-decide 2026-11-23: done = applied (a yes); later / superseded / waiting are NOT waiting for the owner's answer
            out[c["id"]] = a if a in ("yes", "no", "later") else ("yes" if st in ("yes", "approved", "done") else
                                                                    st if st in ("no", "later", "superseded", "waiting") else "open")
        return out
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------ the pure rules
def slots(rows: list) -> dict:
    """MFFU caps over the live accounts (an eval holds its funded slot too): tools/money/money_book.slots."""
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import money_book as MB
    acc = [{"name": r["label"], "plan": r["plan"], "stage": "funded" if r["stage"] == "funded" else "eval"}
           for r in rows if r["stage"] in ALIVE and r["plan"] in MB.PLAN_CAP]
    return MB.slots(acc)


def next_move(rows: list, cd: dict, st: dict) -> str:
    """The one next buy under the approved plan (or what to decide first). Pure."""
    if int(st.get("dead_streak") or 0) >= DEAD_STOP:
        return (f"no buy: {DEAD_STOP} accounts died in a row (the fleet plan's stop). Look at why with Claude first; buying "
                "resumes once an account is added again")
    s = slots(rows)
    if s["open"] <= 0:
        return f"no buy: all {s['total_cap']} MFFU funded slots are taken or planned (5 in all)"
    r50 = s["plans"]["rapideod50"]["open"] > 0
    if r50 and (cd.get(REBUY_CARD["rapideod50"]) == "yes" or cd.get(BUY_CARD) == "yes"):
        return f"buy a Rapid EOD 50K ({usd(PRICE['rapideod50'])} with CLUB): the plan's best money per account"
    if r50:
        return f"decide card {REBUY_CARD['rapideod50']} first (Rapid EOD 50K {usd(PRICE['rapideod50'])}, the plan's #1 money move)"
    open_ = [p for p in ("builder50k", "builder25k", "rapideod25") if s["plans"][p]["open"] > 0]
    if open_:
        p = open_[0]
        return f"a {LABEL[p]} ({usd(PRICE[p])} with CLUB) fits the open slot"
    return "no buy: every plan's MFFU cap is reached"


def dead_move(row: dict, rows: list, cd: dict, st: dict) -> str:
    p = row["plan"]
    if int(st.get("dead_streak") or 0) >= DEAD_STOP:
        return (f"STOP buying: {DEAD_STOP} accounts died in a row (the fleet plan's stop). No re-buy until you and Claude look at "
                "why; buying resumes once an account is added again.")
    alive = [r for r in rows if r["key"] != row["key"]]
    s = slots(alive)
    card = REBUY_CARD.get(p)
    if card:
        if cd.get(card) != "yes":
            return f"Decide card {card} first: it sets the re-buy rule (at most {MAX_REBUYS} re-buys)."
        n = int((st.get("rebuys") or {}).get(p) or 0)
        if n >= MAX_REBUYS:
            return f"No more re-buys: the {MAX_REBUYS} the plan allows are used. Stop this slot (the card's hard stop)."
        if s["plans"][p]["open"] <= 0:
            return f"Re-buy #{n + 1} of {MAX_REBUYS} is allowed, but MFFU's cap for {LABEL[p]} is full: no slot."
        return f"Re-buy #{n + 1} of {MAX_REBUYS} allowed under the plan: {LABEL[p]} {usd(PRICE[p])} with CLUB, tonight."
    if p not in s["plans"] or s["plans"][p]["open"] <= 0:
        return f"No re-buy: MFFU's cap for {LABEL.get(p, p)} is full ({s['taken']} of {s['total_cap']} funded slots planned)."
    extra = ""
    if p == "builder25k":
        r50 = REBUY_CARD["rapideod50"]
        if cd.get(REFILL_CARD) == "yes" or cd.get(r50) == "yes":
            extra = " Your plan says a Rapid EOD 50K ($165) in this slot instead."
        elif cd.get(REFILL_CARD) == "open":
            extra = " Or a Rapid EOD 50K ($165) in this slot instead, if you say yes to card " + REFILL_CARD + "."
        else:                                   # night-decide: the refill card is merged into the Rapid 50K plan card
            extra = f" Or a Rapid EOD 50K ($165) in this slot instead: that is card {r50} (the fleet plan's buy)."
    price = "$63 ($43 if your code works)" if p == "builder25k" else usd(PRICE[p])
    return (f"Re-buy the same plan tonight: {LABEL[p]} {price} with CLUB (not a reset; every day sooner is a funded day sooner).{extra}")


def advice(ev: dict, rows: list, cd: dict, st: dict) -> tuple | None:
    """(key, title, body) for one change, or None. Pure."""
    r, k = ev["row"], ev["kind"]
    nm = r["label"]
    if k == "dead":
        what = "failed its eval" if r["stage"] == "failed" else "funded account was lost"
        return (f"fleet:dead:{r['key']}:{ev.get('n', 0)}", f"{nm} {what}", dead_move(r, rows, cd, st))
    if k == "passed":
        return (f"fleet:passed:{r['key']}", f"{nm} PASSED",
                "MFFU issues the funded account (usually within a day). When it shows in NinjaTrader: one tap on the PC's Start page, "
                "then START BOT + your phrase.")
    if k == "payout":
        n = int(r.get("payouts_n") or 0)
        if r["plan"].startswith("builder") and n >= BUILDER_LAST:
            return (f"fleet:payout:{r['key']}:{n}", f"{nm} took payout {n}: close it, buy the next account",
                    f"Never take payout #5 (MFFU moves you to live and every sim account sleeps). After today, close {nm} in MFFU. "
                    f"Next: {next_move([x for x in rows if x['key'] != r['key']], cd, st)}.")
        if r["plan"].startswith("rapid") and float(r.get("paid") or 0) >= RAPID_LIVE_WARN:
            return (f"fleet:rapidlive:{r['key']}", f"{nm}: {usd(r.get('paid'))} paid in all: Rapid live-move risk",
                    "MFFU's risk team can move a Rapid to live (their example: about $7,000 paid), and then every MFFU sim account "
                    "sleeps. The fleet plan's check: closing near $6,500 paid kept most of the money. Your call; tell Claude.")
        return None
    if k == "closed":
        return (f"fleet:closed:{r['key']}:{ev.get('n', 0)}", f"{nm} is off the bot: its slot is free",
                f"Next: {next_move([x for x in rows if x['key'] != r['key']], cd, st)}.")
    return None


def changes(prev: dict, rows: list) -> list:
    """The stage changes since the last tick: added | passed | dead | payout | closed. Pure."""
    out = []
    now = {r["key"]: r for r in rows}
    for key, r in now.items():
        p = prev.get(key)
        if p is None:
            out.append({"kind": "dead" if r["stage"] in DEAD else "added", "row": r})
            continue
        if r["stage"] != p.get("stage"):
            if r["stage"] in DEAD:
                out.append({"kind": "dead", "row": r})
            elif r["stage"] == "passed":
                out.append({"kind": "passed", "row": r})
            elif r["stage"] in ALIVE and p.get("stage") in DEAD:
                out.append({"kind": "added", "row": r})         # a new account on the same key (re-bought)
        if int(r.get("payouts_n") or 0) > int(p.get("payouts_n") or 0):
            out.append({"kind": "payout", "row": r})
    for key, p in prev.items():
        if key not in now and p.get("stage") not in ("closed",):
            out.append({"kind": "closed", "row": {**p, "key": key, "stage": "closed"}})
    return out


def step(st: dict, rows: list, cd: dict) -> tuple:
    """One tick: (new state, [alerts]). The state keeps the last rows, the dead streak and the re-buys per plan. Pure."""
    st = json.loads(json.dumps(st or {}))
    prev = st.get("rows") or {}
    first = not prev and not st.get("seeded")
    evs = changes(prev, rows)
    alerts = []
    for ev in evs:
        if ev["kind"] == "added":
            if prev:                                    # a new account after the first look: the streak ends; a re-buy counts
                st["dead_streak"] = 0
                p = ev["row"]["plan"]
                if any(v.get("plan") == p and v.get("stage") in DEAD for v in prev.values()) or ev["row"]["key"] in prev:
                    st.setdefault("rebuys", {})[p] = int((st.get("rebuys") or {}).get(p) or 0) + 1
            continue
        if ev["kind"] == "dead":
            st["dead_streak"] = int(st.get("dead_streak") or 0) + 1
            ev["n"] = st["dead_streak"]
        if first:
            continue                                    # the first look only records what is already there
        a = advice(ev, rows, cd, st)
        if a and a[0] not in (st.get("told") or {}):
            alerts.append({"key": a[0], "title": a[1][:120], "body": a[2][:600]})
    st["rows"] = {r["key"]: {k: r.get(k) for k in ("label", "plan", "stage", "payouts_n", "paid")} for r in rows}
    st["seeded"] = True
    return st, alerts


def tiny(rows: list, cd: dict, st: dict) -> dict:
    """The status post's "fl" block (<= ~200 bytes, labels only, no ids): {"s": one line, "n": live accounts, "sl": "3/5"}."""
    live = [r for r in rows if r["stage"] in ALIVE]
    s = slots(rows)
    move = next_move(rows, cd, st)
    move = move.replace("decide card " + REBUY_CARD["rapideod50"] + " first", "decide the Rapid EOD 50K card first")
    return {"n": len(live), "sl": f"{s['taken']}/{s['total_cap']}", "s": f"{len(live)} MFFU accounts, {s['taken']} of 5 funded slots "
            f"planned. Next: {move}"[:200]}


# ------------------------------------------------------------------------------------------------ the PC's numbers
KEY_LABEL = {"lit": "Zlarior 50K", "atlas": "ATLAS 25K"}
PLAN_KEY = {"builder50k": "builder50k", "builder25k": "builder25k", "rapideod": "rapideod50", "rapideod25": "rapideod25"}


def gather() -> list:
    """The PC's accounts: account_cli.inventory (plan, eval / funded) + engine/lifecycle's stage (passed / failed / lost / locked)
    + the payout trackers (engine/payout_autopilot.gather: payouts n, Rapid $ paid). Labels only. Never raises."""
    rows = []
    try:
        from . import account_cli as AC
        from . import lifecycle as LC
        try:
            from . import go
            book = json.load(open(os.path.join(os.path.dirname(go.CFG), LC.FILE), encoding="utf-8")).get("rows") or {}
        except Exception:
            book = {}
        pays = {}
        try:
            from . import payout_autopilot as PA
            for v in PA.gather():
                pays[v["key"]] = v
        except Exception:
            pass
        for r in AC.inventory():
            if r.get("sim") or r.get("role") == "c" or r.get("plan") not in PLAN_KEY:
                continue
            role, rid = r.get("role"), str(r.get("id") or "")
            key = {"main": "lit", "b": "atlas"}.get(role) or (rid if role == "rapid" else f"x:{rid}")
            plan = PLAN_KEY[r["plan"]]
            stage = str((book.get(key) or {}).get("stage") or r.get("stage") or "eval")
            if stage == "payout_ready":
                stage = "funded"
            label = KEY_LABEL.get(key) or (f"{LABEL[plan]}" + (" #2" if key == "rapid2" else "") if role == "rapid" else
                                           str(r.get("label") or LABEL[plan]))
            pv = pays.get("atlas" if key == "atlas" else key) or {}
            rows.append({"key": key, "label": label[:40], "plan": plan, "stage": stage,
                         "payouts_n": int(pv.get("payouts_n") or 0), "paid": float(pv.get("paid") or 0)})
    except Exception:
        pass
    return rows


def _read(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def tick(rows=None, cd=None, sender=None, path: str | None = None) -> dict:
    """tools/pc_report.py every 15 minutes. -> {"alerts", "tiny"}. Never raises."""
    path = path or STATE_PATH
    try:
        rows = gather() if rows is None else rows
        cd = cards() if cd is None else cd
        st = _read(path)
        st, alerts = step(st, rows, cd)
        told = st.setdefault("told", {})
        pend = st.setdefault("pending", {})             # an alert whose send failed waits here and goes out on the next tick
        for a in alerts:
            pend.setdefault(a["key"], a)
        out = []
        for key, a in list(pend.items()):
            if key in told:
                pend.pop(key, None)
                continue
            ok = (sender or _send)(a)
            if ok:
                told[key] = int(time.time())
                pend.pop(key, None)
            out.append({**a, "sent": bool(ok)})
        st["tiny"] = tiny(rows, cd, st) if rows else None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=1)
        os.replace(path + ".tmp", path)
        return {"alerts": out, "tiny": st["tiny"]}
    except Exception as e:  # noqa: BLE001
        return {"alerts": [], "error": e.__class__.__name__}


def read_tiny(path: str | None = None) -> dict | None:
    t = _read(path or STATE_PATH).get("tiny")
    return t if isinstance(t, dict) else None


def _send(a: dict) -> bool:
    try:
        from . import alert_bus as AB
        r = AB.send_critical({"kind": "report", "key": a["key"], "title": a["title"], "body": a["body"],
                              "notify_type": "account_status", "report": True}, wait=True)
        return r in ("sent", "queued", "dup")
    except Exception:
        return False


def main(argv=None) -> int:
    rows = gather()
    cd = cards()
    st = _read(STATE_PATH)
    for r in rows:
        print(f"{r['label']:<22} {LABEL.get(r['plan'], r['plan']):<15} {r['stage']:<8} payouts {r['payouts_n']}")
    print("Next:", next_move(rows, cd, st) if rows else "no account on this PC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
