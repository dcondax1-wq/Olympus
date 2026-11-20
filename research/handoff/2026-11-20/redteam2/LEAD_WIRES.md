# LEAD_WIRES: red team 2 (2026-11-20, branch day-redteam2)

No bot file (engine/live.py, lit*.py, ninjatrader.py, second.py, account_b.py, autoupdate.py, notify.py, server.py, kalshi_*,
live_model*.json, ...) is touched. H1 + H2 are ALREADY COMMITTED on day-redteam2 in engine/fast_alarm.py (not on the
forbidden list; read-only alarm, the in-server watchdog thread calls it every 30 s inside its own try/except). L2 is a patch
for you to apply (engine/rapid.py is bot code).

| # | Rank | File | How to land | Test (red before, green after) |
|---|---|---|---|---|
| H1 | CRITICAL | engine/fast_alarm.py (halt_open) | merge day-redteam2 (commit 1) | `python -X utf8 -m tests.test_redteam2_live` (h1-h10; 6 red on pc) |
| H2 | HIGH | engine/fast_alarm.py (no_stop) | merge day-redteam2 (commit 2) | same file r1-r5 (3 red without it) |
| L2 | LOW | engine/rapid.py (_other_names) | `git apply research/handoff/2026-11-20/redteam2/patch_L2_rapid_names.diff` | `python -X utf8 -m tests.test_redteam2_wires` (1/2 before, 2/2 after) |

Please add both new test files to tests/run_area.py (area "pc" and "nq": `AREAS["pc"] += ["redteam2_live"]`,
`AREAS["nq"] += ["redteam2_live"]`; `redteam2_wires` after L2 lands). I did not edit run_area.py / STATE.md to keep the
merge clean: STATE line for you: "Half-day halt alarm (CLOSE THE TRADE NOW, 10 min before 13:00 / 13:15 ET when a real
trade is open and the bot is stopped) + TRADE HAS NO STOP alarm (redteam2)".

Timing: the PC takes the 16:00 ET update; H1 must be on pc before Wed 11-25 evening to cover Thanksgiving.

