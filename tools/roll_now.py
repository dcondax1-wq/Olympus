"""ROLL.bat: the quarterly contract roll in one double-click (next: Dec 2026, MNQ 12-26 -> MNQ 03-27; docs/ROLL_DEC_2026.md).

What switches, and who switches it (read from the code, 2026-11-13):
  orders   engine/ninjatrader.nt_instrument picks the contract by the ET date: MNQ 12-26 through Wed 2026-12-09, MNQ 03-27 from
           Thu 2026-12-10 00:00 ET (8 days before the Dec 18 expiry). LIT, ATLAS and BLITZ use the same adapter and are all flat
           by 15:55 ET, so nothing is open at that midnight. Nothing to do.
  add-on   no-chart mode (ninjatrader/LE_Feed.cs): the bot rewrites le_feed\\feed_instruments.txt by the same date
           (engine/live.py _feed_addon_tick) and the add-on follows within 3 minutes. Nothing to click.
  chart    chart mode (LE_BarFeed on a chart): only you can switch a NinjaTrader chart. Until it is on the order month the bot
           sends no new entry (the roll guard). This script tells you the one click, waits for it and checks it.
  pin      a contract typed once into the bot's saved start (data/autostart.json "nt_instrument"): it never follows the roll,
           and after the roll the guard refuses every entry. This script removes an OLD pin (a backup is kept).

It acts only when that is safe: from the evening before the roll (after 15:55 ET) or any day after it, and only while
NinjaTrader shows no open MNQ / NQ position and the bot's heartbeat shows no trade. It never places, changes or cancels an
order, never arms anything, never starts or stops the bot and never edits live_model*.json or a strategy setting.

  python tools/roll_now.py              the roll (ROLL.bat): checks, removes an old pin, waits up to 15 min for the chart click
  python tools/roll_now.py --check      only says where things stand (changes nothing, never waits)
  python tools/roll_now.py --wait 0     do not wait for the chart click
Exit 0 = rolled or nothing to do, 1 = something for you to do (the last line says what), 2 = not now (too early or in a trade).
Tests: tests/test_roll_now.py (temp folders, fake NinjaTrader files, fake clock).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import roll_watch  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402

EVE_FROM_MOD = 956                     # 15:56 ET: every bot is flat (15:55) on the evening before the roll
HB_FRESH_S = 20 * 60
WAIT_DEFAULT_S = 900
POLL_S = 10
PIN_KEYS = ("nt_instrument", "nt_instrument_mini")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), nt.ET)


# ------------------------------------------------------------------------------------------------ what this PC shows
def open_positions(folder: str) -> list:
    """Every non-flat MNQ / NQ position NinjaTrader reports (outgoing\\<instrument>_<account>_Position.txt, any account)."""
    out = []
    d = os.path.join(folder, "outgoing")
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        if not n.lower().endswith("_position.txt"):
            continue
        inst, _, acct = n[: -len("_position.txt")].rpartition("_")
        k = nt.inst_key(inst)
        if not k or k[0] not in ("MNQ", "NQ"):
            continue
        pos = nt.parse_position(nt._read_text(os.path.join(d, n)))
        if pos and pos["side"] != "FLAT":
            out.append(f"{pos['side']} {pos['qty']} {inst} on {acct}")
    return out


def heartbeat_trade(root: str, now: int):
    """True when the bot's own heartbeat (under 20 min old) shows an open trade (LIT, or BLITZ on account C), False when it
    shows none, None when there is no fresh heartbeat."""
    try:
        from tools.pc_report import read_heartbeat
        hb, _push, _src = read_heartbeat(root)
    except Exception:
        hb = None
    if not isinstance(hb, dict) or not hb.get("t") or now - int(hb["t"]) > HB_FRESH_S:
        return None
    ac = hb.get("account_c") if isinstance(hb.get("account_c"), dict) else {}
    acct = hb.get("acct") if isinstance(hb.get("acct"), dict) else {}
    return bool(hb.get("position") or acct.get("position") or ac.get("open"))


def autostart_path(root: str) -> str:
    return os.path.join(root, "data", "autostart.json")


def pins(root: str) -> dict:
    """{key: contract} pinned in the bot's saved start (data/autostart.json cfg)."""
    try:
        with open(autostart_path(root), encoding="utf-8") as fh:
            cfg = (json.load(fh) or {}).get("cfg") or {}
    except Exception:
        return {}
    return {k: str(cfg[k]).strip() for k in PIN_KEYS if cfg.get(k)}


