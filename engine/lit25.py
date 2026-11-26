"""Zlarior (LIT) ALSO trades ATLAS's FUNDED Builder 25K, next to ATLAS (owner 2026-11-17, night-bot). OFF by default.

Why (research/writeups/funded25-lit-atlas-2026-11-17.md, tools/money/funded25.py, research/lab/builder_funded25.json):
ATLAS's 25K eval passed (balance $26,946.10 on 2026-11-17). On the funded 25K, LIT + ATLAS $250 asks for the first payout
about 4 (Jan-Jun 2026) / 8 (Jul-Oct 2026) sessions sooner than ATLAS alone, but "no payout in 6 months" is 7.5% / 12.2%
vs 5.0% / 5.5% and 2021-25 is a little worse ($35 vs $48 a month): the owner's call, so this file is OFF until he says.

ON / OFF: data/lit25.json (local, gitignored, never the phrase): {"on": true}. Missing / anything else = OFF = the bot is
exactly today's. It acts only while ATLAS's account_b block is in its FUNDED stage (engine/account_b --to-funded, or the
Start page "Passed -> funded"); in the eval stage nothing changes.
    python -X utf8 -m engine.lit25 --on | --off | --status      (--on asks for I ACCEPT LIVE RISK + a passing NT self-test)
    python -X utf8 -m engine.lit25 --funded "<funded Name>" --start yyyy-mm-dd   (= Start page "Passed -> funded" for ATLAS)
Arming: nothing here arms. LIT's lane on the 25K is armed exactly when ATLAS's 25K is (engine/go.step_arm -> arm_b, only
after the owner typed I ACCEPT LIVE RISK), with the phrase typed at that start; a real account also needs NINJATRADER_LIVE=1
and the allowlist (engine/ninjatrader._live_gate).

What runs on the funded 25K (the same pattern as engine/rapid.py, LIT + ATLAS on one account):
  LIT lane    an engine/multi_account extra account (preset mffu_builder_25k, mode funded, id/lane "lit25", the funded
              start / payouts / prior of ATLAS's block): the 25K funded rule at ATLAS's funded room share (account_b
              FUNDED_ON 40%, owner YES 2026-11-20; the preset's 60% only when that switch is off), <= $750, a winner <= $1,000,
              no extra day guard (= the research's funded_qty).
  ATLAS       SharedAtlas below = engine/account_b.AccountB (its own state, order tag "acctb_", payout tracker) with:
              $ risk = min($250, 30% of the room, the soft day left), micros = $ / one full stop-out (stop + 1 tick, $1.90),
              then account B's soft-daily-loss guard; one position, max 2 a day.
  One account, one book: both lanes size and lock out on the SUM of their closes. Never two positions, never hedged: ATLAS
  is blocked while LIT holds a trade (either side, on any account), is entering one, or has a setup armed the other way;
  LIT entering while ATLAS holds closes ATLAS at market first and routes only once that close is CONFIRMED flat.
"""
from __future__ import annotations

import json
import os

from . import account_b as AB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_REL = os.path.join("data", "lit25.json")
PATH = None                     # tests: another file
LANE_ID = "lit25"
PRESET = "mffu_builder_25k"
ATLAS_USD, ATLAS_F = 250.0, 0.3     # tools/money/funded25.py "LIT + ATLAS $250": $250, 30% of the room
SLIP, PV, COMM = 0.25, 2.0, 1.90    # one full stop-out of 1 micro = (stop + 1 tick) x $2 + $1.90 (research stack_q)


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def path(p: str | None = None) -> str:
    return p or PATH or os.path.join(ROOT, LOCAL_REL)


# ---------------------------------------------------------------------------------------------------------------- switch
def load(p: str | None = None) -> dict:
    try:
        with open(path(p), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def is_on(p: str | None = None) -> bool:
    return load(p).get("on") is True


def save(on: bool, p: str | None = None) -> str:
    fp = path(p)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "on": bool(on)}, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried on a Windows / OneDrive lock
    _fs_replace(tmp, fp)
    return fp


# ---------------------------------------------------------------------------------------------------------------- lanes
def atlas_spec(ab: dict | None = None, lit_account: str | None = None) -> dict | None:
    """ATLAS's account_b spec (engine/account_b.normalize), or None when account B is off."""
    ab = AB.raw_cfg() if ab is None else ab
    if not isinstance(ab, dict) or not ab:
        return None
    return AB.normalize(ab, lit_account=lit_account)


