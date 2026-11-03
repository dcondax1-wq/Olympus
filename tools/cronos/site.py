"""CRONOS in the site build (tools/build_web_dashboard.py, every publish): fresh research data in, honest cards out.

  1. pull   the `cronos` branch (fates/, odeon/, tree/, prometheus/, cronos/status.json) and the `datacity` branch (city.json,
            jarvis.json) into the site, app by app, all of an app's files or none, and only when the branch's card is newer
            than the page's own copy (tools/web_public/<app>/). Branches are read with git (fetch --depth 1 + show); in
            GitHub Actions the build fetches them (the checkout's GITHUB_TOKEN, contents: read is enough), elsewhere only
            with CRONOS_FETCH=1. CRONOS_DIR=<folder> reads a local copy laid out like the branches (<dir>/cronos/...,
            <dir>/datacity/...). A missing branch or file is skipped.
  2. stamp  every research app's jarvis.json (registry.STAMPED) gets t = this publish and its freshness (tools/cronos/fresh.py).
Never raises into the build (the caller wraps it too); returns a short summary per app.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

from tools.cronos import fresh, registry

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRANCHES = ("cronos", "datacity")


def want_fetch() -> bool:
    v = os.environ.get("CRONOS_FETCH")
    if v in ("0", "1"):
        return v == "1"
    return os.environ.get("GITHUB_ACTIONS") == "true"


def git_reader(branch: str, fetch: bool = True, root: str = ROOT):
    """path -> bytes | None for origin/<branch> (fetched first when fetch); None when the branch cannot be read."""
    ref = f"refs/remotes/origin/{branch}"
    try:
        if fetch:
            subprocess.run(["git", "-C", root, "fetch", "-q", "--depth", "1", "origin", f"+refs/heads/{branch}:{ref}"],
                           capture_output=True, timeout=60)
        ok = subprocess.run(["git", "-C", root, "rev-parse", "--verify", "-q", ref], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if ok.returncode != 0:
        return None

    def read(path):
        try:
            p = subprocess.run(["git", "-C", root, "show", f"{ref}:{path}"], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return p.stdout if p.returncode == 0 and p.stdout else None
    return read


def dir_reader(folder: str):
    """path -> bytes | None from a local folder laid out like the branch (tests, local previews)."""
    if not folder or not os.path.isdir(folder):
        return None

    def read(path):
        full = os.path.join(folder, *path.split("/"))
        try:
            with open(full, "rb") as fh:
                return fh.read()
        except OSError:
            return None
    return read


def default_readers() -> dict:
    d = os.environ.get("CRONOS_DIR")
    if d:
        return {b: dir_reader(os.path.join(d, b)) for b in BRANCHES}
    if not want_fetch():
        return {}
    return {b: git_reader(b) for b in BRANCHES}


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def pull(out: str, readers: dict, log=print) -> tuple:
    """Copy each app's branch files into the site when newer. Returns ({app: note}, status or None)."""
    notes, status = {}, None
    rd = readers.get("cronos")
    if rd:
        status = _json(rd("cronos/status.json") or b"")
        status = status if isinstance(status, dict) and isinstance(status.get("tasks"), dict) else None
    for task in registry.TASKS:
        if task.runner == "build":
            continue
        rd = readers.get(task.branch)
        if not rd:
            notes[task.name] = "no branch"
            continue
        pairs = registry.site_files(task)
        blobs = {}
        for src, dst in pairs:
            raw = rd(src)
            if raw is None or _json(raw) is None:
                blobs = None
                break
            blobs[dst] = raw
        if not blobs:
            notes[task.name] = "not on the branch"
            continue
        card_dst = next(dst for _, dst in pairs if dst.endswith("jarvis.json"))
        new_t = fresh.data_time(_json(blobs[card_dst])) or 0
        old_t = fresh.data_time(_load(os.path.join(out, *card_dst.split("/")))) or 0
        if new_t <= old_t:
            notes[task.name] = "page copy is as new"
            continue
        for dst, raw in blobs.items():
            path = os.path.join(out, *dst.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(raw)
        notes[task.name] = f"pulled from {task.branch} ({fresh.when(new_t)})"
    if status is not None:
        os.makedirs(os.path.join(out, "cronos"), exist_ok=True)
        with open(os.path.join(out, "cronos", "status.json"), "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in status.items() if not k.startswith("_")}, fh, separators=(",", ":"))
    return notes, status


def stamp_all(out: str, status: dict | None, now: float) -> dict:
    """Stamp every research app's card in the site; {app: state}."""
    tasks = (status or {}).get("tasks") or {}
    states = {}
    for name in registry.STAMPED:
        task = registry.get(name)
        path = os.path.join(out, task.app, "jarvis.json")
        card = _load(path)
        if not isinstance(card, dict):
            continue
        v = fresh.verdict(task, fresh.data_time(card), tasks.get(name), now)
        new = fresh.stamp(card, task, v, now)
        if fresh.valid_card(new):
            continue                      # never publish a card Jarvis would reject: the engine's card stays
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(new, fh, ensure_ascii=False, separators=(",", ":"))
        states[name] = v["state"]
    return states


def apply(out: str, now: float | None = None, readers: dict | None = None, log=print) -> dict:
    now = time.time() if now is None else now
    readers = default_readers() if readers is None else readers
    readers = {k: v for k, v in readers.items() if v}
    notes, status = pull(out, readers, log)
    states = stamp_all(out, status, now)
    res = {name: f"{states.get(name, 'not stamped')}; {notes.get(name, '-')}" for name in registry.STAMPED}
    log("  cronos: " + "; ".join(f"{k} {v}" for k, v in res.items()))
    return res
