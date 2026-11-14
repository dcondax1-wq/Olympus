"""The post ideas for the two Instagram accounts (hand-written, 2026-11-14). content_plan.py turns them into a dated 30-day plan.

Each post: pillar, headline (on the image and the first caption line), 3-5 points (on the image), body (the caption), and
optionally example=True (the caption shows numbers: it is labelled "Example" and makes no claim about anyone's results).
SPECIALS are tied to a date rule and replace the next regular post on that day.

Rules for the eval journal (checked by content_plan.validate): education only, no results, no profit or income claims, no signals,
no "I passed", every caption ends with the risk line, dollar amounts only in posts marked example. Rules for local growth: no
promised rankings, no fake-review tactics, examples are labelled as examples.
"""
from __future__ import annotations

import datetime as dt

ACCOUNTS = {
    "local_growth": {
        "title": "Main Street Growth",
        "handle_ideas": ["@mainstreet.growth", "@localgrowth.notes", "@thelocalgrowthdesk"],
        "bio": "Simple, honest tips to get more local customers: Google, websites, reviews. Free website check: link below.",
        "purpose": "Teaches local business owners the basics the agency sells (Google profile, fast phone website, honest reviews) and sends "
                   "interested owners to the free website check on the agency storefront (team B3).",
        "time": "11:45",
        "hashtags": [["#smallbusiness", "#localbusiness", "#smallbusinesstips", "#googlebusinessprofile", "#localseo"],
                     ["#smallbusiness", "#websitetips", "#localbusiness", "#smallbusinessowner", "#webdesign"],
                     ["#smallbusiness", "#customerreviews", "#localbusiness", "#smallbusinesstips", "#shoplocal"],
                     ["#smallbusiness", "#socialmediatips", "#localbusiness", "#marketingtips", "#smallbusinessowner"]],
        "ctas": ["Save this for later.", "Send this to a business owner who needs it.",
                 "Want to know how your website does on a phone? Free 60-second website check: link in bio.",
                 "Questions? Ask in the comments and I'll answer.", "Follow for one simple tip a day."],
        "risk_line": "",
    },
    "eval_journal": {
        "title": "The Eval Journal",
        "handle_ideas": ["@the.eval.journal", "@evaljournal.daily", "@rules.before.results"],
        "bio": "Rules, routines and risk math for futures prop-firm evaluations. Education only. No signals. No results shown or promised.",
        "purpose": "Education for traders in prop-firm evaluations (rules, drawdown math, routines, journaling). Sells the eval tracker "
                   "(money_machines/products/eval_tracker) and, later, disclosed affiliate links. Never shows or promises results.",
        "time": "07:30",
        "hashtags": [["#futurestrading", "#propfirm", "#riskmanagement", "#tradingjournal", "#daytrading"],
                     ["#propfirmchallenge", "#futurestrading", "#tradingpsychology", "#riskmanagement", "#tradingrules"],
                     ["#tradingjournal", "#propfirm", "#tradingdiscipline", "#futurestrading", "#daytrader"]],
        "ctas": ["Save this for your next session.", "Share it with a friend who is in an evaluation.",
                 "My eval tracker (drawdown left, daily limit, size helper) is in the bio. It is my own product.",
                 "What is your rule for this? Tell me in the comments.", "Follow for one rule or routine a day."],
        "risk_line": "Education only, not financial advice. Futures trading involves substantial risk of loss and is not for everyone. "
                     "No results are shown or promised.",
    },
}

