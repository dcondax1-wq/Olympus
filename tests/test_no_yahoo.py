"""No Yahoo (owner 2026-10-19: "I don't want Yahoo. Use NinjaTrader or TradingView data only."; engine/pcbars.py).

    python -X utf8 -m tests.test_no_yahoo            # everything (~2 min: two cloud monitor runs)
    python -X utf8 -m tests.test_no_yahoo --quick    # without the cloud monitor runs

Every check runs with yfinance replaced by a module that raises and urllib / requests refusing any Yahoo URL
(pcbars.install_yahoo_guard), and urlopen recording every URL (nothing leaves the machine):
 1. PC live loop (engine/live.py LiveBot, LIT, paper adapter, NinjaTrader LE_BarFeed files on a frozen clock):
    no_yahoo is on by default, data_source "yahoo" becomes "ninjatrader", a poll makes no Yahoo call, VIX goes to CBOE.
 2. FEED STALE: NinjaTrader files 40 min old -> no Yahoo call, nt_down + entries_blocked at once, an entry is NOT routed,
    the heartbeat health block / the cloud verdict say FEED STALE.
 3. Roundtrip: the PC's bars (PCBars) -> heartbeat.push (temp bare repo) -> heartbeat.read -> CloudFeed: same bars.
 4. Basis: a constant offset on the overlap (a roll) back-adjusts the older bars; MNQ-vs-NQ tick noise does not.
 5. CBOE VIX parser + merge (temp file; data/VIX_1d.csv is never written).
 6. Cloud monitor (tools/cloud_monitor.run, fake heartbeat with the PC's bars): no Yahoo call, bars from the PC; then a
    stale heartbeat -> "waiting for NinjaTrader bars from the PC", a pause opens, no new paper entry inside it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:400]}"), flush=True)


def at(y, m, d, hh, mm, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


NOW = at(2026, 10, 16, 10, 3, 30)       # Friday 10:03:30 ET: in session, inside LIT's 02:00-15:30 entry window
TV_END = at(2026, 10, 14, 0, 0)          # pretend the TradingView export ends here (the NinjaTrader feed overlaps it)
NT_FROM = at(2026, 10, 12, 18, 0)


def _bars(tf):
    return pd.read_csv(os.path.join(ROOT, "data", f"NQ_{tf}.csv"))


def write_feed(folder, upto, b1, b5):
    """LE_BarFeed's files (MNQ_1m.csv, MNQ_5m.csv: closed bars, time = bar open) up to `upto` (exclusive of the forming bar)."""
    d = os.path.join(folder, "le_feed")
    os.makedirs(d, exist_ok=True)
    for name, df, secs in (("MNQ_1m.csv", b1, 60), ("MNQ_5m.csv", b5, 300)):
        x = df[(df["time"] >= NT_FROM) & (df["time"] + secs <= upto)]
        x[["time", "open", "high", "low", "close", "volume"]].to_csv(os.path.join(d, name), index=False, header=False)


class Net:
    """urlopen stand-in under the Yahoo guard: records every URL, answers none (no network in this test)."""

    def __init__(self):
        self.urls = []

    def __call__(self, req, *a, **kw):
        self.urls.append(req if isinstance(req, str) else getattr(req, "full_url", str(req)))
        raise OSError("offline test: no network")


