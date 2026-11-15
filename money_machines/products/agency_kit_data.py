"""The "first clients" agency starter kit's documents (hand-written 2026-11-14) as docgen blocks. Audience: someone starting a small
web design / local marketing service. Honest by design: no client or income promises, legal templates marked NOT LEGAL ADVICE,
outreach that follows the US email and call rules, honest-review rules (no rewards, no gating). [Brackets] are fill-ins."""
from __future__ import annotations

NOT_LEGAL = ("NOT LEGAL ADVICE. This template is a plain-English starting point written by a non-lawyer. It is not legal advice, it may not suit "
             "your situation, and it may not follow the law where you or your client are. Have a qualified lawyer in your area review it before you use it.")
EMAIL_FOOTER = "\n\n[Your name]\n[Your business name] \u00b7 [your postal address]\n[phone] \u00b7 [website]\nNot interested? Reply \"no thanks\" and I won't email you again."

START = {
    "title": "First Clients: the 30-day plan",
    "subtitle": "How to use this kit to find, sign and serve your first local clients for websites and local marketing. Read this first (10 minutes).",
    "header": "First Clients Agency Kit",
    "blocks": [
        ("h2", "What this kit is, and what it is not"),
        ("p", "It is the paperwork and the plan a one-person web or marketing service needs in its first month: what to say, what to send, "
              "what to sign, how to bill, and how to keep track. Every document is editable. Words in [brackets] are yours to fill in."),
        ("note", "**Honest note:** a kit cannot promise clients or income. What it does is remove the blank-page problem, so the hours you "
                 "have go into talking to business owners and doing good work."),
        ("warn", "The agreement and the other legal-looking templates are **not legal advice**. Laws differ by state and country. Have a "
                 "qualified local lawyer review them before you rely on them."),
        ("h2", "The kit at a glance"),
        ("table", ["File", "Use it when"], [
            ["01_Outreach_Scripts.docx", "You contact a business for the first time, follow up, or answer an objection"],
            ["02_Discovery_Call.docx", "A business owner agrees to a 20-minute call"],
            ["03_Proposal_Template.docx", "After the call: send a clear proposal within a day"],
            ["04_Service_Agreement.docx", "The client says yes: both sign before work starts"],
            ["05_Client_Onboarding.docx", "Day 1 of a project: welcome email, what you need from them, the launch check, the handover"],
            ["06_Reviews_and_Referrals.docx", "The project is done: ask for an honest review and a referral, the right way"],
            ["07_Service_Checklists.docx", "Doing the work: website launch, local listing set-up, monthly care"],
            ["Agency_Tracker.xlsx", "Every day: prospects, follow-ups, your numbers, pricing, invoices sent and paid"],
            ["Invoice_Template.xlsx", "Billing: a quote and an invoice that add up by themselves"]], [2.4, 4.3]),
        ("h2", "Week 1: one offer, one kind of client, clear prices"),
        ("ol", ["**Pick one service to lead with**, for example a fast one-page website, a website refresh, or local listing set-up. One clear offer is easier to explain than ten.",
                "**Pick one kind of client**, for example trades, salons or cafes in your area. You will learn their questions fast and your examples will fit.",
                "**Set three packages and a monthly plan** with the Pricing tab in Agency_Tracker.xlsx: list the tasks, estimate the hours, multiply by your hourly rate, add costs and a buffer.",
                "**Make one example** (your own site, or a sample site for an imaginary business) so people can see what they would get. Show client work only with permission."]),
        ("table", ["Example package (adjust to your area)", "What is in it", "Example price"], [
            ["Starter", "One-page site, mobile first, contact buttons, hours, basic search set-up", "[$]"],
            ["Standard", "Up to 5 pages, photos, a contact form, local listing set-up", "[$]"],
            ["Plus", "Standard + copywriting help + 30 days of changes after launch", "[$]"],
            ["Monthly care plan", "Small text and photo changes, checks, a short monthly note", "[$] a month"]], [2.1, 3.3, 1.3]),
        ("h2", "Week 1-2: a short list of 25 businesses"),
        ("ul", ["Look for local businesses that would clearly benefit: no website, a site that is hard to use on a phone, outdated hours, no way to book.",
                "Use public business information only (the business's own listing, sign, or site). Note where you found it in the Tracker.",
                "Write one specific, true observation for each, for example \"your hours on the map listing say closed on Saturdays but your sign says open\".",
                "Do not use tools that copy data off websites against their terms, and never buy contact lists."]),
        ("h2", "Week 2-3: reach out, personally, a few at a time"),
        ("ul", ["Aim for about 10 personal contacts a day, by walking in, calling, emailing or messaging. Use 01_Outreach_Scripts.docx.",
                "Follow up twice (after 3-4 days and after a week), then stop. Mark \"not now\" businesses for a check-in in 3 months.",
                "Log every contact in the Tracker the same day. The Dashboard tab counts them for you."]),
        ("warn", "**The rules (US; check yours if you are elsewhere).** Email: the CAN-SPAM Act applies to business emails too: use your real name "
                 "and business, an honest subject line, your postal address, and a clear way to opt out; stop within 10 business days of a request. "
                 "Calls: no autodialers or prerecorded messages, and honour every \"don't call again\". Texts: do not send marketing texts to "
                 "people who have not agreed to receive them (the TCPA). UK and EU: electronic marketing rules (PECR, GDPR) are stricter: check them first."),
        ("h2", "Week 3: the call, the proposal, the yes"),
        ("ol", ["Run the 20-minute discovery call with 02_Discovery_Call.docx. Listen more than you talk.",
                "Send the proposal (03) within 24 hours, while the conversation is fresh. Offer the package that fits, not the biggest.",
                "When they say yes: the service agreement (04) signed by both of you, then the deposit invoice (Invoice_Template.xlsx). No work before both."]),
        ("h2", "Week 4: deliver, bill, ask"),
        ("ol", ["Start with the onboarding email and content list (05). Most delays come from missing content, so ask early and clearly.",
                "Work through the launch checklist (07) before you show the client the finished site.",
                "Send the final invoice at launch. Log it in the Invoice log tab, which marks it paid, due or overdue.",
                "Ask for an honest review and a referral (06). Ask every client the same way, and never offer anything in return for a review."]),
        ("h2", "The numbers worth watching"),
        ("p", "The Tracker's Dashboard counts contacts, replies, calls, proposals and signed clients from your own log. These are your numbers, "
              "not a forecast: they show where you get stuck (few replies: change the opener; calls but no yes: change the offer or the price)."),
        ("h2", "Good habits that protect you"),
        ("ul", ["**Only true claims** about yourself: experience, results and reviews. Never promise rankings, traffic or sales to a client.",
                "**Client data stays private**: keep logins in a password manager, never in emails or the Tracker.",
                "**Accounts in the client's name**: their domain, hosting and listings belong to them; you get access, not ownership.",
                "**Records for taxes**: keep every invoice and receipt. Ask a local accountant how to register and report your income.",
                "**Insurance**: ask about professional liability insurance once you have regular clients."]),
        ("small", "Made with the help of AI tools; written, checked and supported by a person. This kit shows and promises no client, income or "
                  "ranking results. Questions? Message me through the shop where you bought this."),
    ],
}

