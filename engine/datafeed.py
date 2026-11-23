"""DATA FEED over ntfy.sh (night-data 2026-11-18): the PC's NinjaTrader bars + closed trades reach Claude with no GitHub at all.

Why not the git branch `data` (engine/datapipe.py push): the backup repo dcondax1-wq/olympus is PUBLIC (GitHub API on
2026-11-18: "visibility": "public"), so a `data` branch there would publish every trade row forever, and the PC has no push
sign-in (it fetches the public repo anonymously, so Git Credential Manager never saved one: every nightly push failed and the
ZEUS review said "needs you: the PC could not send its data"). Automated pushes from the PC are also the pattern the first
account was suspended for. So the datapipe's git push is OFF by default now (LE_DATAPIPE_GIT=1 turns it back on) and the data
goes this way, on request, with no new sign-in and nothing for the owner to do:

  cloud  `python tools/data_pull.py --latest` posts ONE small request {"kind": "le-data-req", "id", "since"} to the ntfy topic
         TOPIC, waits (the PC answers within ~5 minutes outside its session hours), downloads the zip, imports the bars.
  PC     maybe_answer() runs in the 5-minute ops task (engine/ops_checks.tick -> engine/datapipe.maybe_run): one small GET of
         the topic, never during 01:50-16:00 ET on weekdays (the session). A new request starts ONE detached low-priority child
         (`python -m engine.datafeed answer --from-hook`) that packs the asked days exactly like the data branch's day folders
         and PUTs them as ONE ntfy attachment (the message = the JSON meta: days, sha256, bytes, bar rows):
           days/<day>/bars/<ROOT>_<tf>.csv.gz   NinjaTrader 1m + 5m bars, NQ (else MNQ) and ES (else MES), time = bar OPEN
           days/<day>/trades.jsonl.gz           every ledger row of the day (Zlarior, extra accounts, ATLAS, paper too), tagged
                                                src / bot / acct / mode; account names cut to the last 4, no balances, no paths
           days/<day>/manifest.json             rows, sha256, chart contract, partial (an unfinished session), code version
           days/<day>/review.json, proposals.jsonl   when the nightly run (engine/datapipe) made them
           days/<day>/gaps.json         (2026-11-20) the bot's own "NOT routed" lines, held-back entries and uptime samples
                                        of the day (logs/exec_audit/notes.json, ids cut): why a backtest trade did not reach
                                        the account, readable from the cloud (day_gaps)
         Oldest day first, at most MAX_ZIP bytes: a longer gap says "more" and the cloud asks again from where it stopped.
ntfy.sh anonymous limits, measured 2026-11-18: an attachment up to 2 MB (1.9 MB accepted, 2.6 MB refused with HTTP 413), kept
3 hours; messages kept 12 hours; 250 messages a day per IP. The PC's status posts already use ~210 a day, so an answer is ONE
message and at most DAILY_CAP a day, never more often than MIN_GAP_S. Polls are not messages.
Privacy: like the status topic (tools/web_public/status_feed.json) the topic name is in this public repo, so anyone could read
it: it carries only what the status topic already shows (trades with account names cut to the last 4, no balances, no file
paths, never the live phrase) plus public-kind market bars, and an attachment is gone after 3 hours. The cloud only accepts an
answer to its own request id, from the same ntfy server, with the announced size + sha256, and only day files of the known names.
Never trades, arms, routes or changes a setting; never raises into its caller. Stdlib only here (the child imports pandas
through engine/datapipe, which the PC already has).

    python -X utf8 -m engine.datafeed status                       # the last answers, the last error
    python -X utf8 -m engine.datafeed pack --since 2026-11-10      # build the zip locally only (logs/datafeed/pack.zip)
    python -X utf8 -m engine.datafeed answer --since 2026-11-10    # send one now (by hand; same limits)
Tests: python -X utf8 -m tests.test_datafeed (a local fake ntfy server, no internet). Docs: docs/DATA_PIPE.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
VERSION = 1
BASE = "https://ntfy.sh"
TOPIC = "olympus-nq-data-fe51b8cfeb111559"     # not a secret (see Privacy above); LE_DATAFEED_TOPIC / LE_DATAFEED_BASE = tests
REQ_KIND, ANS_KIND = "le-data-req", "le-data"
WORK = os.path.join(ROOT, "logs", "datafeed")   # logs/ is gitignored: state, pending request, log
MAX_ZIP = 1_850_000                             # ntfy.sh anonymous: 2 MB per attachment
MAX_UNPACKED = 30_000_000                       # the cloud's guard: one file inside the zip, after gunzip
REQ_MAX_AGE_S = 6 * 3600                        # an older request is ignored (ntfy keeps messages 12 h)
POLL_WINDOW_S = 6 * 3600
DAYS_BACK = 60                                  # a request reaches back at most this far (the PC keeps 1m 40 days, 5m 120 days)
DAILY_CAP = 8                                   # answers a day (ntfy.sh 250 messages a day per IP; status posts use ~210)
MIN_GAP_S = 240                                 # between two answers (one 5-minute tick)
MAX_TRIES = 3                                   # children started per request (a failing upload never loops)
STALE_LOCK_S = 1800
BLACKOUT = (110, 960)                           # weekdays 01:50-16:00 ET (engine/datapipe.BLACKOUT): the session, nothing runs
HTTP_TIMEOUT_S = 8.0
PUT_TIMEOUT_S = 120.0
PREFER = {"NQ": ("NQ", "MNQ"), "ES": ("ES", "MES"), "GC": ("GC", "MGC"), "SI": ("SI", "SIL")}
TFS = ("1m", "5m")
SYM_TFS = {"GC": ("1m",), "SI": ("1m",)}        # metals (Kalshi K8 legs): 1-minute around 04:45-05:45 / 15:45-17:15 ET only
                                                # (engine/datapipe.day_bars cuts them; ~150 bars a metal a day, a few KB)
EXTRAS = ("review.json", "proposals.jsonl", "learn.json")   # from the nightly run's local day folder (logs/datapipe/days/<day>/);
                                                # learn.json = ZEUS learned's public cut (engine/zeus_learn.public)
UA = "olympus-pc-data/1"
_ID = re.compile(r"^[a-z0-9]{6,24}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# night-cleanup 2026-11-22: fills.jsonl.gz (pack_day sends it since day-speed 2026-11-20) was missing here, so the cloud refused
# EVERY PC answer from Nov 20 on ("unexpected file in the bundle") and no bar after Nov 19 arrived. tests/test_datafeed_names.py
# keeps this list = every name pack_day can write.
DAY_FILE = re.compile(r"^days/(\d{4}-\d{2}-\d{2})/(manifest\.json|trades\.jsonl\.gz|fills\.jsonl\.gz|review\.json|proposals\.jsonl|learn\.json|gaps\.json|"
                      r"bars/(?:MNQ|NQ|MES|ES|GC|MGC|SI|SIL)_(?:1m|5m)\.csv\.gz)$")


# ================================================================================================ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if v == v and abs(v) != float("inf") else 0.0


def in_session(now) -> bool:
    """Weekdays 01:50-16:00 ET: the PC trades; the feed neither polls nor packs then."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and BLACKOUT[0] <= m < BLACKOUT[1]


