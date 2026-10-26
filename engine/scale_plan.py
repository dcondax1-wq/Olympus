"""The scaling plan, live (read-only): "you are at step N; next step: <action> when <trigger>; progress X%".

Reads the research ladder (research/second/scale.json, tools/scale_plan.py, research/writeups/scale-plan.md) and the owner's
real accounts:
  research/props/business.json    the accounts the owner keeps (stage planned / eval / funded / failed / lost / closed,
                                  strategy LIT / ATLAS), the planner budget; expenses / payouts logs through tools/business.py
  the PC bot (pc_view)            LIT's eval (engine/accounts.pc_activity eval days -> engine/eval_life.view: open / passed /
                                  failed), the extra accounts of engine/multi_account.py (LIT copies, mode eval / funded,
                                  incl. the funded MFFU 50K added by engine.eval_life --to-funded), account B (ATLAS,
                                  engine/account_b.py eval: open / passed / failed / stuck)
  the cloud state (cloud_view)    the same three from the PC's heartbeat (state "pc": acct, acct.accounts, second.route.account_b)
Nothing here trades, sizes, arms or routes anything: it only says which rung of the ladder the owner is on and what the next
one needs.

  python -X utf8 -m engine.scale_plan            the status now (PC files only) as JSON
"""
from __future__ import annotations

import datetime as _dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = os.path.join(ROOT, "research", "second", "scale.json")
VERSION = 1
HELD = ("eval", "passed", "funded", "failed")          # bought (a failed eval still holds its rung: buy it again)
FUNDED = ("funded",)
LOST_QUIET_DAYS = 14                                     # ~10 sessions
PLAN_IDS = ("mffu_builder_50k", "mffu_builder_25k", "lucid_pro_50k", "fn_rapid_daily_50k")


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def plan_id(text) -> str | None:
    """A plan id from an id or a free-text plan name ("LucidPro 50K", "Builder 25K", "Rapid Daily 50K")."""
    t = str(text or "").lower()
    if t in PLAN_IDS:
        return t
    if "lucid" in t:
        return "lucid_pro_50k"
    if "rapid daily" in t or "fundednext" in t or "funded next" in t or t.startswith("fn_"):
        return "fn_rapid_daily_50k"
    if "25k" in t and ("builder" in t or "mffu" in t):
        return "mffu_builder_25k"
    if "50k" in t and ("builder" in t or "mffu" in t):
        return "mffu_builder_50k"
    return None


def type_key(strategy, plan) -> str | None:
    """(LIT | ATLAS, plan id) -> the ladder's account type (tools/scale_plan.TYPES)."""
    s = str(strategy or "LIT").upper()
    p = plan_id(plan)
    k = {("LIT", "mffu_builder_50k"): "lit_b50", ("ATLAS", "mffu_builder_25k"): "atlas_b25", ("LIT", "lucid_pro_50k"): "lit_l50",
         ("LIT", "fn_rapid_daily_50k"): "lit_fn50", ("ATLAS", "lucid_pro_50k"): "atlas_l50", ("ATLAS", "fn_rapid_daily_50k"): "atlas_fn50",
         ("LIT", "mffu_builder_25k"): "lit_b25", ("ATLAS", "mffu_builder_50k"): "atlas_b50"}
    return k.get((s, p))


# ================================================================================================ the research plan
def load_plan(path: str | None = None) -> dict | None:
    d = _json(path or PLAN_PATH)
    if not d or not d.get("steps") or not d.get("table"):
        return None
    return d


def compact_plan(d: dict) -> dict:
    """What the pages need from scale.json (no Monte Carlo blocks)."""
    keep = ("step", "accounts", "lit", "atlas", "add", "action", "trigger_text", "usd_month_h2", "usd_month_h1", "usd_month_2025",
            "usd_month_2021_24", "fees_month_h2", "fees_month_2025", "month_p10_h2", "month_le0_h2", "month_le0_2025",
            "month_p10_2025", "risk", "step_cost", "step_cost_list", "fees_to_reach_h2", "fees_to_reach_h1", "months_h2", "months_h1",
            "months_h2_iqr", "reach_24m_h2", "reach_24m_2025", "reach_24m_2021_24", "months_2025", "cap_binds_ladder")
    L = d.get("ladder") or {}
    curve = {sp: {"cum_med": (L.get(sp) or {}).get("cum_net_med"), "cum_p10": (L.get(sp) or {}).get("cum_net_p10")}
             for sp in ("H2", "2025")}
    return {"built": d.get("built"), "writeup": d.get("writeup"), "budget": d.get("budget"), "day_cap_usd": d.get("day_cap_usd"),
            "table": [{k: r.get(k) for k in keep} for r in d["table"]],
            "types": {k: {kk: v.get(kk) for kk in ("strategy", "label", "firm", "price", "list", "price_basis")} for k, v in (d.get("types") or {}).items()},
            "steps": [{"n": s["n"], "add": s["add"], "trigger": s.get("trigger") or {}, "action": s.get("action"), "why": s.get("why")}
                      for s in d["steps"]],
            "curve": curve, "honest": d.get("honest") or []}


