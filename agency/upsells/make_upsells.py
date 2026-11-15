"""Both monthly add-ons for one client in one go: the Front-desk chat and the Review booster.

    python agency/upsells/make_upsells.py data/agency/clients/joes-barbers.json --site <the client's site folder>
    python agency/upsells/make_upsells.py data/agency/clients/joes-barbers.json          (no --site: files only, to paste by hand)

Runs make_chat.py and make_review.py, then prints what to deploy, what to print and what to check with the client.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from agency.upsells import common as K  # noqa: E402
from agency.upsells import make_chat, make_review  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the Front-desk chat and the Review booster for one client.")
    ap.add_argument("client", help="the client file (JSON)")
    ap.add_argument("--site", help="the client's site folder: the chat goes on every page, the review page into /review/")
    ap.add_argument("--out", help="where the kit goes (default data/agency/upsells/<id>/)")
    ap.add_argument("--only", choices=("chat", "review"), help="build just one of the two")
    a = ap.parse_args(argv)
    try:
        chat = review = None
        if a.only != "review":
            chat = make_chat.build(a.client, a.out, a.site, quiet=True)
        if a.only != "chat":
            review = make_review.build(a.client, a.out, a.site, quiet=True)
    except K.ClientError as e:
        print("can't build:", e, file=sys.stderr)
        return 2
    out = (chat or review)["out"]
    print("DONE")
    if chat:
        print(f"  chat:    {os.path.basename(chat['file'])}, {chat['bytes']:,} bytes ({chat['gzip']:,} sent), {chat['intents']} answers"
              + (" - installed in the site" if a.site else f" - paste the 2 lines in {os.path.join(out, os.path.basename(chat['file'])[:-3] + '-install.txt')}"))
    if review:
        print(f"  reviews: QR -> {review['page_url']} - " + ("review page installed as /review/" if a.site else f"upload {os.path.join(out, 'review')} as /review/"))
        print(f"  print:   {os.path.join(out, 'print', 'card-a6.html')} (or cards-letter-10.html), Print at 100%")
    print("  deploy:  " + (f"{a.site} on Netlify" if a.site else "the site with those files") + ", then send one test message from the chat and the review page")
    for w in (chat or {}).get("warnings", []) + (review or {}).get("warnings", []):
        print("  CHECK WITH THE CLIENT:", w)
    if chat:
        print(f"  every answer, to read through with the client: {os.path.join(out, os.path.basename(chat['file'])[:-3] + '-preview.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
