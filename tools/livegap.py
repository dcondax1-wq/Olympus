"""LIVE vs BACKTEST money audit (owner's #1, 2026-11-24, day-livegap). READ ONLY RESEARCH: never trades, routes, sizes or edits
live code / live_model*.json. Writes research/livegap/LIVEGAP.json; the write-up is research/writeups/livegap-2026-11-24.md.

For each live account since it started: the backtest TWIN on the PC's own bars (data/NQ_1m.csv + NQ_5m.csv: TradingView NQ1!
to Oct 16, the PC's NinjaTrader bars after; futures only) lined up trade by trade against what reached the account
(tools/web_public/trading/trades.json live rows = the PC's data-pipe ledger rows; data/pc_days/<day>/ when pulled; the owner's
typed balances on the board / accounts.json). Every difference gets ONE cause:
  MISSED   the twin traded, the account did not (PC off / silent / not armed / refused / update stuck: with the evidence)
  SLIPPED  both traded: entry / exit price difference in $ at the live size
  SIZE     both traded: the live micros differ from the twin's eval-path micros ($ = the twin R x the micros difference)
  EXTRA    the account moved with no twin trade (unexplained balance moves)
  RULE     a twin rule the live bot did not follow (a bug)
  MARKET   not a gap: the twin itself lost / made this; live = twin
Twins: LIT = engine/lit.run_x with the live params (tools/lit_rev_exit.LIVE = live_model.json "lit"), eval-path size =
engine/sizing.two_week_qty on the live two_week config per account (the order the sessions came); ATLAS = engine/second.run
(the 3 live members) with R x the account's median live $ risk (account_b's own sizing is not replayed: an estimate, said so).

    python -X utf8 tools/livegap.py            # -> research/livegap/LIVEGAP.json + prints the tables
Re-run after `python tools/data_pull.py --latest --since 2026-10-14` lands data/pc_days/ (the PC answers after 16:00 ET):
the day folders then replace the "unknown" rows (fills, decisions = why no trade, uptime).
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "livegap", "LIVEGAP.json")
ET = ZoneInfo("America/New_York")
PV, ECOMM = 2.0, 1.90
BARS_TO = None                       # set from the data

ACCTS = {   # docs/ACCOUNT_RULES.md; start = first session the bot could trade it (live_model eval_start / accounts.json / trades.json)
    "z50k": {"name": "Zlarior 50K (LIT, Builder 50K eval)", "bots": ["LIT"], "start": "2026-10-19", "start_bal": 50000.0,
             "acct": {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0}},
    "z25k2": {"name": "Zlarior 25K #2 (LIT, Builder 25K eval)", "bots": ["LIT"], "start": "2026-11-18", "start_bal": 25000.0,
              "acct": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5}},
    "rapid25k": {"name": "Rapid EOD 25K (LIT + ATLAS <= $250, eval)", "bots": ["LIT", "ATLAS"], "start": "2026-11-20",
                 "start_bal": 25000.0, "atlas_risk": 250.0,
                 "acct": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 500.0, "max_micros": 20, "scale": 0.5}},
    "atlas25": {"name": "ATLAS (Builder 25K: eval Nov 6-17, funded from Nov 18)", "bots": ["ATLAS"], "start": "2026-11-06",
                "start_bal": 25000.0},
}
# trades the cloud has no row for but the account balance pins exactly (inferred; the PC's day folder confirms or refutes)
INFERRED = {("ATLAS", "2026-11-20", "EMA"): {"q": 1, "why": "CONFIRMED by data/pc_days/2026-11-20 trades: SELL 1 at 26,380.75, "
                                                         "TARGET +$514.18 (account acctb); 1 micro = the funded best-day cap"}}
ATLAS_MEMBERS = {"ema_lon_vix": "EMA", "macd_sweep": "MACD", "sr_nyreclaim": "SR"}
# what the files we can see say about the PC (STATE.md / STATE_HISTORY / board events / lit-more-money-2026-11-19.md)
PC_GAPS = [
    {"from": "2026-10-26 08:30", "to": "2026-10-26 08:45", "what": "bot / feed gap: the model entered during it, never routed",
     "src": "engine/live.py comment at the un-routed exit (23:08 ET 2026-10-26)"},
    {"from": "2026-10-27 00:00", "to": "2026-10-27 23:59", "what": "every MFFU order went to an account Name without the 'R': "
     "NinjaTrader refused (fixed)", "src": "engine/ninjatrader._nt_said_no_account, engine/live._void_refused_days"},
    {"from": "2026-11-03 15:00", "to": "2026-11-03 21:06", "what": "bot re-set up and re-armed by hand 20:51-21:06 ET; no record "
     "of the 15:39 signal", "src": "heartbeat remote / autopilot events"},
    {"from": "2026-11-09 15:55", "to": "2026-11-15 20:39", "what": "PC BOT OFF: no uptime sample from Nov 9 15:55 ET to Sun Nov 15 "
     "20:39 ET (the day folders' gaps.json; the report task was not installed either, so nobody saw it)",
     "src": "data/pc_days/2026-11-09 and 2026-11-16 gaps.json uptime; no trade rows Nov 10-13; balance $49,313.54 (Nov 6) -> "
            "$49,192.78 (Nov 17) = only Nov 16's -$129"},
    {"from": "2026-11-24 00:45", "to": "now", "what": "auto-update HELD BACK by a local change on the PC (self-heal could not fix): "
     "the bot runs the code it had before", "src": "board self_heal events Nov 24 00:45-01:45 ET"},
]


def _et(ts):
    return dt.datetime.fromtimestamp(int(ts), ET)


def _hm(ts):
    return _et(ts).strftime("%a %b %d %H:%M")


def in_gap(ts):
    s = _et(ts).strftime("%Y-%m-%d %H:%M")
    for g in PC_GAPS:
        if g["from"] <= s <= (g["to"] if g["to"] != "now" else "9999"):
            return g
    return None


# ================================================================================================ the twins
def lit_twin(since="2026-10-12"):
    from engine import lit
    from tools import lit_final as F
    from tools import lit_rev_exit as R
    c = R.cx()
    M = c["M"]
    ss = [str(d) for d, s, e in M.days if str(d) >= since]
    P = {**lit.DEFAULTS, **R.LIVE}
    Mm, C = F.market(P["ref"], P["extra_boxes"])
    T = lit.run_x(Mm, C, P, ss, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    out = []
    for t in T:
        d = int(t["dir"])
        q = int(t["qty"])
        pts = (t["pnl"] + lit.COMM * q) / (PV * q)
        risk = abs(t["entry_px"] - t["stop_px"])
        out.append({"bot": "LIT", "day": t["day"], "entry_t": int(t["entry_t"]), "dir": d, "exit": t.get("exit"),
                    "entry": t["entry_px"], "stop": t["stop_px"], "target": t["target_px"], "risk": round(risk, 2),
                    "tgt": round(abs(t["target_px"] - t["entry_px"]), 2), "pts": round(pts, 4), "r": round(pts / risk, 3),
                    "w1": round(-risk, 2) if t.get("exit") in ("STOP",) else min(0.0, round(pts, 2)),
                    "lit_qty": q, "lit_usd": round(t["pnl"], 2)})
    return out, ss


def atlas_twin(since="2026-11-01"):
    import pandas as pd
    from engine import second
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    lo = int(dt.datetime.fromisoformat(since).replace(tzinfo=ET).timestamp())
    d5 = d5[d5.time >= lo - 86400 * 45].reset_index(drop=True)
    d1 = d1[d1.time >= lo - 86400 * 3].reset_index(drop=True)
    r = second.run(d5, one_min=d1, now=int(d5.time.max()) + 300, cfg=second.load_cfg(), lit=[])
    out = []
    for k, m in ATLAS_MEMBERS.items():
        for t in r["strategies"][k]["trades"]:
            if t["day"] >= since and t.get("exit_kind"):
                out.append({"bot": "ATLAS", "member": m, "day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]),
                            "dir": int(t["dir"]), "exit": t["exit_kind"], "entry": t["entry"], "stop": t["stop"],
                            "r": round(t["r"], 3), "risk": t["risk_pts"]})
    out.sort(key=lambda t: t["entry_t"])
    # ATLAS's one-position rule on one account: a member trade that starts while another is open is not taken
    book, busy = [], 0
    for t in out:
        t["one_position_skip"] = t["entry_t"] < busy
        if not t["one_position_skip"]:
            busy = t["exit_t"]
            book.append(t)
    return out


def eval_size(twin, A, start, sessions):
    """The twin's micros on the live eval path (two_week sizing, account A), in session order from `start`."""
    from engine import sizing as S
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
    TW = {**lm["two_week"]}
    bal, peak, floor, days = 0.0, 0.0, -A["mll"], 0
    by = collections.defaultdict(list)
    for t in twin:
        by[t["day"]].append(t)
    out = {}
    for k, d in enumerate([s for s in sessions if s >= start]):
        cum = 0.0
        for j, t in enumerate(by.get(d, [])):
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": k + 1, "n_today": j, "days_traded": days}
            q = S.two_week_qty({"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, st, TW, acct=A)
            pnl = t["pts"] * PV * q - ECOMM * q
            out[t["entry_t"]] = {"qty": q, "usd": round(pnl, 2), "session": k + 1}
            cum += pnl
            days += q > 0
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - A["mll"]), A["lock"])
    return out


