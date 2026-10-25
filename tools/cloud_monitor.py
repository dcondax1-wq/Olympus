"""Cloud paper monitor: the live paper bot's decision loop as a scheduled job (GitHub Actions), so it runs with the PC off.

Each run does what LiveBot.poll_once does - stored history + fresh bars, 20-day window, 1h HTF, ES partner,
live params - then writes a dashboard (README.md + chart.png + state.json) into --out, which the workflow publishes on
the repo's `dashboard` branch. Paper only: it never routes an order anywhere.

No Yahoo (live_model.json "no_yahoo", default on; owner 2026-10-19; engine/pcbars.py): the fresh bars are the PC's
NinjaTrader bars, pushed with its heartbeat (branch `heartbeat`: bars_1m.csv.gz, bars_5m.csv.gz), on top of the
TradingView exports (data/NQ_5m.csv, data/NQ_1m.csv) and the cloud's own store of what the PC sent (pc_bars_5m.csv,
bars_1m.csv on the dashboard branch). PC bars missing or stale: no new paper entries ("waiting for NinjaTrader bars from
the PC"); the rest of the run (ledger exits, push, brief, accounts) goes on. "no_yahoo": false brings Yahoo NQ=F back.

Phone notifications: Web Push to the Home Screen app (engine/push.py) for every fill and every outcome, the PC heartbeat
going silent and eval-timing flips; secrets LE_VAPID_PRIVATE + LE_PUSH_SUBS (docs/NOTIFICATIONS.md). Telegram / Discord
(TG_TOKEN + TG_CHAT, DISCORD_WEBHOOK) are off unless LE_ALERTS_CHAT=1 or live_model.json {"alerts": {"chat": true}}.

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
from engine import alerts_plus                 # noqa: E402
from engine import push                        # noqa: E402
from engine import sizing                      # noqa: E402
from engine import lab_adapter                 # noqa: E402
from engine import pcbars                      # noqa: E402
from engine.data import from_frame             # noqa: E402
from engine.lab_adapter import live_model      # noqa: E402
from engine.live import LiveBot, market_open   # noqa: E402
from engine.model import Engine, merge_params  # noqa: E402

ET = ZoneInfo("America/New_York")
SYM, TF, SECS, WINDOW_DAYS = "NQ", "5m", 300, 20
START_BAL, TARGET, MLL_AMT, MLL_LOCK = 50000.0, 3000.0, 2000.0, 50100.0
KILLZONES = ((570, 690), (810, 930))
ALERT_TYPES = ("sweep", "signal", "entry", "exit")
PUSH_SRC = "Cloud paper"
PUSH_MAX_AGE_S = 2 * 86400    # a fill / outcome older than this is never notified (a late first run, a restored state)
_LM = None                    # live_model.json of this run (send_alert's chat switch)
_LEARN = None                 # the learning loop's state (engine/lit_learn.py, <out>/lit_learning.json) for lit_qty
_LEARN_AT = {}                # entry_t -> lit_qty's "learn" block (the multiplier in force / would be), for the ledger row
_LIT_IN = {}                  # the live LIT run's 1m bars (run_model), reused by the lit_base ledger (same bars, no refetch)


def et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def tday(t):
    """Trading day: the session that opens 18:00 ET belongs to the next calendar day (same rule as the engine)."""
    return (et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def money(x):
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.2f}"


def chat_on(lm=None):
    """Telegram / Discord alerts (owner 2026-10-18: notifications come through the app; chat only when switched on)."""
    return os.environ.get("LE_ALERTS_CHAT", "") == "1" or bool(((lm or {}).get("alerts") or {}).get("chat"))


def send_alert(text, lm=None):
    sent = []
    if not chat_on(lm if lm is not None else _LM):
        return sent
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
    """MFFU 50K eval odds of LIT from its stored 2026 run (engine/lit_live.eval_odds: research/runs/lit_live.json)."""
    from engine import lit_live
    return lit_live.eval_odds(ROOT)


def run_model(lm, bot, df_all, now, store_1m=None, week_hist=None):
    """One poll of a strategy on the merged bars: the engine on the 20-day window (as LiveBot.poll_once), LIT on the
    previous-month window with 1m bars (engine/lit_live.py), a lab module on the 20-day window."""
    df = df_all[df_all["time"] >= df_all["time"].max() - WINDOW_DAYS * 86400]
    if lm["model"] == "lit":
        from engine import lit as lit_mod
        from engine import lit_live
        P = {**lit_mod.DEFAULTS, **(lm.get("lit") or {})}
        try:                                   # VIX daily close (the LIT target band): data/VIX_1d.csv, from CBOE (Yahoo with no_yahoo off)
            from engine import news
            news.volatility()
        except Exception as e:
            print("VIX refresh failed:", e.__class__.__name__)
        df1 = None
        if P.get("tf") == "1m":
            keep = dict(bot.health)
            try:
                df1, _ = bot._merged(SYM, "1m", now, 60, period="5d", max_days=7)     # PC NinjaTrader 1m (Yahoo: 7-day cap)
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
        es_df = None                           # ES 5m for the learning loop's ES features (engine/lit_learn.py)
        keep = dict(bot.health)
        try:
            es_df, _ = bot._merged("ES" if SYM == "NQ" else "NQ", TF, now, SECS)
        except Exception as e:
            print("ES bars unavailable (learning features):", e.__class__.__name__)
        bot.health.clear(); bot.health.update(keep)
        if es_df is not None and (not len(es_df) or int(es_df["time"].max()) + 1800 < int(df_all["time"].max())):
            es_df = None                       # no fresh ES (no Yahoo, the PC sends NQ only): the ES features are unknown
        _LIT_IN["df1"] = df1
        _LIT_IN["keep"] = {}                  # the Bot Brain (engine/brain.py) reads this run's market afterwards
        return lit_live.run(df_all, P, one_min=df1, now=now, sym=SYM, week_hist=week_hist, learn=True, es_df=es_df,
                            keep=_LIT_IN["keep"])
    if lm["model"].startswith("lab:"):
        es_df, _ = bot._merged("ES" if SYM == "NQ" else "NQ", TF, now, SECS)     # partner index (SMT)
        es_df = es_df[es_df["time"] >= int(df["time"].min())]
        return lab_adapter.run(lm["model"][4:], df, lm["params"], es_df)
    base = from_frame(SYM, TF, df)
    partner = bot._partner(SYM, TF, now, SECS, int(df["time"].min()))
    htf = bot._htf(SYM, now)
    return Engine(base, htf=htf, partner=partner, params=merge_params({**lm["params"], "live": True})).run().result()


def _watch_summary(out):
    """tools/lit_watch.py's record (<out>/watch.json): last watch, minutes used this month, Yahoo's 1m lag."""
    try:
        from tools.lit_watch import watch_summary
        p = os.path.join(out, "watch.json")
        return watch_summary(load_state(p)) if os.path.exists(p) else None
    except Exception as e:
        print("watch summary failed:", e.__class__.__name__, e)
        return None


def week_rows(ledger):
    """The LIT weekly stop's ledger rows (engine/lit.py week_stops): day, exit reason, exit time of every paper trade."""
    return [{"day": v["day"], "exit": v.get("exit"), "exit_t": v.get("exit_ts")} for v in ledger.values()]


def in_pause(t, pauses) -> bool:
    """Did entry time t fall in a stretch without the PC's NinjaTrader bars (state "feed_pauses": [[from, to|None], ...])?"""
    return any(int(a) <= int(t) and (b is None or int(t) < int(b)) for a, b in (pauses or []))


def update_pauses(pauses, fstat, now):
    """Open a pause when the PC bars stop (from the minute after the newest bar the cloud had), close it when they are
    fresh again. Keeps the last 30."""
    pauses = [list(p) for p in (pauses or [])]
    open_ = bool(pauses) and pauses[-1][1] is None
    if fstat is not None and not fstat.get("ok"):
        if not open_:
            last = fstat.get("last_1m_t")
            pauses.append([int(min(now, (last + 60) if last else now)), None])
    elif open_:
        pauses[-1][1] = int(now)
    return pauses[-30:]


