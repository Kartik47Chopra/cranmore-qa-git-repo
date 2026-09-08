"""Real-data ingestion for the Summerset Oakleigh South QA project.

Walks /app/backend/data/summerset and creates real (no fabricated progress):
- Companies, Project, Templates (one per trade folder)
- Location tree: Building (RACF / ILA / General) -> Floor -> Room (RACF) / Apartment (ILA)
- Documents (every file in the dataset)
- Visis: room-level Skirting/Sanitary for RACF, per-apartment for ILA,
  floor-level Doors, and one Visi per Miscellaneous fixture type. Each linked
  to the drawings that evidence it.
"""
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Callable

DATA_DIR = Path(__file__).parent / "data" / "summerset"

FLOOR_PATTERNS = [
    ("Basement - Part 1", "Basement Part 1"),
    ("Basement - Part 2", "Basement Part 2"),
    ("Basement Part 1", "Basement Part 1"),
    ("Basement Part 2", "Basement Part 2"),
    ("Ground Floor", "Ground Floor"),
    ("First Floor", "First Floor"),
    ("Second Floor", "Second Floor"),
    ("Roof Floor", "Roof"),
    ("Roof Plan", "Roof"),
    ("- Roof", "Roof"),
]
FLOOR_ORDER = ["Basement Part 1", "Basement Part 2", "Ground Floor", "First Floor", "Second Floor", "Roof"]

TEMPLATES = {
    "Skirting": {"discipline": "Architectural", "stage": "Fit-off", "system": "Carpentry / Joinery", "trade": "Cranmore Carpenters", "prefix": "SK",
        "steps": [("Wall / substrate ready & accessible", "inspection"), ("Set-out confirmed to wall setout plan", "inspection"),
                  ("Skirting supplied & checked (Criterion / Bowens)", "inspection"), ("Installed, mitred & fixed", "inspection"),
                  ("Photo of installed skirting", "task"), ("Caulk, fill & finish", "inspection"), ("QA sign-off", "inspection")]},
    "Sanitary": {"discipline": "Services", "stage": "Fit-off", "system": "Hydraulic / Sanitary", "trade": "Summerset Plumbing", "prefix": "SN",
        "steps": [("Rough-in verified", "inspection"), ("Fixtures set out to MFP schedule", "inspection"), ("Fixtures installed", "inspection"),
                  ("Sealed & leak tested", "inspection"), ("Photo evidence of completed fixtures", "task"), ("QA sign-off", "inspection")]},
    "Door": {"discipline": "Architectural", "stage": "Fit-off", "system": "Doors & Hardware", "trade": "Cranmore Carpenters", "prefix": "DR",
        "steps": [("Frame set out to door schedule", "inspection"), ("Door hung plumb & square", "inspection"), ("Hardware fitted", "inspection"),
                  ("Operation & fire-rating check", "inspection"), ("Photo of installed door", "task"), ("QA sign-off", "inspection")]},
    "Miscellaneous": {"discipline": "Architectural", "stage": "Fit-off", "system": "Fixtures & Fittings", "trade": "Fitout & Fixtures Co", "prefix": "MI",
        "steps": [("Location set-out confirmed", "inspection"), ("Backing / bracket / noggin installed", "inspection"), ("Item mounted & secured", "inspection"),
                  ("Photo evidence of installation", "task"), ("QA sign-off", "inspection")]},
    "Robe Jamb": {"discipline": "Architectural", "stage": "Fit-off", "system": "Carpentry / Joinery", "trade": "Cranmore Carpenters", "prefix": "RJ",
        "steps": [("Opening set out to plan & robe schedule", "inspection"), ("Jamb supplied & checked (Criterion / Bowens)", "inspection"),
                  ("Jamb installed plumb & square, fixed", "inspection"), ("Photo of installed robe jamb", "task"), ("QA sign-off", "inspection")]},
}

COMPANIES = [
    {"name": "Cranmore Carpenters", "color": "#059669", "owner": True},
    {"name": "Summerset Plumbing", "color": "#0EA5E9", "owner": False},
    {"name": "Fitout & Fixtures Co", "color": "#8B5CF6", "owner": False},
    {"name": "Criterion Joinery", "color": "#10B981", "owner": False},
    {"name": "Bowens", "color": "#F59E0B", "owner": False},
]

