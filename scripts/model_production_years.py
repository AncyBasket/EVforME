#!/usr/bin/env python3
"""
Finestre di produzione plausibili (anno modello UE) per marca+modello.

Usato da:
- generate_eu_vehicle_catalog.py (non inventare anni pre-lancio)
- prune_impossible_model_years.py (ripulisci seed)
- validate_catalog_quality.py (gate)

Anni = model year tipici mercato UE, non immatricolazioni giorno-per-giorno.
Se un modello esisteva prima del 2005, il catalogo parte da 2005 (floor app).
"""

from __future__ import annotations

import re
from typing import Optional

# Floor / ceiling del catalogo app
CATALOG_YEAR_MIN = 2005
CATALOG_YEAR_MAX = 2026

# (first_inclusive, last_inclusive)
MODEL_PRODUCTION_YEARS: dict[tuple[str, str], tuple[int, int]] = {}


def _add(brand: str, rows: list[tuple[str, int, int]]) -> None:
    for model, first, last in rows:
        MODEL_PRODUCTION_YEARS[(brand, model)] = (first, last)


# --- Fiat / Alfa / Lancia-ish ---
_add(
    "Fiat",
    [
        ("500", 2007, 2026),
        ("Panda", 2005, 2026),
        ("Punto", 2005, 2018),
        ("Tipo", 2015, 2026),
        ("Bravo", 2007, 2014),
        ("500X", 2014, 2026),
        ("500L", 2012, 2022),
        ("Doblo", 2005, 2026),
        ("Qubo", 2008, 2019),
        ("Tipo Cross", 2020, 2026),
        ("500e", 2020, 2026),
        ("600e", 2023, 2026),
    ],
)
_add(
    "Alfa Romeo",
    [
        ("MiTo", 2008, 2018),
        ("Giulietta", 2010, 2020),
        ("Giulia", 2016, 2026),
        ("Stelvio", 2017, 2026),
        ("Tonale", 2022, 2026),
        ("159", 2005, 2011),
        ("Brera", 2005, 2010),
        ("147", 2005, 2010),
    ],
)

# --- VW Group ---
_add(
    "Volkswagen",
    [
        ("up!", 2011, 2023),
        ("Polo", 2005, 2026),
        ("Golf", 2005, 2026),
        ("Passat", 2005, 2026),
        ("T-Roc", 2017, 2026),
        ("Tiguan", 2007, 2026),
        ("Touareg", 2005, 2026),
        ("Touran", 2005, 2026),
        ("Arteon", 2017, 2026),
        ("Taigo", 2021, 2026),
        ("T-Cross", 2018, 2026),
        ("e-up!", 2013, 2023),
        ("e-Golf", 2014, 2020),
        ("ID.3", 2020, 2026),
        ("ID.4", 2020, 2026),
        ("ID.5", 2021, 2026),
        ("ID.7", 2023, 2026),
        ("ID. Buzz", 2022, 2026),
        ("Golf Alltrack", 2015, 2019),
        ("Golf GTI", 2005, 2026),
        ("Golf GTE", 2014, 2026),
        ("Passat GTE", 2015, 2026),
        ("Tiguan eHybrid", 2020, 2026),
        ("Touareg R eHybrid", 2020, 2026),
        ("Arteon Shooting Brake eHybrid", 2020, 2026),
    ],
)
_add(
    "Audi",
    [
        ("A1", 2010, 2026),
        ("A3", 2005, 2026),
        ("A4", 2005, 2026),
        ("A5", 2007, 2026),
        ("A6", 2005, 2026),
        ("Q2", 2016, 2026),
        ("Q3", 2011, 2026),
        ("Q5", 2008, 2026),
        ("Q7", 2005, 2026),
        ("TT", 2005, 2023),
        ("Q4 e-tron", 2021, 2026),
        ("Q6 e-tron", 2024, 2026),
        ("Q8 e-tron", 2018, 2026),  # e-tron → Q8 e-tron lineage
        ("e-tron GT", 2021, 2026),
    ],
)
_add(
    "Skoda",
    [
        ("Fabia", 2005, 2026),
        ("Scala", 2019, 2026),
        ("Octavia", 2005, 2026),
        ("Superb", 2005, 2026),
        ("Kamiq", 2019, 2026),
        ("Karoq", 2017, 2026),
        ("Kodiaq", 2016, 2026),
        ("Yeti", 2009, 2017),
        ("Rapid", 2012, 2019),
        ("Citigo", 2011, 2020),
        ("Citigo-e iV", 2019, 2021),
        ("Enyaq", 2020, 2026),
        ("Elroq", 2024, 2026),
        ("Octavia iV", 2020, 2026),
        ("Superb iV", 2019, 2026),
    ],
)
_add(
    "SEAT",
    [
        ("Ibiza", 2005, 2026),
        ("Leon", 2005, 2026),
        ("Toledo", 2012, 2019),
        ("Altea", 2005, 2015),
        ("Arona", 2017, 2026),
        ("Ateca", 2016, 2026),
        ("Tarraco", 2018, 2026),
        ("Mii", 2011, 2021),
        ("Exeo", 2008, 2013),
        ("Cordoba", 2005, 2009),
        ("Mii electric", 2019, 2021),
        ("Leon e-Hybrid", 2020, 2026),
    ],
)
_add(
    "Cupra",
    [
        ("Formentor", 2020, 2026),
        ("Leon", 2020, 2026),
        ("Ateca", 2018, 2026),
        ("Born", 2021, 2026),
        ("Tavascan", 2024, 2026),
        ("Formentor e-Hybrid", 2020, 2026),
        ("Leon e-Hybrid", 2020, 2026),
        ("Tavascan VZ e-Hybrid", 2024, 2026),
    ],
)

