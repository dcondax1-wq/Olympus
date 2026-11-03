"""Run the search on every root and turn it into DAPHNE's JSON, the top rules in plain words, and run-library runs.

Money columns, every period: $ per trade per MNQ micro (after $1.90 a round trip), win %, trades a week, $ a month at 1
micro, and $ a month at the bot's size (micros = BOT_RISK_USD / the stop's $ per micro, 1..40: a wider stop means fewer
micros, as the live bot sizes).

"Holds out of sample": the rule's test-period (2025-01-01 onwards) mean beats its root's test mean AND is above $0 a trade,
on at least MIN_TEST_N test trades. A placebo search on shuffled conditions gives the rate that chance alone reaches.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tools.strategytree import features as fx
from tools.strategytree import roots as rx
from tools.strategytree import search as sx
from tools.strategytree.sessions import Market, TEST_START, TRAIN_END, YEAR_START, period_of

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT_DIR, "research", "strategytree")
PAGE_JSON = os.path.join(ROOT_DIR, "tools", "web_public", "tree", "tree.json")

NAME = "DAPHNE"
BOT_RISK_USD = 282.0           # LIT's median $ at risk per trade in 2026 (run lit_live): "the bot's size"
MAX_MICROS = 40
MIN_TEST_N = 10
FEATURED = 12                  # roots with a full tree on the page (the seeds)
NODE_QUOTA = 950               # nodes drawn per featured tree (12 x 950 ~ 11.4k)
TOP_N = 10
MIN_TRAIN_COVERAGE = 0.5       # a feature known on fewer train trades than this is left out of the search
PERIODS = ("train", "test", "y2026")
PERIOD_LABELS = {"train": f"train <= {TRAIN_END}", "test": f"test {TEST_START} on", "y2026": f"2026 ({YEAR_START} on)"}
NODE_COLS = ["id", "parent", "cond", "depth", "n", "excess", "score", "bound", "status", "best", "oos", "oos_n"]


@dataclass
class RootResult:
    """One root after the search: its trades (all periods), condition codes, period masks and the searched tree."""
    root: rx.Root
    trades: pd.DataFrame
    codes: np.ndarray
    periods: dict              # name -> bool mask over trades
    tree: sx.Tree
    cmask: np.ndarray          # (C x n) masks over ALL trades of the root


def bot_qty(risk_pts: np.ndarray) -> np.ndarray:
    """Micros at the bot's size: the risk budget over the stop's $ per micro, at least 1, at most MAX_MICROS."""
    q = np.floor(BOT_RISK_USD / (np.asarray(risk_pts, dtype=float) * rx.POINT_USD))
    return np.clip(q, 1, MAX_MICROS).astype(int)


def money(tr: pd.DataFrame, sessions: int) -> dict:
    """Headline money of a set of trades over a span of `sessions` trading days."""
    n = len(tr)
    if not n:
        return {"n": 0}
    pnl = tr["pnl"].values
    months, weeks = sessions / 21.0, sessions / 5.0
    bot = pnl * bot_qty(tr["risk_pts"].values)
    loss = -pnl[pnl < 0].sum()
    return {"n": n, "mean": round(float(pnl.mean()), 2), "win": round(100 * float((pnl > 0).mean()), 1),
            "pf": round(float(pnl[pnl > 0].sum() / loss), 2) if loss else None,
            "tpw": round(n / weeks, 2), "mo_1": round(float(pnl.sum()) / months), "mo_bot": round(float(bot.sum()) / months),
            "net_bot": round(float(bot.sum())), "stop": round(float(tr["risk_pts"].median()), 1)}


def session_counts(m: Market) -> dict:
    """Trading sessions in each judged period (the denominators of trades a week and $ a month)."""
    p = period_of(m.days["date"])
    return {k: int(v.sum()) for k, v in p.items()}


def active_conditions(codes_train: np.ndarray, conds: list) -> tuple[list, list]:
    """Conditions of the features known on enough train trades, and the names of the features left out."""
    known = (codes_train >= 0).mean(axis=0) if len(codes_train) else np.zeros(len(fx.FEATURES))
    skipped = [f.name for i, f in enumerate(fx.FEATURES) if known[i] < MIN_TRAIN_COVERAGE]
    keep = [c for c in conds if fx.FEATURES[c.feature].name not in skipped]
    return keep, skipped


@dataclass
class Prepared:
    """Every root's trades and condition codes, and the conditions the search may use (built once, searched many times)."""
    roots: list                # [(Root, trades, codes)]
    conds: list
    skipped: list
    edges: dict


