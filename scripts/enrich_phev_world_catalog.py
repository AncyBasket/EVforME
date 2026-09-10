#!/usr/bin/env python3
"""
Popola il catalogo con il massimo set PHEV ottenibile da fonti pubbliche.

Fonti:
1) EPA FuelEconomy.gov vehicles.csv — atvType == "Plug-in Hybrid" (USA, open data)
2) Elenco editoriale EU/CN/JP/KR di nameplate PHEV/REEV noti (fatti pubblici)

Nota: non esiste un dump open “tutte le PHEV del mondo” completo (soprattutto
varianti Cina + allestimenti). Questo script massimizza la copertura nameplate
senza scraping di siti proprietari.
"""

from __future__ import annotations

import csv
import json
import math
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
OUT_EPA = REPO / "EVforME?" / "Data" / "external" / "epa_phev_models.json"
EPA_ZIP_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"
EPA_CACHE = Path("/tmp/vehicles_epa_cache.csv")

# Nameplate PHEV/REEV noti fuori (o oltre) EPA USA — mercato mondo/EU/CN.
# Tuple: brand, model, L, W, H, fuel L/km, energy kWh/km, battery kWh, electric km, CO2 g/km
PHEV_WORLD: list[tuple] = [
    # --- Europa / premium ---
    ("Audi", "A3 TFSI e", 4.34, 1.82, 1.43, 0.014, 0.145, 12.8, 63, 30),
    ("Audi", "A6 TFSI e", 4.94, 1.89, 1.46, 0.016, 0.155, 17.9, 73, 35),
    ("Audi", "A7 TFSI e", 4.97, 1.91, 1.42, 0.016, 0.158, 17.9, 70, 36),
    ("Audi", "A8 TFSI e", 5.17, 1.95, 1.47, 0.018, 0.165, 17.9, 59, 52),
    ("Audi", "Q3 TFSI e", 4.50, 1.86, 1.56, 0.015, 0.150, 13.0, 51, 38),
    ("Audi", "Q5 TFSI e", 4.68, 1.89, 1.66, 0.017, 0.158, 17.9, 62, 36),
    ("Audi", "Q7 TFSI e", 5.07, 1.97, 1.74, 0.020, 0.170, 17.9, 56, 48),
    ("Audi", "Q8 TFSI e", 4.99, 2.00, 1.71, 0.020, 0.172, 17.9, 56, 50),
    ("BMW", "225xe Active Tourer", 4.37, 1.82, 1.56, 0.015, 0.148, 10.0, 55, 40),
    ("BMW", "330e", 4.71, 1.83, 1.44, 0.014, 0.150, 12.0, 62, 36),
    ("BMW", "530e", 4.96, 1.87, 1.48, 0.015, 0.152, 12.0, 61, 38),
    ("BMW", "545e", 4.96, 1.87, 1.48, 0.016, 0.155, 12.0, 57, 42),
    ("BMW", "740e", 5.39, 1.95, 1.48, 0.018, 0.165, 12.0, 54, 48),
    ("BMW", "X1 xDrive25e", 4.50, 1.85, 1.62, 0.015, 0.150, 10.0, 55, 40),
    ("BMW", "X2 xDrive25e", 4.55, 1.85, 1.53, 0.015, 0.150, 10.0, 53, 42),
    ("BMW", "X3 xDrive30e", 4.71, 1.89, 1.68, 0.017, 0.158, 12.0, 50, 45),
    ("BMW", "X5 xDrive50e", 4.94, 2.00, 1.75, 0.016, 0.160, 29.5, 100, 22),
    ("BMW", "XM", 5.11, 2.00, 1.72, 0.022, 0.180, 29.5, 82, 35),
    ("Mercedes-Benz", "A 250 e", 4.45, 1.80, 1.44, 0.014, 0.148, 15.6, 76, 22),
    ("Mercedes-Benz", "B 250 e", 4.42, 1.80, 1.56, 0.014, 0.150, 15.6, 70, 24),
    ("Mercedes-Benz", "C 300 e", 4.75, 1.82, 1.44, 0.014, 0.150, 25.4, 110, 13),
    ("Mercedes-Benz", "C 300 de", 4.75, 1.82, 1.44, 0.013, 0.152, 25.4, 110, 12),
    ("Mercedes-Benz", "E 300 e", 4.95, 1.88, 1.46, 0.015, 0.155, 25.4, 110, 15),
    ("Mercedes-Benz", "E 300 de", 4.95, 1.88, 1.46, 0.014, 0.155, 25.4, 110, 14),
    ("Mercedes-Benz", "S 580 e", 5.18, 1.92, 1.50, 0.017, 0.165, 28.6, 100, 20),
    ("Mercedes-Benz", "CLA 250 e", 4.69, 1.83, 1.44, 0.014, 0.148, 15.6, 72, 24),
    ("Mercedes-Benz", "GLA 250 e", 4.41, 1.83, 1.61, 0.015, 0.152, 15.6, 68, 28),
    ("Mercedes-Benz", "GLB 250 e", 4.63, 1.83, 1.66, 0.016, 0.155, 15.6, 65, 30),
    ("Mercedes-Benz", "GLC 300 e", 4.72, 1.89, 1.64, 0.015, 0.155, 25.0, 120, 14),
    ("Mercedes-Benz", "GLC 300 de", 4.72, 1.89, 1.64, 0.014, 0.155, 25.0, 120, 13),
    ("Mercedes-Benz", "GLE 350 de", 4.92, 2.02, 1.77, 0.016, 0.165, 31.2, 100, 20),
    ("Mercedes-Benz", "GLE 400 e", 4.92, 2.02, 1.77, 0.017, 0.168, 31.2, 100, 22),
    ("Porsche", "Cayenne E-Hybrid", 4.93, 1.98, 1.70, 0.020, 0.175, 25.9, 80, 40),
    ("Porsche", "Cayenne Turbo E-Hybrid", 4.93, 1.98, 1.70, 0.022, 0.185, 25.9, 72, 55),
    ("Porsche", "Panamera 4 E-Hybrid", 5.05, 1.94, 1.43, 0.018, 0.170, 25.9, 90, 35),
    ("Porsche", "Panamera Turbo S E-Hybrid", 5.05, 1.94, 1.43, 0.020, 0.180, 25.9, 80, 45),
    ("Volkswagen", "Golf GTE", 4.29, 1.79, 1.48, 0.014, 0.149, 13.0, 64, 21),
    ("Volkswagen", "Passat GTE", 4.78, 1.83, 1.48, 0.015, 0.152, 13.0, 56, 32),
    ("Volkswagen", "Arteon Shooting Brake eHybrid", 4.87, 1.87, 1.45, 0.015, 0.155, 13.0, 55, 34),
    ("Volkswagen", "Tiguan eHybrid", 4.54, 1.86, 1.66, 0.017, 0.156, 19.7, 100, 18),
    ("Volkswagen", "Touareg R eHybrid", 4.90, 1.98, 1.70, 0.020, 0.175, 17.9, 50, 48),
    ("Skoda", "Octavia iV", 4.70, 1.83, 1.47, 0.014, 0.150, 13.0, 64, 24),
    ("Skoda", "Superb iV", 4.86, 1.86, 1.48, 0.015, 0.152, 13.0, 62, 28),
    ("SEAT", "Leon e-Hybrid", 4.37, 1.80, 1.46, 0.014, 0.148, 12.8, 64, 24),
    ("Cupra", "Leon e-Hybrid", 4.40, 1.80, 1.44, 0.014, 0.148, 12.8, 61, 26),
    ("Cupra", "Formentor e-Hybrid", 4.45, 1.84, 1.51, 0.018, 0.155, 12.8, 55, 31),
    ("Cupra", "Tavascan VZ e-Hybrid", 4.64, 1.86, 1.60, 0.016, 0.158, 19.7, 90, 24),
    ("Peugeot", "308 Hybrid", 4.37, 1.85, 1.44, 0.013, 0.148, 12.4, 60, 24),
    ("Peugeot", "408 Hybrid", 4.69, 1.85, 1.48, 0.014, 0.150, 12.4, 55, 28),
    ("Peugeot", "508 Hybrid", 4.75, 1.86, 1.42, 0.014, 0.150, 12.4, 55, 28),
    ("Peugeot", "3008 Hybrid", 4.54, 1.89, 1.64, 0.015, 0.150, 12.4, 59, 28),
    ("Peugeot", "5008 Hybrid", 4.64, 1.84, 1.65, 0.016, 0.155, 12.4, 55, 30),
    ("Citroen", "C5 Aircross Hybrid", 4.50, 1.96, 1.67, 0.016, 0.155, 13.2, 55, 32),
    ("DS", "DS 4 E-Tense", 4.40, 1.83, 1.47, 0.014, 0.150, 12.4, 55, 30),
    ("DS", "DS 7 E-Tense", 4.59, 1.90, 1.63, 0.016, 0.155, 13.2, 58, 32),
    ("DS", "DS 9 E-Tense", 4.93, 1.86, 1.46, 0.015, 0.155, 11.9, 50, 35),
    ("Opel", "Astra Hybrid", 4.37, 1.86, 1.47, 0.014, 0.150, 12.4, 60, 25),
    ("Opel", "Grandland Hybrid", 4.48, 1.91, 1.61, 0.016, 0.155, 13.2, 55, 32),
    ("Renault", "Rafale E-Tech", 4.71, 1.87, 1.64, 0.015, 0.155, 22.0, 90, 22),
    ("Volvo", "XC40 Recharge", 4.44, 1.86, 1.65, 0.015, 0.155, 18.8, 70, 28),
    ("Volvo", "XC60 Recharge", 4.71, 1.90, 1.66, 0.015, 0.157, 18.8, 78, 23),
    ("Volvo", "XC90 Recharge", 4.95, 1.96, 1.78, 0.017, 0.165, 18.8, 70, 30),
    ("Volvo", "S60 Recharge", 4.76, 1.85, 1.43, 0.014, 0.150, 18.8, 80, 22),
    ("Volvo", "V60 Recharge", 4.76, 1.85, 1.43, 0.014, 0.150, 18.8, 80, 22),
    ("Volvo", "S90 Recharge", 4.96, 1.88, 1.44, 0.015, 0.155, 18.8, 75, 25),
    ("Volvo", "V90 Recharge", 4.94, 1.88, 1.48, 0.015, 0.155, 18.8, 75, 25),
    ("Land Rover", "Range Rover Sport PHEV", 4.95, 2.05, 1.82, 0.020, 0.175, 31.8, 80, 40),
    ("Land Rover", "Range Rover PHEV", 5.05, 2.05, 1.87, 0.021, 0.180, 38.2, 90, 38),
    ("Land Rover", "Discovery Sport PHEV", 4.60, 1.90, 1.73, 0.018, 0.165, 15.0, 55, 42),
    ("Jaguar", "F-Pace PHEV", 4.75, 1.94, 1.66, 0.018, 0.165, 17.1, 53, 45),
    ("Mini", "Countryman SE ALL4", 4.44, 1.84, 1.66, 0.015, 0.155, 10.0, 50, 40),
    ("Ford", "Kuga PHEV", 4.61, 1.88, 1.68, 0.015, 0.151, 14.4, 64, 23),
    ("Ford", "Explorer PHEV", 5.05, 2.00, 1.78, 0.018, 0.165, 14.4, 55, 35),
    ("Ford", "Transit Custom PHEV", 4.97, 2.03, 1.96, 0.025, 0.200, 13.6, 50, 50),
    ("Jeep", "Renegade 4xe", 4.24, 1.81, 1.69, 0.020, 0.160, 11.4, 48, 46),
    ("Jeep", "Compass 4xe", 4.40, 1.82, 1.65, 0.019, 0.158, 11.4, 50, 44),
    ("Jeep", "Grand Cherokee 4xe", 4.91, 1.97, 1.81, 0.020, 0.170, 17.3, 40, 55),
    ("Jeep", "Wrangler 4xe", 4.88, 1.89, 1.87, 0.022, 0.175, 17.3, 35, 60),
    ("Alfa Romeo", "Tonale PHEV", 4.53, 1.84, 1.60, 0.016, 0.152, 15.5, 60, 26),
    ("Maserati", "Grecale Folgore Hybrid", 4.85, 1.95, 1.66, 0.018, 0.165, 25.0, 55, 45),
    # --- JP / KR ---
    ("Toyota", "Prius Plug-in", 4.60, 1.78, 1.42, 0.012, 0.145, 13.6, 69, 19),
    ("Toyota", "RAV4 Plug-in", 4.60, 1.86, 1.69, 0.014, 0.158, 18.1, 75, 22),
    ("Toyota", "C-HR Plug-in", 4.36, 1.83, 1.56, 0.014, 0.150, 13.6, 66, 22),
    ("Lexus", "NX 450h+", 4.66, 1.87, 1.66, 0.014, 0.155, 18.1, 70, 25),
    ("Lexus", "RX 450h+", 4.89, 1.92, 1.70, 0.015, 0.160, 18.1, 65, 28),
    ("Honda", "CR-V e:PHEV", 4.71, 1.87, 1.68, 0.015, 0.155, 17.7, 81, 22),
    ("Mitsubishi", "Outlander PHEV", 4.71, 1.86, 1.74, 0.017, 0.162, 20.0, 84, 26),
    ("Mitsubishi", "Eclipse Cross PHEV", 4.55, 1.81, 1.68, 0.018, 0.160, 13.8, 55, 35),
    ("Mazda", "CX-60 PHEV", 4.74, 1.89, 1.68, 0.016, 0.160, 17.8, 63, 30),
    ("Subaru", "Crosstrek PHEV", 4.49, 1.80, 1.60, 0.017, 0.160, 8.8, 27, 55),
    ("Hyundai", "Tucson Plug-in", 4.51, 1.87, 1.65, 0.016, 0.154, 13.8, 62, 29),
    ("Hyundai", "Santa Fe Plug-in", 4.83, 1.90, 1.72, 0.017, 0.160, 13.8, 55, 32),
    ("Kia", "Niro Plug-in", 4.42, 1.83, 1.55, 0.014, 0.148, 11.1, 58, 26),
    ("Kia", "Sportage Plug-in", 4.52, 1.87, 1.65, 0.016, 0.154, 13.8, 65, 25),
    ("Kia", "Sorento Plug-in", 4.81, 1.90, 1.70, 0.017, 0.160, 13.8, 55, 32),
    ("Kia", "Carnival Plug-in", 5.16, 2.00, 1.78, 0.020, 0.175, 13.8, 50, 40),
    # --- Cina / global brands (PHEV + EREV) ---
    ("BYD", "Seal U DM-i", 4.78, 1.89, 1.67, 0.012, 0.155, 18.3, 80, 20),
    ("BYD", "Sealion 6 DM-i", 4.77, 1.92, 1.66, 0.012, 0.155, 18.3, 80, 20),
    ("BYD", "Song Plus DM-i", 4.775, 1.89, 1.67, 0.012, 0.150, 18.3, 100, 18),
    ("BYD", "Han DM-i", 4.995, 1.91, 1.50, 0.013, 0.155, 18.3, 90, 22),
    ("BYD", "Tang DM-i", 4.87, 1.95, 1.73, 0.014, 0.160, 21.5, 100, 25),
    ("BYD", "Qin Plus DM-i", 4.765, 1.84, 1.50, 0.011, 0.145, 8.3, 55, 22),
    ("BYD", "Destroyer 05", 4.78, 1.84, 1.49, 0.011, 0.145, 8.3, 55, 22),
    ("BYD", "Shark", 5.457, 1.98, 1.925, 0.020, 0.180, 29.6, 100, 35),
    ("Li Auto", "L6", 4.925, 1.965, 1.765, 0.0, 0.175, 36.8, 212, 0),  # EREV: treat as phev with low fuel use
    ("Li Auto", "L7", 5.05, 1.995, 1.75, 0.0, 0.180, 42.8, 225, 0),
    ("Li Auto", "L8", 5.08, 1.995, 1.80, 0.0, 0.185, 42.8, 210, 0),
    ("Li Auto", "L9", 5.218, 1.998, 1.80, 0.0, 0.190, 44.5, 215, 0),
    ("Geely", "Galaxy L7", 4.70, 1.905, 1.685, 0.012, 0.150, 18.4, 90, 20),
    ("Geely", "Monjaro PHEV", 4.77, 1.895, 1.689, 0.014, 0.155, 19.1, 80, 25),
    ("Lynk & Co", "08 EM-P", 4.82, 1.915, 1.685, 0.012, 0.155, 39.6, 180, 18),
    ("Lynk & Co", "09 EM-P", 4.823, 1.961, 1.723, 0.014, 0.160, 40.0, 160, 22),
    ("Great Wall", "Wey Coffee 01", 4.878, 1.94, 1.69, 0.015, 0.160, 39.4, 150, 25),
    ("Great Wall", "Tank 500 Hi4-T", 5.07, 2.00, 1.90, 0.022, 0.185, 37.1, 110, 40),
    ("Chery", "Tiggo 8 Pro PHEV", 4.72, 1.86, 1.71, 0.015, 0.155, 19.2, 80, 28),
    ("Chery", "Omoda 5 PHEV", 4.40, 1.83, 1.59, 0.014, 0.150, 18.0, 75, 25),
    ("MG", "HS Plug-in", 4.61, 1.88, 1.69, 0.015, 0.155, 16.6, 52, 35),
    ("MG", "EHS", 4.61, 1.88, 1.69, 0.015, 0.155, 16.6, 52, 35),
    ("Leapmotor", "C10 REEV", 4.737, 1.90, 1.68, 0.0, 0.165, 28.4, 145, 0),
    ("AITO", "M5", 4.77, 1.93, 1.62, 0.0, 0.170, 40.0, 200, 0),
    ("AITO", "M7", 5.02, 1.95, 1.76, 0.0, 0.180, 42.0, 210, 0),
    ("AITO", "M9", 5.23, 2.00, 1.80, 0.0, 0.185, 52.0, 230, 0),
    ("Voyah", "Free", 4.905, 1.95, 1.645, 0.0, 0.175, 33.0, 160, 0),
    ("Voyah", "Dreamer", 5.315, 1.98, 1.82, 0.0, 0.190, 43.0, 180, 0),
    ("Hongqi", "HS5 PHEV", 4.785, 1.905, 1.703, 0.015, 0.155, 19.0, 80, 28),
    ("Denza", "D9 DM-i", 5.25, 1.96, 1.92, 0.014, 0.175, 40.0, 180, 25),
    ("Yangwang", "U8", 5.318, 2.05, 1.93, 0.0, 0.220, 49.0, 180, 0),
    ("Ferrari", "296 GTB", 4.57, 1.95, 1.19, 0.045, 0.200, 7.45, 25, 140),
    ("Ferrari", "SF90 Stradale", 4.71, 1.97, 1.19, 0.050, 0.220, 7.9, 25, 160),
    ("McLaren", "Artura", 4.54, 1.97, 1.19, 0.040, 0.210, 7.4, 30, 120),
    ("Lamborghini", "Revuelto", 4.95, 2.03, 1.16, 0.055, 0.250, 3.8, 10, 200),
    ("Polestar", "1", 4.59, 1.96, 1.35, 0.018, 0.165, 34.0, 100, 40),
]


def slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def mpg_to_l_per_km(mpg: float) -> float:
    if mpg <= 0:
        return 0.015
    return round((235.214 / mpg) / 100.0, 4)


def kwh_per_100mi_to_per_km(kwh100mi: float) -> float:
    if kwh100mi <= 0:
        return 0.155
    return round(kwh100mi / 160.934, 4)


def load_epa_phevs(path_or_download: bool = True) -> list[dict]:
    csv_text: str
    cached = EPA_CACHE
    if cached.exists():
        csv_text = cached.read_text(encoding="utf-8", errors="replace")
    else:
        print("Downloading EPA vehicles.csv.zip …")
        with urllib.request.urlopen(EPA_ZIP_URL, timeout=120) as resp:
            zdata = resp.read()
        with zipfile.ZipFile(BytesIO(zdata)) as zf:
            name = next(n for n in zf.namelist() if n.endswith("vehicles.csv"))
            csv_text = zf.read(name).decode("utf-8", errors="replace")
        cached.write_text(csv_text, encoding="utf-8")
        print(f"Cached {cached}")

    reader = csv.DictReader(StringIO(csv_text))
    best: dict[tuple[str, str], dict] = {}
    for row in reader:
        if (row.get("atvType") or "").strip() != "Plug-in Hybrid":
            continue
        make = (row.get("make") or "").strip()
        model = (row.get("model") or "").strip()
        base = (row.get("baseModel") or model).strip()
        if not make or not model:
            continue
        year = int(float(row["year"]))
        key = (make, model)
        if key not in best or year > int(best[key]["year"]):
            best[key] = row

    out: list[dict] = []
    for (make, model), row in sorted(best.items()):
        year = int(float(row["year"]))
        base = (row.get("baseModel") or model).strip()
        mpg = float(row.get("comb08") or 0) or 30.0
        combe = float(row.get("combE") or 0) or 45.0
        range_mi = float(row.get("rangeA") or 0) or 30.0
        co2 = row.get("co2")
        try:
            co2_v = float(co2) if co2 not in (None, "", "-1") else None
        except ValueError:
            co2_v = None
        fuel = mpg_to_l_per_km(mpg)
        energy = kwh_per_100mi_to_per_km(combe)
        display = model if "plug" in model.lower() or "hybrid" in model.lower() or "phev" in model.lower() else f"{base} PHEV"
        out.append(
            {
                "id": f"{slug(make)}-{slug(model)}-phev-{year}",
                "brand": make,
                "model": display,
                "year": year,
                "powertrain": "phev",
                "lengthM": 4.55,
                "widthM": 1.86,
                "heightM": 1.60,
                "fuelConsumptionLPerKm": fuel,
                "energyConsumptionKWhPerKm": energy,
                "maintenancePerYear": 480.0,
                "taxesPerYear": 90.0,
                "imageURL": None,
                "trim": model,
                "market": "US/EPA",
                "sourceName": "EPA-FuelEconomy",
                "sourceUpdatedAt": datetime.now(timezone.utc).isoformat(),
                "confidenceScore": 0.95,
                "wltpConsumptionKWh100km": round(energy * 100, 1),
                "batteryKWh": None,
                "wltpRangeKm": int(round(range_mi * 1.609)),
                "co2gKm": co2_v,
            }
        )
    OUT_EPA.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"EPA unique PHEV make+model: {len(out)}")
    return out


