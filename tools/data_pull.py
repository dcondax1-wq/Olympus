"""Claude's side of the data pipe (engine/datapipe.py, docs/DATA_PIPE.md): the PC's days (NinjaTrader bars + trades) into data/.

    python tools/data_pull.py --latest           # THE way (night-data 2026-11-18): ask the PC over ntfy (engine/datafeed.py), wait
                                                 # (it answers within ~5 min outside 01:50-16:00 ET), unzip into data/pc_days/,
                                                 # append the new bars to data/NQ_1m / NQ_5m / ES_5m.csv (+ coarser files), queue
    python tools/data_pull.py --latest --edge    # + tools/edge_health.py on the fresh data/
    python tools/data_pull.py --latest --wait 0  # only ask (or use an answer already on the topic); run it again later
    python tools/data_pull.py --feed-status      # the answers on the topic (3 h) and the last pull, nothing written

The old route (the PC's git push to the backup's branch `data`) is OFF on the PC (the backup repo is public; no push sign-in):
    git fetch olympus data                       # what the plain command does first (the backup repo dcondax1-wq/olympus)
    python tools/data_pull.py                    # fetch, copy new days to data/pc_days/, import the bars, queue the proposals
    python tools/data_pull.py --review           # + the ZEUS daily review of the newest day, rebuilt here from the same files
    python tools/data_pull.py --edge             # + tools/edge_health.py on the now-current data/
    python tools/data_pull.py --no-import        # copy only (data/NQ_*.csv untouched)
    python tools/data_pull.py --ref <rev>        # read another ref (tests, or an already fetched branch); --no-fetch skips git fetch

What it imports (futures only: NinjaTrader bars of the owner's PC, never Yahoo / CFD):
  GC / SI (else MGC / SIL) 1-minute bars around the Kalshi K8 windows (04:45-05:45, 15:45-17:15 ET) when the PC has a chart of
         them -> data/metals/<SYM>_1m.csv (append-only, with the chart contract per bar: import_metals)
  NQ  <- bars/NQ_1m (an NQ chart) else bars/MNQ_1m (same index points, research/writeups/mnq-vs-nq-feed.md), then 5m for days
         without 1m; ES <- ES else MES. Through data/import_futures._finish (builds 5m / 15m / 1h, the roll file applied), and ONLY
         bars newer than the newest bar already in data/<SYM>_1m.csv / _5m.csv: the TradingView exports are never overwritten
         (the research baselines stay reproducible). The overlap with the exports is price-checked first (median 5 pts a
         session, import_futures._check_price_space); a chart on a contract other than the roll file's anchor (the December
         roll: "MNQ 03-27" vs anchor NQZ26) is refused with the fix (record the roll in data/NQ_rolls.json), never mixed.
  proposals.jsonl of every day -> research/zeus_queue.jsonl (de-duplicated by id): ideas for Claude to TEST, never applied.
Nothing here trades or touches a live setting.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "pc_days")                     # gitignored
QUEUE = os.path.join(ROOT, "research", "zeus_queue.jsonl")
REPO = ROOT                                             # the git repo read (tests point it at a scratch repo)
PREFER = {"NQ": ("NQ", "MNQ"), "ES": ("ES", "MES")}
MONTH = {"03": "H", "06": "M", "09": "U", "12": "Z"}


def git(args, binary=False, timeout=300):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, timeout=timeout)
    return r.returncode, (r.stdout if binary else r.stdout.decode("utf-8", "replace")), r.stderr.decode("utf-8", "replace")


def fetch(remote: str = "olympus") -> tuple:
    """git fetch <remote> data. The remote is added from update_source.json (no user part) when missing."""
    c, _o, _e = git(["remote", "get-url", remote])
    if c:
        try:
            src = json.load(open(os.path.join(REPO, "update_source.json"), encoding="utf-8"))
            url = re.sub(r"(https?://)[^@/\s]+@", r"\1", str(src.get("url") or ""))
            if url:
                git(["remote", "add", remote, url])
        except Exception:
            pass
    c, _o, e = git(["fetch", "-q", remote, "data"])
    return c == 0, e.strip()[-300:]


def list_days(ref: str) -> dict:
    """{day: [paths inside the day folder]} on ref."""
    c, o, _e = git(["ls-tree", "-r", "--name-only", ref, "days/"])
    out: dict = {}
    for p in (o.splitlines() if c == 0 else []):
        m = re.match(r"days/(\d{4}-\d{2}-\d{2})/(.+)$", p)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def copy_days(ref: str, out_dir: str = OUT, force: bool = False) -> list:
    """Write every day folder of ref into out_dir/<day>/ (a day whose manifest is unchanged is skipped). -> days written."""
    done = []
    for day, paths in sorted(list_days(ref).items()):
        d = os.path.join(out_dir, day)
        c, man, _e = git(["show", f"{ref}:days/{day}/manifest.json"], binary=True)
        mp = os.path.join(d, "manifest.json")
        if not force and c == 0 and os.path.exists(mp) and open(mp, "rb").read() == man:
            rv = os.path.join(d, "review.json")
            if "review.json" not in paths or os.path.exists(rv):
                continue
        for p in paths:
            c, b, _e = git(["show", f"{ref}:days/{day}/{p}"], binary=True)
            if c:
                continue
            fp = os.path.join(d, *p.split("/"))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as fh:
                fh.write(b)
        done.append(day)
    return done


def _contract_code(chart: str | None) -> str | None:
    m = re.search(r"(\d{2})-(\d{2})$", str(chart or "").strip())
    return f"{MONTH.get(m.group(1), '?')}{m.group(2)}" if m else None


def anchor_code(sym: str, data_dir: str = DATA) -> str | None:
    try:
        a = json.load(open(os.path.join(data_dir, f"{sym}_rolls.json"), encoding="utf-8")).get("anchor") or ""
        return a[-3:] if len(a) >= 3 else None
    except Exception:
        return None


def complete_days(out_dir: str = OUT) -> list:
    """The pulled days whose session had closed when they were packed (manifest "partial": false). Only these go into data/:
    an unfinished session is sent again (complete) by the next answer, so no bar is ever skipped or doubled."""
    out = []
    try:
        names = sorted(p for p in os.listdir(out_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p))
    except OSError:
        return out
    for d in names:
        try:
            with open(os.path.join(out_dir, d, "manifest.json"), encoding="utf-8") as fh:
                man = json.load(fh)
        except Exception:
            continue
        if isinstance(man, dict) and not man.get("partial"):
            out.append(d)
    return out


def gather(out_dir: str, sym: str, days: list | None = None, data_dir: str = DATA) -> tuple:
    """({tf: frame of the preferred root}, [notes]) over every pulled day."""
    import pandas as pd
    from engine import pcbars
    frames = {"1m": [], "5m": []}
    notes = []
    anchor = anchor_code(sym, data_dir)
    for day in sorted(days if days is not None else complete_days(out_dir)):
        d = os.path.join(out_dir, day)
        try:
            man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        except Exception:
            continue
        files = man.get("files") or {}
        for tf in ("1m", "5m"):
            root = next((r for r in PREFER[sym] if (files.get(f"bars/{r}_{tf}.csv.gz") or {}).get("rows")), None)
            if root is None:
                continue
            code = _contract_code((man.get("chart") or {}).get(root))
            if anchor and code and code != anchor:
                notes.append(f"{sym} {day}: chart on {man['chart'][root]} but data/{sym}_rolls.json is anchored to {anchor}: "
                             f"record the roll first (docs/ROLL_DEC_2026.md), nothing imported for this day")
                continue
            with open(os.path.join(d, "bars", f"{root}_{tf}.csv.gz"), "rb") as fh:
                frames[tf].append(pcbars.decode(fh.read()))
    out = {tf: (pcbars.tidy(pd.concat(v)) if v else pcbars.tidy(None)) for tf, v in frames.items()}
    return out, notes


def import_bars(out_dir: str = OUT, data_dir: str = DATA, days: list | None = None, dry: bool = False) -> list:
    """Append the PC's bars newer than data/<SYM>_1m / _5m.csv. -> one line per symbol."""
    import pandas as pd
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import import_futures as IF
    lines = []
    for sym in ("NQ", "ES"):
        F, notes = gather(out_dir, sym, days, data_dir)
        lines += notes
        for tf in ("5m", "1m"):             # 5m first: the PC's whole 5m bar is on file before 1m rebuilds the coarser files
            # (import_futures._finish keeps an old bar for a 5m bucket the new 1m bars cover only in part)
            new = F[tf]
            path = os.path.join(data_dir, f"{sym}_{tf}.csv")
            if not len(new):
                continue
            if not os.path.exists(path):
                lines.append(f"{sym} {tf}: no data/{sym}_{tf}.csv to append to (skipped)")
                continue
            old = pd.read_csv(path)
            last = int(old["time"].max()) if len(old) else 0
            ov = new[new["time"] <= last]
            add = new[new["time"] > last]
            try:
                if len(ov):
                    IF._check_price_space(sym, tf, old[old["time"] >= int(ov["time"].min())], ov)
            except ValueError as e:
                lines.append(f"{sym} {tf}: REFUSED, {e}")
                continue
            if len(add) < 3:
                lines.append(f"{sym} {tf}: up to date ({pd.to_datetime(last, unit='s', utc=True):%Y-%m-%d %H:%M} UTC)")
                continue
            if dry:
                lines.append(f"{sym} {tf}: would add {len(add)} bars")
                continue
            import contextlib
            add = add.copy()
            if len(add) and (add["volume"].round() == add["volume"]).all():
                add["volume"] = add["volume"].round().astype("int64")     # whole volumes stay "313", not "313.0": the
            with contextlib.redirect_stdout(io.StringIO()):                  # rewritten file keeps every old line as it was
                IF._finish(sym, add, data_dir, check=True)
            lines.append(f"{sym} {tf}: +{len(add)} bars to {pd.to_datetime(int(add['time'].max()), unit='s', utc=True):%Y-%m-%d %H:%M} UTC")
    return lines


