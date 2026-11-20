"""AI CALLER (day-caller, 2026-11-20): the consent-first AI phone assistant for the Website Factory.

Separate from trading: its own package, its own process and port (127.0.0.1:8790); it never imports engine/ or server.py and never
touches NinjaTrader, the live strategy files or the phone site's service worker. OFF until the owner types START CALLING (CALLER_ON.bat).

Why consent-first: Maryland's Stop the Spam Calls Act (Md. Code, Com. Law 14-4502(a)(3), in force 2024-01-01) bans sales calls that use an
automated dialing system or a recorded message without the called party's SIGNED prior express written consent, and its only
business-to-business exemption needs 3+ years of operation under the same name. So the caller (1) answers inbound calls from businesses
that call the agency back, and (2) dials out ONLY to businesses that signed the consent form. research/writeups/ai-caller-2026-11-20.md

  python -m tools.caller.simulate              run every scripted business owner offline, write transcripts + scores
  python -m tools.caller.cost                  the monthly cost table
  python -m tools.caller.run --dry             what the dialer WOULD do today (gate decisions only, no call)
  python -m tools.caller.server                the webhook + ConversationRelay socket on 127.0.0.1:8790 (CALLER_ON.bat starts it)
  python -X utf8 -m tests.test_caller          the checks
"""