# --- German premium ---
_add(
    "BMW",
    [
        ("1 Series", 2005, 2026),
        ("2 Series", 2013, 2026),
        ("3 Series", 2005, 2026),
        ("4 Series", 2013, 2026),
        ("5 Series", 2005, 2026),
        ("X1", 2009, 2026),
        ("X2", 2017, 2026),
        ("X3", 2005, 2026),
        ("X5", 2005, 2026),
        ("Z4", 2005, 2026),
        ("i3", 2013, 2022),
        ("iX1", 2022, 2026),
        ("i4", 2021, 2026),
        ("i5", 2023, 2026),
        ("i7", 2022, 2026),
        ("iX3", 2020, 2026),
        ("iX", 2021, 2026),
    ],
)
_add(
    "MINI",
    [
        ("Hatch", 2005, 2026),
        ("Clubman", 2007, 2026),
        ("Countryman", 2010, 2026),
        ("Convertible", 2005, 2026),
        ("Coupe", 2011, 2015),
        ("Roadster", 2011, 2015),
        ("Electric Hatch", 2019, 2026),
    ],
)
_add(
    "Mercedes-Benz",
    [
        ("A-Class", 2005, 2026),
        ("B-Class", 2005, 2026),
        ("C-Class", 2005, 2026),
        ("E-Class", 2005, 2026),
        ("CLA", 2013, 2026),
        ("GLA", 2013, 2026),
        ("GLB", 2019, 2026),
        ("GLC", 2015, 2026),
        ("GLE", 2015, 2026),
        ("S-Class", 2005, 2026),
        ("EQA", 2021, 2026),
        ("EQB", 2021, 2026),
        ("EQE", 2022, 2026),
        ("EQS", 2021, 2026),
        ("EQV", 2020, 2026),
        ("G 580 EQ", 2024, 2026),
    ],
)
_add(
    "Smart",
    [
        ("Fortwo", 2005, 2026),
        ("Forfour", 2014, 2021),
        ("#1", 2022, 2026),
        ("#3", 2023, 2026),
    ],
)
_add(
    "Porsche",
    [
        ("911", 2005, 2026),
        ("718", 2016, 2026),
        ("Macan", 2014, 2026),
        ("Cayenne", 2005, 2026),
        ("Panamera", 2009, 2026),
        ("Taycan", 2019, 2026),
        ("Macan Electric", 2024, 2026),
    ],
)