def feed_cfg(env=None) -> tuple:
    """(ntfy base URL, topic)."""
    env = os.environ if env is None else env
    return str(env.get("LE_DATAFEED_BASE") or BASE).rstrip("/"), str(env.get("LE_DATAFEED_TOPIC") or TOPIC).strip()


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj):
    try:
        from .datapipe import _write_json as _w
        _w(path, obj)
    except Exception:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=1, default=str)
        except Exception:
            pass


def log(text: str, work: str | None = None):
    try:
        from .datapipe import scrub_text
        d = work or WORK
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "datafeed.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now(ET):%Y-%m-%d %H:%M:%S} ET  {scrub_text(text)[:400]}\n")
    except Exception:
        pass


# ================================================================================================ ntfy (one place, fakeable)
def http(method, url, body=None, headers=None, timeout=HTTP_TIMEOUT_S, limit=4_000_000) -> tuple:
    """-> (status, bytes). Never raises; status 0 = no answer. LE_PR_NO_NET=1 = no network (as tools/pc_report)."""
    if os.environ.get("LE_PR_NO_NET") == "1":
        return 0, b"network off (LE_PR_NO_NET=1)"
    try:
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("User-Agent", UA)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.read(limit + 1)
    except urllib.error.HTTPError as e:
        try:
            b = e.read(2000)
        except Exception:
            b = b""
        return int(e.code), b
    except Exception as e:  # noqa: BLE001
        return 0, e.__class__.__name__.encode()


def poll(base, topic, since, http_fn=None) -> tuple:
    """(answered, [ntfy message dicts], oldest first) cached on the topic since `since` (unix seconds or e.g. '3h')."""
    if not topic:
        return False, []
    st, body = (http_fn or http)("GET", f"{base}/{topic}/json?poll=1&since={urllib.parse.quote(str(since))}", None, None,
                                 HTTP_TIMEOUT_S)
    if not 200 <= int(st or 0) < 300:
        return False, []
    out = []
    for ln in (body or b"").decode("utf-8", "replace").splitlines():
        try:
            m = json.loads(ln)
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("event", "message") == "message":
            out.append(m)
    return True, sorted(out, key=lambda m: (_num(m.get("time")), str(m.get("id"))))