OUTREACH = {
    "title": "Outreach scripts",
    "subtitle": "First contact, follow-ups and answers to common objections. Personal, short and true: change every [bracket].",
    "header": "First Clients Agency Kit: outreach",
    "blocks": [
        ("note", "**Three rules for every message:** 1. Say who you are and why you are contacting them, with one specific, true observation. "
                 "2. Ask for one small next step (a 15-20 minute call or a quick look at an example). 3. Make it easy to say no."),
        ("h2", "1. Walking in (the best first contact for local businesses)"),
        ("script", [("You", "Hi, I'm [name]. I make websites for local businesses here in [town]. Is the owner or manager around for one minute?"),
                    ("You", "I noticed [one true observation, e.g. you don't have a website yet / your site is hard to read on a phone / the hours online don't match your door]."),
                    ("You", "I could show you an example of what that would look like for [business name]. Would a 15-minute call this week work, or should I leave my card?"),
                    ("If busy", "No problem at all. Here's my card: when's a better time to stop by?")]),
        ("small", "Go when it is quiet (mid-morning or mid-afternoon), never when customers are waiting. Leave a card with your name, phone and one line about what you do."),
        ("h2", "2. Phone opener (about 30 seconds)"),
        ("script", [("You", "Hi, is this [business name]? My name is [name], I'm a local web designer here in [town]. Do you have 30 seconds, or is now a bad time?"),
                    ("You", "I was looking at [business] online and noticed [observation]. I help businesses like yours fix that with [your offer]."),
                    ("You", "Would you be open to a quick 15-minute call or visit this week so I can show you an example? [Day] or [day]?"),
                    ("If no", "Understood, thanks for your time. Would it be all right if I checked back in a few months?")]),
        ("h3", "Voicemail"),
        ("script", [("You", "Hi, this is [name], a web designer here in [town]. I had a quick idea about [business]'s [website / listing]. "
                            "If you'd like to hear it, my number is [phone]. Again, [name], [phone]. Thanks!")]),
        ("warn", "Call business lines yourself, by hand. No autodialers, no prerecorded messages, and stop when someone asks you to."),
        ("h2", "3. First email"),
        ("email", "A quick idea for [business name]'s website",
         "Hi [first name],\n\nI'm [your name], a web designer in [town]. I came across [business name] and noticed [one specific, true observation].\n\n"
         "I help local [type of business] with [your offer], for example [one sentence about an example or sample site].\n\n"
         "Would a 15-minute call next week be useful? I can show you what it could look like for [business name]. If now isn't a good time, no problem at all."
         + EMAIL_FOOTER),
        ("small", "CAN-SPAM (US): honest subject line, your real name and business, a real postal address, and a clear opt-out. Remove anyone who opts out within 10 business days."),
        ("h2", "4. Follow-up 1 (3-4 days later)"),
        ("email", "Re: A quick idea for [business name]'s website",
         "Hi [first name],\n\nJust bringing this back to the top of your inbox. I put together a quick example of how [business name]'s page could look on a phone: "
         "happy to send it over or show you in 15 minutes.\n\nWould [day] or [day] work?" + EMAIL_FOOTER),
        ("h2", "5. Follow-up 2 (a week later, the last one)"),
        ("email", "Should I close the loop?",
         "Hi [first name],\n\nI haven't heard back, so I'll assume the timing isn't right, and that's completely fine. "
         "If you'd like to talk about [business name]'s website later, just reply to this email.\n\nWishing you a great season." + EMAIL_FOOTER),
        ("h2", "6. Social media message (short, no links in the first message)"),
        ("email", "(no subject: a direct message)",
         "Hi [first name]! I'm [name], a web designer in [town]. Love your [true compliment about their posts or work]. I noticed [observation] "
         "and had a quick idea that might help. Would you be open to hearing it?"),
        ("h2", "7. Asking your network"),
        ("email", "A small favour",
         "Hi [name],\n\nI've started a small business making websites for local businesses. If you know an owner who's been meaning to fix their website "
         "or listing, I'd be grateful for an introduction. No pressure on them, and I'll be kind with their time.\n\nThanks!\n[Your name]"),
        ("h2", "8. Replies"),
        ("h3", "When they say \"not now\""),
        ("email", "Thanks, [first name]",
         "Thanks for letting me know. Would it be all right if I checked in around [month]? If anything changes before then, I'm here.\n\n[Your name]"),
        ("h3", "When they say \"no thanks\""),
        ("email", "Thanks for your time",
         "Thanks for the reply, [first name]. I won't contact you again. Best of luck with [business name]!\n\n[Your name]"),
        ("h2", "9. Common objections, honest answers"),
        ("table", ["They say", "You can say"], [
            ["\"We already have a website.\"", "Great. Can I show you one thing I noticed when I opened it on a phone? If it's fine, I'll tell you so."],
            ["\"It's too expensive.\"", "Understood. What would make it worth it for you? I also have a smaller starter option at [price]."],
            ["\"I don't have time.\"", "That's exactly why I keep it simple: one 20-minute call, then I need about [time] of yours in total."],
            ["\"Send me some information.\"", "Happy to. So I send the right thing: is the main goal more calls, more bookings, or just looking professional?"],
            ["\"My nephew does it.\"", "That's great to have. If you ever want a second pair of eyes, I'm happy to help."],
            ["\"Will this bring me more customers?\"", "No one can honestly say for sure. What I can do is a fast, clear site, and exactly what's in the proposal, on time."]], [2.2, 4.5]),
    ],
}

