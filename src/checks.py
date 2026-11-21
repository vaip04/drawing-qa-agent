"""Drawing-set rule checks.

Each check_RXX function takes a loaded package dict and rules config,
and returns a list of finding dicts:
  {finding_id, rule_id, group, severity, sheet_no, element, issue, evidence, values}

Group is RULE_FAILED or NEEDS_REVIEW.
"""

from __future__ import annotations
import uuid
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from thefuzz import fuzz

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _fid():
    """Generate a unique finding ID."""
    return str(uuid.uuid4())[:8]


def _poly_area(verts):
    """Area from vertex list."""
    if not verts or len(verts) < 3:
        return 0.0
    return Polygon(verts).area


def _aspect_ratio(verts):
    """Aspect ratio of the minimum bounding rectangle."""
    if not verts or len(verts) < 3:
        return 1.0
    p = Polygon(verts)
    mbr = p.minimum_rotated_rectangle
    coords = list(mbr.exterior.coords)
    d1 = ((coords[0][0] - coords[1][0])**2 + (coords[0][1] - coords[1][1])**2) ** 0.5
    d2 = ((coords[1][0] - coords[2][0])**2 + (coords[1][1] - coords[2][1])**2) ** 0.5
    if min(d1, d2) == 0:
        return float("inf")
    return max(d1, d2) / min(d1, d2)


def _match_name(room_name: str, brief_name: str, threshold: int = 70) -> bool:
    """Check whether a room name matches a brief requirement name.

    E.g., 'Toilet 1' matches 'Toilet'; 'Bedroom 2' matches 'Bedroom'.
    Must not accidentally match 'Dining Room' to 'Living Room'.
    """
    rn = room_name.strip().lower()
    bn = brief_name.strip().lower()
    # Exact match
    if rn == bn:
        return True
    # If room name starts with brief name followed by space or digit (e.g. "Toilet 1", "Bedroom 2")
    if rn.startswith(bn) and len(rn) > len(bn) and rn[len(bn)] in (" ", "-", "_", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
        return True
    # Specific known variants (e.g. Master Bedroom / Mstr Bed)
    if ("mstr" in rn and "master" in bn) or ("master" in rn and "mstr" in bn):
        if "bed" in rn and "bed" in bn:
            return True
    # For general fuzzy, require high similarity and same starting token to prevent cross-matching
    if fuzz.token_sort_ratio(rn, bn) >= threshold:
        rn_first = rn.split()[0] if rn.split() else ""
        bn_first = bn.split()[0] if bn.split() else ""
        if rn_first and bn_first and (rn_first == bn_first or fuzz.ratio(rn_first, bn_first) >= 75):
            return True
    return False


# ──────────────────────────────────────────────────────────────────
# R01: Room area from polygon vs area statement (tolerance %)
# ──────────────────────────────────────────────────────────────────

def check_R01(pkg, rules):
    tol = rules.get("tolerances", {}).get("area_mismatch_pct", 2.0)
    findings = []
    rooms = pkg["rooms"]
    area_stmt = pkg["area_stmt"]

    if rooms.empty or area_stmt.empty:
        return findings

    for _, room in rooms.iterrows():
        poly_a = _poly_area(room["polygon"])
        # Find matching row in area_statement by name and floor
        matches = area_stmt[
            (area_stmt["room_name"].str.strip().str.lower() == room["name"].strip().lower()) &
            (area_stmt["floor"].astype(int) == int(room["floor"]))
        ]
        if matches.empty:
            # Try fuzzy matching
            for _, stmt_row in area_stmt[area_stmt["floor"].astype(int) == int(room["floor"])].iterrows():
                if _match_name(room["name"], stmt_row["room_name"]):
                    matches = stmt_row
                    break
            if isinstance(matches, type(area_stmt)) and matches.empty:
                continue  # R08 or R11 would catch missing entries

        if hasattr(matches, 'iterrows'):
            stmt_row = matches.iloc[0]
        else:
            stmt_row = matches

        stmt_a = float(stmt_row["area_sqft"])
        if poly_a == 0:
            continue
        pct_diff = abs(stmt_a - poly_a) / poly_a * 100
        if pct_diff > tol:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R01",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": room["name"],
                "issue": f"Area on statement ({stmt_a:.1f} sqft) differs from polygon ({poly_a:.1f} sqft) by {pct_diff:.1f}%",
                "evidence": f"polygon={poly_a:.1f}, statement={stmt_a:.1f}, diff={pct_diff:.1f}%, tolerance={tol}%",
                "values": {"polygon_area": poly_a, "statement_area": stmt_a, "pct_diff": round(pct_diff, 1)},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R02: Area statement arithmetic
# ──────────────────────────────────────────────────────────────────

def check_R02(pkg, rules):
    findings = []
    area_stmt = pkg["area_stmt"]
    if area_stmt.empty:
        return findings

    floors = sorted(area_stmt["floor"].dropna().unique())
    floor_totals_written = {}

    for floor in floors:
        floor_rows = area_stmt[area_stmt["floor"] == floor]
        room_sum = floor_rows["area_sqft"].astype(float).sum()
        # Find the written floor total (last non-empty floor_total_sqft for this floor)
        ft_vals = floor_rows["floor_total_sqft"].dropna()
        ft_vals = ft_vals[ft_vals != ""]
        if ft_vals.empty:
            continue
        written_ft = float(ft_vals.iloc[-1])
        floor_totals_written[floor] = written_ft
        if abs(room_sum - written_ft) > 0.05:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R02",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": f"Floor {int(floor)} total",
                "issue": f"Room areas sum to {room_sum:.1f} but floor total says {written_ft:.1f}",
                "evidence": f"sum={room_sum:.1f}, written={written_ft:.1f}",
                "values": {"computed_sum": room_sum, "written_total": written_ft},
            })

    # Grand total check
    gt_vals = area_stmt["grand_total_sqft"].dropna()
    gt_vals = gt_vals[gt_vals != ""]
    if not gt_vals.empty:
        written_gt = float(gt_vals.iloc[-1])
        sum_ft = sum(floor_totals_written.values())
        if abs(sum_ft - written_gt) > 0.05:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R02",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": "Grand total",
                "issue": f"Floor totals sum to {sum_ft:.1f} but grand total says {written_gt:.1f}",
                "evidence": f"sum_of_floors={sum_ft:.1f}, written_grand={written_gt:.1f}",
                "values": {"computed_sum": sum_ft, "written_grand": written_gt},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R03: Every required room exists in correct count and floor
