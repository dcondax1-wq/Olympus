"""Telegram trade cards (day-cards 2026-11-26, owner: important features + live updates): on every real entry and exit the
alert bus's Telegram message becomes a chart PICTURE (engine/png_chart: the last ~2 h of 1-minute bars, entry / stop / target
lines, the entry and exit marks) with the caption the bus already writes plus the bot's one-line reason (the LIT Brain's setup
status_text / the ATLAS member's own state words) and R / $ risk / $ result. Every other channel stays text only.

night-nq-cards 2026-11-27: the premium look (engine/png_chart: OLYMPUS NIGHT, 1280 x 720, header with bot / account / side / R / $,
entry / stop / target / sweep lines with tags) + the day summary and week report as pictures too (summary_photo).
READ-ONLY: it reads bars and the bot's brain, writes logs/cards/ (gitignored: <entry_t>.json + <key>.png, newest 120 files kept),
never routes or changes anything. engine/push._bus_send calls attach() in its background thread (after the order went out).
Off: notify_settings.json alerts.trade_cards false, or LE_TRADE_CARDS=0: the old text message, exactly.
Tests: python -X utf8 -m tests.test_trade_cards
"""
from __future__ import annotations

import glob
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD_DIR = os.path.join(ROOT, "logs", "cards")
_DEFAULT_DIR = CARD_DIR
TYPE = "trade_cards"
BEFORE_S = 90 * 60                      # day-tgpretty (owner): the last ~90 min of 1-minute candles
KEEP = 60
PV_MNQ = 2.0


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    if str(e.get("LE_TRADE_CARDS", "1")).strip() == "0":
        return False
    try:
        from . import notify
        return bool(notify.on(TYPE))
    except Exception:
        return True


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def entry_time(p: dict) -> int | None:
    k = str((p or {}).get("key") or "")
    for pre in ("fill:", "out:"):
        if k.startswith(pre):
            digits = k[len(pre):].split(":")[0]
            return int(digits) if digits.isdigit() else None
    return None


def _bot():
    try:
        from .live import BOT
        return BOT
    except Exception:
        return None


def bars(t_from: int, t_to: int, bot=None) -> list:
    """[(t, o, h, l, c)] 1-minute bars in [t_from, t_to] from the running bot's history (data/<sym>_1m.csv, the PC's bars), else
    NinjaTrader's feed files. [] when none. Never raises."""
    bot = bot if bot is not None else _bot()

    def _cut(df):
        try:
            d = df[(df["time"] >= t_from) & (df["time"] <= t_to)]
            if len(d) >= 5:
                return [(int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)) for r in d.itertuples()]
        except Exception:
            pass
        return None

    try:                                                   # the bot's own (cached) history first
        sym = (getattr(bot, "cfg", None) or {}).get("sym") or "NQ"
        got = _cut(bot._read_hist(sym, "1m"))
        if got:
            return got
    except Exception:
        pass
    try:                                                   # red team 2026-11-26: NinjaTrader's files only when the history has no bars
        from .ninjatrader import NinjaTraderBars           # (each extra read delays the alert, never the order: a worker thread)
        r = NinjaTraderBars((getattr(bot, "cfg", None) or {}).get("nt_folder")).recent_bars("NQ", "1m")
        df = r[0] if isinstance(r, tuple) else r          # recent_bars -> (df | None, error, flag)
        if df is not None:
            return _cut(df) or []
    except Exception:
        pass
    return []


def reason(p: dict, bot=None) -> str:
    """The bot's one line on why it entered: the LIT Brain's setup row (filled / entering, this side), else the ATLAS member's
    state words. '' when unknown."""
    bot = bot if bot is not None else _bot()
    try:
        side = str(p.get("side") or "").upper()
        d = 1 if side == "LONG" else -1
        br = getattr(bot, "brain", None) or {}
        rows = [s for s in br.get("setups") or [] if isinstance(s, dict) and s.get("dir") == d
                and s.get("status") in ("filled", "entering", "tapped", "armed")]
        if rows and not p.get("who"):
            s = rows[-1]
            sw = ", ".join(str(x) for x in (s.get("swept") or [])[:2]) if isinstance(s.get("swept"), list) else str(s.get("swept") or "")
            return (f"LIT: swept {sw}; " if sw else "LIT: ") + str(s.get("status_text") or "")[:160]
        sec = getattr(bot, "second", None) or {}
        for k, s in (sec.get("strategies") or {}).items():
            st = (s or {}).get("state") or {}
            if st.get("stage") in ("armed", "in_trade") and st.get("text"):
                return f"ATLAS {s.get('short') or k}: {str(st['text'])[:160]}"
    except Exception:
        pass
    return ""