DISCOVERY = {
    "title": "Discovery call",
    "subtitle": "A 20-minute call to understand the business before you propose anything. Print it or keep it open during the call.",
    "header": "First Clients Agency Kit: discovery call",
    "blocks": [
        ("h2", "The plan for the call (20 minutes)"),
        ("table", ["Minutes", "What happens"], [["0-2", "Thank them, say how long it will take, and that you'll send a proposal only if it fits."],
                                                ["2-12", "Ask the questions below. Listen and take notes. Do not pitch yet."],
                                                ["12-17", "Say back what you heard in two sentences. Suggest one option that fits."],
                                                ["17-20", "Agree the next step: \"I'll send a proposal by [day]. Who else needs to see it?\""]], [0.9, 5.8]),
        ("h2", "Questions"),
        ("h3", "The business"),
        ("ol", ["In a sentence or two, what do you do, and for whom?", "Where do most new customers come from today?",
                "What makes you different from the other [type of business] nearby?", "Which services do you most want more of?"]),
        ("h3", "Customers"),
        ("ol", ["Who is your ideal customer?", "What do they usually ask before they book or buy?", "How do they contact you now: phone, text, walk in, email, booking app?"]),
        ("h3", "The website and listings today"),
        ("ol", ["What do you like and dislike about your current site (if any)?", "Do you control your domain and hosting? Whose name are they in?",
                "Which online listings do you have, and who can log in to them?", "Any sites you like the look of (any industry)?"]),
        ("h3", "Goals, timing and budget"),
        ("ol", ["What would a good result look like in 3 months?", "Is there a date it needs to be ready by, and why?",
                "Have you set aside a budget for this? (If not: \"Most of my projects are between [$] and [$]; does that fit?\")",
                "Who else is involved in the decision?"]),
        ("h3", "Content"),
        ("ol", ["Do you have a logo, photos and text, or do you need help with them?", "Who will be my contact for questions and approvals?"]),
        ("h2", "Notes"),
        ("fields", [("Business name", "[ ]"), ("Contact name and role", "[ ]"), ("Phone and email", "[ ]"), ("Main goal", "[ ]"),
                    ("Services to focus on", "[ ]"), ("Deadline and reason", "[ ]"), ("Budget range", "[ ]"), ("Decision makers", "[ ]"),
                    ("Content they have / need", "[ ]"), ("Package that fits", "[ ]"), ("Proposal due by", "[ ]")]),
        ("lines", 5),
        ("h2", "Watch for these (they predict problems)"),
        ("ul", ["No clear decision maker, or someone else \"has to approve everything\".", "A deadline that is days away with no content ready.",
                "\"Just copy [competitor]'s site.\" (Copying a design or text is a legal risk.)", "Expecting a set number of new customers or a top search position.",
                "Unwilling to pay a deposit."]),
        ("note", "Close kindly either way: \"Thanks for your time. I'll send the proposal by [day]\" or \"I don't think I'm the right fit for this, and here is why.\""),
    ],
}

