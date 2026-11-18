"""One-tap new / upgraded MFFU accounts on the PC dashboard's Start page (2026-11-18, owner: setting up 2 accounts "should
have taken no longer than 5 mins"). Every new NinjaTrader account Name is read, its plan guessed, and ONE right button
offered. A tap runs the same code as the console lines (engine/account_cli.py `engine.accounts add`, engine/lit25.py
`--funded`, engine/go.to_funded); the account is added DISARMED. Nothing here arms: it is armed at the next START, when the
owner types the live phrase himself ("Re-arm now" = the existing START flow, rearm() below).

  parse_name(name)        MFFU<stage><plan><digits>: stage EV = eval, SF = sim-funded (FD / F read as funded too); plan
                          BLDR / BLD = Builder. Rapid: no MFFU document or code names its prefix (searched 2026-11-18), so RP...
                          / RAPID... are read as Rapid EOD (25K or 50K from the balance) but marked "guess" and the card
                          offers the choice (Rapid first).
  size_of(balance)        $35,000 and up = 50K, $10,000-35,000 = 25K (= go.slot_problem / new_accounts.SIZE_SPLIT), else None.
  infer(name, balance, stage_hint, outcome)
                          {"plan", "stage", "size", "kind", "guess", "passed", "why"}; kind = fresh_eval | passed_eval |
                          funded | unknown. A passed eval = an eval whose balance is at / above start + target (25K $26,500,
                          50K $53,000), or the lifecycle (data/lifecycle.json, the Name's hash) says PASSED / LOCKED, or the
                          bot remembered its pass (engine/new_accounts outcomes).
  offers(info, evals)     the buttons, the right one first ("primary"):
                            fresh Builder eval -> "Zlarior trades it"            (add:builder25k | add:builder50k)
                            fresh Rapid EOD    -> "Zlarior + ATLAS"              (add:rapideod | add:rapideod25)
                            funded (SF)        -> "Move ATLAS here (funded)" / "Move Zlarior here (funded)" for the same-size
                                                  eval the bot trades, the passed one first (move:<eval Name>); none -> add
                                                  it as a funded Zlarior account (funded:<plan>)
                            old passed eval    -> "Not for the bot" only (dismiss)
                            unknown plan       -> a choice (Builder / Rapid) + "Not for the bot"
  status(rows)            the Start page's block {"new": [{name, balance, say, options, kind, plan, ...}]} (never raises).
  do(name, act)           the tap (PC only). Moves to funded need the bot stopped: a running bot is stopped first ONLY when it
                          is flat (autoupdate.bot_flat_reason), else refused. Never arms.
  rearm(phrase, ...)      "Re-arm now": with the typed phrase, only when flat: STOP, then the START BOT arm step
                          (engine/go.job_start("arm"): it arms every account the owner added, after his phrase).
  detect_lines()          plain lines for ADD_ACCOUNT.bat (python -X utf8 -m engine.onboard).
"""
from __future__ import annotations

import json
import os
import re
import time

ARMED_LATER = "Armed at the next START (you type the phrase)."
BUILDER_CODES = ("BLDR", "BLD", "BUILDER")
RAPID_CODES = ("RPD", "RAPID", "RP", "REOD")       # not confirmed by MFFU: a guess (the card still offers the choice)
RAPIDS = ("rapideod", "rapideod25")
STAGE_CODES = {"EV": "eval", "SF": "funded", "FD": "funded", "F": "funded"}
_NAME = re.compile(r"^MFFU(EV|SF|FD|F)?([A-Z]*?)(\d+)$")
START = {"25K": 25000.0, "50K": 50000.0}
TARGET = {"25K": 1500.0, "50K": 3000.0}
PLAN_LABEL = {"builder25k": "Builder 25K", "builder50k": "Builder 50K", "rapideod": "Rapid EOD 50K", "rapideod25": "Rapid EOD 25K"}


