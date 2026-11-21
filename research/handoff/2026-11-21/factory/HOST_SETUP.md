# Put the business sites on their own neutral web address (5 minutes, free)

**Why:** today the 67 sample sites live on your personal GitHub Pages, next to Olympus. A business owner who gets a postcard should
land on a plain, separate address that has nothing to do with you, your trading or your accounts. Do this once, before any postcard is mailed.

**Pick a neutral name first** (you'll use it twice). Not your name, not Olympus. Example: `mainstreet-sites` or `frederick-web-studio`.

---

## Option A (recommended): a separate GitHub organization: free, works from the iPhone, updates itself

1. **iPhone Safari** -> `github.com/organizations/plan` (you're already signed in to GitHub).
2. Tap **Create a free organization**.
3. **Organization account name:** your neutral name (e.g. `mainstreet-sites`). **Contact email:** your usual one (GitHub keeps it private). **Belongs to:** *My personal account*. Tick the terms, tap **Next**, then **Skip this step** on the "add members" page.
4. In the new organization tap **Create a new repository** (or go to `github.com/new` and pick the organization as Owner).
   - **Repository name:** `<your-org-name>.github.io` exactly (e.g. `mainstreet-sites.github.io`). That makes the address `https://mainstreet-sites.github.io/`.
   - **Public**. Tick **Add a README file**. Tap **Create repository**.
5. Let Claude publish to it: open `github.com/apps/claude/installations/select_target` -> pick the **new organization** -> **Only select repositories** -> pick the new repository -> **Install**.
6. Tell the lead (one line, copy-paste and fill in):
   ```
   Neutral host ready: https://mainstreet-sites.github.io/ (repo mainstreet-sites/mainstreet-sites.github.io)
   ```
   The lead puts that address in `tools/site_factory_agency.json` as `public_base`, runs `python tools/site_factory.py --export`, and pushes the site there.
7. About 1 minute later, open `https://mainstreet-sites.github.io/` on the phone: you should see a plain "Local web studio" page. A sample site is at `.../f/<code>/`, and the private list on Olympus links to each one.

GitHub Pages turns itself on for a repository named `<org>.github.io`. If the page doesn't appear after 5 minutes: in the repository tap **Settings -> Pages -> Source: Deploy from a branch -> main / (root) -> Save**.

---

## Option B: Cloudflare Pages: free, a `*.pages.dev` address, no GitHub organization in the address

Needs the PC once (the upload page wants a folder; the iPhone can't pick a folder).

1. **PC browser** -> `dash.cloudflare.com/sign-up` -> email + password -> verify the email. Free plan, no card.
2. On the PC, in the Olympus folder, run (copy-paste):
   ```
   python tools/site_factory.py --export C:\neutral-site
   ```
   (The first time it says *refused: set public_base* because the address doesn't exist yet. Do step 3, then come back and run it again.)
3. Cloudflare dashboard -> **Workers & Pages** -> **Create** -> **Pages** tab -> **Upload assets**.
   - **Project name:** your neutral name (e.g. `mainstreet-sites`). That gives `https://mainstreet-sites.pages.dev/`.
   - Tell the lead that address. The lead sets `public_base`, then you run the export line from step 2 again.
   - Drag the folder `C:\neutral-site` onto the upload box -> **Deploy site**.
4. Open `https://mainstreet-sites.pages.dev/` on the phone and check that the plain studio page shows.

Each later update (new towns, your phone number added) means running step 2 again and dragging the folder in again (**Create new deployment**).
Option A has no repeat step: Claude pushes the updates.

---

## What the export guarantees (checked by `tests/test_site_factory.py`)

- It **refuses** without `public_base`, or if the address is your GitHub Pages, Olympus or a PC address. It writes nothing then.
- Nothing in the exported site points back at Olympus, your GitHub name, Jarvis, ntfy or any PC/Tailscale address. If anything does, the export stops before writing.
- The sample sites stay hidden from Google (noindex + robots). The landing page also stays hidden until you give the agency a name (`agency_name`).
- Your private list of sites stays on Olympus. It is not part of the export.

## Still yours to decide (then tell the lead)

| What | Where it goes | Until then |
|---|---|---|
| Agency name | `agency_name` | landing says "Local web studio", hidden from Google |
| Agency phone (the AI receptionist answers) | `phone`, `phone_label` | "number coming" |
| Payment link (e.g. a Stripe Payment Link) | `pay_url` | "Claim this site: call us" |
