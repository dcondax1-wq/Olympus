"""One way to add any MFFU account: one pasted line per account (docs/NEW_ACCOUNT.md). Nothing here arms or trades.

    python -X utf8 -m engine.accounts add --plan builder25k|builder50k|rapideod|rapideod25 --name "<NinjaTrader Name>" [--bots lit|atlas|lit+atlas]
                                          [--start yyyy-mm-dd] [--funded]
    python -X utf8 -m engine.accounts list | status | remove --name "<Name>"

What each plan becomes (research/writeups/builder-levers-2026-11-16.md, stack-one-account-2026-11-16.md):
  builder50k  LIT (Zlarior) copies onto it: an extra account of engine/multi_account (preset mffu_builder_50k, LIT's live
              two_week eval size). The fresh 50K next to Zlarior's hole eval: whichever passes first is kept (MFFU funds
              one Builder 50K). The first 50K ever (no Zlarior account yet) becomes Zlarior's own (engine/go.add_account).
  builder25k  LIT on the eval (preset mffu_builder_25k), then LIT + ATLAS $250 once funded. The ATLAS part is OFF until the
              owner says (--bots lit+atlas records his yes; its lane on a 2nd 25K still has to be wired: told at add time).
              --bots atlas = ATLAS's own 25K (account B), only while ATLAS has none (engine/go.add_account).
  rapideod    LIT + ATLAS on one account: engine/rapid.py (data/rapid.json), ONE Rapid only (owner: "I'll stick with 1 rapid").
  rapideod25  the Rapid EOD 25K (owner 2026-11-18): the same lanes and rules at the 25K's numbers (engine/rapid.PLANS,
              research/writeups/rapid-25k-vs-50k-2026-11-17.md); still ONE Rapid at a time (a 50K or a 25K).

Rules on every account:
  * MFFU limits checked at add time (research/lit/mffu_rules.json multi_account): at most 10 evals; at most 5 funded, of
    which Builder 50K 1, Builder 25K 2, Rapid EOD 50K 3, Rapid EOD 25K 3 (its own). Sim accounts (Sim101 ...) are never counted.
  * No hedging across accounts (MFFU bans it): every LIT copy is the same side; engine/multi_account.AccountRouter.
    opposite_open refuses an order opposite to any open position on any account, account B / the Rapid's ATLAS never
    take the other side of LIT, and LIT goes first (ATLAS is closed before LIT enters on a shared account).
  * Added DISARMED. A real (non-Sim) account goes on the NinjaTrader allowlist (that alone never trades). It is armed only
    by START BOT after the owner typed I ACCEPT LIVE RISK (engine/go.step_arm -> arm() here, rapid.arm for the Rapid); a
    real account also needs NINJATRADER_LIVE=1 (each adapter's own gate). It joins at the next START BOT.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
TAG = "engine.accounts"          # rows this CLI wrote in data/accounts.json carry {"cli": {...}} (arm() touches only those)

PLANS = {
    "builder50k": {"preset": "mffu_builder_50k", "label": "Builder 50K", "size": "50K", "cap_key": "builder_50k_sim_funded",
                   "cap": 1, "bots": "lit", "ok": ("lit",), "id": "b50k", "price": "$91.80 (CLUB 40% off)"},
    "builder25k": {"preset": "mffu_builder_25k", "label": "Builder 25K", "size": "25K", "cap_key": "builder_25k_sim_funded",
                   "cap": 2, "bots": "lit", "ok": ("lit", "lit+atlas", "atlas"), "id": "b25k", "price": "$63 (CLUB 40% off)"},
    "rapideod": {"preset": "mffu_rapid_eod_50k", "label": "Rapid EOD 50K", "size": "50K", "cap_key": "rapid_eod_50k_sim_funded",
                 "cap": 3, "bots": "lit+atlas", "ok": ("lit+atlas",), "id": "rapid", "price": "$165 with CLUB ($275 list)"},
    "rapideod25": {"preset": "mffu_rapid_eod_25k", "label": "Rapid EOD 25K", "size": "25K", "cap_key": "rapid_eod_25k_sim_funded",
                   "cap": 3, "bots": "lit+atlas", "ok": ("lit+atlas",), "id": "rapid", "price": "$97.20 with CLUB ($162 list)"},
}
RAPID_PLANS = ("rapideod", "rapideod25")
MAX_EVALS, MAX_FUNDED = 10, 5
RULE_LINES = ("No hedging: every account takes the same side (an order opposite to any open position is refused).",
              "LIT first: on a shared account ATLAS is closed before LIT enters, and never trades against LIT.",
              "Disarmed until START BOT + you type I ACCEPT LIVE RISK.")


# ---------------------------------------------------------------------------------------------------------------- helpers
def limits() -> dict:
    """MFFU's account caps (research/lit/mffu_rules.json multi_account; the constants when it is unreadable)."""
    out = {"evals": MAX_EVALS, "funded": MAX_FUNDED, **{k: p["cap"] for k, p in PLANS.items()}}
    try:
        with open(RULES_PATH, encoding="utf-8") as fh:
            v = (json.load(fh).get("multi_account") or {}).get("value") or {}
        out["evals"] = int(v.get("max_evaluations") or out["evals"])
        out["funded"] = int(v.get("max_sim_funded") or out["funded"])
        for k, p in PLANS.items():
            out[k] = int(v.get(p["cap_key"]) or out[k])
    except Exception:
        pass
    return out