# ──────────────────────────────────────────────────────────────────

def check_R03(pkg, rules):
    findings = []
    brief = pkg["brief"]
    rooms = pkg["rooms"]
    threshold = rules.get("tolerances", {}).get("name_match_threshold", 70)

    for req in brief.get("required_rooms", []):
        req_name = req["name"]
        req_floor = req["floor"]
        req_count = req["count"]

        # Count matching rooms on the required floor
        matched = 0
        if not rooms.empty:
            for _, room in rooms.iterrows():
                if int(room["floor"]) == req_floor and _match_name(room["name"], req_name, threshold):
                    matched += 1

        if matched < req_count:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R03",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": f"{req_name} (floor {req_floor})",
                "issue": f"Brief requires {req_count} but only {matched} found",
                "evidence": f"required={req_count}, found={matched}",
                "values": {"required": req_count, "found": matched},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R04: Each required room meets brief min_area_sqft
# ──────────────────────────────────────────────────────────────────

def check_R04(pkg, rules):
    findings = []
    brief = pkg["brief"]
    rooms = pkg["rooms"]
    threshold = rules.get("tolerances", {}).get("name_match_threshold", 70)

    for req in brief.get("required_rooms", []):
        req_name = req["name"]
        req_floor = req["floor"]
        min_area = req.get("min_area_sqft", 0)
        if min_area <= 0:
            continue

        if rooms.empty:
            continue
        for _, room in rooms.iterrows():
            if int(room["floor"]) == req_floor and _match_name(room["name"], req_name, threshold):
                area = _poly_area(room["polygon"])
                if area < min_area:
                    findings.append({
                        "finding_id": _fid(),
                        "rule_id": "R04",
                        "group": "RULE_FAILED",
                        "severity": "medium",
                        "sheet_no": "",
                        "element": room["name"],
                        "issue": f"Area {area:.1f} sqft is below brief minimum {min_area} sqft (short by {min_area - area:.1f})",
                        "evidence": f"area={area:.1f}, min={min_area}",
                        "values": {"area": area, "min_area": min_area},
                    })
    return findings