def update_ledger(ledger, res, first_run, eqf_cfg, shadow_path, sizing_cfg, params, lit_sizing=None, pauses=None, scale_in=None):
    """Paper ledger: the model's trades that entered after this ledger started watching, sized as the PC bot sizes them.
    pauses (no Yahoo): a trade that would ENTER inside a stretch without the PC's NinjaTrader bars is not added (no new paper
    entries while waiting; the PC bot did not route it either: it blocks entries on a stale feed and never chases late ones).
    lit_sizing (LIT only): live_model.json "lit_sizing" -> engine/sizing.lit_qty (normal / eval / fast_eval / safe_eval /
    two_week; the room and the two_week eval state from this ledger's MFFU eval tracker at the entry, from
    lit_sizing.eval_start); the model's micros already carry the weekly stop. scale_in (live_model.json lit.scale_in): a
    trade with adds books them as the PC bot sizes them (lit_add_usd)."""
    for t in sorted(res["trades"], key=lambda x: x["entry_t"]):
        if t["entry_t"] >= first_run - SECS:
            prev = ledger.get(int(t["entry_t"]))
            if prev is None and pauses and in_pause(t["entry_t"], pauses):
                continue
            if prev and prev.get("exit_ts") and prev.get("exit") not in (None, "OPEN"):
                # a finished paper trade is the decision made on the bars available then (LIT report ch.27): a later re-run on
                # revised bars (Yahoo corrections, late 1m bars) never rewrites it; the difference is only noted
                new = {"exit": t.get("exit_reason"), "R": round(float(t["pnl_r"]), 2),
                       "exit_ts": int(t["exit_t"]) if t.get("exit_t") else None}
                if any(new[k] != prev.get(k) for k in new):
                    prev["revised_replay"] = new
                else:
                    prev.pop("revised_replay", None)
                continue
            reasons = None
            if prev and "mult" in prev:
                mult, qty = prev["mult"], prev.get("qty", 0)
                reasons = prev.get("reasons")
            else:
                mult, qty, reasons = paper_size(ledger, t, res.get("model"), eqf_cfg, shadow_path, sizing_cfg, params, lit_sizing)
            usd, add_q = round(float(t["pnl"]) * mult, 2), None
            if res.get("model") == "lit" and t.get("adds") and t.get("qty") and qty:
                usd, add_q = lit_add_usd(ledger, t, int(qty), lit_sizing, (scale_in or {}).get("f", 1.0))
            ledger[int(t["entry_t"])] = {"day": tday(t["entry_t"]), "entry": f"{et(t['entry_t']):%m-%d %H:%M}",
                                         "side": "LONG" if t["dir"] == 1 else "SHORT", "grade": t.get("grade"),
                                         "trigger": t.get("trigger"), "exit": t.get("exit_reason"),
                                         "exit_t": f"{et(t['exit_t']):%H:%M}" if t.get("exit_t") else None,
                                         "R": round(float(t["pnl_r"]), 2), "taken": mult > 0, "mult": mult,
                                         "usd": usd, "qty": qty, **({"add_qty": add_q} if add_q is not None else {}),
                                         "exit_ts": int(t["exit_t"]) if t.get("exit_t") else None,
                                         # prices for the app's Activity feed and the notifications
                                         **{k: (round(float(t[s]), 2) if t.get(s) is not None else None) for k, s in
                                            (("entry_px", "entry"), ("stop_px", "stop"), ("target_px", "target"),
                                             ("exit_px", "exit_price"), ("risk_pts", "risk_pts"))},
                                         **({"reasons": reasons} if reasons else {}),
                                         **({"learn": _learn_row(prev, t)} if _learn_row(prev, t) else {})}
    return ledger


def lit_add_usd(ledger, t, qty, lit_sizing=None, f=1.0, max_micros=40):
    """($ of a scale-in trade at the paper size, [micros of each add]) sized as the PC bot sizes the add (engine/live.py
    _add_qty): eval modes (two_week / eval / safe_eval) = engine/sizing.scale_in_qty at the paper size on this ledger's own
    eval state at the entry (room to the floor, today's closed P&L; one trade a day, so it is the state at the add too);
    normal = the model's add x paper micros / model micros (rounded down). The whole position at most max_micros.
    Remaining difference to the PC: the PC books the broker's real add fill price, the paper ledger the model's."""
    from engine import lit as _lit
    mode = str((lit_sizing or {}).get("mode") or "normal")
    adds = t.get("adds") or []
    cm = float(t.get("comm_rt", _lit.COMM))
    q0, qm = int(qty), int(t["qty"])
    if mode in ("two_week", "eval", "safe_eval"):
        start = (lit_sizing or {}).get("eval_start")
        before = {k: v for k, v in ledger.items() if int(k) < int(t["entry_t"])}
        state = {"room": eval_track(before, start)["cushion"],
                 "cum": float(eval_day_pnl(before, start).get(tday(t["entry_t"]), 0.0))}
        qa = sizing.scale_in_qty(q0, q0, float(t["risk_pts"]), [{"rk": float(a["rk"]), "prev_rk": list(a.get("prev_rk") or [])}
                                                                 for a in adds], f=f, state=state, max_micros=max_micros)
    else:
        qa, tot = [], q0
        for a in adds:
            n = max(0, min(int(int(a.get("qty") or 0) * q0 / qm + 1e-9), int(max_micros) - tot))
            qa.append(n)
            tot += n
    usd = q0 * (float(t["pts"]) * _lit.PV - cm) + sum(n * (float(a["pts"]) * _lit.PV - cm) for n, a in zip(qa, adds))
    return round(usd, 2), [int(n) for n in qa]


def _learn_row(prev, t):
    """The learning layer at the entry (kept from the first sizing of the trade): mode, applied / would-be multiplier, buckets."""
    if prev and prev.get("learn"):
        return prev["learn"]
    L = _LEARN_AT.get(int(t["entry_t"]))
    if not L or not L.get("mode"):
        return None
    return {k: L.get(k) for k in ("mode", "mult", "would", "skip", "would_skip", "buckets")}


def paper_size(ledger, t, model, eqf_cfg, shadow_path, sizing_cfg, params, lit_sizing=None):
    """(mult, micros, reasons) of one entry, sized as the PC bot sizes it (update_ledger, and the fill notification of a
    position that is still open)."""
    if model == "lit":
        ls = lit_sizing or {}
        start = ls.get("eval_start")
        before = {k: v for k, v in ledger.items() if int(k) < int(t["entry_t"])}
        mode = ls.get("mode")
        room = eval_track(before, start)["cushion"] if mode in ("safe_eval", "eval", "two_week") else None
        # every eval mode gets the eval state (2026-10-20): the pass / fail lock and the weekly loss stop (wk_loss_usd)
        state = lit_eval_state(before, start, tday(t["entry_t"])) if mode in ("two_week", "eval", "safe_eval", "fast_eval") else None
        r = sizing.lit_qty(int(t.get("qty") or 0), t, lit_sizing, room=room, state=state, learning=_LEARN)
        if r.get("learn"):
            _LEARN_AT[int(t["entry_t"])] = r["learn"]
        if r.get("fallback"):
            print(f"sizing {et(t['entry_t']):%m-%d %H:%M}: {r['fallback']}")
        return r["mult"], r["qty"], r["reasons"]
    cold = equity_filter.status(eqf_cfg, before_t=int(t["entry_t"]), path=shadow_path)["mult"]
    profit = sum(v["usd"] for k, v in ledger.items() if int(k) < int(t["entry_t"])) if ledger else None
    r = sizing.route_qty(int(t.get("qty") or 0), t, cold, sizing_cfg, params, profit)
    return r["mult"], r["qty"], None


def _armed_size(ledger, lm):
    """The paper ledger's own sizing for a "setup armed" estimate (as paper_size, without the learning record)."""
    def f(tr):
        from engine import lit as _lit
        ls = lm.get("lit_sizing") or {}
        start, mode = ls.get("eval_start"), ls.get("mode")
        room = eval_track(ledger, start)["cushion"] if mode in ("safe_eval", "eval", "two_week") else None
        est = lit_eval_state(ledger, start, tday(tr["entry_t"])) if mode in ("two_week", "eval", "safe_eval", "fast_eval") else None
        return sizing.lit_qty(int(_lit.qty_for(tr["risk_pts"])), tr, ls, room=room, state=est, learning=None)["qty"]
    return f


def alerts_plus_step(st, state, res, ledger, lm, pc, pc_outage, relay, relay_msgs, now, feed_ok=True, mopen=True):
    """engine/alerts_plus.py on the cloud: the app's levels and acks from the relay, "setup armed" / "expired" for the paper
    bot, the Surface-offline alert repeated until "Got it", the PC-vs-cloud rules check. Never raises."""
    out = {"notices": [], "prefs": {}, "prefs_state": st.get("push_prefs"), "crit": st.get("crit") or {},
           "setups_seen": st.get("setups_seen"), "rules": None, "rules_check": st.get("rules_check")}
    try:
        pst = alerts_plus.prefs_from(relay_msgs, st.get("push_prefs"))
        out["prefs_state"], out["prefs"] = pst, pst.get("prefs") or {}
        acks = alerts_plus.acks_from(relay_msgs)
        if lm["model"] == "lit":
            cis = (lm.get("lit") or {}).get("cisd1m") or 20
            out["setups_seen"], ns = alerts_plus.setup_step(st.get("setups_seen"), state, now, trades=res.get("trades"),
                                                            size_fn=_armed_size(ledger, lm), src="Cloud", cisd1m=cis,
                                                            enabled=bool(feed_ok and mopen))
            out["notices"] += ns
        active = []
        o = pc_outage or {}
        if o.get("since") and o.get("alerted_at") and not o.get("back_at") and push.pc_offline_window(now):
            p0 = push.pc_offline_payload(o["since"], now, (pc or {}).get("host"), bool((pc or {}).get("position")))
            active.append({"id": f"pc_offline:{int(o['since'])}", "kind": "pc_offline", "title": p0["title"], "body": p0["body"],
                           "sent_at": o["alerted_at"]})
        before = st.get("crit") or {}
        out["crit"], cn = alerts_plus.crit_step(before, active, acks, now, out["prefs"], src="Cloud")
        out["notices"] += cn
        if cn or alerts_plus.crit_open(before) != alerts_plus.crit_open(out["crit"]):
            relay.post({"le": "crit", "src": "cloud", "open": alerts_plus.crit_open(out["crit"]), "t": int(now)})
        out["rules"] = alerts_plus.model_rules(lm)
        fresh = bool((pc or {}).get("present")) and int((pc or {}).get("age_s") or 1e9) <= 30 * 60
        out["rules_check"], rn = alerts_plus.rules_step(st.get("rules_check"), (pc or {}).get("rules"), out["rules"], now, fresh)
        out["notices"] += rn
    except Exception as e:
        print("alerts plus failed:", e.__class__.__name__, e)
    return out


