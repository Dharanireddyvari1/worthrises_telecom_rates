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
    "RE ENTRY",
    "PROBATION",
    "PAROLE",
    "ELECTRONIC MONITORING",
    "STATE HOSPITAL",
)

# Private/contracted operator names to flag for review.
PRIVATE_OPERATORS = (
    "CCA",
    "CORECIVIC",
    "GEO GROUP",
    "GEO ",
    "MTC ",
    "MANAGEMENT AND TRAINING",
    "EMERALD",
    "LASALLE",
)

# County-specific terms. These should NOT include generic phrases like
# "CORRECTIONAL FACILITY" or "CORRECTIONAL COMPLEX" which also appear
# in state DOC facilities.
COUNTY_INCLUDE_TERMS = (
    "JAIL",
    "SHERIFF",
    "DETENTION",
    "COUNTY DOC",
    "COUNTY PRISON",
    "COUNTY CORRECTIONS",
    "COUNTY CORRECTIONAL",
    "LAW ENFORCEMENT CENTER",
    "CRIMINAL JUSTICE CENTER",
    "SHERFF",
)

# State DOC pattern: two-letter abbreviation followed by "DOC".
STATE_DOC_PATTERN = re.compile(r"\b[A-Z]{2}\s+DOC\b")

# Strong state-level indicators. Generic terms like "CORRECTIONAL FACILITY"
# or "CORRECTIONAL COMPLEX" are intentionally excluded — they appear in both
# state and county contexts, so without a stronger signal they go to review.
STATE_INCLUDE_TERMS = (
    "DEPARTMENT OF CORRECTIONS",
    "CORRECTIONAL CENTER",
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

# Check if the facility name contains a private/contracted operator name.
def is_private_operator(name: str) -> bool:
    return has_any(name, PRIVATE_OPERATORS)

# Classify a facility based on its name.
# Precedence: exclude -> state DOC prefix -> county keywords -> state keywords -> private -> review.
def classify_facility(facility_name: object) -> tuple[str, str]:

    name = f" {normalize_text(facility_name)} "

    # 1. Excluded facility types always come first.
    for term in EXCLUDE_TERMS:
        if term in name:
            return "exclude", f"facility name contains '{term.lower()}'"

    # 2. Strong state indicator: "<STATE> DOC" prefix takes priority over
    #    any county keywords that might also appear in the name.
    #    e.g. "CO DOC - BENT COUNTY CORRECTIONAL FACILITY" is state, not county.
    if STATE_DOC_PATTERN.search(name):
        return "state_candidate", "state DOC prefix"

    # 3. County-specific keywords (jail, sheriff, detention, county prison).
    if has_any(name, COUNTY_INCLUDE_TERMS):
        # Flag if a private operator is also present.
        if is_private_operator(name):
            return "review", "county keyword but private operator detected"
        return "county_candidate", "county jail/sheriff/detention keyword"

    # 4. Strong state keywords (department of corrections, state prison).
    #    Generic terms like "correctional facility" and "correctional complex"
    #    are NOT included here — without a DOC prefix or other state signal,
    #    they could be either state or county.
    if has_any(name, STATE_INCLUDE_TERMS):
        if is_private_operator(name):
            return "review", "state keyword but private operator detected"
        return "state_candidate", "state prison/correctional keyword"

    # 5. Private operator with no clear jurisdiction signal.
    if is_private_operator(name):
        return "review", "private operator, unclear jurisdiction type"

    return "review", "no clear jail/prison keyword"

# Check if '<county> COUNTY' appears in the facility name.
def has_explicit_county_phrase(county: str, facility_name: str) -> bool:
    county_norm = county_key(county)
    facility_norm = normalize_text(facility_name)
    return f"{county_norm} COUNTY" in facility_norm

# Score one county jurisdiction against one facility record.
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