def _go():
    from . import go
    return go


def _ma():
    from . import multi_account
    return multi_account


def _rapid():
    from . import rapid
    return rapid


def _is_sim(name) -> bool:
    from .ninjatrader import is_sim
    return is_sim(str(name or "").strip())


def _today() -> str:
    return _go().session_day()


def _allow(name, remove=False):
    if _is_sim(name):
        return None
    try:
        _go()._allow(name, remove=remove)
        return None
    except Exception as e:
        return f"allowlist NOT updated ({e.__class__.__name__}): python -m engine.ninjatrader --allow-account \"{name}\""


def _plan_of_preset(preset) -> str | None:
    return next((k for k, p in PLANS.items() if p["preset"] == preset), None)


# ---------------------------------------------------------------------------------------------------------------- inventory
def inventory() -> list:
    """Every account the bot knows, one row each: {name, plan (builder50k / builder25k / rapideod / other), stage (eval /
    funded), bots, role (main / b / extra / rapid / c), id, armed, sim, mffu}. Never raises."""
    go, rows = _go(), []

    def add(**r):
        r["name"] = str(r.get("name") or "").strip()
        if r["name"]:
            r["sim"] = _is_sim(r["name"])
            r.setdefault("mffu", True)
            rows.append(r)
    try:
        cfg = go._read(go.CFG) or {}
    except Exception:
        cfg = {}
    lit, atlas = str(cfg.get("lit") or "").strip(), str(cfg.get("atlas") or "").strip()
    add(name=lit, plan="builder50k", stage="eval", bots="lit", role="main", id="zlarior", armed=None)
    try:
        b = go._b() or {}
    except Exception:
        b = {}
    b_on = str(b.get("account") or "").strip()
    if b_on or atlas:
        funded = bool(b_on) and str(b.get("stage") or "").lower() == "funded"
        bots = "atlas"
        try:
            from . import lit25
            if funded and lit25.is_on():
                bots = "lit+atlas"
        except Exception:
            pass
        add(name=b_on or atlas, plan=str(b.get("plan") or "builder25k") if b_on else "builder25k",
            stage="funded" if funded else "eval", bots=bots, role="b", id="atlas", armed=b.get("armed") is True)
    try:
        extras = go._extras()
    except Exception:
        extras = []
    ma = _ma()
    for e in extras:
        n = ma.normalize(e)
        cli = e.get("cli") if isinstance(e.get("cli"), dict) else {}
        plan = cli.get("plan") or _plan_of_preset(n["preset"]) or n["preset"]
        add(name=n["nt_account"] or (n["name"] if n["adapter"] == "ninjatrader" else ""), plan=plan,
            stage="funded" if n["mode"] == "funded" else "eval", bots=cli.get("bots") or "lit", role="extra", id=n["id"],
            armed=n["armed"], enabled=n["enabled"], mffu=n["firm"] == "MFFU", cli=bool(cli),
            atlas_when_funded=bool(cli.get("atlas_when_funded")))
    try:
        blk = _rapid().read()
    except Exception:
        blk = None
    if blk:
        add(name=blk["account"], plan="rapideod25" if blk.get("plan") == PLANS["rapideod25"]["preset"] else "rapideod", stage="funded" if blk.get("stage") == "funded" else "eval",
            bots="lit+atlas", role="rapid", id="rapid", armed=blk.get("armed") is True)
    try:
        c = go._c() or {}
    except Exception:
        c = {}
    if str(c.get("account") or "").strip():
        add(name=c["account"], plan="builder25k", stage="funded" if str(c.get("stage") or "").lower() == "funded" else "eval",
            bots="blitz", role="c", id="blitz", armed=c.get("armed") is True)
    return rows


