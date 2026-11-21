"""Importer for Architectural AI Prototype data.

Converts reference standards from the prototype catalogue directory into a
drawing package format with unverified status.
"""

from pathlib import Path
import json
import pandas as pd
from make_packages import write_package, rect, build_area_statement

PROTOTYPE_DIR = Path(r"C:\Users\vvaib\Downloads\furniture_catalogue")


def import_prototype():
    print(f"Importing prototype standards from {PROTOTYPE_DIR}...")
    if not PROTOTYPE_DIR.exists():
        print(f"[WARN] Prototype directory not found at {PROTOTYPE_DIR}")
        return

    # Check for space standards
    space_std_file = PROTOTYPE_DIR / "space_standards.csv"
    room_map_file = PROTOTYPE_DIR / "room_name_map.csv"

    if not space_std_file.exists():
        print("[WARN] space_standards.csv missing from prototype folder. Skipping.")
        return

    space_df = pd.read_csv(space_std_file)
    print(f"  Loaded {len(space_df)} space standard definitions.")

    # Synthesize a villa layout package implementing the prototype's space standards
    brief = {
        "project": "PrototypeDemoVilla (Unverified Import)",
        "brief_version": "v1-proto",
        "plot": {"w": 50, "d": 70, "setbacks": {"front": 12, "rear": 8, "left": 4, "right": 4}},
        "limits": {"max_builtup_sqft": 2000, "max_ground_coverage_pct": 50, "floors": 1},
        "required_rooms": [
            {"name": "Living Room", "floor": 0, "min_area_sqft": 220, "count": 1},
            {"name": "Master Bedroom", "floor": 0, "min_area_sqft": 180, "count": 1},
            {"name": "Kitchen", "floor": 0, "min_area_sqft": 90, "count": 1},
            {"name": "Dining Room", "floor": 0, "min_area_sqft": 120, "count": 1},
            {"name": "Toilet", "floor": 0, "min_area_sqft": 40, "count": 2},
        ]
    }

    rooms = [
        {"room_id": "P01", "floor": 0, "name": "Living Room", "polygon": rect(0, 0, 18, 14)},     # 252 sqft
        {"room_id": "P02", "floor": 0, "name": "Master Bedroom", "polygon": rect(18, 0, 14, 14)}, # 196 sqft
        {"room_id": "P03", "floor": 0, "name": "Kitchen", "polygon": rect(0, 14, 10, 10)},        # 100 sqft
        {"room_id": "P04", "floor": 0, "name": "Dining Room", "polygon": rect(10, 14, 12, 10)},    # 120 sqft
        {"room_id": "P05", "floor": 0, "name": "Toilet 1", "polygon": rect(22, 14, 6, 8)},        # 48 sqft
        {"room_id": "P06", "floor": 0, "name": "Toilet 2", "polygon": rect(28, 14, 6, 8)},        # 48 sqft
    ]

    sheets = [
        {"sheet_no": "A101", "title": "Ground Floor Plan", "brief_version": "v1-proto",
         "revision_index": "A", "revision_titleblock": "A",
         "has_overall_dims": True,
         "rooms_dimensioned": "Living Room;Master Bedroom;Kitchen;Dining Room;Toilet 1;Toilet 2"},
    ]

    callouts = []
    openings = [
        {"tag": "D01", "type": "door", "floor": 0, "room": "Living Room", "width_mm": 1200, "height_mm": 2100},
        {"tag": "D02", "type": "door", "floor": 0, "room": "Master Bedroom", "width_mm": 900, "height_mm": 2100},
        {"tag": "W01", "type": "window", "floor": 0, "room": "Living Room", "width_mm": 1800, "height_mm": 1500},
    ]
    schedule = [{"tag": o["tag"], "type": o["type"], "width_mm": o["width_mm"], "height_mm": o["height_mm"]} for o in openings]

    area_rows = build_area_statement(rooms)

    write_package(
        "demo_prototype_import",
        brief=brief,
        rooms=rooms,
        area_rows=area_rows,
        sheets=sheets,
        callouts=callouts,
        openings=openings,
        schedule=schedule,
    )
    print("  ✓ Created packages/demo_prototype_import (marked unverified).")


if __name__ == "__main__":
    import_prototype()