def read_list(folder: str) -> list:
    txt = nt._read_text(os.path.join(folder, nt.FEED_DIR, nt.FEED_INSTRUMENTS))
    return [x.strip() for x in str(txt or "").splitlines() if x.strip()]


def gather(now=None, folder: str | None = None, root: str = ROOT, cfg: dict | None = None) -> dict:
    now = int(now if now is not None else time.time())
    folder = folder or nt.default_folder()
    cfg = dict(cfg or {})
    e = _et(now)
    today = e.date()
    st = roll_watch.fact(folder, cfg, now)
    addon = nt.read_feed_status(folder, now)
    cfg_feed = {k: v for k, v in cfg.items() if k != "nt_instrument"}
    return {"now": now, "today": today, "mod": e.hour * 60 + e.minute, "folder": folder, "root": root, "cfg": cfg,
            "folder_ok": os.path.isdir(folder), "st": st, "orders": nt.nt_instrument("MNQ", today),
            "next": roll_watch.next_roll(today), "last": roll_watch.last_roll(today),
            "addon": bool(addon and addon.get("fresh")), "addon_installed": nt.addon_installed(folder),
            "feed_list": read_list(folder), "want_list": nt.feed_instruments(cfg_feed, today),
            "open": open_positions(folder), "hb_trade": heartbeat_trade(root, now), "pins": pins(root)}


# ------------------------------------------------------------------------------------------------ the decision (pure)
def target(f: dict):
    """(contract month the chart must be on, why) or (None, why not yet). The evening before the roll (after 15:56 ET) the
    target is the NEW month; otherwise today's order month."""
    nx = f.get("next")
    if nx:
        day, _old, new = nx
        n = (day - f["today"]).days
        if n == 1 and f["mod"] >= EVE_FROM_MOD:
            return new, "eve"
        if n == 1:
            return None, f"too early: run ROLL.bat today after 16:00 ET ({day - dt.timedelta(days=1):%a %b %d})"
    return f["orders"], "now"


def _month(name) -> str:
    return str(name or "").split(" ")[-1]


def old_pins(f: dict, tgt: str) -> dict:
    te = nt.contract_expiry(tgt)
    return {k: v for k, v in (f.get("pins") or {}).items() if nt.contract_expiry(v) and te and nt.contract_expiry(v) < te}


def chart_on(st: dict, tgt: str) -> bool:
    ce = nt.contract_expiry((st or {}).get("chart"))
    return bool(ce and ce == nt.contract_expiry(tgt))


def decide(f: dict) -> dict:
    """{"code": done | todo | busy | early | nothing, "target", "do": [...], "say": [...]} from gather()'s facts."""
    st = f.get("st") or {}
    tgt, why = target(f)
    nx = f.get("next")
    if tgt is None:
        return {"code": "early", "target": None, "do": [], "say": [why[0].upper() + why[1:] + ". Nothing changed."]}
    chart_ok = chart_on(st, tgt) or f.get("addon")
    pins_old = old_pins(f, tgt)
    list_old = f.get("addon") and why == "now" and f.get("feed_list") != f.get("want_list")
    if why == "now" and chart_ok and not pins_old and not list_old:
        more = ""
        if nx:
            day, _o, new = nx
            more = (f" Next roll {day:%a %b %d} ({new}): run ROLL.bat on {day - dt.timedelta(days=1):%a %b %d} after 16:00 ET"
                    if (day - f["today"]).days > 1 else "")
        return {"code": "nothing", "target": tgt, "do": [],
                "say": [f"Nothing to roll: chart and orders on {_month(tgt)}.{more}"]}
    busy = list(f.get("open") or [])
    if f.get("hb_trade"):
        busy.append("the bot's heartbeat shows an open trade")
    if busy:
        return {"code": "busy", "target": tgt, "do": [],
                "say": [f"Not now: {'; '.join(busy)}. Run ROLL.bat again once every bot is flat (15:55 ET at the latest). "
                        "Nothing changed."]}
    do = []
    if pins_old:
        do.append(("unpin", pins_old))
    if list_old:
        do.append(("feed_list", f.get("want_list")))
    if not chart_ok and nt.contract_expiry(st.get("chart")) is None:
        do.append(("chart_unknown", tgt))      # no / a continuous contract file: the click cannot be checked from here
    elif not chart_ok:
        do.append(("chart", tgt))
    return {"code": "todo", "target": tgt, "do": do, "say": []}