# ================================================================================================ the owner's accounts
def from_business(b: dict | None = None) -> tuple[list, dict]:
    """research/props/business.json accounts (+ the payout / expense logs) -> account rows, money {fees, payouts, budget}."""
    rows, money = [], {"fees": 0.0, "payouts": 0.0, "payouts_n": 0, "budget": 300.0}
    try:
        from tools import business as B
        b = B.business(b)
        money["budget"] = float(B.settings(b).get("budget") or 300.0)
        money["fees"] = round(sum(float(e.get("usd") or 0) for e in B.paid(b)), 2)
        pays = [p for p in (b.get("payouts") or []) if _num(p.get("received_usd", p.get("usd")), 0) > 0]
        money["payouts"] = round(sum(_num(p.get("received_usd", p.get("usd")), 0) for p in pays), 2)
        money["payouts_n"] = len(pays)
        accts = B.accounts(b)
    except Exception:
        b = b or _json(os.path.join(ROOT, "research", "props", "business.json"), {}) or {}
        accts = b.get("accounts") or []
        money["budget"] = float(((b.get("planner") or {}).get("budget_usd")) or 300.0)
    for a in accts:
        rows.append({"id": a.get("id"), "strategy": (a.get("strategy") or "LIT").upper(), "plan": plan_id(a.get("lit_id") or a.get("plan")),
                     "label": " ".join(x for x in (a.get("firm"), a.get("plan")) if x), "stage": str(a.get("stage") or "eval").lower(),
                     "start": a.get("start"), "payouts_n": int(a.get("payouts") or 0), "lost_on": a.get("lost_on"), "src": "business.json"})
    return rows, money


def _match(rows, strategy, plan, stages=("planned", "eval", "passed", "funded", "failed")):
    for r in rows:
        if r.get("_m") or r["strategy"] != strategy or r["plan"] != plan or r["stage"] not in stages:
            continue
        return r
    return None


def overlay(rows: list, lit_eval: dict | None = None, extras: list | None = None, acct_b: dict | None = None) -> list:
    """The bot's own view on top of the owner's list: LIT's eval status, the extra (LIT copy) accounts, account B (ATLAS)."""
    rows = [dict(r) for r in rows]
    st = str((lit_eval or {}).get("status") or "").lower()
    if st in ("passed", "failed", "open"):
        r = _match(rows, "LIT", "mffu_builder_50k", ("planned", "eval", "passed", "failed"))
        if r is not None:
            r.update(stage={"open": "eval"}.get(st, st), src=r["src"] + " + PC eval", _m=True)
    for x in extras or []:
        if not isinstance(x, dict) or x.get("error"):
            continue
        p = plan_id(x.get("preset") or x.get("plan") or x.get("firm"))
        if not p:
            continue
        stage = "funded" if (x.get("kind") == "funded" or x.get("mode") == "funded") else "eval"
        r = _match(rows, "LIT", p)
        if r is None:
            rows.append({"id": x.get("id"), "strategy": "LIT", "plan": p, "label": x.get("name") or p, "stage": stage, "src": "bot accounts", "_m": True})
        else:
            r.update(stage=stage if r["stage"] != "funded" else "funded", src=r["src"] + " + bot accounts", _m=True)
    if acct_b:
        ev = acct_b.get("eval") if isinstance(acct_b.get("eval"), dict) else acct_b
        s = str((ev or {}).get("status") or "").lower()
        p = plan_id(acct_b.get("plan") or acct_b.get("plan_label") or "builder 25k") or "mffu_builder_25k"
        stage = {"open": "eval", "passed": "passed", "failed": "failed", "stuck": "failed"}.get(s)
        if acct_b.get("stage") == "funded":       # engine/account_b.py funded stage (owner-run switch)
            stage = {"funded": "funded", "graduated": "closed", "lost": "lost", "stuck": "lost"}.get(s, "funded")
        if stage:
            r = _match(rows, "ATLAS", p)
            if r is None:
                rows.append({"id": "account_b", "strategy": "ATLAS", "plan": p, "label": acct_b.get("label") or "Account B", "stage": stage,
                             "src": "account B", "_m": True})
            else:
                r.update(stage=stage if r["stage"] != "funded" else "funded", src=r["src"] + " + account B", _m=True)
    for r in rows:
        r.pop("_m", None)
        r["type"] = type_key(r["strategy"], r["plan"])
    return rows


