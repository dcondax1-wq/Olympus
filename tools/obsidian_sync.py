"""Obsidian living sync (night A, 2026-11-16, owner: "connect to Obsidian somehow; everything needs to be synced").

Runs ON THE PC inside the PC report's 15-minute run (tools/pc_report.py main -> maybe_run; no new scheduler). When a vault is set,
it writes and updates ONE folder of the owner's Obsidian vault, <vault>/OLYMPUS/Sync/, from files that already exist on this PC:

    OLYMPUS/Sync/OLYMPUS Index.md          the map: today, the last days, trades, research, business, STATE ([[links]] everywhere)
    OLYMPUS/Sync/Days/Bots <YYYY-MM-DD>.md the bots' day (not named like your own daily notes): Zlarior / ATLAS drawdown left, today's $, balance, trades (links to the trade notes)
    OLYMPUS/Sync/Trades/<day> <bot> <hhmm>.md   one note per trade: side, entry / stop / target / exit, $ and R, its picture
    OLYMPUS/Sync/Pictures/<same name>.png  the trade picture (copied from the bot's logs/charts/, ~100-250 KB each)
    OLYMPUS/Sync/Research/Learning <day>.md     the nightly learning one-pager (research/learn/latest.md)
    OLYMPUS/Sync/Business checklist.md     every money model's next step + first-dollar list as [ ] tasks (your ticks are kept)
    OLYMPUS/Sync/STATE.md                  the repo's STATE.md (what's live, what's waiting, what's next)

Sources (read only): data/pc_report/live.json (the bots' board, written by the PC report), logs/charts/index.json + PNGs (trade
pictures), research/learn/latest.md, tools/web_public/business/business.json (else the DEMO fixture), STATE.md.
Rules: never a secret, a login, an email or an account id (scrub() cuts them; accounts are "Zlarior 50K" / "ATLAS 25K"); hidden
bots (dashboard_view.json, BLITZ today) are left out; it writes ONLY inside OLYMPUS/Sync/ and never deletes a note; a file is
rewritten only when its text changed. Every failure is soft (pc_report never stops).

One-time setup (docs/OBSIDIAN_SYNC.md):  python tools/obsidian_sync.py --setup "C:\\Users\\you\\Documents\\Obsidian\\MyVault"
    -> data/obsidian_sync.json {"vault": ...} (gitignored). Or set LE_OBSIDIAN_VAULT. Then:
    python tools/obsidian_sync.py            one sync now (prints what it wrote)
    python tools/obsidian_sync.py --status   the vault path and the last sync
Tests: tests/test_obsidian_sync.py (a temp vault, fake files).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CFG_PATH = os.path.join(ROOT, "data", "obsidian_sync.json")       # gitignored: {"vault": "<path>", "last": {...}}
SUB = os.path.join("OLYMPUS", "Sync")
LIVE = os.path.join(ROOT, "data", "pc_report", "live.json")
CHARTS = os.path.join(ROOT, "logs", "charts")
LEARN = os.path.join(ROOT, "research", "learn", "latest.md")
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
STATE = os.path.join(ROOT, "STATE.md")
EVERY_S = 10 * 60          # at most one sync every 10 minutes (the PC report runs every 15)
BRAIN_EVERY_S = 60 * 60    # the ZEUS Brain rebuild (tools/obsidian_brain.py) at most once an hour
KEEP_DAYS = 14             # the Index lists the last 14 days
BOTS = {"lit": ("Zlarior", "50K"), "atlas": ("ATLAS", "25K"), "blitz": ("BLITZ", "25K")}
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001  (no tz data: UTC-5 is close enough for a note's day)
    ET = dt.timezone(dt.timedelta(hours=-5))


# ------------------------------------------------------------------------------------------------ small helpers
def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def read_text(path) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:  # noqa: BLE001
        return ""


def num(x):
    try:
        v = float(x)
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def money(x, sign=False) -> str:
    v = num(x)
    if v is None:
        return "-"
    a = abs(round(v))
    s = "-" if v < 0 and a else ("+" if sign and v > 0 and a else "")
    return f"{s}${a:,.0f}"


def et_of(t) -> dt.datetime | None:
    v = num(t)
    if v is None:
        return None
    if v > 1e12:
        v /= 1000.0
    return dt.datetime.fromtimestamp(v, tz=dt.timezone.utc).astimezone(ET)


def today_et(now=None) -> str:
    return (et_of(now if now is not None else time.time()) or dt.datetime.now()).strftime("%Y-%m-%d")


# never a secret, a login, an email or an account id in the vault
_SCRUB = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|xox[abp]-[A-Za-z0-9-]{10,}|nfp_[A-Za-z0-9]{20,})\b"), "[key]"),
    (re.compile(r"(?i)\b(token|api[_ -]?key|password|secret)\s*[:=]\s*\S+"), r"\1: [hidden]"),
    (re.compile(r"\b[A-Z]{2,8}[-_]?\d{5,}\b"), "[account]"),            # broker / prop account ids (letters + 5+ digits)
    (re.compile(r"\b\d{7,}\b"), "[number]"),                           # any other long id
]


def scrub(text: str) -> str:
    s = str(text or "")
    for rx, rep in _SCRUB:
        s = rx.sub(rep, s)
    return s


def safe_name(s: str, n=80) -> str:
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "-", str(s or "")).strip()[:n] or "note"


def hidden_set() -> set:
    try:
        from engine import hidden_bots
        return set(hidden_bots.hidden() or ())
    except Exception:  # noqa: BLE001
        return {"blitz"}


def bot_of(key: str) -> str | None:
    k = str(key or "").lower()
    if k in BOTS:
        return k
    if "atlas" in k or k in ("acct_b", "acctb", "account_b", "second"):
        return "atlas"
    if "blitz" in k or "scalp" in k or "acct_c" in k or "acctc" in k:
        return "blitz"
    if k.startswith("lit") or k in ("zlarior", "mffu50k"):
        return "lit"
    return None


# ------------------------------------------------------------------------------------------------ config
def load_cfg(env=None, path=CFG_PATH) -> dict:
    e = os.environ if env is None else env
    c = read_json(path, {}) or {}
    v = (e.get("LE_OBSIDIAN_VAULT") or c.get("vault") or "").strip()
    return {"vault": v, "last": c.get("last") or {}, "path": path, "off": bool(c.get("off"))}


def save_cfg(cfg: dict, path=CFG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keep = {"vault": cfg.get("vault") or "", "last": cfg.get("last") or {}}
    if cfg.get("off"):
        keep["off"] = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=1)
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------ the notes (pure: text in, text out)
# the trade pictures' strategy keys (engine/trade_chart.STRATS): the 50K's own LIT trades are 'lit'; ATLAS's strategies draw under their
# own keys (also as paper shadows), so an ATLAS picture is used only when it matches one of ATLAS's real trades on the board
CHART_LIT = ("lit",)
CHART_ATLAS = ("ema_lon_vix", "macd_sweep", "atlas", "acct_b", "second")


def trade_rows(live: dict, charts_ix: dict, day: str, hide: set, charts: str = CHARTS) -> list:
    """the day's trades of the shown bots: [{bot, name, hhmm, side, qty, entry, stop, target, exit, usd, r, open, how, pic, note}]"""
    out, seen, atlas_pics = [], set(), []
    for key, rows in ((charts_ix or {}).get("strategies") or {}).items():
        k = str(key).lower()
        b = "lit" if k in CHART_LIT else "atlas" if (k in CHART_ATLAS or k.startswith("atlas")) else None
        if not b or b in hide:
            continue
        for r in rows or []:
            if not isinstance(r, dict) or r.get("src") == "paper":
                continue
            t = et_of(r.get("entry_t"))
            if not t or t.strftime("%Y-%m-%d") != day:
                continue
            pic = os.path.join(charts, key, str(r.get("tid") or "") + ".png") if r.get("tid") else None
            if b == "atlas":                                     # only beside a real ATLAS trade (below)
                atlas_pics.append((_secs(r.get("entry_t")), pic))
                continue
            out.append(_trade(b, r, t, pic))
            seen.add((b, _secs(r.get("entry_t"))))
    board = (live or {}).get("board") or {}
    for r in board.get("trades") or []:
        if not isinstance(r, dict):
            continue
        b = bot_of(r.get("acct") or r.get("key") or "lit")
        if not b or b in hide or r.get("src") == "paper":
            continue
        t = et_of(r.get("entry_t"))
        if not t or t.strftime("%Y-%m-%d") != day:
            continue
        et_s = _secs(r.get("entry_t"))
        if any(bb == b and abs(s - et_s) < 120 for bb, s in seen):
            continue
        pic = next((pp for s, pp in atlas_pics if abs(s - et_s) < 120), None) if b == "atlas" else None
        out.append(_trade(b, r, t, pic))
        seen.add((b, et_s))
    out.sort(key=lambda x: x["hhmm"])
    return out


