"""Cloud paper monitor: the live paper bot's decision loop as a scheduled job (GitHub Actions), so it runs with the PC off.

Each run does what LiveBot.poll_once does - stored history + fresh Yahoo bars, 20-day window, 1h HTF, ES partner,
live params - then writes a dashboard (README.md + chart.png + state.json) into --out, which the workflow publishes on
the repo's `dashboard` branch. Paper only: it never routes an order anywhere.

Optional phone alerts: set TG_TOKEN + TG_CHAT (Telegram) and/or DISCORD_WEBHOOK as repository secrets.

    python tools/cloud_monitor.py --out dash
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import equity_filter               # noqa: E402
from engine import heartbeat                   # noqa: E402
from engine import sizing                      # noqa: E402
from engine import lab_adapter                 # noqa: E402
from engine.data import from_frame             # noqa: E402
from engine.lab_adapter import live_model      # noqa: E402
from engine.live import LiveBot, market_open   # noqa: E402
from engine.model import Engine, merge_params  # noqa: E402

ET = ZoneInfo("America/New_York")
SYM, TF, SECS, WINDOW_DAYS = "NQ", "5m", 300, 20
START_BAL, TARGET, MLL_AMT, MLL_LOCK = 50000.0, 3000.0, 2000.0, 50100.0
KILLZONES = ((570, 690), (810, 930))
ALERT_TYPES = ("sweep", "signal", "entry", "exit")


def et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def tday(t):
    """Trading day: the session that opens 18:00 ET belongs to the next calendar day (same rule as the engine)."""
    return (et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def money(x):
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.2f}"


def send_alert(text):
    sent = []
    tok, chat = os.environ.get("TG_TOKEN", ""), os.environ.get("TG_CHAT", "")
    if tok and chat:
        try:
            body = json.dumps({"chat_id": chat, "text": text[:3900]}).encode()
            req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", body, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).read()
            sent.append("telegram")
        except Exception as e:
            print("telegram failed:", e.__class__.__name__)
    hook = os.environ.get("DISCORD_WEBHOOK", "")
    if hook:
        try:
            req = urllib.request.Request(hook, json.dumps({"content": text[:1900]}).encode(), {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).read()
            sent.append("discord")
        except Exception as e:
            print("discord failed:", e.__class__.__name__)
    return sent


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _lit_eval_odds():
    """MFFU 50K eval odds of LIT from its stored 2026 run (research/runs/lit_final.json), in eval_timing's fields."""
    try:
        with open(os.path.join(ROOT, "research", "runs", "lit_final.json"), encoding="utf-8") as fh:
            s = json.load(fh)["spans"]["2026"]
        return {"pass_2w": round(s["p10"] / 100, 3), "fail_2w": round(s["f10"] / 100, 3), "pass_1m": round(s["p20"] / 100, 3),
                "fail_1m": round(s["f20"] / 100, 3),
                "median_pass": s["pass_med"], "funded_wk": None,
                "reason": "no cold-streak filter: odds from the LIT 2026 backtest (tuned on Jan-Jun; Jul-Oct was weaker)"}
    except Exception:
        return {"pass_2w": None, "fail_2w": None, "pass_1m": None, "fail_1m": None, "median_pass": None, "funded_wk": None}