def main():
    quick = "--quick" in sys.argv
    os.environ.pop("LE_NO_YAHOO", None)
    os.environ.pop("LE_LIVE_MODEL", None)
    import urllib.request
    net = Net()
    orig_urlopen = urllib.request.urlopen
    urllib.request.urlopen = net                         # recorded first, then wrapped by the Yahoo guard
    from engine import pcbars
    undo = pcbars.install_yahoo_guard()
    tmp = tempfile.mkdtemp(prefix="le_noyahoo_")
    try:
        from engine import accounts, alerts, heartbeat, live, news
        alerts.send = lambda *a, **kw: None
        news.ff_calendar = lambda: []
        news.guard = lambda now=None, params=None, vol=None, events=None: {"allowed": True, "reasons": [], "regime": None,
                                                                            "next_high": None, "now": now}
        news.DATA = os.path.join(tmp, "newsdata")             # CBOE's VIX would be written here, never into data/
        os.makedirs(news.DATA, exist_ok=True)
        for n in ("VIX", "VXN"):
            shutil.copy(os.path.join(ROOT, "data", f"{n}_1d.csv"), os.path.join(news.DATA, f"{n}_1d.csv"))
        b1, b5 = _bars("1m"), _bars("5m")
        check("policy: live_model.json says no_yahoo true and pcbars.no_yahoo() is on by default",
              json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("no_yahoo") is True and pcbars.no_yahoo()
              and pcbars.no_yahoo({"no_yahoo": False}) is False)

        # ---------------------------------------------------------------- 1. the PC live loop
        print("1. PC live loop (LIT, paper, NinjaTrader files)", flush=True)
        folder = os.path.join(tmp, "NinjaTrader 8")
        write_feed(folder, NOW - NOW % 60, b1, b5)
        clock = [NOW]
        bot = live.LiveBot()
        bot.clock = lambda: clock[0]
        bot.state_path = os.path.join(tmp, "live_state.json")
        bot._remember = lambda *a, **kw: None
        tv = {tf: df[df["time"] < TV_END].reset_index(drop=True) for tf, df in (("1m", b1), ("5m", b5))}
        bot.read_hist = lambda sym, tf: tv.get(tf, pd.DataFrame(columns=pcbars.COLS)) if sym == "NQ" else pd.DataFrame(columns=pcbars.COLS)
        r = bot.start({"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "nt_folder": folder}, spawn=False)
        check("start: no_yahoo on, data_source 'yahoo' (the default) became 'ninjatrader'",
              r.get("ok") and bot.no_yahoo and bot.cfg["data_source"] == "ninjatrader" and bot.health.get("no_yahoo"), r)
        n_url = len(net.urls)
        st = err = None
        try:
            st = bot.poll_once()
        except Exception as e:
            err = f"{e.__class__.__name__}: {e}"
        h = bot.health
        last5 = h.get("last_bar_t")
        check("poll: no Yahoo / yfinance call, the bars are NinjaTrader's (last closed 5m bar 09:55 ET, last 1m 10:02 ET)",
              st is not None and not undo.calls and not any("yahoo" in u.lower() for u in net.urls)
              and last5 == at(2026, 10, 16, 9, 55) and h.get("last_1m_bar_t") == at(2026, 10, 16, 10, 2)
              and not h.get("nt_down") and not h.get("nt_down_1m") and not h.get("entries_blocked") and not h.get("stale"),
              f"err={err} yahoo={undo.calls} last5={last5} h={ {k: h.get(k) for k in ('nt_down', 'nt_down_1m', 'stale', 'entries_blocked', 'last_1m_bar_t')} }")
        check("VIX / VXN refresh goes to CBOE, not Yahoo",
              any(("cdn-api.cboe.com" in u or "cdn.cboe.com" in u) and "VIX_History" in u for u in net.urls[n_url:]), net.urls[n_url:])
        check("history: the TradingView file ends 10-14, NinjaTrader's starts 10-12 18:00: overlap, no gap noted",
              not any((h.get("hist_gap") or {}).values()), h.get("hist_gap"))

        # ---------------------------------------------------------------- 2. FEED STALE
        print("2. FEED STALE blocks new entries (no Yahoo fallback)", flush=True)
        write_feed(folder, NOW - NOW % 60 - 40 * 60, b1, b5)
        bot._nt_feed = None
        clock[0] = NOW + 60
        st2 = None
        try:
            st2 = bot.poll_once()
        except Exception as e:
            err = f"{e.__class__.__name__}: {e}"
        h = bot.health
        check("stale NinjaTrader files: no Yahoo call, nt_down set, NEW entries blocked at once (no 3-poll grace)",
              st2 is not None and not undo.calls and "stale" in str(h.get("nt_down")) and h.get("entries_blocked")
              and h.get("feed_block") and not h.get("fallback"), {k: h.get(k) for k in ("nt_down", "entries_blocked", "feed_block", "fallback")})
        check("the log says FEED STALE ... no Yahoo fallback ... new entries blocked",
              any("FEED STALE" in x["text"] and "no Yahoo" in x["text"] for x in bot.log), [x["text"] for x in list(bot.log)[:5]])
        ent_t = NOW - NOW % 300
        bot.state = {"model": "lit", "position": {"entry_t": ent_t, "dir": 1, "qty": 3, "entry": 29000.0, "stop": 28950.0,
                                                  "target": 29100.0, "risk_pts": 50.0, "setup": "LIT"}}
        bot.started_at = ent_t - 3600
        n_led = len(bot.ledger)
        bot._route_signals({"trades": [], "events": []}, "NQ", int(clock[0]), 300)
        check("an entry while the feed is stale is NOT routed (no order), logged as 'feed stale'",
              not [x for x in bot.ledger[n_led:] if x.get("side") in ("buy", "sell")]
              and any("NOT routed: feed stale" in x["text"] for x in bot.log))
        hl = accounts.pc_health(bot)
        f = hl.get("feed") or {}
        check("heartbeat health block: no_yahoo, used ninjatrader (never 'yahoo'), entries_blocked, the reason",
              f.get("no_yahoo") and f.get("used") == "ninjatrader" and f.get("entries_blocked") and "stale" in str(f.get("block")), f)
        hb = {"present": True, "t": int(time.time()), "every_s": 300, "running": True,
              "health": {**hl, "running": True, "kill": False, "model": "lit",
                         "account": {**(hl.get("account") or {}), "adapter": "ninjatrader", "is_live": True, "enabled": True,
                                     "name": "MFFUEV1", "label": "LIVE"},
                         "poll": {**(hl.get("poll") or {}), "age_s": 30},
                         "feed": {**f, "market_open": True, "age_5m_s": 100, "age_1m_s": 50, "stale": False}}}
        v = accounts.verdict(hb, now=at(2026, 10, 19, 10, 0))
        check("cloud verdict on that heartbeat: FEED STALE (new entries blocked)", v["code"] == "FEED" and v["label"] == "FEED STALE"
              and "blocked" in v["reason"], v)
        write_feed(folder, NOW - NOW % 60 + 120, b1, b5)
        bot._nt_feed = None
        clock[0] = NOW + 150
        bot.poll_once()
        check("fresh again: entries allowed, 'Feed recovered' logged", not bot.health.get("entries_blocked")
              and any("Feed recovered" in x["text"] for x in bot.log) and not undo.calls)

        # ---------------------------------------------------------------- 3. PC bars -> heartbeat -> cloud
        print("3. PC bars -> heartbeat branch -> cloud", flush=True)
        bare, work = os.path.join(tmp, "bare.git"), os.path.join(tmp, "work")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        subprocess.run(["git", "init", "-q", work], check=True)
        subprocess.run(["git", "-C", work, "remote", "add", "origin", bare], check=True)
        pb = pcbars.PCBars(sym="NQ", root=os.path.join(tmp, "no_archive"))
        files = pb.files(bot, now=clock[0])
        meta = pcbars.PCBars.meta(files, bot)
        res = heartbeat.push({"t": int(clock[0]), "running": True, "every_s": 300, "bars": meta}, cwd=work, files=files)
        got = heartbeat.read(cwd=work, now=clock[0] + 30, files=pcbars.HB_FILES)
        cf = pcbars.CloudFeed(os.path.join(tmp, "dash0"), got, now=clock[0] + 30)
        nt1 = bot._nt_last[("NQ", "1m")]
        nt1 = nt1[nt1["time"] >= clock[0] - pcbars.BARS_1M_DAYS * 86400]
        same1 = len(cf.b1) == len(nt1) and (cf.b1[["time", "open", "high", "low", "close"]].to_numpy()
                                             == pcbars.tidy(nt1)[["time", "open", "high", "low", "close"]].to_numpy()).all()
        r5 = cf.recent("NQ", "5m")
        n5 = bot._nt_last[("NQ", "5m")]
        both = r5.merge(pcbars.tidy(n5), on="time", suffixes=("", "_n"))
        check("push/read roundtrip: the 1m bars arrive byte-identical, 5m equal on every bar, gz sizes small",
              res["ok"] and got["files"][pcbars.BARS_1M] == files[pcbars.BARS_1M] and same1 and len(both) > 500
              and (both["close"] == both["close_n"]).all() and len(files[pcbars.BARS_1M]) < 120_000,
              f"push={res} n1={len(cf.b1)}/{len(nt1)} n5={len(both)} sizes={ {k: len(v) for k, v in files.items()} }")
        stt = cf.status()
        check("cloud feed status ok (fresh PC bars), the store saved, ES / anything else: None (never Yahoo)",
              stt["ok"] and os.path.exists(os.path.join(tmp, "dash0", pcbars.STORE_5M)) and cf.recent("ES", "5m") is None, stt)
        stale_hb = dict(got, files={pcbars.BARS_1M: pcbars.encode(nt1[nt1["time"] < clock[0] - 3600])})
        s2 = pcbars.CloudFeed(None, stale_hb, now=clock[0]).status()
        s3 = pcbars.CloudFeed(None, {"present": False}, now=clock[0]).status()
        check("cloud feed: PC bars an hour old / no heartbeat -> not ok, 'waiting for NinjaTrader bars from the PC'",
              not s2["ok"] and pcbars.WAITING in s2["text"] and not s3["ok"] and pcbars.WAITING in s3["text"], [s2, s3])
        files2 = pb.files(bot, now=clock[0] + 600)
        check("the 5m file is rebuilt at most hourly: the same bytes 10 min later (same git blob, nothing new to push)",
              files2[pcbars.BARS_5M] is files[pcbars.BARS_5M])

        # ---------------------------------------------------------------- 4. basis
        print("4. price basis (TradingView NQ1! vs NinjaTrader MNQ)", flush=True)
        a = b5[(b5["time"] >= at(2026, 10, 1, 0, 0)) & (b5["time"] < TV_END)].reset_index(drop=True)
        rolled = a.copy()
        for c in ("open", "high", "low", "close"):
            rolled[c] = rolled[c] + 187.25
        m, sh = pcbars.merge_basis(a, rolled.tail(500))
        jitter = a.copy()
        jitter["close"] = jitter["close"] + [0.25 if i % 3 == 0 else 0.0 for i in range(len(jitter))]
        m2, sh2 = pcbars.merge_basis(a, jitter.tail(500))
        check("a roll (+187.25 on the overlap) back-adjusts the older bars onto the new contract; tick noise shifts nothing",
              sh == 187.25 and abs(float(m["close"].iloc[0]) - float(a["close"].iloc[0]) - 187.25) < 1e-9 and sh2 == 0.0
              and float(m2["close"].iloc[0]) == float(a["close"].iloc[0]), (sh, sh2))
        arc = os.path.join(tmp, "arc")
        r1 = pcbars.archive_add("NQ", "5m", a.head(300), root=arc, now=TV_END)
        r2 = pcbars.archive_add("NQ", "5m", a.iloc[250:400], root=arc, now=TV_END)
        ar = pcbars.archive_read("NQ", "5m", arc)
        check("archive: first write, then append only the newer bars (no duplicates)",
              r1["rewritten"] and r2["added"] == 100 and not r2["rewritten"] and len(ar) == 400 and ar["time"].is_unique, (r1, r2, len(ar)))

        # ---------------------------------------------------------------- 5. CBOE VIX
        print("5. CBOE VIX", flush=True)
        vp = os.path.join(tmp, "VIX_1d.csv")
        shutil.copy(os.path.join(ROOT, "data", "VIX_1d.csv"), vp)
        old = pd.read_csv(vp)
        last_d = str(old["date"].iloc[-1])
        nd = (pd.Timestamp(last_d) + pd.offsets.BDay(1))
        raw = ("DATE,OPEN,HIGH,LOW,CLOSE\n" + f"{pd.Timestamp(last_d):%m/%d/%Y},16.02,22.31,15.72,19.99\n"
               + f"{nd:%m/%d/%Y},19.5,20.1,18.2,18.75\n").encode()
        out = news._cboe_daily("VIX", vp, fetch=lambda u: raw)
        check("CBOE file: adds the new date, keeps the history, its close wins for the last stored dates",
              len(out) == len(old) + 1 and float(out["close"].iloc[-1]) == 18.75 and abs(float(out.loc[last_d, "close"]) - 19.99) < 1e-9
              and str(out.index[0]) == str(old["date"].iloc[0]), out.tail(3))

        # ---------------------------------------------------------------- 6. cloud monitor
        if not quick:
            print("6. cloud monitor on the PC's bars (fake heartbeat)", flush=True)
            cloud_run(tmp, bot, b1, b5, undo, net)
    finally:
        undo()
        urllib.request.urlopen = orig_urlopen
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nno-Yahoo test: {'PASS' if n_ok == len(RESULTS) else 'FAIL'} ({n_ok}/{len(RESULTS)})")
    return n_ok == len(RESULTS)


def cloud_run(tmp, bot, b1, b5, undo, net):
    import cloud_monitor as cm
    from engine import heartbeat, live, pcbars, push
    out = os.path.join(tmp, "dash")
    os.makedirs(out, exist_ok=True)
    clock = [NOW + 150]
    hbs = {}

    def fake_read(cwd=None, remote="origin", branch="heartbeat", now=None, files=()):
        hb = json.loads(json.dumps(hbs["hb"]))
        hb.update(present=True, age_s=int((now or clock[0]) - hb["t"]), silent=False)
        if files:
            hb["files"] = {n: hbs["files"].get(n) for n in files}
        return hb

    def make_hb(upto):
        f1 = pcbars.tidy(bot._nt_last[("NQ", "1m")])
        f5 = pcbars.tidy(bot._nt_last[("NQ", "5m")])
        f1, f5 = f1[f1["time"] + 60 <= upto], f5[f5["time"] + 300 <= upto]
        files = {pcbars.BARS_1M: pcbars.encode(f1[f1["time"] >= upto - 3 * 86400]), pcbars.BARS_5M: pcbars.encode(f5)}
        hbs.update(hb={"t": int(upto), "running": True, "adapter": "ninjatrader", "every_s": 300, "host": "test",
                       "bars": pcbars.PCBars.meta(files)}, files=files)

    saved = (heartbeat.read, push.Relay.read, cm.time.time, live.LiveBot._read_hist)
    tv5 = b5[b5["time"] < TV_END].reset_index(drop=True)
    tv1 = b1[b1["time"] < TV_END].reset_index(drop=True)
    heartbeat.read = fake_read
    push.Relay.read = lambda self, *a, **kw: []
    cm.time.time = lambda: clock[0]
    live.LiveBot._read_hist = lambda self, sym, tf: (tv5 if tf == "5m" else tv1 if tf == "1m" else pd.DataFrame(columns=pcbars.COLS)) \
        if sym == "NQ" else pd.DataFrame(columns=pcbars.COLS)
    try:
        make_hb(clock[0] - clock[0] % 60)
        n0 = len(net.urls)
        err = None
        try:
            cm.run(out)
        except Exception as e:
            import traceback
            err = traceback.format_exc()[-800:]
        st = json.load(open(os.path.join(out, "state.json"), encoding="utf-8")) if os.path.exists(os.path.join(out, "state.json")) else {}
        hl = st.get("health") or {}
        check("cloud run on the PC's bars: no Yahoo / yfinance call, bars_src pc-ninjatrader, feed ok, last 5m bar 10:00 ET",
              err is None and not undo.calls and not any("yahoo" in u.lower() for u in net.urls[n0:])
              and st.get("bars_src") == "pc-ninjatrader" and not st.get("feed_wait") and hl.get("source") == "pc-ninjatrader"
              and hl.get("last_bar", "").endswith("10:00 ET") and os.path.exists(os.path.join(out, pcbars.STORE_5M)),
              f"err={err} yahoo={undo.calls} hl={ {k: hl.get(k) for k in ('source', 'last_bar', 'waiting', 'stale')} }")
        check("cloud run: the ledger / README / state keep working (state.json has the model state, README the PC-bars feed line)",
              st.get("model_state") is not None and "PC NinjaTrader bars" in open(os.path.join(out, "README.md"), encoding="utf-8").read())
        # the PC goes quiet: its newest bar stays at 10:05 while the clock moves on to 10:50
        clock[0] = NOW + 47 * 60
        hbs["hb"]["t"] = int(clock[0])                    # the heartbeat itself is fresh, its bars are not
        err = None
        try:
            cm.run(out)
        except Exception:
            import traceback
            err = traceback.format_exc()[-800:]
        st = json.load(open(os.path.join(out, "state.json"), encoding="utf-8"))
        readme = open(os.path.join(out, "README.md"), encoding="utf-8").read()
        pauses = st.get("feed_pauses") or []
        check("stale PC bars: 'waiting for NinjaTrader bars from the PC' in state + README, a pause opened, nothing armed, no Yahoo",
              err is None and pcbars.WAITING in str(st.get("feed_wait")) and pcbars.WAITING in readme and pauses
              and pauses[-1][1] is None and not st.get("armed") and not undo.calls,
              f"err={err} wait={st.get('feed_wait')} pauses={pauses}")
        led = {}
        t_in, t_out = pauses[-1][0] + 600, pauses[-1][0] - 7200
        resx = {"model": "lit", "trades": [{"entry_t": t, "exit_t": t + 600, "dir": 1, "pnl_r": 1.0, "pnl": 100.0, "exit_reason": "TARGET",
                                            "entry": 29000.0, "stop": 28950.0, "target": 29050.0, "risk_pts": 50.0, "qty": 4}
                                           for t in (t_out, t_in)]}
        cm.update_ledger(led, resx, NOW - 86400, None, os.path.join(tmp, "sig.json"), None, {}, pauses=pauses)
        check("no new paper entry inside a pause (the one before it is kept)", int(t_out) in led and int(t_in) not in led, sorted(led))
        check("pause bookkeeping: closes when the PC bars are fresh again",
              cm.update_pauses([[100, None]], {"ok": True}, 500) == [[100, 500]] and cm.in_pause(200, [[100, 500]])
              and not cm.in_pause(500, [[100, 500]]) and cm.update_pauses([], {"ok": False, "last_1m_t": 1000}, 5000) == [[1060, None]])
    finally:
        heartbeat.read, push.Relay.read, cm.time.time, live.LiveBot._read_hist = saved


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
