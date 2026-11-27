"""Trade cards, the 16:20 day summary and the Friday week report (day-cards 2026-11-26). Temp folders, a fake Telegram (alert_bus
_HTTP), fake bars; never the owner's phone.

    python -X utf8 -m tests.test_trade_cards
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import struct
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


ET0 = ts(2026, 11, 25, 9, 52)


def fake_bars(t_from, t_to):
    out, px = [], 25500.0
    for t in range(t_from - t_from % 60, t_to, 60):
        o = px
        px += (1 if (t // 60) % 3 else -2) * 1.5
        out.append((t, o, max(o, px) + 1, min(o, px) - 1, px))
    return out


def t_png():
    print("1. the PNG renderer (numpy + zlib only)", flush=True)
    from engine import png_chart as PC
    b = fake_bars(ET0 - 7200, ET0 + 600)
    png = PC.render(b, [(25530, PC.GREEN, ET0, False), (25480, PC.RED, ET0, False), (25500, PC.WHITE, ET0, True)],
                    [(ET0, 25500, PC.GOLD)])
    ok = png and png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (1280, 720)
    check("a valid 1280 x 720 PNG (Telegram's own photo size: retina on a phone)", ok, png[:30] if png else None)
    check("small (< 300 KB)", png and len(png) < 300_000, len(png or b""))
    check("fewer than 2 bars -> None (text-only card)", PC.render(b[:1]) is None)
    import importlib.util
    check("no new package: matplotlib is not needed on the PC", importlib.util.find_spec("engine.png_chart") is not None
          and "matplotlib" not in open(os.path.join(ROOT, "engine", "png_chart.py")).read().split('"""', 2)[-1])


def t_card(tmp):
    print("2. the card: chart + the bot's reason + $ risk / R", flush=True)
    from engine import trade_card as TC
    TC.CARD_DIR = os.path.join(tmp, "cards")
    bot = SimpleNamespace(brain={"setups": [{"dir": 1, "status": "filled", "swept": ["London low"],
                                             "status_text": "Filled 09:52 at 25,500 - still open"}]}, second={}, cfg={})
    fill = {"kind": "fill", "key": f"fill:{ET0}", "side": "LONG", "qty": 2, "entry": 25500.0, "stop": 25480.0, "target": 25560.0,
            "t": ET0}
    c = TC.build(fill, "entry", now=ET0 + 5, bot=bot, bars_fn=fake_bars)
    check("entry card: a PNG file, the Brain's reason, $ risk and the target in R", c and c["photo"] and os.path.exists(c["photo"])
          and "swept London low" in c["why"] and "Risk $80" in c["extra"] and "3.0R" in c["extra"], c)
    out = {"kind": "outcome", "key": f"out:{ET0}", "side": "LONG", "qty": 2, "exit_px": 25560.0, "usd": 240.0, "exit": "TARGET",
           "t": ET0 + 1800}
    c2 = TC.build(out, "exit", now=ET0 + 1810, bot=SimpleNamespace(brain={}, second={}, cfg={}), bars_fn=fake_bars)
    check("exit card: stop / target from the entry's card, 'Result +3.00R', the reason kept", c2 and "Result +3.00R" in c2["extra"]
          and "London low" in c2["why"] and "white ring = exit" in c2["legend"], c2)
    TC_bars = TC.bars
    TC.bars = lambda *a, **k: []
    try:
        ev = TC.attach({"kind": "entry", "key": fill["key"]}, fill, "entry", now=ET0, bot=bot)
    finally:
        TC.bars = TC_bars
    check("no bars -> no picture, the reason line still added (text message)", "photo" not in ev and "London low" in ev.get("more", ""), ev)
    import pandas as pd
    import engine.ninjatrader as NTm
    keep = NTm.NinjaTraderBars

    class FakeNTB:
        def __init__(self, *a, **k):
            pass

        def recent_bars(self, sym, interval="5m", period="5d", now=None):
            b = fake_bars(ET0 - 7200, ET0 + 600)
            return pd.DataFrame(b, columns=["time", "open", "high", "low", "close"]), None, True
    NTm.NinjaTraderBars = FakeNTB
    try:
        got = TC.bars(ET0 - 3600, ET0, bot=SimpleNamespace(cfg={}))   # no _read_hist on this bot: the NinjaTrader feed answers
    finally:
        NTm.NinjaTraderBars = keep
    check("bars from NinjaTrader's feed (recent_bars returns (df, error, flag)) when the bot's history has none",
          len(got) >= 50 and got[0][0] >= ET0 - 3600, len(got))
    os.environ["LE_TRADE_CARDS"] = "0"
    try:
        ev0 = {"kind": "entry", "key": "x"}
        check("LE_TRADE_CARDS=0 -> the event is unchanged", TC.attach(ev0, fill, "entry", bot=bot) is ev0)
    finally:
        os.environ.pop("LE_TRADE_CARDS", None)
    return c