def prepare(m: Market, roots: list | None = None) -> Prepared:
    """Trades and condition codes of every root (roots sharing a level and mode share their entries)."""
    edges = fx.train_edges(m.days)
    signals: dict = {}
    raw = []
    for r in roots or rx.all_roots():
        tr = rx.root_trades(m, r, signals)
        raw.append((r, tr, fx.encode(m, tr, edges)))
    train_codes = np.vstack([c[period_of(tr["date"])["train"]] for _, tr, c in raw if len(tr)])
    conds, skipped = active_conditions(train_codes, fx.conditions())
    return Prepared(raw, conds, skipped, edges)


def _search_job(job) -> sx.Tree:
    x, masks, cfeat, cfg = job
    return sx.search(x, masks, cfeat, cfg)


def search_all(prep: Prepared, cfg: sx.SearchConfig, placebo_seed: int | None = None, procs: int = 1) -> list:
    """The searched tree of every root, on train trades only. placebo_seed shuffles each root's condition rows (the
    same shuffle for train and test): the conditions then carry no information, which shows what chance alone finds."""
    cfeat = np.array([c.feature for c in prep.conds], dtype=int)
    staged = []
    for i, (r, tr, codes) in enumerate(prep.roots):
        if placebo_seed is not None and len(codes):
            codes = codes[np.random.default_rng([placebo_seed, i]).permutation(len(codes))]
        per = period_of(tr["date"])
        staged.append((r, tr, codes, per, fx.condition_masks(codes, prep.conds)))
    jobs = [(tr["pnl"].values[per["train"]], cmask[:, per["train"]], cfeat, cfg) for _, tr, _, per, cmask in staged]
    if procs > 1:
        from multiprocessing import Pool
        with Pool(procs) as pool:
            trees = pool.map(_search_job, jobs, chunksize=1)
    else:
        trees = [_search_job(j) for j in jobs]
    return [RootResult(r, tr, codes, per, tree, cmask) for (r, tr, codes, per, cmask), tree in zip(staged, trees)]


def node_keep(rr: RootResult, node: int) -> np.ndarray:
    """Bool mask over all of the root's trades for the rule at `node`."""
    keep = np.ones(len(rr.trades), dtype=bool)
    for c in rr.tree.conds_of(node):
        keep &= rr.cmask[c]
    return keep


def oos_excess(rr: RootResult, node: int, period: str = "test") -> tuple[int, float]:
    """(n, mean - root mean) of the node's trades in a period."""
    per = rr.periods[period]
    x = rr.trades["pnl"].values
    keep = node_keep(rr, node) & per
    n = int(keep.sum())
    if not n or not per.any():
        return n, float("nan")
    return n, float(x[keep].mean() - x[per].mean())


def holds(rr: RootResult, node: int, period: str = "test", min_n: int = MIN_TEST_N) -> bool:
    """The out-of-sample test: more than the root AND more than $0 a trade, on min_n+ trades of the period."""
    n, ex = oos_excess(rr, node, period)
    if n < min_n or not math.isfinite(ex):
        return False
    return bool(ex > 0 and rr.trades["pnl"].values[node_keep(rr, node) & rr.periods[period]].mean() > 0)


def honesty(results: list[RootResult]) -> dict:
    """How the best rules (one per root, when the root itself is not the best) do out of sample: how many hold in the
    test (and in 2026 alone, on half the trades), and their average test excess over their root ($ a trade per micro,
    on the ones with MIN_TEST_N+ test trades)."""
    found = [rr for rr in results if rr.tree.best != 0]
    ok = [rr for rr in found if holds(rr, rr.tree.best)]
    ok26 = [rr for rr in found if holds(rr, rr.tree.best, "y2026", MIN_TEST_N // 2)]
    ex = [e for n, e in (oos_excess(rr, rr.tree.best) for rr in found) if n >= MIN_TEST_N and math.isfinite(e)]
    return {"nodes": sum(len(rr.tree) - 1 for rr in results), "roots": len(results), "best_rules": len(found),
            "hold": len(ok), "hold_pct": round(100 * len(ok) / len(found), 1) if found else None,
            "hold_2026": len(ok26), "mean_test_excess": _r2(float(np.mean(ex))) if ex else None}


def _r2(v):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), 2)