# ──────────────────────────────────────────────────────────────────
# R05: Built-up area and ground coverage within limits
# ──────────────────────────────────────────────────────────────────

def check_R05(pkg, rules):
    findings = []
    brief = pkg["brief"]
    rooms = pkg["rooms"]
    limits = brief.get("limits", {})
    plot = brief.get("plot", {})

    if rooms.empty:
        return findings

    # Total built-up area (sum of all polygon areas, all floors)
    total_builtup = sum(_poly_area(row["polygon"]) for _, row in rooms.iterrows())

    max_builtup = limits.get("max_builtup_sqft", float("inf"))
    bt_tol = rules.get("tolerances", {}).get("builtup_tolerance_pct", 0) / 100
    if total_builtup > max_builtup * (1 + bt_tol):
        findings.append({
            "finding_id": _fid(),
            "rule_id": "R05",
            "group": "RULE_FAILED",
            "severity": "high",
            "sheet_no": "",
            "element": "Built-up area",
            "issue": f"Total built-up {total_builtup:.1f} sqft exceeds limit {max_builtup} sqft",
            "evidence": f"builtup={total_builtup:.1f}, limit={max_builtup}",
            "values": {"builtup": total_builtup, "limit": max_builtup},
        })

    # Ground coverage (union of ground-floor polygons / plot area)
    max_cov = limits.get("max_ground_coverage_pct", 100)
    ct_tol = rules.get("tolerances", {}).get("coverage_tolerance_pct", 0) / 100
    plot_area = plot.get("w", 0) * plot.get("d", 0)
    if plot_area > 0:
        gf_polys = []
        for _, row in rooms.iterrows():
            if int(row["floor"]) == 0 and row["polygon"]:
                try:
                    gf_polys.append(Polygon(row["polygon"]))
                except Exception:
                    pass
        if gf_polys:
            footprint = unary_union(gf_polys)
            coverage_pct = (footprint.area / plot_area) * 100
            if coverage_pct > max_cov * (1 + ct_tol):
                findings.append({
                    "finding_id": _fid(),
                    "rule_id": "R05",
                    "group": "RULE_FAILED",
                    "severity": "high",
                    "sheet_no": "",
                    "element": "Ground coverage",
                    "issue": f"Coverage {coverage_pct:.1f}% exceeds limit {max_cov}%",
                    "evidence": f"coverage={coverage_pct:.1f}%, limit={max_cov}%",
                    "values": {"coverage_pct": round(coverage_pct, 1), "limit_pct": max_cov},
                })
    return findings


# ──────────────────────────────────────────────────────────────────
# R06: Sheet brief_version matches current brief version
# ──────────────────────────────────────────────────────────────────

def check_R06(pkg, rules):
    findings = []
    brief = pkg["brief"]
    sheets = pkg["sheets"]
    current_ver = brief.get("brief_version", "")

    if sheets.empty:
        return findings

    for _, sheet in sheets.iterrows():
        sv = str(sheet.get("brief_version", "")).strip()
        if sv and sv != current_ver:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R06",
                "group": "RULE_FAILED",
                "severity": "medium",
                "sheet_no": sheet["sheet_no"],
                "element": sheet["sheet_no"],
                "issue": f"Sheet has brief_version '{sv}' but current brief is '{current_ver}'",
                "evidence": f"sheet_version={sv}, brief_version={current_ver}",
                "values": {"sheet_version": sv, "brief_version": current_ver},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R07: Every callout points to an existing sheet and view
# ──────────────────────────────────────────────────────────────────

