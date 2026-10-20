"""Sunday re-check of the research watch-list (research/backlog.json): re-score every "auto" lead on the current data the
LIT way and push once when a lead crosses its adopt bar. Read-only research: never changes live_model.json.

Each auto lead = the live LIT settings (live_model.json "lit") + the lead's engine params, or + a post-hoc size rule
("post"), or the live trades with other eval sizing ("sizing"). Scored like the live results:
  LIT size rule   tools/lit_final.run + score: H1 (pick) / H2 (check) / 2026 net $, PF, trades a week
  eval path       engine/eval_mc: a fresh MFFU Builder 50K eval, 2,000 Monte Carlo paths of 5-session blocks from the half,
                  sized by sizing.lit_qty with lit_sizing (two_week to session 10, then safe_eval): 2-week pass / fail
  trades changed  trades whose day / entry / P&L differ from live (the lead's "need" count)
Adopt bar (research/backlog.json "bar"): H1 and H2 net above live on the LIT size rule (eval-only leads: skipped), 2026 >= 2
trades a week, eval 2-week pass not lower and fail not more than 1 point higher in both halves, and the need count reached.

    python -X utf8 tools/backlog_recheck.py              # score every auto lead, print the table (~1-2 min)
    python -X utf8 tools/backlog_recheck.py --push       # + push once per lead and data version when a lead crosses its bar
    python -X utf8 tools/backlog_recheck.py --save       # + write research/lab/backlog_check.json and research/BACKLOG.md
    python -X utf8 tools/backlog_recheck.py --render     # research/BACKLOG.md from the last saved check, no replays
The PC ops task (engine/ops_checks.tick, Sunday 17:00-23:59 ET) runs it once a week with --push; its result goes to
logs/backlog_check.json (never a tracked file, so UPDATE's git pull stays clean).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BACKLOG = os.path.join(ROOT, "research", "backlog.json")
SAVED = os.path.join(ROOT, "research", "lab", "backlog_check.json")
LOCAL = os.path.join(ROOT, "logs", "backlog_check.json")
MD = os.path.join(ROOT, "research", "BACKLOG.md")
N_MC = 2000


def _data_key():
    st = os.stat(os.path.join(ROOT, "data", "NQ_5m.csv"))
    s1 = os.path.getsize(os.path.join(ROOT, "data", "NQ_1m.csv")) if os.path.exists(os.path.join(ROOT, "data", "NQ_1m.csv")) else 0
    return f"{st.st_size}-{s1}"


def _vix_prior():
    import csv
    rows = sorted((r["date"], float(r["close"])) for r in csv.DictReader(open(os.path.join(ROOT, "data", "VIX_1d.csv"), encoding="utf-8"))
                  if r.get("close"))
    return rows


def _post(T, post):
    """A post-hoc size rule on the LIT-size-rule trades: x on days whose prior VIX close >= vix_ge (P&L scaled)."""
    import bisect
    V = _vix_prior()
    ds = [d for d, _ in V]
    out = []
    for t in T:
        i = bisect.bisect_left(ds, t["day"]) - 1
        v = V[i][1] if i >= 0 else None
        m = float(post["x"]) if v is not None and v >= float(post["vix_ge"]) else 1.0
        q0 = int(t["qty"])
        q1 = max(1, min(40, int(q0 * m + 1e-9))) if m != 1.0 else q0      # one rounding, 40 micros max (LIT size rule)
        f = q1 / q0 if q0 else 1.0
        out.append({**t, "qty": q1, "pnl": t["pnl"] * f, "low": t.get("low", 0) * f, "size_mult": float(t.get("size_mult", 1.0)) * m,
                    "post_hit": m != 1.0})
    return out


def _eval(T, sizing):
    from engine import eval_mc
    from tools import lit_eval_sample
    D = lit_eval_sample.to_sample(T)
    o = {}
    for sp in ("H1", "H2"):
        r = eval_mc.simulate(1, 0.0, 2000.0, sizing, n=N_MC, seed=7, span=sp, D=D)
        o[sp] = {k: r[k] for k in ("p10", "f10", "pass", "fail", "pass_med")}
    return o


def _changed(T, T0):
    a = {(t["day"], int(t["entry_t"]), round(float(t["pnl"]))) for t in T if t["day"] >= "2026"}
    b = {(t["day"], int(t["entry_t"]), round(float(t["pnl"]))) for t in T0 if t["day"] >= "2026"}
    return len({x[0] for x in a ^ b})


def score_all(only=None, log=print):
    from engine import lit
    from tools import lit_final as F
    B = json.load(open(BACKLOG, encoding="utf-8"))
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    base = {**lit.DEFAULTS, **lm["lit"]}
    ls = lm.get("lit_sizing") or {}
    t0 = time.time()
    T0 = F.run(base)
    S0 = F.score(T0, spans=("H1", "H2", "2026"), fast=True)
    E0 = _eval(T0, ls)
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "data_key": _data_key(), "data_to": max(F.SESS),
           "live": {"lit": S0, "eval": E0}, "leads": {}}
    log(f"live: H1 {S0['H1']['net']:+,} H2 {S0['H2']['net']:+,} | eval 2wk H1 {E0['H1']['p10']}/{E0['H1']['f10']} H2 {E0['H2']['p10']}/{E0['H2']['f10']}")
    for L in B["leads"]:
        if L.get("kind") != "auto" or (only and L["id"] not in only):
            continue
        try:
            if L.get("params"):
                T = F.run({**base, **L["params"]})
            elif L.get("post"):
                T = _post(T0, L["post"])
            else:
                T = T0
            S = F.score(T, spans=("H1", "H2", "2026"), fast=True)
            E = _eval(T, {**ls, **(L.get("sizing") or {})})
            need = L.get("need") or {}
            if L.get("post"):
                sp = need.get("span")
                a, z = F.SPAN[sp] if sp else ("2026-01-01", "2026-12-31")
                have = sum(1 for t in T if t.get("post_hit") and a <= t["day"] <= z)
            elif L.get("sizing") and not L.get("params"):
                have = sum(1 for t in T if t["day"] >= "2026")
            else:
                have = _changed(T, T0)
            chk = {}
            if not L.get("eval_only"):
                chk["H1 net above live"] = S["H1"]["net"] > S0["H1"]["net"]
                chk["H2 net above live"] = S["H2"]["net"] > S0["H2"]["net"]
            chk["2+ trades a week"] = (S["2026"]["tpw"] or 0) >= 2
            for sp in ("H1", "H2"):
                chk[f"eval {sp} 2-week pass not lower"] = E[sp]["p10"] >= E0[sp]["p10"]
                chk[f"eval {sp} 2-week fail within +1"] = E[sp]["f10"] <= E0[sp]["f10"] + 1.0
            chk[f"{need.get('what', 'trades')} >= {need.get('n', 0)}"] = have >= int(need.get("n", 0))
            crossed = all(chk.values())
            out["leads"][L["id"]] = {"lit": S, "eval": E, "have": have, "need": need.get("n"), "checks": chk,
                                     "crossed": crossed, "gated": L.get("gated")}
            log(f"{L['id']:18s} H1 {S['H1']['net'] - S0['H1']['net']:+7,} H2 {S['H2']['net'] - S0['H2']['net']:+7,} vs live | "
                f"eval 2wk H1 {E['H1']['p10']}/{E['H1']['f10']} H2 {E['H2']['p10']}/{E['H2']['f10']} | {have}/{need.get('n')} | "
                f"{'CROSSED' if crossed else 'not yet: ' + ', '.join(k for k, v in chk.items() if not v)}")
        except Exception as e:                   # one broken lead never stops the others
            out["leads"][L["id"]] = {"error": f"{e.__class__.__name__}: {e}"}
            log(f"{L['id']}: error {e}")
    out["seconds"] = round(time.time() - t0)
    return out


def notices(res, now=None):
    """Push payloads (engine/ops_checks._payload) for leads that crossed: one key per lead and data version."""
    from engine import ops_checks as O
    now = time.time() if now is None else now
    B = {L["id"]: L for L in json.load(open(BACKLOG, encoding="utf-8"))["leads"]}
    out = []
    for lid, r in (res.get("leads") or {}).items():
        if not r.get("crossed"):
            continue
        L = B.get(lid, {})
        S, S0 = r["lit"], res["live"]["lit"]
        body = (f"{L.get('title', lid)}: H1 {S['H1']['net'] - S0['H1']['net']:+,} / H2 {S['H2']['net'] - S0['H2']['net']:+,} vs live, "
                f"eval 2-week {r['eval']['H2']['p10']:.0f}% pass / {r['eval']['H2']['f10']:.0f}% fail (H2), {r['have']} trades. "
                + (f"Gated: {L['gated']}. " if L.get("gated") else "")
                + f"Not switched on: ask Claude to review ({L.get('writeup', 'research/BACKLOG.md')}).")
        out.append(O._payload("backlog", f"Research lead ready: {lid}", body, f"backlog:{lid}:{res.get('data_key')}", now))
    return out


def render(res=None):
    B = json.load(open(BACKLOG, encoding="utf-8"))
    res = res if res is not None else (json.load(open(SAVED, encoding="utf-8")) if os.path.exists(SAVED) else {})
    R = res.get("leads") or {}
    L = ["# Research backlog: the watch-list", "",
         "Generated by `tools/backlog_recheck.py --render` from `research/backlog.json` (edit that file, not this one).",
         f"Last check: {res.get('built', 'never')} on data to {res.get('data_to', '?')}. The PC ops task re-checks the auto leads",
         "every Sunday (17:00-23:59 ET) and pushes once to the phone when one crosses its bar. Nothing is ever switched on",
         "automatically: a crossed lead is reviewed, written up and approved by the owner first.",
         "New data only counts once it is in: the owner's TradingView export (data/), then `python tools/runlib.py baseline`",
         "(tools/lit_final.SESS, the session list every score uses, comes from the stored baseline run).", "",
         f"**Adopt bar.** {B['bar']}", ""]
    lv = res.get("live") or {}
    if lv:
        s, e = lv["lit"], lv["eval"]
        L += [f"Live now (LIT size rule): H1 {s['H1']['net']:+,} PF {s['H1']['pf']} · H2 {s['H2']['net']:+,} PF {s['H2']['pf']} · "
              f"{s['2026']['tpw']}/wk; eval path 2-week pass/fail H1 {e['H1']['p10']}/{e['H1']['f10']} · H2 {e['H2']['p10']}/{e['H2']['f10']}.", ""]
    L += ["| Lead | Kind | H1 vs live | H2 vs live | Eval 2-wk pass/fail H1 · H2 | Trades: have / need | Status |", "|---|---|---:|---:|---|---|---|"]
    for x in B["leads"]:
        r = R.get(x["id"]) or {}
        if x["kind"] == "auto" and r and "lit" in r:
            d1 = r["lit"]["H1"]["net"] - lv["lit"]["H1"]["net"]
            d2 = r["lit"]["H2"]["net"] - lv["lit"]["H2"]["net"]
            ev = f"{r['eval']['H1']['p10']}/{r['eval']['H1']['f10']} · {r['eval']['H2']['p10']}/{r['eval']['H2']['f10']}"
            miss = [k for k, v in r["checks"].items() if not v]
            st = ("**crossed**" + (" (gated)" if x.get("gated") else "")) if r["crossed"] else "not yet: " + "; ".join(miss)
            L.append(f"| [{x['title']}](writeups/{x['writeup']}) | auto | {d1:+,} | {d2:+,} | {ev} | {r['have']} / {r['need']} | {st} |")
        else:
            L.append(f"| [{x['title']}](writeups/{x['writeup']}) | {x['kind']} | – | – | – | ? / {x['need']['n']} | "
                     f"{'error: ' + r['error'] if r.get('error') else 'manual rerun'} |")
    L += ["", "## Each lead: why it waits, how to rerun, what it needs", ""]
    for x in B["leads"]:
        L += [f"### {x['title']} (`{x['id']}`)", "",
              f"- Write-up: `research/writeups/{x['writeup']}`; runs: {', '.join('`' + r + '`' for r in x['runs']) or '-'}.",
              f"- Why it waits: {x['why_wait']}."]
        if x["kind"] == "auto":
            what = (f"engine params `{json.dumps(x['params'])}`" if x.get("params") else f"post-hoc size `{json.dumps(x['post'])}`"
                    if x.get("post") else f"eval sizing `{json.dumps(x['sizing'])}`")
            L.append(f"- Rerun (exact): `python -X utf8 tools/backlog_recheck.py --only {x['id']}` = the live settings + {what}.")
        else:
            L.append(f"- Rerun: `{x['rerun']}`.")
        L.append(f"- Needs: {x['need']['what']} >= {x['need']['n']}." + (f" Gate: {x['gated']}." if x.get("gated") else ""))
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    if a.render:
        open(MD, "w", encoding="utf-8").write(render())
        print("->", os.path.relpath(MD, ROOT))
        return 0
    res = score_all(a.only)
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
    json.dump(res, open(LOCAL, "w", encoding="utf-8"), indent=1)
    if a.save:
        json.dump(res, open(SAVED, "w", encoding="utf-8"), indent=1)
        open(MD, "w", encoding="utf-8").write(render(res))
        print("->", os.path.relpath(SAVED, ROOT), os.path.relpath(MD, ROOT))
    if a.push:
        from engine import ops_checks as O
        st = O.load_state()
        for p in notices(res):
            print("push", p["key"], O.send(p, st))
        O.save_state(st)
    print(f"{sum(1 for r in res['leads'].values() if r.get('crossed'))} lead(s) crossed their bar ({res['seconds']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
