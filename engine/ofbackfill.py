"""OF BACKFILL (night-of-backfill 2026-11-27; owner: "a ton of agents on order flow ... for next week"): the rest of the PC's tick
year (LE_TickRec backfill, up to 400 days) reaches the cloud in a few nights instead of weeks, by itself.

The old way: ONE "of" ask a night, 4 gzip pages (engine/datafeed._answer_of) -> 51 days in the first night; ~350 days = ~6 more
nights at best. The numbers that bind (ntfy.sh anonymous, GET https://ntfy.sh/v1/account, measured 2026-11-27):
  messages 250 a UTC day per IP (reset 00:00 UTC = 19:00 ET) | one attachment <= 2 MiB | 20 MiB of attachments in flight (each
  kept 3 h) | 350 MiB attachment bandwidth a day. The PC's status posts + alerts use ~210-230 messages on a weekday, far fewer on a
  closed-market weekend. So pages are MESSAGE-bound on weekdays and STORAGE-bound (20 MiB / 3 h = ~10 pages) on weekends.
What this does, three levers together:
  1. smaller pages: engine/ofpack (columns + deltas + one xz stream, lossless, sha256 per file): ~0.53 of the gzip bytes, so a
     1.85 MB page carries ~2x the days;
  2. as many pages as ntfy's OWN live count allows, never more: before EVERY page the PC reads GET /v1/account (a read is not a
     message) and sends only while
         messages_remaining - projected rest-of-UTC-day use - ALERT_RESERVE - ANSWER_RESERVE >= 1   and
         attachment room (20 MiB minus what is in flight) - STORE_KEEP >= one page,
     where the projection = hourly post rate x hours left until ntfy's reset, per hour kind (weekday session 01:50-16:10 ET,
     off hours, closed market Fri 17:00 - Sun 18:00 ET); the rates start from the documented budget (tools/pc_report: ~210 status
     posts a weekday) and are LEARNED from ntfy's own count between two samples outside the session (x1.25 safety, never under
     the core's 4/h). Trade alerts keep their room: ALERT_RESERVE is on top of the projection, and tools/pc_report's own ext /
     chart posts already give way first (TRADE_ALERT_RESERVE). Unknown count (ntfy did not answer) = no page.
  3. a "bf" ask carries the days the cloud ALREADY holds (a bitmap from a base day: 400 days = ~70 characters), so pages carry
     only missing days, newest first, and a cloud run that dies loses nothing (the next ask says what it has: resumable from the
     cloud's own truth, nothing to keep in step on the PC).
The child that answers is the datafeed child (engine/datafeed.spawn: detached, BELOW_NORMAL, no window), never in the weekday
session (checked before every page), builds missing summaries first (engine/tickrec.build_summaries, time-boxed), and every page's
meta is signed by the PC (engine/datafeed.send -> tools/status_sign) with the blob's sha256 + size. Never trades, arms, routes.

    python -X utf8 -m engine.ofbackfill budget        # tonight's page budget on this PC, with the math (one GET, no message)
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACCOUNT_PATH = "/v1/account"
MAX_PAGES = 12                 # pages for one "bf" ask at most (20 MiB in flight = 10 full pages; the count decides first)
DAY_MAX = 60                   # pages a UTC day at most (a stranger's asks on the public topic can never burn more)
ALERT_RESERVE = 25             # messages always left for trade alerts / alarms on top of the projection (pc_report keeps 12)
ANSWER_RESERVE = 3             # ... and for the normal bars / trades answers of the night (datafeed.OF_RESERVE = 2)
STORE_KEEP = 2_500_000         # bytes of ntfy attachment room always left (chart / alert attachments)
PAGE_GAP_S = 20                # between two pages
BUILD_S = 900                  # summaries built before the first page at most (the rest on the next ask / the autopilot)
EST_RATIO = 0.6                # first guess of pack bytes / gzip bytes (then the real ratio of the previous page)
BITMAP_DAYS = 420              # the "have" bitmap covers this many days back from its base day
SAMPLE_GAP_S = 900             # ntfy count sampled at most every 15 min (outside the session, by the 5-min hook)
SAFETY = 1.25                  # learned rates x this
MIN_RATE = 4.0                 # the core status post every 15 min: never project less
# posts an hour by kind (documented budget: ~210 status posts a weekday, most in the bots' hours; weekends: core + few ext)
DEFAULT_RATES = {"session": 11.0, "off": 5.8, "closed": 5.0}
RATE_MIN_N = 4                 # samples of a kind before its learned rate is used


# ------------------------------------------------------------------------------------------------ the "have" bitmap
def have_bitmap(days, base: str | None = None) -> dict:
    """{"hb0": base day (newest), "hb": base64url bits, bit i = base - i days held}. Days older than BITMAP_DAYS are dropped."""
    ds = sorted({str(d) for d in days})
    if not ds:
        return {}
    b0 = dt.date.fromisoformat(base or ds[-1])
    bits = bytearray((BITMAP_DAYS + 7) // 8)
    for d in ds:
        i = (b0 - dt.date.fromisoformat(d)).days
        if 0 <= i < BITMAP_DAYS:
            bits[i // 8] |= 1 << (i % 8)
    while bits and bits[-1] == 0:
        bits.pop()
    return {"hb0": b0.isoformat(), "hb": base64.urlsafe_b64encode(bytes(bits)).decode("ascii").rstrip("=")}


def have_days(req: dict) -> set:
    """The days a "bf" ask says the cloud holds. A bad bitmap = an empty set (the PC then sends everything it has)."""
    try:
        b0 = dt.date.fromisoformat(str(req.get("hb0")))
        s = str(req.get("hb") or "")
        if len(s) > 200:
            return set()
        bits = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        return {(b0 - dt.timedelta(days=i)).isoformat() for i in range(len(bits) * 8) if bits[i // 8] >> (i % 8) & 1}
    except Exception:  # noqa: BLE001
        return set()


# ------------------------------------------------------------------------------------------------ the budget
def _et(t):
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York"))


def hour_kind(t) -> str:
    """'session' (weekday 01:50-16:10 ET: LIT / ATLAS / charts), 'closed' (Fri 17:00 - Sun 18:00 ET), else 'off'."""
    e = _et(t)
    m, wd = e.hour * 60 + e.minute, e.weekday()
    if (wd == 4 and m >= 1020) or wd == 5 or (wd == 6 and m < 1080):
        return "closed"
    if wd < 5 and 110 <= m <= 970:
        return "session"
    return "off"


def rates(st: dict | None) -> dict:
    """Posts an hour per kind: the learned rate (x SAFETY) once it has RATE_MIN_N samples, else the default; never < MIN_RATE."""
    learned = ((st or {}).get("bf_rates") or {}) if isinstance(st, dict) else {}
    out = {}
    for k, d in DEFAULT_RATES.items():
        r = learned.get(k) if isinstance(learned.get(k), dict) else {}
        use = float(r.get("r", 0)) * SAFETY if int(r.get("n", 0)) >= RATE_MIN_N else d
        out[k] = round(max(MIN_RATE, use), 2)
    return out


def projected(now, reset_at, rt: dict) -> float:
    """Messages this PC will still post before ntfy's reset (15-minute steps, each at its kind's rate)."""
    now, reset_at = int(now), int(reset_at or 0)
    if reset_at <= now:
        return 0.0
    tot, t = 0.0, now
    while t < reset_at:
        step = min(900, reset_at - t)
        tot += rt[hour_kind(t + step // 2)] * step / 3600.0
        t += step
    return tot


def account(base: str, http_fn=None) -> dict | None:
    """ntfy's own count for this internet address: {"remaining", "used", "limit", "reset_at", "att_left", "att_file"} or None."""
    try:
        from . import datafeed as DF
        st, b = (http_fn or DF.http)("GET", str(base).rstrip("/") + ACCOUNT_PATH, None, {"Accept": "application/json"}, DF.HTTP_TIMEOUT_S)
        if int(st or 0) != 200:
            return None
        j = json.loads((b or b"{}").decode("utf-8", "replace"))
        s, lim = j.get("stats") or {}, j.get("limits") or {}
        if not isinstance(s, dict) or s.get("messages_remaining") is None or s.get("reset_at") is None:
            return None
        return {"remaining": int(s["messages_remaining"]), "used": int(s.get("messages") or 0), "limit": int(lim.get("messages") or 0),
                "reset_at": int(s["reset_at"]), "att_left": int(s.get("attachment_total_size_remaining") or 0),
                "att_file": int(lim.get("attachment_file_size") or 2_097_152)}
    except Exception:  # noqa: BLE001
        return None


