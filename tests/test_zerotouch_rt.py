"""Zero-touch red team (2026-11-23). Offline: temp files, fake processes; nothing opens, arms or trades.

  a. a keep-alive file from BEFORE owner_off existed: an explicit false is the owner's OFF, a START phrase keeps it off
  b. self-heal reopens a closed NinjaTrader at most twice a day and never again when it was closed within 6 h of its own open
  c. START BOT with the bot already running: no console at the keep-alive question = left off, no crash
    python -X utf8 -m tests.test_zerotouch_rt
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import keepalive as K  # noqa: E402
from engine import self_heal as SH  # noqa: E402
from engine import go as G  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


ARMED = [("lit", "Zlarior 50K ..6016", "MFFUEVBLDR000006016"), ("atlas", "ATLAS 25K ..6018", "MFFUSFBLDR000006018")]


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "keepalive.json")
        json.dump({"accounts": {"atlas": False}}, open(p, "w"))          # he turned ATLAS off before this update
        r = K.start_consent(LIVE_PHRASE, ARMED, path=p)
        c = json.load(open(p))
        check("a1. old file, ATLAS explicitly off: the START phrase keeps ATLAS OFF, turns on only the 50K",
              c["accounts"].get("atlas") is False and c["accounts"].get("lit") is True and "ATLAS 25K ..6018" in r["kept_off"], (r, c))
        r2 = K.start_consent(LIVE_PHRASE, ARMED, path=p)                 # the next START (file now has "consent")
        c2 = json.load(open(p))
        check("a2. ... and the next START too (the old OFF is kept as owner_off: only KEEPALIVE_ON clears it)",
              c2["accounts"].get("atlas") is False, (r2, c2))
        q = os.path.join(d, "fresh.json")
        r3 = K.start_consent(LIVE_PHRASE, ARMED, path=q)
        check("a3. no file at all (never set): both on", sorted(json.load(open(q))["accounts"]) == ["atlas", "lit"], r3)
        r4 = K.start_consent("i accept", ARMED, path=os.path.join(d, "none.json"))
        check("a4. no exact phrase: nothing written", not os.path.exists(os.path.join(d, "none.json")) and not r4["on"], r4)
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "data"))
        json.dump({"cfg": {}}, open(os.path.join(tmp, "data", "autostart.json"), "w"))
        opened = []

        def ctx(now):
            return SH.Ctx(root=tmp, now=now, apply=True, procs=[(1, "python.exe")], is_windows=True, git=lambda *a, **k: (0, ""),
                          ping=lambda: True, nt=None, open_nt=lambda: opened.append(now) or True)
        t0 = 1795000000.0                                               # a weekday, ET morning
        a = SH.fix_nt(ctx(t0))
        b = SH.fix_nt(ctx(t0 + 3600))                                   # an hour later it is closed again (by him)
        check("b1. opened once; closed again within 6 h = left closed, one 'need' line", opened == [t0] and a[0]["status"] == "fixed"
              and b and b[0]["status"] == "need" and "closed again" in b[0]["what" if "what" in b[0] else "text"] if b else False, (a, b))
        c = SH.fix_nt(ctx(t0 + 7 * 3600))
        d_ = SH.fix_nt(ctx(t0 + 14 * 3600))
        check("b2. at most 2 opens a day", len([x for x in opened]) == 2 and d_ and d_[0]["status"] == "need", (opened, c, d_))
    real = {k: getattr(G, k) for k in ("bot_running", "keepalive_missing", "_open", "keepalive_consent", "CFG")}
    tmpd = tempfile.mkdtemp()
    G.CFG = os.path.join(tmpd, "start_bot.json")
    json.dump({"lit": "MFFUEVBLDR000006016", "atlas": "MFFUSFBLDR000006018"}, open(G.CFG, "w"))
    calls = []
    G.bot_running = lambda: True
    G.keepalive_missing = lambda: ["ATLAS 25K ..6018"]
    G._open = lambda: None
    G.keepalive_consent = lambda ph, main_on=True: calls.append(ph)

    def eof(prompt=""):
        raise EOFError
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = G.run(dry=False, inp=eof, pull=False)
        check("c. bot running, stdin closed at the keep-alive question: rc 0, nothing switched", rc == 0 and not calls, (rc, calls))
    except Exception as e:  # noqa: BLE001
        check("c. bot running, stdin closed at the keep-alive question: rc 0, nothing switched", False, repr(e))
    finally:
        for k, v in real.items():
            setattr(G, k, v)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
