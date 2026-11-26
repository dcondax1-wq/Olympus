"""Telegram trade cards (day-cards 2026-11-26, owner: important features + live updates): on every real entry and exit the
alert bus's Telegram message becomes a chart PICTURE (engine/png_chart: the last ~2 h of 1-minute bars, entry / stop / target
lines, the entry and exit marks) with the caption the bus already writes plus the bot's one-line reason (the LIT Brain's setup
status_text / the ATLAS member's own state words) and R / $ risk / $ result. Every other channel stays text only.

READ-ONLY: it reads bars and the bot's brain, writes logs/cards/ (gitignored: <entry_t>.json + <key>.png, newest 60 kept),
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
TYPE = "trade_cards"
BEFORE_S = 2 * 3600
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
    dfs = []
    try:
        sym = (getattr(bot, "cfg", None) or {}).get("sym") or "NQ"
        dfs.append(bot._read_hist(sym, "1m"))
    except Exception:
        pass
    try:
        from .ninjatrader import NinjaTraderBars
        r = NinjaTraderBars((getattr(bot, "cfg", None) or {}).get("nt_folder")).recent_bars("NQ", "1m")
        df = r[0] if isinstance(r, tuple) else r          # recent_bars -> (df | None, error, flag)
        if df is not None:
            dfs.append(df)
    except Exception:
        pass
    for df in dfs:
        try:
            d = df[(df["time"] >= t_from) & (df["time"] <= t_to)]
            if len(d) >= 5:
                return [(int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)) for r in d.itertuples()]
        except Exception:
            continue
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


def build(p: dict, what: str, now=None, bot=None, bars_fn=None) -> dict | None:
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
        if what == "entry":
            info = {"entry": _f(p.get("entry")), "stop": _f(p.get("stop")), "target": _f(p.get("target")), "qty": _f(p.get("qty")),
                    "side": side, "why": reason(p, bot)}
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
            lines = [(target, PC.GREEN, et_, False), (stop, PC.RED, et_, False), (entry, PC.WHITE, et_, True)]
            marks = [(et_, entry, PC.GOLD)]
            if what == "exit" and x_px is not None:
                marks.append((int(p.get("t") or now), x_px, PC.BLUE))
            png = PC.render(B, lines, marks)
            if png:
                os.makedirs(CARD_DIR, exist_ok=True)
                photo = os.path.join(CARD_DIR, f"{what}_{int(et_)}.png")
                with open(photo, "wb") as fh:
                    fh.write(png)
                _trim()
        return {"photo": photo, "why": info.get("why") or "", "extra": " · ".join(extra),
                "legend": "Chart: 1-min candles · white dashed = entry · red = stop · green = target · gold = entry fill"
                          + (" · blue = exit" if what == "exit" else "")}
    except Exception:
        return None


def attach(ev: dict, p: dict, what: str, now=None, bot=None) -> dict:
    """The bus event with the picture + the extra caption lines (unchanged when off / nothing to draw). Never raises."""
    try:
        if not enabled():
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