def _secs(v) -> int:
    x = int(num(v) or 0)
    return x // 1000 if x > 1e12 else x


def _trade(b, r, t, pic):
    name = BOTS[b][0]
    hhmm = t.strftime("%H%M")
    side = str(r.get("side") or r.get("dir") or "").lower()
    side = "long" if side in ("long", "buy", "1", "l") else "short" if side in ("short", "sell", "-1", "s") else side or "-"
    note = safe_name(f"{t.strftime('%Y-%m-%d')} {name} {hhmm}")
    return {"bot": b, "name": name, "hhmm": hhmm, "time": t.strftime("%H:%M ET"), "side": side, "qty": num(r.get("qty")),
            "entry": num(r.get("entry")), "stop": num(r.get("stop")), "target": num(r.get("target")), "exit": num(r.get("exit")),
            "usd": num(r.get("usd")), "r": num(r.get("r")), "open": bool(r.get("open")), "how": str(r.get("exit_kind") or "")[:20],
            "pic": pic if pic and os.path.isfile(pic) else None, "note": note}


def px(v) -> str:
    return "-" if v is None else f"{v:,.2f}"


def trade_note(tr: dict) -> str:
    res = "open" if tr["open"] else f"{money(tr['usd'], True)}" + (f" ({tr['r']:+.2f}R)" if tr["r"] is not None else "")
    L = ["---", "type: trade", f"bot: {tr['name']}", f"day: {tr['note'][:10]}", f"result_usd: {'' if tr['usd'] is None else round(tr['usd'], 2)}",
         "tags: [olympus, trade, " + tr["bot"] + "]", "---", f"# {tr['name']} {tr['side']} at {tr['time']}", "",
         f"Day: [[Bots {tr['note'][:10]}]] · Bot: {tr['name']} · Result: **{res}**", "",
         "| What | Value |", "|---|---|", f"| Side | {tr['side']}{'' if tr['qty'] is None else ' ' + str(int(tr['qty'])) + ' micros'} |",
         f"| Entry | {px(tr['entry'])} |", f"| Stop | {px(tr['stop'])} |", f"| Target | {px(tr['target'])} |",
         f"| Exit | {px(tr['exit'])}{' (' + tr['how'] + ')' if tr['how'] else ''} |", ""]
    if tr["pic"]:
        L += ["![[" + tr["note"] + ".png]]", ""]
    else:
        L += ["(No picture yet: the bot draws it a few minutes after the trade.)", ""]
    L += ["## My notes", "", "- "]
    return "\n".join(L) + "\n"


