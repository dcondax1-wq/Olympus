"""MORNING BRIEF (2026-11-18): one short ZEUS push at about 07:30 ET on CME trading days, in the owner's "important only" set
(notify_settings.json type morning_brief, ON by default; morning_brief_at = the time). Four lines, phone-sized:

  ZEUS - Wed Nov 18 - PC ok                                                  (the title)
  Zlarior 50K $49,193 ($3,807 to pass) · 25K #2 $25,000 ($1,500 to pass) · ATLAS 25K funded $25,000 ($2,100 to payout)
  Overnight: no trades · Today: Zlarior till 15:30, ATLAS till 12:00 · CPI 08:30
  Edge: GREEN · Needs you: none

Sources = the bot's own state the PC report already has (the same as the 16:15 day summary, tools/pc_guard.day_summary): the
accounts as the Board shows them (engine/board_events rows fed by the PC's live cards + accounts, matched by PC id like
tools/board.lite_live), the funded payout tracker (engine/funded_life via the cards), the edge light (data/edge/tiny.json, the
status key "eh"), today's big US news (engine/notify.news_on), the CME calendar (engine/cme_calendar: full closures skipped,
an early close shortens the windows), the contract roll (engine/roll_watch) and the PC's problems (tools/pc_report.conditions).
No account id: names only, any long digit run cut to its last 4.

Called by tools/pc_guard.guard every report run (15 min); the key guard:brief:<day> is sent once (pc_report keeps it in its
state.json, so a restart never repeats it; a failed POST is retried by the next run). Window: morning_brief_at (07:30) up to
09:30 ET, weekdays that are not a CME full closure. Also ONE Board event a day (kind "brief", engine/board_events.emit), only
from the real report (LE_PC_REPORT=1, set by pc_report.main) or a test's own LE_BOARD_DIR, never twice for the same day.
Read only: it never places, changes or arms anything. Tests: python -X utf8 -m tests.test_notify (section h).
"""
from __future__ import annotations

import datetime as dt
import os
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PREFIX = "guard:brief:"
BRIEF_FROM, BRIEF_TO = 7 * 60 + 30, 9 * 60 + 30
HB_FRESH_S = 900
LIT_WINDOW = (120, 930)
ATLAS_WINDOWS = {"ema_lon_vix": [(180, 570)], "macd_sweep": [(120, 300), (570, 660)], "sr_nyreclaim": [(570, 720)]}
ATLAS_NO_MONDAY = {"ema_lon_vix"}
try:                                                  # the bots' real entry hours (one source); the copies above if it fails
    from engine.live_board import ATLAS_NO_MONDAY, ATLAS_WINDOWS, LIT_WINDOW  # noqa: F811
except Exception:  # noqa: BLE001
    pass
COND_WORD = {"bot_down": ("bot down", "STOP BOT, START BOT"), "bot_stopped": ("bot stopped", "START BOT"),
             "nt_down": ("NinjaTrader closed", "open NinjaTrader"), "feed_stale": ("FEED STALE", "re-add LE_BarFeed")}
WORD = {"G": "GREEN", "A": "AMBER", "R": "RED"}
CARD_NAME = {"lit": "Zlarior", "atlas": "ATLAS"}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = _f(x)
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def signed(x) -> str:
    v = _f(x)
    return "-" if v is None else ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(round(v)))


