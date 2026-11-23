"""WRITE GUARD (night-hermetic 2026-11-23): a test may never change the bot's LIVE files.

Loaded by Python at startup when this folder is on PYTHONPATH (engine/pc_selftest.child_env puts it there for every self-test
child; tests/test_hermetic.py and tools/hermetic_scan.py use it here). With LE_WRITE_GUARD set, an audit hook (sys.addaudithook)
watches every file open for writing, rename / replace, remove, mkdir, rmtree and truncate. A target under a PROTECTED path of the
repo (data/, logs/, cache/, the strategy / config files at the top: live_model*.json, second_model.json, dashboard_view.json,
notify_settings.json, update_source.json, *.ps1 next to the bat files) or the owner's settings folder (~/.olympus) is:
  LE_WRITE_GUARD=raise   refused: PermissionError (the self-test child: a dirty suite fails loudly, the live file stays as it was)
  LE_WRITE_GUARD=log     allowed, one JSON line appended to LE_WRITE_GUARD_LOG (the scan: which suite writes where)
Every other write inside the repo (outside __pycache__, scratch/, .git) is logged as "repo" in log mode (a tracked file a test
rewrites), never refused. Children inherit it (PYTHONPATH + the env). Stdlib only; never raises on its own.
"""
import json
import os
import sys

_MODE = os.environ.get("LE_WRITE_GUARD", "")
if _MODE in ("raise", "log"):
    _ROOT = os.path.normcase(os.path.realpath(os.environ.get("LE_WRITE_GUARD_ROOT")
                                              or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    _HOME = os.path.normcase(os.path.realpath(os.path.join(os.path.expanduser("~"), ".olympus")))
    _DIRS = tuple(os.path.join(_ROOT, d) for d in ("data", "logs", "cache"))
    _TOP = {os.path.normcase(x) for x in ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json",
                                          "dashboard_view.json", "notify_settings.json", "update_source.json", ".env.local.ps1")}
    _SKIP = tuple(os.path.join(_ROOT, d) for d in (".git", "scratch", "tests" + os.sep + "write_guard"))
    _LOG = os.environ.get("LE_WRITE_GUARD_LOG") or ""
    _TAG = os.environ.get("LE_WRITE_GUARD_TAG") or ""
    _busy = [False]

    def _kind(p, ev="open"):
        try:
            if isinstance(p, int):
                return None, None
            p = os.fsdecode(p)
            if not os.path.isabs(p) and os.sep not in p and (os.altsep or "/") not in p:
                # a bare name: often relative to a dir_fd (shutil.rmtree / tempfile walk a temp folder that way), so it says nothing
                # about where it is; only an open-for-write of a top config file by its bare name (cwd = the repo) is still checked
                if ev != "open" or os.path.normcase(p) not in _TOP or os.path.normcase(os.path.realpath(os.getcwd())) != _ROOT:
                    return None, None
            full = os.path.normcase(os.path.realpath(p))
        except Exception:  # noqa: BLE001
            return None, None
        if full == _HOME or full.startswith(_HOME + os.sep):
            return "protected", full
        if not (full == _ROOT or full.startswith(_ROOT + os.sep)):
            return None, None
        if "__pycache__" in full or full.startswith(_SKIP):
            return None, None
        if full.startswith(tuple(d + os.sep for d in _DIRS)) or full in _DIRS:
            return "protected", full
        rel = full[len(_ROOT) + 1:]
        if os.sep not in rel and (rel in _TOP or rel.endswith(".local.ps1")):
            return "protected", full
        return "repo", full

    def _note(kind, full, ev):
        if _busy[0] or not _LOG:
            return
        _busy[0] = True
        try:
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"kind": kind, "path": full[len(_ROOT) + 1:] if full.startswith(_ROOT) else full, "ev": ev,
                                     "tag": _TAG, "argv": " ".join(sys.argv[:2])[:160]}) + "\n")
        except Exception:  # noqa: BLE001
            pass
        finally:
            _busy[0] = False

    def _check(ev, paths, soft=False):
        for p in paths:
            k, full = _kind(p, ev)
            if not k:
                continue
            if k == "protected" and _MODE == "raise" and not soft:
                raise PermissionError(f"write guard: a test may not change the live file {full} ({ev}); use a temp folder")
            _note(k, full, ev)

    def _hook(ev, args):
        if _busy[0]:
            return
        try:
            if ev == "open":
                path, mode, flags = (list(args) + [None, None, None])[:3]
                w = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                if w and path is not None:
                    _check(ev, [path])
            elif ev in ("os.rename", "os.link", "os.symlink"):
                _check(ev, [args[0], args[1]] if len(args) > 1 else [args[0]])
            elif ev == "sqlite3.connect":           # sqlite opens its file in C (no "open" event): data/memory.db ...
                db = args[0] if args else None
                if isinstance(db, (str, bytes, os.PathLike)) and os.fsdecode(db) not in (":memory:", "") and not os.fsdecode(db).startswith("file:"):
                    _check(ev, [db], soft=os.path.exists(db))   # creating a live db is refused; opening the live one only logged
            elif ev == "os.mkdir":
                if not isinstance(args[0], int) and not os.path.exists(args[0]):   # os.makedirs(exist_ok=True) on a folder that is there
                    _check(ev, [args[0]])
            elif ev in ("os.remove", "os.rmdir", "os.truncate", "shutil.rmtree"):
                if isinstance(args[0], int) or os.path.lexists(args[0]):   # a clean-up of what is not there changes nothing
                    _check(ev, [args[0]])
        except PermissionError:
            raise
        except Exception:  # noqa: BLE001
            pass

    sys.addaudithook(_hook)
