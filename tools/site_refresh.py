"""Refresh the research apps' data files that used to come from CRONOS (day-archive 2026-11-20).

Why: CRONOS (.github/workflows/cronos.yml) pushed fates / odeon / pantheon / tree / prometheus to a `cronos` branch that the site build
read. Since the move to dcondax1-wq/Olympus there is no `cronos` branch, so those files froze on Nov 3-4 (Fates showed hard-coded
fallback numbers, Forum a 17-day-old market read). This runs the same builders at site-build time, each in its own subprocess with a
timeout; a failure is printed, never raised, and leaves the committed copy in place.

    python -X utf8 tools/site_refresh.py --site <built site dir>    # write the fresh files into the built site (the site build calls this)
    python -X utf8 tools/site_refresh.py --repo                     # refresh the committed copies under tools/web_public/ instead
    python -X utf8 tools/site_refresh.py --list                     # what it runs

Research / display only: nothing here reads or changes live trading settings. Network: free public sources only (Pantheon: FRED, CBOE,
Treasury, CFTC; Fates: the PC's public status post on ntfy). Never fatal.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PY = [sys.executable, "-X", "utf8"]

# name -> (command builder(out_dir) -> argv, files it writes into out_dir, timeout s). out_dir mirrors the site folder of the app.
STEPS = {
    "pantheon": (lambda d: PY + ["-m", "tools.pantheon", "--no-research", "--no-web", "--out", d], ("pantheon.json", "states.json", "jarvis.json"), 240),
    "fates": (lambda d: PY + ["-m", "tools.fates.build", "--out", d], ("fates.json", "jarvis.json"), 600),
}
# Only builders with an --out folder: in --site mode nothing under tools/web_public/ is written (a dirty checkout would block the PC's
# auto-update pull). Odeon needs the PC's trade days (the `data` branch, not on this repo yet): LEAD_WIRES.


def run(names, site: str | None, quiet: bool = False) -> dict:
    res = {}
    for name in names:
        cmd, files, tmo = STEPS[name]
        t0 = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = tmp
            try:
                r = subprocess.run(cmd(out_dir), cwd=ROOT, capture_output=True, text=True, timeout=tmo)
                ok = r.returncode == 0 and all(os.path.isfile(os.path.join(out_dir, f)) for f in files)
                note = "" if ok else (r.stdout[-200:] + r.stderr[-200:]).strip().replace("\n", " ")
            except Exception as e:  # noqa: BLE001
                ok, note = False, str(e)[:200]
            if ok and site is not None:
                dst = os.path.join(site, name)
                os.makedirs(dst, exist_ok=True)
                for f in files:
                    shutil.copy2(os.path.join(out_dir, f), os.path.join(dst, f))
            elif ok and out_dir != os.path.join(WEB, name):
                for f in files:
                    shutil.copy2(os.path.join(out_dir, f), os.path.join(WEB, name, f))
        res[name] = (ok, round(time.time() - t0, 1), note)
        if not quiet:
            print(f"  refresh {name}: {'ok' if ok else 'kept the old copy'} ({res[name][1]} s){' ' + note if note else ''}")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", help="the built site folder to write into")
    ap.add_argument("--repo", action="store_true", help="refresh the committed copies under tools/web_public/")
    ap.add_argument("--only", help="comma list of steps")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for k, (_, files, tmo) in STEPS.items():
            print(f"{k}: {', '.join(files)} (timeout {tmo} s)")
        return 0
    if not a.site and not a.repo:
        ap.error("--site DIR or --repo")
    names = [n for n in (a.only.split(",") if a.only else STEPS) if n in STEPS]
    run(names, None if a.repo else a.site)
    return 0                                     # never fatal: a failed step keeps the old copy


if __name__ == "__main__":
    sys.exit(main())
