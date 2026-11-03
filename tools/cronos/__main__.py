"""python -X utf8 -m tools.cronos --task <name>[,<name>] | --group nightly|weekly | --all [--out <dir>] [--force] [--saver auto|on|off]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.cronos import registry, run  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.cronos", description="CRONOS: the nightly refresh of the OLYMPUS research apps")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--task", help="one task or several, comma separated (see --list)")
    g.add_argument("--group", choices=sorted(registry.GROUPS), help="nightly | weekly | all")
    g.add_argument("--all", action="store_true", help="every task CRONOS runs itself")
    g.add_argument("--list", action="store_true", help="print the registry")
    ap.add_argument("--out", default=run.DEFAULT_OUT, help="the output folder, laid out like the site (default research/cronos/out)")
    ap.add_argument("--force", action="store_true", help="rebuild even when nothing new came in")
    ap.add_argument("--saver", choices=("auto", "on", "off"), default="auto",
                    help="skip the heavy tasks in Actions saver mode (auto: the dashboard branch's budget.json)")
    ap.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""), help="append a Markdown log here")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a task failed (default: always 0, failures are in status.json)")
    a = ap.parse_args(argv)
    if a.list:
        for t in registry.TASKS:
            print(f"{t.name:<11} {t.cadence:<8} {t.runner:<8} timeout {t.timeout_s // 60:>2} min  max age {t.max_age_h:>4.0f} h  "
                  f"~{t.est_min:g} min  {t.what}")
        return 0
    if a.task:
        names = [n.strip() for n in a.task.split(",") if n.strip()]
        for n in names:
            registry.get(n)
    else:
        names = list(registry.GROUPS["all" if a.all else a.group])
    saver = a.saver == "on" or (a.saver == "auto" and run.saver_mode())
    st = run.run(names, a.out, force=a.force, saver=saver)
    if a.summary:
        try:
            with open(a.summary, "a", encoding="utf-8") as fh:
                fh.write(run.summary_md(st, names))
        except OSError as e:
            print("summary not written:", e)
    failed = [n for n in names if (st["tasks"].get(n) or {}).get("ok") is False and n in st.get("_logs", {})]
    print(f"cronos: {len(names)} task(s), {len(failed)} failed{': ' + ', '.join(failed) if failed else ''} -> {run.status_path(a.out)}")
    return 1 if (a.strict and failed) else 0


if __name__ == "__main__":
    sys.exit(main())
