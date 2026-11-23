# Both computers fast (2026-11-02; v2 deep tune 2026-11-03)

**The short answer:** the Surface's 4 GB memory is soldered to the board and can't be upgraded. Cleaning helps, but
NinjaTrader plus the bot will always fill 4 GB. The best fix for the money is a **used Lenovo ThinkCentre M720q Tiny
(i5-9500T, 16 GB, SSD), about $250** as the bot's own computer (details below). Until then, `tools/bat/CLEAN_PC.bat` keeps
the Surface as light as it can be.

**Low memory now (2026-11-03):** double-click **`tools/bat/BOT_LITE.bat`**: the bot drops from ~690 MB to ~180 MB and trades the
same. PC-off options and costs: `docs/PC_OFF_PLAN.md`.

## Surface (the bot PC): 3 steps
1. After 4:05 PM ET (or on the weekend), double-click **`tools/bat/CLEAN_PC.bat`** in the bot folder. Click **Yes** once when
   Windows asks. It cleans, then runs the **v2 deep tune** (below) and prints a **health score** before and after.
2. Restart the Surface after 4:05 PM ET (the bot comes back by itself).
3. Do what its **NinjaTrader check** lines say (yellow lines). The bot's MNQ chart with LE_BarFeed stays at **30 days**.

Something feels wrong after the tune? Double-click **`tools/bat/UNDO_PC_TUNE.bat`** and click **Yes**: every deep-tune change goes
back to exactly what it was (safe any time, also while the bot trades). Keep the Surface plugged in and on its kickstand.

## Main PC: 3 steps
1. After step 1 on the Surface, a **`PC_KIT`** folder (with the deep tune and `tools/bat/UNDO_PC_TUNE.bat`) appears in your OneDrive (or on the Surface's Desktop if it has
   no OneDrive: copy it to a USB stick). Open it on the main PC.
2. Double-click **`tools/bat/CLEAN_PC.bat`** in it. Click **Yes** once.
3. Send Claude the **`PC_REPORT-<name>.txt`** it writes next to tools/bat/CLEAN_PC.bat (a photo is fine). It shows what the main PC
   is and whether it can run the bot.

