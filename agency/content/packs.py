"""Trade packs: the words, colours, fonts, icons and posting times for each kind of local business.

Eight packs: barber, salon, restaurant, plumber (plumbing + HVAC), landscaper, auto (repair), gym, dentist.

Writing rules for everything in here (the owner sells this to real businesses):
  - nothing invented about the business: no prices, no opening hours, no "since 1998", no fake reviews or star counts;
  - anything that assumes a service the client may not offer (gift cards, catering, emergency calls, financing ...) carries a
    `check`: a yes/no question the owner asks the client before the post goes out (they are listed together in the approval note);
  - tips are plain, widely accepted advice (manufacturer / ADA / extension-service style), never medical or legal promises;
  - headlines are short enough for the image (about 30 characters); *word* marks the word drawn in the accent colour.

Placeholders filled per client: {name} {city} {site} {phone} {pro} {pros} {weather} {season} {month} {next_month} {year} {next_year}
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------------------------------------------- shared words
# the season x climate phrases behind {weather}
WEATHER = {
    ("winter", "cold"): ["the snow and ice", "freezing mornings", "the deep cold"],
    ("winter", "mild"): ["the cold snaps", "chilly mornings", "the cooler days"],
    ("winter", "warm"): ["our mild winter", "the cooler evenings", "the winter crowds"],
    ("winter", "rainy"): ["the rain and grey skies", "the damp cold", "the short, wet days"],
    ("spring", "cold"): ["the thaw", "the first warm days", "spring rain"],
    ("spring", "mild"): ["the first warm days", "spring storms", "pollen season"],
    ("spring", "warm"): ["the warm-up", "the last mild weeks", "pollen season"],
    ("spring", "rainy"): ["spring showers", "the first dry days", "longer evenings"],
    ("summer", "cold"): ["the summer heat", "the long summer days", "the warm days"],
    ("summer", "mild"): ["the summer heat", "the long hot days", "the humidity"],
    ("summer", "warm"): ["the heat", "the long hot days", "the sunny days"],
    ("summer", "rainy"): ["the dry summer days", "the summer heat", "the sunshine"],
    ("fall", "cold"): ["the first frost", "the falling leaves", "the cooler nights"],
    ("fall", "mild"): ["the cooler mornings", "the falling leaves", "the first cool front"],
    ("fall", "warm"): ["the first cool front", "the cooler evenings", "the end of the heat"],
    ("fall", "rainy"): ["the return of the rain", "the falling leaves", "the shorter days"],
}

REVIEW_ASK = [
    ("Your *words* matter", "If we took good care of you this month, would you leave us a quick Google review? It takes a minute and helps "
     "other {city} neighbors find a {pro} they can trust. Thank you!"),
    ("Thank you for every *review*", "Every review you leave helps a small {city} business like ours. If you have a minute, search {name} on "
     "Google and tell people how it went. We read every single one."),
    ("Happy with your visit?", "Tell your neighbors! A short Google review is the best thank-you a local business can get. Search {name} "
     "on Google, tap Reviews, done."),
    ("Five stars make our *day*", "Reviews keep the lights on at local businesses. If you liked your visit, a few words on Google mean the "
     "world to the team at {name}."),
]

TEAM = [
    ("Meet the *team*", "The people behind {name} are {city} locals who care about doing it right. Next time you are in, say hi and "
     "ask us anything."),
    ("The faces behind *{name}*", "We are a small team and we know a lot of you by name. That is our favorite part of the job. Thanks for "
     "being part of it, {city}."),
]

LOCAL = [
    ("Proudly *local*", "We are not a chain. {name} is a local business run by people who live in {city}, shop here and care how this "
     "town looks and feels. Thank you for keeping it local."),
    ("Love where you *live*", "Every visit to a local business keeps money in {city}. Tell us your favorite local spot in the comments, "
     "we love to support them too."),
    ("Here for *{city}*", "From the first customer we ever had to the newest one this week: thank you for trusting a neighbor. That "
     "trust is everything to us."),
    ("Shop small, *{city}*", "Big brands do not know your name. We do. Thanks for choosing a small local business."),
]

BOOKING = [
    ("Plan *ahead*", "Our calendar fills up a week or two out. Pick your day now and your next {visit} is one less thing to think about."),
    ("Book in a *minute*", "Booking your next {visit} takes about a minute. Pick a time that suits you and we will take it from there."),
    ("Popular times go *first*", "Have a favorite day or time? Book your {visit} early in the week, before it is taken."),
    ("{month} is *filling up*", "There are still good times left in {month}. Book your {visit} before they are gone."),
]

ENGAGE = [
    ("Tell us in the *comments*", "What should we post more of: tips, behind the scenes, or before-and-afters? Tell us below, we read "
     "every comment."),
    ("Question of the *week*", "What is one thing you wish every {pro} did better? Honest answers welcome. We are listening."),
]

# holiday words for every trade (a trade's own `holiday` entry wins). Respect days never sell.
HOLIDAY = {
    "new_year": [("Happy New *Year*", "Thank you for an amazing {last_year}, {city}. Here is to a healthy, happy year ahead. We cannot wait "
                  "to see you soon.")],
    "mlk": [("Honoring *Dr. King*", "Today we honor the life and legacy of Dr. Martin Luther King Jr. and the work of building a fairer "
             "community for all of us.")],
    "valentines": [("Happy *Valentine's* Day", "To our customers, neighbors and the whole {city} community: we love being your {pro}. "
                    "Happy Valentine's Day!")],
    "presidents": [("Happy Presidents' *Day*", "Wishing everyone in {city} a good long weekend. See you soon!")],
    "st_patricks": [("Lucky to have *you*", "Happy St. Patrick's Day, {city}! We are lucky to have customers like you.")],
    "easter": [("Happy *Easter*", "Wishing every family in {city} a happy, sunny Easter weekend.")],
    "earth_day": [("Happy Earth *Day*", "Small changes add up. Today we are thinking about how we can waste less and take care of {city} "
                   "for the long run.")],
    "mothers_day": [("For every *mom*", "Happy Mother's Day to all the moms, grandmas and mother figures in {city}. You deserve the best "
                     "day.")],
    "memorial_day": [("We *remember*", "Today we remember the men and women who gave their lives in service to our country. With gratitude.")],
    "fathers_day": [("Happy Father's *Day*", "To the dads, granddads and father figures of {city}: thank you. Enjoy your day.")],
    "juneteenth": [("Honoring *Juneteenth*", "Today we mark Juneteenth and the end of slavery in the United States, and we celebrate "
                    "freedom with our community.")],
    "july4": [("Happy *4th* of July", "Wishing everyone in {city} a safe, happy Independence Day with family, friends and good food.")],
    "labor_day": [("Happy Labor *Day*", "To every hard-working person in {city}: enjoy the long weekend. You earned it.")],
    "halloween": [("Happy *Halloween*", "Have a safe and spooky Halloween, {city}! Watch out for the little ones out trick-or-treating "
                   "tonight.")],
    "veterans_day": [("Thank you, *veterans*", "Today we honor every veteran in {city} and beyond. Thank you for your service.")],
    "thanksgiving": [("We are *thankful*", "This Thanksgiving we are thankful for you, our customers and neighbors. Thank you for "
                      "supporting a local business. Enjoy the day with the people you love.")],
    "small_business_saturday": [("Shop *small* this Saturday", "Small Business Saturday is about the shops and services that make {city} "
                                 "feel like home. Thank you for choosing local, this weekend and every weekend.")],
    "dst_start": [("Clocks spring *forward*", "Reminder: the clocks go forward an hour this weekend. Lighter evenings are on the way, "
                   "{city}!")],
    "dst_end": [("Clocks fall *back*", "Reminder: the clocks go back an hour this weekend. Enjoy the extra hour of sleep, {city}.")],
    "spring": [("Hello, *spring*", "The first day of spring is here. Time for fresh starts, open windows and longer days in {city}.")],
    "summer": [("Hello, *summer*", "Longest day of the year! Get outside and enjoy it, {city}.")],
    "fall": [("Hello, *fall*", "The first day of fall is here. Cooler mornings, cozy evenings, and a busy season ahead.")],
    "winter": [("Hello, *winter*", "Today is the shortest day of the year. From here on, the days only get longer. Stay warm, {city}!")],
    "back_to_school": [("Back to *school*", "A new school year is almost here. Good luck to every student, parent and teacher in {city}!")],
    "hanukkah": [("Happy *Hanukkah*", "Wishing a happy Hanukkah to everyone celebrating in {city}. May the festival of lights bring "
                  "warmth and joy to your home.")],
    "christmas_eve": [("Almost *Christmas*", "The countdown is on, {city}! Thank you for being part of our year. Wishing you a calm, "
                       "happy Christmas Eve.")],
    "christmas": [("Merry *Christmas*", "From all of us at {name}: merry Christmas, {city}. Thank you for a wonderful year. Enjoy the "
                   "day with the people you love.")],
    "kwanzaa": [("Happy *Kwanzaa*", "Wishing a joyful Kwanzaa to everyone celebrating in {city}.")],
    "nye": [("Cheers to *{next_year}*", "Thank you for every visit, call and kind word this year. We are ready for {next_year}. Happy "
             "New Year's Eve, {city}!")],
    # trade observances get their words from the trade pack
}

# ------------------------------------------------------------------------------------------------------------------- palettes
def _pal(name, bg, ink, accent, paper, paper_ink, soft=None):
    return {"name": name, "bg": bg, "ink": ink, "accent": accent, "paper": paper, "paper_ink": paper_ink, "soft": soft or bg}


# --------------------------------------------------------------------------------------------------------------------- packs
PACKS: dict[str, dict] = {}

PACKS["barber"] = {
    "label": "Barbershop", "pro": "barber", "pros": "barbers", "visit": "cut", "aliases": ["barber", "barbershop", "barber shop", "mens grooming", "men's grooming", "fade"],
    "icons": ["scissors", "comb", "razor"], "motif": "pole", "upper": True,
    "fonts": {"display": "bebas", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Slate & barber red", "#1E2A2F", "#F3EBDD", "#D9603F", "#F3EBDD", "#1E2A2F"),
                 _pal("Navy & brass", "#14213D", "#F5EFE3", "#D4A24C", "#F5EFE3", "#14213D"),
                 _pal("Forest & gold", "#1F3B2D", "#F1EADB", "#D2A84B", "#EFE7D6", "#1F3B2D")],
    "tags": ["#barber", "#barbershop", "#freshcut", "#fade", "#mensgrooming", "#barberlife", "#haircut", "#beardcare"],
    "city_tag": "Barber",
    "cta": ["Book your chair: {site}", "Call {phone} to grab a chair.", "Book online at {site} or call {phone}."],
    "times": {1: "11:30", 2: "11:30", 3: "17:30", 4: "11:30", 5: "08:30"},
    "times_note": "Tue, Wed, Fri 11:30 am (lunch-break bookings), Thu 5:30 pm, Sat 8:30 am",
    "services": [
        ("Skin *fade*", "Clean, sharp and blended down to the skin. Tell us how high you want it and we will take it from there.", ""),
        ("Beard *trim*", "Shape, line and condition. A good beard trim changes your whole face, and it only takes a few minutes in the chair.", ""),
        ("Hot towel *shave*", "Old-school straight razor shave with a hot towel. The most relaxing half hour in {city}.", "Do you offer hot towel shaves?"),
        ("Kids' *cuts*", "Patient barbers, quick cuts, no tears (well, fewer tears). Bring the little ones in.", "Do you cut kids' hair?"),
        ("The classic *taper*", "Timeless, tidy, works in the office and on the weekend. Ask for it by name.", ""),
        ("Line-up & *edge*", "In between cuts? A quick line-up keeps your look sharp for days.", ""),
    ],
    "tips": {
        "any": [
            ("Condition short hair *too*", "Conditioner is not just for long hair. A quick condition keeps short hair soft and easier to style."),
            ("Less product, *more* style", "Start with a pea-size amount of product. You can always add more, but too much weighs hair down."),
            ("Style it *damp*", "Most products work best on slightly damp hair. Towel dry, then style."),
            ("Get a beard *brush*", "A boar-bristle brush trains your beard to grow the right way and spreads the oil evenly."),
            ("Keep your razor *clean*", "Rinse your razor well and let it dry between shaves. A clean blade means fewer nicks and bumps."),
            ("Shave *with* the grain", "Shave with the grain first for less irritation. Go against it only on a second pass, if at all."),
            ("Scalps *burn* too", "Short cut or shaved head? Your scalp burns too. A little sunscreen on sunny days goes a long way."),
            ("Tell us your *cowlick*", "Every head has its quirks. Tell your barber where your hair fights you and they will cut with it, not against it."),
            ("Fades last 2-3 *weeks*", "A fade grows out fast. Book every two to three weeks and it never looks like it needs a cut."),
            ("Beard oil every *day*", "A few drops of beard oil after a shower keeps the skin under your beard from getting itchy and flaky."),
            ("Paste or *pomade*?", "Matte paste for a natural, textured look. Pomade for shine and a slick finish. Not sure? Ask your barber."),
            ("Do not shave the *neckline*", "The most common home mistake: shaving the neckline too high. Leave it to us between cuts."),
            ("Wash less, rinse *more*", "Shampoo every day dries out your scalp. Try every other day and rinse with water in between."),
            ("Bring a *photo*", "Pictures beat words. Save a photo of the cut you like and show it to your barber."),
            ("Towel dry *gently*", "Rubbing hard with a towel roughs up your hair. Pat it dry and style while it is still a little damp."),
            ("Trim your *brows*", "Ask us to tidy your eyebrows during your cut. Small detail, big difference."),
        ],
        "winter": [("Winter *scalp* care", "Dry indoor heat and {weather} are rough on your scalp. A light moisturizing shampoo helps.", {"cold", "mild", "rainy"}),
                   ("Hat hair *fix*", "Wearing a beanie? A little texture powder brings flat hair back to life in seconds.")],
        "spring": [("Spring *refresh*", "New season, new look. Spring is the perfect time to try something shorter or bolder.")],
        "summer": [("Go shorter for *summer*", "Shorter sides keep you cooler in {weather}. Ask for a taper that grows out clean.")],
        "fall": [("Fall *reset*", "After a summer of sun and salt, a fresh cut and beard trim gets you back to sharp.")],
    },
    "checklists": [("Fresh cut *checklist*", ["Book every 2-3 weeks", "Bring a photo", "Oil your beard daily", "Ask about products"])],
    "offers": [
        ("Gift a fresh *cut*", "Gift cards make the easiest present for the guy who has everything. Ask at the shop.", "Do you sell gift cards?", {11, 12}),
        ("Bring a *friend*", "Refer a friend and you both get a little something off your next cut. Ask us how.", "Do you want a refer-a-friend deal? What is it?", None),
        ("Father & son *day*", "Book two chairs side by side for you and the kid. Best hour of the month.", "Do you cut kids' hair?", None),
        ("New here? *Welcome*", "First visit to {name}? Tell your barber, we will make sure you leave happy.", "", None),
    ],
    "bts": [
        ("Behind the *chair*", "Every cut starts with a clean station and a sharp blade. This is what 8 am looks like at {name}.", "a photo of the stations being set up in the morning"),
        ("Tools of the *trade*", "Clippers, shears, straight razors and a lot of practice. What would you like to know about how we work?", "a flat-lay of the barber's tools"),
        ("Before & *after*", "Same guy, 40 minutes apart. Swipe to see the difference a fresh fade makes.", "a before/after of a real client (with permission)"),
    ],
    "faq": [
        ("How often should I get a *cut*?", "Fades and short styles: every 2-3 weeks. Longer styles: every 4-6 weeks."),
        ("Do I need to *book*?", "Booking guarantees your chair. Walk in when you like and we will fit you in if we can."),
        ("Can you fix a *bad cut*?", "Usually, yes. Come in, show us what happened, and we will tell you honestly what we can do."),
    ],
    "engage": [("Fade or *taper*?", "Settle it in the comments: skin fade or classic taper? Wrong answers only... just kidding, tell us yours.")],
    "booking": [("Book before the *rush*", "Our chairs fill up fast before the holidays. Grab your spot now so you are not stuck "
                 "looking shaggy in the family photos.", {11, 12}),
                ("Your chair is *waiting*", "It has been a few weeks, has it not? Book your next cut today.")],
    "season": {
        "winter": [("Sharp for the *season*", "Holiday parties, family photos, a big night out. Look sharp for all of it in {city} this {season}.", {11, 12}),
                   ("Winter *sharp*", "Cold outside, fresh cut inside. Keep it clean and sharp all {season} in {city}.", {1, 2})],
        "spring": [("Spring *clean-up*", "Shed the winter shag. Spring is the season for a clean, fresh cut.")],
        "summer": [("Summer *ready*", "Short, clean and easy to style when it is hot out. Summer cuts are our favorite.")],
        "fall": [("Back in *style*", "Fall is here and so is the season of looking put together. Come see us.")],
    },
    "holiday": {
        "christmas_eve": [("Last chairs before *Christmas*", "A few chairs are left before Christmas. Grab one now and walk into the family dinner looking your best.")],
        "nye": [("Fresh for *{next_year}*", "Ring in the new year with a fresh cut. Last appointments of the year go fast. Happy New Year's Eve, {city}!")],
        "fathers_day": [("For the best *dads*", "Happy Father's Day! The best gift for dad? An hour in the chair with a hot towel and zero to-do list.")],
        "back_to_school": [("Back-to-school *cuts*", "First-day photos are coming. Book the kids' back-to-school cuts before the rush.")],
        "valentines": [("Date night *ready*", "Valentine's dinner booked? Now book the cut. Look sharp for date night.")],
    },
}

PACKS["salon"] = {
    "label": "Hair Salon", "pro": "stylist", "pros": "stylists", "visit": "appointment", "aliases": ["salon", "hair salon", "hair", "beauty salon", "stylist", "hairdresser", "spa"],
    "icons": ["comb", "sparkle", "mirror"], "motif": "arcs", "upper": False,
    "fonts": {"display": "cormorant", "accent": "playfair_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Aubergine & rose gold", "#3B2A35", "#F6EAE4", "#D9A08F", "#F6EAE4", "#3B2A35"),
                 _pal("Sage & champagne", "#3F5244", "#F4F1EA", "#D8BB82", "#EEF0E8", "#34443A"),
                 _pal("Espresso & cream", "#2B2523", "#F3E9DC", "#C9A27A", "#F3E9DC", "#2B2523")],
    "tags": ["#hairsalon", "#hairstylist", "#balayage", "#haircolor", "#hairgoals", "#salonlife", "#healthyhair", "#blowout"],
    "city_tag": "Salon",
    "cta": ["Book your appointment: {site}", "Call {phone} to book.", "Book online at {site} or call {phone}."],
    "times": {1: "10:00", 2: "19:00", 3: "10:00", 4: "12:00", 5: "09:00"},
    "times_note": "Tue, Thu 10 am, Wed 7 pm (evening scrolling), Fri noon, Sat 9 am",
    "services": [
        ("Balayage", "Soft, hand-painted color that grows out beautifully. Low maintenance, high impact.", "Do you do balayage?"),
        ("The perfect *blowout*", "Smooth, bouncy and lasts for days. Perfect before an event, a trip or just because.", ""),
        ("Gloss & *shine*", "A gloss treatment refreshes your color and adds serious shine between appointments.", "Do you offer gloss treatments?"),
        ("Precision *cut*", "A great cut is the base of every great hair day. Tell us how you style it and we will cut for your real life.", ""),
        ("Color *refresh*", "Roots showing? A quick color refresh gets you back to your best shade.", ""),
        ("Deep *treatment*", "A repairing treatment for hair that is dry, colored or heat-styled. Your ends will thank you.", "Do you offer deep conditioning treatments?"),
    ],
    "tips": {
        "any": [
            ("Air-dry *halfway*", "Let hair air-dry about halfway before you blow-dry. Less time under heat means less damage."),
            ("Finish with the *cool shot*", "End your blow-dry with the cool button. It helps set the style and adds shine."),
            ("Be gentle when *wet*", "Hair is most fragile when it is wet. Use a wide-tooth comb and take your time."),
            ("Clean your *brushes*", "Wash brushes and combs every couple of weeks. Old product and oil end up right back in your hair."),
            ("Loosen the *ponytail*", "A tight ponytail in the same spot every day can cause breakage. Switch it up and use soft ties."),
            ("Purple shampoo, *sparingly*", "Blonde turning brassy? Purple shampoo once a week or so tones it down. Too often can leave a tint."),
            ("Book *before* you leave", "Book your next appointment at the desk. You get the time you want and never go too long between visits."),
            ("Tell us your *routine*", "How you style at home matters. Tell your stylist what you do each morning and they will cut for it."),
            ("Heat protectant, *always*", "Before every blow-dry or flat iron, use a heat protectant. It is the easiest way to keep hair healthy."),
            ("Trim every 8-12 *weeks*", "Regular trims stop split ends from traveling up the hair. Growing it out? Trims still help."),
            ("Try a *silk* pillowcase", "Silk or satin causes less friction than cotton, so you wake up with less frizz and fewer tangles."),
            ("Wash in *lukewarm* water", "Very hot water can dull color and dry out your scalp. Lukewarm is kinder to your hair."),
            ("Dry shampoo *the night before*", "Spray dry shampoo at night and it absorbs oil while you sleep. Brush it out in the morning."),
            ("Color-safe *shampoo*", "Sulfate-free, color-safe shampoo helps your color last weeks longer."),
            ("Brush from the *ends*", "Start brushing at the ends and work up. Less breakage, less pain."),
            ("Save your *inspo*", "Save photos of hair you love and bring them in. It helps us get it exactly right."),
        ],
        "winter": [("Winter *hydration*", "Indoor heat and {weather} pull moisture out of hair. Add a weekly hydrating mask.", {"cold", "mild", "rainy"}),
                   ("Fight the *static*", "Static flyaways? A drop of hair oil on your palms, smoothed over the top, tames them fast.")],
        "spring": [("Spring *lightening*", "Thinking of going lighter for spring? Book early, it can take more than one visit to get there gently.")],
        "summer": [("Protect from the *sun*", "Sun fades color. A hat or a UV-protect spray keeps your shade bright through summer."),
                   ("Pool *tip*", "Wet your hair with clean water before swimming. It soaks up less chlorine.")],
        "fall": [("Fall *color* season", "Fall is the perfect time for richer, warmer tones. Ask us about your best fall shade.")],
    },
    "checklists": [("Healthy hair *routine*", ["Heat protectant every time", "Trim every 8-12 weeks", "Weekly hydrating mask", "Silk pillowcase"])],
    "offers": [
        ("Give the gift of *glow*", "Gift cards for every budget. The easiest present for anyone who loves a salon day.", "Do you sell gift cards?", {11, 12}),
        ("Bring a *friend*", "Book together and make it a salon date. Ask us about booking side-by-side appointments.", "", None),
        ("Treat *yourself*", "Add a treatment to any appointment this month. Ask your stylist which one is right for you.", "Any treatment add-on to promote this month?", None),
        ("New client? *Welcome*", "First time at {name}? Mention this post when you book and tell us what you love about your hair.", "", None),
    ],
    "bts": [
        ("Behind the *chair*", "Coffee on, music on, tools ready. This is how a day at {name} begins.", "the salon before opening, lights on"),
        ("Color *lab*", "Every color is mixed for you, by hand. A little science, a lot of art.", "the stylist mixing color"),
        ("The *transformation*", "Before and after a few hours in the chair. Swipe to see it.", "a before/after (with the client's OK)"),
    ],
    "faq": [
        ("How long does color *take*?", "A root touch-up is usually around 90 minutes; a full balayage can take 3 hours or more. We will tell you when you book."),
        ("Can I go *blonde* in one visit?", "Sometimes. If your hair is dark or colored, going light gently may take two visits. We always put hair health first."),
        ("What should I bring to my *consult*?", "Photos of hair you love (and hate!), and how much time you spend styling each morning."),
    ],
    "engage": [("Warm or *cool*?", "Golden honey or icy blonde? Tell us your shade in the comments.")],
    "booking": [("Party season is *here*", "Holiday parties, photos and dinners: book your color and blowout now while there is still room.", {11, 12}),
                ("Time for a *refresh*?", "It has been about eight weeks, has it not? Book your next visit today.")],
    "season": {
        "winter": [("Winter *glow*", "Rich tones, glossy finishes, and healthy ends. Winter hair, done right in {city}.")],
        "spring": [("Spring *refresh*", "Lighter, brighter, fresher. Spring is the season for a change.")],
        "summer": [("Sun-kissed *season*", "Soft highlights and easy styles for {weather}. Summer hair should be effortless.")],
        "fall": [("Fall *favorites*", "Copper, chocolate and caramel. Our favorite colors of the year are back.")],
    },
    "holiday": {
        "nye": [("New Year's Eve *glam*", "Last chance for New Year's Eve hair! Book a blowout or updo and ring in {next_year} looking your best.")],
        "mothers_day": [("Treat *mom*", "Happy Mother's Day! A salon gift card is the gift moms actually use. Ask us in the salon.", "Do you sell gift cards?")],
        "valentines": [("Date night *hair*", "Valentine's plans? Book a blowout and feel amazing all night.")],
        "christmas_eve": [("Last-minute *gift*?", "A salon visit is a gift anyone would love. Stop by before Christmas.")],
    },
}

PACKS["restaurant"] = {
    "label": "Restaurant", "pro": "restaurant", "pros": "restaurants", "visit": "table", "aliases": ["restaurant", "cafe", "café", "bistro", "pizzeria", "pizza", "diner", "bar", "grill", "bakery", "taqueria", "kitchen", "food"],
    "icons": ["cutlery", "chefhat", "plate"], "motif": "gingham", "upper": False,
    "fonts": {"display": "fraunces", "accent": "playfair_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Tomato & cream", "#7A2420", "#FBF3E4", "#EDB84F", "#FBF3E4", "#3A1A12"),
                 _pal("Olive & paprika", "#3D4A2A", "#F6F0E1", "#E58A4E", "#F6F0E1", "#2E3620"),
                 _pal("Charcoal & saffron", "#23211F", "#F4ECDD", "#F0A43A", "#F4ECDD", "#23211F")],
    "tags": ["#foodie", "#localeats", "#dinnertime", "#eatlocal", "#restaurant", "#goodfood", "#datenight", "#lunchtime"],
    "city_tag": "Eats",
    "cta": ["Reserve a table: {phone}", "See the menu: {site}", "Call {phone} or visit {site}."],
    "times": {0: "11:00", 1: "11:00", 2: "16:30", 3: "16:30", 4: "11:30", 5: "10:00", 6: "10:00"},
    "times_note": "Mon, Tue 11 am and Fri 11:30 am (lunch plans), Wed, Thu 4:30 pm (dinner plans), weekends 10 am",
    "services": [
        ("House *favorite*", "The dish our regulars order again and again. Ask your server which one, then thank us later.", ""),
        ("Date *night*", "Good food, good company, no dishes to wash. Bring someone you like.", ""),
        ("Lunch, *sorted*", "Need a lunch break that feels like a break? We have you covered.", ""),
        ("Family *table*", "Big table, big appetites, everyone happy. Bring the whole crew.", ""),
        ("Takeout *night*", "Not in the mood to cook? Call ahead and pick it up hot.", "Do you do takeout?"),
        ("Celebrate *here*", "Birthdays, anniversaries, promotions: let us do the cooking. Call ahead for groups.", ""),
    ],
    "tips": {
        "any": [
            ("Short lunch *break*?", "Tell your server when you sit down that you are on the clock. We will keep things moving."),
            ("Celebrating *something*?", "Birthday, anniversary, new job? Tell us when you book. We love to celebrate with you."),
            ("Order for the *table*", "Order a few plates to share and try more of the menu in one visit."),
            ("Ask what is *fresh*", "Ask your server what the kitchen is excited about today. There is always a favorite."),
            ("Bringing the *kids*?", "Tell us when you arrive and we will find the best table for your crew."),
            ("Leftovers, *safely*", "Get leftovers into the fridge within two hours and enjoy them within a few days."),
            ("Want a quiet *table*?", "Ask when you book and we will do our best to find you a calm corner."),
            ("Midweek is *relaxed*", "Want a slower, easy dinner? Early evenings midweek are usually our calmest hours."),
            ("Beat the *rush*", "Fridays fill up fast. Come a little early or call ahead and skip the wait."),
            ("Big group? *Call ahead*", "Six or more? A quick call helps us set the perfect table for you."),
            ("Ask about *allergies*", "Tell your server about any allergy. We will walk you through the menu."),
            ("Reheat it *right*", "Leftovers? A hot pan or the oven beats the microwave every time."),
            ("Save room for *dessert*", "Just saying. You will not regret it."),
            ("Try something *new*", "Always order the same thing? Ask your server what they would order tonight."),
            ("Lunch is the *secret*", "Some of our best tables are quiet at lunch. Treat yourself midweek."),
            ("Tag *us*", "Love your plate? Tag {name} in your photos, we share our favorites."),
        ],
        "winter": [("Comfort food *season*", "With {weather} outside, warm plates and a cozy table are the best plan for the evening.", {"cold", "mild", "rainy"}),
                   ("Cool evenings, *warm* plates", "Cooler evenings in {city} call for a warm plate and good company.", {"warm"})],
        "spring": [("Patio *season*", "The first warm evenings are here. Ask for a table outside when the weather is nice.", "Do you have outdoor seating?")],
        "summer": [("Cool down *here*", "Escape the heat with something cold and a seat in the shade or the A/C.")],
        "fall": [("Cozy *season*", "Cooler nights call for warm, hearty dishes. Come in and warm up.")],
    },
    "checklists": [("Party of *six* or more?", ["Call ahead", "Tell us about allergies", "Ask about the specials", "Save room for dessert"])],
    "offers": [
        ("Gift *dinner*", "Restaurant gift cards: the present that everyone actually uses. Ask at the counter.", "Do you sell gift cards?", {11, 12}),
        ("Holiday *parties*", "Office party or family get-together? Ask us about booking a big table this season.", "Do you host holiday parties or large groups?", {11, 12}),
        ("Midweek *treat*", "Make Wednesday the best night of the week. Come in for dinner midweek.", "Any midweek special to promote?", None),
        ("Catering for your *event*", "Feeding a crowd? Ask us about catering for your next party or meeting.", "Do you cater?", None),
    ],
    "bts": [
        ("Before the *doors open*", "Prep starts long before you sit down. A peek at the kitchen before service at {name}.", "the kitchen during prep"),
        ("Meet the *kitchen*", "The people who cook your food. Say hi next time you are in!", "the cooks at the pass (with their OK)"),
        ("Fresh from the *pass*", "This is the moment a plate leaves the kitchen. Hot, fresh, and on its way to you.", "a plate at the pass, close-up"),
    ],
    "faq": [
        ("Do you take *reservations*?", "Call us and we will hold a table for you. Walk-ins are welcome too."),
        ("Is there *parking*?", "Ask us when you call and we will point you to the easiest spot nearby."),
        ("Can you do *gluten-free*?", "Tell your server and we will show you the options. Please mention any allergy when you order."),
    ],
    "engage": [("Sweet or *savory*?", "Settle it: are you a dessert-first or a second-appetizer person? Tell us below.")],
    "booking": [("Book the *holiday table*", "Holiday nights fill up fast. Call now to reserve your table for the holidays.", {11, 12}),
                ("Weekend *plans*?", "Reserve your table for the weekend before it fills up.")],
    "season": {
        "winter": [("Warm *plates*, cold nights", "With {weather} outside, there is no better place to be than a warm table in {city}.", {"cold", "mild", "rainy"}),
                   ("Winter *evenings*", "Mild winter evenings in {city} are made for dinner out. Come in and stay a while.", {"warm"})],
        "spring": [("Fresh *season*", "Spring is here and so are lighter, fresher plates. Come taste the season.")],
        "summer": [("Summer *nights*", "Long evenings, cold drinks and good food. Summer in {city} tastes better here.")],
        "fall": [("Hello, *cozy*", "Fall flavors are back. Come in from the cold and stay a while.")],
    },
    "holiday": {
        "nye": [("New Year's Eve *dinner*", "Ring in {next_year} with dinner at {name}. Call to reserve your table before they are gone.")],
        "valentines": [("Valentine's *dinner*", "Skip the dishes, bring your favorite person. Book your Valentine's table now.")],
        "mothers_day": [("Take *mom* to dinner", "Mother's Day is one of our busiest days. Reserve now so mom gets the best table.")],
        "thanksgiving": [("Thankful for *you*", "Happy Thanksgiving from our kitchen to your table. Thank you for every meal you shared with us this year.")],
        "christmas_eve": [("Holiday *gift* idea", "Still shopping? A {name} gift card is the gift of a night off. Ask at the counter.", "Do you sell gift cards?")],
    },
}

PACKS["plumber"] = {
    "label": "Plumbing & HVAC", "pro": "plumber", "pros": "plumbers", "visit": "service visit", "aliases": ["plumber", "plumbing", "hvac", "heating", "cooling", "air conditioning", "ac repair", "furnace", "heating & cooling", "plumbing & hvac", "plumber/hvac", "drain"],
    "icons": ["wrench", "droplet", "flame"], "motif": "pipes", "upper": True,
    "fonts": {"display": "archivo", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Trust blue & safety orange", "#0F2D4A", "#F2F6F9", "#F28C28", "#EEF3F7", "#0F2D4A"),
                 _pal("Deep teal & yellow", "#0E4D5A", "#F1F7F7", "#F6C445", "#EDF5F5", "#0E3A44"),
                 _pal("Navy & heat red", "#1B263B", "#F4F1EC", "#E25A3F", "#F4F1EC", "#1B263B")],
    "tags": ["#plumber", "#plumbing", "#hvac", "#homeowner", "#homemaintenance", "#heatingandcooling", "#waterheater", "#homeimprovement"],
    "city_tag": "Plumber",
    "cta": ["Call {phone} to book a visit.", "Book online: {site}", "Call {phone} or book at {site}."],
    "times": {0: "07:30", 1: "07:30", 2: "12:00", 3: "07:30", 4: "12:00", 5: "09:00"},
    "times_note": "Mon, Tue, Thu 7:30 am (before work), Wed, Fri noon, Sat 9 am",
    "hvac_words": ["hvac", "heating", "cooling", "air", "ac ", "a/c", "furnace", "heat"],
    "services": [
        ("Water heater *service*", "No hot water, rusty water or strange noises? We repair and replace water heaters.", "", "p"),
        ("Drain *cleaning*", "Slow drains and clogs cleared properly, not just pushed further down the pipe.", "", "p"),
        ("Leak *repair*", "A small drip today is a big bill tomorrow. We find and fix leaks fast.", "", "p"),
        ("Furnace *tune-up*", "A tune-up before the cold keeps your heat running when you need it most.", "", "h", {8, 9, 10, 11, 12, 1, 2}),
        ("AC *check*", "Get your AC checked before the heat arrives, not during the first heat wave.", "", "h", {3, 4, 5, 6, 7}),
        ("Fixture *installs*", "New faucet, toilet or garbage disposal? We install it right the first time.", "", "p"),
    ],
    "tips": {
        "any": [
            ("Exercise your *valves*", "Turn the shut-off valves under sinks and toilets once a year so they do not seize up when you need them.", "p"),
            ("Strainers save *drains*", "A cheap mesh strainer in the shower and kitchen sink catches hair and food before it becomes a clog.", "p"),
            ("Only flush the *3 Ps*", "Pee, poo and paper. Wipes, even the 'flushable' kind, are one of the top causes of clogs.", "p"),
            ("Banging pipes?", "Banging pipes or dripping fixtures can mean the water pressure is too high. We can test it for you.", "p"),
            ("How old is your *heater*?", "Find the date on the water heater label. Knowing its age helps you plan a replacement before it fails.", "p"),
            ("Program the *thermostat*", "A programmable or smart thermostat can cut heating and cooling costs while you sleep or are away.", "h"),
            ("Dust the *vents*", "Vacuum supply and return vents a few times a year. Dust on the grilles ends up in your air.", "h"),
            ("Seal the *drafts*", "Weather-stripping on doors and windows keeps warm or cool air in, so your system works less.", "h"),
            ("Find your *shut-off*", "Know where your main water shut-off valve is. In a burst-pipe emergency, it saves your floors.", "p"),
            ("No grease down the *drain*", "Grease hardens in your pipes. Let it cool, wipe it into the trash, and your drains will thank you.", "p"),
            ("Flush your water *heater*", "Draining a little water from the tank once a year clears sediment and helps it last longer.", "p"),
            ("The food coloring *test*", "Put a few drops of food coloring in the toilet tank. Color in the bowl without flushing? You have a leak.", "p"),
            ("Go easy on drain *cleaners*", "Harsh chemical drain cleaners can damage pipes over time. Call us for a clog that will not clear.", "p"),
            ("Change your air *filter*", "Swap the HVAC filter every 1-3 months. Cleaner air and less strain on your system.", "h"),
            ("Keep the unit *clear*", "Leave about two feet of open space around your outdoor AC unit so it can breathe.", "h"),
            ("Do not close *vents*", "Closing vents in empty rooms can make your system work harder, not less. Keep them open.", "h"),
        ],
        "winter": [("Drip on freezing *nights*", "When it drops well below freezing, let faucets on outside walls drip and open the cabinet doors.", "p", {"cold", "mild", "rainy"}),
                   ("Unhook the *hose*", "Disconnect garden hoses before a freeze so the outdoor faucet does not split.", "p", {"cold", "mild", "rainy"}),
                   ("Heat on? *Listen*", "Banging, rattling or a burning smell from the furnace is your cue to call us.", "h")],
        "spring": [("Check the *sump pump*", "Pour a bucket of water into the sump pit. If the pump does not kick on, call us before the spring rain.", "p"),
                   ("AC check *now*", "Book your AC check in spring and skip the summer waiting list.", "h")],
        "summer": [("Help your *AC*", "Close blinds on sunny windows and change the filter. Your AC will run less in {weather}.", "h"),
                   ("Vacation *tip*", "Going away? Turn the water heater to vacation mode and shut the main water off for peace of mind.", "p")],
        "fall": [("Furnace *tune-up* time", "Book your heating tune-up before the first cold night, not after.", "h"),
                 ("Clear the *gutters*", "Leaves block gutters and downspouts, and that water ends up in your basement.", "p")],
    },
    "checklists": [("Winter-proof your *pipes*", ["Know your shut-off valve", "Unhook garden hoses", "Insulate exposed pipes", "Drip faucets on freezing nights"], {10, 11, 12, 1, 2}, {"cold", "mild", "rainy"}),
                   ("Before you call *us*", ["Is the breaker on?", "Is the valve open?", "Any water on the floor?", "Snap a photo for us"], None)],
    "offers": [
        ("Book your *tune-up*", "Book a seasonal tune-up this month and get ahead of the busy season.", "Any tune-up deal this month? (or keep it as a plain reminder)", None),
        ("Ask about a *second opinion*", "Got a big quote somewhere else? We are happy to take a look and give you an honest second opinion.", "Do you do second opinions?", None),
        ("Senior & veteran *thanks*", "We offer a thank-you discount for seniors and veterans. Just ask when you call.", "Do you give a senior/veteran discount?", None),
        ("Peace of mind *plan*", "Ask about our yearly maintenance visit: one call, and we keep an eye on everything.", "Do you offer a maintenance plan?", None),
    ],
    "bts": [
        ("On the *job*", "Clean boots, covered floors, tidy work. This is how we treat every home in {city}.", "the tech on a job (with the homeowner's OK)"),
        ("The *van*", "Our van is a workshop on wheels, stocked so most jobs get fixed on the first visit.", "the inside of the work van"),
        ("Meet your *tech*", "The person who shows up at your door. Licensed, friendly, and on time.", "a portrait of a technician"),
    ],
    "faq": [
        ("How old is too old?", "Most tank water heaters last around 8-12 years. Older than that and acting up? Time to talk about a replacement."),
        ("Why is my bill *higher*?", "A running toilet or a hidden leak can waste a lot of water. If your bill jumped, call us to check."),
        ("Repair or *replace*?", "We will tell you honestly. If a repair makes sense, we repair it."),
    ],
    "engage": [("What is that *noise*?", "Gurgling drains, banging pipes, a humming furnace? Tell us your weirdest house noise below.")],
    "booking": [("Beat the *rush*", "Our calendar fills up fast when the weather turns. Book your visit now."),
                ("Small leak? *Call now*", "A small drip is cheap to fix. A ceiling stain is not. Call us today.")],
    "season": {
        "winter": [("Ready for *winter*?", "With {weather} here, frozen pipes and tired furnaces keep us busy. A quick check now saves a cold night later.", {"cold", "mild", "rainy"}),
                   ("Busy season at *home*", "Holiday guests and full houses keep drains and water heaters busy. A quick check now saves a call later.", {"warm"})],
        "spring": [("Spring *check-up*", "Spring rain and the first warm days are the time to check sump pumps, outdoor faucets and the AC.")],
        "summer": [("Beat the *heat*", "Summer heat is hard on your AC. A quick check keeps it running when you need it.")],
        "fall": [("Fall *prep*", "Before the cold sets in: furnace check, hoses off, gutters clear. We can help.")],
    },
    "holiday": {
        "thanksgiving": [("Thankful for *you*", "Happy Thanksgiving! Tip from your plumber: scrape plates into the trash, not the disposal, and run cold water while it is on.")],
        "christmas_eve": [("Guests coming *over*?", "More guests mean more showers, more dishes and more toilet flushes. Space out the showers and keep grease out of the sink.")],
        "dst_end": [("Clocks back? *Check*", "When the clocks change, test your smoke and carbon monoxide detectors. Takes a minute, could save a life.")],
        "dst_start": [("Clocks forward? *Check*", "Clocks change this weekend: a good moment to test smoke and CO detectors.")],
        "world_plumbing": [("Happy World Plumbing *Day*", "Today is World Plumbing Day! Clean water and working pipes keep {city} healthy. Proud to be part of it.")],
    },
}

PACKS["landscaper"] = {
    "label": "Landscaping", "pro": "landscaper", "pros": "landscapers", "visit": "visit", "aliases": ["landscaper", "landscaping", "lawn", "lawn care", "yard", "gardening", "garden", "tree service", "lawncare"],
    "icons": ["leaf", "tree", "sprout"], "motif": "leaves", "upper": False,
    "fonts": {"display": "dmserif", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Forest & leaf", "#20402F", "#F3F0E3", "#A9C45C", "#F3F0E3", "#20402F"),
                 _pal("Soil & sprout", "#4A3B2A", "#F5EFE2", "#97B85A", "#F1ECDC", "#3A2E21"),
                 _pal("Sage & terracotta", "#3E5641", "#F4EFE6", "#D9845A", "#F4EFE6", "#2E3F31")],
    "tags": ["#landscaping", "#lawncare", "#curbappeal", "#yardgoals", "#gardendesign", "#outdoorliving", "#greengrass", "#homeowner"],
    "city_tag": "Landscaping",
    "cta": ["Get a quote: {phone}", "Request a quote at {site}", "Call {phone} or visit {site}."],
    "times": {0: "07:00", 1: "12:00", 2: "07:00", 3: "12:00", 4: "07:00", 5: "08:00"},
    "times_note": "Mon, Wed, Fri 7 am (coffee scroll), Tue, Thu noon, Sat 8 am (yard-work mood)",
    "services": [
        ("Weekly *mowing*", "Crisp lines and a clean cut every week, so your weekends are yours again.", ""),
        ("Mulch & *beds*", "Fresh mulch and tidy beds make the whole house look cared for.", ""),
        ("Spring *clean-up*", "Leaves out, beds edged, lawn ready to grow. The fastest way to curb appeal.", ""),
        ("Planting & *design*", "New beds, shrubs and trees that suit your yard and the {city} climate.", "Do you do planting/design?"),
        ("Leaf *removal*", "We clear the leaves so your lawn can breathe before winter.", ""),
        ("Hedge & shrub *trimming*", "Neat shapes, healthy growth, no ladder for you.", ""),
    ],
    "tips": {
        "any": [
            ("Water the *roots*", "Water at the base of plants, not over the leaves. More water reaches the roots and leaves stay healthier."),
            ("Weed *after rain*", "Weeds come out roots and all when the soil is moist. Best time to weed: the day after rain."),
            ("Feed the *soil*", "Healthy soil grows healthy plants. A thin layer of compost each year does wonders."),
            ("Mow *dry* grass", "Mowing wet grass gives a ragged cut and leaves clumps. Wait until it dries."),
            ("Change direction", "Switch your mowing direction each time. Grass stands up straighter and wheels do not leave ruts."),
            ("Young trees get *thirsty*", "New trees need deep watering in dry spells for their first couple of years."),
            ("Group by *thirst*", "Plant thirsty plants together and tough, dry-loving plants together. Watering gets easier and wastes less."),
            ("Native plants *win*", "Plants native to your area need less water and care once settled in, and they feed local pollinators."),
            ("Mow *high*", "Taller grass shades the soil, holds water and crowds out weeds. Never cut more than a third at once."),
            ("Water in the *morning*", "Early watering loses less to evaporation and helps prevent lawn disease."),
            ("Leave the *clippings*", "Grass clippings break down fast and feed your lawn. Skip the bag."),
            ("Sharp blades *matter*", "A dull mower blade tears grass and leaves brown tips. Sharpen it a couple of times a season."),
            ("Mulch 2-3 *inches*", "A 2-3 inch layer of mulch holds moisture and blocks weeds. Keep it off tree trunks."),
            ("Water *deeply*", "Deep watering a few times a week beats a little every day. Roots grow down, lawns get tougher."),
            ("Right plant, right *place*", "Sun-loving plants in shade will struggle. Ask us what thrives in your yard."),
            ("Edges make the *yard*", "A crisp edge along beds and paths makes even a simple yard look professionally kept."),
        ],
        "winter": [("Stay off frozen *grass*", "Walking on frosted grass breaks the blades. Give your lawn a break on frosty mornings.", {"cold", "mild", "rainy"}),
                   ("Plan your *spring*", "Winter is the time to plan new beds and planting. Our spring calendar fills up fast.")],
        "spring": [("Spring *starts now*", "Rake out dead grass, edge the beds and add fresh mulch. Your lawn wakes up happy.")],
        "summer": [("Raise the *mower*", "In hot weather, raise the mower deck. Longer grass handles heat much better.")],
        "fall": [("Fall is for *planting*", "Cooler air and warm soil make fall a great time to plant trees and shrubs."),
                 ("Mulch the *leaves*", "Run the mower over light leaf cover. The shreds feed the lawn over winter.")],
    },
    "checklists": [("Spring yard *checklist*", ["Rake and clear debris", "Edge the beds", "Fresh mulch", "Sharpen the mower"], {2, 3, 4, 5}),
                   ("Fall yard *checklist*", ["Clear the leaves", "Last low mow", "Plant trees and shrubs", "Drain hoses"], {9, 10, 11})],
    "offers": [
        ("Book spring *early*", "Our spring schedule fills up fast. Get on the list now and be first in line.", "", {1, 2, 3}),
        ("Free *estimate*", "Tell us about your yard and we will send you a clear, honest quote.", "Do you give free estimates?", None),
        ("Neighbor *deal*", "Get your neighbor to sign up too and we will both save on the visit. Ask us how.", "Do you want a neighbor discount? What is it?", None),
        ("Gift a *clean yard*", "A clean-up for mom or dad is a gift they will see every day.", "Do you sell gift certificates?", {11, 12}),
    ],
    "bts": [
        ("Crew at *work*", "Early start, clean finish. Our crew takes pride in every yard in {city}.", "the crew working (with the homeowner's OK)"),
        ("Before & *after*", "Same yard, one visit apart. Swipe to see the difference.", "a before/after of a real yard"),
        ("The *trailer*", "Mowers, trimmers and a lot of mulch. Ready for the day.", "the loaded trailer in the morning"),
    ],
    "faq": [
        ("How often should I *mow*?", "In the growing season, about once a week. Cut no more than a third of the blade at a time."),
        ("When should I *aerate*?", "Cool-season grass: early fall. Warm-season grass: late spring. We can tell you which you have."),
        ("Do you *haul away*?", "Ask when you book and we will tell you what is included in your visit."),
    ],
    "engage": [("Stripes or *no stripes*?", "Do you love the striped lawn look or keep it classic? Tell us below.")],
    "booking": [("Spring is *coming*", "Our spring calendar opens soon. Reserve your spot now.", {1, 2, 3}),
                ("Ready for *curb appeal*?", "Call this week to get on the schedule.")],
    "season": {
        "winter": [("Winter *yard* care", "With {weather} here, your yard is resting. Now is the time to plan, prune and get on the spring list.", {"cold", "mild", "rainy"}),
                   ("Winter *yard* care", "Cooler days in {city} are a good time to plant, prune and plan the spring. Let us help.", {"warm"})],
        "spring": [("Spring *green-up*", "Spring is here and your lawn is waking up. Let us help it start strong.")],
        "summer": [("Summer *lawn* care", "Summer heat is hard on lawns. Mow high, water deep, and call us for the rest.")],
        "fall": [("Fall *clean-up*", "Leaves down, beds tucked in, lawn ready for winter. Book your fall clean-up.")],
    },
    "holiday": {
        "earth_day": [("Happy Earth *Day*", "Healthy lawns and trees cool our streets and clean our air. Proud to keep {city} green.")],
        "lawn_month": [("National Lawn Care *Month*", "April is National Lawn Care Month! The perfect time to get your lawn on a schedule.")],
        "july4": [("Backyard *ready*", "Hosting the 4th? A fresh mow and tidy beds the day before makes the whole party look good. Happy Independence Day!")],
        "christmas_eve": [("Merry & *green*", "Wishing you a peaceful holiday. Thank you for trusting us with your yard this year.")],
    },
}

PACKS["auto"] = {
    "label": "Auto Repair", "pro": "mechanic", "pros": "mechanics", "visit": "service", "aliases": ["auto", "auto repair", "mechanic", "garage", "car repair", "auto shop", "tire", "tires", "body shop", "oil change", "automotive"],
    "icons": ["car", "gear", "wrench"], "motif": "chevrons", "upper": True,
    "fonts": {"display": "anton", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Graphite & signal yellow", "#1C1F24", "#F2F2EE", "#F2B705", "#ECEBE6", "#1C1F24"),
                 _pal("Navy & racing red", "#12263A", "#F2F4F6", "#E5484D", "#EEF1F4", "#12263A"),
                 _pal("Steel & orange", "#2E3440", "#ECEFF4", "#F28F3B", "#ECEFF4", "#2E3440")],
    "tags": ["#autorepair", "#mechanic", "#carcare", "#autoshop", "#carmaintenance", "#oilchange", "#brakes", "#tires"],
    "city_tag": "AutoRepair",
    "cta": ["Book a service: {phone}", "Book online at {site}", "Call {phone} or book at {site}."],
    "times": {0: "07:45", 1: "12:00", 2: "07:45", 3: "12:00", 4: "07:45", 5: "09:00"},
    "times_note": "Mon, Wed, Fri 7:45 am (the commute), Tue, Thu noon, Sat 9 am",
    "services": [
        ("Brake *check*", "Squeaks, grinding or a soft pedal? Brakes are not something to wait on. We check them fast.", ""),
        ("Oil *change*", "Fresh oil, a quick look over the car, and you are back on the road.", ""),
        ("Check engine *light*", "We read the code, find the real cause, and explain it in plain English.", ""),
        ("Tires & *alignment*", "Even wear, straight steering, better mileage. Ask us to check yours.", "Do you do tires/alignment?"),
        ("Battery *test*", "A quick test tells you if your battery will make it through the season.", ""),
        ("Pre-trip *inspection*", "Road trip coming? We check the essentials before you go.", ""),
    ],
    "tips": {
        "any": [
            ("Check your *oil*", "Check the dipstick once a month with the engine off and cool. Low oil is an easy fix, and an expensive one to ignore."),
            ("Learn your *warning lights*", "Red on the dash usually means stop soon; yellow means get it checked. Your manual shows each one."),
            ("Air filter *check*", "A dirty engine air filter can hurt performance. It is a quick, cheap part to check at your next service."),
            ("Easy on the *brakes*", "Riding the brakes downhill overheats them. Use a lower gear on long hills and they will last longer."),
            ("The penny *test*", "Put a penny in the tread, Lincoln's head down. If you can see all of his head, it is time for new tires."),
            ("Smooth is *cheaper*", "Gentle starts and stops save fuel and wear on your brakes and tires."),
            ("Keep your *records*", "Save every service receipt. A full history helps us find problems faster and helps when you sell."),
            ("Strange smell? *Stop in*", "Sweet, burning or fuel smells each point to a different problem. Do not drive around with it."),
            ("Check tire *pressure*", "Check it once a month with the tires cold. The right number is on the sticker inside the driver's door."),
            ("Do not ignore the *light*", "A check engine light can be small or serious. Get the code read before a small problem grows."),
            ("Wipers every *year*", "Streaky wipers? Replace the blades about once a year. Clear glass is safe glass."),
            ("Follow the *manual*", "Your owner's manual has the right oil-change interval for your car. Ask us if you are not sure."),
            ("Listen to your *brakes*", "Squealing or grinding means it is time for a check. Do not wait for it to get worse."),
            ("Rotate your *tires*", "Rotating tires every 5,000-7,500 miles helps them wear evenly and last longer."),
            ("Watch the *gauges*", "If the temperature gauge climbs, pull over safely and let the engine cool before you check anything."),
            ("Keep it *clean*", "Washing off road salt and grime protects your paint and the underside of your car."),
        ],
        "winter": [("Cold kills *batteries*", "Cold weather is hard on batteries. A quick test now beats a dead car on a freezing morning.", {"cold", "mild", "rainy"}),
                   ("Half a tank in *winter*", "Keep at least half a tank in {weather}. It is your safety margin if you get stuck.", {"cold", "mild"}),
                   ("Pressure drops in the *cold*", "Tire pressure drops when it gets cold. Check it after the first cold mornings.")],
        "spring": [("After-winter *check*", "Potholes and salt are hard on cars. A spring check catches alignment and brake issues early.")],
        "summer": [("Keep it *cool*", "Summer heat is hard on engines. Check coolant and get the A/C looked at before a long drive.")],
        "fall": [("Winter is *coming*", "Fall is the time for a battery test, new wipers and a tire check before the cold arrives.")],
    },
    "checklists": [("Winter car *checklist*", ["Battery test", "Tire pressure & tread", "New wiper blades", "Emergency kit in the trunk"], {10, 11, 12, 1, 2}, {"cold", "mild", "rainy"}),
                   ("Road trip *checklist*", ["Tire pressure & tread", "Oil level", "Lights & wipers", "Coolant & A/C"], {4, 5, 6, 7, 8, 11, 12})],
    "offers": [
        ("Free battery *test*", "Stop by and we will test your battery while you wait. No appointment needed.", "Do you offer a free battery test?", {10, 11, 12, 1, 2}),
        ("Holiday road trip *check*", "Driving to family this month? Book a quick pre-trip check before you go.", "", {11, 12}),
        ("Second opinion? *Sure*", "Got a big quote somewhere else? Bring it in and we will take an honest look.", "Do you do second opinions?", None),
        ("Ask about our *warranty*", "Ask us how our repairs are covered, so you know exactly where you stand before we start.", "Do you offer a warranty on repairs? How long?", None),
        ("Send us a *friend*", "Know someone looking for an honest mechanic? Send them our way, and ask us about our thank-you for referrals.", "Do you want a referral thank-you? What is it?", None),
        ("Gift a *service*", "An oil change gift card is the gift that keeps the car running.", "Do you sell gift cards?", {11, 12}),
    ],
    "bts": [
        ("In the *bay*", "Lifts up, tools out. This is where the work happens at {name}.", "a car up on the lift"),
        ("Meet your *mechanic*", "The person who works on your car. Ask them anything, they love explaining.", "a portrait of a mechanic"),
        ("The *diagnosis*", "We do not guess. We test, find the cause, and show you what we found.", "a tech with the scan tool"),
    ],
    "faq": [
        ("How often do I need an *oil change*?", "It depends on your car and oil. Check your owner's manual, or ask us and we will look it up."),
        ("Can I *wait*?", "For quick jobs, yes. Call ahead and we will tell you how long it should take."),
        ("Why is my car *pulling*?", "Usually alignment or tire pressure. Bring it in and we will check both."),
    ],
    "engage": [("First car *story*", "What was your first car? Best (or worst) answer wins our respect.")],
    "booking": [("Book before the *trip*", "Driving for the holidays? Book your check now, our calendar fills up before every big weekend.", {11, 12}),
                ("That noise? *Book it*", "If your car is making a new noise, book a check this week before it gets worse.")],
    "season": {
        "winter": [("Winter-ready *car*?", "With {weather} here, batteries, tires and wipers get tested hard. Let us check them before they fail.", {"cold", "mild", "rainy"}),
                   ("Road trip *season*", "Mild winter days in {city} mean road trips and visits. Get your car checked before you go.", {"warm"})],
        "spring": [("Spring *tune-up*", "After winter, your car deserves a check-up. Brakes, alignment and a fresh oil change.")],
        "summer": [("Summer *road trips*", "Summer heat and long drives: get your car checked before you go.")],
        "fall": [("Fall *car care*", "Shorter days, cooler mornings. Time for lights, wipers and a battery test.")],
    },
    "holiday": {
        "car_care_spring": [("Car Care *Month*", "April is National Car Care Month. The perfect excuse for a full check-up before summer driving.")],
        "car_care_fall": [("Fall Car Care *Month*", "October is Fall Car Care Month. Get your car ready for winter now.")],
        "dst_end": [("Darker *drives*", "The clocks went back and the evening drive just got darker. Check your headlights and clean the lenses.")],
        "july4": [("Road trip *ready*", "Happy 4th of July! Driving to the fireworks? Check tire pressure before you go.")],
        "christmas_eve": [("Safe travels *home*", "Driving to family for the holidays? Check your tires, wipers and lights before you go. Safe travels!")],
    },
}

PACKS["gym"] = {
    "label": "Gym & Fitness", "pro": "coach", "pros": "coaches", "visit": "session", "aliases": ["gym", "fitness", "crossfit", "studio", "yoga", "pilates", "personal trainer", "personal training", "boxing", "martial arts", "training"],
    "icons": ["dumbbell", "kettlebell", "pulse"], "motif": "bars", "upper": True,
    "fonts": {"display": "bebas", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Iron & ember", "#17181B", "#F4F4F0", "#E8613C", "#EDEDE8", "#17181B"),
                 _pal("Royal & amber", "#24164A", "#F6F2FF", "#F5B83D", "#F1EEF8", "#24164A"),
                 _pal("Ink & coral", "#102A43", "#F0F4F8", "#FF7A63", "#F0F4F8", "#102A43")],
    "tags": ["#fitness", "#gym", "#workout", "#fitnessmotivation", "#strengthtraining", "#healthylifestyle", "#fitfam", "#training"],
    "city_tag": "Fitness",
    "cta": ["Try a class: {site}", "Questions? Call {phone}.", "Stop by or book at {site}."],
    "times": {0: "06:00", 1: "17:00", 2: "06:00", 3: "17:00", 4: "06:00", 5: "08:00", 6: "17:00"},
    "times_note": "Mon, Wed, Fri 6 am (before the workout), Tue, Thu 5 pm (after work), Sat 8 am, Sun 5 pm (planning the week)",
    "services": [
        ("Personal *training*", "A plan built for you, a coach in your corner, and real progress.", "Do you offer personal training?"),
        ("Group *classes*", "More energy, more fun, and someone to notice when you skip. Find your class.", ""),
        ("Strength *basics*", "New to lifting? Learn the basics safely with a coach.", ""),
        ("Open *gym*", "Train your way on your schedule. All the equipment you need.", ""),
        ("Mobility & *stretch*", "Move better, recover faster, feel younger. Mobility work pays off everywhere.", ""),
        ("Beginner *friendly*", "Everyone starts somewhere. We will meet you where you are.", ""),
    ],
    "tips": {
        "any": [
            ("Form *first*", "Learn each movement with a light weight first. Good form keeps you safe and makes you stronger faster."),
            ("Breathe *out* on the push", "Exhale as you push or pull, inhale as you lower. Do not hold your breath."),
            ("Set a *4-week* goal", "Pick one goal you can hit in four weeks. Small wins keep you coming back."),
            ("Mix it *up*", "Strength, cardio and mobility all matter. A little of each makes a balanced week."),
            ("Cool down *too*", "Five easy minutes of movement and stretching after training helps you feel better tomorrow."),
            ("Book it like a *meeting*", "Put your workouts in your calendar. It is harder to skip an appointment with yourself."),
            ("Walk on rest *days*", "Easy walking on rest days helps you recover and keeps your energy up."),
            ("Ask a *coach*", "Not sure how a machine works or how to do a lift? Ask us. That is what we are here for."),
            ("Warm up *first*", "Five to ten minutes of easy movement before you train gets your body ready and helps you lift better."),
            ("Consistency beats *intensity*", "Three steady workouts a week beat one brutal one. Show up, again and again."),
            ("Sleep is *training*", "Most adults need 7-9 hours. Sleep is when your body recovers and gets stronger."),
            ("Drink *water*", "Bring a bottle and sip it during your session. Thirst slows you down."),
            ("Add a little *more*", "Small steps: one more rep, a little more weight. That is how strength is built."),
            ("Walk after *meals*", "A 10-minute walk after eating is one of the easiest healthy habits there is."),
            ("Log your *workouts*", "Write down what you did. Seeing progress on paper keeps you going."),
            ("Rest days *count*", "Muscles grow when you rest. Take your rest days seriously."),
        ],
        "winter": [("Short on *time*?", "Busy season? A 20-minute workout still counts. Something always beats nothing."),
                   ("Warm up *longer*", "With {weather} outside, give yourself a few extra minutes to warm up.", {"cold", "mild", "rainy"})],
        "spring": [("Spring *reset*", "New season, fresh start. Pick one goal for the next 8 weeks and write it down.")],
        "summer": [("Train in the *heat*?", "In hot weather, train early, drink more water, and ease off on the hottest days.")],
        "fall": [("Back to *routine*", "Fall is the best time to lock in a routine before the holidays. Pick your days now.")],
    },
    "checklists": [("Gym bag *checklist*", ["Water bottle", "Towel", "Good shoes", "A plan for today"])],
    "offers": [
        ("Gift a *membership*", "Give someone the gift of feeling great. Ask us about gift memberships.", "Do you sell gift memberships/cards?", {11, 12}),
        ("Bring a *friend*", "Train with a friend this week. Bring them along and show them around.", "Can members bring a friend for free?", None),
        ("Try a *class*", "Curious? Come try a class and see if it is for you.", "Do you offer a free/intro class?", None),
        ("Start before *January*", "Beat the New Year rush. Start now and you will be a regular by January.", "", {11, 12}),
    ],
    "bts": [
        ("Before the *6 am*", "Lights on, music up, coffee brewing. The gym before everyone shows up.", "the empty gym early morning"),
        ("Coach's *corner*", "Planning this week's workouts. A lot of thought goes into every session.", "a coach writing the workout on the board"),
        ("The *community*", "The best part of {name}? The people. Tag your training partner.", "a group photo after a class (with OK)"),
    ],
    "faq": [
        ("I am *out of shape*. Can I join?", "Yes. Every workout can be scaled. Our coaches will meet you where you are."),
        ("How often should I *train*?", "Two to four times a week is a great start. Consistency matters more than the number."),
        ("What should I *eat*?", "Simple: protein, vegetables, water, and not too much junk. Ask a coach for the basics."),
    ],
    "engage": [("Leg day or *arm day*?", "Be honest: which day do you secretly skip? Tell us below.")],
    "booking": [("Beat the *January rush*", "New Year, new members. Start now and own your spot before January.", {11, 12}),
                ("This is your *sign*", "You have been thinking about it. Book your first session this week.")],
    "season": {
        "winter": [("Stay strong this *winter*", "Cold outside, warm gym inside. Keep your routine going this {season} in {city}.", {"cold", "mild", "rainy"}),
                   ("Winter *strong*", "Cooler mornings in {city} are perfect for training. Keep your routine going this {season}.", {"warm"})],
        "spring": [("Spring *into it*", "Longer days, more energy. Now is the time to step it up.")],
        "summer": [("Summer *strong*", "Hot out? Train early, train smart, stay hydrated. See you at {name}.")],
        "fall": [("Fall *focus*", "Back to routine season. Lock in your training days now.")],
    },
    "holiday": {
        "new_year": [("New year, *new goals*", "Happy New Year, {city}! What is your goal for {year}? Tell us and we will help you get there.")],
        "nye": [("Ready for *{next_year}*?", "Tomorrow is day one. Your goals for {next_year} start with your first workout. See you this week!")],
        "fitness_month": [("Fitness & Sports *Month*", "May is National Physical Fitness and Sports Month. Celebrate it the best way: move!")],
        "thanksgiving": [("Earn the *pie*", "Happy Thanksgiving! A quick morning workout and a walk after dinner. Then enjoy every bite.")],
        "christmas_eve": [("Holiday *workout*", "Twenty minutes, no equipment: squats, push-ups, lunges, plank. Merry Christmas from the gym!")],
    },
}

PACKS["dentist"] = {
    "label": "Dental Practice", "pro": "dentist", "pros": "dentists", "visit": "visit", "aliases": ["dentist", "dental", "dental office", "dental practice", "orthodontist", "orthodontics", "dds", "family dentistry"],
    "icons": ["tooth", "sparkle", "toothbrush"], "motif": "bubbles", "upper": False,
    "fonts": {"display": "manrope_x", "accent": "dmserif_i", "body": "manrope", "hand": "caveat"},
    "palettes": [_pal("Fresh teal & mint", "#0B5563", "#F2FBFA", "#86D6CB", "#F2FBFA", "#0B3C45"),
                 _pal("Navy & sky", "#13315C", "#F4F8FC", "#8DBEF2", "#F4F8FC", "#13315C"),
                 _pal("Aqua & coral", "#1D5C63", "#FDF7F2", "#F4A08C", "#FDF7F2", "#1D3F44")],
    "tags": ["#dentist", "#dentalcare", "#smile", "#oralhealth", "#healthysmile", "#familydentist", "#teethcleaning", "#dentalhygiene"],
    "city_tag": "Dentist",
    "cta": ["Book your visit: {site}", "Call {phone} to book.", "Book at {site} or call {phone}."],
    "times": {0: "12:15", 1: "19:00", 2: "12:15", 3: "19:00", 4: "12:15", 6: "19:00"},
    "times_note": "Mon, Wed, Fri 12:15 pm (lunch break), Tue, Thu 7 pm, Sun 7 pm (planning the week)",
    "services": [
        ("Cleaning & *checkup*", "A fresh, clean feeling and a chance to catch small problems before they grow.", ""),
        ("Teeth *whitening*", "A brighter smile, safely, with a dentist who knows your teeth.", "Do you offer whitening?"),
        ("Family *dentistry*", "Kids, parents, grandparents. One friendly office for the whole family.", "Do you see kids?"),
        ("Gentle *care*", "Nervous about the dentist? Tell us. We go at your pace and explain every step.", ""),
        ("Emergency *visits*", "Toothache or a broken tooth? Call us and we will do our best to see you quickly.", "Do you take emergency visits?"),
        ("Night *guards*", "Waking up with a sore jaw? Grinding may be the reason. Ask us about a night guard.", "Do you make night guards?"),
    ],
    "tips": {
        "any": [
            ("Chew *sugar-free*", "Chewing sugar-free gum after meals helps your mouth make saliva, which protects your teeth."),
            ("Rinse after *coffee*", "Love coffee or tea? A sip of water afterward helps limit staining."),
            ("Let your brush *dry*", "Store your toothbrush upright in the open air, not in a closed case where germs grow."),
            ("Electric or *manual*?", "Both work when used well. The best brush is the one you use for two full minutes, twice a day."),
            ("Kids: *pea-sized*", "Ages 3 to 6 need just a pea-sized amount of fluoride toothpaste. Under 3: a smear the size of a grain of rice."),
            ("Teeth are not *tools*", "Opening packages or bottles with your teeth is a fast way to chip one. Grab the scissors instead."),
            ("Bedtime brushing *counts*", "Brushing before bed matters most. Your mouth makes less saliva at night, so leftover food sits longer."),
            ("Listen to your *gums*", "Healthy gums are pink and firm. Red, puffy or bleeding gums are worth a checkup."),
            ("Two minutes, *twice* a day", "Brush for two full minutes, twice a day, with a fluoride toothpaste."),
            ("Floss *daily*", "Brushing misses the spaces between teeth. Floss or use interdental brushes once a day."),
            ("New brush every *3 months*", "Replace your toothbrush every three to four months, or sooner if the bristles fray."),
            ("Wait to *brush*", "After acidic foods or drinks, wait a little before brushing so you do not scrub softened enamel."),
            ("Water *wins*", "Sipping water through the day rinses away sugar and acid. Your teeth love it."),
            ("Soft bristles, *gentle* hands", "Hard scrubbing can wear gums. A soft brush and gentle circles do the job."),
            ("Do not skip *checkups*", "Regular visits catch small problems early, when they are easier to fix."),
            ("Tongue counts *too*", "Brush or scrape your tongue. It is home to a lot of the bacteria behind bad breath."),
        ],
        "winter": [("Holiday *sweets*?", "Enjoy them, then drink some water. Sweets with a meal are easier on teeth than snacking all day.", {11, 12, 1}),
                   ("Sensitive to the *cold*?", "Cold air or drinks making your teeth zing? Tell us at your next visit. Sensitivity has causes we can look at.")],
        "spring": [("Spring *clean* your smile", "New season, new toothbrush. Toss the old one and start fresh.")],
        "summer": [("Sports? Wear a *guard*", "Playing contact sports this summer? A mouthguard protects teeth. Ask us about one.")],
        "fall": [("Halloween *plan*", "Candy is coming. Let kids enjoy it with meals, then brush, rather than snacking all evening.", {10}),
                 ("Fall *routine*", "Back-to-school and busy schedules: keep a toothbrush at work or in your bag for after lunch.")],
    },
    "checklists": [("Healthy smile *checklist*", ["Brush 2 minutes, twice a day", "Floss once a day", "New brush every 3 months", "Checkups on schedule"])],
    "offers": [
        ("Use your *benefits*", "Many dental plans reset on January 1. If you have unused benefits, book before the year ends.", "", {10, 11, 12}),
        ("New patients *welcome*", "Looking for a dentist in {city}? We are welcoming new patients. Call to book your first visit.", "Are you taking new patients?", None),
        ("Refer a *friend*", "The best compliment we get is a referral. Thank you for sending friends and family our way.", "", None),
        ("Gift a *smile*", "Ask us about whitening gift certificates.", "Do you offer whitening gift certificates?", None),
    ],
    "bts": [
        ("Behind the *mask*", "Meet the team that takes care of your smile. Next visit, say hi!", "the team in the office (with their OK)"),
        ("Clean, calm, *ready*", "Every room is cleaned and set up before you arrive. Your comfort matters to us.", "a treatment room, clean and bright"),
        ("A day at the *office*", "Lots of smiles, a few nervous patients made comfortable, and good conversations. That is a good day.", "the front desk team"),
    ],
    "faq": [
        ("How often should I *visit*?", "Many people come every six months, but your dentist will tell you what is right for you."),
        ("Is whitening *safe*?", "Professional whitening done under a dentist's care is safe for most people. Ask us if it is right for you."),
        ("Why do my gums *bleed*?", "Bleeding when you brush can be a sign of gum inflammation. Keep brushing gently and book a checkup."),
    ],
    "engage": [("Floss *before* or *after*?", "Do you floss before or after brushing? Tell us below. (The best answer: whenever you will actually do it!)")],
    "booking": [("Book *before* the year ends", "Our end-of-year calendar is filling up. Call now to grab a spot.", {10, 11, 12}),
                ("Time for your *checkup*?", "If it has been six months or more, it is time. Book today.")],
    "season": {
        "winter": [("Smile through the *season*", "Holiday treats and a busy calendar: keep your smile healthy this {season}.", {11, 12}),
                   ("Winter *smile* care", "Hot and cold drinks can make sensitive teeth zing. Tell us at your next visit in {city}.", {1, 2})],
        "spring": [("Spring *smile* check", "Fresh season, fresh start. Is your checkup on the calendar?")],
        "summer": [("Summer *smile*", "Vacations, BBQs and lots of photos. Make sure your smile is ready.")],
        "fall": [("Back to *routine*", "Fall is a great time to get everyone's checkups on the calendar.")],
    },
    "holiday": {
        "dental_month": [("Kids' dental health *month*", "February is National Children's Dental Health Month! Healthy habits start young: brush together tonight.")],
        "hygiene_month": [("Dental hygiene *month*", "October is National Dental Hygiene Month. Brush, floss, rinse, chew (sugar-free gum). Simple daily habits.")],
        "halloween": [("Happy *Halloween*", "Enjoy the candy! Tip: chocolate rinses away more easily than sticky or sour candy. Then brush before bed.")],
        "back_to_school": [("Back-to-school *checkups*", "New school year, healthy smile. Book the kids' checkups before the calendar fills up.")],
        "christmas_eve": [("Sweet *season*", "Enjoy every treat, then a glass of water. Merry Christmas from our office to yours!")],
    },
}

TRADES = list(PACKS)
# the trade observances that only exist in a trade pack (their key -> the pack that defines the words)
OBSERVANCE_TRADES = {"dental_month": "dentist", "hygiene_month": "dentist", "world_plumbing": "plumber", "lawn_month": "landscaper",
                     "car_care_spring": "auto", "car_care_fall": "auto", "fitness_month": "gym"}


def trade_of(text: str) -> str:
    """the pack for a client's `trade` field ('Plumbing & HVAC' -> 'plumber'); ValueError when no pack fits"""
    t = (text or "").strip().lower()
    if t in PACKS:
        return t
    best = ""
    for key, pack in PACKS.items():
        for a in pack["aliases"]:
            if t == a:
                return key
            if re.search(rf"\b{re.escape(a)}\b", t) and len(a) > len(best):
                best, hit = a, key
    if best:
        return hit
    raise ValueError(f"no content pack for trade {text!r}: use one of {', '.join(TRADES)}")


def is_hvac(text: str) -> bool:
    t = " " + (text or "").lower() + " "
    return any(w in t for w in PACKS["plumber"]["hvac_words"])


def is_plumbing(text: str) -> bool:
    t = (text or "").lower()
    return "plumb" in t or "drain" in t or "water" in t or t.strip() in ("plumber", "plumbing")
