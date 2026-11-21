# The "yes" playbook: from "I'm interested" to money the same day

Who: **Caller** (human commission caller), **AI** (the receptionist, when on), **Claude** (cloud/PC), **Owner** (you).

| # | Step | Who | How long | Tools (all free) |
|---|---|---|---|---|
| 1 | **The call:** the business says yes to the link or a 10-min call. Logged "Interested" / "Booked a call" in the portal | Caller (or the AI receptionist on an inbound call) | 5 min | Caller portal, agency Gmail |
| 2 | **Same hour:** email the concept-site link + prices + the agreement (SERVICES_AGREEMENT.md filled in as a Google Doc, "anyone with the link can view") + the deposit link | Claude drafts, Owner clicks Send (or the autopilot sends it, as its own links are allowed) | 2 min of owner time | Gmail, Google Docs, Stripe Payment Link |
| 3 | **The 10-min call** (only if they booked one): answer questions, agree on Option A ($1,500, 50/50) or B ($149/mo) | Owner | 10 min | Phone |
| 4 | **Agreement:** client replies "I agree" (or signs the Doc) | Client | same day | Email = the record |
| 5 | **Deposit:** $750 (+3% MD tax if it applies) through the Stripe link (bank = $5 fee), or Zelle. Receipt the same day | Client pays; Claude drafts the receipt | minutes | Stripe (auto receipt) / receipt template |
| 6 | **Intake:** send the intake page link `.../agency/intake/?code=<FR-code>`; the client fills it on their phone and attaches logo + photos to the email it opens | Client | 10 min | Intake page (mailto, no backend) |
| 7 | **Build:** save the email's JSON block as `edits.json`, photos in a folder, add their paths, run `python tools/client_deliver.py <FR-code> edits.json` | Claude | under 1 h | client_deliver.py (static bundle) |
| 8 | **Review:** send the preview, take up to 2 rounds of changes | Owner forwards; Claude edits | 1-3 days (client speed) | Email |
| 9 | **Launch:** the launch payment ($750) first, then the domain DNS (PUBLISH.md in the bundle) on free hosting (GitHub Pages or Cloudflare Pages); add the Privacy + Terms pages | Claude prepares; Client or Owner does the DNS login (their account, their password) | 30 min | Domain registrar, free hosting |
| 10 | **Care plan:** start the $79/month Stripe link on launch day; monthly checklist (CARE_PLAN.md in the bundle); small edits up to 30 min a month | Claude; Owner approves anything bigger | 30-45 min a month | Stripe Billing, CARE_PLAN.md |

**Day 0 money:** the $750 deposit usually arrives the day of the "yes" if the email in step 2 goes out within the hour. Each step waits only
for the client.
**Total owner time per client:** about 30-45 minutes (send, one call, DNS help if needed), the rest is Claude.

**Hard rules on the way:** no work before the deposit (Option A) or the first $149 (Option B); the domain and logins stay in the client's
name; no promises of rankings or sales; any extra is quoted in writing first; a "no" at any step = never contacted again.

## Files
- `SERVICES_AGREEMENT.md`: the one-page agreement (template, not legal advice)
- `PAYMENTS_INVOICES.md`: Stripe / Square / Zelle steps and fees, invoice + receipt templates, the Maryland 3% tech-services tax check
- `CLIENT_SITE_PRIVACY_TERMS.md`: privacy policy + terms for client sites (contact form only)
- `tools/web_public/agency/intake/`: the intake page (fields = client_deliver.py edits.json)
