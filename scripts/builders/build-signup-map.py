"""Build the athlete-signup hero map (inline SVG) into athlete-signup/index.html.

Data: athlete-signup/_data/map-data.json (dotted lower 48 + national outline
projected with Albers USA from the Census state file, the ten campus channels
at their IPEDS campus coordinates, Durham as the hub, and one entry per school
on the applicant list with a count).

The SVG is written between <!-- signup-map:start --> and <!-- signup-map:end -->
so the rest of the page is untouched. Run from the repo root:
    python scripts/builders/build-signup-map.py
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "athlete-signup" / "_data" / "map-data.json"
PAGE = ROOT / "athlete-signup" / "index.html"
START, END = "<!-- signup-map:start -->", "<!-- signup-map:end -->"

NC = {"truebluetv", "chapelhilltv", "redpacktv", "goldsalemtv"}
LABEL_POS = {
    "saltcitytv": (843, 150, "middle"),
    "goldendometv": (678, 208, "middle"),
    "dorecitytv": (681, 386, "middle"),
    "starkvilletv": (649, 452, "middle"),
    "brazostv": (470, 468, "end"),
    "collegestationtv": (520, 522, "start"),
    "goldsalemtv": (758, 312, "end"),
    "chapelhilltv": (870, 378, "start"),
    "redpacktv": (870, 400, "start"),
    "truebluetv": (870, 356, "start"),
}


def arc(c, hub):
    x1, y1, x2, y2 = c["x"], c["y"], hub["x"], hub["y"]
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 8:
        return ""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    lift = min(120, dist * 0.32)
    nx, ny = -dy / dist, dx / dist
    if ny > 0:
        nx, ny = -nx, -ny
    return f"M{x1} {y1}Q{mx + nx * lift:.1f} {my + ny * lift:.1f} {x2} {y2}"


def build_svg(d: dict) -> str:
    hub = d["hub"]
    out = [f'<svg class="usmap" viewBox="0 0 {d["W"]} {d["H"]}" role="img" '
           'aria-label="Map of the United States: NIL TV campus channels and applicant schools, connected to Durham, North Carolina">']
    out.append(f'<path class="land" d="{d["dots"]}"/>' if isinstance(d["dots"], str) else
               '<path class="land" d="' + "".join(f"M{x-1.55:.1f} {y:.1f}a1.55 1.55 0 1 0 3.1 0a1.55 1.55 0 1 0 -3.1 0" for x, y in d["dots"]) + '"/>')
    out.append(f'<path class="outline" d="{d["outline"]}"/>')
    for a in sorted(d["applicants"], key=lambda a: -a["n"]):
        r = 2.2 + min(9, math.sqrt(a["n"]) * 1.6)
        out.append(f'<circle class="app" cx="{a["x"]}" cy="{a["y"]}" r="{r:.1f}"><title>{html.escape(a["school"])}</title></circle>')
    for c in d["channels"]:
        p = arc(c, hub)
        if p:
            out.append(f'<path class="arc" d="{p}"/>')
    for c in d["channels"]:
        if c["slug"] == "truebluetv":
            continue
        out.append(f'<circle class="pin" cx="{c["x"]}" cy="{c["y"]}" r="4"/>')
    for c in d["channels"]:
        lx, ly, anchor = LABEL_POS[c["slug"]]
        if c["slug"] in NC:
            out.append(f'<line class="leader" x1="{c["x"]}" y1="{c["y"]}" x2="{lx + (-6 if anchor == "start" else 6)}" y2="{ly - 4}"/>')
        out.append(f'<text class="lbl" x="{lx}" y="{ly}" text-anchor="{anchor}">{html.escape(c["label"].upper())}</text>')
    x, y = hub["x"], hub["y"]
    out.append(f'<g class="hub"><circle class="hub-ring r1" cx="{x}" cy="{y}" r="14"/><circle class="hub-ring r2" cx="{x}" cy="{y}" r="26"/>'
               f'<circle class="hub-core" cx="{x}" cy="{y}" r="6.5"/><text class="hub-lbl" x="{x}" y="{y - 34}" text-anchor="middle">NIL TV · DURHAM</text></g>')
    out.append("</svg>")
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print the SVG instead of writing the page")
    args = ap.parse_args()
    d = json.loads(DATA.read_text(encoding="utf-8"))
    svg = build_svg(d)
    if args.print:
        print(svg)
        return 0
    page = PAGE.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in page else "\n"
    i, j = page.find(START), page.find(END)
    if i < 0 or j < 0:
        raise SystemExit(f"markers {START} / {END} not found in {PAGE}")
    page = page[: i + len(START)] + nl + svg + nl + page[j:]
    PAGE.write_text(page, encoding="utf-8", newline="")
    print(f"signup map: {len(d['applicants'])} applicant schools, {len(d['channels'])} channels, {len(svg) // 1024} KB into {PAGE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