# --- French ---
_add(
    "Renault",
    [
        ("Twingo", 2005, 2026),
        ("Clio", 2005, 2026),
        ("Megane", 2005, 2026),
        ("Captur", 2013, 2026),
        ("Kadjar", 2015, 2022),
        ("Austral", 2022, 2026),
        ("Scenic", 2005, 2026),
        ("Koleos", 2008, 2026),
        ("Arkana", 2021, 2026),
        ("Espace", 2005, 2026),
        ("Zoe", 2012, 2024),
        ("Megane E-Tech", 2021, 2026),
        ("Scenic E-Tech", 2023, 2026),
        ("5 E-Tech", 2024, 2026),
        ("Twingo Electric", 2020, 2024),
        ("Rafale E-Tech", 2024, 2026),
    ],
)
_add(
    "Dacia",
    [
        ("Logan", 2005, 2026),
        ("Sandero", 2008, 2026),
        ("Duster", 2010, 2026),
        ("Lodgy", 2012, 2022),
        ("Dokker", 2012, 2021),
        ("Jogger", 2021, 2026),
        ("Spring", 2021, 2026),
    ],
)
_add(
    "Peugeot",
    [
        ("107", 2005, 2014),
        ("108", 2014, 2021),
        ("207", 2006, 2014),
        ("208", 2012, 2026),
        ("307", 2005, 2008),
        ("308", 2007, 2026),
        ("2008", 2013, 2026),
        ("3008", 2008, 2026),
        ("5008", 2009, 2026),
        ("508", 2010, 2026),
        ("408", 2022, 2026),
        ("e-208", 2019, 2026),
        ("e-2008", 2019, 2026),
        ("e-308", 2022, 2026),
        ("e-3008", 2023, 2026),
        ("e-5008", 2024, 2026),
        ("308 Hybrid", 2021, 2026),
        ("3008 Hybrid", 2019, 2026),
        ("5008 Hybrid", 2020, 2026),
        ("508 Hybrid", 2019, 2026),
        ("408 Hybrid", 2023, 2026),
    ],
)
_add(
    "Citroen",
    [
        ("C1", 2005, 2022),
        ("C3", 2005, 2026),
        ("C4", 2005, 2026),
        ("C5", 2005, 2026),
        ("C3 Aircross", 2017, 2026),
        ("C5 Aircross", 2018, 2026),
        ("Berlingo", 2005, 2026),
        ("C4 Cactus", 2014, 2020),
        ("C-Elysee", 2012, 2020),
        ("C8", 2005, 2014),
        ("e-C4", 2020, 2026),
        ("e-C3", 2023, 2026),
        ("e-Berlingo", 2021, 2026),
        ("C5 Aircross Hybrid", 2020, 2026),
    ],
)
_add(
    "DS",
    [
        ("DS 3", 2009, 2026),
        ("DS 4", 2011, 2026),
        ("DS 7", 2017, 2026),
        ("DS 9", 2020, 2026),
        ("DS 4 E-Tense", 2021, 2026),
        ("DS 7 E-Tense", 2019, 2026),
        ("DS 9 E-Tense", 2020, 2026),
    ],
)
_add(
    "Opel",
    [
        ("Agila", 2005, 2014),
        ("Corsa", 2005, 2026),
        ("Astra", 2005, 2026),
        ("Insignia", 2008, 2022),
        ("Mokka", 2012, 2026),
        ("Crossland", 2017, 2026),
        ("Grandland", 2017, 2026),
        ("Zafira", 2005, 2019),
        ("Vectra", 2005, 2008),
        ("Meriva", 2005, 2017),
        ("Corsa Electric", 2019, 2026),
        ("Mokka Electric", 2020, 2026),
        ("Astra Electric", 2023, 2026),
        ("Grandland Electric", 2024, 2026),
        ("Frontera Electric", 2024, 2026),
        ("Astra Hybrid", 2021, 2026),
        ("Grandland Hybrid", 2019, 2026),
    ],
)

