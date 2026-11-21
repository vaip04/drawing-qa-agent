#!/usr/bin/env python3
"""Load a drawing package from disk into a dict of DataFrames / dicts.

Usage:
    from src.loader import load_package
    pkg = load_package("packages/demo_clean")
"""

import json
import csv
from pathlib import Path
import pandas as pd
import yaml


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a CSV, returning an empty DataFrame if the file is missing."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, skipinitialspace=True)


def load_package(pkg_path: str | Path) -> dict:
    """Load all files in a drawing package folder.

    Returns a dict with keys:
        name        – package folder name (str)
        path        – resolved Path
        brief       – dict from brief.json
        rooms       – DataFrame (room_id, floor, name, polygon)
        area_stmt   – DataFrame (floor, room_name, area_sqft, floor_total_sqft, grand_total_sqft)
        sheets      – DataFrame (sheet_no, title, brief_version, revision_index, revision_titleblock, has_overall_dims, rooms_dimensioned)
        callouts    – DataFrame (on_sheet, callout_type, label, target_sheet, target_view)
        openings    – DataFrame (tag, type, floor, room, width_mm, height_mm)
        schedule    – DataFrame (tag, type, width_mm, height_mm)
        answer_key  – DataFrame (or empty)   – only in seeded/mixed
        plan_images – list of Path to PNG files
    """
    pkg_path = Path(pkg_path).resolve()
    if not pkg_path.exists():
        raise FileNotFoundError(f"Package folder not found: {pkg_path}")

    # Brief
    with open(pkg_path / "brief.json", "r") as f:
        brief = json.load(f)

    # CSVs
    rooms = _read_csv(pkg_path / "rooms.csv")
    area_stmt = _read_csv(pkg_path / "area_statement.csv")
    sheets = _read_csv(pkg_path / "sheets.csv")
    callouts = _read_csv(pkg_path / "callouts.csv")
    openings = _read_csv(pkg_path / "openings.csv")
    schedule = _read_csv(pkg_path / "opening_schedule.csv")
    answer_key = _read_csv(pkg_path / "answer_key.csv")

    # Parse polygon strings back to lists of tuples
    if "polygon" in rooms.columns and len(rooms) > 0:
        rooms["polygon"] = rooms["polygon"].apply(_parse_polygon)

    # Parse boolean-ish columns
    if "has_overall_dims" in sheets.columns:
        sheets["has_overall_dims"] = sheets["has_overall_dims"].map(
            lambda v: str(v).strip().lower() in ("true", "1", "yes")
        )

    # Parse rooms_dimensioned to lists
    if "rooms_dimensioned" in sheets.columns:
        sheets["rooms_dimensioned"] = sheets["rooms_dimensioned"].fillna("").apply(
            lambda v: [s.strip() for s in str(v).split(";") if s.strip()]
        )

    # Plan images
    plans_dir = pkg_path / "plans"
    plan_images = sorted(plans_dir.glob("*.png")) if plans_dir.exists() else []

    return {
        "name": pkg_path.name,
        "path": pkg_path,
        "brief": brief,
        "rooms": rooms,
        "area_stmt": area_stmt,
        "sheets": sheets,
        "callouts": callouts,
        "openings": openings,
        "schedule": schedule,
        "answer_key": answer_key,
        "plan_images": plan_images,
    }


def load_rules(rules_path: str | Path | None = None) -> dict:
    """Load tolerances and thresholds from rules.yaml."""
    if rules_path is None:
        rules_path = Path(__file__).parent.parent / "rules.yaml"
    rules_path = Path(rules_path)
    if not rules_path.exists():
        # Return defaults
        return {
            "tolerances": {
                "area_mismatch_pct": 2.0,
                "builtup_tolerance_pct": 0.0,
                "coverage_tolerance_pct": 0.0,
                "name_match_threshold": 70,
                "narrow_aspect_ratio": 3.0,
                "opening_size_tolerance_mm": 0,
            }
        }
    with open(rules_path, "r") as f:
        return yaml.safe_load(f)


def _parse_polygon(val) -> list[tuple[float, float]]:
    """Parse a polygon string like '[(0,0),(10,0),(10,5),(0,5)]' to a list of (x,y) tuples."""
    import ast
    if isinstance(val, list):
        return val
    try:
        parsed = ast.literal_eval(str(val))
        return [(float(x), float(y)) for x, y in parsed]
    except (ValueError, SyntaxError):
        return []