def day_note(day: str, live: dict, trades: list, hide: set, now_s: float) -> str:
    board = (live or {}).get("board") or {}
    pc = (live or {}).get("pc") or {}
    t = et_of(pc.get("t") or board.get("data_t"))
    age = None if not t else max(0, int(now_s - t.timestamp()))
    fresh = "no report from the PC yet" if age is None else ("fresh (" + str(age // 60) + " min old)" if age < 1200 else
                                                           f"OLD: last report {t.strftime('%a %H:%M ET')}")
    L = ["---", "type: day", f"day: {day}", "tags: [olympus, day]", "---", f"# {day}: the bots' day", "",
         f"Data: {fresh}. Back to [[OLYMPUS Index]].", "", "| Bot | Drawdown left | Today | Balance | Trades | Status |", "|---|---|---|---|---|---|"]
    tot, any_pnl = 0.0, False
    for k in ("lit", "atlas", "blitz"):
        if k in hide:
            continue
        c = board.get(k) or {}
        if not isinstance(c, dict) or (not c and k == "blitz"):
            continue
        nm, size = BOTS[k]
        room, mll = num(c.get("room")), num(c.get("mll"))
        dd = "-" if room is None else money(room) + (f" of {money(mll)}" if mll else "")
        pnl = num(c.get("today_pnl"))
        if pnl is not None:
            tot += pnl
            any_pnl = True
        st = scrub(str(c.get("status") or ("off" if c.get("off") else "")))[:60].replace("|", "/")
        L.append(f"| {nm} {size} | {dd} | {money(pnl, True)} | {money(c.get('balance'))} | {int(num(c.get('trades_today')) or 0)} | {st or '-'} |")
    L += ["", f"**Both bots today: {money(tot, True) if any_pnl else '-'}**", "", "## Trades", ""]
    if trades:
        for tr in trades:
            res = "open" if tr["open"] else money(tr["usd"], True) + (f", {tr['r']:+.2f}R" if tr["r"] is not None else "")
            L.append(f"- [[{tr['note']}]]: {tr['name']} {tr['side']} at {tr['time']} → {res}" + (" (picture)" if tr["pic"] else ""))
    else:
        L.append("- No trade today.")
    L += ["", "## How I feel / what I learned", "", "- ", ""]
    return "\n".join(L) + "\n"


def keep_ticks(new: str, old: str) -> str:
    """the owner's ticks survive a rewrite: a '- [ ] x' in the new text becomes '- [x] x' when the old note had it ticked"""
    done = {m.group(1).strip() for m in re.finditer(r"^\s*- \[[xX]\] (.+)$", old or "", re.M)}
    if not done:
        return new
    return re.sub(r"^(\s*)- \[ \] (.+)$", lambda m: f"{m.group(1)}- [x] {m.group(2)}" if m.group(2).strip() in done else m.group(0), new, flags=re.M)


def business_note(doc: dict | None, demo: bool) -> str:
    L = ["---", "type: checklist", "tags: [olympus, business]", "---", "# Business checklist", "",
         "Tick the boxes here: the sync keeps your ticks. Back to [[OLYMPUS Index]].", ""]
    if demo:
        L += ["> Example list (the PC has no business.json yet: run `python tools/biz_publish.py`).", ""]
    for m in (doc or {}).get("models") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        L += [f"## {scrub(m['name'])}{' (paused)' if m.get('paused') else ''}", ""]
        if m.get("next"):
            L.append(f"- [ ] Next: {scrub(m['next'])}")
        for x in m.get("first_dollar") or []:
            L.append(f"- [ ] {scrub(x)}")
        real = num(m.get("real_usd_month"))
        L += ["", f"Earned so far: {money(real or 0)} a month (real money only).", ""]
    wk = (doc or {}).get("week") or []
    if wk:
        L += ["## This week", ""]
        for d in wk:
            if isinstance(d, dict):
                L.append(f"### Day {d.get('day')}: {scrub(d.get('title') or '')}")
                L += [f"- [ ] {scrub(x)}" for x in d.get("tasks") or [] if isinstance(x, str)]
                L.append("")
    return "\n".join(L) + "\n"


def research_note(day: str, md: str) -> str:
    body = scrub(md).strip()
    return "\n".join(["---", "type: research", f"day: {day}", "tags: [olympus, research, learning]", "---",
                      f"# Learning {day}", "", "The PC's nightly learning (research only, never a live setting). Back to [[OLYMPUS Index]].", "", body, ""])


def state_note(md: str) -> str:
    return "\n".join(["---", "type: state", "tags: [olympus, state]", "---", "Back to [[OLYMPUS Index]].", "", scrub(md).strip(), ""])


def index_note(days: list, research: list, today: str, trades: list, now_s: float) -> str:
    t = et_of(now_s)
    L = ["---", "type: index", "tags: [olympus, index]", "---", "# OLYMPUS Index (synced from the PC)", "",
         f"Updated {t.strftime('%a %b %d, %H:%M ET') if t else '-'} by the PC (every 15 minutes). Written by tools/obsidian_sync.py: "
         "edit the 'My notes' parts freely; the rest is rewritten.", "",
         "## Today", f"- [[Bots {today}]]" + (f": {len(trades)} trade" + ("s" if len(trades) != 1 else "") if trades else ": no trade yet"), "",
         "## Start here", "- [[STATE]]: what's live, what's waiting, what's next", "- [[Business checklist]]", "", "## Last days"]
    L += [f"- [[{d}]]" for d in days[:KEEP_DAYS]] or ["- (none yet)"]
    L += ["", "## Research (nightly learning)"]
    L += [f"- [[{r}]]" for r in research[:10]] or ["- (none yet: the PC writes one after its first learning night)"]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------ writing
def put(path: str, text: str, wrote: list, base: str):
    old = read_text(path) if os.path.isfile(path) else None
    if old == text:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    wrote.append(os.path.relpath(path, base))


def sync(vault: str, now_s=None, root: str = ROOT, live_path=LIVE, charts=CHARTS, learn=LEARN, biz=BIZ, state=STATE, hide=None) -> dict:
    """one sync into <vault>/OLYMPUS/Sync. Returns {ok, wrote: [paths], day, trades, why?}. Never deletes a file."""
    now_s = time.time() if now_s is None else now_s
    if not vault or not os.path.isdir(vault):
        return {"ok": False, "why": f"vault folder not found: {vault or '(not set)'}", "wrote": []}
    base = os.path.join(vault, SUB)
    hide = hidden_set() if hide is None else set(hide)
    day = today_et(now_s)
    live = read_json(live_path, {}) or {}
    trades = trade_rows(live, read_json(os.path.join(charts, "index.json"), {}) or {}, day, hide, charts)
    wrote = []
    for tr in trades:
        if tr["pic"]:
            dst = os.path.join(base, "Pictures", tr["note"] + ".png")
            if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(tr["pic"]):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(tr["pic"], dst)
                wrote.append(os.path.relpath(dst, base))
        put(os.path.join(base, "Trades", tr["note"] + ".md"), trade_note(tr), wrote, base)
    dpath = os.path.join(base, "Days", f"Bots {day}.md")
    new_day = day_note(day, live, trades, hide, now_s)
    old_day = read_text(dpath)
    if old_day and "## How I feel / what I learned" in old_day:     # keep what the owner wrote under the last heading
        mine = old_day.split("## How I feel / what I learned", 1)[1]
        new_day = new_day.split("## How I feel / what I learned", 1)[0] + "## How I feel / what I learned" + mine
    put(dpath, new_day, wrote, base)
    md = read_text(learn)
    if md.strip():
        ld = day
        m = re.search(r"(20\d\d-\d\d-\d\d)", md[:400])
        if m:
            ld = m.group(1)
        put(os.path.join(base, "Research", f"Learning {ld}.md"), research_note(ld, md), wrote, base)
    doc, demo = read_json(os.path.join(biz, "business.json")), False
    if not isinstance(doc, dict) or not doc.get("models"):
        doc, demo = read_json(os.path.join(biz, "fixture.json"), {}) or {}, True
    bpath = os.path.join(base, "Business checklist.md")
    put(bpath, keep_ticks(business_note(doc, demo), read_text(bpath)), wrote, base)
    st = read_text(state)
    if st.strip():
        put(os.path.join(base, "STATE.md"), state_note(st), wrote, base)
    days = sorted((f[:-3] for f in os.listdir(os.path.join(base, "Days")) if re.match(r"^Bots \d{4}-\d\d-\d\d\.md$", f)), reverse=True) \
        if os.path.isdir(os.path.join(base, "Days")) else []
    rdir = os.path.join(base, "Research")
    research = sorted((f[:-3] for f in os.listdir(rdir) if f.endswith(".md")), reverse=True) if os.path.isdir(rdir) else []
    put(os.path.join(base, "OLYMPUS Index.md"), index_note(days, research, day, trades, now_s), wrote, base)
    return {"ok": True, "wrote": wrote, "day": day, "trades": len(trades), "folder": base}


def maybe_run(now_s=None, say=print, env=None, cfg_path=CFG_PATH) -> dict | None:
    """tools/pc_report.py's 15-minute hook: one sync when a vault is set and the last one is 10+ minutes old. Never raises."""
    try:
        e = os.environ if env is None else env
        if e.get("LE_PR_NO_NET") == "1" and cfg_path == CFG_PATH:
            return None                                       # the PC report's tests: never touch a real vault
        cfg = load_cfg(e, cfg_path)
        if not cfg["vault"] or cfg["off"]:
            return None
        now = time.time() if now_s is None else now_s
        if now - float((cfg["last"] or {}).get("t") or 0) < EVERY_S:
            return None
        res = sync(cfg["vault"], now)
        brain_t = float((cfg["last"] or {}).get("brain_t") or 0)
        if res["ok"] and now - brain_t >= BRAIN_EVERY_S:      # ZEUS Brain (tools/obsidian_brain.py): <vault>/OLYMPUS/ZEUS Brain, once an hour, soft
            try:
                from tools import obsidian_brain as _brain
                br = _brain.build(cfg["vault"], standalone=False)
                brain_t = now
                if br.get("wrote") or br.get("removed"):
                    say(f"  [OK]  ZEUS Brain: {br['notes']} notes, {len(br['wrote'])} updated in OLYMPUS/ZEUS Brain")
            except Exception as ex:  # noqa: BLE001
                say(f"  [..] ZEUS Brain skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        cfg["last"] = {"t": int(now), "ok": res["ok"], "n": len(res.get("wrote") or []), "why": res.get("why", ""), "brain_t": int(brain_t)}
        save_cfg(cfg, cfg_path)
        if res["ok"] and res["wrote"]:
            say(f"  [OK]  Obsidian: {len(res['wrote'])} note(s) updated in OLYMPUS/Sync")
        elif not res["ok"]:
            say(f"  [..] Obsidian sync skipped: {res['why']}")
        return res
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] Obsidian sync skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools/obsidian_sync.py", description="Write the bots' day, trades, research, business and STATE into your Obsidian vault.")
    ap.add_argument("--setup", metavar="VAULT", help="save your vault folder (data/obsidian_sync.json, gitignored) and sync once")
    ap.add_argument("--status", action="store_true", help="the vault folder and the last sync")
    ap.add_argument("--off", action="store_true", help="stop the 15-minute sync (keeps the notes)")
    a = ap.parse_args(argv)
    cfg = load_cfg()
    if a.off:
        cfg["off"] = True
        save_cfg(cfg)
        print("  [OK]  Obsidian sync off (your notes stay). Turn it on again with --setup.")
        return 0
    if a.setup:
        v = os.path.abspath(os.path.expanduser(a.setup.strip().strip('"')))
        if not os.path.isdir(v):
            print(f"  [X]  folder not found: {v}\n       Open Obsidian -> the vault switcher (bottom left) -> 'Show in system explorer' and copy that path.")
            return 1
        cfg.update(vault=v, off=False)
        save_cfg(cfg)
        print(f"  [OK]  vault saved: {v}")
    if a.status:
        print(f"  vault: {cfg['vault'] or '(not set)'}   last sync: {cfg['last'] or '-'}")
        return 0
    if not cfg["vault"]:
        print('  [..] no vault yet: python tools/obsidian_sync.py --setup "C:\\path\\to\\your\\vault"')
        return 0
    res = sync(cfg["vault"])
    cfg["last"] = {"t": int(time.time()), "ok": res["ok"], "n": len(res.get("wrote") or []), "why": res.get("why", "")}
    save_cfg(cfg)
    if not res["ok"]:
        print(f"  [X]  {res['why']}")
        return 1
    print(f"  [OK]  {len(res['wrote'])} file(s) updated in {res['folder']} (today {res['day']}, {res['trades']} trade(s))")
    for w in res["wrote"][:30]:
        print("        " + w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
