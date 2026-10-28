"""Live board (engine/live_board.py, engine/board_api.py, boardcore.js on both dashboards; 2026-10-26, read-only).

  a. entry windows: next LIT / ATLAS windows as absolute ET times (weekend, open now, early close, full closure, EMA no Monday)
  b. Right now: Zlarior (balance / room / $ to go / today / waiting / size now / stage) and ATLAS (members, next window, size)
  c. blocks: clock drift / feed / stopped / kill / account B off, each with its one-line fix, de-duplicated
  d. today's map: levels by price, points and $ per micro, the VIX objective and the 18:00 open
  e. health strip: poll time amber above 5 s, clock red when the guard blocks, old vs recent error, ages with absolute times
  f. week and eval progress: trades vs the goal, odds rows, $ a month expected vs actual pace
  g. trade log: PC trades, account-B rows paired and filled from the member's paper trade, paper rows, newest first
  h. build() never raises (garbage in), JSON safe; site_block over a data.json-like dict
  i. PC API GET /api/next/board on the fake PC bot: 200, read-only (bot unchanged, no file written), cached
  j. live.json carries the board and stays under 64 KB; fit() trims the board's trades first
  k. static wiring: boardcore.js byte-identical on both apps, phone loads board.js after clean.js, sw bumped, PC page /
     sidebar / Command center slot, only GETs; node syntax check + a node render of BoardUI.page / csv

  python -X utf8 -m tests.test_live_board
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from engine import live_board as LB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {str(detail)[:300]}"), flush=True)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


# ------------------------------------------------------------------------------------------------ a heartbeat-shaped fixture
NOW = ts(2026, 10, 25, 22, 25)          # Sunday evening ET: the session of Mon 2026-10-26 is open, entries from 02:00


def hb_fixture(now=NOW):
    """The shape of the PC's real heartbeat of 2026-10-25 22:25 ET (account names replaced)."""
    return {
        "t": now, "running": True, "adapter": "ninjatrader", "position": False, "host": "TEST-PC", "model": "lit", "every_s": 300,
        "model_state": "LIT: waiting for London sweep (entries from 02:00 ET)",
        "acct": {"v": 1, "t": now, "account": {"name": "MFFUEVTEST50K", "adapter": "ninjatrader", "kind": "live", "label": "LIVE ACCOUNT"},
                 "running": True, "kill": False, "eval": {"start": "2026-10-19", "days": {"0000-00-00": -100.0},
                                                          "anchor": {"as_of": "2026-10-23", "balance": 49710.8, "floor": 48168.2, "set_t": now - 3000}},
                 "position": None, "orders": [], "trades": [
                     {"day": "2026-10-23", "entry_t": ts(2026, 10, 23, 3, 10), "exit_t": ts(2026, 10, 23, 4, 0), "side": "SHORT", "qty": 6,
                      "entry": 29500.0, "stop": 29540.0, "target": 29200.0, "exit_px": 29540.25, "exit": "STOP", "r": -1.01, "pnl": -495.4}],
                 "day_pnl": 0, "since_t": now - 900000},
        "health": {"v": 1, "t": now, "account": {"name": "MFFUEVTEST50K", "adapter": "ninjatrader", "is_live": True, "label": "LIVE", "armed": True},
                   "running": True, "kill": False, "model": "lit",
                   "feed": {"source": "ninjatrader", "used": "ninjatrader", "no_yahoo": True, "block": None, "tf": "5m",
                            "last_5m_t": now - 350, "age_5m_s": 50, "last_1m_t": now - 110, "age_1m_s": 50, "stale": False,
                            "market_open": True, "entries_blocked": False},
                   "poll": {"last_t": now - 48, "age_s": 48, "last_ok_t": now - 48, "errors": 0, "consecutive_errors": 0,
                            "last_error": "poll failed: TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'",
                            "last_error_t": now - 1291, "poll_ms": 29392},
                   "lit": {"stage": "levels", "text": "LIT: waiting for London sweep", "price": 29107.75},
                   "eval_life": {"status": "open", "trading": "trading"},
                   "nt": {"connections": {"Simulation": "CONNECTED"}, "connected": True, "last_error": None}},
        "brain": {"v": 1, "kind": "le-brain", "t": now - 48, "day": "2026-10-26", "price": 29107.75, "bar_hm": "22:20", "atr": 43.03,
                  "stage": {"key": "sweep", "n": 2, "label": "Sweep", "dir": None,
                            "waiting": "Before 02:00 ET (no entries yet): Waiting for price to sweep a level by >= 0.5 ATR (= 21.4 pts). "
                                       "BLOCKED: PC clock 5.0 s ahead of internet time (max 5 s) (no new entry while this lasts)."},
                  "rules": {"depth": 0.5, "monday": True, "monday_today": "high"},
                  "day_trades": 0, "day_pnl": 0,
                  "stages": [["levels", "done"], ["sweep", "now"], ["inducement", "todo"], ["displacement", "todo"], ["cisd5", "todo"],
                             ["limit", "todo"], ["cisd1m", "todo"], ["entry", "todo"], ["trade", "todo"], ["done", "todo"]],
                  "levels": [{"label": "PWH", "price": 30114.0, "side": "H", "kind": "pw", "taken": False},
                             {"label": "equal highs", "price": 29379.5, "side": "H", "kind": "buildup", "taken": False},
                             {"label": "PDH", "price": 29325.75, "side": "H", "kind": "pd", "taken": True, "taken_hm": "18:45"},
                             {"label": "PDL", "price": 28986.25, "side": "L", "kind": "pd", "taken": False}],
                  "sizing": {"mode": "two_week", "what": "a typical 46-pt stop with the target one VIX move away (359 pts) - no setup is live",
                             "qty": 5, "risk_pts": 45.8, "tgt_pts": 358.61, "risk_usd": 470.0, "win_usd": 3577.0,
                             "steps": [{"label": "One winner passes", "value": "5 micros", "text": "..."}],
                             "eval": {"session": 6, "limit": 10, "to_target": 3289.2, "room": 1542.6, "status": "open"}},
                  "guards": {"blocking": ["PC clock 5.0 s ahead of internet time (max 5 s)"],
                             "vix": {"vix": 19.45, "vxn": 28.3, "move": 358.61, "open18": 29268.5, "up": 29627.11, "dn": 28909.89},
                             "clock_drift_s": -5.0}},
        "second": {"t": now - 60, "day": "2026-10-26", "paper": False, "strategies": {
            "ema_lon_vix": {"label": "London EMA trend pullback", "short": "EMA", "on": True, "route": True,
                            "state": {"stage": "off", "window": "03:00-09:30 ET", "text": "No trades on Mondays (rule): back on Tuesday from 03:00 ET"},
                            "trades": [{"day": "2026-10-23", "entry_t": ts(2026, 10, 23, 3, 30), "exit_t": ts(2026, 10, 23, 4, 55), "dir": -1,
                                        "entry": 29078.0, "stop": 29145.25, "target": 28764.0, "exit": 29077.0, "exit_kind": "BE", "r": 0.001, "qty": 3, "usd": 0.28}],
                            "brain": {"first_fail": "window"}},
            "macd_sweep": {"label": "MACD divergence at a liquidity sweep", "short": "MACD", "on": True, "route": True,
                           "state": {"stage": "off", "window": "02:00-05:00, 09:30-11:00 ET", "text": "Outside its hours: entries 02:00-05:00, 09:30-11:00 ET"},
                           "trades": [{"day": "2026-10-22", "entry_t": ts(2026, 10, 22, 2, 5), "exit_t": ts(2026, 10, 22, 2, 13), "dir": 1,
                                       "entry": 29503.75, "stop": 29450.0, "target": 29933.75, "exit": 29449.75, "exit_kind": "STOP", "r": -1.022, "qty": 4, "usd": -439.6}]},
            "sr_nyreclaim": {"label": "NY sweep-and-reclaim", "short": "S/R", "on": True, "route": True,
                             "state": {"stage": "off", "window": "09:30-12:00 ET", "text": "Outside its hours: entries 09:30-12:00 ET"}, "trades": []},
            "sh_asia": {"label": "Asia resweep hunt", "short": "Asia hunt", "candidate": True, "route": False, "state": {"stage": "waiting"}, "trades": []}},
            "route": {"keys": [], "account_b": {
                "label": "ATLAS MFFUEVTEST25K", "account": "MFFUEVTEST25K", "plan": "builder25k", "plan_label": "MFFU Builder 25K", "kind": "LIVE",
                "keys": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "enabled": True, "disabled": None,
                "eval": {"start_balance": 25000.0, "balance": 25000.0, "profit": 0.0, "today": 0.0, "floor": 24000.0, "room": 1000.0,
                         "target": 26500.0, "to_target": 1500.0, "session": 1, "status": "open", "start": "2026-10-26", "dll": 600.0, "max_micros": 20},
                "open": None, "routed": [], "day_pnl": 0, "entries_today": 0, "locked": None, "size": None}}},
        "live_pub": {"at": now - 21, "ok": True, "fails": 0, "error": None},
        "crit": [{"id": "clock:2026-10-26", "kind": "clock", "title": "Clock drift: entries blocked",
                  "body": "PC clock 5.0 s ahead of internet time (max 5 s). Windows: Settings > Time > Sync now."}],
    }


LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))


def board_of(hb, now=NOW, **kw):
    return LB.from_heartbeat(hb, now=now, lm=LM, where=kw.pop("where", "pc"), n_trades=kw.pop("n_trades", 40), **kw)


# ------------------------------------------------------------------------------------------------ a. windows
def windows_checks():
    w = LB.next_windows(NOW, [LB.LIT_WINDOW])
    check("a. Sunday 22:25 ET: next LIT window Mon 02:00-15:30 ET", w and w[0]["open_t"] == ts(2026, 10, 26, 2, 0)
          and w[0]["close_t"] == ts(2026, 10, 26, 15, 30) and w[0]["day"] == "2026-10-26", w[:1])
    s = LB.window_state(NOW, w)
    check("a. window state: not open, text names Mon 02:00", s["open"] is False and "Mon 02:00-15:30" in s["text"], s)
    s2 = LB.window_state(ts(2026, 10, 26, 9, 0), LB.next_windows(ts(2026, 10, 26, 9, 0), [LB.LIT_WINDOW]))
    check("a. Mon 09:00: open, closes 15:30", s2["open"] is True and s2["close_t"] == ts(2026, 10, 26, 15, 30), s2)
    f = LB.next_windows(ts(2026, 10, 30, 16, 0), [LB.LIT_WINDOW])
    check("a. Friday 16:00: next is Monday 02:00 (weekend skipped)", f[0]["open_t"] == ts(2026, 11, 2, 2, 0), f[:1])
    ec = LB.next_windows(ts(2026, 11, 27, 1, 0), [LB.LIT_WINDOW])
    check("a. day after Thanksgiving: entries end 15 min before the 13:15 halt (13:00)", ec[0]["close_t"] == ts(2026, 11, 27, 13, 0)
          and ec[0].get("early_close") == "13:15", ec[:1])
    xm = LB.next_windows(ts(2026, 12, 24, 16, 0), [LB.LIT_WINDOW])
    check("a. Christmas Day closed: Dec 24 16:00 -> Mon Dec 28", xm[0]["day"] == "2026-12-28", xm[:1])
    em = LB.next_windows(NOW, LB.ATLAS_WINDOWS["ema_lon_vix"], no_monday=True)
    check("a. ATLAS EMA skips Monday: next Tue 03:00", em[0]["open_t"] == ts(2026, 10, 27, 3, 0), em[:1])
    mc = LB.next_windows(ts(2026, 10, 26, 6, 0), LB.ATLAS_WINDOWS["macd_sweep"])
    check("a. ATLAS MACD at 06:00: next is 09:30-11:00 the same day", mc[0]["open_t"] == ts(2026, 10, 26, 9, 30)
          and mc[0]["close_t"] == ts(2026, 10, 26, 11, 0), mc[:1])