def rule_card(rr: RootResult, node: int, conds: list, sessions: dict) -> dict:
    """A rule (root + the conditions to `node`) with its money in every period and the plain-language text."""
    keep = node_keep(rr, node)
    path = rr.tree.conds_of(node)
    steps = [conds[c].label for c in path]
    text = rr.root.text + (", only when " + "; ".join(conds[c].text for c in path) if path else "")
    out = {"root": rr.root.id, "key": rr.root.key, "node": node, "steps": steps, "text": text,
           "score": _r2(rr.tree.score[node]), "bound": _r2(rr.tree.bound[node]), "holds": holds(rr, node)}
    for p in PERIODS:
        base = money(rr.trades[rr.periods[p]], sessions[p])
        rule = money(rr.trades[keep & rr.periods[p]], sessions[p])
        rule["excess"] = _r2(rule["mean"] - base["mean"]) if rule.get("n") and base.get("n") else None
        out[p] = rule
    return out


def top_rules(results: list[RootResult], conds: list, sessions: dict, k: int = TOP_N) -> list[dict]:
    """The best rule of each root, best train score first, one per level and direction (the 4 target / horizon
    variants of a setup find near-identical rules)."""
    ranked = sorted((rr for rr in results if rr.tree.best != 0), key=lambda rr: -rr.tree.score[rr.tree.best])
    out, seen = [], set()
    for rr in ranked:
        if rr.root.key in seen:
            continue
        seen.add(rr.root.key)
        out.append(rule_card(rr, rr.tree.best, conds, sessions))
        if len(out) == k:
            break
    return out


def sample_nodes(tree: sx.Tree, quota: int, seed: int) -> list[int]:
    """Node ids for the page, in creation (search) order: the best path, then seeded random nodes, each with all its
    ancestors, until `quota`. Every kept node's parent is kept, so the sample is a tree."""
    keep = set(tree.path(tree.best))
    for i in np.random.default_rng(seed).permutation(len(tree)):
        if len(keep) >= quota:
            break
        keep.update(tree.path(int(i)))
    return sorted(keep)


def _tree_rows(rr: RootResult, quota: int, seed: int) -> list:
    """The page's node sample, one row per node (see NODE_COLS)."""
    t = rr.tree
    best_path = set(t.path(t.best))
    rows = []
    for i in sample_nodes(t, quota, seed):
        tn, tex = oos_excess(rr, i)
        rows.append([i, t.parent[i], t.cond[i], t.depth[i], t.n[i], _r2(t.mean[i] - t.root_mean), _r2(t.score[i]),
                     _r2(t.bound[i]), t.status[i], int(i in best_path), _r2(tex), tn])
    return rows


def build(m: Market, cfg: sx.SearchConfig, roots: list | None = None, placebos: int = 1, procs: int = 1) -> dict:
    """Everything DAPHNE shows for the real market, as one JSON-ready dict (the key "_results" keeps the searched roots
    for save_runs)."""
    span = {"first_day": str(m.days["date"].iloc[0]), "last_day": str(m.days["date"].iloc[-1])}
    return assemble(prepare(m, roots), session_counts(m), cfg, placebos, procs, span)