def body_of(m) -> dict:
    try:
        j = json.loads((m or {}).get("message") or "")
    except (TypeError, ValueError, AttributeError):
        return {}
    return j if isinstance(j, dict) else {}


def parse_request(m, now) -> dict | None:
    """A valid request: {"id", "since", "t"}; None for anything else (other kinds, too old, a bad id / day)."""
    j = body_of(m)
    if j.get("kind") != REQ_KIND or j.get("v") != VERSION:
        return None
    rid, since = str(j.get("id") or ""), str(j.get("since") or "")
    if not _ID.match(rid) or not _DAY.match(since):
        return None
    try:
        dt.date.fromisoformat(since)
    except ValueError:
        return None
    t = _num(m.get("time")) or _num(j.get("t"))
    if not t or t < now - REQ_MAX_AGE_S or t > now + 600:
        return None
    lo = (_et(now).date() - dt.timedelta(days=DAYS_BACK)).isoformat()
    return {"id": rid, "since": max(since, lo), "t": int(t)}


def _pinned_vk():
    """The PC's public verify key pinned in tools/web_public/status_feed.json (tools/status_sign.py), or None. Never raises."""
    try:
        from tools import status_sign as _ss
        return _ss.feed_vk()
    except Exception:  # noqa: BLE001
        return None


def _sign_msg(msg: str) -> str:
    """The PC's signature on the answer's meta (day-security2 2026-11-20, LEAD_WIRES W7): Claude then knows the bars came from this
    PC, not from a stranger who posted to the public topic. No key / no `cryptography` / too big = the message as before."""
    try:
        from tools import status_sign as _ss
        k = _ss.load_key()
        if not k:
            return msg
        out = _ss.sign_text(msg, k)
        return out if len(out.encode("utf-8")) <= 4000 else msg
    except Exception:  # noqa: BLE001
        return msg


def parse_answer(m, now=None, base: str | None = None, vk="pinned") -> dict | None:
    """An answer: its meta + the attachment {"url", "size", "expires"}; None when it is not one, is expired, or points to
    another server than `base`. A "days": 0 answer (the PC has nothing) has no attachment. With the PC's key pinned
    (status_feed.json "vk"; vk=None = do not check), an answer the PC did not sign is None (a stranger's fake bars)."""
    if vk == "pinned":                               # the real ntfy.sh only (a test's local fake server checks with vk=...)
        vk = _pinned_vk() if str(base or BASE).rstrip("/") == BASE else None
    if vk:
        try:
            from tools import status_sign as _ss
            if not _ss.verify_text((m or {}).get("message"), vk):
                return None
        except Exception:  # noqa: BLE001
            return None
    j = body_of(m)
    if j.get("kind") != ANS_KIND or j.get("v") != VERSION or not _ID.match(str(j.get("req") or "")):
        return None
    out = {**j, "time": int(_num(m.get("time"))), "mid": str(m.get("id") or "")}
    if not int(_num(j.get("days"))):
        return {**out, "days": 0, "url": None}
    att = m.get("attachment") if isinstance(m.get("attachment"), dict) else {}
    url, size, exp = str(att.get("url") or ""), int(_num(att.get("size"))), _num(att.get("expires"))
    if base and not url.startswith(str(base).rstrip("/") + "/file/"):
        return None
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        return None
    if size <= 0 or size > MAX_ZIP + 150_000 or size != int(_num(j.get("bytes"))):
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", str(j.get("sha256") or "")):
        return None
    if now is not None and exp and exp < now + 20:
        return None
    if not (_DAY.match(str(j.get("from") or "")) and _DAY.match(str(j.get("to") or ""))):
        return None
    return {**out, "url": url, "size": size, "expires": int(exp)}


def post_request(rid: str, since: str, now=None, env=None, http_fn=None) -> tuple:
    """The cloud's ask. -> (ok, why)."""
    base, topic = feed_cfg(env)
    body = json.dumps({"v": VERSION, "kind": REQ_KIND, "id": rid, "since": since, "t": int(now or time.time()),
                       "want": ["bars", "trades"]}, separators=(",", ":")).encode("utf-8")
    st, b = (http_fn or http)("POST", f"{base}/{topic}", body, {"Priority": "1", "Content-Type": "text/plain"}, HTTP_TIMEOUT_S)
    if 200 <= int(st or 0) < 300:
        return True, "ok"
    return False, ("ntfy.sh rate limit" if st == 429 else f"ntfy answered {st or 'nothing'} {(b or b'')[:80]!r}")