def _hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def safe(s, n: int = 40) -> str:
    """A name for the phone: any run of 5+ digits (a broker account id) cut to its last 4."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return re.sub(r"[A-Za-z]*\d{5,}", lambda m: "..." + re.sub(r"\D", "", m.group(0))[-4:], s)[:n]


def _settings() -> dict:
    try:
        from engine import notify
        return notify.settings()
    except Exception:  # noqa: BLE001
        return {}


def _et(now) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(now), ET)


def due(now, s: dict | None = None) -> bool:
    """07:30 (morning_brief_at) up to 09:30 ET on a weekday that is not a CME full closure."""
    e = _et(now)
    try:
        from engine import notify
        frm = notify.hm_min((s or _settings()).get("morning_brief_at"), BRIEF_FROM)
    except Exception:  # noqa: BLE001
        frm = BRIEF_FROM
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (frm <= m < max(BRIEF_TO, frm + 60)):
        return False
    try:
        from engine import cme_calendar
        return not cme_calendar.full_closure(e.date())
    except Exception:  # noqa: BLE001
        return True


def key(now) -> str:
    return PREFIX + _et(now).date().isoformat()


# ------------------------------------------------------------------------------------------------ the accounts (Board rows)
def _plan_accounts(plan_doc) -> list:
    return [a for a in _l(_d(plan_doc).get("accounts")) if isinstance(a, dict) and a.get("key")]


def _sources(L: dict, pa: list) -> dict:
    """{plan key: the PC's own card / account dict} (the payout tracker, the position, the quiet days)."""
    from engine import board_events as B
    out = {}
    bd = _d(L.get("board"))
    for ck in ("lit", "atlas"):
        c = _d(bd.get(ck))
        if c and not c.get("error"):
            out.setdefault(B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck), {**c, "_card": ck})
    for a in _l(L.get("accounts")):
        a = _d(a)
        if a.get("id") and a.get("kind") in ("eval", "funded") and a.get("source") not in ("cloud", "pc_blitz") and a.get("id") != "acct_c":
            k = B.plan_key(pa, a.get("id"), a.get("name")) or str(a["id"])
            out.setdefault(k, {**a, "_acct": str(a["id"])})
    return out


def rows(snap: dict, now: int, plan_doc=None, events=None) -> list:
    """The Board's account rows (engine/board_events.build) with the PC's live numbers, planned rows and rows without a
    balance left out, each with its PC source under "_src"."""
    from engine import board_events as B
    try:
        from tools import board as TB
    except Exception:  # noqa: BLE001
        TB = None
    plan_doc = B.plan() if plan_doc is None else plan_doc
    pa = _plan_accounts(plan_doc)
    L = _d(snap.get("live"))
    live = TB.lite_live(L, pa) if TB else {}
    if snap.get("hb_t"):
        for v in live.values():
            v["t"] = max(_f(v.get("t")) or 0, float(snap["hb_t"]))
    board = B.build(events=events, plan_doc=plan_doc, live=live, pc={"t": snap.get("hb_t"), "via": "this PC"}, now=now)
    src = _sources(L, pa)
    out = []
    for r in board.get("accounts") or []:
        if r.get("chip") == "planned" or _f(r.get("balance")) is None:
            continue
        out.append({**r, "_src": src.get(r.get("key")) or {}})
    first = {}                                        # the same bot's accounts side by side ("Zlarior 50K · 25K #2 · ATLAS ...")
    for r in out:
        first.setdefault(label(r).split(" ")[0], len(first))
    return sorted(out, key=lambda r: first[label(r).split(" ")[0]])


def label(r: dict) -> str:
    name = safe(r.get("name") or r.get("key"), 30)
    size = re.search(r"(\d+K)", str(r.get("plan") or ""))
    if size and size.group(1).lower() not in name.lower():
        name = f"{name} {size.group(1)}"
    return name


def short_labels(rs: list) -> list:
    """'Zlarior 50K', 'Zlarior 25K #2' -> 'Zlarior 50K', '25K #2' (the name once in a row)."""
    out, prev = [], None
    for r in rs:
        lab = label(r)
        first = lab.split(" ", 1)
        if prev and len(first) == 2 and first[0] == prev:
            out.append(first[1])
        else:
            out.append(lab)
        prev = first[0]
    return out