def world_rows() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    for item in PHEV_WORLD:
        brand, model, l, w, h, fuel, energy, batt, rng, co2 = item
        if not brand or model.lower() == "none":
            continue
        if l <= 0 or w <= 0:
            continue
        # Skip pure BEV masquerading (no fuel, huge battery/range)
        if fuel <= 0 and batt and batt > 80 and rng and rng > 400:
            continue
        # Mild hybrid / invalid
        if batt == 0 and fuel == 0:
            continue
        # EREV with fuel=0: assign small fuel use for range-extender sims
        if fuel <= 0:
            fuel = 0.012
        year = 2024
        rows.append(
            {
                "id": f"{slug(brand)}-{slug(model)}-phev-{year}",
                "brand": brand,
                "model": model,
                "year": year,
                "powertrain": "phev",
                "lengthM": round(float(l), 3),
                "widthM": round(float(w), 3),
                "heightM": round(float(h), 3),
                "fuelConsumptionLPerKm": float(fuel),
                "energyConsumptionKWhPerKm": float(energy),
                "maintenancePerYear": 480.0,
                "taxesPerYear": 90.0,
                "imageURL": None,
                "trim": "PHEV",
                "market": "WORLD",
                "sourceName": "manual-world-PHEV",
                "sourceUpdatedAt": now,
                "confidenceScore": 0.75,
                "wltpConsumptionKWh100km": round(float(energy) * 100, 1),
                "batteryKWh": float(batt) if batt else None,
                "wltpRangeKm": int(rng) if rng else None,
                "co2gKm": float(co2) if co2 else None,
            }
        )
    return rows


