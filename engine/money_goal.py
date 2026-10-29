"""Road to $10K / Stingray 3LT (owner 2026-10-26: "a $10,000 month by February 2027; a 2024 Stingray 3LT before I turn 19").

Read-only to trading: nothing here arms, routes, sizes or changes a config. It only reads the account data the dashboards
already have and the owner's own money figures, and writes one gitignored file of those figures.

The card (build(), pure), in this order on both dashboards:
  next     the next action in one line (a payout to request, a passed eval to switch, the next evals to buy, or wait)
  stack    the owner's 9 planned accounts (1 MFFU Builder 50K Zlarior, 2 MFFU Builder 25K ATLAS, 4 LucidPro 50K Zlarior,
           2 FundedNext Rapid Daily 50K Zlarior), each slot's state from the real data (not bought / eval / passed / funded /
           paying), how many are funded, and the $ a month once all are funded at the stored H2 2026 rates
           (research/second/money_goal_rates.json, built by tools/money_goal_rates.py from the research files)
  My goals (at the bottom)
    1. "$10K month by February 2027": this month so far, a bar split into jobs + Kalshi (typed in by the owner on the PC)
       + prop payouts (recorded with the bot: engine.account_b --payout, eval_life --payout / data/accounts.json
       funded.payouts; x the firm's split = to you), and the plan line once all 9 are funded
    2. "2024 Stingray 3LT before I turn 19 (Feb 22, 2027)": saved vs the $38,000 target (40% down on ~$78K + a $7K cushion)
       with a stretch marker at $46,000 (50% down + cushion), days left, $ a week needed from today, and on pace / behind
       by $X at the current pace (the savings entries since the $20,000 start of 2026-10-26)
    3. "C8 Z06": saved vs $60,000 (about $55K down + $5K cushion on a ~$108K all-in 2023-24 Z06), no date
  "current pace" / "plan pace" label every projection: backtest rates and the owner's own pace, not promises.

Owner figures: data/goals_money.json (gitignored), written only by the PC's local form (engine/money_api.py, POST refused
off this PC by engine/cloud_guard.local_only). The heartbeat carries them (heartbeat_block, unless "publish" is off) so the
cloud's data.json and the PC's live.json show the same card on the phone, read-only.

    python -X utf8 -m engine.money_goal            the card from the local file + the plan alone (no bot)
"""
from __future__ import annotations

import calendar
import copy
import datetime as dt
import json
import math
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "goals_money.json")            # gitignored: the owner's savings / jobs / Kalshi figures
RATES_PATH = os.path.join(ROOT, "research", "second", "money_goal_rates.json")
VERSION = 1
MAX_SAVINGS_ROWS = 120
PACE_MIN_DAYS = 7                  # a pace needs two balances at least a week apart
PACE_MAX_DAYS = 180

# Every value is editable in the PC form (engine/money_api.py -> data/goals_money.json "settings").
DEFAULTS = {
    "month_goal": 10000.0, "goal_by": "2027-02",              # goal 1: a $10K month by February 2027
    "start": {"usd": 20000.0, "day": "2026-10-26"},            # the savings balance the owner gave (2026-10-26)
    # goal 2 (owner 2026-10-26 final): a 2024 C8 Stingray 3LT before he turns 19 (2027-02-22), ~$78K all-in; target 40% down
    # ($31.2K) + a $7K cushion = $38K; stretch 50% down + cushion = $46K
    "car": {"name": "2024 Stingray 3LT", "short": "Stingray 3LT", "why": "before I turn 19", "by": "2027-02-22", "price": 78000.0,
            "target": 38000.0, "target_note": "40% down on ~$78K all-in + a $7K cushion",
            "stretch": 46000.0, "stretch_note": "50% down + the cushion"},
    # goal 3: a C8 Z06, no date
    "z06": {"name": "C8 Z06", "target": 60000.0, "note": "about $55K down + a $5K cushion on a ~$108K all-in 2023-24 Z06"},
    "plan": {"jobs": 2900.0, "kalshi_day_lo": 50.0, "kalshi_day_hi": 100.0, "kalshi_days": 30},
    "publish": False,                                         # the phone shows the figures (the public dashboard site)
}
# the owner's plan (chat 2026-10-26): per account type the count, the bot, the firm's cap, the price + where to get it
TYPES = {
    "lit_b50": {"label": "MFFU Builder 50K", "short": "MFFU 50K", "bot": "Zlarior", "firm": "MFFU", "count": 1, "split": 0.8,
                "cap": "MFFU allows 1", "price": 91.80, "plan": "mffu_builder_50k",
                "buy": "your MFFU code (you paid $91.80); try MKT91 or PROPSCOPE at checkout"},
    "atlas_b25": {"label": "MFFU Builder 25K", "short": "MFFU 25K", "bot": "ATLAS", "firm": "MFFU", "count": 2, "split": 0.8,
                  "cap": "MFFU allows 2 active", "price": 43.0, "plan": "mffu_builder_25k", "bot_slots": 1,
                  "buy": "your MFFU code (the last 25K was $43)",
                  "bot_note": "the bot runs ATLAS on one 25K today (a 2nd ATLAS account is not built yet)"},
    "lit_l50": {"label": "LucidPro 50K", "short": "LucidPro", "bot": "Zlarior", "firm": "Lucid", "count": 4, "split": 0.9,
                "cap": "Lucid allows 5 per household", "price": 115.40, "plan": "lucid_pro_50k", "preset": "lucid_pro_50k",
                "buy": "code VIBES or ETFPROMO, check the total at checkout"},
    "lit_fn50": {"label": "FundedNext Rapid Daily 50K", "short": "FundedNext", "bot": "Zlarior", "firm": "FundedNext", "count": 2,
                 "split": 0.9, "cap": "no account cap found", "price": 169.99, "plan": "fn_rapid_daily_50k", "preset": "fn_rapid_daily_50k",
                 "buy": "the no-code first-buy offer (up to 50% off), check the total at checkout"},
}
ORDER = ("lit_b50", "atlas_b25", "lit_l50", "lit_fn50")
# the stored H2 2026 rates (tools/money_goal_rates.py); used only when the rates file is missing (tests: equal to the file)
FALLBACK_RATES = {"lit_b50": 915, "atlas_b25": 517, "lit_l50": 938, "lit_fn50": 629}
FALLBACK_REF = {"lit_b50": 66, "atlas_b25": 39, "lit_l50": 43, "lit_fn50": 44}
STATES = ("not bought", "eval", "passed", "funded", "paying")
RANK = {"paying": 5, "funded": 4, "passed": 3, "eval": 2, "failed": 1, "not bought": 0}
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TEXT_BAD = re.compile(r"[<>\"`\\{}]")