def slots(rows=None) -> dict:
    """What MFFU slots are used (Sim and non-MFFU accounts never count)."""
    rows = inventory() if rows is None else rows
    real = [r for r in rows if not r["sim"] and r.get("mffu", True)]
    out = {"evals": sum(1 for r in real if r["stage"] == "eval"), "funded": sum(1 for r in real if r["stage"] == "funded")}
    for k in PLANS:
        out[k] = sum(1 for r in real if r["stage"] == "funded" and r["plan"] == k)
    return out


def slots_text(rows=None) -> str:
    s, L = slots(rows), limits()
    return (f"MFFU slots: evals {s['evals']} of {L['evals']} · funded {s['funded']} of {L['funded']} (Builder 50K "
            f"{s['builder50k']}/{L['builder50k']}, Builder 25K {s['builder25k']}/{L['builder25k']}, Rapid EOD "
            f"{s['rapideod']}/{L['rapideod']}, Rapid EOD 25K {s['rapideod25']}/{L['rapideod25']})")


def limit_problem(plan: str, stage: str, name: str, rows=None) -> str | None:
    """Why MFFU would not allow one more account of this plan and stage (None = fine). Sim accounts are not MFFU slots."""
    if _is_sim(name):
        return None
    s, L = slots(rows), limits()
    if stage == "eval" and s["evals"] >= L["evals"]:
        return f"MFFU allows {L['evals']} evals and you have {s['evals']}: remove one first"
    if stage == "funded":
        if s[plan] >= L[plan]:
            return f"MFFU allows {L[plan]} funded {PLANS[plan]['label']} and you have {s[plan]}: remove one first"
        if s["funded"] >= L["funded"]:
            return f"MFFU allows {L['funded']} funded accounts and you have {s['funded']}: remove one first"
    return None


def name_problem(name: str, plan: str, rows=None) -> str | None:
    name = str(name or "").strip()
    if not name or len(name) > 60 or any(c in name for c in ";,|\r\n"):
        return "type the account Name exactly as NinjaTrader's Accounts tab shows it (between the quotes)"
    for r in (inventory() if rows is None else rows):
        if r["name"] == name:
            who = {"main": "Zlarior's 50K", "b": "ATLAS's 25K", "rapid": "the Rapid EOD", "c": "BLITZ's 25K"}.get(
                r["role"], f"the account {r['id']}")
            return f"{name} is already {who}: one NinjaTrader account is added once"
    if _is_sim(name):
        return None
    size = PLANS[plan]["size"]
    u, other = name.upper().replace(" ", ""), "25K" if size == "50K" else "50K"
    if other in u and size not in u:
        return f"{name} reads like a {other} account, not a {PLANS[plan]['label']}"
    try:
        bal = _go().nt_balances().get(name)
    except Exception:
        bal = None
    if bal is not None and (float(bal) < 35000) == (size == "50K"):
        return f"{name} has ${float(bal):,.0f} in NinjaTrader: that is not a {PLANS[plan]['label']}"
    return None


def _new_id(plan: str, rows_file: list) -> str:
    base = PLANS[plan]["id"]
    ids = {str(r.get("id")) for r in rows_file}
    return next(x for x in (f"{base}_{i}" for i in range(2, 200)) if x not in ids)


