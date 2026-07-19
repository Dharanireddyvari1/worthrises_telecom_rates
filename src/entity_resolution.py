"""Small, explainable helpers for matching provider facilities to jurisdictions."""

import re
from fuzzywuzzy import fuzz


EXCLUDE_TERMS = (
    "JUVENILE",
    "YOUTH",
    "FEDERAL",
    "POLICE DEPT",
    "POLICE DEPARTMENT",
    "MUNICIPAL COURT",
    "COURT",
    "WORK RELEASE",
    "COMMUNITY CORRECTION",
    "COMMUNITY CORRECTIONS",
    "TRANSITION",
    "TRANSITIONAL",
    "REENTRY",
    "RE-ENTRY",
    "PROBATION",
    "PAROLE",
    "ELECTRONIC MONITORING",
    "STATE HOSPITAL",
)

COUNTY_INCLUDE_TERMS = (
    "JAIL",
    "SHERIFF",
    "DETENTION",
    "CORRECTIONS",
    "COUNTY DOC",
    "COUNTY PRISON",
    "CORRECTIONAL COMPLEX",
    "CORRECTIONAL FACILITY",
    "LAW ENFORCEMENT CENTER",
    "CRIMINAL JUSTICE CENTER",
    "SHERFF",
)

STATE_INCLUDE_TERMS = (
    " DOC ",
    "DEPARTMENT OF CORRECTIONS",
    "CORRECTIONAL CENTER",
    "CORRECTIONAL FACILITY",
    "STATE PRISON",
)

# Normalize facility and jurisdiction names before comparison.
def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).upper().replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

# Extract the county name from a jurisdiction value.
def county_key(value: object) -> str:
    text = normalize_text(value)
    text = re.sub(r"\bCOUNTY\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


# Check if any of the given terms are present in the text.
def has_any(text: str, terms: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(term in padded or term in text for term in terms)

# Classify a facility based on its name. Return a simple include/exclude/review classification and reason.
def classify_facility(facility_name: object) -> tuple[str, str]:
    
    name = f" {normalize_text(facility_name)} "
    for term in EXCLUDE_TERMS:
        if term in name:
            return "exclude", f"facility name contains '{term.lower()}'"

    if has_any(name, COUNTY_INCLUDE_TERMS):
        return "county_candidate", "county jail/sheriff/detention keyword"

    if has_any(name, STATE_INCLUDE_TERMS):
        return "state_candidate", "state prison/DOC keyword"

    return "review", "no clear jail/prison keyword"

# Check if '<county> COUNTY' appears in the facility name.
def has_explicit_county_phrase(county: str, facility_name: str) -> bool:
    county_norm = county_key(county)
    facility_norm = normalize_text(facility_name)
    return f"{county_norm} COUNTY" in facility_norm

# Score one county jurisdiction against one facility record. Correctional facility keywords, and light fuzzy similarity.
def county_match_score(county: object, facility_name: object, raw_county: object = None) -> int:
    county_norm = county_key(county)
    facility_norm = normalize_text(facility_name)
    raw_county_norm = county_key(raw_county)
    if not county_norm or not facility_norm:
        return 0

    score = 0
    if raw_county_norm and raw_county_norm == county_norm:
        score += 80
    if re.search(rf"\b{re.escape(county_norm)}\b", facility_norm):
        score += 70
    if has_any(facility_norm, COUNTY_INCLUDE_TERMS):
        score += 20

    ratio = fuzz.ratio(county_norm, facility_norm) / 100
    if ratio >= 0.85:
        score += 15
    elif ratio >= 0.65:
        score += 8

    return min(score, 100)