# ================================================================================================ the bundle (PC side)
def _code(root: str) -> str | None:
    try:
        from .datapipe import _code_version
        return _code_version(root)
    except Exception:
        return None


def manifest(day: str, files: dict, now, partial: bool, contracts: dict, counts: dict, code) -> bytes:
    """The same shape as engine/datapipe.manifest (tools/data_pull.gather reads files[...]["rows"] and "chart")."""
    from . import pcbars
    info = {}
    for p, b in sorted(files.items()):
        if p == "manifest.json":
            continue
        x = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        if p.startswith("bars/"):
            f = pcbars.decode(b)
            x.update(rows=int(len(f)), first=int(f["time"].min()) if len(f) else None, last=int(f["time"].max()) if len(f) else None)
        info[p] = x
    m = {"v": VERSION, "day": day, "made_t": int(now), "partial": bool(partial), "files": info, "counts": counts or {},
         "chart": contracts or {}, "code": code, "via": "ntfy", "privacy": "account names cut to the last 4; no balances"}
    return json.dumps(m, indent=1, sort_keys=True).encode("utf-8")


def pick_frames(frames: dict) -> dict:
    """{(sym, tf): (root, frame)}: NQ else MNQ, ES else MES (one root per symbol: the cloud imports only that one)."""
    out = {}
    for sym, roots in PREFER.items():
        for tf in SYM_TFS.get(sym, TFS):
            for r in roots:
                f = frames.get((r, tf))
                if f is not None and len(f):
                    out[(sym, tf)] = (r, f)
                    break
    return out


def wanted_days(since: str, now, frames: dict, rows: list) -> list:
    from . import datapipe as DP
    newest = DP.trading_day(now)
    cand = {d for d in DP.bar_days(frames) if since <= d <= newest}
    for r in rows:
        try:
            d = DP.trading_day(int(r.get("entry_t") or r.get("t")))
        except (TypeError, ValueError):
            continue
        if since <= d <= newest:
            cand.add(d)
    return sorted(d for d in cand if dt.date.fromisoformat(d).weekday() < 5)


GAPS_UPTIME_MAX = 400                           # uptime samples a day in gaps.json (the bot samples every 4 min + each change)


def day_gaps(day: str, notes: dict | None) -> bytes | None:
    """gaps.json of one CME day (night-nqlive 2026-11-20, research/writeups/lit-more-money-2026-11-19.md "Proposal 2": a real
    miss like Nov 10-11 could not be explained from the cloud): the bot's own "NOT routed / NOT traded / size 0 / never routed"
    lines of the day, the entries it held back with its reason, and the uptime samples (running, entries blocked, feed block,
    kill), all from logs/exec_audit/notes.json (engine/fill_audit.collect). Account ids cut to the last 4 (engine/notify.mask_ids);
    no balances, no paths. None when the day has nothing (no file then). Never raises."""
    try:
        from . import fill_audit as FA
        from .notify import mask_ids
        N = notes or {}
        lines = FA.day_not_routed(day, notes=N)
        blocked = [{"entry_t": int(k), "et": FA._hm(int(k)), "reason": mask_ids(str((v or {}).get("reason") or ""))[:200],
                    "running": (v or {}).get("running")}
                   for k, v in sorted((N.get("blocked") or {}).items()) if str(k).isdigit() and FA.trading_day(int(k)) == day]
        ups = [{"t": int(u["t"]), "et": FA._hm(int(u["t"])), **{k: u.get(k) for k in ("running", "blocked", "feed_block", "kill")}}
               for u in (N.get("uptime") or []) if isinstance(u, dict) and u.get("t") and FA.trading_day(int(u["t"])) == day]
        if not (lines or blocked or ups):
            return None
        for u in ups:
            if u.get("feed_block"):
                u["feed_block"] = mask_ids(str(u["feed_block"]))[:120]
        rec = {"v": 1, "day": day, "not_routed": lines, "blocked": blocked, "uptime": ups[-GAPS_UPTIME_MAX:],
               "uptime_n": len(ups), "note": "the PC bot's own record of why an entry of this day did not reach the account"}
        return json.dumps(rec, indent=1, sort_keys=True).encode("utf-8")
    except Exception:
        return None