# ------------------------------------------------------------------------------------------------ the actions
def unpin(root: str, keys, now: int) -> str:
    """Remove old pinned contracts from data/autostart.json (backup next to it). Returns the backup path."""
    p = autostart_path(root)
    with open(p, encoding="utf-8") as fh:
        rec = json.load(fh)
    bak = f"{p}.before-roll-{_et(now):%Y%m%d-%H%M}"
    shutil.copy2(p, bak)
    cfg = rec.get("cfg") or {}
    for k in keys:
        cfg.pop(k, None)
    rec["cfg"] = cfg
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    os.replace(tmp, p)
    return bak


def click_text(st: dict, tgt: str) -> list:
    root = (st or {}).get("root") or str((st or {}).get("chart") or "MNQ").split(" ")[0] or "MNQ"
    to = f"{root} {_month(tgt)}"
    return [f"1. NinjaTrader: right-click the {root} chart with LE_BarFeed > Instrument > {to} (or click the chart, type {to}, Enter).",
            "2. Right-click > Data Series: Days to load 30, OK.",
            "3. File (Control Center: Workspaces) > Save Workspace. Leave the bot running."]


def run(f: dict, check_only: bool = False, wait_s: int = WAIT_DEFAULT_S, regather=None, sleep=time.sleep, say=print,
        roll_check=None) -> int:
    """Carry out decide(f). regather() -> fresh facts while waiting for the chart click (tests pass a fake)."""
    d = decide(f)
    rows = [("ORDERS", f"{f['orders']} today" + (f"; {f['next'][2]} from {f['next'][0]:%a %b %d} 00:00 ET by themselves"
                                                  if f.get("next") and (f["next"][0] - f["today"]).days <= 7 else ""))]
    st = f.get("st") or {}
    if f.get("addon"):
        rows.append(("BARS", "LE_Feed add-on (no chart): it follows the roll by itself"
                     + (f" ({', '.join(f.get('feed_list') or [])})" if f.get("feed_list") else "")))
    else:
        rows.append(("CHART", f"{st.get('chart') or 'unknown (no LE_BarFeed contract file)'}"))
    pz = f.get("pins") or {}
    rows.append(("PIN", ", ".join(f"{k} {v}" for k, v in pz.items()) if pz else "none (the bot follows the date)"))
    rows.append(("FLAT", "yes" if not f.get("open") and not f.get("hb_trade") else "NO: " + "; ".join(
        (f.get("open") or []) + (["heartbeat shows a trade"] if f.get("hb_trade") else []))))
    for k, v in rows:
        say(f"  {k:<7} {v}")
    say("")
    if d["code"] in ("early", "busy", "nothing") or check_only:
        for x in d["say"]:
            say(f"  {x}")
        if check_only and d["code"] == "todo":
            say("  To do: " + "; ".join(a[0] for a in d["do"]) + " (double-click ROLL.bat; --check changes nothing)")
        return {"early": 2, "busy": 2, "nothing": 0}.get(d["code"], 1)
    tgt = d["target"]
    for kind, arg in d["do"]:
        if kind == "unpin":
            bak = unpin(f["root"], list(arg), f["now"])
            say(f"  [OK]  removed the pinned contract {', '.join(arg.values())} from the bot's saved start (backup: "
                f"{os.path.basename(bak)}). The bot follows the date from its next start.")
            say("        The bot that runs now keeps it in memory: once, while flat, double-click STOP_BOT.bat, then BOTS_BACK.bat.")
        elif kind == "feed_list":
            ok = nt.sync_feed_instruments(f["folder"], {k: v for k, v in (f.get("cfg") or {}).items() if k != "nt_instrument"},
                                          f["today"])
            say(f"  [OK]  told the LE_Feed add-on: {', '.join(arg)}" + ("" if ok else " (it already had it)"))
        elif kind == "chart_unknown":
            say(f"  The chart's contract cannot be read here ({st.get('chart') or 'no LE_BarFeed contract file'}). Make sure the chart")
            say(f"  with LE_BarFeed is on {_month(tgt)}:")
            for ln in click_text(st, tgt):
                say(f"     {ln}")
            say("  [FIX] Open NinjaTrader with the LE_BarFeed chart on a dated contract (not ##-##), then double-click ROLL.bat again.")
            return 1
        elif kind == "chart":
            say("  Your one job now (the bot waits; every bot is flat):")
            for ln in click_text(st, tgt):
                say(f"     {ln}")
            if wait_s <= 0 or regather is None:
                say("  [FIX] Do the click above, then double-click ROLL.bat again.")
                return 1
            say(f"  Waiting up to {wait_s // 60} minutes for the chart to show {_month(tgt)} ...")
            t0 = time.monotonic()
            ok = False
            while time.monotonic() - t0 < wait_s:
                sleep(POLL_S)
                g = regather()
                if chart_on(g.get("st") or {}, tgt):
                    ok = True
                    f = g
                    break
            if not ok:
                say(f"  [FIX] The chart is still not on {_month(tgt)}. Do the click above, then double-click ROLL.bat again.")
                return 1
            say(f"  [OK]  chart on {(f.get('st') or {}).get('chart')}")
    if roll_check is not None:
        try:
            r = roll_check()
            if r:
                say("  History check: " + r)
        except Exception as e:
            say(f"  History check skipped ({e.__class__.__name__})")
    nx = f.get("next")
    if target(f)[1] == "eve" and nx:
        say(f"  [OK]  Roll ready. Orders follow at 00:00 ET {nx[0]:%a %b %d} by themselves. Nothing else to do tonight.")
    else:
        say(f"  [OK]  Roll done: the bot trades {_month(tgt)}.")
    return 0


