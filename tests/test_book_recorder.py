"""Book recorder (tools/kalshi_kit/public/book_recorder.py) and the stop-list builder: stubbed API, no network.
    python -X utf8 -m tests.test_book_recorder"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True
for name, cmd in (("book_recorder selftest", ["tools/kalshi_kit/public/book_recorder.py", "--selftest"]),
                  ("suggestions builder selftest", ["tools/kalshi_suggestions_build.py", "--selftest"]),
                  ("suggestions files up to date", ["tools/kalshi_suggestions_build.py", "--check"])):
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, cmd[0])] + cmd[1:], capture_output=True, text=True, timeout=120)
    good = r.returncode == 0
    ok &= good
    print("[%s] %s %s" % ("PASS" if good else "FAIL", name, "" if good else r.stdout[-300:] + r.stderr[-300:]))
src = open(os.path.join(ROOT, "tools", "kalshi_kit", "public", "book_recorder.py"), encoding="utf-8").read()
safe = "POST" not in src and "KALSHI-ACCESS" not in src and "private" not in src.lower().replace("private scratch", "")
ok &= safe
print("[%s] recorder is GET-only and reads no key" % ("PASS" if safe else "FAIL"))
sys.exit(0 if ok else 1)