LOCAL = [
    {"pillar": "Google profile", "headline": "5 things your Google profile needs this week",
     "points": ["Your real business name, nothing added", "The most specific main category", "Correct hours, holidays too", "10+ real photos", "A reply to every review"],
     "body": "Your Google Business Profile is often the first thing a new customer sees, before your website, before your Instagram. "
             "It is free, and most local businesses leave half of it empty. Fix these five this week and you are ahead of most of your street."},
    {"pillar": "Website", "headline": "Your website has 3 seconds",
     "points": ["Say what you do and where, in one line", "Phone number at the top, tap-to-call", "One big button: Call, Book or Get a quote"],
     "body": "People on a phone decide fast. If they can't tell what you do, where, and how to reach you in about three seconds, they go back to Google "
             "and tap the next result. Open your own site on your phone right now and check those three things."},
    {"pillar": "Reviews", "headline": "How to ask for a review without feeling awkward",
     "points": ["Ask right after a good moment", "Send the direct link, not 'search us'", "Ask every customer, not only happy ones", "Never offer a reward"],
     "body": "Most happy customers would leave a review. They just forget, or can't find where. Ask at the right moment, make it one tap, "
             "and ask everyone the same way. Rewards for reviews break Google's rules and the FTC's review rule, so keep it simple: just ask."},
    {"pillar": "Myths", "headline": "Myth: 'My customers find me by word of mouth'",
     "points": ["People still Google you after a referral", "They read your reviews first", "No site or profile? They call the next name"],
     "body": "Word of mouth is great, and it now goes through Google. A friend says 'call Sam's Plumbing', and the first thing people do is search the name. "
             "What they find decides if they call. Make sure they find you, your hours and your reviews."},
    {"pillar": "Website", "headline": "Is your website losing calls? A 2-minute test",
     "points": ["Open it on your phone", "Tap the phone number: does it dial?", "Send your own form: did it arrive?", "Count: does it load in 3 seconds?"],
     "body": "You don't need a tech person for this test. Do it once a month. A broken form or a number that doesn't dial loses customers silently, "
             "and you never hear about it."},
    {"pillar": "Google profile", "headline": "Google profile photos that get calls",
     "points": ["Outside, so people find the door", "Your team, smiling", "Your work: before and after", "Inside your shop or van", "No stock photos"],
     "body": "Real photos build trust. Add a few every month, from your own phone. Good light, no filters needed. Stock photos make people wonder "
             "what you are hiding."},
    {"pillar": "Social", "headline": "What to post when you don't know what to post",
     "points": ["A job you just finished", "A question customers always ask", "A tip that saves them money", "Your team at work", "A review (with permission)"],
     "body": "You don't need to be funny or go viral. Show your work, answer questions, and be consistent. Three useful posts a week beat seven "
             "posts you can't keep up."},
    {"pillar": "Reviews", "headline": "Reply to a bad review like this",
     "points": ["Thank them for the feedback", "Own what was yours to own", "Take it offline: phone or email", "Short and calm", "Remember: new customers read it"],
     "body": "A calm, kind reply to a bad review can win you more customers than a five-star one. The reply is not for the angry reviewer, "
             "it is for everyone reading later."},
    {"pillar": "Website", "headline": "Why your website should load in under 3 seconds",
     "points": ["Big photos are the usual problem", "Shrink images before you upload", "Fewer plugins and pop-ups", "Test free with PageSpeed Insights"],
     "body": "Slow pages lose visitors, especially on a phone with a weak signal. The fix is often simple: smaller images and fewer extras. "
             "Google's free PageSpeed Insights shows what slows you down."},
    {"pillar": "Google profile", "headline": "Don't stuff keywords into your business name",
     "points": ["Use your real name, as on your sign", "'Best plumber in town' in the name can get you suspended", "Put services in the Services section"],
     "body": "It is tempting to add keywords to your name on Google. It breaks Google's guidelines and can get your profile suspended. "
             "Your services, categories and description are where those words belong."},
    {"pillar": "Myths", "headline": "Myth: 'Social media is free advertising'",
     "points": ["Free to post, not free in time", "Consistency beats volume", "Plan a month in one sitting"],
     "body": "Posting costs no money, but it costs time. The businesses that do well treat it like a small weekly job: one hour to plan, "
             "a few minutes a day to post and answer."},
    {"pillar": "Website", "headline": "5 things every local business website needs",
     "points": ["What you do and where", "Tap-to-call at the top", "Opening hours", "Real reviews", "A form or booking button"],
     "body": "You don't need ten pages and an animated slider. You need these five things, working on a phone, and loading fast. "
             "Everything else is extra."},
    {"pillar": "Money and time", "headline": "What a simple website really costs",
     "points": ["Domain: about $10-15 a year", "Hosting: free for a simple site", "Your time to keep it current", "The real cost: calls you miss without one"],
     "body": "A simple, fast website does not need a big monthly bill. Keep your domain in your own name, keep the site simple, "
             "and update your hours and services when they change."},
    {"pillar": "Google profile", "headline": "Google posts: the free ad space you're ignoring",
     "points": ["Post an offer, update or event", "Add a photo and a button", "Once a week is enough"],
     "body": "Posts on your Google profile show up when people search for you. Most businesses never use them. A short weekly post shows "
             "you are open, active and worth calling."},
    {"pillar": "Reviews", "headline": "The review QR card: one tap to your review page",
     "points": ["Put your review link in a QR code", "Counter, receipts, invoices, the van", "Ask every customer the same way"],
     "body": "Make leaving a review as easy as scanning a menu. A small card at the counter or on the invoice does the asking for you, "
             "every day, without feeling pushy."},
    {"pillar": "Social", "headline": "Instagram bio checklist for local businesses",
     "points": ["What you do + your town in line one", "How to book or call", "One link that works on phones", "Hours or service area"],
     "body": "Your bio is your shop window on Instagram. People decide in seconds whether to follow, call or leave. Make it clear, local and simple."},
    {"pillar": "Website", "headline": "Your contact form might be broken. Check today.",
     "points": ["Fill it out yourself", "Check the spam folder", "Answer within the hour", "Add tap-to-call as a backup"],
     "body": "A form that stopped sending emails months ago is more common than you think. Test it today. It takes one minute and might "
             "save a customer this week."},
    {"pillar": "Google profile", "headline": "Wrong hours on Google = angry customers",
     "points": ["Set holiday hours now", "Add special hours for events", "Check Apple Maps and Bing too"],
     "body": "Nothing annoys a customer more than driving over and finding the door locked. Update holiday hours a week ahead and you avoid "
             "the angry review."},
    {"pillar": "Myths", "headline": "Myth: 'I need a fancy website'",
     "points": ["One fast page beats a slow fancy one", "Clear beats clever", "Built for the phone first"],
     "body": "Customers don't want animations. They want to know what you do, see proof you are good, and call you. A simple page that does that "
             "wins."},
    {"pillar": "Reviews", "headline": "Should you reply to every review? Yes.",
     "points": ["Thank them by name", "Mention the service they had", "Invite them back", "Short is fine"],
     "body": "Replies show future customers that a real person cares. Thirty seconds per review. Do it every Friday and it never piles up."},
    {"pillar": "Money and time", "headline": "Where your next customer is searching",
     "points": ["Google Maps", "Google search", "Instagram and Facebook", "Neighbourhood groups", "Apple Maps"],
     "body": "Customers search in more than one place. Make sure your name, phone, address and hours are the same everywhere. "
             "Different details confuse both people and Google."},
    {"pillar": "Website", "headline": "A clear homepage, before and after (example)",
     "points": ["Before: logo, slogan, no phone number", "After: what we do in your town", "After: a call button and hours", "After: three real reviews"],
     "body": "This is a made-up example, not a real business. Look at your own homepage: is the first thing people see your logo, "
             "or the answer to 'can you help me, and how do I reach you?'"},
    {"pillar": "Google profile", "headline": "Add your services on Google (most skip this)",
     "points": ["List each main service", "A short description each", "A price if you share it", "Use the words customers use"],
     "body": "The Services section helps Google understand exactly what you offer, and it helps customers see it before they call. "
             "It is free and takes ten minutes."},
    {"pillar": "Social", "headline": "One hour, one month of posts",
     "points": ["Pick 4 themes", "Take photos during work", "Write captions in one sitting", "Schedule in Meta Business Suite (free)"],
     "body": "Batching saves your sanity. One hour on a quiet afternoon, and your Instagram and Facebook post themselves for the month. "
             "Meta Business Suite's planner is free."},
    {"pillar": "Reviews", "headline": "Never do this with reviews",
     "points": ["Buy reviews", "Write your own", "Give discounts for 5 stars", "Ask only the happy customers"],
     "body": "These shortcuts can get your profile restricted, and the FTC's 2024 rule allows big fines for fake reviews. "
             "Real reviews, asked for honestly, are slower and they last."},
    {"pillar": "Website", "headline": "Your website and your Google profile should match",
     "points": ["Same name", "Same phone number", "Same address or service area", "Same hours"],
     "body": "When your details match everywhere, customers trust you and Google trusts you. A five-minute check can fix years of mixed-up listings."},
    {"pillar": "Money and time", "headline": "Track where your calls come from",
     "points": ["Ask every new caller: how did you find us?", "Write it down for a month", "Spend more where calls come from"],
     "body": "The cheapest marketing research is one question on the phone. After a month you know if Google, referrals, Instagram or your sign "
             "brings the work."},
    {"pillar": "Social", "headline": "Show your face",
     "points": ["People buy from people", "A 10-second hello beats a logo", "Introduce your team, one per week"],
     "body": "Local customers want to know who will walk into their home or cut their hair. A friendly face builds trust faster than any slogan."},
    {"pillar": "Google profile", "headline": "Check for duplicate Google listings",
     "points": ["Search your name on Google Maps", "Old address? Duplicate profile?", "Ask Google to merge or remove it"],
     "body": "Duplicate listings split your reviews and confuse customers. Search for yourself once a quarter and clean up anything old."},
    {"pillar": "Website", "headline": "Free website check: what we look at",
     "points": ["Speed on a phone", "Tap-to-call and the contact form", "The padlock (https)", "Your Google profile link and reviews"],
     "body": "Not sure how your website does? We run a free check and send the results in plain words. No obligation and no jargon."},
    {"pillar": "Money and time", "headline": "Answer fast, win the job",
     "points": ["Many people call the next business if you don't answer", "Return missed calls within the hour", "Use a voicemail that says when you'll call back"],
     "body": "Speed is a feature. The business that answers first often gets the job. If you can't pick up, a clear voicemail and a fast call-back "
             "keep the customer."},
    {"pillar": "Reviews", "headline": "Where to put your review link",
     "points": ["Email signature", "Invoices and receipts", "Thank-you texts", "Your website footer"],
     "body": "Put the link where customers already look. Every place is one more chance for a happy customer to leave a few kind words."},
]