# Real bedroom registry extracted from A1203 (Level 1) / A1204 (Level 2) GA plans.
# (room_no, type_desc). Type in {S BED, P BED, ACC BED} with letter = layout/mirror variant.
RACF_BEDROOMS_L1 = [
    ("101", "P BED (D)"), ("102", "P BED (E)"), ("103", "P BED (E MIR.)"), ("104", "P BED (D MIR.)"),
    ("105", "S BED (C MIR.)"), ("106", "S BED (A)"), ("107", "S BED (A)"), ("108", "S BED (A MIR.)"),
    ("109", "P BED (C)"), ("110", "P BED (C)"), ("111", "S BED (C MIR.)"), ("112", "S BED (C)"),
    ("113", "S BED (D)"), ("114", "S BED (A MIR.)"), ("115", "S BED (A)"), ("116", "S BED (A MIR.)"),
    ("117", "S BED (A)"), ("118", "S BED (A MIR.)"), ("119", "S BED (A)"), ("120", "S BED (A MIR.)"),
    ("121", "S BED (A)"), ("122", "S BED (A MIR.)"), ("123", "S BED (A)"), ("125", "S BED (B)"),
    ("126", "S BED (A MIR.)"), ("127", "S BED (B)"), ("128", "S BED (A MIR.)"), ("129", "ACC BED (RHS)"),
    ("130", "P BED (C MIR.)"), ("131", "P BED (F MIR.)"), ("132", "P BED (B)"), ("133", "P BED (A)"),
]
RACF_BEDROOMS_L2 = [
    ("201", "P BED (D)"), ("202", "P BED (E)"), ("203", "P BED (E MIR.)"), ("204", "P BED (D MIR.)"),
    ("205", "S BED (A MIR.)"), ("206", "S BED (A)"), ("207", "S BED (A)"), ("208", "S BED (A MIR.)"),
    ("209", "P BED (C)"), ("210", "P BED (C)"), ("211", "S BED (A MIR.)"), ("212", "S BED (A)"),
    ("213", "S BED (D)"), ("214", "S BED (A MIR.)"), ("215", "S BED (A)"), ("216", "S BED (A MIR.)"),
    ("217", "S BED (A)"), ("218", "S BED (A MIR.)"), ("219", "S BED (A)"), ("220", "S BED (A MIR.)"),
    ("221", "S BED (A)"), ("222", "S BED (A MIR.)"), ("223", "S BED (A)"), ("225", "S BED (A)"),
    ("226", "S BED (A MIR.)"), ("227", "S BED (A)"), ("228", "S BED (A MIR.)"), ("229", "ACC BED (LHS)"),
    ("230", "P BED (C MIR.)"), ("231", "P BED (F MIR.)"), ("232", "P BED (B)"), ("233", "P BED (A)"),
]
RACF_BEDROOMS_BY_FLOOR = {"First Floor": RACF_BEDROOMS_L1, "Second Floor": RACF_BEDROOMS_L2}

