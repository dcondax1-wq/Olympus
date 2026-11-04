# Jarvis x Obsidian

Jarvis reads your Obsidian vault, answers from it and adds to it (only after you say yes). Free. Phone first.

## Set it up (once, about 5 minutes)

First, in Obsidian: Settings → Community plugins → Browse → install **Git** and turn it on.

1. On github.com, make a **private** repo named `obsidian-vault` (+ → New repository → Private → Create).
2. Make a token: `github.com/settings/personal-access-tokens/new` → Repository access: **Only select repositories** →
   `obsidian-vault` → Permissions → **Contents: Read and write** → Generate → Copy. Use it in the Git plugin too (it asks
   for your GitHub name and this token), so the vault syncs to the repo.
3. In Jarvis: ⋯ → **Obsidian** → paste `demetrades2000-coder/obsidian-vault` and the token → **Connect**.

No GitHub yet? Same screen: paste a note and Jarvis answers from it today. Anything you save waits on the phone and goes
to the vault once you connect.

## What to say

| Say | Jarvis does |
|---|---|
| "what did I write about drawdown" | the best matching notes, with their words (smart mode: a summary that names the notes) |
| "today's daily note", "yesterday's note" | that day's note and its open tasks |
| "open tasks" | every `- [ ]` across the vault, newest daily note first |
| "what's on my mind lately", "summarize this week's notes" | the themes and the notes of the last days |
| "what links to MFFU notes" | links out and back |
| "my goals" | your Goals note (else the Road to $10K card) |
| "note: …", "remember …", "add task …" | asks first, then appends to `OLYMPUS/Inbox/<day>.md` (+ `OLYMPUS/Jarvis/Memory.md` for remember, + today's daily note) |
| "write down …", "note that …", "jot down …" | the same inbox note (kept on the phone at once; asks before the vault) |
| "make a note called Gym plan: …" | a new note `OLYMPUS/Notes/Gym plan.md` (asks first; if it exists, the text is appended) |
| "add deadlift 3x5 to my gym note", "add to my gym note: …" | appended to your own note with that title (else a new one in `OLYMPUS/Notes/`) |
| "log today: …" | appended to today's daily note (else the inbox) |
| "read my gym note" | that note, in plain words |
| smart mode: "make me a leg day plan and save it" | the model writes it and asks: "Save this to OLYMPUS/Notes/Leg day.md? Say yes or no." Nothing is written before yes |
| "I don't like …", "always …", "from now on …" | offers to save it to `OLYMPUS/Jarvis/Me.md` |
| "write the OLYMPUS log" | asks first, then writes today's systems table to `OLYMPUS/Logs/<day>.md` |
| "is Obsidian connected", "sync my vault" | the status, a refresh |

Not connected yet: what you dictate is kept on the phone and waits in the outbox; it goes to the vault the moment you connect.

## How it works

- `tools/web_public/jarvis/obsidian.js`: the vault. Reads the repo's tree, fetches only the notes whose SHA changed, parses
  titles, headings, tags, `[[links]]`, frontmatter, tasks and daily notes (a date in the file name), and keeps the index in
  this phone's IndexedDB. BM25 search. Writes are GET + PUT through GitHub's contents API: append only, never a delete or an
  overwrite (the old text is kept byte for byte). A rate limit stops the calls until it resets. Refreshes every 10 minutes
  while Jarvis is open.
- `tools/web_public/jarvis/memory.js`: what you say → a confirmed write or an answer from the notes; smart mode gets the
  top note snippets and Me.md with the question (never the token), and cites the note titles.
- `OLYMPUS/Jarvis/Me.md`: seeded once from a starter template (money first, results not talk, the trading rules, OLYMPUS).
  Jarvis reads it to rank and phrase answers your way, and only appends what you approve.
- The Mind page (`tools/web_public/mind/`) reads the same cache through `graphSnapshot()` and `onIndexChange()`.

## Privacy

- The token lives only in this phone's localStorage (`jarvis.vault`) and goes only to `https://api.github.com`.
- Notes are cached only on this phone. Nothing personal is in the repo or on the public site.
- ⋯ → Obsidian → **Disconnect** wipes the token, the cache, pasted notes, the outbox and the learned list. The vault itself
  is never touched.

Tests: `python -X utf8 -m tests.test_jarvis_obsidian` (a fake vault behind a mocked GitHub API).