PROPOSAL = {
    "title": "Website proposal for [Client business name]",
    "subtitle": "Prepared by [Your name], [Your business name] \u00b7 [Date] \u00b7 Proposal no. [000] \u00b7 Valid for 14 days",
    "header": "Proposal for [Client business name]",
    "blocks": [
        ("h2", "1. What you told me"),
        ("p", "[Two or three sentences in the client's words: who they are, what is not working today, and what a good result looks like for them.]"),
        ("h2", "2. What I recommend"),
        ("p", "[One paragraph: the package that fits and why. Keep it about their goal, for example \"a fast one-page site with a big call button, "
              "your hours and your prices, so people who find you on a phone can call you in one tap\".]"),
        ("h2", "3. Options"),
        ("table", ["", "Starter", "Standard", "Plus"], [
            ["Pages", "1 page", "Up to 5 pages", "Up to 5 pages"],
            ["Phone-first design, call / text / email buttons", "Yes", "Yes", "Yes"],
            ["Opening hours, services or prices, location", "Yes", "Yes", "Yes"],
            ["Contact form", "-", "Yes", "Yes"],
            ["Photo editing and placement", "Up to 5", "Up to 15", "Up to 30"],
            ["Local listing set-up or clean-up", "-", "Yes", "Yes"],
            ["Help writing the text", "-", "-", "Yes"],
            ["Changes after launch", "7 days", "14 days", "30 days"],
            ["Price", "[$]", "[$]", "[$]"]], [2.6, 1.35, 1.35, 1.35]),
        ("p", "**Optional monthly care plan:** [$] a month. Small text and photo changes (up to [1 hour] a month), regular checks that everything works, "
              "and a short monthly note. Month to month; cancel with 30 days' notice."),
        ("h2", "4. Timeline"),
        ("table", ["Week", "What happens"], [["1", "Kick-off call; you send logo, photos and text (checklist provided)"],
                                             ["2", "First version for your review"], ["3", "Your changes ([2] rounds included)"],
                                             ["4", "Launch, final check together, handover"]], [0.9, 5.8]),
        ("p", "The timeline starts when the agreement is signed, the deposit is paid and the content has arrived."),
        ("h2", "5. Not included"),
        ("ul", ["Domain name and hosting fees (paid by you, in your name; I help you set them up)", "Paid advertising and ongoing posting on social media",
                "Professional photography (I can recommend a photographer)", "Online shop or booking systems beyond a simple link"]),
        ("h2", "6. What I need from you"),
        ("ul", ["Your logo, photos and the information on the content checklist", "One contact person who can approve the work",
                "Feedback within [3] working days of each version"]),
        ("h2", "7. Investment and payment"),
        ("p", "[Package]: **[$ total]**. A deposit of [50]% ([$]) is due before work starts and the rest ([$]) at launch. "
              "Payment by [bank transfer / card / other]. The monthly plan, if chosen, is billed on the [1st] of each month."),
        ("h2", "8. Next steps"),
        ("ol", ["Reply to say which option you choose.", "I send the service agreement and the deposit invoice.", "We book the kick-off call."]),
        ("note", "This proposal describes the work and the price. The terms (changes, ownership, cancellation) are in the service agreement we both sign. "
                 "It does not promise a result such as search ranking, traffic or sales."),
        ("sign", ["Accepted by (name and title)", "Date"]),
    ],
}