def why_idle(spec: dict | None) -> str | None:
    """Why the switch, although ON, changes nothing (None = LIT trades the funded 25K)."""
    if spec is None:
        return "ATLAS's 25K (account B) is off"
    if spec.get("problem"):
        return f"ATLAS's 25K cannot trade: {spec['problem']}"
    if not AB.is_funded(spec):
        return "ATLAS's 25K is still in its eval stage: LIT joins once it is funded (Start page 'Passed -> funded')"
    if not (spec.get("funded") or {}).get("start"):
        return "the funded start day is missing"
    return None


def lane_spec(spec: dict, cfg: dict | None = None) -> dict:
    """LIT's lane: one engine/multi_account extra account entry on ATLAS's funded 25K."""
    cfg = cfg or {}
    F = spec["funded"]
    armed = spec.get("armed") is True
    s = {"id": LANE_ID, "name": "LIT on the funded 25K", "preset": PRESET, "mode": "funded",
         "adapter": "ninjatrader" if cfg.get("adapter") == "ninjatrader" else "paper", "nt_account": spec["account"],
         "eval_start": "", "enabled": True, "armed": armed, "lane": LANE_ID,
         "eval_prior_pnl": float(F.get("prior") or 0.0),
         "funded": {"start": F.get("start") or "", "payouts": dict(F.get("payouts") or {})},
         "lit_sizing": {"guard": None}}
    fp = spec.get("funded_room_pct")            # day-alloc 2026-11-26 (lead): the lane follows ATLAS's owner-approved funded room
    if fp is not None:                          # share (account_b FUNDED_ON 40%, owner YES 2026-11-20), never above the preset's 60%
        s["lit_sizing"]["funded"] = {"pct": min(0.6, float(fp))}
    if armed and cfg.get("confirm"):
        s["confirm"] = cfg["confirm"]           # the phrase typed at this start, in memory only
    return s


def add_lane(bot, cfg: dict) -> dict:
    """LiveBot._start_accounts: the start cfg with LIT's lane on the funded 25K added (cfg unchanged when OFF / idle).
    Test harnesses: the start cfg's "lit25" ({"on": true}) when the key is there; otherwise off unless the real bot."""
    if "lit25" in (cfg or {}):
        on = isinstance(cfg.get("lit25"), dict) and cfg["lit25"].get("on") is True
    else:
        from .live import STATE_PATH
        on = getattr(bot, "state_path", None) == STATE_PATH and is_on()
    if not on:
        return cfg
    lit_acct = None
    try:
        if (cfg or {}).get("adapter") == "ninjatrader":
            from .ninjatrader import resolve_account
            lit_acct = resolve_account(cfg)
    except Exception:
        lit_acct = None
    if "account_b" in (cfg or {}):
        ab = cfg.get("account_b")
        spec = AB.normalize(ab, lit_account=lit_acct) if isinstance(ab, dict) and ab else None
    else:
        spec = atlas_spec(None, lit_account=lit_acct)
    why = why_idle(spec)
    if why:
        bot._log("risk", f"LIT on the 25K is ON but idle: {why}")
        return cfg
    lane = lane_spec(spec, cfg)
    rows = [r for r in (cfg.get("accounts") or []) if isinstance(r, dict) and r.get("id") != lane["id"]
            and r.get("nt_account") != lane["nt_account"]]
    bot._log("system", f"LIT on the funded 25K: ON ({spec['account']}, {'armed with ATLAS' if lane['armed'] else 'not armed'}); "
                       "LIT first, never two positions on the account")
    return {**cfg, "accounts": rows + [lane]}


def lane_of(bot, name: str | None = None):
    ac = getattr(bot, "accts", None)
    return next((a for a in (getattr(ac, "accounts", None) or []) if a.spec.get("lane") == LANE_ID
                 and (name is None or a.spec.get("nt_account") == name)), None)


def atlas_class(bot, spec: dict):
    """engine/account_b.build: SharedAtlas when LIT's lane runs on this same (funded) account, else None."""
    if spec and AB.is_funded(spec) and lane_of(bot, spec.get("account")) is not None:
        return SharedAtlas
    return None