def run_model(lm, bot, df_all, now, store_1m=None):
    """One poll of a strategy on the merged bars: the engine on the 20-day window (as LiveBot.poll_once), LIT on the
    previous-month window with 1m bars (engine/lit_live.py), a lab module on the 20-day window."""
    df = df_all[df_all["time"] >= df_all["time"].max() - WINDOW_DAYS * 86400]
    if lm["model"] == "lit":
        from engine import lit as lit_mod
        from engine import lit_live
        P = {**lit_mod.DEFAULTS, **(lm.get("lit") or {})}
        try:                                   # VIX daily close (the LIT target band): data/VIX_1d.csv, refreshed from Yahoo
            from engine import news
            news.volatility()
        except Exception as e:
            print("VIX refresh failed:", e.__class__.__name__)
        df1 = None
        if P.get("tf") == "1m":
            keep = dict(bot.health)
            try:
                df1, _ = bot._merged(SYM, "1m", now, 60, period="5d", max_days=7)     # Yahoo caps 1m at 7 days
            except Exception as e:
                print("1m bars unavailable:", e.__class__.__name__)
            bot.health.clear(); bot.health.update(keep)
            # the 1m bars of the last 12 days are kept on the dashboard branch (bars_1m.csv), so a failed fetch or the 7-day
            # cap never takes a traded day's 1m bars away (that day would be re-simulated on 5m bars)
            if store_1m:
                try:
                    old = pd.read_csv(store_1m) if os.path.exists(store_1m) else None
                except Exception:
                    old = None
                parts = [x for x in (old, df1) if x is not None and len(x)]
                if parts:
                    df1 = pd.concat(parts).drop_duplicates("time", keep="last").sort_values("time")
                    df1 = df1[df1["time"] >= int(df1["time"].max()) - 12 * 86400].reset_index(drop=True)
                    df1[["time", "open", "high", "low", "close", "volume"]].to_csv(store_1m, index=False)
        return lit_live.run(df_all, P, one_min=df1, now=now, sym=SYM)
    if lm["model"].startswith("lab:"):
        es_df, _ = bot._merged("ES" if SYM == "NQ" else "NQ", TF, now, SECS)     # partner index (SMT)
        es_df = es_df[es_df["time"] >= int(df["time"].min())]
        return lab_adapter.run(lm["model"][4:], df, lm["params"], es_df)
    base = from_frame(SYM, TF, df)
    partner = bot._partner(SYM, TF, now, SECS, int(df["time"].min()))
    htf = bot._htf(SYM, now)
    return Engine(base, htf=htf, partner=partner, params=merge_params({**lm["params"], "live": True})).run().result()


def update_ledger(ledger, res, first_run, eqf_cfg, shadow_path, sizing_cfg, params):
    """Paper ledger: the model's trades that entered after this ledger started watching, sized as the PC bot sizes them."""
    for t in sorted(res["trades"], key=lambda x: x["entry_t"]):
        if t["entry_t"] >= first_run - SECS:
            prev = ledger.get(int(t["entry_t"]))
            if prev and "mult" in prev:
                mult, qty = prev["mult"], prev.get("qty", 0)
            else:
                cold = equity_filter.status(eqf_cfg, before_t=int(t["entry_t"]), path=shadow_path)["mult"]
                profit = sum(v["usd"] for k, v in ledger.items() if int(k) < int(t["entry_t"])) if ledger else None
                r = sizing.route_qty(int(t.get("qty") or 0), t, cold, sizing_cfg, params, profit)
                mult, qty = r["mult"], r["qty"]
            ledger[int(t["entry_t"])] = {"day": tday(t["entry_t"]), "entry": f"{et(t['entry_t']):%m-%d %H:%M}",
                                         "side": "LONG" if t["dir"] == 1 else "SHORT", "grade": t.get("grade"),
                                         "trigger": t.get("trigger"), "exit": t.get("exit_reason"),
                                         "exit_t": f"{et(t['exit_t']):%H:%M}" if t.get("exit_t") else None,
                                         "R": round(float(t["pnl_r"]), 2), "taken": mult > 0, "mult": mult,
                                         "usd": round(float(t["pnl"]) * mult, 2), "qty": qty}
    return ledger


def eval_track(ledger):
    """MFFU 50K eval tracker from a paper ledger (EOD trailing max loss, locks at $50,100)."""
    by_day = {}
    for v in ledger.values():
        by_day[v["day"]] = by_day.get(v["day"], 0.0) + v["usd"]
    bal, peak, mll = START_BAL, START_BAL, START_BAL - MLL_AMT
    for d in sorted(by_day):
        bal += by_day[d]
        peak = max(peak, bal)
        mll = min(max(mll, peak - MLL_AMT), MLL_LOCK)
    return {"balance": round(bal, 2), "profit": round(bal - START_BAL, 2), "to_target": round(START_BAL + TARGET - bal, 2),
            "trailing_mll": round(mll, 2), "cushion": round(bal - mll, 2)}