def _setup_line(res, entry_t, d, trade=None):
    """'Swept Asia low, PDL · target 18:00 open + VIX move · limit entry' for a fill notification."""
    swept, label, kind = (trade or {}).get("swept"), (trade or {}).get("target_label"), (trade or {}).get("entry_kind")
    if not swept:
        sig = [s for s in res.get("signals") or [] if int(s.get("t") or 0) <= int(entry_t) and s.get("dir") == d]
        if sig:
            try:
                from engine.lit_live import _sweep_names
                swept = _sweep_names(sig[-1].get("swept"))
            except Exception:
                swept = sig[-1].get("swept")
            label = label or sig[-1].get("target_label")
    parts = [f"Swept {', '.join(swept)}" if swept else "", f"target {label}" if label else "", f"{kind} entry" if kind else ""]
    return " · ".join(p for p in parts if p)


def _news(reasons):
    """Size reasons worth a line in a notification (the weekly stop's half size, a room cap), not the size mode's usual one."""
    return [r for r in reasons or [] if not str(r).lower().startswith(("eval size", "fast eval", "two week", "one winner"))]


def trade_notices(ledger, res, pos, lm, since, state=None, size=None):
    """Push payloads for every fill and every outcome since `since` (the Notifier sends each key once).
    size(t) -> (mult, micros, reasons) sizes an open position the way the ledger will."""
    model = lm.get("model", "engine")
    mname = "LIT" if model == "lit" else str(lm.get("label") or model).split(" (")[0]
    acct = push.account_label(lm, "paper")          # "Paper": the cloud bot never trades a real account
    out = []
    by_t = {int(t["entry_t"]): t for t in res.get("trades") or []}
    for ev in res.get("events") or []:
        if ev.get("type") != "entry" or int(ev["t"]) < since:
            continue
        et_ = int(ev["t"])
        t = by_t.get(et_)
        p = pos if pos and int(pos.get("entry_t") or 0) == et_ else None
        src = p or t
        if src is None:
            continue
        row = ledger.get(et_) or {}
        if row:
            mult, qty, reasons = row.get("mult", 1.0), row.get("qty"), row.get("reasons")
        elif size is not None:
            mult, qty, reasons = size({**src, "entry_t": et_})
        else:
            mult, qty, reasons = 1.0, src.get("qty"), None
        d = int(src.get("dir") or 1)
        note = []
        if mult is not None and mult <= 0:
            note.append("NOT TAKEN (cold-streak filter), tracked on paper only")
        if _news(reasons):
            note.append("Size: " + "; ".join(_news(reasons)))
        if t is not None and not p:
            note.append(f"Closed before this check ({t.get('exit_reason')}): the outcome follows")
        stop = src.get("stop0", src.get("stop"))
        risk_pts = src.get("risk_pts") if src.get("risk_pts") is not None else (abs(float(src["entry"]) - float(stop)) if src.get("entry") is not None and stop is not None else None)
        out.append(push.entry_payload(acct, "LONG" if d == 1 else "SHORT", qty, et_, src=PUSH_SRC, model=mname,
                                      entry=src.get("entry"), stop=stop, target=src.get("target"),
                                      risk_usd=round(float(qty or 0) * float(risk_pts or 0) * 2.0, 2) if risk_pts is not None else None,
                                      setup=_setup_line(res, et_, d, t), note="\n".join(note)))
    rules = (state or {}).get("lit_rules") or {}
    for k in sorted(ledger):
        v = ledger[k]
        if not v.get("exit_ts") or v.get("exit") in (None, "OPEN") or int(v["exit_ts"]) < since:
            continue
        bal = eval_track({j: w for j, w in ledger.items() if j <= k}, (lm.get("lit_sizing") or {}).get("eval_start") if model == "lit" else None)
        note = []
        if not v.get("taken", True):
            note.append("Not taken (cold-streak filter): paper only")
        if _news(v.get("reasons")):
            note.append("Size: " + "; ".join(_news(v["reasons"])))
        ws = rules.get("weekly_stop") or {}
        if v.get("exit") == "STOP" and ws.get("on") and float(ws.get("mult") or 1) < 1 and k == max(ledger):
            note.append(f"Weekly stop ON: {ws.get('stops')} stop-outs this week, {float(ws['mult']):g}x size for the rest of it")
        out.append(push.outcome_payload(acct, v.get("side"), v.get("exit"), v.get("usd"), k, v.get("exit_ts"), src=PUSH_SRC, model=mname,
                                        R=v.get("R"), qty=v.get("qty"), balance=bal["balance"], to_target=bal["to_target"],
                                        note="\n".join(note)))
    return out


def eval_day_pnl(ledger, start=None):
    """Paper P&L per trading day of the eval: ledger rows from `start` (yyyy-mm-dd, lit_sizing.eval_start) on."""
    by_day = {}
    for v in ledger.values():
        if start and v["day"] < str(start):
            continue
        by_day[v["day"]] = by_day.get(v["day"], 0.0) + v["usd"]
    try:                                     # the eval's P&L before eval_start (lit_sizing.eval_prior_pnl, e.g. -$100)
        prior = float((json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {})
                      .get("eval_prior_pnl") or 0.0) if start else 0.0
    except Exception:
        prior = 0.0
    if prior:
        by_day["0000-00-00"] = prior
    return by_day


def lit_eval_state(before, start, day):
    """The two_week sizer's eval state at an entry on trading day `day` (engine/sizing.eval_state): the closed paper P&L of
    the eval's earlier days, today's closed P&L so far (`before` = the ledger rows that entered before this entry) and the
    session number since lit_sizing.eval_start. None when the eval start is unknown (lit_qty then falls back to eval)."""
    if not start:
        return None
    pnl = eval_day_pnl(before, start)
    st = sizing.eval_state({d: v for d, v in pnl.items() if d < day}, pnl.get(day, 0.0),
                           session=max(1, sizing.eval_session(start, day) or 1), today=day)   # today: wk_pnl (wk_loss_usd)
    st["n_today"] = sum(1 for v in before.values() if v.get("day") == day)
    return st


def eval_life(ledger, lm, now):
    """State key eval_life (engine/eval_life.view) of the cloud paper eval: open / passed / failed, the minimum-days trade
    and the eval weekly loss stop (off / armed / tripped). Display only: the pass / fail / weekly-stop pushes come from
    the PC bot (the real account). None for the old engine or an unknown eval start."""
    if lm.get("model") != "lit":
        return None
    ls = lm.get("lit_sizing") or {}
    start = ls.get("eval_start")
    if not start or (ls.get("mode") or "") not in ("two_week", "eval", "safe_eval", "fast_eval"):
        return None
    from engine import eval_life as _el
    e = et(now)
    over = e.weekday() < 5 and e.hour * 60 + e.minute >= 16 * 60
    day = tday(now)
    return _el.view(eval_day_pnl(ledger, start), start, day, ls, session_over=over,
                    n_today=sum(1 for v in ledger.values() if v.get("day") == day))


def eval_clock(ledger, lm, now):
    """State key eval_2wk: the two-week eval clock (session x of 10 since lit_sizing.eval_start, reset recommended after
    session 10), engine/sizing.eval_clock. None for the old engine."""
    if lm.get("model") != "lit":
        return None
    start = (lm.get("lit_sizing") or {}).get("eval_start")
    e = et(now)
    over = e.weekday() < 5 and e.hour * 60 + e.minute >= 16 * 60           # after the 15:55 flat: today's session is done
    return sizing.eval_clock(eval_day_pnl(ledger, start), start, tday(now), session_over=over)


def eval_track(ledger, start=None):
    """MFFU 50K eval tracker from a paper ledger (EOD trailing max loss, locks at $50,100); rows from `start` on."""
    by_day = eval_day_pnl(ledger, start)
    bal, peak, mll = START_BAL, START_BAL, START_BAL - MLL_AMT
    for d in sorted(by_day):
        bal += by_day[d]
        peak = max(peak, bal)
        mll = min(max(mll, peak - MLL_AMT), MLL_LOCK)
    return {"balance": round(bal, 2), "profit": round(bal - START_BAL, 2), "to_target": round(START_BAL + TARGET - bal, 2),
            "trailing_mll": round(mll, 2), "cushion": round(bal - mll, 2)}


def learning_paths(out):
    """The cloud's learning files, kept on the dashboard branch: <out>/lit_journal.jsonl (append-only) and
    <out>/lit_learning.json; seeded from the repo's data/ copies (the 2026 backtest records, the replay's state) on the
    first run."""
    import shutil
    from engine import lit_learn
    jp, lp = os.path.join(out, "lit_journal.jsonl"), os.path.join(out, "lit_learning.json")
    for dst, src in ((jp, lit_learn.JOURNAL_PATH), (lp, lit_learn.LEARNING_PATH)):
        if not os.path.exists(dst) and os.path.exists(src):
            shutil.copyfile(src, dst)
    return jp, lp