# ---------------------------------------------------------------------------------------------------------------- add
def add(plan: str, name: str, bots: str | None = None, start: str | None = None, funded: bool = False) -> dict:
    """The owner's one line. Returns {"ok", "say" | "error", "notes": [...]}; never arms."""
    plan = str(plan or "").lower().replace(" ", "").replace("_", "").replace("-", "")
    if plan == "rapideod25k":
        plan = "rapideod25"
    if plan not in PLANS:
        return {"ok": False, "error": "pick --plan builder25k, builder50k, rapideod or rapideod25"}
    P = PLANS[plan]
    bots = str(bots or P["bots"]).lower().replace(" ", "")
    if bots == "atlas+lit":
        bots = "lit+atlas"
    if bots not in P["ok"]:
        why = {"builder50k": "a Builder 50K is LIT only (the research picked LIT alone on the 50K eval)",
               "rapideod": "the Rapid EOD runs LIT + ATLAS together (engine/rapid.py)",
               "rapideod25": "the Rapid EOD runs LIT + ATLAS together (engine/rapid.py)"}.get(plan, "")
        return {"ok": False, "error": f"--bots {bots} is not offered for {P['label']}: {why or 'use lit, lit+atlas or atlas'}"}
    name = str(name or "").strip()
    try:
        start = _dt.date.fromisoformat(str(start)).isoformat() if start else _today()
    except ValueError:
        return {"ok": False, "error": f"--start {start!r} is not yyyy-mm-dd"}
    stage = "funded" if funded else "eval"
    rows = inventory()
    why = name_problem(name, plan, rows) or limit_problem(plan, stage, name, rows)
    if why:
        return {"ok": False, "error": why}
    notes = []
    s, L = slots(rows), limits()
    if stage == "eval" and not _is_sim(name) and s[plan] >= L[plan]:
        notes.append(f"MFFU already has your {L[plan]} funded {P['label']}: a pass of this eval cannot be activated until one goes")
    if plan in RAPID_PLANS:
        r = _add_rapid(name, start, funded, rows, plan)
    elif bots == "atlas":
        r = _add_atlas(name, start, funded, rows)
    else:
        r = _add_lit(plan, name, bots, start, funded, rows)
    if r.get("ok"):
        r["notes"] = notes + list(r.get("notes") or [])
        r["slots"] = slots_text()
    return r


def _add_lit(plan, name, bots, start, funded, rows) -> dict:
    go, ma, P = _go(), _ma(), PLANS[plan]
    if plan == "builder50k" and not funded and not any(r["role"] == "main" for r in rows):
        r = go.add_account(name, "builder50k", "zlarior", start)      # the first 50K is Zlarior's own account
        return {"ok": bool(r.get("ok")), "say": r.get("say"), "error": r.get("error")}
    path = go._accounts_path()
    file_rows = ma.load_file(path)
    ident = _new_id(plan, file_rows)
    n_same = 1 + sum(1 for r in rows if r["plan"] == plan)
    row = {"id": ident, "name": f"Zlarior {P['label']} #{n_same}", "nt_account": name, "preset": P["preset"],
           "mode": "funded" if funded else "two_week", "eval_start": "" if funded else start, "adapter": "ninjatrader",
           "enabled": True, "armed": False,
           "cli": {"by": TAG, "plan": plan, "bots": bots, "added": _today(),
                   **({"atlas_when_funded": bots == "lit+atlas"} if plan == "builder25k" else {})}}
    if funded:
        row["funded"] = {"start": start, "payouts": {}}
    n = ma.normalize(row)
    if n["problem"]:
        return {"ok": False, "error": f"not added: {n['problem']}"}
    ma.save_file(file_rows + [row], path)
    notes = [x for x in [_allow(name)] if x]
    if plan == "builder25k":
        notes.append("ATLAS $250 joins this 25K only once it is funded AND you say yes"
                     + (" (your yes is saved; Claude wires ATLAS's lane on it then)" if bots == "lit+atlas" else
                        ": add it again later with --bots lit+atlas"))
    what = "funded" if funded else "eval"
    return {"ok": True, "id": ident, "notes": notes,
            "say": f"[OK] {P['label']} {what} {name} = {row['name']} (LIT), from {start}, NOT armed. It joins at the next "
                   "START BOT (you type I ACCEPT LIVE RISK)."}


def _add_atlas(name, start, funded, rows) -> dict:
    if funded:
        return {"ok": False, "error": "ATLAS's funded 25K comes from its passed eval: python -X utf8 -m engine.lit25 --funded "
                                      "\"<Name>\" --start yyyy-mm-dd"}
    if any(r["role"] == "b" for r in rows):
        return {"ok": False, "error": "ATLAS already has its 25K: a 2nd 25K is LIT first (--bots lit+atlas), ATLAS joins once funded"}
    r = _go().add_account(name, "builder25k", "atlas", start)
    return {"ok": bool(r.get("ok")), "say": (r.get("say") or "") + " It joins at the next START BOT.", "error": r.get("error")}


