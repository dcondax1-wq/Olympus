"""Claude's side of the data pipe (engine/datapipe.py, docs/DATA_PIPE.md): the PC's days from the backup repo branch `data`.

    git fetch olympus data                       # what this does first (the backup repo dcondax1-wq/olympus)
    python tools/data_pull.py                    # fetch, copy new days to data/pc_days/, import the bars, queue the proposals
    python tools/data_pull.py --review           # + the ZEUS daily review of the newest day, rebuilt here from the same files
    python tools/data_pull.py --edge             # + tools/edge_health.py on the now-current data/
    python tools/data_pull.py --no-import        # copy only (data/NQ_*.csv untouched)
    python tools/data_pull.py --ref <rev>        # read another ref (tests, or an already fetched branch); --no-fetch skips git fetch

What it imports (futures only: NinjaTrader bars of the owner's PC, never Yahoo / CFD):
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
import io
import json
import os
import re
import subprocess
import sys

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


def gather(out_dir: str, sym: str, days: list | None = None, data_dir: str = DATA) -> tuple:
    """({tf: frame of the preferred root}, [notes]) over every pulled day."""
    import pandas as pd
    from engine import pcbars
    frames = {"1m": [], "5m": []}
    notes = []
    anchor = anchor_code(sym, data_dir)
    for day in sorted(days or [os.path.basename(p) for p in os.listdir(out_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)]):
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
        for tf in ("1m", "5m"):
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
            with contextlib.redirect_stdout(io.StringIO()):
                IF._finish(sym, add.copy(), data_dir, check=True)
            lines.append(f"{sym} {tf}: +{len(add)} bars to {pd.to_datetime(int(add['time'].max()), unit='s', utc=True):%Y-%m-%d %H:%M} UTC")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pull the PC's days from the backup repo branch data (futures bars, trades, review).")
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
    global REPO
    REPO = a.repo or REPO
    ref = a.ref or "FETCH_HEAD"
    if not a.no_fetch and not a.ref:
        ok, err = fetch(a.remote)
        if not ok:
            print(f"git fetch {a.remote} data failed: {err or 'no branch data yet'}")
            print("  The PC has not sent data yet, or the backup repo is not attached (add_repo dcondax1-wq/olympus).")
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
