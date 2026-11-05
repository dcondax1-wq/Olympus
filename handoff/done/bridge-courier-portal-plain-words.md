# Bridge: courier portal and plain-word liquidity

- Added a premium courier portal: two cities, a glowing arch, moving checked packet and three safety seals. It is CSS/DOM only and becomes still when reduced motion is enabled.
- Added one direct first-screen instruction: connect once, pick a ready job, and let ChatGPT carry the checked result back through GitHub for Claude.
- Explained the only `liquidity` mention in plain words beside the portal. The original Pantheon-lore job payload remains unchanged.
- Improved mobile targets: category chips and every details summary are at least 44 px; the portal stacks cleanly on narrow phones.
- Preserved all 11 job payloads, GitHub/ChatGPT links, status/jobs/deliveries reads, local storage keys, link word, delivery rules and connector behavior.
- Checks: focused contract/syntax tests 3/3, existing Bridge static suite 30/30, app guard OK, Jarvis shell 3/3, apps list in step, money wording clean, numbers audit 0 wrong (6 unrelated existing warnings).
- Browser QA: effective 360 px and 390 px content viewports both had zero horizontal overflow and 0/71 visible controls below 44 px or outside the viewport. The only console errors were the known Chrome-extension metadata error, not Bridge code. No physical iPhone was available.
