"""CRONOS orchestrator: run the registry's tasks, each in a subprocess with its own timeout; a failure is recorded, never raised.

Every task writes into <out>/.cronos_tmp/<app>/ first; only when its files are there, parse as JSON and its jarvis.json
passes the Jarvis contract are they moved into <out>/<app>/ (a failed or killed run keeps the last good outputs).
<out>/cronos/status.json keeps one entry per task:
  {ok (true / false; unchanged on a saver-mode skip), ran (outputs rebuilt), last_run_t, last_ok_t (last success, also a
   "nothing new" check), data_t (last rebuild), seconds, note, error (short), inputs (what the skip test compares)}
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

from tools.cronos import fresh, registry

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB = os.path.join(ROOT, "tools", "web_public")
DEFAULT_OUT = os.path.join(ROOT, "research", "cronos", "out")
SITE_DATA_URL = "https://demetrades2000-coder.github.io/nq-dashboard/data.json"   # the public site's data.json (paper ledger)
LOG_TAIL = 40


class TaskError(Exception):
    pass


# ------------------------------------------------------------------------------------------------------------ helpers
def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_json(path, obj, compact=True):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 1)
    os.replace(tmp, path)


def sub(cmd, timeout, log):
    """Run cmd from the repo root with a hard timeout; its output goes to log. Raises TaskError on a non-zero exit."""
    env = dict(os.environ, PYTHONUTF8="1", MPLBACKEND="Agg")
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        log.extend(out.splitlines())
        raise TaskError(f"timed out after {timeout // 60} min") from None
    log.extend(p.stdout.decode("utf-8", "replace").splitlines())
    if p.returncode != 0:
        last = next((x for x in reversed(log) if x.strip()), "")
        raise TaskError(f"exit {p.returncode}: {last}"[:200])


def git_file(branch, path):
    """bytes of <path> on origin/<branch> (fetched by the workflow), or None."""
    try:
        p = subprocess.run(["git", "-C", ROOT, "show", f"refs/remotes/origin/{branch}:{path}"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 and p.stdout else None


def fingerprint(paths) -> str:
    """sha1 over the inputs (a folder = its .py files): the same inputs give the same print."""
    h = hashlib.sha1()
    for rel in paths:
        full = os.path.join(ROOT, rel)
        files = []
        if os.path.isdir(full):
            for d, _, names in os.walk(full):
                files += [os.path.join(d, n) for n in names if n.endswith(".py")]
        else:
            files = [full]
        for f in sorted(files):
            h.update(os.path.relpath(f, ROOT).replace("\\", "/").encode())
            try:
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                h.update(b"missing")
    return h.hexdigest()[:16]


def has_outputs(task, out) -> bool:
    return all(os.path.exists(os.path.join(out, task.app, f)) for f in task.files)


def check_outputs(task, tmp) -> None:
    for f in task.files:
        p = os.path.join(tmp, f)
        if not os.path.exists(p):
            raise TaskError(f"{task.app}/{f} was not written")
        obj = load_json(p)
        if obj is None:
            raise TaskError(f"{task.app}/{f} is not valid JSON")
        if f == "jarvis.json":
            bad = fresh.valid_card(obj)
            if bad:
                raise TaskError(f"{task.app}/jarvis.json breaks the Jarvis contract: {', '.join(bad)}")


def copy_page_files(task, tmp, since):
    """The engines that only write next to their page (tools/web_public/<app>/): copy their fresh files into tmp."""
    for f in task.files:
        src = os.path.join(WEB, task.app, f)
        if not os.path.exists(src) or os.path.getmtime(src) < since - 2:
            raise TaskError(f"tools/web_public/{task.app}/{f} was not rewritten by this run")
        shutil.copy(src, os.path.join(tmp, f))


# ------------------------------------------------------------------------------------------------------------ runners
def py(*args):
    return [sys.executable, "-X", "utf8", *args]


def run_fates(task, tmp, ctx):
    sub(py("-m", "tools.fates.build", "--out", tmp), task.timeout_s, ctx["log"])
    return {"ran": True, "note": "1,000 futures from the latest live.json state"}


def heartbeat_bars(ctx):
    """The PC's NinjaTrader 1m bars from the heartbeat branch -> (csv path, newest bar time) or (None, None)."""
    raw = ctx.get("bars_gz")
    if raw is None:
        raw = git_file("heartbeat", "bars_1m.csv.gz")
    if not raw:
        return None, None
    try:
        text = gzip.decompress(raw).decode("ascii", "replace") if raw[:2] == b"\x1f\x8b" else raw.decode("ascii", "replace")
    except (OSError, EOFError):
        return None, None
    rows = [r for r in text.splitlines()[1:] if r.count(",") >= 4]
    if not rows:
        return None, None
    newest = max(int(float(r.split(",", 1)[0])) for r in rows)
    path = os.path.join(ctx["work"], "pc_bars_1m.csv")
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("time,open,high,low,close\n")
        for r in rows:
            fh.write(",".join(r.split(",")[:5]) + "\n")
    return path, newest