AGREEMENT = {
    "title": "Website services agreement",
    "subtitle": "Between [Your business name] (\"Designer\") and [Client legal name] (\"Client\") \u00b7 Date: [date]",
    "header": "Website services agreement (template: not legal advice)",
    "blocks": [
        ("warn", NOT_LEGAL),
        ("h2", "1. The parties"),
        ("fields", [("Designer", "[Your name / business name], [address], [email]"), ("Client", "[Client legal name], [address], [contact person], [email]")]),
        ("h2", "2. The services"),
        ("p", "The Designer will provide the services described in proposal no. [000] dated [date] (the \"Proposal\"), which is part of this agreement. "
              "Anything not listed in the Proposal is not included unless both parties agree to it in writing (email is fine)."),
        ("h2", "3. Timeline"),
        ("p", "Work starts when this agreement is signed, the deposit is paid and the Client's content has arrived. The Designer will aim to meet the timeline in the "
              "Proposal. Delays in content or feedback from the Client move the timeline by the same amount."),
        ("h2", "4. Fees and payment"),
        ("ul", ["Total fee: [$] as in the Proposal. Deposit: [50]% ([$]), due before work starts. Balance: [$], due at launch or [14] days after the final version is delivered, whichever comes first.",
                "Monthly care plan (if chosen): [$] a month, billed in advance on the [1st] of each month.",
                "Invoices are due within [14] days. [Optional, where lawful: a late fee of [x]% a month on overdue amounts.]",
                "The Designer may pause work while an invoice is overdue."]),
        ("h2", "5. Changes"),
        ("p", "The fee includes [2] rounds of changes to each version. Extra changes, or new work outside the Proposal, are charged at [$] an hour or quoted in advance, "
              "and only after the Client agrees in writing."),
        ("h2", "6. The Client's part"),
        ("ul", ["Provide content (text, photos, logo, information) and answers on time, and approve or comment within [3] working days of each version.",
                "Make sure the content is accurate and that the Client has the right to use it (for example photos, logos and reviews).",
                "Keep the domain, hosting and listings in the Client's own name and pay their fees."]),
        ("h2", "7. Ownership"),
        ("ul", ["When the Client has paid in full, the Client owns the final website design and content made for this project.",
                "The Designer keeps ownership of their own tools, templates and know-how used to make it, and gives the Client a permanent licence to use them as part of the website.",
                "Third-party items (fonts, photos, plugins, services) stay under their own licences.",
                "The Designer may show the finished work in their portfolio [only with the Client's written permission / unless the Client says no in writing]."]),
        ("h2", "8. Third-party services"),
        ("p", "Hosting, domain, email, booking and other third-party services are provided by those companies under their terms. The Designer is not responsible "
              "for their outages, price changes or policy changes."),
        ("h2", "9. Confidentiality"),
        ("p", "Both parties keep the other's non-public information private and use it only for this project. Logins are shared through a secure method and changed at handover if the Client wishes."),
        ("h2", "10. No guarantees of results; limits"),
        ("ul", ["The Designer will do the work with reasonable skill and care. The Designer does not guarantee search rankings, traffic, leads or sales.",
                "To the extent the law allows, the Designer's total liability under this agreement is limited to the fees the Client paid under it, and neither party is liable for indirect or lost-profit damages.",
                "[Some places do not allow these limits: your lawyer will tell you what applies.]"]),
        ("h2", "11. Ending the agreement"),
        ("ul", ["Either party may end this agreement with [14] days' written notice. The Client pays for work done up to that date; the deposit covers the first [x] hours of work.",
                "The monthly care plan is month to month and can be cancelled with 30 days' written notice.",
                "On ending, the Designer hands over the files and access for the work paid for."]),
        ("h2", "12. General"),
        ("ul", ["This agreement and the Proposal are the whole agreement. Changes must be in writing and agreed by both.",
                "Governing law: [state / country]. [Optional: how disputes are handled, for example by talking first, then mediation, then the courts of [place].]",
                "Each party is an independent business; this agreement does not create employment or a partnership.",
                "Signatures can be electronic."]),
        ("sign", ["Designer: name and signature", "Date", "Client: name, title and signature", "Date"]),
        ("small", "Template version 1.0. Not legal advice. Review with a qualified lawyer in your area before use."),
    ],
}

