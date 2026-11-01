"""Kalshi in Jarvis (owner 2026-11-01: "where is kalshi ... figure out a way to have it there").

The owner's Kalshi bot ("Kalshi Edge v2") runs 24/7 on an Oracle Cloud VM (/home/ubuntu/kalshi), with real money. Its
numbers reach the phone as kalshi.json: one orphan commit force-pushed to the branch `kalshi` of the public Pages repo
nq-dashboard. The phone's Kalshi page (tools/web_public/kalshi/, <site>/kalshi/) and the Jarvis Kalshi card read it from
raw.githubusercontent.com. docs/KALSHI_PUBLISH.md has the whole picture.

THE way: the VM publishes by itself (cron every minute, its own deploy key), set up by the bot's own Claude chat
("kalshi-server") from tools/kalshi_kit/public/SETUP.md. This module is the PC side, same contract:
  --ssh        (= --from-vm) the FALLBACK: runs the read-only builder on the VM through the PC's own srv.py helper (the
               VM's address stays in srv.py, read by it at run time; nothing is installed on the VM), then pushes from
               the PC by the same route and git login as the NQ bot's live.json (engine/live_publish: target repo, orphan
               commit, the repo's credential settings), from its own scratch git dir (data/kalshi_pub.git, gitignored).
  --src FILE   a status file (v1 keys, plus the optional v2 `strategies` and `equity`).
  --from-bot DIR / --from-api   also accepted (--from-api is NOT recommended: the account already meets Kalshi's limits).
The contract, the readers, the API client and the money math live in ONE file: tools/kalshi_kit/public/kalshi_status_vm.py
(stdlib only; public copy <site>/kalshi/kalshi_status_vm.py). This module loads that file, so both give the same
kalshi.json for the same input; only the push differs.

Read-only and separate from the NQ bot: it never places anything and never runs inside the NQ bot's server.

    python -m engine.kalshi_publish --sample                       a sample status file (the contract, v2)
    python -m engine.kalshi_publish --ssh --check                  what the VM's files would publish (no push)
    python -m engine.kalshi_publish --ssh --once | --loop          push once / every 60 s when it changed (else 10 min)
    python -m engine.kalshi_publish --src <file> --check|--once|--loop   the same from a status file
--vm-helper <srv.py> when it isn't found under %APPDATA%\\Claude\\scratch-workspaces; LE_KALSHI_SRC sets the default
--src; LE_LIVE_REPO overrides the target repo.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

from . import live_publish as lp

ROOT = lp.ROOT
KIT_PATH = os.path.join(ROOT, "tools", "kalshi_kit", "public", "kalshi_status_vm.py")


def _load_kit():
    name = "kalshi_to_jarvis_kit"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, KIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True     # no __pycache__ in the public kit folder
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


kit = _load_kit()

BRANCH = kit.BRANCH
FILE = kit.FILE
SCRATCH = os.path.join(ROOT, "data", "kalshi_pub.git")      # gitignored scratch git dir (objects pruned)
MAX_BYTES = kit.MAX_BYTES
EVERY_S = kit.EVERY_S
KEEPALIVE_S = kit.KEEPALIVE_S
TOP, NUM, POS, TRADE, STRAT, CAPS = kit.TOP, kit.NUM, kit.POS, kit.TRADE, kit.STRAT, kit.CAPS
SAMPLE, SAMPLE_V2 = kit.SAMPLE, kit.SAMPLE_V2
ReadOnlyError, ApiError = kit.ReadOnlyError, kit.ApiError


def _push(p: dict, url: str | None, **kw) -> dict:
    """The kit's push: one orphan commit force-pushed like engine/live_publish.push, with the repo's own git login (its
    local credential settings are copied into the scratch dir, as live_publish does) and no console window under pythonw
    (the Task Scheduler fallback)."""
    return kit.push(p, url, copy_config_from=ROOT, **kw)


def clean(raw: dict, now: float | None = None, phrases=()) -> dict:
    """The status -> kalshi.json: only the contract's keys (v1, plus v2 `strategies` / `equity` when given), numbers as
    numbers, lists capped, secrets dropped, paths redacted. Never raises on junk."""
    return kit.clean(raw, now, phrases)


def read(src: str, now: float | None = None) -> tuple[dict | None, str | None]:
    """(kalshi.json payload, error). The status file's own "t" is when the Kalshi bot wrote it (else the file's time)."""
    return kit.read(src, now, max_bytes=MAX_BYTES)


def push_once(src: str, url: str | None = None, git_dir: str = SCRATCH, push_fn=None, now: float | None = None) -> dict:
    """Read the status file and push it as kalshi.json to the branch `kalshi`. {"ok", "error"|"commit", "bytes"}."""
    p, err = read(src, now)
    if err:
        return {"ok": False, "error": err}
    url = url or lp.target_url()
    return (push_fn or _push)(p, url, branch=BRANCH, git_dir=git_dir, prune=True, file=FILE)


def loop(src: str, every: float = EVERY_S, keepalive: float = KEEPALIVE_S, log=print, clock=time.time, sleep=time.sleep,
         push_fn=None, url: str | None = None, git_dir: str = SCRATCH, max_rounds: int | None = None) -> None:
    """Push when the status file changed (checked every `every` s), and at least every `keepalive` s."""
    last_sig, last_t, n = None, 0.0, 0
    while max_rounds is None or n < max_rounds:
        n += 1
        try:
            st = os.stat(src)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        now = clock()
        if sig is not None and (sig != last_sig or now - last_t >= keepalive):
            r = push_once(src, url=url, git_dir=git_dir, push_fn=push_fn, now=now)
            log(f"kalshi publish: {'ok ' + str(r.get('commit')) if r.get('ok') else 'FAILED ' + lp._redact(str(r.get('error')))}")
            if r.get("ok"):
                last_sig, last_t = sig, now
        elif sig is None:
            log("kalshi publish: waiting for the status file")
        sleep(every)


# ---------------------------------------------------------------------------------------------------- the Kalshi account
def api_payload(client, now: float | None = None, cache: dict | None = None, name: str = "Kalshi bot") -> dict:
    """The account, read-only (GET balance / positions / fills / settlements / markets) -> the kalshi.json payload."""
    return kit.api_payload(client, now=now, cache=cache, name=name, max_bytes=MAX_BYTES)


def push_payload(p: dict, url: str | None = None, git_dir: str = SCRATCH, prune: bool = True, push_fn=None) -> dict:
    url = url or lp.target_url()
    return (push_fn or _push)(p, url, branch=BRANCH, git_dir=git_dir, prune=prune, file=FILE)


def main(argv=None) -> int:
    """The kit's command line (same flags), pushing to the target of live.json (lp.target_url) from data/kalshi_pub.git."""
    a, _ = kit.parser(prog="python -m engine.kalshi_publish").parse_known_args(argv)
    url = a.repo or lp.target_url()
    git_dir = a.git_dir or SCRATCH

    def push_fn(p, prune=False):
        return push_payload(p, url, git_dir=git_dir, prune=prune)

    return kit.main(argv, push_fn=push_fn, prog="python -m engine.kalshi_publish",
                    defaults={"src": os.environ.get("LE_KALSHI_SRC"), "git_dir": git_dir, "repo": url})


if __name__ == "__main__":
    sys.exit(main())
