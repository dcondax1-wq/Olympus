"""Entry point of the "LiquidityEngineOps" scheduled task (scripts/install_ops_task.ps1 runs it with pythonw every 5 min).

Same as `python -X utf8 -m engine.ops_checks --tick`, from any working folder. Read-only helper: pushes the notices that
are due and makes the nightly backup; it never starts, stops, arms or routes anything. Never raises: errors go to
logs/ops-YYYYMMDD.log.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

if __name__ == "__main__":
    try:
        from engine import ops_checks
        sys.exit(ops_checks.main(["--tick"]))
    except Exception as e:                                  # pythonw has no console: log it
        try:
            os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
            with open(os.path.join(ROOT, "logs", "ops-crash.log"), "a", encoding="utf-8") as fh:
                fh.write(f"{e.__class__.__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(1)
