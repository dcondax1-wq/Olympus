"""OF BACKFILL, the cloud half (night-of-backfill 2026-11-27): ask the PC for every order-flow summary day the cloud does not hold
yet, collect the pages, verify them, keep them for good. PC half + the quota math: engine/ofbackfill.py.

    python tools/of_backfill.py                 # restore the store, ask ("bf" + what we hold), wait up to 25 min, save the store
    python tools/of_backfill.py --wait 0        # only ask (a later run collects: the ask is remembered for 3 h)
    python tools/of_backfill.py --push          # ... and commit the store to branch `of-store` (tools/learn_night step 'backfill')
    python tools/of_backfill.py --status        # what we hold, what the PC said it holds, the last pages
    python tools/of_backfill.py --restore-only  # only unpack branch `of-store` into data/pc_days (any session, before research)

Why a store: data/pc_days/ is gitignored and every cloud session starts empty, so the year would have to cross ntfy again each
time. The store = one engine/ofpack file a month (data/of_store/<YYYY-MM>.ofp, ~2 MB a month, lossless, sha256 per file) on its
own data branch `of-store` of this repo (never pc / main: no code there, the PC never pulls it). The PC never pushes anything
(it has no push sign-in; engine/datafeed's notes): only this cloud side commits, with the session's own git access.
A page is accepted only when: it answers OUR ask id, the PC signed its meta (engine/datafeed.parse_answer, pinned key), the
download has the announced size + sha256, every file inside has its own sha256 (engine/ofpack), every path is a known order-flow
day file (engine/datafeed.DAY_FILE via datafeed.extract). Research data only: never trades, never touches a live file.
Tests: python -X utf8 -m tests.test_of_backfill (fake ntfy + a fake git remote, no network).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "data", "pc_days")              # gitignored (tools/data_pull.OUT)
STORE = os.path.join(ROOT, "data", "of_store")           # gitignored; its copy lives on branch BRANCH
BRANCH = "of-store"
TIP = "refs/ofstore/tip"                                 # our local copy of the branch tip (any remote name / path)
MARK = "_bf_ask.json"
ASK_TTL_S = 3 * 3600                                      # an ask is reused this long (its pages are kept 3 h on ntfy)
WAIT_MIN = 25.0
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def say(msg: str) -> None:
    print(msg, flush=True)


def of_days(out_dir: str = OUT) -> list:
    try:
        return sorted(d for d in os.listdir(out_dir) if _DAY.match(d) and os.path.exists(os.path.join(out_dir, d, "of", "NQ_meta.json")))
    except OSError:
        return []


# ------------------------------------------------------------------------------------------------ one page -> data/pc_days
def extract_bf(blob: bytes, out_dir: str) -> list:
    """An "ofp1" page -> out_dir/<day>/of/* via engine/datafeed.extract (its name / manifest / size rules). Each day's
    of/manifest.json is rewritten with the sha256 of the files as written (the content itself was checked by engine/ofpack).
    -> [(day, partial)]. Raises ValueError (nothing written) on any bad file."""
    from engine import datafeed as DF, ofpack
    files = ofpack.unpack(blob)
    days = {}
    for p in files:
        m = DF.DAY_FILE.match(p)
        if not m or not m.group(2).startswith("of/"):
            raise ValueError(f"unexpected file in the page: {p[:80]}")
        days.setdefault(m.group(1), []).append(p)
    import hashlib
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for d, ps in sorted(days.items()):
            mp = f"days/{d}/of/manifest.json"
            if mp not in files:
                raise ValueError(f"{d}: no manifest in the page")
            try:
                man = json.loads(files[mp].decode("utf-8"))
            except ValueError:
                raise ValueError(f"{d}: the manifest is not JSON") from None
            if not isinstance(man, dict) or man.get("day") != d:
                raise ValueError(f"{d}: the manifest names another day")
            man["files"] = {p.split("/", 2)[2]: {"bytes": len(files[p]), "sha256": hashlib.sha256(files[p]).hexdigest()}
                            for p in ps if p != mp}
            man["via"] = "bf"
            for p in sorted(ps):
                z.writestr(p, json.dumps(man, indent=1, sort_keys=True).encode("utf-8") if p == mp else files[p])
    return DF.extract(buf.getvalue(), out_dir)


# ------------------------------------------------------------------------------------------------ the store (branch of-store)
def _git(args, cwd=ROOT, env=None, inp=None, timeout=300):
    r = subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **(env or {})}, input=inp, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def save(out_dir: str = OUT, store: str = STORE) -> list:
    """Pack every order-flow day of out_dir into store/<YYYY-MM>.ofp (only months whose days changed). -> months written."""
    from engine import ofpack
    os.makedirs(store, exist_ok=True)
    idx_p = os.path.join(store, "index.json")
    try:
        idx = json.load(open(idx_p, encoding="utf-8"))
    except (OSError, ValueError):
        idx = {}
    months = {}
    for d in of_days(out_dir):
        months.setdefault(d[:7], []).append(d)
    wrote = []
    for mo, ds in sorted(months.items()):
        files = {}
        for d in ds:
            base = os.path.join(out_dir, d, "of")
            for f in sorted(os.listdir(base)):
                if f.endswith((".csv.gz", ".json", ".json.gz")):
                    files[f"days/{d}/of/{f}"] = open(os.path.join(base, f), "rb").read()
            mp = f"days/{d}/of/manifest.json"
            if mp not in files:                                  # a day pulled the old way may have none: one is made here
                files[mp] = json.dumps({"v": 1, "day": d, "kind": "of", "partial": False, "via": "store"}, sort_keys=True).encode()
        import hashlib
        sig = hashlib.sha256(json.dumps({p: hashlib.sha256(b).hexdigest() for p, b in files.items() if not p.endswith("manifest.json")},
                                        sort_keys=True).encode()).hexdigest()
        if (idx.get(mo) or {}).get("sig") == sig and os.path.exists(os.path.join(store, f"{mo}.ofp")):
            continue
        blob = ofpack.pack(files)
        with open(os.path.join(store, f"{mo}.ofp.tmp"), "wb") as fh:
            fh.write(blob)
        os.replace(os.path.join(store, f"{mo}.ofp.tmp"), os.path.join(store, f"{mo}.ofp"))
        idx[mo] = {"sig": sig, "days": len(ds), "first": ds[0], "last": ds[-1], "bytes": len(blob)}
        wrote.append(mo)
    idx["_total"] = {"days": sum(v["days"] for k, v in idx.items() if not k.startswith("_")), "t": int(time.time())}
    json.dump(idx, open(idx_p, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return wrote


def restore(out_dir: str = OUT, store: str = STORE, remote: str = "origin", repo: str = ROOT) -> int:
    """git fetch <remote> of-store -> store/ (its files) -> unpack the days out_dir lacks. -> days written. Never raises."""
    n = 0
    try:
        c, _o, _e = _git(["fetch", "-q", "--depth", "1", remote, f"+refs/heads/{BRANCH}:{TIP}"], cwd=repo)
        if c == 0:
            c, o, _e = _git(["ls-tree", "--name-only", TIP], cwd=repo)
            os.makedirs(store, exist_ok=True)
            for name in o.decode().split():
                if re.fullmatch(r"\d{4}-\d{2}\.ofp|index\.json", name):
                    c2, b, _e2 = _git(["show", f"{TIP}:{name}"], cwd=repo)
                    if c2 == 0:
                        with open(os.path.join(store, name), "wb") as fh:
                            fh.write(b)
    except Exception:  # noqa: BLE001
        pass
    have = set(of_days(out_dir))
    try:
        names = sorted(f for f in os.listdir(store) if f.endswith(".ofp"))
    except OSError:
        names = []
    for f in names:
        try:
            blob = open(os.path.join(store, f), "rb").read()
            from engine import ofpack
            days = {p.split("/")[1] for p in ofpack.unpack(blob)}
            if days - have:
                n += len([d for d, _p in extract_bf(blob, out_dir) if d not in have])
        except (OSError, ValueError) as e:
            say(f"  store file {f} not usable: {e}")
    return n


def push(store: str = STORE, remote: str = "origin", repo: str = ROOT, tries: int = 4, sleep=None) -> tuple:
    """Commit store/*.ofp + index.json as the next commit of branch of-store and push it (a temp index: the work tree and the
    current branch are never touched). -> (ok, why)."""
    sleep = sleep or time.sleep
    try:
        files = sorted(f for f in os.listdir(store) if f.endswith(".ofp") or f == "index.json")
    except OSError:
        files = []
    if not files:
        return False, "the store is empty"
    with tempfile.TemporaryDirectory() as td:
        env = {"GIT_INDEX_FILE": os.path.join(td, "index"), "GIT_AUTHOR_NAME": "Claude", "GIT_AUTHOR_EMAIL": "noreply@anthropic.com",
               "GIT_COMMITTER_NAME": "Claude", "GIT_COMMITTER_EMAIL": "noreply@anthropic.com"}
        _git(["fetch", "-q", "--depth", "1", remote, f"+refs/heads/{BRANCH}:{TIP}"], cwd=repo)
        c, parent, _e = _git(["rev-parse", "-q", "--verify", f"{TIP}^{{commit}}"], cwd=repo)
        parent = parent.decode().strip() if c == 0 else ""
        for f in files:
            c, h, e = _git(["hash-object", "-w", os.path.join(store, f)], cwd=repo)
            if c:
                return False, f"hash-object: {e.decode()[:120]}"
            c, _o, e = _git(["update-index", "--add", "--cacheinfo", f"100644,{h.decode().strip()},{f}"], cwd=repo, env=env)
            if c:
                return False, f"update-index: {e.decode()[:120]}"
        c, tree, e = _git(["write-tree"], cwd=repo, env=env)
        if c:
            return False, f"write-tree: {e.decode()[:120]}"
        tree = tree.decode().strip()
        if parent:
            c, ptree, _e = _git(["rev-parse", f"{parent}^{{tree}}"], cwd=repo)
            if c == 0 and ptree.decode().strip() == tree:
                return True, "unchanged"
        try:
            idx = json.load(open(os.path.join(store, "index.json"), encoding="utf-8"))
            tot = (idx.get("_total") or {}).get("days")
        except (OSError, ValueError):
            tot = "?"
        msg = f"of-store: {tot} order-flow summary days (tools/of_backfill.py)\n".encode()
        c, commit, e = _git(["commit-tree", tree, *(["-p", parent] if parent else [])], cwd=repo, env=env, inp=msg)
        if c:
            return False, f"commit-tree: {e.decode()[:120]}"
        commit = commit.decode().strip()
        why = ""
        for k in range(tries):
            c, _o, e = _git(["push", "-q", remote, f"{commit}:refs/heads/{BRANCH}"], cwd=repo)
            if c == 0:
                return True, commit[:9]
            why = e.decode()[:160]
            sleep(2 ** (k + 1))
        return False, f"push failed: {why}"


# ------------------------------------------------------------------------------------------------ ask + collect
def _mark(out_dir):
    try:
        return json.load(open(os.path.join(out_dir, MARK), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ask_and_collect(out_dir: str = OUT, wait_min: float = WAIT_MIN, pages: int = 12, sleep=None, now_fn=None) -> dict:
    """Post ONE "bf" ask (or reuse the one out < 3 h), collect its pages as they come, extract each. -> summary dict."""
    from engine import datafeed as DF, ofbackfill as BF
    sleep = sleep or time.sleep
    now_fn = now_fn or time.time
    os.makedirs(out_dir, exist_ok=True)
    have = of_days(out_dir)
    mk = _mark(out_dir)
    res = {"before": len(have), "pages": 0, "got": [], "pc": None, "held": None, "rid": None}
    if mk.get("rid") and now_fn() - float(mk.get("t") or 0) < ASK_TTL_S:
        rid, t0 = mk["rid"], int(mk["t"])
        say(f"The backfill ask {rid} is still out ({int((now_fn() - t0) // 60)} min old): collecting its pages.")
    else:
        rid, t0 = "bf" + secrets.token_hex(4), int(now_fn())
        since = (dt.date.today() - dt.timedelta(days=DF.DAYS_BACK_OF - 5)).isoformat()
        extra = {**BF.have_bitmap(have), "pages": int(pages)}
        ok, why = DF.post_request(rid, since, t0, what="bf", extra=extra)
        if not ok:
            res["held"] = f"could not ask the PC: {why}"
            say(res["held"])
            return res
        json.dump({"rid": rid, "t": t0, "have": len(have)}, open(os.path.join(out_dir, MARK), "w", encoding="utf-8"))
        say(f"Asked the PC for every order-flow day we do not hold ({len(have)} here; request {rid}).")
    res["rid"] = rid
    base, topic = DF.feed_cfg()
    seen = set(mk.get("seen") or []) if mk.get("rid") == rid else set()
    end = now_fn() + 60.0 * wait_min
    while True:
        ok, msgs = DF.poll(base, topic, int(t0 - 60))
        now = int(now_fn())
        done = False
        for m in msgs if ok else []:
            x = DF.parse_answer(m, now, base)
            if not x or x.get("what") != "bf" or not (x.get("req") == rid or rid in (x.get("also") or [])):
                continue
            if x.get("mid") in seen:
                continue
            seen.add(x.get("mid"))
            res["pc"] = x.get("pc") or res["pc"]
            if x.get("days"):
                try:
                    from tools.data_pull import fetch_bundle
                    wrote = extract_bf(fetch_bundle(x), out_dir)
                    res["pages"] += 1
                    res["got"] += [d for d, _p in wrote]
                    say(f"  page {x.get('page')}: {len(wrote)} days {x.get('from')} .. {x.get('to')} ({int(x.get('bytes') or 0):,} B, "
                        f"x{x.get('ratio')} of gzip; messages free after it ~{x.get('left')})")
                except ValueError as e:
                    say(f"  page {x.get('page')} not usable: {e}")
            if x.get("held"):
                res["held"] = x["held"]
            if not x.get("more") or x.get("more_tomorrow") or (not x.get("days") and x.get("held")):
                done = True
                res["more"] = bool(x.get("more"))
        try:
            mk = {"rid": rid, "t": t0, "seen": sorted(s for s in seen if s)[-300:]}
            json.dump(mk, open(os.path.join(out_dir, MARK), "w", encoding="utf-8"))
        except OSError:
            pass
        if done or now_fn() >= end or wait_min <= 0:
            break
        sleep(20)
    res["after"] = len(of_days(out_dir))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backfill the PC's order-flow summary year into the cloud (engine/ofbackfill.py)")
    ap.add_argument("--wait", type=float, default=WAIT_MIN, help="minutes to wait for the pages (0 = only ask)")
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--push", action="store_true", help="commit the store to branch of-store")
    ap.add_argument("--restore-only", action="store_true")
    ap.add_argument("--no-restore", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--store", default=STORE)
    a = ap.parse_args(argv)
    if a.status:
        ds = of_days(a.out)
        say(json.dumps({"days_here": len(ds), "first": ds[0] if ds else None, "last": ds[-1] if ds else None,
                        "ask": {k: v for k, v in _mark(a.out).items() if k != "seen"}}, indent=1))
        return 0
    if not a.no_restore:
        n = restore(a.out, a.store)
        say(f"store: {n} day(s) restored from branch {BRANCH}; {len(of_days(a.out))} order-flow days here")
    if a.restore_only:
        return 0
    r = ask_and_collect(a.out, a.wait, a.pages)
    wrote = save(a.out, a.store) if r["got"] else []
    pc = r.get("pc") or {}
    say(f"backfill: {r['before']} -> {r.get('after', r['before'])} days here (+{len(set(r['got']))} in {r['pages']} page(s)); "
        f"the PC holds {pc.get('of_days', '?')} summary days (oldest {pc.get('of_oldest', '?')}), "
        f"{pc.get('tick_days', '?')} tick days (oldest {pc.get('tick_oldest', '?')})"
        + (f"; held: {r['held']}" if r.get("held") else "") + ("; more next run" if r.get("more") else ""))
    if a.push and (wrote or r["got"]):
        ok, why = push(a.store)
        say(f"store branch {BRANCH}: {'pushed ' + why if ok else why}")
    return 0 if r["got"] or not (r.get("held") or "").startswith("could not") else 1


if __name__ == "__main__":
    sys.exit(main())