# ================================================================================================ the status
def detect_step(rows: list, plan: dict) -> dict:
    """The highest step whose accounts are all held (multiset), and what is missing for the next one."""
    held = [r["type"] for r in rows if r.get("type") and r.get("stage") in HELD]
    have = {}
    for t in held:
        have[t] = have.get(t, 0) + 1
    need, done, missing = {}, -1, []
    for s in plan["steps"]:
        for t in s["add"]:
            need[t] = need.get(t, 0) + 1
        short = [t for t, c in need.items() for _ in range(max(0, c - have.get(t, 0)))]
        if short:
            missing = short
            break
        done = s["n"]
    return {"done": done, "missing": missing, "held": len(held)}


def _cond(label, have, need, money=False):
    have, need = float(have or 0), float(need or 0)
    frac = 1.0 if need <= 0 else max(0.0, min(1.0, have / need))
    return {"label": label, "have": round(have, 2), "need": round(need, 2), "ok": have >= need, "frac": round(frac, 3), "money": money}


def conditions(step: dict, rows: list, money: dict, cost: float, now=None) -> list:
    tr = step.get("trigger") or {}
    funded = sum(1 for r in rows if r.get("stage") in FUNDED)
    out = []
    if tr.get("payouts_n"):
        out.append(_cond("payouts received", money.get("payouts_n"), tr["payouts_n"]))
    if tr.get("funded"):
        out.append(_cond("accounts funded at the same time", funded, tr["funded"]))
    if tr.get("payouts_usd"):
        out.append(_cond("$ paid out in total", money.get("payouts"), tr["payouts_usd"], money=True))
    cash = float(money.get("budget") or 0) + float(money.get("payouts") or 0) - float(money.get("fees") or 0)
    out.append(_cond("cash for the two evals (budget + payouts - fees)", round(cash, 2), cost, money=True))
    today = _dt.date.fromtimestamp(now) if isinstance(now, (int, float)) else (now or _dt.date.today())
    recent = []
    for r in rows:
        try:
            if r.get("stage") == "lost" and r.get("lost_on") and (today - _dt.date.fromisoformat(str(r["lost_on"])[:10])).days < LOST_QUIET_DAYS:
                recent.append(r.get("label") or r.get("id"))
        except ValueError:
            continue
    c = _cond("no funded account lost in the last 2 weeks", 0 if recent else 1, 1)
    if recent:
        c["note"] = ", ".join(map(str, recent))
    out.append(c)
    return out


def status(rows: list, money: dict, plan: dict | None = None, now=None) -> dict:
    """-> {step, of, accounts, next: {n, action, when, conditions, progress, ready}, sentence, table, ...}"""
    plan = plan or load_plan()
    if not plan:
        return {"v": VERSION, "error": "research/second/scale.json missing: run python -X utf8 tools/scale_plan.py"}
    P = plan if "types" in plan and isinstance(plan.get("table"), list) and "curve" in plan else compact_plan(plan)
    det = detect_step(rows, P)
    steps = P["steps"]
    last = steps[-1]["n"]
    T = P.get("types") or {}
    def lab(t):
        x = T.get(t) or {}
        name = str(x.get("label") or t)
        return f"{'an' if name[:1] in 'AEIOUM' else 'a'} {name} for {x.get('strategy', '?')}"
    out = {"v": VERSION, "plan_built": P.get("built"), "writeup": P.get("writeup"), "day_cap_usd": P.get("day_cap_usd"),
           "accounts": [{k: r.get(k) for k in ("id", "strategy", "plan", "type", "label", "stage", "src", "start")} for r in rows],
           "money": {**money, "cash": round(float(money.get("budget") or 0) + float(money.get("payouts") or 0) - float(money.get("fees") or 0), 2)},
           "table": P["table"], "steps": steps, "types": T, "curve": P.get("curve"), "honest": P.get("honest")}
    if det["done"] < 0:                                  # step 0 not complete yet: buy what is missing
        s0 = steps[0]
        need = len(s0["add"])
        have = need - len(det["missing"])
        planned = sorted({str(r.get("start")) for r in rows if r.get("stage") == "planned" and r.get("type") in det["missing"] and r.get("start")})
        out.update(step=0, step_done=False, of=last,
                   next={"n": 0, "action": "buy " + " and ".join(lab(t) for t in det["missing"]),
                         "when": ("planned " + ", ".join(planned)) if planned else "now (today's plan)",
                         "conditions": [_cond("step 0 accounts bought", have, need)], "progress": round(100.0 * have / need),
                         "ready": False})
        out["sentence"] = (f"You are at step 0 ({have} of {need} accounts bought). Next: {out['next']['action']} ({out['next']['when']}). "
                           f"Progress {out['next']['progress']}%.")
        return out
    n = det["done"]
    out.update(step=n, step_done=True, of=last)
    if n >= last:
        out["next"] = {"n": None, "action": "keep the 10 accounts; re-buy what fails. More accounts: only once a firm confirms its cap "
                                            "(Lucid 5 per household, MFFU 1 x 50K + 2 x 25K)", "when": None, "conditions": [], "progress": 100,
                       "ready": False}
        out["sentence"] = f"You are at step {n} of {last} (the top of the ladder). Keep it running; re-buy what fails."
        return out
    nx = steps[n + 1]
    cost = round(sum(float((T.get(t) or {}).get("price") or 0) for t in nx["add"]), 2)
    C = conditions(nx, rows, out["money"], cost, now)
    prog = round(100.0 * sum(c["frac"] for c in C) / len(C)) if C else 0
    ready = all(c["ok"] for c in C)
    row = next((r for r in P["table"] if r.get("step") == nx["n"]), {})
    when = row.get("trigger_text") or ""
    out["next"] = {"n": nx["n"], "action": nx.get("action") or ("buy " + " and ".join(lab(t) for t in nx["add"])), "why": nx.get("why"),
                   "when": when, "conditions": C, "progress": prog, "ready": ready, "cost": cost,
                   "usd_month_h2": row.get("usd_month_h2"), "usd_month_2025": row.get("usd_month_2025"), "months_h2": row.get("months_h2")}
    short = "; ".join(c["label"] + (f" ${c['have']:,.0f} of ${c['need']:,.0f}" if c["money"] else f" {c['have']:g} of {c['need']:g}")
                      for c in C if not c["ok"])
    out["sentence"] = (f"You are at step {n} of {last}. Next step: {out['next']['action']} "
                       + ("- ready now (all conditions met)." if ready else f"when {short}.") + f" Progress {prog}%.")
    return out