def site_data(ctx):
    """The public site's data.json (adds the paper ledger and the eval's trades to the reels); None when unreachable."""
    if ctx.get("data_json") is not None:
        return ctx["data_json"] or None
    path = os.path.join(ctx["work"], "data.json")
    try:
        with urllib.request.urlopen(SITE_DATA_URL, timeout=30) as r, open(path, "wb") as fh:
            shutil.copyfileobj(r, fh)
        json.load(open(path, encoding="utf-8"))
        return path
    except Exception as e:  # noqa: BLE001 - optional input
        ctx["log"].append(f"site data.json not read ({e.__class__.__name__}): reels without the paper ledger")
        return None


def run_odeon(task, tmp, ctx):
    bars, newest = heartbeat_bars(ctx)
    prev = (ctx["entry"].get("inputs") or {}).get("bars_t")
    have = has_outputs(task, ctx["out"])
    if have and not ctx["force"]:
        if newest is None:
            return {"ran": False, "note": "no PC bars on the heartbeat branch: reels kept", "inputs": {"bars_t": prev}}
        if prev and newest <= prev:
            return {"ran": False, "note": f"no new PC bars since {fresh.when(prev)}", "inputs": {"bars_t": prev}}
    cmd = py("tools/odeon_export.py", "--out", os.path.join(tmp, "trades.json"))
    if bars:
        cmd += ["--bars", bars]
    data = site_data(ctx)
    if data:
        cmd += ["--data", data]
    sub(cmd, task.timeout_s, ctx["log"])
    return {"ran": True, "note": f"reels re-exported (PC bars to {fresh.when(newest)})" if newest else "reels re-exported",
            "inputs": {"bars_t": newest or prev}}


def _weekly(cmd_args):
    def runner(task, tmp, ctx):
        fp = fingerprint(task.inputs)
        prev = (ctx["entry"].get("inputs") or {}).get("fp")
        if prev == fp and has_outputs(task, ctx["out"]) and not ctx["force"]:
            return {"ran": False, "note": "inputs unchanged since the last run: results kept", "inputs": {"fp": fp}}
        t0 = time.time()
        sub(py(*cmd_args), task.timeout_s, ctx["log"])
        copy_page_files(task, tmp, t0)
        return {"ran": True, "note": "rebuilt", "inputs": {"fp": fp}}
    return runner


RUNNERS = {
    "fates": run_fates,
    "odeon": run_odeon,
    "tree": _weekly(("-m", "tools.strategytree", "--no-runs", "--procs", str(max(1, min(4, os.cpu_count() or 1))))),
    "prometheus": _weekly(("-m", "tools.prometheus.forge", "--no-runs")),
}


# ------------------------------------------------------------------------------------------------------------ orchestrator
def status_path(out):
    return os.path.join(out, "cronos", "status.json")