# ------------------------------------------------------------------------------------------------ b-g. the board parts
def board_checks():
    hb = hb_fixture()
    B = board_of(hb)
    L, A = B["lit"], B["atlas"]
    check("b. Zlarior: balance / floor / room / $ to go from the anchored eval", L["balance"] == 49710.8 and L["floor"] == 48168.2
          and L["room"] == 1542.6 and abs(L["to_target"] - 3289.2) < 0.01 and L["target_balance"] == 53000.0, L)
    check("b. Zlarior: today $0, session 6 of 10, 0 of 1 trades, room 77% of $2,000", L["today_pnl"] == 0.0 and L["session"] == 6
          and L["sessions"] == 10 and L["trades_today"] == 0 and L["max_day"] == 1 and abs(L["room_frac"] - 0.7713) < 1e-3, L)
    check("b. Zlarior: waiting text without the BLOCKED tail (the block is listed apart)", "Waiting for price to sweep" in L["waiting"]
          and "BLOCKED" not in L["waiting"], L["waiting"])
    check("b. Zlarior: stage Sweep step 2 of 10 + the stage list", L["stage"]["key"] == "sweep" and L["stage"]["n"] == 2 and L["stage"]["of"] == 10
          and L["stages"][1] == ["sweep", "now"], L["stage"])
    check("b. Zlarior: size now 5 micros at the typical 46-pt stop, risk $470, target pays $3,577",
          L["micros"]["qty"] == 5 and L["micros"]["risk_usd"] == 470 and L["micros"]["win_usd"] == 3577 and L["micros"]["typical"] is True, L["micros"])
    check("b. Zlarior: Monday rule note (shorts only)", "shorts only" in (L.get("rule_note") or ""), L.get("rule_note"))
    check("b. Zlarior: next window Mon 02:00 as absolute times", L["window"]["open_t"] == ts(2026, 10, 26, 2, 0) and L["window"]["open"] is False, L["window"])
    check("b. ATLAS: 25K balance / room / $ to go / session 1 / max 20 micros", A["balance"] == 25000.0 and A["room"] == 1000.0
          and A["to_target"] == 1500.0 and A["session"] == 1 and A["max_micros"] == 20 and A["max_day"] == 2, A)
    check("b. ATLAS: three routed members (candidates left out)", [m["key"] for m in A["members"]] == ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], A["members"])
    check("b. ATLAS: all outside hours -> next MACD Mon 02:00", "Next: MACD at Mon 02:00 ET" in A["waiting"] and A["window"]["who"] == "MACD"
          and A["window"]["open_t"] == ts(2026, 10, 26, 2, 0), (A["waiting"], A["window"]))
    check("b. ATLAS: no sizing exposed -> the rule in words (no number made up)", A["micros"]["qty"] is None and "$600 daily loss" in A["micros"]["what"], A["micros"])
    # c. blocks
    bl = B["blocks"]
    check("c. clock drift blocks both accounts once (brain guard + crit de-duplicated), fix = Sync now",
          len(bl) == 1 and bl[0]["kind"] == "clock" and "Sync now" in bl[0]["fix"] and bl[0]["scope"] == "both", bl)
    check("c. lines: the block first, then the slow poll warning; board level bad", B["lines"][0]["kind"] == "clock"
          and any(x["kind"] == "poll" and x["level"] == "warn" for x in B["lines"]) and B["level"] == "bad", B["lines"])
    hb2 = hb_fixture()
    hb2["brain"]["guards"]["blocking"] = []
    hb2["crit"] = []
    hb2["health"]["feed"].update(stale=True, entries_blocked=True, block="FEED STALE: newest 1m bar 12 min old")
    hb2["health"]["kill"] = True
    hb2["second"]["route"]["account_b"].update(disabled="not on the allowlist", locked="2 entries today already")
    B2 = board_of(hb2)
    kinds = [b["kind"] for b in B2["blocks"]]
    check("c. feed stale + kill -> two global blocks with their fixes", kinds == ["kill", "feed"] and "Reload NinjaScript" in B2["blocks"][1]["fix"], B2["blocks"])
    check("c. account B off / locked -> ATLAS's own blocks", len(B2["atlas"]["blocks"]) == 2 and B2["atlas"]["blocks"][0]["scope"] == "atlas", B2["atlas"]["blocks"])
    hb3 = hb_fixture()
    hb3["running"] = False
    hb3["health"]["running"] = False
    check("c. bot stopped -> 'stopped' block with the start fix", board_of(hb3)["blocks"][0]["kind"] == "stopped"
          and "Bot Control" in board_of(hb3)["blocks"][0]["fix"])
    # d. map
    M = B["map"]
    prices = [r["price"] for r in M["levels"]]
    check("d. map: levels + VIX objective + 18:00 open, sorted high to low", prices == sorted(prices, reverse=True)
          and any(r["kind"] == "target" and r["price"] == 29627.11 for r in M["levels"]) and any(r["kind"] == "open" for r in M["levels"]), prices)
    pdl = next(r for r in M["levels"] if r["label"] == "PDL")
    check("d. map: PDL -121.5 pts = $243 a micro, $1,215 at 5 micros", pdl["dist"] == -121.5 and pdl["usd_micro"] == 243 and pdl["usd_size"] == 1215, pdl)
    check("d. map: nearest untaken level above / below (PDH taken is skipped)", M["nearest_above"]["label"] == "equal highs"
          and M["nearest_below"]["label"] == "PDL" and M["sweep_pts"] == 21.5, (M["nearest_above"], M["nearest_below"]))
    # e. health
    H = {x["key"]: x for x in B["health"]["items"]}
    check("e. health: poll 29.4 s -> amber (warn, not red), poll_warn", H["poll_ms"]["warn"] is True and H["poll_ms"]["ok"] is None
          and B["health"]["poll_warn"] is True and H["poll_ms"]["value"] == "29.4 s", H["poll_ms"])
    check("e. health: clock red while the guard blocks (5.0 s at a 5 s max)", H["clock"]["ok"] is False and "Sync now" in H["clock"]["fix"], H["clock"])
    check("e. health: an error 21 min old is grey (not red), with its text", H["error"]["ok"] is None and "TypeError" in H["error"]["detail"], H["error"])
    check("e. health: feed 1m / 5m green with the bar close as t", H["age_1m_s"]["ok"] is True and H["age_1m_s"]["t"] == NOW - 110 + 60
          and H["age_5m_s"]["t"] == NOW - 350 + 300, (H["age_1m_s"], H["age_5m_s"]))
    check("e. health: NinjaTrader, heartbeat and phone feed present", H["nt"]["ok"] is True and "heartbeat" in H and H["live_pub"]["ok"] is True, list(H))
    hb4 = hb_fixture()
    hb4["health"]["poll"].update(poll_ms=800, last_error_t=NOW - 60, consecutive_errors=2)
    H4 = {x["key"]: x for x in board_of(hb4)["health"]["items"]}
    check("e. health: poll 0.8 s green; an error 1 min ago with errors in a row is red", H4["poll_ms"]["ok"] is True and H4["error"]["ok"] is False
          and H4["loop"]["ok"] is False, (H4["poll_ms"], H4["error"], H4["loop"]))
    # f. progress
    P = B["progress"]
    check("f. week: Zlarior 2-4, ATLAS 3-4, Mon-Fri strip", P["lit"]["week"]["lo"] == 2 and P["lit"]["week"]["hi"] == 4 and P["atlas"]["week"]["lo"] == 3
          and len(P["lit"]["week"]["days"]) == 5, P["lit"]["week"])
    check("f. eval: session 6 of 10 (5 left) / ATLAS 1 of 10", P["lit"]["session"] == 6 and P["lit"]["sessions_left"] == 5 and P["atlas"]["session"] == 1, P["lit"])
    lo = (P["lit"]["odds"] or {}).get("rows") or {}
    check("f. odds: Zlarior H2 + H1 2-week pass / fail from uprisk_eval at the live switches", "H2" in lo and "H1" in lo and lo["H2"]["p10"] > 0, lo)
    ao = (P["atlas"]["odds"] or {}).get("rows") or {}
    check("f. odds: ATLAS 25K H2 + H1 from research/second/atlas.json", "H2" in ao and ao["H2"]["p10"] is not None, ao)
    check("f. $ a month: expected (H2 backtest) and the actual pace", (P["lit"]["expected"] or {}).get("per_month") and P["lit"]["actual"]["sessions"] == 6
          and P["lit"]["actual"]["per_month_pace"] == round(-289.2 / 6 * 21) and (P["atlas"]["expected"] or {}).get("per_month"), (P["lit"]["expected"], P["lit"]["actual"]))
    # g. trade log
    T = B["trades"]
    check("g. trades: newest first", [t.get("entry_t") for t in T] == sorted([t.get("entry_t") for t in T], reverse=True), [t.get("entry_t") for t in T])
    lt = [t for t in T if t["acct"] == "lit"]
    check("g. trades: Zlarior's PC trade (live) with R and $", lt and lt[0]["src"] == "live" and lt[0]["usd"] == -495.4 and lt[0]["exit"] == "STOP", lt)
    at = [t for t in T if t["acct"] == "atlas"]
    check("g. trades: ATLAS members' paper trades with member and prices", len(at) == 2 and all(t["src"] == "paper" for t in at)
          and {t["member"] for t in at} == {"EMA", "MACD"} and at[0]["exit_px"] == 29077.0, at)
    hb5 = hb_fixture()
    e_t = ts(2026, 10, 22, 2, 5)
    hb5["second"]["route"]["account_b"]["routed"] = [
        {"t": e_t + 3, "side": "buy", "qty": 4, "entry_t": e_t, "src": "macd_sweep", "strategy": "MACD", "stop": 29450.0, "target": 29933.75},
        {"t": e_t + 480, "side": "exit", "qty": 4, "reason": "STOP", "pnl": -441.2, "entry_t": e_t}]
    at5 = [t for t in board_of(hb5)["trades"] if t["acct"] == "atlas"]
    live5 = [t for t in at5 if t["src"] == "live"]
    check("g. trades: an account-B entry + exit -> one live ATLAS trade, entry price filled from the MACD paper trade, no duplicate paper row",
          len(live5) == 1 and live5[0]["entry"] == 29503.75 and live5[0]["usd"] == -441.2 and live5[0]["member"] == "MACD"
          and not any(t["src"] == "paper" and t["entry_t"] == e_t for t in at5), at5)