# Real support / BOH / amenity rooms per RACF floor, extracted room-by-room from the GA plans.
# (name, keywords for doc matching, is_wet room)
RACF_BASEMENT1_ROOMS = [
    ("R.B02 Hydraulic Plant Room", ["Hydraulic Plant"], True),
    ("R.B03 Stair 01", ["Stair 01"], False),
    ("R.B04 Store", ["R.B04", "Store"], False),
    ("R.B05 Store", ["R.B05", "Store"], False),
    ("R.B06 Stair 02", ["Stair 02"], False),
    ("R.B07 Store", ["R.B07", "Store"], False),
    ("RACF Lift Lobby", ["RACF LIFT LOBBY"], False),
    ("RACF Lift", ["RACF LIFT"], False),
    ("BOH Lift", ["BOH LIFT"], False),
    ("Storage Cages (Bays 1-90)", ["Storage"], False),
]
RACF_BASEMENT2_ROOMS = [
    ("A.B01 Stair 03", ["Stair 03"], False),
    ("A.B02 ILA Lift", ["ILA LIFT"], False),
    ("ILA Lift Lobby", ["ILA LIFT LOBBY"], False),
    ("A.B03 ILA Bin Room", ["BIN ROOM"], True),
    ("A.B04 Store", ["A.B04", "Store"], False),
    ("Bin Wash", ["BIN WASH"], True),
    ("Wash Bay", ["WASH BAY"], True),
    ("Hard Waste Bay", ["HARD WASTE"], False),
    ("Scooters", ["SCOOTERS"], False),
    ("BOL1 Storage Cages", ["Storage"], False),
]
RACF_GROUND_ROOMS = [
    ("R.G01 Airlock", ["R.G01", "AIRLOCK"], False),
    ("R.G02 Sales Manager", ["SALES MANAGER"], False),
    ("R.G03 Village Manager", ["VILLAGE MANAGER"], False),
    ("R.G04 CBM Office", ["CBM OFFICE"], False),
    ("R.G05 Meeting Room", ["MEETING"], False),
    ("R.G06 Store", ["R.G06", "STORE"], False),
    ("R.G07 Staff Admin", ["STAFF ADMIN"], False),
    ("R.G08 Corridor", ["R.G08", "CORRIDOR"], False),
    ("R.G09 Reception", ["RECEPTION"], False),
    ("R.G10 Waiting", ["WAITING"], False),
    ("R.G11 Cafe", ["R.G11", "CAFE"], True),
    ("R.G12 Servery", ["SERVERY"], True),
    ("R.G13 Cafe Seating", ["CAFE SEATING"], False),
    ("R.G14 Circulation", ["R.G14", "CIRCULATION"], False),
    ("R.G15 Lounge", ["R.G15", "LOUNGE"], False),
    ("R.G16 Lobby", ["LOBBY"], False),
    ("R.G16 Sitting / Wait", ["SITTING / WAIT"], False),
    ("R.G17 Salon", ["SALON"], True),
    ("R.G18 Lounge", ["R.G18", "LOUNGE"], False),
    ("R.G19 Private Dining / Meeting", ["PRIVATE DINING"], False),
    ("R.G20 Furniture Store", ["FURNITURE STORE"], False),
    ("R.G21 Library", ["LIBRARY"], False),
    ("R.G22 Lounge / Bar", ["LOUNGE / BAR"], True),
    ("R.G23 Airlock", ["R.G23", "AIRLOCK"], False),
    ("R.G24 Male WC", ["MALE WC"], True),
    ("R.G25 Accessible WC", ["ACC. WC", "ACC WC"], True),
    ("R.G26 Female WC", ["FEMALE WC"], True),
    ("R.G27 Sitting / Wait", ["SITTING / WAIT"], False),
    ("R.G28 Airlock", ["R.G28", "AIRLOCK"], False),
    ("R.G29 Theatre / Chapel", ["THEATRE"], False),
    ("R.G30 Flex / Group Exercise", ["FLEX / GROUP EXERCISE"], False),
    ("R.G31 Consult Room", ["CONS"], False),
    ("R.G32 Gym", ["GYM"], False),
    ("R.G33 Consult Room", ["CONS"], False),
    ("R.G34 Circulation", ["R.G34", "CIRCULATION"], False),
    ("R.G35 Loading Dock", ["LOADING"], False),
    ("R.G36 Waste Room", ["WASTE"], True),
    ("R.G37 BOH Corridor", ["BOH CORRIDOR"], False),
    ("R.G38 Staff Room", ["STAFF ROOM"], False),
    ("R.G39 Airlock", ["R.G39", "AIRLOCK"], False),
    ("R.G40 Staff Shower", ["STAFF SHR"], True),
    ("R.G41 Staff Amb WC", ["STAFF (AMB) WC"], True),
    ("R.G42 Staff Accessible WC", ["STAFF ACC WC"], True),
    ("R.G43 Main Kitchen", ["KITCHEN"], True),
    ("R.G44 Cleaners", ["CLEANERS"], True),
    ("R.G45 Chemical Store", ["CHEM STORE"], True),
    ("R.G46 Chef Office", ["CHEF OFFICE"], False),
    ("R.G47 Trolley Store", ["TROLLEY STORE"], False),
    ("R.G48 Comms Room", ["COMMS"], False),
    ("R.G49 Laundry", ["R.G49", "LAUNDRY"], True),
    ("R.G50 Laundry", ["R.G50", "LAUNDRY"], True),
    ("R.G51 Stair 01", ["STAIR 01"], False),
    ("R.G52 Stair 02", ["STAIR 02"], False),
    ("R.G53 Fire Corridor", ["FIRE CORRIDOR"], False),
    ("R.G54 SCV Room", ["SCV"], False),
    ("R.G55 Main Switchboard", ["MAIN SWITCHBOARD"], True),
    ("Bulk Storage", ["BULK STORAGE"], False),
    ("Mech Room", ["MECH"], False),
    ("BOH Lift", ["BOH LIFT"], False),
    ("RACF FOH Lift", ["RACF FOH LIFT"], False),
    ("Outdoor Terrace", ["OUTDOOR TERRACE"], False),
    ("Hard Waste Bay", ["HARD WASTE"], False),
]
RACF_L1_SUPPORT_ROOMS = [
    ("R.150 Sit", ["SIT"], False),
    ("R.151 Sit", ["SIT"], False),
    ("R.152 Circulation", ["CIRCULATION"], False),
    ("R.153 Stair 01", ["STAIR 01"], False),
    ("R.154 Circulation / Elec", ["ELEC", "CIRCULATION"], False),
    ("R.156 Accessible WC", ["ACC WC"], True),
    ("R.157 Pantry - East", ["PANTRY"], True),
    ("R.158 Pantry - West", ["PANTRY"], True),
    ("R.159 Furniture Storage", ["FURNITURE STORAGE"], False),
    ("R.159 Lounge - West", ["LOUNGE - WEST"], False),
    ("R.159 Dining - West", ["DINING - WEST"], False),
    ("R.159 Library - West", ["LIBRARY - WEST"], False),
    ("R.160 Circulation - West", ["CIRCULATION - WEST"], False),
    ("R.161 Kitchen - West", ["KITCHEN - WEST"], True),
    ("R.162 Comms", ["COMMS"], False),
    ("R.163 Mech CPE", ["MECH CPE"], False),
    ("R.164 Airlock / Lobby", ["AIRLOCK/LOBBY"], False),
    ("R.165 Staff Hub", ["STAFF HUB"], False),
    ("R.166 BOH Circulation", ["BOH CIRCULATION"], False),
    ("Treatment Room", ["TREATMENT"], True),
    ("Sluice Room", ["SLUICE"], True),
    ("R.170 Kitchen - East", ["KITCHEN - EAST"], True),
    ("R.171 Accessible WC - East", ["ACC WC"], True),
    ("R.172 Circulation - East", ["CIRCULATION - EAST"], False),
    ("R.173 Dining - East", ["DINING - EAST"], False),
    ("R.173 Lounge - East", ["LOUNGE - EAST"], False),
    ("R.173 Library - East", ["LIBRARY - EAST"], False),
    ("R.173 Store", ["STORE"], False),
    ("R.177 Circulation", ["CIRCULATION"], False),
    ("R.178 Sit", ["SIT"], False),
    ("R.179 CM Office", ["CM OFFICE"], False),
    ("R.179 Planted Terrace", ["PLANTED TERRACE"], False),
    ("R.180 Communal Terrace", ["COMMUNAL TERRACE"], False),
    ("R.181 Planted Terrace", ["PLANTED TERRACE"], False),
    ("R.182 Communal Terrace", ["COMMUNAL TERRACE"], False),
    ("Linen - Household 1", ["LINEN"], False),
    ("Linen - Household 2", ["LINEN"], False),
]
RACF_L2_SUPPORT_ROOMS = [
    ("R.250 Sit", ["SIT"], False),
    ("R.251 Sit", ["SIT"], False),
    ("R.252 Circulation", ["CIRCULATION"], False),
    ("R.253 Stair 01", ["STAIR 01"], False),
    ("R.254 Circulation / Elec", ["ELEC", "CIRCULATION"], False),
    ("R.255 Sit", ["SIT"], False),
    ("R.256 Store", ["STORE"], False),
    ("R.257 Accessible WC", ["ACC WC"], True),
    ("R.258 Activity Room", ["ACTIVITY"], False),
    ("R.259 Lounge - West", ["LOUNGE - WEST"], False),
    ("R.259 Dining - West", ["DINING - WEST"], False),
    ("R.259 Library - West", ["LIBRARY - WEST"], False),
    ("R.260 Circulation - West", ["CIRCULATION - WEST"], False),
    ("R.261 Kitchen - West", ["KITCHEN - WEST"], True),
    ("R.262 Pantry - West", ["PANTRY"], True),
    ("R.264 Airlock / Lobby", ["AIRLOCK/LOBBY"], False),
    ("R.265 Staff Hub", ["STAFF HUB"], False),
    ("R.266 BOH Circulation", ["BOH CIRCULATION"], False),
    ("R.267 Cleaner Room", ["CLEANER"], True),
    ("R.268 Sluice Room", ["SLUICE"], True),
    ("R.269 Treatment Room", ["TREATMENT"], True),
    ("R.270 Kitchen - East", ["KITCHEN - EAST"], True),
    ("R.271 Accessible WC - East", ["ACC WC"], True),
    ("R.272 Circulation - East", ["CIRCULATION - EAST"], False),
    ("R.273 Dining - East", ["DINING - EAST"], False),
    ("R.273 Lounge - East", ["LOUNGE - EAST"], False),
    ("R.273 Library - East", ["LIBRARY - EAST"], False),
    ("R.274 Comms", ["COMMS"], False),
    ("R.275 Accessible WC", ["ACC WC"], True),
    ("R.276 Stair 02", ["STAIR 02"], False),
    ("R.278 Sit", ["SIT"], False),
    ("R.279 Planted Terrace", ["PLANTED TERRACE"], False),
    ("R.280 Communal Terrace", ["COMMUNAL TERRACE"], False),
    ("R.281 Planted Terrace", ["PLANTED TERRACE"], False),
    ("R.282 Communal Terrace", ["COMMUNAL TERRACE"], False),
    ("Mech Room", ["MECH"], False),
    ("Linen - Household 3", ["LINEN"], False),
    ("Linen - Household 4", ["LINEN"], False),
]
RACF_ROOF_ROOMS = [
    ("R.301 Roof Access Walkway", ["ROOF ACCESS WALKWAY"], False),
    ("R.302 Roof Plant Room", ["ROOF PLANT"], False),
    ("Solar PV Array (Min. 60kW)", ["SOLAR PANEL"], False),
    ("Roof Safety & Anchor Point System", ["ROOF SAFETY SYSTEM", "ANCHOR POINT"], False),
    ("Metal Louvre Screens", ["METAL LOUVRE SCREEN"], False),
]
RACF_FLOOR_SUPPORT_ROOMS = {
    "Basement Part 1": RACF_BASEMENT1_ROOMS,
    "Basement Part 2": RACF_BASEMENT2_ROOMS,
    "Ground Floor": RACF_GROUND_ROOMS,
    "First Floor": RACF_L1_SUPPORT_ROOMS,
    "Second Floor": RACF_L2_SUPPORT_ROOMS,
    "Roof": RACF_ROOF_ROOMS,
}
RACF_ALL_FLOORS = ["Basement Part 1", "Basement Part 2", "Ground Floor", "First Floor", "Second Floor", "Roof"]