Checks run on the final code (this container): tests.test_redteam2_live 15/15, tests.test_nq_live_reliability 119/119 (the
fast alarm's own suite), python -m engine.ninjatrader --selftest EXIT 0, tests.test_holiday_replay 9/9, tests.test_holidays
19/19, tests.test_account_box 40/40, tests.test_multi_account --quick 49/49, tests.test_rapid 60/60, tests.test_rapid25 94/94,
tests.test_mffu_rules 55 ok / 0 FAIL / 3 WARN, tests.test_lit_live --quick OK (120/120 day-end trades identical, 489 intraday polls 0 differences, LiveBot 1/1 entries + exits, 0 errors), tests/smoke.py 7/8 (test_zenith_mode
needs the python playwright module, not in this container: unrelated). Not run: test_win_scripts (never), browser suites.

## H1 + H2: the engine/fast_alarm.py diff (vs origin/pc)

```diff
diff --git a/engine/fast_alarm.py b/engine/fast_alarm.py
index f10146d9..12cdcefd 100644
--- a/engine/fast_alarm.py
+++ b/engine/fast_alarm.py
@@ -44,8 +44,17 @@ REPEAT_S = 30 * 60                                    # the same condition again
 DAY_MAX = 6                                           # alarm pushes (starts) an ET day at most
 PERSIST_S = 5 * 60                                    # a held repeat that lasts this long is pushed anyway (not a blip)
 WIN_FROM, WIN_TO = 1 * 60 + 58, 15 * 60 + 55          # ET minutes, weekdays
-COND = {"bot_down": "bot_down", "feed_stale": "feed_stale", "bot_stopped": "bot_stopped"}   # -> tools/pc_report.py condition code
-TITLE = {"bot_down": "ZEUS not polling", "feed_stale": "FEED STALE", "bot_stopped": "Bot stopped"}
+COND = {"bot_down": "bot_down", "feed_stale": "feed_stale", "bot_stopped": "bot_stopped", "halt_open": "halt_open",
+        "no_stop": "no_stop"}   # -> pc_report code
+TITLE = {"bot_down": "ZEUS not polling", "feed_stale": "FEED STALE", "bot_stopped": "Bot stopped",
+         "halt_open": "CLOSE THE TRADE NOW", "no_stop": "TRADE HAS NO STOP"}
+NO_STOP_AGE_S = 60                                    # the state file's open leg is this old with the bot stopped
+# redteam2 2026-11-20: a CME half day (Thanksgiving 11-26 halt 13:00, 11-27 and 12-24 13:15 ET). MFFU does NOT auto-close at a
+# half-day halt ("the trader is responsible for closing the positions ... failure ... will result in breaching", help center
+# 'Permitted Times to Trade'); the adapter's own flat (halt - 5 min) only runs while the bot runs. A STOP, a crash / restart
+# that did not resume, or a refused CLOSEPOSITION leaves the broker position open into the halt = the account fails.
+HALT_WARN_MIN = 10                                    # bot NOT running: warn from halt - 10 min
+HALT_LATE_MIN = 4                                     # bot running: its own flat is at halt - 5; still open at halt - 4 = warn
 
 
 def enabled(env=None) -> bool:
@@ -70,6 +79,129 @@ def _span(s) -> str:
     return f"{s} s" if s < 120 else f"{s // 60} min"
 
 
+def _real_positions(folder) -> list:
+    """["SHORT 2 MNQ 12-26 on <acct ..1234>"] for every non-FLAT NinjaTrader position file of a NON-Sim account (outgoing/
+    <instrument>_<account>_Position.txt). Read-only, never raises."""
+    out = []
+    try:
+        from .ninjatrader import is_sim, parse_position
+        og = os.path.join(folder, "outgoing")
+        for n in sorted(os.listdir(og)):
+            if not n.lower().endswith("_position.txt"):
+                continue
+            parts = n[:-len("_position.txt")].rsplit("_", 1)
+            if len(parts) != 2 or not parts[0] or is_sim(parts[1]):
+                continue
+            try:
+                with open(os.path.join(og, n), encoding="utf-8-sig", errors="replace") as fh:
+                    pos = parse_position(fh.read())
+            except OSError:
+                continue
+            if pos and pos["side"] != "FLAT":
+                out.append(f"{pos['side']} {pos['qty']} {parts[0]} on account ..{parts[1][-4:]}")
+    except Exception:
+        pass
+    return out
+
+
+def no_stop(bot, now, folder=None, state_dir=None) -> str | None:
+    """redteam2 2026-11-20: the bot is NOT running and a state file of its NinjaTrader adapters (data/ninjatrader_state*.json:
+    LIT, ATLAS, account C, the extra accounts, the Rapid lanes) holds a leg whose entry went out but whose stop / target was
+    never placed ("entry_sent" / "pending" / "unprotected"), while NinjaTrader shows that real account in a position: a crash /
+    restart between the entry fill and the bracket that did not resume (an eval without auto-resume) = a trade with NO stop at
+    the broker. The restarted adapter places the bracket only once the bot runs again. Read-only, never raises."""
+    try:
+        if getattr(bot, "running", False):
+            return None
+        import glob
+        import json
+        from . import ninjatrader as NT
+        sd = state_dir or os.path.dirname(NT.STATE_PATH)
+        if folder is None:
+            folder = (getattr(bot, "cfg", None) or {}).get("nt_folder") or NT.default_folder()
+        og = os.path.join(folder, "outgoing")
+        out = []
+        for p in sorted(glob.glob(os.path.join(sd, "ninjatrader_state*.json"))):
+            if "simcheck" in os.path.basename(p):
+                continue
+            try:
+                with open(p, encoding="utf-8") as fh:
+                    st = json.load(fh)
+            except Exception:
+                continue
+            acct = str((st or {}).get("account") or "")
+            if not acct or NT.is_sim(acct) or st.get("day") != NT._trading_day(now):
+                continue                               # another day's file: the adapter itself ignores it
+            for lg in st.get("legs") or []:
+                if not isinstance(lg, dict) or lg.get("status") not in ("entry_sent", "pending", "unprotected"):
+                    continue
+                if now - float(lg.get("sent_at") or st.get("saved_at") or now) < NO_STOP_AGE_S:
+                    continue
+                inst = str(lg.get("instrument") or "")
+                suffix = f"_{acct.lower()}_position.txt"
+                try:
+                    names = [n for n in os.listdir(og) if n.lower().endswith(suffix)]
+                except OSError:
+                    names = []
+                for n in names:
+                    if not NT.same_instrument(n[:-len(suffix)], inst):
+                        continue
+                    try:
+                        with open(os.path.join(og, n), encoding="utf-8-sig", errors="replace") as fh:
+                            pos = NT.parse_position(fh.read())
+                    except OSError:
+                        pos = None
+                    if pos and pos["side"] != "FLAT":
+                        out.append(f"{pos['side']} {pos['qty']} {inst} on account ..{acct[-4:]}")
+        if not out:
+            return None
+        return ("The bot is stopped and " + "; ".join(out[:3]) + " has NO stop or target at the broker (the PC restarted between "
+                "the entry and its bracket). Start the bot (GO_LIVE_EVAL.bat: it places the stop at once) or close the trade in "
+                "NinjaTrader now.")
+    except Exception:
+        return None
+
+
+def halt_open(bot, now, folder=None) -> str | None:
+    """A broker position still open just before a CME early close (see HALT_WARN_MIN), else None. Only inside the last
+    HALT_WARN_MIN minutes before the halt of an early-close day (3 days a year here: no file read at any other time)."""
+    try:
+        from . import cme_calendar as C
+        e = dt.datetime.fromtimestamp(float(now), ET)
+        if e.weekday() >= 5 or e.hour >= 18:
+            return None
+        ec = C.early_close(e.date())
+        m = e.hour * 60 + e.minute
+        if ec is None or not (ec - HALT_WARN_MIN <= m < ec):
+            return None
+        running = bool(getattr(bot, "running", False))
+        if running and m < ec - HALT_LATE_MIN:
+            return None                                # the running bot flattens at halt - 5 itself
+        if folder is None:
+            folder = (getattr(bot, "cfg", None) or {}).get("nt_folder")
+        if not folder:
+            from .ninjatrader import default_folder
+            folder = default_folder()
+        pos = _real_positions(folder)
+        if not pos:
+            return None
+        return (f"CME closes early today at {ec // 60:02d}:{ec % 60:02d} ET and MFFU does NOT close trades on a half day: "
+                f"{'; '.join(pos[:3])} is still open" + ("" if running else " and the bot is stopped")
+                + ". Close it in NinjaTrader NOW (right-click the position > Close), or the account fails at the halt.")
+    except Exception:
+        return None
+
+
+def _halt_passed(now) -> bool:
+    try:
+        from . import cme_calendar as C
+        e = dt.datetime.fromtimestamp(float(now), ET)
+        ec = C.early_close(e.date())
+        return ec is not None and e.hour * 60 + e.minute >= ec
+    except Exception:
+        return True
+
+
 def evaluate(bot, now, server_started_at=None, autostart=None, run_seen=None) -> dict:
     """{code: text} of what stops the bot from taking a trade right now (empty outside the hours / for a paper bot). Pure.
     server_started_at / autostart (engine/watchdog: this server's start, data/autostart.json = the bot was running and nobody
@@ -77,6 +209,12 @@ def evaluate(bot, now, server_started_at=None, autostart=None, run_seen=None) ->
     out: dict = {}
     if bot is None:
         return out
+    ho = halt_open(bot, now)
+    if ho:
+        out["halt_open"] = ho                          # whatever else is wrong: this one costs the account
+    ns = no_stop(bot, now)
+    if ns:
+        out["no_stop"] = ns
     if not getattr(bot, "running", False):
         rec = autostart if isinstance(autostart, dict) else None
         acfg = (rec or {}).get("cfg") if isinstance((rec or {}).get("cfg"), dict) else None
@@ -145,7 +283,7 @@ class FastAlarm:
         if lp is not None and now - lp < REPEAT_S and not (since is not None and now - float(since) >= PERSIST_S):
             return f"held: {code} pushed {_span(now - lp)} ago"
         day = dt.datetime.fromtimestamp(float(now), ET).date().isoformat()
-        if int(self.day_n.get(day) or 0) >= DAY_MAX:
+        if int(self.day_n.get(day) or 0) >= DAY_MAX and code not in ("halt_open", "no_stop"):   # the account: never capped
             return f"held: {DAY_MAX} alarm pushes today already"
         return None
 
@@ -191,6 +329,8 @@ class FastAlarm:
                     done.append((key, r))
             for code in [c for c in self.active if c not in cur]:
                 a = self.active.pop(code)
+                if code == "halt_open" and (not a.get("sent") or _halt_passed(now)):
+                    continue                           # the halt came: "back to normal" would read as "it is closed"
                 if a.get("sent") and code in ("bot_down", "feed_stale") and not running:
                     # cleared because the bot was STOPPED (the owner's STOP / kill, often his answer to this alarm): never a
                     # "Back to normal: the bot polls again" (redteam 2026-11-20); a stop that should not be is "Bot stopped"
@@ -198,7 +338,9 @@ class FastAlarm:
                 if a.get("sent"):
                     key = f"fast:{code}:back:{int(now)}"
                     r = self.send({"key": key, "code": code, "cond": COND[code], "back": True, "title": "Back to normal",
-                                   "body": {"bot_down": "The bot polls again.", "bot_stopped": "The bot runs again."}.get(
+                                   "body": {"bot_down": "The bot polls again.", "bot_stopped": "The bot runs again.",
+                                            "halt_open": "NinjaTrader shows the account flat before the halt.",
+                                            "no_stop": "The bot runs again (it places the stop at its first poll) or the trade is closed."}.get(
                                        code, "NinjaTrader bars are fresh again.")
                                    + f" It was out for {_span(now - a['since'])}.", "tags": "white_check_mark"})
                     done.append((key, r))
```

## L2: engine/rapid.py

```diff
diff --git a/engine/rapid.py b/engine/rapid.py
index 8fd25873..52d30f12 100644
--- a/engine/rapid.py
+++ b/engine/rapid.py
@@ -148,6 +148,13 @@ def _other_names() -> dict:
         out["ATLAS (25K)"] = out["ATLAS (25K)"] or (AB.raw_cfg() or {}).get("account")
     except Exception:
         pass
+    try:                       # redteam2 2026-11-20: the extra accounts too (Zlarior 25K #2, account C), as account_cli does
+        from . import account_cli
+        for r in account_cli.inventory():
+            if r.get("role") not in ("main", "b", "rapid") and r.get("name"):
+                out.setdefault(f"the account {r.get('id')}", r["name"])
+    except Exception:
+        pass
     return out
 
 
```