def t_bus(card):
    print("3. alert bus: Telegram sendPhoto, text fallbacks", flush=True)
    from engine import alert_bus as AB
    calls = []

    def http(method, url, body, headers, timeout):
        calls.append((url.rsplit("/", 1)[-1], headers.get("Content-Type", ""), body))
        if url.endswith("sendPhoto") and http.fail:
            return 500, '{"ok": false, "description": "bad photo"}'
        return 200, '{"ok": true, "result": {"message_id": 7}}'
    http.fail = False
    old = AB._HTTP
    AB._HTTP = http
    try:
        cfg = {"telegram": {"token": "T", "chat_id": "1"}, "ntfy": False, "webpush": False}
        ev = {"kind": "entry", "key": "k1", "account": "Zlarior 50K", "side": "LONG", "qty": 2, "price": 25500, "stop": 25480,
              "target": 25560, "risk": 80, "gain": 240, "t": ET0, "photo": card["photo"], "legend": card["legend"],
              "more": card["why"] + "\n" + card["extra"]}
        r = AB.deliver(ev, cfg=cfg, path=os.devnull, log_path=os.devnull)
        ph = [c for c in calls if c[0] == "sendPhoto"]
        check("Telegram gets sendPhoto (multipart, the PNG inside) and nothing else", r.get("ok") and len(ph) == 1 and len(calls) == 1
              and ph[0][1].startswith("multipart/form-data") and b"\x89PNG" in ph[0][2], (r, [c[:2] for c in calls]))
        cap = ph[0][2].split(b'name="caption"')[1][:900].decode("utf-8", "replace") if ph else ""
        check("the caption: account, side, size, entry / stop / target, $ risk, the reason, R, the colour legend",
              all(w in cap for w in ("Zlarior 50K", "LONG", "2 MNQ", "25,480", "risk $80", "London low", "3.0R", "green = target")), cap)
        calls.clear()
        http.fail = True
        r2 = AB.deliver({**ev, "key": "k2"}, cfg=cfg, path=os.devnull, log_path=os.devnull)
        check("sendPhoto refused -> the plain text message goes instead", r2.get("ok") and [c[0] for c in calls] == ["sendPhoto", "sendMessage"],
              [c[0] for c in calls])
        t, b = AB.text(ev)
        check("every other channel: text only, with the reason line", "London low" in b and "photo" not in b)
    finally:
        AB._HTTP = old


def t_hook():
    print("4. push._bus_send attaches the card to real entries / exits", flush=True)
    from engine import push, alert_bus as AB, notify, trade_card as TC
    got = []
    saved = (AB.active, AB.send, notify.real_trade, TC.attach)
    AB.active = lambda *a, **k: True
    AB.send = lambda ev, on_done=None, **k: got.append(ev) or "queued"
    notify.real_trade = lambda p: True
    TC.attach = lambda ev, p, what, **k: {**ev, "photo": "/x.png", "more": "why"}
    try:
        push._bus_send({"kind": "fill", "key": f"fill:{ET0}", "side": "LONG", "qty": 1, "entry": 1, "stop": 0, "target": 3, "account": "Zlarior 50K"})
        check("the bus event carries the picture", got and got[0].get("photo") == "/x.png" and got[0]["kind"] == "entry", got)
        TC.attach = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        got.clear()
        push._bus_send({"kind": "outcome", "key": f"out:{ET0}", "side": "LONG", "usd": 5, "exit": "TARGET", "account": "Zlarior 50K"})
        check("a broken card never stops the alert (plain event sent)", got and "photo" not in got[0], got)
    finally:
        AB.active, AB.send, notify.real_trade, TC.attach = saved


