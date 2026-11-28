"""NinjaTrader state save, durable (day-moneyaudit / red team #47, 2026-11-27): ATLAS funded's and the 25K #2 combo lane's state
files were BOTH unreadable at the Thu Nov 26 22:01:57 ET restart -> STARTUP DISARMED all of Nov 27 (S/R +$304 x 2 missed). The
save wrote .tmp + replace without flush / fsync: an unclean shutdown can leave the renamed file empty / NUL.

    python -X utf8 -m tests.test_nt_state_save          # ~3 s, temp folders only, nothing routed

  1. a save that changes what a restart needs (legs / watch / state_problem ...) is flushed + fsynced and refreshes <state>.bak
  2. a save where only the clock / seen_pos moved: no fsync; nothing but saved_at changed: no write at all (cheaper than before)
  3. a crash mid-write (the dump or the replace dies): the old good file is still the state file, never a torn one
  4. a NUL-filled state file + a good .bak (no order placed since): restored from the .bak, NO STARTUP DISARMED
  5. ... the .bak holds an open bracket: restored OPEN (never flat)
  6. ... an order was PLACEd after the .bak (audit log): not trusted -> the old hold ("unreadable", entries blocked)
  7. ... no .bak / a torn .bak: the old hold, unchanged
  8. perf: 2,000 polls' saves with only the clock moving cost < 0.5 s and write the file once
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import ninjatrader as N  # noqa: E402

RES = []
T0 = 1795742000                       # Thu 2026-11-26 ~20:33 ET (the CME day of Fri Nov 27)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def make(root, tag, now=None):
    base = os.path.join(root, tag)
    fold = os.path.join(base, "NinjaTrader 8")
    N._FakeNT(fold)
    clk = [float(now or T0)]
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": "Sim102", "nt_folder": fold, "params": {"max_micros": 20, "flat_mod": 955},
           "nt_state_path": os.path.join(base, "st.json"), "nt_audit_log": os.path.join(base, "oif.log"), "nt_session_from": 120}
    return (lambda: N.NinjaTraderAdapter(cfg, clock=lambda: clk[0])), cfg, clk


LEG = {"instrument": "MNQ 12-26", "qty": 1, "side": "BUY", "dir": 1, "entry_t": T0 - 600, "stop": 26210.75, "target": 26440.25,
       "status": "protected", "entry_id": "E1", "stop_id": "S1", "target_id": "T1", "filled": 1}


def count_fsync():
    n = [0]
    real = os.fsync

    def f(fd):
        n[0] += 1
        return real(fd)
    return n, real, f


def part1_2(root):
    new, cfg, clk = make(root, "a")
    ad = new()
    n, real, f = count_fsync()
    os.fsync = f
    try:
        ad.legs = [dict(LEG)]
        ad._save()
        st, bak = json.load(open(cfg["nt_state_path"])), json.load(open(cfg["nt_state_path"] + ".bak"))
        check("1. a new open bracket: saved + fsynced (state and .bak), the .bak = the same legs + its wall time",
              n[0] == 2 and st["legs"] == bak["legs"] == [LEG] and bak.get("saved_wall"), (n[0], bak.get("saved_wall")))
        m0 = os.stat(cfg["nt_state_path"]).st_mtime_ns
        clk[0] += 30
        ad._save()
        check("2. only the clock moved: no write at all (the file is unchanged), no fsync",
              n[0] == 2 and os.stat(cfg["nt_state_path"]).st_mtime_ns == m0 and json.load(open(cfg["nt_state_path"]))["saved_at"] == int(T0))
        ad.seen_pos = {"MNQ 12-26": {"side": "LONG", "qty": 1}}
        ad._save()
        check("2. seen_pos changed (not needed by a restart): written, not fsynced", n[0] == 2
              and json.load(open(cfg["nt_state_path"]))["seen_pos"], n[0])
        ad.legs[0]["status"] = "closing"
        ad._save()
        check("2. the bracket moved to closing: fsynced again (state + .bak)", n[0] == 4
              and json.load(open(cfg["nt_state_path"] + ".bak"))["legs"][0]["status"] == "closing", n[0])
    finally:
        os.fsync = real


def part3(root):
    new, cfg, clk = make(root, "b")
    ad = new()
    ad.legs = [dict(LEG)]
    ad._save()
    good = open(cfg["nt_state_path"]).read()
    real_dump = json.dump

    def dies(obj, fh, **kw):
        fh.write('{"version": 1, "legs": [{"instr')
        raise KeyboardInterrupt("power cut mid-write")
    json.dump = dies
    try:
        ad.legs[0]["status"] = "closing"
        try:
            ad._save()
        except KeyboardInterrupt:
            pass
    finally:
        json.dump = real_dump
    check("3. killed mid-dump: the state file is still the last good one (the torn bytes only in .tmp)",
          open(cfg["nt_state_path"]).read() == good and json.load(open(cfg["nt_state_path"]))["legs"][0]["status"] == "protected")
    import engine.fsutil as F
    real_rep = F.replace

    def no_rep(a, b, **kw):
        raise KeyboardInterrupt("killed before the rename")
    F.replace = no_rep
    try:
        ad.legs[0]["status"] = "closing"
        ad._saved_crit = None
        try:
            ad._save()
        except KeyboardInterrupt:
            pass
    finally:
        F.replace = real_rep
    check("3. killed before the replace: the old good file stays", open(cfg["nt_state_path"]).read() == good)


def torn(path):
    open(path, "wb").write(b"\x00" * 600)


def part4_7(root):
    new, cfg, clk = make(root, "c")
    ad = new()
    ad.legs = []
    ad._save()
    torn(cfg["nt_state_path"])
    ad2 = new()
    check("4. NUL state file + a good .bak (flat, no order since): restored, NO STARTUP DISARMED", ad2.state_problem is None
          and ad2.legs == [] and any(f.startswith("st.json.corrupt-") for f in os.listdir(os.path.dirname(cfg["nt_state_path"]))),
          ad2.state_problem)
    new, cfg, clk = make(root, "d")
    ad = new()
    ad.legs = [dict(LEG)]
    ad._save()
    torn(cfg["nt_state_path"])
    ad2 = new()
    check("5. NUL state file + a .bak holding an open bracket: restored OPEN (never flat), no hold",
          ad2.state_problem is None and len(ad2.legs) == 1 and ad2.legs[0]["status"] == "protected", (ad2.state_problem, ad2.legs))
    new, cfg, clk = make(root, "e")
    ad = new()
    ad.legs = []
    ad._save()
    time.sleep(1.1)
    stamp = N._et(time.time()).strftime("%Y-%m-%d %H:%M:%S")
    with open(cfg["nt_audit_log"], "a") as fh:
        fh.write(f"{stamp} ET  Sim102  ENTRY  PLACE;Sim102;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;E9;;\n")
    torn(cfg["nt_state_path"])
    ad2 = new()
    check("6. an order PLACEd after the .bak: the .bak is not trusted -> the old hold (unreadable, entries blocked)",
          ad2.state_problem is not None and "unreadable" in ad2.state_problem["text"], ad2.state_problem)
    new, cfg, clk = make(root, "f")
    ad = new()
    ad._save()
    os.remove(cfg["nt_state_path"] + ".bak")
    torn(cfg["nt_state_path"])
    check("7. no .bak: the old hold, unchanged", new().state_problem is not None)
    new, cfg, clk = make(root, "g")
    ad = new()
    ad._save()
    torn(cfg["nt_state_path"])
    torn(cfg["nt_state_path"] + ".bak")
    check("7. a torn .bak too: the old hold", new().state_problem is not None)


def part8(root):
    new, cfg, clk = make(root, "h")
    ad = new()
    ad.legs = [dict(LEG)]
    ad._save()
    m0 = os.stat(cfg["nt_state_path"]).st_mtime_ns
    t = time.perf_counter()
    for _ in range(2000):
        clk[0] += 1
        ad._save()
    dt_ = time.perf_counter() - t
    check(f"8. 2,000 clock-only saves: {dt_:.2f} s, the file written once", dt_ < 0.5 and os.stat(cfg["nt_state_path"]).st_mtime_ns == m0, dt_)
    # red team #47: an unchanged state is still rewritten every SAVE_EVERY_S (autoupdate ignores a state file untouched 24 h)
    ad._saved_wall_t = time.time() - ad.SAVE_EVERY_S - 1
    time.sleep(0.02)
    ad._save()
    check("8. rt: unchanged but older than SAVE_EVERY_S: rewritten (mtime fresh for the update's flat check)",
          os.stat(cfg["nt_state_path"]).st_mtime_ns != m0)


def main():
    root = tempfile.mkdtemp(prefix="ntsave_")
    try:
        for fn in (part1_2, part3, part4_7, part8):
            try:
                fn(root)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} raised {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if RES and all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