def _add_rapid(name, start, funded, rows, plan="rapideod") -> dict:
    rp, P = _rapid(), PLANS[plan]
    lbl = "Rapid EOD" if plan == "rapideod" else P["label"]
    cur = rp.read()
    others = {f"{r['role']} {r['id']}": r["name"] for r in rows if r["role"] != "rapid"}
    if cur is not None and str(cur.get("plan") or rp.PRESET) != P["preset"]:
        return {"ok": False, "error": f"the Rapid EOD is already {cur['account']} ({rp.plan_info(cur)['label']}): one Rapid only. "
                                      f"Remove it first: python -X utf8 -m engine.accounts remove --name \"{cur['account']}\""}
    if funded:
        if cur is None:
            r = rp.set_account(name, start, others=others, allow=_allow_raise, preset=P["preset"])
            if not r.get("ok"):
                return {"ok": False, "error": r.get("error")}
        r = rp.to_funded(name, start, others=others, allow=_allow_raise)
        if not r.get("ok"):
            return {"ok": False, "error": r.get("error")}
        return {"ok": True, "notes": [x for x in [r.get("note")] if x],
                "say": f"[OK] {lbl} funded {name} from {start} (LIT + ATLAS), NOT armed. START BOT + you type the phrase."}
    if cur is not None and cur["account"] != name and cur.get("stage") != "funded":
        return {"ok": False, "error": f"the Rapid EOD is already {cur['account']} (one Rapid only: \"I'll stick with 1 rapid\"). "
                                      f"Remove it first: python -X utf8 -m engine.accounts remove --name \"{cur['account']}\""}
    if cur is not None and cur.get("stage") == "funded":
        return {"ok": False, "error": f"the Rapid EOD {cur['account']} is funded: one Rapid only (\"I'll stick with 1 rapid\")"}
    r = rp.set_account(name, start, others=others, allow=_allow_raise, preset=P["preset"])
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    b = r["block"]
    return {"ok": True, "notes": [x for x in [r.get("note"), _rules_line(rp, b)] if x],
            "say": f"[OK] {P['label']} = {b['account']} (LIT + ATLAS), eval from {b['eval_start']}, NOT armed. It joins at the "
                   "next START BOT (you type I ACCEPT LIVE RISK)."}


def _rules_line(rp, blk):
    """The numbers the bot will use on the Rapid (so a wrong size shows at once); None when it cannot be read."""
    try:
        return rp.rules_line(blk)
    except Exception:
        return None


def _allow_raise(name):
    _go()._allow(name)


# ---------------------------------------------------------------------------------------------------------------- remove
def remove(name: str) -> dict:
    name = str(name or "").strip()
    rows = inventory()
    r = next((x for x in rows if name and name in (x["name"], str(x.get("id") or ""))), None)
    if r is None:
        return {"ok": False, "error": f"no account {name!r} (python -X utf8 -m engine.accounts list)"}
    go = _go()
    if r["role"] == "rapid":
        _rapid().off()
        if not any(x["name"] == r["name"] for x in inventory()):
            _allow(r["name"], remove=True)
        return {"ok": True, "say": f"Removed {r['name']} (the Rapid EOD): no new trades on it after the next START BOT."}
    if r["role"] == "extra":
        ma = _ma()
        path = go._accounts_path()
        ma.save_file([e for e in ma.load_file(path) if str(e.get("id")) != str(r["id"])], path)
        if not any(x["name"] == r["name"] for x in inventory()):
            _allow(r["name"], remove=True)
        return {"ok": True, "say": f"Removed {r['name']} ({r['id']}): no new trades on it after the next START BOT."}
    out = go.remove_account(r["name"])
    return {"ok": bool(out.get("ok")), "say": out.get("say"), "error": out.get("error")}


# ---------------------------------------------------------------------------------------------------------------- arming
def arm(phrase: str) -> list:
    """START BOT after the owner typed the live phrase (engine/go.step_arm): every account this CLI added gets "armed":
    true, so engine.ninjatrader --start hands it the phrase in memory. Nothing else here ever arms. Returns lines to print."""
    from .tradovate import LIVE_PHRASE
    if phrase != LIVE_PHRASE:
        return []
    go, ma = _go(), _ma()
    path = go._accounts_path()
    rows = ma.load_file(path)
    done = []
    for r in rows:
        if isinstance(r.get("cli"), dict) and r.get("enabled", True) is not False and r.get("armed") is not True:
            r["armed"] = True
            done.append(str(r.get("name") or r.get("id")))
    if done:
        ma.save_file(rows, path)
    return [f"Added accounts armed: {', '.join(done)}"] if done else []


