# Jarvis for the Kalshi bot: setup

**For the bot's own Claude chat ("kalshi-server", on the bot's server).** The owner pasted: "Set up Jarvis for my Kalshi
bot by following this page". Do the steps below in order. Each step is a few shell commands. Show the owner the short
results. Step 3 needs one click from him on GitHub.

**What it does:** a small script reads the bot's own files every minute and publishes the numbers to his phone app
(Jarvis): the balance, P&L for today, this week and all time, open bets, the last trades, the three strategies and the
24 h equity curve. It pushes one small JSON file to the branch `kalshi` of the public repo
`demetrades2000-coder/nq-dashboard`.

## Rules: read these first
- **Never touch trading.** Don't edit, restart, stop or reconfigure any `kalshi-*` service, cron job, settings file
  (`bot_settings.json`, `combo_settings.json`, `sniper_settings.json`, ...), `paused.txt`, `trades.db` or any other bot
  file. Don't import the bot's Python modules.
- **Never print secrets.** That means `.env`, `.env2`, `keys/`, the Discord token, the dashboard token or URL, and the
  server's IP address. The only thing you show the owner from step 3 is the deploy key's PUBLIC line (it starts with
  `ssh-ed25519`).
- **No Kalshi API calls.** The script only reads files: `trades.db` (opened read-only), `account_truth.json`,
  `autotrader_status.json`, `autotune_state.json`, the three settings files and `paused.txt`.
  It never opens `.env`, `keys/` or `sniper.db`.
- **Everything new goes in `~/kalshi_jarvis`.** Nothing in `/home/ubuntu/kalshi` changes. The script runs once a
  minute at low priority (`nice`/`ionice`), and a run takes well under a second.
- **Stop and ask the owner on anything unexpected:** a missing file, an error you don't understand, or a step that would
  need `sudo` or a change to the bot.

## 1. Get the script
```
mkdir -p ~/kalshi_jarvis && cd ~/kalshi_jarvis
curl -fsSL https://demetrades2000-coder.github.io/nq-dashboard/kalshi/kalshi_status_vm.py -o ~/kalshi_jarvis/kalshi_status_vm.py
python3 --version && git --version && head -5 kalshi_status_vm.py
```
It's one file of Python 3.9+, standard library only, and you may read it all. If `git` is missing, stop and ask the owner;
installing it needs `sudo apt-get install -y git`.

## 2. Run it once and show the JSON
```
cd ~/kalshi_jarvis && nice -n 15 python3 kalshi_status_vm.py --from-bot /home/ubuntu/kalshi --check
```
This prints exactly what will be public. Show the owner the top part: `status`, `balance`, `today_pnl`, `week_pnl`,
`total_pnl` and the `strategies`. Then check the numbers:
- `balance` should match `account_truth.json` `total`.
- `today_pnl` should match today on Discord `/money` (the bot's own P&L, by ET day).
- The week starts Monday 00:00 ET. If Discord's week is a rolling 7 days, add `--week rolling7` to steps 2, 4 and 5.

If the output says `trades.db could not be read`, or anything looks wrong, stop and tell the owner.

## 3. A deploy key: write access to nq-dashboard only
```
ssh-keygen -t ed25519 -N "" -C "kalshi-jarvis server" -f ~/kalshi_jarvis/deploy_key
cat ~/kalshi_jarvis/deploy_key.pub
```
Show the owner **only** the `.pub` line, and tell him:

> On GitHub, open **demetrades2000-coder/nq-dashboard** → **Settings** → **Deploy keys** → **Add deploy key**.
> Title: `kalshi-jarvis server`. Key: paste this line. Tick **Allow write access**, then **Add key**. Tell me "OK" when
> it's done.

Never show `deploy_key`, the private half.

## 4. Wait for his OK, then push once
```
cd ~/kalshi_jarvis && python3 kalshi_status_vm.py --from-bot /home/ubuntu/kalshi --once --git-dir ~/kalshi_jarvis/pub.git --deploy-key ~/kalshi_jarvis/deploy_key
```
Expect `"ok": true` and the address the phone reads. If you get `Permission denied (publickey)`, the key isn't added or
**Allow write access** isn't ticked: ask the owner to check. The first push adds github.com to `~/.ssh/known_hosts`.

## 5. Every minute: one cron line
```
crontab -l 2>/dev/null | grep -q kalshi_status_vm.py || ( crontab -l 2>/dev/null; echo '* * * * * cd $HOME/kalshi_jarvis && flock -n .lock nice -n 15 ionice -c3 python3 kalshi_status_vm.py --from-bot /home/ubuntu/kalshi --cron --git-dir pub.git --deploy-key deploy_key >> cron.log 2>&1' ) | crontab -
crontab -l | grep kalshi_status_vm.py
```
This keeps every existing cron line and adds one. Each minute it reads the files and pushes only when the numbers
changed, plus once every 10 minutes so the phone knows it's alive. `cron.log` gets one line per push and any errors.

## 6. Check it
```
sleep 75; tail -3 ~/kalshi_jarvis/cron.log
curl -fsSL "https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/kalshi/kalshi.json" | head -c 300; echo
```
The address can lag a few minutes behind the push. When it shows the bot's numbers, tell the owner in one line:
"Done: Jarvis shows your Kalshi bot now, updated every minute."

## Later
- **Update the script:** run step 1's `curl` line again. Cron uses the new file from the next minute.
- **Pause publishing:** `crontab -l | grep -v kalshi_status_vm.py | crontab -`. Turn it back on with step 5.
- **Remove it:** run the pause line, then `rm -rf ~/kalshi_jarvis`. Ask the owner to delete the deploy key on GitHub
  (nq-dashboard → Settings → Deploy keys).
