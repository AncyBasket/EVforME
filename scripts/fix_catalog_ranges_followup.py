#!/usr/bin/env python3
"""Clear remaining interpolated EV ranges; set known WLTP per generation or nil."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("ë", "e").replace("é", "e").split())


def known_range(brand: str, model: str, year: int) -> int | None | object:
    """Return int km, None to clear, or Ellipsis to leave unchanged."""
    b, m = _norm(brand), _norm(model)

    if b == "nissan" and m == "leaf":
        # Gen2 40 kWh ~270 WLTP; earlier NEDC-only / trim-ambiguous → nil.
        if 2018 <= year <= 2022:
            return 270
        return None

    if b == "volkswagen" and m in {"e-golf", "e golf"}:
        # 35.8 kWh facelift ~232 WLTP; pre-2017 uncertain → nil.
        if year >= 2017:
            return 230
        return None

    if b == "renault" and m == "zoe":
        if year >= 2020:
            return 395  # ZE50
        if year >= 2017:
            return 300  # ZE40
        return None

    if b == "volkswagen" and ("e-up" in m or m.startswith("e up")):
        if year >= 2019:
            return 260  # 36.8 kWh
        return None

    if b == "dacia" and m == "spring":
        if year <= 2023:
            return 230  # first-gen Electric 45
        return 220  # 2024+ band already in seed

    if b == "kia" and m == "ev6":
        # Long Range RWD representative WLTP; trim-specific GT omitted.
        return 528

    if b == "toyota" and "bz4x" in m.replace("-", ""):
        return 460

    if b == "subaru" and m == "solterra":
        return 460

    if b == "citroen" and ("e-c3" in m or "ec3" in m.replace("-", "").replace(" ", "")):
        if year <= 2023:
            return None  # 518 km row was interpolated / pre-launch junk
        return 320

    return Ellipsis


def has_constant_step_subsequence(pairs: list[tuple[int, int]]) -> bool:
    """True if any contiguous ≥3-point window has identical non-zero deltas."""
    if len(pairs) < 3:
        return False
    rows = sorted(pairs)
    n = len(rows)
    for start in range(n - 2):
        for end in range(start + 2, n):
            sub = rows[start : end + 1]
            deltas = [sub[i + 1][1] - sub[i][1] for i in range(len(sub) - 1)]
            if len(set(deltas)) == 1 and deltas[0] != 0:
                return True
    return False


def apply_known(rows: list[dict]) -> int:
    changed = 0
    for row in rows:
        if row.get("powertrain") != "ev":
            continue
        val = known_range(str(row.get("brand", "")), str(row.get("model", "")), int(row.get("year") or 0))
        if val is Ellipsis:
            continue
        if row.get("wltpRangeKm") != val:
            row["wltpRangeKm"] = val
            changed += 1
    return changed


def clear_remaining_interpolations(rows: list[dict]) -> int:
    """Nil any EV series that still has a constant-step subsequence."""
    changed = 0
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if row.get("powertrain") != "ev":
            continue
        key = (_norm(str(row.get("brand", ""))), _norm(str(row.get("model", ""))))
        groups.setdefault(key, []).append(row)

    for key, group in groups.items():
        pairs = [
            (int(r["year"]), int(r["wltpRangeKm"]))
            for r in group
            if r.get("wltpRangeKm") is not None
        ]
        if not has_constant_step_subsequence(pairs):
            continue
        # Prefer clearing only the interpolated window; if ambiguous, clear all non-nil.
        for r in group:
            if r.get("wltpRangeKm") is not None:
                r["wltpRangeKm"] = None
                changed += 1
        print(f"cleared interpolated ranges: {key[0]} {key[1]}")
    return changed


def main() -> None:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    n1 = apply_known(rows)
    n2 = clear_remaining_interpolations(rows)
    # Re-apply known after clear so generation values win.
    n3 = apply_known(rows)
    text = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    SEED.write_text(text, encoding="utf-8")
    print(f"known edits={n1}, cleared={n2}, reapply={n3}, total={len(rows)}")


if __name__ == "__main__":
    main()
