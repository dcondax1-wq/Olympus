"""AGENCY BILLING (team B6 "get paid", 2026-11-14): close and collect for the local-business website agency.

Proposal -> agreement (template) -> numbered invoice -> payment recorded -> MRR / churn summary for the money pages.
Run `python -m agency.billing` for the commands. Real data lives in data/agency/ (gitignored); fixtures in agency/billing/fixtures/.
Payment set-up (Stripe Payment Links vs Square vs PayPal, fees, payout times, the owner's 3 steps): agency/billing/PAYMENTS.md.
Modules: core (pure maths), store (files, numbering, ledger), render (HTML / PDF), __main__ (the command line).
"""
VERSION = 1