# Fire safety / utility items tracked per RACF floor, evidenced by the GA plan legend abbreviations
# (FE, FH, FHR, RHYD = fire extinguisher / hydrant / hose reel / recessed hydrant).
RACF_UTILITY_ITEMS = [
    ("Fire Extinguishers", ["FE", "FIRE EXTINGUISHER"]),
    ("Fire Hydrants", ["FH", "FIRE HYDRANT"]),
    ("Fire Hose Reels", ["FHR", "FIRE HOSE REEL"]),
    ("Recessed Hydrants (RHYD)", ["RHYD"]),
]

# ------------------------------------------------------------------ ILA apartments
# Real apartment registry extracted from the ILA type plan drawings (A2800-A2812
# "ILA Finish Types" tables). Each entry: (apt_number, level_idx, apt_type, bed_count, finish, mirrored).
# level_idx maps to ILA_LEVELS below; apt_type is the apartment type plan the unit is built to.
ILA_LEVELS = ["Ground Floor", "First Floor", "Second Floor"]
ILA_APARTMENTS = [
    ("G01", 0, 2, 2, "Standard", True), ("G02", 0, 2, 2, "Standard", False), ("G03", 0, 2, 2, "Standard", True),
    ("G04", 0, 5, 2, "Standard", False), ("G05", 0, 6, 2, "Standard", False), ("G06", 0, 1, 1, "Standard", True),
    ("G07", 0, 1, 1, "Standard", False), ("G08", 0, 1, 1, "Standard", True), ("G09", 0, 3, 2, "Standard", True),
    ("G10", 0, 1, 1, "Standard", False), ("G11", 0, 4, 2, "Standard", False), ("G12", 0, 13, 2, "Standard", False),
    ("G13", 0, 1, 1, "Standard", True), ("G14", 0, 1, 1, "Standard", False), ("G15", 0, 6, 2, "Standard", True),
    ("G16", 0, 2, 2, "Standard", False), ("G17", 0, 2, 2, "Standard", True), ("G18", 0, 2, 2, "Standard", False),
    ("101", 1, 2, 2, "Standard", True), ("102", 1, 2, 2, "Standard", False), ("103", 1, 2, 2, "Standard", True),
    ("104", 1, 5, 2, "Standard", False), ("105", 1, 6, 2, "Standard", False), ("106", 1, 7, 2, "Standard", True),
    ("107", 1, 1, 1, "Standard", False), ("108", 1, 1, 1, "Standard", True), ("109", 1, 3, 2, "Standard", True),
    ("110", 1, 1, 1, "Standard", False), ("111", 1, 4, 2, "Standard", False), ("112", 1, 13, 2, "Standard", False),
    ("113", 1, 8, 2, "Standard", False), ("114", 1, 7, 2, "Standard", False), ("115", 1, 6, 2, "Standard", True),
    ("116", 1, 9, 3, "Standard", True), ("117", 1, 10, 3, "Standard", False),
    ("201", 2, 10, 3, "Premium", True), ("202", 2, 9, 3, "Premium", False), ("203", 2, 5, 2, "Standard", False),
    ("204", 2, 6, 2, "Standard", False), ("205", 2, 7, 2, "Standard", True), ("206", 2, 1, 1, "Standard", False),
    ("207", 2, 11, 3, "Premium", False), ("208", 2, 12, 2, "Standard", False), ("209", 2, 4, 2, "Standard", False),
    ("210", 2, 13, 2, "Standard", False), ("211", 2, 8, 2, "Standard", False), ("212", 2, 7, 2, "Standard", False),
    ("213", 2, 6, 2, "Standard", True), ("214", 2, 9, 3, "Premium", True), ("215", 2, 10, 3, "Premium", False),
]
# Standard number of bedroom slots per apartment. Slots beyond the apartment's real bed
# count are created as N/A rooms so they can be activated / removed / re-marked later.
ILA_STANDARD_BEDROOMS = 3