def sweep_level(p: dict, bot=None):
    """The swept level's extreme (the LIT Brain's setup row "ext", this side) for the chart's SWEEP line; None when unknown."""
    bot = bot if bot is not None else _bot()
    try:
        if p.get("who"):
            return None
        d = 1 if str(p.get("side") or "").upper() == "LONG" else -1
        rows = [s for s in (getattr(bot, "brain", None) or {}).get("setups") or [] if isinstance(s, dict) and s.get("dir") == d
                and s.get("status") in ("filled", "entering", "tapped", "armed")]
        return _f(rows[-1].get("ext")) if rows else None
    except Exception:
        return None


def _account(p: dict) -> str:
    try:
        from . import notify
        return notify.mask_ids(notify.display_name(p))[:40]
    except Exception:
        return "Account"


def _mask(s) -> str:
    try:
        from . import notify
        return notify.mask_ids(s)
    except Exception:
        return str(s or "")


def _save(et_, info: dict):
    try:
        os.makedirs(CARD_DIR, exist_ok=True)
        with open(os.path.join(CARD_DIR, f"{int(et_)}.json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh)
    except Exception:
        pass


def _load(et_) -> dict:
    try:
        with open(os.path.join(CARD_DIR, f"{int(et_)}.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _trim():
    try:
        fs = sorted(glob.glob(os.path.join(CARD_DIR, "*")), key=os.path.getmtime)
        for f in fs[:-KEEP * 2]:
            os.remove(f)
    except Exception:
        pass


def build(p: dict, what: str, now=None, bot=None, bars_fn=None, keep_info: bool = False) -> dict | None:
    """{"photo": path to the PNG | None, "why", "extra"} for a fill ("entry") / outcome ("exit") payload. Never raises."""
    try:
        from . import png_chart as PC
        now = int(now if now is not None else time.time())
        et_ = entry_time(p)
        if not et_:
            return None
        side = str(p.get("side") or "").upper()
        d = 1 if side == "LONG" else -1
        info = _load(et_)
        if what == "entry" and not (keep_info and info):     # attach_lazy saved the entry's words already: never read the brain twice
            info = {"entry": _f(p.get("entry")), "stop": _f(p.get("stop")), "target": _f(p.get("target")), "qty": _f(p.get("qty")),
                    "side": side, "why": reason(p, bot), "sweep": sweep_level(p, bot)}
            _save(et_, info)
        entry, stop, target = info.get("entry") or _f(p.get("entry")), info.get("stop"), info.get("target")
        qty = _f(p.get("qty")) or info.get("qty")
        extra = []
        risk_pts = abs(entry - stop) if entry is not None and stop is not None else None
        if what == "entry" and risk_pts and qty:
            line = f"Risk ${risk_pts * PV_MNQ * qty:,.0f} ({risk_pts:.2f} pts)"
            if target is not None:
                rr = abs(target - entry) / risk_pts
                line += f" · target {rr:.1f}R = ${abs(target - entry) * PV_MNQ * qty:,.0f}"
            extra.append(line)
        x_px = _f(p.get("exit_px"))
        if what == "exit" and risk_pts and x_px is not None and entry is not None:
            extra.append(f"Result {(x_px - entry) * d / risk_pts:+.2f}R")
        t_end = now if what == "entry" else int(p.get("t") or now)
        B = (bars_fn or bars)(et_ - BEFORE_S, t_end + 60) if bars_fn else bars(et_ - BEFORE_S, t_end + 60, bot)
        photo = None
        if B:
            acct = _account(p)
            bot_name = "ATLAS" if ("ATLAS" in acct.upper() or p.get("who")) else "LIT"
            lines = [(target, PC.GREEN, et_, False, "TARGET"), (entry, PC.GOLD, et_, True, "ENTRY"),
                     (stop, PC.RED, et_, False, "STOP")]
            if info.get("sweep") is not None:
                lines.append((info["sweep"], PC.LILAC, None, True, "SWEEP"))
            marks = [(et_, entry, PC.GOLD, "entry")]
            zones = [(entry, target, et_, PC.UP), (entry, stop, et_, PC.DOWN)]
            q = int(qty) if qty else None
            usd = _f(p.get("usd"))
            if what == "exit":
                if x_px is not None:
                    marks.append((int(p.get("t") or now), x_px, PC.WHITE, "exit"))
                rr = (x_px - entry) * d / risk_pts if (risk_pts and x_px is not None and entry is not None) else None
                hero = PC.money(usd) if usd is not None else (f"{rr:+.2f}R" if rr is not None else "CLOSED")
                hc = PC.col_of(usd if usd is not None else rr)
                sub = " \u00b7 ".join(x for x in ((f"{rr:+.2f}R" if rr is not None and usd is not None else ""),
                                                  str(p.get("exit") or "").upper()[:12],
                                                  (f"RISK ${risk_pts * PV_MNQ * qty:,.0f}" if risk_pts and qty else "")) if x)
            else:
                rr = abs(target - entry) / risk_pts if (risk_pts and target is not None) else None
                hero = f"{rr:.1f}R" if rr is not None else "IN TRADE"
                hc = PC.GOLD
                sub = " \u00b7 ".join(x for x in ((f"RISK ${risk_pts * PV_MNQ * qty:,.0f}" if risk_pts and qty else ""),
                                                  (f"TARGET +${abs(target - entry) * PV_MNQ * qty:,.0f}"
                                                   if (target is not None and qty and entry is not None) else "")) if x)
            try:
                from . import png_chart as _pc
                tag = f"{_pc._et(et_):%a %b %d}".upper()
            except Exception:
                tag = ""
            head = {"bot": bot_name, "account": acct, "side": side, "qty": q, "hero": hero, "hero_col": hc, "sub": sub, "tag": tag}
            foot = _mask(info.get("why") or "")
            png = PC.render(B, lines, marks, head=head, foot=foot, zones=zones)
            if png:
                os.makedirs(CARD_DIR, exist_ok=True)
                photo = os.path.join(CARD_DIR, f"{what}_{int(et_)}.png")
                with open(photo, "wb") as fh:
                    fh.write(png)
                _trim()
        return {"photo": photo, "why": info.get("why") or "", "extra": " · ".join(extra),
                "legend": "Chart: 1-min candles · gold dashed = entry · red = stop · green = target · violet dashed = sweep level"
                          + (" · white ring = exit" if what == "exit" else "")}
    except Exception:
        return None


def _masked(x):
    if isinstance(x, str):
        return _mask(x)
    if isinstance(x, dict):
        return {k: _masked(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return type(x)(_masked(v) for v in x)
    return x


def _test_transport() -> bool:
    """A test's fake alert transport (alert_bus._HTTP) never draws into the repo's logs/."""
    try:
        from . import alert_bus as _AB
        return _AB._HTTP is not None and CARD_DIR == _DEFAULT_DIR
    except Exception:
        return False


def summary_photo(card: dict, key: str = "") -> str | None:
    """night-nq-cards: the day summary (16:20 ET, half day: halt + 20 min) / the Friday week report as a picture (engine/png_chart
    render_day / render_week) -> the PNG's path in logs/cards/, or None (off / nothing to draw / any trouble: the text message).
    Called by alert_bus.from_report in tools/pc_report's 15-minute run, never on the order path. Never raises."""
    try:
        if not isinstance(card, dict) or not enabled() or _test_transport():
            return None
        from . import png_chart as PC
        c = _masked(card)
        fn = {"day": PC.render_day, "week": PC.render_week}.get(str(c.get("type")))
        png = fn(c) if fn else None
        if not png:
            return None
        os.makedirs(CARD_DIR, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(key or c.get("type")))[-60:]
        path = os.path.join(CARD_DIR, f"{c.get('type')}_{safe}.png")
        with open(path, "wb") as fh:
            fh.write(png)
        _trim()
        return path
    except Exception:
        return None


def attach_lazy(ev: dict, p: dict, what: str, now=None, bot=None) -> dict:
    """day-tgpretty: the bus event with the bot's reason + the $ risk line NOW (cheap: the brain's words, the saved entry), and the
    chart as ev["photo_fn"]: engine/alert_bus draws it on its own thread AFTER the text went (the alert never waits for a picture).
    Unchanged when off. Never raises."""
    try:
        if not enabled() or _test_transport():
            return ev
        et_ = entry_time(p)
        if not et_:
            return ev
        out = dict(ev)
        side = str(p.get("side") or "").upper()
        info = _load(et_)
        if what == "entry":
            info = {"entry": _f(p.get("entry")), "stop": _f(p.get("stop")), "target": _f(p.get("target")), "qty": _f(p.get("qty")),
                    "side": side, "why": reason(p, bot), "sweep": sweep_level(p, bot)}
            _save(et_, info)
        more = [x for x in (_mask(info.get("why") or ""),) if x]
        if more:
            out["more"] = "\n".join(more)[:400]
        p2, bot2 = dict(p), bot

        def draw():
            c = build(p2, what, now=now, bot=bot2, keep_info=True)
            return (c or {}).get("photo")

        out["photo_fn"] = draw
        return out
    except Exception:
        return ev


def attach(ev: dict, p: dict, what: str, now=None, bot=None) -> dict:
    """The bus event with the picture + the extra caption lines (unchanged when off / nothing to draw). Never raises."""
    try:
        if not enabled():
            return ev
        if _test_transport():
            return ev
        c = build(p, what, now=now, bot=bot)
        if not c:
            return ev
        more = [x for x in (c.get("why"), c.get("extra")) if x]
        out = dict(ev)
        if more:
            out["more"] = "\n".join(more)[:400]
        if c.get("photo"):
            out["photo"] = c["photo"]
            out["legend"] = c["legend"]
        return out
    except Exception:
        return ev