def learning_step(out, ledger, res, now, today):
    """The learning loop's cloud part (engine/lit_learn.py): journal every finished paper trade once its session is over
    (the hindsight facts then cover the whole day), run the weekly review on Sunday or on the first run after it (or now
    with LE_LEARN_REVIEW=1, the workflow's "learn_review" input), and return the state.json "learning" block."""
    from engine import lit_learn
    jp, lp = learning_paths(out)
    L = lit_learn.load_learning(lp) or lit_learn.default_learning()
    by_t = {int(t["entry_t"]): t for t in res.get("trades") or []}
    have = {r.get("key") for r in lit_learn.load_journal(jp) if r.get("source") == "cloud"}
    et_now = et(now)
    new = []
    for k, v in sorted(ledger.items()):
        if v.get("exit") in (None, "OPEN") or not v.get("exit_ts"):
            continue
        over = v["day"] < today or (et_now.hour * 60 + et_now.minute >= 960)
        t = by_t.get(int(k))
        if not over or t is None:
            continue
        lr = t.get("learn") or {}
        rec = lit_learn.record(t, "cloud", f=lr.get("f"), post=t.get("post"), qty=v.get("qty"), pnl=v.get("usd"),
                               learn=v.get("learn"), logged_at=now)
        if rec["key"] not in have:
            new.append(rec)
    n_new = lit_learn.append_journal(new, jp)
    if n_new:
        print(f"learning: journaled {n_new} trade(s)")
    J = lit_learn.load_journal(jp)
    due = lit_learn.review_due(L, et_now.date())
    force = os.environ.get("LE_LEARN_REVIEW", "") == "1"
    if due or force:
        asof = due if due else et_now.date().isoformat()
        L, d = lit_learn.review(J, L, asof, source="cloud weekly" if due else "cloud manual")
        lit_learn.save_learning(L, lp)
        print(f"learning: review as of {asof}: {d['action']} - {d['reason'][:160]}")
    return lit_learn.summary(L, J, today)