## Disk full? CLEAN_STORAGE (both computers, 2026-11-04)
One double-click, same on the Surface and the main PC: **`tools/bat/CLEAN_STORAGE.bat`** (in the bot folder; or download it alone from
the site page `.../nq-dashboard/pc/`, section "Clean storage": it then fetches `pc/clean_storage.ps1` itself).
1. It prints a plain table of what it would free (a size per category) and asks **Y**.
2. It clears only safe things: temp files (older than 1 day), browser caches (never passwords or sign-ins), thumbnail and
   icon caches, crash dumps and error reports, npm / pip caches, NinjaTrader's own old log and trace files (14+ days), the
   bot's own old logs / backups (the 3 newest stay) / `data\*.corrupt-*` / every `__pycache__` of its code / the research
   replay cache `research\runs\_cache` (14+ days, rebuilt when needed) / old `OLYMPUS_BACKUP_*.zip` code zips in the bot
   folder (14+ days, the 2 newest stay). Windows asks once (click **Yes**) for its own part: Windows temp, the Windows
   Update download cache, the Delivery Optimization cache, Windows crash dumps and old Windows logs. The **Recycle Bin** and
   **Windows.old** (big, no way back to the old Windows) are asked about separately.
   **Second drive (2026-11-19):** if the PC has another fixed drive (D:, E: ...) with room and the bot and NinjaTrader are
   stopped, ONE more Y/N question moves the bot's old archives that nothing reads (`data\_pre_clean_backup`,
   `data\_cfd_archive`, `data\duka_cache`, `data\nt_export`, offered from 200 MB together) to
   `<drive>\LiquidityEngine-archive` (robocopy /MOVE; a README.txt there says where they came from). Never the bot,
   NinjaTrader, `backups\` (the bot restores from it) or anything live.
3. It ends with **"Done: freed X GB. C: now Y GB free."** and writes every removed file with its size to
   `logs\clean_storage-DATE.txt` (no bot folder: `%LOCALAPPDATA%\LiquidityEngine\logs`).
- **Never touched:** the bot's `data\` state files, `.env.local.ps1`, live_state / accounts / journals, the bar archive
  `data\nt_bars`, NinjaTrader's database (`db`, `db\cache` included), workspaces, templates, settings, `bin`, `le_feed`
  (the bot's bars), `incoming` / `outgoing` (orders), and anything outside its allow-list (a wrong `TEMP` variable cannot widen it).
- **If the bot or NinjaTrader is running** it says so and skips their folders, Windows.old and the archive move; only temp
  files (3 days old then), caches and Windows junk are cleaned. For the full clean: when the bot is flat, STOP BOT, close
  NinjaTrader, double-click tools/bat/CLEAN_STORAGE.bat again.
- `tools/bat/CLEAN_STORAGE.bat -DryRun` (or `clean_pc.ps1 -Storage -DryRun`) only prints the table. `-KeepDays 30` keeps the bot's
  logs longer. OneDrive: it prints the "Free up space" (Files On-Demand) hint and warns not to use it on the NinjaTrader 8 folder.
- The PC health line **Storage** (free GB on the bot's drive + bot folder + NinjaTrader folder size; amber < 15 GB, red
  < 2 GB, fix "Run tools/bat/CLEAN_STORAGE.bat") rides the normal heartbeat (`pc_health.storage`) and shows on Jarvis' System view.
- Test: `python -X utf8 -m tests.test_clean_storage`.

## PC_CARE: one icon that looks after THIS PC (both computers, 2026-11-04)
`tools/bat/PC_CARE.bat` (runs `scripts\pc_care.ps1`; downloaded alone it fetches the script from the site's `pc/` page, like CLEAN_STORAGE).
It finds the role by itself (**bot folder here = MAIN PC**; no bot folder and a Surface, or a small laptop with 8 GB or less = **SURFACE**;
`-Role main|surface` forces it), prints a plain table (what it is now / what it will be), asks **Y**, and ends with one line:
`BOT PC HEALTHY: YES` (or `NO, look at: ...`). Windows asks once (click Yes) for the power plan; the startup / background / effects
parts run in your own account.

| Part | Main PC (bot + NinjaTrader) | Surface (hot, dark screen, little memory) |
|---|---|---|
| Power plan "PC Care" (a copy; your plan stays and comes back on undo) | from High performance: never sleeps / hibernates (plugged in), screen off after 10 min, disk never sleeps, USB selective suspend off, PCI Express and Wi-Fi power saving off, CPU 100% | from Balanced: CPU top speed 75% on AC and battery (turbo off = far less heat), cooling policy active (fan first), adaptive brightness off, brightness 100% plugged in, battery saver does not dim the screen and does not start by itself while plugged in, screen off 10 min (5 on battery) |
| Startup apps (your account) | lists every Run entry with a verdict; asks Y/N for each it suggests (Teams, Spotify, Discord, Steam, Epic, Skype, Zoom, Adobe, iTunes, Dropbox, Slack, Edge / Chrome auto-launch, game launchers, PC-maker helpers); flips the same switch as Task Manager > Startup apps (`StartupApproved\Run`); the Run entry itself is never deleted | same |
| Never offered | security / Defender, OneDrive, NinjaTrader, the bot, python, Obsidian, Claude, git, drivers (audio, touchpad, Intel / NVIDIA / AMD, Surface), VPN / remote tools, anything it does not recognise; machine-wide (all users) entries are listed and left alone | same |
| Background apps (Store) | `GlobalUserDisabled=1` (classic programs such as NinjaTrader are not affected) | same |
| Visual effects | transparency, window animation, taskbar animation off, "best performance" (rest after sign-out) | same |
| Windows search indexing | two SYSTEM tasks stop `WSearch` weekdays 01:15 ET and start it 16:05 ET (shown on this PC's clock; stopped at once if it is market time); files are found slower in the day, apps are still found | same |
| Health check (read only, always) | uptime (amber at 10+ days), RAM (amber 88%, red 95%), disk (amber < 15 GB, red < 2 GB), sleep setting, battery, temperature **only if Windows shows it**, and in market hours (weekdays 01:15-16:05 ET) NinjaTrader running and the bot answering on its port | the same minus NinjaTrader and the bot |

- **Honest limits:** the CPU temperature is read from the ACPI thermal zone or the Windows thermal counter; most PCs show neither without
  HWiNFO / Core Temp, and then the line says "not shown by Windows" (it never guesses). The Surface's **content adaptive brightness** tick is
  the graphics driver's, not a Windows power setting: the table prints the two Settings paths to untick it by hand once. A power setting a
  PC does not have is reported ("this PC does not have that setting") and skipped.
- **Undo:** every change is written to an undo file BEFORE it is made (`%LOCALAPPDATA%\LiquidityEngine\pc_care_user.json` for your account,
  `%ProgramData%\LiquidityEngine\pc_care_state.json` for the Windows part; the first before-value is kept, so running it twice loses
  nothing). `tools/bat/UNDO_PC_TUNE.bat` undoes PC_CARE first (a copy of the script sits next to the account undo file), then the deep tune; a step that
  cannot be undone is said in plain words and stays in the file for the next try. If the old power plan is gone it falls back to Balanced.
- `tools/bat/PC_CARE.bat -DryRun` prints the table and changes nothing (no undo file, no health file); `-CheckOnly` runs only the health check.
- The last result is `logs\pc_care.json` (no bot folder: `%LOCALAPPDATA%\LiquidityEngine\pc_care.json`). The bot's PC health block shows it as the
  **PC care** line (`engine/pc_health.py`, display only: green when ok, amber when it found something or is older than 45 days, never red, no
  push; no line if PC_CARE was never run) and Jarvis / Argus show it in the System view (amber ones first).
- Not done on purpose: services (CLEAN_PC / the deep tune own those), Defender, network, memory settings, anything in `HKLM`.
- Test: `python -X utf8 -m tests.test_pc_care` (about 2 min with pwsh; a fake Windows with a JSON world, a UAC that really runs the
  elevated child, StrictMode 2 repeats).

## What CLEAN_PC does
- **On both computers:** turns off apps that start with Windows but trading doesn't need (switch them back on in Task
  Manager > Startup apps). Also: a lighter Windows (no transparency or animations), old junk files deleted. The deep
  part (search indexing off, Windows clean-up, Defender scan) runs only outside 01:15-16:05 ET on weekdays.
- **It never touches:** NinjaTrader, the bot (python), Edge, OneDrive, Git or Claude.
- **NinjaTrader check (read-only, every run):** never closes or changes NinjaTrader. It reads NinjaTrader's folder and
  reports:
  - OneDrive syncing that folder (pause syncing while trading)
  - ATI on or off
  - each workspace: charts, days loaded, Tick Replay, indicators
  - how big the tick data is

  It saves a backup copy of your workspaces in `logs\nt_workspaces-DATE` before you change anything.
- **PC report:** CPU, cores, memory (size, speed, slots), disk (SSD or not, free space), graphics, Windows version,
  power mode, apps that start with Windows, and a verdict: GOOD or WEAK as a bot computer.
- **Main PC differences (found on its own, no bot folder there):** nothing running gets closed (it only lists those
  apps). Xbox and gaming apps stay. The deep part runs any time unless NinjaTrader is open.
- **Main PC:** the v2 deep tune gives it a full-speed plugged-in power plan by itself (the Surface gets the cooler one).
- **Obsidian is never closed or switched off** (the owner's vault; see the v2 section).

## v2 deep tune: every change, why, and how it is undone

`tools/bat/CLEAN_PC.bat` runs `scripts\pc_tune.ps1` in its Administrator part, only outside trading hours (weekdays 01:15-16:05 ET it
waits; on the main PC only while NinjaTrader is open). **Before each change it writes the old value** to
`C:\ProgramData\LiquidityEngine\pc_tune_state.json`; **`tools/bat/UNDO_PC_TUNE.bat`** reads that file and puts every value back,
then archives it. Running the tune twice keeps the first old values. NinjaTrader and python are never closed, NinjaTrader's
files are never changed, nothing is downloaded.

"Surface" = a hot, small PC (any Surface, or a laptop with 8 GB or less). "Main PC" = the PC_KIT copy (no bot folder).

| Change | Surface (bot PC) | Main PC | Why | Undo puts back |
|---|---|---|---|---|
| Power plan "Liquidity Engine trading" (a copy), plugged in: never sleeps / hibernates, disk never sleeps, USB suspend off, Wi-Fi power saving off | from Balanced | from Ultimate / High performance | a 24/5 bot must never nap; on battery it acts like the original plan | the old plan, the copy deleted |
| CPU top speed capped at **2,800 MHz** when plugged in | yes | no | far less heat, so less screen glitching; a hot Surface throttles below that anyway. Not "max processor state 85%": anything under 100% switches turbo off, and this CPU's base speed is only 1.1 GHz | the cap goes with the plan |
| PCI Express link power saving off | no (heat) | yes | no wake-up delay on the disk / network card | goes with the plan |
| Services off: telemetry (DiagTrack, dmwappushservice), Maps, Retail demo, Fax, Media Player sharing, Remote Registry | yes | yes | background CPU / disk / network nobody uses; Remote Registry off is also safer | each service's old start type |
| Xbox services off (XblAuthManager, XblGameSave, XboxNetApiSvc, XboxGipSvc) | yes | no (games stay) | no games on the bot PC | old start type |
| Print Spooler off | only if no printer | only if no printer | nothing to print to | old start type |
| SysMain (Superfetch) off | 6 GB or less on an SSD | kept (16 GB helps) | on 4 GB it fills scarce memory with guesses | old start type |
| Compressed memory | kept / turned on | kept / turned on | holds ~30% more in memory before using the disk | as it was |
| Page file back to "system managed" | only if set by hand under 4 GB | same | too small = NinjaTrader can run out of memory | set by hand again |
| Defender skips **only** NinjaTrader 8's `db`, `log`, `trace` and the bot's `data`, `logs` folders | yes | NinjaTrader's only | their many small writes stall behind the scanner. Trade-off: files in those folders are not scanned when written; the rest of the PC and the weekly scan are unchanged; no program is excluded | the exclusions removed |
| Network card: Energy Efficient / Green Ethernet off; Windows may not turn the card off to save power | yes | yes | no wake-up delay on the line | old values |
| Not done on purpose: Nagle / TcpAckFrequency, DNS changes | | | folklore for NinjaTrader's feed; DNS is only the first lookup | |
| Edge: startup boost off, no background running, sleeping tabs on (Surface 5 min, main 15 min); Surface: efficiency mode on | yes | yes | Edge was pre-loading at sign-in and staying in memory. Edge may say "managed by your organization": that is these settings | the settings removed (or the old value) |
| Chrome (if installed): no background running, Memory Saver on | yes | yes | same, for Chrome | removed |
| Office startup-boost task off | yes | yes | Office pre-loads at sign-in | task back on |
| Storage Sense on: weekly, temp files, recycle bin after 30 days | yes | yes | junk stays away by itself; Downloads and OneDrive files are never touched | old values / removed |
| Game Bar background recording off | yes | no | records the screen in the background | old values |
| Task **LiquidityEngine-Keeper** (every 15 min + at sign-in, no window) | NinjaTrader + the bot's python AboveNormal | NinjaTrader AboveNormal | Windows serves trading first; OneDrive, Teams, Discord, Spotify ... BelowNormal; at 85%+ memory it trims idle background apps. Never closes anything, never High / Realtime | task + its file removed |
| Task **LiquidityEngine-WeeklyCare** (Sunday 11:00, low priority) | yes | yes | Windows temp, component store clean-up, Defender quick scan; refuses weekdays 01:15-16:05 ET while trading | task + its file removed |
| **Health score** 0-100 before and after (free memory, CPU idle, start-up apps, free disk, temperature when readable) | yes | yes | one number to compare runs; also in `PC_REPORT-<name>.txt` | nothing to undo (read-only) |

**Obsidian is protected (2026-11-03):** it is the owner's notes vault and Jarvis syncs it with the Obsidian Git plugin.
CLEAN_PC never closes it, never switches it off at sign-in, the keeper never lowers it, and if an older CLEAN_PC run
had switched its sign-in entry off, every CLEAN_PC run (and `tools/bat/UNDO_PC_TUNE.bat`) switches it back on.

The NinjaTrader check also prints, read-only: untick Tools > Options > Market data > "Show Tick Replay"; once a month after
4:05 PM ET, Tools > Database Management > Repair DB (never "Reset DB"); pause OneDrive syncing while trading (don't switch
off OneDrive's Documents backup without asking Claude: NinjaTrader's folder would stay in OneDrive and a new empty one start).

## The Surface options (prices checked 2026-11-02, US)

| Option | Cost | What it fixes | Verdict |
|---|---|---|---|
| Add memory to the Surface | not possible | — | Every Surface Pro has its memory soldered to the board (iFixit gives the Pro 7 a 1/10 repair score) |
| **(a) Used business mini PC, 16 GB:** Lenovo ThinkCentre M720q Tiny, i5-9500T, 16 GB, 256 GB SSD, Windows 11 Pro | **~$225-275** ($249 refurbished Grade A with a 1-year warranty) | 4x the memory, 6 cores, a desktop fan: never heat-throttles; runs 24/5 at ~15 W | **BEST VALUE** |
| (a) Dell OptiPlex 7070 Micro, i5-9500T, 16 GB | ~$370-420 refurbished | the same as the M720q | good, costs more |
| (a) New Beelink mini PC (Mini S12 Pro N100 16 GB / SER5 Ryzen 5 5500U 16 GB) | ~$180-230 for the N100, ~$230-330 for the SER5 (memory prices went up in 2026) | new, 16 GB | the N100 is slower than the M720q; the SER5 is fine but costs more |
| (b) External monitor (24-inch 1080p, e.g. Sceptre) | ~$75-90 | you get a clean screen to look at. The Surface's own screen still glitches and the Surface is still hot and slow | only treats the symptom |
| (b) Fan cooling stand / clip-on tablet cooler | ~$40-70 | a cooler Surface: less glitching and less CPU slow-down | a stop-gap; still 4 GB |
| (c) Microsoft out-of-warranty service (Surface Pro 7) | ~$450 (Microsoft swaps it for a refurbished unit; it doesn't fix the screen alone); third-party screen ~$299 | a new screen | too expensive: you'd still have 4 GB |
| (d) Run the bot on the main PC | $0 | everything, if the PC has 8 GB+ (16 GB is best) and an SSD | depends on the PC report and on leaving it on all week |

**Recommendation: a used Lenovo ThinkCentre M720q Tiny (i5-9500T / 16 GB / 256 GB SSD / Windows 11 Pro), ~$249**,
e.g. this refurbished Grade A unit with a 1-year warranty:
https://reach.dog/shop/system-liquidation/products/lenovo-thinkcentre-m720q-tiny-desktop-intel-core-i5-9500t-3-70ghz-16gb-ram-256gb-ssd-windows-11-pro-grade-a-refurbished
(the same box is about $250-275 on eBay; search "M720q i5-9500T 16GB"). Make sure the listing includes 16 GB, the power
adapter and Wi-Fi. It costs less than one Microsoft repair and fixes both problems: memory and heat. Used business
computers came with their memory already installed, so they missed the 2026 memory price rise. You run it
headless (no screen needed) through Chrome Remote Desktop, the same way you reach the Surface now. A spare TV or monitor is only
needed for the first setup. If the main PC's report says **GOOD** and you're happy to leave it on all week, use the
main PC instead ($0) and keep this purchase for later.

Sources: iFixit Surface Pro 7 RAM answer (ifixit.com/Answers/View/762219); Surface Pro 7 teardown, 1/10 (slashgear.com,
techradar.com); M720q prices (reach.dog, ebay.com/shop/tiny-lenovo); OptiPlex 7070 Micro (bestbuy.com, pcliquidations.com);
Beelink (ebay.com, camelcamelcamel.com B0C7726ZYB, slickdeals.net); 2026 memory price rises (tomshardware.com, pcworld.com);
Surface out-of-warranty ~$450 (mspoweruser.com, onmsft.com, Microsoft's per-country price page on support.microsoft.com);
third-party screen $299 (onehourdevicerepair.com); monitors (walmart.com, productchart.com); coolers (neweggbusiness.com,
homedepot.com); heat and red-line glitches (Microsoft Q&A / Tech Community). Prices change: check the listing before buying.

## tools/bat/STATUS.bat and the safety review (2026-11-04)

- **tools/bat/STATUS.bat** (repo root, also `<site>/pc/STATUS.bat`; script `scripts/pc_status.ps1` / `pc/pc_status.ps1`): a six line health card
  for THIS PC, read-only, no Administrator: DISK (free space), RAM, BOT (running / armed / heartbeat age from the published `home.json`
  `live.pc`), NINJA (process), BARS (age of the last 1-minute bar from the same heartbeat), POWER (active plan). Ends with ONE
  `NEXT:` sentence (the first red line, else the first yellow, else "nothing to do"). The Surface (not the bot PC) shows its own disk,
  RAM and plan and where the bot runs; a stopped bot / closed NinjaTrader outside market hours is `[..]`, never red.
- **Which PC gets which script** (the first line of the PC page): main PC = STATUS, PC care, Clean storage, Fresh start once;
  Surface (retired, cooling) = Clean storage and PC care only.
- **Failures**: every script (`pc_care`, `clean_storage`, `move_bot`, `pc_status`, `FRESH_START`) ends an unexpected failure with ONE
  sentence ("Something unexpected stopped this: take a photo of this window and send it to Claude"), never a stack trace; the detail
  goes to the log. Test hook `LE_T_BOOM=1`.
- **Clean storage** also refuses any root inside a person's own folders (Downloads, Desktop, Documents, Pictures, Videos, Music,
  OneDrive / Dropbox ones, `.ssh`, `.aws`, `.gnupg`; NinjaTrader's folder and the bot folder are the exceptions) and never deletes
  keys / wallets / sign-ins by name (`*.pem *.key *.ppk *.kdbx id_rsa ...`).
- Tests: `tests.test_pc_care` (STATUS, the failure sentence), `tests.test_clean_storage` (Downloads / .ssh / Desktop decoys and
  hostile TEMP), `tests.test_win_scripts`.