def budget(now, q: dict | None, st: dict | None, page_bytes: int, want: int = MAX_PAGES) -> dict:
    """{"pages", "why", "math"}: how many pages may go now (0 when the count is unknown or the reserve is reached)."""
    now = int(now)
    if not q:
        return {"pages": 0, "why": "ntfy did not say its count (GET /v1/account): no page", "math": {}}
    rt = rates(st)
    need = projected(now, q["reset_at"], rt)
    msg_free = int(q["remaining"] - need - ALERT_RESERVE - ANSWER_RESERVE)
    store_free = int((q["att_left"] - STORE_KEEP) // max(1, page_bytes))
    utc = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    today = sum(1 for s in ((st or {}).get("bf_sent") or []) if s.get("utc") == utc)
    day_free = DAY_MAX - today
    pages = max(0, min(msg_free, store_free, day_free, int(want), MAX_PAGES))
    why = "ok" if pages else ("message reserve reached" if msg_free <= 0 else "attachment room full (pages expire in 3 h)"
                              if store_free <= 0 else f"{DAY_MAX} pages today already" if day_free <= 0 else "nothing asked")
    return {"pages": pages, "why": why, "math": {"remaining": q["remaining"], "projected": round(need, 1), "alert_reserve": ALERT_RESERVE,
                                                 "answer_reserve": ANSWER_RESERVE, "msg_free": msg_free, "att_left": q["att_left"],
                                                 "store_free": store_free, "day_free": day_free, "rates": rt,
                                                 "reset_in_h": round((q["reset_at"] - now) / 3600, 2)}}


def sample(st: dict, now, base: str, http_fn=None) -> dict:
    """Learn this PC's real posts an hour from ntfy's own count (called by the 5-minute hook outside the session, every 15 min).
    The PC's own data-feed posts between two samples are taken out (st["bf_own"]). Changes st in place; never raises."""
    try:
        now = int(now)
        last = st.get("bf_sample") if isinstance(st.get("bf_sample"), dict) else None
        if last and now - int(last.get("t", 0)) < SAMPLE_GAP_S:
            return st
        q = account(base, http_fn)
        if not q:
            return st
        own = int(st.get("bf_own") or 0)
        if last and int(last.get("reset_at", 0)) == q["reset_at"] and now - int(last["t"]) <= 4 * 3600:
            dh = (now - int(last["t"])) / 3600.0
            d = q["used"] - int(last.get("used", 0)) - (own - int(last.get("own", 0)))
            if dh > 0 and d >= 0:
                k = hour_kind((now + int(last["t"])) // 2)
                r = (st.setdefault("bf_rates", {})).setdefault(k, {"r": DEFAULT_RATES[k], "n": 0})
                r["r"] = round(d / dh if r["n"] == 0 else 0.8 * float(r["r"]) + 0.2 * d / dh, 3)
                r["n"] = int(r["n"]) + 1
        st["bf_sample"] = {"t": now, "used": q["used"], "reset_at": q["reset_at"], "own": own}
    except Exception:  # noqa: BLE001
        pass
    return st


# ------------------------------------------------------------------------------------------------ the pages
def candidates(dp_work: str | None, since: str, have: set, done: set) -> list:
    """Days with a full summary on the PC, since .., not held by the cloud, not sent in this answer: NEWEST first."""
    from . import datafeed as DF
    from . import datapipe as DP
    base = os.path.join(dp_work or DP.WORK, "days")
    try:
        names = os.listdir(base)
    except OSError:
        return []
    out = [d for d in names if DF._DAY.match(d) and d >= since and d not in have and d not in done
           and all(os.path.exists(os.path.join(base, d, "of", f)) for f in DF.OF_FILES)]
    return sorted(out, reverse=True)


def day_files(dp_work: str | None, d: str, now: int) -> dict:
    """{"days/<d>/of/<file>": bytes} + its of/manifest.json, the same files engine/datafeed.build_of sends."""
    from . import datafeed as DF
    from . import datapipe as DP
    base = os.path.join(dp_work or DP.WORK, "days", d, "of")
    fs = {}
    for f in DF.OF_FILES + ("NQ_depth5m.csv.gz", "NQ_paper.json.gz"):
        p = os.path.join(base, f)
        if f in DF.OF_FILES or os.path.exists(p):
            with open(p, "rb") as fh:
                fs[f"days/{d}/of/{f}"] = fh.read()
    info = {p.split("/", 2)[2]: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for p, b in fs.items()}
    fs[f"days/{d}/of/manifest.json"] = json.dumps({"v": DF.VERSION, "day": d, "kind": "of", "made_t": now, "partial": False,
                                                   "files": info}, indent=1, sort_keys=True).encode("utf-8")
    return fs


def build_page(cands: list, dp_work, now: int, max_zip: int, ratio: float = EST_RATIO) -> tuple:
    """(blob, days in it, gzip bytes in it) of the newest candidates that fit max_zip (at least one day; a day too big alone is
    skipped with days = [that day], blob b"")."""
    from . import ofpack
    files, days, gz = {}, [], 0
    for d in cands:
        fs = day_files(dp_work, d, now)
        c = sum(len(b) for b in fs.values())
        if days and (gz + c) * ratio > max_zip * 0.94:
            break
        files.update(fs)
        days.append(d)
        gz += c
    if not days:
        return b"", [], 0
    blob = ofpack.pack(files)
    while len(blob) > max_zip and len(days) > 1:
        drop = days.pop()                                              # the OLDEST day of the page waits for the next one
        for p in [p for p in files if p.startswith(f"days/{drop}/")]:
            gz -= len(files.pop(p))
        blob = ofpack.pack(files)
    if len(blob) > max_zip:
        return b"", days, gz
    return blob, days, gz


def pc_holds(dp_work=None) -> dict:
    """What the PC itself has: tick days (LE_TickRec) and summary days, oldest of each. Never raises."""
    out = {}
    try:
        from . import tickrec as T
        nq = T.nq_days()
        out.update(tick_days=len(nq), tick_oldest=nq[0] if nq else None)
    except Exception:  # noqa: BLE001
        pass
    try:
        allc = candidates(dp_work, "0000-00-00", set(), set())
        out.update(of_days=len(allc), of_oldest=allc[-1] if allc else None)
    except Exception:  # noqa: BLE001
        pass
    return out


def answer_bf(req: dict, now: int, w: str, env, http_fn, dp_work, max_zip: int, also: list, sleep=None, clock=None,
              build=None) -> dict:
    """ONE "bf" ask -> pages of the missing days, newest first, each only after ntfy's own count allows it. Never raises."""
    from . import datafeed as DF
    sleep = sleep or time.sleep
    clock = clock or time.time
    t0w, t0 = clock(), int(now)
    tnow = lambda: t0 + int(clock() - t0w)                                       # noqa: E731  (tests pass a fixed now)
    out = {"ok": False, "req": req.get("id"), "days": 0, "pages": 0, "what": "bf"}
    try:
        if build is None:
            try:
                from . import tickrec as T
                build = lambda: T.build_summaries(BUILD_S)                         # noqa: E731
            except Exception:  # noqa: BLE001
                build = None
        if build:
            try:
                out["built"] = (build() or {}).get("made")
            except Exception:  # noqa: BLE001
                pass
        have = have_days(req)
        since = str(req.get("since") or "0000-00-00")
        want = max(1, min(MAX_PAGES, int(DF._num(req.get("pages")) or MAX_PAGES)))
        base, _topic = DF.feed_cfg(env)
        holds = pc_holds(dp_work)
        done, ratio, first, last, why = set(), EST_RATIO, None, None, None
        page = 0
        while page < want:
            t = tnow()
            if DF.in_session(t):
                why = "the session started (01:50 ET): the rest waits for tonight"
                break
            cands = candidates(dp_work, since, have, done)
            if not cands:
                why = "nothing left: the cloud has every summary day this PC holds" if page else None
                break
            st = DF._state(w)
            q = account(base, http_fn)
            b = budget(t, q, st, max_zip, want - page)
            if not b["pages"]:
                why = b["why"]
                out["math"] = b["math"]
                break
            blob, days, gz = build_page(cands, dp_work, t, max_zip, ratio)
            if not blob:
                done.update(days)
                log_ = f"day {days[0] if days else '?'} alone is over one page: skipped"
                DF.log(f"backfill {req.get('id')}: {log_}", w)
                continue
            done.update(days)
            ratio = max(0.2, min(1.0, len(blob) / max(1, gz) * 1.03))
            page += 1
            more = bool(candidates(dp_work, since, have, done))
            meta = {"v": DF.VERSION, "kind": DF.ANS_KIND, "what": "bf", "enc": "ofp1", "req": str(req.get("id")), "page": page,
                    "made_t": t, "since": since, "days": len(days), "from": min(days), "to": max(days), "more": more,
                    "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "gz": gz, "ratio": round(len(blob) / max(1, gz), 3),
                    "pc": holds, "left": b["math"].get("msg_free"), "code": DF._code(DF.ROOT)}
            if more and (page == want or b["pages"] <= 1):              # the last page the ask / ntfy's count allows now
                meta["more_tomorrow"] = True
                meta["held"] = "the pages asked" if page == want else "ntfy count: the last page for now (reserve kept)"
            if also:
                meta["also"] = also
            ok, why_s, _j = DF.send(blob, meta, env, http_fn)
            _record(w, t, ok, why_s, meta, [req.get("id"), *also])
            DF.log(f"backfill {req.get('id')} page {page}: ok {ok} {len(days)} days ({meta['from']}..{meta['to']}) "
                   f"{len(blob)} B (gz {gz}, x{meta['ratio']}) left {meta['left']} {'' if ok else why_s}", w)
            if not ok:
                why = why_s
                page -= 1
                break
            out.update(ok=True, pages=page, days=out["days"] + len(days), more=more)
            first = meta["from"] if first is None or meta["from"] < first else first
            last = meta["to"] if last is None or meta["to"] > last else last
            if not more:
                break
            sleep(PAGE_GAP_S)
        if not out["ok"]:                                       # nothing went: ONE small signed line says why (no attachment)
            msg = {"v": DF.VERSION, "kind": DF.ANS_KIND, "what": "bf", "req": str(req.get("id")), "days": 0, "made_t": tnow(),
                   "more": bool(candidates(dp_work, since, have, done)), "pc": holds, "held": str(why or "nothing to send")[:160]}
            if also:
                msg["also"] = also
            q = account(base, http_fn)
            if q and q["remaining"] - projected(tnow(), q["reset_at"], rates(DF._state(w))) - ALERT_RESERVE > 1:
                ok, why_s, _j = DF.send(b"", msg, env, http_fn)
                _record(w, tnow(), ok, why_s, {**msg, "page": 0}, [req.get("id"), *also])
                out["ok"] = bool(ok)
        out.update(first=first, last=last, why=why, pc=holds)
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, why=f"{e.__class__.__name__}: {str(e)[:160]}")
    return out


def _record(w: str, now: int, ok: bool, why: str, meta: dict, rids: list) -> None:
    from . import datafeed as DF
    st = DF._state(w)
    if ok:
        ans = st.get("answered") or {}
        for rid in rids:
            ans[str(rid)] = now
        st["answered"] = {k: v for k, v in ans.items() if int(DF._num(v)) > now - 2 * 86400}
        if meta.get("days"):
            utc = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
            st["bf_sent"] = ([s for s in (st.get("bf_sent") or []) if int(DF._num(s.get("t"))) > now - 3 * 86400]
                             + [{"t": now, "utc": utc, "req": meta.get("req"), "page": meta.get("page"), "days": meta.get("days"),
                                 "bytes": meta.get("bytes"), "from": meta.get("from"), "to": meta.get("to")}])[-200:]
        st["bf_own"] = int(st.get("bf_own") or 0) + 1
        st["last_sent_t"] = now
    else:
        st["last_error"] = {"t": now, "req": meta.get("req"), "why": str(why)[:200]}
    DF._write_json(os.path.join(w, "state.json"), st)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["budget"]:
        from . import datafeed as DF
        base, _t = DF.feed_cfg()
        now = int(time.time())
        b = budget(now, account(base), DF._state(DF.WORK), DF.MAX_ZIP)
        print(json.dumps({"in_session": DF.in_session(now), **b, "pc": pc_holds()}, indent=1))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