# ------------------------------------------------------------------------------------------------ pure inference
def parse_name(name) -> dict:
    """{"firm", "stage" (eval / funded / None), "code", "plan" (builder / rapid / None), "guess"} from the Name alone."""
    n = str(name or "").strip().upper().replace(" ", "")
    m = _NAME.match(n)
    if not m:
        return {"firm": "MFFU" if n.startswith("MFFU") else None, "stage": None, "code": "", "plan": None, "guess": True}
    st, code = m.group(1) or "", m.group(2) or ""
    plan, guess = None, True
    if code in BUILDER_CODES:
        plan, guess = "builder", False
    elif code.startswith("RP") or "RAPID" in code or code in RAPID_CODES:
        plan = "rapid"
    return {"firm": "MFFU", "stage": STAGE_CODES.get(st), "code": code, "plan": plan, "guess": guess}


def size_of(balance) -> str | None:
    try:
        b = float(balance)
    except (TypeError, ValueError):
        return None
    if b != b:
        return None
    return "50K" if b >= 35000 else "25K" if b >= 10000 else None


def _plan_key(plan, size) -> str | None:
    if plan == "builder" and size in ("25K", "50K"):
        return f"builder{size.lower()}"
    if plan == "rapid":
        return "rapideod25" if size == "25K" else "rapideod"        # Rapid EOD 25K (owner 2026-11-18) / 50K
    return None


def infer(name, balance=None, life_stage=None, outcome=None) -> dict:
    """What a NinjaTrader Name is. life_stage = its lifecycle stage (passed / locked / ...), outcome = new_accounts' memory."""
    p = parse_name(name)
    size = size_of(balance)
    stage = p["stage"] or "eval"
    plan = _plan_key(p["plan"], size)
    try:
        bal = float(balance) if balance is not None else None
    except (TypeError, ValueError):
        bal = None
    passed, why = False, ""
    if stage == "eval":
        if str(life_stage or "").lower() in ("passed", "locked"):
            passed, why = True, f"the bot saw it {str(life_stage).upper()}"
        elif str(outcome or "").lower() == "passed":
            passed, why = True, "the bot saw it pass"
        elif bal is not None and size and bal >= START[size] + TARGET[size]:     # Rapid 25K / 50K: the same targets
            passed, why = True, f"${bal:,.0f} is at / above the ${START[size] + TARGET[size]:,.0f} target"
    if passed:
        kind = "passed_eval"
    elif plan is None or p["guess"]:
        kind = "unknown"
    elif stage == "funded":
        kind = "funded"
    else:
        kind = "fresh_eval"
    return {"name": str(name or "").strip(), "balance": bal, "plan": plan, "stage": stage, "size": size, "kind": kind,
            "guess": p["guess"], "code": p["code"], "passed": passed, "why": why}


def _who(r) -> str:
    return {"b": "ATLAS", "main": "Zlarior", "rapid": "Zlarior + ATLAS"}.get(r.get("role"), "Zlarior")


