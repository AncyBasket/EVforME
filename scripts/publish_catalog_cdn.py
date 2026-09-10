#!/usr/bin/env python3
"""Pubblica il catalogo online e aggiorna AUTOMATICAMENTE i puntatori nell’app.

Non serve copiare URL a mano.

Aggiorna:
  - api/static/vehicles.catalog(.min).json
  - api/static/catalog_cdn.json
  - EVforME?/Data/catalog_cdn.json   ← letto dall’app a runtime
  - Defaults.swift (fallback)
  - Info.plist EVFORME_CATALOG_URL (vuoto = usa Data/catalog_cdn.json;
    se era localhost, lo lascia stare)

Uso:
  python3 scripts/publish_catalog_cdn.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUALITY = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
APP_DATA = REPO / "EVforME?" / "Data"
STATIC = REPO / "api" / "static"
MIN_JSON = STATIC / "vehicles.catalog.min.json"
FULL_JSON = STATIC / "vehicles.catalog.json"
CDN_META_API = STATIC / "catalog_cdn.json"
CDN_META_APP = APP_DATA / "catalog_cdn.json"
DEFAULTS_SWIFT = REPO / "EVforME?" / "Core" / "Constants" / "Defaults.swift"
INFO_PLIST = REPO / "EVforME?" / "Info.plist"


def upload_catbox(path: Path) -> str:
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            "180",
            "-F",
            "reqtype=fileupload",
            "-F",
            f"fileToUpload=@{path}",
            "https://catbox.moe/user/api.php",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    url = result.stdout.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"upload failed: {url!r}")
    return url


def write_meta(url: str, rows: int, bytes_count: int) -> dict:
    meta = {
        "url": url,
        "rows": rows,
        "bytes": bytes_count,
        "source": QUALITY.name,
        "host": "catbox.moe",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "note": "Auto-updated by scripts/publish_catalog_cdn.py — do not edit by hand.",
    }
    text = json.dumps(meta, indent=2) + "\n"
    CDN_META_API.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA.mkdir(parents=True, exist_ok=True)
    CDN_META_API.write_text(text, encoding="utf-8")
    CDN_META_APP.write_text(text, encoding="utf-8")
    return meta


def patch_defaults_swift(url: str) -> None:
    if not DEFAULTS_SWIFT.exists():
        return
    src = DEFAULTS_SWIFT.read_text(encoding="utf-8")
    patched, n = re.subn(
        r'static let publicVehicleCatalogCDNURL = "https://[^"]+"',
        f'static let publicVehicleCatalogCDNURL = "{url}"',
        src,
        count=1,
    )
    if n == 0:
        # insert after eurostat if constant missing
        patched, n = re.subn(
            r'(static let eurostatElectricityURL =\n\s+"[^"]+"\n)',
            r'\1\n    /// Catalogo veicoli HTTPS pubblico (auto da publish_catalog_cdn.py).\n'
            f'    static let publicVehicleCatalogCDNURL = "{url}"\n',
            src,
            count=1,
        )
    if n == 0:
        print("warning: could not patch Defaults.swift", file=sys.stderr)
        return
    DEFAULTS_SWIFT.write_text(patched, encoding="utf-8")


def patch_info_plist(url: str) -> None:
    """Scrive l’URL remoto nel plist, salvo override localhost di sviluppo."""
    if not INFO_PLIST.exists():
        return
    text = INFO_PLIST.read_text(encoding="utf-8")
    # Se lo sviluppatore punta a localhost, non toccare.
    if "127.0.0.1" in text and "EVFORME_CATALOG_URL" in text:
        block = re.search(
            r"<key>EVFORME_CATALOG_URL</key>\s*<string>(.*?)</string>",
            text,
            flags=re.S,
        )
        if block and "127.0.0.1" in block.group(1):
            print("Info.plist: lasciato override localhost")
            return
    patched, n = re.subn(
        r"(<key>EVFORME_CATALOG_URL</key>\s*<string>)(.*?)(</string>)",
        rf"\g<1>{url}\g<3>",
        text,
        count=1,
        flags=re.S,
    )
    if n == 0:
        print("warning: could not patch Info.plist", file=sys.stderr)
        return
    INFO_PLIST.write_text(patched, encoding="utf-8")


def main() -> int:
    if not QUALITY.exists():
        print(f"missing {QUALITY}; run enrich scripts first", file=sys.stderr)
        return 1

    rows = json.loads(QUALITY.read_text(encoding="utf-8"))
    compact = [{k: v for k, v in row.items() if v is not None} for row in rows]
    STATIC.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(compact, separators=(",", ":"), ensure_ascii=False)
    MIN_JSON.write_text(payload, encoding="utf-8")
    FULL_JSON.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")

    url = upload_catbox(MIN_JSON)
    meta = write_meta(url, len(compact), MIN_JSON.stat().st_size)
    patch_defaults_swift(url)
    patch_info_plist(url)

    print(json.dumps(meta, indent=2))
    print("\nOK — URL aggiornato automaticamente in:")
    print(f"  - {CDN_META_APP.relative_to(REPO)}")
    print(f"  - {CDN_META_API.relative_to(REPO)}")
    print(f"  - {DEFAULTS_SWIFT.relative_to(REPO)}")
    print(f"  - {INFO_PLIST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
