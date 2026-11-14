"""One signal, many accounts: the per-account guard layer of the fleet (engine/fleet.py). OFF by default.

The fleet copies one lead's routed trades (Zlarior = LIT, ATLAS, BLITZ) to N follower accounts at any firm. This module
holds the rules that make each copy THAT account's own decision, on top of the firm's rule engine (engine/firms.py):

  profile_for(spec)        the follower's rule profile: the firm's plan (research/props/firm_rules.json, else a placeholder
                           plan of research/props/copy_profiles.json) + the owner's values, which only ever TIGHTEN a
                           verified firm rule (a looser value is refused and listed in "owner_refused"; an unknown /
                           unverified value may be filled, as before) + the account's own limits ("own": day_stop_usd,
                           week_stop_usd, max_micros, max_risk_usd), each the smaller of the firm's and the owner's.
                           firms.check then sizes and blocks every copy with them (contracts, floor at the stop, the own day
                           stop / the firm's daily loss, best-day rule, ...): never more contracts than the firm allows.
  own_problem(own)         why an "own" block is unusable (None = fine)
  why_not(follower, now)   extra reasons a follower takes no new entry: stopped for today by the owner ("stop_day"), or
                           over the firm's account limit (funded accounts of one plan = max_active; of one firm =
                           accounts.max_funded_total; the owner's accounts outside the fleet = "held_funded")
  confirm_arm(row, inp)    the owner types I ACCEPT LIVE RISK for THIS account Name before it is armed (engine/go.step_arm's
                           phrase); nothing here arms by itself, a page never arms (engine/fleet_api refuses)
  armed_problem(spec)      the live gate's last check: armed for this very Name ("armed_for"), else refused

Nothing here routes, writes or arms. With no data/fleet.json the fleet is never built and this module is never used.

  python -X utf8 -m engine.copy_accounts --show mffu_builder_50k [--stage funded] [--own day_stop_usd=300,max_micros=10]
  python -X utf8 -m engine.copy_accounts --unfilled          (placeholder values still to fill from the firm research)
"""
from __future__ import annotations

import json
import os

from . import firms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_PATH = os.path.join(ROOT, "research", "props", "copy_profiles.json")
OWN_KEYS = {"day_stop_usd": "dll", "week_stop_usd": "weekly_stop", "max_micros": "max_micros", "max_risk_usd": "max_risk_usd"}
LOWER_STRICTER = ("max_micros", "max_minis", "dll", "dd_amount", "weekly_stop", "max_risk_usd", "consistency")
HIGHER_STRICTER = ("lock",)
DD_STRICT = {"static": 0, "eod": 1, "intraday": 2}
INPUT = None              # tests: a fake input() for confirm_arm
_CACHE: dict = {"key": None, "d": None}


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def load_profiles(path: str | None = None) -> dict:
    """copy_profiles.json (cached by mtime). Missing / broken -> {} (no firm account limits, no placeholder plans)."""
    p = path or PROFILES_PATH
    try:
        key = (p, os.path.getmtime(p))
    except OSError:
        return {}
    if _CACHE["key"] != key:
        try:
            with open(p, encoding="utf-8") as fh:
                _CACHE.update(key=key, d=json.load(fh))
        except Exception:
            _CACHE.update(key=key, d={})
    return _CACHE["d"] or {}


def base_profile(plan: str, stage: str = "eval", overrides: dict | None = None) -> dict | None:
    """The firm's plan (firm_rules.json first), else a plan of copy_profiles.json: a placeholder ("placeholder": true, the
    default) or a plan filled from the firm research ("placeholder": false, e.g. Bulenox 2026-11-14). None = unknown plan."""
    P = firms.profile(plan, stage, overrides=overrides)
    pl = (load_profiles().get("plans") or {}).get(plan)
    if P is None and pl is not None:
        P = firms.profile(plan, stage, overrides=overrides, path=PROFILES_PATH)
        if P is not None and pl.get("placeholder", True) is not False:
            P["placeholder"] = True
            P["warn"] = ["placeholder plan: its rules are not filled yet (it never trades until the max loss is known)"] + list(P.get("warn") or [])
        elif P is not None:
            P["filled"] = True
            P["warn"] = ["filled from the firm research (research/props/copy_profiles.json): values marked unverified are third-party "
                         "readings, check them before buying"] + list(P.get("warn") or [])
    return P