def run(out):
    global SYM
    lm = live_model()                    # live_model.json: same strategy and symbol as the PC paper bot
    SYM = lm["sym"]
    os.makedirs(out, exist_ok=True)
    now = int(time.time())
    st = load_state(os.path.join(out, "state.json"))
    first_run = int(st.get("first_run") or now)
    seen = set(tuple(k) for k in st.get("seen", []))
    ledger = {int(k): v for k, v in st.get("ledger", {}).items()}
    # the old Liquidity Engine keeps a paper ledger next to LIT (shadow, no alerts): live_model_engine.json
    sh_lm = lab_adapter.engine_model() if lm["model"] != "engine" else None
    sh_st = st.get("shadow") or {}
    prev_model = st.get("model") or "engine"          # state.json files from before LIT have no "model": the engine's
    if prev_model != lm["model"]:
        # strategy switch: the old ledger belongs to the old strategy -> it becomes the shadow ledger; the new one starts now
        if sh_lm is not None and prev_model == "engine" and not sh_st:
            sh_st = {"model": "engine", "first_run": first_run, "ledger": st.get("ledger", {}), "moved_at": now}
        ledger, first_run = {}, now
        print(f"strategy switch {prev_model} -> {lm['model']}: new paper ledger from now")

    bot = LiveBot()
    bot.cfg = {"sym": SYM, "tf": TF, "adapter": "paper", "data_source": "yahoo", "params": {}, "window_days": WINDOW_DAYS}
    df_all, drops = bot._merged(SYM, TF, now, SECS)
    if not len(df_all):
        raise SystemExit("no bars at all (history missing and Yahoo failed)")
    df = df_all[df_all["time"] >= df_all["time"].max() - WINDOW_DAYS * 86400]
    res = run_model(lm, bot, df_all, now, store_1m=os.path.join(out, "bars_1m.csv"))
    state = res["state"] or {}
    state.setdefault("model_label", lm.get("label") or lm["model"])

    # ---- feed health (same freshness rule as the live bot)
    last_bar = int(df["time"].max())
    age = now - (last_bar + SECS)
    mopen = market_open(now)
    stale = age > 2 * SECS + 60
    today = tday(now)
    tb = [int(t) for t in df["time"] if tday(t) == today]
    rth = [t for t in tb if 570 <= et(t).hour * 60 + et(t).minute < 960]
    gaps = [f"{et(a):%H:%M}-{et(b):%H:%M}" for a, b in zip(tb, tb[1:]) if b - a > SECS and mopen]
    health = {"fetch_ok": bool(bot.health.get("fetch_ok")), "last_bar": f"{et(last_bar):%a %H:%M} ET", "age_min": round(age / 60, 1),
              "stale": bool(stale and mopen), "market_open": bool(mopen), "bars_today": len(tb), "rth_bars_today": len(rth),
              "gaps_today": gaps[:10], "dropped": drops, "error": bot.health.get("last_error")}

    # ---- equity-curve filter (same rule as the PC bot): every finished signal goes into the signal ledger. The engine's
    # is shadow_ledger.json (its history since the cloud monitor began); another model keeps its own file.
    shadow_path = os.path.join(out, "shadow_ledger.json" if lm["model"] == "engine" else f"signals_{lm['model'].replace(':', '_')}.json")
    eqf_cfg = lm.get("equity_filter")
    if eqf_cfg:
        equity_filter.record(res["trades"], shadow_path)
    eqf_now = equity_filter.status(eqf_cfg, path=shadow_path)
    state["equity_filter"] = eqf_now
    state["eval_timing"] = equity_filter.eval_timing(eqf_now, equity_filter.sessions_since_flip(eqf_cfg, now, shadow_path))   # when to buy/reset the eval
    if lm["model"] == "lit":                      # the odds above are the old engine's; LIT's come from its own 2026 run
        state["eval_timing"] = {**state["eval_timing"], **_lit_eval_odds()}

    # ---- paper ledger: model trades that entered after the cloud monitor started watching
    sizing_cfg = lm.get("sizing")
    update_ledger(ledger, res, first_run, eqf_cfg, shadow_path, sizing_cfg, lm.get("params"))
    pos = state.get("position")

    # ---- shadow: the old strategy on the same bars, its own paper ledger and cold-streak history, no alerts
    shadow = None
    if sh_lm is not None:
        try:
            sres = run_model(sh_lm, bot, df_all, now)
            sstate = sres["state"] or {}
            s_path = os.path.join(out, "shadow_ledger.json")
            s_eqf = sh_lm.get("equity_filter")
            if s_eqf:
                equity_filter.record(sres["trades"], s_path)
            s_first = int(sh_st.get("first_run") or now)
            s_ledger = {int(k): v for k, v in (sh_st.get("ledger") or {}).items()}
            update_ledger(s_ledger, sres, s_first, s_eqf, s_path, sh_lm.get("sizing"), sh_lm.get("params"))
            shadow = {"model": sh_lm["model"], "label": sh_lm.get("label"), "first_run": s_first,
                      "ledger": {str(k): v for k, v in sorted(s_ledger.items())}, "eval": eval_track(s_ledger),
                      "model_state": sstate.get("model_state"), "position": sstate.get("position"),
                      "equity_filter": equity_filter.status(s_eqf, path=s_path),
                      "engine_trades": [{"day": tday(t["entry_t"]), "entry_t": int(t["entry_t"]), "dir": t["dir"],
                                         "R": round(float(t["pnl_r"]), 2), "exit": t.get("exit_reason"), "trigger": t.get("trigger"),
                                         "grade": t.get("grade"), "pnl": round(float(t["pnl"]), 2)} for t in sres["trades"][-10:]]}
            if sh_st.get("moved_at"):
                shadow["moved_at"] = sh_st["moved_at"]
        except Exception as e:                    # the shadow must never stop the live strategy's dashboard
            print("shadow engine failed:", e.__class__.__name__, e)
            shadow = {**sh_st, "error": f"{e.__class__.__name__}: {e}"} if sh_st else {"error": f"{e.__class__.__name__}: {e}"}

    # ---- alerts for events not seen before (only events from after the monitor started, like LiveBot._emit_events)
    new_alerts = []
    for ev in res["events"]:
        key = (int(ev["t"]), ev["type"], ev["text"])
        if ev["t"] < first_run - 3600 or key in seen:
            continue
        seen.add(key)
        if ev["type"] in ALERT_TYPES:
            note = ""
            m = equity_filter.status(eqf_cfg, before_t=int(ev["t"]), path=shadow_path)["mult"] \
                if ev["type"] == "entry" and eqf_cfg else 1.0
            if m <= 0:
                note = "\nNOT TAKEN - cold-streak filter (last 15 signals net negative), tracked on paper only"
            elif m < 1:
                note = f"\n{m:g}x SIZE - cold-streak filter (last 15 signals net negative)"
            if ev["type"] == "entry" and sizing_cfg and sizing_cfg.get("late_mult") is not None:
                note += "\n(late entries, where the 15m trend already turned, are traded at half size)"
            new_alerts.append(f"{SYM} {ev['type'].upper()} {et(ev['t']):%H:%M} ET\n{ev['text']}{note}")
    # eval timing flipped since the last run (cold streak <-> full size): the owner buys/resets the eval on GO
    prev_et = (st.get("eval_timing") or {}).get("verdict") if prev_model == lm["model"] else None   # no flip alert on a switch
    now_et = state["eval_timing"]
    if prev_et and prev_et != now_et["verdict"]:
        new_alerts.append(f"{SYM} EVAL TIMING: {now_et['verdict'].upper()}\n{now_et['reason']}\n"
                          + ("Good time to buy or reset the MFFU eval." if now_et["verdict"] == "go" else
                             "Hold off on a new eval until the filter is back at full size."))
    et_now = et(now)
    eod_sent = st.get("eod_sent")
    if et_now.weekday() < 5 and et_now.hour * 60 + et_now.minute >= 965 and eod_sent != today:
        eod_sent = today
        tt = [v for v in ledger.values() if v["day"] == today]
        lines = [f"{SYM} cloud paper - end of day {today}", f"Trades: {len(tt)} | P&L {money(sum(v['usd'] for v in tt))}"]
        lines += [f"{v['side']} {v['grade'] or ''} {v['trigger']} -> {v['exit']} {v['R']:+.2f}R {money(v['usd'])}" for v in tt]
        lines.append(f"Model now: {state.get('model_state')}")
        new_alerts.append("\n".join(lines))
    sent = []
    for a in new_alerts:
        sent = send_alert(a) or sent

    # ---- eval tracker from the cloud ledger (EOD trailing max loss, locks at $50,100)
    ev_track = eval_track(ledger)

    # ---- the always-on PC's heartbeat (engine/heartbeat.py): alert when it went silent in a session
    pc = heartbeat.read(cwd=ROOT, now=now)
    pc_alert_at = st.get("pc_alert_at")
    in_session = et_now.weekday() < 5 and 480 <= et_now.hour * 60 + et_now.minute <= 990
    if pc.get("present") and pc.get("silent") and in_session and now - float(pc_alert_at or 0) > 3600:
        pc_alert_at = now
        sent = send_alert(f"PC BOT SILENT: the {pc.get('host') or 'PC'} bot ({pc.get('adapter')}) last reported "
                          f"{pc['age_s'] // 60} min ago{' WITH AN OPEN POSITION' if pc.get('position') else ''}. "
                          "Check the PC / NinjaTrader. The cloud paper bot keeps running.") or sent
    write_chart(os.path.join(out, "chart.png"), df, state, res, today)
    write_readme(os.path.join(out, "README.md"), now, state, res, health, ledger, ev_track, today, sent, first_run, shadow, lm)
    new_state = {"first_run": first_run, "last_run": now, "runs": int(st.get("runs", 0)) + 1, "eod_sent": eod_sent,
                 "model": lm["model"],
                 "seen": [list(k) for k in sorted(seen)][-600:], "ledger": {str(k): v for k, v in sorted(ledger.items())},
                 "health": health, "eval": ev_track, "model_state": state.get("model_state"), "position": pos,
                 "strategy": lm.get("label"), "params": lm.get("lit") if lm["model"] == "lit" else lm.get("params"),
                 "equity_filter": state.get("equity_filter"),
                 "eval_timing": state.get("eval_timing"), "price": state.get("price"), "today": today,
                 "setups": state.get("setups") or {},
                 "events": [{"t": int(e["t"]), "type": e["type"], "text": e["text"]} for e in res["events"] if tday(e["t"]) == today][-25:],
                 "engine_trades": [{"day": tday(t["entry_t"]), "entry_t": int(t["entry_t"]), "dir": t["dir"], "R": round(float(t["pnl_r"]), 2),
                                    "exit": t.get("exit_reason"), "trigger": t.get("trigger"), "risk_pts": t.get("risk_pts"),
                                    "qty": t.get("qty"), "target_label": t.get("target_label")} for t in res["trades"][-10:]],
                 # for the web dashboard's Chart tab: the last ~2 sessions of 5m bars and the untaken pools around price
                 "bars": [[int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)] for r in df.tail(200).itertuples()],
                 "pools": _near_pools(state),
                 "pc": {k: pc.get(k) for k in ("present", "t", "age_s", "silent", "running", "adapter", "position", "model_state", "host", "reason")},
                 "pc_alert_at": pc_alert_at}
    if shadow is not None:
        new_state["shadow"] = shadow
    with open(os.path.join(out, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(new_state, fh, indent=1, default=str)
    print(f"ok: last bar {health['last_bar']}, model {state.get('model_state')}, ledger {len(ledger)}, alerts {len(new_alerts)} {sent}"
          + (f" | shadow {shadow.get('model_state')}, ledger {len(shadow.get('ledger') or {})}" if shadow else ""))


def _near_pools(state, n=6):
    """Nearest untaken liquidity pools above and below price (label, price, side H/L, strength)."""
    px = state.get("price")
    pools = [p for p in state.get("active_pools") or [] if px and abs(p.get("price", 0) - px) / px < 0.03]
    above = sorted([p for p in pools if p["price"] > px], key=lambda p: p["price"])[:n]
    below = sorted([p for p in pools if p["price"] < px], key=lambda p: -p["price"])[:n]
    return [{"label": p.get("label"), "price": p["price"], "side": p.get("side"), "strength": p.get("strength")} for p in above + below]


def write_chart(path, df, state, res, today):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        d = df[[tday(t) == today for t in df["time"]]]
        if len(d) < 12:                                   # weekend / before the open: show the last session
            last_day = tday(int(df["time"].max()))
            d = df[[tday(t) == last_day for t in df["time"]]]
        day_part = d[[480 <= et(t).hour * 60 + et(t).minute <= 975 for t in d["time"]]]     # 08:00-16:15 ET
        if len(day_part) >= 12:
            d = day_part
        if not len(d):
            return
        fig, ax = plt.subplots(figsize=(11, 5.5), dpi=110)
        fig.patch.set_facecolor("#0e1116")
        ax.set_facecolor("#0e1116")
        xs = list(range(len(d)))
        for x, (_, r) in zip(xs, d.iterrows()):
            up = r["close"] >= r["open"]
            col = "#26a69a" if up else "#ef5350"
            ax.vlines(x, r["low"], r["high"], color=col, linewidth=0.8)
            ax.add_patch(Rectangle((x - 0.35, min(r["open"], r["close"])), 0.7, max(abs(r["close"] - r["open"]), 0.25),
                                   color=col, linewidth=0))
        ts = [int(t) for t in d["time"]]
        for a, z in KILLZONES:                            # shade the killzones
            idx = [i for i, t in enumerate(ts) if a <= et(t).hour * 60 + et(t).minute < z]
            if idx:
                ax.axvspan(idx[0] - 0.5, idx[-1] + 0.5, color="#f5c542", alpha=0.07)
        lo, hi = float(d["low"].min()), float(d["high"].max())
        pad = (hi - lo) * 0.25 or 10
        ylo, yhi = lo - pad * 0.4, hi + pad * 0.4
        labelled = []
        for p in sorted(state.get("active_pools") or [], key=lambda p: -p.get("strength", 0)):
            px = float(p["price"])
            if ylo <= px <= yhi:
                col = "#ef5350" if p.get("side") == "H" else "#26a69a"
                ax.axhline(px, color=col, linewidth=0.7, alpha=0.6, linestyle="--")
                if all(abs(px - q) > (yhi - ylo) * 0.025 for q in labelled):     # no overlapping labels
                    labelled.append(px)
                    ax.text(xs[-1] + 1, px, f" {p.get('label', '')} {px:,.2f}", color=col, fontsize=7, va="center")
        for side, s in (state.get("setups") or {}).items():
            if s and s.get("ext") is not None:
                ax.axhline(float(s["ext"]), color="#bb86fc", linewidth=1.0)
                ax.text(0, float(s["ext"]), f" {side} armed, extreme {float(s['ext']):,.2f}", color="#bb86fc", fontsize=8, va="bottom")
        pos_of = {t: i for i, t in enumerate(ts)}
        for t in res["trades"]:
            for key, mk in (("entry_t", "^" if t["dir"] == 1 else "v"), ("exit_t", "x")):
                bt = int(t.get(key) or 0) // 300 * 300
                if bt in pos_of:
                    px = t["entry"] if key == "entry_t" else t.get("exit_price", t["entry"])
                    ax.scatter(pos_of[bt], px, marker=mk, s=70, color="#ffffff", zorder=5)
        step = max(1, len(ts) // 12)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels([f"{et(t):%H:%M}" for t in ts[::step]], color="#9aa4b2", fontsize=8)
        ax.tick_params(axis="y", colors="#9aa4b2", labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#2a2f3a")
        ax.set_xlim(-1, len(xs) + 18)
        ax.set_ylim(ylo, yhi)
        ax.set_title(f"{SYM} 5m - {tday(ts[-1])} (ET) - {state.get('model_state', '')}", color="#e6e6e6", fontsize=10)
        ax.grid(color="#1c212b", linewidth=0.5)
        fig.tight_layout()
        fig.savefig(path, facecolor=fig.get_facecolor())
        plt.close(fig)
    except Exception as e:                                # a chart problem must never stop the dashboard update
        print("chart failed:", e)


def usd_cell(v):
    if not v.get("taken", True):
        return "skipped (cold streak)"
    return money(v["usd"]) + (f" ({v.get('mult', 1.0):g}x size: {', '.join(v.get('reasons') or ['cold streak'])})" if v.get("mult", 1.0) < 1 else "")


def write_readme(path, now, state, res, health, ledger, ev_track, today, sent, first_run, shadow=None, lm=None):
    st_day = next((x for x in res["days"] if x["date"] == today), None) or (res["days"][-1] if res["days"] else {})
    setups = state.get("setups") or {}
    arm = []
    for side, s in setups.items():
        if s and s.get("limit") is not None:          # LIT: a working limit (or tapped, waiting for the 1m CISD)
            arm.append(f"{side.upper()} limit {float(s['limit']):,.2f} stop {float(s['stop']):,.2f} target {float(s['target']):,.2f} "
                       f"(placed {et(s['arm_t']):%H:%M}, until {et(s['expires_t']):%H:%M} ET, waiting for {s.get('waiting')}; "
                       f"swept {', '.join(s.get('pools') or [])})")
        elif s:
            arm.append(f"{side.upper()} armed {et(s['arm_t']):%H:%M} ET, extreme {float(s['ext']):,.2f} "
                       f"(pools: {', '.join(dict.fromkeys(s.get('pools') or []))})")
    sess = state.get("session") or {}
    sess_txt = "<br>".join(f"{k} {v[0]:,.2f}/{v[1]:,.2f}" for k, v in sess.items() if v and v[0] is not None)
    mtf = state.get("mtf") or {}
    bias = ", ".join(f"{x['tf']} {'bull' if x['bias'] > 0 else 'bear' if x['bias'] < 0 else 'flat'}" for x in mtf.get("tfs", []))
    price = state.get("price")
    pools = sorted(state.get("active_pools") or [], key=lambda p: abs(float(p["price"]) - float(price or 0)))[:8]
    feed = "OK" if health["fetch_ok"] and not health["stale"] else ("STALE" if health["stale"] else "Yahoo fetch failed, using stored history")
    L = [f"# {SYM} Liquidity Engine - cloud paper monitor",
         f"Updated **{et(now):%a %b %d %H:%M} ET** - runs every 30 min, 02:00-16:25 ET, on market days (GitHub Actions) - "
         f"**paper only, never places orders** - watching since {et(first_run):%b %d %H:%M} ET",
         "", "![NQ 5m today](chart.png)", "",
         "## Status", "| | |", "|---|---|",
         f"| Strategy | {state.get('model_label', 'engine')} |",
         f"| Cold-streak filter | {(state.get('equity_filter') or {}).get('reason', 'off')} |",
         f"| Eval timing | **{(state.get('eval_timing') or {}).get('verdict', '?').upper()}**: {(state.get('eval_timing') or {}).get('reason', '')} |",
         f"| Model | **{state.get('model_state', '?')}** |",
         f"| Price | {price:,.2f} (last bar {health['last_bar']}, {health['age_min']} min old) |" if price else "| Price | - |",
         f"| Setups | {'<br>'.join(arm) or 'none armed'} |",
         f"| Open position | {json.dumps(state.get('position')) if state.get('position') else 'flat'} |",
         *([f"| Structure | 1H {state.get('h1_trend')}, 15m {state.get('m15_trend')}; MTF {bias or '-'} |"]
           if state.get("h1_trend") is not None else []),
         f"| Sessions (H/L) | {sess_txt or '-'} |",
         *([f"| Regime | {st_day.get('regime', '-')} (10-day eff {st_day.get('er10', '-')}, 5-day {st_day.get('er5', '-')}) |"]
           if st_day.get("regime") else []),
         *([f"| LIT today | 18:00 open {lt['open18']:,.2f}, VIX {lt.get('vix')} -> one-day move {lt.get('vix_move')} pts "
            f"(target band {lt['open18'] - (lt.get('vix_move') or 0):,.2f} / {lt['open18'] + (lt.get('vix_move') or 0):,.2f}); "
            f"{'1m' if lt.get('one_min_day') else '5m (no full 1m feed today)'} execution; "
            f"{len(lt.get('signals_today') or [])} setups today |"] if (lt := state.get("lit")) and lt.get("open18") else []),
         f"| Feed | {feed}; {health['rth_bars_today']}/78 RTH bars today; gaps: {', '.join(health['gaps_today']) or 'none'} |",
         f"| Alerts | {', '.join(sent) if sent else ('phone alerts on' if os.environ.get('TG_TOKEN') or os.environ.get('DISCORD_WEBHOOK') else 'phone alerts off (add TG_TOKEN + TG_CHAT secrets)')} |",
         "", "## Nearest liquidity pools", "| Pool | Price | Distance |", "|---|---:|---:|"]
    L += [f"| {p.get('label')} ({'buy-side' if p.get('side') == 'H' else 'sell-side'}) | {float(p['price']):,.2f} | "
          f"{float(p['price']) - float(price or 0):+,.2f} |" for p in pools] or ["| - | - | - |"]
    tt = [v for v in ledger.values() if v["day"] == today]
    L += ["", f"## Today {today} (cloud paper)"]
    L += ["| Entry | Side | Grade | Trigger | Exit | R | $ |", "|---|---|---|---|---|---:|---:|"] + \
         [f"| {v['entry']} | {v['side']} | {v['grade']} | {v['trigger']} | {v['exit']} {v['exit_t'] or ''} | {v['R']:+.2f} | {usd_cell(v)} |" for v in tt] \
        if tt else ["No paper trades today."]
    L += ["", "## Eval tracker (MFFU 50K rules, cloud paper ledger)", "| Balance | Profit | To $3k target | Trailing max loss | Cushion |",
          "|---:|---:|---:|---:|---:|",
          f"| ${ev_track['balance']:,.2f} | {money(ev_track['profit'])} | ${ev_track['to_target']:,.2f} | ${ev_track['trailing_mll']:,.2f} | ${ev_track['cushion']:,.2f} |"]
    allv = sorted(ledger.values(), key=lambda v: v["entry"], reverse=True)[:20]
    L += ["", "## Cloud paper ledger (latest 20)"]
    L += ["| Entry | Side | Grade | Trigger | Exit | R | $ |", "|---|---|---|---|---|---:|---:|"] + \
         [f"| {v['entry']} | {v['side']} | {v['grade']} | {v['trigger']} | {v['exit']} | {v['R']:+.2f} | {usd_cell(v)} |" for v in allv] \
        if allv else ["No cloud paper trades yet."]
    evs = [e for e in res["events"] if tday(e["t"]) == today][-15:]
    L += ["", "## Today's events"] + ([f"- {et(e['t']):%H:%M} {e['type']}: {e['text']}" for e in evs] or ["- none yet"])
    ctx = res["trades"][-8:]
    L += ["", "## Model trades in the recent window (context, same rules)", "| Day | Entry | Side | Grade | Trigger | Exit | R | $ |",
          "|---|---|---|---|---|---|---:|---:|"]
    L += [f"| {tday(t['entry_t'])} | {et(t['entry_t']):%H:%M} | {'L' if t['dir'] == 1 else 'S'} | {t.get('grade')} | {t.get('trigger')} | "
          f"{t.get('exit_reason')} | {t['pnl_r']:+.2f} | {money(t['pnl'])} |" for t in ctx] or ["| - |"]
    if shadow:
        sl = sorted((shadow.get("ledger") or {}).values(), key=lambda v: v["entry"], reverse=True)
        se = shadow.get("eval") or {}
        L += ["", "## Old strategy (shadow, paper)",
              f"The previous strategy ({shadow.get('label') or shadow.get('model')}) runs on the same bars for comparison: "
              "own paper ledger, no alerts.", "| | |", "|---|---|",
              f"| Model | {shadow.get('model_state') or '-'} |",
              f"| Cold-streak filter | {(shadow.get('equity_filter') or {}).get('reason', 'off')} |",
              f"| Open position | {json.dumps(shadow.get('position')) if shadow.get('position') else 'flat'} |",
              f"| Paper ledger | {len(sl)} trades, {money(sum(v['usd'] for v in sl))} since {et(shadow.get('first_run') or now):%b %d} |",
              f"| Eval tracker | balance ${se.get('balance', 0):,.2f}, profit {money(se.get('profit', 0))}, cushion ${se.get('cushion', 0):,.2f} |"]
        if shadow.get("error"):
            L.append(f"| Error | {shadow['error']} |")
        lit_since = [v for k, v in (shadow.get("ledger") or {}).items() if int(k) >= first_run - SECS]
        L += ["", f"Since the new strategy started ({et(first_run):%b %d %H:%M} ET): new {money(sum(v['usd'] for v in ledger.values()))} "
              f"in {len(ledger)} trades vs old {money(sum(v['usd'] for v in lit_since))} in {len(lit_since)} trades.", "",
              "| Entry | Side | Grade | Trigger | Exit | R | $ |", "|---|---|---|---|---|---:|---:|"]
        L += [f"| {v['entry']} | {v['side']} | {v['grade']} | {v['trigger']} | {v['exit']} | {v['R']:+.2f} | {usd_cell(v)} |" for v in sl[:10]] \
            or ["| - | - | - | - | - | - | - |"]
    model = (lm or {}).get("model", "engine")
    L += ["", "---", ("Same LIT rules and settings as the PC paper bot (engine/lit.py via engine/lit_live.py, live_model.json)."
                      if model == "lit" else "Same engine and defaults as the PC paper bot (engine/model.py).")
          + " Live trading, if ever enabled, runs TradingView -> bridge, never through this job. Rules: STRATEGY.md on main."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dash")
    run(ap.parse_args().out)
