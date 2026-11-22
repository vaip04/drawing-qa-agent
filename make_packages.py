#!/usr/bin/env python3
"""Generate three synthetic drawing packages for the Drawing QA Agent.

Packages:
  demo_clean  – correct in every respect (expect zero RULE_FAILED findings)
  demo_seeded – same villa with 12 planted errors + 2 review traps
  demo_mixed  – different bungalow layout with 6 planted errors

Run:  python make_packages.py
"""

import copy
import csv
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Polygon

PACKAGES_DIR = Path("packages")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def rect(x, y, w, h):
    """Rectangle polygon vertices at (x,y) with width w, height h."""
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def poly_area(verts):
    """Polygon area via Shapely."""
    return Polygon(verts).area


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def draw_plan(rooms, floor, path):
    """Draw room polygons for one floor and save as PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    for r in rooms:
        if r["floor"] != floor:
            continue
        verts = r["polygon"]
        poly = plt.Polygon(verts, fill=True, facecolor="#e8f0fe",
                           edgecolor="#333", linewidth=1.5)
        ax.add_patch(poly)
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        area = poly_area(verts)
        ax.text(cx, cy, f"{r['name']}\n{area:.0f} sqft",
                ha="center", va="center", fontsize=7, weight="bold")
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_title(f"Floor {floor} Plan", fontsize=12)
    ax.set_xlabel("x (feet)")
    ax.set_ylabel("y (feet)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Villa project data (used for demo_clean and demo_seeded)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VILLA_BRIEF = {
    "project": "DemoVilla",
    "brief_version": "v2",
    "plot": {
        "w": 50, "d": 80,
        "setbacks": {"front": 15, "rear": 10, "left": 5, "right": 5}
    },
    "limits": {
        "max_builtup_sqft": 2200,
        "max_ground_coverage_pct": 55,
        "floors": 2
    },
    "required_rooms": [
        {"name": "Living Room",     "floor": 0, "min_area_sqft": 250, "count": 1},
        {"name": "Dining Room",     "floor": 0, "min_area_sqft": 120, "count": 1},
        {"name": "Kitchen",         "floor": 0, "min_area_sqft": 80,  "count": 1},
        {"name": "Master Bedroom",  "floor": 0, "min_area_sqft": 180, "count": 1},
        {"name": "Toilet",          "floor": 0, "min_area_sqft": 35,  "count": 2},
        {"name": "Staircase",       "floor": 0, "min_area_sqft": 50,  "count": 1},
        {"name": "Bedroom",         "floor": 1, "min_area_sqft": 150, "count": 2},
        {"name": "Study",           "floor": 1, "min_area_sqft": 80,  "count": 1},
        {"name": "Toilet",          "floor": 1, "min_area_sqft": 35,  "count": 2},
        {"name": "Passage",         "floor": 1, "min_area_sqft": 35,  "count": 1},
        {"name": "Balcony",         "floor": 1, "min_area_sqft": 50,  "count": 1},
        {"name": "Staircase",       "floor": 1, "min_area_sqft": 50,  "count": 1},
    ]
}

VILLA_ROOMS = [
    # Ground floor
    {"room_id": "G01", "floor": 0, "name": "Living Room",    "polygon": rect(0,  0, 20, 15)},   # 300
    {"room_id": "G02", "floor": 0, "name": "Dining Room",    "polygon": rect(20, 0, 12, 12)},   # 144
    {"room_id": "G03", "floor": 0, "name": "Kitchen",        "polygon": rect(20, 12, 10, 10)},  # 100
    {"room_id": "G04", "floor": 0, "name": "Master Bedroom", "polygon": rect(0, 15, 14, 15)},   # 210
    {"room_id": "G05", "floor": 0, "name": "Toilet 1",       "polygon": rect(30, 12, 8, 6)},    # 48
    {"room_id": "G06", "floor": 0, "name": "Toilet 2",       "polygon": rect(30, 18, 7, 6)},    # 42
    {"room_id": "G07", "floor": 0, "name": "Passage",        "polygon": rect(14, 15, 6, 9)},    # 54
    {"room_id": "G08", "floor": 0, "name": "Staircase",      "polygon": rect(32, 0,  8, 8)},    # 64
    # First floor
    {"room_id": "F01", "floor": 1, "name": "Bedroom 2",      "polygon": rect(0,  0, 16, 14)},   # 224
    {"room_id": "F02", "floor": 1, "name": "Bedroom 3",      "polygon": rect(16, 0, 14, 14)},   # 196
    {"room_id": "F03", "floor": 1, "name": "Study",          "polygon": rect(0, 14, 10, 10)},   # 100
    {"room_id": "F04", "floor": 1, "name": "Toilet 3",       "polygon": rect(30, 0,  8,  6)},   # 48
    {"room_id": "F05", "floor": 1, "name": "Toilet 4",       "polygon": rect(30, 6,  7,  6)},   # 42
    {"room_id": "F06", "floor": 1, "name": "Passage",        "polygon": rect(10, 14, 6,  8)},   # 48
    {"room_id": "F07", "floor": 1, "name": "Balcony",        "polygon": rect(0, 24, 12,  6)},   # 72
    {"room_id": "F08", "floor": 1, "name": "Staircase",      "polygon": rect(16, 14, 8,  8)},   # 64
]

VILLA_SHEETS = [
    {"sheet_no": "A101", "title": "Ground Floor Plan",    "brief_version": "v2",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": True,
     "rooms_dimensioned": "Living Room;Dining Room;Kitchen;Master Bedroom;Toilet 1;Toilet 2;Passage;Staircase"},
    {"sheet_no": "A102", "title": "First Floor Plan",     "brief_version": "v2",
     "revision_index": "C", "revision_titleblock": "C",
     "has_overall_dims": True,
     "rooms_dimensioned": "Bedroom 2;Bedroom 3;Study;Toilet 3;Toilet 4;Passage;Balcony;Staircase"},
    {"sheet_no": "A201", "title": "Sections",             "brief_version": "v2",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
    {"sheet_no": "A202", "title": "Elevations",           "brief_version": "v2",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
    {"sheet_no": "A301", "title": "Door & Window Details", "brief_version": "v2",
     "revision_index": "B", "revision_titleblock": "B",
     "has_overall_dims": False, "rooms_dimensioned": ""},
    {"sheet_no": "A401", "title": "Kitchen Detail",       "brief_version": "v2",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
    {"sheet_no": "A501", "title": "Staircase Detail",     "brief_version": "v2",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
]

VILLA_CALLOUTS = [
    {"on_sheet": "A101", "callout_type": "section", "label": "A",
     "target_sheet": "A201", "target_view": "Section A"},
    {"on_sheet": "A101", "callout_type": "section", "label": "B",
     "target_sheet": "A201", "target_view": "Section B"},
    {"on_sheet": "A101", "callout_type": "detail",  "label": "1",
     "target_sheet": "A401", "target_view": "Kitchen Detail"},
    {"on_sheet": "A102", "callout_type": "detail",  "label": "2",
     "target_sheet": "A501", "target_view": "Staircase Detail"},
    {"on_sheet": "A201", "callout_type": "detail",  "label": "3",
     "target_sheet": "A301", "target_view": "Window Head Detail"},
]

VILLA_OPENINGS = [
    {"tag": "D01", "type": "door",   "floor": 0, "room": "Living Room",    "width_mm": 1200, "height_mm": 2100},
    {"tag": "D02", "type": "door",   "floor": 0, "room": "Kitchen",        "width_mm": 900,  "height_mm": 2100},
    {"tag": "D03", "type": "door",   "floor": 0, "room": "Toilet 1",       "width_mm": 750,  "height_mm": 2100},
    {"tag": "D04", "type": "door",   "floor": 0, "room": "Toilet 2",       "width_mm": 750,  "height_mm": 2100},
    {"tag": "D05", "type": "door",   "floor": 1, "room": "Bedroom 2",      "width_mm": 900,  "height_mm": 2100},
    {"tag": "D06", "type": "door",   "floor": 1, "room": "Bedroom 3",      "width_mm": 900,  "height_mm": 2100},
    {"tag": "D07", "type": "door",   "floor": 1, "room": "Study",          "width_mm": 900,  "height_mm": 2100},
    {"tag": "W01", "type": "window", "floor": 0, "room": "Living Room",    "width_mm": 1800, "height_mm": 1500},
    {"tag": "W02", "type": "window", "floor": 0, "room": "Kitchen",        "width_mm": 1200, "height_mm": 1200},
    {"tag": "W03", "type": "window", "floor": 0, "room": "Master Bedroom", "width_mm": 1500, "height_mm": 1500},
    {"tag": "W04", "type": "window", "floor": 1, "room": "Bedroom 2",      "width_mm": 1200, "height_mm": 1500},
    {"tag": "W05", "type": "window", "floor": 1, "room": "Bedroom 3",      "width_mm": 1200, "height_mm": 1500},
]

VILLA_SCHEDULE = [
    {"tag": o["tag"], "type": o["type"], "width_mm": o["width_mm"], "height_mm": o["height_mm"]}
    for o in VILLA_OPENINGS
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bungalow project data (used for demo_mixed)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BUNGALOW_BRIEF = {
    "project": "DemoBungalow",
    "brief_version": "v1",
    "plot": {
        "w": 40, "d": 60,
        "setbacks": {"front": 10, "rear": 8, "left": 4, "right": 4}
    },
    "limits": {
        "max_builtup_sqft": 1200,
        "max_ground_coverage_pct": 35,
        "floors": 1
    },
    "required_rooms": [
        {"name": "Living Room",    "floor": 0, "min_area_sqft": 200, "count": 1},
        {"name": "Kitchen-Dining", "floor": 0, "min_area_sqft": 150, "count": 1},
        {"name": "Bedroom",        "floor": 0, "min_area_sqft": 140, "count": 3},
        {"name": "Toilet",         "floor": 0, "min_area_sqft": 35,  "count": 2},
        {"name": "Porch",          "floor": 0, "min_area_sqft": 40,  "count": 1},
    ]
}

BUNGALOW_ROOMS = [
    {"room_id": "B01", "floor": 0, "name": "Living Room",    "polygon": rect(0,  0, 18, 14)},  # 252
    {"room_id": "B02", "floor": 0, "name": "Kitchen-Dining", "polygon": rect(18, 0, 12, 14)},  # 168
    {"room_id": "B03", "floor": 0, "name": "Bedroom 1",      "polygon": rect(0, 14, 14, 12)},  # 168
    {"room_id": "B04", "floor": 0, "name": "Bedroom 2",      "polygon": rect(14, 14, 14, 12)}, # 196
    {"room_id": "B05", "floor": 0, "name": "Toilet 1",       "polygon": rect(28, 14, 8,  6)},  # 48
    {"room_id": "B06", "floor": 0, "name": "Toilet 2",       "polygon": rect(28, 20, 8,  6)},  # 48
    {"room_id": "B07", "floor": 0, "name": "Porch",          "polygon": rect(30, 0,  6,  8)},  # 48
]

BUNGALOW_SHEETS = [
    {"sheet_no": "A101", "title": "Floor Plan",   "brief_version": "v1",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": True,
     "rooms_dimensioned": "Living Room;Kitchen-Dining;Bedroom 1;Bedroom 2;Toilet 1;Toilet 2;Porch"},
    {"sheet_no": "A201", "title": "Sections",     "brief_version": "v1",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
    {"sheet_no": "A202", "title": "Elevations",   "brief_version": "v1",
     "revision_index": "A", "revision_titleblock": "A",
     "has_overall_dims": False, "rooms_dimensioned": ""},
]

BUNGALOW_CALLOUTS = [
    {"on_sheet": "A101", "callout_type": "section", "label": "A",
     "target_sheet": "A201", "target_view": "Section A"},
    {"on_sheet": "A101", "callout_type": "section", "label": "B",
     "target_sheet": "A201", "target_view": "Section B"},
]

BUNGALOW_OPENINGS = [
    {"tag": "D01", "type": "door",   "floor": 0, "room": "Living Room",    "width_mm": 1200, "height_mm": 2100},
    {"tag": "D02", "type": "door",   "floor": 0, "room": "Bedroom 1",      "width_mm": 900,  "height_mm": 2100},
    {"tag": "D03", "type": "door",   "floor": 0, "room": "Bedroom 2",      "width_mm": 900,  "height_mm": 2100},
    {"tag": "D04", "type": "door",   "floor": 0, "room": "Toilet 1",       "width_mm": 750,  "height_mm": 2100},
    {"tag": "D05", "type": "door",   "floor": 0, "room": "Toilet 2",       "width_mm": 750,  "height_mm": 2100},
    {"tag": "W01", "type": "window", "floor": 0, "room": "Living Room",    "width_mm": 1800, "height_mm": 1500},
    {"tag": "W02", "type": "window", "floor": 0, "room": "Bedroom 1",      "width_mm": 1200, "height_mm": 1500},
    {"tag": "W03", "type": "window", "floor": 0, "room": "Kitchen-Dining", "width_mm": 1200, "height_mm": 1200},
]

BUNGALOW_SCHEDULE = [
    {"tag": o["tag"], "type": o["type"], "width_mm": o["width_mm"], "height_mm": o["height_mm"]}
    for o in BUNGALOW_OPENINGS
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Area-statement builder
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_area_statement(rooms, area_overrides=None, floor_total_overrides=None,
                         grand_total_override=None):
    """Build area_statement rows from room data.

    area_overrides: dict  room_id → overridden area
    floor_total_overrides: dict  floor → overridden total
    grand_total_override: float | None
    """
    area_overrides = area_overrides or {}
    floor_total_overrides = floor_total_overrides or {}

    floors = sorted(set(r["floor"] for r in rooms))
    rows = []
    real_floor_totals = {}

    for floor in floors:
        floor_rooms = [r for r in rooms if r["floor"] == floor]
        floor_total = 0.0
        for r in floor_rooms:
            area = area_overrides.get(r["room_id"], round(poly_area(r["polygon"]), 1))
            floor_total += area
            rows.append({
                "floor": floor,
                "room_name": r["name"],
                "area_sqft": area,
                "floor_total_sqft": "",
                "grand_total_sqft": "",
            })
        real_floor_totals[floor] = round(floor_total, 1)
        written_total = floor_total_overrides.get(floor, real_floor_totals[floor])
        rows[-1]["floor_total_sqft"] = written_total

    grand = sum(
        floor_total_overrides.get(f, real_floor_totals[f]) for f in floors
    )
    if grand_total_override is not None:
        grand = grand_total_override
    rows[-1]["grand_total_sqft"] = grand

    return rows


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Package writer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOMS_FIELDS   = ["room_id", "floor", "name", "polygon"]
AREA_FIELDS    = ["floor", "room_name", "area_sqft", "floor_total_sqft", "grand_total_sqft"]
SHEETS_FIELDS  = ["sheet_no", "title", "brief_version", "revision_index",
                  "revision_titleblock", "has_overall_dims", "rooms_dimensioned"]
CALLOUT_FIELDS = ["on_sheet", "callout_type", "label", "target_sheet", "target_view"]
OPENING_FIELDS = ["tag", "type", "floor", "room", "width_mm", "height_mm"]
SCHED_FIELDS   = ["tag", "type", "width_mm", "height_mm"]
ANSWER_FIELDS  = ["error_id", "rule_id", "group", "element", "description"]


def write_package(name, brief, rooms, area_rows, sheets, callouts,
                  openings, schedule, answer_key=None):
    """Write all files for one package."""
    pkg = PACKAGES_DIR / name
    pkg.mkdir(parents=True, exist_ok=True)

    # brief.json
    write_json(pkg / "brief.json", brief)

    # rooms.csv — serialize polygon as string
    room_rows = []
    for r in rooms:
        room_rows.append({
            "room_id": r["room_id"],
            "floor": r["floor"],
            "name": r["name"],
            "polygon": str(r["polygon"]),
        })
    write_csv(pkg / "rooms.csv", room_rows, ROOMS_FIELDS)

    # area_statement.csv
    write_csv(pkg / "area_statement.csv", area_rows, AREA_FIELDS)

    # sheets.csv
    write_csv(pkg / "sheets.csv", sheets, SHEETS_FIELDS)

    # callouts.csv
    write_csv(pkg / "callouts.csv", callouts, CALLOUT_FIELDS)

    # openings.csv
    write_csv(pkg / "openings.csv", openings, OPENING_FIELDS)

    # opening_schedule.csv
    write_csv(pkg / "opening_schedule.csv", schedule, SCHED_FIELDS)

    # answer_key.csv
    if answer_key:
        write_csv(pkg / "answer_key.csv", answer_key, ANSWER_FIELDS)

    # Plan images
    floors = sorted(set(r["floor"] for r in rooms))
    for fl in floors:
        draw_plan(rooms, fl, pkg / "plans" / f"floor_{fl}.png")

    print(f"  ✓ {name}/ written ({len(rooms)} rooms, {len(sheets)} sheets)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# demo_clean
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def gen_demo_clean():
    area_rows = build_area_statement(VILLA_ROOMS)
    write_package(
        "demo_clean",
        brief=VILLA_BRIEF,
        rooms=VILLA_ROOMS,
        area_rows=area_rows,
        sheets=VILLA_SHEETS,
        callouts=VILLA_CALLOUTS,
        openings=VILLA_OPENINGS,
        schedule=VILLA_SCHEDULE,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# demo_seeded — 12 planted errors + 2 review traps
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def gen_demo_seeded():
    # Deep-copy base data so we can mutate
    brief = copy.deepcopy(VILLA_BRIEF)
    rooms = copy.deepcopy(VILLA_ROOMS)
    sheets = copy.deepcopy(VILLA_SHEETS)
    callouts = copy.deepcopy(VILLA_CALLOUTS)
    openings = copy.deepcopy(VILLA_OPENINGS)
    schedule = copy.deepcopy(VILLA_SCHEDULE)

    # ── Error 4 (R03): remove Toilet 4 → only 1 toilet on first floor ──
    rooms = [r for r in rooms if r["room_id"] != "F05"]

    # ── Error 5 (R04): Study 20 sqft below brief min of 80 ──
    # Change Study polygon to 6×10 = 60 sqft
    for r in rooms:
        if r["room_id"] == "F03":
            r["polygon"] = rect(0, 14, 6, 10)  # 60 sqft
            break

    # ── Error 6 (R05): built-up area exceeds brief limit ──
    brief["limits"]["max_builtup_sqft"] = 1650

    # ── Review trap: name variant (R11) ──
    # Rename "Master Bedroom" → "Mstr Bed" in rooms
    for r in rooms:
        if r["room_id"] == "G04":
            r["name"] = "Mstr Bed"
            break

    # ── Review trap: narrow room (R13) ──
    # Change Passage on floor 1 to 4×14 = 56 sqft, aspect 3.5:1
    for r in rooms:
        if r["room_id"] == "F06":
            r["polygon"] = rect(10, 14, 4, 14)  # 56 sqft, ratio 3.5:1
            break

    # ── Error 1 (R01): Bedroom 2 area in statement 8% higher ──
    real_f01_area = poly_area(rect(0, 0, 16, 14))  # 224
    inflated_f01 = round(real_f01_area * 1.08, 1)   # ~241.9 → 241.9
    area_overrides = {"F01": inflated_f01}

    # ── Error 2 (R02): ground-floor total wrong ──
    # Actual GF total is 962; write 950
    floor_total_overrides = {0: 950.0}

    # ── Error 3 (R02): grand total wrong ──
    grand_total_override = 1800.0

    area_rows = build_area_statement(
        rooms,
        area_overrides=area_overrides,
        floor_total_overrides=floor_total_overrides,
        grand_total_override=grand_total_override,
    )

    # ── Error 7 (R06): two sheets carry brief_version v1 ──
    for s in sheets:
        if s["sheet_no"] in ("A201", "A301"):
            s["brief_version"] = "v1"

    # ── Error 8 (R07): Section callout A → non-existent sheet A601 ──
    for c in callouts:
        if c["label"] == "A" and c["on_sheet"] == "A101":
            c["target_sheet"] = "A601"
            break

    # ── Error 9 (R08): D07 on plan but missing from schedule ──
    schedule = [s for s in schedule if s["tag"] != "D07"]

    # ── Error 10 (R08): W04 width 1200 on plan, 1500 in schedule ──
    for s in schedule:
        if s["tag"] == "W04":
            s["width_mm"] = 1500
            break

    # ── Error 11 (R09): A102 revision index C, titleblock B ──
    for s in sheets:
        if s["sheet_no"] == "A102":
            s["revision_titleblock"] = "B"
            break

    # ── Error 12 (R10): Kitchen not dimensioned on A101 ──
    for s in sheets:
        if s["sheet_no"] == "A101":
            dims = s["rooms_dimensioned"].split(";")
            dims = [d for d in dims if d.strip() != "Kitchen"]
            s["rooms_dimensioned"] = ";".join(dims)
            break

    # Answer key
    answer_key = [
        {"error_id": 1,  "rule_id": "R01", "group": "RULE_FAILED",
         "description": "Bedroom 2 area on statement 8% higher than polygon (224 vs 241.9)"},
        {"error_id": 2,  "rule_id": "R02", "group": "RULE_FAILED",
         "description": "Ground-floor total 950 != sum of room areas 962"},
        {"error_id": 3,  "rule_id": "R02", "group": "RULE_FAILED",
         "description": "Grand total 1800 != sum of floor totals"},
        {"error_id": 4,  "rule_id": "R03", "group": "RULE_FAILED",
         "description": "Brief requires 2 toilets on floor 1; only 1 exists"},
        {"error_id": 5,  "rule_id": "R04", "group": "RULE_FAILED",
         "description": "Study area 60 sqft is 20 below brief minimum 80"},
        {"error_id": 6,  "rule_id": "R05", "group": "RULE_FAILED",
         "description": "Built-up area exceeds brief limit of 1650 sqft"},
        {"error_id": 7,  "rule_id": "R06", "group": "RULE_FAILED",
         "description": "Sheets A201, A301 carry brief_version v1; brief is v2"},
        {"error_id": 8,  "rule_id": "R07", "group": "RULE_FAILED",
         "description": "Section callout A on A101 targets non-existent sheet A601"},
        {"error_id": 9,  "rule_id": "R08", "group": "RULE_FAILED",
         "description": "Door D07 on plan but missing from schedule"},
        {"error_id": 10, "rule_id": "R08", "group": "RULE_FAILED",
         "description": "Window W04 width 1200mm on plan vs 1500mm in schedule"},
        {"error_id": 11, "rule_id": "R09", "group": "RULE_FAILED",
         "description": "Sheet A102 revision index C != titleblock revision B"},
        {"error_id": 12, "rule_id": "R10", "group": "RULE_FAILED",
         "description": "Kitchen not dimensioned on sheet A101"},
    ]

    # element = the drawing element each planted error is on (";" = error spans several)
    for row, el in zip(answer_key, ['Bedroom 2', 'Floor 0 total', 'Grand total', 'Toilet (floor 1)', 'Study', 'Built-up area', 'A201;A301', 'section A', 'D07', 'W04', 'A102', 'Kitchen']):
        row["element"] = el

    write_package(
        "demo_seeded",
        brief=brief,
        rooms=rooms,
        area_rows=area_rows,
        sheets=sheets,
        callouts=callouts,
        openings=openings,
        schedule=schedule,
        answer_key=answer_key,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# demo_mixed — different layout, 6 planted errors
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def gen_demo_mixed():
    brief = copy.deepcopy(BUNGALOW_BRIEF)
    rooms = copy.deepcopy(BUNGALOW_ROOMS)
    sheets = copy.deepcopy(BUNGALOW_SHEETS)
    callouts = copy.deepcopy(BUNGALOW_CALLOUTS)
    openings = copy.deepcopy(BUNGALOW_OPENINGS)
    schedule = copy.deepcopy(BUNGALOW_SCHEDULE)

    # Actual areas (unchanged):
    # B01 Living=252, B02 KD=168, B03 Bed1=168, B04 Bed2=196,
    # B05 T1=48, B06 T2=48, B07 Porch=48
    # Total = 928;  plot=40×60=2400;  coverage=928/2400=38.7%

    # ── Error 1 (R01): Living room area on statement 6% higher ──
    real_b01 = poly_area(rect(0, 0, 18, 14))  # 252
    inflated_b01 = round(real_b01 * 1.06, 1)   # 267.1

    # ── Error 2 (R02): floor total arithmetic error ──
    floor_total_overrides = {0: 900.0}  # actual ~928

    area_rows = build_area_statement(
        rooms,
        area_overrides={"B01": inflated_b01},
        floor_total_overrides=floor_total_overrides,
    )

    # ── Error 3 (R03): brief requires 3 bedrooms, only 2 exist ──
    # (already the case: brief says count=3, rooms has Bedroom 1 and 2)

    # ── Error 4 (R05): ground coverage 38.7% > limit 35% ──
    # (already the case with the brief limit)

    # ── Error 5 (R07): callout to non-existent sheet A301 ──
    callouts.append({
        "on_sheet": "A101", "callout_type": "detail", "label": "1",
        "target_sheet": "A301", "target_view": "Window Detail"
    })

    # ── Error 6 (R08): Window W02 size mismatch ──
    for s in schedule:
        if s["tag"] == "W02":
            s["width_mm"] = 1000  # plan says 1200
            break

    answer_key = [
        {"error_id": 1, "rule_id": "R01", "group": "RULE_FAILED",
         "description": "Living Room area on statement 6% higher than polygon (252 vs 267.1)"},
        {"error_id": 2, "rule_id": "R02", "group": "RULE_FAILED",
         "description": "Floor total 900 != sum of room areas ~943"},
        {"error_id": 3, "rule_id": "R03", "group": "RULE_FAILED",
         "description": "Brief requires 3 bedrooms on floor 0; only 2 exist"},
        {"error_id": 4, "rule_id": "R05", "group": "RULE_FAILED",
         "description": "Ground coverage 38.7% exceeds brief limit 35%"},
        {"error_id": 5, "rule_id": "R07", "group": "RULE_FAILED",
         "description": "Detail callout 1 on A101 targets non-existent sheet A301"},
        {"error_id": 6, "rule_id": "R08", "group": "RULE_FAILED",
         "description": "Window W02 width 1200mm on plan vs 1000mm in schedule"},
    ]

    for row, el in zip(answer_key, ['Living Room', 'Floor 0 total', 'Bedroom (floor 0)', 'Ground coverage', 'detail 1', 'W02']):
        row["element"] = el

    write_package(
        "demo_mixed",
        brief=brief,
        rooms=rooms,
        area_rows=area_rows,
        sheets=sheets,
        callouts=callouts,
        openings=openings,
        schedule=schedule,
        answer_key=answer_key,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print("Generating drawing packages …")
    PACKAGES_DIR.mkdir(exist_ok=True)
    gen_demo_clean()
    gen_demo_seeded()
    gen_demo_mixed()
    print("Done. All packages written to packages/")


if __name__ == "__main__":
    main()
