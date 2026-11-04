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
CTX = ("Context: I am building OLYMPUS, a set of phone web apps (three.js, dark futuristic Greek-god theme: marble, gold #f5c96a and violet #a855f7 "
       "on near-black). I am 18 and use an iPhone. Use plain words.")
CAPS = "File limits: PNG / WebP up to 5 MB each, SVG up to 200 KB, JSON up to 1 MB, Markdown / text up to 200 KB, JS up to 100 KB."

CATS = [
    ("textures", "Textures and skies"), ("art", "App icons and splash art"), ("logo", "Logos and glyphs"), ("sound", "Sound-design briefs"),
    ("copy", "Copywriting"), ("lore", "Lore and story"), ("obsidian", "Obsidian vault"), ("strategy", "Strategy brainstorms"),
    ("research", "Research summaries"), ("fixtures", "Test data"), ("docs", "Docs polish"), ("mockup", "UI mockups"), ("names", "Names and taglines"),
]
APPS = "Jarvis, Zenith, Oracle, Odeon, Fates, Data City, Daphne, Prometheus, Pantheon, Mind, Arena, Kalshi, Tyche, Hermes, Plutus, Ares, Athena, Forum, Labyrinth, Argus, Nemesis, Chronos, Hephaestus, Bridge"

# (id, cat, title, makes, minutes, difficulty, files, body)
J = [
    # ---------------------------------------------------------------- textures and skies
    ("tex-marble-white", "textures", "White marble PBR set", "Four tileable 1024 px maps of white Greek marble (colour, normal, roughness, ambient occlusion)", 8, "medium",
     ["marble-white-albedo.png", "marble-white-normal.png", "marble-white-roughness.png", "marble-white-ao.png"],
     "Make a seamless tileable PBR texture set of polished white Greek marble with soft grey veins, 1024x1024 each: albedo (colour), normal (tangent space, the usual blue-purple look, gentle), roughness (greyscale, polished = dark), ambient occlusion (greyscale, subtle). No text, no logo, evenly lit, no baked shadows."),
    ("tex-marble-black-gold", "textures", "Black marble with gold veins", "Four tileable maps of black marble with thin gold veins", 8, "medium",
     ["marble-black-albedo.png", "marble-black-normal.png", "marble-black-roughness.png", "marble-black-ao.png"],
     "Make a seamless tileable PBR set of black marble with thin branching gold veins, 1024x1024: albedo, normal, roughness (veins slightly rougher), ambient occlusion. Evenly lit, no text, no baked shadows."),
    ("tex-gold-brushed", "textures", "Brushed gold", "Brushed gold metal maps with a long horizontal grain", 7, "easy",
     ["gold-albedo.png", "gold-normal.png", "gold-roughness.png"],
     "Make a seamless tileable brushed gold metal set, 1024x1024: albedo (warm #e0b030 tones), normal (fine horizontal brushing), roughness (greyscale, medium-low). Evenly lit, no text, no reflections of a room."),
    ("tex-bronze-aged", "textures", "Aged bronze", "Bronze with green-blue patina in the cracks", 7, "easy",
     ["bronze-albedo.png", "bronze-normal.png", "bronze-roughness.png"],
     "Make a seamless tileable aged bronze set, 1024x1024: albedo (warm bronze with verdigris in the recesses), normal (hammered, shallow), roughness (greyscale, patina rougher). Evenly lit, no text."),
    ("tex-parchment", "textures", "Parchment and scroll paper", "Tileable parchment plus a scroll edge strip", 6, "easy",
     ["parchment-albedo.png", "parchment-edge.png"],
     "Make a seamless tileable parchment paper texture 1024x1024 (warm cream, faint fibres, a few tiny stains, no writing), and a 1024x256 strip of burnt, torn parchment edge on a transparent background (PNG with alpha)."),
    ("tex-fire-sheet", "textures", "Fire sprite sheet", "A 4 x 4 sprite sheet of flame frames on transparent background", 9, "hard",
     ["fire-sheet-4x4.png"],
     "Make one PNG sprite sheet 2048x2048, a 4 x 4 grid of 512x512 frames of a single torch flame burning (loops from the last frame back to the first), orange-yellow core fading to deep red at the tips, transparent background (alpha), no smoke, no torch, no text. Add the frame order (left to right, top to bottom) to DONE.md."),
    ("tex-water-caustics", "textures", "Water caustics and ripples", "A tileable caustics light pattern and a water normal map", 7, "medium",
     ["caustics.png", "water-normal.png"],
     "Make two seamless tileable 1024x1024 textures: (1) underwater caustics, bright light net on pure black, (2) a gentle water ripple normal map (tangent space). No text."),
    ("tex-lava-cracks", "textures", "Lava and glowing cracks", "Dark crust with glowing orange cracks, colour and emissive maps", 8, "medium",
     ["lava-albedo.png", "lava-emissive.png"],
     "Make a seamless tileable 1024x1024 pair: albedo of dark cooled lava crust, and an emissive map (cracks glowing orange-yellow on pure black, same layout). No text."),
    ("sky-time-of-day", "textures", "Four times of day skies", "Four ultra-wide seamless sky panoramas: dawn, noon, dusk, storm", 10, "medium",
     ["sky-dawn.png", "sky-noon.png", "sky-dusk.png", "sky-storm.png"],
     "Make four seamless equirectangular-style sky panoramas, 4096x2048 if you can (otherwise as wide as possible, 2:1): dawn (gold and pink over layered clouds), noon (clear deep blue with few thin clouds), dusk (violet and orange with a first star), storm (dark green-grey cloud wall with a distant lightning). No ground, no sun disc detail, no text."),
    ("sky-olympus-cube", "textures", "Mount Olympus cube-map faces", "Six square faces for a skybox of Mount Olympus above the clouds at night", 12, "hard",
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
    ("glyph-greek-letters", "logo", "Greek letter glyph set", "Twenty-four gold Greek letters as SVG", 8, "easy",
     ["greek-glyphs.svg", "README.md"],
     "Design the 24 Greek capital letters (Alpha to Omega) as ONE SVG sprite with a <symbol id=\"alpha\"> ... <symbol id=\"omega\"> each, 64x64 viewBox, bold geometric futuristic style, filled with currentColor, no text elements (draw the shapes as paths), no scripts. README.md lists the ids."),
    ("logo-wordmarks", "logo", "OLYMPUS wordmarks", "Six wordmark styles in SVG", 9, "medium",
     ["wordmark-01.svg", "wordmark-02.svg", "wordmark-03.svg", "wordmark-04.svg", "wordmark-05.svg", "wordmark-06.svg"],
     "Design 6 wordmarks of the word OLYMPUS as SVG outlines (letters drawn as paths, not text elements, no fonts needed), viewBox 0 0 640 128: wide futuristic caps, carved marble caps, thin gold line caps, neon tube caps, laurel-decorated caps, minimal monoline. No scripts, no raster images."),
    ("emblem-ranks", "logo", "Rank emblems", "Five rank emblems: Mortal, Hero, Demigod, Olympian, Titan", 8, "medium",
     ["mortal.svg", "hero.svg", "demigod.svg", "olympian.svg", "titan.svg"],
     "Design 5 rank emblems for a discipline app as SVG (viewBox 0 0 256 256, no text, no scripts, no raster): Mortal (a plain bronze ring), Hero (a shield with a laurel), Demigod (a winged shield with a small star), Olympian (a golden crown of light with columns), Titan (a huge glowing crown with lightning). Each clearly grander than the last."),
    # ---------------------------------------------------------------- sound-design briefs (text only)
    ("sound-ui-sfx", "sound", "UI sound briefs", "Synth-parameter descriptions for the six UI sounds", 8, "medium",
     ["ui-sounds.json", "README.md"],
     "Write sound-design briefs (TEXT ONLY, do not make audio) for these UI sounds of a futuristic Greek-god app: tick, tap, portal, thunder, rankup, pad. In ui-sounds.json give for each sound an object with: feel (one plain sentence), oscillators (type, frequency in Hz, detune), envelope (attack, decay, sustain, release in seconds), filter (type, cutoff Hz, resonance, any sweep), noise (type, level), reverb (size, mix), lfo (target, rate, depth), length in ms, and a note on how it must stay quiet and soft on a phone. README.md explains the file in plain words."),
    ("sound-ambient", "sound", "Ambient drone briefs", "Per-app ambient pad descriptions", 8, "medium",
     ["ambient.json"],
     "Write ambient background sound briefs (TEXT ONLY, no audio) for 12 apps (Jarvis, Zenith, Oracle, Odeon, Fates, Data City, Daphne, Prometheus, Pantheon, Mind, Arena, Tyche). For each app give: mood in 5 words, root note and scale, 3 oscillator layers (waveform, octave, detune cents), a slow filter movement (cutoff range Hz, rate), a noise bed (type, level), reverb size, a quiet loudness target in dB, and one 'event' sound idea. Must be very soft: it plays under speech."),
    ("sound-jarvis-fx", "sound", "Jarvis voice effects brief", "How to make her voice feel futuristic without hurting clarity", 6, "easy",
     ["jarvis-voice-fx.md"],
     "Write a short brief (Markdown, plain words) for the effects chain on Jarvis's female voice in a phone web app (Web Audio API): a gentle formant lift, a very light chorus, a short plate reverb, a soft high shelf, a ducking rule for background music. Give each effect as a Web Audio node with exact starting parameter values, and say what to change if the voice sounds metallic or muddy."),
    ("sound-win-loss", "sound", "Win and loss stingers", "Briefs for celebration and calm 'bad day' sounds", 6, "easy",
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
    ("fx-demo-trades", "fixtures", "Synthetic trade history", "200 made-up trades in the apps' JSON shape", 8, "medium",
     ["trades.json", "README.md"],
     "Generate a SYNTHETIC (clearly fake) list of 200 NQ/MNQ trades over the last 120 weekdays as trades.json: an array of {id, day (YYYY-MM-DD), time (HH:MM, between 02:00 and 15:30 ET), side (long/short), qty, entry, stop, target, exit, risk_pts, pnl (dollars after 1.25 points of costs), r (R multiple), exit_reason (target/stop/breakeven/time)}. Make it realistic: about 1 trade a day, a win rate near 45 percent, a few 8R winners, stop 8-60 points. README.md says it is fake test data."),
    ("fx-demo-kalshi", "fixtures", "Synthetic Kalshi feed", "A fake kalshi.json in the feed contract's shape", 7, "medium",
     ["kalshi.json", "README.md"],
     "Generate a SYNTHETIC kalshi.json for testing an app: {v: 3, t (unix), name, running, balance, today_pnl, week_pnl, total_pnl, positions: [...6 open bets...], trades: [...80 settled bets with ticker, title, side, contracts, price, pnl, t, category, strategy...], days: [[YYYY-MM-DD, pnl]...30], strategies: [{name, wins, losses, total_pnl}...3]}. Crypto 15-minute markets, gold, S&P. Realistic numbers, balance near 2,400 dollars. README.md says it is fake."),
    ("fx-demo-weeks", "fixtures", "Synthetic weekly recaps", "Eight weeks of fake wrapped data", 7, "medium",
     ["weeks.json"],
     "Generate SYNTHETIC weekly recap data for 8 weeks as weeks.json: [{from, to, net, trades, wins, losses, best_trade: {day, pnl, r}, worst_trade: {...}, discipline: score 0-100, rules_broken: [..]}]. Include one red week and one 8R week. Fake numbers only."),
    ("fx-demo-planner", "fixtures", "Synthetic planner data", "Fake tasks, events and habits for tests", 8, "medium",
     ["planner-demo.json"],
     "Generate SYNTHETIC planner data as planner-demo.json: {tasks: 30 [{id, title, date, done, p (0-3), est (minutes), proj}], events: 20 [{id, title, date, start, end}], habits: 5 [{id, name, color, done: [dates over 90 days]}]}. Dates within 2026-09-01 to 2026-11-30. Normal student/trader life, nothing private."),
    # ---------------------------------------------------------------- docs polish
    ("docs-readme-plain", "docs", "A plain-words README", "A friendly README for the repo front page", 9, "easy",
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
]

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
        out.append({"id": jid, "cat": cat, "title": title, "makes": makes, "tool": "chatgpt", "prompt": prompt, "files": files + ["DONE.md"],
                    "lands": f"handoff/inbox/{jid}/", "minutes": minutes, "difficulty": diff})
    return out


def build():
    return {"v": 1, "kind": "olympus-bridge-jobs", "cats": [{"id": i, "name": n} for i, n in CATS], "jobs": jobs()}


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(dumps(build()))
    print(f"{len(J)} jobs -> {os.path.relpath(OUT, ROOT)}")