# ------------------------------------------------------------------------------------------------ helpers
def _f(x, d=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else d
    except (TypeError, ValueError):
        return d


def _money(v, sign=False) -> str:
    v = float(v or 0)
    s = f"${abs(v):,.0f}"
    if v < 0:
        return "-" + s
    return ("+" + s) if sign and v > 0 else s


def _k(v) -> str:
    """$10K, $12.5K, $950 (titles)."""
    v = float(v or 0)
    if abs(v) >= 1000:
        t = f"{v / 1000:.1f}".rstrip("0").rstrip(".")
        return f"${t}K"
    return _money(v)


def _et_day(now) -> dt.date:
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(now), ZoneInfo("America/New_York")).date()


def month_label(m: str) -> str:
    try:
        return f"{calendar.month_name[int(m[5:7])]} {int(m[:4])}"
    except Exception:
        return str(m)


def day_label(d: str) -> str:
    try:
        x = dt.date.fromisoformat(d)
        return f"{calendar.month_abbr[x.month]} {x.day}, {x.year}"
    except Exception:
        return str(d)


def _add_months(m: str, n: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + n
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _deep(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep(out[k], v)
        elif k in out:
            out[k] = copy.deepcopy(v)
    return out


# ------------------------------------------------------------------------------------------------ the owner's file
def _empty() -> dict:
    return {"v": VERSION, "updated": None, "savings": [], "months": {}, "settings": copy.deepcopy(DEFAULTS)}


def load(path: str | None = None) -> dict:
    """data/goals_money.json with the defaults filled in. Missing / unreadable -> the empty inputs. Never raises."""
    out = _empty()
    try:
        with open(path or PATH, encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        return out
    if not isinstance(raw, dict):
        return out
    out["updated"] = raw.get("updated") if isinstance(raw.get("updated"), (int, float)) else None
    rows = []
    for r in raw.get("savings") or []:
        if isinstance(r, dict) and _DAY.match(str(r.get("day") or "")) and _f(r.get("usd")) is not None:
            rows.append({"day": str(r["day"]), "usd": round(float(r["usd"]), 2)})
    out["savings"] = sorted(rows, key=lambda r: r["day"])[-MAX_SAVINGS_ROWS:]
    for m, v in (raw.get("months") or {}).items() if isinstance(raw.get("months"), dict) else []:
        if _MONTH.match(str(m)) and isinstance(v, dict):
            out["months"][str(m)] = {k: round(float(v[k]), 2) for k in ("jobs", "kalshi") if _f(v.get(k)) is not None}
    if isinstance(raw.get("settings"), dict):
        out["settings"] = _deep(DEFAULTS, raw["settings"])
    return out


def settings_of(inputs: dict | None) -> dict:
    return _deep(DEFAULTS, (inputs or {}).get("settings") or {})


def _num_in(d: dict, key: str, lo: float, hi: float, errs: list, label: str):
    if key not in d or d[key] in (None, ""):
        return None
    v = _f(d[key])
    if v is None or v < lo or v > hi:
        errs.append(f"{label} must be a number from {lo:,.0f} to {hi:,.0f}")
        return None
    return round(v, 2)


def _text_in(d: dict, key: str, n: int, errs: list, label: str):
    if key not in d or d[key] in (None, ""):
        return None
    t = str(d[key]).strip()
    if not t or len(t) > n or _TEXT_BAD.search(t):
        errs.append(f"{label}: plain words, up to {n} characters")
        return None
    return t


def _day_in(d: dict, key: str, errs: list, label: str):
    if key not in d or d[key] in (None, ""):
        return None
    try:
        x = dt.date.fromisoformat(str(d[key]))
        if not 2020 <= x.year <= 2100:
            raise ValueError
        return x.isoformat()
    except ValueError:
        errs.append(f"{label} must look like 2027-02-22")
        return None


def _clean_settings(s: dict, errs: list) -> dict:
    """The settings part of a form post -> only known keys with sane values (errors listed in errs)."""
    out: dict = {}
    if not isinstance(s, dict):
        return out
    v = _num_in(s, "month_goal", 100, 10_000_000, errs, "The month goal")
    if v is not None:
        out["month_goal"] = v
    if s.get("goal_by"):
        if _MONTH.match(str(s["goal_by"])):
            out["goal_by"] = str(s["goal_by"])
        else:
            errs.append("The goal month must look like 2027-02")
    if "publish" in s:
        if not isinstance(s["publish"], bool):
            errs.append("publish must be true or false")
        else:
            out["publish"] = s["publish"]
    if isinstance(s.get("start"), dict):
        so = {}
        v = _num_in(s["start"], "usd", 0, 100_000_000, errs, "The starting balance")
        if v is not None:
            so["usd"] = v
        d = _day_in(s["start"], "day", errs, "The starting day")
        if d:
            so["day"] = d
        if so:
            out["start"] = so
    if isinstance(s.get("car"), dict):
        c, co = s["car"], {}
        for k, n, lab in (("name", 40, "The car name"), ("short", 24, "The short car name"), ("why", 40, "The reason"),
                          ("target_note", 80, "The target note"), ("stretch_note", 80, "The stretch note")):
            t = _text_in(c, k, n, errs, lab)
            if t:
                co[k] = t
        for k, lab in (("price", "The car price"), ("target", "The car target"), ("stretch", "The stretch target")):
            v = _num_in(c, k, 0, 10_000_000, errs, lab)
            if v is not None:
                co[k] = v
        d = _day_in(c, "by", errs, "The car date")
        if d:
            co["by"] = d
        if co:
            out["car"] = co
    if isinstance(s.get("z06"), dict):
        z, zo = s["z06"], {}
        t = _text_in(z, "name", 40, errs, "The Z06 name")
        if t:
            zo["name"] = t
        t = _text_in(z, "note", 80, errs, "The Z06 note")
        if t:
            zo["note"] = t
        v = _num_in(z, "target", 0, 10_000_000, errs, "The Z06 target")
        if v is not None:
            zo["target"] = v
        if zo:
            out["z06"] = zo
    if isinstance(s.get("plan"), dict):
        p, po = s["plan"], {}
        for k, lo, hi, lab in (("jobs", 0, 1_000_000, "Plan jobs $"), ("kalshi_day_lo", 0, 100_000, "Kalshi low $ a day"),
                               ("kalshi_day_hi", 0, 100_000, "Kalshi high $ a day"), ("kalshi_days", 0, 31, "Kalshi days a month")):
            v = _num_in(p, k, lo, hi, errs, lab)
            if v is not None:
                po[k] = v
        if po:
            out["plan"] = po
    return out


def save(patch: dict, path: str | None = None, now=None) -> dict:
    """The PC form's post -> data/goals_money.json. Accepted keys only:
      savings (the balance now, $) + savings_day (yyyy-mm-dd, default today), savings_delete (a day to remove),
      month (yyyy-mm, default this month) + jobs ($ that month) and / or kalshi ($ P&L that month), settings {...}.
    Refuses anything malformed (nothing written). -> {"ok", "say" | "error", "inputs"}"""
    path = path or PATH
    now = int(now or time.time())
    today = _et_day(now)
    if not isinstance(patch, dict):
        return {"ok": False, "error": "Nothing to save."}
    known = {"savings", "savings_day", "savings_delete", "month", "jobs", "kalshi", "settings"}
    extra = sorted(set(patch) - known)
    if extra:
        return {"ok": False, "error": "Unknown field: " + ", ".join(extra)[:120]}
    errs: list = []
    cur = load(path)
    say = []
    sv = _num_in(patch, "savings", 0, 100_000_000, errs, "Savings")
    if sv is not None:
        day = str(patch.get("savings_day") or today.isoformat())
        try:
            d = dt.date.fromisoformat(day)
            if d > today + dt.timedelta(days=1) or d.year < 2020:
                errs.append("The savings day must be today or earlier")
        except ValueError:
            errs.append("The savings day must look like 2026-10-26")
        if not errs:
            cur["savings"] = sorted([r for r in cur["savings"] if r["day"] != day] + [{"day": day, "usd": sv}],
                                    key=lambda r: r["day"])[-MAX_SAVINGS_ROWS:]
            say.append(f"savings {_money(sv)} on {day}")
    if patch.get("savings_delete"):
        day = str(patch["savings_delete"])
        if not _DAY.match(day) or not any(r["day"] == day for r in cur["savings"]):
            errs.append("No savings entry on that day")
        else:
            cur["savings"] = [r for r in cur["savings"] if r["day"] != day]
            say.append(f"removed the savings entry of {day}")
    jobs = _num_in(patch, "jobs", 0, 10_000_000, errs, "Job income")
    kal = _num_in(patch, "kalshi", -10_000_000, 10_000_000, errs, "Kalshi P&L")
    if jobs is not None or kal is not None:
        m = str(patch.get("month") or today.strftime("%Y-%m"))
        if not _MONTH.match(m):
            errs.append("The month must look like 2026-10")
        else:
            row = dict(cur["months"].get(m) or {})
            if jobs is not None:
                row["jobs"] = jobs
            if kal is not None:
                row["kalshi"] = kal
            cur["months"][m] = row
            say.append(f"{month_label(m)}: " + ", ".join(x for x in (f"jobs {_money(jobs)}" if jobs is not None else "",
                                                                     f"Kalshi {_money(kal)}" if kal is not None else "") if x))
    if patch.get("settings") is not None:
        st = _clean_settings(patch["settings"], errs)
        if st:
            cur["settings"] = _deep(cur["settings"], st)
            say.append("targets and settings")
    c = cur["settings"]["car"]
    if not errs and c["stretch"] and c["stretch"] < c["target"]:
        errs.append("The stretch target is below the car target")
    p = cur["settings"]["plan"]
    if not errs and p["kalshi_day_lo"] > p["kalshi_day_hi"]:
        errs.append("Kalshi low $ a day is above the high")
    if errs:
        return {"ok": False, "error": "; ".join(errs)[:300]}
    if not say:
        return {"ok": False, "error": "Nothing to save: type a number first."}
    cur["updated"] = now
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)
    return {"ok": True, "say": "Saved: " + "; ".join(say) + ".", "inputs": cur}


def local_block(path: str | None = None) -> dict:
    """The owner's figures as the PC shows them (always full)."""
    inp = load(path)
    return {"v": VERSION, "t": inp.get("updated"), "inputs": inp}


def heartbeat_block(path: str | None = None) -> dict | None:
    """The heartbeat's "money" block (-> the cloud's data.json and the PC's live.json): the figures, or only the settings
    when the owner switched "show on the phone" off. None before the first save. Never raises."""
    try:
        inp = load(path)
        if not inp.get("updated"):
            return None
        if inp["settings"].get("publish") is False:
            return {"v": VERSION, "t": inp["updated"], "hidden": True, "inputs": {"settings": inp["settings"]}}
        return {"v": VERSION, "t": inp["updated"], "inputs": {**inp, "savings": inp["savings"][-24:]}}
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ rates
def load_rates(path: str | None = None) -> dict:
    """{type: {"usd_month", "usd_month_ref", "src"}} from research/second/money_goal_rates.json (fallback: the stored values)."""
    try:
        with open(path or RATES_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        T = d.get("types") or {}
        out = {k: {"usd_month": float(T[k]["usd_month"]), "usd_month_ref": _f(T[k].get("usd_month_ref"), 0.0),
                   "ref_span": T[k].get("ref_span"), "src": T[k].get("src"), "writeup": T[k].get("writeup")} for k in ORDER}
        out["_meta"] = {"built": d.get("built"), "span": d.get("span") or "H2", "file": "research/second/money_goal_rates.json"}
        return out
    except Exception:
        out = {k: {"usd_month": float(FALLBACK_RATES[k]), "usd_month_ref": float(FALLBACK_REF[k]), "src": "stored fallback"} for k in ORDER}
        out["_meta"] = {"built": None, "span": "H2", "file": "fallback (rates file missing)"}
        return out


# ------------------------------------------------------------------------------------------------ the accounts
def _ab(data: dict):
    S = data.get("second") or {}
    ab = S.get("account_b") or ((S.get("route") or {}).get("account_b") if isinstance(S.get("route"), dict) else None)
    return ab if isinstance(ab, dict) else None


def _pays(d) -> dict:
    return {str(k): float(v) for k, v in (d or {}).items() if (_f(v, 0) or 0) > 0} if isinstance(d, dict) else {}


def _type_of(a: dict) -> str | None:
    from . import scale_plan as SP
    fp = (a.get("funded") or {}).get("preset") if isinstance(a.get("funded"), dict) else None
    p = SP.plan_id(" ".join(str(x) for x in (a.get("firm"), a.get("plan"), fp) if x)) or SP.plan_id(fp)
    if p is None and a.get("kind") == "funded":
        p = "mffu_builder_50k"                     # engine.eval_life --to-funded's default plan
    return SP.type_key("LIT", p) if p else None


def real_accounts(data: dict) -> list:
    """Every account the data knows: [{type, state (eval / passed / funded / paying / failed), name, src, payouts_n,
    payouts {day: gross}, tracker, note}]. Zlarior's 50K from the eval block (engine/goals._lit_account), the extra / funded
    Zlarior accounts from data.json "accounts", ATLAS's 25K from account B, then the owner's list (business.json via the
    scale block) for accounts the bot has not reported."""
    from . import goals as G
    rows = []
    acc = [a for a in data.get("accounts") or [] if isinstance(a, dict) and a.get("id") and not a.get("error")]
    try:                                           # Zlarior's main 50K (PC eval, else the cloud's eval clock)
        lit = G._lit_account(data)
    except Exception:
        lit = {}
    st = str(lit.get("status") or "")
    if lit.get("stage") == "funded":
        rows.append({"type": "lit_b50", "state": "funded", "name": lit.get("name"), "src": lit.get("source")})
    elif st in ("open", "passed", "failed") or (lit.get("balance") is not None and st != "not started"):
        rows.append({"type": "lit_b50", "state": st if st in ("passed", "failed") else "eval",
                     "name": lit.get("name") or "MFFU Builder 50K", "src": lit.get("source")})
    for a in acc:                                  # extra / funded Zlarior accounts (multi_account, eval_life --to-funded)
        if a.get("source") == "cloud" or not (a.get("extra") or a.get("kind") == "funded"):
            continue
        t = _type_of(a)
        if t not in TYPES:
            continue
        if a.get("kind") == "funded" or a.get("mode") == "funded":
            pays = _pays((a.get("funded") or {}).get("payouts") if isinstance(a.get("funded"), dict) else None)
            trk = None
            if t == "lit_b50":
                try:
                    from . import funded_life as FL
                    trk = FL.from_account(a)
                except Exception:
                    trk = None
            lost = bool((trk or {}).get("lost"))
            rows.append({"type": t, "state": "failed" if lost else ("paying" if pays else "funded"), "name": a.get("name") or a["id"],
                         "src": "bot accounts", "payouts": pays, "payouts_n": len(pays), "tracker": trk,
                         "note": "funded account lost: buy a new eval" if lost else None})
        else:
            s = str((a.get("eval") or {}).get("status") or "open")
            rows.append({"type": t, "state": {"passed": "passed", "failed": "failed"}.get(s, "eval"), "name": a.get("name") or a["id"],
                         "src": "bot accounts"})
    ab = _ab(data)                                 # ATLAS's 25K (engine/account_b.py; stage "funded" after the owner's switch)
    if ab and (ab.get("account") or ab.get("eval")):
        nm = ab.get("label") or ab.get("account") or "MFFU Builder 25K"
        if ab.get("stage") == "funded":
            f = ab.get("funded") if isinstance(ab.get("funded"), dict) else {}
            pays = _pays(f.get("payouts") or ab.get("payouts"))
            n = max(len(pays), int(_f(f.get("payouts_n"), 0) or 0))
            s = str(f.get("status") or "")
            bad = s in ("lost", "stuck") or bool(f.get("lost"))
            rows.append({"type": "atlas_b25", "state": "failed" if bad else ("paying" if n else "funded"), "name": nm, "src": "account B",
                         "payouts": pays, "payouts_n": n, "tracker": f or None,
                         "note": (("funded account lost" if s == "lost" or f.get("lost") else "funded account stuck (under $100 of room)")
                                  + ": buy a new eval") if bad else None})
        else:
            ev = ab.get("eval") if isinstance(ab.get("eval"), dict) else {}
            s = str(ev.get("status") or "")
            if s != "no eval_start" or ab.get("account"):
                rows.append({"type": "atlas_b25", "state": {"passed": "passed", "failed": "failed", "stuck": "failed"}.get(s, "eval"),
                             "name": nm, "src": "account B", "note": "eval stuck (under $100 of room): buy a new one" if s == "stuck" else None})
    live_n: dict = {}                              # the owner's list (business.json + the bot's view, engine/scale_plan.py)
    for r in rows:
        live_n[r["type"]] = live_n.get(r["type"], 0) + 1
    sc = [r for r in ((data.get("scale") or {}).get("accounts") or []) if isinstance(r, dict) and r.get("type") in TYPES]
    for t in ORDER:
        held = sorted([r for r in sc if r["type"] == t and r.get("stage") in ("eval", "passed", "funded")],
                      key=lambda r: -RANK.get(r.get("stage"), 0))
        for r in held[live_n.get(t, 0):]:
            rows.append({"type": t, "state": r["stage"], "name": r.get("label") or r.get("id"), "src": r.get("src") or "business.json"})
    return rows


def _planned(data: dict) -> dict:
    """{type: [planned start days]} from the owner's list (scale block, stage planned)."""
    out: dict = {}
    for r in ((data.get("scale") or {}).get("accounts") or []):
        if isinstance(r, dict) and r.get("type") in TYPES and r.get("stage") == "planned":
            out.setdefault(r["type"], []).append(str(r.get("start") or ""))
    return out


def stack(data: dict, rates: dict | None = None) -> dict:
    """The 9 planned slots with their state, the funded count and the $ a month now / once all are funded."""
    rates = rates or load_rates()
    rows = real_accounts(data)
    planned = _planned(data)
    slots, groups = [], []
    for t in ORDER:
        T = TYPES[t]
        mine = sorted([r for r in rows if r["type"] == t], key=lambda r: -RANK.get(r["state"], 0))
        rate = rates[t]["usd_month"]
        g = {"type": t, "label": T["label"], "short": T["short"], "bot": T["bot"], "firm": T["firm"], "count": T["count"], "cap": T["cap"],
             "usd_month_each": rate, "usd_month": round(rate * T["count"], 2), "price": T["price"], "slots": []}
        pl = list(planned.get(t) or [])
        for i in range(T["count"]):
            r = mine[i] if i < len(mine) else None
            st = r["state"] if r else "not bought"
            note = (r or {}).get("note")
            if st == "failed":
                note = note or "last eval failed: buy a new one"
                st = "not bought"
            if st == "not bought" and not note:
                if pl:
                    d = pl.pop(0)
                    note = f"planned {d}" if d else "planned"
                elif i >= int(T.get("bot_slots") or T["count"]):
                    note = T.get("bot_note")
            s = {"type": t, "n": i + 1, "label": T["label"] + (f" #{i + 1}" if T["count"] > 1 else ""), "bot": T["bot"], "state": st,
                 "name": (r or {}).get("name") if st != "not bought" else None, "src": (r or {}).get("src") if r else None,
                 "payouts_n": (r or {}).get("payouts_n") or 0, "usd_month": rate, "note": note,
                 "runnable": i < int(T.get("bot_slots") or T["count"])}
            slots.append(s)
            g["slots"].append({k: s[k] for k in ("n", "state", "name", "note", "payouts_n")})
        g["extra"] = max(0, len(mine) - T["count"])           # more accounts of this type than the plan holds
        groups.append(g)
    funded = [s for s in slots if s["state"] in ("funded", "paying")]
    bought = [s for s in slots if s["state"] != "not bought"]
    all_m = round(sum(s["usd_month"] for s in slots), 2)
    now_m = round(sum(s["usd_month"] for s in funded), 2)
    ref = round(sum(rates[s["type"]].get("usd_month_ref") or 0 for s in slots), 2)
    n = len(slots)
    sent = (f"{len(funded)} of {n} funded, {len(bought)} of {n} bought. Once all {n} are funded: about {_money(all_m)} a month "
            f"(the 2026 Jul-Oct backtest rate, plan pace).")
    return {"slots": slots, "groups": groups, "of": n, "funded": len(funded), "bought": len(bought),
            "paying": sum(1 for s in slots if s["state"] == "paying"), "usd_month_all": all_m, "usd_month_now": now_m,
            "usd_month_ref_all": ref, "span": (rates.get("_meta") or {}).get("span", "H2"), "rates_file": (rates.get("_meta") or {}).get("file"),
            "rates_built": (rates.get("_meta") or {}).get("built"), "sentence": sent, "_rows": rows}


# ------------------------------------------------------------------------------------------------ money in
def payouts(rows: list) -> list:
    """Every recorded payout [{day, gross, to_you, type, name}] (the firm's split: MFFU 80%, Lucid / FundedNext 90%)."""
    out = []
    for r in rows:
        sp = TYPES.get(r["type"], {}).get("split", 0.8)
        for d, v in (r.get("payouts") or {}).items():
            out.append({"day": d, "gross": round(v, 2), "to_you": round(v * sp, 2), "type": r["type"], "name": r.get("name")})
    return sorted(out, key=lambda x: x["day"])


def month_in(inputs: dict, pays: list, month: str) -> dict:
    """The month's income lines: jobs + Kalshi (the owner's figures) + prop payouts to you (recorded with the bot)."""
    m = (inputs.get("months") or {}).get(month) or {}
    jobs, kal = m.get("jobs"), m.get("kalshi")
    prop = round(sum(p["to_you"] for p in pays if p["day"][:7] == month), 2)
    return {"month": month, "jobs": jobs, "kalshi": kal, "prop": prop, "entered": jobs is not None or kal is not None,
            "total": round((jobs or 0) + (kal or 0) + prop, 2), "prop_n": sum(1 for p in pays if p["day"][:7] == month)}


# ------------------------------------------------------------------------------------------------ savings
def balance_points(inputs: dict) -> list:
    """The savings balances in time order: the starting balance (settings.start) + the owner's entries (an entry on the
    start day replaces the start)."""
    S = settings_of(inputs)
    pts = {r["day"]: r["usd"] for r in inputs.get("savings") or []}
    st = S.get("start") or {}
    if _DAY.match(str(st.get("day") or "")) and _f(st.get("usd")) is not None:
        pts.setdefault(str(st["day"]), float(st["usd"]))
    return [{"day": d, "usd": round(v, 2)} for d, v in sorted(pts.items())]


def pace_week(points: list) -> dict | None:
    """$ a week from the balances: the newest vs the oldest one 7-180 days before it. None until two are a week apart."""
    if len(points) < 2:
        return None
    new = points[-1]
    d1 = dt.date.fromisoformat(new["day"])
    old = next((p for p in points if PACE_MIN_DAYS <= (d1 - dt.date.fromisoformat(p["day"])).days <= PACE_MAX_DAYS), None)
    if not old:
        return None
    days = (d1 - dt.date.fromisoformat(old["day"])).days
    return {"usd_week": round((new["usd"] - old["usd"]) / days * 7, 2), "from": old["day"], "to": new["day"], "days": days}


def car_goal(C: dict, saved, points: list, today: dt.date, hidden: bool) -> dict:
    """Goal 2: saved vs the target with a stretch marker, days left, $ a week needed from today, on pace / behind at the
    current pace."""
    target, stretch = float(C["target"]), float(C.get("stretch") or 0)
    by = str(C["by"])
    try:
        days_left = max(0, (dt.date.fromisoformat(by) - today).days)
    except ValueError:
        days_left = 0
    title = f"{C['name']} {C.get('why') or ''} ({day_label(by)})".replace("  ", " ")
    top = max(target, stretch)
    out = {"k": "car", "kind": "car", "title": title, "name": C["name"], "short": C.get("short") or C["name"], "price": C.get("price"),
           "target": target, "target_note": C.get("target_note"), "stretch": stretch or None, "stretch_note": C.get("stretch_note"),
           "by": by, "by_label": day_label(by), "days_left": days_left, "weeks_left": round(days_left / 7, 1),
           "scale": top, "target_at": round(target / top, 4) if top else 1.0, "hidden": hidden}
    if hidden or saved is None:
        out.update(saved=None, frac=0.0, bar=0.0, status="hidden" if hidden else "unknown",
                   sentence=f"Target {_money(target)} by {day_label(by)} ({days_left} days left); "
                            + ("your savings are hidden on the phone." if hidden else "enter your savings on the PC."))
        return out
    left = round(max(0.0, target - saved), 2)
    need = round(left / (days_left / 7), 2) if days_left > 0 and left > 0 else (0.0 if left <= 0 else None)
    pc = pace_week(points)
    proj = gap = None
    if saved >= target:
        status = "reached"
    elif days_left <= 0:
        status = "late"
    elif pc is None:
        status = "unknown"
    else:
        proj = round(saved + pc["usd_week"] * days_left / 7, 2)
        gap = round(proj - target, 2)
        status = "on_pace" if gap >= 0 else "behind"
    out.update(saved=saved, left=left, frac=round(min(1.0, saved / target), 4) if target else 0.0,
               bar=round(min(1.0, saved / top), 4) if top else 0.0, need_week=need, pace=pc, projected=proj, gap=gap, status=status,
               stretch_left=round(max(0.0, stretch - saved), 2) if stretch else None,
               stretch_need_week=round(max(0.0, stretch - saved) / (days_left / 7), 2) if stretch and days_left > 0 else None)
    bits = [f"{_money(saved)} of {_money(target)} ({round(100 * saved / target) if target else 0}%)."]
    if status == "reached":
        bits.append("Target reached" + (f"; {_money(out['stretch_left'])} to the {_money(stretch)} stretch." if stretch and saved < stretch else "."))
    elif status == "late":
        bits.append(f"{day_label(by)} has passed: {_money(left)} short.")
    else:
        bits.append(f"{days_left} days left: {_money(need)} a week needed.")
        if status == "on_pace":
            bits.append(f"On pace at the current pace ({_money(pc['usd_week'])} a week): {_money(gap, True)} over by {day_label(by)}.")
        elif status == "behind":
            bits.append(f"Behind by {_money(-gap)} at the current pace ({_money(pc['usd_week'])} a week).")
        else:
            bits.append("Current pace: enter your balance again a week after the last one.")
    out["sentence"] = " ".join(bits)
    return out


# ------------------------------------------------------------------------------------------------ the next action
def next_action(st: dict, rows: list) -> dict:
    """One line: a payout to request, a passed eval to switch, else the next account(s) to buy, else wait."""
    for r in rows:                                        # 1. money waiting: a payout ready on a funded MFFU account
        t = r.get("tracker") or {}
        if isinstance(t, dict) and t.get("ready") and (_f(t.get("max_request"), 0) or 0) > 0:
            nm = r.get("name") or TYPES[r["type"]]["label"]
            return {"kind": "payout", "text": f"Request {_money(t['max_request'])} on {nm} in the MFFU dashboard "
                                              f"({_money(_f(t.get('to_you'), t['max_request'] * 0.8))} to you), then record it.",
                    "how": t.get("record_cmd") or "The bot never requests a payout for you."}
    for s in st["slots"]:                                 # 2. a passed eval waits for the funded switch
        if s["state"] == "passed":
            how = ("Start page > Accounts > ATLAS's 25K > Passed -> funded" if s["type"] == "atlas_b25" else
                   "Start page > Accounts > Passed -> funded (or python -X utf8 -m engine.eval_life --to-funded --account \"<funded Name>\" --start <day>)"
                   if s["type"] == "lit_b50" else
                   "python -X utf8 -m engine.multi_account --set --id <its id> --mode funded --funded-start <first funded day> (with the funded account's NinjaTrader Name)")
            return {"kind": "funded", "text": f"Switch the passed {s['label']} ({s['bot']}) to funded: {TYPES[s['type']]['firm']} gives it a new account Name.",
                    "how": how}
    for t in ORDER:                                       # 3. buy what the plan still misses (and the bot can run)
        T = TYPES[t]
        open_ = [s for s in st["slots"] if s["type"] == t and s["state"] == "not bought" and s["runnable"]]
        if not open_:
            continue
        n = min(2, len(open_))
        cost = round(n * T["price"], 2)
        what = (f"{'an' if T['label'][:1] in 'AEIOUM' else 'a'} {T['label']} eval") if n == 1 else f"{n} {T['label']} evals"
        how = (f"Then add it on the Start page (Accounts > Add, {T['bot']})." if t in ("lit_b50", "atlas_b25") else
               f"Then add each on the PC: python -X utf8 -m engine.multi_account --add --id {T['short'].lower()}1 --nt-account \"<NinjaTrader Name>\" "
               f"--preset {T['preset']} --eval-start <first day> (disarmed; Zlarior copies the trades once it is armed).")
        return {"kind": "buy", "type": t, "n": n, "cost": cost, "text": f"Buy {what} (about {_money(cost)}): {T['buy']}.", "how": how}
    later = [s for s in st["slots"] if s["state"] == "not bought"]
    waiting = [s for s in st["slots"] if s["state"] == "eval"]
    if waiting:
        return {"kind": "wait", "text": f"Let the evals run: {st['funded']} of {st['of']} funded, {len(waiting)} in eval. Nothing to buy now.",
                "how": (later[0]["note"] or "") if later else ""}
    if st["funded"] >= st["of"]:
        return {"kind": "done", "text": f"All {st['of']} funded: request each payout when this card says ready.", "how": ""}
    return {"kind": "wait", "text": f"{st['funded']} of {st['of']} funded. Next: wait for the payouts.",
            "how": (later[0]["note"] or "") if later else ""}


# ------------------------------------------------------------------------------------------------ the card
def _inputs_of(money) -> tuple[dict, bool, int | None]:
    """money = a heartbeat / local block {"v", "t", "inputs" | "hidden"} or the raw file dict -> (inputs, hidden, t)."""
    if not isinstance(money, dict):
        return _empty(), False, None
    if isinstance(money.get("inputs"), dict):
        inp, hidden, t = money["inputs"], bool(money.get("hidden")), money.get("t")
    else:
        inp, hidden, t = money, False, money.get("updated")
    base = _empty()
    base["settings"] = settings_of(inp)
    if not hidden:
        base["savings"] = sorted([{"day": str(r["day"]), "usd": float(r["usd"])} for r in inp.get("savings") or []
                                  if isinstance(r, dict) and _DAY.match(str(r.get("day") or "")) and _f(r.get("usd")) is not None],
                                 key=lambda r: r["day"])
        base["months"] = {k: v for k, v in (inp.get("months") or {}).items() if isinstance(v, dict) and _MONTH.match(str(k))}
    base["updated"] = t
    return base, hidden, (int(t) if isinstance(t, (int, float)) else None)


def build(data: dict | None, money=None, now=None, rates: dict | None = None) -> dict:
    """data = data.json (or the PC's goals_data) blocks; money = the owner's figures (heartbeat / local block). -> the card."""
    data = data or {}
    now = int(now or time.time())
    today = _et_day(now)
    month = today.strftime("%Y-%m")
    inp, hidden, t_in = _inputs_of(money)
    S = inp["settings"]
    goal = float(S["month_goal"])
    st = stack(data, rates)
    rows = st.pop("_rows")
    pays = payouts(rows)
    mi = month_in(inp, pays, month)
    nx = next_action(st, rows)
    # goal 1: the $10K month (the bar: jobs / Kalshi / prop payouts)
    P = S["plan"]
    kal_plan = round((float(P["kalshi_day_lo"]) + float(P["kalshi_day_hi"])) / 2 * float(P["kalshi_days"]), 2)
    plan_lines = round(float(P["jobs"]) + kal_plan, 2)
    full = round(plan_lines + st["usd_month_all"], 2)
    parts = [{"k": "jobs", "label": "Jobs", "usd": None if hidden else mi["jobs"]},
             {"k": "kalshi", "label": "Kalshi", "usd": None if hidden else mi["kalshi"]},
             {"k": "prop", "label": "Prop payouts", "usd": mi["prop"]}]
    top = max(goal, sum(max(0.0, p["usd"] or 0) for p in parts))
    for p in parts:
        p["frac"] = round(max(0.0, p["usd"] or 0) / top, 4) if top else 0.0
    total = mi["prop"] if hidden else mi["total"]
    ml = month_label(month).split(" ")[0]
    if hidden:
        msent = f"{ml}: prop payouts {_money(mi['prop'])}; jobs and Kalshi are hidden on the phone."
    elif not mi["entered"] and not mi["prop"]:
        msent = f"{ml} so far: nothing entered yet. Type this month's job income and Kalshi P&L on the PC (Goals page)."
    else:
        msent = (f"{ml} so far: {_money(total)} of {_money(goal)} ({round(100 * total / goal) if goal else 0}%): jobs "
                 f"{_money(mi['jobs']) if mi['jobs'] is not None else 'not entered'}, Kalshi "
                 f"{_money(mi['kalshi']) if mi['kalshi'] is not None else 'not entered'}, prop payouts {_money(mi['prop'])}.")
    g_month = {"k": "month", "kind": "month", "title": f"{_k(goal)} month by {month_label(S['goal_by'])}", "goal": goal,
               "by": S["goal_by"], "month": month, "month_label": month_label(month), "jobs": parts[0]["usd"], "kalshi": parts[1]["usd"],
               "prop": mi["prop"], "prop_n": mi["prop_n"], "total": total, "frac": round(max(0.0, total) / goal, 4) if goal else 0.0,
               "parts": parts, "scale": top, "entered": mi["entered"], "hidden": hidden, "sentence": msent,
               "plan": {"jobs": P["jobs"], "kalshi_month": kal_plan, "kalshi_day_lo": P["kalshi_day_lo"], "kalshi_day_hi": P["kalshi_day_hi"],
                        "kalshi_days": P["kalshi_days"], "prop_all": st["usd_month_all"], "prop_now": st["usd_month_now"], "full": full,
                        "reaches_goal": full >= goal,
                        "sentence": f"Plan pace with all {st['of']} accounts funded: jobs {_money(P['jobs'])} + Kalshi {_money(kal_plan)} "
                                    f"+ props {_money(st['usd_month_all'])} = {_money(full)} a month."}}
    # goals 2 + 3: the cars (saved = the owner's latest savings balance, else the starting balance)
    pts = balance_points(inp) if not hidden else []
    saved = pts[-1]["usd"] if pts else None
    g_car = car_goal(S["car"], saved, pts, today, hidden)
    Z = S["z06"]
    zt = float(Z["target"])
    g_z = {"k": "z06", "kind": "bar", "title": Z["name"], "target": zt, "note": Z.get("note"), "saved": None if hidden else saved,
           "frac": round(min(1.0, (saved or 0) / zt), 4) if zt and saved is not None and not hidden else 0.0, "hidden": hidden,
           "sentence": ("Your savings are hidden on the phone." if hidden else "Enter your savings on the PC." if saved is None else
                        f"{_money(saved)} of {_money(zt)} ({round(100 * saved / zt) if zt else 0}%), no date.")}
    honest = ["The $ per account are the 2026 Jul-Oct backtest rates (H2, research/second/money_goal_rates.json): a plan, not a promise.",
              f"In a 2021-25-like year the same {st['of']} accounts pay about {_money(st['usd_month_ref_all'])} a month.",
              "A first payout comes about 5-7 weeks after an account is funded; every Zlarior account trades the same signals, "
              "so a cold month is cold on all of them.",
              "Current pace = your own savings entries (the start balance included), not a forecast."]
    lines = []
    if t_in and not hidden:                               # only once the owner saved his figures
        lines.append({"k": "money", "text": f"Road to $10K: {_money(total)} this month ({round(100 * total / goal) if goal else 0}%); "
                                            f"{g_car['short']}: {g_car['sentence'].split('. ')[0]}.", "level": "good" if total >= goal else "idle"})
        lines.append({"k": "money_next", "text": "Next: " + nx["text"], "level": "warn" if nx["kind"] in ("payout", "funded") else "idle"})
    return {"v": VERSION, "t": now, "today": today.isoformat(), "title": f"Road to $10K / {g_car['short']}", "inputs_t": t_in,
            "has_inputs": bool(t_in) and not hidden, "hidden": hidden, "next": nx, "stack": st, "goals": [g_month, g_car, g_z],
            "saved": None if hidden else saved, "saved_day": pts[-1]["day"] if pts else None,
            "payouts": [] if hidden else pays[-12:], "honest": honest, "lines": lines, "settings": S,
            "savings": [] if hidden else inp["savings"][-6:], "this_month": {k: g_month[k] for k in ("month", "jobs", "kalshi", "prop", "total", "goal", "frac")}}


def from_heartbeat(hb: dict | None, now=None, accounts: list | None = None) -> dict:
    """The card from a heartbeat payload alone (engine/live_publish.py: live.json "money" for the phone, fresher than the
    cloud's data.json). accounts = the PC sections engine/accounts.build_accounts made of the same payload."""
    hb = hb or {}
    sec = hb.get("second") if isinstance(hb.get("second"), dict) else {}
    ab = ((sec.get("route") or {}).get("account_b") if isinstance(sec.get("route"), dict) else None) or sec.get("account_b")
    data = {"accounts": accounts or [], "second": {"account_b": ab} if isinstance(ab, dict) else {}, "live": {}}
    try:
        from . import scale_plan as SP
        data["scale"] = SP.cloud_view({"pc": hb}, now)
    except Exception:
        data["scale"] = {}
    return build(data, hb.get("money"), now)


if __name__ == "__main__":
    print(json.dumps(build({}, local_block()), indent=1, default=str))