# --- Others EU volume ---
_add(
    "Volvo",
    [
        ("S40", 2005, 2012),
        ("S60", 2005, 2026),
        ("S80", 2005, 2016),
        ("V40", 2012, 2019),
        ("V60", 2010, 2026),
        ("V90", 2016, 2026),
        ("XC40", 2017, 2026),
        ("XC60", 2008, 2026),
        ("XC90", 2005, 2026),
        ("C30", 2006, 2013),
        ("EX30", 2023, 2026),
        ("EX40", 2024, 2026),
        ("EC40", 2022, 2026),
        ("EX90", 2024, 2026),
        ("XC40 Recharge", 2020, 2026),
        ("C40 Recharge", 2021, 2026),
    ],
)
_add(
    "Ford",
    [
        ("Ka", 2005, 2021),
        ("Fiesta", 2005, 2023),
        ("Focus", 2005, 2026),
        ("Mondeo", 2005, 2022),
        ("Puma", 2019, 2026),
        ("Kuga", 2008, 2026),
        ("S-Max", 2006, 2023),
        ("Galaxy", 2005, 2023),
        ("Mustang", 2015, 2026),
        ("Tourneo Connect", 2005, 2026),
        ("Mustang Mach-E", 2020, 2026),
        ("Explorer EV", 2024, 2026),
        ("Capri EV", 2024, 2026),
        ("Puma Gen-E", 2024, 2026),
        ("Kuga PHEV", 2020, 2026),
    ],
)
_add(
    "Jeep",
    [
        ("Renegade", 2014, 2026),
        ("Compass", 2006, 2026),
        ("Cherokee", 2005, 2023),
        ("Grand Cherokee", 2005, 2026),
        ("Wrangler", 2005, 2026),
        ("Avenger", 2023, 2026),
        ("Avenger Electric", 2023, 2026),
        ("Wagoneer S", 2024, 2026),
    ],
)
_add(
    "Toyota",
    [
        ("Aygo", 2005, 2021),
        ("Yaris", 2005, 2026),
        ("Corolla", 2005, 2026),
        ("Auris", 2006, 2018),
        ("Prius", 2005, 2026),
        ("C-HR", 2016, 2026),
        ("RAV4", 2005, 2026),
        ("Land Cruiser", 2005, 2026),
        ("Proace City", 2019, 2026),
        ("bZ4X", 2022, 2026),
        ("Proace Electric", 2020, 2026),
        ("Prius Plug-in", 2012, 2026),
        ("Prius Plug-in Hybrid", 2012, 2026),
        ("Prius PHEV", 2017, 2026),
        ("Prius PHEV SE", 2023, 2026),
        ("Prius Prime PHEV", 2017, 2026),
        ("RAV4 PHEV", 2020, 2026),
        ("RAV4 Plug-in", 2020, 2026),
        ("C-HR Plug-in", 2023, 2026),
    ],
)
_add(
    "Lexus",
    [
        ("CT", 2010, 2022),
        ("IS", 2005, 2026),
        ("ES", 2018, 2026),
        ("NX", 2014, 2026),
        ("RX", 2005, 2026),
        ("UX", 2018, 2026),
        ("LS", 2005, 2026),
        ("GS", 2005, 2020),
        ("UX 300e", 2020, 2026),
        ("RZ", 2022, 2026),
        ("NX 450h+", 2021, 2026),
        ("RX 450h+", 2022, 2026),
    ],
)
_add(
    "Honda",
    [
        ("Jazz", 2005, 2026),
        ("Civic", 2005, 2026),
        ("Accord", 2005, 2015),
        ("CR-V", 2005, 2026),
        ("HR-V", 2015, 2026),
        ("e", 2019, 2023),
        ("e:Ny1", 2023, 2026),
        ("CR-V e:PHEV", 2023, 2026),
    ],
)
_add(
    "Mazda",
    [
        ("Mazda2", 2005, 2026),
        ("Mazda3", 2005, 2026),
        ("Mazda6", 2005, 2026),
        ("CX-3", 2015, 2021),
        ("CX-30", 2019, 2026),
        ("CX-5", 2012, 2026),
        ("CX-60", 2022, 2026),
        ("MX-5", 2005, 2026),
        ("MX-30", 2020, 2026),
        ("6e", 2024, 2026),
        ("CX-60 PHEV", 2022, 2026),
    ],
)
_add(
    "Nissan",
    [
        ("Micra", 2005, 2026),
        ("Note", 2005, 2019),
        ("Juke", 2010, 2026),
        ("Qashqai", 2006, 2026),
        ("X-Trail", 2005, 2026),
        ("Pulsar", 2014, 2018),
        ("Navara", 2005, 2026),
        ("Leaf", 2010, 2026),
        ("Ariya", 2021, 2026),
    ],
)
_add(
    "Suzuki",
    [
        ("Swift", 2005, 2026),
        ("Ignis", 2016, 2026),
        ("Baleno", 2015, 2019),
        ("SX4", 2005, 2014),
        ("S-Cross", 2013, 2026),
        ("Vitara", 2005, 2026),
        ("Jimny", 2005, 2026),
        ("Splash", 2008, 2014),
    ],
)
_add(
    "Mitsubishi",
    [
        ("Colt", 2005, 2012),
        ("Lancer", 2005, 2017),
        ("ASX", 2010, 2026),
        ("Eclipse Cross", 2017, 2026),
        ("Outlander", 2005, 2026),
        ("Space Star", 2012, 2026),
        ("Outlander PHEV", 2013, 2026),
    ],
)
_add(
    "Hyundai",
    [
        ("i10", 2007, 2026),
        ("i20", 2008, 2026),
        ("i30", 2007, 2026),
        ("ix35", 2009, 2015),
        ("Tucson", 2005, 2026),
        ("Santa Fe", 2005, 2026),
        ("Kona", 2017, 2026),
        ("Bayon", 2021, 2026),
        ("Ioniq", 2016, 2022),
        ("Nexo", 2018, 2026),
        ("Ioniq Electric", 2016, 2022),
        ("Kona Electric", 2018, 2026),
        ("Ioniq 5", 2021, 2026),
        ("Ioniq 6", 2022, 2026),
        ("Inster", 2024, 2026),
        ("Ioniq 5 N", 2023, 2026),
        ("Ioniq PHEV", 2017, 2022),
        ("Ioniq Plug-in Hybrid", 2017, 2022),
        ("Tucson PHEV", 2020, 2026),
        ("Santa Fe PHEV", 2020, 2026),
    ],
)
_add(
    "Kia",
    [
        ("Picanto", 2005, 2026),
        ("Rio", 2005, 2026),
        ("Ceed", 2006, 2026),
        ("Proceed", 2018, 2026),
        ("Sportage", 2005, 2026),
        ("Sorento", 2005, 2026),
        ("Stonic", 2017, 2026),
        ("Niro", 2016, 2026),
        ("Optima", 2005, 2020),
        ("Carens", 2005, 2019),
        ("Soul EV", 2014, 2026),
        ("e-Niro", 2018, 2022),
        ("EV3", 2024, 2026),
        ("EV4", 2025, 2026),
        ("EV6", 2021, 2026),
        ("EV9", 2023, 2026),
        ("Niro PHEV", 2017, 2026),
        ("Sportage PHEV", 2021, 2026),
        ("Sorento PHEV", 2020, 2026),
    ],
)
_add(
    "Tesla",
    [
        ("Model S", 2012, 2026),
        ("Model X", 2015, 2026),
        ("Model 3", 2017, 2026),
        ("Model Y", 2020, 2026),
        ("Cybertruck", 2023, 2026),
    ],
)
_add(
    "MG",
    [
        ("MG3", 2011, 2026),
        ("ZS", 2017, 2026),
        ("HS", 2019, 2026),
        ("GS", 2015, 2019),
        ("MG4", 2022, 2026),
        ("MG5", 2020, 2026),
        ("MG ZS EV", 2019, 2026),
        ("Marvel R", 2021, 2026),
        ("EHS", 2020, 2026),
        ("HS Plug-in", 2020, 2026),
    ],
)
_add(
    "BYD",
    [
        ("Dolphin", 2023, 2026),
        ("Atto 3", 2022, 2026),
        ("Seal", 2023, 2026),
        ("Seal U", 2024, 2026),
        ("Tang", 2021, 2026),
        ("Han", 2021, 2026),
    ],
)
_add(
    "Genesis",
    [
        ("G70", 2018, 2026),
        ("G80", 2016, 2026),
        ("GV70", 2020, 2026),
        ("GV80", 2020, 2026),
        ("Electrified G80", 2021, 2026),
        ("GV60", 2021, 2026),
        ("Electrified GV70", 2021, 2026),
    ],
)
_add(
    "Polestar",
    [
        ("2", 2020, 2026),
        ("3", 2023, 2026),
        ("4", 2023, 2026),
    ],
)
_add(
    "Jaguar",
    [
        ("XE", 2014, 2024),
        ("XF", 2007, 2024),
        ("XJ", 2005, 2019),
        ("F-Pace", 2015, 2026),
        ("E-Pace", 2017, 2026),
        ("I-Pace", 2018, 2026),
    ],
)
_add(
    "Land Rover",
    [
        ("Discovery Sport", 2014, 2026),
        ("Range Rover Evoque", 2011, 2026),
        ("Range Rover Sport", 2005, 2026),
        ("Defender", 2019, 2026),
        ("Discovery", 2005, 2026),
        ("Freelander", 2005, 2014),
    ],
)
_add(
    "Subaru",
    [
        ("Impreza", 2005, 2026),
        ("Legacy", 2005, 2020),
        ("Forester", 2005, 2026),
        ("XV", 2011, 2026),
        ("Outback", 2005, 2026),
        ("BRZ", 2012, 2026),
        ("Solterra", 2022, 2026),
    ],
)
_add(
    "Chevrolet",
    [
        ("Spark", 2009, 2022),
        ("Aveo", 2005, 2020),
        ("Cruze", 2008, 2019),
        ("Trax", 2012, 2026),
        ("Orlando", 2010, 2018),
        ("Camaro", 2009, 2024),
        ("Corvette", 2005, 2026),
        ("Bolt EV", 2016, 2023),
        ("Bolt EUV", 2021, 2023),
        ("Equinox EV", 2023, 2026),
    ],
)