def check_R07(pkg, rules):
    findings = []
    callouts = pkg["callouts"]
    sheets = pkg["sheets"]

    if callouts.empty:
        return findings

    sheet_nos = set()
    if not sheets.empty:
        sheet_nos = set(sheets["sheet_no"].astype(str).str.strip())

    for _, co in callouts.iterrows():
        target = str(co["target_sheet"]).strip()
        if target not in sheet_nos:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R07",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": co["on_sheet"],
                "element": f"{co['callout_type']} {co['label']}",
                "issue": f"Callout points to sheet {target} which does not exist",
                "evidence": f"on_sheet={co['on_sheet']}, target={target}",
                "values": {"target_sheet": target},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R08: Opening tags and sizes match between plans and schedule
# ──────────────────────────────────────────────────────────────────

def check_R08(pkg, rules):
    findings = []
    openings = pkg["openings"]
    schedule = pkg["schedule"]
    size_tol = rules.get("tolerances", {}).get("opening_size_tolerance_mm", 0)

    if openings.empty and schedule.empty:
        return findings

    plan_tags = {}
    if not openings.empty:
        for _, o in openings.iterrows():
            plan_tags[o["tag"]] = o

    sched_tags = {}
    if not schedule.empty:
        for _, s in schedule.iterrows():
            sched_tags[s["tag"]] = s

    # Tags on plan but missing from schedule
    for tag, o in plan_tags.items():
        if tag not in sched_tags:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R08",
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": tag,
                "issue": f"{o['type'].title()} {tag} is on the plan but missing from the schedule",
                "evidence": f"tag={tag}, on_plan=True, in_schedule=False",
                "values": {"tag": tag, "location": "plan_only"},
            })

    # Tags in schedule but missing from plan
    for tag, s in sched_tags.items():
        if tag not in plan_tags:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R08",
                "group": "RULE_FAILED",
                "severity": "medium",
                "sheet_no": "",
                "element": tag,
                "issue": f"{s['type'].title()} {tag} is in the schedule but missing from the plan",
                "evidence": f"tag={tag}, on_plan=False, in_schedule=True",
                "values": {"tag": tag, "location": "schedule_only"},
            })

    # Size mismatches
    for tag in plan_tags:
        if tag in sched_tags:
            po = plan_tags[tag]
            so = sched_tags[tag]
            pw, ph = int(po["width_mm"]), int(po["height_mm"])
            sw, sh = int(so["width_mm"]), int(so["height_mm"])
            if abs(pw - sw) > size_tol or abs(ph - sh) > size_tol:
                findings.append({
                    "finding_id": _fid(),
                    "rule_id": "R08",
                    "group": "RULE_FAILED",
                    "severity": "high",
                    "sheet_no": "",
                    "element": tag,
                    "issue": f"{po['type'].title()} {tag} size mismatch: plan {pw}×{ph}mm vs schedule {sw}×{sh}mm",
                    "evidence": f"plan={pw}x{ph}, schedule={sw}x{sh}",
                    "values": {"plan_w": pw, "plan_h": ph, "sched_w": sw, "sched_h": sh},
                })
    return findings


# ──────────────────────────────────────────────────────────────────
# R09: Revision in sheet index equals titleblock revision
# ──────────────────────────────────────────────────────────────────

def check_R09(pkg, rules):
    findings = []
    sheets = pkg["sheets"]
    if sheets.empty:
        return findings

    for _, sheet in sheets.iterrows():
        ri = str(sheet.get("revision_index", "")).strip()
        rt = str(sheet.get("revision_titleblock", "")).strip()
        if ri and rt and ri != rt:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R09",
                "group": "RULE_FAILED",
                "severity": "medium",
                "sheet_no": sheet["sheet_no"],
                "element": sheet["sheet_no"],
                "issue": f"Revision index '{ri}' does not match titleblock revision '{rt}'",
                "evidence": f"index={ri}, titleblock={rt}",
                "values": {"revision_index": ri, "revision_titleblock": rt},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# R10: Plan sheets have overall dims, every room dimensioned
# ──────────────────────────────────────────────────────────────────

