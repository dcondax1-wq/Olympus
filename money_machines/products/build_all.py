"""Make every digital product's upload zip in one go (plain Python, works on the Windows PC):

    python -m money_machines.products.build_all --zip      -> money_machines/out/products/*.zip (8 zips) + where each cover and listing is

The products: the Prop Eval Tracker (team F1) and the website templates, social media kit, agency starter kit and trader planner
(team D2). Each also has its own script (python -m money_machines.products.build_<name> --zip). Prices, fees and the listing text:
each product's shop/listing.md; the plan: docs/MONEY_MACHINES.md section 3.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

MODULES = ["build_eval_tracker", "build_site_templates", "build_social_kit", "build_agency_kit", "build_trader_planner", "build_prop_kit"]
# build_prop_kit (night team B, 2026-11-16) makes three zips: the eval risk calculator, the rules cheat sheet and the prop trader bundle


def zips() -> list:
    out = []
    for name in MODULES:
        m = importlib.import_module(f"money_machines.products.{name}")
        if hasattr(m, "zips"):                       # one module, several products
            for which, z in zip(m.LISTINGS, m.zips()):
                out.append((m.LISTINGS[which]["id"], z, m.DIRS[which]))
            continue
        z = m.make_zip()
        shop = getattr(m, "SHOP", None) or getattr(m, "PROD", "")
        out.append((name.replace("build_", ""), z, shop))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_all")
    ap.add_argument("--zip", action="store_true", help="make the 8 upload zips (the default)")
    ap.parse_args(argv)
    for name, z, shop in zips():
        print(f"{name:16} {os.path.getsize(z) // 1024:>6} KB  {z}")
        print(f"{'':16}         covers + listing.md: {shop}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
