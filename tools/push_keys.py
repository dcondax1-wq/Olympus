"""Optional: your own VAPID key pair for the phone notifications. Not needed: the cloud monitor makes one by itself and keeps
it in the GitHub Actions cache (docs/NOTIFICATIONS.md). Use this only to pin a key in a GitHub Secret.

    python tools/push_keys.py            # new pair: prints both keys, saves them for the PC bot in data/push.json
    python tools/push_keys.py --show     # the public key and how many phones are set up (never the private key)
    python tools/push_keys.py --add-sub '<subscription JSON>'    # manual override: the PC bot also notifies that phone

The private key goes into the GitHub Secret LE_VAPID_PRIVATE
(https://github.com/demetrades2000-coder/nq-liquidity-engine/settings/secrets/actions) and data/push.json (gitignored);
never into the repo or a chat. Phones re-subscribe with the new key by themselves on their next open.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import push  # noqa: E402

PUBLIC_FILE = os.path.join(ROOT, "tools", "web_public", "push_key.json")
SECRETS_URL = "https://github.com/demetrades2000-coder/nq-liquidity-engine/settings/secrets/actions"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true", help="show the public key and the set-up devices, make nothing")
    ap.add_argument("--add-sub", metavar="CODE", help="add the app's subscription code to data/push.json (PC bot)")
    ap.add_argument("--force", action="store_true", help="replace an existing key pair (every phone must turn notifications on again)")
    ap.add_argument("--no-save", action="store_true", help="only print the pair, write no file")
    a = ap.parse_args(argv)
    cur = push.config(env={}, path=push.CONFIG_PATH)
    if a.add_sub:
        st = push.save_pc_config({"subs": a.add_sub})
        print(f"saved: the PC bot now notifies {st['devices']} device(s) (data/push.json)")
        return 0
    if a.show:
        print(json.dumps(push.status(push.config()), indent=1))
        return 0
    if cur["private"] and not a.force and not a.no_save:
        print("data/push.json already has a key pair. Public key (not secret):\n  " + cur["public"])
        print("Use --force to make a new pair (every phone then has to turn notifications on again).")
        return 0
    priv, pub = push.generate_keys()
    if not a.no_save:
        push.save_pc_config({"vapid_private": priv})
        with open(PUBLIC_FILE, "w", encoding="utf-8") as fh:
            json.dump({"vapid_public": pub, "note": "Web Push public key (not secret). The private key is the GitHub Secret LE_VAPID_PRIVATE."}, fh, indent=1)
            fh.write("\n")
    print("Phone notification keys\n")
    print("1. PRIVATE key (secret). Copy it into a GitHub Secret named LE_VAPID_PRIVATE:")
    print(f"   {SECRETS_URL}  ->  New repository secret")
    print(f"\n   {priv}\n")
    print("   Do not paste it into a chat or a file in the repo.")
    print("\n2. PUBLIC key (not secret):", pub)
    if not a.no_save:
        print(f"   saved in {os.path.relpath(PUBLIC_FILE, ROOT)} (commit this file) and, with the private key, in data/push.json (gitignored)")
    print("\n3. Nothing else: phones subscribe with the new key by themselves the next time the app opens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
