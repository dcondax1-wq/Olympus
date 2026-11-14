# OLYMPUS backup (private)

Private backup of the bot and the dashboard. **Keep this repo private.**

- The code the PC runs is on the branch **`pc`**. The PC checks it once a day (and hourly outside trading time) and
  updates itself only when no trade is open and never during trading hours.
- This `main` branch only holds this note, so none of the code's scheduled jobs run here.