def run(out):
    global SYM, _LM, _LEARN
    lm = live_model()                    # live_model.json: same strategy and symbol as the PC paper bot
    SYM = lm["sym"]
    _LM = lm
    os.makedirs(out, exist_ok=True)
    now = int(time.time())
    if lm["model"] == "lit":             # the learning loop's knobs for the paper ledger's sizing (observe mode: 1.0)
        try:
            from engine import lit_learn
            _LEARN = lit_learn.load_learning(learning_paths(out)[1])
        except Exception as e:
            print("learning state unavailable:", e.__class__.__name__, e)
            _LEARN = None
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
    # ---- the bars: no Yahoo -> the PC's NinjaTrader bars from its heartbeat (engine/pcbars.py)
    noy = pcbars.no_yahoo()
    pc = fstat = None
    pauses = st.get("feed_pauses") or []
    if noy:
        if st.get("bars_src") != "pc-ninjatrader":      # the 1m store was filled from Yahoo before: start it again from the PC
            for f in (pcbars.STORE_1M, pcbars.STORE_5M):
                try:
                    os.remove(os.path.join(out, f))
                except OSError:
                    pass
        pc = heartbeat.read(cwd=ROOT, now=now, files=pcbars.HB_FILES)
        feed = pcbars.CloudFeed(out, pc, now, sym=SYM)
        fstat = feed.status()
        bot.no_yahoo = True
        bot.cfg.update(data_source="pc-ninjatrader", no_yahoo=True)
        bot.fetch_recent = feed.recent
        pauses = update_pauses(pauses, fstat, now)
        print(f"bars: {fstat['text']} (1m {fstat['n_1m']}, 5m store {fstat['n_5m']}"
              + (f", newest 1m {et(fstat['last_1m_t']):%a %H:%M} ET" if fstat.get("last_1m_t") else "") + ")")
    else:
        bot.no_yahoo = False
    df_all, drops = bot._merged(SYM, TF, now, SECS)
    if not len(df_all):
        raise SystemExit("no bars at all (history missing and " + (pcbars.WAITING if noy else "Yahoo failed") + ")")
    df = df_all[df_all["time"] >= df_all["time"].max() - WINDOW_DAYS * 86400]
    res = run_model(lm, bot, df_all, now, store_1m=os.path.join(out, "bars_1m.csv"),
                    week_hist=week_rows(ledger) if lm["model"] == "lit" else None)
    state = res["state"] or {}
    state.setdefault("model_label", lm.get("label") or lm["model"])
    if lm["model"] == "lit":                 # armed / forming setup (tools/lit_watch.py keeps the job polling while it is set)
        try:
            from engine import lit as _lit
            from engine import lit_watch
            _P = {**_lit.DEFAULTS, **(lm.get("lit") or {})}
            _brew = [] if (state.get("position") or state.get("day_trades")) else lit_watch.brewing(lit_watch.market(df_all, _P, SYM), _P)
            state["armed"] = lit_watch.armed_line(state, _brew, _P.get("cisd1m") or 20)
            if fstat is not None and not fstat["ok"] and not state.get("position"):
                state["armed"] = None            # no PC bars: nothing new can enter, so the watcher has nothing to watch
        except Exception as e:
            print("armed line failed:", e.__class__.__name__, e)
            state["armed"] = None

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
              "gaps_today": gaps[:10], "dropped": drops, "error": bot.health.get("last_error"),
              "source": "pc-ninjatrader" if noy else "yahoo", "no_yahoo": noy}
    if fstat is not None:
        health.update(pc_bars=fstat, waiting=None if fstat["ok"] else fstat["text"], fetch_ok=bool(fstat["ok"]))

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
    update_ledger(ledger, res, first_run, eqf_cfg, shadow_path, sizing_cfg, lm.get("params"),
                  lit_sizing=lm.get("lit_sizing") if lm["model"] == "lit" else None, pauses=pauses if noy else None,
                  scale_in=(lm.get("lit") or {}).get("scale_in") if lm["model"] == "lit" else None)
    pos = state.get("position")
    learning = None
    if lm["model"] == "lit":                     # the learning loop (journal + Sunday review); never stops the dashboard
        try:
            learning = learning_step(out, ledger, res, now, today)
            if res.get("learn_error"):
                learning["error"] = res["learn_error"]
        except Exception as e:
            print("learning step failed:", e.__class__.__name__, e)
            learning = {"error": f"{e.__class__.__name__}: {e}"}

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
            update_ledger(s_ledger, sres, s_first, s_eqf, s_path, sh_lm.get("sizing"), sh_lm.get("params"),
                          pauses=pauses if noy else None)
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

    # ---- lit_base: LIT without the three upgrades (t_check, scale_in, be_off), same bars, own paper ledger, no alerts
    lit_base, upgrades_live = lit_base_step(lm, st, df_all, now, ledger, res, first_run, pauses if noy else None)

    # ---- second strategies (paper only, engine/second.py + second_model.json): EMA / MACD next to LIT on the same bars,
    # own frozen paper ledger, "PAPER" pushes of kind "second" (the app's on / silent / off); never stops the LIT run
    second_block = None
    try:
        second_block = second_step(st, df_all, _LIT_IN.get("df1") if lm["model"] == "lit" else None,
                                   res if lm["model"] == "lit" else None, now, pauses if noy else None)
    except Exception as e:
        print("second strategies failed:", e.__class__.__name__, e)
        second_block = {**(st.get("second") or {}), "error": f"{e.__class__.__name__}: {e}"}

    # ---- ATLAS v2 PAPER SHADOW (engine/atlas_v2.py, research/writeups/atlas-v2.md candidate 1b): the members' frozen paper
    # ledgers above + LIT's run on the same bars -> its own frozen paper ledger and 25K eval tracker (state "atlas_v2").
    # Never routed; never stops the LIT run; the live ATLAS (second_model.json account_b) is not read or changed here
    atlas_v2 = None
    try:
        from engine import atlas_v2 as _av2
        if lm["model"] == "lit" and second_block and not second_block.get("error") and _av2.enabled():
            atlas_v2 = _av2.step(st.get("atlas_v2"), _av2.members_rows(second_block), res, df_all, _LIT_IN.get("df1"), now)
    except Exception as e:
        print("atlas v2 shadow failed:", e.__class__.__name__, e)
        atlas_v2 = {**(st.get("atlas_v2") or {}), "error": f"{e.__class__.__name__}: {e}"} if st.get("atlas_v2") else None

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
            if ev["type"] == "entry" and lm["model"] == "lit":
                lr = ledger.get(int(ev["t"])) or {}
                mode = (lm.get("lit_sizing") or {}).get("mode") or "normal"
                if mode == "normal" and lr.get("reasons"):           # e.g. the weekly stop's half size
                    note += f"\n{lr.get('qty')} micros ({'; '.join(lr['reasons'])})"
                if mode != "normal":
                    note += f"\nsizing mode {mode}" + (f": {lr['qty']} micros ({'; '.join(lr.get('reasons') or [])})" if lr else "")
            new_alerts.append(f"{SYM} {'LIT ' if lm['model'] == 'lit' else ''}{ev['type'].upper()} {et(ev['t']):%H:%M} ET\n{ev['text']}{note}")
    # eval timing flipped since the last run (cold streak <-> full size): the owner buys/resets the eval on GO
    prev_et = (st.get("eval_timing") or {}).get("verdict") if prev_model == lm["model"] else None   # no flip alert on a switch
    now_et = state["eval_timing"]
    if prev_et and prev_et != now_et["verdict"]:
        new_alerts.append(f"{SYM} EVAL TIMING: {now_et['verdict'].upper()}\n{now_et['reason']}\n"
                          + ("Good time to buy or reset the MFFU eval." if now_et["verdict"] == "go" else
                             "Hold off on a new eval until the filter is back at full size."))
    et_now = et(now)
    eod_sent = st.get("eod_sent")
    if et_now.weekday() < 5 and et_now.hour * 60 + et_now.minute >= 960 and eod_sent != today:
        eod_sent = today
        tt = [v for v in ledger.values() if v["day"] == today]
        lines = [f"{SYM} {'LIT ' if lm['model'] == 'lit' else ''}cloud paper - end of day {today}", f"Trades: {len(tt)} | P&L {money(sum(v['usd'] for v in tt))}"]
        lines += [f"{v['side']} {v['grade'] or ''} {v['trigger']} -> {v['exit']} {v['R']:+.2f}R {money(v['usd'])}" for v in tt]
        lines.append(f"Model now: {state.get('model_state')}")
        new_alerts.append("\n".join(lines))
    sent = []
    for a in new_alerts:
        sent = send_alert(a) or sent

    # ---- eval tracker from the cloud ledger (EOD trailing max loss, locks at $50,100), from lit_sizing.eval_start (a new
    # purchase restarts it), and the two-week clock: session x of 10, reset recommended after session 10
    ev_start = (lm.get("lit_sizing") or {}).get("eval_start") if lm["model"] == "lit" else None
    ev_track = {**eval_track(ledger, ev_start), **({"start": ev_start} if ev_start else {})}
    state["eval_2wk"] = eval_clock(ledger, lm, now)
    try:
        state["eval_life"] = eval_life(ledger, lm, now)
    except Exception as e:
        state["eval_life"] = None
        print(f"eval lifecycle failed: {e.__class__.__name__}: {e}")

    # ---- the always-on PC's heartbeat (engine/heartbeat.py): alert when it went silent in a session
    if pc is None:
        pc = heartbeat.read(cwd=ROOT, now=now)
    pc_alert_at = st.get("pc_alert_at")
    other_notices = []
    # loud, once per outage (engine/push.pc_outage): heartbeat older than 30 min inside 01:30-16:00 ET on a weekday ->
    # "Surface offline since HH:MM ET" (key = the last check-in, so it is never repeated), and "back online" when it reports
    # again. Replaces the hourly "PC bot silent" repeat, which also needed the PC to have said it was running.
    pc_outage, outage_notices = push.pc_outage(st.get("pc_outage"), pc, now)
    for n in outage_notices:
        if n["key"].startswith("pc_offline:"):
            pc_alert_at = now
            sent = send_alert("SURFACE OFFLINE: " + n["body"]) or sent
        other_notices.append(n)
    pc_line = push.pc_checkin_line(pc, now)
    print(f"surface: {pc_line['text']}" + (f" -> {', '.join(n['key'] for n in outage_notices)}" if outage_notices else ""))
    # ---- is the PC bot trading the eval? (engine/accounts.verdict) one push per reason per hour, 01:50-15:55 ET weekdays,
    # whenever it is not green (a silent PC that said it was running already has the alert above)
    from engine import accounts as _accounts
    pc_verdict = _accounts.verdict(pc, now)
    v_due, pc_verdict_alerts = _accounts.alert_due(pc_verdict, now, st.get("pc_verdict_alerts"))
    if v_due and pc_verdict["code"] != "SILENT":          # silence has its own once-per-outage alert above
        other_notices.append(_accounts.verdict_notice(pc_verdict, pc, now))
    # a failed / rolled-back PC auto-update, a refused real-account auto-resume (same keys as the PC's own pushes)
    other_notices += _accounts.auto_notices(pc.get("health") if pc.get("present") else None, now)
    if prev_et and prev_et != now_et["verdict"]:
        other_notices.append(push.text_payload("Cloud", "timing", f"Eval timing: {now_et['verdict'].upper()}",
                                               f"{now_et['reason']} " + ("Good time to buy or reset the MFFU eval." if now_et["verdict"] == "go"
                                                                         else "Hold off on a new eval until the filter is back at full size."),
                                               key=f"timing:{now_et['verdict']}:{now}", t=now))
    if os.environ.get("LE_PUSH_TEST", "") == "1":             # Actions -> cloud-monitor -> Run workflow -> "Send a test notification"
        other_notices.append(push.text_payload("Cloud", "test", "Test notification",
                                               "Notifications from the cloud paper bot work. You get one for every fill and every outcome.",
                                               key=f"test:{now}", t=now))

    # ---- phone app notifications (Web Push, engine/push.py): entry + outcome of every trade once each, de-duplicated by key
    # across runs (state.json "pushed") and with the PC (relay "sent" markers); nothing older than 2 days. Subscriptions
    # arrive through the relay (the app posts them when notifications are allowed) and live in state.json "push_subs".
    push_since = int(st.get("push_since") or now)
    key_file = os.environ.get("LE_VAPID_KEY_FILE")
    if key_file and not os.environ.get("LE_VAPID_PRIVATE"):
        try:
            if push.ensure_key_file(key_file)["new"]:
                print("push: made a new notification key (kept in the Actions cache; phones subscribe again on their next open)")
        except Exception as e:
            print("push: key file unavailable:", e.__class__.__name__)
    relay = push.Relay()
    relay_msgs = relay.read()
    pub_now = push.config()["public"]
    push_subs = push.merge_relay_subs(st.get("push_subs") or [], relay_msgs, pub_now, now=now)
    pcfg = push.config(subs_extra=[r["sub"] for r in push_subs])
    notifier = push.Notifier(keys=st.get("pushed") or [], cfg=pcfg, relay=relay, src="cloud")
    pc_sent = relay.sent_keys(relay_msgs)
    candidates = trade_notices(ledger, res, pos, lm, max(push_since - 60, now - PUSH_MAX_AGE_S, first_run - SECS), state,
                               size=lambda t: paper_size(ledger, t, lm["model"], eqf_cfg, shadow_path, sizing_cfg, lm.get("params"),
                                                         lm.get("lit_sizing") if lm["model"] == "lit" else None))
    notices = list(st.get("notices") or [])
    push_res = []
    for n in sorted(candidates, key=lambda x: (x["t"], x["kind"] != "fill")) + other_notices:
        if notifier.seen(n):
            continue
        # entry / outcome are pushed, and "Surface offline" / "back online" (the PC may be trading a real eval overnight); eval-timing
        # notices stay in the app (LE_PUSH_EXTRA=1 pushes them too)
        r = notifier.notify(n, push_it=n["kind"] in ("fill", "outcome", "test", "pc") or push.extra_on(), other_sent=pc_sent)
        push_res.append(r)
        notices.append({**{k: n.get(k) for k in ("t", "kind", "src", "account", "key", "title", "body", "url", "side", "R", "usd", "exit",
                                                 "qty", "entry", "stop", "target", "risk_usd", "setup", "balance", "to_target", "note")},
                        "sent": int(r.get("sent") or 0), **({"by": "PC"} if r.get("by") else {}), "at": now})
    plus = alerts_plus_step(st, state, res, ledger, lm, pc, pc_outage, relay, relay_msgs, now,
                            feed_ok=fstat is None or bool(fstat["ok"]), mopen=market_open(now))
    for n in plus["notices"]:
        if notifier.seen(n):
            continue
        q = alerts_plus.apply_level(n, plus["prefs"])
        if q is None:                              # level "off" in the app: recorded, not pushed
            notifier.mark(n)
            r = {"sent": 0, "skipped": "off"}
        else:
            r = notifier.notify(q, push_it=True, other_sent=pc_sent)
            if r.get("sent") and n["kind"] == "armed":
                relay.post({"le": "sent", "key": n["key"], "src": "cloud", "t": now})   # the PC skips the same setup notice
        push_res.append(r)
        notices.append({**{k: n.get(k) for k in ("t", "kind", "src", "key", "title", "body", "url", "side", "entry", "stop", "target",
                                                 "qty", "risk_usd", "setup")}, "sent": int(r.get("sent") or 0), "at": now})
    for n in second_notices(second_block, max(push_since - 60, now - PUSH_MAX_AGE_S)):   # PAPER entries / exits, kind "second"
        if notifier.seen(n):
            continue
        q = alerts_plus.apply_level(n, plus["prefs"])
        if q is None:
            notifier.mark(n)
            r = {"sent": 0, "skipped": "off"}
        else:
            r = notifier.notify(q, push_it=True, other_sent=pc_sent)
        push_res.append(r)
        notices.append({**{k: n.get(k) for k in ("t", "kind", "src", "key", "title", "body", "url", "side", "entry", "stop", "target",
                                                 "qty", "usd", "exit", "setup")}, "sent": int(r.get("sent") or 0), "at": now})
    if atlas_v2 and not atlas_v2.get("error"):    # ATLAS v2 PAPER shadow: kind "second", sent only with second_model.json atlas_v2.push true
        try:
            from engine import atlas_v2 as _av2
            av2_push = _av2.push_on()
            for n in _av2.notices(atlas_v2, max(push_since - 60, now - PUSH_MAX_AGE_S), money):
                if notifier.seen(n):
                    continue
                q = alerts_plus.apply_level(n, plus["prefs"]) if av2_push else None
                if q is None:                          # shadow pushes off (default) or the app's "second" level off: recorded only
                    notifier.mark(n)
                    r = {"sent": 0, "skipped": "off"}
                else:
                    r = notifier.notify(q, push_it=True, other_sent=pc_sent)
                push_res.append(r)
                notices.append({**{k: n.get(k) for k in ("t", "kind", "src", "key", "title", "body", "url", "side", "entry", "stop", "target",
                                                         "qty", "usd", "exit", "setup")}, "sent": int(r.get("sent") or 0), "at": now})
        except Exception as e:                     # never fails the run
            print("atlas v2 notices failed:", e.__class__.__name__, e)
    notices = sorted(notices, key=lambda x: (x.get("t") or 0, x.get("at") or 0))[-80:]
    gone = sorted({g for r in push_res for g in r.get("gone") or []})
    if gone:                                       # expired / made for an old key: the app re-subscribes on its next open
        push_subs = [r for r in push_subs if r["id"] not in set(gone)]
    push_errs = [e for r in push_res for e in r.get("errors") or []]
    # the PC bot's copy of the key: sealed to the PC's own public key from its heartbeat (only the PC can open it)
    push_pc = st.get("push_pc") or None
    if pc.get("push_pk") and pcfg["private"]:
        if not push_pc or push_pc.get("pk") != pc["push_pk"] or push_pc.get("pub") != pcfg["public"]:
            try:
                push_pc = {"pk": pc["push_pk"], "pub": pcfg["public"], "box": push.seal(pcfg["private"].encode(), pc["push_pk"]), "t": now}
            except Exception as e:
                print("push: could not seal the key for the PC:", e.__class__.__name__)
    push_state = push.status(push.config(subs_extra=[r["sub"] for r in push_subs]))
    push_state.update({"sent_this_run": sum(int(r.get("sent") or 0) for r in push_res), "new": len(push_res),
                       "gone": gone if push_res else ((st.get("push") or {}).get("gone") or []), "errors": push_errs[:5],
                       "last_sent_at": now if any(r.get("sent") for r in push_res) else (st.get("push") or {}).get("last_sent_at"),
                       "relay": relay.public(), "relay_ok": relay.error is None, "relay_msgs": len(relay_msgs),
                       "pc_linked": bool(push_pc and pc.get("push_pk") == push_pc.get("pk")), "chat": chat_on(lm)})
    print(f"push: {push_state['devices']} device(s), key from {push_state['source'] or 'nowhere'}, relay {'ok' if relay.error is None else relay.error}"
          + (f", {len(push_res)} new notice(s), sent {push_state['sent_this_run']}" if push_res else "")
          + (f", expired {len(gone)}" if gone else "") + (f", errors {push_errs[:3]}" if push_errs else ""))
    write_chart(os.path.join(out, "chart.png"), df, state, res, today)
    write_readme(os.path.join(out, "README.md"), now, state, res, health, ledger, ev_track, today, sent, first_run, shadow, lm,
                 push_state=push_state, pc_health=pc.get("health") if pc.get("present") else None,
                 pc_ops=pc.get("ops") if pc.get("present") else None,
                 pc_remote=pc.get("remote") if pc.get("present") else None, upgrades_live=upgrades_live, pc_line=pc_line,
                 second=second_block)
    new_state = {"first_run": first_run, "last_run": now, "runs": int(st.get("runs", 0)) + 1, "eod_sent": eod_sent,
                 "model": lm["model"],
                 "seen": [list(k) for k in sorted(seen)][-600:], "ledger": {str(k): v for k, v in sorted(ledger.items())},
                 "lit_rules": state.get("lit_rules"), "lit_sizing": (lm.get("lit_sizing") or {}).get("mode") if lm["model"] == "lit" else None,
                 "health": health, "eval": ev_track, "eval_2wk": state.get("eval_2wk"), "eval_life": state.get("eval_life"), "model_state": state.get("model_state"), "position": pos,
                 "strategy": lm.get("label"), "params": lm.get("lit") if lm["model"] == "lit" else lm.get("params"),
                 "equity_filter": state.get("equity_filter"),
                 "eval_timing": state.get("eval_timing"), "price": state.get("price"), "today": today,
                 "setups": state.get("setups") or {},
                 # the phone line of an armed / forming LIT setup and the fast-entry watcher's record (tools/lit_watch.py)
                 "armed": state.get("armed"), "watch": _watch_summary(out),
                 "events": [{"t": int(e["t"]), "type": e["type"], "text": e["text"]} for e in res["events"] if tday(e["t"]) == today][-25:],
                 "engine_trades": [{"day": tday(t["entry_t"]), "entry_t": int(t["entry_t"]), "dir": t["dir"], "R": round(float(t["pnl_r"]), 2),
                                    "exit": t.get("exit_reason"), "trigger": t.get("trigger"), "risk_pts": t.get("risk_pts"),
                                    "qty": t.get("qty"), "target_label": t.get("target_label")} for t in res["trades"][-10:]],
                 # for the web dashboard's Chart tab: the last ~2 sessions of 5m bars and the untaken pools around price
                 "bars": [[int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)] for r in df.tail(200).itertuples()],
                 "pools": _near_pools(state),
                 # the last ~6 hours of 1m bars (bars_1m.csv) for the live trade chart (tools/web_public/live_panel.js)
                 "bars1": _bars_1m_tail(out),
                 # LIT panels (tools/web_public/litkit.js): the day context (18:00 open, VIX band, today's signals), the session
                 # boxes' highs / lows and every untaken LIT level (the Levels board marks a level taken when it leaves this list)
                 "lit": state.get("lit") if lm["model"] == "lit" else None,
                 "session": state.get("session") if lm["model"] == "lit" else None,
                 "levels": [{k: p.get(k) for k in ("label", "price", "side", "strength", "kind")} for p in state.get("active_pools") or []][:60]
                 if lm["model"] == "lit" else None,
                 "pc": {k: pc.get(k) for k in ("present", "t", "age_s", "silent", "running", "adapter", "position", "model_state", "host",
                                               "reason", "model", "push_pk", "acct", "health", "every_s", "exec", "ops", "remote", "live_pub",
                                               "brain", "second", "ai", "launch")},  # the PC bot's Bot Brain (engine/brain.py compact), second strategies (paper)
                 # is the PC bot really trading the eval (engine/accounts.verdict on the heartbeat's "health" block)
                 "pc_verdict": pc_verdict, "pc_verdict_alerts": pc_verdict_alerts,
                 "pc_alert_at": pc_alert_at,
                 # the Surface-offline tracker (engine/push.pc_outage) and the README / app line (push.pc_checkin_line)
                 "pc_outage": pc_outage, "pc_checkin": pc_line,
                 # no Yahoo: where the bars came from, the stretches without PC bars (no new paper entries in them)
                 "bars_src": "pc-ninjatrader" if noy else "yahoo", "feed_pauses": pauses if noy else [],
                 "feed_wait": (None if fstat["ok"] else fstat["text"]) if fstat is not None else None,
                 # phone app notifications: the keys already sent (de-dup), when they started, the public status (never the
                 # private key or an endpoint) and the last 80 notices for the app's Activity feed
                 "push_since": push_since, "pushed": notifier.keys()[-600:], "push": push_state, "notices": notices,
                 "push_subs": push_subs, "push_pc": push_pc,
                 # engine/alerts_plus.py: the app's on / silent / off levels, the repeating critical alerts (Surface offline),
                 # the LIT setups seen (armed / expired pushes), this run's rules fingerprint and the PC-vs-cloud check
                 "push_prefs": plus["prefs_state"], "crit": plus["crit"], "crit_open": alerts_plus.crit_open(plus["crit"]),
                 "setups_seen": plus["setups_seen"], "rules": plus["rules"], "rules_check": plus["rules_check"],
                 # the learning loop (engine/lit_learn.py): mode, knobs, last review, decisions, this month's loss causes
                 "learning": learning}
    if shadow is not None:
        new_state["shadow"] = shadow
    if lit_base is not None:
        new_state["lit_base"], new_state["upgrades_live"] = lit_base, upgrades_live
    if second_block is not None:
        new_state["second"] = second_block
        if (second_block.get("strategies") or {}).get("lit_asia"):     # LIT + Asia slot paper shadow: its own state key too
            new_state["lit_asia"] = second_block["strategies"]["lit_asia"]
    if atlas_v2 is not None or st.get("atlas_v2"):   # ATLAS v2 PAPER shadow: its own state key (kept when a run skipped it)
        new_state["atlas_v2"] = atlas_v2 if atlas_v2 is not None else st["atlas_v2"]
    from engine import uptime as _uptime        # status page: 30-day uptime per part + incidents -> state "uptime" (never raises)
    _uptime.cloud_hook(new_state, st, pc, now)
    try:                    # LIT day analyst (engine/lit_brief.py): morning briefing, intraday log, recap -> state "brief" + README
        from engine import lit_brief
        lit_brief.cloud_hook(out, new_state, st, res, df_all, now, lm)
    except Exception as e:  # never fails the run; no notifications
        print("brief failed:", e.__class__.__name__, e)
    try:                    # Bot Brain (engine/brain.py, read-only): the cloud paper bot's thoughts (the phone shows the PC's first)
        if lm["model"] == "lit" and _LIT_IN.get("keep"):
            from engine import brain
            ls = lm.get("lit_sizing") or {}
            day0 = tday(now)
            led = new_state.get("ledger") or {}
            bctx = {"lit_sizing": ls, "eval_clock": new_state.get("eval_2wk"), "eval_life": new_state.get("eval_life"),
                    "eval_state": lit_eval_state({k: v for k, v in led.items()}, ls.get("eval_start"), day0),
                    "news": brain._news(str(et(now).date()))}
            new_state["brain"] = brain.compact(brain.build(res, lm.get("lit") or {}, now, keep=_LIT_IN["keep"], ctx=bctx, mode="cloud"))
    except Exception as e:  # never fails the run
        print("brain failed:", e.__class__.__name__, e)
    # ---- learn from every trade (tools/recap.py, read-only): a recap card PNG per finished trade (paper ledger + the PC's
    # routed trades), the morning brief as one image, the Sunday weekly review -> <out>/recaps/ + state "recaps" / "weekly";
    # their notices (recap / brief / weekly) go out through the same notifier (de-duplicated, nothing older than 2 days)
    try:
        from tools import recap
        try:
            with open(os.path.join(ROOT, "data", "news", "hub.json"), encoding="utf-8") as fh:
                hub = json.load(fh)
        except Exception:
            hub = None
        rres = recap.cloud_hook(out, new_state, st, df_all, _LIT_IN.get("df1"), lm, now, hub=hub)
        for n in rres.get("notices") or []:
            if notifier.seen(n):
                continue
            r = notifier.notify(n, push_it=now - int(n.get("t") or 0) <= PUSH_MAX_AGE_S, other_sent=pc_sent)
            new_state["notices"].append({**{k: n.get(k) for k in ("t", "kind", "src", "account", "key", "title", "body", "url", "image",
                                                                  "side", "R", "usd", "exit")},
                                         "sent": int(r.get("sent") or 0), "at": now})
        new_state["notices"] = sorted(new_state["notices"], key=lambda x: (x.get("t") or 0, x.get("at") or 0))[-80:]
        new_state["pushed"] = notifier.keys()[-600:]
    except Exception as e:  # never fails the run
        print("recap failed:", e.__class__.__name__, e)
    # ---- trade pictures (engine/trade_chart.py, read-only): a chart PNG of every new paper trade of each strategy (LIT, the
    # ATLAS members, the stop-hunt candidates, LIT + Asia) at its entry, re-drawn at its exit -> <out>/charts/<key>/<id>.png +
    # charts/index.json (newest 60 per strategy, restored every run); at most 10 a run / ~50 s, nothing new = nothing drawn
    try:
        from engine import trade_chart
        new_state["charts"] = trade_chart.cloud_hook(out, new_state, df_all, _LIT_IN.get("df1") if lm["model"] == "lit" else None,
                                                     keep=_LIT_IN.get("keep") if lm["model"] == "lit" else None, now=now)
        if new_state["charts"].get("made"):
            print(f"charts: {len(new_state['charts']['made'])} drawn in {new_state['charts'].get('secs')} s")
    except Exception as e:  # never fails the run
        print("charts failed:", e.__class__.__name__, e)
    with open(os.path.join(out, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(new_state, fh, indent=1, default=str)
    print(f"ok: last bar {health['last_bar']}, model {state.get('model_state')}, ledger {len(ledger)}, alerts {len(new_alerts)} {sent}"
          + (f" | shadow {shadow.get('model_state')}, ledger {len(shadow.get('ledger') or {})}" if shadow else ""))


def second_step(st, df_all, df1, res, now, pauses=None):
    """Second strategies (paper only): engine/second.run on the LIT run's bars (5m history + the 1m bars), LIT's trades of
    the window for the "with LIT" view, then the frozen paper ledger (engine/second.ledger_update). None when
    second_model.json has nothing on and nothing was ever recorded."""
    from engine import second
    cfg = second.load_cfg()
    if not any(s.get("on", True) for s in cfg["strategies"].values()) and not st.get("second"):
        return None
    r = second.run(df_all, one_min=df1, now=now, cfg=cfg, lit=second.lit_windows(res))
    return second.ledger_update(st.get("second"), r, now, pauses, in_pause)


def second_notices(block, since):
    """Push payloads (kind "second", marked PAPER) for each new paper entry and exit of the second strategies."""
    out = []
    for key, s in ((block or {}).get("strategies") or {}).items():
        if s.get("route"):
            continue                 # routed on the PC account: the PC sends its LIVE pushes (no PAPER duplicate)
        nm = s.get("short") or key
        pre = "ATLAS PAPER" if key in ("ema_lon_vix", "macd_sweep", "sr_nyreclaim") else "PAPER"     # ATLAS = the 25K strategy (EMA + MACD + S/R)
        for v in (s.get("ledger") or {}).values():
            et_ = int(v.get("entry_t") or 0)
            side = v.get("side") or ("LONG" if (v.get("dir") or 0) > 0 else "SHORT")
            lit = v.get("lit") or {}
            extra = "" if lit.get("taken", True) else f" On LIT's account it would be skipped ({lit.get('why')})."
            if et_ >= since:
                p = push.text_payload("Cloud", "second", f"{pre} {nm} {side}",
                                      f"Paper entry {v.get('qty')} MNQ at {float(v.get('entry') or 0):,.2f}, stop {float(v.get('stop') or 0):,.2f}, "
                                      f"target {float(v.get('target') or 0):,.2f}. Not traded.{extra}",
                                      key=f"second:{key}:fill:{et_}", t=et_, url="#/second")
                out.append({**p, "side": side, "entry": v.get("entry"), "stop": v.get("stop"), "target": v.get("target"),
                            "qty": v.get("qty"), "setup": s.get("label")})
            xt = v.get("exit_t")
            if xt and v.get("exit_kind") not in (None, "OPEN") and int(xt) >= since:
                p = push.text_payload("Cloud", "second", f"{pre} {nm} {side} {v.get('exit_kind')}",
                                      f"{money(float(v.get('usd') or 0))} on paper ({float(v.get('r') or 0):+.2f}R). Not traded.",
                                      key=f"second:{key}:out:{et_}", t=int(xt), url="#/second")
                out.append({**p, "side": side, "usd": v.get("usd"), "exit": v.get("exit_kind"), "setup": s.get("label")})
    return sorted(out, key=lambda n: n["t"])


def lit_base_step(lm, st, df_all, now, ledger, res, first_run, pauses=None):
    """(lit_base, upgrades_live): LIT without t_check / scale_in / be_off on the live run's bars (tools/upgrade_shadow.py),
    sized like the live ledger (lit_sizing on its own eval state), no alerts. (None, None) when the live model is not LIT or
    none of the three is on. Never raises: an error is reported in both blocks."""
    from tools import upgrade_shadow as us
    if lm.get("model") != "lit":
        return None, None
    on = us.upgrades_on(lm.get("lit"))
    if not on:
        return None, None
    b_st = st.get("lit_base") or {}
    try:
        from engine import lit as lit_mod
        from engine import lit_live
        P = us.base_params({**lit_mod.DEFAULTS, **(lm.get("lit") or {})})
        since = int(b_st.get("since") or now)
        # first run: the live ledger's finished rows (both start from the same eval balance); then its own ledger
        b_ledger = {int(k): v for k, v in (b_st.get("ledger") or {}).items()} if b_st.get("since") else us.seed(ledger)
        bres = lit_live.run(df_all, P, one_min=_LIT_IN.get("df1"), now=now, sym=SYM, week_hist=week_rows(b_ledger))
        bres["model"] = "lit"
        update_ledger(b_ledger, bres, first_run, None, None, None, None, lit_sizing=lm.get("lit_sizing"), pauses=pauses)
        bst = bres.get("state") or {}
        cmp_ = us.compare(ledger, b_ledger, since, on, live_trades=res.get("trades"),
                          scale_in_live=any(t.get("adds") for t in res.get("trades") or []))
        start = (lm.get("lit_sizing") or {}).get("eval_start")
        cmp_["eval_live"], cmp_["eval_base"] = eval_track(ledger, start), eval_track(b_ledger, start)
        base = {"since": since, "upgrades_off": on, "model_state": bst.get("model_state"), "position": bst.get("position"),
                "ledger": {str(k): v for k, v in sorted(b_ledger.items())}, "eval": cmp_["eval_base"]}
        print(f"lit_base: {cmp_['trades_base']} trades {money(cmp_['usd_base'])} vs live {cmp_['trades_live']} "
              f"{money(cmp_['usd_live'])} since {cmp_['since_et']} (upgrades {money(cmp_['delta'])})")
        return base, cmp_
    except Exception as e:                        # the comparison must never stop the live strategy's dashboard
        print("lit_base failed:", e.__class__.__name__, e)
        err = f"{e.__class__.__name__}: {e}"
        return {**b_st, "error": err}, {"on": on, "error": err}


def _bars_1m_tail(out, n=360):
    """The newest n 1m bars of <out>/bars_1m.csv as [[t, o, h, l, c], ...]; [] when there is none. Never raises."""
    try:
        p = os.path.join(out, "bars_1m.csv")
        if not os.path.exists(p):
            return []
        b = pd.read_csv(p).tail(n)
        return [[int(r.time), round(float(r.open), 2), round(float(r.high), 2), round(float(r.low), 2), round(float(r.close), 2)]
                for r in b.itertuples()]
    except Exception as e:
        print("1m bars for the chart unavailable:", e.__class__.__name__)
        return []


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


def _accounts_auto_text(hl):
    try:
        from engine import accounts
        return accounts.auto_text(hl)
    except Exception as e:
        return f"unknown ({e.__class__.__name__})"


def _ops_cell(o):
    """README row "PC checks": the owner's PC helpers (engine/ops_checks.hb_fields, in the heartbeat's "ops" block)."""
    try:
        parts = []
        if o.get("checks_t"):
            parts.append(f"{int(o.get('bad') or 0)} red, {int(o.get('warn') or 0)} yellow ({et(o['checks_t']):%a %H:%M} ET)")
            if o.get("first_fix"):
                parts.append(f"fix: {o['first_fix']}")
        else:
            parts.append("no health check run yet (HEALTH_CHECK.bat / the ops task)")
        parts.append(f"backup {et(o['backup_t']):%a %H:%M} ET" if o.get("backup_t") else "no backup yet")
        if o.get("disk_free_gb") is not None:
            parts.append(f"disk {o['disk_free_gb']:.0f} GB free")
        return "; ".join(parts)
    except Exception as e:
        return f"unknown ({e.__class__.__name__})"


def _push_cell(p):
    p = p or {}
    if not p.get("configured"):
        return "no notification key yet (the workflow makes one on its next run)"
    if not p.get("devices"):
        return "on, no phone yet: open the app from the Home Screen and tap Allow"
    s = f"on: {p['devices']} phone(s), entry + outcome of every trade"
    if p.get("sent_this_run"):
        s += f"; sent {p['sent_this_run']} this run"
    if p.get("pc_linked"):
        s += "; PC bot linked"
    if p.get("relay_ok") is False:
        s += "; relay unreachable this run"
    if p.get("errors"):
        s += f"; errors: {'; '.join(p['errors'][:2])}"
    return s


def usd_cell(v):
    if not v.get("taken", True):
        return "skipped (learned skip)" if any("learned skip" in x for x in v.get("reasons") or []) else "skipped (cold streak)"
    if v.get("mult", 1.0) >= 1 and v.get("reasons"):         # LIT: the weekly stop is inside the model's micros
        return money(v["usd"]) + f" ({v.get('qty')} micros: {', '.join(v['reasons'])})"
    return money(v["usd"]) + (f" ({v.get('mult', 1.0):g}x size: {', '.join(v.get('reasons') or ['cold streak'])})" if v.get("mult", 1.0) < 1 else "")


def write_readme(path, now, state, res, health, ledger, ev_track, today, sent, first_run, shadow=None, lm=None, push_state=None,
                 pc_health=None, pc_ops=None, pc_remote=None, upgrades_live=None, pc_line=None, second=None):
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
    if health.get("waiting"):
        feed = "**WAITING** - " + str(health["waiting"]) + " (no new paper entries)"
    else:
        feed = ("OK" if health["fetch_ok"] and not health["stale"] else ("STALE" if health["stale"] else "Yahoo fetch failed, using stored history")) \
            + (" (PC NinjaTrader bars, no Yahoo)" if health.get("no_yahoo") else "")
    L = [f"# {SYM} {'LIT' if (lm or {}).get('model') == 'lit' else 'Liquidity Engine'} - cloud paper monitor",   # the strategy's name (LIT since 2026-10-18)
         f"Updated **{et(now):%a %b %d %H:%M} ET** - runs every 30 min, 02:00-16:25 ET, on market days (GitHub Actions) - "
         f"**paper only, never places orders** - watching since {et(first_run):%b %d %H:%M} ET",
         "", "![NQ 5m today](chart.png)", "",
         "## Status", "| | |", "|---|---|",
         *([f"| Surface | {pc_line['text']} |"] if isinstance(pc_line, dict) else []),
         f"| Strategy | {state.get('model_label', 'engine')} |",
         *([f"| Cold-streak filter | {(state.get('equity_filter') or {}).get('reason', 'off')} |"] if (lm or {}).get("model") != "lit" else
           [f"| Weekly stop | {((state.get('lit_rules') or {}).get('weekly_stop') or {}).get('text') or 'off'} |",
            f"| Monday rule | {((state.get('lit_rules') or {}).get('monday') or {}).get('text') or ('on (applies on Mondays)' if ((state.get('lit_rules') or {}).get('monday') or {}).get('on') else 'off')} |",
            f"| Sizing mode | {((lm or {}).get('lit_sizing') or {}).get('mode') or 'normal'} |",
            *([f"| Eval clock | {'**RESET RECOMMENDED** - ' if ck.get('reset') else ''}{ck.get('text')} (eval start {ck.get('start') or '?'}) |"]
              if (ck := state.get("eval_2wk")) else []),
            *([f"| Eval loss stop | {(el.get('wk_stop') or {}).get('text') or 'off'} ({el.get('trading')}) |"]
              if (el := state.get("eval_life")) else [])]),
         f"| Eval timing | **{(state.get('eval_timing') or {}).get('verdict', '?').upper()}**: {(state.get('eval_timing') or {}).get('reason', '')} |",
         f"| Model | **{state.get('model_state', '?')}** |",
         f"| Price | {price:,.2f} (last bar {health['last_bar']}, {health['age_min']} min old) |" if price else "| Price | - |",
         *([f"| Armed setup | **{state['armed']['text']}** |"] if state.get("armed") else []),
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
         *([f"| PC bot version | {_accounts_auto_text(pc_health)} |"] if isinstance(pc_health, dict) else []),
         *([f"| PC checks | {_ops_cell(pc_ops)} |"] if isinstance(pc_ops, dict) and pc_ops else []),
         *([f"| Remote control | {(pc_remote.get('last') or 'on, no command yet') if pc_remote.get('on') else 'off (LE_REMOTE=1)'}"
            f"{' · a stop waits for flat' if pc_remote.get('pending_stop') else ''}"
            f"{(' · ' + str(pc_remote['error'])[:80]) if pc_remote.get('error') else ''} |"] if isinstance(pc_remote, dict) else []),
         f"| Notifications | {_push_cell(push_state)} |",
         f"| Telegram / Discord | {', '.join(sent) if sent else ('on' if chat_on(lm) and (os.environ.get('TG_TOKEN') or os.environ.get('DISCORD_WEBHOOK')) else 'off (the app notifies; LE_ALERTS_CHAT=1 turns chat alerts back on)')} |",
         "", "## Nearest liquidity pools", "| Pool | Price | Distance |", "|---|---:|---:|"]
    L += [f"| {p.get('label')} ({'buy-side' if p.get('side') == 'H' else 'sell-side'}) | {float(p['price']):,.2f} | "
          f"{float(p['price']) - float(price or 0):+,.2f} |" for p in pools] or ["| - | - | - |"]
    tt = [v for v in ledger.values() if v["day"] == today]
    L += ["", f"## Today {today} (cloud paper)"]
    L += ["| Entry | Side | Grade | Trigger | Exit | R | $ |", "|---|---|---|---|---|---:|---:|"] + \
         [f"| {v['entry']} | {v['side']} | {v['grade']} | {v['trigger']} | {v['exit']} {v['exit_t'] or ''} | {v['R']:+.2f} | {usd_cell(v)} |" for v in tt] \
        if tt else ["No paper trades today."]
    L += ["", f"## Eval tracker (MFFU 50K rules, cloud paper ledger{', since ' + ev_track['start'] if ev_track.get('start') else ''})",
          "| Balance | Profit | To $3k target | Trailing max loss | Cushion |",
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
        L += ["", "## Old strategy (shadow, paper) - Archive: previous strategy (Liquidity Engine, Oct 17)",
              f"The previous strategy ({shadow.get('label') or shadow.get('model')}) runs on the same bars for comparison: "
              "own paper ledger, no alerts. It is archived, not deleted: research/archive/engine-2026-10-17/README.md "
              "(rules, numbers, files, how to switch back).", "| | |", "|---|---|",
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
    if upgrades_live:                         # the three LIT upgrades vs LIT without them (tools/upgrade_shadow.py)
        from tools import upgrade_shadow
        L += upgrade_shadow.readme_rows(upgrades_live)
    if second is not None:                    # second strategies, paper only (engine/second.py)
        from engine import second as _second
        L += _second.readme_lines(second, money)
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