LOCAL_SPECIALS = [
    {"rule": "thanksgiving", "pillar": "Seasonal", "headline": "Thankful for the businesses on our street",
     "points": ["Share a local business you love", "Tag them", "Leave them a review this week"],
     "body": "Happy Thanksgiving. Small shout-outs help small businesses more than you think. Tag a local favourite in the comments."},
    {"rule": "black_friday", "pillar": "Seasonal", "headline": "Black Friday offers that don't kill your margin",
     "points": ["Bundle instead of discount", "Gift cards with a small bonus", "Early booking for January", "A thank-you for regulars"],
     "body": "You don't have to fight the big stores on price. Give local customers a reason to choose you: a bundle, a bonus, or a thank-you."},
    {"rule": "small_business_saturday", "pillar": "Seasonal", "headline": "Small Business Saturday checklist",
     "points": ["Update today's hours on Google", "Post your offer on your profile", "Review QR card at the counter", "Thank every customer"],
     "body": "Today is Small Business Saturday. People are looking for local shops on purpose. Make sure they find you open, with your offer up."},
    {"rule": "holiday_hours", "pillar": "Seasonal", "headline": "Holiday season: update these 4 things",
     "points": ["Holiday hours on Google and your site", "Gift cards, if you sell them", "A holiday post", "A thank-you to your customers"],
     "body": "December is busy. Set your hours for Christmas and New Year now so nobody finds a locked door."},
    {"rule": "new_year", "pillar": "Seasonal", "headline": "3 small goals for your business this year",
     "points": ["Ask every customer for a review", "Post 3 times a week", "Keep your Google profile current"],
     "body": "Big plans are nice. Small habits win. Pick these three and do them every week this year."},
]