METALS = {"GC": ("GC", "MGC"), "SI": ("SI", "SIL")}       # engine/datafeed.SYM_TFS: 1-minute, the Kalshi K8 windows only
METALS_DIR = os.path.join(DATA, "metals")
METAL_COLS = ("time", "open", "high", "low", "close", "volume", "contract")


def import_metals(out_dir: str = OUT, metals_dir: str = METALS_DIR, days: list | None = None, dry: bool = False) -> list:
    """The PC's COMEX gold / silver 1-minute bars around the K8 windows (04:45-05:45, 15:45-17:15 ET) -> data/metals/<SYM>_1m.csv
    (append-only: only bars newer than the file's last, each with its chart contract, e.g. "GC 12-26"; futures, never CFD).
    Stdlib only. -> one line per metal that had bars."""
    import csv
    import gzip as _gz
    lines = []
    for sym, roots in METALS.items():
        rows = {}
        for day in sorted(days if days is not None else complete_days(out_dir)):
            d = os.path.join(out_dir, day)
            try:
                man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
            except Exception:
                continue
            files = man.get("files") or {}
            root = next((r for r in roots if (files.get(f"bars/{r}_1m.csv.gz") or {}).get("rows")), None)
            if root is None:
                continue
            chart = str((man.get("chart") or {}).get(root) or root)[:20]
            try:
                with open(os.path.join(d, "bars", f"{root}_1m.csv.gz"), "rb") as fh:
                    text = _gz.decompress(fh.read()).decode("ascii", "replace")
            except (OSError, EOFError, ValueError):
                continue
            for r in csv.DictReader(io.StringIO(text)):
                try:
                    t = int(float(r["time"]))
                    rows[t] = [t] + [float(r[k]) for k in ("open", "high", "low", "close")] + [r.get("volume") or "0", chart]
                except (KeyError, ValueError, TypeError):
                    continue
        if not rows:
            continue
        path = os.path.join(metals_dir, f"{sym}_1m.csv")
        last = 0
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    for r in csv.DictReader(fh):
                        last = max(last, int(float(r["time"])))
            except Exception:
                last = 0
        add = [rows[t] for t in sorted(rows) if t > last]
        if not add:
            lines.append(f"{sym} 1m (K8 windows): up to date")
            continue
        if dry:
            lines.append(f"{sym} 1m (K8 windows): would add {len(add)} bars")
            continue
        os.makedirs(metals_dir, exist_ok=True)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            if new:
                w.writerow(METAL_COLS)
            for r in add:
                w.writerow([r[0]] + [f"{x:g}" for x in r[1:5]] + r[5:])
        lines.append(f"{sym} 1m (K8 windows): +{len(add)} bars to {dt.datetime.fromtimestamp(add[-1][0], dt.timezone.utc):%Y-%m-%d %H:%M} UTC "
                     f"-> data/metals/{sym}_1m.csv")
    return lines


