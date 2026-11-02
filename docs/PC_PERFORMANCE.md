# Both computers fast (2026-11-02)

**The short answer:** the Surface's 4 GB memory is soldered to the board and can't be upgraded. Cleaning helps, but
NinjaTrader plus the bot will always fill 4 GB. The best fix for the money is a **used Lenovo ThinkCentre M720q Tiny
(i5-9500T, 16 GB, SSD), about $250** as the bot's own computer (details below). Until then, `CLEAN_PC.bat` keeps
the Surface as light as it can be.

## Surface (the bot PC): 3 steps
1. After 4:05 PM ET, double-click **`CLEAN_PC.bat`** in the bot folder. Click **Yes** once when Windows asks.
2. Do what its **NinjaTrader check** lines say (yellow lines). The bot's MNQ chart with LE_BarFeed stays at **30 days**.
   Set charts you only look at to **3-5 days**, turn Tick Replay off, and close workspaces you don't use.
3. Keep it plugged in and standing up on its kickstand (air needs to reach the back). The heat glitch is a hardware
   problem: if it gets worse, move the bot to the box below.

## Main PC: 3 steps
1. After step 1 on the Surface, a **`PC_KIT`** folder appears in your OneDrive (or on the Surface's Desktop if it has
   no OneDrive: copy it to a USB stick). Open it on the main PC.
2. Double-click **`CLEAN_PC.bat`** in it. Click **Yes** once.
3. Send Claude the **`PC_REPORT-<name>.txt`** it writes next to CLEAN_PC.bat (a photo is fine). It shows what the main PC
   is and whether it can run the bot.

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
- **Main PC tip:** Settings > System > Power > Power mode: **Best performance** (when plugged in). Don't do this on
  the Surface: more heat makes the glitch worse.

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
