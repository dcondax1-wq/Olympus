#!/usr/bin/env python3
"""VERIFY LIVE: after a publish, check that the LIVE site really serves what the repo says it should. READ ONLY: plain GET requests, nothing is written
anywhere but the report file (research/handoff/<today>/verify_live.md); no key, no login, no POST.

    python tools/verify_live.py                                   # the real site + the bot heartbeat
    python tools/verify_live.py --base http://127.0.0.1:8000/     # a local copy (tests/test_verify_live.py)
    python tools/verify_live.py --no-heartbeat --no-write         # only the site, nothing written
    options: --max-age-h 30 (jarvis.json cards; a card's own stale_after wins; weekend-aware), --hb-age-min 10, --workers 4, --out FILE, --repo ROOT

What it checks (one row each, ONE table, then VERIFIED or PROBLEMS; exit code 0 / 1):
  every app of olympus/apps-list.js   its page is 200 and carries the kit tags / data-app / ?v= the repo's page has; its manifest, apple-touch-icon and icons are 200 with
                                      the right content-type and the PNG size the file really has (read from the PNG header); its jarvis.json (apps marked live) is 200,
                                      valid JSON and not older than the limit. A missing manifest or touch icon is a WARN (a home-screen gap, not a broken deploy).
  the workers                         root sw.js le-public-vNN, jarvis/sw.js jarvis-vNN, kalshi/sw.js kalshi-kNN equal the repo's (a stale deploy is caught);
                                      web_next/sw.js (the PC dashboard) is compared only if the site serves it
  the key data files                  data.json, home.json, odeon/trades.json, plutus/plans.json, bridge/jobs.json, kalshicity/*.json: 200 and valid JSON
  the bot heartbeat                   raw.githubusercontent.com/.../heartbeat/heartbeat.json: in market hours (weekday 01:30-16:00 ET) fresh (< 10 min), running and armed
Every request is retried twice with a short backoff; 4 at a time.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                   # pragma: no cover
    ET = timezone.utc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = "https://demetrades2000-coder.github.io/nq-dashboard/"
HEARTBEAT = "https://raw.githubusercontent.com/demetrades2000-coder/nq-liquidity-engine/heartbeat/heartbeat.json"
UA = "olympus-verify-live/1 (read only)"
DATA_FILES = ["data.json", "home.json", "odeon/trades.json", "plutus/plans.json", "bridge/jobs.json", "kalshicity/edges.json", "kalshicity/learning_log.json",
              "kalshicity/hypotheses.json", "kalshicity/learned.json", "kalshicity/jarvis.json"]
WORKERS = [("root worker", "tools/web_public/sw.js", "sw.js", r"CACHE\s*=\s*'(le-public-v\d+)'"),
           ("Jarvis worker", "tools/web_public/jarvis/sw.js", "jarvis/sw.js", r"CACHE\s*=\s*'(jarvis-v\d+)'"),
           ("Kalshi worker", "tools/web_public/kalshi/sw.js", "kalshi/sw.js", r"CACHE\s*=\s*'(kalshi-k\d+)'")]
PC_WORKER = ("PC dashboard worker", "web_next/sw.js", "next/sw.js", r"SHELL\s*=\s*'(le-shell-next-v\d+)'")


class Net:
    """GET with two retries (0.4 s, 1.2 s), a per-run cache, and a polite User-Agent. Returns (status, content_type, body bytes, error text)."""

    def __init__(self, timeout=20.0, sleep=time.sleep):
        self.timeout, self.sleep, self.cache = timeout, sleep, {}

    def get(self, url):
        if url in self.cache:
            return self.cache[url]
        out = (0, "", b"", "no answer")
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    out = (r.status, r.headers.get("Content-Type", ""), r.read(), "")
                break
            except urllib.error.HTTPError as e:
                out = (e.code, e.headers.get("Content-Type", "") if e.headers else "", b"", f"HTTP {e.code}")
                if e.code < 500 and e.code != 429:
                    break                                     # a 404 is an answer, not a hiccup
            except Exception as e:                            # noqa: BLE001 - timeouts, resets, DNS
                out = (0, "", b"", f"{e.__class__.__name__}")
            if attempt < 2:
                self.sleep((0.4, 1.2)[attempt])
        self.cache[url] = out
        return out


def read(*p):
    with open(os.path.join(*p), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def png_size(b):
    return struct.unpack(">II", b[16:24]) if b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR" and len(b) >= 24 else None


def loads(b):
    try:
        return json.loads(b.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None


def apps_list(repo):
    src = read(repo, "tools", "web_public", "olympus", "apps-list.js")
    return json.loads(src[src.index("["):src.rindex("]") + 1])


def tag(html, rx):
    m = re.search(rx, html, re.I)
    return m.group(1) if m else None


# ------------------------------------------------------------------------------------------------ the checks (each returns (result, detail); result PASS | FAIL | WARN)
def check_app(net, base, repo, a, now, max_age_h):
    aid, path, live = a["id"], a.get("path") or "", bool(a.get("live"))
    bad, warn = [], []
    url = urljoin(base, path)
    st, ct, body, err = net.get(url)
    if st != 200:
        return "FAIL", f"page {path or '/'} is {st or err}"
    if "html" not in ct.lower():
        bad.append(f"page content-type {ct or 'none'}")
    html = body.decode("utf-8", "ignore")
    local = os.path.join(repo, "tools", "web_public", path.strip("/"), "index.html") if path else os.path.join(repo, "tools", "web_public", "index.html")
    if os.path.isfile(local):
        mine = read(local)
        d = tag(mine, r'data-app="([a-z0-9_-]+)"')
        if d and f'data-app="{d}"' not in html:
            bad.append(f'data-app="{d}" missing from the live page (stale deploy?)')
        for rx in (r'(olympus/olympus\.css\?v=[\w.]+)', r'(olympus/olympus\.js\?v=[\w.]+)', r'(olympus/themes\.js\?v=[\w.]+)'):
            m = tag(mine, rx)
            if m and m not in html:
                bad.append(f"kit tag {m} missing from the live page (stale deploy?)")
    mhref = tag(html, r'<link[^>]*rel="manifest"[^>]*href="([^"]+)"')
    ahref = tag(html, r'<link[^>]*rel="apple-touch-icon"[^>]*href="([^"]+)"')
    if not mhref:
        warn.append("no manifest (home-screen gap)")
    else:
        murl = urljoin(url, mhref)
        st, ct, mb, err = net.get(murl)
        man = loads(mb) if st == 200 else None
        if st != 200:
            bad.append(f"manifest {st or err}")
        elif not isinstance(man, dict):
            bad.append("manifest is not JSON")
        else:
            if not ("manifest" in ct.lower() or "json" in ct.lower()):
                bad.append(f"manifest content-type {ct or 'none'}")
            for ic in man.get("icons") or []:
                iu = urljoin(murl, ic.get("src", ""))
                s2, c2, ib, e2 = net.get(iu)
                if s2 != 200:
                    bad.append(f"icon {ic.get('src')} {s2 or e2}")
                    continue
                if not c2.lower().startswith("image/"):
                    bad.append(f"icon {ic.get('src')} content-type {c2 or 'none'}")
                if ic.get("type") == "image/png":
                    wh = png_size(ib)
                    if wh is None or "%dx%d" % wh != ic.get("sizes"):
                        bad.append(f"icon {ic.get('src')} is {wh}, manifest says {ic.get('sizes')}")
    if not ahref:
        warn.append("no apple-touch-icon (home-screen gap)")
    else:
        s3, c3, tb, e3 = net.get(urljoin(url, ahref))
        if s3 != 200 or not c3.lower().startswith("image/png") or png_size(tb) != (180, 180):
            bad.append(f"apple-touch-icon {s3 or e3} {c3 or ''} {png_size(tb) if s3 == 200 else ''}".strip())
    if live:
        s4, c4, cb, e4 = net.get(urljoin(url, "jarvis.json"))
        card = loads(cb) if s4 == 200 else None
        if s4 != 200:
            bad.append(f"jarvis.json {s4 or e4}")
        elif not isinstance(card, dict):
            bad.append("jarvis.json is not JSON")
        else:
            t = card.get("t")
            if isinstance(t, (int, float)) and t > 0:
                age_h = (now - t) / 3600.0
                limit = card.get("stale_after")
                limit_h = limit / 3600.0 if isinstance(limit, (int, float)) and limit > 0 else max_age_h
                dt = datetime.fromtimestamp(now, ET)
                weekend = dt.weekday() >= 5 or (dt.weekday() == 0 and dt.hour < 9)
                if weekend and not (isinstance(limit, (int, float)) and limit > 0):
                    limit_h = max(limit_h, 72.0)
                if age_h > limit_h:
                    bad.append(f"jarvis.json card is {age_h:.1f} h old (limit {limit_h:.0f} h{', weekend allowance' if weekend else ''})")
            else:
                warn.append("jarvis.json has no time")
    if bad:
        return "FAIL", "; ".join(bad + warn)
    return ("WARN", "; ".join(warn)) if warn else ("PASS", "page, manifest, icons" + (", card fresh" if live else ""))


def check_worker(net, base, repo, label, rel, live_rel, rx, optional=False):
    f = os.path.join(repo, rel)
    if not os.path.isfile(f):
        return "WARN", f"{rel} is not in this repo checkout"
    mine = tag(read(f), rx)
    st, ct, body, err = net.get(urljoin(base, live_rel))
    if st != 200:
        return ("PASS", "not on the public site (PC dashboard only)") if optional and st == 404 else ("FAIL", f"{live_rel} is {st or err}")
    theirs = tag(body.decode("utf-8", "ignore"), rx)
    if mine is None or theirs is None:
        return "FAIL", f"cannot read the cache name (repo {mine}, live {theirs})"
    return ("PASS", f"live = repo = {theirs}") if mine == theirs else ("FAIL", f"STALE DEPLOY: live {theirs}, repo {mine}")


def check_data(net, base, rel):
    st, ct, body, err = net.get(urljoin(base, rel))
    if st != 200:
        return "FAIL", f"{st or err}"
    j = loads(body)
    if j is None:
        return "FAIL", "not valid JSON"
    return "PASS", f"{len(body) // 1024 or 1} KB, {'object' if isinstance(j, dict) else 'list'} of {len(j)}"


def market_hours(now):
    d = datetime.fromtimestamp(now, ET)
    return d.weekday() < 5 and (d.hour, d.minute) >= (1, 30) and d.hour < 16


def local_heartbeat(repo):
    """The heartbeat branch of the local clone (read only; fetch that branch first for a fresh one), or None."""
    try:
        r = subprocess.run(["git", "-C", repo, "show", "origin/heartbeat:heartbeat.json"], capture_output=True, timeout=20)
        return r.stdout if r.returncode == 0 and r.stdout else None
    except (OSError, subprocess.SubprocessError):
        return None


def check_heartbeat(net, url, now, max_min, repo=None):
    st, ct, body, err = net.get(url)
    note = ""
    if st != 200 and repo:                                   # a private repo has no public raw address: the local clone's heartbeat branch is the fallback
        lb = local_heartbeat(repo)
        if lb:
            st, body, note = 200, lb, f" [raw address answered {err or st}: read from the local clone's origin/heartbeat, fetch it first]"
    if st != 200:
        return "FAIL", f"heartbeat {st or err} (the repo may be private: use --hb-url, or fetch the heartbeat branch into the clone)"
    hb = loads(body)
    if not isinstance(hb, dict) or not isinstance(hb.get("t"), (int, float)):
        return "FAIL", "heartbeat is not the expected JSON"
    age = (now - hb["t"]) / 60.0
    h = hb.get("health") if isinstance(hb.get("health"), dict) else {}
    acct = h.get("account") if isinstance(h.get("account"), dict) else {}
    lf = (hb.get("launch") or {}).get("facts") if isinstance(hb.get("launch"), dict) else None
    armed = acct.get("armed") if "armed" in acct else (lf or {}).get("lit_armed")
    running, kill = hb.get("running"), bool(hb.get("kill") or h.get("kill"))
    word = f"{age:.0f} min old, running={running}, armed={armed}{note}"
    if market_hours(now):
        if age > max_min:
            return "FAIL", f"{word}: older than {max_min} min in market hours (the PC bot is silent)"
        if running is not True or armed is not True or kill:
            return "FAIL", f"{word}, kill={kill}: must be running and armed in market hours"
        return "PASS", word
    return "PASS", word + " (outside market hours: freshness not required)"


# ------------------------------------------------------------------------------------------------ the run
def run(base, repo=ROOT, hb_url=HEARTBEAT, heartbeat=True, max_age_h=30.0, hb_age_min=10.0, workers=4, now=None, net=None):
    """-> (rows [(check, result, detail)], verdict 'VERIFIED' | 'PROBLEMS')."""
    now = time.time() if now is None else now
    base = base if base.endswith("/") else base + "/"
    net = net or Net()
    apps = apps_list(repo)
    jobs = [(f"app {a['id']}", lambda a=a: check_app(net, base, repo, a, now, max_age_h)) for a in apps]
    jobs += [(label, lambda r=(label, rel, lr, rx): check_worker(net, base, repo, *r)) for label, rel, lr, rx in WORKERS]
    jobs.append((PC_WORKER[0], lambda: check_worker(net, base, repo, *PC_WORKER, optional=True)))
    jobs += [(f"data {rel}", lambda rel=rel: check_data(net, base, rel)) for rel in DATA_FILES]
    if heartbeat:
        jobs.append(("bot heartbeat", lambda: check_heartbeat(net, hb_url, now, hb_age_min, repo)))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [(name, ex.submit(fn)) for name, fn in jobs]
        rows = []
        for name, f in futs:
            try:
                res, detail = f.result()
            except Exception as e:                           # noqa: BLE001 - one broken check never hides the others
                res, detail = "FAIL", f"check crashed: {e.__class__.__name__}"
            rows.append((name, res, detail))
    return rows, ("PROBLEMS" if any(r[1] == "FAIL" for r in rows) else "VERIFIED")


def render(rows, verdict, base, now):
    when = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fails, warns = sum(r[1] == "FAIL" for r in rows), sum(r[1] == "WARN" for r in rows)
    out = [f"verify_live {when} · {base}", "", "| check | result | detail |", "|---|---|---|"]
    out += [f"| {n} | {r} | {d.replace('|', '/')} |" for n, r, d in rows]
    out += ["", f"{verdict}: {len(rows)} checks, {fails} problem{'s' if fails != 1 else ''}, {warns} warning{'s' if warns != 1 else ''}"
            + (" (warnings are home-screen gaps or notes, not a broken deploy)" if warns else "")]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the LIVE site after a publish (read only).")
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--repo", default=ROOT)
    ap.add_argument("--hb-url", default=HEARTBEAT)
    ap.add_argument("--no-heartbeat", action="store_true")
    ap.add_argument("--max-age-h", type=float, default=30.0)
    ap.add_argument("--hb-age-min", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None, help="report file (default research/handoff/<today UTC>/verify_live.md)")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    now = time.time()
    rows, verdict = run(a.base, a.repo, a.hb_url, not a.no_heartbeat, a.max_age_h, a.hb_age_min, a.workers, now)
    text = render(rows, verdict, a.base, now)
    print(text)
    if not a.no_write:
        out = a.out or os.path.join(a.repo, "research", "handoff", datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d"), "verify_live.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