# ------------------------------------------------------------------------------------------------ h. robustness
def robust_checks():
    ok = True
    for bad in (None, {}, {"pc": None}, {"pc": {"brain": "x", "second": [], "health": 3}}, {"pc": {"brain": {"levels": [None, 5, {"price": "x"}]}}},
                {"pc": hb_fixture(), "accounts": "nope", "goals": [], "odds_lit": 7, "atlas_info": "x"}):
        try:
            b = LB.build(bad, NOW)
            json.dumps(b)
            ok = ok and isinstance(b, dict) and all(k in b for k in ("lit", "atlas", "map", "health", "progress", "trades", "lines"))
        except Exception as e:
            ok = False
            print("   raised on", str(bad)[:80], e)
    check("h. build() never raises on garbage, every part present, JSON safe", ok)
    data = {"live": {"pc": {**hb_fixture(), "present": True, "age_s": 30}, "ledger": []},
            "accounts": [], "goals": None, "second": {"strategies": [{"key": "macd_sweep", "trades": hb_fixture()["second"]["strategies"]["macd_sweep"]["trades"]}],
                                                       "atlas": {"numbers": {"H2": {"per_month": 1194}}, "eval25k": {"H2": {"p10": 43.5, "f10": 0.0}}}},
            "extras": {"two_week": {"eval": {"H2": {"p10": 58.6, "f10": 20.9, "pass_med": 5}}, "eval_cfg": {"room_f": 0.8}}}}
    sb = LB.site_block(data, now=NOW + 30)
    check("h. site_block: cloud board with the PC brain (fresh), odds from extras, ATLAS numbers from second.atlas",
          sb["where"] == "cloud" and sb["brain_src"] == "PC bot" and sb["progress"]["lit"]["odds"]["rows"]["H2"]["p10"] == 58.6
          and sb["progress"]["atlas"]["expected"]["per_month"] == 1194 and sb["map"]["price"] == 29107.75, {k: sb.get(k) for k in ("where", "brain_src")})
    data["live"]["pc"]["t"] = NOW - 3 * 3600
    data["live"]["brain"] = {**hb_fixture()["brain"], "price": 29200.0}
    sb2 = LB.site_block(data, now=NOW)
    check("h. site_block: a 3-hour-old PC heartbeat -> the map uses the cloud paper twin's brain", sb2["brain_src"] == "cloud paper twin"
          and sb2["map"]["price"] == 29200.0, sb2.get("brain_src"))


