"""ATLAS v2 PAPER SHADOW (engine/atlas_v2.py, research/writeups/atlas-v2.md candidate 1b) + the account_b "weights" /
"min_room" keys (BUILT BUT OFF). Paper only: nothing is armed, routed or written to second_model.json.

    python -X utf8 -m tests.test_atlas_v2_shadow            # everything incl. a cloud dry run (~3 min)
    python -X utf8 -m tests.test_atlas_v2_shadow --no-cloud # without the cloud dry run

 a. 2026 replay: the shadow's executor on the research units (EMA / MACD / S/R / the two hunts, LIT's trades and armed
    setups) gives exactly the research executor's back-to-back 25K path of candidate 1b (tools/atlas_v2.score, run
    atlas_v2_hunts_w05_stuck200's V) in H1 (from 2026-01-02) and H2 (from 2026-07-01): every trade, micros, exit and $;
    the same evals (pass / fail / stuck). Against the STORED run file: the trades and $ agree within the stated tolerance
    (the stored run was scored on an older unit cache; the exact check is the line above).
 b. the live mechanics: the same 2026 H2 replayed poll by poll (every entry / exit / session end, members' trades OPEN
    until they finish, the state JSON-round-tripped each poll, open trades rebuilt from the 1m / 5m bars) = the batch replay.
 c. unit_of (a member's paper trade -> account-B unit, from the bars) = the research units (risk, target, pts, worst open
    pts, open path) for every 2026 trade of the five members.
 d. account_b "weights" / "min_room" OFF by default: second_model.json "account_b" unchanged (null) and its strategies
    byte-identical to git HEAD; normalize() without the keys gives today's spec (no new keys); qty() with key= and no
    weights = qty() without (a grid of stops / targets / eval states); today's ATLAS research path re-sized through
    engine/account_b.qty(key=) = tools/atlas.q_variant (identical trades); with the keys: weights x0.5 and min_room 200
    behave as the research (= candidate 1b path above), bad values are refused.
 e. never routed: engine/atlas_v2.py imports no broker / adapter / NinjaTrader module and writes no order file; the PC hook
    runs in the paper thread after LIT's routing; the cloud monitor never routes; pushes are kind "second", titled
    "ATLAS v2 PAPER ...", OFF by default (second_model.json atlas_v2.push false).
 f. the scorecard (research/second/atlas_v2_scorecard.json bands, bootstrap like engine/second_scorecard), card(), compact()
    (PC heartbeat second.atlas_v2), pc_step() file, the phone / PC renderer (secondcore.js v8, node) draws the card.
 g. the cloud workflow's sparse checkout covers every file the shadow reads; a cloud dry run (python tools/cloud_monitor.py
    --out <tmp>) writes state "atlas_v2".
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

from engine import account_b as AB  # noqa: E402
from engine import atlas_v2 as AV  # noqa: E402

RESULTS = []
SRCS = ("EMA", "MD", "SR", "SHA", "SHT")
FILES = {"EMA": ("second", "ema_best.json"), "MD": ("second", "md_best.json"), "SR": ("second", "sr_best.json"),
         "SHA": ("stophunt", "sh_asia_resweep.json"), "SHT": ("stophunt", "sh_trend_idm5.json")}


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"\n     {str(detail)[:600]}"), flush=True)


# ================================================================================================ research inputs
_R = {}


def research():
    if not _R:
        from tools import atlas_v2 as V2
        from tools import second_mix as M
        from tools import atlas_lit_armed as ARM
        V2.install()
        U = M.units()
        V = json.load(open(os.path.join(ROOT, "research", "runs", AV.RUN + ".json"), encoding="utf-8"))["params"]["V"]
        px = {}
        for nm, (d, fn) in FILES.items():
            for t in json.load(open(os.path.join(ROOT, "research", d, fn), encoding="utf-8"))["trades"]:
                px[(nm, int(t["entry_t"]))] = float(t["entry"])
        units = [{**u, "id": f"{nm}:{u['entry_t']}", "key": AV.KEY_OF[nm], "open": False, "entry": px.get((nm, u["entry_t"]))}
                 for nm in SRCS for u in U[nm]]
        lit = [{"day": x["day"], "entry_t": x["entry_t"], "exit_t": x["exit_t"], "dir": x["dir"]} for x in U["LIT"]]
        armed = [[d, a[0], a[1], a[2]] for d, L in ARM.by_day().items() for a in L]
        _R.update(V2=V2, M=M, U=U, V=V, units=units, lit=lit, armed=armed)
    return _R


def span(name):
    R = research()
    a, z = R["M"].SPANS[name]
    sess = [d for d in R["U"]["sessions"] if a <= d <= z]
    fr = int(dt.datetime.fromisoformat(sess[0] + "T00:00:00-05:00").timestamp()) - 6 * 3600     # 18:00 ET the evening before
    return a, z, sess, fr


def batch(name):
    R = research()
    a, z, sess, fr = span(name)
    S = AV.new_state(fr, fr)
    AV.advance(S, [u for u in R["units"] if a <= u["day"] <= z], [x for x in R["lit"] if a <= x["day"] <= z], R["armed"], sess, 2_000_000_000)
    return S


def key_of(x):
    return (x["entry_t"], x["src"], int(x["qty"]), int(x["exit_t"]), round(float(x["usd"] if "usd" in x else x["pnl"]), 2))


# ================================================================================================ a. 2026 replay
def part_a():
    R = research()
    o, P = R["V2"].score(R["V"], spans=("H1", "H2"), mp=False, keep_paths=True)
    for nm in ("H1", "H2"):
        S = batch(nm)
        mine = sorted(S["ledger"].values(), key=lambda r: r["entry_t"])
        ref = P[nm]
        bad = [(x, y) for x, y in zip(mine, ref) if key_of(x) != key_of(y)]
        check(f"a. {nm}: shadow replay = research executor (tools/atlas_v2.score, candidate 1b): {len(mine)} trades, every micro / exit / $",
              len(mine) == len(ref) and not bad, bad[:2] or (len(mine), len(ref)))
        b2b = o[nm]["b2b"].split("/")
        cnt = [sum(1 for e in S["evals"] if e["result"] == r) for r in ("PASS", "FAIL", "STUCK")]
        check(f"a. {nm}: the same evals (pass / fail / stuck {'/'.join(map(str, cnt))} = research {o[nm]['b2b']})",
              cnt == [int(b2b[0]), int(b2b[1]), int(b2b[2])], (cnt, o[nm]["b2b"]))
        net = round(sum(r["usd"] for r in mine))
        check(f"a. {nm}: path $ {net:+,} = research {o[nm]['net']:+,}", net == o[nm]["net"], (net, o[nm]["net"]))
    # the stored run file (scored on an older unit cache: EMA / MACD targets up to ~0.6 pts apart): agreement within tolerance
    from tools import runlib as rl
    d = rl.load(AV.RUN)
    cols = d["trade_cols"]
    st = [dict(zip(cols, t)) for t in d["trades"] if t[0] >= "2026"]
    mine = sorted([r for nm in ("H1", "H2") for r in batch(nm)["ledger"].values()], key=lambda r: r["entry_t"])
    A = {(r["entry_t"], r["src"], r["qty"]) for r in mine}
    B = {(t["entry_t"], t["trigger"], t["qty"]) for t in st}
    same = len(A & B) / max(len(A | B), 1)
    na, nb = sum(r["usd"] for r in mine), sum(t["pnl"] for t in st)
    check(f"a. stored run {AV.RUN}: {len(A & B)} of {len(B)} stored 2026 trades identical (entry, member, micros), "
          f"{100 * same:.1f}% overlap; 2026 $ {na:+,.0f} vs stored {nb:+,.0f}", same >= 0.97 and abs(na - nb) <= 0.05 * abs(nb), (same, na, nb))


# ================================================================================================ b. poll by poll
def part_b():
    from tools import lit_final as F
    R = research()
    Mk, _ = F.market("cisd", [])
    B1, B5 = AV.Bars(F.bars(Mk, "1m"), 60), AV.Bars(F.bars(Mk, "5m"), 300)
    a, z, sess, fr = span("H2")
    U = [u for u in R["units"] if a <= u["day"] <= z]
    L = [x for x in R["lit"] if a <= x["day"] <= z]
    ends = {d: int(dt.datetime.fromisoformat(d + "T17:00:00-04:00").timestamp()) for d in sess}
    polls = sorted({u["entry_t"] for u in U} | {u["exit_t"] + 60 for u in U} | {x["entry_t"] + 60 for x in L} | set(ends.values()))
    S = AV.new_state(fr, fr)
    t0 = time.time()
    for now in polls:
        vis = []
        for u in U:
            if u["entry_t"] > now:
                continue
            if u["exit_t"] <= now:
                vis.append(u)
            else:                                   # still open at this poll: no exit yet, the bars give its path
                vis.append({k: v for k, v in u.items() if k not in ("exit_t", "exit", "pts", "w1", "pt", "po", "pw")} | {"open": True, "_B": AV._pick(B1, B5, u["entry_t"])})
        lit = [{**x, "exit_t": x["exit_t"] if x["exit_t"] <= now else None} for x in L if x["entry_t"] <= now]
        arm = [w for w in R["armed"] if w[2] <= now]
        S = json.loads(json.dumps(S))
        AV.advance(S, vis, lit, arm, [d for d in sess if d <= AV.trading_day(now)], now)
    S = json.loads(json.dumps(S))
    AV.advance(S, U, L, R["armed"], sess, 2_000_000_000)
    ref = sorted(batch("H2")["ledger"].values(), key=lambda r: r["entry_t"])
    mine = sorted(S["ledger"].values(), key=lambda r: r["entry_t"])
    bad = [(x, y) for x, y in zip(mine, ref) if key_of(x) != key_of(y)]
    check(f"b. 2026 H2 poll by poll ({len(polls)} polls, {time.time() - t0:.0f} s, state JSON-round-tripped): = the batch replay "
          f"({len(mine)} trades, {len(S['evals'])} evals)", len(mine) == len(ref) and not bad and
          [e["result"] for e in S["evals"]] == [e["result"] for e in batch("H2")["evals"]], bad[:2] or (len(mine), len(ref)))
    hedge = [r for r in mine if r["exit_kind"] == "HEDGE"]
    check(f"b. HEDGE cuts booked live ({len(hedge)} in H2) at the research price", all(key_of(x) in {key_of(y) for y in ref} for x in hedge))


# ================================================================================================ c. unit_of
def part_c():
    from tools import lit_final as F
    R = research()
    Mk, _ = F.market("cisd", [])
    B1, B5 = AV.Bars(F.bars(Mk, "1m"), 60), AV.Bars(F.bars(Mk, "5m"), 300)
    files = {"EMA": ("second", "ema_best.json"), "MD": ("second", "md_best.json"), "SR": ("second", "sr_best.json"),
             "SHA": ("stophunt", "sh_asia_resweep.json"), "SHT": ("stophunt", "sh_trend_idm5.json")}
    for nm, (d, fn) in files.items():
        rows = [t for t in json.load(open(os.path.join(ROOT, "research", d, fn), encoding="utf-8"))["trades"] if t["day"] >= "2026-01-01"]
        ref = {u["entry_t"]: u for u in R["U"][nm] if u["day"] >= "2026-01-01"}
        bad = 0
        for t in rows:
            u = AV.unit_of(t, AV.KEY_OF[nm], B1, B5)
            r = ref.get(int(t["entry_t"]))
            if u is None or r is None or any(abs(float(u[k]) - float(r[k])) > 1e-6 for k in ("risk", "tgt", "pts", "w1")) \
                    or not np.array_equal(u["pt"], r["pt"]) or not np.allclose(u["po"], r["po"]) or not np.allclose(u["pw"], r["pw"]):
                bad += 1
        check(f"c. unit_of = research units for {nm}: {len(rows)} 2026 trades (risk, target, pts, worst open, path)", bad == 0 and len(rows) == len(ref), bad)


# ================================================================================================ d. account_b keys off
def part_d():
    raw = open(os.path.join(ROOT, "second_model.json"), encoding="utf-8").read()
    c = json.loads(raw)
    try:
        head = json.loads(subprocess.run(["git", "show", "HEAD:second_model.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    except Exception:
        head = None
    check("d. second_model.json: account_b still null (the live ATLAS is not switched to v2)", c.get("account_b") is None)
    check("d. second_model.json: every strategy byte-identical to git HEAD (no member, weight or route changed)",
          head is not None and json.dumps(c["strategies"], sort_keys=True) == json.dumps(head["strategies"], sort_keys=True))
    check("d. second_model.json atlas_v2: on, push false (shadow pushes off by default)", (c.get("atlas_v2") or {}).get("push") is False
          and AV.push_on(c["atlas_v2"]) is False and AV.enabled(c["atlas_v2"]))
    blk = {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-10-26", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need"}
    s0 = AB.normalize(blk)
    check("d. normalize() without weights / min_room: no new spec keys, no problem (today's spec)",
          s0["problem"] is None and "weights" not in s0 and "min_room" not in s0 and AB.min_room(s0) == AB.MIN_ROOM == 100.0
          and AB.weight(s0, "ema_lon_vix") == 1.0)
    diff, n = [], 0
    for risk in (6.0, 9.5, 14.25, 22.0, 35.5, 60.0, 79.75):
        for tgt_r in (1.6, 2.0, 3.4, 6.0):
            for prof, cum, room, sess in ((0.0, 0.0, 1000.0, 1), (420.0, -150.0, 640.0, 6), (-300.0, 0.0, 420.0, 11), (900.0, 200.0, 1100.0, 14), (0.0, -480.0, 380.0, 3)):
                st = {"profit": prof, "cum": cum, "room": room, "session": sess, "n_today": 0}
                tr = {"risk_pts": risk, "tgt_pts": risk * tgt_r}
                for k in ("ema_lon_vix", "macd_sweep", "sr_nyreclaim"):
                    for sz in ("need", "safe"):
                        sp = {**s0, "sizing": sz}
                        a, b = AB.qty(sp, tr, st), AB.qty(sp, tr, st, key=k)
                        n += 1
                        if a != b:
                            diff.append((risk, tgt_r, st, k, sz, a, b))
    check(f"d. qty(key=) without weights = qty() ({n} stop / target / eval-state / member / sizing cases)", not diff, diff[:2])
    # today's ATLAS research path, re-sized through engine/account_b.qty(key=) = tools/atlas.q_variant (identical trades)
    R = research()
    from tools import atlas as A
    from tools import second_account_b as SAB
    V0 = A.BASE
    U = A.account_units(V0)
    sp = A.spec()

    def path(fn):
        keep = A.q_variant
        A.q_variant = fn
        try:
            with A.Plan(V0) as pl:
                return {s: SAB.score(U, "atlas", s, pl.safe_rule)[1] for s in ("H1", "H2")}
        finally:
            A.q_variant = keep
    ref = path(A.q_variant)
    eng = path(lambda t, st, V: AB.qty(sp, {"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, dict(st), key=AV.KEY_OF.get(t["src"]))["qty"])
    same = all([key_of(x) for x in ref[s]] == [key_of(x) for x in eng[s]] for s in ref)
    check(f"d. today's ATLAS (EMA + MACD + S/R) 2026 H1 + H2 path through engine/account_b.qty(key=), keys absent = the research "
          f"q_variant ({sum(len(v) for v in ref.values())} trades identical)", same and sum(len(v) for v in ref.values()) > 50, sum(len(v) for v in ref.values()))
    # with the keys: the 1b spec
    s1 = AV.spec()
    check("d. with the keys (candidate 1b, never written to the file): weights {sh_asia 0.5, sh_trend 0.5}, min_room 200, no problem",
          s1["problem"] is None and s1["weights"] == {"sh_asia": 0.5, "sh_trend": 0.5} and AB.min_room(s1) == 200.0)
    st = {"profit": 0.0, "cum": 0.0, "room": 1000.0, "session": 1, "n_today": 0}
    q1 = AB.qty({**s1, "weights": {}}, {"risk_pts": 20.0, "tgt_pts": 40.0}, st, key="sh_asia")["qty"]
    q2 = AB.qty(s1, {"risk_pts": 20.0, "tgt_pts": 40.0}, st, key="sh_asia")["qty"]
    check(f"d. weight 0.5: {q1} -> {q2} micros (max(1, int(q x 0.5)))", q1 > 1 and q2 == max(1, int(q1 * 0.5 + 1e-9)), (q1, q2))
    bad = [AB.normalize({**blk, "weights": {"ema_lon_vix": 3}})["problem"], AB.normalize({**blk, "weights": {"sh_trend": 0.5}})["problem"],
           AB.normalize({**blk, "min_room": "x"})["problem"], AB.normalize({**blk, "weights": [1]})["problem"]]
    check("d. bad weights / min_room are refused (a problem = not traded)", all(bad), bad)


# ================================================================================================ e. never routed
def part_e():
    src = open(os.path.join(ROOT, "engine", "atlas_v2.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    imp = re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", code, re.M)
    mods = {a or b for a, b in imp}
    check("e. engine/atlas_v2.py imports no broker / adapter / NinjaTrader / live module",
          not any(re.search(r"ninjatrader|adapter|broker|\.live\b|^live$|oif", m) for m in mods), sorted(mods))
    check("e. engine/atlas_v2.py never routes (no route / order-file / place-order call)",
          not re.search(r"\.route\(|place_order|order_file|\.oif|write_oif|\.submit\(", code))
    live = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    i = live.find("def _second_tick")
    j = live.find("_av2.pc_step(", i)
    k = live.find("self._second_tick(df_full, df1, res, now)")
    r = live.find("self._account_b_tick(df_full, df1, sym, now)")
    check("e. PC hook: inside the paper thread of _second_tick, which runs after LIT's routing and account B's tick",
          i > 0 and j > i and live.find("def run():", i) < j < live.find("threading.Thread(target=run", i) and r < k)
    cm = open(os.path.join(ROOT, "tools", "cloud_monitor.py"), encoding="utf-8").read()
    seg = cm[cm.find("ATLAS v2 PAPER SHADOW"):cm.find("# ---- alerts for events not seen before")]
    check("e. cloud monitor: the shadow block computes only (no route / adapter / order) and keeps the run alive on errors",
          seg and "_av2.step(" in seg and "except Exception" in seg and not re.search(r"route|adapter|ninjatrader", seg.split("\n", 3)[-1]))
    S = batch("H2")
    S["t"] = max(int(r.get("booked_t") or r["entry_t"]) for r in S["ledger"].values())
    for r in S["ledger"].values():
        r["decided_t"] = r["entry_t"]
    N = AV.notices(S, 0)
    check(f"e. pushes: {len(N)} notices, all kind \"second\", titled \"ATLAS v2 PAPER ...\", keys atlas_v2:*",
          N and all(n["kind"] == "second" and n["title"].startswith("ATLAS v2 PAPER") and n["key"].startswith("atlas_v2:") for n in N))
    check("e. pushes OFF by default: cloud sends them only when atlas_v2.push is true",
          "av2_push = _av2.push_on()" in cm and "if av2_push else None" in cm and not AV.push_on())


# ================================================================================================ f. scorecard / card / PC
def part_f():
    bands = AV.load_bands()
    check("f. bands built (research/second/atlas_v2_scorecard.json from the run's 2026 H2 / 2025 path trades)",
          bands and bands.get("run") == AV.RUN and set(bands["bands"]) == {"hunts", "account"}
          and bands["bands"]["hunts"]["expected"]["n_pool"] > 20, (bands or {}).get("run"))
    S = batch("H2")
    sc = AV.scorecard(S, bands)
    nh = sum(1 for r in S["ledger"].values() if r["src"] in AV.HUNTS)
    check(f"f. scorecard on the H2 replay: {nh} hunt trades -> {sc['hunts']['text']} (the research itself must sit inside its band)",
          sc["hunts"]["n"] == nh and sc["hunts"]["kind"] in ("ready", "on_track"), sc["hunts"])
    cd = AV.card(S, bands=bands)
    check("f. card(): paper, never routed, hunt trades / 20, $, eval progress, research numbers",
          cd["paper"] and cd["never_routed"] and cd["progress"]["need"] == 20 and cd["progress"]["hunts_n"] == nh
          and cd["eval"]["status"] in ("open", "failed today") and cd["research"]["H2"]["usd"] == 3859 and len(cd["trades"]) <= 40)
    cp = AV.compact(S)
    check("f. compact() (PC heartbeat second.atlas_v2) small and complete", len(json.dumps(cp, default=str)) < 6000 and cp["eval"] and cp["money"]["n"] == len(S["ledger"]))
    cd2 = AV.card(None, pc=cp, bands=bands)
    check("f. card() from the PC heartbeat when the cloud has none", cd2["source"] == "PC" and cd2["money"]["n"] == len(S["ledger"]))
    # pc_step: one step on a PC-style second run, own file
    tmp = tempfile.mkdtemp(prefix="av2_")
    try:
        p = AV.pc_path(os.path.join(tmp, "live_state.json"))
        run = {"strategies": {k: {"trades": []} for k in AV.SPEC["strategies"]}}
        import pandas as pd
        t0 = 1_792_000_000 - 1_792_000_000 % 300
        df5 = pd.DataFrame({"time": [t0 + 300 * i for i in range(40)], "open": 25000.0, "high": 25010.0, "low": 24990.0, "close": 25000.0, "volume": 1.0})
        S1 = AV.pc_step(p, run, {"trades": [], "state": {}, "signals": []}, df5, None, t0 + 12000)
        check("f. pc_step writes data/live_state_atlas_v2.json (next to the bot state) and returns the state", os.path.exists(p) and S1 and S1.get("ev"), S1)
        from engine import heartbeat
        class _Bot:
            second = {"t": t0, "day": "x", "strategies": {}}
            atlas_v2 = S1
            def second_route_info(self):
                return None
        hb = heartbeat._second(_Bot())
        check("f. heartbeat \"second\" carries atlas_v2 (compact)", hb and (hb.get("atlas_v2") or {}).get("paper") is True, hb)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check(".gitignore: data/live_state_atlas_v2.json", "data/live_state_atlas_v2.json" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read())
    # the renderer (phone + PC copy), node with a stub DOM
    a, b = (os.path.join(ROOT, "tools", "web_public", "secondcore.js"), os.path.join(ROOT, "web_next", "js", "next", "secondcore.js"))
    check("f. secondcore.js phone and PC copies byte-identical (v8)", open(a, "rb").read() == open(b, "rb").read() and "version: 8" in open(a, encoding="utf-8").read())
    node = shutil.which("node")
    if not node:
        check("f. node render (skipped: no node)", True)
    else:
        from engine import second
        blk = second.dashboard_block({"first_run": 1_790_000_000, "t": 1_790_100_000, "strategies": {}})
        blk["atlas_v2"] = cd
        js = ("const fs=require('fs');const window={};const document={head:{appendChild(){}},getElementById(){return null},createElement(){return {}}};"
              f"global.window=window;global.document=document;eval(fs.readFileSync({json.dumps(a)},'utf8'));const U=window.SecondUI;const el={{innerHTML:''}};"
              f"const S={json.dumps(blk, default=str)};U.atlas(el,S,{{}});const h=el.innerHTML;"
              "console.log(JSON.stringify({fail:h.includes('failed to draw'),card:h.includes('ATLAS v2 (paper shadow)'),n:h.includes(' / 20'),"
              "never:h.includes('never routed'),ev:h.includes('Shadow eval'),v:U.version}));")
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            o = {"err": r.stderr[-400:]}
        check("f. SecondUI.atlas draws the ATLAS v2 card (hunt trades / 20, never routed, shadow eval)",
              o.get("card") and o.get("n") and o.get("never") and o.get("ev") and not o.get("fail") and o.get("v") == 8, o)
    idx = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    sw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    check("f. phone loads secondcore.js?v=8, service worker cache le-public-v31 or later", "secondcore.js?v=8" in idx
          and int(__import__("re").search(r"le-public-v(\d+)", sw).group(1)) >= 31)


# ================================================================================================ g. sparse checkout + cloud dry run
def sparse_patterns():
    wf = open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8").read()
    m = re.search(r"sparse-checkout: \|\n((?:\s{12}\S.*\n)+)", wf)
    return [l.strip() for l in m.group(1).splitlines() if l.strip()] if m else []


def covered(path, pats):
    p = "/" + path.replace(os.sep, "/")
    for x in pats:
        if x.endswith("/") and p.startswith(x):
            return True
        if fnmatch.fnmatchcase(p, x):
            return True
    return False


def part_g(cloud=True):
    pats = sparse_patterns()
    need = ["engine/atlas_v2.py", "engine/account_b.py", "engine/second_scorecard.py", "second_model.json",
            "research/second/atlas_v2_scorecard.json", f"research/runs/{AV.RUN}.json", "research/stophunt/sh_asia_resweep.json",
            "research/stophunt/sh_trend_idm5.json", "tools/cloud_monitor.py", "data/NQ_5m.csv", "data/NQ_1m.csv", "live_model.json"]
    miss = [p for p in need if not covered(p, pats)]
    check(f"g. cloud-monitor.yml sparse checkout covers every file the shadow reads ({len(need)})", pats and not miss, miss)
    if not cloud:
        return
    tmp = tempfile.mkdtemp(prefix="av2_cloud_")
    # the dry run refreshes the CBOE files in data/ (as the cloud job does): put the repo's copies back afterwards
    keep = {p: open(p, "rb").read() for p in (os.path.join(ROOT, "data", f) for f in ("VIX_1d.csv", "VXN_1d.csv", "CBOE_vol_1d.csv"))
            if os.path.exists(p)}
    try:
        t0 = time.time()
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join("tools", "cloud_monitor.py"), "--out", tmp], cwd=ROOT,
                           capture_output=True, text=True, timeout=1500)
        st = json.load(open(os.path.join(tmp, "state.json"), encoding="utf-8")) if os.path.exists(os.path.join(tmp, "state.json")) else {}
        a = st.get("atlas_v2") or {}
        check(f"g. cloud dry run ({time.time() - t0:.0f} s): exit 0, state \"atlas_v2\" written (paper, never routed, eval {(a.get('ev') or {}).get('n')})",
              r.returncode == 0 and a.get("v") == AV.VERSION and a.get("paper") and a.get("never_routed") and not a.get("error")
              and "atlas v2 shadow failed" not in r.stdout, (r.returncode, r.stdout[-600:], r.stderr[-600:], a.get("error")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for p, b in keep.items():
            with open(p, "wb") as fh:
                fh.write(b)


def main():
    t0 = time.time()
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
    part_g(cloud="--no-cloud" not in sys.argv)
    ok = all(r for _, r in RESULTS)
    print(f"\n{sum(1 for _, r in RESULTS if r)}/{len(RESULTS)} passed in {time.time() - t0:.0f} s -> {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
