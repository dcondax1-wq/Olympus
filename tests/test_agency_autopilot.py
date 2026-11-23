"""The Website Factory's EMAIL AUTOPILOT (agency/autopilot/, day-a11y 2026-11-20): fake Gmail (SMTP + IMAP), a temp OLYMPUS_HOME, a local
bare git repo for the private 'agency-inbox' branch. Never the real network.

    python -X utf8 -m tests.test_agency_autopilot
a. the phrase gate: OFF until setup; the phrase SEND EMAILS = live, anything else = dry; missing details = OFF; stop = OFF
b. the limits: Mon-Fri 9-16 ET only, 20 new a day (warm-up) across runs, 5 a run, follow-ups on day 3 and 7 only, a reply stops the sequence
c. the words: the CAN-SPAM footer (sender, postal address, a way to say no) in every message, no [placeholder], the call-me line only with a
   built site, compliant() refuses a message without the address
d. dry run: only the test address receives, no lead is marked contacted, 3 samples a day
e. replies: opt-out and bounce = never again; trimmed words (no quoted thread, no signature, phones and emails masked); an unrelated email is not
   stored; one phone push for an interested reply
f. Claude's drafts: an allowed kind with our links goes out; a foreign link or an unknown kind waits (one push); approved goes; a 'no' lead never
g. no secret: the app password is in agency_mail.json only (not the log, the state, the branch, the printed output, the repo)
h. the private branch: inbox/ + status.json pushed to 'agency-inbox' of a bare repo, a draft committed by another clone is read back
i. the Windows side: tools/bat/EMAIL_SETUP.bat / tools/bat/EMAIL_STOP.bat (CRLF, the setup -> test -> task chain, stop removes the task), the 30-minute task script
"""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS: list = []
N = [0]
PW = "abcd efgh ijkl mnop"


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port):
        self.host = host

    def login(self, user, pw):
        self.user = user

    def send_message(self, m):
        FakeSMTP.sent.append({"to": m["To"], "subject": m["Subject"], "body": m.get_content(), "lu": m["List-Unsubscribe"], "from": m["From"]})

    def quit(self):
        pass


class FakeIMAP:
    box: list = []                 # [(uid, raw bytes)]

    def __init__(self, host):
        pass

    def login(self, u, p):
        pass

    def select(self, name, readonly=False):
        return "OK", [b"1"]

    def uid(self, cmd, *a):
        if cmd == "search":
            lo = int(a[1].split()[1].split(":")[0])
            return "OK", [" ".join(str(u) for u, _ in FakeIMAP.box if u >= lo).encode()]
        u = int(a[0])
        raw = next(r for x, r in FakeIMAP.box if x == u)
        return "OK", [(b"1 (RFC822)", raw), b")"]

    def logout(self):
        pass


def raw_mail(frm, subject, text, in_reply_to=""):
    m = email.message.EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, "me@example.com", subject
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
    m.set_content(text)
    return m.as_bytes()


def T(y, mo, d, h, mi=0):
    """an ET wall time as UTC (November: ET = UTC-5)"""
    return dt.datetime(y, mo, d, h + 5, mi, tzinfo=dt.timezone.utc)


