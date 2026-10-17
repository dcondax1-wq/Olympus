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

    bot = LiveBot()
    bot.cfg = {"sym": SYM, "tf": TF, "adapter": "paper", "data_source": "yahoo", "params": {}, "window_days": WINDOW_DAYS}
    df, drops = bot._merged(SYM, TF, now, SECS)
    if not len(df):
        raise SystemExit("no bars at all (history missing and Yahoo failed)")
    df = df[df["time"] >= df["time"].max() - WINDOW_DAYS * 86400]
    if lm["model"].startswith("lab:"):
        es_df, _ = bot._merged("ES" if SYM == "NQ" else "NQ", TF, now, SECS)     # partner index (SMT)
        es_df = es_df[es_df["time"] >= int(df["time"].min())]
        res = lab_adapter.run(lm["model"][4:], df, lm["params"], es_df)
    else:
        base = from_frame(SYM, TF, df)
        partner = bot._partner(SYM, TF, now, SECS, int(df["time"].min()))
        htf = bot._htf(SYM, now)
        res = Engine(base, htf=htf, partner=partner, params=merge_params({**lm["params"], "live": True})).run().result()
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

    # ---- equity-curve filter (same rule as the PC bot): every finished signal goes into the shadow ledger
    shadow_path = os.path.join(out, "shadow_ledger.json")
    eqf_cfg = lm.get("equity_filter")
    if eqf_cfg:
        equity_filter.record(res["trades"], shadow_path)
    eqf_now = equity_filter.status(eqf_cfg, path=shadow_path)
    state["equity_filter"] = eqf_now
    state["eval_timing"] = equity_filter.eval_timing(eqf_now)   # buy/reset the eval at full size, not in a cold streak

    # ---- paper ledger: engine trades that entered after the cloud monitor started watching
    sizing_cfg = lm.get("sizing")
    for t in sorted(res["trades"], key=lambda x: x["entry_t"]):
        if t["entry_t"] >= first_run - SECS:
            prev = ledger.get(int(t["entry_t"]))
            if prev and "mult" in prev:
                mult, qty = prev["mult"], prev.get("qty", 0)
            else:
                cold = equity_filter.status(eqf_cfg, before_t=int(t["entry_t"]), path=shadow_path)["mult"]
                profit = sum(v["usd"] for k, v in ledger.items() if int(k) < int(t["entry_t"])) if ledger else None
                r = sizing.route_qty(int(t.get("qty") or 0), t, cold, sizing_cfg, lm.get("params"), profit)
                mult, qty = r["mult"], r["qty"]
            ledger[int(t["entry_t"])] = {"day": tday(t["entry_t"]), "entry": f"{et(t['entry_t']):%m-%d %H:%M}",
                                         "side": "LONG" if t["dir"] == 1 else "SHORT", "grade": t.get("grade"),
                                         "trigger": t.get("trigger"), "exit": t.get("exit_reason"),
                                         "exit_t": f"{et(t['exit_t']):%H:%M}" if t.get("exit_t") else None,
                                         "R": round(float(t["pnl_r"]), 2), "taken": mult > 0, "mult": mult,
                                         "usd": round(float(t["pnl"]) * mult, 2), "qty": qty}
    pos = state.get("position")

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
    by_day = {}
    for v in ledger.values():
        by_day[v["day"]] = by_day.get(v["day"], 0.0) + v["usd"]
    bal, peak, mll = START_BAL, START_BAL, START_BAL - MLL_AMT
    for d in sorted(by_day):
        bal += by_day[d]
        peak = max(peak, bal)
        mll = min(max(mll, peak - MLL_AMT), MLL_LOCK)
    ev_track = {"balance": round(bal, 2), "profit": round(bal - START_BAL, 2), "to_target": round(START_BAL + TARGET - bal, 2),
                "trailing_mll": round(mll, 2), "cushion": round(bal - mll, 2)}

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
    write_readme(os.path.join(out, "README.md"), now, state, res, health, ledger, ev_track, today, sent, first_run)
    new_state = {"first_run": first_run, "last_run": now, "runs": int(st.get("runs", 0)) + 1, "eod_sent": eod_sent,
                 "seen": [list(k) for k in sorted(seen)][-600:], "ledger": {str(k): v for k, v in sorted(ledger.items())},
                 "health": health, "eval": ev_track, "model_state": state.get("model_state"), "position": pos,
                 "strategy": lm.get("label"), "params": lm.get("params"), "equity_filter": state.get("equity_filter"),
                 "price": state.get("price"), "today": today,
                 "events": [{"t": int(e["t"]), "type": e["type"], "text": e["text"]} for e in res["events"] if tday(e["t"]) == today][-25:],
                 "engine_trades": [{"day": tday(t["entry_t"]), "entry_t": int(t["entry_t"]), "dir": t["dir"], "R": round(float(t["pnl_r"]), 2),
                                    "exit": t.get("exit_reason"), "trigger": t.get("trigger"), "risk_pts": t.get("risk_pts"),
                                    "qty": t.get("qty"), "target_label": t.get("target_label")} for t in res["trades"][-10:]],
                 # for the web dashboard's Chart tab: the last ~2 sessions of 5m bars and the untaken pools around price
                 "bars": [[int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)] for r in df.tail(200).itertuples()],
                 "pools": _near_pools(state),
                 "pc": {k: pc.get(k) for k in ("present", "t", "age_s", "silent", "running", "adapter", "position", "model_state", "host", "reason")},
                 "pc_alert_at": pc_alert_at}
    with open(os.path.join(out, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(new_state, fh, indent=1, default=str)
    print(f"ok: last bar {health['last_bar']}, model {state.get('model_state')}, ledger {len(ledger)}, alerts {len(new_alerts)} {sent}")


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


def write_readme(path, now, state, res, health, ledger, ev_track, today, sent, first_run):
    st_day = next((x for x in res["days"] if x["date"] == today), None) or (res["days"][-1] if res["days"] else {})
    setups = state.get("setups") or {}
    arm = []
    for side, s in setups.items():
        if s:
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
         f"Updated **{et(now):%a %b %d %H:%M} ET** - runs every 15 min on market days (GitHub Actions) - "
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
         f"| Structure | 1H {state.get('h1_trend')}, 15m {state.get('m15_trend')}; MTF {bias or '-'} |",
         f"| Sessions (H/L) | {sess_txt or '-'} |",
         f"| Regime | {st_day.get('regime', '-')} (10-day eff {st_day.get('er10', '-')}, 5-day {st_day.get('er5', '-')}) |",
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
    L += ["", "## Engine trades in the 20-day window (context, same rules)", "| Day | Entry | Side | Grade | Trigger | Exit | R | $ |",
          "|---|---|---|---|---|---|---:|---:|"]
    L += [f"| {tday(t['entry_t'])} | {et(t['entry_t']):%H:%M} | {'L' if t['dir'] == 1 else 'S'} | {t.get('grade')} | {t.get('trigger')} | "
          f"{t.get('exit_reason')} | {t['pnl_r']:+.2f} | {money(t['pnl'])} |" for t in ctx] or ["| - |"]
    L += ["", "---", "Same engine and defaults as the PC paper bot (engine/model.py). Live trading, if ever enabled, runs "
          "TradingView -> bridge, never through this job. Five-year research: see research/FIVE_YEAR_REPORT.md on main."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dash")
    run(ap.parse_args().out)