def pack_day(day: str, picked: dict, rows: list, names, contracts: dict, now, code, local_days: str, notes: dict | None = None) -> dict:
    """{path inside days/<day>/: bytes} for one CME day (manifest.json last)."""
    from . import datapipe as DP
    files = {}
    for (sym, tf), (root, f) in sorted(picked.items()):
        files.update(DP.day_bars(day, {(root, tf): f}))
    tr = DP.day_trades(day, rows, names)
    files["trades.jsonl.gz"] = DP.gz(DP.jsonl_bytes(tr))
    try:                                         # day-speed 2026-11-20: send / fill times of every entry order (read-only)
        fl = DP.day_fills(day, names=names)
        if fl:
            files["fills.jsonl.gz"] = DP.gz(DP.jsonl_bytes(fl))
    except Exception:
        pass
    g = day_gaps(day, notes)
    if g is not None and len(g) < 200_000:
        files["gaps.json"] = g
    for x in EXTRAS:
        p = os.path.join(local_days, day, x)
        try:
            if os.path.getsize(p) < 200_000:
                with open(p, "rb") as fh:
                    files[x] = fh.read()
        except OSError:
            pass
    close = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(17, 0), ET).timestamp())
    files["manifest.json"] = manifest(day, files, now, now < close, {r: contracts.get(r) for (_s, _t), (r, _f) in picked.items()
                                                                       if contracts.get(r)},
                                      {"trades": len(tr), "entries": sum(1 for r in tr if r.get("side") in ("buy", "sell")),
                                       "exits": sum(1 for r in tr if r.get("side") == "exit")}, code)
    return files


def _entry_cost(day: str, files: dict) -> int:
    return sum(len(b) + 2 * len(f"days/{day}/{p}") + 100 for p, b in files.items())