ONBOARDING = {
    "title": "Client onboarding",
    "subtitle": "From \"yes\" to launch day: the welcome email, the content list, the kick-off agenda, the launch check and the handover.",
    "header": "First Clients Agency Kit: onboarding",
    "blocks": [
        ("h2", "1. Welcome email (send the day they sign)"),
        ("email", "Welcome! Next steps for [business name]'s website",
         "Hi [first name],\n\nThank you for choosing [your business name]. I'm looking forward to this.\n\nHere's what happens next:\n"
         "1. Your deposit invoice is attached (due [date]).\n2. Please send the items on the attached content list by [date]. Photos straight from your phone are fine.\n"
         "3. Kick-off call: [day, time] (or reply with a better time).\n\nYou'll see the first version by [date]. Any questions, just reply here.\n\n[Your name]"),
        ("h2", "2. Content list (send with the welcome email)"),
        ("check", ["Logo (the original file if you have it, otherwise a clear photo)", "5-15 photos: the work, the place, the team (with their permission)",
                   "Services or menu with prices (or \"from\" prices)", "Opening hours, including holidays", "Address or the area you serve",
                   "Phone, email and how customers should contact you", "Two or three sentences about you and the business",
                   "Answers to the 4-6 questions customers ask most", "Real reviews you are allowed to show (and the customers' permission)",
                   "Logins or access: domain, hosting, listings (shared securely, never by plain email)", "Anything that must not be on the site"]),
        ("h2", "3. Kick-off call agenda (30 minutes)"),
        ("ol", ["Confirm the goal and the main action for visitors (call, book, visit).", "Walk through the content list: what is missing and who sends it.",
                "Agree dates for the first version and for feedback.", "Agree how feedback is sent (one email with all changes works best).", "Questions."]),
        ("h2", "4. Before launch: the check"),
        ("check", ["Every button works on a real phone: call, text, email, directions, booking", "Name, address, phone and hours match the listings",
                   "No sample text or placeholder photos are left", "Spelling checked by you and by the client", "Every claim is true and approved by the client",
                   "Page titles and descriptions say what and where", "Loads fast on a phone (test it on mobile data)", "The client has said \"yes, launch it\" in writing"]),
        ("h2", "5. Handover email (launch day)"),
        ("email", "[Business name]'s website is live",
         "Hi [first name],\n\nYour new website is live at [address]. Congratulations!\n\nWhat you have:\n- The site and its files (attached / in your account)\n"
         "- Access: [where the logins are, shared securely]\n- [Care plan: what's included each month, if chosen]\n\nYour final invoice is attached (due [date]).\n\n"
         "One small request: if you're happy with how it went, an honest review of my work would help me a lot. Here is the link: [review link]. "
         "Good or bad, I read every review.\n\nThank you!\n[Your name]"),
    ],
}

