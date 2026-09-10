#!/usr/bin/env python3
"""
Genera vehicles.seed.json per il mercato UE nel senso di *disponibilità*:

- Includi marchi (anche extra-UE) che vendono o consegnano auto omologate in UE.
- Escludi marchi/modelli che nel seed rappresentiamo come non offerti nel mercato UE
  (es. solo altri continenti senza percorso di vendita UE).

I valori tecnici sono approssimativi, solo per simulazione nell'app.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eu_vehicle_dimensions_data import MODEL_DIMS, length_segment_for_economics, resolve_dims

# Marche / modelli tipici del mercato europeo (ICE)
ICE_EU: dict[str, list[str]] = {
    "Fiat": ["500", "Panda", "Punto", "Tipo", "Bravo", "500X", "500L", "Doblo", "Qubo", "Tipo Cross"],
    "Alfa Romeo": ["MiTo", "Giulietta", "Giulia", "Stelvio", "Tonale", "159", "Brera", "147"],
    "Volkswagen": ["up!", "Polo", "Golf", "Passat", "T-Roc", "Tiguan", "Touareg", "Touran", "Arteon", "Taigo", "T-Cross"],
    "Audi": ["A1", "A3", "A4", "A5", "A6", "Q2", "Q3", "Q5", "Q7", "TT"],
    "Skoda": ["Fabia", "Scala", "Octavia", "Superb", "Kamiq", "Karoq", "Kodiaq", "Yeti", "Rapid", "Citigo"],
    "SEAT": ["Ibiza", "Leon", "Toledo", "Altea", "Arona", "Ateca", "Tarraco", "Mii", "Exeo", "Cordoba"],
    "Cupra": ["Formentor", "Leon", "Ateca", "Born"],
    "BMW": ["1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "X1", "X2", "X3", "X5", "Z4"],
    "MINI": ["Hatch", "Clubman", "Countryman", "Convertible", "Coupe", "Roadster"],
    "Mercedes-Benz": ["A-Class", "B-Class", "C-Class", "E-Class", "CLA", "GLA", "GLB", "GLC", "GLE", "S-Class"],
    "Smart": ["Fortwo", "Forfour"],
    "Renault": ["Twingo", "Clio", "Megane", "Captur", "Kadjar", "Austral", "Scenic", "Koleos", "Arkana", "Espace"],
    "Dacia": ["Logan", "Sandero", "Duster", "Lodgy", "Dokker", "Jogger"],
    "Peugeot": ["107", "108", "207", "208", "307", "308", "2008", "3008", "5008", "508", "408"],
    "Citroen": ["C1", "C3", "C4", "C5", "C3 Aircross", "C5 Aircross", "Berlingo", "C4 Cactus", "C-Elysee", "C8"],
    "DS": ["DS 3", "DS 4", "DS 7", "DS 9"],
    "Opel": ["Agila", "Corsa", "Astra", "Insignia", "Mokka", "Crossland", "Grandland", "Zafira", "Vectra", "Meriva"],
    "Volvo": ["S40", "S60", "S80", "V40", "V60", "V90", "XC40", "XC60", "XC90", "C30"],
    "Ford": ["Ka", "Fiesta", "Focus", "Mondeo", "Puma", "Kuga", "S-Max", "Galaxy", "Mustang", "Tourneo Connect"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Wrangler", "Avenger"],
    "Toyota": ["Aygo", "Yaris", "Corolla", "Auris", "Prius", "C-HR", "RAV4", "Land Cruiser", "Proace City"],
    "Lexus": ["CT", "IS", "ES", "NX", "RX", "UX", "LS", "GS"],
    "Honda": ["Jazz", "Civic", "Accord", "CR-V", "HR-V"],
    "Mazda": ["Mazda2", "Mazda3", "Mazda6", "CX-3", "CX-30", "CX-5", "CX-60", "MX-5"],
    "Nissan": ["Micra", "Note", "Juke", "Qashqai", "X-Trail", "Pulsar", "Navara"],
    "Suzuki": ["Swift", "Ignis", "Baleno", "SX4", "S-Cross", "Vitara", "Jimny", "Splash"],
    "Mitsubishi": ["Colt", "Lancer", "ASX", "Eclipse Cross", "Outlander", "Space Star"],
    "Hyundai": ["i10", "i20", "i30", "ix35", "Tucson", "Santa Fe", "Kona", "Bayon", "Ioniq", "Nexo"],
    "Kia": ["Picanto", "Rio", "Ceed", "Proceed", "Sportage", "Sorento", "Stonic", "Niro", "Optima", "Carens"],
    "Genesis": ["G70", "G80", "GV70", "GV80"],
    "Subaru": ["Impreza", "Legacy", "Forester", "XV", "Outback", "BRZ"],
    "Jaguar": ["XE", "XF", "XJ", "F-Pace", "E-Pace"],
    "Land Rover": ["Discovery Sport", "Range Rover Evoque", "Range Rover Sport", "Defender", "Discovery", "Freelander"],
    "MG": ["MG3", "ZS", "HS", "GS"],
    # Tesla: solo elettriche (vedi EV_EU); qui non va elencata come ICE (evitava ID duplicati nel seed).
    "Porsche": ["911", "718", "Macan", "Cayenne", "Panamera"],
    # Storico / import ufficiosi UE (non più linea completa ma venduti in Europa)
    "Chevrolet": ["Spark", "Aveo", "Cruze", "Trax", "Orlando", "Camaro", "Corvette"],
}

# EV venduti o in arrivo in UE (no focus USA puro)
EV_EU: dict[str, list[str]] = {
    "Tesla": ["Model S", "Model X", "Model 3", "Model Y", "Cybertruck"],
    "Renault": ["Zoe", "Megane E-Tech", "Scenic E-Tech", "5 E-Tech", "Twingo Electric"],
    "Nissan": ["Leaf", "Ariya"],
    "Peugeot": ["e-208", "e-2008", "e-308", "e-3008", "e-5008"],
    "Citroen": ["e-C4", "e-C3", "e-Berlingo"],
    "Opel": ["Corsa Electric", "Mokka Electric", "Astra Electric", "Grandland Electric", "Frontera Electric"],
    "Fiat": ["500e", "600e"],
    "Volkswagen": ["e-up!", "e-Golf", "ID.3", "ID.4", "ID.5", "ID.7", "ID. Buzz"],
    "Audi": ["Q4 e-tron", "Q6 e-tron", "Q8 e-tron", "e-tron GT"],
    "Skoda": ["Citigo-e iV", "Enyaq", "Elroq"],
    "SEAT": ["Mii electric"],
    "Cupra": ["Born", "Tavascan"],
    "BMW": ["i3", "iX1", "i4", "i5", "i7", "iX3", "iX"],
    "MINI": ["Electric Hatch"],
    "Mercedes-Benz": ["EQA", "EQB", "EQE", "EQS", "EQV", "G 580 EQ"],
    "Smart": ["#1", "#3"],
    "Hyundai": ["Ioniq Electric", "Kona Electric", "Ioniq 5", "Ioniq 6", "Inster"],
    "Kia": ["Soul EV", "e-Niro", "EV3", "EV4", "EV6", "EV9"],
    "Toyota": ["bZ4X", "Proace Electric"],
    "Lexus": ["UX 300e", "RZ"],
    "Honda": ["e", "e:Ny1"],
    "Mazda": ["MX-30", "6e"],
    "Subaru": ["Solterra"],
    "Volvo": ["EX30", "EX40", "EC40", "EX90", "XC40 Recharge", "C40 Recharge"],
    "Polestar": ["2", "3", "4"],
    "Ford": ["Mustang Mach-E", "Explorer EV", "Capri EV", "Puma Gen-E"],
    "Jeep": ["Avenger Electric", "Wagoneer S"],
    "Porsche": ["Taycan", "Macan Electric"],
    "Jaguar": ["I-Pace"],
    "MG": ["MG4", "MG5", "MG ZS EV", "Marvel R"],
    "BYD": ["Dolphin", "Atto 3", "Seal", "Seal U", "Tang", "Han"],
    "Genesis": ["Electrified G80", "GV60", "Electrified GV70"],
    "Dacia": ["Spring"],
    # Marchi con vendita o consegna ufficiale / rete in vari paesi UE
    "NIO": ["ET5", "ET5 Touring", "ET7", "EL6", "EL8"],
    "XPeng": ["P7", "G6", "G9"],
    "Lucid": ["Air", "Gravity"],
    "Rivian": ["R1T", "R1S"],
    "Chevrolet": ["Bolt EV", "Bolt EUV", "Equinox EV"],
}

POPULAR_EU = {
    "Volkswagen", "Fiat", "Renault", "Peugeot", "Opel", "Ford", "Toyota", "BMW", "Mercedes-Benz", "Audi",
    "Skoda", "Hyundai", "Kia", "Nissan", "Tesla", "Dacia", "Citroen", "MG", "BYD", "Volvo",
    "NIO", "XPeng", "Lucid", "Rivian", "Chevrolet",
}


def stable_seed(s: str) -> int:
    return int(hashlib.md5(s.encode(), usedforsecurity=False).hexdigest()[:8], 16)


ICE_CONS_L_PER_KM = {"small": 0.054, "compact": 0.061, "medium": 0.067, "suv": 0.074}
ICE_MAINT = {"small": 500, "compact": 620, "medium": 690, "suv": 780}
ICE_TAX = {"small": 140, "compact": 190, "medium": 220, "suv": 260}

EV_KWH_PER_KM = {"small": 0.142, "compact": 0.164, "medium": 0.176, "suv": 0.192}
EV_MAINT = {"small": 220, "compact": 280, "medium": 310, "suv": 360}


def assert_all_models_have_dims() -> None:
    missing: list[tuple[str, str]] = []
    for brand, models in ICE_EU.items():
        for m in models:
            if (brand, m) not in MODEL_DIMS:
                missing.append((brand, m))
    for brand, models in EV_EU.items():
        for m in models:
            if (brand, m) not in MODEL_DIMS:
                missing.append((brand, m))
    if missing:
        msg = "MODEL_DIMS mancanti:\n" + "\n".join(f"  {b} {m}" for b, m in missing)
        raise SystemExit(msg)


def slug(s: str) -> str:
    return (
        s.lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("+", "plus")
        .replace(":", "")
        .replace("#", "")
    )


def wiki_style_img(brand: str, model: str) -> str:
    q = urllib.parse.quote_plus(f"{brand} {model}")
    return f"https://source.unsplash.com/featured/?{q},car"


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    out_path = repo / "EVforME?" / "Data" / "vehicles.seed.json"

    assert_all_models_have_dims()

    vehicles: list[dict] = []
    seen: set[str] = set()

    # ICE UE: 2005–2026
    for brand, models in ICE_EU.items():
        for model in models:
            seed = stable_seed(f"EU-ICE-{brand}-{model}")
            ref_l, _, _ = resolve_dims(brand, model, 2020)
            seg = length_segment_for_economics(ref_l)
            base_cons = ICE_CONS_L_PER_KM[seg] + (seed % 10) / 1000
            maint = ICE_MAINT[seg] + int((seed % 9) * 7)
            taxes = ICE_TAX[seg] + int((seed % 8) * 6)

            for year in range(2005, 2027):
                vid = f"{slug(brand)}-{slug(model)}-{year}".replace("--", "-")
                if vid in seen:
                    continue
                seen.add(vid)
                age_step = year - 2005
                cons = max(0.044, base_cons - age_step * 0.00032)
                l, w, h = resolve_dims(brand, model, year)
                image = wiki_style_img(brand, model) if (brand in POPULAR_EU and year >= 2015) else None
                vehicles.append(
                    {
                        "id": vid,
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "powertrain": "ice",
                        "lengthM": l,
                        "widthM": w,
                        "heightM": h,
                        "fuelConsumptionLPerKm": round(cons, 4),
                        "energyConsumptionKWhPerKm": None,
                        "maintenancePerYear": round(maint + age_step * 2.0),
                        "taxesPerYear": round(taxes),
                        "imageURL": image,
                    }
                )

    # EV UE
    for brand, models in EV_EU.items():
        for model in models:
            seed = stable_seed(f"EU-EV-{brand}-{model}")
            ref_l, _, _ = resolve_dims(brand, model, 2023)
            seg = length_segment_for_economics(ref_l)
            base_cons = EV_KWH_PER_KM[seg] + (seed % 12) / 1000
            maint = EV_MAINT[seg] + int((seed % 9) * 6)
            launch = 2010 + (seed % 8)
            if any(
                x in model
                for x in [
                    "EV3", "EV4", "Inster", "6e", "Puma Gen-E", "Capri EV", "Explorer EV",
                    "Grandland Electric", "Frontera Electric", "Elroq", "e-3008", "e-5008", "5 E-Tech",
                    "Q6 e-tron", "EX90", "Wagoneer S", "Marvel R", "Equinox EV", "Gravity",
                ]
            ):
                launch = max(2022, launch)
            if brand == "NIO" or brand == "XPeng":
                launch = max(2021, launch)
            if brand == "Lucid":
                launch = max(2022, launch)
            if brand == "Rivian":
                launch = max(2023, launch)
            if brand == "Chevrolet" and "Bolt" in model:
                launch = max(2017, launch)
            if brand == "Tesla":
                launch = max(2012, launch)
            if model == "Cybertruck":
                launch = max(2024, launch)

            for year in range(launch, 2027):
                vid = f"{slug(brand)}-{slug(model)}-{year}".replace("--", "-")
                if vid in seen:
                    continue
                seen.add(vid)
                age_step = year - launch
                cons = max(0.118, base_cons - age_step * 0.00075)
                l, w, h = resolve_dims(brand, model, year)
                image = wiki_style_img(brand, model) if (brand in POPULAR_EU or year >= 2020) else None
                vehicles.append(
                    {
                        "id": vid,
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "powertrain": "ev",
                        "lengthM": l,
                        "widthM": w,
                        "heightM": h,
                        "fuelConsumptionLPerKm": None,
                        "energyConsumptionKWhPerKm": round(cons, 4),
                        "maintenancePerYear": round(maint + age_step * 1.4),
                        "taxesPerYear": 0,
                        "imageURL": image,
                    }
                )

    vehicles.sort(key=lambda x: (x["brand"], x["model"], x["year"]))
    out_path.write_text(json.dumps(vehicles, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    ice = sum(1 for v in vehicles if v["powertrain"] == "ice")
    ev = len(vehicles) - ice
    print(f"Wrote {len(vehicles)} vehicles ({ice} ICE, {ev} EV) to {out_path}")


if __name__ == "__main__":
    main()