def _snap(now):
    return {"t": now, "hb_age": 60, "mode": "LIVE",
            "live": {"board": {"lit": {"plan": "MFFU Builder 50K", "today_pnl": 120.0, "week_pnl": -80.0, "trades_today": 1,
                                       "to_target": 3200, "room": 1500, "mll": 2000},
                               "atlas": {"name": "ATLAS", "plan": "25K", "today_pnl": 0, "week_pnl": 514.18, "trades_today": 0,
                                         "configured": True, "real": True}}},
            "hb": {"acct": {"eval": {"days": {"2026-11-03": 50.0, "2026-11-24": -100.0, "2026-10-30": 999.0}}},
                   "brain": {"setups": [{"hm": "10:05", "side": "LONG", "status": "rejected",
                                         "status_text": "Rejected: Displacement >= 0.8 ATR - biggest body 0.78 ATR"},
                                        {"hm": "06:16", "side": "LONG", "status": "filled", "status_text": "Filled"}]}}}


def t_summary_cards(tmp):
    print("7. the day summary and week report as pictures (night-nq-cards)", flush=True)
    from tools import pc_guard as G
    from engine import trade_card as TC, alert_bus as AB
    TC.CARD_DIR = os.path.join(tmp, "cards")
    n2 = ts(2026, 11, 24, 16, 21)
    m = G.day_summary(_snap(n2), n2, {})
    cd = m[0].get("card") if m else None
    check("the day summary carries a card: total, one row per account, the last trading days",
          cd and cd["type"] == "day" and cd["total"] == 120.0 and [r["name"] for r in cd["rows"]] == ["Zlarior 50K", "ATLAS 25K"]
          and cd["rows"][0]["room"] == 1500 and len(cd["days"]) == 3, cd)
    ev = AB.from_report(m[0])
    check("alert_bus.from_report: the day summary goes as a photo (title / body unchanged)",
          ev.get("photo") and os.path.exists(ev["photo"]) and ev["title"] == m[0]["title"] and ev["body"] == m[0]["body"], ev)
    png = open(ev["photo"], "rb").read() if ev.get("photo") else b""
    check("day card: a PNG under 300 KB", png[:4] == b"\x89PNG" and len(png) < 300_000, len(png))
    rp = os.path.join(tmp, "reviews2.jsonl")
    with open(rp, "w") as fh:
        fh.write(json.dumps({"bot": "lit", "day": "2026-11-23", "status": "matched", "live": {"usd": 240.0}, "twin": {"usd": 250.0}}) + "\n")
    fr = ts(2026, 11, 27, 17, 5)
    w = G.weekly_report(_snap(fr), fr, {}, reviews_path=rp)
    wc = w[0].get("card") if w else None
    check("the week report carries a card: $ per account, live vs backtest per bot, Mon-Fri bars",
          wc and wc["type"] == "week" and len(wc["daily"]) == 5 and wc["daily"][0] == ("MON", 240.0, 250.0)
          and wc["bots"] and wc["bots"][0]["live"] == 1, wc)
    ev2 = AB.from_report(w[0])
    check("...and goes as a photo", ev2.get("photo") and os.path.exists(ev2["photo"]), ev2)
    seen = []
    from engine import png_chart as PC
    keep = PC.render_day
    PC.render_day = lambda spec: seen.append(spec) or keep(spec)
    try:
        TC.summary_photo({"type": "day", "date": "X", "total": 1, "rows": [{"name": "Acct MFFUEVBLDR123456", "today": 1}]}, "k")
    finally:
        PC.render_day = keep
    check("account ids are masked before they are drawn", seen and "MFFUEVBLDR123456" not in json.dumps(seen)
          and "...3456" in json.dumps(seen), seen)
    PC.render_day = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        ev3 = AB.from_report(m[0])
    finally:
        PC.render_day = keep
    check("a broken picture -> no photo, the text message exactly", "photo" not in ev3 and ev3["body"] == m[0]["body"], ev3)
    os.environ["LE_TRADE_CARDS"] = "0"
    try:
        check("trade cards off -> no summary picture either", "photo" not in AB.from_report(m[0]))
    finally:
        os.environ.pop("LE_TRADE_CARDS", None)
    m_nocard = {k: v for k, v in m[0].items() if k != "card"}
    check("a report push without a card: unchanged event", "photo" not in AB.from_report(m_nocard))