# ================================================================================================ the live side
def live_rows():
    T = json.load(open(os.path.join(ROOT, "tools", "web_public", "trading", "trades.json"), encoding="utf-8"))
    rows = [t for t in T["trades"] if t["src"] in ("live", "paper")]
    for d in sorted(glob.glob(os.path.join(ROOT, "data", "pc_days", "????-??-??"))):
        p = os.path.join(d, "trades.jsonl.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rows.append({**json.loads(line), "src": "pc_days"})
                    except ValueError:
                        pass
    return rows, T.get("built_from")


def match(tw, rows, bot, window=900):
    for r in rows:
        if r.get("src") != "live" or r.get("bot") != bot:
            continue
        if abs(int(r["t"]) - tw["entry_t"]) <= window and (1 if r["side"] == "LONG" else -1) == tw["dir"]:
            return r
    return None


def paper_of(tw, rows, bot):
    for r in rows:
        if r.get("src") == "paper" and r.get("bot") == bot and abs(int(r["t"]) - tw["entry_t"]) <= 900:
            return r
    return None


# ================================================================================================ the audit
def audit():
    lit, sess = lit_twin()
    atl = atlas_twin()
    rows, built = live_rows()
    bars_to = sess[-1]
    pulled = sorted(os.path.basename(d) for d in glob.glob(os.path.join(ROOT, "data", "pc_days", "????-??-??")))
    res = {"made": dt.date.today().isoformat(), "bars_to": bars_to, "pc_days_pulled": pulled,
           "live_source": "tools/web_public/trading/trades.json (data-pipe ledger rows, built "
                          f"{built}) + data/pc_days ({len(pulled)} days) + owner / PC balances on the board",
           "pc_gaps": PC_GAPS, "accounts": {}}
    # ---- Zlarior 50K
    A = ACCTS["z50k"]
    sz = eval_size(lit, A["acct"], A["start"], sess)
    L = []
    for t in [t for t in lit if t["day"] >= A["start"]]:
        e = sz.get(t["entry_t"], {})
        lv = match(t, rows, "LIT")
        pp = paper_of(t, rows, "LIT")
        g = in_gap(t["entry_t"])
        row = {"when": _hm(t["entry_t"]), "day": t["day"], "side": "LONG" if t["dir"] > 0 else "SHORT", "twin_exit": t["exit"],
               "twin_r": t["r"], "twin_qty": e.get("qty"), "twin_usd": e.get("usd"), "live_qty": None, "live_usd": 0.0}
        if lv:
            row.update(live_qty=lv["q"], live_usd=lv["usd"], live_entry=lv["e"], twin_entry=t["entry"],
                       live_exit_px=lv.get("x"))
            slip = (lv["e"] - t["entry"]) * -t["dir"] * PV * lv["q"]
            row["parts"] = {"SIZE": round(t["r"] * t["risk"] * PV * (lv["q"] - (e.get("qty") or 0)), 2),
                            "SLIPPED": round(lv["usd"] - (t["pts"] * PV * lv["q"] - ECOMM * lv["q"]), 2)}
            row["cause"] = "traded (SIZE + SLIPPED)"
            row["entry_slip_usd"] = round(slip, 2)
        else:
            row["parts"] = {"MISSED": round(-(e.get("usd") or 0.0), 2)}
            why = g["what"] if g else ("no live row; the balance did not move that day" if t["day"] in ("2026-11-10", "2026-11-11")
                                       else "no live row found (pull data/pc_days to see the bot's 'why no trade')")
            if pp and t["day"] == "2026-10-27":
                why = PC_GAPS[1]["what"] + f" (the bot booked {pp['q']} MNQ {pp['usd']:+.0f} that was voided)"
            row["cause"] = "MISSED: " + why
        L.append(row)
    live_known = sum(r["live_usd"] for r in L)
    bal_now, bal_src = 49214.0, "PC live via ntfy, 2026-11-24 11:00 ET (board)"
    acct_move = bal_now - A["start_bal"]
    twin_total = sum((r["twin_usd"] or 0) for r in L)
    extra = round(acct_move - live_known, 2)
    res["accounts"]["z50k"] = {
        "name": A["name"], "start": A["start"], "sessions": len([s for s in sess if s >= A["start"]]), "bars_to": bars_to,
        "twin_usd": round(twin_total, 2), "twin_trades": len(L), "twin_usd_lit_size": round(sum(t["lit_usd"] for t in lit if t["day"] >= A["start"]), 2),
        "live_usd_balance": round(acct_move, 2), "balance_src": bal_src, "live_trades_seen": sum(1 for r in L if r["live_qty"]),
        "live_usd_trades_seen": round(live_known, 2), "extra_unexplained_usd": extra,
        "extra_note": ("balance move not explained by a trade we can see: fees + rows not in the cloud (Oct 19-23 and after Nov 20); "
                       "the room says the account once closed a day at ~$50,168 (floor $48,168), so at least one unseen winner ~+$168 "
                       "came before Oct 28"),
        "trades": L}
    # ---- ATLAS
    B = ACCTS["atlas25"]
    lv_a = [r for r in rows if r.get("src") == "live" and r.get("bot") == "ATLAS"]
    risk_usd = sorted(abs(r["usd"] / r["r"]) for r in lv_a if r.get("r"))
    med = risk_usd[len(risk_usd) // 2] if risk_usd else 170.0
    AL = []
    for t in [t for t in atl if t["day"] >= B["start"]]:
        lv = match(t, rows, "ATLAS", window=600)
        row = {"when": _hm(t["entry_t"]), "day": t["day"], "member": t["member"], "side": "LONG" if t["dir"] > 0 else "SHORT",
               "twin_exit": t["exit"], "twin_r": t["r"], "twin_usd_est": round(t["r"] * med, 2), "one_position_skip": t["one_position_skip"],
               "live_usd": lv["usd"] if lv else 0.0, "live_r": lv.get("r") if lv else None, "live_qty": lv.get("q") if lv else None}
        inf = INFERRED.get(("ATLAS", t["day"], t["member"]))
        if inf and not lv:
            usd_ = round(t["r"] * t["risk"] * PV * inf["q"] - ECOMM * inf["q"], 2)
            row.update(live_usd=usd_, live_qty=inf["q"], live_r=t["r"], inferred=inf["why"])
            row["cause"] = "traded (confirmed by the day folder): SIZE vs the usual risk"
            row["parts"] = {"SIZE": round(usd_ - row["twin_usd_est"], 2)}
        elif t["one_position_skip"]:
            row["cause"], row["parts"] = "not a gap: the one-position rule skips it (another member open)", {}
            row["twin_usd_est"] = 0.0
        elif lv:
            row["cause"] = "traded (SLIPPED = live R vs twin R x risk)"
            row["parts"] = {"SLIPPED": round(lv["usd"] - t["r"] * abs(lv["usd"] / lv["r"]), 2) if lv.get("r") else 0.0}
        else:
            g = in_gap(t["entry_t"])
            row["cause"] = "MISSED: " + (g["what"] if g else "no live row in data/pc_days")
            row["parts"] = {"MISSED_or_unseen": round(-t["r"] * med, 2)}
        AL.append(row)
    res["accounts"]["atlas25"] = {
        "name": B["name"], "start": B["start"], "bars_to": bars_to, "median_live_risk_usd": round(med, 2),
        "twin_usd_est": round(sum(r["twin_usd_est"] for r in AL), 2), "twin_r": round(sum(r["twin_r"] for r in AL if not r["one_position_skip"]), 2),
        "live_usd_trades_seen": round(sum(r["live_usd"] for r in AL), 2),
        "live_usd_balance": {"eval_passed": 1946.10, "funded_now": 401.0, "total": 2347.10,
                             "src": "owner note Nov 17 ($26,946.10, passed) + PC live Nov 24 (funded $401)"},
        "note": ("ATLAS twin $ = twin R x the median live $ risk of its seen trades (the account's own need / funded sizing is not "
                 "replayed): an estimate. The balance (+$2,347) is MORE than the seen trades (+$1,510): live rows are missing for "
                 "the silent Nov 7-17 and for Nov 19-24. Eval: +$1,946.10 = seen -$168.81 + $1,791.89 + $323 not seen (no twin "
                 "trade explains it: an EXTRA). Funded: $401 = Nov 18 -$112.80 + Nov 20 1 micro +$512.4 (inferred)."),
        "trades": AL}
    # ---- the two new LIT accounts
    for key in ("z25k2", "rapid25k"):
        A = ACCTS[key]
        tt = [t for t in lit if t["day"] >= A["start"]]
        at = [t for t in atl if t["day"] >= A["start"] and not t["one_position_skip"]] if "ATLAS" in A["bots"] else []
        bal = {"z25k2": 25024.0, "rapid25k": 24976.0}[key]
        res["accounts"][key] = {
            "name": A["name"], "start": A["start"], "bars_to": bars_to, "twin_lit_trades": len(tt),
            "twin_atlas_trades": [{"when": _hm(t["entry_t"]), "member": t["member"], "r": t["r"],
                                   "usd_at_250_risk": round(t["r"] * A.get("atlas_risk", 0), 2)} for t in at],
            "twin_usd": round(sum(t["r"] * A.get("atlas_risk", 0) for t in at), 2),
            "live_usd_balance": round(bal - A["start_bal"], 2), "balance_src": "PC live via ntfy, 2026-11-24 11:00 ET (board)",
            "note": ("no LIT twin trade from the start to the last bar we have; the small balance move is unexplained from the cloud"
                     + ("; the Rapid account's 'armed' check is still on the owner's to-do (board 'WAITING ON THE OWNER'), so ATLAS's "
                        "Nov 20 +6.6R twin trade may not have been eligible" if key == "rapid25k" else ""))}
    # ---- $ per cause, ranked
    causes = collections.Counter()
    for key, a in res["accounts"].items():
        for r in a.get("trades", []):
            for c, v in (r.get("parts") or {}).items():
                tag = c
                if c.startswith("MISSED"):
                    cc = r["cause"]
                    tag = ("MISSED: PC bot OFF Nov 9-15" if "BOT OFF" in cc or "SILENT" in cc or "balance did not move" in cc else
                           "MISSED: order refused (account Name, fixed)" if "refused" in cc else
                           "MISSED: bot / feed gap" if "gap" in cc else
                           "MISSED: bot re-set up by hand" if "re-set up" in cc else "MISSED or unseen: no live row")
                causes[(key, tag)] += v
        if key == "z50k":
            causes[(key, "EXTRA: unexplained balance move")] += a["extra_unexplained_usd"]
        if key == "atlas25":
            seen = sum(r["live_usd"] for r in a["trades"])
            causes[(key, "EXTRA: unexplained balance move")] += a["live_usd_balance"]["total"] - seen
        if key in ("z25k2", "rapid25k"):
            causes[(key, "MISSED or not armed (ATLAS on Rapid)" if a["twin_usd"] else "EXTRA: unexplained balance move")] += \
                a["live_usd_balance"] - a["twin_usd"]
    rank = sorted(({"account": k, "cause": c, "usd_vs_twin": round(v, 2)} for (k, c), v in causes.items()), key=lambda x: x["usd_vs_twin"])
    res["causes_ranked"] = rank
    T = json.load(open(os.path.join(ROOT, "tools", "web_public", "trading", "trades.json"), encoding="utf-8"))
    h2 = (T.get("lit_ref") or {}).get("h2") or {}
    n_s = res["accounts"]["z50k"]["sessions"]
    exp = round(h2.get("per_month", 0) * n_s / 21)
    res["market"] = {"z50k_twin_eval_usd": res["accounts"]["z50k"]["twin_usd"],
                     "z50k_twin_lit_size_usd": res["accounts"]["z50k"]["twin_usd_lit_size"],
                     "backtest_expectation_lit_size_usd": exp, "expectation_basis": f"Jul-Oct 2026 ${h2.get('per_month')}/mo x {n_s} sessions / 21",
                     "market_shortfall_lit_size_usd": round(res["accounts"]["z50k"]["twin_usd_lit_size"] - exp),
                     "twin_winners": sum(1 for r in res["accounts"]["z50k"]["trades"] if r["twin_r"] > 0.5),
                     "words": "the twin ITSELF lost money in the live window: most of the gap to the backtest's monthly average is the "
                              "market, not the bot"}
    return res


def main():
    R = audit()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, default=str)
    for k, a in R["accounts"].items():
        print(f"== {a['name']}: twin ${a.get('twin_usd', a.get('twin_usd_est'))} | live balance {a['live_usd_balance']}")
        for r in a.get("trades", []):
            print(f"   {r['when']} {r.get('member', '')} {r['side']} twin {r['twin_exit']} {r['twin_r']}R "
                  f"${r.get('twin_usd', r.get('twin_usd_est'))} q{r.get('twin_qty')} | live {r.get('live_qty')} ${r['live_usd']} | {r['cause']}")
    print("causes (negative = live behind the twin):")
    for c in R["causes_ranked"]:
        print(f"   {c['account']:9s} {c['cause']:45s} {c['usd_vs_twin']:+,.0f}")
    print(f"-> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
