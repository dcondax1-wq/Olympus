# OLYMPUS sync board (Claude <-> ChatGPT)

Both sides read this first and update only their own section. The owner only relays "Bridge: <id> done".
Claude refreshes the AUTO block with `python tools/bridge_sync.py`.

## How a job moves
Owner copies a job from the Bridge page -> ChatGPT builds it -> PR to `handoff/inbox/<id>/` (or upload) ->
owner says "Bridge: <id> done" -> Claude reviews, wires it in, ticks it here, and ships.

## ChatGPT section (ChatGPT edits)
- (nothing yet)

## Claude section (Claude edits)
- Waiting on ChatGPT: icons, skies, textures, me, persona, labours, lore, deals, obsidian, ascend, codex-portal
- Claude owns: engine, bots, tests, service workers, publishing, Jarvis wiring

<!-- AUTO:BEGIN -->
_updated 2026-11-03 22:43 UTC_

**Inbox (ChatGPT results):**
- empty

**Open ChatGPT branches:** none

**Latest Claude commits:**
- cee1081 Jarvis worker v18: saves the 3D home backdrop and the portal jump
- c793cf8 Merge branch 'worktree-agent-a9679adfa320c1bb8' into claude/clever-heisenberg-51zwcr
- 92f8047 Merge Jarvis talks: speaks every answer by default, first-tap unlock on iPhone, speaker toggle; worker v17 + jarvis.css j13
- 7e2e901 Jarvis worker v17: saves tools.js (the smart-mode tools)
- e240ca3 Backdrop: the temple of OLYMPUS on the horizon (marble columns, gold capitals), a violet haze and a key light
- f106a13 Backdrop waits for the boot log / OLYMPUS intro to end before compiling (never holds up the boot screen)
- 48dc1b1 Merge branch 'worktree-agent-aff487a5924bfa470' into claude/clever-heisenberg-51zwcr
- e51c5bf Site build publishes app subfolders (olympus/three-addons/ for the render core); test + doc
<!-- AUTO:END -->
