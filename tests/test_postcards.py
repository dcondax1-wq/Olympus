"""PERSONALISED POSTCARDS (tools/postcards.py, day-a11y 2026-11-20): a fake Lob, a temp OLYMPUS_HOME, never the network.

    python -X utf8 -m tests.test_postcards
a. the art: 3 sample cards (front + back PNG, one 6-page PDF), 4x6 + bleed at 300 dpi, the QR made locally, the back's address block left blank,
   the honest words: the business name, the link, the sender, the return address, a way to say "no more mail"
b. who gets a card: a full street address (the map's one-line address cleaned), their OWN concept site built, never twice, never a 'no'
   (the ONE never-again list shared with the email autopilot: lead ids, emails, its opt-outs and bounces)
c. the gate + the limits: OFF by default; TEST mode = 3 a day with a test_ key; LIVE only with the phrase SEND POSTCARDS AND a live_ key;
   20 a day, 100 a week, weekdays after 10:00 ET, once a day
d. the provider call: Lob's form (4x6, First Class, marketing, to / from, front / back PNG), the key only in the Basic auth header
e. no secret: the key is in postcards.json only (not the state, not an error, not the printed output, not the repo)
f. the Windows side: POSTCARD_SETUP.bat (installs Pillow + segno, setup -> samples -> the task), POSTCARD_STOP.bat, CRLF
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS: list = []
N = [0]
KEY_T, KEY_L = "test_0123456789abcdef0123456789abcdef", "live_fedcba9876543210fedcba9876543210"


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


def T(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h + 5, mi, tzinfo=dt.timezone.utc)      # ET (November) -> UTC


def main():
    tmp = tempfile.mkdtemp(prefix="postcards-")
    os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "home")
    try:
        import segno  # noqa: F401
        from PIL import Image
    except ImportError:
        print("SKIP: needs Pillow + segno (pip install pillow segno)")
        return
    from tools import postcards as P
    cfg = P.norm_cfg({"api_key": KEY_T, "mode": "test", "from_name": "Sam Test", "business_name": "Peak Web Studio", "reply_email": "hello@peak.example",
                      "return": {"line1": "PO Box 12", "city": "Frederick", "state": "MD", "zip": "21701"}, "site_base": "https://example.org/site"})
    try:
        # ---------------------------------------------------------------- a. the art
        files = P.samples(os.path.join(tmp, "s"), cfg)
        pngs = [f for f in files if f.endswith(".png")]
        check("a. 3 sample cards: 6 PNG sides + one PDF", len(pngs) == 6 and files[-1].endswith(".pdf") and os.path.getsize(files[-1]) > 10000, files)
        L = {"id": "osm-1", "name": "Joe's Diner", "niche": "food", "address": "12 Main Street, Frederick", "city": "Frederick", "state": "MD"}
        fr, bk = P.render(L, cfg, "https://example.org/site/agency/sites/joes/")
        check("a. 4x6 + the 1/8\" bleed at 300 dpi (1875 x 1275)", fr.size == (1875, 1275) == bk.size)
        zone = bk.crop(P.ADDR_ZONE).convert("L")
        check("a. the back's address + postage block is left blank for the printer", zone.getextrema()[0] >= 250, zone.getextrema())
        q = fr.crop((1875 - int(2.2 * 300) - int(0.45 * 300), int(0.85 * 300), 1875 - int(0.45 * 300), int(0.85 * 300) + int(2.2 * 300))).convert("L")
        dark = sum(1 for v in q.getdata() if v < 80) / (q.size[0] * q.size[1])
        check("a. the QR code is on the front (made on this PC by segno)", 0.25 < dark < 0.75, round(dark, 2))
        src = open(os.path.join(ROOT, "tools", "postcards.py"), encoding="utf-8").read()
        check("a. the honest words: the business by name, 'free to look', the call-me button, the sender, the return address, 'no more mail'",
              all(x in src for x in ("your new website is already built", "free to look", "Have our assistant call me", "Don't want mail from us?", "STOP", "return")))
        check("a. a clean agency brand, not the OLYMPUS look (no gold, no AGORA, no Olympus name on the card)", "OLYMPUS" not in src.split("def render")[1].split("def png")[0]
              and "#c8a24a" not in src and "gold" not in src.split("BRAND =")[1].split("\n")[0])

        # ---------------------------------------------------------------- b. who gets a card
        a1, w1 = P.mail_address({"name": "Pearl", "address": "196, Suite 200 Thomas Johnson Drive, Frederick", "city": "Frederick", "state": "MD"})
        a2, w2 = P.mail_address({"name": "X", "address": "", "city": "Frederick", "state": "MD"})
        a3, _ = P.mail_address({"name": "Y", "addr": {"line1": "5 Elm St", "city": "Frederick", "state": "MD", "zip": "21701"}})
        check("b. the map's one-line address cleaned ('196 Thomas Johnson Drive Suite 200, Frederick MD'); none = skipped with a reason; the leads team's structured address + ZIP first",
              a1 and a1["address_line1"] == "196 Thomas Johnson Drive Suite 200" and a1["address_city"] == "Frederick" and a2 is None and "street" in w2
              and a3["address_zip"] == "21701", (a1, w2, a3))
        leads = [dict(L, id=f"L{i}", name=f"Shop {i}", address=f"{10 + i} Main Street, Frederick", heat="hot" if i < 2 else "cold", score=i) for i in range(30)]
        leads.append({"id": "Lnoaddr", "name": "No Address", "city": "Frederick", "state": "MD", "heat": "hot"})
        sites = {x["id"]: f"sites/{x['id']}/" for x in leads}
        sites.pop("L5")
        never = {"lead_ids": {"L1"}, "emails": set()}
        got, skip = P.pick(leads, {"L0": {}}, never, sites, 50)
        ids = [x[0]["id"] for x in got]
        check("b. never twice, never a 'no', never without a built site or a street address; each skip counted with its reason",
              "L0" not in ids and "L1" not in ids and "L5" not in ids and "Lnoaddr" not in ids and skip.get("already sent") == 1 and skip.get("said no (never again)") == 1
              and skip.get("their own concept site is not built yet") == 1, (ids[:3], skip))
        os.makedirs(os.environ["OLYMPUS_HOME"], exist_ok=True)
        json.dump({"suppress": ["no@shop7.example"], "replied": {"L8": "optout", "L9": "bounce", "L10": "question"}}, open(os.path.join(os.environ["OLYMPUS_HOME"], "agency_mail_state.json"), "w"))
        P.add_never("L11")
        nl = P.never_list()
        check("b. the ONE never-again list: agency_never.json + the email autopilot's opt-outs / bounces / suppressed emails (a question is not a no)",
              {"L8", "L9", "L11"} <= nl["lead_ids"] and "L10" not in nl["lead_ids"] and "no@shop7.example" in nl["emails"], nl)

        # ---------------------------------------------------------------- c. the gate + the limits
        calls = []

        def fake_send(c, to, front, back, lid):
            calls.append((c["api_key"][:5], to["address_line1"], lid))
            return {"id": f"psc_{len(calls)}", "test": c["api_key"].startswith("test_")}
        st = {}
        r = P.run_once(P.norm_cfg({}), st, leads, sites, now=T(2026, 11, 23, 11), send=fake_send)
        check("c. OFF by default: nothing", not r["sent"] and not calls)
        r = P.run_once(cfg, st, leads, sites, now=T(2026, 11, 23, 11), send=fake_send)
        check("c. TEST mode: 3 cards a day with the test_ key, nothing counted as a real card", len(r["sent"]) == 3 and all(c[0] == "test_" for c in calls)
              and all(v.get("test") for v in st["sent"].values()), r)
        r2 = P.run_once(cfg, st, leads, sites, now=T(2026, 11, 23, 13), send=fake_send)
        check("c. once a day (a second run the same day sends nothing)", not r2["sent"])
        live = dict(cfg, mode="live", api_key=KEY_L)
        st2 = {}
        r = P.run_once(live, st2, leads, sites, now=T(2026, 11, 24, 11), send=fake_send)
        check("c. LIVE without the typed phrase: refused", not r["sent"] and any("SEND POSTCARDS" in e for e in r["errors"]), r["errors"])
        r = P.run_once(dict(live, api_key=KEY_T), {"phrase": "SEND POSTCARDS"}, leads, sites, now=T(2026, 11, 24, 11), send=fake_send)
        check("c. LIVE with a test_ key: refused (the key must match the mode)", not r["sent"] and r["errors"], r["errors"])
        st2 = {"phrase": "SEND POSTCARDS"}
        calls.clear()
        per = []
        for d in (23, 24, 25, 26, 27, 28):                                 # Mon-Sat of one week (wider leads list so the cap bites)
            big = leads + [dict(L, id=f"M{i}", name=f"More {i}", address=f"{200 + i} Oak Street, Frederick", heat="warm", score=i) for i in range(150)]
            bsites = dict(sites, **{f"M{i}": f"sites/M{i}/" for i in range(150)})
            per.append(len(P.run_once(live, st2, big, bsites, now=T(2026, 11, d, 11), send=fake_send)["sent"]))
        check("c. LIVE with the phrase: 20 a day, nothing on Saturday", per[:5] == [20, 20, 20, 20, 20] and per[5] == 0, per)
        check("c. 100 a week at most", sum(per) <= 100, sum(per))
        check("c. not before 10:00 ET", not P.run_once(live, {"phrase": "SEND POSTCARDS"}, leads, sites, now=T(2026, 11, 30, 9, 59), send=fake_send)["sent"])
        check("c. a card goes only to businesses never sent before (no address twice)", len({c[1] for c in calls}) == len(calls))

        # ---------------------------------------------------------------- d. the provider call
        seen = {}

        class Resp:
            def __init__(self, b):
                self.b = b

            def read(self):
                return self.b

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        def opener(req, timeout=0):
            seen["url"], seen["auth"], seen["body"], seen["ct"] = req.full_url, req.get_header("Authorization"), req.data, req.get_header("Content-type")
            return Resp(b'{"id": "psc_123"}')
        to, _ = P.mail_address(leads[3])
        out = P.lob_send(cfg, to, P.png(fr), P.png(bk), "L3", opener=opener)
        body = seen["body"].decode("latin-1")
        import base64
        check("d. Lob's postcards endpoint, the key only as Basic auth, 4x6 First Class marketing, to / from / front / back PNG",
              seen["url"] == P.LOB_URL and seen["auth"] == "Basic " + base64.b64encode((KEY_T + ":").encode()).decode() and KEY_T not in body
              and all(f'name="{k}"' in body for k in ("size", "mail_type", "use_type", "to[address_line1]", "from[address_zip]", "front", "back"))
              and "usps_first_class" in body and "marketing" in body and out == {"id": "psc_123", "test": True}, (seen.get("url"), out))

        # ---------------------------------------------------------------- e. no secret
        import tools.postcards as PP

        def boom(c, *a, **k):
            raise RuntimeError("401 bad key " + c["api_key"])
        r = PP.run_once(dict(cfg), {}, leads, sites, now=T(2026, 12, 1, 11), send=boom)
        check("e. an error that quotes the key never repeats it", r["errors"] and all(KEY_T not in e for e in r["errors"]), r["errors"])
        ans = iter(["Sam Test", "Peak Web Studio", "hello@peak.example", "PO Box 12", "Frederick", "MD", "21701", "send postcards please"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = P.cmd_setup(ask=lambda p: next(ans), secret=lambda p: KEY_T, out=print)
        saved = json.load(open(os.path.join(os.environ["OLYMPUS_HOME"], "postcards.json")))
        check("e. setup without the exact phrase = TEST mode; the key saved, never printed", rc == 0 and saved["mode"] == "test" and saved["api_key"] == KEY_T and KEY_T not in buf.getvalue(), saved.get("mode"))
        ans = iter(["", "", "", "", "", "", "", "SEND POSTCARDS"])
        with redirect_stdout(buf):
            rc = P.cmd_setup(ask=lambda p: next(ans), secret=lambda p: KEY_L, out=print)
        saved = json.load(open(os.path.join(os.environ["OLYMPUS_HOME"], "postcards.json")))
        stt = json.load(open(os.path.join(os.environ["OLYMPUS_HOME"], "postcards_state.json")))
        check("e. the phrase SEND POSTCARDS + a live_ key = LIVE (the phrase recorded in the state, the key never there)", saved["mode"] == "live" and stt.get("phrase") == "SEND POSTCARDS" and KEY_L not in json.dumps(stt))
        leak = []
        for dp, _, fs in os.walk(os.environ["OLYMPUS_HOME"]):
            for f in fs:
                if f != "postcards.json" and (KEY_T in open(os.path.join(dp, f), errors="replace").read() or KEY_L in open(os.path.join(dp, f), errors="replace").read()):
                    leak.append(f)
        check("e. the key is in postcards.json only", not leak, leak)
        tracked = subprocess.run(["git", "grep", "-l", "-I", "-E", "(test|live)_[0-9a-f]{32}"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        check("e. no Lob key in the repo (only this test's made-up ones)", set(tracked) <= {"tests/test_postcards.py"}, tracked)

        # ---------------------------------------------------------------- f. the Windows side
        bs, bt = open(os.path.join(ROOT, "POSTCARD_SETUP.bat"), "rb").read(), open(os.path.join(ROOT, "POSTCARD_STOP.bat"), "rb").read()
        check("f. both .bat files use CRLF", all(b"\n" not in x.replace(b"\r\n", b"") for x in (bs, bt)))
        s = bs.decode()
        check("f. POSTCARD_SETUP.bat: installs Pillow + segno, setup -> samples -> the task -> status (stops when setup fails)",
              "pip install --user --quiet segno pillow" in s and s.index("postcards.py setup") < s.index("postcards.py samples") < s.index("agency_mail_task.ps1") < s.index("postcards.py status")
              and "if errorlevel 1 goto :end" in s)
        check("f. POSTCARD_STOP.bat: OFF", "postcards.py stop" in bt.decode())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
