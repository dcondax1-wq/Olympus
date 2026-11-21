# Human caller (commission only): the owner's page

Everything is in `research/handoff/2026-11-21/caller/` (README first). In short:

- **Legal:** a person dialing by hand to business numbers, saying who they are, weekdays 9-5, no recordings (Maryland needs everyone's
  consent), 1 call + 1 follow-up, "no" = never again. No AI voice, no auto-dialer, no texts (Md. Com. Law 14-4502(a)(3)).
- **Cost:** $0 to hire (Indeed, Facebook groups, LinkedIn free posts). Pay = $300 per sale OR $40 per booked call that shows (one per business), only after the client's money clears; clawed back if refunded within 30 days (`python -m agency.portal paid <id> deposit|launch|refund`). By Zelle.
  W-9 from the caller; a 1099-NEC only if you pay them $2,000+ in 2026 (free e-file: IRS IRIS).
- **Do-Not-Call:** free for 5 area codes (301, 240, 227, 410, 443). `python -m agency.portal build` then `python -m agency.dnc_scrub`
  before every publish. Re-download every 31 days.
- **Expect (middle case, 2 weeks):** ~340 dials, ~10 interested, ~1 sale = $1,120 + $79/month to you after the commission. No sale in 2 weeks = change the
  niche, script or price.
