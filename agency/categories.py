"""The trades the lead finder looks for: OpenStreetMap tags -> category, demo-site template, how much a site is worth to them.

value (1-10) = how much a website is typically worth to that trade (ticket size x how often people search for it):
roofers / plumbers / HVAC sell $500-$15,000 jobs to people who search first, so they rank above a cafe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    key: str
    label: str            # singular, plain words ("Plumber")
    plural: str           # "plumbers"
    filters: tuple        # ((osm key, exact value or "~regex"), ...): any one matches
    template: str         # demo-site template id (agency/templates/themes.json)
    value: int            # 1-10
    schema: str           # schema.org type for the demo site's JSON-LD
    words: tuple = field(default_factory=tuple)   # what customers type into Google ("barber near me")


CATEGORIES = (
    Category("restaurant", "Restaurant", "restaurants", (("amenity", "restaurant"),), "table", 5, "Restaurant", ("restaurant", "food")),
    Category("cafe", "Cafe", "cafes", (("amenity", "cafe"),), "table", 4, "CafeOrCoffeeShop", ("coffee", "cafe")),
    Category("bakery", "Bakery", "bakeries", (("shop", "bakery"), ("shop", "pastry")), "table", 4, "Bakery", ("bakery",)),
    Category("barber", "Barbershop", "barbershops", (("shop", "hairdresser"),), "studio", 6, "HairSalon", ("barber", "haircut")),
    Category("salon", "Hair salon", "hair salons", (("shop", "hairdresser"),), "bloom", 6, "HairSalon", ("hair salon", "haircut")),
    Category("beauty", "Beauty salon", "beauty and nail salons", (("shop", "beauty"), ("shop", "nails"), ("shop", "cosmetics_service")), "bloom", 6, "BeautySalon", ("nail salon", "beauty salon")),
    Category("plumber", "Plumber", "plumbers", (("craft", "plumber"), ("shop", "plumber")), "pro", 10, "Plumber", ("plumber",)),
    Category("hvac", "Heating and cooling", "heating and cooling companies", (("craft", "hvac"), ("craft", "heating_engineer"), ("shop", "hvac")), "pro", 10, "HVACBusiness", ("ac repair", "furnace repair")),
    Category("electrician", "Electrician", "electricians", (("craft", "electrician"),), "pro", 9, "Electrician", ("electrician",)),
    Category("roofer", "Roofer", "roofers", (("craft", "roofer"),), "pro", 10, "RoofingContractor", ("roofer", "roof repair")),
    Category("painter", "Painter", "painters", (("craft", "painter"),), "pro", 8, "HousePainter", ("house painter",)),
    Category("builder", "Builder and carpenter", "builders and carpenters", (("craft", "carpenter"), ("craft", "builder"), ("craft", "handyman")), "pro", 8, "GeneralContractor", ("contractor", "handyman")),
    Category("locksmith", "Locksmith", "locksmiths", (("shop", "locksmith"), ("craft", "locksmith")), "pro", 7, "Locksmith", ("locksmith",)),
    Category("landscaper", "Landscaper", "landscapers", (("craft", "gardener"), ("craft", "landscaper")), "fresh", 8, "HomeAndConstructionBusiness", ("landscaping", "lawn care")),
    Category("cleaner", "Cleaner", "cleaners", (("shop", "dry_cleaning"), ("craft", "cleaning"), ("office", "cleaning")), "fresh", 5, "DryCleaningOrLaundry", ("dry cleaning", "cleaning service")),
    Category("florist", "Florist", "florists", (("shop", "florist"),), "fresh", 5, "Florist", ("florist", "flowers")),
    Category("pet_grooming", "Pet groomer", "pet groomers", (("shop", "pet_grooming"),), "fresh", 5, "LocalBusiness", ("dog grooming",)),
    Category("auto_repair", "Auto repair", "auto repair shops", (("shop", "car_repair"), ("shop", "tyres")), "garage", 9, "AutoRepair", ("auto repair", "mechanic")),
    Category("car_wash", "Car wash", "car washes", (("amenity", "car_wash"),), "garage", 4, "AutoWash", ("car wash",)),
    Category("dentist", "Dentist", "dentists", (("amenity", "dentist"), ("healthcare", "dentist")), "clinic", 9, "Dentist", ("dentist",)),
    Category("chiropractor", "Chiropractor", "chiropractors", (("healthcare:speciality", "~chiropractic"),), "clinic", 8, "MedicalBusiness", ("chiropractor",)),
    Category("physio", "Physical therapist", "physical therapists", (("healthcare", "physiotherapist"),), "clinic", 8, "MedicalBusiness", ("physical therapy",)),
    Category("vet", "Veterinarian", "veterinarians", (("amenity", "veterinary"),), "clinic", 8, "VeterinaryCare", ("vet", "animal hospital")),
    Category("massage", "Massage", "massage studios", (("shop", "massage"),), "clinic", 5, "HealthAndBeautyBusiness", ("massage",)),
    Category("gym", "Gym", "gyms", (("leisure", "fitness_centre"),), "pulse", 6, "ExerciseGym", ("gym", "fitness")),
    Category("tattoo", "Tattoo studio", "tattoo studios", (("shop", "tattoo"),), "studio", 5, "LocalBusiness", ("tattoo",)),
)
BY_KEY = {c.key: c for c in CATEGORIES}
DEFAULT_KEYS = tuple(c.key for c in CATEGORIES)

# Aliases the owner may type: --categories "barbers,hvac,roofing"
ALIASES = {
    "restaurants": "restaurant", "food": "restaurant", "cafes": "cafe", "coffee": "cafe", "bakeries": "bakery",
    "barbers": "barber", "barbershop": "barber", "barbershops": "barber", "salons": "salon", "hair": "salon", "nails": "beauty", "nail": "beauty",
    "plumbers": "plumber", "plumbing": "plumber", "heating": "hvac", "ac": "hvac", "electricians": "electrician", "electrical": "electrician",
    "roofers": "roofer", "roofing": "roofer", "painters": "painter", "carpenter": "builder", "carpenters": "builder", "handyman": "builder",
    "contractor": "builder", "contractors": "builder", "locksmiths": "locksmith", "landscapers": "landscaper", "landscaping": "landscaper",
    "lawn": "landscaper", "gardener": "landscaper", "cleaners": "cleaner", "cleaning": "cleaner", "dry_cleaning": "cleaner", "florists": "florist",
    "grooming": "pet_grooming", "groomer": "pet_grooming", "auto": "auto_repair", "mechanic": "auto_repair", "mechanics": "auto_repair",
    "car_repair": "auto_repair", "carwash": "car_wash", "dentists": "dentist", "dental": "dentist", "chiropractors": "chiropractor",
    "chiro": "chiropractor", "physiotherapist": "physio", "pt": "physio", "vets": "vet", "veterinary": "vet", "gyms": "gym", "fitness": "gym",
    "tattoos": "tattoo",
}

# Franchises and chains: they have a head-office website and never buy one from a local designer.
CHAINS = re.compile(r"\b(great clips|supercuts|sport clips|fantastic sams|smartstyle|cost cutters|floyd'?s 99|regis salon|hair cuttery|"
                    r"jiffy lube|midas|meineke|firestone|pep boys|valvoline|take 5|les schwab|discount tire|big o tires|goodyear|ntb\b|monro|"
                    r"maaco|safelite|christian brothers|grease monkey|planet fitness|anytime fitness|24 hour fitness|orangetheory|gold'?s gym|"
                    r"la fitness|snap fitness|crunch fitness|f45|9round|club pilates|pure barre|aspen dental|western dental|bright now|"
                    r"comfort dental|smile brands|heartland dental|banfield|vca\b|petsmart|petco|starbucks|subway|mcdonald|dunkin|"
                    r"roto-rooter|mr\.? rooter|mister sparky|one hour heating|aire serv|molly maid|merry maids|the joint chiropractic|"
                    r"massage envy|hand & stone|european wax|ulta|sally beauty|tide cleaners|servpro|servicemaster|chem-dry|lawn doctor|"
                    r"trugreen|weed man)\b", re.I)
FRANCHISE_NOTE = re.compile(r"franchise|chain", re.I)


def resolve(names) -> tuple:
    """'barbers, hvac,roofing' or a list -> category keys (unknown words are refused with a plain message)."""
    if not names:
        return DEFAULT_KEYS
    if isinstance(names, str):
        names = [n for n in re.split(r"[,\s]+", names) if n]
    out, bad = [], []
    for n in names:
        k = n.strip().lower().replace("-", "_")
        k = ALIASES.get(k, k)
        if k in BY_KEY:
            if k not in out:
                out.append(k)
        else:
            bad.append(n)
    if bad:
        raise ValueError(f"unknown categories: {', '.join(bad)} (known: {', '.join(DEFAULT_KEYS)})")
    return tuple(out)


def _match(tags: dict, osm_key: str, want: str) -> bool:
    v = tags.get(osm_key)
    if v is None:
        return False
    if want.startswith("~"):
        return re.search(want[1:], v, re.I) is not None
    return v == want


def is_barber(tags: dict) -> bool:
    """OSM: shop=hairdresser + hairdresser=barber, or the name says barber, or men only."""
    if tags.get("hairdresser") in ("barber", "barber;hairdresser") or re.search(r"barber", tags.get("name", ""), re.I):
        return True
    return tags.get("male") == "yes" and tags.get("female") in ("no", None) and tags.get("unisex") != "yes"


def classify(tags: dict, wanted=DEFAULT_KEYS):
    """The category key of an OSM element, or None. Barber vs hair salon is decided by is_barber()."""
    wanted = set(wanted)
    for c in CATEGORIES:
        if c.key not in wanted and not (c.key == "barber" and "salon" in wanted) and not (c.key == "salon" and "barber" in wanted):
            continue
        if not any(_match(tags, k, v) for k, v in c.filters):
            continue
        if c.key in ("barber", "salon"):
            k = "barber" if is_barber(tags) else "salon"
            return k if k in wanted else None
        return c.key
    return None


def is_chain(tags: dict) -> bool:
    """Brand tags (from the Name Suggestion Index), a franchise note, or a known chain name."""
    if any(tags.get(k) for k in ("brand", "brand:wikidata", "brand:wikipedia", "operator:wikidata")):
        return True
    if FRANCHISE_NOTE.search(tags.get("note", "")):
        return True
    return bool(CHAINS.search(tags.get("name", "")))


def overpass_filters(keys) -> list:
    """The distinct (osm key, value) filters of these categories, for one Overpass union query."""
    seen, out = set(), []
    for k in keys:
        for f in BY_KEY[k].filters:
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out