def history_check() -> str:
    """tools/roll_check.py in one line (the bars' basis and NinjaTrader's merge policy)."""
    import io
    import contextlib
    from tools import roll_check
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = roll_check.main([])
    lines = [ln.strip() for ln in buf.getvalue().splitlines() if ln.strip()]
    if code == 0:
        return "OK (chart, orders and history on one contract)"
    acts = [ln[2:] for ln in lines if ln.startswith("- ")]
    return "ACTION: " + ("; ".join(acts) if acts else (lines[-1] if lines else "see python tools/roll_check.py"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/roll_now.py", description="The contract roll in one double-click (ROLL.bat).")
    ap.add_argument("--check", action="store_true", help="only say where things stand")
    ap.add_argument("--wait", type=int, default=WAIT_DEFAULT_S, help="seconds to wait for the chart click (0 = no wait)")
    ap.add_argument("--folder", default=None, help="Documents\\NinjaTrader 8")
    a = ap.parse_args(argv)
    print("  ROLL: the quarterly contract switch (docs/ROLL_DEC_2026.md)")
    f = gather(folder=a.folder)
    if not f["folder_ok"]:
        print(f"  [FIX] NinjaTrader's folder was not found ({f['folder']}). Open NinjaTrader once, then double-click ROLL.bat again.")
        return 1
    return run(f, check_only=a.check, wait_s=a.wait, regather=lambda: gather(folder=a.folder), roll_check=history_check)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("  stopped. Nothing else changed.")
        sys.exit(1)
