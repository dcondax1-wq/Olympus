"""ME HEALTH (team ME1, 2026-11-14, docs/ME_HUB.md): your Apple Watch days for the Me hub and Jarvis, made on the PC. Free, no app.

Two ways in, both yours, both private:
  1. every evening the iPhone Shortcut "Health to PC" posts the day (steps, active energy, exercise minutes, stand hours, resting heart
     rate, HRV, sleep, weight, workouts) to the PC's own link: POST /inbox/health (engine/day_inbox.validate_health, strict), one line
     each in data/inbox/health.jsonl. The newest post of a day wins, field by field.
  2. once, for history: the Health app's full export (Health > your picture > Export All Health Data -> export.zip on the PC):
       python tools/me_health.py --import "%USERPROFILE%\\Downloads\\export.zip"      (or the export.xml inside it)
     STREAMED with expat (a 2 GB export never sits in memory), the last 400 days by default (--days), entities refused (a real export
     has none). It keeps the daily totals in %USERPROFILE%\\.olympus\\me\\health_history.json, nothing else of the file.

  python tools/me_health.py               rebuild data/me/health.json and print the day
  python tools/me_health.py --goal steps=10000 --goal sleep=7.5     your goals (move kcal, exercise min, stand h, steps, sleep h)

data/me/health.json (the phone reads it at /site/me/health.json, the PC's own link only; Jarvis answers from its "jarvis" lines):
  today + rings-style goals (move / exercise / stand + steps / sleep), last night's sleep, the week, 7 / 30-day trends, resting HR and HRV
  against your own 30-day normal, workouts, weight, a rule-based "recovered?" line. Plain numbers, not medical advice.
Double counting: the export holds the same steps from the iPhone AND the watch; a day takes the biggest single source (as close to the
Health app as a file can get), the rings come from Apple's own daily ActivitySummary when it is there, sleep is the union of the asleep
periods (core, deep, REM) of every source.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys
import time
import zipfile
from xml.parsers import expat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import me_core as M  # noqa: E402

INBOX_DEFAULT = os.path.join(ROOT, "data", "inbox", "health.jsonl")
OUT_NAME = "health.json"
HISTORY = "health_history.json"
GOALS_FILE = "health_goals.json"
GOALS_DEFAULT = {"move": 500, "exercise": 30, "stand": 12, "steps": 8000, "sleep": 7.5}
GOAL_RANGE = {"move": (50, 5000), "exercise": (5, 300), "stand": (1, 24), "steps": (1000, 60000), "sleep": (4, 12)}
DAYS_KEEP = 60                 # rows on the phone
HISTORY_DAYS = 400             # rows kept from an export
METRICS = ("steps", "active_kcal", "exercise_min", "stand_h", "rhr", "hrv_ms", "sleep_h", "sleep_deep_h", "sleep_rem_h", "weight_lb")
CONNECT = "Make the iPhone Shortcut 'Health to PC' (docs/ME_HUB.md, 5 minutes, no app); it runs each evening"

# the export's record types -> how a day sums them
T_STEPS = "HKQuantityTypeIdentifierStepCount"
T_KCAL = "HKQuantityTypeIdentifierActiveEnergyBurned"
T_EXER = "HKQuantityTypeIdentifierAppleExerciseTime"
T_STAND = "HKCategoryTypeIdentifierAppleStandHour"
T_RHR = "HKQuantityTypeIdentifierRestingHeartRate"
T_HRV = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
T_MASS = "HKQuantityTypeIdentifierBodyMass"
T_SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"
ASLEEP = {"HKCategoryValueSleepAnalysisAsleep", "HKCategoryValueSleepAnalysisAsleepUnspecified", "HKCategoryValueSleepAnalysisAsleepCore",
          "HKCategoryValueSleepAnalysisAsleepDeep", "HKCategoryValueSleepAnalysisAsleepREM"}
DEEP, REM = "HKCategoryValueSleepAnalysisAsleepDeep", "HKCategoryValueSleepAnalysisAsleepREM"
STOOD = "HKCategoryValueAppleStandHourStood"
WORKOUT_NAMES = {"Running": "Run", "Walking": "Walk", "Cycling": "Ride", "TraditionalStrengthTraining": "Strength", "FunctionalStrengthTraining": "Strength",
                 "HighIntensityIntervalTraining": "HIIT", "Swimming": "Swim", "Yoga": "Yoga", "Hiking": "Hike", "Elliptical": "Elliptical",
                 "Rowing": "Row", "CoreTraining": "Core", "Basketball": "Basketball", "Soccer": "Soccer", "Boxing": "Boxing", "Dance": "Dance",
                 "MixedCardio": "Cardio", "StairClimbing": "Stairs", "Pilates": "Pilates", "Golf": "Golf", "Tennis": "Tennis", "Other": "Workout"}


def inbox_path(env=None) -> str:
    env = os.environ if env is None else env
    return os.path.join(env.get("LE_INBOX_DIR") or os.path.join(ROOT, "data", "inbox"), "health.jsonl")


def goals_of(env=None) -> dict:
    g = dict(GOALS_DEFAULT)
    hist = M.read_json(os.path.join(M.me_dir(env), HISTORY), {}) or {}
    for k, v in M.obj(hist.get("goals")).items():      # Apple's own ring goals from the export
        if k in g and M.num(v):
            g[k] = M.num(v)
    for k, v in M.obj(M.read_json(os.path.join(M.me_dir(env), GOALS_FILE), {})).items():   # what you set (wins)
        if k in g and M.num(v):
            g[k] = M.num(v)
    return g


# ------------------------------------------------------------------------------------------------ 1. the Shortcut's posts
def read_inbox(path: str) -> dict:
    """{day: row} from data/inbox/health.jsonl: posts in time order, the newest value of a field wins; workouts of a day are the newest list"""
    days: dict = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return {}
    recs = []
    for ln in lines:
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if isinstance(j, dict) and M.parse_day(j.get("date")):
            recs.append(j)
    recs.sort(key=lambda j: M.num(j.get("t")) or 0)
    for j in recs:
        d = days.setdefault(j["date"][:10], {"date": j["date"][:10], "src": "watch"})
        for k in METRICS:
            v = M.num(j.get(k))
            if v is not None:
                d[k] = v
        if isinstance(j.get("workouts"), list):
            d["workouts"] = [{"type": M.clean(w.get("type"), 40) or "Workout", "min": M.num(w.get("min")), "kcal": M.num(w.get("kcal")), "km": M.num(w.get("km"))}
                             for w in j["workouts"][:12] if isinstance(w, dict)]
        elif j.get("workouts_text"):
            d["workouts_text"] = M.clean(j["workouts_text"], 300)
        d["t"] = int(M.num(j.get("t")) or 0)
    return days


# ------------------------------------------------------------------------------------------------ 2. the full export, streamed
class Refused(ValueError):
    pass


def _ts(s: str):
    """'2026-11-13 23:15:02 -0500' -> aware datetime (None when it is not that shape)"""
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except (TypeError, ValueError):
        return None


def _union_h(iv: list) -> float:
    """hours covered by a list of (start, end) epoch pairs, overlaps counted once"""
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(iv):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        elif e > cur_e:
            cur_e = e
    if cur_e is not None:
        tot += cur_e - cur_s
    return tot / 3600.0


def _kcal(v, unit: str):
    x = M.num(v)
    if x is None:
        return None
    return x * 0.239006 if str(unit or "").lower() == "kj" else x


def _lb(v, unit: str):
    x = M.num(v)
    if x is None:
        return None
    u = str(unit or "").lower()
    return x * 2.20462 if u == "kg" else x / 453.592 if u == "g" else x * 14.0 if u == "st" else x


def parse_export(stream, days: int = HISTORY_DAYS, today: str | None = None) -> dict:
    """the Health export (a binary stream of export.xml) -> {days: {day: row}, goals, workouts, records, first, last}. Streamed (expat)."""
    today = today or M.ny_day(time.time())
    cutoff = M.add_days(today, -int(days))
    per_src = {"steps": {}, "kcal": {}, "exer": {}}           # metric -> (day, source) -> sum
    stand, rhr, hrv, mass, sleep, deep, rem = {}, {}, {}, {}, {}, {}, {}
    acts, workouts, goals = {}, [], {}
    st = {"records": 0, "first": None, "last": None, "wk": None}

    def start(name, a):
        if name == "Record":
            t = a.get("type")
            sd = a.get("startDate") or ""
            if sd[:10] < cutoff:
                return
            day = sd[:10]
            if t == T_STEPS or t == T_KCAL or t == T_EXER:
                key = "steps" if t == T_STEPS else "kcal" if t == T_KCAL else "exer"
                v = _kcal(a.get("value"), a.get("unit")) if t == T_KCAL else M.num(a.get("value"))
                if v is not None:
                    k = (day, a.get("sourceName") or "")
                    per_src[key][k] = per_src[key].get(k, 0.0) + v
            elif t == T_STAND:
                if a.get("value") == STOOD:
                    stand[day] = stand.get(day, 0) + 1
            elif t == T_RHR:
                v = M.num(a.get("value"))
                if v:
                    rhr.setdefault(day, []).append(v)
            elif t == T_HRV:
                v = M.num(a.get("value"))
                if v:
                    hrv.setdefault(day, []).append(v)
            elif t == T_MASS:
                v = _lb(a.get("value"), a.get("unit"))
                if v:
                    mass[day] = v
            elif t == T_SLEEP:
                val = a.get("value")
                s, e = _ts(sd), _ts(a.get("endDate") or "")
                if val in ASLEEP and s and e and e > s:
                    wake = (a.get("endDate") or "")[:10]
                    pair = (s.timestamp(), e.timestamp())
                    sleep.setdefault(wake, []).append(pair)
                    if val == DEEP:
                        deep.setdefault(wake, []).append(pair)
                    elif val == REM:
                        rem.setdefault(wake, []).append(pair)
            else:
                return
            st["records"] += 1
            st["first"] = day if not st["first"] or day < st["first"] else st["first"]
            st["last"] = day if not st["last"] or day > st["last"] else st["last"]
        elif name == "ActivitySummary":
            day = a.get("dateComponents") or ""
            if day < cutoff or not M.parse_day(day):
                return
            row = {"active_kcal": _kcal(a.get("activeEnergyBurned"), a.get("activeEnergyBurnedUnit")), "exercise_min": M.num(a.get("appleExerciseTime")),
                   "stand_h": M.num(a.get("appleStandHours"))}
            acts[day] = row
            g = {"move": _kcal(a.get("activeEnergyBurnedGoal"), a.get("activeEnergyBurnedUnit")), "exercise": M.num(a.get("appleExerciseTimeGoal")),
                 "stand": M.num(a.get("appleStandHoursGoal"))}
            if day >= goals.get("_day", ""):
                goals.update({k: v for k, v in g.items() if v}, _day=day)
        elif name == "Workout":
            sd = a.get("startDate") or ""
            if sd[:10] < cutoff:
                st["wk"] = None
                return
            typ = str(a.get("workoutActivityType") or "").replace("HKWorkoutActivityType", "")
            mins = M.num(a.get("duration"))
            if mins is not None and str(a.get("durationUnit") or "min").lower().startswith("s"):
                mins = mins / 60.0
            km = M.num(a.get("totalDistance"))
            if km is not None and str(a.get("totalDistanceUnit") or "km").lower() == "mi":
                km *= 1.609344
            w = {"date": sd[:10], "type": WORKOUT_NAMES.get(typ, M.clean(typ, 30) or "Workout"), "min": round(mins, 1) if mins is not None else None,
                 "kcal": _kcal(a.get("totalEnergyBurned"), a.get("totalEnergyBurnedUnit")), "km": round(km, 2) if km else None}
            workouts.append(w)
            st["wk"] = w
        elif name == "WorkoutStatistics" and st["wk"] is not None:
            t = a.get("type")
            if t == T_KCAL and st["wk"].get("kcal") is None:
                st["wk"]["kcal"] = _kcal(a.get("sum"), a.get("unit"))
            elif t in ("HKQuantityTypeIdentifierDistanceWalkingRunning", "HKQuantityTypeIdentifierDistanceCycling", "HKQuantityTypeIdentifierDistanceSwimming") and not st["wk"].get("km"):
                x = M.num(a.get("sum"))
                if x:
                    st["wk"]["km"] = round(x * (1.609344 if str(a.get("unit") or "").lower() == "mi" else 1.0), 2)

    def end(name):
        if name == "Workout":
            st["wk"] = None

    def refuse(*_a):
        raise Refused("this file declares entities: not a Health export (refused)")

    p = expat.ParserCreate()
    p.buffer_text = True
    p.StartElementHandler = start
    p.EndElementHandler = end
    p.EntityDeclHandler = refuse
    p.ExternalEntityRefHandler = refuse
    try:
        p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    except AttributeError:
        pass
    while True:
        chunk = stream.read(1 << 20)
        if not chunk:
            break
        p.Parse(chunk, False)
    p.Parse(b"", True)

    out = {}

    def row(day):
        return out.setdefault(day, {"date": day, "src": "export"})

    for key, dst in (("steps", "steps"), ("kcal", "active_kcal"), ("exer", "exercise_min")):
        best = {}
        for (day, _src), v in per_src[key].items():
            best[day] = max(best.get(day, 0.0), v)
        for day, v in best.items():
            row(day)[dst] = round(v)
    for day, n in stand.items():
        row(day)["stand_h"] = n
    for day, a in acts.items():                       # Apple's own daily totals win over the sums
        for k, v in a.items():
            if v is not None:
                row(day)[k] = round(v)
    for day, vs in rhr.items():
        row(day)["rhr"] = round(sum(vs) / len(vs), 1)
    for day, vs in hrv.items():
        row(day)["hrv_ms"] = round(sum(vs) / len(vs), 1)
    for day, v in mass.items():
        row(day)["weight_lb"] = round(v, 1)
    for day, iv in sleep.items():
        if day < cutoff:
            continue
        row(day)["sleep_h"] = round(_union_h(iv), 2)
        if deep.get(day):
            row(day)["sleep_deep_h"] = round(_union_h(deep[day]), 2)
        if rem.get(day):
            row(day)["sleep_rem_h"] = round(_union_h(rem[day]), 2)
    for w in workouts:
        if w.get("kcal") is not None:
            w["kcal"] = round(w["kcal"])
        row(w["date"]).setdefault("workouts", []).append({k: w[k] for k in ("type", "min", "kcal", "km")})
    goals.pop("_day", None)
    return {"days": out, "goals": {k: round(v) for k, v in goals.items()}, "workouts": workouts[-400:], "records": st["records"],
            "first": st["first"], "last": st["last"]}


def open_export(path: str):
    """the export.xml stream inside export.zip (the biggest .xml that is not the CDA file; its name changes with the iPhone's language), or the file"""
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        xs = [i for i in z.infolist() if i.filename.lower().endswith(".xml") and "cda" not in os.path.basename(i.filename).lower()]
        if not xs:
            raise Refused("no export.xml in this zip: is it the Health app's export.zip?")
        return z.open(max(xs, key=lambda i: i.file_size))
    return open(path, "rb")


def import_export(path: str, env=None, days: int = HISTORY_DAYS, now_s: float | None = None) -> dict:
    """read an export (zip or xml), merge its days into the private health_history.json -> the import's report"""
    now_s = time.time() if now_s is None else now_s
    t0 = time.time()
    with open_export(path) as fh:
        got = parse_export(fh, days, M.ny_day(now_s))
    hp = os.path.join(M.me_dir(env), HISTORY)
    old = M.read_json(hp, {}) or {}
    merged = dict(M.obj(old.get("days")))
    merged.update(got["days"])
    keep = sorted(merged)[-HISTORY_DAYS:]
    doc = {"v": 1, "kind": "olympus-health-history", "imported_t": int(now_s), "file": os.path.basename(path), "records": got["records"],
           "first": keep[0] if keep else None, "last": keep[-1] if keep else None, "goals": got["goals"] or M.obj(old.get("goals")),
           "days": {d: merged[d] for d in keep},
           "about": "Daily totals from your Apple Health export (no raw samples). Private: this file never leaves the PC."}
    M.write_json(hp, doc, compact=True)
    return {"days": len(got["days"]), "records": got["records"], "first": got["first"], "last": got["last"], "goals": doc["goals"],
            "seconds": round(time.time() - t0, 2), "file": hp}


# ------------------------------------------------------------------------------------------------ the phone file
def _avg(vals):
    v = [x for x in vals if x is not None]
    return round(sum(v) / len(v), 1) if v else None


def _window(rows: dict, today: str, a: int, b: int, key: str):
    """the values of key on the days today-a .. today-b (a >= b)"""
    return [M.num(M.obj(rows.get(M.add_days(today, -i))).get(key)) for i in range(b, a + 1)]


def trend(rows: dict, today: str, key: str, good: str = "up") -> dict:
    d7, prev7, d30 = _avg(_window(rows, today, 6, 0, key)), _avg(_window(rows, today, 13, 7, key)), _avg(_window(rows, today, 29, 0, key))
    ch = round((d7 - prev7) / prev7 * 100.0, 1) if d7 is not None and prev7 else None
    way = "flat" if ch is None or abs(ch) < 3 else ("up" if ch > 0 else "down")
    lvl = "" if way == "flat" else ("ok" if way == good else "warn")
    return {"d7": d7, "prev7": prev7, "d30": d30, "change_pct": ch, "way": way, "lvl": lvl}


def recovery(rows: dict, today: str, goals: dict) -> dict:
    """rule-based, your own normal: last night's HRV and today's resting HR against the 30 days before, and the sleep"""
    t = M.obj(rows.get(today))
    if not t:
        y = M.add_days(today, -1)
        t, today = M.obj(rows.get(y)), (y if rows.get(y) else today)
    base_hrv = [x for x in _window(rows, today, 30, 1, "hrv_ms") if x]
    base_rhr = [x for x in _window(rows, today, 30, 1, "rhr") if x]
    hrv, rhr, slp = M.num(t.get("hrv_ms")), M.num(t.get("rhr")), M.num(t.get("sleep_h"))
    if len(base_hrv) < 7 or len(base_rhr) < 7 or hrv is None or rhr is None:
        have = min(len(base_hrv), len(base_rhr))
        return {"level": "", "word": "Not enough history", "day": today, "text": f"Not enough history yet: it needs 7 days of HRV and resting heart rate ({have} so far).",
                "reasons": []}
    mh, sh = statistics.mean(base_hrv), (statistics.pstdev(base_hrv) or 0.0)
    mr = statistics.mean(base_rhr)
    z = (hrv - mh) / max(sh, 0.05 * mh)
    dr = rhr - mr
    reasons = [f"HRV {hrv:.0f} ms (your normal {mh:.0f})", f"resting HR {rhr:.0f} (normal {mr:.0f})"]
    if slp is not None:
        reasons.append(f"slept {slp:.1f} h (goal {goals['sleep']:g})")
    if z <= -1.0 or dr >= 5 or (slp is not None and slp < 5.5):
        lvl, word, head = "bad", "Take it easy", "Take it easy today"
    elif z <= -0.5 or dr >= 3 or (slp is not None and slp < goals["sleep"] - 1):
        lvl, word, head = "warn", "Partly recovered", "Partly recovered"
    else:
        lvl, word, head = "ok", "Recovered", "Recovered"
    return {"level": lvl, "word": word, "day": today, "hrv_z": round(z, 2), "rhr_diff": round(dr, 1),
            "text": f"{head}: " + ", ".join(reasons) + ". Your own numbers, not medical advice.", "reasons": reasons}


def rings(row: dict, goals: dict) -> list:
    out = []
    for key, g, label, unit in (("active_kcal", "move", "Move", "kcal"), ("exercise_min", "exercise", "Exercise", "min"), ("stand_h", "stand", "Stand", "h"),
                                ("steps", "steps", "Steps", ""), ("sleep_h", "sleep", "Sleep", "h")):
        v = M.num(M.obj(row).get(key))
        goal = goals[g]
        out.append({"id": g, "label": label, "value": v, "goal": goal, "unit": unit, "pct": round(min(999.0, v / goal * 100.0), 1) if v is not None and goal else None,
                    "done": bool(v is not None and goal and v >= goal)})
    return out


def merged_rows(inbox: dict, history: dict) -> dict:
    rows = {d: dict(r) for d, r in M.obj(history).items() if isinstance(r, dict)}
    for d, r in inbox.items():                         # tonight's Shortcut wins over the old export, field by field
        base = rows.get(d, {"date": d})
        rows[d] = {**base, **{k: v for k, v in r.items() if v is not None}, "src": "watch" if base.get("src") != "export" else "watch+export"}
    return rows


def _fmt(v, nd=0):
    return "-" if v is None else (f"{v:,.0f}" if nd == 0 else f"{v:,.{nd}f}")


def build(inbox: dict, history: dict, goals: dict, now_s: float, hist_meta: dict | None = None) -> dict:
    today = M.ny_day(now_s)
    rows = merged_rows(inbox, M.obj(history))
    have = sorted(d for d in rows if d <= today)
    last = have[-1] if have else None
    trow = M.obj(rows.get(today))
    lrow = M.obj(rows.get(last)) if last else {}
    last_post = max([r.get("t") or 0 for r in inbox.values()] or [0]) or None
    hm = M.obj(hist_meta)
    src_t = last_post or (M.day_epoch(last, 21) if last else None)
    week = []
    ws = M.add_days(today, -M.parse_day(today).weekday())       # Monday
    for i in range(7):
        d = M.add_days(ws, i)
        r = M.obj(rows.get(d))
        week.append({"date": d, "dow": M.parse_day(d).strftime("%a"), "steps": M.num(r.get("steps")), "exercise_min": M.num(r.get("exercise_min")),
                     "sleep_h": M.num(r.get("sleep_h")), "future": d > today})
    trends = {k: trend(rows, today, k, good) for k, good in (("steps", "up"), ("active_kcal", "up"), ("exercise_min", "up"), ("sleep_h", "up"),
                                                            ("rhr", "down"), ("hrv_ms", "up"), ("weight_lb", ""))}
    rec = recovery(rows, today, goals)
    wk = []
    for d in sorted((x for x in rows if x >= M.add_days(today, -13) and x <= today), reverse=True):
        for w in M.arr(rows[d].get("workouts")):
            wk.append({"date": d, **w})
        if rows[d].get("workouts_text"):
            wk.append({"date": d, "type": rows[d]["workouts_text"], "min": None})
    wsteps = [x["steps"] for x in week if x["steps"] is not None and not x["future"]]
    best = max((x for x in week if x["steps"] is not None), key=lambda x: x["steps"], default=None)
    # the Jarvis lines (jarvis/skills.js reads them as they are)
    sl = M.obj(rows.get(today)) if M.num(M.obj(rows.get(today)).get("sleep_h")) is not None else {}
    if sl:
        j_sleep = (f"Last night: {sl['sleep_h']:.1f} h asleep" + (f" (deep {sl['sleep_deep_h']:.1f} h, REM {sl['sleep_rem_h']:.1f} h)" if sl.get("sleep_deep_h") is not None and sl.get("sleep_rem_h") is not None else "")
                   + (f"; your 7-day average {trends['sleep_h']['d7']:.1f} h" if trends["sleep_h"]["d7"] is not None else "") + f", goal {goals['sleep']:g} h.")
    else:
        prev = max((d for d in have if M.num(rows[d].get("sleep_h")) is not None), default=None)
        j_sleep = (f"No sleep for last night yet (the Shortcut runs in the evening). The last night I have, {M.short_day(prev)}: {rows[prev]['sleep_h']:.1f} h."
                   if prev else "I have no sleep data yet: the Shortcut 'Health to PC' sends it each evening.")
    j_steps = (f"This week (Monday to today): {sum(wsteps):,.0f} steps, about {sum(wsteps) / len(wsteps):,.0f} a day; goal {goals['steps']:,.0f} a day"
               + (f"; best day {best['dow']} {best['steps']:,.0f}" if best else "") + "."
               + (f" Today so far {trow['steps']:,.0f}." if M.num(trow.get("steps")) is not None else "")) if wsteps else "I have no steps for this week yet."
    doc = {"v": 1, "kind": "olympus-health", "t": int(now_s), "built": dt.datetime.fromtimestamp(now_s, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "today": today, "private": True, "status": "ok" if rows else "empty",
           "about": "Your Apple Watch days, made on your PC. Private: only the PC's own link serves it. Plain numbers, not medical advice.",
           "sources": {"watch": {"posts": len(inbox), "last_t": last_post, "days": sorted(inbox)[-1] if inbox else None},
                       "export": {"imported_t": hm.get("imported_t"), "first": hm.get("first"), "last": hm.get("last")}},
           "src_t": src_t, "last_day": last, "goals": goals,
           "today_row": trow, "today_rings": rings(trow, goals), "last_row": lrow, "last_rings": rings(lrow, goals),
           "week": week, "trends": trends, "recovery": rec, "workouts": wk[:20],
           "days": [rows[d] for d in have[-DAYS_KEEP:]],
           "jarvis": {"sleep": j_sleep, "steps_week": j_steps, "recovered": rec["text"]}}
    return M.scrub_doc(doc)


def build_and_write(now_s: float | None = None, env=None) -> dict:
    now_s = time.time() if now_s is None else now_s
    hist = M.read_json(os.path.join(M.me_dir(env), HISTORY), {}) or {}
    doc = build(read_inbox(inbox_path(env)), M.obj(hist.get("days")), goals_of(env), now_s, hist)
    M.write_json(os.path.join(M.out_dir(env), OUT_NAME), doc, compact=True)
    return doc


def card_text(doc: dict) -> str:
    r = M.obj(doc.get("today_row")) or M.obj(doc.get("last_row"))
    if not r:
        return "  Health: nothing yet. " + CONNECT
    return (f"  Health {r.get('date')}: {_fmt(M.num(r.get('steps')))} steps, {_fmt(M.num(r.get('exercise_min')))} min exercise, "
            f"slept {_fmt(M.num(r.get('sleep_h')), 1)} h, resting HR {_fmt(M.num(r.get('rhr')))}; {M.obj(doc.get('recovery')).get('text', '')}")


def main(argv=None, env=None, say=print, now_s: float | None = None) -> int:
    ap = argparse.ArgumentParser(description="Your Apple Watch days for the Me hub (private, on this PC).")
    ap.add_argument("--import", dest="imp", metavar="EXPORT", help="the Health app's export.zip (or export.xml)")
    ap.add_argument("--days", type=int, default=HISTORY_DAYS)
    ap.add_argument("--goal", action="append", default=[], metavar="NAME=VALUE", help="move, exercise, stand, steps, sleep")
    a = ap.parse_args(argv)
    now_s = time.time() if now_s is None else now_s
    if a.goal:
        gp = os.path.join(M.me_dir(env), GOALS_FILE)
        g = M.obj(M.read_json(gp, {}))
        for kv in a.goal:
            k, _, v = kv.partition("=")
            k = k.strip().lower()
            x = M.num(v)
            if k not in GOAL_RANGE or x is None or not (GOAL_RANGE[k][0] <= x <= GOAL_RANGE[k][1]):
                say(f"  [FIX] {kv!r}: use move=500, exercise=30, stand=12, steps=8000 or sleep=7.5")
                return 2
            g[k] = x
        M.write_json(gp, g)
        say(f"  [OK]  goals saved: {', '.join(f'{k} {v:g}' for k, v in sorted(g.items()))}")
    if a.imp:
        try:
            rep = import_export(a.imp, env, a.days, now_s)
        except (Refused, OSError, zipfile.BadZipFile, expat.ExpatError) as e:
            say(f"  [FIX] not imported: {e.__class__.__name__}: {str(e)[:160]}")
            return 2
        say(f"  [OK]  imported {rep['days']} days ({rep['first']} to {rep['last']}, {rep['records']:,} records) in {rep['seconds']} s -> {rep['file']}")
    doc = build_and_write(now_s, env)
    say(card_text(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