def offers(info: dict, evals=None) -> list:
    """[{"act", "label", "primary"}] for one Name. evals = the bot's eval accounts [{name, plan, role, passed}]."""
    kind, plan, size, stage = info["kind"], info["plan"], info["size"], info["stage"]
    no = {"act": "dismiss", "label": "Not for the bot", "primary": False}
    if kind in ("passed_eval", "unsupported"):
        return [{**no, "primary": True}]
    if kind == "fresh_eval":
        return [{"act": f"add:{plan}", "label": "Zlarior + ATLAS" if plan in RAPIDS else "Zlarior trades it",
                 "primary": True}, no]
    if kind == "funded":
        same = [e for e in (evals or []) if e.get("plan") == plan and e.get("role") in ("main", "b", "extra", "rapid")]
        same.sort(key=lambda e: (not e.get("passed"), e.get("role") != "b"))
        out = []
        for e in same:
            if e.get("role") == "rapid":
                out.append({"act": f"funded:{plan}", "label": "Move Zlarior + ATLAS here (funded)", "from": e["name"]})
                continue
            lab = f"Move {_who(e)} here (funded)"
            if len(same) > 1:
                lab += f" from …{e['name'][-3:]}"
            out.append({"act": f"move:{e['name']}", "label": lab, "from": e["name"]})
        if not out:
            out.append({"act": f"funded:{plan}", "label": "Zlarior + ATLAS (funded)" if plan in RAPIDS else
                        "Zlarior trades it (funded)"})
        for i, o in enumerate(out):
            o["primary"] = i == 0
        return out + [no]
    # unknown: a choice, never a guess acted on alone
    fund = stage == "funded"
    sizes = [size] if size in ("25K", "50K") else ["25K", "50K"]
    out = [{"act": ("funded:" if fund else "add:") + f"builder{s.lower()}",
            "label": f"Builder {s}: Zlarior trades it" + (" (funded)" if fund else ""), "primary": False} for s in sizes]
    for s in sizes:
        out.append({"act": ("funded:" if fund else "add:") + ("rapideod" if s == "50K" else "rapideod25"),
                    "label": f"Rapid EOD {s}: Zlarior + ATLAS" + (" (funded)" if fund else ""), "primary": False})
    if info.get("plan") and out:                       # the guessed plan first (one tap), the others still offered
        out.sort(key=lambda o: o["act"].split(":", 1)[1] != info["plan"])
        out[0]["primary"] = out[0]["act"].split(":", 1)[1] == info["plan"]
    return out + [no]


def say(info: dict, opts: list) -> str:
    n = info["name"]
    bal = f" (${info['balance']:,.0f})" if info.get("balance") is not None else ""
    lab = PLAN_LABEL.get(info.get("plan") or "", "MFFU")
    k = info["kind"]
    if k == "passed_eval":
        return f"Old {lab} eval {n}{bal}: already passed ({info['why']}). Not for the bot."
    if k == "unsupported":
        return f"{n}{bal}: {info['why']}. Not for the bot."
    if k == "fresh_eval":
        return f"New {lab} eval {n}{bal} in NinjaTrader: {opts[0]['label']}?"
    if k == "funded":
        src = next((o.get("from") for o in opts if o.get("from")), None)
        return (f"New FUNDED {lab} {n}{bal} in NinjaTrader" + (f" (the eval {src} passed)" if src else "") +
                f": {opts[0]['label']}?")
    return (f"New account {n}{bal} in NinjaTrader: the plan is not clear from its name"
            + (" (looks like Rapid, not confirmed)" if info.get("plan") in RAPIDS else "") + ". Pick one:")


# ------------------------------------------------------------------------------------------------ the PC's facts
def _go():
    from . import go
    return go


def _na():
    from . import new_accounts
    return new_accounts


def _life_path() -> str:
    from . import lifecycle
    return os.path.join(os.path.dirname(_go().CFG), lifecycle.FILE)


def life_stages(path: str | None = None) -> dict:
    """{name hash: stage} from data/lifecycle.json (the bot stores a hash, never the Name). Never raises."""
    try:
        with open(path or _life_path(), encoding="utf-8") as fh:
            rows = (json.load(fh) or {}).get("rows") or {}
        return {str(r.get("acct")): str(r.get("stage") or "") for r in rows.values() if isinstance(r, dict) and r.get("acct")}
    except Exception:
        return {}


def _hash(name):
    from .lifecycle import acct_hash
    return acct_hash(name)


