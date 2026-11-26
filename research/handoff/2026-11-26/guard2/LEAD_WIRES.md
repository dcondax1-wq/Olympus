# day-guard2 (2026-11-26): lead wires

The helper did NOT touch sw.js, build_web_dashboard.py, jarvis/apps.js or the olympus.js APPS table.

1. **Bump `pc_feed.js?v=n8` -> `n9`** on every page (bump_versions --apply), so cached phones get the multi-key / rotation reader.
   An old cached pc_feed.js still works with the pinned "vk" (it checks one key), so nothing breaks before the bump.
2. **Publish the site.** `tools/web_public/status_feed.json` now pins the PC's vk (BARkFWc9zQou...; 97/97 posts on the live topic
   verified under it on 2026-11-26). sw.js never caches status_feed.json, so phones read the pin at once. From then on, pages
   (pc_feed.js) and the board drop unsigned / foreign status posts.
3. New public file `tools/web_public/pc_key_trust.js`: lazy-loaded by pc_feed.js only when a rotation post shows up, or when no
   trusted key has posted for 3 h. It does not need precaching (it is never needed offline); add it if the SHELL list is explicit.
4. Still NOT verifying signatures (each polls the status topic itself): `widget/olympus-widget.js` (Scriptable, no WebCrypto),
   `kalshi/kalshi.js` (rewards block), `jarvis/shortcuts.js`, `nq/nqbars.js` (bars topic). Each could call
   `window.PC_FEED.keepSigned(text, PC_FEED.feedKeys(feed))` on its ndjson before parsing. That's a follow-up.

## Key rotation (no lock-out)
- Planned (PC still has its key): on the PC, `python tools/status_sign.py rotate`. The OLD key signs a hand-over post (kind
  le-key-rotate). Every reader that trusts the old key trusts the new one at once. The 15-minute report repeats the hand-over
  every 6 h for 14 days (ntfy keeps a post 12 h). Then Claude runs `python tools/status_sign.py pin <first 12 chars>` (pinned
  beside the old key in "vks"), commits, publishes.
- Lost key (reinstall / new PC): the 3-hour window. When no pinned key has posted for 3 h+ and one other key has signed 12+ posts
  over 3 h+:
  - `tools/board.py read` notes it, with the pin command, and does NOT believe its posts;
  - the phone shows a "Your PC's signing key changed?" banner. "Trust new key" trusts it on that phone only (localStorage);
    "Not now" hides it for the session.
  - Claude pins it after the owner confirms in chat.