# Rooms present in each type's plan (drawings A2800-A2812, verified per type). Bedrooms are handled separately.
ILA_TYPE_ROOMS = {
    1: {"ensuite": False, "study": True, "store": True, "linen": True, "powder": False},
    2: {"ensuite": False, "study": False, "store": True, "linen": True, "powder": True},
    3: {"ensuite": False, "study": False, "store": False, "linen": True, "powder": False},
    4: {"ensuite": True, "study": True, "store": True, "linen": True, "powder": False},
    5: {"ensuite": True, "study": False, "store": False, "linen": True, "powder": False},
    6: {"ensuite": True, "study": True, "store": False, "linen": True, "powder": False},
    7: {"ensuite": True, "study": True, "store": True, "linen": True, "powder": False},
    8: {"ensuite": True, "study": False, "store": False, "linen": True, "powder": False},
    9: {"ensuite": True, "study": False, "store": True, "linen": True, "powder": False},
    10: {"ensuite": True, "study": True, "store": False, "linen": True, "powder": False},
    11: {"ensuite": True, "study": False, "store": True, "linen": True, "powder": False},
    12: {"ensuite": True, "study": True, "store": False, "linen": True, "powder": False},
    13: {"ensuite": False, "study": True, "store": True, "linen": False, "powder": False},
}