def attach_images(rows: list[dict], seed: list[dict]) -> None:
    # Map brand|token -> newest imageURL
    index: dict[str, tuple[int, str]] = {}
    for r in seed:
        url = r.get("imageURL")
        if not url:
            continue
        brand = str(r.get("brand", "")).lower()
        model = str(r.get("model", "")).lower()
        year = int(r.get("year") or 0)
        for token in model.split():
            if len(token) < 3:
                continue
            key = f"{brand}|{token}"
            prev = index.get(key)
            if not prev or year > prev[0]:
                index[key] = (year, url)
        index[f"{brand}|"] = (year, url) if (brand + "|") not in index or year > index[f"{brand}|"][0] else index[f"{brand}|"]

    for r in rows:
        if r.get("imageURL"):
            continue
        brand = r["brand"].lower()
        model = r["model"].lower()
        best = None
        best_score = -1
        for token in re.split(r"[^a-z0-9]+", model):
            if len(token) < 3:
                continue
            hit = index.get(f"{brand}|{token}")
            if hit and hit[0] > best_score:
                best_score = hit[0]
                best = hit[1]
        if not best:
            hit = index.get(f"{brand}|")
            if hit:
                best = hit[1]
        r["imageURL"] = best


def merge(seed: list[dict], extras: list[dict]) -> tuple[list[dict], int, int]:
    by_id = {r["id"]: i for i, r in enumerate(seed)}
    # Also index brand+model+phev for soft dedupe
    soft: dict[tuple[str, str], int] = {}
    for i, r in enumerate(seed):
        if r.get("powertrain") != "phev":
            continue
        soft[(r["brand"].lower(), re.sub(r"\s+phev$", "", r["model"].lower()).strip())] = i

    added = updated = 0
    for row in extras:
        soft_key = (row["brand"].lower(), re.sub(r"\s+phev$", "", row["model"].lower()).strip())
        if row["id"] in by_id:
            seed[by_id[row["id"]]] = row
            updated += 1
            continue
        if soft_key in soft:
            # Prefer EPA over manual if replacing
            idx = soft[soft_key]
            existing = seed[idx]
            if existing.get("sourceName") == "EPA-FuelEconomy" and row.get("sourceName") != "EPA-FuelEconomy":
                continue
            seed[idx] = row
            by_id[row["id"]] = idx
            soft[soft_key] = idx
            updated += 1
            continue
        seed.append(row)
        by_id[row["id"]] = len(seed) - 1
        soft[soft_key] = len(seed) - 1
        added += 1
    return seed, added, updated


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    epa = load_epa_phevs()
    world = world_rows()
    # Prefer EPA first then fill gaps with world list
    extras = epa + world
    attach_images(extras, seed)
    seed, added, updated = merge(seed, extras)
    SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    phev = [r for r in seed if r.get("powertrain") == "phev"]
    print(
        f"seed={len(seed)} phev={len(phev)} added={added} updated={updated} "
        f"with_images={sum(1 for r in phev if r.get('imageURL'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
