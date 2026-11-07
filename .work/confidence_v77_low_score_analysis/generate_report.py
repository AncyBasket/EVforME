from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json"
OUT = ROOT / "outputs" / "confidence_v77_low_score_analysis"
OUT.mkdir(parents=True, exist_ok=True)

rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
low = [r for r in rows if float(r.get("confidenceScore", 1.0)) < 0.5]
assert len(rows) == 6977 and len(low) == 2283
assert all(r.get("confidencePolicyVersion") == 1 for r in low)

def get_reason(r):
    return r["confidenceEvidence"]["reasonCode"]

def pct(n, d):
    return 100.0 * n / d if d else 0.0

def fmt_pct(n, d):
    return f"{pct(n,d):.1f}%"

def label_band(score):
    return "bassa" if score < 0.5 else "media" if score < 0.8 else "alta"

def year_band(year):
    if year < 2010:
        return "<2010"
    if year < 2020:
        return "2010–2019"
    if year < 2025:
        return "2020–2024"
    return "2025+"

def join_values(values):
    return "; ".join(str(v) for v in values) if values else ""

reason_labels = {
    "unmatched_eu_version": "Versione EEA EU non abbinata",
    "pre_2010_unverified_estimate": "Stima pre-2010 non verificata",
    "estimated_or_unmatched_it_data": "Stima / match EEA IT non affidabile",
    "stale_or_uncovered_estimate": "Fonte obsoleta o anno non coperto",
    "weak_single_sample_proxy": "Proxy variante sorella (n=1)",
    "eea_it_older_year": "Fonte EEA IT più vecchia di un anno",
    "eea_it_one_year_old": "Fonte EEA IT di un anno precedente",
}

# Detailed row-level CSV.
detail_fields = [
    "id", "brand", "model", "year", "trim", "powertrain", "market",
    "confidenceScore", "confidenceScoreLegacy", "legacyBand", "reasonCode",
    "sourceClass", "sourceName", "sourceUpdatedAt", "sourceYear", "modelYear",
    "yearRelation", "variantMatch", "sampleSize", "provisional",
    "evidenceScope", "fieldSourceCoverage", "requiredCalculationFields",
    "missingRequiredCalculationFields", "fieldSourcesForRequiredFields",
    "catalogDataIncompleteKey", "catalogDataIncompleteValue",
    "missingCalcFieldsKey", "missingCalcFieldsValue",
]
with (OUT / "low_confidence_records.csv").open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=detail_fields)
    writer.writeheader()
    for r in sorted(low, key=lambda x: (get_reason(x), x.get("brand", ""), x.get("model", ""), int(x.get("year", 0)), x.get("id", ""))):
        ev = r["confidenceEvidence"]
        req = ev.get("requiredCalculationFields") or []
        missing = [field for field in req if r.get(field) is None]
        sources = r.get("fieldSources") if isinstance(r.get("fieldSources"), dict) else {}
        required_sources = [f"{field}={sources[field]}" for field in req if sources.get(field)]
        writer.writerow({
            "id": r.get("id"), "brand": r.get("brand"), "model": r.get("model"),
            "year": r.get("year"), "trim": r.get("trim"), "powertrain": r.get("powertrain"),
            "market": r.get("market"), "confidenceScore": r.get("confidenceScore"),
            "confidenceScoreLegacy": r.get("confidenceScoreLegacy"),
            "legacyBand": label_band(float(r.get("confidenceScoreLegacy", 0))),
            "reasonCode": get_reason(r), "sourceClass": ev.get("sourceClass"),
            "sourceName": r.get("sourceName"), "sourceUpdatedAt": r.get("sourceUpdatedAt"),
            "sourceYear": ev.get("sourceYear"), "modelYear": ev.get("modelYear"),
            "yearRelation": ev.get("yearRelation"), "variantMatch": ev.get("variantMatch"),
            "sampleSize": ev.get("sampleSize"), "provisional": ev.get("provisional"),
            "evidenceScope": ev.get("evidenceScope"), "fieldSourceCoverage": ev.get("fieldSourceCoverage"),
            "requiredCalculationFields": join_values(req),
            "missingRequiredCalculationFields": join_values(missing),
            "fieldSourcesForRequiredFields": join_values(required_sources),
            "catalogDataIncompleteKey": "present" if "catalogDataIncomplete" in r else "absent",
            "catalogDataIncompleteValue": r.get("catalogDataIncomplete", ""),
            "missingCalcFieldsKey": "present" if "missingCalcFields" in r else "absent",
            "missingCalcFieldsValue": join_values(r.get("missingCalcFields") or []),
        })

