"""CRONOS task registry: what refreshes, when, how long it may take and how old its data may get before its card goes amber.

cadence  nightly   Mon-Fri nights after the CME close (.github/workflows/cronos.yml, datacity.yml)
         frequent  every 6 hours, any day (.github/workflows/kalshicity.yml: the Kalshi feed never sleeps)
         weekly    Sunday (cronos.yml), before the Sunday evening site publish
         publish   inside every site build (tools/build_web_dashboard.py): nothing for CRONOS to run
runner   cronos    run by tools/cronos/run.py
         workflow  run by its own workflow (`workflow` names it); CRONOS only reads its branch and stamps its card
         build     run by the site build itself
max_age_h is in weekday hours (tools/cronos/fresh.py business_hours): the nightly jobs do not run on weekends by design,
so Friday night's data is still "fresh" on Monday morning; after max_age_h the card says "not updated since ...".
"""
from __future__ import annotations

import dataclasses

NIGHTLY_MAX_H = 36.0
WEEKLY_MAX_H = 5 * 24.0 + 36.0     # a week of weekday hours + the same 36 h of slack


@dataclasses.dataclass(frozen=True)
class Task:
    name: str
    app: str                       # the site folder (tools/web_public/<app>/)
    cadence: str                   # nightly | weekly | publish
    runner: str                    # cronos | workflow | build
    timeout_s: int                 # the task's own limit (the subprocess is killed after it)
    max_age_h: float               # weekday hours before the card goes amber
    files: tuple = ()              # the app files the task publishes (relative to <out>/<app>/), jarvis.json last
    branch: str = "cronos"         # where the outputs live between publishes
    branch_files: tuple = ()       # (path on the branch, path in the site) when the branch is not laid out like the site
    optional_files: tuple = ()     # (path on the branch, path in the site) copied when present and valid JSON, silently skipped when absent: never part of the all-or-nothing rule
    inputs: tuple = ()             # repo files whose fingerprint decides "nothing new: skip" (weekly tasks)
    heavy: bool = False            # skipped in Actions saver mode (engine/actions_budget.py budget.json "saver")
    est_min: float = 1.0           # typical billed minutes on a 2-core GitHub runner (docs/CRONOS.md budget)
    workflow: str = ""
    what: str = ""

    @property
    def every(self) -> str:
        return {"nightly": "nightly", "weekly": "weekly", "publish": "at every publish", "frequent": "every 6 hours"}[self.cadence]


TASKS: tuple = (
    Task("datacity", "datacity", "nightly", "workflow", 20 * 60, NIGHTLY_MAX_H,
         files=("city.json", "jarvis.json"), branch="datacity",
         branch_files=(("city.json", "datacity/city.json"), ("jarvis.json", "datacity/jarvis.json")),
         est_min=3.0, workflow=".github/workflows/datacity.yml",
         what="Data City: the PC's new 5m bars appended, the event table extended, ~67k combinations re-scored"),
    Task("kalshicity", "kalshicity", "frequent", "workflow", 5 * 60, NIGHTLY_MAX_H,
         files=("edges.json", "learning_log.json", "hypotheses.json", "jarvis.json"), branch="kalshicity",
         branch_files=(("edges.json", "kalshicity/edges.json"), ("learning_log.json", "kalshicity/learning_log.json"),
                       ("hypotheses.json", "kalshicity/hypotheses.json"), ("jarvis.json", "kalshicity/jarvis.json")),
         optional_files=(("whatif.json", "kalshicity/whatif.json"), ("forward.json", "kalshicity/forward.json")),
         est_min=1.0, workflow=".github/workflows/kalshicity.yml",
         what="Kalshi City: the public kalshi-feed re-read, every edge re-measured, the learning log extended (ledger.json stays on the branch)"),
    Task("fates", "fates", "nightly", "cronos", 15 * 60, NIGHTLY_MAX_H,
         files=("fates.json", "jarvis.json"), heavy=True, est_min=5.5,
         what="FATES: 1,000 futures of today's evals from the latest live.json state"),
    Task("odeon", "odeon", "nightly", "cronos", 5 * 60, NIGHTLY_MAX_H,
         files=("trades.json", "jarvis.json"), est_min=0.5,
         what="ODEON: the replay reels, re-exported when the PC pushed new NinjaTrader bars (heartbeat branch)"),
    Task("pantheon", "pantheon", "nightly", "cronos", 8 * 60, NIGHTLY_MAX_H,
         files=("pantheon.json", "states.json", "jarvis.json"), est_min=1.0,
         what="PANTHEON: the eight free data gods (FRED, CBOE, CFTC, SqueezeMetrics, Treasury, calendar) re-read, "
              "the council verdict and the states.json Data City reads"),
    Task("hermes", "hermes", "publish", "build", 60, NIGHTLY_MAX_H, est_min=0.0,
         what="HERMES: OLYMPUS Wrapped, rebuilt from data.json inside every site build"),
    Task("tree", "tree", "weekly", "cronos", 30 * 60, WEEKLY_MAX_H,
         files=("tree.json", "jarvis.json"), heavy=True, est_min=11.0,
         inputs=("data/NQ_5m.csv", "data/ES_5m.csv", "data/VIX_1d.csv", "tools/strategytree"),
         what="DAPHNE: the strategy-tree search (80 roots + a placebo), rerun when its data or code changed"),
    Task("prometheus", "prometheus", "weekly", "cronos", 30 * 60, WEEKLY_MAX_H,
         files=("forge.json", "jarvis.json"), heavy=True, est_min=9.0,
         inputs=("data/NQ_5m.csv", "data/NQ_1m.csv", "data/VIX_1d.csv", "live_model_lit.json", "engine/lit.py",
                 "tools/prometheus"),
         what="PROMETHEUS: the LIT evolution forge (H1 pick, H2 check), rerun when its data, LIT or code changed"),
)

BY_NAME = {t.name: t for t in TASKS}
GROUPS = {"nightly": tuple(t.name for t in TASKS if t.cadence == "nightly" and t.runner == "cronos"),
          "weekly": tuple(t.name for t in TASKS if t.cadence == "weekly" and t.runner == "cronos")}
GROUPS["all"] = GROUPS["nightly"] + GROUPS["weekly"]
STAMPED = tuple(t.name for t in TASKS if t.runner != "build")   # the cards CRONOS stamps at every publish (hermes stamps itself)


def get(name: str) -> Task:
    if name not in BY_NAME:
        raise KeyError(f"unknown CRONOS task {name!r} (known: {', '.join(BY_NAME)})")
    return BY_NAME[name]


def optional_site_files(task: Task) -> list:
    """[(branch path, site path)] the site build takes from the branch only when they are there (a newer engine writes them, an older branch does not yet)."""
    return list(task.optional_files)


def site_files(task: Task) -> list:
    """[(branch path, site path)] of what the site build takes from the task's branch."""
    if task.branch_files:
        return list(task.branch_files)
    return [(f"{task.app}/{f}", f"{task.app}/{f}") for f in task.files]