def bot_evals(outcomes=None, stages=None, balances=None) -> list:
    """The eval accounts the bot trades now: [{name, plan, role, passed}] (engine/account_cli.inventory)."""
    from . import account_cli
    stages = life_stages() if stages is None else stages
    outcomes = outcomes or {}
    if balances is None:
        try:
            balances = _go().nt_balances()
        except Exception:
            balances = {}
    out = []
    for r in account_cli.inventory():
        if r.get("stage") != "eval" or r.get("sim") or r.get("role") == "c":
            continue
        i = infer(r["name"], balances.get(r["name"]), stages.get(_hash(r["name"]) or ""), outcomes.get(r["name"]))
        size = "25K" if r["plan"] in ("builder25k", "rapideod25") else "50K"
        bal = balances.get(r["name"])
        passed = i["passed"] or (bal is not None and float(bal) >= START[size] + TARGET[size])
        out.append({"name": r["name"], "plan": r["plan"], "role": r["role"], "id": r.get("id"), "passed": bool(passed)})
    return out


def _used(path=None) -> set:
    try:
        return set((_na()._load(path).get("used") or {}).keys())
    except Exception:
        return set()


def status(rows=None, folder: str | None = None, path: str | None = None, names=None, now=None) -> dict:
    """The Start page's block: {"new": [{name, balance, kind, plan, say, options}], "running"}. Never raises."""
    try:
        na = _na()
        outcomes = na.remember(rows, path) if rows is not None else dict(na._load(path).get("outcomes") or {})
        stages = life_stages()
        kw = {"names": names} if names is not None else {}
        cands = [c for c in na.candidates(folder, path, now=now, **kw) if c["name"] not in _used(path)]
        evals = bot_evals(outcomes, stages) if cands else []
        out = []
        for c in cands:
            i = infer(c["name"], c.get("balance"), stages.get(_hash(c["name"]) or ""), outcomes.get(c["name"]))
            o = offers(i, evals)
            out.append({**c, **i, "options": o, "say": say(i, o), "armed_note": ARMED_LATER})
        return {"new": out, "running": bool(_go().bot_running()), "armed_note": ARMED_LATER}
    except Exception as e:
        return {"new": [], "error": f"{e.__class__.__name__}"}


# ------------------------------------------------------------------------------------------------ the tap
def _plain(r: dict) -> dict:
    """The CLI's answer with the owner's sentence on arming (never armed here)."""
    if not r.get("ok"):
        return {"ok": False, "error": str(r.get("error") or "Not added.")}
    s = str(r.get("say") or "Done.").replace("[OK] ", "")
    notes = [n for n in (r.get("notes") or []) if n]
    return {**{k: v for k, v in r.items() if k not in ("say",)}, "ok": True, "armed": False,
            "say": f"{s} {ARMED_LATER}".strip(), "notes": notes}


def do(name: str, act: str, start: str | None = None, path: str | None = None, folder: str | None = None,
       stop_fn=None, flat_reason=None) -> dict:
    """The owner's tap. act: add:<plan> | funded:<plan> | move:<eval Name> | dismiss. Never arms."""
    from . import account_cli
    go, na = _go(), _na()
    name, act = str(name or "").strip(), str(act or "").strip()
    if not name:
        return {"ok": False, "error": "No account name."}
    if act == "dismiss":
        return na.dismiss(name, path)
    seen = {c["name"]: c for c in na.candidates(folder, path)}
    if name not in seen:
        return {"ok": False, "error": f"NinjaTrader does not show {name} as a new account: open NinjaTrader (Accounts tab) and try again."}
    start = start or go.session_day()
    kind, _, arg = act.partition(":")
    stopped = ""
    if kind == "add" and arg in account_cli.PLANS:
        r = account_cli.add(arg, name, start=start)
    elif kind == "funded" and arg in account_cli.PLANS:
        r = account_cli.add(arg, name, start=start, funded=True)
    elif kind == "move" and arg:
        if go.bot_running():                        # the switch needs the bot stopped: stop it only when flat
            why = flat_reason() if flat_reason else "the bot is running"
            if why:
                return {"ok": False, "error": f"Not now: {why}. Try again once it is flat (or stop the bot first)."}
            if stop_fn is None:
                return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
            stop_fn()
            if go.bot_running():
                return {"ok": False, "error": "The bot did not stop: nothing changed."}
            stopped = "The bot was flat and is stopped for the switch. "
        b = go._b() or {}
        if arg == str(b.get("account") or "").strip():
            from . import lit25
            r = lit25.to_funded(name, start)         # = python -X utf8 -m engine.lit25 --funded "<Name>" --start <day>
        else:
            r = go.to_funded(arg, name, start)
    else:
        return {"ok": False, "error": "Unknown button: reload the page."}
    out = _plain(r)
    if out.get("ok"):
        s = na._load(path)
        s.setdefault("used", {})[name] = {"act": act, "t": int(time.time())}
        if kind == "move":                          # the passed eval is history now: never offered back as "new"
            s.setdefault("retired", {})[arg] = int(time.time())
        na._save(s, path)
        if stopped:
            out["say"] = stopped + out["say"] + " Tap Re-arm now (you type the phrase)."
            out["stopped"] = True
    return out