def main():
    tmp = tempfile.mkdtemp(prefix="autopilot-")
    os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "home")
    from agency.autopilot import bridge, core, run
    from agency import public as PUB
    PUB.CFG = os.path.join(tmp, "site_factory_agency.json")      # the public settings file (tools/site_factory_agency.json) for this test
    json.dump({"public_base": "https://example.org/site"}, open(PUB.CFG, "w"))
    words = json.load(open(os.path.join(ROOT, "tools", "web_public", "agency", "outreach", "scripts.json"), encoding="utf-8"))
    offers = json.load(open(os.path.join(ROOT, "tools", "web_public", "agency", "offers", "offers.json"), encoding="utf-8"))
    leads = [{"id": f"L{i:02d}", "name": f"Shop {i}", "email": f"owner{i}@shop{i}.example", "heat": "hot" if i < 3 else "cold", "score": 10 - i % 10,
              "niche": "food", "category": "restaurant", "town": "Frederick"} for i in range(40)]
    leads.append({"id": "Lnoemail", "name": "No Mail Cafe", "heat": "hot", "score": 99})
    leads.append({"id": "Ldup", "name": "Shop 0 again", "email": "OWNER0@shop0.example", "heat": "hot", "score": 99})
    try:
        # ---------------------------------------------------------------- a. the phrase gate
        ans = iter(["me@gmail.example", "Sam Test", "Peak Web", "555-0100", "PO Box 12, Frederick MD 21701", "test@me.example", "", "", "send emails"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run.setup(ask=lambda p: next(ans), secret=lambda p: PW, out=print)
        cfg = run.load_cfg()
        check("a. setup without the exact phrase: DRY RUN (lower-case 'send emails' is not the phrase)", rc == 0 and cfg["mode"] == "dry", cfg.get("mode"))
        ans = iter(["", "", "", "", "", "", "", "", "SEND EMAILS"])
        with redirect_stdout(buf):
            run.setup(ask=lambda p: next(ans), secret=lambda p: "", out=print)
        cfg = run.load_cfg()
        check("a. the phrase SEND EMAILS = live; Enter keeps every saved answer (the password too)", cfg["mode"] == "live" and cfg["app_password"] == PW.replace(" ", "") and cfg["from_name"] == "Sam Test")
        with redirect_stdout(buf):
            run.stop(out=print)
        check("a. stop = OFF", run.load_cfg()["mode"] == "off")
        res = run.run_once(run.load_cfg(), core.empty_state(), leads, words, offers, {}, now=T(2026, 11, 23, 10), smtp_factory=FakeSMTP, imap_factory=FakeIMAP)
        check("a. OFF sends nothing and reads nothing", not res["sent"] and not res["inbox"] and not FakeSMTP.sent)
        ans = iter(["me@gmail.example", "Sam Test", "Peak Web", "555-0100", "", "test@me.example", "", ""])
        bad = core.norm_cfg(dict(cfg, postal_address=""))
        check("a. a missing postal address keeps it OFF (cfg_problems names it)", any("postal" in p for p in core.cfg_problems(bad)))
        printed = buf.getvalue()
        check("g. setup never prints the password", PW not in printed and PW.replace(" ", "") not in printed)

        live = dict(cfg, mode="live", site_base="https://example.org/site")
        # ---------------------------------------------------------------- b. the limits
        st = core.empty_state()
        check("b. Saturday and Sunday: nothing", core.plan(leads, st, T(2026, 11, 21, 10)) == [] and core.plan(leads, st, T(2026, 11, 22, 11)) == [])
        check("b. before 9:00 and from 16:00 ET: nothing", core.plan(leads, st, T(2026, 11, 23, 8, 59)) == [] and core.plan(leads, st, T(2026, 11, 23, 16, 0)) == [])
        FakeSMTP.sent = []
        day = []
        for k in range(14):                                   # every 30 minutes, 9:00-15:30
            r = run.run_once(live, st, leads, words, offers, {}, now=T(2026, 11, 23, 9 + k // 2, 30 * (k % 2)), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, sleep=lambda s: None,
                             public=None, notify=None)
            day.append(len(r["sent"]))
        check("b. at most 5 a run, 20 new businesses on day 1 in all", max(day) <= 5 and sum(day) == 20 and len(FakeSMTP.sent) == 20, day)
        tos = [m["to"] for m in FakeSMTP.sent]
        check("b. hot leads first, one address written once (two leads with one address: only one of them), never a lead without email", "owner0@shop0.example" in tos[:3]
              and len(set(tos)) == len(tos) and ("Ldup" in st["sent"]) != ("L00" in st["sent"]) and "Lnoemail" not in st["sent"], tos[:5])
        st["replied"]["L01"] = "question"
        FakeSMTP.sent = []
        for d_, label in ((24, "day 1"), (25, "day 2")):
            run.run_once(live, st, leads[:0] + leads, words, offers, {}, now=T(2026, 11, d_, 10), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, sleep=lambda s: None, public=None, notify=None)
        nb = [m for m in FakeSMTP.sent if m["subject"].startswith("Re: A free website draft")]
        check("b. no follow-up before day 3", not nb, [m["subject"] for m in FakeSMTP.sent][:3])
        FakeSMTP.sent = []
        for k in range(14):
            run.run_once(live, st, leads, words, offers, {}, now=T(2026, 11, 26, 9 + k // 2, 30 * (k % 2)), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, sleep=lambda s: None, public=None, notify=None)
        bumps = [m for m in FakeSMTP.sent if m["subject"].startswith("Re: A free website draft")]
        check("b. day 3: the short follow-up to each of the 20 except the one that replied", len(bumps) == 19 and "owner1@shop1.example" not in [m["to"] for m in bumps], len(bumps))
        c26 = st["days"]["2026-11-26"]
        check("b. new emails on top stay within 20 a day and the day's ceiling", c26["new"] <= 20 and c26["new"] + c26["followup"] <= core.MAX_DAY, c26)

        # ---------------------------------------------------------------- c. the words
        m = core.message(words, leads[5], "first", live, offers, {})
        check("c. the first email: honest subject with the business, the demo link, the price line, sender + postal address + 'no thanks'",
              m["subject"] == "A free website draft for Shop 5" and "https://example.org/site/agency/demos/restaurant/" in m["body"] and "$1,500" in m["body"]
              and "Sam Test" in m["body"] and "PO Box 12, Frederick MD 21701" in m["body"] and "no thanks" in m["body"] and not core.compliant(m["body"], live, m["subject"]))
        check("c. no unfilled [placeholder] in a live email", "[" not in m["body"].replace("[phone]", ""), m["body"][:200])
        CL = "Questions? Call (301) 555-0142: our AI assistant answers."
        m2 = core.message(words, leads[5], "first", dict(live, agency_number="(301) 555-0142"), offers, {"L05": "f/abcdefgh/"})
        check("c. the inbound-only line 'Call <agency number>: our AI assistant answers' (no 'or text', no 'any time', no call-me button); none until the number is set",
              CL in m2["body"] and "https://example.org/site/f/abcdefgh/" in m2["body"] and "Questions? Call" not in m["body"]
              and not any(w in (m["body"] + m2["body"]).lower() for w in ("have our assistant call me", "or text", "any time")), m2["body"][:400])
        json.dump({"public_base": "https://example.org/site", "agency_number": "(301) 555-0142"}, open(PUB.CFG, "w"))
        check("c. the agency number can come from the public settings file too", CL in core.message(words, leads[5], "first", live, offers, {})["body"])
        json.dump({"public_base": "https://example.org/site"}, open(PUB.CFG, "w"))
        # privacy (lead 2026-11-21): no default public address, never the owner's handle / personal dashboards
        nob = dict(live, site_base="")
        json.dump({}, open(PUB.CFG, "w"))
        try:
            core.message(words, leads[5], "first", nob, offers, {})
            raised = False
        except ValueError:
            raised = True
        check("c. no public_base = nothing is sent (no default; setup names it)", raised and any("public web address" in p for p in core.cfg_problems(nob)))
        bad = [PUB.public_base(u) for u in ("https://dcondax1-wq.github.io/jarvis", "https://x.github.io/jarvis", "https://box.tail1234.ts.net", "http://plain.example")]
        check("c. public_base refuses the owner's handle, github.io/jarvis, ts.net and plain http", bad == ["", "", "", ""] and PUB.public_base("https://sites.example.com/") == "https://sites.example.com", bad)
        check("c. compliant() refuses any message showing dcondax / github.io/jarvis / ts.net",
              all(any("private address" in p for p in core.compliant(m["body"] + " " + u, live, m["subject"])) for u in ("dcondax1-wq", "see x.github.io/jarvis/agency", "pc.ts.net")))
        json.dump({"public_base": "https://example.org/site"}, open(PUB.CFG, "w"))
        check("c. compliant() refuses a message without the postal address or the way to say no",
              "no postal address" in core.compliant("Hi from Sam Test. Reply no thanks.", live) and "no way to say no" in core.compliant("Sam Test, PO Box 12, Frederick MD 21701", live))
        check("c. every sent message carries List-Unsubscribe", all(x["lu"] and "unsubscribe" in x["lu"] for x in FakeSMTP.sent))

        # ---------------------------------------------------------------- d. dry run
        FakeSMTP.sent = []
        dry = dict(live, mode="dry")
        sd = core.empty_state()
        for k in range(6):
            run.run_once(dry, sd, leads, words, offers, {}, now=T(2026, 11, 23, 10 + k), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, sleep=lambda s: None, public=None, notify=None)
        check("d. dry run: every email to the test address only, 3 samples a day, no lead marked contacted",
              FakeSMTP.sent and all(x["to"] == "test@me.example" for x in FakeSMTP.sent) and len(FakeSMTP.sent) == 3 and not sd["sent"] and all(x["subject"].startswith("[DRY RUN") for x in FakeSMTP.sent),
              [x["to"] for x in FakeSMTP.sent])

        # ---------------------------------------------------------------- e. replies
        FakeIMAP.box = [
            (1, raw_mail("Owner Two <owner2@shop2.example>", "Re: A free website draft for Shop 2", "Please remove me from your list.\n\nOn Mon, Sam wrote:\n> Hi")),
            (2, raw_mail("Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Delivery Status Notification (Failure)", "Address not found: owner3@shop3.example could not be delivered")),
            (3, raw_mail("Owner Four <owner4@shop4.example>", "Re: A free website draft for Shop 4", "Yes, looks great! Call me at (301) 555-0199 or joe@shop4.example\n\nThanks,\nJoe\nCell 301-555-0100")),
            (4, raw_mail("Owner Five <owner5@shop5.example>", "Re: draft", "How much is the monthly part?")),
            (5, raw_mail("Random <news@letter.example>", "Weekly news", "Big sale!")),
            (6, raw_mail("Owner Six <owner6@shop6.example>", "Re: draft", "Not right now, maybe after the holidays.")),
        ]
        pushes = []
        notes = []
        res = run.run_once(live, st, leads, words, offers, {}, now=T(2026, 11, 27, 18), smtp_factory=FakeSMTP, imap_factory=FakeIMAP,
                           push=lambda files, msg: pushes.append(files) or "", notify=notes.append, public=None)
        cls = {x["lead_id"]: x["class"] for x in res["inbox"]}
        check("e. classes: opt-out, bounce, interested, question, not now", cls == {"L02": "optout", "L03": "bounce", "L04": "interested", "L05": "question", "L06": "not_now"}, cls)
        check("e. opt-out and bounce: never again (suppressed), a reply stops the sequence", core.suppressed(st, "owner2@shop2.example") and core.suppressed(st, "owner3@shop3.example")
              and all(k in st["replied"] for k in ("L02", "L03", "L04", "L05", "L06")))
        w4 = next(x for x in res["inbox"] if x["lead_id"] == "L04")["words"]
        check("e. trimmed words: no quoted thread, no signature, phone numbers and addresses masked", w4.startswith("Yes, looks great!") and "555" not in w4 and "@" not in w4 and "Joe" not in w4 and "Cell" not in w4, w4)
        check("e. an email that is not a reply to the autopilot is never stored", all("news" not in json.dumps(f) and "sale" not in json.dumps(f).lower() for f in pushes))
        check("e. one phone push for the replies to answer, with the businesses' names", len(notes) == 1 and "Shop 4" in notes[0] and "Shop 5" in notes[0], notes)
        check("e. replies are read outside the sending window (18:00 ET) but nothing is sent then", not res["sent"])
        FakeSMTP.sent = []
        for k in range(14):
            run.run_once(live, st, leads, words, offers, {}, now=T(2026, 11, 30, 9 + k // 2, 30 * (k % 2)), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, sleep=lambda s: None, public=None, notify=None)
        check("e. never again: the opt-out and the bounced address get nothing later", not [x for x in FakeSMTP.sent if x["to"] in ("owner2@shop2.example", "owner3@shop3.example")])

        # ---------------------------------------------------------------- f. Claude's drafts
        FakeSMTP.sent, notes = [], []
        drafts = [
            {"id": "d1", "inbox_id": "r4", "lead_id": "L05", "kind": "price", "subject": "Re: draft", "body": "Hi! The monthly part is $79: hosting and small edits. Book a time: https://cal.example/sam\n\nSam Test"},
            {"id": "d2", "inbox_id": "r3", "lead_id": "L04", "kind": "demo", "subject": "Re: draft", "body": "Great! Here it is: https://evil.example/x\n\nSam Test"},
            {"id": "d3", "inbox_id": "r3", "lead_id": "L04", "kind": "other", "subject": "Re: draft", "body": "Let's meet Tuesday.\n\nSam Test"},
            {"id": "d4", "inbox_id": "r3", "lead_id": "L04", "kind": "other", "subject": "Re: draft", "body": "Confirmed for Tuesday.\n\nSam Test", "approved": True},
            {"id": "d5", "inbox_id": "r1", "lead_id": "L02", "kind": "price", "subject": "Re", "body": "Our price is $1,500.\n\nSam Test"},
        ]
        cfgb = dict(live, booking_link="https://cal.example/sam")
        res = run.run_once(cfgb, st, leads, words, offers, {}, now=T(2026, 11, 30, 18), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, outbox=lambda: drafts,
                           push=lambda files, msg: "", notify=notes.append, public=None)
        stt = {x["id"]: x["status"] for x in res["outbox"]}
        check("f. a price answer with our own booking link goes out by itself; the approved one goes; the opted-out lead never",
              stt.get("d1") == "sent" and stt.get("d4") == "sent" and stt.get("d5") == "refused", stt)
        check("f. a foreign link or an unknown kind waits for the owner (one push names them)", "d2" not in stt and "d3" not in stt and notes and "wait for your OK" in notes[-1], (stt, notes))
        check("f. every reply that went out has the postal address and the way to say no", all("PO Box 12" in x["body"] and "no thanks" in x["body"].lower() for x in FakeSMTP.sent))
        res2 = run.run_once(cfgb, st, leads, words, offers, {}, now=T(2026, 11, 30, 18, 30), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, outbox=lambda: drafts,
                            push=lambda files, msg: "", notify=notes.append, public=None)
        check("f. a draft is never sent twice, a held one is not pushed again", not res2["outbox"] and len([n for n in notes if "wait" in n]) == 1)

        # ---------------------------------------------------------------- g. no secret anywhere
        st_path = os.path.join(os.environ["OLYMPUS_HOME"], "agency_mail_state.json")
        run.write_json(st_path, st)
        run.log(live, {"t": 1, "err": "login failed for " + PW.replace(" ", "")})
        leak = []
        for dp, _, fs in os.walk(os.environ["OLYMPUS_HOME"]):
            for f in fs:
                if f == "agency_mail.json":
                    continue
                txt = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                if PW in txt or PW.replace(" ", "") in txt:
                    leak.append(f)
        check("g. the app password is only in agency_mail.json (not the state, not the log even when an error quotes it)", not leak, leak)
        check("g. the public counts carry numbers only (no name, no address, no words)", not any(isinstance(v, str) and ("@" in v or "Shop" in v) for v in core.public_counts(st, live, 3).values()))
        tracked = subprocess.run(["git", "grep", "-l", "-I", "-E", "app_password\"\\s*:\\s*\"[a-z]{16}\""], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        check("g. no Gmail app password in any file of the repo", not tracked, tracked)

        # ---------------------------------------------------------------- h. the private branch (a local bare repo as the remote)
        bare = os.path.join(tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        # H1: nothing is pushed unless GitHub says the repo is private (a public repo, a 404, an error, a non-GitHub address = held on the PC)
        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        pub = lambda req, timeout=15: Resp(b'{"private": false}')  # noqa: E731
        prv = lambda req, timeout=15: Resp(b'{"private": true}')  # noqa: E731

        def e404(req, timeout=15):
            raise OSError("HTTP Error 404: Not Found")
        gh = "https://github.com/someone/somerepo.git"
        check("h. H1 gate: private only when the API says private: true (public, 404, error, a non-GitHub address = not private)",
              bridge.repo_private(gh, opener=prv) and not bridge.repo_private(gh, opener=pub) and not bridge.repo_private(gh, opener=e404)
              and not bridge.repo_private(bare, opener=prv) and bridge.repo_of("git@github.com:a-b/c.d.git") == "a-b/c.d")
        wd0 = os.path.join(tmp, "clone0")
        e0 = bridge.write_and_push(bare, wd0, {"inbox/r1.json": {"id": "r1", "words": "Yes"}}, "test")
        ls0 = subprocess.run(["git", "--git-dir", bare, "branch", "--list"], capture_output=True, text=True).stdout.strip()
        check("h. H1: while the repo is not proven private, nothing is pushed (no branch, no words) and it says why", e0 == bridge.PUBLIC_MSG and not ls0, (e0, ls0))
        bridge.PRIVATE = lambda url: True                 # the bare test repo stands in for a private GitHub repo from here on
        wd = os.path.join(tmp, "wd")
        err = bridge.write_and_push(bare, wd, {"inbox/r3.json": {"id": "r3", "class": "interested", "words": "Yes"}, "status.json": {"kind": "agency-mail-status"}}, "test")
        ls = subprocess.run(["git", "--git-dir", bare, "ls-tree", "-r", "--name-only", bridge.BRANCH], capture_output=True, text=True).stdout.split()
        check("h. inbox/ and status.json pushed to the 'agency-inbox' branch (made the first time)", not err and "inbox/r3.json" in ls and "status.json" in ls, (err, ls))
        other = os.path.join(tmp, "claude")
        subprocess.run(["git", "clone", "-q", "-b", bridge.BRANCH, bare, other], check=True)
        os.makedirs(os.path.join(other, "outbox"))
        json.dump({"id": "d9", "lead_id": "L05", "kind": "price", "body": "x"}, open(os.path.join(other, "outbox", "d9.json"), "w"))
        subprocess.run(["git", "-C", other, "-c", "user.name=c", "-c", "user.email=c@c", "-c", "commit.gpgsign=false", "add", "-A"], check=True)
        subprocess.run(["git", "-C", other, "-c", "user.name=c", "-c", "user.email=c@c", "-c", "commit.gpgsign=false", "commit", "-qm", "draft"], check=True)
        subprocess.run(["git", "-C", other, "push", "-q", "origin", bridge.BRANCH], check=True)
        e2 = bridge.sync(bare, wd)
        ob = bridge.read_outbox(wd)
        err3 = bridge.write_and_push(bare, wd, {"sent/d9.json": {"id": "d9", "status": "sent"}}, "sent")
        ls2 = subprocess.run(["git", "--git-dir", bare, "ls-tree", "-r", "--name-only", bridge.BRANCH], capture_output=True, text=True).stdout.split()
        check("h. Claude's draft (another clone's commit) is read back, the PC's answer lands on top without losing it", not e2 and [d["id"] for d in ob] == ["d9"]
              and not err3 and "outbox/d9.json" in ls2 and "sent/d9.json" in ls2, (e2, ob, err3, ls2))

        # ---------------------------------------------------------------- j. the PC report's card (no ntfy post of its own)
        from agency.autopilot import card
        croot = os.path.join(tmp, "croot")
        ok = card.write_card(core.public_counts(st, live, 7), croot)
        cd = card.read_card(card.path(croot))
        raw = open(card.path(croot), encoding="utf-8").read()
        check("j. the card for the PC report: written, < 120 bytes, numbers + the mode only, read back fresh", ok and len(raw) < 120 and cd and cd["m"] == "live" and cd["q"] == 7
              and not any(isinstance(v, str) and v not in ("live", "dry", "off") for v in cd.values()), (len(raw), cd))
        os.utime(card.path(croot), (1, 1))
        check("j. a card older than 2 days is not sent", card.read_card(card.path(croot)) is None)
        rsrc = open(os.path.join(ROOT, "agency", "autopilot", "run.py"), encoding="utf-8").read()
        check("j. the autopilot never posts to the public status topic itself (only the PC report does)", "status_feed.json" not in rsrc and "card.write_card" in rsrc)
        nn = []
        sx = core.norm_state(json.loads(json.dumps(st)))
        sx["notes"] = {}
        for k in range(8):
            FakeIMAP.box = [(1000 + k, raw_mail(f"Owner Seven <owner7@shop7.example>", "Re: draft", "How much is it?"))]
            sx["replied"].pop("L07", None)
            run.run_once(live, sx, leads, words, offers, {}, now=T(2026, 12, 1, 18, k), smtp_factory=FakeSMTP, imap_factory=FakeIMAP, notify=nn.append, public=None)
        check("j. at most 4 phone pushes a day (the PC shares ntfy's per-IP budget with the bot's alerts)", len(nn) == 4, len(nn))

        # ---------------------------------------------------------------- k. the AI caller (day-caller) + postcard codes
        import types
        H = os.environ["OLYMPUS_HOME"]
        for sub, n, j in (("consent", "k1.json", {"id": "k1", "lead_id": "L20", "business": "Shop 20", "asked_t": 1, "window": "9-12", "phone_source": "form", "version": 1}),
                          ("status", "L21.json", {"lead_id": "L21", "s": "interested", "t": "2026-12-01", "outcome": "booked"}),
                          ("outbox", "call-1.json", {"id": "call-1", "inbox_id": "", "lead_id": "L22", "kind": "booking", "subject": "Your booking",
                                                     "body": "As promised on the call, book here: https://cal.example/sam\n\nSam Test", "approved": False,
                                                     "to": "boss@shop22.example", "from_app": "caller", "caller_kind": "booking", "t": 1})):
            os.makedirs(os.path.join(H, "caller", "share", sub), exist_ok=True)
            json.dump(j, open(os.path.join(H, "caller", "share", sub, n), "w"))
        dnc = []
        fake = types.ModuleType("tools.caller")
        fake.compliance = types.SimpleNamespace(add_dnc=lambda ph, why, *a: dnc.append(("dnc", ph, why)))
        fake.consent = types.SimpleNamespace(revoke=lambda ph, why, *a: dnc.append(("revoke", ph, why)))
        sys.modules["tools.caller"], sys.modules["tools.caller.compliance"], sys.modules["tools.caller.consent"] = fake, fake.compliance, fake.consent
        kl = [dict(L) for L in leads]
        for L in kl:
            if L["id"] == "L23":
                L["phone"], L["_code"] = "(301) 555-0123", "FR-23"
            if L["id"] == "L24":
                L["_code"] = "FR-24"
                L.pop("email", None)
        sk = core.norm_state(json.loads(json.dumps(st)))
        sk["sent"].setdefault("L23", [{"to": "owner23@shop23.example", "step": "d0", "d": "2026-11-23"}])
        FakeIMAP.box = [(2001, raw_mail("Owner 23 <owner23@shop23.example>", "Re: draft", "Please stop emailing us.")),
                        (2002, raw_mail("Pat <pat@gmail.example>", "Postcard FR-24", "Got your card, how much would it cost?"))]
        FakeSMTP.sent, kp = [], []
        res = run.run_once(cfgb, sk, kl, words, offers, {}, now=T(2026, 12, 1, 18), smtp_factory=FakeSMTP, imap_factory=FakeIMAP,
                           push=lambda files, msg: kp.append(dict(files)) or "", notify=None, public=None)
        pushed = set().union(*[set(x) for x in kp]) if kp else set()
        check("k. caller/share is pushed to agency-inbox as caller/ (consent, status, outbox), the business address masked",
              {"caller/consent/k1.json", "caller/status/L21.json", "caller/outbox/call-1.json"} <= pushed
              and "boss@shop22.example" not in json.dumps(kp), sorted(pushed))
        check("k. a lead that asked for the call (consent) or was called (status) leaves the email sequence", sk["replied"].get("L20") == "call_me" and sk["replied"].get("L21") == "call_interested", sk["replied"])
        out = {x["id"]: x for x in res["outbox"]}
        check("k. the caller's promised booking email goes to the address said on the call (inbox_id empty -> 'to')",
              out.get("call-1", {}).get("status") == "sent" and any("shop22" in str(m.get("to", "")) or "shop22" in json.dumps(m, default=str) for m in FakeSMTP.sent), (out, len(FakeSMTP.sent)))
        check("k. an email opt-out also puts the phone on the caller's do-not-call list and revokes its consent",
              ("dnc", "(301) 555-0123", "email stop") in dnc and ("revoke", "(301) 555-0123", "email stop") in dnc, dnc)
        cls = {x["lead_id"]: x["class"] for x in res["inbox"]}
        check("k. a reply naming a postcard code (FR-24) is that business's reply, and its answer can go back to the writer",
              cls.get("L24") == "question" and sk["pc_from"].get("L24") == "pat@gmail.example", (cls, sk["pc_from"]))
        kp.clear()
        run.run_once(cfgb, sk, kl, words, offers, {}, now=T(2026, 12, 1, 18, 30), smtp_factory=FakeSMTP, imap_factory=FakeIMAP,
                     push=lambda files, msg: kp.append(dict(files)) or "", notify=None, public=None)
        check("k. unchanged caller files are not pushed again; the caller draft is never sent twice", not any(k.startswith("caller/") for x in kp for k in x)
              and len([m for m in FakeSMTP.sent if "shop22" in json.dumps(m, default=str)]) == 1)
        for k_ in ("tools.caller", "tools.caller.compliance", "tools.caller.consent"):
            sys.modules.pop(k_, None)

        # ---------------------------------------------------------------- i. the Windows side
        bs, bt = open(os.path.join(ROOT, "tools/bat/EMAIL_SETUP.bat"), "rb").read(), open(os.path.join(ROOT, "tools/bat/EMAIL_STOP.bat"), "rb").read()
        ps = open(os.path.join(ROOT, "scripts", "agency_mail_task.ps1"), encoding="utf-8").read()
        check("i. both .bat files use CRLF line endings", b"\r\n" in bs and b"\n" not in bs.replace(b"\r\n", b"") and b"\n" not in bt.replace(b"\r\n", b""))
        s = bs.decode()
        check("i. tools/bat/EMAIL_SETUP.bat: setup -> a test email -> the task -> status (stops if setup fails)", s.index("autopilot setup") < s.index("autopilot test") < s.index("agency_mail_task.ps1") < s.index("autopilot status") and "if errorlevel 1 goto :end" in s)
        check("i. tools/bat/EMAIL_STOP.bat: OFF, then the task removed", "autopilot stop" in bt.decode() and "-Remove" in bt.decode())
        check("i. the task: 30 minutes, pythonw, its own name, never the bot", "OlympusAgencyMail" in ps and "Minutes 30" in ps and "pythonw" in ps and "agency.autopilot run" in ps and "engine" not in ps.split("#>")[1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