# ------------------------------------------------------------------------------------------------ i. PC API
def api_checks(tmp):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import board_api as BA
    from tests.test_pcdash_api import fake_bot
    b, now = fake_bot(tmp)
    snap = lambda: json.dumps({"ledger": b.ledger, "state": b.state, "running": b.running, "kill": b.kill, "cfg": b.cfg}, default=str, sort_keys=True)  # noqa: E731
    before, files0 = snap(), sorted(os.listdir(tmp))
    old = BA._bot
    BA._bot = lambda: b
    BA._cache.update(t=0.0, v=None)
    try:
        app = FastAPI()
        app.include_router(BA.router)
        cl = TestClient(app)
        r = cl.get("/api/next/board")
        check("i. GET /api/next/board: 200 JSON", r.status_code == 200 and r.headers["content-type"].startswith("application/json"), r.text[:200])
        d = r.json()
        L = d.get("lit") or {}
        check("i. PC board: Zlarior balance 51,327.20, room 1,977.20, today -$22.80, open SHORT 8", L.get("balance") == 51327.2 and L.get("room") == 1977.2
              and L.get("today_pnl") == -22.8 and (L.get("position") or {}).get("side") == "SHORT" and L["position"].get("qty") == 8, L)
        check("i. PC board: today's closed trade + the open one counted (2), the PC trade in the log", L.get("trades_today") == 2
              and any(t["acct"] == "lit" and t["src"] == "live" and t["usd"] == -22.8 for t in d.get("trades") or []), (L.get("trades_today"), d.get("trades")))
        check("i. PC board: where pc, health items include poll time 0.5 s green", d.get("where") == "pc"
              and any(x["key"] == "poll_ms" and x["ok"] is True for x in (d.get("health") or {}).get("items") or []), d.get("health"))
        check("i. PC board: odds rows from the repo", bool(((d.get("progress") or {}).get("lit") or {}).get("odds")), (d.get("progress") or {}).get("lit"))
        r2 = cl.get("/api/next/board")
        check("i. cached: a second GET within 4 s is the same JSON", r2.json() == d)
        check("i. read-only: bot unchanged, no file written", snap() == before and sorted(os.listdir(tmp)) == files0, sorted(os.listdir(tmp)))
        BA._cache.update(t=0.0, v=None)
        BA._bot = lambda: (_ for _ in ()).throw(RuntimeError("no bot"))
        r3 = cl.get("/api/next/board")
        check("i. a broken bot -> 500 JSON with the error (the page never crashes)", r3.status_code == 500 and "no bot" in r3.json().get("error", ""), r3.text[:200])
        from engine import next_api
        mounted = any(getattr(rt, "original_router", None) is BA.router or getattr(rt, "path", "") == "/api/next/board" for rt in next_api.router.routes)
        check("i. mounted by next_api; the board router has one route, GET only", mounted
              and [(rt.path, rt.methods) for rt in BA.router.routes] == [("/api/next/board", {"GET"})], [(rt.path, rt.methods) for rt in BA.router.routes])
    finally:
        BA._bot = old
        BA._cache.update(t=0.0, v=None)


