"""What the caller costs per month at 50 / 200 / 500 dials a weekday. Prices checked 2026-11-20 (sources in the writeup);
the rates marked GUESS are ours, not measured. python -m tools.caller.cost [--model claude-haiku-5-5] [--md]
"""
from __future__ import annotations

import argparse
import sys

PRICES = {                       # USD, list prices
    "voice_out_min": 0.014,      # Twilio Programmable Voice, outbound to US numbers
    "voice_in_min": 0.0085,      # Twilio, inbound to a local number
    "relay_min": 0.07,           # Twilio ConversationRelay (speech-to-text + text-to-speech), on top of voice
    "lookup": 0.008,             # Twilio Lookup v2 Line Type Intelligence, per number (cached 30 days)
    "number_month": 1.15,        # Twilio local number
}
MODELS = {                       # $ per million tokens: input, cache read, output (Claude API, 2026-11)
    "claude-opus-5-5": (4.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 0.10, 10.00),
    "claude-haiku-5-5": (0.10, 0.01, 0.50),
}
ASSUME = {                       # per dial
    "connect": 0.40,             # GUESS for consented callbacks (cold B2B benchmarks: 5-10% per dial)
    "voicemail": 0.20,           # GUESS: answered by a machine, hung up at once (no AI voicemail)
    "talk_min": 3.0,             # GUESS: a connected call
    "vm_min": 0.5,
    "turns_per_min": 4,
    "in_tokens_uncached": 1600, "in_tokens_cached": 900, "out_tokens": 160,     # per turn, incl. low-effort thinking
    "book_of_connect": 0.25,     # GUESS for people who asked us to call
    "close_of_booked": 0.30,     # GUESS
    "sale_setup": 1500, "sale_monthly": 79,     # agency/offers/offers.json Starter
    "lookup_share": 0.5,         # half the dials are follow-ups or cached numbers
    "weekdays": 22,
}


def per_dial(model: str) -> dict:
    pi, pc, po = MODELS[model]
    a = ASSUME
    turn = (a["in_tokens_uncached"] * pi + a["in_tokens_cached"] * pc + a["out_tokens"] * po) / 1e6
    llm_min = turn * a["turns_per_min"]
    talk = a["connect"] * a["talk_min"] * (PRICES["voice_out_min"] + PRICES["relay_min"] + llm_min)
    vm = a["voicemail"] * a["vm_min"] * (PRICES["voice_out_min"] + PRICES["relay_min"])
    look = a["lookup_share"] * PRICES["lookup"]
    return {"all_in_min": PRICES["voice_out_min"] + PRICES["relay_min"] + llm_min, "llm_min": llm_min, "per_dial": talk + vm + look}


def table(model: str = "claude-opus-5-5", per_day=(50, 200, 500)) -> list:
    d = per_dial(model)
    a = ASSUME
    rows = []
    for n in per_day:
        dials = n * a["weekdays"]
        cost = dials * d["per_dial"] + PRICES["number_month"]
        booked = dials * a["connect"] * a["book_of_connect"]
        sales = booked * a["close_of_booked"]
        rows.append({"per_day": n, "dials_month": dials, "cost": cost, "booked": booked, "sales": sales,
                     "revenue_first_month": sales * (a["sale_setup"] + a["sale_monthly"]), "cost_per_booking": cost / booked if booked else 0})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-5-5", choices=list(MODELS))
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args(argv)
    d = per_dial(a.model)
    print(f"{a.model}: ${d['all_in_min']:.3f}/talk-minute all-in (Claude ${d['llm_min']:.3f}), ${d['per_dial']:.3f} per dial on average")
    if a.md:
        print("| dials/weekday | dials/month | cost/month | bookings (guess) | sales (guess) | first-month revenue (guess) | cost per booking |")
        print("|---|---|---|---|---|---|---|")
    for r in table(a.model):
        if a.md:
            print(f"| {r['per_day']} | {r['dials_month']:,} | ${r['cost']:,.0f} | {r['booked']:,.0f} | {r['sales']:,.0f} | "
                  f"${r['revenue_first_month']:,.0f} | ${r['cost_per_booking']:.2f} |")
        else:
            print(f"{r['per_day']:>4}/day  {r['dials_month']:>6,} dials  ${r['cost']:>8,.0f}/month  ~{r['booked']:,.0f} bookings  "
                  f"~{r['sales']:,.0f} sales  ~${r['revenue_first_month']:,.0f}  (${r['cost_per_booking']:.2f}/booking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
