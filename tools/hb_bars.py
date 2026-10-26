"""Collect the PC's NinjaTrader bars from the history of the `heartbeat` branch (research, read-only).

The PC force-pushes ONE orphan commit to `heartbeat` every ~5 min (engine/heartbeat.py), with bars_1m.csv.gz (the last
3 days of LE_BarFeed's MNQ 1m bars) and bars_5m.csv.gz (the last 40 days of 5m bars). The branch therefore holds one
commit only; the older ones stay fetchable by their SHA, which GitHub's activity API lists (one row per push). This tool
pages that list (gh api, through the session's proxy), fetches a spread of commits by SHA (one per `--every` hours, the
last one of each block), and joins their bars: for a bar that several commits carry, the NEWEST commit's version wins and
the number of bars NinjaTrader revised between commits is counted.

    python tools/hb_bars.py                    # -> research/feed/nt_mnq_1m.csv.gz, nt_mnq_5m.csv.gz, nt_mnq_meta.json
    python tools/hb_bars.py --every 6          # fewer commits (1m bars: 3 days per commit, so <= 48 h never leaves a hole)
    python tools/hb_bars.py --no-api           # only the commit the branch points to now (no gh / no activity API)

No secrets: the bars are market data the PC already publishes. Never writes to the branch.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import pcbars  # noqa: E402

OUT_DIR = os.path.join(ROOT, "research", "feed")
REPO = "demetrades2000-coder/nq-liquidity-engine"
BRANCH = "heartbeat"


def _git(*args, binary=False):
    p = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, timeout=300)
    return p.returncode, (p.stdout if binary else p.stdout.decode("utf-8", "replace")), p.stderr.decode("utf-8", "replace")


def activity(repo=REPO, branch=BRANCH, pages=200) -> list:
    """[(sha, iso time)] of every push to the branch, oldest first (GitHub activity API; [] without gh)."""
    if not shutil.which("gh"):
        return []
    base = f"repos/{repo}/activity?ref=refs/heads/{branch}&per_page=100"
    url, rows = base, []
    for _ in range(pages):
        p = subprocess.run(["gh", "api", "-i", url], capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            break
        head, _, body = p.stdout.replace("\r\n", "\n").partition("\n\n")
        try:
            data = json.loads(body)
        except ValueError:
            break
        rows += [(x["after"], x["timestamp"]) for x in data if x.get("after")]
        m = re.search(r'after=([^>&]+)>; rel="next"', head)
        if not m:
            break
        url = base + "&after=" + m.group(1)          # the Link header names the numeric repo id, which the proxy refuses
    return sorted(set(rows), key=lambda r: r[1])


def pick(rows, every_h=3) -> list:
    """The last push of every `every_h`-hour block."""
    last = {}
    for sha, ts in rows:
        last[(ts[:10], int(ts[11:13]) // every_h)] = (sha, ts)
    return sorted(last.values(), key=lambda r: r[1])


def read_commit(sha) -> dict:
    """{name: DataFrame} of the bar files in one heartbeat commit (missing / unreadable files left out)."""
    rc, ls, _ = _git("ls-tree", "--name-only", sha)
    out = {}
    if rc != 0:
        return out
    for name in ls.split():
        nm = name.strip('"')
        if nm in pcbars.HB_FILES:
            rc, blob, _ = _git("show", f"{sha}:{nm}", binary=True)
            if rc == 0:
                df = pcbars.decode(blob)
                if len(df):
                    out[nm] = df
    return out


def join(frames: list) -> tuple:
    """Frames oldest commit first -> (union with the newest version of every bar, [(bar time, max |OHLC change|)] of the
    bars NinjaTrader revised between commits)."""
    import pandas as pd
    if not frames:
        return pcbars.tidy(None), 0
    cur = pcbars.tidy(frames[0])
    revised = []
    for f in frames[1:]:
        f = pcbars.tidy(f)
        m = cur.merge(f, on="time", suffixes=("_a", "_b"))
        if len(m):
            d = pd.concat([(m[c + "_a"] - m[c + "_b"]).abs() for c in ("open", "high", "low", "close")], axis=1).max(axis=1)
            revised += [(int(t), float(x)) for t, x in zip(m["time"], d) if x > 1e-9]
        cur = pcbars.tidy(pd.concat([cur, f]))          # last wins = the newer commit
    return cur, revised


def collect(every_h=3, use_api=True, out_dir=OUT_DIR, verbose=True) -> dict:
    rows = activity() if use_api else []
    sel = pick(rows, every_h) if rows else []
    rc, tip, _ = _git("ls-remote", "origin", f"refs/heads/{BRANCH}")
    tip = tip.split()[0] if rc == 0 and tip.strip() else None
    if tip and all(s != tip for s, _ in sel):
        sel.append((tip, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    shas = [s for s, _ in sel]
    for i in range(0, len(shas), 20):
        _git("fetch", "--quiet", "--depth=1", "origin", *shas[i:i + 20])
    got = {n: [] for n in pcbars.HB_FILES}
    used = []
    for sha, ts in sel:
        files = read_commit(sha)
        if files:
            used.append({"sha": sha[:12], "t": ts, "files": sorted(files)})
        for n, df in files.items():
            got[n].append(df)
    os.makedirs(out_dir, exist_ok=True)
    meta = {"source": f"github {REPO} branch {BRANCH}: {len(rows)} pushes listed, {len(sel)} commits fetched, "
                      f"{len(used)} with bars", "every_h": every_h, "commits": used, "files": {}}
    for n, tf in ((pcbars.BARS_1M, "1m"), (pcbars.BARS_5M, "5m")):
        df, rev = join(got[n])
        path = os.path.join(out_dir, f"nt_mnq_{tf}.csv.gz")
        with open(path, "wb") as fh:
            fh.write(pcbars.encode(df))
        meta["files"][tf] = {"path": os.path.relpath(path, ROOT).replace(os.sep, "/"), "bars": int(len(df)),
                             "first_t": int(df["time"].min()) if len(df) else None,
                             "last_t": int(df["time"].max()) if len(df) else None, "revised_between_commits": len(rev),
                             "revised": [[t, round(x, 2)] for t, x in rev[:300]]}
        if verbose:
            print(f"{tf}: {len(df)} bars, {len(rev)} revised between commits -> {path}")
    if verbose:
        print(meta["source"])
    with open(os.path.join(out_dir, "nt_mnq_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    return meta


def load(tf: str, out_dir=OUT_DIR):
    """The collected NinjaTrader MNQ bars of one timeframe (tidy frame; empty when not collected)."""
    p = os.path.join(out_dir, f"nt_mnq_{tf}.csv.gz")
    if not os.path.exists(p):
        return pcbars.tidy(None)
    with open(p, "rb") as fh:
        return pcbars.decode(fh.read())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--every", type=int, default=3, help="hours between the commits fetched (default 3)")
    ap.add_argument("--no-api", action="store_true", help="only the branch's current commit")
    a = ap.parse_args(argv)
    collect(every_h=a.every, use_api=not a.no_api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
