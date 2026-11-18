# The "Powered by Netlify" badge, and moving the phone site (2026-11-18)

## Why the badge shows
- It is **Netlify's own badge**, not our code. Since 2026-08-19 every NEW public project on Netlify's Free plan starts with it
  on (projects made before that date have it off). Our site moonlit-scone-08afe5 was made in November with Netlify Drop, so it
  has it. Netlify injects it when the page is served (a script at `/.netlify/scripts/hud` that opens a small box,
  `#nl-badge-frame`, bottom right). Source: docs.netlify.com/manage/projects/powered-by-netlify-badge, and Netlify's changelog for
  2026-08-19.
- **Not a preview or draft problem.** `tools/pc_publish.py` sends to production: `POST /sites/<id>/deploys` without
  `"draft": true`, then waits until the deploy is `ready`. The built pages contain no badge and no "Powered by" text. Netlify's
  other overlay (the "pre-launch toolbar") only appears on private projects on paid credit plans.
- Netlify's docs say turning the badge off **"depends on your plan"**, and that upgrading to Personal or Pro unlocks the
  switch if it is locked. Other people say the switch is locked on Free. No paid plan here.

## Fastest fix on the phone (free, try in this order)
1. app.netlify.com > the project **moonlit-scone-08afe5** > **Project configuration** > **General** > **Powered by Netlify
   badge** > Off > **Save**. This works straight away, no new deploy needed. If the switch is grey (locked), go to 2.
2. On your own phone: tap the badge > **Hide this badge**. It stays hidden in that browser. Safari forgets it if you skip the
   site for 7 days.
3. A workaround for everyone who opens the site: **Project configuration** > **Developer settings** > **Post processing** >
   **Snippet injection** > **Add snippet**, choose "Before `</head>`", name it `hide badge`, paste this line, then **Save**:
   `<style>#nl-badge-frame,.nl-badge{display:none!important}</style>`
   This is a workaround that other sites use, not a Netlify setting. Netlify can rename the box, and then the badge comes
   back. Netlify's docs don't say whether Free includes snippet injection.

## Free hosts compared
| Host | Badge | Cost | Updates | Privacy | Verdict |
|---|---|---|---|---|---|
| **Cloudflare Pages** | None | Free | 500 a month (we use at most 450 = 15 a day) vs Netlify's ~18 a month | Public link, same as Netlify | **Built (OFF until you switch it on)** |
| GitHub Pages | None | Free only with a PUBLIC repo | Every push | The whole repo and its history would be public forever. The old account was suspended 11-08 | No |
| Vercel (Hobby) | Toolbar on preview deploys only, can be turned off | Free, non-commercial use only | ~100 a day | Public link | Works, but needs the same Node.js and an extra account. Not built |
| Your Oracle VM (`--setup scp`) | None | Free | No limit | Your own server | Already built (docs/HOSTING_OPTIONS.md) |

Privacy is the same as Netlify: the same lite set leaves the PC, private files stay home (`deploy_set`), and the build
removes ids, emails and names (docs/PRIVACY.md).

## Move to Cloudflare Pages (3 steps, one time)
1. **Get the key (phone or PC):** dash.cloudflare.com, sign up free > your picture > **Profile** > **API Tokens** >
   **Create Token** > **Custom token** > Permissions: *Account* / *Cloudflare Pages* / *Edit* > **Continue** > **Create**.
   Copy the key. Also copy your **Account ID** (Workers & Pages page, right side). Never paste the key in a chat or the repo.
2. **On the PC:** install Node.js free with `winget install OpenJS.NodeJS.LTS`. Then open the variables window with
   `rundll32 sysdm.cpl,EditEnvironmentVariables` and add two **User variables** with **New**: `CLOUDFLARE_API_TOKEN` = the key,
   `CLOUDFLARE_ACCOUNT_ID` = the account id. The key lives only there. Sign out and back in once.
3. **Switch on:** `python tools/pc_publish.py --setup cloudflare --cf-project olympus-dash` and then
   `python tools/pc_publish.py --force`. The site is now at **https://olympus-dash.pages.dev** (pick another name if that one
   is taken). Add it to your home screen. To go back: `python tools/pc_publish.py --setup netlify --site-name moonlit-scone-08afe5 --token-stdin`.

How it works: `publish_cloudflare` in `tools/pc_publish.py` copies only the files that go out into `data/pc_publish/cf_site`.
It then runs Cloudflare's own `npx wrangler@4.156.2 pages deploy` (a pinned version) on the production branch `main`, because
a deploy to any other branch would only be a preview. The key goes to wrangler only through the environment, never the
command line, and it never appears in the logs. If the project is missing, the first run creates it. Each provider has its
own deploy counter (`deploys_cloudflare.json`). Tests: `python -X utf8 -m tests.test_pc_publish_cloudflare` (pc area).
