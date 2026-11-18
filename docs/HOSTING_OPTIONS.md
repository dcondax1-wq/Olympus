# Where the OLYMPUS site can live (free, no GitHub needed)

Every limit below is from memory: **verify on the provider page** before you rely on it.

| Host | How `pc_publish` sends the site | Free limit (verify on the provider page) | Fit for 15-minute updates |
|---|---|---|---|
| **Your Oracle VM** (scp + Caddy or nginx) | Built: `--setup scp`. Zips only the changed files, sends with ssh/scp, unpacks on the server | No deploy limit; the VM is always-free, you run the web server | Best |
| **Netlify** | Built: `--setup netlify` (digest deploy, only changed files) | About 20 deploys a month on the new free plan (verify on the provider page) | Daily page only |
| **Cloudflare Pages** | Built 2026-11-18, OFF by default: `--setup cloudflare` (Cloudflare's own wrangler via Node.js; docs/HOSTING.md) | Generous deploy count, 500 builds a month applies to Git builds (verify on the provider page) | Would fit, but needs a hashing add-on |
| **Vercel** (CLI) | Not built. Needs their command-line tool (Node) on the PC | Daily deploy cap on the free plan (verify on the provider page) | Maybe |
| **Surge** | Not built. Needs their command-line tool (Node) | Free, plain static hosting, no stated deploy cap (verify on the provider page) | Maybe |
| **A folder** (`--setup folder`) | Built: copies the site to any folder you already sync | Whatever that sync tool allows | Depends |

## What to pick
- **Fresh numbers every 15 minutes:** your own Oracle VM with `scp`. No limit, no account on a third party.
- **One page a day, nothing to run:** Netlify.
- No Netlify badge, no VM: Cloudflare Pages (docs/HOSTING.md, 3 steps).

## Set up the Oracle VM (one time)
1. On the VM: install Caddy (or nginx) and point it at a folder, for example `/var/www/olympus`. Python 3 must be there (it unpacks the upload).
2. On the PC: `python tools/pc_publish.py --setup scp --scp-target user@VM_ADDRESS --scp-dir /var/www/olympus --scp-key ~/.ssh/YOUR_KEY`
3. Run `python tools/pc_publish.py` once. After that the PC sends only what changed.

The key path lives in the settings file outside the repo (`%USERPROFILE%\.olympus\publish.json`), never in the repo.

## The Kalshi feed on the same site
Set `kalshi_file` (or `kalshi_feed_url`) in that settings file, or leave a `kalshi.json` in `%USERPROFILE%\.olympus\kalshi_feed\`: `pc_publish` copies it into the site as `kalshi.json`, and every Kalshi page reads it from there first (the old GitHub address is only the fallback).