def check_R10(pkg, rules):
    findings = []
    sheets = pkg["sheets"]
    rooms = pkg["rooms"]
    threshold = rules.get("tolerances", {}).get("name_match_threshold", 70)

    if sheets.empty:
        return findings

    # Only check plan sheets (those that have rooms_dimensioned or has_overall_dims)
    for _, sheet in sheets.iterrows():
        is_plan = sheet.get("has_overall_dims", False) or bool(sheet.get("rooms_dimensioned"))
        if not is_plan:
            continue

        # Check overall dims
        if not sheet.get("has_overall_dims", False):
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R10",
                "group": "RULE_FAILED",
                "severity": "medium",
                "sheet_no": sheet["sheet_no"],
                "element": sheet["sheet_no"],
                "issue": "Plan sheet missing overall dimensions",
                "evidence": "has_overall_dims=False",
                "values": {},
            })

        # Check rooms dimensioned — which floor does this sheet cover?
        dims_list = sheet.get("rooms_dimensioned", [])
        if isinstance(dims_list, str):
            dims_list = [s.strip() for s in dims_list.split(";") if s.strip()]

        if not rooms.empty and dims_list:
            # Identify the floor where the majority of this sheet's dimensioned rooms reside
            matched_floors = []
            for d in dims_list:
                m = rooms[rooms["name"].str.strip().str.lower() == d.lower()]
                if not m.empty:
                    matched_floors.append(int(m.iloc[0]["floor"]))
            if matched_floors:
                # Target the primary floor for this plan sheet
                primary_floor = max(set(matched_floors), key=matched_floors.count)
                floor_rooms = rooms[rooms["floor"] == primary_floor]
                floor_room_names = set(floor_rooms["name"].str.strip())
                dims_set = {d.lower() for d in dims_list}
                for rname in floor_room_names:
                    # Check exact or fuzzy match against dimensioned list (handles name variants like Mstr Bed vs Master Bedroom)
                    is_dim = (
                        rname.lower() in dims_set or
                        any(_match_name(rname, d, threshold) for d in dims_list)
                    )
                    if not is_dim:
                        findings.append({
                            "finding_id": _fid(),
                            "rule_id": "R10",
                            "group": "RULE_FAILED",
                            "severity": "medium",
                            "sheet_no": sheet["sheet_no"],
                            "element": rname,
                            "issue": f"Room '{rname}' not dimensioned on sheet {sheet['sheet_no']}",
                            "evidence": f"room={rname}, sheet={sheet['sheet_no']}",
                            "values": {"room": rname},
                        })
    return findings


# ──────────────────────────────────────────────────────────────────
# R11: Room names consistent across rooms.csv, area statement, brief
# ──────────────────────────────────────────────────────────────────

def check_R11(pkg, rules):
    findings = []
    rooms = pkg["rooms"]
    area_stmt = pkg["area_stmt"]
    brief = pkg["brief"]
    threshold = rules.get("tolerances", {}).get("name_match_threshold", 70)

    if rooms.empty:
        return findings

    # Collect name sets
    room_names = set()
    for _, r in rooms.iterrows():
        room_names.add((r["name"].strip(), int(r["floor"])))

    stmt_names = set()
    if not area_stmt.empty:
        for _, s in area_stmt.iterrows():
            stmt_names.add((s["room_name"].strip(), int(s["floor"])))

    brief_names = set()
    for req in brief.get("required_rooms", []):
        brief_names.add(req["name"].strip())

    # Check rooms.csv names against area_statement names
    for rname, floor in room_names:
        exact_match = any(sn == rname and sf == floor for sn, sf in stmt_names)
        if not exact_match:
            # Check fuzzy match
            fuzzy_match = any(
                _match_name(rname, sn, threshold) and sf == floor
                for sn, sf in stmt_names
            )
            if fuzzy_match:
                findings.append({
                    "finding_id": _fid(),
                    "rule_id": "R11",
                    "group": "NEEDS_REVIEW",
                    "severity": "low",
                    "sheet_no": "",
                    "element": rname,
                    "issue": f"Room name '{rname}' in rooms.csv differs from area statement (fuzzy match only)",
                    "evidence": f"rooms.csv='{rname}', floor={floor}",
                    "values": {"room_name": rname, "floor": floor},
                })

    # Check rooms.csv names against brief required_rooms
    for rname, floor in room_names:
        # Find if this room matches any brief requirement
        for bname in brief_names:
            if _match_name(rname, bname, threshold) and not (
                rname.lower() == bname.lower() or rname.lower().startswith(bname.lower())
            ):
                # Fuzzy match but not exact/prefix → flag
                findings.append({
                    "finding_id": _fid(),
                    "rule_id": "R11",
                    "group": "NEEDS_REVIEW",
                    "severity": "low",
                    "sheet_no": "",
                    "element": rname,
                    "issue": f"Room name '{rname}' may be a variant of brief requirement '{bname}'",
                    "evidence": f"rooms='{rname}', brief='{bname}', score={fuzz.token_sort_ratio(rname.lower(), bname.lower())}",
                    "values": {"room_name": rname, "brief_name": bname},
                })
    return findings