def assemble(prep: Prepared, sessions: dict, cfg: sx.SearchConfig, placebos: int = 1, procs: int = 1,
             extra_meta: dict | None = None, quota: int = NODE_QUOTA) -> dict:
    """Search prepared roots (and `placebos` shuffled copies) and lay the result out as DAPHNE's JSON."""
    t0 = time.time()
    conds, skipped, edges = prep.conds, prep.skipped, prep.edges
    results = search_all(prep, cfg, procs=procs)
    real = honesty(results)
    placebo = [honesty(search_all(prep, cfg, placebo_seed=1000 + s, procs=procs)) for s in range(placebos)]
    top = top_rules(results, conds, sessions)
    order = sorted(range(len(results)), key=lambda i: -results[i].tree.score[results[i].tree.best])
    index = {rr.root.id: i for i, rr in enumerate(results)}
    featured = [index[r["root"]] for r in top][:FEATURED]          # the seeds: the top rules' roots, then the next best
    featured += [i for i in order if i not in featured][:FEATURED - len(featured)]
    roots_out, trees = [], {}
    for i, rr in enumerate(results):
        st = rr.tree.stats()
        card = rule_card(rr, rr.tree.best, conds, sessions)
        base = {p: money(rr.trades[rr.periods[p]], sessions[p]) for p in PERIODS}
        roots_out.append({"id": rr.root.id, "key": rr.root.key, "level": rr.root.level, "mode": rr.root.mode,
                          "dir": rr.root.dir, "target_r": rr.root.target_r, "horizon": rr.root.horizon,
                          "text": rr.root.text, "base": base, "tree": st, "best": card,
                          "best_path": rr.tree.path(rr.tree.best), "featured": i in featured})
        if i in featured:
            trees[rr.root.id] = _tree_rows(rr, quota, seed=i)
    nodes = real["nodes"]
    cut = sum(r["tree"]["cut"] for r in roots_out)
    meta = {"name": NAME, "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0),
            "complete": sum(r["tree"]["open"] == 0 for r in roots_out),
            "data": "TradingView CME NQ1! 5m (back-adjusted), ES1! 5m from 2025-04, CBOE VIX",
            "train_end": TRAIN_END, "test_start": TEST_START, "year_start": YEAR_START, "periods": PERIOD_LABELS,
            "sessions": sessions, "criterion": "mean excess $ per trade per micro over the root, x n/(n+k)",
            "costs": f"${rx.COST_RT:.2f} a round trip per micro, ${rx.POINT_USD:g} a point",
            "bot_risk_usd": BOT_RISK_USD, "min_n": cfg.min_n, "shrink_k": cfg.shrink_k, "depth": cfg.max_depth,
            "max_expand": cfg.max_expand, "min_test_n": MIN_TEST_N, "skipped_features": skipped, "edges": edges,
            "nodes": nodes, "cut": cut, "cut_pct": round(100 * cut / nodes, 1) if nodes else 0.0,
            "shown": sum(len(v) for v in trees.values()), "paper_only": True, "demo": False, **(extra_meta or {})}
    return {"v": 1, "meta": meta,
            "features": [{"name": f.name, "labels": list(f.labels), "ordinal": f.ordinal, "text": f.text}
                         for f in fx.FEATURES],
            "conds": [[c.feature, c.lo, c.hi, c.label, c.text] for c in conds],
            "node_cols": NODE_COLS,
            "status_names": list(sx.STATUS_NAMES),
            "roots": roots_out, "trees": trees, "top": top,
            "honesty": {"real": real, "placebo": placebo,
                        "rule": f"holds = test mean beats the root's test mean and is above $0, on {MIN_TEST_N}+ test trades"},
            "_results": results}


def beats_chance(doc: dict) -> bool:
    """The real hold rate beats every placebo run by more than 10 points (otherwise the search found chance)."""
    real, plc = doc["honesty"]["real"], doc["honesty"]["placebo"]
    return bool(plc) and real["hold_pct"] is not None and real["hold_pct"] > max(p["hold_pct"] or 0 for p in plc) + 10


def jarvis_card(doc: dict, now: float | None = None) -> dict:
    """The live card for Jarvis (docs/JARVIS_APPS.md): plain text, short fields, the theme colour."""
    real, plc, meta = doc["honesty"]["real"], doc["honesty"]["placebo"], doc["meta"]
    nodes = real["nodes"]
    nodes_txt = f"{nodes / 1e6:.2f}M" if nodes >= 1e6 else f"{nodes:,}"
    chance = beats_chance(doc)
    placebo = max((p["hold_pct"] or 0 for p in plc), default=0)
    lines = []
    if doc["top"]:
        t = doc["top"][0]
        lines.append(f"#1 {t['key']}: train {_usd(t['train'].get('mean'))}, test {_usd(t['test'].get('mean'))} a trade per micro")
    lines.append("Beats chance out of sample" if chance else "Out of sample it is chance level: paper only")
    return {"v": 1, "name": NAME,
            "status": {"level": "ok" if chance else "warn",
                       "label": f"{real['hold']}/{real['best_rules']} rules hold, {'beats' if chance else 'no better than'} chance"[:48]},
            "kpis": [{"label": "Nodes searched", "value": nodes_txt}, {"label": "Cut by the bound", "value": f"{meta['cut_pct']}%"},
                     {"label": "Hold vs placebo", "value": f"{real['hold_pct']:.0f}% vs {placebo:.0f}%"}],
            "lines": lines, "t": int(now if now is not None else time.time()), "open": "#top", "theme": "#030705"}