def funded_part(r: dict) -> tuple:
    """(' ($2,100 to payout)' / ' (payout READY $1,000)', need-you text or None) from the funded payout tracker."""
    s = _d(r.get("_src"))
    f = _d(s.get("funded"))
    if not f:
        return "", None
    if f.get("lost"):
        return " (floor reached)", None
    if f.get("ready"):
        amt = _f(f.get("max_request"))
        return f" (payout READY {money(amt)})", f"request the {label(r)} payout" + (f" {money(amt)}" if amt else "")
    ta = _f(f.get("to_ask"))
    if ta is None:
        ta = _f(s.get("to_target")) if s.get("_card") == "atlas" else None
    return (f" ({money(ta)} to payout)" if ta is not None and ta > 0 else ""), None


def accounts_line(rs: list) -> tuple:
    """(line, [needs you])."""
    parts, needs = [], []
    for r, lab in zip(rs, short_labels(rs)):
        bal = money(r.get("balance"))
        st = str(r.get("stage") or "eval")
        if r.get("locked"):
            parts.append(f"{lab} LOCKED {bal}")
            needs.append(f"{label(r)} locked: check MFFU")
        elif st == "failed":
            parts.append(f"{lab} failed")
        elif st == "passed":
            parts.append(f"{lab} PASSED {bal}")
            needs.append(f"{label(r)} passed: send Claude the funded name")
        elif st == "funded":
            tail, need = funded_part(r)
            parts.append(f"{lab} funded {bal}{tail}")
            if need:
                needs.append(need)
        else:
            tp = _f(r.get("to_pass"))
            parts.append(f"{lab} {bal}" + (f" ({money(tp)} to pass)" if tp is not None and tp > 0 else ""))
        q = _f(_d(r.get("_src")).get("quiet_days"))      # (counts a keep-alive / hand trade noted: engine/keepalive)
        ka_cover = bool(_d(_d(r.get("_src")).get("keepalive")).get("cover"))   # the keep-alive warns for it itself
        if q is not None and q >= 6 and st in ("eval", "funded") and not r.get("locked") and not ka_cover:
            needs.append(f"{label(r)} {int(q)} days without a trade: 1 MNQ by hand")
    return (" · ".join(parts) if parts else "No account numbers in the last report"), needs


# ------------------------------------------------------------------------------------------------ overnight
def session_start(now) -> int:
    """18:00 ET the evening before today's CME trading date."""
    e = _et(now)
    d = e.date() if e.hour < 18 else e.date() + dt.timedelta(days=1)
    s = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(18, 0), ET)
    return int(s.timestamp())


def overnight(snap: dict, now: int, rs: list, plan_doc=None) -> str:
    """'no trades' / 'Zlarior +$605 (1 trade)' / '... · ATLAS SHORT open' since 18:00 ET (paper left out)."""
    from engine import board_events as B
    pa = _plan_accounts(plan_doc if plan_doc is not None else B.plan())
    names = dict(zip([r.get("key") for r in rs], short_labels(rs)))
    L = _d(snap.get("live"))
    t0 = session_start(now)
    per, seen, opened = {}, set(), []

    def add(k, t):
        t = _d(t)
        if str(t.get("src") or "") == "paper":
            return
        et_ = int(_f(t.get("entry_t")) or 0)
        xt = int(_f(t.get("exit_t")) or 0)
        if max(et_, xt) < t0 or max(et_, xt) > now:
            return
        if (k, et_) in seen:
            return
        seen.add((k, et_))
        if t.get("open") or str(t.get("exit_kind") or t.get("exit") or "").upper() == "OPEN":
            opened.append((k, str(t.get("side") or "").upper()))
            return
        v = _f(t.get("usd"))
        v = _f(t.get("pnl")) if v is None else v
        if v is None:
            return
        n, s = per.get(k, (0, 0.0))
        per[k] = (n + 1, s + v)

    bd = _d(L.get("board"))
    for t in _l(bd.get("trades")):
        ck = str(_d(t).get("acct") or "")
        add(B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck), t)
    for a in _l(L.get("accounts")):
        a = _d(a)
        if not a.get("id") or a.get("source") in ("cloud", "pc_blitz") or a.get("id") == "acct_c":
            continue
        k = B.plan_key(pa, a.get("id"), a.get("name")) or str(a["id"])
        for t in _l(a.get("trades")):
            add(k, t)
    for ck in ("lit", "atlas"):                      # an open position the trade list does not carry yet
        p = _d(_d(bd.get(ck)).get("position"))
        k = B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck)
        if p and not any(x[0] == k for x in opened):
            opened.append((k, str(p.get("side") or "").upper()))
    nm = lambda k: names.get(k) or CARD_NAME.get(k) or safe(k, 20)   # noqa: E731
    bits = [f"{nm(k)} {signed(s)} ({n} trade{'s' if n != 1 else ''})" for k, (n, s) in per.items()]
    bits += [f"{nm(k)} {side or 'trade'} open".replace("  ", " ") for k, side in opened]
    return ", ".join(bits) if bits else "no trades"