def zip_days(packed: dict) -> bytes:
    """Deterministic zip (fixed dates): gzip members stored, json members deflated."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for day in sorted(packed):
            for p, b in sorted(packed[day].items(), key=lambda kv: (kv[0] == "manifest.json", kv[0])):
                zi = zipfile.ZipInfo(f"days/{day}/{p}", date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_STORED if p.endswith(".gz") else zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                z.writestr(zi, bytes(b))
    return buf.getvalue()


def build(since: str, now=None, root: str = ROOT, folder: str | None = None, archive_root: str | None = None,
          exec_store: str | None = None, dp_work: str | None = None, max_zip: int = MAX_ZIP) -> tuple:
    """(zip bytes or b"", meta) of every CME day from `since` (oldest first, under max_zip). Raises only on a broken PC
    install (the caller catches)."""
    from . import datapipe as DP
    now = int(now if now is not None else time.time())
    w = dp_work or DP.WORK
    frames = DP.bar_frames(folder, archive_root)
    rows = DP._jl_read(os.path.join(w, DP.ARCHIVE)) + DP.ledger_rows(root, exec_store)
    names = DP.known_names(root, folder)
    contracts = DP.chart_contracts(folder)
    picked = pick_frames(frames)
    code = _code(root)
    days = wanted_days(since, now, {(r, tf): f for (_s, tf), (r, f) in picked.items()}, rows)
    notes = _read_json(os.path.join(exec_store or os.path.join(root, "logs", "exec_audit"), "notes.json"), {}) or {}
    packed, size, more = {}, 22, False
    for d in days:
        fs = pack_day(d, picked, rows, names, contracts, now, code, os.path.join(w, "days"), notes=notes)
        c = _entry_cost(d, fs)
        if packed and size + c > max_zip:
            more = True
            break
        packed[d] = fs
        size += c
    blob = zip_days(packed) if packed else b""
    while len(blob) > max_zip and len(packed) > 1:                   # the estimate was low: drop the newest day, say "more"
        packed.pop(max(packed))
        more = True
        blob = zip_days(packed)
    bars = {}
    for (sym, tf), (r, _f) in sorted(picked.items()):
        xs = [(json.loads(fs["manifest.json"]).get("files") or {}).get(f"bars/{r}_{tf}.csv.gz") or {} for fs in packed.values()]
        n = sum(int(x.get("rows") or 0) for x in xs)
        if n:
            bars[f"{sym}_{tf}"] = {"root": r, "rows": n, "last": max(int(x.get("last") or 0) for x in xs)}
    meta = {"v": VERSION, "kind": ANS_KIND, "made_t": now, "since": since, "days": len(packed),
            "from": min(packed) if packed else None, "to": max(packed) if packed else None,
            "partial": sorted(d for d, fs in packed.items() if json.loads(fs["manifest.json"]).get("partial"))[:3],
            "more": bool(more), "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest() if blob else None,
            "bars": bars, "trades": sum(int((json.loads(fs["manifest.json"]).get("counts") or {}).get("trades") or 0)
                                        for fs in packed.values()), "code": code}
    return blob, meta


def send(blob: bytes, meta: dict, env=None, http_fn=None) -> tuple:
    """PUT the zip as ONE ntfy attachment (message = the meta JSON). -> (ok, why, ntfy's answer dict)."""
    base, topic = feed_cfg(env)
    msg = json.dumps(meta, separators=(",", ":"), sort_keys=True, default=str)
    if len(msg.encode("utf-8")) > 3900:
        msg = json.dumps({k: meta.get(k) for k in ("v", "kind", "req", "made_t", "since", "days", "from", "to", "more",
                                                    "bytes", "sha256", "code")}, separators=(",", ":"), sort_keys=True)
    msg = _sign_msg(msg)
    if blob:
        h = {"Filename": f"pcdata-{meta.get('from')}-{meta.get('to')}.zip", "Message": msg, "Priority": "1"}
        st, b = (http_fn or http)("PUT", f"{base}/{topic}", blob, h, PUT_TIMEOUT_S)
    else:
        st, b = (http_fn or http)("POST", f"{base}/{topic}", msg.encode("utf-8"), {"Priority": "1"}, HTTP_TIMEOUT_S)
    try:
        j = json.loads((b or b"{}").decode("utf-8", "replace"))
    except ValueError:
        j = {}
    if 200 <= int(st or 0) < 300:
        return True, "ok", j if isinstance(j, dict) else {}
    if st == 413:
        return False, "ntfy.sh refused the size (413): attachment too large or today's attachment budget used", {}
    if st == 429:
        return False, "ntfy.sh rate limit (429): too many messages today from this PC", {}
    return False, f"ntfy answered {st or 'nothing'}", {}


# ================================================================================================ the answer (PC child)
def _state(w: str) -> dict:
    st = _read_json(os.path.join(w, "state.json"), {}) or {}
    return st if isinstance(st, dict) else {}


def answer(req: dict, now=None, root: str = ROOT, work: str | None = None, folder: str | None = None, env=None,
           http_fn=None, archive_root: str | None = None, exec_store: str | None = None, dp_work: str | None = None,
           max_zip: int = MAX_ZIP) -> dict:
    """Pack the days since req["since"] and send them as the answer to req["id"]. Returns a summary; never raises."""
    w = work or WORK
    now = int(now if now is not None else time.time())
    out = {"ok": False, "req": req.get("id"), "days": 0}
    also = [str(x) for x in (req.get("also") or [])][:6]
    try:
        blob, meta = build(str(req.get("since")), now, root, folder, archive_root, exec_store, dp_work, max_zip)
        meta["req"] = str(req.get("id"))
        if also:
            meta["also"] = also
        ok, why, j = send(blob, meta, env, http_fn)
        out.update(ok=ok, why=why, days=meta["days"], bytes=meta["bytes"], first=meta["from"], last=meta["to"], more=meta["more"],
                   mid=j.get("id"))
    except Exception as e:  # noqa: BLE001   (a broken pack: say so on the topic, so Claude reads why instead of waiting)
        out.update(ok=False, why=f"{e.__class__.__name__}: {str(e)[:160]}")
        try:
            from .datapipe import scrub_text
            err = {"v": VERSION, "kind": ANS_KIND, "req": str(req.get("id")), "days": 0, "made_t": now,
                   "error": scrub_text(out["why"])[:200], **({"also": also} if also else {})}
            if send(b"", err, env, http_fn)[0]:
                out.update(ok=True, error=err["error"])
        except Exception:
            pass
    st = _state(w)
    day = _et(now).date().isoformat()
    if out["ok"]:
        ans = st.get("answered") or {}
        for rid in [req.get("id"), *(req.get("also") or [])]:
            ans[str(rid)] = now
        st["answered"] = {k: v for k, v in ans.items() if int(_num(v)) > now - 2 * 86400}
        st["sent"] = ([s for s in (st.get("sent") or []) if str(s.get("day") or "") >= (_et(now).date() - dt.timedelta(days=7)).isoformat()]
                      + [{"t": now, "day": day, "req": out["req"], "days": out["days"], "bytes": out.get("bytes"),
                          "from": out.get("first"), "to": out.get("last"), "more": out.get("more")}])[-40:]
        st["last_sent_t"] = now
    if not out["ok"] or out.get("error"):
        st["last_error"] = {"t": now, "req": out["req"], "why": str(out.get("why"))[:200]}
    _write_json(os.path.join(w, "state.json"), st)
    log(f"answer {out['req']}: ok {out['ok']} days {out['days']} ({out.get('first')}..{out.get('last')}) bytes {out.get('bytes')} "
        f"{'' if out['ok'] else out.get('why')}", w)
    return out


# ================================================================================================ the hook (5-minute ops task)
def _pid_alive(pid) -> bool:
    try:
        from .learn_loop import _pid_alive as _a
        return _a(pid)
    except Exception:
        return False


def spawn(work: str | None = None) -> int | None:
    """One detached, low-priority child with no window (it outlives the 5-minute task)."""
    try:
        import subprocess
        w = work or WORK
        os.makedirs(w, exist_ok=True)
        lg = open(os.path.join(w, "child.log"), "a", encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", "-m", "engine.datafeed", "answer", "--from-hook"]
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8",
               "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
        kw = {"cwd": ROOT, "stdout": lg, "stderr": lg, "stdin": subprocess.DEVNULL, "env": env}
        if os.name == "nt":
            base = 0x00004000 | 0x08000000 | 0x00000200          # BELOW_NORMAL | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid     # + BREAKAWAY_FROM_JOB
            except OSError:
                return subprocess.Popen(cmd, creationflags=base, **kw).pid
        kw["start_new_session"] = True
        kw["preexec_fn"] = lambda: os.nice(10)
        return subprocess.Popen(cmd, **kw).pid
    except Exception:
        return None


def pending(msgs: list, now, st: dict) -> list:
    """The requests on the topic not answered yet (by this PC's state or by an answer already on the topic), oldest first."""
    done = set((st.get("answered") or {}).keys())
    for m in msgs:
        a = body_of(m)
        if a.get("kind") == ANS_KIND:
            done.add(str(a.get("req") or ""))
            done.update(str(x) for x in (a.get("also") or []) if isinstance(a.get("also"), list))
    tries = st.get("tries") or {}
    out = []
    for m in msgs:
        r = parse_request(m, now)
        if r and r["id"] not in done and int(_num(tries.get(r["id"]))) < MAX_TRIES and r["id"] not in {x["id"] for x in out}:
            out.append(r)
    return out


def maybe_answer(now=None, env=None, say=print, work: str | None = None, spawn_fn=None, http_fn=None) -> dict | None:
    """The ops task's hook (every 5 min, from engine/datapipe.maybe_run): outside the session, one GET of the topic; a new
    request starts the child once (limits: DAILY_CAP a day, MIN_GAP_S apart, MAX_TRIES per request). Never raises."""
    try:
        e = os.environ if env is None else env
        if str(e.get("LE_DATAFEED", "")).strip() == "0":
            return None
        now = int(now if now is not None else time.time())
        if in_session(now):
            return None
        w = work or WORK
        st = _state(w)
        lk = _read_json(os.path.join(w, "running.json"), None)
        if isinstance(lk, dict) and now - int(_num(lk.get("t"))) < STALE_LOCK_S and _pid_alive(lk.get("pid")):
            return None
        base, topic = feed_cfg(e)
        ok, msgs = poll(base, topic, int(now - POLL_WINDOW_S), http_fn)
        st["last_poll"] = {"t": now, "ok": ok, "n": len(msgs)}
        visible = {r["id"] for r in (parse_request(m, now) for m in msgs) if r}
        st["tries"] = {k: v for k, v in (st.get("tries") or {}).items() if k in visible}   # forget asks gone from the topic
        todo = pending(msgs, now, st) if ok else []
        why = None
        day = _et(now).date().isoformat()
        if todo and sum(1 for s in (st.get("sent") or []) if s.get("day") == day) >= DAILY_CAP:
            why = f"{DAILY_CAP} answers today already"
        elif todo and now - int(_num(st.get("last_sent_t"))) < MIN_GAP_S:
            why = "answered a few minutes ago"
        if not todo or why:
            if why and st.get("held_why") != why:
                st["held_why"] = why
                log(f"request held: {why}", w)
            _write_json(os.path.join(w, "state.json"), st)
            return None
        req = dict(todo[-1])                                        # the newest ask, from the earliest day any open ask wants
        req["since"] = min(r["since"] for r in todo)
        req["also"] = [r["id"] for r in todo[:-1]]
        tr = st.get("tries") or {}
        for rid in [req["id"], *req["also"]]:
            tr[rid] = int(_num(tr.get(rid))) + 1                   # counted before the start: a child that dies still counts
        st["tries"] = tr
        st.pop("held_why", None)
        _write_json(os.path.join(w, "state.json"), st)              # written BEFORE the child: its own write comes after
        _write_json(os.path.join(w, "pending.json"), {**req, "t_seen": now})
        pid = (spawn_fn or spawn)(w)
        if not pid:
            log(f"request {req['id']}: the child did not start", w)
            return None
        _write_json(os.path.join(w, "running.json"), {"pid": pid, "t": now, "req": req["id"]})
        say(f"  [OK]  data feed: answering Claude's request {req['id']} (days since {req['since']}; pid {pid})")
        return {"pid": pid, "req": req}
    except Exception as ex:  # noqa: BLE001
        try:
            say(f"  [..] data feed skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        except Exception:
            pass
        return None


def status(work: str | None = None) -> dict:
    w = work or WORK
    st = _state(w)
    return {"topic": feed_cfg()[1], "last_poll": st.get("last_poll"), "sent": (st.get("sent") or [])[-5:],
            "last_error": st.get("last_error"), "held": st.get("held_why")}


# ================================================================================================ unpacking (cloud side)
def extract(blob: bytes, out_dir: str) -> list:
    """Write the zip's day files into out_dir/<day>/... -> [(day, partial)] written. Only names DAY_FILE allows (no other
    path, no '..'), every member and its gunzip under MAX_UNPACKED, a day's manifest must name that day. Raises ValueError on a
    bad zip (nothing of that day is written)."""
    import gzip
    try:
        z = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as e:
        raise ValueError(f"not a zip: {e}") from e
    by_day: dict = {}
    for info in z.infolist():
        name = info.filename
        m = DAY_FILE.match(name)
        if not m or ".." in name or name.startswith("/") or "\\" in name:
            raise ValueError(f"unexpected file in the bundle: {name[:80]}")
        if info.file_size > MAX_UNPACKED:
            raise ValueError(f"file too large in the bundle: {name}")
        by_day.setdefault(m.group(1), {})[m.group(2)] = info
    checked = []                                                    # every day is checked before anything is written
    for day, members in sorted(by_day.items()):
        if "manifest.json" not in members:
            raise ValueError(f"{day}: no manifest in the bundle")
        data = {}
        for p, info in members.items():
            try:
                b = z.read(info)
                if p.endswith(".gz"):
                    with gzip.GzipFile(fileobj=io.BytesIO(b)) as gf:
                        if len(gf.read(MAX_UNPACKED + 1)) > MAX_UNPACKED:
                            raise ValueError(f"{day}/{p}: unpacks too large")
            except (zipfile.BadZipFile, OSError, EOFError) as e:
                raise ValueError(f"{day}/{p}: damaged ({e.__class__.__name__})") from e
            data[p] = b
        try:
            man = json.loads(data["manifest.json"].decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ValueError(f"{day}: the manifest is not JSON") from e
        if not isinstance(man, dict) or man.get("day") != day:
            raise ValueError(f"{day}: the manifest names another day")
        for p, x in (man.get("files") or {}).items():
            if p in data and isinstance(x, dict) and x.get("sha256") and hashlib.sha256(data[p]).hexdigest() != x["sha256"]:
                raise ValueError(f"{day}/{p}: checksum differs from the manifest")
        checked.append((day, data, bool(man.get("partial"))))
    out = []
    for day, data, partial in checked:
        d = os.path.join(out_dir, day)
        for p, b in data.items():
            fp = os.path.join(d, *p.split("/"))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp + ".tmp", "wb") as fh:
                fh.write(b)
            os.replace(fp + ".tmp", fp)
        out.append((day, partial))
    return out


# ================================================================================================ CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.datafeed", description="PC -> Claude data over ntfy.sh (bars, trades)")
    ap.add_argument("cmd", choices=("status", "pack", "answer"), nargs="?", default="status")
    ap.add_argument("--since", help="first CME day (YYYY-MM-DD); default 10 days ago")
    ap.add_argument("--from-hook", action="store_true", help="the ops task's child: answer logs/datafeed/pending.json")
    ap.add_argument("--out", default=os.path.join(WORK, "pack.zip"))
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=1, default=str))
        return 0
    try:
        from .learn_loop import lower_priority
        lower_priority()
    except Exception:
        pass
    since = a.since or (dt.date.today() - dt.timedelta(days=10)).isoformat()
    if a.cmd == "pack":
        blob, meta = build(since)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "wb") as fh:
            fh.write(blob)
        print(json.dumps(meta, indent=1, default=str))
        print(f"wrote {a.out} ({len(blob):,} bytes): nothing sent")
        return 0
    if a.from_hook:
        req = _read_json(os.path.join(WORK, "pending.json"), None)
        try:
            if not isinstance(req, dict) or not _ID.match(str(req.get("id") or "")):
                print("no pending request")
                return 1
            r = answer(req)
        finally:
            for f in ("running.json", "pending.json"):
                try:
                    os.remove(os.path.join(WORK, f))
                except OSError:
                    pass
    else:
        r = answer({"id": "byhand" + dt.datetime.now(ET).strftime("%H%M%S").lower(), "since": since})
    print(("sent" if r["ok"] else "NOT sent") + f": {r.get('days')} day(s) {r.get('first')}..{r.get('last')} "
          f"({r.get('bytes') or 0:,} bytes){'' if r['ok'] else ' - ' + str(r.get('why'))}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
