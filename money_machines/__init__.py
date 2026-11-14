"""MONEY MACHINES (team F1, 2026-11-14): more honest ways to make money next to the trading bots and the agency kit.

Owner: "I want more money making machines ... freelance work automatically, or Instagram accounts." The plan, numbers and
rules are in docs/MONEY_MACHINES.md (one table first). The tools here PREPARE work; the owner stays the person who signs up,
talks to clients, presses Deliver / Post / Publish and checks every result. Nothing here bids, scrapes, auto-messages or
fakes a review, and nothing reaches the network unless the owner runs a live command with his own token.

    python -m money_machines.gig_pack --check          the 8 freelance gigs (docs/GIG_PACK.md) and which tool delivers each
    python -m money_machines.brand_kit --name ... --industry ... --out DIR      logo + brand kit from code (SVG)
    python -m money_machines.content_plan --account local_growth --render        30-day Instagram plan: captions + images
    python -m money_machines.ig_post --plan money_machines/plans/local_growth_30d.json --image-base-url URL   dry run (default)
    python -m money_machines.products.build_eval_tracker --zip                    the eval tracker upload zip (digital product)
    python -m money_machines.products.build_all --zip                             all 5 product zips (tracker, site templates, social kit, agency kit, trader planner)

Tests: python -X utf8 -m tests.test_money_machines   (no network; the image and product renders are skipped without Chromium)
       python -X utf8 -m tests.test_digital_products  (the 4 team-D2 products: files, zips, covers, links, brand names, promises)
"""
from __future__ import annotations

import os

__version__ = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("MONEY_MACHINES_OUT") or os.path.join(HERE, "out")       # gitignored: client orders, rendered images, ledgers
