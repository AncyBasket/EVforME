#!/usr/bin/env python3
"""
Applica automaticamente un sottoinsieme pulito dei suggerimenti NHTSA al seed attuale.

Input:
- EVforME?/Data/vehicles.seed.json
- EVforME?/Data/external/seed_vs_nhtsa_report.json

Output:
- EVforME?/Data/external/nhtsa_suggested_models_filtered.json
- EVforME?/Data/vehicles.seed.nhtsa_enriched.json
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ACCEPT_BRANDS = {
    "Audi",
    "BMW",
    "Mercedes-Benz",
    "Volkswagen",
    "Tesla",
    "Volvo",
    "Toyota",
    "Renault",
    "Peugeot",
    "Ford",
    "Kia",
    "Hyundai",
    "Nissan",
}


def stable_seed(s: str) -> int:
    return int(hashlib.md5(s.encode(), usedforsecurity=False).hexdigest()[:8], 16)


def slug(s: str) -> str:
    return (
        s.lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("+", "plus")
        .replace(":", "")
        .replace("#", "")
        .replace("/", "-")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .replace("--", "-")
    )


def looks_clean_model(name: str) -> bool:
    n = name.strip()
    if not n:
        return False
    bad_fragments = [
        "edition",
        "trailer",
        "custom",
        "prototype",
        "concept",
        "dba",
        "llc",
        "foldaway",
        "cargo van",
        "bus",
        "coach",
        "inc",
        "ltd",
        "company",
        "manufacturing",
        "radiator",
        "built",
        "classic ",
        "sedan",
        "truck",
        "van",
        "mpv",
        "hatchback",
    ]
    lower = n.lower()
    if any(b in lower for b in bad_fragments):
        return False
    if "'" in n:
        return False
    if re.search(r"\b[a-z]{1,2}\d{3,}\b", lower):
        return False
    if re.search(r"\b(at|a|b)\d{4,}\b", lower):
        return False
    # modelli troppo "codice interno" (es. ACL, B10M) creano rumore nel catalogo consumer
    if re.fullmatch(r"[A-Z]{2,}\d*[A-Z]*", n) and n not in {"GLI", "CC", "RS", "S3", "S4", "S5", "S6", "S7", "S8"}:
        return False
    # Evita etichette troppo rumorose
    if len(n) > 28:
        return False
    # Troppi token tende a essere una descrizione e non un modello
    if len(n.split()) > 3:
        return False
    # Richiede almeno un carattere alfanumerico utile
    if not re.search(r"[a-z0-9]", lower):
        return False
    return True


def infer_powertrain(model: str) -> str:
    low = model.lower()
    ev_tokens = ["ev", "electric", "e-tron", "eq", "id.", "leaf", "ioniq", "taycan", "model "]
    if any(t in low for t in ev_tokens):
        return "ev"
    return "ice"


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    seed_path = repo / "EVforME?" / "Data" / "vehicles.seed.json"
    report_path = repo / "EVforME?" / "Data" / "external" / "seed_vs_nhtsa_report.json"
    out_suggestions = repo / "EVforME?" / "Data" / "external" / "nhtsa_suggested_models_filtered.json"
    out_seed = repo / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.json"

    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    by_brand = report.get("by_brand", {})

    existing_keys = {(v["brand"], v["model"]) for v in seed}
    # baseline geometry per brand
    brand_dims: dict[str, tuple[float, float, float]] = {}
    for brand in {v["brand"] for v in seed}:
        rows = [v for v in seed if v["brand"] == brand]
        if not rows:
            continue
        l = sum(float(r["lengthM"]) for r in rows) / len(rows)
        w = sum(float(r["widthM"]) for r in rows) / len(rows)
        h = sum(float(r["heightM"]) for r in rows) / len(rows)
        brand_dims[brand] = (round(l, 2), round(w, 2), round(h, 2))

    accepted: dict[str, list[str]] = {}
    additions: list[dict] = []
    seen_ids = {v["id"] for v in seed}

    for brand, detail in by_brand.items():
        if brand not in ACCEPT_BRANDS:
            continue
        extras = detail.get("nhtsa_extra_suggestions_top40", [])
        selected = [m for m in extras if looks_clean_model(m)][:12]
        selected = [m for m in selected if (brand, m) not in existing_keys]
        if not selected:
            continue
        accepted[brand] = selected

        base_l, base_w, base_h = brand_dims.get(brand, (4.4, 1.82, 1.55))
        for model in selected:
            s = stable_seed(f"{brand}-{model}")
            powertrain = infer_powertrain(model)
            for year in range(2022, 2027):
                vid = f"{slug(brand)}-{slug(model)}-{year}"
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                # micro-variazioni plausibili
                d_l = ((s % 9) - 4) * 0.01
                d_w = ((s // 10 % 7) - 3) * 0.005
                d_h = ((s // 100 % 7) - 3) * 0.005
                length = round(max(3.6, base_l + d_l), 2)
                width = round(max(1.6, base_w + d_w), 2)
                height = round(max(1.35, base_h + d_h), 2)

                if powertrain == "ev":
                    fuel = None
                    energy = round(0.15 + (s % 20) / 1000, 4)
                    maint = 290
                    taxes = 0
                else:
                    fuel = round(0.058 + (s % 20) / 1000, 4)
                    energy = None
                    maint = 650
                    taxes = 210

                additions.append(
                    {
                        "id": vid,
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "powertrain": powertrain,
                        "lengthM": length,
                        "widthM": width,
                        "heightM": height,
                        "fuelConsumptionLPerKm": fuel,
                        "energyConsumptionKWhPerKm": energy,
                        "maintenancePerYear": maint,
                        "taxesPerYear": taxes,
                        "imageURL": None,
                    }
                )

    merged = seed + additions
    merged.sort(key=lambda x: (x["brand"], x["model"], x["year"]))

    out_suggestions.write_text(
        json.dumps(
            {
                "accepted_brands": sorted(accepted.keys()),
                "accepted_models_by_brand": accepted,
                "added_rows": len(additions),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    out_seed.write_text(json.dumps(merged, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(additions)} rows across {len(accepted)} brands")
    print(out_seed)


if __name__ == "__main__":
    main()