EVAL = [
    {"pillar": "Rules", "headline": "Read your eval rules like a contract",
     "points": ["How the max loss moves (EOD, intraday, static)", "The daily loss limit", "Any consistency rule", "News and holiday rules", "Write them on one card"],
     "body": "Most failed evaluations break a rule, not the market. Every firm writes its rules differently. Read yours line by line before the first trade, "
             "and keep a one-card summary next to your screen."},
    {"pillar": "Risk math", "headline": "Drawdown left is the number that matters",
     "points": ["Drawdown left = balance minus the max-loss level", "A trailing level moves up, never down", "Check it before every session"],
     "body": "Example only: a $50,000 account with a $2,000 max loss starts with the max-loss level at $48,000, so drawdown left is $2,000. "
             "Every plan for the day starts from that number, not from the balance.", "example": True},
    {"pillar": "Risk math", "headline": "How end-of-day trailing drawdown works",
     "points": ["The level follows your best end-of-day balance", "Dips during the day still count", "Many firms stop the trail at a set level", "Read your firm's exact rule"],
     "body": "Example only: if the account closes a day at $50,600 with a $2,000 trailing max loss, the level moves to $48,600 and stays there "
             "until a higher close. Some firms stop trailing once it reaches the starting balance or a set amount above it.", "example": True},
    {"pillar": "Risk math", "headline": "Size follows the stop",
     "points": ["Risk in $ / (stop in points x $ per point)", "Wide stop, fewer contracts", "Never widen a stop to fit the size"],
     "body": "Example only: risking $200 with a 20-point stop on a micro Nasdaq contract ($2 a point) is $40 a contract, so 5 contracts. "
             "A 40-point stop means 2 contracts. The stop decides the size, never the other way round.", "example": True},
    {"pillar": "Routine", "headline": "A 5-minute pre-market checklist",
     "points": ["News calendar for today", "Drawdown left", "Max trades today", "Stop size and position size", "Your walk-away rule"],
     "body": "Five minutes before the open saves a lot of pain after it. Same list, every day, written down."},
    {"pillar": "Discipline", "headline": "The walk-away rule",
     "points": ["Decide before the open when you stop", "After X losses or a set amount", "Write it down", "Follow it. Tomorrow exists."],
     "body": "The worst trades happen after the plan is already broken. A walk-away rule decided in a calm moment protects you from the tilted version of you."},
    {"pillar": "Journal", "headline": "What to write in a trade journal",
     "points": ["Setup and reason", "Stop and size", "Result in R", "Emotion, 1 to 5", "Rules followed: yes or no"],
     "body": "A journal is not a diary of wins and losses. It is data about your decisions. The 'rules followed' column is the most important one."},
    {"pillar": "Myths", "headline": "Myth: 'Passing fast is the goal'",
     "points": ["The goal is not breaking rules", "Rushing usually means oversizing", "Consistency rules punish one big day"],
     "body": "An evaluation is a test of following rules. Trying to finish in two days usually means risking too much on each trade."},
    {"pillar": "Risk math", "headline": "The consistency rule, explained",
     "points": ["Some firms cap your best day as a share of total profit", "It is checked before a pass or payout", "Plan for many average days"],
     "body": "Example only: with a 40% rule, a $1,000 best day needs at least $2,500 of total profit before it counts. Read your firm's version: "
             "some apply it in the evaluation, some only for payouts.", "example": True},
    {"pillar": "Rules", "headline": "Daily loss limit vs. max loss",
     "points": ["Daily limit resets each day", "Max loss is the account's life", "Know both numbers", "Make your own daily stop smaller"],
     "body": "Two different lines, two different jobs. Breaking either one can end the account, so your personal daily stop should sit well inside both."},
    {"pillar": "Routine", "headline": "Trade less, review more",
     "points": ["A few planned trades a day", "Review each one", "Quality over quantity"],
     "body": "More trades means more costs and more chances to break a rule. A short list of planned setups, reviewed properly, is a better habit."},
    {"pillar": "Risk math", "headline": "Risk a share of drawdown left, not of the balance",
     "points": ["Pick a share, e.g. 10% of drawdown left", "Recalculate every day", "Less room means smaller trades"],
     "body": "Example only: with $2,000 of drawdown left, 10% is $200 a trade. If drawdown left falls to $1,000, the same rule gives $100. "
             "Size shrinks automatically when the account is under pressure.", "example": True},
    {"pillar": "Discipline", "headline": "How to spot revenge trading",
     "points": ["Bigger size after a loss", "No setup, just 'getting it back'", "Trading outside your hours", "The fix: your walk-away rule"],
     "body": "Everyone feels it. The difference is noticing it early. If you catch one of these signs, stand up and step away for ten minutes."},
    {"pillar": "Journal", "headline": "Rate your rules, not your P&L",
     "points": ["Score each day: plan followed, yes or no", "A red day with rules followed is a good day", "A green day with rules broken is a warning"],
     "body": "Outcomes are noisy over a few days. Process is what you control. Grade the process."},
    {"pillar": "Rules", "headline": "News days: read the rules first",
     "points": ["Some firms limit trading around big news", "Check the economic calendar each morning", "When unsure, be flat before the release"],
     "body": "Rules about news differ between firms and plans, and they change. Look them up in your firm's help pages, not in a chat group."},
    {"pillar": "Risk math", "headline": "Costs eat small targets",
     "points": ["Commissions and fees on every round trip", "Slippage on entries and stops", "On micros, costs are a big share of a small target"],
     "body": "Add costs to every plan. A setup that looks fine before costs can be flat or negative after them, especially with tight targets."},
    {"pillar": "Routine", "headline": "The end-of-day routine",
     "points": ["Screenshot your trades", "Fill in the journal", "Update drawdown left", "Set tomorrow's max loss", "Close the platform"],
     "body": "Ten minutes at the end of the day turns a session into lessons. Closing the platform is part of the routine."},
    {"pillar": "Myths", "headline": "Myth: 'More accounts means more safety'",
     "points": ["The same trades mean the same losses", "Copied accounts often fail together", "Size each one as if it were the only one"],
     "body": "Running the same trades on several accounts multiplies results in both directions. It is not diversification."},
    {"pillar": "Discipline", "headline": "Boredom is part of the job",
     "points": ["No setup, no trade", "Waiting is a decision", "Set alerts and walk away"],
     "body": "Many rule breaks start with boredom. Plan what you do while waiting: alerts on, screen off, journal open."},
    {"pillar": "Risk math", "headline": "Win rate means nothing without R",
     "points": ["R = what you make vs. what you risk", "A high win rate with tiny wins can still lose", "A low win rate with big wins can still work"],
     "body": "Example only: winning 70% of trades at 0.3R while losing 1R on the rest averages a loss per trade. Track both numbers together.", "example": True},
    {"pillar": "Rules", "headline": "Inactivity rules exist",
     "points": ["Some firms close idle accounts", "Know your firm's limit", "Put a reminder in your calendar"],
     "body": "Not trading can also break a rule. If you take a break, check your firm's inactivity rule first."},
    {"pillar": "Journal", "headline": "Tag your mistakes",
     "points": ["Early entry", "Moved stop", "Oversized", "No setup", "Chased the move"],
     "body": "Count your tags each week. Fix the most common one first. One fixed habit is worth more than ten new indicators."},
    {"pillar": "Routine", "headline": "Your trading hours are a rule",
     "points": ["Pick a window and write it down", "Trade only inside it", "Many mistakes happen outside it"],
     "body": "A fixed window keeps you rested and selective. Outside the window, the platform stays closed."},
    {"pillar": "Risk math", "headline": "How many losses in a row can you take?",
     "points": ["Drawdown left / risk per trade", "Plan for streaks, they happen", "Smaller risk = more room for mistakes"],
     "body": "Example only: $2,000 of drawdown left and $200 risk per trade means 10 losses in a row reach the max-loss level. "
             "Losing streaks are normal; the plan must survive one.", "example": True},
    {"pillar": "Discipline", "headline": "One trade does not define you",
     "points": ["Think in sets of 20 trades", "A loss is information", "Follow the process"],
     "body": "Judging yourself trade by trade leads to changing rules all the time. Judge a block of trades against your plan instead."},
    {"pillar": "Rules", "headline": "Read the payout rules before you start",
     "points": ["Minimum trading days", "Required buffer", "Maximum payout", "Any consistency rule"],
     "body": "Payout rules shape how you should trade from day one. Read them at the start, not when you think you are done."},
    {"pillar": "Myths", "headline": "Myth: 'A bigger account is easier'",
     "points": ["Bigger price, same rules in %", "More room means more room to oversize", "Prove the habits on a small one first"],
     "body": "A bigger account doesn't fix a process problem. It makes the same mistake cost more."},
    {"pillar": "Routine", "headline": "A weekly review in 15 minutes",
     "points": ["Rules followed, in %", "Mistakes tagged and counted", "Best setup of the week", "One change for next week"],
     "body": "Same time every week, same questions. Small changes, kept, add up."},
    {"pillar": "Journal", "headline": "Screenshot every trade",
     "points": ["Entry, stop and target visible", "Write the reason on it", "Review them every weekend"],
     "body": "Memory flatters us. Screenshots don't. A folder of marked charts is the best teacher you will ever pay nothing for."},
    {"pillar": "Tools", "headline": "Track your evaluation on one page",
     "points": ["Drawdown left after every day", "Daily loss limit check", "Target progress and consistency", "Position-size helper"],
     "body": "I built an eval tracker for my own routine: a spreadsheet and an offline web page with drawdown left, the daily limit, "
             "the consistency check and a size helper. It tracks rules; it does not predict or promise anything. It is my own product."},
    {"pillar": "Discipline", "headline": "Sleep is a trading tool",
     "points": ["Tired traders take worse trades", "No trading after a bad night", "Same bedtime on trading days"],
     "body": "Your rules work only if you are alert enough to follow them. Rest is part of the plan."},
    {"pillar": "Rules", "headline": "Contract limits are rules too",
     "points": ["Many plans cap how many contracts you can hold", "Micros and minis may count differently", "Check before you size up"],
     "body": "Read how your firm counts contracts. Going over the limit, even for a moment, can break the account."},
]

