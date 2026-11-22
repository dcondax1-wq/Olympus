# Overture check of the website leads (2026-11-21)

`python tools/web_leads_overture.py` (latest Overture release 2026-11-18.0, DuckDB + anonymous S3, ~5 s download + ~50 s of site checks).

| what | result |
|---|---|
| Original 1,577 leads | **710 already have a working site** (own domain + it answers) -> `website` set, off the call lists, in `agency/leads/redesign.json` (676 with a phone) for a redesign / audit offer. **97 site_down** (own domain, does not load) -> lane `site_down`. 770 still no site. |
| Yesterday's first 100 | 42 had a working site (the opener was false), 6 site down, 52 no site: matches the money sweep. |
| Phones | **990 leads got a phone** from Overture (strict name match only). |
| New leads | **2,961 new** no-website places with a phone in the 16 towns (open, not a chain/brand, a trade we sell to; churches, parks, schools, offices, closed places dropped). |
| Now | 4,538 leads, **3,826 concept sites** (3,415 with a phone; was 138), shared `f/site.css` (repo 60 MB -> 28 MB), caller list 3,827 (`agency.portal build`), first 100 re-ranked: 96 no_site + 4 site_down, each with an opener line. |
| Honesty / privacy | Overture emails never read; credit "OpenStreetMap contributors (ODbL) and Overture Maps Foundation (CDLA-Permissive-2.0 / ODbL)" on the town files, first100 and redesign list; the do-not-call scrub (portal never-again + agency/calls opt-outs / registry-listed numbers) applies on the PC. |
| Tests | test_leads_overture 13/13 (fixture parquet), test_site_factory 28/28, test_factory2 22/22, test_web_portal 54/54, test_web_leads 42/42, smoke 11/11; added to run_area agency. |

Caveats: a site check is one fetch from a cloud machine; 403/429 count as "up" (the site blocks robots). The site_down opener is soft ("it didn't load for me").