def stack_qty(risk: float, room, cum: float, maxq: int, dll: float = 600.0) -> tuple:
    """research stack_q: $ = min($250, 30% x room, the soft day left), micros = $ / one full stop-out of 1 micro."""
    loss1 = (float(risk) + SLIP) * PV + COMM
    usd = min(ATLAS_USD, ATLAS_F * max(0.0, float(room or 0.0)), float(dll) + min(0.0, float(cum or 0.0)))
    return max(0, min(int(maxq), int(usd // loss1))), usd, loss1


class SharedAtlas(AB.AccountB):
    """ATLAS on its funded 25K while LIT's lane trades the same account (LiveBot.acct_b)."""

    shared_lane = LANE_ID

    def lane(self):
        return lane_of(self.bot, self.name)

    def all_closes(self) -> list:
        ln = self.lane()
        return list(self.closes) + [list(c) for c in (getattr(ln, "closes", None) or [])]

    def day_pnl(self, day) -> float:
        return round(sum(float(p) for d, _, p, *_ in self.all_closes() if d == day), 2)

    def funded_days(self, today=None) -> dict:
        F = self.spec.get("funded") or {}
        days = {}
        for d, _, p, *_ in self.all_closes():
            if F.get("start") and str(d) >= F["start"] and (today is None or str(d) <= today):
                days[str(d)] = round(days.get(str(d), 0.0) + float(p), 2)
        return days

    def _funded_state(self, today):
        from . import multi_account as MA
        F = self.spec["funded"]
        if not F.get("start"):
            return None
        st = MA.sizing_state("funded", [(d, t, p) for d, t, p, *_ in self.all_closes()], today, F["start"], self.rules,
                             prior=float(F.get("prior") or 0.0), payouts=dict(F.get("payouts") or {}))
        if F.get("payouts"):
            lock = float(self.rules["lock"])
            if float(st["floor"]) < lock:
                st["floor"] = lock
                st["room"] = round(float(st["balance"]) + float(st["cum"]) - lock, 2)
                st["locked"] = True
        st["n_today"] = self.entries_today(today)
        return st

    def size(self, trade: dict, state, key=None) -> dict:
        R = self.rules
        if state is None:
            return {"qty": 0, "reasons": ["funded state unknown (funded_start missing?): not traded"], "lock": None}
        risk = _num(trade.get("risk_pts"))
        if not risk or risk <= 0:
            return {"qty": 0, "reasons": ["no stop distance"], "lock": None}
        room = _num(state.get("room"), 0.0)
        if room <= 0:
            return {"qty": 0, "reasons": [f"room ${room:,.0f} to the floor: no trade"], "lock": "lost"}
        q, usd, loss1 = stack_qty(risk, room, float(state.get("cum") or 0.0), int(R["max_micros"]), float(R["dll"]))
        r = {"qty": int(q), "reasons": [f"${usd:,.0f} risk (min $250, 30% of the ${room:,.0f} room, the day left) / ${loss1:,.0f} "
                                        f"a micro -> {q} (LIT shares this account)"], "lock": None}
        return AB.dll_guard(r, float(risk), R, state)

    def lit_opposite(self, d: int):
        st = getattr(self.bot, "state", None) or {}
        ln = self.lane()
        if ln is not None and ln.open_t is not None:
            return "LIT holds a trade on this account"
        if st.get("position"):
            return "LIT is in a trade"
        if st.get("enter_now"):
            return "LIT is entering a trade"
        return super().lit_opposite(d)

    def yield_to_lit(self, d: int, sym: str, now: int, px=None, any_side: bool = False) -> bool:
        """LIT's lane is about to enter here: ATLAS's position (any side) is closed at market first. True = LIT may route
        now (flat, or the close CONFIRMED)."""
        with self.mx:
            try:
                self.reconcile_unplaced(now)
            except Exception:
                pass
            if self.open_t is None:
                return True
            et_ = int(self.open_t)
            pv = self.prov.get(et_) or {}
            if not any_side and int(pv.get("dir") or 0) != -d:
                return True
            cl = pv.get("closing")
            if cl and not cl.get("done"):
                self.settle_closing(sym, now)
            else:
                self.log("risk", f"LIT enters {'LONG' if d == 1 else 'SHORT'}: ATLAS's {pv.get('short') or pv.get('key')} on "
                                 f"{self.name} is closed at market first (LIT has priority)")
                if self.flatten(et_, "HEDGE", sym, now, px=_num(px)):
                    pv["final"] = True
            return self.open_t is None or int(self.open_t) != et_


# ---------------------------------------------------------------------------------------------------------------- owner
def status(p: str | None = None) -> dict:
    on = is_on(p)
    try:
        spec = atlas_spec()
    except Exception:
        spec = None
    why = why_idle(spec)
    if not on:
        txt = "LIT on the funded 25K: OFF (python -X utf8 -m engine.lit25 --on)"
    elif why:
        txt = f"LIT on the funded 25K: ON, idle: {why}"
    else:
        txt = (f"LIT on the funded 25K: ON on {spec['account']} from {spec['funded']['start']} "
               f"({'armed with ATLAS' if spec.get('armed') else 'not armed: START BOT + you type the phrase'}); "
               "takes effect at the next START BOT")
    return {"on": on, "idle": why, "text": txt}


def to_funded(funded_name: str, start: str) -> dict:
    """The owner's one line after MFFU issues the funded 25K: = the Start page "Passed -> funded" on ATLAS's eval row
    (engine/go.to_funded: account_b funded stage on the new Name, disarmed, allowlisted, start_bot.json "atlas" follows)."""
    from . import go
    ab = AB.raw_cfg() or {}
    cur = str(ab.get("account") or "").strip()
    if not cur:
        return {"ok": False, "error": "ATLAS's 25K (account B) is off: nothing to switch"}
    if str(ab.get("stage") or "") == "funded":
        return {"ok": False, "error": f"ATLAS already trades the funded {cur}"}
    return go.to_funded(cur, funded_name, start)


def set_on(phrase: str, p: str | None = None, selftest=None) -> dict:
    """The owner's switch ON (day-alloc 2026-11-26, research/writeups/alloc-2026-11-26.md card 2): refused without the typed live
    phrase or with a failing NinjaTrader self-test; the file never holds the phrase. OFF never needs it (save(False))."""
    from .go import LIVE_PHRASE, typed_phrase
    if typed_phrase(phrase) != LIVE_PHRASE:
        return {"ok": False, "error": "the live phrase was not typed: nothing switched on"}
    try:
        if selftest is None:
            from .second import _selftest_ok as selftest
        ok, line = selftest()
    except Exception as e:  # noqa: BLE001
        ok, line = False, f"{e.__class__.__name__}"
    if not ok:
        return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): nothing switched on"}
    fp = save(True, p)
    return {"ok": True, "path": fp, "say": "LIT on ATLAS's funded 25K: ON (takes effect at the next START BOT, after hours; arming follows "
                                            "ATLAS's 25K, nothing is armed here)"}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.lit25", description="LIT also trades ATLAS's funded Builder 25K (OFF by default)")
    ap.add_argument("--on", action="store_true")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--funded", metavar="NAME", help="ATLAS's new funded 25K Name exactly as NinjaTrader shows it")
    ap.add_argument("--start", help="--funded: the first funded session (yyyy-mm-dd)")
    a = ap.parse_args(argv)
    if a.funded:
        if not a.start:
            print('--funded needs --start yyyy-mm-dd (the first funded day)')
            return 1
        r = to_funded(a.funded, a.start)
        print(r.get("say") if r.get("ok") else f"NOT switched: {r.get('error')}")
        return 0 if r.get("ok") else 1
    if a.on:
        print(" Zlarior (LIT) will ALSO trade ATLAS's FUNDED 25K, next to ATLAS (one position at a time, LIT first).")
        try:
            phrase = input(" Type  I ACCEPT LIVE RISK  then Enter (anything else stops here, nothing switched on): ")
        except EOFError:
            phrase = ""
        r = set_on(phrase)
        print(" " + (r["say"] if r.get("ok") else "NOT switched on: " + str(r.get("error"))))
        return 0 if r.get("ok") else 1
    if a.off:
        save(False)
        print("LIT on the funded 25K: OFF (after the next START BOT: ATLAS alone, as before)")
        return 0
    print(status()["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
