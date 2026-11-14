"""One-command backup of the whole project: a zip of every tracked file (+ optional full-history git bundle) and a SHA-256 list.

    python tools/make_backup.py --out "C:/Users/you/iCloudDrive/OLYMPUS_BACKUPS"          # code zip
    python tools/make_backup.py --out <folder> --bundle                                  # also the full git history bundle
    python tools/make_backup.py --out <folder> --dry-run                                 # only say what it would do
Run it weekly (Windows Task Scheduler). Stdlib only; needs git on the PATH. Never includes untracked/ignored files (keys, .env, alerts).
Keep the output on a device or drive that is NOT the machine itself and NOT the same company as the code host. See docs/DISASTER_RECOVERY.md.
REFUSES (exit 1, nothing written, also with --dry-run) when the ref's committed tools/model_versions.json is stale (it misses an older
version of a live_model*.json): a PC with that version would keep it as if the owner had made it (tools/update_from_zip.py). Fix:
python tools/model_versions.py, commit it, run this again. --no-model-check skips it (tools/second_backup.py: the PC's own weekly
zip of the files it runs, whose list is the one its last code zip brought).
"""
import argparse, datetime, hashlib, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_list_problem(ref):
    """None when a zip of `ref` carries a current tools/model_versions.json, else the words why not (tools/model_versions.py)."""
    try:
        from tools import model_versions as mv
    except ImportError:                                  # run as python tools/make_backup.py: tools/ is on the path, the repo is not
        import model_versions as mv
    try:
        miss = mv.missing(ROOT, ref)
    except mv.GitError as e:
        return f"tools/model_versions.json could not be checked at {ref} ({e}). Nothing was written."
    if not miss:
        return None
    files = ", ".join(sorted({n for n, _s in miss}))
    return (f"tools/model_versions.json at {ref} misses {len(miss)} older version{'s' if len(miss) != 1 else ''} of {files}: a PC with one of "
            f"them would keep it as if the owner had made it. Run python tools/model_versions.py, commit it, then run this again. Nothing was written.")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("git failed: " + " ".join(args) + "\n" + (r.stderr or r.stdout)[-400:])
    return r.stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="folder to write the backup into (iCloud / Drive / USB)")
    ap.add_argument("--ref", default="HEAD", help="what to archive (default HEAD)")
    ap.add_argument("--bundle", action="store_true", help="also write a full-history git bundle (can be 400+ MB)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-model-check", action="store_true", help="skip the tools/model_versions.json check (the PC's own weekly zip)")
    a = ap.parse_args(argv)
    stamp = datetime.date.today().isoformat()
    commit = run(["git", "rev-parse", "--short", a.ref])
    zip_path = os.path.join(a.out, f"OLYMPUS_BACKUP_{stamp}_{commit}.zip")
    plan = [f"zip of every tracked file at {a.ref} ({commit}) -> {zip_path}"]
    if a.bundle:
        plan.append(f"full-history bundle -> {os.path.join(a.out, f'OLYMPUS_HISTORY_{stamp}_{commit}.bundle')}")
    print("backup plan:\n  " + "\n  ".join(plan))
    if not a.no_model_check:
        why = model_list_problem(a.ref)
        if why:
            print("[STOP] " + why)
            return 1
    if a.dry_run:
        return 0
    os.makedirs(a.out, exist_ok=True)
    run(["git", "archive", "--format=zip", "-9", "-o", zip_path, a.ref])
    written = [zip_path]
    if a.bundle:
        b = os.path.join(a.out, f"OLYMPUS_HISTORY_{stamp}_{commit}.bundle")
        run(["git", "bundle", "create", b, "--all"])
        written.append(b)
    lines = []
    for p in written:
        lines.append(f"{sha256(p)}  {os.path.basename(p)}  {os.path.getsize(p) / 1048576:.1f} MB")
    with open(os.path.join(a.out, f"OLYMPUS_BACKUP_{stamp}_{commit}.sha256.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("done. Keep a copy on a second device or company (rule: 3 copies, 2 companies, 1 on your own device).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