def t_day():
    print("5. the day summary: 16:20 ET (half days 13:20), week / month, trades, close setups, 7-day", flush=True)
    from tools import pc_guard as G
    n1 = ts(2026, 11, 24, 16, 16)
    check("16:16 ET -> not yet (16:20 now)", not G.day_summary(_snap(n1), n1, {}))
    n2 = ts(2026, 11, 24, 16, 21)
    m = G.day_summary(_snap(n2), n2, {})
    b = m[0]["body"] if m else ""
    check("16:21 ET -> one summary: today, week, month, trades per account", m and "+$120 today" in b and "-$80 week" in b
          and "-$50 month" in b and "1 trade" in b and "+$514 week" in b, b)
    check("...and the setup that got close, in the Brain's words", "Close but no trade: 10:05 LONG Rejected: Displacement" in b, b)
    h = ts(2026, 11, 27, 13, 36)                              # the day after Thanksgiving: CME halts at 13:15
    try:
        from engine import cme_calendar as C
        ec = C.early_close(dt.date(2026, 11, 27))
    except Exception:
        ec = None
    if ec is not None:
        check(f"half day (halt {ec // 60}:{ec % 60:02d}): the summary 20 min after the halt", bool(G.day_summary(_snap(h), h, {}))
              and not G.day_summary(_snap(ts(2026, 11, 27, 12, 0)), ts(2026, 11, 27, 12, 0), {}))
    check("a sent day is not sent again", not G.day_summary(_snap(n2), n2, {m[0]["key"]: 1}) if m else False)
    from engine import notify
    check("the default time is 16:20 (notify defaults + notify_settings.json)", notify.DEFAULTS["daily_summary_at"] == "16:20"
          and json.load(open(os.path.join(ROOT, "notify_settings.json")))["daily_summary_at"] == "16:20")


def t_week(tmp):
    print("6. the Friday 17:00 ET week report", flush=True)
    from tools import pc_guard as G
    rp = os.path.join(tmp, "reviews.jsonl")
    rows = [{"bot": "lit", "day": "2026-11-23", "status": "matched", "entry_t": ts(2026, 11, 23, 6, 0),
             "live": {"usd": 240.0, "r": 3.0}, "twin": {"usd": 250.0, "r": 3.1}, "diff": {"entry_ticks": 2}, "cause": "slippage"},
            {"bot": "lit", "day": "2026-11-25", "status": "missed", "entry_t": ts(2026, 11, 25, 4, 0), "twin": {"usd": -129.4, "r": -1},
             "gap_usd": 129.4, "cause": "PC off"},
            {"bot": "atlas", "day": "2026-11-24", "status": "matched", "entry_t": ts(2026, 11, 24, 4, 0),
             "live": {"usd": 514.18, "r": 2.0}, "twin": {"usd": 500.0, "r": 2.0}}]
    with open(rp, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    th = ts(2026, 11, 26, 17, 5)
    check("Thursday -> nothing", not G.weekly_report(_snap(th), th, {}, reviews_path=rp))
    fr = ts(2026, 11, 27, 17, 5)
    w = G.weekly_report(_snap(fr), fr, {}, reviews_path=rp)
    b = w[0]["body"] if w else ""
    check("Friday 17:05 ET -> one report: $ per account this week", w and w[0]["key"] == "guard:week:2026-11-23" and "Zlarior 50K -$80" in b
          and "+$514" in b, w)
    check("...the trades live vs backtest per bot (missed counted) and the win rate vs the twin",
          "Zlarior: 1 live vs 2 backtest" in b and "1 missed" in b and "winners 1/1 live vs 1/2 backtest" in b, b)
    check("...and what the learning journal noticed", "Learning noticed:" in b and "PC off" in b and "slippage" in b, b)
    check("sent once", not G.weekly_report(_snap(fr), fr, {w[0]["key"]: 1}, reviews_path=rp) if w else False)
    sa = ts(2026, 11, 28, 11, 0)
    check("missed Friday -> Saturday morning catches up; Saturday afternoon -> nothing",
          bool(G.weekly_report(_snap(sa), sa, {}, reviews_path=rp)) and not G.weekly_report(_snap(sa + 4 * 3600), sa + 4 * 3600, {}, reviews_path=rp))
    from engine import notify
    check("its switch: guard:week:* = weekly_report (ON by default); trade_cards ON too",
          notify.kind_of("guard:week:2026-11-23") == "weekly_report" and notify.on("weekly_report") and notify.on("trade_cards")
          and {"weekly_report", "trade_cards"} <= set(notify.IMPORTANT))


def main():
    tmp = tempfile.mkdtemp(prefix="cards_")
    try:
        card = None
        for f in (t_png, lambda: t_card(tmp), None, t_hook, t_day, lambda: t_week(tmp), lambda: t_summary_cards(tmp)):
            try:
                if f is None:
                    if card:
                        t_bus(card)
                    continue
                r = f()
                if isinstance(r, dict):
                    card = r
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("suite ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\ntrade cards: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