REVIEWS = {
    "title": "Reviews and referrals, the honest way",
    "subtitle": "Ask every client for an honest review, reply to every review, and ask for introductions. With the rules that keep you and your clients safe.",
    "header": "First Clients Agency Kit: reviews and referrals",
    "blocks": [
        ("warn", "**The rules.** Ask every customer, not only the happy ones. Never offer money, discounts or gifts for a review, and never ask only for positive ones. "
                 "Never write reviews yourself, for your own business or for a client's, and never ask friends or family to pose as customers. Never hide or "
                 "suppress honest negative reviews. In the US the FTC's Consumer Reviews and Testimonials Rule (2024) bans fake and bought reviews and "
                 "review suppression, with civil penalties, and review sites remove reviews that break their own rules."),
        ("h2", "1. Asking for a review"),
        ("h3", "In person or on the phone"),
        ("script", [("You", "Thanks for working with me. Would you be willing to leave an honest review about how it went? It really helps a small business like mine. "
                            "I'll text or email you the link, and good or bad, I read every one.")]),
        ("h3", "By email"),
        ("email", "Would you share how it went?",
         "Hi [first name],\n\nThank you again for choosing [your business name]. If you have two minutes, would you leave an honest review of your experience? "
         "Here's the link: [review link]\n\nIt helps other business owners decide, and it helps me improve. Thank you!\n\n[Your name]"),
        ("h3", "By text (only to clients who agreed to texts from you)"),
        ("email", "(text message)", "Hi [first name], it's [name] from [business]. Thanks again! If you have a minute, an honest review would mean a lot: [review link]"),
        ("h2", "2. Replying to reviews"),
        ("h3", "A positive review"),
        ("email", "(public reply)", "Thank you, [first name]! It was a pleasure working on [project]. Wishing [their business] a great season."),
        ("h3", "A mixed review"),
        ("email", "(public reply)", "Thank you for the honest feedback, [first name]. I'm glad [the good part] worked well, and you're right about [the issue]: "
                                    "I've [what you changed]. I'd be glad to talk it through: [phone or email]."),
        ("h3", "A negative review"),
        ("email", "(public reply)", "[First name], I'm sorry this wasn't the experience you expected. I take this seriously and would like to put it right. "
                                    "Please contact me at [phone or email] so we can talk. [Your name]"),
        ("small", "Stay calm and short, never argue in public, never share private details, and fix what you can. If a review is clearly not about your business, report it "
                  "through the site's own process instead of arguing."),
        ("h2", "3. Testimonial permission (before you quote a client on your site)"),
        ("fields", [("Client name and business", "[ ]"), ("The words you may quote", "[their exact words]"), ("Where you may show them", "[website / proposals / social media]"),
                    ("Name shown as", "[first name and business / initials only]"), ("Photo or logo allowed?", "[yes / no]")]),
        ("p", "I agree that [your business name] may show the words above, as written, in the places listed. I can ask for them to be removed at any time."),
        ("sign", ["Client signature", "Date"]),
        ("h2", "4. Asking for a referral"),
        ("email", "A small favour",
         "Hi [first name],\n\nI'm glad [project] is working well for you. If you know another business owner who'd like help with their website or listing, "
         "I'd be grateful for an introduction. I'll be respectful of their time.\n\nThank you!\n[Your name]"),
        ("note", "Thank people for referrals with a sincere thank-you. If you decide to offer a referral reward, offer it for introductions, never for reviews, and keep "
                 "it the same for everyone."),
    ],
}

