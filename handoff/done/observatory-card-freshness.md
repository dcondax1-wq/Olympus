# Observatory status card

Fixed the static Observatory `jarvis.json` card's `stale_after` value to the 14-day maximum accepted by Jarvis (`1,209,600` seconds). The old 315,360,000-second value fails `validateStatus`, leaving no status card.

Checked the card against the explicit 60 to 1,209,600-second contract in `jarvis/apps.js` and parsed the updated JSON. This changes no trading code or feed.
