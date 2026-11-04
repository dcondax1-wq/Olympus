# Running the bot with the PC off: the honest answer (2026-11-03)

**Short answer:** there is no truly free machine that can run NinjaTrader. Today, run the bot in **LITE mode** on the
Surface (`BOT_LITE.bat`, free, the bot drops from ~690 MB to ~180 MB). For the PC-off goal, the **~$249 used mini PC
(16 GB)** is the real fix. **Azure for Students** works as a bridge for about **2-3 months** if you qualify and MFFU
says yes to a VPS.

| Option | Cost | Can it run NinjaTrader + the bot? | Verdict |
|---|---|---|---|
| **LITE mode on the Surface** (`BOT_LITE.bat`) | $0 | yes, with ~500 MB more free memory | **do it now** |
| **Used mini PC** (Lenovo M720q, i5, 16 GB, SSD) | ~$249 once + ~$2/month power | yes, easily (4x the Surface's memory) | **the real fix** |
| Azure for Students, Windows VM B2s (4 GB) | $0 out of pocket; the $100 credit lasts ~3.4 months (on 15 h a weekday) | yes, tight (same 4 GB as the Surface: LITE needed) | bridge only |
| Azure for Students, Windows VM B2ms (8 GB) | $100 credit lasts ~2.3 months (15 h a weekday) | yes, comfortable | bridge only |
| Azure / AWS / Google "always free" VMs | $0 | **no**: 1 GB of memory, Windows alone needs more | fails |
| Oracle Cloud Always Free (Arm, 24 GB) | $0 | **no**: Linux on Arm chips; NinjaTrader is a Windows (Intel/AMD) program | fails |
| GitHub Actions cloud monitor (already running) | $0 | no NinjaTrader; paper only, and since "no Yahoo" it only waits when the PC is off | keeps the phone updated, no trades |

## 1. Azure for Students (what the offer is, 2026)

- **$100 of credit to use within 12 months, no credit card.** Renew once a year while you are still a student (another
  $100; unused credit does not carry over). When the credit or the 12 months runs out, the subscription is switched
  off; it only bills a card if you upgrade to pay-as-you-go yourself.
- **Who can get it:** full-time students at an accredited college or university, verified with the school email (or
  school sign-in). If you are not a student right now, this option is not for you; don't sign up with someone else's
  email.
- **Free VM hours included:** 750 hours a month of B1s, B2pts v2 and B2ats v2. **They all have 1 GB of memory.** That is
  too little for Windows + NinjaTrader, so the bot would run on a paid size that uses up the credit.

**What a bot VM costs** (official Azure price list, East US, Windows, checked 2026-11-03):

| Part | Price |
|---|---|
| VM B2s: 2 cores, **4 GB** | $0.0496 an hour |
| VM B2ms: 2 cores, **8 GB** | $0.0912 an hour |
| Disk: 128 GB Standard SSD (the Windows image needs 127 GB) | $9.60 a month, also while the VM is off |
| Public IP address (to reach it by Remote Desktop) | ~$3.65 a month |

How long the $100 lasts:

| Running time | Hours a month | B2s (4 GB) a month | B2s lasts | B2ms (8 GB) a month | B2ms lasts |
|---|---|---|---|---|---|
| **Weekdays 01:30-16:30 ET** (covers LIT: entries 02:00-15:30, flat 15:55) | ~326 | ~$29 | **~3.4 months** | ~$43 | **~2.3 months** |
| 24/5 (Sunday 18:00 to Friday 17:00 ET) | ~512 | ~$39 | ~2.6 months | ~$60 | ~1.7 months |
| 24/7 | ~730 | ~$49 | ~2 months | ~$80 | ~1.2 months |

The money only lasts if the VM is **stopped (deallocated)** outside those hours. Azure's built-in **auto-shutdown**
(VM > Operations > Auto-shutdown) is free and does the 16:30 stop. **Starting it again is not built in:** either tap
Start in the Azure phone app each morning before 01:30 ET, or add Azure's "Start/Stop VMs" add-on (a few cents a
month). NinjaTrader then needs Windows to log in by itself, NinjaTrader's password saved and "Connect on startup".

