# Lead wires (day-taxes)

Nothing in sw.js / apps.js / build_web_dashboard.py / olympus.js is required: taxes.html is an existing page and taxes.js moved
to ?v=2 inside taxes.html itself.

Optional:
1. If the business/ service worker or site build caches taxes.js by name, bump it so phones get v2 (grep "taxes.js" in the business
   worker / build; I did not touch either).
2. STATE.md line (under Money ideas): "- Keep the most (day-taxes 2026-11-20, research/writeups/keep-the-most-2026-11-20.md,
   tools/money/keep_most.py): pot 30% until state/job known (15-40% table); waterfall 30 tax / 10 eval reserve to $320 / 10 retirement /
   20 live fund to $5,000 / rest yours; live futures account at $5,000 from payouts + 4 payouts, 1 MNQ per bot, stop $2,500;
   S-corp break-even ~$51k; page business/taxes.html. Owner to-do: tell Claude state + day job."
3. Owner to-do list (STATE 'Waiting on the owner'): "Tell Claude your state and whether you have a day job (tax pot %)".