def _usd(x) -> str:
    return "n/a" if x is None else f"{'-' if x < 0 else '+'}${abs(x):,.2f}"


def write(doc: dict, out_dir: str = OUT_DIR, page_json: str | None = PAGE_JSON) -> str:
    """Write tree.json (compact) to out_dir and, when given, the page's copy and its jarvis.json. Returns the path."""
    os.makedirs(out_dir, exist_ok=True)
    body = json.dumps({k: v for k, v in doc.items() if not k.startswith("_")}, separators=(",", ":"), allow_nan=False)
    path = os.path.join(out_dir, "tree.json")
    for p in [path] + ([page_json] if page_json else []):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
    if page_json:
        with open(os.path.join(os.path.dirname(page_json), "jarvis.json"), "w", encoding="utf-8") as fh:
            json.dump(jarvis_card(doc), fh, indent=1, ensure_ascii=False)
    return path


def runlib_trades(rr: RootResult, node: int) -> list[dict]:
    """The rule's trades at the bot's size, as tools/runlib stores them."""
    tr = rr.trades[node_keep(rr, node)]
    q = bot_qty(tr["risk_pts"].values)
    out = []
    for (_, t), qty in zip(tr.iterrows(), q.tolist()):        # plain Python numbers: runlib stores them as JSON
        risk_usd = float(t["risk_pts"]) * rx.POINT_USD * qty
        pnl = float(t["pnl"]) * qty
        out.append({"day": t["date"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "r": round(pnl / risk_usd, 3), "pnl": round(pnl, 2), "risk_pts": float(t["risk_pts"]), "qty": int(qty),
                    "risk_usd": round(risk_usd, 2), "half": False, "exit": t["reason"], "trigger": rr.root.key,
                    "mfe": float(t["mfe_r"]), "mae": float(t["mae_r"]), "bars_held": int(t["bars_held"]),
                    "regime": None, "mult": 1.0, "low": -min(float(t["mae_r"]), 1.0) * risk_usd})
    return out


def save_runs(doc: dict, m: Market) -> list[str]:
    """Store the #1 rule and the top-5 basket in the run library (research/runs/), judged like every other run."""
    from tools import runlib as rl
    results = {rr.root.id: rr for rr in doc["_results"]}
    sessions = list(m.days["date"])
    real, placebo = doc["honesty"]["real"], doc["honesty"]["placebo"]
    chance = beats_chance(doc)
    plc = " / ".join(f"{p['hold_pct']}%" for p in placebo) or "no placebo run"
    common = (f"{real['nodes']:,} nodes searched over {real['roots']} roots, {doc['meta']['cut_pct']}% cut by the bound; "
              f"{real['hold']}/{real['best_rules']} best rules hold out of sample ({real['hold_pct']}%) vs {plc} with "
              f"shuffled conditions: {'beats' if chance else 'no better than'} chance.")
    ids = []
    picks = [("strategytree_top1", doc["top"][:1], "DAPHNE #1 rule"), ("strategytree_top5", doc["top"][:5], "DAPHNE top-5 basket")]
    for run_id, cards, title in picks:
        if not cards:
            continue
        trades = sorted((t for c in cards for t in runlib_trades(results[c["root"]], c["node"])), key=lambda t: t["entry_t"])
        S = rl.score(trades, sessions)
        held = all(c["holds"] for c in cards)
        if held:
            verdict = ("Holds out of sample, " + ("and the search beats chance" if chance else
                       "but the search as a whole is chance level, so treat it as luck"))
        else:
            verdict = "Does not hold out of sample" + ("" if chance else "; the search as a whole is chance level")
        verdict += ". Paper only, never routed. " + common
        rl.save(run_id, title, "other", "Does a branch-and-bound condition search on plain level trades find an edge "
                "that holds after 2024?", params={"rules": [c["text"] for c in cards], "min_n": doc["meta"]["min_n"]},
                trades=trades, scored=S, status="promising" if held and chance else "rejected", verdict=verdict,
                notes="Train <= 2024-12-31 (so 2021-24 is in-sample), test 2025-26. Sized at $282 risk a trade.",
                writeup="2026-11-03-strategy-tree.md", tags=["strategytree", "daphne", "paper"])
        ids.append(run_id)
    return ids