# ------------------------------------------------------------------------------------------------ Re-arm now
def rearm_problem(cfg=None) -> str | None:
    """go.arm_problem without the "bot running" line (Re-arm stops it first): checked BEFORE anything is stopped."""
    go = _go()
    cfg = go._read(go.CFG) if cfg is None else cfg
    lit, atlas = cfg.get("lit"), cfg.get("atlas")
    if not lit or not atlas or lit == atlas:
        return "two different account names are needed (50K for Zlarior, 25K for ATLAS)"
    bad = go.mixup(lit, atlas)
    if bad:
        return bad
    if not all(go.sims_passed().values()):
        return "the Sim101 test has not passed yet"
    if go.job_status().get("running"):
        return "a step is already running: wait for it to finish"
    return None


def rearm(phrase: str, stop_fn=None, flat_reason=None, job=None) -> dict:
    """"Re-arm now": the typed phrase, then (only when flat) STOP and the START BOT arm step. The phrase reaches the job in
    its environment (engine/go.job_start), checked again by step_arm and engine/ninjatrader."""
    go = _go()
    phrase = go.typed_phrase(phrase or "")
    if phrase != go.LIVE_PHRASE:
        return {"ok": False, "error": f"Type {go.LIVE_PHRASE} exactly. Nothing is armed."}
    bad = rearm_problem()
    if bad:
        return {"ok": False, "error": f"Not now: {bad}. Nothing stopped."}
    if go.bot_running():
        why = flat_reason() if flat_reason else "cannot tell if flat"
        if why:
            return {"ok": False, "error": f"Not flat ({why}): re-arm after the trade / setup is done. Nothing stopped."}
        if stop_fn is None:
            return {"ok": False, "error": "Cannot stop the bot from here: use STOP BOT, then Start trading."}
        stop_fn()
        if go.bot_running():
            return {"ok": False, "error": "The bot did not stop: nothing changed."}
    r = (job or go.job_start)("arm", phrase)
    if not r.get("ok"):
        return {"ok": False, "error": f"Stopped, but START did not begin: {r.get('error')}. Tap Start trading."}
    return {"ok": True, "say": "Re-arming: stopped while flat, START runs now with your phrase (every added account)."}


# ------------------------------------------------------------------------------------------------ ADD_ACCOUNT.bat
def detect_lines(folder: str | None = None, path: str | None = None) -> list:
    st = status(folder=folder, path=path)
    rows = st.get("new") or []
    if not rows:
        return [" No new MFFU account in NinjaTrader (open NinjaTrader, log in, then run this again)."]
    out = [" NinjaTrader shows these new accounts:"]
    for r in rows:
        out.append(f"   {r['say']}")
        btn = next((o for o in r["options"] if o.get("primary")), None)
        if btn and btn["act"] != "dismiss":
            out.append(f"     -> best choice: {btn['label']} (or tap it on the Start page)")
    return out


def main(argv=None) -> int:
    for ln in detect_lines():
        print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