# ---------------------------------------------------------------------------------------------------------------- tighten
def _stricter(k, firm_v, own_v) -> bool | None:
    """True = the owner's value is at least as strict as the firm's, False = looser, None = not comparable."""
    if k in LOWER_STRICTER:
        f = float("inf") if firm_v == "none" else _num(firm_v)
        o = float("inf") if own_v == "none" else _num(own_v)
        return None if f is None or o is None else o <= f
    if k in HIGHER_STRICTER:
        f, o = _num(firm_v), _num(own_v)
        if own_v is None:
            return True
        return None if f is None or o is None else o >= f
    if k == "dd_type":
        f, o = DD_STRICT.get(str(firm_v)), DD_STRICT.get(str(own_v))
        return None if f is None or o is None else o >= f
    if k == "flat_by":
        try:
            fh, fm = (int(x) for x in str(firm_v).split(":"))
            oh, om = (int(x) for x in str(own_v).split(":"))
            return oh * 60 + om <= fh * 60 + fm
        except Exception:
            return None
    return own_v == firm_v


def own_problem(own) -> str | None:
    if own in (None, {}):
        return None
    if not isinstance(own, dict):
        return "own limits unreadable (\"own\" must be {day_stop_usd, week_stop_usd, max_micros, max_risk_usd})"
    for k, v in own.items():
        if k not in OWN_KEYS:
            return f"own limit {k} unknown (day_stop_usd | week_stop_usd | max_micros | max_risk_usd)"
        if v is None:
            continue
        n = _num(v)
        if n is None or n <= 0:
            return f"own limit {k} must be a positive number"
        if k == "max_micros" and int(n) != n:
            return "own max_micros must be a whole number"
    return None


def tighten(plan: str, stage: str, rules: dict | None = None, own: dict | None = None) -> dict | None:
    """The plan's profile with the owner's values applied the safe way (see the module doc). None = unknown plan."""
    base = base_profile(plan, stage)
    if base is None:
        return None
    ver = base.get("verified") or {}
    keep, refused = {}, []
    for k, v in (rules or {}).items():
        if v is None:
            continue
        if k == "payout" or not ver.get(k) or base.get(k) is None:
            keep[k] = v                                     # unknown / unverified / payout: the owner's confirmed value
            continue
        s = _stricter(k, base.get(k), v)
        if s:
            keep[k] = v
        else:
            refused.append(f"{k} {v} (the firm's verified {base.get(k)} kept: an owner value may only be stricter)")
    P0 = base_profile(plan, stage, overrides=keep) if keep else base
    applied = {}
    for k, v in (own or {}).items():
        n = _num(v)
        if n is None or n <= 0 or k not in OWN_KEYS:
            continue
        fk = OWN_KEYS[k]
        firm_v = firms.max_micros(P0) if fk == "max_micros" else P0.get(fk)
        fn = _num(firm_v)
        val = int(n) if fk == "max_micros" else float(n)
        if fn is None or val < fn:
            keep[fk] = val
            applied[k] = val
            if fk == "dll":
                keep["dll_type"] = "own day stop"
    P = base_profile(plan, stage, overrides=keep) if keep else base
    if P is None:
        return None
    if applied.get("day_stop_usd") is not None:
        P["firm_dll"], P["firm_dll_type"] = base.get("dll"), base.get("dll_type")
    P["own"] = {k: v for k, v in (own or {}).items() if v is not None}
    P["own_applied"] = applied
    P["owner_refused"] = refused
    if refused:
        P["warn"] = [f"owner value refused: {r}" for r in refused] + list(P.get("warn") or [])
    if base.get("placeholder"):
        P["placeholder"] = True
    if base.get("filled"):
        P["filled"] = True
    return P