CHECKLISTS = {
    "title": "Service checklists",
    "subtitle": "Three services you can offer and deliver the same way every time: website launch, local listing set-up, monthly care.",
    "header": "First Clients Agency Kit: service checklists",
    "blocks": [
        ("h2", "1. Website launch"),
        ("check", ["Domain and hosting in the client's name; you have access", "Mobile-first design checked on two real phones",
                   "Tap-to-call, text, email and directions buttons tested", "Hours, address and phone match the listings", "Every page has a title and a description that say what and where",
                   "Photos compressed so pages load fast", "Every image has a short text description (alt text)", "Text readable: colour contrast checked",
                   "Contact form (if any) tested end to end; a short privacy notice if it collects data", "HTTPS (the padlock) on",
                   "Old addresses redirected if a previous site existed", "The client approved the final version in writing", "Handover email sent"]),
        ("h2", "2. Local listing set-up (a free business profile on the big search and map sites)"),
        ("note", "The business owner creates or claims the listing and completes the verification steps themselves; you help with the details. "
                 "Follow each site's guidelines: the real business name with no extra keywords, a real address (no virtual offices) or a service area, "
                 "and only real photos."),
        ("check", ["Business name exactly as on the sign and the paperwork", "The most specific main category, plus a few accurate extra categories",
                   "Address or service area (never both a fake address and a service area)", "Opening hours, including special and holiday hours",
                   "Phone number and website address", "A plain description of what the business does (no promises, no keyword lists)",
                   "Services or products with short descriptions", "10 or more real photos: outside, inside, work, team (with permission)",
                   "Questions and answers customers often ask", "A plan to reply to every review (see the reviews document)",
                   "Same name, address and phone on the website and other listings"]),
        ("h2", "3. Monthly care plan"),
        ("check", ["Small text and photo changes the client asked for (up to the hours in the plan)", "Check every page and button still works on a phone",
                   "Check hours and holiday hours on the site and listings", "Check the domain and hosting renewal dates", "Back up the site files",
                   "Note any errors or security warnings and fix or report them", "Send a short monthly note: what you did, anything that needs the client's decision"]),
        ("h3", "The monthly note"),
        ("email", "[Business name]: your website this month",
         "Hi [first name],\n\nThis month I:\n- [change 1]\n- [change 2]\n- Checked every page and button on a phone: [all fine / fixed X]\n\n"
         "Coming up: [renewal date, holiday hours, anything to decide].\n\nAnything you'd like changed next month? Just reply.\n\n[Your name]"),
    ],
}

DOCS = [("01_Outreach_Scripts.docx", OUTREACH), ("02_Discovery_Call.docx", DISCOVERY), ("03_Proposal_Template.docx", PROPOSAL),
        ("04_Service_Agreement.docx", AGREEMENT), ("05_Client_Onboarding.docx", ONBOARDING), ("06_Reviews_and_Referrals.docx", REVIEWS),
        ("07_Service_Checklists.docx", CHECKLISTS)]