def resume_optin(phrase: str) -> list:
    """After START BOT's own auto-resume opt-in: each armed real account added here comes back by itself after a crash too
    (engine/autoresume.enable_extra, its own proof). Returns lines to print."""
    from .tradovate import LIVE_PHRASE
    if phrase != LIVE_PHRASE:
        return []
    out = []
    for r in _ma().load_file(_go()._accounts_path()):
        nm = str(r.get("nt_account") or "").strip()
        if isinstance(r.get("cli"), dict) and r.get("armed") is True and nm and not _is_sim(nm):
            try:
                from . import autoresume
                autoresume.enable_extra(nm, phrase)
            except Exception as e:
                out.append(f"auto-resume NOT on for {r.get('name')}: {e}")
    return out


# ---------------------------------------------------------------------------------------------------------------- views
def _label(r) -> str:
    bots = {"lit": "LIT", "atlas": "ATLAS", "lit+atlas": "LIT + ATLAS", "blitz": "BLITZ"}.get(r["bots"], r["bots"])
    if r["role"] == "extra" and r.get("atlas_when_funded"):        # a 2nd 25K: LIT now, ATLAS $250 is the owner's yes for later
        bots = "LIT (+ATLAS $250 once funded)" if r["stage"] == "eval" else "LIT (ATLAS $250: not wired yet)"
    plan = PLANS.get(r["plan"], {}).get("label", r["plan"])
    arm = "Sim" if r["sim"] else "armed" if r.get("armed") else "not armed" if r.get("armed") is False else "-"
    return f"{r['name']:24s} {plan:14s} {r['stage']:7s} {bots:28s} {arm}" + ("" if r.get("enabled", True) else " (off)")


def list_lines(rows=None) -> list:
    rows = inventory() if rows is None else rows
    if not rows:
        return ["No accounts yet.", slots_text(rows)]
    return [_label(r) for r in rows] + [slots_text(rows)]


def status_lines() -> list:
    rows = inventory()
    out = []
    go = _go()
    try:
        bals = go.nt_balances()
    except Exception:
        bals = {}
    for r in rows:
        line = _label(r)
        try:
            if r["role"] == "rapid":
                line += " | " + _rapid().status()["text"]
            elif r["plan"] in PLANS and r["plan"] not in RAPID_PLANS:
                m = go._money(r["name"], PLANS[r["plan"]]["preset"], r["role"] == "main", bals)
                line += f" | ${float(m['balance']):,.2f}, floor ${float(m['floor']):,.2f} ({m['source']})"
        except Exception:
            pass
        out.append(line)
    if not rows:
        out.append("No accounts yet.")
    return out + [slots_text(rows)] + list(RULE_LINES)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -X utf8 -m engine.accounts", description="add / list / remove MFFU accounts")
    sub = ap.add_subparsers(dest="cmd")
    a_add = sub.add_parser("add", help="add one account (DISARMED)")
    a_add.add_argument("--plan", required=True)
    a_add.add_argument("--name", required=True, help="the account Name exactly as NinjaTrader's Accounts tab shows it")
    a_add.add_argument("--bots", default=None, help="lit | atlas | lit+atlas (default: what the research picked)")
    a_add.add_argument("--start", default=None, help="first session yyyy-mm-dd (default: today's session)")
    a_add.add_argument("--funded", action="store_true", help="a funded account MFFU issued (needs --start = first funded day)")
    a_rm = sub.add_parser("remove", help="take one account off")
    a_rm.add_argument("--name", required=True)
    sub.add_parser("list")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        if a.funded and not a.start:
            print("--funded needs --start yyyy-mm-dd (the first funded day)")
            return 1
        r = add(a.plan, a.name, a.bots, a.start, a.funded)
        if not r.get("ok"):
            print(f"[NOT ADDED] {r.get('error')}")
            return 1
        print(r.get("say") or "[OK]")
        for n in r.get("notes") or []:
            print(f"  - {n}")
        print(f"  {r.get('slots') or slots_text()}")
        return 0
    if a.cmd == "remove":
        r = remove(a.name)
        print(r.get("say") if r.get("ok") else f"[NOT REMOVED] {r.get('error')}")
        return 0 if r.get("ok") else 1
    print("\n".join(status_lines() if a.cmd == "status" else list_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
