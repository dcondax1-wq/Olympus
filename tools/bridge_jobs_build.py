"""The Bridge job library (tools/web_public/bridge/jobs.json): ready-to-paste ChatGPT jobs, written as data.

    python tools/bridge_jobs_build.py          writes tools/web_public/bridge/jobs.json  (tests/test_bridge_page.py checks it is fresh)

Every job: id, cat, title, makes (what it produces), prompt (the exact text to paste), files (what must come back), lands
(handoff/inbox/<id>/), minutes (estimate for ChatGPT), difficulty (easy | medium | hard), tool (chatgpt | codex). Every prompt carries
the rules of handoff/ONBOARD.md (only add under handoff/inbox/<id>/, no secrets, plain files, paper only, DONE.md, QUESTION.md) and the
size caps tools/bridge_ingest.py enforces, so a delivery that follows the prompt is accepted by the ingest.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "bridge", "jobs.json")
CTX = ("Context: I am building OLYMPUS, a set of phone web apps (three.js, calm classical Greek AGORA look: marble, bronze, gold #c8a24a, olive and terracotta "
       "on warm near-black #14110e; no neon, no sci-fi). I am 18 and use an iPhone. Use plain words.")
CAPS = "File limits: PNG / WebP up to 5 MB each, SVG up to 200 KB, JSON up to 1 MB, Markdown / text up to 200 KB, JS up to 100 KB."

CATS = [
    ("textures", "Textures and skies"), ("art", "App icons and splash art"), ("logo", "Logos and glyphs"), ("sound", "Sound-design briefs"),
    ("copy", "Copywriting"), ("lore", "Lore and story"), ("obsidian", "Obsidian vault"), ("strategy", "Strategy brainstorms"),
    ("research", "Research summaries"), ("fixtures", "Test data"), ("docs", "Docs polish"), ("mockup", "UI mockups"), ("names", "Names and taglines"),
    ("money", "Money and prop firms"),
]
APPS = "Jarvis, Zenith, Oracle, Odeon, Fates, Data City, Daphne, Prometheus, Pantheon, Mind, Arena, Kalshi, Tyche, Hermes, Plutus, Ares, Athena, Forum, Labyrinth, Argus, Nemesis, Chronos, Hephaestus, Bridge"

# the money jobs (2026-11-04): research the owner pastes into ChatGPT about his own trading money. Every one opens with this preamble.
MONEY = ("Money job. Rules: research and plain-words explanation only; this is not financial, tax or legal advice. Where it touches taxes, law, accounts or a firm's "
         "decision, write 'ask a CPA' or 'ask the firm' and give me the QUESTIONS to ask instead of answers. Use only public, official sources (the firm's own pages, CME Group, "
         "IRS.gov, Kalshi's help center), list every source (name and web address) and the date you checked it, mark anything you could not verify as UNVERIFIED, and never "
         "invent a number, a code or a rule. Never ask me for passwords, API keys, account numbers, SSN, ID or bank details, and never put any in a file. Nothing here places or "
         "arms an order (paper only). Plain words, short sentences, tables where they help.\n\nThe task: ")
MONEY_TAX = MONEY.replace("The task: ", "Tax topics: I am a US person; rules differ by state and by year, so say which tax year you mean and give the question to ask a CPA wherever the answer depends on my situation.\n\nThe task: ")

# (id, cat, title, makes, minutes, difficulty, files, body)
J = [
    # ---------------------------------------------------------------- textures and skies
    ("tex-marble-white", "textures", "White marble look", "Four 1024 px pictures that make white Greek marble look real on a 3D surface", 8, "medium",
     ["marble-white-albedo.png", "marble-white-normal.png", "marble-white-roughness.png", "marble-white-ao.png"],
     "Make a seamless tileable PBR texture set of polished white Greek marble with soft grey veins, 1024x1024 each: albedo (colour), normal (tangent space, the usual blue-purple look, gentle), roughness (greyscale, polished = dark), ambient occlusion (greyscale, subtle). No text, no logo, evenly lit, no baked shadows."),
    ("tex-marble-black-gold", "textures", "Black marble with gold veins", "Four pictures that make black marble with thin gold veins look real", 8, "medium",
     ["marble-black-albedo.png", "marble-black-normal.png", "marble-black-roughness.png", "marble-black-ao.png"],
     "Make a seamless tileable PBR set of black marble with thin branching gold veins, 1024x1024: albedo, normal, roughness (veins slightly rougher), ambient occlusion. Evenly lit, no text, no baked shadows."),
    ("tex-gold-brushed", "textures", "Brushed gold", "Brushed gold metal maps with a long horizontal grain", 7, "easy",
     ["gold-albedo.png", "gold-normal.png", "gold-roughness.png"],
     "Make a seamless tileable brushed gold metal set, 1024x1024: albedo (warm #e0b030 tones), normal (fine horizontal brushing), roughness (greyscale, medium-low). Evenly lit, no text, no reflections of a room."),
    ("tex-bronze-aged", "textures", "Aged bronze", "Bronze with green-blue patina in the cracks", 7, "easy",
     ["bronze-albedo.png", "bronze-normal.png", "bronze-roughness.png"],
     "Make a seamless tileable aged bronze set, 1024x1024: albedo (warm bronze with verdigris in the recesses), normal (hammered, shallow), roughness (greyscale, patina rougher). Evenly lit, no text."),
    ("tex-parchment", "textures", "Parchment and scroll paper", "Parchment paper that repeats smoothly, plus a scroll edge strip", 6, "easy",
     ["parchment-albedo.png", "parchment-edge.png"],
     "Make a seamless tileable parchment paper texture 1024x1024 (warm cream, faint fibres, a few tiny stains, no writing), and a 1024x256 strip of burnt, torn parchment edge on a transparent background (PNG with alpha)."),
    ("tex-fire-sheet", "textures", "Flame animation sheet", "A 4 x 4 grid of flame pictures on a see-through background", 9, "hard",
     ["fire-sheet-4x4.png"],
     "Make one PNG sprite sheet 2048x2048, a 4 x 4 grid of 512x512 frames of a single torch flame burning (loops from the last frame back to the first), orange-yellow core fading to deep red at the tips, transparent background (alpha), no smoke, no torch, no text. Add the frame order (left to right, top to bottom) to DONE.md."),
    ("tex-water-caustics", "textures", "Water caustics and ripples", "A repeating pattern of light under water, and a ripple picture for water", 7, "medium",
     ["caustics.png", "water-normal.png"],
     "Make two seamless tileable 1024x1024 textures: (1) underwater caustics, bright light net on pure black, (2) a gentle water ripple normal map (tangent space). No text."),
    ("tex-lava-cracks", "textures", "Lava and glowing cracks", "Dark crust with glowing orange cracks, colour and emissive maps", 8, "medium",
     ["lava-albedo.png", "lava-emissive.png"],
     "Make a seamless tileable 1024x1024 pair: albedo of dark cooled lava crust, and an emissive map (cracks glowing orange-yellow on pure black, same layout). No text."),
    ("sky-time-of-day", "textures", "Four times of day skies", "Four ultra-wide sky pictures with no visible seam: dawn, noon, dusk, storm", 10, "medium",
     ["sky-dawn.png", "sky-noon.png", "sky-dusk.png", "sky-storm.png"],
     "Make four seamless equirectangular-style sky panoramas, 4096x2048 if you can (otherwise as wide as possible, 2:1): dawn (gold and pink over layered clouds), noon (clear deep blue with few thin clouds), dusk (violet and orange with a first star), storm (dark green-grey cloud wall with a distant lightning). No ground, no sun disc detail, no text."),
    ("sky-olympus-cube", "textures", "Mount Olympus sky box", "Six square faces for a skybox of Mount Olympus above the clouds at night", 12, "hard",
     ["px.png", "nx.png", "py.png", "ny.png", "pz.png", "nz.png"],
     "Make six 1024x1024 images that form a seamless skybox (faces px, nx, py, ny, pz, nz) of a night sky above a sea of clouds with the peak of Mount Olympus glowing faintly gold and violet on one horizon. The edges of neighbouring faces must match. No text."),
    # ---------------------------------------------------------------- app icons and splash art
    ("icons-new-apps", "art", "Icons for the newer apps", "Ten 1024 px icons in the same Greek emblem style", 10, "medium",
     ["ares.png", "plutus.png", "athena.png", "forum.png", "labyrinth.png", "argus.png", "nemesis.png", "chronos.png", "hephaestus.png", "bridge.png"],
     "Make 10 square app icons, 1024x1024, one consistent style: a single glowing Greek emblem in gold and violet light on a near-black background, no text, crisp, premium, like a luxury game UI. Ares (a spear and shield, red glow), Plutus (a gold coin vault), Athena (an owl), Forum (a marble tablet with a laurel), Labyrinth (a spiral maze), Argus (a many-eyed peacock feather), Nemesis (a balance scale with a flame), Chronos (an hourglass wrapped in a serpent), Hephaestus (an anvil with sparks), Bridge (a glowing arch bridge between two stars). Each as its own file."),
    ("icons-mono", "art", "One-colour icon set", "Monochrome SVG icons for small sizes", 9, "medium",
     ["icons-mono-sheet.svg", "README.md"],
     "Design a set of 24 simple one-colour line icons (one per OLYMPUS app: " + APPS + ") as ONE SVG file with a <symbol id=\"app-name\"> for each, 24x24 viewBox, 1.75 stroke, currentColor, round caps, no fills except small dots, no text. In README.md list the symbol ids. No scripts, no external references."),
    ("splash-1", "art", "Splash screens 1 of 4", "Five portrait splash screens", 12, "medium",
     ["jarvis.png", "zenith.png", "oracle.png", "odeon.png", "fates.png"],
     "Make 5 portrait splash screens, 1170x2532, cinematic and minimal: the app's emblem glowing in the centre on a deep gradient with a faint marble floor reflection, no text. Apps: Jarvis (AI core orb, violet), Zenith (rising star, gold), Oracle (eye with a radar ring, cyan), Odeon (Greek theatre of film, rose), Fates (three threads, amber)."),
    ("splash-2", "art", "Splash screens 2 of 4", "Five portrait splash screens", 12, "medium",
     ["datacity.png", "daphne.png", "prometheus.png", "pantheon.png", "mind.png"],
     "Make 5 portrait splash screens, 1170x2532, cinematic and minimal: the app's emblem glowing in the centre on a deep gradient, no text. Apps: Data City (skyline of light towers, blue), Daphne (a laurel tree of light, green), Prometheus (a torch flame, orange), Pantheon (a temple with columns, gold), Mind (a galaxy brain, teal)."),
    ("splash-3", "art", "Splash screens 3 of 4", "Five portrait splash screens", 12, "medium",
     ["arena.png", "kalshi.png", "tyche.png", "hermes.png", "plutus.png"],
     "Make 5 portrait splash screens, 1170x2532, cinematic and minimal: the app's emblem glowing in the centre on a deep gradient, no text. Apps: Arena (colosseum with a laurel crown, amber), Kalshi (a K coin, green), Tyche (a wheel of fortune, magenta), Hermes (a winged helmet, gold), Plutus (a vault of coins, lime)."),
    ("splash-4", "art", "Splash screens 4 of 4", "Eight portrait splash screens", 16, "hard",
     ["ares.png", "athena.png", "forum.png", "labyrinth.png", "argus.png", "nemesis.png", "chronos.png", "hephaestus.png"],
     "Make 8 portrait splash screens, 1170x2532, cinematic and minimal: the app's emblem glowing in the centre on a deep gradient, no text. Apps: Ares (spear and shield, red), Athena (owl, blue), Forum (marble tablets, lime), Labyrinth (spiral maze, crimson), Argus (many eyes, cyan), Nemesis (scale and flame, violet), Chronos (hourglass and serpent, bronze), Hephaestus (anvil and sparks, magenta)."),
    ("art-hero-banners", "art", "Hero banners per area", "Wide banners for the dashboard sections", 9, "easy",
     ["banner-trading.png", "banner-money.png", "banner-mind.png", "banner-life.png"],
     "Make 4 wide banners 2400x800, subtle and dark so text can sit on top: Trading (storm and lightning over a marble harbour), Money (gold coins floating in violet mist), Mind (a starry library of glowing books), Life (sunrise over a Greek hillside). No text, nothing busy in the middle."),
    # ---------------------------------------------------------------- logos and glyphs
    ("logo-olympus-variants", "logo", "OLYMPUS mark variants", "Ten variants of the O / laurel / temple logo as SVG", 10, "medium",
     ["olympus-01.svg", "olympus-02.svg", "olympus-03.svg", "olympus-04.svg", "olympus-05.svg", "olympus-06.svg", "olympus-07.svg", "olympus-08.svg", "olympus-09.svg", "olympus-10.svg"],
     "Design 10 different logo marks for OLYMPUS as separate SVG files (viewBox 0 0 256 256, gold and violet gradients, a transparent background, no text, no raster images, no scripts). Ideas: an O made of a laurel wreath, an O with a temple pediment inside, an O ring with a lightning bolt, a column capital as an O, an eye in an O, and five more of your own. Keep them simple enough to read at 32 px."),
    ("glyph-greek-letters", "logo", "Greek letter set", "Twenty-four gold Greek letters as SVG", 8, "easy",
     ["greek-glyphs.svg", "README.md"],
     "Design the 24 Greek capital letters (Alpha to Omega) as ONE SVG sprite with a <symbol id=\"alpha\"> ... <symbol id=\"omega\"> each, 64x64 viewBox, bold geometric futuristic style, filled with currentColor, no text elements (draw the shapes as paths), no scripts. README.md lists the ids."),
    ("logo-wordmarks", "logo", "OLYMPUS name logos", "Six wordmark styles in SVG", 9, "medium",
     ["wordmark-01.svg", "wordmark-02.svg", "wordmark-03.svg", "wordmark-04.svg", "wordmark-05.svg", "wordmark-06.svg"],
     "Design 6 wordmarks of the word OLYMPUS as SVG outlines (letters drawn as paths, not text elements, no fonts needed), viewBox 0 0 640 128: wide futuristic caps, carved marble caps, thin gold line caps, neon tube caps, laurel-decorated caps, minimal monoline. No scripts, no raster images."),
    ("emblem-ranks", "logo", "Rank emblems", "Five rank emblems: Mortal, Hero, Demigod, Olympian, Titan", 8, "medium",
     ["mortal.svg", "hero.svg", "demigod.svg", "olympian.svg", "titan.svg"],
     "Design 5 rank emblems for a discipline app as SVG (viewBox 0 0 256 256, no text, no scripts, no raster): Mortal (a plain bronze ring), Hero (a shield with a laurel), Demigod (a winged shield with a small star), Olympian (a golden crown of light with columns), Titan (a huge glowing crown with lightning). Each clearly grander than the last."),
    # ---------------------------------------------------------------- sound-design briefs (text only)
    ("sound-ui-sfx", "sound", "Button and screen sound ideas", "Short written recipes for the six button and screen sounds", 8, "medium",
     ["ui-sounds.json", "README.md"],
     "Write sound-design briefs (TEXT ONLY, do not make audio) for these UI sounds of a futuristic Greek-god app: tick, tap, portal, thunder, rankup, pad. In ui-sounds.json give for each sound an object with: feel (one plain sentence), oscillators (type, frequency in Hz, detune), envelope (attack, decay, sustain, release in seconds), filter (type, cutoff Hz, resonance, any sweep), noise (type, level), reverb (size, mix), lfo (target, rate, depth), length in ms, and a note on how it must stay quiet and soft on a phone. README.md explains the file in plain words."),
    ("sound-ambient", "sound", "Ambient drone briefs", "Per-app ambient pad descriptions", 8, "medium",
     ["ambient.json"],
     "Write ambient background sound briefs (TEXT ONLY, no audio) for 12 apps (Jarvis, Zenith, Oracle, Odeon, Fates, Data City, Daphne, Prometheus, Pantheon, Mind, Arena, Tyche). For each app give: mood in 5 words, root note and scale, 3 oscillator layers (waveform, octave, detune cents), a slow filter movement (cutoff range Hz, rate), a noise bed (type, level), reverb size, a quiet loudness target in dB, and one 'event' sound idea. Must be very soft: it plays under speech."),
    ("sound-jarvis-fx", "sound", "Jarvis voice effects brief", "How to make her voice feel futuristic without hurting clarity", 6, "easy",
     ["jarvis-voice-fx.md"],
     "Write a short brief (Markdown, plain words) for the effects chain on Jarvis's female voice in a phone web app (Web Audio API): a gentle formant lift, a very light chorus, a short plate reverb, a soft high shelf, a ducking rule for background music. Give each effect as a Web Audio node with exact starting parameter values, and say what to change if the voice sounds metallic or muddy."),
    ("sound-win-loss", "sound", "Win and loss jingles", "Briefs for celebration and calm 'bad day' sounds", 6, "easy",
     ["stingers.json"],
     "Write synth briefs (TEXT ONLY) for 6 short stingers: green day, red day (calm, never mocking), eval passed, payout received, streak extended, rank up. In stingers.json give for each: length ms, the notes (MIDI numbers) and rhythm, waveform per layer, envelope, filter, reverb, and loudness. Reward process, never risk."),
    # ---------------------------------------------------------------- copywriting
    ("copy-tooltips", "copy", "Plain-words tooltips", "A glossary of trading and app terms in one sentence each", 9, "easy",
     ["tooltips.json"],
     "Write plain-words tooltips (max 140 characters each, an 18-year-old with no finance background must get it) for these terms used in my trading dashboards: R multiple, stop, target, breakeven, drawdown, trailing floor, eval, funded account, payout, profit factor, win rate, expectancy, micro contract, MNQ, NQ, sweep, CISD, FVG, VIX, session, paper trading, slippage, commission, Kelly. Output tooltips.json as an object {term: text}. No advice words like 'buy' or 'sell'."),
    ("copy-empty-states", "copy", "Empty-state copy per app", "A title and a helpful line for when an app has no data yet", 9, "easy",
     ["empty-states.json"],
     "For each of these apps write the text shown when there is no data yet: " + APPS + ". In empty-states.json give for each app: title (max 28 characters), line (max 90 characters, says what will appear and what to do, warm, a little Greek), and button (max 18 characters). Never say 'error'."),
    ("copy-onboarding", "copy", "First-run onboarding text", "Three short onboarding screens per app", 12, "medium",
     ["onboarding.json"],
     "Write first-run onboarding for these apps: Jarvis, Zenith, Oracle, Fates, Data City, Arena, Tyche, Hermes, Plutus, Ares, Forum, Bridge. For each: 3 screens, each with a headline (max 24 characters) and one line (max 80 characters). Plain words, no jargon, a bit of epic Greek flavour. Output onboarding.json as {app: [{h, t}, ...]}."),
    ("copy-friendly-errors", "copy", "Friendly messages", "Offline, stale, loading and stopped messages", 6, "easy",
     ["messages.json"],
     "Write friendly one-line messages (max 80 characters) for these states in my phone apps: offline, data is stale, loading, the bot is stopped, the PC is off, market closed, weekend, no trades today, feed not linked yet, saved, copied. Give 3 variants of each. Output messages.json as {state: [variants]}. Calm and kind, never scary, never blame the user."),
    ("copy-notifications", "copy", "Push notification texts", "Short push texts for key moments", 6, "easy",
     ["notifications.json"],
     "Write push notification texts (title max 30 characters, body max 80) for: trade opened, trade closed in profit, trade closed at the stop, daily loss limit near, eval target reached, eval failed, payout available, bot stopped, morning briefing ready, oath not sealed by 9 am, streak at risk. Three variants each, output notifications.json. Paper trading wording; no hype, no 'guaranteed'."),
    # ---------------------------------------------------------------- lore and story
    ("lore-olympians", "lore", "The twelve Olympians as characters", "A profile for each of the 12 gods as a guide in the apps", 12, "medium",
     ["olympians.json"],
     "Write profiles for the 12 Olympians as characters that guide a trading-discipline app: Zeus, Hera, Poseidon, Demeter, Athena, Apollo, Artemis, Ares, Aphrodite, Hephaestus, Hermes, Hestia. For each: domain in the app (what they watch over), a 2-sentence story, a signature line (max 90 characters), an element and a colour (hex), and one 'warning' line they say when the user is about to break a rule. Output olympians.json as an array. Tone: epic, short, never mystical advice about markets."),
    ("lore-arenas", "lore", "Each app as a place", "A short origin story for every app as a Greek location", 12, "medium",
     ["places.json"],
     "For each app (" + APPS + ") write a place in the OLYMPUS world: name (a Greek-style place name), a 3-sentence origin story, who guards it, and one line that appears when you open it (max 80 characters). Output places.json as {app: {...}}."),
    ("lore-ranks", "lore", "The road from Mortal to Titan", "Story beats and quotes for the five ranks", 7, "easy",
     ["ranks.json"],
     "Write the story of the five ranks Mortal, Hero, Demigod, Olympian, Titan: for each a 3-sentence chapter, the quote shown when you earn it (max 100 characters), the unlock teaser line, and a rank-up fanfare description in words (no audio). Output ranks.json. It rewards discipline and process, never profit or risk."),
    ("lore-daily-lines", "lore", "Sixty daily lines", "Short motivational lines for the Forum morning briefing", 8, "easy",
     ["daily-lines.json"],
     "Write 60 one-line morning sayings (max 100 characters) in the voice of the Greek gods for a trading-discipline briefing: patience, process, small size, calm after a loss, rest. Output daily-lines.json as an array of {line, god}. No promises of profit, no market predictions."),
    # ---------------------------------------------------------------- Obsidian vault
    ("obs-daily-template", "obsidian", "Daily note template", "A Markdown daily note with a morning oath and evening review", 6, "easy",
     ["Daily.md", "README.md"],
     "Write an Obsidian daily-note template (Markdown, Templater-free so it works in plain Obsidian with the Daily Notes core plugin) with: a morning section (date, mood 1-5, sleep hours, the oath of three pledges as tick boxes: follow the plan, no revenge trade, write the journal), top 3 tasks, a trading section (bot status, trades reviewed, rules kept), gym, study, money, an evening review with 3 questions, and tags. README.md says where to put it."),
    ("obs-trading-journal", "obsidian", "Trading journal templates", "Trade review and weekly review templates", 8, "medium",
     ["Trade review.md", "Weekly review.md", "Monthly review.md", "README.md"],
     "Write three Obsidian templates in Markdown for reviewing a futures trading process (paper and eval accounts): a Trade review (setup, entry, stop beyond the sweep, target, result in R and dollars, rules kept yes/no, what I would repeat), a Weekly review (numbers, rule breaks, best and worst trade, one goal for next week), a Monthly review (pass-rate of the checklist, drawdown, money per month, lessons). Each with YAML properties at the top. README.md explains the folders."),
    ("obs-weekly-review", "obsidian", "Life weekly review", "A weekly review across trading, gym, study and money", 6, "easy",
     ["Life weekly.md"],
     "Write one Obsidian note template for a weekly life review: wins, misses, trading discipline score out of 10, gym sessions, study hours, money in and out, sleep average, one thing to stop, one to start, one goal. Markdown only, short, with a checklist."),
    ("obs-starter-vault", "obsidian", "Starter notes for Jarvis", "Ten starter notes Jarvis can read and write to", 12, "medium",
     ["Me.md", "Trading rules.md", "Goals.md", "Routine.md", "Money.md", "Gym.md", "Study.md", "Likes and dislikes.md", "Talk to me.md", "Inbox.md"],
     "Write 10 starter Obsidian notes as separate Markdown files that my assistant Jarvis will read and update: Me, Trading rules (LIT strategy basics: sweep, CISD, stop beyond the sweep, 8R target, one trade a day, paper only), Goals, Routine, Money, Gym, Study, Likes and dislikes, Talk to me (how she should speak to me), Inbox. Fill each with sensible placeholders marked [fill in] and short example lines. Plain words."),
    # ---------------------------------------------------------------- strategy brainstorms (text only)
    ("strat-ideas-nq", "strategy", "Fifteen NQ idea sketches", "Text-only hypotheses to test in the backtester, with how to test each", 12, "hard",
     ["ideas.md"],
     "Brainstorm 15 hypotheses for an NQ futures day-trading bot that trades liquidity sweeps then a change-in-state-of-delivery entry with the stop beyond the sweep extreme. TEXT ONLY (no code, no signals, no advice): for each: the idea in 2 sentences, why it might work, how to test it on 5-minute NQ data in 2021-2026 (what to measure: trades per week, profit factor, max drawdown), and one way it could fail. Mark which are NEW and which sound like standard ICT teaching. Paper research only."),
    ("strat-risk-sizing", "strategy", "Position-sizing ideas", "Ideas for sizing that follow the stop, text only", 9, "medium",
     ["sizing.md"],
     "Write 10 position-sizing ideas for a prop-firm eval (MFFU Builder 50K: 2,000 dollar trailing drawdown, 1,000 daily loss, up to 40 micros) where size follows the stop: for each, a plain formula, a worked example in dollars, when it helps, when it hurts, and what to measure in a backtest. Text only, no advice, paper only."),
    ("strat-regimes", "strategy", "Market regime ideas", "Ways to tell a trend day from a range day", 9, "medium",
     ["regimes.md"],
     "List 12 ways to describe the market regime of an NQ day from data available by 09:30 ET (overnight range, gap, VIX level and change, 18:00 open vs previous close, news day, expiry day...). For each: how to compute it, what it might predict, how to test it honestly (train on one half, check on the other), and the main risk of fooling yourself. Text only, no signals."),
    # ---------------------------------------------------------------- research summaries
    ("res-prop-rules", "research", "Prop firm rules summary", "A sourced table of the rules of six futures prop firms", 15, "hard",
     ["rules-table.md", "sources.md"],
     "Search the web and summarise the CURRENT rules of futures prop firms (MyFundedFutures, Lucid Trading, FundedNext Futures, Apex Trader Funding, Topstep, Take Profit Trader): account sizes, profit target, max loss (trailing or end-of-day), daily loss, contract limits, consistency rule, payout rules (minimum, split, buffer), news trading, bots/automation allowed or not, activation fee. Table in rules-table.md; every row has the source link and the date you read it in sources.md. Mark anything you could not confirm as UNCONFIRMED."),
    ("res-nq-calendar", "research", "Recurring NQ market events", "A list of recurring events that move NQ with typical times (ET)", 10, "medium",
     ["events.md", "sources.md"],
     "List the recurring US events that move Nasdaq futures, with the usual time in New York time: CPI, jobs report, FOMC statement and press conference, PPI, retail sales, jobless claims, ISM, quad witching, monthly opex, MNQ/NQ rollover, the 08:30 and 10:00 data prints, Treasury auctions. For each: how often, usual time, why it matters in one plain sentence, source link. Put sources in sources.md."),
    ("res-kalshi-markets", "research", "Kalshi market types", "How the main Kalshi market families work", 10, "medium",
     ["kalshi-markets.md", "sources.md"],
     "Explain in plain words how Kalshi's main market families work (15-minute crypto up/down, hourly and daily crypto ranges, gold and silver, S&P and Nasdaq ranges, weather, economics): what a contract is, price vs probability, fees, how settlement works, typical liquidity, and the common ways people lose money. Source links in sources.md. Education only, no advice."),
    # ---------------------------------------------------------------- test-data fixtures (synthetic JSON)
    ("fx-demo-trades", "fixtures", "Practice trade history", "200 made-up trades the apps can read", 8, "medium",
     ["trades.json", "README.md"],
     "Generate a SYNTHETIC (clearly fake) list of 200 NQ/MNQ trades over the last 120 weekdays as trades.json: an array of {id, day (YYYY-MM-DD), time (HH:MM, between 02:00 and 15:30 ET), side (long/short), qty, entry, stop, target, exit, risk_pts, pnl (dollars after 1.25 points of costs), r (R multiple), exit_reason (target/stop/breakeven/time)}. Make it realistic: about 1 trade a day, a win rate near 45 percent, a few 8R winners, stop 8-60 points. README.md says it is fake test data."),
    ("fx-demo-kalshi", "fixtures", "Practice Kalshi feed", "A fake Kalshi data file the apps can read", 7, "medium",
     ["kalshi.json", "README.md"],
     "Generate a SYNTHETIC kalshi.json for testing an app: {v: 3, t (unix), name, running, balance, today_pnl, week_pnl, total_pnl, positions: [...6 open bets...], trades: [...80 settled bets with ticker, title, side, contracts, price, pnl, t, category, strategy...], days: [[YYYY-MM-DD, pnl]...30], strategies: [{name, wins, losses, total_pnl}...3]}. Crypto 15-minute markets, gold, S&P. Realistic numbers, balance near 2,400 dollars. README.md says it is fake."),
    ("fx-demo-weeks", "fixtures", "Practice weekly recaps", "Eight weeks of fake wrapped data", 7, "medium",
     ["weeks.json"],
     "Generate SYNTHETIC weekly recap data for 8 weeks as weeks.json: [{from, to, net, trades, wins, losses, best_trade: {day, pnl, r}, worst_trade: {...}, discipline: score 0-100, rules_broken: [..]}]. Include one red week and one 8R week. Fake numbers only."),
    ("fx-demo-planner", "fixtures", "Practice planner data", "Fake tasks, events and habits for tests", 8, "medium",
     ["planner-demo.json"],
     "Generate SYNTHETIC planner data as planner-demo.json: {tasks: 30 [{id, title, date, done, p (0-3), est (minutes), proj}], events: 20 [{id, title, date, start, end}], habits: 5 [{id, name, color, done: [dates over 90 days]}]}. Dates within 2026-09-01 to 2026-11-30. Normal student/trader life, nothing private."),
    # ---------------------------------------------------------------- docs polish
    ("docs-readme-plain", "docs", "A plain-words README", "A friendly intro page for the front of the project", 9, "easy",
     ["README-plain.md"],
     "Read README.md and STRATEGY.md in the repo. Write README-plain.md: what this project is in 5 plain sentences, the three things the owner looks at every day, a picture-free map of the apps (one line each), and how to ask for changes. No jargon, no secrets, do not change the existing README."),
    ("docs-faq", "docs", "Owner FAQ", "Thirty questions the owner asks, answered", 10, "medium",
     ["faq.md"],
     "Read docs/CLAUDE_REFERENCE.md and STRATEGY.md. Write faq.md with 30 questions an 18-year-old trader would ask about this system (what is an eval, why paper only, what does GO/WAIT/HALT mean, what is R, how do I know the bot is alive, what if the PC is off...) and short plain answers, each ending with where to look in the apps. Only state what the docs say; mark guesses as GUESS."),
    ("docs-glossary", "docs", "Glossary", "One-page glossary of every term in the apps", 8, "easy",
     ["glossary.md"],
     "Write glossary.md: 80 terms used across the OLYMPUS apps (trading, prop firms, Kalshi, the planner, the Greek theme), alphabetical, one plain sentence each, no jargon inside the definitions."),
    ("docs-release-notes", "docs", "Release notes in plain words", "What changed this month, for the owner", 7, "easy",
     ["release-notes.md"],
     "Read the git log of the repo (last 60 commits). Write release-notes.md for the owner: 10 bullets grouped under New, Better, Fixed, each one plain sentence about what he can see or do now. Skip anything about tests or internals."),
    # ---------------------------------------------------------------- UI mockup descriptions
    ("ui-mock-home", "mockup", "Home screen redesign brief", "Three written mockups of the Jarvis home", 9, "medium",
     ["home-mockups.md"],
     "Write three alternative designs for the Jarvis home screen (phone portrait, iPhone 390x844, dark Greek-futuristic): for each, a layout described top to bottom with sizes in px, the colours (hex), the type (Orbitron for names and numbers, Rajdhani for text), what animates and how (duration, easing), what a tap does, and what shows when there is no data. Words only, no images."),
    ("ui-mock-cards", "mockup", "Card system brief", "A written design system for cards, chips and buttons", 8, "medium",
     ["cards.md"],
     "Write a one-page design brief for a set of reusable phone UI parts (glass card, chip, big button, ring gauge, tab bar, toast, bottom sheet): sizes, radii, borders, shadows, blur, colours (hex) for the default violet theme and a gold theme, states (idle, pressed, disabled, loading), and motion. Include exact CSS custom properties as a small code block."),
    ("ui-mock-onboarding", "mockup", "Onboarding flow brief", "A three-screen wizard for a new user", 7, "easy",
     ["onboarding-flow.md"],
     "Write a design brief for a three-screen onboarding wizard of a phone app (connect, teach, first job): screen by screen layout, copy (max 12 words per line), the one big button each, what the progress ring does, the success moment (confetti? sparks? sound?) and how it fails gently."),
    # ---------------------------------------------------------------- names and taglines
    ("names-taglines", "names", "App taglines", "Three taglines per app", 6, "easy",
     ["taglines.json"],
     "For each app (" + APPS + ") write 3 taglines (max 40 characters, plain words, a little epic). Output taglines.json as {app: [3 strings]}."),
    ("names-bots", "names", "Bot and strategy names", "Greek names for bots, strategies and accounts", 5, "easy",
     ["bot-names.json"],
     "Suggest 40 names for trading bots, strategies and accounts in a Greek-myth style (short, easy to say, no existing company names), each with a one-line meaning. Output bot-names.json as [{name, meaning, fits}] where fits is one of: bot, strategy, account, app."),
    ("names-features", "names", "Feature names", "Catchy names for new dashboard features", 5, "easy",
     ["feature-names.json"],
     "Suggest 40 names for dashboard features (a replay of past trades, a risk calculator, a pre-trade checklist, a weekly recap, a streak tracker, a sound mixer, ...), Greek or futuristic, max 14 characters, each with what it is in one line. Output feature-names.json as [{name, for}]."),
    # ---------------------------------------------------------------- money and prop firms (2026-11-04: research for the owner's own trading money)
    ("money-prop-compare", "money", "Prop-firm rule comparison", "A side-by-side table of the main futures prop firms' evaluation rules", 14, "hard",
     ["prop-firms.md", "prop-firms.json"],
     MONEY + "Compare the futures prop firms I could use for a 50K evaluation: MyFundedFutures (Builder 50K, what I use), Topstep, Apex Trader Funding, TakeProfitTrader, Tradeify, Alpha Futures, Bulenox, FundingTicks. For each: evaluation fee (one-time or monthly), activation fee, profit target, max loss type (trailing, end-of-day, static) and amount, daily loss limit, max contracts (minis / micros), consistency rule, minimum trading days, news-trading rule, profit split, minimum payout, payout frequency, and scaling. prop-firms.md = one table (firms across, rules down) + 10 plain-words takeaways for a 18-year-old who trades NQ / MNQ day trades only. prop-firms.json = the same as [{firm, plan, fee, target, max_loss_type, max_loss, daily_loss, contracts, consistency, min_days, news_rule, split, min_payout, source, checked_on, verified}] with verified = true only when you read it on the firm's own page."),
    ("money-discount-codes", "money", "Prop-firm discount codes", "Which public discount codes or promos exist right now for those firms, and what each really costs", 10, "medium",
     ["discount-codes.md"],
     MONEY + "Find the public discount codes and promotions that are live today for MyFundedFutures, Topstep, Apex, TakeProfitTrader, Tradeify, Alpha Futures and Bulenox 50K evaluations. Never invent a code: only list a code you saw on the firm's own page, its official social account or its official newsletter, with the page name and the date you checked, and mark every other code UNVERIFIED. For each firm: list price, best verified code, price after the code, whether the code works on resets and activation fees, expiry if stated. Then one line on which firm is cheapest to try for 3 attempts. My real prices are Builder 25K $63 and Builder 50K $91.80 (one-time, $0 activation): compare against those. discount-codes.md = a table + a 'how I would double-check a code before paying' list."),
    ("money-payout-rules", "money", "Payout rule digest", "The payout rules of five prop firms in plain words, with the traps", 12, "hard",
     ["payout-rules.md", "payout-checklist.md"],
     MONEY + "Write a payout rule digest for MyFundedFutures (Builder and Core plans), Topstep, Apex, TakeProfitTrader and Tradeify: when the first payout is possible (minimum days, minimum profit, buffer above the starting balance), the consistency or best-day rule, maximum payout per request, how often, the split, fees on withdrawal, how long the money takes to arrive, what resets the account after a payout, and what makes a payout get denied. payout-rules.md = one section per firm with the exact wording of each rule (short quote) and the source page. payout-checklist.md = a 15-line checklist I can tick before I ask for my first payout, written so it works for any firm."),
    ("money-payout-plan", "money", "First payout plan template", "A worked template that turns a firm's rules into a day-by-day plan to the first payout", 10, "medium",
     ["payout-plan.md", "payout-plan.json"],
     MONEY + "Make a planning template for getting from the start of a 50K evaluation to the first payout on a funded account: the steps (pass the evaluation, activate, trade the minimum days, build the buffer, request), the numbers each step needs as placeholders to fill from the firm's own rules (target, max loss, buffer, minimum days, consistency), and a worked example that uses clearly marked ILLUSTRATIVE numbers (not the firm's real rules). payout-plan.json = {steps: [{name, rule_needed, how_to_check, typical_days}], inputs: {target, max_loss, buffer, min_days, consistency_pct}, formulas: {...}} so a script could fill it later. Say plainly that I must copy the real numbers from my firm's dashboard."),
    ("money-tax-setaside", "money", "Tax set-aside questions", "Questions for a CPA and a safe way to set money aside, for an 18-year-old US prop-firm trader", 12, "hard",
     ["tax-questions-for-cpa.md", "setaside-worksheet.json"],
     MONEY_TAX + "I am 18, a US resident, and I may receive payouts from a futures prop firm and trading income of my own. Explain in plain words the ideas I should know BEFORE I see a CPA (how a payout is usually reported to the IRS, what self-employment tax is, what estimated quarterly tax payments are, why many people set money aside from every payout, what the tax year and the quarter dates are) and then write the 25 best questions to ask a CPA, grouped: payouts and evaluation fees, trading business or hobby, deductions I may be able to claim (data, platform, education), futures contracts and how gains are treated, state tax, being claimed as a dependent, and paperwork. tax-questions-for-cpa.md = the explainer + the questions. setaside-worksheet.json = {inputs: [...], rows: [{payout, set_aside_pct_placeholder, note}], disclaimer} with the percentage left as a placeholder the CPA fills in. Do NOT give me a tax percentage as if it were advice."),
    ("money-tax-dependent", "money", "Dependent and parent questions", "What changes if my parents still claim me, as questions for a CPA", 8, "easy",
     ["dependent-questions.md"],
     MONEY_TAX + "I am 18 and my parents may still claim me as a dependent. Write a plain-words list of the questions to ask a CPA together with my parents about: how my trading or payout income interacts with being a dependent, filing my own return, whether I need to file, any special rule for young people with unearned income, health insurance and student aid (FAFSA) effects, and what records my parents and I should each keep. dependent-questions.md = 20 questions, each with one line on why it matters. No answers presented as fact."),
    ("money-tax-records", "money", "Trading records checklist", "What to save and how, so tax time is easy", 7, "easy",
     ["records-checklist.md", "records-template.json"],
     MONEY_TAX + "Write a record-keeping checklist for a young futures trader: what to save every month (payout statements, evaluation and reset fees, data and platform subscriptions, broker or Kalshi year-end forms, bank transfers), where to keep it, a 10-minute monthly routine, and a yearly routine. records-template.json = {months: [{month, payouts: [], fees: [], subscriptions: [], notes}]} as an empty example with 2 filled sample rows marked ILLUSTRATIVE. Never put an account number, login, SSN or ID in anything."),
    ("money-nq-events", "money", "NQ scheduled-news calendar", "Which scheduled US events move NQ, at what time, how often", 12, "medium",
     ["nq-events.md", "nq-events.json"],
     MONEY + "Make a calendar guide for NQ futures: the scheduled US releases and events that usually move the Nasdaq-100 (CPI, PPI, jobs report, FOMC decision and minutes and press conference, jobless claims, ISM, GDP, retail sales, consumer confidence, Fed speeches, big-tech earnings weeks, quad witching and monthly options expiry, index rebalances) with the usual release time in New York time, how often, and what is usually different about that day for a short-term trader (wider ranges, spikes at the release, quieter afterwards). Be honest about what is common knowledge and what you could not verify; no invented statistics. nq-events.md = a table + the 6 events that matter most + 'how a rule-based bot should treat each' as a suggestion. nq-events.json = [{event, time_et, frequency, usual_effect, source, verified}]."),
    ("money-news-rules", "money", "Prop-firm news rules", "What each firm says about trading during news, with the exact windows", 9, "medium",
     ["news-rules.md"],
     MONEY + "For MyFundedFutures, Topstep, Apex, TakeProfitTrader and Tradeify: what the firm's rules say about trading around scheduled news (restricted windows before and after releases, whether holding through is allowed, penalties). Quote the rule in a few words and give the page. news-rules.md = a table (firm, rule, window, penalty, source, checked date) and a 'what this means for a bot that trades 02:00-15:30 New York time' paragraph for each firm, marked as my reading, not the firm's."),
    ("money-cme-holidays", "money", "CME holiday and early-close calendar", "The next 12 months of CME equity-index futures holidays and early closes", 9, "medium",
     ["cme-holidays.md", "cme-holidays.json"],
     MONEY + "From CME Group's own holiday calendar, list the next 12 months of holidays and early closes that affect CME equity index futures (NQ, MNQ, ES): the date, the day name, whether the market is closed, closes early (at what New York time) or has a trading halt, and when the next session reopens. Mark any date you could only infer as UNVERIFIED. cme-holidays.json = [{date, name, effect, close_et, reopen_et, source, verified}]. cme-holidays.md = the same as a table plus 5 plain lines on what a day-trading bot should do on a short day."),
    ("money-nq-roll", "money", "NQ contract roll dates", "The quarterly NQ / MNQ roll for the next four contracts", 8, "easy",
     ["nq-roll.md", "nq-roll.json"],
     MONEY + "List the next four quarterly NQ / MNQ contracts (month codes H M U Z): last trading day, usual volume-roll date (when most volume moves to the next contract), and the New York time of settlement, from CME Group's pages. Explain in plain words what a roll does to a chart and to a bot (the gap between contracts, why back-adjusting matters, what to do on roll day). nq-roll.json = [{contract, last_trade, usual_roll, settlement_et, source}]."),
    ("money-kalshi-fees", "money", "Kalshi fee digest", "How Kalshi charges, with worked examples", 10, "medium",
     ["kalshi-fees.md", "fee-table.json"],
     MONEY + "From Kalshi's own help center and fee schedule: how trading fees are calculated for event contracts, whether they differ by market type, settlement and withdrawal costs, and any minimum. Then work out the fee for buying 1, 10 and 100 contracts at 10, 25, 50, 75 and 90 cents and show the break-even win rate after fees at each price. fee-table.json = [{price_cents, contracts, fee, break_even_win_pct}] with your formula written in the markdown. kalshi-fees.md = the rules in plain words + the table + 5 things a new user gets wrong. State that rules can change and that I must check the app. This is about understanding costs only."),
    ("money-kalshi-scan", "money", "Kalshi market-type scan", "Which kinds of Kalshi markets could have an edge after fees, and how to measure it", 12, "hard",
     ["kalshi-scan-method.md", "kalshi-watchlist.json"],
     MONEY + "Do NOT give live prices or tell me what to bet. Describe the TYPES of Kalshi markets (economic releases such as CPI and jobs numbers, the Fed decision, daily index ranges, weather, others you find) and for each: how its price relates to something I can measure (a consensus forecast, a historical distribution, an index level), how fast the market usually resolves, how big the fee is relative to a typical edge, and what data I would need to test whether any edge survives fees. kalshi-watchlist.json = [{market_type, measurable_anchor, resolves, data_needed, fee_drag_note, difficulty}]. kalshi-scan-method.md = a step-by-step method to test one market type on past data (paper only, with a table of the results I should record) and the three most common mistakes."),
    ("money-kalshi-vs-futures", "money", "Kalshi against futures", "How event contracts and NQ futures differ as places to put risk money", 9, "medium",
     ["kalshi-vs-futures.md"],
     MONEY + "Compare Kalshi event contracts with NQ / MNQ futures for a small account: how profit and loss work (capped payoff against open-ended), cost per trade, leverage and margin, trading hours, how much a bad day can cost, what a beginner can lose fastest, how each fits a rule-based bot, and what each needs from me (age, identity checks, tax forms: as questions for a CPA). kalshi-vs-futures.md = a table + 8 plain lines + 5 questions to ask before using either."),
    ("money-content-ideas", "money", "Trading journey content ideas", "30 honest content ideas for an 18-year-old documenting a prop-firm journey", 9, "easy",
     ["content-ideas.md", "content-calendar.json"],
     MONEY + "Give me 30 short-video / post ideas for an 18-year-old documenting a futures prop-firm journey with a rule-based paper-trading bot, in an honest, no-hype style: each with a hook line (max 12 words), what to show on screen, and what NOT to say. Mix: process (building the bot, what a loss taught me), numbers (always with the risk and the sample size), explainers (what is a trailing drawdown), behind the scenes. No income claims, no 'guaranteed', no get-rich promises. content-calendar.json = a 4-week plan [{week, day, idea_number, format, minutes_to_make}] with 3 posts a week."),
    ("money-content-risk-kit", "money", "Safe-language kit for posts", "What not to say, and the disclosure lines to use", 7, "easy",
     ["risk-language-kit.md"],
     MONEY + "Write a plain-words safe-language kit for someone posting about futures trading and prop firms: the phrases to avoid (income claims, guarantees, 'passive income', screenshots without context), a short risk line to put on posts, how to disclose an affiliate or discount code, how to show results honestly (period, sample size, costs, max drawdown), and the platform rules in general terms for TikTok, YouTube and X. Mark clearly that this is general guidance and not legal advice, and list 5 questions to ask a lawyer or the platform's help center. risk-language-kit.md = checklists and ready-to-paste lines."),
    ("money-eval-traps", "money", "Evaluation and payout traps", "The top ways traders lose an evaluation or a payout, and how a bot avoids each", 11, "medium",
     ["eval-traps.md", "eval-traps.json"],
     MONEY + "List the 25 most common ways traders fail an evaluation or lose a payout at futures prop firms (trailing drawdown misunderstandings, the daily loss limit, consistency rules, news windows, copy trading and hedging bans, holding past the close, scaling limits, inactivity, using the wrong account) with one plain sentence each and, for each, how a rule-based bot with a position-size cap, a flat time and a weekly stop could be built to avoid it (as a suggestion only). eval-traps.json = [{trap, rule_type, how_to_avoid, bot_guard_idea}]. eval-traps.md = the same grouped by type with the 5 worst first."),
    ("money-risk-budget", "money", "Risk budget worksheet", "What several evaluation attempts cost, as a simple worksheet", 8, "easy",
     ["risk-budget.md", "risk-budget.json"],
     MONEY + "Make a worksheet that answers: if each 50K evaluation costs a fee and I may need several attempts, what is the expected cost to reach a funded account and a first payout? Inputs as placeholders I fill with my own honest numbers (fee, pass rate, reset fee, payout size, split); formulas written out in words and in json; and a worked example with clearly ILLUSTRATIVE numbers (including the $91.80 Builder 50K price). Add a table of how the expected cost changes if the pass rate is 20%, 35%, 50% and 65%. Say plainly that a pass rate is a guess until I have many attempts. risk-budget.json = {inputs: {...}, formulas: {...}, table: [...]}."),
    ("money-futures-costs", "money", "All-in cost of trading NQ and MNQ", "The real cost per contract round trip at prop firms and brokers", 11, "hard",
     ["futures-costs.md", "futures-costs.json"],
     MONEY + "Work out the all-in cost of one round trip of 1 NQ and 1 MNQ contract: the exchange fee, the clearing and NFA fees, the broker or prop-platform commission, and typical slippage in ticks, for MyFundedFutures, Topstep, Apex, TakeProfitTrader and a typical discount futures broker; plus monthly data (CME non-professional) and platform fees. Sources for every number. Compare my bot's cost model of 1.90 dollars commission plus 2 ticks slippage per micro round trip (about 2.90 dollars all-in) against what you found and say if it looks too low or too high. futures-costs.json = [{firm_or_broker, product, commission_rt, exchange_nfa_rt, total_rt, source, verified}]."),
    ("money-business-setup", "money", "Business setup questions", "Do I need an LLC, an EIN or a separate bank account? Questions for a CPA", 8, "easy",
     ["business-setup-questions.md"],
     MONEY_TAX + "I am 18 and may earn payouts from prop firms. Write a plain-words guide to the questions to ask a CPA (and, where it fits, a lawyer) about: whether to keep trading income as a sole proprietor, when an LLC or an EIN could make sense, a separate bank account for payouts and fees, how a firm usually pays and what form it sends, state registration, and what to do about estimated taxes. business-setup-questions.md = 20 questions with a one-line 'why this matters' each and a 'what to bring to the CPA' checklist. Never ask me for or write my SSN, ID or bank details."),
]
INGEST = {
    "money-prop-compare": "python tools/bridge_ingest.py lists prop-firms.md and prop-firms.json under Deliveries (text only, never run). Claude reads the json, checks each row against the firm's page, and updates the prop-firm prices and rules in docs/ (the owner's real prices stay as they are).",
    "money-discount-codes": "python tools/bridge_ingest.py previews discount-codes.md. Claude re-checks every code that is not marked UNVERIFIED and quotes only checked ones, next to the owner's real prices.",
    "money-payout-rules": "python tools/bridge_ingest.py previews both files. Claude compares them with the MFFU payout rules already in docs/ and turns the checklist into the pre-payout checklist.",
    "money-payout-plan": "python tools/bridge_ingest.py previews the plan; the json is read as data. Claude fills the inputs from the owner's real MFFU dashboard numbers and keeps the plan in docs/.",
    "money-tax-setaside": "python tools/bridge_ingest.py previews the questions. Claude saves them as a 'questions for my CPA' page; the owner brings them to a CPA. The set-aside percentage stays blank until a CPA gives one.",
    "money-tax-dependent": "python tools/bridge_ingest.py previews the list. Claude adds it to the CPA question page for the owner and a parent to read together.",
    "money-tax-records": "python tools/bridge_ingest.py previews both files. Claude turns the json into the monthly records template the owner fills in (no account numbers).",
    "money-nq-events": "python tools/bridge_ingest.py previews the table; the json is read as data. Claude compares it with data/news/events.csv (the calendar the bot already uses) and lists what is missing, never changing the bot.",
    "money-news-rules": "python tools/bridge_ingest.py previews the table. Claude compares it with the bot's news rules and reports differences to the owner (paper only, no bot change).",
    "money-cme-holidays": "python tools/bridge_ingest.py previews the table; the json is read as data. Claude checks each date against CME's page and the data/ calendar and reports gaps.",
    "money-nq-roll": "python tools/bridge_ingest.py previews the table. Claude checks it against data/NQ_rolls.json and notes the next roll in docs/.",
    "money-kalshi-fees": "python tools/bridge_ingest.py previews the digest. Claude recomputes the fee table from the formula and, if it matches, keeps it with the Kalshi notes.",
    "money-kalshi-scan": "python tools/bridge_ingest.py previews the method. Claude turns one market type into a paper test on past data; nothing is traded.",
    "money-kalshi-vs-futures": "python tools/bridge_ingest.py previews the comparison. Claude keeps it as a read-only note next to the Kalshi City data.",
    "money-content-ideas": "python tools/bridge_ingest.py previews both files. Claude copies the calendar into the owner's notes; the owner picks and posts himself.",
    "money-content-risk-kit": "python tools/bridge_ingest.py previews the kit. Claude keeps it as the safe-language page the owner checks before posting.",
    "money-eval-traps": "python tools/bridge_ingest.py previews both files. Claude maps each trap to a guard the bot already has or does not have, and reports the gaps (no bot change without the owner).",
    "money-risk-budget": "python tools/bridge_ingest.py previews both files. Claude recomputes the table from the formulas and keeps the worksheet; the owner enters his real numbers.",
    "money-futures-costs": "python tools/bridge_ingest.py previews both files. Claude compares the totals with the cost model in the backtests and reports whether the costs are too low (no change without the owner).",
    "money-business-setup": "python tools/bridge_ingest.py previews the questions. Claude adds them to the CPA question page; the owner decides after he has talked to a CPA.",
}

RULES = ("How to deliver (the OLYMPUS sync rules): only add files under handoff/inbox/{id}/ (open a pull request on branch chatgpt/{id}); never edit the "
         "bots, live_model*.json, engine/, .github/ or any existing app; no secrets, keys, tokens or logins anywhere; plain files only (PNG / WebP, SVG, JSON, "
         "Markdown, text; no scripts); paper trading only, nothing that places or arms real orders. When finished, add one line to handoff/inbox/{id}/DONE.md: "
         "what you made, the file list, and anything Claude must wire. If you are blocked, write handoff/inbox/{id}/QUESTION.md instead of guessing. "
         + CAPS)


def jobs():
    out = []
    for (jid, cat, title, makes, minutes, diff, files, body) in J:
        files = list(files)
        prompt = f"Job {jid}. {CTX}\n\n{body}\n\nFiles to deliver (exact names): {', '.join(files)}.\n\n{RULES.format(id=jid)}"
        job = {"id": jid, "cat": cat, "title": title, "makes": makes, "tool": "chatgpt", "prompt": prompt, "files": files + ["DONE.md"],
               "lands": f"handoff/inbox/{jid}/", "minutes": minutes, "difficulty": diff}
        if jid in INGEST:
            job["ingest"] = INGEST[jid]               # how Claude takes it in (tools/bridge_ingest.py), shown on the Library card
        out.append(job)
    return out


def build():
    return {"v": 1, "kind": "olympus-bridge-jobs", "cats": [{"id": i, "name": n} for i, n in CATS], "jobs": jobs()}


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(dumps(build()))
    print(f"{len(J)} jobs -> {os.path.relpath(OUT, ROOT)}")
