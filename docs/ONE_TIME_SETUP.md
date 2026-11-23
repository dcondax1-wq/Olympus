# One-time setup on the Surface (the last visit)

After this the Surface stays awake, restarts by itself, updates itself, and your phone shouts
**"Surface offline since HH:MM ET"** if it ever goes quiet in trading hours.

## 1. Open PowerShell and paste ONE line

Start menu, type `powershell`, Enter. Paste this line, Enter (it finds the bot folder, gets the new version, starts the setup):

```powershell
$d = (Get-ScheduledTask LiquidityEngine -EA 0).Actions.WorkingDirectory; if (-not $d) { $d = (Get-ChildItem $HOME -Filter server.py -Recurse -Depth 4 -EA 0 | ? { Test-Path "$($_.DirectoryName)\engine\ninjatrader.py" } | select -First 1).DirectoryName }; cd $d; git checkout main; git pull --ff-only origin main; .\ONE_TIME_SETUP.bat
```

Already in the bot folder? The short one: `git checkout main; git pull --ff-only origin main; .\ONE_TIME_SETUP.bat`

Next time, just double-click `tools/bat/ONE_TIME_SETUP.bat` in the bot folder.

## 2. What it does (green [OK] / red [FIX] lines)

| Step | What |
|---|---|
| a | stops the bot, `git pull` (main), `pip install` |
| b | power: never sleep or hibernate on AC, lid close = nothing, USB suspend off |
| c | Windows Update: paused 5 weeks, active hours 00:00-18:00 ET, no restart while signed in |
| d | at logon: the bot, the 5-minute helper, NinjaTrader |
| e | the 4 desktop icons |
| f | the bot updates itself |
| g | starts the bot: asks your **eval account name** and your **confirm phrase** |
| h | health check |
| i | prints what is left for your hands |

- Windows asks **"Allow this app to make changes?"** once: click **Yes** (needed for b, c and the logon tasks).
- The phrase is **hidden** while you type, kept in memory only, never saved by the setup.
  Just Enter = the bot runs on **Sim101** (practice) instead.
- The eval also needs your live switch in `.env.local.ps1` (`docs/GO_LIVE_TONIGHT.md` step 10). The setup checks it and
  waits while you add it; it never writes it for you.

## 3. Still by hand (once, free, ~10 min)

1. **NinjaTrader connects by itself** (3 clicks): Control Center > Connections > Configure > your MFFU connection >
   tick **Connect on startup** > OK. Check Tools > Options > Automated trading interface > **AT Interface** is ticked.
   Save the workspace with the MNQ chart that has LE_BarFeed.
2. **Automatic sign-in** after a restart: Microsoft's free **Autologon**
   (learn.microsoft.com/sysinternals/downloads/autologon): download, unzip, run `Autologon64.exe`, your Windows password,
   **Enable**.
3. **Reach the Surface from the phone**: Chrome Remote Desktop (free). On the Surface, in Chrome:
   remotedesktop.google.com/access > sign in > **Set up remote access** > install > name it > PIN (6+ digits).
   On the phone: install **Chrome Remote Desktop**, same Google account, tap the Surface, PIN.
4. Plugged in, Wi-Fi on, lock it with Win+L, leave it.

## 4. Afterwards, on the phone

- Home shows **Surface last check-in HH:MM ET**. Red **OFFLINE since ...** = it stopped reporting for 30+ min in
  trading hours (weekdays 01:30-16:00 ET).
- One push per outage ("Surface offline since HH:MM ET — the bot can't trade ...") and one when it is back.
- Fix: Chrome Remote Desktop to the Surface (or walk to it), wake it, check NinjaTrader is connected.
