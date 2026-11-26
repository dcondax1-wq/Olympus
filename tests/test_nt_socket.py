"""engine/nt_socket.py offline self-test (socket order bridge, PAPER prototype, big-execution 2026-11-26).
Run: python -X utf8 -m tests.test_nt_socket"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.nt_socket import selftest  # noqa: E402

if __name__ == "__main__":
    ok = selftest()
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)
