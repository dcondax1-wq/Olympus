"""ZEUS learn night, the cloud half (night-learnloop 2026-11-19; owner: "our bot that is constantly learning both / all of our
strategies ... more data pulls, smarter and faster thinking bot"). ONE command the lead runs after the PC's nightly run
(the PC learns from ~17:05 ET: engine/datapipe -> engine/zeus_learn; docs/LEARN_LOOP.md "ZEUS learned"):

    python tools/learn_night.py                 # pull the PC's fresh days, re-run edge health, the anatomy, the ZEUS Lab; the card,
                                                # the Decide proposals; then one table of what changed
    python tools/learn_night.py --no-pull       # use data/pc_days/ as it is (no ntfy request)
    python tools/learn_night.py --wait 0        # only ask the PC (it answers within ~5 min outside 01:50-16:00 ET); run again later
    python tools/learn_night.py --skip lab,anatomy  [--full: the anatomy's rules too, slow]  [--fetch: CBOE VIX first]
    python tools/learn_night.py --dry-run       # the plan only, nothing run or written
Heavy steps (edge, anatomy, lab) load the full backtests: run the whole command as `/home/user/heavy.sh python tools/learn_night.py`.

Steps (each soft and its own process with a time limit: one failing never stops the rest):
  1 pull     tools/data_pull.py --latest [--wait N]: the PC's days -> data/pc_days/, newer NQ / ES bars -> data/, GC / SI around the
             K8 windows -> data/metals/, the PC's proposals -> research/zeus_queue.jsonl
  2 edge     tools/edge_health.py [--fetch]: the edge light -> research/lab/edge_health.json + tools/web_public/edge.json
  3 anatomy  tools/win_loss_anatomy.py build / explain / page (+ rules with --full) -> research/anatomy/, tools/web_public/why/why.json
  4 lab      tools/zeus_lab.py run --publish -> tools/web_public/business/lab.json (the Lab page)
  5 learned  the PC's newest learn.json (data/pc_days/<day>/learn.json = engine/zeus_learn.public), else engine/zeus_learn.build
             on the pulled days -> tools/web_public/hub/learned.json (the ZEUS page card's cloud copy, with its date)
  6 decide   the PC's proposals -> tools/web_public/business/decisions.json (new ids only, status open, the existing schema:
             a "yes" = Claude TESTS it under CLAUDE.md "Strategy changes"; nothing live changes without proof + another yes)
  7 report   before / after -> research/learn/night_cloud.json (gitignored) + the printed table
Research only: never trades, never touches live_model*.json (hashed before / after, a change is reported loudly).
Tests: python -X utf8 -m tests.test_learn_night (fake steps, no network).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PC_DAYS = os.path.join(ROOT, "data", "pc_days")
CARD = os.path.join(ROOT, "tools", "web_public", "hub", "learned.json")
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
EDGE = os.path.join(ROOT, "research", "lab", "edge_health.json")
WHY = os.path.join(ROOT, "tools", "web_public", "why", "why.json")
LAB = os.path.join(ROOT, "tools", "web_public", "business", "lab.json")
REPORT = os.path.join(ROOT, "research", "learn", "night_cloud.json")
PROTECTED = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json", "data/account_b.json")
STEPS = ("pull", "edge", "anatomy", "lab", "learned", "decide")
LIMIT_S = {"pull": 1500, "edge": 1200, "anatomy": 2400, "lab": 2400}
CARD_MAX_BYTES = 6000
DECIDE_MAX_NEW = 3                       # proposals added per night at most (the owner's card stays short)
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{1,39}")


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, ensure_ascii=False, default=str)
        fh.write("\n")
    os.replace(tmp, path)


def usd(v) -> str:
    v = round(float(v or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def hashes(root: str = ROOT) -> dict:
    out = {}
    for rel in PROTECTED:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[rel] = None
    return out


def _last_time(path) -> str | None:
    """The newest bar of a data CSV (its last line's time, ET text), read from the file's end only."""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 400))
            last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
        t = int(float(last.split(",")[0]))
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(t, ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


# ================================================================================================ the before / after picture
def snapshot(root: str = ROOT) -> dict:
    """The numbers the night can move, read from the files (never re-computed)."""
    d = os.path.join(root, "data")
    e = (_read_json(os.path.join(root, "research", "lab", "edge_health.json"), {}) or {}).get("card") or {}
    w = _read_json(os.path.join(root, "tools", "web_public", "why", "why.json"), {}) or {}
    lab = _read_json(os.path.join(root, "tools", "web_public", "business", "lab.json"), {}) or {}
    dec = _read_json(os.path.join(root, "tools", "web_public", "business", "decisions.json"), {}) or {}
    card = _read_json(os.path.join(root, "tools", "web_public", "hub", "learned.json"), {}) or {}
    pulled = sorted(p for p in os.listdir(os.path.join(d, "pc_days")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)) \
        if os.path.isdir(os.path.join(d, "pc_days")) else []
    met = {s: _last_time(os.path.join(d, "metals", f"{s}_1m.csv")) for s in ("GC", "SI")}
    return {"NQ 1m to": _last_time(os.path.join(d, "NQ_1m.csv")), "NQ 5m to": _last_time(os.path.join(d, "NQ_5m.csv")),
            "ES 5m to": _last_time(os.path.join(d, "ES_5m.csv")),
            "metals to": ", ".join(f"{k} {v}" for k, v in met.items() if v) or None,
            "PC days pulled": f"{len(pulled)} ({pulled[0]} .. {pulled[-1]})" if pulled else "0",
            "Zlarior edge": f"{e.get('light')} (PF40 {e.get('pf40')}, data to {e.get('data_to')})" if e else None,
            "ATLAS edge": (f"{(e.get('atlas') or {}).get('light')} (R-PF40 {(e.get('atlas') or {}).get('pf_r40')})" if e.get("atlas") else None),
            "Why page": f"built {w.get('built')}, data to {w.get('data_to')}" if w else None,
            "ZEUS Lab": (", ".join(f"{k} {v}" for k, v in sorted((lab.get("counts") or {}).items())) + f" (data to {lab.get('data_to')})") if lab else None,
            "Decide card": f"{sum(1 for i in dec.get('items') or [] if i.get('status', 'open') == 'open')} open" if dec else None,
            "ZEUS learned": (f"{card.get('day')}: {card.get('line')}"[:160]) if card else None}


def changes(before: dict, after: dict) -> list:
    return [{"what": k, "before": before.get(k), "after": after.get(k), "changed": before.get(k) != after.get(k)}
            for k in after]


def table(rows: list) -> str:
    out = ["| What | Before | After |", "|---|---|---|"]
    for r in rows:
        out.append(f"| {r['what']}{' (new)' if r['changed'] else ''} | {r['before'] or '-'} | {r['after'] or '-'} |")
    return "\n".join(out)


# ================================================================================================ the steps
def run_cmd(cmd: list, limit_s: float, say=print) -> dict:
    """One step as its own process (python -X utf8 ...), a hard time limit, the tail of its output. Never raises."""
    t0 = time.monotonic()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "2")}
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", *cmd], cwd=ROOT, capture_output=True, text=True, timeout=limit_s, env=env)
        tail = (r.stdout or "").strip().splitlines()[-8:] + [x for x in (r.stderr or "").strip().splitlines()[-3:] if r.returncode]
        return {"ok": r.returncode == 0, "rc": r.returncode, "s": round(time.monotonic() - t0, 1), "tail": tail}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": None, "s": round(time.monotonic() - t0, 1), "tail": [f"stopped after {limit_s:.0f} s"]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rc": None, "s": round(time.monotonic() - t0, 1), "tail": [f"{e.__class__.__name__}: {e}"]}


def plan(a) -> list:
    """[(step, [cmd ...])] of tonight's run (learned + decide run in this process)."""
    skip = {x.strip() for x in (a.skip or "").split(",") if x.strip()}
    out = []
    if "pull" not in skip and not a.no_pull:
        out.append(("pull", [["tools/data_pull.py", "--latest"] + (["--wait", str(a.wait)] if a.wait is not None else [])]))
    if "edge" not in skip:
        out.append(("edge", [["tools/edge_health.py"] + (["--fetch"] if a.fetch else [])]))
    if "anatomy" not in skip:
        out.append(("anatomy", [["tools/win_loss_anatomy.py", c] for c in (("build", "explain", "rules", "page") if a.full
                                                                             else ("build", "explain", "page"))]))
    if "lab" not in skip:
        out.append(("lab", [["tools/zeus_lab.py", "run", "--publish"]]))
    for s in ("learned", "decide"):
        if s not in skip:
            out.append((s, []))
    return out


def newest_learn(days_dir: str = PC_DAYS) -> dict | None:
    """The PC's newest learn.json among the pulled days (engine/zeus_learn.public), or None."""
    try:
        names = sorted((p for p in os.listdir(days_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)), reverse=True)
    except OSError:
        return None
    for d in names:
        j = _read_json(os.path.join(days_dir, d, "learn.json"), None)
        if isinstance(j, dict) and j.get("kind") == "zeus-learned" and j.get("day"):
            return j
    return None


def card_doc(S: dict, src: str) -> dict:
    """tools/web_public/hub/learned.json: what the ZEUS page's card shows (hidden bots already left out), small."""
    bots = []
    for k, b in (S.get("bots") or {}).items():
        if b.get("hidden"):
            continue
        td, r20 = b.get("today") or {}, ((b.get("roll") or {}).get("20") or {})
        row = {"key": k, "name": b.get("name"), "today_n": td.get("n"), "today_usd": td.get("usd"), "paper": td.get("paper"),
               "edge": (b.get("edge") or {}).get("light"), "verdict": b.get("verdict"),
               "last20": {x: r20.get(x) for x in ("n", "win", "pf", "usd")}, "why": (b.get("anatomy") or {}).get("say") or None}
        if k != "k8":       # night-atlasfills 2026-11-20: "real slippage so far" (engine/zeus_learn.fills, the PC's real fills)
            try:
                from tools import fill_cost
                fc = fill_cost.block(b.get("fills"))
                if fc:
                    row["fills"] = fc
            except Exception:  # noqa: BLE001
                pass
        bots.append(row)
    doc = {"v": 1, "kind": "zeus-learned-card", "day": S.get("day"), "t": int(S.get("t") or 0),
           "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "src": src, "line": S.get("line"),
           "market": (S.get("regime") or {}).get("tag"), "bots": bots, "proposals": len(S.get("proposals") or []),
           "note": "Research + advice only: ZEUS changed nothing. Ideas go to the Decide card; nothing live changes without your yes."}
    try:
        from engine import hidden_bots
        doc = hidden_bots.scrub(doc)
    except Exception:
        pass
    while len(json.dumps(doc, ensure_ascii=False).encode("utf-8")) > CARD_MAX_BYTES and doc["bots"]:
        for b in doc["bots"]:
            b.pop("why", None)
        if len(json.dumps(doc, ensure_ascii=False).encode("utf-8")) > CARD_MAX_BYTES:
            doc["bots"] = doc["bots"][:-1]
    return doc


def step_learned(days_dir: str = PC_DAYS, card_path: str = CARD, root: str = ROOT) -> dict:
    S = newest_learn(days_dir)
    src = "the PC's nightly learning (engine/zeus_learn)"
    if S is None:
        from engine import datapipe, zeus_learn
        days = datapipe.load_days(days_dir, n=120)
        if not days:
            return {"ok": False, "why": "no PC days pulled yet (python tools/data_pull.py --latest)"}
        S = zeus_learn.build(days, days_dir, root=root, k8={}, brk={})
        S["bots"] = {k: {**v, "hidden": v.get("hidden") or k in zeus_learn.hidden(root)} for k, v in S["bots"].items()}
        S["line"] = zeus_learn.line(S)
        src = "rebuilt in the cloud from the PC's trades + bars (no twin / breaker / K8 here)"
    doc = card_doc(S, src)
    old = _read_json(card_path, {}) or {}
    if {k: v for k, v in old.items() if k != "built"} != {k: v for k, v in doc.items() if k != "built"}:
        _write_json(card_path, doc)
    return {"ok": True, "day": doc["day"], "line": doc["line"], "src": src, "proposals": S.get("proposals") or []}


def decide_item(p: dict) -> dict | None:
    """A ZEUS learned proposal -> one Decide-card item (tests/test_decide part a schema), or None when it does not fit."""
    pid = str(p.get("id") or "")[:40].lower()
    if not _ID.fullmatch(pid) or not p.get("question") or not p.get("why"):
        return None
    full = p.get("decide_item")                 # a ready Decide item (engine/kalshi_adapt's restore asks): kept as it is, checked
    if isinstance(full, dict) and str(full.get("id")) == pid and "$" in str(full.get("impact")) and full.get("source") \
            and isinstance(full.get("impact_usd"), (int, float)) and set(full.get("options") or []) <= {"yes", "no", "later"}:
        try:
            from engine.datapipe import scrub_text
            words = {k: scrub_text(str(full.get(k) or ""))[:240] for k in ("question", "why", "impact")}
        except Exception:
            words = {k: str(full.get(k) or "")[:240] for k in ("question", "why", "impact")}
        return dict(full, status="open", **words)
    imp = str(p.get("impact") or "Not known until tested: $0 changes before a yes.")
    if "$" not in imp:
        imp += " ($0 changes before a yes.)"
    try:
        from engine.datapipe import scrub_text
        q, why, imp = scrub_text(p["question"])[:200], scrub_text(p["why"])[:240], scrub_text(imp)[:200]
    except Exception:
        q, why, imp = str(p["question"])[:200], str(p["why"])[:240], imp[:200]
    return {"id": pid, "question": q, "why": why, "impact": imp, "impact_usd": 0, "options": ["yes", "no", "later"], "status": "open",
            "source": f"ZEUS learned on the PC, {p.get('day')} (engine/zeus_learn.py)",
            "applies": "A yes = Claude tests it under CLAUDE.md Strategy changes (Jan-Jun pick, Jul-Oct check, costs in); nothing "
                       "live changes unless it passes and you say yes again",
            "added": str(p.get("day") or dt.date.today().isoformat()), "from": "zeus_learn"}


def step_decide(proposals: list, path: str = DECISIONS, max_new: int = DECIDE_MAX_NEW, hide=None) -> dict:
    """New proposals onto the Decide card: an id already there (any status) is never added again; at most max_new a night."""
    doc = _read_json(path, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        return {"ok": False, "why": "decisions.json missing or not the Decide card"}
    have = {str(i.get("id")) for i in doc["items"]}
    hide = set(hide or ())
    add = []
    for p in proposals or []:
        if p.get("bot") in hide:
            continue
        it = decide_item(p)
        if it and it["id"] not in have and len(add) < max_new:
            add.append(it)
            have.add(it["id"])
    if add:
        doc["items"] = doc["items"] + add
        doc["updated"] = dt.date.today().isoformat()
        _write_json(path, doc)
    return {"ok": True, "added": [i["id"] for i in add]}


# ================================================================================================ the night
def run(a, runner=None, say=print, root: str = ROOT, days_dir: str = PC_DAYS, card_path: str = CARD,
        decisions: str = DECISIONS, report: str = REPORT) -> dict:
    runner = runner or run_cmd
    P = plan(a)
    if a.dry_run:
        for s, cmds in P:
            say(f"  {s:8s} " + ("; ".join("python " + " ".join(c) for c in cmds) if cmds else "(in this process)"))
        return {"plan": [s for s, _ in P]}
    h0 = hashes(root)
    before = snapshot(root)
    res, learned = {}, {}
    for s, cmds in P:
        if s == "learned":
            try:
                learned = step_learned(days_dir, card_path, root)
            except Exception as e:  # noqa: BLE001
                learned = {"ok": False, "why": f"{e.__class__.__name__}: {e}"[:200]}
            res[s] = learned
        elif s == "decide":
            try:
                from engine import zeus_learn
                res[s] = step_decide(learned.get("proposals") or [], decisions, hide=zeus_learn.hidden(root))
            except Exception as e:  # noqa: BLE001
                res[s] = {"ok": False, "why": f"{e.__class__.__name__}: {e}"[:200]}
        else:
            rs = []
            for c in cmds:
                say(f"  [..] {s}: python {' '.join(c)}")
                r = runner(c, LIMIT_S.get(s, 1800))
                rs.append(r)
                if s == "pull" and r.get("rc") not in (0, 3):
                    break
            res[s] = {"ok": all(r.get("ok") or (s == "pull" and r.get("rc") == 3) for r in rs), "s": round(sum(r.get("s") or 0 for r in rs), 1),
                      "tail": (rs[-1].get("tail") or [])[-4:] if rs else []}
    after = snapshot(root)
    h1 = hashes(root)
    rows = changes(before, after)
    out = {"t": int(time.time()), "steps": res, "changes": rows, "protected_ok": h0 == h1,
           "learned": learned.get("line"), "decide_added": (res.get("decide") or {}).get("added") or []}
    try:
        _write_json(report, out)
    except Exception:
        pass
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ZEUS learn night (cloud): pull the PC's days, edge health, anatomy, ZEUS Lab, card, Decide")
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--wait", type=float, default=None, help="minutes to wait for the PC's answer (tools/data_pull.py --wait)")
    ap.add_argument("--skip", default="", help="comma list of: " + ", ".join(STEPS))
    ap.add_argument("--full", action="store_true", help="the anatomy's rules too (slow)")
    ap.add_argument("--fetch", action="store_true", help="edge health: refresh CBOE's VIX first")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    out = run(a)
    if a.dry_run:
        return 0
    print()
    print("| Step | Result |")
    print("|---|---|")
    for s, r in out["steps"].items():
        txt = ("ok" if r.get("ok") else "FAILED") + (f" ({r['s']:.0f} s)" if r.get("s") else "")
        if s == "learned":
            txt = (r.get("line") or r.get("why") or "")[:140]
        elif s == "decide":
            txt = (f"+{len(r.get('added') or [])} on the Decide card: {', '.join(r.get('added') or [])}" if r.get("added")
                   else "nothing new for the Decide card") if r.get("ok") else str(r.get("why"))
        elif not r.get("ok") and r.get("tail"):
            txt += ": " + " / ".join(r["tail"][-2:])[:160]
        print(f"| {s} | {txt} |")
    print()
    print(table(out["changes"]))
    if not out["protected_ok"]:
        print("\n!! A live settings file changed during the run: check git diff before shipping (nothing here should write it).")
    print("\nResearch only: nothing here changed a bot, a size or an order.")
    return 0 if out["protected_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