def profile_for(spec: dict) -> dict | None:
    """A prop follower's profile (engine/fleet.profile_of): plan + stage + the owner's "rules" + "own"."""
    stage = "funded" if spec.get("stage") == "funded" else "eval"
    own = spec.get("own") if isinstance(spec.get("own"), dict) else None
    return tighten(str(spec.get("plan") or ""), stage, spec.get("rules") or None, own)


# ---------------------------------------------------------------------------------------------------------------- limits
def firm_limits(firm_id: str) -> dict:
    """{"max_funded_total": n | None, "max_eval_active": n | None, "verified": {...}, "n": {...}} for a firm."""
    a = (load_profiles().get("accounts") or {}).get(str(firm_id)) or {}
    out = {"verified": {}, "n": {}}
    for k in ("max_funded_total", "max_eval_active"):
        x = a.get(k)
        out[k] = _num(x.get("v")) if isinstance(x, dict) else _num(x)
        out["verified"][k] = bool(isinstance(x, dict) and x.get("verified"))
        out["n"][k] = x.get("n") if isinstance(x, dict) else None
    return out


def slot_problem(follower, fleet) -> str | None:
    """A funded follower over the firm's account limit (the first ones in data/fleet.json keep their slot)."""
    if follower.stage != "funded" or not follower.profile:
        return None
    held = (getattr(fleet, "cfg", None) or {}).get("held_funded") or {}
    plan, firm = follower.spec.get("plan"), follower.profile.get("firm_id")
    n_plan = int(_num(held.get(plan), 0) or 0)
    n_firm = sum(int(_num(v, 0) or 0) for k, v in held.items() if (firms.profile(k, "funded") or base_profile(k, "funded") or {}).get("firm_id") == firm)
    for f in fleet.followers:
        if f is follower:
            break
        if f.stage != "funded" or f.problem is not None or f.spec.get("killed") or not f.profile:
            continue
        if f.profile.get("firm_id") == firm:
            n_firm += 1
            if f.spec.get("plan") == plan:
                n_plan += 1
    mx = _num(follower.profile.get("max_active"))
    if mx is not None and n_plan + 1 > mx:
        return (f"over the firm's account limit: {follower.profile.get('firm')} allows {int(mx)} funded "
                f"{follower.profile.get('plan')} per person ({n_plan} already)")
    tot = firm_limits(firm).get("max_funded_total")
    if tot is not None and n_firm + 1 > tot:
        return f"over the firm's account limit: {follower.profile.get('firm')} allows {int(tot)} funded accounts per person ({n_firm} already)"
    return None


def stop_today_problem(spec: dict, today: str) -> str | None:
    sd = str(spec.get("stop_day") or "")
    return f"stopped for today by you ({today}; it resumes next session)" if sd and sd == today else None


def why_not(follower, now) -> str | None:
    """Extra reasons (after engine/fleet.Follower.why_not's own) this follower takes no new entry now."""
    from .fleet import trading_day
    return stop_today_problem(follower.spec, trading_day(now)) or slot_problem(follower, follower.fleet)


# ---------------------------------------------------------------------------------------------------------------- arming
def _phrase() -> str:
    from .tradovate import LIVE_PHRASE
    return LIVE_PHRASE


def needs_arming(row: dict) -> bool:
    from .ninjatrader import is_sim
    return row.get("adapter") == "ninjatrader" and bool(row.get("nt_account")) and not is_sim(row.get("nt_account"))


