"""Build athlete-signup/schools.json from the federal IPEDS institution list.

Source: NCES IPEDS "Institutional Characteristics" header file (public domain),
https://nces.ed.gov/ipeds/datacenter/data/HD<year>.zip. Keeps active 2-year
and 4-year institutions (sectors 1-6), so every NCAA / NAIA / NJCAA school is
present, and prettifies the federal spelling ("Texas A & M" -> "Texas A&M").

Output is a compact array the signup form searches client-side:
  [{"n": name, "a": alias, "c": city, "s": state, "d": web domain}, ...]

Run (from the repo root):  python scripts/build-schools.py [--year 2023]
Then copy the same file to the dashboard repo's backend/onboarding/data/.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "athlete-signup" / "schools.json"


def pretty(name: str) -> str:
    name = name.replace(" A & M ", " A&M ").replace("A & M", "A&M")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def domain(web: str) -> str:
    web = (web or "").strip().lower()
    web = re.sub(r"^https?://", "", web).replace("www.", "")
    return web.split("/")[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", default="2023")
    args = ap.parse_args()
    url = f"https://nces.ed.gov/ipeds/datacenter/data/HD{args.year}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    rows = list(csv.DictReader(io.StringIO(z.read(csv_name).decode("latin-1"))))
    rows = [{k.lstrip("﻿"): v for k, v in r.items()} for r in rows]
    keep = [r for r in rows if r.get("SECTOR") in ("1", "2", "3", "4", "5", "6") and r.get("CYACTIVE") == "1"]
    out = []
    for r in keep:
        out.append({
            "n": pretty(r["INSTNM"]),
            "a": pretty(r.get("IALIAS") or ""),
            "c": r.get("CITY", "").strip(),
            "s": r.get("STABBR", "").strip(),
            "d": domain(r.get("WEBADDR", "")),
        })
    out.sort(key=lambda x: x["n"].lower())
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({len(out)} schools, {OUT.stat().st_size // 1024} KB) from IPEDS HD{args.year}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