# ------------------------------------------------------------------------------------------------ j. live.json
def live_checks():
    from engine import live_publish as LP
    hb = hb_fixture()
    out = LP.build(hb, now=NOW + 10, lm=LM, hb_last={"at": NOW - 40, "ok": True})
    size = len(json.dumps(out, separators=(",", ":"), default=str))
    bd = out.get("board") or {}
    hl = next((x for x in (bd.get("health") or {}).get("items") or [] if x["key"] == "heartbeat"), {})
    check("j. live.json carries the board (where live) under 64 KB", bd.get("where") == "live" and bd.get("lit") and size < LP.MAX_BYTES, (size, bd.get("error")))
    check("j. live.json board: heartbeat item = the last real heartbeat push (40 s before)", hl.get("t") == NOW - 40 and hl.get("ok") is True, hl)
    check("j. live.json board: the account names never leak beyond what live.json already shows", "MFFUEVTEST50K" in json.dumps(out)
          and "push_pk" not in json.dumps(bd))
    big = copy.deepcopy(out)
    big["board"]["trades"] = [dict(big["board"]["trades"][0], entry_t=i) for i in range(400)] if big["board"].get("trades") else [{"x": "y" * 200, "entry_t": i} for i in range(400)]
    big["pc"]["pad"] = None
    f = LP.fit(big, max_bytes=60_000)
    check("j. fit(): the board's trade list is trimmed first (4 left), the board itself stays", len((f.get("board") or {}).get("trades") or []) == 4, len((f.get("board") or {}).get("trades") or []))