# ------------------------------------------------------------------------------------------------ today
def _merge(rs: list) -> list:
    out = []
    for a, z in sorted(rs):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], z)
        else:
            out.append([a, z])
    return out


def windows_line(now: int) -> str:
    """'Zlarior till 15:30, ATLAS till 12:00' (what is left of today's entry hours; an early close ends them 15 min before)."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    try:
        from engine import cme_calendar
        cut = cme_calendar.entry_cut(e.date(), 24 * 60)
    except Exception:  # noqa: BLE001
        cut = 24 * 60
    bots = (("Zlarior", [LIT_WINDOW]),
            ("ATLAS", [w for k, ws in ATLAS_WINDOWS.items() for w in ws if not (e.weekday() == 0 and k in ATLAS_NO_MONDAY)]))
    out = []
    for name, ws in bots:
        left = [[max(a, m), min(z, cut)] for a, z in ws if min(z, cut) > max(a, m)]
        segs = _merge(left)
        if not segs:
            out.append(f"{name} done")
            continue
        out.append(name + " " + ", ".join(("till " + _hm(z)) if a <= m else f"{_hm(a)}-{_hm(z)}" for a, z in segs))
    return ", ".join(out)


def news_today(now: int, root: str | None = None, n: int = 2) -> str:
    """'CPI 08:30' (today's high-impact US releases, the big ones first, n at most) or ''."""
    try:
        from engine import notify
        rs = notify.news_on(_et(now).date(), root or notify.ROOT)
        big = [r for r in rs if any(w in r[1].lower() + " " for w in notify.NEWS_WORDS)] or rs
    except Exception:  # noqa: BLE001
        return ""
    paren = re.compile(r"\s*\(.*?\)")
    txt = ", ".join((paren.sub("", title).strip()[:24] + " " + t).strip() for t, title in big[:n])
    return txt + (f" (+{len(big) - n})" if len(big) > n else "")


def early_note(now: int) -> str:
    try:
        from engine import cme_calendar
        ec = cme_calendar.early_close(_et(now).date())
    except Exception:  # noqa: BLE001
        ec = None
    return f"early close {_hm(ec)}" if ec else ""


# ------------------------------------------------------------------------------------------------ edge, PC, roll
def edge_text(snap: dict) -> str:
    eh = _d(snap.get("eh"))
    z, a = _l(eh.get("z")), _l(eh.get("a"))
    lz = WORD.get(z[0]) if z else None
    la = WORD.get(a[0]) if a else None
    if not lz:
        return "no reading"
    if not la or la == lz:
        return lz
    return f"Zlarior {lz}, ATLAS {la}"


def pc_text(snap: dict) -> tuple:
    """('PC ok' / 'PC: bot down' / 'PC: last report 40 min old', [needs you])."""
    cond = _d(snap.get("cond"))
    age = snap.get("hb_age")
    needs = [f"{COND_WORD[c][0]}: {COND_WORD[c][1]}" for c in COND_WORD if c in cond]
    if needs:
        return "PC: " + COND_WORD[next(c for c in COND_WORD if c in cond)][0], needs
    if age is None:
        return "PC: no bot report", ["check the PC: STATUS.bat"]
    if age > HB_FRESH_S:
        return f"PC: last report {int(age) // 60} min old", ["check the PC: STATUS.bat"]
    return "PC ok", []


def roll_needs(snap: dict, now: int) -> list:
    try:
        from engine import roll_watch
        st = snap.get("roll")
        st = st if isinstance(st, dict) else roll_watch.fact(None, {}, now)
        ms = roll_watch.countdown(st, now)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in ms:
        k = str(m.get("key") or "")
        if k.startswith("roll:late:"):
            out.append("contract roll late: ROLL.bat")
        elif k.startswith("roll:soon:") and m.get("priority") == "high":
            out.append("contract roll tonight: ROLL.bat after 16:00")
    return out


# ------------------------------------------------------------------------------------------------ the message
def build(snap: dict, now: int | None = None, plan_doc=None, events=None, root: str | None = None) -> dict:
    """{"title", "body", "lines": [4], "day"}. Never raises on a bad snapshot (a part that fails says so)."""
    now = int(now if now is not None else snap.get("t"))
    e = _et(now)
    pc, needs = pc_text(snap)
    try:
        rs = rows(snap, now, plan_doc, events)
    except Exception as x:  # noqa: BLE001
        rs = []
        needs.append(f"brief: accounts not readable ({x.__class__.__name__})")
    acc, n2 = accounts_line(rs)
    if not rs and snap.get("hb_age") is not None:
        acc = "No account numbers in the last report"
    try:
        ov = overnight(snap, now, rs, plan_doc)
    except Exception:  # noqa: BLE001
        ov = "not readable"
    today = windows_line(now)
    extra = [x for x in (news_today(now, root), early_note(now)) if x]
    needs += n2 + roll_needs(snap, now)
    nd = ", ".join(needs[:2]) + (f" (+{len(needs) - 2} more)" if len(needs) > 2 else "") if needs else "none"
    title = f"ZEUS - {e:%a %b} {e.day} - {pc}"
    lines = [f"ZEUS · {e:%a %b} {e.day} · {pc}", acc, f"Overnight: {ov} · Today: {today}" + "".join(f" · {x}" for x in extra),
             f"Edge: {edge_text(snap)} · Needs you: {nd}"]
    return {"title": title, "body": "\n".join(lines[1:]), "lines": lines, "day": e.date().isoformat(), "needs": len(needs)}


def board_post(b: dict, env=None) -> dict | None:
    """ONE Board event (kind "brief") per day: only from the real PC report (LE_PC_REPORT=1) or a test's LE_BOARD_DIR, and
    never when that day's brief is already in data/board/events.jsonl. Never raises."""
    env = os.environ if env is None else env
    if env.get("LE_PC_REPORT") != "1" and not env.get("LE_BOARD_DIR"):
        return None
    try:
        from engine import board_events as B
        path = os.path.join(B.dirs(env)[0], B.EVENTS)
        if any(r.get("kind") == "brief" and _d(r.get("data")).get("day") == b["day"] for r in B.read_jsonl(path)[-400:]):
            return None
        return B.emit("brief", "", " | ".join(b["lines"]), {"day": b["day"], "needs": b.get("needs") or 0})
    except Exception:  # noqa: BLE001
        return None


def pushes(snap: dict, sent: dict, now: int, plan_doc=None, events=None) -> list:
    """tools/pc_guard.guard's hook: [the brief push] once a day inside the window, else []."""
    if not due(now):
        return []
    k = key(now)
    if k in (sent or {}):
        return []
    b = build(snap, now, plan_doc, events)
    board_post(b)
    return [{"key": k, "kind": "morning_brief", "title": b["title"], "body": b["body"], "priority": "default", "tags": "sunrise"}]


if __name__ == "__main__":                       # a dry look on the PC: python -X utf8 -m tools.morning_brief
    import time
    from tools import pc_report as R
    s = R.gather(int(time.time()))
    s["cond"] = R.conditions(s)
    print("\n".join(build(s)["lines"]))