**Catch:** B2s has the same 4 GB as the Surface. It is still better (no screen, no heat, no Windows apps), and LITE
mode makes it fit, but B2ms (8 GB) is the comfortable size and burns the credit in ~2.3 months.

## 2. Truly free options and why they fail

- **Azure / AWS / Google free VMs:** all are 1 GB machines (Azure B1s / B2ats v2, AWS t2/t3.micro, Google e2-micro;
  Google's free one is Linux only, Windows costs extra). Windows plus NinjaTrader needs about 3 GB or more.
- **Oracle Cloud Always Free:** the big free machine (4 Arm cores, 24 GB) is Linux on Arm chips. NinjaTrader 8 is a
  Windows desktop program for Intel/AMD chips: it does not run there. Oracle's free Intel/AMD machines have 1 GB.
- **GitHub Actions (already set up, free):** runs the paper cloud monitor every 15 minutes, but it cannot run
  NinjaTrader, and since "no Yahoo" it has no bars of its own when the PC is off, so it only waits.

## 3. The mini PC (~$249): the real fix

Used Lenovo ThinkCentre M720q Tiny (i5-9500T, **16 GB**, 256 GB SSD, Windows 11 Pro), about $249 refurbished with a
1-year warranty (details and links: `docs/PC_PERFORMANCE.md`). It runs 24/5 at ~15 W (about $2 a month of
electricity), has 4x the Surface's memory, never overheats, and you reach it from the phone by Chrome Remote Desktop
like the Surface now. **It costs about what 4-6 months of an Azure 8 GB VM would.** Moving the bot to it:
`MOVE_BOT.bat` (`docs/MOVE_TO_MAIN_PC.md`).

## 4. Check MFFU's rule before any VPS

Ask MFFU support **in writing** before you run the eval from a cloud VM: *"May I run NinjaTrader on my own cloud VM
(Microsoft Azure) for my Builder 50K eval?"* Reasons:

- Online sources disagree on MyFundedFutures' rules for automation and VPS use (some say allowed since mid-2025, some
  say not), and some prop firms flag trades from data-center IP addresses or a sudden IP change.
- MFFU requires you to be present for live trading: a VM changes where the bot runs, not that rule. The bot stays
  paper / Sim by default and only you arm the eval (`docs/GO_LIVE_TONIGHT.md`).

## Sources

- Azure VM and disk prices: Azure Retail Prices API (official, `prices.azure.com/api/retail/prices`, Standard_B2s /
  Standard_B2ms, eastus, Windows meters; Standard SSD E10 LRS), queried 2026-11-03.
- Azure for Students offer ($100, 12 months, no card, 750 h of B1s / B2pts v2 / B2ats v2):
  https://azure.microsoft.com/en-us/free/students ; renewal / expiry: Microsoft Q&A
  https://learn.microsoft.com/en-us/answers/questions/5807382/clarification-regarding-on-azure-for-students-rene ,
  https://learn.microsoft.com/en-us/answers/questions/5924367/azure-student-account-credit-expired ,
  https://learn.microsoft.com/en-us/answers/questions/5831889/need-to-extend-student-credits ;
  free B-series hours: https://learn.microsoft.com/en-us/answers/questions/1032030/how-to-create-b-series-vm-with-750-free-hours-for
- Third-party B2s price check: https://www.azurespeed.com/AzureVmPricing/Standard_B2s ,
  https://costcalc.cloudoptimo.com/azure-pricing-calculator/vm/Standard-B2s
- MFFU automation / VPS (conflicting, unofficial): https://algopropfirms.pages.dev/blog/myfundedfutures-automation-rules ,
  https://roboquant.dev/blog/my-funded-futures-automation-guide , https://tradingfinder.com/props/my-funded-futures/rules ,
  https://blog.pickmytrade.io/prop-firm-ip-address-rule-why-a-vps-can-get-you-banned.md
- Mini PC prices and the Surface's soldered memory: `docs/PC_PERFORMANCE.md` (checked 2026-11-02).

Microsoft's own pages could not be opened from this session (network block); the offer terms above come from search
results of those pages. Check the offer page once before you sign up: terms change.