EVAL_SPECIALS = [
    {"rule": "thanksgiving_week", "pillar": "Rules", "headline": "Holiday week: check the trading hours",
     "points": ["Markets can close early around holidays", "Your firm may have its own holiday rules", "Thin markets move strangely: smaller or flat"],
     "body": "Before a holiday week, look up the exchange's holiday schedule and your firm's rules. If you are not sure, sit it out."},
    {"rule": "year_end", "pillar": "Journal", "headline": "Year-end: review rules, not results",
     "points": ["Rules followed, in % per month", "Most common mistake", "One habit to keep", "One habit to drop"],
     "body": "Look back at your process this year, not your balance. The habits you build now carry into next year."},
]


# ------------------------------------------------------------------------------------------------ date rules for the specials
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def special_dates(year: int) -> dict:
    tg = _nth_weekday(year, 11, 3, 4)                     # Thanksgiving: 4th Thursday of November
    return {"thanksgiving": tg, "black_friday": tg + dt.timedelta(days=1), "small_business_saturday": tg + dt.timedelta(days=2),
            "thanksgiving_week": tg - dt.timedelta(days=3), "holiday_hours": dt.date(year, 12, 1), "year_end": dt.date(year, 12, 29),
            "new_year": dt.date(year, 1, 2)}


TOPICS = {"local_growth": (LOCAL, LOCAL_SPECIALS), "eval_journal": (EVAL, EVAL_SPECIALS)}