# ──────────────────────────────────────────────────────────────────
# R12: Room overlaps or gaps (geometry sanity)
# ──────────────────────────────────────────────────────────────────

def check_R12(pkg, rules):
    findings = []
    rooms = pkg["rooms"]
    if rooms.empty:
        return findings

    for floor in sorted(rooms["floor"].unique()):
        floor_rooms = rooms[rooms["floor"] == floor]
        polys = []
        names = []
        for _, r in floor_rooms.iterrows():
            if r["polygon"] and len(r["polygon"]) >= 3:
                try:
                    p = Polygon(r["polygon"])
                    if p.is_valid:
                        polys.append(p)
                        names.append(r["name"])
                except Exception:
                    pass

        # Check pairwise overlaps
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                if polys[i].intersects(polys[j]):
                    inter = polys[i].intersection(polys[j])
                    if inter.area > 0.1:  # ignore touching edges
                        findings.append({
                            "finding_id": _fid(),
                            "rule_id": "R12",
                            "group": "NEEDS_REVIEW",
                            "severity": "medium",
                            "sheet_no": "",
                            "element": f"{names[i]} / {names[j]}",
                            "issue": f"Rooms overlap by {inter.area:.1f} sqft on floor {int(floor)}",
                            "evidence": f"overlap={inter.area:.1f} sqft",
                            "values": {"overlap_area": round(inter.area, 1)},
                        })
    return findings


# ──────────────────────────────────────────────────────────────────
# R13: Room aspect ratio (narrow rooms)
# ──────────────────────────────────────────────────────────────────

def check_R13(pkg, rules):
    findings = []
    rooms = pkg["rooms"]
    max_ratio = rules.get("tolerances", {}).get("narrow_aspect_ratio", 3.0)

    if rooms.empty:
        return findings

    for _, room in rooms.iterrows():
        if not room["polygon"] or len(room["polygon"]) < 3:
            continue
        ratio = _aspect_ratio(room["polygon"])
        if ratio > max_ratio:
            findings.append({
                "finding_id": _fid(),
                "rule_id": "R13",
                "group": "NEEDS_REVIEW",
                "severity": "low",
                "sheet_no": "",
                "element": room["name"],
                "issue": f"Room has narrow aspect ratio {ratio:.1f}:1 (threshold {max_ratio}:1)",
                "evidence": f"aspect_ratio={ratio:.1f}, threshold={max_ratio}",
                "values": {"aspect_ratio": round(ratio, 1), "threshold": max_ratio},
            })
    return findings


# ──────────────────────────────────────────────────────────────────
# Run all checks
# ──────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    check_R01, check_R02, check_R03, check_R04, check_R05,
    check_R06, check_R07, check_R08, check_R09, check_R10,
    check_R11, check_R12, check_R13,
]


def run_all_checks(pkg, rules=None):
    """Run every rule check and return a combined list of findings."""
    if rules is None:
        from src.loader import load_rules
        rules = load_rules()

    all_findings = []
    for check_fn in ALL_CHECKS:
        try:
            results = check_fn(pkg, rules)
            all_findings.extend(results)
        except Exception as e:
            all_findings.append({
                "finding_id": _fid(),
                "rule_id": check_fn.__name__.replace("check_", ""),
                "group": "RULE_FAILED",
                "severity": "high",
                "sheet_no": "",
                "element": "CHECK_ERROR",
                "issue": f"Check raised an exception: {e}",
                "evidence": str(e),
                "values": {},
            })
    return all_findings