# ================================================================================================ sources
def _eval_status(eval_block: dict | None, now=None) -> dict | None:
    """heartbeat acct.eval {start, days} -> engine/eval_life.view status (open / passed / failed)."""
    try:
        if not eval_block or not eval_block.get("start"):
            return None
        from . import eval_life as EL
        from .accounts import trading_day
        import time as _t
        today = trading_day(int(now or _t.time()))
        lm = _json(os.path.join(ROOT, "live_model.json"), {}) or {}
        return EL.view(eval_block.get("days") or {}, eval_block.get("start"), today, lm.get("lit_sizing"),
                       anchor=eval_block.get("anchor"))
    except Exception:
        return None


def cloud_view(state: dict | None, now=None, plan_path: str | None = None) -> dict:
    """tools/build_web_dashboard.py -> data.json "scale": the status from the PC's heartbeat in the cloud state + business.json."""
    try:
        pc = (state or {}).get("pc") or {}
        acct = pc.get("acct") or {}
        sec = pc.get("second") or {}
        ab = ((sec.get("route") or {}).get("account_b")) or sec.get("account_b")
        rows, money = from_business()
        rows = overlay(rows, _eval_status(acct.get("eval"), now), acct.get("accounts"), ab if isinstance(ab, dict) else None)
        out = status(rows, money, load_plan(plan_path), now)
        out["source"] = "business.json + the PC heartbeat" if pc else "business.json (no PC heartbeat yet)"
        return out
    except Exception as e:
        return {"v": VERSION, "error": f"{e.__class__.__name__}: {str(e)[:160]}"}


def pc_view(bot=None, now=None, plan_path: str | None = None) -> dict:
    """/api/next/scale: the status from the running PC bot (LIT eval, extra accounts, account B) + business.json."""
    try:
        lit_eval, extras, ab = None, None, None
        if bot is not None:
            try:
                from . import accounts as A
                act = A.pc_activity(bot, now=now)
                lit_eval = _eval_status(act.get("eval"), now)
                extras = act.get("accounts")
            except Exception:
                pass
            try:
                if getattr(bot, "acct_b", None) is not None:
                    ab = bot.acct_b.info(now)
            except Exception:
                ab = None
        rows, money = from_business()
        rows = overlay(rows, lit_eval, extras, ab)
        out = status(rows, money, load_plan(plan_path), now)
        out["source"] = "business.json + the PC bot" if bot is not None and getattr(bot, "cfg", None) else "business.json"
        return out
    except Exception as e:
        return {"v": VERSION, "error": f"{e.__class__.__name__}: {str(e)[:160]}"}


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in pc_view().items() if k not in ("table", "curve", "types", "steps")}, indent=1, default=str))