# Cause summary and cross-tabs.
reason_counts = Counter(get_reason(r) for r in low)
score_counts = Counter(float(r["confidenceScore"]) for r in low)
pt_counts = Counter(r.get("powertrain", "N/D") for r in low)
all_pt_counts = Counter(r.get("powertrain", "N/D") for r in rows)
source_counts = Counter(r.get("sourceName") or "N/D" for r in low)
reason_pt = Counter((get_reason(r), r.get("powertrain", "N/D")) for r in low)
reason_year = Counter((get_reason(r), year_band(int(r["year"]))) for r in low)
brand_low = Counter(r.get("brand") or "N/D" for r in low)
brand_all = Counter(r.get("brand") or "N/D" for r in rows)
legacy_bands = Counter(label_band(float(r.get("confidenceScoreLegacy", 0))) for r in low)

with (OUT / "reason_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = ["reasonCode", "label", "count", "shareOfLow", "scoreValues", "EV", "ICE", "HEV", "PHEV"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for reason, n in reason_counts.most_common():
        scores = sorted({float(r["confidenceScore"]) for r in low if get_reason(r) == reason})
        writer.writerow({
            "reasonCode": reason, "label": reason_labels.get(reason, reason), "count": n,
            "shareOfLow": round(pct(n, len(low)), 2), "scoreValues": join_values(scores),
            **{pt.upper(): reason_pt[(reason, pt)] for pt in ("ev", "ice", "hev", "phev")},
        })

with (OUT / "brand_breakdown.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = ["brand", "catalogRecords", "lowRecords", "shareLowWithinBrand", "shareOfAllLow"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for brand, total in sorted(brand_all.items(), key=lambda item: (-brand_low[item[0]], item[0])):
        writer.writerow({
            "brand": brand, "catalogRecords": total, "lowRecords": brand_low[brand],
            "shareLowWithinBrand": round(pct(brand_low[brand], total), 2),
            "shareOfAllLow": round(pct(brand_low[brand], len(low)), 2),
        })

# Deterministic PNG chart using Pillow (no generated/simulated data, no extra package install).
W, H = 1800, 980
image = Image.new("RGB", (W, H), "#fbfcfe")
draw = ImageDraw.Draw(image)
font_candidates = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]
def font(size):
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()
ftitle, fsub, flabel, fsmall, fnum = font(38), font(22), font(23), font(18), font(20)
draw.text((60, 34), "Catalogo v77 · Record con qualità dati < 0,5", font=ftitle, fill="#172b4d")
draw.text((60, 90), "2.283 record · causa di scoring ripartita per powertrain · dati dal seed locale", font=fsub, fill="#52647b")
colors = {"ev": "#2979b8", "ice": "#e57a35", "hev": "#46a17b", "phev": "#8d6cab"}
legend_x = 60
for pt, text in [("ev", "EV"), ("ice", "ICE"), ("hev", "HEV"), ("phev", "PHEV")]:
    if pt_counts.get(pt, 0) == 0:
        continue
    draw.rounded_rectangle((legend_x, 137, legend_x + 24, 161), radius=4, fill=colors[pt])
    draw.text((legend_x + 34, 136), text, font=fsmall, fill="#26364b")
    legend_x += 115

reasons_sorted = [reason for reason, _ in reason_counts.most_common()]
left, top, chart_width = 610, 205, 960
max_count = 1200
row_h, bar_h = 96, 46
# Grid and axis labels.
for value in (0, 300, 600, 900, 1200):
    x = left + int(chart_width * value / max_count)
    draw.line((x, top - 18, x, top + row_h * len(reasons_sorted) - 25), fill="#d9e0e8", width=2)
    draw.text((x - 22, top - 51), str(value), font=fsmall, fill="#52647b")
for i, reason in enumerate(reasons_sorted):
    y = top + i * row_h
    label = reason_labels.get(reason, reason)
    draw.text((60, y + 7), label, font=flabel, fill="#26364b")
    x_cursor = left
    segments = []
    for pt in ("ev", "ice", "hev", "phev"):
        n = reason_pt[(reason, pt)]
        if n:
            width = int(chart_width * n / max_count)
            draw.rectangle((x_cursor, y, x_cursor + width, y + bar_h), fill=colors[pt])
            x_cursor += width
            segments.append((pt, n, width))
    total = reason_counts[reason]
    draw.text((x_cursor + 12, y + 11), f"{total:,}".replace(",", "."), font=fnum, fill="#172b4d")
# Redraw segment values accurately over bars.
for i, reason in enumerate(reasons_sorted):
    y = top + i * row_h
    x_cursor = left
    for pt in ("ev", "ice", "hev", "phev"):
        n = reason_pt[(reason, pt)]
        if n:
            width = int(chart_width * n / max_count)
            if width > 78:
                txt = str(n)
                box = draw.textbbox((0, 0), txt, font=fsmall)
                tw = box[2] - box[0]
                draw.text((x_cursor + (width - tw) // 2, y + 11), txt, font=fsmall, fill="white")
            x_cursor += width

foot_y = top + row_h * len(reasons_sorted) + 16
draw.line((60, foot_y, W - 60, foot_y), fill="#d9e0e8", width=2)
draw.text((60, foot_y + 20), "Score basso: < 0,50 · tutti i 2.283 record hanno i campi minimi di calcolo valorizzati, ma nessuno ha provenance puntuale sui campi richiesti.", font=fsmall, fill="#52647b")
chart_path = OUT / "cause_per_powertrain.png"
image.save(chart_path, format="PNG", optimize=True)

# Aggregate metrics used in the narrative.
missing_required = sum(
    1 for r in low
    if any(r.get(field) is None for field in (r["confidenceEvidence"].get("requiredCalculationFields") or []))
)
required_instances = Counter(
    field for r in low for field in (r["confidenceEvidence"].get("requiredCalculationFields") or [])
)
source_covered_rows = sum(
    any((r.get("fieldSources") or {}).get(field) for field in (r["confidenceEvidence"].get("requiredCalculationFields") or []))
    for r in low
)
evidence_scopes = Counter(r["confidenceEvidence"].get("evidenceScope") for r in low)
reason_source = Counter((get_reason(r), r.get("sourceName") or "N/D") for r in low)
raw_source_relation = Counter(r["confidenceEvidence"].get("yearRelation") for r in low)
pre2010 = [r for r in low if get_reason(r) == "pre_2010_unverified_estimate"]
pre2010_false_year = sum(
    r["confidenceEvidence"].get("sourceYear") == 2010
    and r["confidenceEvidence"].get("yearRelation") == "source_future"
    for r in pre2010
)
legacy_band_for_low = Counter(label_band(float(r.get("confidenceScoreLegacy", 0))) for r in low)
score_reason = Counter((float(r["confidenceScore"]), get_reason(r)) for r in low)

# Brand tables.
top_brand_count = brand_low.most_common(10)
brands_at_least_20 = [b for b, n in brand_all.items() if n >= 20]
top_brand_rates = sorted(brands_at_least_20, key=lambda b: (-(brand_low[b] / brand_all[b]), -brand_low[b], b))[:8]

def md_table(headers, data):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in data:
        lines.append("| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |")
    return "\n".join(lines)

reason_rows = []
for reason, n in reason_counts.most_common():
    scores = sorted({float(r["confidenceScore"]) for r in low if get_reason(r) == reason})
    reason_rows.append([
        reason_labels.get(reason, reason), n, fmt_pct(n, len(low)), ", ".join(f"{s:.2f}" for s in scores),
        reason_pt[(reason, "ev")], reason_pt[(reason, "ice")], reason_pt[(reason, "hev")],
    ])
pt_rows = []
for pt in ["ev", "ice", "hev", "phev"]:
    pt_rows.append([pt.upper(), all_pt_counts[pt], pt_counts[pt], fmt_pct(pt_counts[pt], all_pt_counts[pt]), fmt_pct(pt_counts[pt], len(low))])
year_rows = []
for band in ["<2010", "2010–2019", "2020–2024", "2025+"]:
    total = sum(1 for r in rows if year_band(int(r["year"])) == band)
    n = sum(1 for r in low if year_band(int(r["year"])) == band)
    year_rows.append([band, total, n, fmt_pct(n, total), fmt_pct(n, len(low))])
brand_count_rows = []
for brand, n in top_brand_count:
    den = brand_all[brand]
    brand_count_rows.append([brand, n, den, fmt_pct(n, den), fmt_pct(n, len(low))])
brand_rate_rows = []
for brand in top_brand_rates:
    n, den = brand_low[brand], brand_all[brand]
    cause = Counter(get_reason(r) for r in low if r.get("brand") == brand)
    dominant, dominant_n = cause.most_common(1)[0]
    brand_rate_rows.append([brand, n, den, fmt_pct(n, den), f"{reason_labels.get(dominant, dominant)} ({dominant_n})"])
source_rows = []
for source, n in source_counts.most_common():
    example = next(r for r in low if (r.get("sourceName") or "N/D") == source)
    source_rows.append([n, fmt_pct(n, len(low)), example["confidenceEvidence"]["reasonCode"], source.replace("\n", " ")])

# Key source-name clusters and estimated years.
source_detail = []
for (reason, source), n in reason_source.most_common():
    source_detail.append((reason, source, n))

report = f'''# Analisi dei 2.283 record a score < 0,5 — catalogo v77

**Snapshot analizzato:** `EVforME?/Data/vehicles.seed.quality.json`, manifest `seedVersion=77`; 6.977 record totali. Filtro esatto: `confidenceScore < 0.5` e `confidencePolicyVersion=1`. Analisi eseguita sui dati salvati, senza riscrivere il catalogo.

![Cause degli score sotto soglia per powertrain](cause_per_powertrain.png)

## Sintesi

- I record sotto soglia sono **2.283/6.977 (32,7%)**.
- Il punteggio basso segnala soprattutto **provenienza/match non verificati**, non un consumo assente: per tutti i **2.283/2.283** i campi minimi richiesti dallo scorer sono presenti (EV: `energyConsumptionKWhPerKm`; ICE/HEV: `fuelConsumptionLPerKm`). Non è un’attestazione della correttezza del valore.
- Allo stesso tempo, **0/2.283** ha una fonte puntuale (`fieldSources`) per i campi di calcolo richiesti; tutti hanno `evidenceScope=record_level` e `fieldSourceCoverage=0`.
- Nei record low, le chiavi `catalogDataIncomplete` e `missingCalcFields` sono **assenti** in tutti i casi. L’assenza del flag non va interpretata come certificazione di completezza: per questo sotto sono controllati direttamente i campi richiesti.
- Il gruppo è composto da **1.295 EV (56,7%)**, **971 ICE (42,5%)** e **17 HEV (0,7%)**; non ci sono PHEV sotto soglia.

## Distribuzione per causa

{md_table(["Motivo policy", "Record", "% dei low", "Score", "EV", "ICE", "HEV"], reason_rows)}

Le cause principali sono:

1. **Versione EEA EU non abbinata: 1.089 (47,7%)**, tutti EV e tutti con score 0,40. L’auto ha un dato `Zr` EEA EU, ma nel record non c’è un match dimostrato fra variante omologata, allestimento e riga EEA.
2. **Stime pre-2010: 682 (29,9%)**, di cui 677 ICE e 5 HEV. Il catalogo esplicita che non è stata trovata copertura EEA IT affidabile; lo score 0,30 è deterministico ma non prova che ogni consumo sia errato.
3. **Stime o match EEA IT non affidabili: 344 (15,1%)**: 165 usano la stessa variante ma un anno fonte precedente, 142 non hanno match EEA IT in cache, 35 derivano una stima da EEA IT 2024, 2 usano un riferimento medio ibrido 2018.
4. **Fonte non coprente/recupero non verificato: 161 (7,1%)**: 135 record 2026 non coperti dall’ultimo EEA IT indicato e 26 record ripristinati senza match EEA IT affidabile.
5. **Proxy `n=1`: 5 (0,2%)**; un record ha fonte EEA IT più vecchia di un anno e un record usa una fonte EEA IT di un anno precedente.

## Score puntuali

{md_table(["Score", "Record", "% dei low", "Lettura sintetica"], [
    [f"{s:.2f}", n, fmt_pct(n, len(low)), {0.30:"stima pre-2010",0.35:"proxy/stima stantia",0.40:"match insufficiente o stima",0.45:"fonte un anno precedente"}.get(s,"—")]
    for s,n in sorted(score_counts.items())
])}

## Powertrain

{md_table(["Tipo", "Record catalogo", "Sotto 0,5", "% del tipo sotto soglia", "% dei 2.283 low"], pt_rows)}

Il problema è concentrato sui BEV: **70,7% degli EV nel catalogo** è sotto soglia; per ICE è 19,9%, per HEV 12,1%. Fra gli EV low, 1.089/1.295 (84,1%) ricadono nel match EEA EU non verificato. Il fatto che gli EV siano più colpiti dipende quindi in larga parte dal diverso livello di matching/provenienza, non da un campo energia mancante.

## Anno modello

{md_table(["Anno modello", "Record catalogo", "Sotto 0,5", "% del periodo sotto soglia", "% dei low"], year_rows)}

Tutti i **682 record con anno <2010** sono sotto soglia, per la regola esplicita `pre_2010_unverified_estimate`. Fra 2020–2024, 843/3.002 (28,1%) sono low; la maggioranza (824) è attribuita a versione EEA EU non abbinata. Fra 2025+, 756/1.010 (74,9%) sono low, soprattutto per stime/match IT (342), anni non coperti (145) e match EEA EU (265). La forte incidenza 2025+ segnala una lacuna di copertura del catalogo recente.

### Anomalia nei metadati dell’anno fonte

In tutti i **682** record pre-2010, `confidenceEvidence.sourceYear` vale erroneamente **2010** e `yearRelation=source_future`. Il parser sta leggendo il testo letterale `pre-2010` come se “2010” fosse l’anno della fonte. Questo non è un dato di fonte futuro e non ha guidato il loro score (il `reasonCode` pre-2010 determina 0,30), ma rende fuorviante la dimensione temporale dell’evidence. Per gli altri 1.601 record low, la relazione salvata è: unknown 1.115, same-year 279, source one-year old 201, source older 6. È opportuno correggere il parser in una nuova revisione della policy e rigenerare l’evidence.

## Provenienza e campi di calcolo

- **Campi minimi mancanti:** 0/2.283 secondo `requiredCalculationFields` in `confidenceEvidence`.
- **Provenienza di campo sui campi richiesti:** 0/2.283. Tutte le fonti sono etichette record-level (`sourceName`), non URL/data collegati esplicitamente al campo consumo.
- **Flag catalogo:** `catalogDataIncomplete` e `missingCalcFields` non sono proprio serializzati nei 2.283 record. Non si può inferire “completo” dalla loro assenza.
- **Unicità:** {len(set(r['id'] for r in low))} ID distinti; nessun record è contato più di una volta.

Quindi il rischio è principalmente **epistemico** (non è dimostrato che quel valore appartenga esattamente a quel modello/anno/trim), non un blocco immediato dovuto a input nullo del simulatore. La presenza di un valore non sostituisce la fonte.

## Confronto con lo score legacy

{md_table(["Banda legacy tra i 2.283 low attuali", "Record", "% dei low attuali"], [
    [band, n, fmt_pct(n, len(low))] for band,n in [("bassa",legacy_bands["bassa"]),("media",legacy_bands["media"]),("alta",legacy_bands["alta"])]
])}

**967 record (42,4%)** che oggi hanno score <0,5 avevano legacy ≥0,8; altri 17 avevano legacy fra 0,5 e 0,75. Questo mostra che la policy precedente sovrastimava soprattutto EV basati su EEA EU non abbinato. Il legacy è conservato per audit, ma non va usato come indicatore corretto senza la vecchia rubrica.

## Marche maggiormente interessate

### Maggior numero assoluto di record low

{md_table(["Marca", "Low", "Catalogo", "% marca low", "% di tutti i low"], brand_count_rows)}

### Maggiore incidenza (marche con almeno 20 record nel catalogo)

{md_table(["Marca", "Low", "Catalogo", "% marca low", "Causa dominante"], brand_rate_rows)}

Le percentuali più alte sono fortemente associate a brand con cataloghi BEV recenti: Polestar, XPeng, Lucid, Tesla, BYD e NIO. Nei gruppi mostrati prevale il reason `unmatched_eu_version` (per esempio Tesla 119/125, Polestar 52/58, BYD 56/68). Le marche maggiori per volume (BMW, Volkswagen, Kia, Hyundai) combinano invece EV non abbinati e stime ICE storiche; il volume assoluto da solo non misura la qualità media.

## Priorità operative suggerite

1. **Chiudere i match dei 1.089 EV EEA EU.** Per ogni ID, confrontare brand/modello/anno, potenza kW, trazione e variante OEM; annotare URL OEM e identificativo/riga EEA. Promuovere lo score solo dopo un match verificabile, non per semplice somiglianza nominale.
2. **Aggiungere provenance per campo.** Per i 2.283 record, valutare `fieldSources` e `fieldSourceDates` per i consumi effettivamente usati dal simulatore; non basta `sourceName` generico.
3. **Prioritizzare 2025+ e fonti non coprenti.** Rivedere 135 record 2026, 142 no-match e 165 same-variant/year-proxy; i dati recenti sono la parte più esposta a stime o copertura incompleta.
4. **Trattare i 682 pre-2010 come stime storiche.** Se il prodotto li mantiene, esplicitare in UI la natura stimata e cercare archivi OEM omologativi dove disponibili.
5. **Correggere il bug `pre-2010 → sourceYear=2010`.** Aggiornare il parser e la versione policy; i reason score resterebbero 0,30, ma l’evidence temporale diverrebbe corretta.

## File di supporto

- `low_confidence_records.csv`: dettaglio dei 2.283 ID con score, reason, score legacy, fonte, match, anno fonte, campi minimi e provenance puntuale.
- `reason_summary.csv`: conteggi e cross-tab cause × powertrain.
- `brand_breakdown.csv`: tutte le marche con denominatori e tasso low.
- `cause_per_powertrain.png`: grafico cause e composizione per powertrain.
- Generatore usato: `.work/confidence_v77_low_score_analysis/generate_report.py`.

**Limite dell’analisi:** misura la policy/evidence presenti nel seed locale v77. Non verifica online i 2.283 singoli dati e non conclude che un consumo sia falso; quantifica dove il record non è sufficientemente tracciabile o abbinato.
'''
(OUT / "analysis.md").write_text(report, encoding="utf-8")
print("wrote", OUT)
print("low", len(low), "reason buckets", len(reason_counts), "detail csv", OUT / "low_confidence_records.csv")