def run(names, out=DEFAULT_OUT, now=None, force=False, saver=False, runners=None, ctx_extra=None, echo=print) -> dict:
    """Run the named tasks into <out>; returns the status document (also written to <out>/cronos/status.json)."""
    runners = runners or RUNNERS
    os.makedirs(out, exist_ok=True)
    status = load_json(status_path(out))
    if not isinstance(status, dict) or not isinstance(status.get("tasks"), dict):
        status = {"v": 1, "tasks": {}}
    logs = {}
    for name in names:
        task = registry.get(name)
        entry = dict(status["tasks"].get(name) or {})
        t_start = now if now is not None else time.time()
        if task.runner != "cronos":
            echo(f"[{name}] runs {'in ' + task.workflow if task.workflow else 'inside the site build'}: nothing to do here")
            continue
        if saver and task.heavy:
            entry.update(task=name, app=task.app, cadence=task.cadence, last_run_t=int(t_start), ran=False,
                         note="skipped: Actions saver mode (budget.json)", seconds=0)
            status["tasks"][name] = entry
            logs[name] = ["skipped: Actions saver mode"]
            echo(f"[{name}] skipped (Actions saver mode)")
            continue
        tmp = os.path.join(out, ".cronos_tmp", task.app)
        work = os.path.join(out, ".cronos_tmp", "_work_" + name)
        for d in (tmp, work):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        log = []
        ctx = {"out": out, "entry": entry, "force": force, "log": log, "work": work, **(ctx_extra or {})}
        t0 = time.time()
        echo(f"[{name}] {task.what}")
        try:
            fn = runners.get(name)
            if fn is None:
                raise TaskError("no runner")
            res = fn(task, tmp, ctx) or {}
            if res.get("ran"):
                check_outputs(task, tmp)
                os.makedirs(os.path.join(out, task.app), exist_ok=True)
                for f in task.files:
                    os.replace(os.path.join(tmp, f), os.path.join(out, task.app, f))
                entry["data_t"] = int(t_start)
            entry.update(ok=True, ran=bool(res.get("ran")), last_ok_t=int(t_start), note=str(res.get("note") or "")[:200],
                         error="")
            if "inputs" in res:
                entry["inputs"] = res["inputs"]
        except Exception as e:  # noqa: BLE001 - a task never breaks the run
            msg = str(e) if isinstance(e, TaskError) else f"{e.__class__.__name__}: {e}"
            log.append(f"FAILED: {msg}")
            entry.update(ok=False, ran=False, error=msg[:200], note="failed: the last good outputs are kept")
        entry.update(task=name, app=task.app, cadence=task.cadence, last_run_t=int(t_start),
                     seconds=round(time.time() - t0, 1))
        status["tasks"][name] = entry
        logs[name] = log
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        echo(f"[{name}] {'ok' if entry['ok'] else 'FAILED'} in {entry['seconds']:.0f}s: {entry.get('error') or entry.get('note')}")
    shutil.rmtree(os.path.join(out, ".cronos_tmp"), ignore_errors=True)
    t_end = now if now is not None else time.time()
    status.update(v=1, t=int(t_end), built=dt.datetime.fromtimestamp(t_end, fresh.ET).strftime("%Y-%m-%d %H:%M ET"))
    write_json(status_path(out), status, compact=False)
    status["_logs"] = logs
    return status


def summary_md(status, names) -> str:
    """The Actions run summary: a table of the tasks and each task's log tail."""
    rows = ["## CRONOS", "", "| Task | Result | Seconds | Note |", "|---|---|---|---|"]
    for n in names:
        e = status["tasks"].get(n)
        if not e:
            continue
        res = "failed" if e.get("ok") is False and e.get("error") else ("rebuilt" if e.get("ran") else
                                                                         "skipped" if str(e.get("note", "")).startswith("skipped") else "checked, nothing new")
        note = (e.get("error") or e.get("note") or "").replace("|", "/")
        rows.append(f"| {n} | {res} | {e.get('seconds', 0):.0f} | {note} |")
    for n, log in (status.get("_logs") or {}).items():
        tail = "\n".join(log[-LOG_TAIL:]).replace("```", "'''")
        rows += ["", f"<details><summary>{n} log (last {LOG_TAIL} lines)</summary>", "", "```", tail, "```", "", "</details>"]
    return "\n".join(rows) + "\n"


def saver_mode(now=None) -> bool:
    """True when the cloud monitor's budget.json (dashboard branch) says the Actions minutes are in saver mode this month."""
    raw = git_file("dashboard", "budget.json")
    try:
        b = json.loads(raw) if raw else None
    except ValueError:
        return False
    if not isinstance(b, dict):
        return False
    month = dt.datetime.fromtimestamp(now or time.time(), fresh.ET).strftime("%Y-%m")
    return b.get("month") == month and b.get("saver") is True