# ------------------------------------------------------------------------------------------------ k. static wiring + node
def static_checks():
    rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()  # noqa: E731
    a = open(os.path.join(ROOT, "tools", "web_public", "boardcore.js"), "rb").read()
    b = open(os.path.join(ROOT, "web_next", "js", "next", "boardcore.js"), "rb").read()
    check("k. boardcore.js: phone and PC copies byte-identical", a == b)
    core = a.decode("utf-8")
    check("k. boardcore.js: no network call, no POST (read-only renderer)", "fetch(" not in core and "XMLHttpRequest" not in core and "POST" not in core)
    idx = rd("tools/web_public/index.html")
    check("k. phone: board.js loads after clean.js (it wraps clean's Home)", 'src="board.js?v=' in idx and idx.index("clean.js?v=") < idx.index("board.js?v="))
    import re
    sw = rd("tools/web_public/sw.js")
    check("k. phone service worker bumped (le-public-v37 or later)", int(re.search(r"le-public-v(\d+)", sw).group(1)) >= 37)
    pb = rd("tools/web_public/board.js")
    check("k. phone board.js: page #/board + Home cut, keeps clean.js flags, reads live.json's board", "VIEWS.board" in pb and "Object.assign(w, h0)" in pb
          and "LIVE.j.board" in pb and "fetch(" not in pb)
    pcb = rd("web_next/js/next/board.js")
    check("k. PC board.js: only GET /api/next/board (+ the charts helper)", "fetch('/api/next/board')" in pcb and "method" not in pcb and "POST" not in pcb)
    app, html, routes, cc = rd("web_next/js/app.js"), rd("web_next/index.html"), rd("web_next/js/next/routes.js"), rd("web_next/js/next/cc.js")
    check("k. PC: page registered, section in index.html, title in routes", "board: boardPage" in app and 'id="page-board"' in html and "{ id: 'board', label: 'Live board'" in routes)
    check("k. PC sidebar: Main untouched (6 items), the board under Advanced > Accounts", "{ label: 'Accounts', ids: ['board', 'goals', 'sesscal'] }" in routes
          and "{ label: 'Main', ids: ['cc', 'start', 'zlarior', 'atlas', 'real', 'modules'] }" in routes)   # 2026-10-28: Real results
    check("k. PC Command center: 'Right now' slot + fillBoardHome after each render", 'id="ccBoard"' in cc and "fillBoardHome().catch" in cc and "import { fillBoardHome }" in cc)
    check("k. data.json / home.json carry the board (build_web_dashboard)", 'data["board"] = _lb.site_block(data, st)' in rd("tools/build_web_dashboard.py")
          and '"board": {**data["board"]' in rd("tools/build_web_dashboard.py"))
    node = shutil.which("node")
    if not node:
        check("k. node available for the JS checks (skipped: no node)", True)
        return
    errs = []
    for p in ("tools/web_public/boardcore.js", "tools/web_public/board.js"):
        r = subprocess.run([node, "--check", os.path.join(ROOT, p)], capture_output=True, text=True)
        if r.returncode:
            errs.append(p + ": " + r.stderr[-300:])
    for p in ("web_next/js/next/board.js", "web_next/js/next/cc.js", "web_next/js/next/routes.js"):
        r = subprocess.run([node, "--input-type=module", "--check"], input=open(os.path.join(ROOT, p), encoding="utf-8").read(), capture_output=True, text=True)
        if r.returncode:
            errs.append(p + ": " + r.stderr[-300:])
    check("k. node --check: boardcore.js, phone board.js, PC board.js / cc.js / routes.js parse", not errs, errs)
    B = board_of(hb_fixture(), now=NOW)
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "b.json")
        json.dump(B, open(bp, "w"))
        js = r"""
global.window = global; global.setInterval = () => 0;
global.document = { getElementById: () => ({}), querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}) };
require(process.argv[1]);
const B = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const h = window.BoardUI.page(B, {});
const m = window.BoardUI.home(B, {});
const c = window.BoardUI.csv(B.trades);
const out = { len: h.length, right: h.includes('Right now'), map: h.includes('bd-ladder'), now: h.includes('Price now'), fix: h.includes('Sync now'),
  poll: h.includes('Poll time'), odds: h.includes('pass in 2 weeks'), tl: h.includes('Export CSV'), cd: h.includes('data-bd-open="'),
  home: m.includes('bd-homecut') && m.includes('Open the live board'), csvh: c.split('\n')[0], csvn: c.split('\n').length,
  wt: window.BoardUI.windowText(Date.now() / 1000 + 3700, Date.now() / 1000 + 9000).t, err: window.BoardUI.page({ error: 'x' }, {}).includes('x') };
console.log(JSON.stringify(out));
"""
        r = subprocess.run([node, "-e", js, os.path.join(ROOT, "tools", "web_public", "boardcore.js"), bp], capture_output=True, text=True)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            o = {"stderr": r.stderr[-400:]}
        check("k. node render: the page has Right now, the ladder with Price now, the fix, the poll item, odds, the CSV button, countdowns",
              all(o.get(k) for k in ("right", "map", "now", "fix", "poll", "odds", "tl", "cd")), o)
        check("k. node render: the Home cut, CSV header + one row per trade, countdown text, error box",
              o.get("home") and o.get("csvh", "").startswith("day,entry_et,exit_et,account,source,member,side,qty") and o.get("csvn") == len(B["trades"]) + 1
              and o.get("wt") == "opens in 1 h 2 min" and o.get("err"), o)


def main() -> int:
    windows_checks()
    board_checks()
    robust_checks()
    with tempfile.TemporaryDirectory() as tmp:
        api_checks(tmp)
    live_checks()
    static_checks()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for f in FAIL:
        print("FAILED:", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