def queue_proposals(out_dir: str = OUT, queue: str = QUEUE) -> int:
    from engine.datapipe import _jl_read
    have = {r.get("id") for r in _jl_read(queue)}
    new = []
    for day in sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []:
        for r in _jl_read(os.path.join(out_dir, day, "proposals.jsonl")):
            if r.get("id") and r["id"] not in have:
                have.add(r["id"])
                new.append({**r, "status": "new"})
    if new:
        os.makedirs(os.path.dirname(queue), exist_ok=True)
        with open(queue, "a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return len(new)


# ================================================================================================ the ntfy route (--latest)
def newest_day(data_dir: str = DATA) -> str | None:
    """The CME day of the OLDEST "newest bar" of data/NQ_1m, NQ_5m, ES_5m.csv: the PC is asked from that day on (it is asked
    again because it may be cut short; only newer bars are ever added)."""
    from engine.datapipe import trading_day
    days = []
    for nm in ("NQ_1m", "NQ_5m", "ES_5m"):
        p = os.path.join(data_dir, f"{nm}.csv")
        try:
            with open(p, "rb") as fh:
                fh.seek(max(0, os.path.getsize(p) - 400))
                last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
            days.append(trading_day(int(float(last.split(",")[0]))))
        except Exception:
            continue
    return min(days) if days else None


def _et_str(t) -> str:
    from zoneinfo import ZoneInfo
    try:
        return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York")).strftime("%a %b %d %H:%M ET")
    except Exception:
        return "?"


def answers_on_topic(now=None, since="3h") -> tuple:
    """(ntfy answered, [valid answers, oldest first]) of the data topic."""
    from engine import datafeed as DF
    base, topic = DF.feed_cfg()
    ok, msgs = DF.poll(base, topic, since)
    now = int(now or time.time())
    return ok, [x for x in (DF.parse_answer(m, now, base) for m in msgs) if x]


def covering(answers: list, since: str, need: str) -> dict | None:
    """The newest answer already on the topic that covers since .. need in one piece."""
    for x in reversed(answers):
        if x.get("days") and str(x.get("from")) <= since and str(x.get("to")) >= need and not x.get("more"):
            return x
    return None


def wait_answer(rid: str, t0: int, wait_s: float, step: float = 15.0, sleep=None, say=print) -> dict | None:
    """Poll the topic until the answer to request rid is there (or wait_s passed)."""
    from engine import datafeed as DF
    sleep = sleep or time.sleep
    base, topic = DF.feed_cfg()
    end, nxt = time.time() + wait_s, time.time() + 120
    while True:
        ok, msgs = DF.poll(base, topic, int(t0 - 60))
        now = int(time.time())
        for m in reversed(msgs if ok else []):
            x = DF.parse_answer(m, now, base)
            if x and (x.get("req") == rid or rid in (x.get("also") or [])):
                return x
        if time.time() >= end:
            return None
        if time.time() >= nxt:
            say(f"  still waiting for the PC ({int((time.time() - t0) // 60)} min)")
            nxt += 120
        sleep(step)


def fetch_bundle(x: dict) -> bytes:
    """Download one answer's zip; its size and sha256 must be the ones the PC announced. ValueError otherwise."""
    from engine import datafeed as DF
    st, b = DF.http("GET", x["url"], None, None, 120, DF.MAX_ZIP + 200_000)
    if st != 200:
        raise ValueError(f"download failed (HTTP {st or 'no answer'}): the file is kept 3 h after the PC sent it")
    if len(b) != int(x.get("size") or -1):
        raise ValueError(f"download is {len(b):,} bytes, the PC announced {x.get('size')}")
    if hashlib.sha256(b).hexdigest() != x.get("sha256"):
        raise ValueError("download checksum differs from the PC's")
    return b


def latest(a, sleep=None) -> int:
    """Ask the PC over ntfy (or use its answer already on the topic), unzip into data/pc_days/. 0 = days received,
    2 = asked but no answer yet, 3 = the PC had nothing new, 1 = a problem (said in plain words)."""
    from engine import datafeed as DF
    from engine.datapipe import last_session
    sleep = sleep or time.sleep
    now = int(time.time())
    since = a.since or newest_day(a.data) or (dt.date.today() - dt.timedelta(days=30)).isoformat()
    need = last_session(now)
    session = DF.in_session(now)
    ok, answers = answers_on_topic(now)
    if not ok:
        print("ntfy.sh did not answer: nothing changed, try again in a minute.")
        return 1
    use = covering(answers, since, need)
    wait_s = 60.0 * (a.wait if a.wait is not None else (0 if session else 9))
    got, rounds, last = [], 0, None
    while True:
        if use is None:
            rid = secrets.token_hex(5)
            okp, why = DF.post_request(rid, since, int(time.time()))
            if not okp:
                print(f"could not ask the PC: {why}")
                return 1
            print(f"Asked the PC for its bars + trades since {since} (request {rid})."
                  + (" It is trading now (01:50-16:00 ET): it answers after 16:00 ET; run this again then." if session else
                     " It answers within ~5 min."))
            if wait_s <= 0:
                return 2
            use = wait_answer(rid, int(time.time()), wait_s, sleep=sleep)
            if use is None:
                print(f"No answer from the PC in {int(wait_s // 60)} min. It checks every 5 min when the bot task runs; "
                      "`python tools/board.py read` shows when it last reported. Run this again later (the answer waits 3 h).")
                return 2
        last = use
        if not use.get("days"):
            print(f"The PC could not pack its data: {use['error']}. Nothing imported." if use.get("error") else
                  f"The PC answered: no bars or trades since {since} (is its LE_BarFeed chart open?).")
            break
        try:
            blob = fetch_bundle(use)
            wrote = DF.extract(blob, a.out)
        except ValueError as e:
            print(f"The PC's answer was not usable: {e}. Nothing imported.")
            return 1
        got += wrote
        print(f"Received {len(wrote)} day(s) {use['from']} .. {use['to']} ({len(blob):,} bytes, sent {_et_str(use.get('made_t'))})"
              + (f"; unfinished session kept out of data/: {', '.join(d for d, p in wrote if p)}" if any(p for _d, p in wrote) else ""))
        if use.get("more") and rounds < 4:                       # the PC stopped at its size cap: ask from the next day
            since = (dt.date.fromisoformat(str(use["to"])) + dt.timedelta(days=1)).isoformat()
            use, rounds = None, rounds + 1
            continue
        break
    rec = {"t": now, "via": "ntfy", "req": (last or {}).get("req"), "days": sorted({d for d, _p in got}),
           "from": (last or {}).get("from"), "to": (last or {}).get("to"), "made_t": (last or {}).get("made_t")}
    try:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "_last_pull.json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
    except OSError:
        pass
    return 0 if got else 3


def feed_status() -> int:
    from engine import datafeed as DF
    ok, answers = answers_on_topic(since="12h")
    print(f"ntfy topic {DF.feed_cfg()[1]}: " + ("not reachable" if not ok else f"{len(answers)} answer(s) in 12 h"))
    for x in answers[-5:]:
        print(f"  {_et_str(x.get('time'))}: request {x.get('req')}, {x.get('days')} day(s) {x.get('from')} .. {x.get('to')}"
              f"{' (more)' if x.get('more') else ''}, {x.get('size') or 0:,} bytes"
              + ("" if x.get("url") else " (nothing to send)"))
    try:
        with open(os.path.join(OUT, "_last_pull.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        print(f"last pull here: {_et_str(r.get('t'))}, {len(r.get('days') or [])} day(s) {r.get('from')} .. {r.get('to')}")
    except Exception:
        print("last pull here: none yet")
    print(f"data/ needs the PC's bars from: {newest_day()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pull the PC's days (futures bars, trades, review): --latest over ntfy, else the "
                                             "backup repo branch data.")
    ap.add_argument("--latest", action="store_true", help="ask the PC over ntfy and import (engine/datafeed.py)")
    ap.add_argument("--since", default=None, help="--latest: first CME day to ask for (default: the newest day in data/)")
    ap.add_argument("--wait", type=float, default=None, help="--latest: minutes to wait for the PC (default 9; 0 = only ask)")
    ap.add_argument("--feed-status", action="store_true", help="show the answers on the ntfy topic and the last pull")
    ap.add_argument("--remote", default="olympus")
    ap.add_argument("--repo", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--ref", default=None, help="read this ref instead of FETCH_HEAD (implies --no-fetch unless given)")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--queue", default=QUEUE)
    ap.add_argument("--no-import", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-copy every day folder")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--edge", action="store_true")
    a = ap.parse_args(argv)
    if a.feed_status:
        return feed_status()
    if a.latest:
        rc = latest(a)
        if rc not in (0, 3):
            return rc
        if rc == 3:
            print("Nothing new from the PC.")
    else:
        global REPO
        REPO = a.repo or REPO
        ref = a.ref or "FETCH_HEAD"
        if not a.no_fetch and not a.ref:
            ok, err = fetch(a.remote)
            if not ok:
                print(f"git fetch {a.remote} data failed: {err or 'no branch data yet'}")
                print("  The PC no longer pushes there (the backup repo is public): use python tools/data_pull.py --latest")
                return 1
            c, o, _e = git(["rev-parse", "FETCH_HEAD"])
            ref = o.strip() if c == 0 and o.strip() else ref
        days = list_days(ref)
        if not days:
            print("branch data has no day folders yet")
            return 1
        wrote = copy_days(ref, a.out, a.force)
        print(f"days on branch data: {len(days)} ({min(days)} .. {max(days)}); copied {len(wrote)} to {os.path.relpath(a.out, ROOT)}/")
    if not a.no_import:
        for ln in import_bars(a.out, a.data, dry=a.dry_run):
            print("  " + ln)
        for ln in import_metals(a.out, os.path.join(a.data, "metals"), dry=a.dry_run):
            print("  " + ln)
    n = 0 if a.dry_run else queue_proposals(a.out, a.queue)
    print(f"research queue: +{n} proposal(s) -> {os.path.relpath(a.queue, ROOT)}")
    if a.review:
        from engine import datapipe, zeus_review
        R = zeus_review.review(datapipe.load_days(a.out), zeus_review.edge_light())
        print(R["text"])
        for i in R["items"]:
            print(f"  [{'!!' if i['level'] == 'act' else '..'}] {i['text']}")
        pc = (datapipe.load_day(os.path.join(a.out, R["day"])) or {}).get("review") if R.get("day") else None
        if pc and pc.get("text") != R["text"]:
            print(f"  (the PC wrote: {pc.get('text')})")
    if a.edge and not a.dry_run:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "edge_health.py")], cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
