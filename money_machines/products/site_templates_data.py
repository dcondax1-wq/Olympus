"""The five one-page website templates: the looks (colours checked for contrast), the special section each one has and the sample
text of a made-up business for each (phone numbers in the 555-01xx range kept for fiction, addresses invented, example.com email).
Used by build_site_templates.py, which injects all of it into the Site Editor."""
from __future__ import annotations

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def week(mon_fri: str, sat: str = "", sun: str = "", mon: str | None = None) -> list:
    h = [mon_fri] * 5 + [sat, sun]
    if mon is not None:
        h[0] = mon
    return [{"day": d, "hours": x} for d, x in zip(DAYS, h)]


def with_day(h: list, i: int, hours: str) -> list:
    h[i] = dict(h[i], hours=hours)
    return h


THEMES = {
    "trades": {
        "label": "Trades", "short": "Trades", "folder": "1-trades", "special": "steps", "schema": "HomeAndConstructionBusiness",
        "for": "plumbers, electricians, heating and cooling, roofers, painters, handymen", "mood": "navy and safety orange: a slanted hero, a big phone number, numbered steps",
        "palette": {"bg": "#f5f7fa", "surface": "#ffffff", "ink": "#0f2238", "muted": "#4a5a6c", "accent": "#c2410c", "accent_ink": "#ffffff", "accent_text": "#b83d0b",
                    "line": "#d9e0e8", "hero_bg": "#0f2a44", "hero_ink": "#ffffff", "hero_muted": "#c9d6e3"},
        "art": ["#f97316", "#ffffff", "#5b8db8", "#163a5c"],
        "display": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",
        "body": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif", "radius": "10px"},
    "garden": {
        "label": "Home and Garden", "short": "Home & garden", "folder": "2-home-garden", "special": "seasons", "schema": "LocalBusiness",
        "for": "landscapers, lawn care, gardeners, cleaners, pet groomers", "mood": "sage and forest: rolling hills, leaf-shaped cards, four seasons",
        "palette": {"bg": "#f6f8f1", "surface": "#ffffff", "ink": "#1c3324", "muted": "#4d6353", "accent": "#2e6b34", "accent_ink": "#ffffff", "accent_text": "#2a6230",
                    "line": "#dbe5d3", "hero_bg": "#e6efd9", "hero_ink": "#1c3324", "hero_muted": "#4d6353"},
        "art": ["#2e6b34", "#8fbf6a", "#f2c14e", "#c9dcb4"],
        "display": "Optima,Candara,'Segoe UI','Avenir Next',-apple-system,Roboto,Arial,sans-serif",
        "body": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif", "radius": "24px 6px"},
    "cafe": {
        "label": "Cafe", "short": "Cafe", "folder": "3-cafe", "special": "menu", "schema": "CafeOrCoffeeShop",
        "for": "cafes, bakeries, small restaurants, food trucks", "mood": "cream and tomato: a scalloped edge, serif headings, a menu board",
        "palette": {"bg": "#fff8ec", "surface": "#fffdf8", "ink": "#2a1a12", "muted": "#6b5446", "accent": "#a8261d", "accent_ink": "#ffffff", "accent_text": "#9c231b",
                    "line": "#ecdcc4", "hero_bg": "#fbecd3", "hero_ink": "#2a1a12", "hero_muted": "#6b5446"},
        "art": ["#a8261d", "#f3c06b", "#5d7a3a", "#2a1a12"],
        "display": "'Iowan Old Style','Palatino Linotype',Palatino,Georgia,serif",
        "body": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif", "radius": "14px"},
    "salon": {
        "label": "Salon", "short": "Salon", "folder": "4-salon", "special": "prices", "schema": "HairSalon",
        "for": "hair salons, nail and beauty salons, lash and brow studios", "mood": "blush and plum: arches, petals, italic serif, a price list",
        "palette": {"bg": "#fcf7f3", "surface": "#ffffff", "ink": "#2b1b24", "muted": "#6b5560", "accent": "#a63d62", "accent_ink": "#ffffff", "accent_text": "#9a3459",
                    "line": "#ead8d6", "hero_bg": "#f6e7e3", "hero_ink": "#2b1b24", "hero_muted": "#6b5560"},
        "art": ["#a63d62", "#f2c6c9", "#d98c8f", "#7a2c4a"],
        "display": "'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif",
        "body": "'Avenir Next',Avenir,-apple-system,'Segoe UI',Roboto,Arial,sans-serif", "radius": "22px"},
    "barber": {
        "label": "Barber", "short": "Barber", "folder": "5-barber", "special": "prices", "schema": "HairSalon",
        "for": "barbers, tattoo studios, grooming", "mood": "brass and ink: a dark shop, poster capitals, a barber-pole stripe, a price board",
        "palette": {"bg": "#141210", "surface": "#1f1b17", "ink": "#f4ede1", "muted": "#c7bba7", "accent": "#d4ad4b", "accent_ink": "#141210", "accent_text": "#e0bd62",
                    "line": "#3a332a", "hero_bg": "#141210", "hero_ink": "#f4ede1", "hero_muted": "#c7bba7"},
        "art": ["#d4ad4b", "#f4ede1", "#8c2f2f", "#2b2620"],
        "display": "'Didot','Bodoni 72','Bodoni MT','Playfair Display',Georgia,'Times New Roman',serif",
        "body": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif", "radius": "2px"},
}
ORDER = ["trades", "garden", "cafe", "salon", "barber"]
CONTRAST_PAIRS = [["ink", "bg"], ["muted", "bg"], ["ink", "surface"], ["muted", "surface"], ["accent_ink", "accent"], ["accent_text", "bg"],
                  ["accent_text", "surface"], ["hero_ink", "hero_bg"], ["hero_muted", "hero_bg"]]

SCHEMA_TYPES = [["LocalBusiness", "Local business (general)"], ["HomeAndConstructionBusiness", "Home services"], ["Plumber", "Plumber"],
                ["Electrician", "Electrician"], ["HVACBusiness", "Heating and cooling"], ["RoofingContractor", "Roofer"], ["HousePainter", "Painter"],
                ["Locksmith", "Locksmith"], ["GeneralContractor", "Builder"], ["MovingCompany", "Movers"], ["ProfessionalService", "Professional service"],
                ["CafeOrCoffeeShop", "Cafe"], ["Bakery", "Bakery"], ["Restaurant", "Restaurant"], ["HairSalon", "Hair salon or barber"],
                ["BeautySalon", "Beauty salon"], ["NailSalon", "Nail salon"], ["DaySpa", "Spa"], ["HealthAndBeautyBusiness", "Health and beauty"],
                ["AutoRepair", "Auto repair"], ["Store", "Shop"]]

COMMON = {"since": "", "region": "", "postcode": "", "mapLink": "", "bookLink": "", "reviewsConfirmed": False, "reviews": [], "accent": "",
          "photos": {"hero": "", "about": "", "gallery": []}, "seoTitle": "", "seoDescription": "", "footerNote": "", "steps": [], "seasons": [], "menu": [],
          "prices": [], "pricesNote": "", "textOk": False, "street": ""}


def sample(**kw) -> dict:
    d = dict(COMMON)
    d.update(kw)
    return d


SAMPLES = {
    "trades": sample(
        template="trades", name="Riverton Plumbing & Heating", trade="Plumbing and heating", town="Riverton", area="Riverton and about 20 miles around",
        since="2011", schema="Plumber", phone="(555) 010-0142", textOk=True, email="hello@example.com",
        headline="Plumbing and heating repairs, done right the first time",
        intro="Leaks, water heaters, boilers and blocked drains. We answer the phone, give you a clear price before we start, and leave your home as tidy as we found it.",
        cta="quote", ctaLabel="Get a free quote", badges=["Clear prices up front", "Tidy, careful work", "Local and easy to reach"],
        servicesTitle="Services", servicesIntro="From a dripping tap to a new heating system: one call, one clear price.",
        services=[
            {"title": "Leaks and repairs", "text": "Dripping taps, burst pipes, running toilets and leaking valves, found and fixed.", "price": "", "icon": "drop"},
            {"title": "Water heaters", "text": "Repairs, replacements and new tank or tankless heaters sized for your home.", "price": "", "icon": "flame"},
            {"title": "Drains", "text": "Slow or blocked sinks, showers and main drains cleared, with a camera check when needed.", "price": "", "icon": "pipe"},
            {"title": "Heating service", "text": "Yearly boiler and furnace checks, so the heat works on the first cold night.", "price": "", "icon": "gauge"},
            {"title": "Bathrooms and kitchens", "text": "New fixtures, showers, sinks and appliance hook-ups, fitted neatly.", "price": "", "icon": "home"},
            {"title": "Urgent call-outs", "text": "Water where it should not be? Call: we will tell you honestly how soon we can come.", "price": "", "icon": "bolt"}],
        steps=[{"title": "Call or send a message", "text": "Tell us what is going on. A photo helps."},
               {"title": "Get a clear price", "text": "We look at the job and give you the price before any work starts."},
               {"title": "We fix it and tidy up", "text": "The work is done, the area is cleaned, and we explain what we did."}],
        why=[{"title": "Clear prices", "text": "You know the price before we start. No surprises on the bill."},
             {"title": "On time", "text": "We give you a time window and text you when we are on the way."},
             {"title": "Careful in your home", "text": "Shoe covers, drop sheets and a tidy finish on every visit."},
             {"title": "Local", "text": "We live and work here, so we are never far away."}],
        aboutTitle="A local plumbing and heating team",
        about=("We started Riverton Plumbing & Heating to be the plumber we would want to call ourselves: one who answers, explains the options in "
               "plain words and does tidy work at a fair price.\n\nToday we are a small team looking after homes and small businesses across Riverton "
               "and the towns around it."),
        owner="Sam Ortega, owner", hours=week("7:00 am - 6:00 pm", "8:00 am - 1:00 pm", ""), hoursNote="Holiday hours are posted here.",
        faq=[{"q": "Do you charge for a quote?", "a": "No. Tell us about the job and we give you a price before we start. For bigger jobs we come and look first."},
             {"q": "Which areas do you cover?", "a": "Riverton and about 20 miles around it. Not sure? Call and ask."},
             {"q": "Can you come today?", "a": "Often, yes. Call in the morning and we will tell you honestly when we can be there."},
             {"q": "How can I pay?", "a": "Card, bank transfer or check. You get a written invoice for every job."}],
        footerNote="Licence and insurance details here (only real ones)"),
    "garden": sample(
        template="garden", name="Greenway Garden Care", trade="Lawn and garden care", town="Maple Falls", area="Maple Falls and the towns nearby",
        schema="LocalBusiness", phone="(555) 010-0175", textOk=True, email="hello@example.com",
        headline="A tidy garden all year, without the weekend work",
        intro="Mowing, hedges, beds and seasonal clean-ups for homes in Maple Falls. Regular visits or one-off jobs, always left neat.",
        cta="quote", ctaLabel="Get a free quote", badges=["Regular or one-off visits", "Green waste taken away", "Friendly local team"],
        servicesTitle="What we do", servicesIntro="Pick one job or a plan for the whole season.",
        services=[
            {"title": "Lawn mowing", "text": "Weekly or every two weeks, edges trimmed and clippings cleared.", "price": "From $40 a visit", "icon": "leaf"},
            {"title": "Hedges and shrubs", "text": "Shaped and trimmed, with all the cuttings taken away.", "price": "", "icon": "tree"},
            {"title": "Seasonal clean-ups", "text": "Leaves, branches and tired beds cleared in spring and fall.", "price": "", "icon": "wind"},
            {"title": "Planting and beds", "text": "New beds, fresh mulch, flowers and shrubs planted with care.", "price": "", "icon": "flower"},
            {"title": "Leaf removal", "text": "Raked, blown and hauled away before winter sets in.", "price": "", "icon": "sun"},
            {"title": "Honest advice", "text": "We tell you what your lawn and plants need, and when.", "price": "", "icon": "chat"}],
        seasons=[{"title": "Spring", "items": "First mow and edging; Bed clean-up and mulch; Aeration and overseeding"},
                 {"title": "Summer", "items": "Regular mowing; Hedge trimming; Weeding the beds"},
                 {"title": "Fall", "items": "Leaf removal; The last mow; Planting bulbs and shrubs"},
                 {"title": "Winter", "items": "Pruning while plants rest; Storm clean-up; Planning next year's garden"}],
        why=[{"title": "We show up", "text": "Your visits are on the calendar, and we tell you before we change one."},
             {"title": "Neat finish", "text": "Paths blown clean and every cutting taken away."},
             {"title": "Clear prices", "text": "A written quote before we start, so you know the cost."},
             {"title": "Local people", "text": "A small team from Maple Falls who care about the street."}],
        aboutTitle="Gardeners from just down the road",
        about=("Greenway started with one mower and a borrowed trailer. We still run it the same way: show up when we say, do careful work, and "
               "leave every garden tidier than we found it.\n\nWe look after lawns and gardens across Maple Falls, from small front yards to big family gardens."),
        owner="Jordan Lee, owner", hours=week("8:00 am - 6:00 pm", "9:00 am - 2:00 pm", ""),
        hoursNote="Garden visits by appointment. We reply to messages within one working day.",
        faq=[{"q": "Do you take one-off jobs?", "a": "Yes. A single clean-up or hedge trim is fine, and so is a regular plan."},
             {"q": "Do I need to be home?", "a": "No. Leave the side gate open and we will text you when we are done."},
             {"q": "What happens if it rains?", "a": "Light rain is fine. In heavy rain we move your visit to the next dry day and let you know."},
             {"q": "Do you take green waste away?", "a": "Yes, every cutting and leaf goes with us. It is included in the price."}]),
    "cafe": sample(
        template="cafe", name="Corner Table Cafe", trade="Coffee, bakery and lunch", town="Oak Hill", street="12 Market Street", schema="CafeOrCoffeeShop",
        phone="(555) 010-0118", email="hello@example.com",
        headline="Good coffee, fresh baking and a table with your name on it",
        intro="A neighbourhood cafe on Market Street. Pastries baked here every morning, simple lunches, and coffee made with care.",
        cta="call", ctaLabel="Call to order ahead", badges=["Baked here every morning", "Vegetarian options daily", "Take away or stay"],
        servicesTitle="At the cafe", servicesIntro="",
        services=[
            {"title": "Eat in", "text": "Cosy tables, water on the side, a quiet corner in the mornings.", "price": "", "icon": "cup"},
            {"title": "Take away", "text": "Coffee and pastries ready in a few minutes.", "price": "", "icon": "bag"},
            {"title": "Catering trays", "text": "Pastries and sandwiches for meetings and parties. Order two days ahead.", "price": "", "icon": "food"},
            {"title": "Cakes to order", "text": "Birthday and celebration cakes. Ask us about flavours.", "price": "", "icon": "cake"},
            {"title": "Fresh bread", "text": "Loaves from our oven, while they last.", "price": "", "icon": "bread"},
            {"title": "Gift cards", "text": "Any amount, at the counter.", "price": "", "icon": "gift"}],
        menu=[{"group": "Coffee", "items": [{"name": "Espresso", "price": "$3.00", "desc": ""}, {"name": "Cappuccino", "price": "$4.25", "desc": ""},
                                            {"name": "Latte", "price": "$4.50", "desc": "Oat or almond milk, add $0.75"},
                                            {"name": "Pour-over", "price": "$4.00", "desc": "Ask us what is on today"},
                                            {"name": "Hot chocolate", "price": "$3.75", "desc": ""}]},
              {"group": "Bakery", "items": [{"name": "Butter croissant", "price": "$3.50", "desc": ""}, {"name": "Cinnamon roll", "price": "$4.25", "desc": ""},
                                            {"name": "Banana bread", "price": "$3.75", "desc": "Toasted, with butter"},
                                            {"name": "Muffin of the season", "price": "$3.50", "desc": ""}, {"name": "Cookie of the day", "price": "$2.50", "desc": ""}]},
              {"group": "Lunch", "items": [{"name": "Soup of the day", "price": "$7.50", "desc": "With fresh bread"},
                                           {"name": "Grilled cheese and tomato soup", "price": "$10.50", "desc": ""},
                                           {"name": "Garden salad", "price": "$9.50", "desc": "Add chicken, $3.00"},
                                           {"name": "Turkey and avocado sandwich", "price": "$11.00", "desc": "On our own bread"}]}],
        why=[{"title": "Baked here", "text": "Our pastries come out of the oven every morning."},
             {"title": "Friendly faces", "text": "We learn your name and your usual order."},
             {"title": "Something for everyone", "text": "Vegetarian options every day. Ask about allergens."},
             {"title": "Stay a while", "text": "Plenty of plugs and a quiet corner for working."}],
        aboutTitle="A table for everyone on Market Street",
        about=("Corner Table started with a simple idea: a place where neighbours can sit down, take their time and eat something made by hand.\n\n"
               "We bake every morning, buy from local suppliers where we can, and keep the menu short so everything on it is good."),
        owner="Ana and Luis, owners", hours=week("7:00 am - 4:00 pm", "8:00 am - 3:00 pm", "8:00 am - 1:00 pm"), hoursNote="Kitchen closes 30 minutes before we do.",
        faq=[{"q": "Can I work from the cafe?", "a": "Yes. Mornings are quiet and there are plugs by the window tables."},
             {"q": "Do you have dairy-free options?", "a": "Yes: oat and almond milk for coffee, and the soup of the day is often dairy-free. Just ask."},
             {"q": "Can I order a cake?", "a": "Yes. Call or come in at least three days ahead and we will plan it with you."},
             {"q": "Do you cater?", "a": "Pastry and sandwich trays for 6 to 40 people. Order two days ahead."}]),
    "salon": sample(
        template="salon", name="Willow & Rose Hair Studio", trade="Hair salon", town="Linden", street="48 Elm Avenue", schema="HairSalon",
        phone="(555) 010-0163", textOk=True, email="hello@example.com",
        headline="Cuts, colour and care in a calm little studio",
        intro="Unhurried appointments, honest advice and hair that suits the way you live. Book a cut, a colour or a free chat about what you want.",
        cta="call", ctaLabel="Call or text to book", badges=["Unhurried appointments", "Price confirmed before we start", "Late opening on Thursdays"],
        servicesTitle="Services", servicesIntro="Every appointment starts with a short chat about what you want.",
        services=[
            {"title": "Cuts and styling", "text": "Precision cuts and easy styles you can do at home.", "price": "", "icon": "scissors"},
            {"title": "Colour", "text": "All-over colour, roots and glosses, matched to your skin tone.", "price": "", "icon": "brush"},
            {"title": "Highlights and balayage", "text": "Soft, natural brightness that grows out gently.", "price": "", "icon": "sparkle"},
            {"title": "Treatments", "text": "Deep conditioning for dry, coloured or tired hair.", "price": "", "icon": "drop"},
            {"title": "Events and bridal", "text": "Updos and styling for the days that matter.", "price": "", "icon": "flower"},
            {"title": "Gift cards", "text": "For a birthday, a thank you or just because.", "price": "", "icon": "gift"}],
        prices=[{"name": "Cut and style", "price": "from $55", "note": "Includes wash and blow-dry"}, {"name": "Men's cut", "price": "from $30", "note": ""},
                {"name": "Children's cut (under 12)", "price": "from $22", "note": ""}, {"name": "Blow-dry", "price": "$40", "note": ""},
                {"name": "All-over colour", "price": "from $90", "note": ""}, {"name": "Roots touch-up", "price": "from $70", "note": ""},
                {"name": "Highlights", "price": "from $120", "note": ""}, {"name": "Balayage", "price": "from $150", "note": "Includes toner"},
                {"name": "Gloss or toner", "price": "$35", "note": ""}, {"name": "Treatment", "price": "$25", "note": ""},
                {"name": "Updo or event style", "price": "from $65", "note": ""}, {"name": "Bridal", "price": "ask us", "note": "Trial appointment included"}],
        pricesNote="Prices depend on hair length and thickness. We always confirm the price before we start.",
        why=[{"title": "Time for you", "text": "No rushing between clients: your appointment is yours."},
             {"title": "Honest advice", "text": "We tell you what will work for your hair, and what will not."},
             {"title": "Gentle on your hair", "text": "Careful colour work and a patch test before any new colour."},
             {"title": "Easy booking", "text": "Call or text and we will find a time that suits you."}],
        aboutTitle="A small studio with three chairs",
        about=("Willow & Rose is a small, light studio on Elm Avenue. We keep it to three chairs so every appointment is calm and nobody is rushed.\n\n"
               "Come for a cut, stay for a cup of tea, and leave with hair you can look after yourself."),
        owner="Rosa, founder", hours=with_day(week("9:00 am - 6:00 pm", "8:00 am - 4:00 pm", "", mon=""), 3, "9:00 am - 8:00 pm"),
        hoursNote="Please give 24 hours' notice to change an appointment.",
        faq=[{"q": "How do I book?", "a": "Call or text us. Tell us what you would like and we will suggest a time."},
             {"q": "Do you do a patch test for colour?", "a": "Yes, at least 48 hours before your first colour appointment with us."},
             {"q": "What if I need to cancel?", "a": "Please tell us 24 hours ahead so someone else can have the slot."},
             {"q": "Do you sell gift cards?", "a": "Yes, for any amount or any service, at the studio or by phone."}]),
    "barber": sample(
        template="barber", name="Old Town Barbers", trade="Barbershop", town="Fairview", street="7 Station Road", since="2009", schema="HairSalon",
        phone="(555) 010-0190", email="hello@example.com",
        headline="Sharp cuts, hot towels and no rush",
        intro="A proper barbershop on Station Road. Classic cuts, fades and beard work by barbers who take their time.",
        cta="call", ctaLabel="Call to book", badges=["Walk-ins welcome", "Appointments too", "Kids' cuts"],
        servicesTitle="The chair", servicesIntro="",
        services=[
            {"title": "Classic cuts", "text": "Scissor or clipper, finished with a neck shave.", "price": "", "icon": "scissors"},
            {"title": "Skin fades", "text": "Clean, even fades, from low to high.", "price": "", "icon": "comb"},
            {"title": "Beard trims", "text": "Shaped, lined up and conditioned.", "price": "", "icon": "razor"},
            {"title": "Hot towel shaves", "text": "The full ritual: hot towels, lather, straight razor.", "price": "", "icon": "flame"},
            {"title": "Kids' cuts", "text": "Patient barbers for first cuts and fidgety ones.", "price": "", "icon": "smile"},
            {"title": "Line-ups", "text": "A quick clean-up between cuts.", "price": "", "icon": "sparkle"}],
        prices=[{"name": "Classic cut", "price": "$28", "note": ""}, {"name": "Skin fade", "price": "$32", "note": ""}, {"name": "Scissor cut", "price": "$34", "note": ""},
                {"name": "Beard trim", "price": "$15", "note": ""}, {"name": "Cut and beard", "price": "$40", "note": ""},
                {"name": "Hot towel shave", "price": "$35", "note": ""}, {"name": "Kids (under 12)", "price": "$20", "note": ""},
                {"name": "Line-up", "price": "$12", "note": ""}, {"name": "Seniors (65 and over)", "price": "$22", "note": ""}],
        pricesNote="Card or cash. Walk-ins welcome; appointments are seen first.",
        why=[{"title": "Consistent cuts", "text": "The same careful cut every visit."},
             {"title": "No rush", "text": "We take the time the cut needs."},
             {"title": "Fair prices", "text": "Clear prices on the wall and on this page."},
             {"title": "Walk in or book", "text": "Drop by, or call and we will hold a chair."}],
        aboutTitle="Cutting hair on Station Road",
        about=("Old Town Barbers is a four-chair shop with a simple idea: good cuts, a warm welcome and a bit of conversation if you want it.\n\n"
               "Bring a photo of what you like, or ask us what would suit you."),
        owner="Marcus, head barber", hours=week("9:00 am - 7:00 pm", "8:00 am - 5:00 pm", "10:00 am - 2:00 pm", mon=""),
        hoursNote="Last walk-in 30 minutes before closing.",
        faq=[{"q": "Do I need an appointment?", "a": "No, walk-ins are welcome. Appointments are seen first, so call if you are short on time."},
             {"q": "How long does a cut take?", "a": "About 30 minutes for a cut, 45 for a cut and beard."},
             {"q": "Do you cut kids' hair?", "a": "Yes, from first cuts up. Weekday afternoons are quieter for little ones."},
             {"q": "Can I bring a photo?", "a": "Please do. It is the quickest way to show us what you want."}]),
}
