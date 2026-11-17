"""tools/kalshi_rewards_paper.py: offline selftest (stub API, no network, never an order).
    python -X utf8 -m tests.test_kalshi_rewards_paper
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import kalshi_rewards_paper as KR  # noqa: E402

if __name__ == "__main__":
    KR.selftest()