# ILA common rooms per floor, extracted from the ILA GA plans (A2200-A2202): numbered
# rooms use the "A." prefix. (name, keywords, is_wet)
ILA_COMMON_ROOMS = {
    "Ground Floor": [
        ("A.G50 Corridor", ["CORRIDOR"], False),
        ("Stair 03", ["STAIR 03"], False),
        ("Stair 04", ["STAIR 04"], False),
        ("Stair 05", ["STAIR 05"], False),
        ("ILA Lift", ["ILA LIFT"], False),
        ("ILA Lift Lobby", ["LIFT LOBBY"], False),
        ("Mech Room", ["MECH"], False),
        ("Garbage Chute", ["CHUTE"], False),
        ("Group Meter Panel", ["GROUP METER"], False),
        ("Circulation Link (Grade Link)", ["CIRCULATION LINK"], False),
        ("Bicycle Parking (6 Spaces)", ["BICYCLE"], False),
    ],
    "First Floor": [
        ("A.150 Corridor", ["CORRIDOR"], False),
        ("A.152 Corridor", ["CORRIDOR"], False),
        ("A.153 ILA Communal Space", ["COMMUNAL"], False),
        ("A.155 Corridor", ["CORRIDOR"], False),
        ("A.157 Lift Lobby", ["LIFT LOBBY"], False),
        ("Stair 03", ["STAIR 03"], False),
        ("Stair 04", ["STAIR 04"], False),
        ("Stair 05", ["STAIR 05"], False),
        ("ILA Lift", ["ILA LIFT"], False),
        ("Mech Room", ["MECH"], False),
        ("Garbage Chute", ["CHUTE"], False),
        ("Hyd / Elec Riser", ["HYD ELEC"], False),
    ],
    "Second Floor": [
        ("A.250 Corridor", ["CORRIDOR"], False),
        ("A.252 Corridor", ["CORRIDOR"], False),
        ("A.253 ILA Communal Space", ["COMMUNAL"], False),
        ("A.255 Corridor", ["CORRIDOR"], False),
        ("A.257 Lift Lobby", ["LIFT LOBBY"], False),
        ("Stair 03", ["STAIR 03"], False),
        ("Stair 04", ["STAIR 04"], False),
        ("Stair 05", ["STAIR 05"], False),
        ("ILA Lift", ["ILA LIFT"], False),
        ("Mech Room", ["MECH"], False),
        ("Garbage Chute", ["CHUTE"], False),
        ("Hyd / Elec Riser", ["HYD ELEC"], False),
        ("Bin Room Riser", ["BIN ROOM"], False),
        ("Roof Access Hatch", ["ACCESS HATCH"], False),
    ],
    "Roof": [
        ("Roof Safety & Anchor Point System", ["ROOF SAFETY", "ANCHOR POINT"], False),
        ("Waste Room Exhaust Riser (Rooftop)", ["WASTE ROOM EXHAUST"], False),
        ("Fresh Air Dropper (Rooftop)", ["FRESH AIR DROPPER"], False),
        ("Car Park Exhaust (Rooftop)", ["CAR PARK EXHAUST"], False),
        ("Stair / Lift Bulkheads", ["STAIR", "LIFT"], False),
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_floor(text: str) -> Optional[str]:
    for pat, norm in FLOOR_PATTERNS:
        if pat.lower() in text.lower():
            return norm
    return None


def parse_document(filename: str) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    stem = filename[: -(len(ext) + 1)] if ext else filename
    mrev = re.search(r"\[([^\]]+)\]", stem)
    rev = mrev.group(1) if mrev else None
    clean_stem = re.sub(r"\[[^\]]*\]", "", stem).strip()
    drawing_no = None
    mdn = re.search(r"-([A-Z]{1,4}\d{2,4})-", clean_stem)
    if mdn:
        drawing_no = mdn.group(1)
        title = clean_stem.split(f"-{drawing_no}-", 1)[1].strip(" -")
    else:
        title = clean_stem
    title = title.strip(" -") or clean_stem
    return {"drawing_no": drawing_no, "revision": rev, "title": title, "ext": ext}


async def seed_all(db, hash_password: Callable[[str], str]) -> None:
    if await db.projects.count_documents({}) > 0:
        return

    comps = {}
    for c in COMPANIES:
        cid = str(uuid.uuid4())
        await db.companies.insert_one({"id": cid, "name": c["name"], "color": c["color"], "plan": "pro", "logo": None, "is_owner": c["owner"]})
        comps[c["name"]] = cid
    owner_id = comps["Cranmore Carpenters"]

    if not await db.users.find_one({"email": "factory@maxxdoors.com.au"}):
        await db.users.insert_one({"email": "factory@maxxdoors.com.au", "password_hash": hash_password("Cranmore2026!"), "name": "Site Factory Admin", "role": "admin", "company_id": owner_id, "created_at": now_iso()})
    if not await db.users.find_one({"email": "plumbing@maxxdoors.com.au"}):
        await db.users.insert_one({"email": "plumbing@maxxdoors.com.au", "password_hash": hash_password("Cranmore2026!"), "name": "Summerset Plumbing Lead", "role": "trade", "company_id": comps["Summerset Plumbing"], "created_at": now_iso()})

    project_id = str(uuid.uuid4())
    await db.projects.insert_one({"id": project_id, "name": "Summerset Oakleigh South", "address": "Oakleigh South, Melbourne VIC · Drawing set 225-MB-CHC", "company_id": owner_id, "member_company_ids": list(comps.values())})

    for disc, t in TEMPLATES.items():
        tid = str(uuid.uuid4())
        steps = []
        for label, typ in t["steps"]:
            step = {"id": str(uuid.uuid4()), "label": label, "type": typ, "assignee_company_id": comps[t["trade"]], "reviewer_company_id": owner_id, "requirements": []}
            if typ == "task":
                step["requirements"] = [{"id": str(uuid.uuid4()), "label": label}]
            steps.append(step)
        t["id"] = tid
        await db.templates.insert_one({"id": tid, "name": disc, "revision": 1, "discipline": t["discipline"], "stage": t["stage"], "system": t["system"], "assignee_company": comps[t["trade"]], "steps": steps})

    BUILDING_LABELS = {"RACF": "RACF · Aged Care Facility", "ILA": "ILA · Independent Living Apartments", "General": "General / Whole Site"}
    building_nodes, floor_nodes = {}, {}
    locations = []

    def building_node(bld):
        if bld not in building_nodes:
            lid = str(uuid.uuid4())
            building_nodes[bld] = lid
            locations.append({"id": lid, "project_id": project_id, "parent_id": None, "name": BUILDING_LABELS.get(bld, bld), "type": "Building", "order": {"RACF": 0, "ILA": 1, "General": 2}.get(bld, 3)})
        return building_nodes[bld]

    def floor_node(bld, floor):
        key = (bld, floor)
        if key not in floor_nodes:
            parent = building_node(bld)
            lid = str(uuid.uuid4())
            floor_nodes[key] = lid
            order = FLOOR_ORDER.index(floor) if floor in FLOOR_ORDER else 90
            locations.append({"id": lid, "project_id": project_id, "parent_id": parent, "name": floor, "type": "Level", "order": order})
        return floor_nodes[key]

    # ---- ingest documents
    documents = []
    all_files = sorted([p for p in DATA_DIR.rglob("*") if p.is_file()])
    for p in all_files:
        rel = p.relative_to(DATA_DIR)
        parts = list(rel.parts)
        discipline = parts[0] if parts else "Miscellaneous"
        building = "RACF" if "RACF" in parts else ("ILA" if "ILA" in parts else "General")
        cat_parts = [x for x in parts[1:-1] if x not in ("RACF", "ILA")]
        category = " / ".join(cat_parts) if cat_parts else "Plans"
        meta = parse_document(p.name)
        floor = parse_floor(p.name)
        uploader = "Bowens" if "Bowens" in p.name else ("Criterion Joinery" if "Criterion" in p.name else "Cranmore Carpenters")
        content_type = "image/png" if meta["ext"] == "png" else "application/pdf"
        loc_id = floor_node(building, floor) if (floor and building != "General") else building_node(building)
        documents.append({"id": str(uuid.uuid4()), "project_id": project_id, "discipline": discipline, "building": building,
                          "category": category, "floor": floor, "drawing_no": meta["drawing_no"], "revision": meta["revision"],
                          "title": meta["title"], "filename": p.name, "rel_path": rel.as_posix(), "content_type": content_type,
                          "size": p.stat().st_size, "location_id": loc_id, "uploaded_by_company": comps.get(uploader, owner_id), "uploaded_at": now_iso()})

    # ---- RACF rooms (every real room off the GA plans, all floors) + ILA apartments + RACF fixtures zone
    room_nodes = []  # (loc_id, floor, room_name, keywords, is_wet)
    bedroom_nodes = []  # (loc_id, floor, room_no, type_desc) - bedrooms get their own Door+Skirting+Sanitary Visi
    racf_util_zones = {}  # floor -> Zone location id for Fire Safety & Utilities
    for floor in RACF_ALL_FLOORS:
        fnode = floor_node("RACF", floor)
        order = 0
        for (rname, kws, wet) in RACF_FLOOR_SUPPORT_ROOMS.get(floor, []):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": fnode, "name": rname, "type": "Room", "order": order})
            room_nodes.append((rid, floor, rname, kws, wet, "RACF"))
            order += 1
        for (room_no, type_desc) in RACF_BEDROOMS_BY_FLOOR.get(floor, []):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": fnode, "name": f"Room {room_no} · {type_desc}", "type": "Room", "order": order, "room_no": room_no})
            bedroom_nodes.append((rid, floor, room_no, type_desc))
            order += 1
        util_zone = str(uuid.uuid4())
        locations.append({"id": util_zone, "project_id": project_id, "parent_id": fnode, "name": "Fire Safety & Utilities", "type": "Zone", "order": 900})
        racf_util_zones[floor] = util_zone

    # ILA: Level -> Apartment (real registry from drawings) -> standard rooms.
    # Every apartment gets 3 bedroom slots; slots beyond the real bed count are
    # marked status "na" so they can be activated / removed / edited later.
    apts = []       # (loc_id, apt_number, apt_type, bed_count, level_idx)
    apt_rooms = {}  # loc_id -> list of (room_loc_id, name, is_active)
    for (num, lvl_idx, typ, beds, finish, mirrored) in ILA_APARTMENTS:
        fnode = floor_node("ILA", ILA_LEVELS[lvl_idx])
        aid = str(uuid.uuid4())
        order = int(re.sub(r"\D", "", num) or 99)
        locations.append({"id": aid, "project_id": project_id, "parent_id": fnode,
                          "name": f"Apartment {num} · Type {typ}", "type": "Unit", "order": order,
                          "apt_number": num, "apt_type": typ, "bed_count": beds, "finish": finish, "mirrored": mirrored})
        apts.append((aid, num, typ, beds, lvl_idx))
        rooms = ILA_TYPE_ROOMS[typ]
        room_defs = [(f"Bedroom {b}", "active" if b <= beds else "na") for b in range(1, ILA_STANDARD_BEDROOMS + 1)]
        if rooms["ensuite"]:
            room_defs.append(("Ensuite", "active"))
        room_defs += [("Bathroom", "active"), ("Living / Kitchen / Dining", "active"), ("Laundry", "active")]
        if rooms.get("powder"):
            room_defs.append(("Powder Room", "active"))
        if rooms["study"]:
            room_defs.append(("Study", "active"))
        if rooms["store"]:
            room_defs.append(("Store", "active"))
        if rooms["linen"]:
            room_defs.append(("Linen", "active"))
        apt_rooms[aid] = []
        for i, (rname, rstatus) in enumerate(room_defs):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": aid, "name": rname, "type": "Room", "order": i, "status": rstatus})
            apt_rooms[aid].append((rid, rname, rstatus == "active"))

    # ILA common rooms per floor (corridors, stairs, lift, communal spaces) + utilities zone
    ila_util_zones = {}
    for floor, commons in ILA_COMMON_ROOMS.items():
        fnode = floor_node("ILA", floor)
        for i, (rname, kws, wet) in enumerate(commons):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": fnode, "name": rname, "type": "Room", "order": 200 + i})
            room_nodes.append((rid, floor, rname, kws, wet, "ILA"))
        util_zone = str(uuid.uuid4())
        locations.append({"id": util_zone, "project_id": project_id, "parent_id": fnode, "name": "Fire Safety & Utilities", "type": "Zone", "order": 900})
        ila_util_zones[floor] = util_zone

    racf_bnode = building_node("RACF")
    fixtures_zone = str(uuid.uuid4())
    locations.append({"id": fixtures_zone, "project_id": project_id, "parent_id": racf_bnode, "name": "Fixtures & Fittings", "type": "Zone", "order": 80})

    await db.locations.insert_many([dict(l) for l in locations])
    await db.documents.insert_many([dict(d) for d in documents])

    # ---- doc matching helper
    def match_docs(discipline, building=None, keywords=None):
        out = []
        for d in documents:
            if d["discipline"] != discipline:
                continue
            if building and d["building"] not in (building, "General"):
                continue
            if keywords:
                hay = ((d["title"] or "") + " " + (d["category"] or "") + " " + d["filename"]).lower()
                if not any(k.lower() in hay for k in keywords):
                    continue
            out.append(d["id"])
        return out

    # ---- visi builder
    visi_docs = []
    seq = {k: 0 for k in TEMPLATES}

    def make_visi(discipline, loc_id, doc_ids, visi_type="Inspection"):
        seq[discipline] += 1
        t = TEMPLATES[discipline]
        steps = []
        for label, typ in t["steps"]:
            s = {"step_id": str(uuid.uuid4()), "label": label, "type": typ, "status": "pending", "assignee_company_id": comps[t["trade"]], "requirements": []}
            if typ == "task":
                s["requirements"] = [{"id": str(uuid.uuid4()), "label": label, "attachment_id": None}]
            steps.append(s)
        visi_docs.append({"id": str(uuid.uuid4()), "code": f"225-{t['prefix']}-{seq[discipline]:03d}", "visi_type": visi_type,
                          "template_id": t["id"], "template_name": discipline, "template_revision": 1, "location_id": loc_id,
                          "project_id": project_id, "assignee_company_id": comps[t["trade"]], "reviewer_company_id": owner_id,
                          "visible_to": list({owner_id, comps[t["trade"]]}), "steps": steps, "override_status": None,
                          "system": t["system"], "stage": t["stage"], "discipline": t["discipline"], "due_date": None,
                          "created_by": "Site Factory Admin", "created_by_company": owner_id, "created_at": now_iso(),
                          "last_updated": now_iso(), "closed_at": None, "closed_by": None, "document_ids": doc_ids})

    # RACF GA plan per floor - used as door / utility evidence when no dedicated Door doc matches
    racf_floor_ga_docs = {}
    for d in documents:
        if d["building"] == "RACF" and d.get("floor"):
            racf_floor_ga_docs.setdefault(d["floor"], []).append(d["id"])

    # RACF + ILA common room-level Skirting (all rooms) + Sanitary (wet rooms) + Door
    ila_floor_ga_docs = {}
    for d in documents:
        if d["building"] == "ILA" and d.get("floor"):
            ila_floor_ga_docs.setdefault(d["floor"], []).append(d["id"])
    for (rid, floor, rname, kws, wet, bld) in room_nodes:
        bga = racf_floor_ga_docs if bld == "RACF" else ila_floor_ga_docs
        sk = match_docs("Skirting", bld, kws) or match_docs("Skirting", bld, None)[:3]
        make_visi("Skirting", rid, sk)
        if wet:
            sn = match_docs("Sanitary", bld, kws) or match_docs("Sanitary", bld, ["Ensuite", "Amenities", "Bathroom"]) or match_docs("Sanitary", bld, None)
            make_visi("Sanitary", rid, sn)
        dr = match_docs("Door", bld, kws) or bga.get(floor, [])[:2]
        make_visi("Door", rid, dr)

    # RACF bedrooms (Level 1 / Level 2): Door + Skirting Visi per bedroom, keyed off its room number
    for (rid, floor, room_no, type_desc) in bedroom_nodes:
        dr = match_docs("Door", "RACF", [room_no]) or racf_floor_ga_docs.get(floor, [])[:2]
        make_visi("Door", rid, dr)
        sk = match_docs("Skirting", "RACF", [room_no]) or match_docs("Skirting", "RACF", None)[:2]
        make_visi("Skirting", rid, sk)

    # RACF fire safety utilities - one trackable Visi per item type, per floor, evidenced by that floor's GA plan
    for floor in RACF_ALL_FLOORS:
        util_zone = racf_util_zones[floor]
        for (label, kws) in RACF_UTILITY_ITEMS:
            docs = racf_floor_ga_docs.get(floor, [])
            make_visi("Miscellaneous", util_zone, docs)
            visi_docs[-1]["fixture_label"] = label
            visi_docs[-1]["template_name"] = f"Utility · {label} · {floor}"

    # ILA fire safety utilities (FE-JC / FH items shown on the ILA GA plans)
    for floor, util_zone in ila_util_zones.items():
        for (label, kws) in RACF_UTILITY_ITEMS:
            docs = ila_floor_ga_docs.get(floor, [])
            make_visi("Miscellaneous", util_zone, docs)
            visi_docs[-1]["fixture_label"] = label
            visi_docs[-1]["template_name"] = f"Utility · {label} · {floor}"

    # ILA per-apartment: Skirting + Sanitary on the apartment, a Door Visi per bedroom
    # (each bedroom door gets its own page) and per ensuite, plus a Robe Jamb Visi per bedroom.
    ila_door_schedules = [d["id"] for d in documents if d["discipline"] == "Door" and (d.get("drawing_no") or "").startswith("A29")]
    for (aid, num, typ, beds, lvl_idx) in apts:
        type_plan = match_docs("Skirting", "ILA", [f"Apartment Type {typ} Plan"])
        floor_name = ILA_LEVELS[lvl_idx]
        ga_docs = [d["id"] for d in documents if d["discipline"] in ("Skirting", "Sanitary") and d["building"] == "ILA" and d.get("floor") == floor_name]
        make_visi("Skirting", aid, type_plan + ga_docs or match_docs("Skirting", "ILA", ["Apartment"]))
        make_visi("Sanitary", aid, type_plan + ga_docs or match_docs("Sanitary", "ILA", None))
        for (rid, rname, active) in apt_rooms[aid]:
            if not active:
                continue
            if rname.startswith("Bedroom"):
                make_visi("Door", rid, type_plan + ila_door_schedules)
                make_visi("Robe Jamb", rid, type_plan)
            elif rname == "Ensuite":
                make_visi("Door", rid, type_plan + ila_door_schedules)

    # Doors at each building floor that has door drawings
    door_floor_docs = {}
    for d in documents:
        if d["discipline"] == "Door":
            door_floor_docs.setdefault(d["location_id"], []).append(d["id"])
    for loc_id, ids in door_floor_docs.items():
        make_visi("Door", loc_id, ids)

    # Miscellaneous fixtures -> one trackable Visi per fixture type
    misc_groups = {}
    for d in documents:
        if d["discipline"] != "Miscellaneous":
            continue
        cat = d["category"] or "Plans"
        label = cat.split("/")[-1].strip()
        if label in ("Plans", "Miscellaneous"):
            label = "General Miscellaneous & Markups"
        misc_groups.setdefault(label, []).append(d["id"])
    for label, ids in sorted(misc_groups.items()):
        make_visi("Miscellaneous", fixtures_zone, ids)
        visi_docs[-1]["fixture_label"] = label
        visi_docs[-1]["template_name"] = f"Misc · {label}"

    if visi_docs:
        await db.visis.insert_many([dict(v) for v in visi_docs])