# Brand-level floors when model not listed (rare / import)
BRAND_YEAR_FLOOR: dict[str, int] = {
    "Cupra": 2018,
    "Polestar": 2019,
    "NIO": 2021,
    "XPeng": 2021,
    "Lucid": 2021,
    "Rivian": 2022,
    "BYD": 2020,
    "MG": 2011,
}


def _norm_key(brand: str, model: str) -> tuple[str, str]:
    return brand.strip(), model.strip()


def lookup_production_years(brand: str, model: str) -> Optional[tuple[int, int]]:
    """Exact match, then stripped PHEV/EV suffixes, then None."""
    b, m = _norm_key(brand, model)
    if (b, m) in MODEL_PRODUCTION_YEARS:
        return MODEL_PRODUCTION_YEARS[(b, m)]

    # Strip common PHEV/EV suffixes for fallback to base ICE range when present
    cleaned = re.sub(
        r"\s+(PHEV|Plug-in(?: Hybrid)?|e-Hybrid|Hybrid|Electric|Recharge|Prime|TFSI e|4xe|iV)\s*$",
        "",
        m,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned != m and (b, cleaned) in MODEL_PRODUCTION_YEARS:
        first, last = MODEL_PRODUCTION_YEARS[(b, cleaned)]
        # Electrified variants usually arrive later than ICE base
        return (max(first, 2012), last)

    return None


def resolve_year_window(brand: str, model: str, powertrain: str | None = None) -> tuple[int, int]:
    """
    Finestra [first, last] da usare per generazione/prune.
    Se sconosciuto: heuristica conservativa (non 2005–2026 cieco).
    """
    found = lookup_production_years(brand, model)
    if found:
        first, last = found
    else:
        first, last = _heuristic_window(brand, model, powertrain)

    first = max(CATALOG_YEAR_MIN, first)
    last = min(CATALOG_YEAR_MAX, last)
    if last < first:
        last = first
    return first, last


def _heuristic_window(brand: str, model: str, powertrain: str | None) -> tuple[int, int]:
    m = model.lower()
    b = brand.strip()
    floor = BRAND_YEAR_FLOOR.get(b, CATALOG_YEAR_MIN)
    last = CATALOG_YEAR_MAX

    # Keyword floors for modern nameplates
    rules: list[tuple[str, int]] = [
        ("id.", 2020),
        ("id ", 2020),
        ("ioniq 5", 2021),
        ("ioniq 6", 2022),
        ("model y", 2020),
        ("model 3", 2017),
        ("model x", 2015),
        ("model s", 2012),
        ("cybertruck", 2023),
        ("mach-e", 2020),
        ("mach e", 2020),
        ("enyaq", 2020),
        ("born", 2021),
        ("formentor", 2020),
        ("tavascan", 2024),
        ("ateca", 2016 if b != "Cupra" else 2018),
        ("arona", 2017),
        ("tarraco", 2018),
        ("t-roc", 2017),
        ("t-cross", 2018),
        ("taigo", 2021),
        ("arteon", 2017),
        ("500e", 2020),
        ("600e", 2023),
        ("corsa electric", 2019),
        ("e-208", 2019),
        ("e-2008", 2019),
        ("leaf", 2010),
        ("zoe", 2012),
        ("spring", 2021),
        ("bz4x", 2022),
        ("ev6", 2021),
        ("ev9", 2023),
        ("eqa", 2021),
        ("eqb", 2021),
        ("eqe", 2022),
        ("eqs", 2021),
        ("i4", 2021),
        ("i5", 2023),
        ("ix1", 2022),
        ("phev", 2013),
        ("plug-in", 2012),
        ("e-hybrid", 2014),
        ("hybrid", 2010),
    ]
    for needle, y in rules:
        if needle in m:
            floor = max(floor, y)

    if powertrain == "ev":
        floor = max(floor, 2010)
    elif powertrain == "phev":
        floor = max(floor, 2012)

    # Very new-looking alphanumeric EV names → don't backfill to 2005
    if powertrain in {"ev", "phev"} and floor <= CATALOG_YEAR_MIN:
        floor = 2018

    return floor, last


def year_is_plausible(brand: str, model: str, year: int, powertrain: str | None = None) -> bool:
    first, last = resolve_year_window(brand, model, powertrain)
    return first <= year <= last