def confirm_arm(row: dict, inp=None) -> tuple:
    """The owner types the live phrase for THIS account Name (as START BOT's step 4). (ok, message). A closed / missing
    console (EOF) or anything else typed = not armed. The phrase is never stored."""
    if not needs_arming(row):
        return True, f"{row.get('nt_account') or 'paper'}: Sim / paper, no arming needed"
    ask = inp or INPUT or input
    try:
        typed = ask(f" Arm {row.get('nt_account')} ({row.get('id')}) for REAL money. Type  {_phrase()}  then Enter "
                    "(anything else stops here, nothing armed): ")
    except (EOFError, KeyboardInterrupt, OSError):
        typed = ""
    if " ".join(str(typed or "").split()).upper() != _phrase():
        return False, f"NOT armed: the phrase was not typed for {row.get('nt_account')}."
    return True, f"{row.get('nt_account')}: phrase typed."


def armed_problem(spec: dict) -> str | None:
    """A real follower armed in the file must be armed for this very Name (--arm writes "armed_for"): a hand-set
    "armed": true, or a Name changed after arming, is refused."""
    if not needs_arming(spec) or spec.get("armed") is not True:
        return None
    af = str(spec.get("armed_for") or "").strip().lower()
    if af != str(spec.get("nt_account") or "").strip().lower():
        return (f"real account {spec.get('nt_account')} was not armed with the typed phrase for this Name "
                f"(python -X utf8 -m engine.fleet --arm {spec.get('id')})")
    return None


# ---------------------------------------------------------------------------------------------------------------- views
def unfilled(path: str | None = None) -> list:
    """[(plan id, [fields still null])] of the placeholder plans + firms with no account limit known."""
    d = load_profiles(path)
    out = []
    for pid, p in sorted((d.get("plans") or {}).items()):
        miss = [k for k, x in (p.get("eval") or {}).items() if isinstance(x, dict) and x.get("v") is None]
        miss += [f"funded.{k}" for k, x in (p.get("funded") or {}).items() if isinstance(x, dict) and x.get("v") is None]
        miss += [f"payout.{k}" for k, x in (p.get("payout") or {}).items() if isinstance(x, dict) and x.get("v") is None]
        out.append((pid, miss))
    for fid, a in sorted((d.get("accounts") or {}).items()):
        x = a.get("max_funded_total")
        if isinstance(x, dict) and x.get("v") is None:
            out.append((f"firm {fid}", ["accounts.max_funded_total"]))
    return out


def _parse_own(s: str | None) -> dict:
    out = {}
    for part in (s or "").split(","):
        k, _, v = part.partition("=")
        if k.strip():
            out[k.strip()] = _num(v.strip())
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -X utf8 -m engine.copy_accounts")
    ap.add_argument("--show", metavar="PLAN")
    ap.add_argument("--stage", default="eval", choices=("eval", "funded"))
    ap.add_argument("--own", help="day_stop_usd=300,max_micros=10,...")
    ap.add_argument("--unfilled", action="store_true")
    a = ap.parse_args(argv)
    if a.show:
        own = _parse_own(a.own)
        bad = own_problem(own)
        if bad:
            print(bad)
            return 1
        P = tighten(a.show, a.stage, None, own)
        if P is None:
            print(f"unknown plan {a.show}")
            return 1
        print(f"{P.get('label')} ({a.stage})" + ("  PLACEHOLDER" if P.get("placeholder") else ""))
        for ln in firms.describe(P):
            print("  " + ln)
        if P.get("own_applied"):
            print("  own limits: " + ", ".join(f"{k} {v}" for k, v in P["own_applied"].items()))
        lim = firm_limits(P.get("firm_id"))
        print(f"  funded accounts a person may hold: this plan {P.get('max_active') if a.stage == 'funded' else '(see --stage funded)'}, "
              f"the firm {lim.get('max_funded_total') if lim.get('max_funded_total') is not None else 'unknown'}")
        for w in P.get("warn") or []:
            print("  ! " + w)
        return 0
    if a.unfilled:
        for pid, miss in unfilled():
            print(f"{pid}: " + (", ".join(miss) if miss else "complete"))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
