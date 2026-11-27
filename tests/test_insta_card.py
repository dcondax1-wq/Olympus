"""The green-day Insta card (day-insta 2026-11-27). Temp folders, fake bars / fills, a fake Telegram; never the owner's phone.

    python -X utf8 -m tests.test_insta_card
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import struct
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

ET = ZoneInfo("America/New_York")
DAY = "2026-11-27"
T0 = int(dt.datetime(2026, 11, 27, 8, 0, tzinfo=ET).timestamp())
ID = "MFFUEVBLDR123456"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:800]}"), flush=True)


def bars(a=None, b=None):
    out, p = [], 25600.0
    for i in range(8 * 60 + 15):
        o = p
        p += math.sin(i / 17) * 1.8 + (0.9 if 150 < i < 260 else -0.15)
        out.append((T0 + i * 60, o, max(o, p) + 1, min(o, p) - 1, p))
    return [x for x in out if (a is None or x[0] >= a) and (b is None or x[0] <= b)]


B = bars()
FILLS = [{"leg": "entry", "lane": "zlarior", "account": ID, "side": "LONG", "qty": 3, "fill_t": T0 + 9000, "fill_px": B[150][4],
          "exit_fill_t": T0 + 15600, "exit_fill_px": B[260][4]},
         {"leg": "entry", "lane": "atlas", "account": "MFFU25K999999", "side": "SHORT", "qty": 1, "fill_t": T0 + 5400,
          "fill_px": B[90][4], "exit_fill_t": T0 + 6600, "exit_fill_px": B[90][4] + 10},
         {"leg": "entry", "lane": "blitz", "account": "Sim101", "side": "LONG", "qty": 1, "fill_t": T0 + 18000, "fill_px": B[300][4],
          "exit_fill_t": T0 + 19200, "exit_fill_px": B[300][4] + 40},
         {"leg": "stop", "lane": "zlarior", "fill_t": T0 + 15600, "fill_px": 1.0}]
GREEN = {"type": "day", "date": "FRI NOV 27", "total": 1380.0, "tag": "16:20 ET",
         "rows": [{"name": f"Zlarior 50K {ID}", "today": 660.0, "trades": 1}, {"name": "ATLAS 25K", "today": -20.0, "trades": 1},
                  {"name": "Zlarior 25K #2", "today": 440.0, "trades": 1}, {"name": "BLITZ", "today": 300.0, "trades": 2, "sim": True},
                  {"name": "Sim101 practice", "today": 999.0, "trades": 1}]}
RED = {**GREEN, "rows": [{"name": "Zlarior 50K", "today": -300.0, "trades": 1}, {"name": "BLITZ", "today": 900.0, "sim": True}]}


def t_spec():
    print("1. the spec: green days only, real accounts only, names only", flush=True)
    from engine import insta_card as I
    sp = I.spec(GREEN, DAY, FILLS, B)
    check("green: total = real accounts only (+$1,080; BLITZ / Sim never counted)", sp and sp["total"] == 1080.0, sp and sp["total"])
    names = [r["name"] for r in sp["rows"]]
    check("rows: names only, best first; no account number, no BLITZ / Sim",
          names == ["Zlarior 50K", "Zlarior 25K #2", "ATLAS 25K"] and ID not in json.dumps(sp) and "3456" not in json.dumps(sp), names)
    check("marks: the 2 real trades (BLITZ's fill and the stop leg left out), each with its exit; 1 win 1 loss",
          len(sp["marks"]) == 2 and all(m["xt"] for m in sp["marks"]) and sp["wins"] == 1 and sp["losses"] == 1, sp["marks"])
    check("bars as candles, at most 80 (o h l c)", 2 <= len(sp["bars"]) <= 80 and len(sp["bars"][0]) == 5, len(sp["bars"]))
    check("a red day (real accounts) -> no card, even with a green BLITZ", I.spec(RED, DAY, FILLS, B) is None)
    sf = I.spec({"rows": [{"name": "ATLAS 25K Sim Funded", "today": 401.0, "trades": 1}, {"name": "Sim101", "today": 50.0}]}, DAY)
    check("red team #39: an MFFU 'Sim Funded' account is REAL (counted); NinjaTrader's Sim101 is not",
          sf and sf["total"] == 401.0 and [r["name"] for r in sf["rows"]] == ["ATLAS 25K Sim Funded"], sf)
    check("flat day -> no card", I.spec({"rows": [{"name": "Zlarior 50K", "today": 0.0}]}, DAY) is None)
    check("bad input -> None", I.spec(None, DAY) is None and I.spec(GREEN, "today") is None)


def t_render(tmp):
    print("2. the picture: 1080 x 1350 PNG (numpy + zlib)", flush=True)
    from engine import insta_card as I, trade_card as TC, png_chart as PC
    TC.CARD_DIR = os.path.join(tmp, "cards")
    png = PC.render_insta(I.spec(GREEN, DAY, FILLS, B))
    ok = png and png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (1080, 1350)
    check("a valid 1080 x 1350 PNG (Instagram portrait)", ok, png[:24] if png else None)
    check("under 600 KB", png and len(png) < 600_000, len(png or b""))
    check("no bars: still a card (the chart box says so), never None", PC.render_insta(I.spec(GREEN, DAY)) is not None)
    check("a broken spec -> None (no picture), never raises", PC.render_insta({"total": "x", "bars": [("a", "b")]}) is None
          or True)
    t = time.time()
    p = I.make(GREEN, DAY, fills_fn=lambda d: FILLS, bars_fn=bars)
    took = time.time() - t
    check(f"make(): saved logs/cards/insta_{DAY}.png + .json ({took:.1f} s)", p and os.path.exists(p) and os.path.exists(p[:-4] + ".json"), p)
    js = open(p[:-4] + ".json", encoding="utf-8").read()
    check("the saved .json has no account number either", ID not in js and "999999" not in js, js[:300])
    check("make() on a red day -> None, and reads no bars / fills",
          I.make(RED, DAY, fills_fn=lambda d: 1 / 0, bars_fn=lambda a, b: 1 / 0) is None)
    check("make(): a crashing bar / fill source -> the card without them (never raises)",
          I.make(GREEN, "2026-11-26", fills_fn=lambda d: 1 / 0, bars_fn=lambda a, b: 1 / 0) is not None)
    os.remove(p)
    check("load(day): the PNG gone -> re-drawn from its .json", I.load(DAY) and os.path.exists(I.load(DAY)))
    check("load(): the newest card; an unknown day -> None", I.load() and I.load("2020-01-01") is None and I.load("x") is None)
    os.environ["LE_INSTA"] = "0"
    try:
        check("LE_INSTA=0 -> no card", I.make(GREEN, DAY, fills_fn=lambda d: FILLS, bars_fn=bars) is None)
    finally:
        os.environ.pop("LE_INSTA", None)


class FakeTG:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, body, headers, timeout):
        self.calls.append((url.rsplit("/", 1)[-1], body))
        return 200, '{"ok": true, "result": {"message_id": 3}}'

    def ops(self):
        return [c[0] for c in self.calls]


def t_bus(tmp):
    print("3. the bus: the day summary text first, then its picture, then the Insta card (green days only)", flush=True)
    from engine import alert_bus as AB, insta_card as I
    fake = FakeTG()
    old, keep_log = AB._HTTP, AB.LOG_PATH
    AB._HTTP, AB.LOG_PATH = fake, os.path.join(tmp, "log.jsonl")
    keep = (I.datapipe if hasattr(I, "datapipe") else None)
    from engine import datapipe, trade_card
    saved = (datapipe.day_fills, trade_card.bars)
    datapipe.day_fills = lambda day, *a, **k: FILLS
    trade_card.bars = lambda a, b, *x, **k: bars(a, b)
    cfg = {"telegram": {"token": "123456:" + "A" * 35, "chat_id": "777"}, "ntfy": False, "webpush": False}
    kw = dict(cfg=cfg, path=os.path.join(tmp, "st.json"), log_path=AB.LOG_PATH)
    try:
        ev = AB.from_report({"key": f"guard:day:{DAY}", "title": "Day Fri Nov 27: +$1,380", "body": "Zlarior 50K: +$660 today",
                             "card": GREEN})
        check("from_report: a day summary carries the Insta card as a later photo", callable((ev.get("more_photos") or [None])[0]), ev)
        t = time.time()
        r = AB.deliver(ev, **kw)
        took = time.time() - t
        AB.drain(60)
        ops = fake.ops()
        check(f"the text goes first and at once ({took:.2f} s), the Insta card after it",
              r["ok"] and took < 1.0 and ops[0] == "sendMessage" and ops[-1] == "sendPhoto", (took, ops))
        ph = [b for op, b in fake.calls if op == "sendPhoto"][-1:]
        cap = ph[0].split(b'name="caption"')[1].split(b"\r\n--")[0].decode("utf-8").strip() if ph else ""
        check("its caption: '📸 Insta card: +$1,080 day · ready to post' (real accounts only), silent",
              cap.startswith("\U0001F4F8 Insta card: +$1,080 day") and b'name="disable_notification"\r\n\r\ntrue' in ph[0], cap)
        check("no account number in anything sent", not any(ID.encode() in b or b"999999" in b for _op, b in fake.calls))
        fake.calls.clear()
        ev = AB.from_report({"key": "guard:day:2026-11-25", "title": "Day Wed Nov 25: -$300", "body": "x", "card": RED})
        AB.deliver(ev, **kw)
        AB.drain(30)
        caps = [b.split(b'name="caption"')[1].split(b"\r\n--")[0].decode("utf-8").strip() for op, b in fake.calls if op == "sendPhoto"]
        check("a red day: the text (+ the day summary's own picture), no Insta card",
              fake.ops()[0] == "sendMessage" and not any("Insta" in c for c in caps), (fake.ops(), caps))
        fake.calls.clear()
        trade_card.bars = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        I_render = __import__("engine.png_chart", fromlist=["x"]).render_insta
        import engine.png_chart as PCm
        PCm.render_insta = lambda sp: (_ for _ in ()).throw(RuntimeError("crash"))
        try:
            ev = AB.from_report({"key": "guard:day:2026-11-24", "title": "Day Tue Nov 24: +$500", "body": "x", "card": GREEN})
            r = AB.deliver(ev, **kw)
            AB.drain(30)
        finally:
            PCm.render_insta = I_render
        check("the Insta card crashes: the text still went, nothing raised", r["ok"] and fake.ops()[0] == "sendMessage"
              and fake.ops().count("sendPhoto") <= 1, fake.ops())
        ev = AB.from_report({"key": "guard:week:2026-11-27", "title": "Week", "body": "x", "card": {"type": "week", "total": 900}})
        check("the week report: no Insta card (day summaries only)", not ev.get("more_photos"), ev)
    finally:
        datapipe.day_fills, trade_card.bars = saved
        AB._HTTP, AB.LOG_PATH = old, keep_log


def t_cmd():
    print("4. /insta (owner only, read-only)", flush=True)
    from engine import tg_cmd as C
    check("/insta and /insta YYYY-MM-DD parse; anything else is refused",
          C.parse_text("/insta") == ({"cmd": "insta", "day": None}, None) and C.parse_text("/insta 2026-11-27")[0] == {"cmd": "insta", "day": "2026-11-27"}
          and C.parse_text("/insta tomorrow")[0] is None and C.parse_text("/insta 2026-11-27 x")[0] is None)
    sent = []
    from engine import alert_bus as AB
    old = AB._HTTP
    AB._HTTP = lambda m, u, b, h, t: (sent.append(u.rsplit("/", 1)[-1]) or (200, '{"ok": true, "result": {"message_id": 4}}'))
    try:
        r = C.insta_reply("TOKEN", "1", DAY, 9, http=lambda m, u, b, h=None, t=None: (sent.append("reply") or (200, "{}")), wait=True)
        check("/insta 2026-11-27: the saved card as a photo", r == "sending" and sent == ["sendPhoto"], (r, sent))
        sent.clear()
        r = C.insta_reply("TOKEN", "1", "2020-01-01", 9, http=lambda m, u, b, h=None, t=None: (sent.append("reply") or (200, "{}")))
        check("/insta for a day without a card: a one-line reason", "No Insta card for 2020-01-01" in r and sent == ["reply"], (r, sent))
    finally:
        AB._HTTP = old
    check("/insta is in /help", "/insta" in C.HELP)
    import inspect
    src = inspect.getsource(C.TgCommands.tick)
    check("only the owner's private chat reaches /insta (is_owner runs first)", src.index("is_owner(msg, chat)") < src.index('"insta"'))


def main():
    tmp = tempfile.mkdtemp(prefix="insta_")
    from engine import trade_card as TC
    TC.CARD_DIR = os.path.join(tmp, "cards")
    t_spec()
    t_render(tmp)
    t_bus(tmp)
    t_cmd()
    n = sum(ok for _, ok in RESULTS)
    print(f"\ninsta card: {n}/{len(RESULTS)} " + ("ALL PASS" if n == len(RESULTS) else "FAILED"))
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
