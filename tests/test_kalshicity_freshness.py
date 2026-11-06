"""Read-only status freshness checks for Kalshi City (no trader imports)."""
from __future__ import annotations

import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "tools", "web_public", "kalshicity", "cityfeed.js")


class FeedStatus(unittest.TestCase):
    def test_running_and_paused_need_a_recent_timestamp(self):
        script = r'''
import { pathToFileURL } from 'node:url';
const { shape, BOT_FEED_MAX_AGE_S, worldBotLabel } = await import(pathToFileURL(process.argv[1]).href);
const now = 1800000000;
const base = { t: now - 100, edges: [], book: { feed_t: now - 100, running: true, status: 'Running' }, regime: { state: 'clear' } };
const live = (t, running, status) => ({ kind: 'kalshi', t, running, status, balance: 42 });
const fresh = shape(base, null, live(now - 90, true, 'Running'), now);
const olderBase = { ...base, book: { ...base.book, feed_t: now - BOT_FEED_MAX_AGE_S - 1 } };
const stopped = shape(base, null, live(now - 90, false, 'Stopped'), now);
const paused = shape(base, null, live(now - 90, false, 'Paused'), now);
const stoppedUnclear = shape(base, null, live(now - 90, false, 'Quiet'), now);
const staleRun = shape(olderBase, null, live(now - BOT_FEED_MAX_AGE_S - 1, true, 'Running'), now);
const stalePause = shape(olderBase, null, live(now - BOT_FEED_MAX_AGE_S - 1, false, 'Paused'), now);
const missing = shape({ ...base, book: { running: true, status: 'Running' } }, null, null, now);
console.log(JSON.stringify({ max: BOT_FEED_MAX_AGE_S,
  fresh: [fresh.book.statusFresh, fresh.book.running, fresh.book.status],
  labels: [worldBotLabel(fresh.book), worldBotLabel(paused.book), worldBotLabel(stopped.book), worldBotLabel(stoppedUnclear.book), worldBotLabel(stalePause.book), worldBotLabel(missing.book), worldBotLabel(fresh.book, true), worldBotLabel(stalePause.book, true)],
  staleRun: [staleRun.book.statusFresh, staleRun.book.running, staleRun.book.status, staleRun.book.lastStatus],
  stalePause: [stalePause.book.statusFresh, stalePause.book.running, stalePause.regime.paused, stalePause.book.lastStatus],
  missing: [missing.book.statusFresh, missing.book.running, missing.book.status] }));
'''
        proc = subprocess.run(["node", "--input-type=module", "-e", script, MODULE],
                              capture_output=True, text=True, timeout=20, check=True)
        result = json.loads(proc.stdout.strip())
        self.assertEqual(result["max"], 900)
        self.assertEqual(result["fresh"], [True, True, "Running"])
        self.assertEqual(result["labels"], ["BOT RUNNING", "BOT PAUSED", "BOT STOPPED", "BOT NOT RUNNING", "BOT STATUS UNKNOWN", "BOT STATUS UNKNOWN", "DEMO DATA", "DEMO DATA"])
        self.assertEqual(result["staleRun"], [False, None, "Status unverified", "Running"])
        self.assertEqual(result["stalePause"], [False, None, False, "Paused"])
        self.assertEqual(result["missing"], [False, None, "Status unverified"])


if __name__ == "__main__":
    unittest.main()
