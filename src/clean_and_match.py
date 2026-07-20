"""Build a cleaned telecom rate dataset from the input raw dataset."""

from pathlib import Path

import pandas as pd

from entity_resolution import (
    classify_facility,
    county_match_score,
    has_explicit_county_phrase,
    normalize_text,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "staff_technologist_data_test.xlsx"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "matched_telecom_rates.csv"
DEFAULT_REVIEW = PROJECT_ROOT / "outputs" / "match_review.csv"

RAW_COLUMNS = ["provider", "state", "county", "facility_id", "facility_name", "phone", "in_state", "per_min"]
JURISDICTION_COLUMNS = ["type", "state", "county"]


# Load raw provider and jurisdictions sheets from the Excel file
def load_inputs(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(path, sheet_name="Raw Data", usecols="A:H")
    jurisdictions = pd.read_excel(path, sheet_name="Jurisdictions to Match", usecols="A:C")
    raw = raw.dropna(how="all")
    jurisdictions = jurisdictions.dropna(how="all")
    validate_input_columns(raw, jurisdictions)
    return raw, jurisdictions


# Verify required columns exist in both DataFrames and raise if missing
def validate_input_columns(raw: pd.DataFrame, jurisdictions: pd.DataFrame) -> None:
    missing_raw = [column for column in RAW_COLUMNS if column not in raw.columns]
    missing_jurisdictions = [column for column in JURISDICTION_COLUMNS if column not in jurisdictions.columns]
    if missing_raw or missing_jurisdictions:
        problems = []
        if missing_raw:
            problems.append(f"raw data missing columns: {', '.join(missing_raw)}")
        if missing_jurisdictions:
            problems.append(f"jurisdiction list missing columns: {', '.join(missing_jurisdictions)}")
        raise ValueError("; ".join(problems))


# Produce a cleaned rates table with normalized names and pivoted rates
def prepare_rates(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["state"] = raw["state"].astype(str).str.upper().str.strip()
    raw["county"] = raw["county"].fillna("")
    raw["facility_name_clean"] = raw["facility_name"].map(normalize_text)
    raw[["facility_class", "class_reason"]] = pd.DataFrame(
        raw["facility_name"].map(classify_facility).tolist(),
        index=raw.index,
    )

    rates = (
        raw.pivot_table(
            index=[
                "provider",
                "state",
                "county",
                "facility_id",
                "facility_name",
                "facility_name_clean",
                "facility_class",
                "class_reason",
            ],
            columns="in_state",
            values="per_min",
            aggfunc="median",
        )
        .rename(columns={True: "in_state_rate", False: "out_of_state_rate"})
        .reset_index()
    )

    for column in ("in_state_rate", "out_of_state_rate"):
        if column not in rates:
            rates[column] = pd.NA
    return rates


# Build a summary dict for a target jurisdiction and its matched candidates
def summarize_match(target: pd.Series, candidates: pd.DataFrame, status: str, reason: str) -> dict:
    return {
        "type": target["type"],
        "state": target["state"],
        "county": target.get("county"),
        "match_status": status,
        "match_reason": reason,
        "matched_facility_count": len(candidates),
        "matched_facilities": "; ".join(candidates["facility_name"].astype(str).sort_values()),
        "in_state_rate": candidates["in_state_rate"].median() if len(candidates) else pd.NA,
        "out_of_state_rate": candidates["out_of_state_rate"].median() if len(candidates) else pd.NA,
    }


# Match a state jurisdiction by locating state correctional facilities
def match_state_jurisdiction(target: pd.Series, rates: pd.DataFrame) -> dict:
    candidates = rates[
        (rates["state"] == target["state"])
        & (rates["facility_class"] == "state_candidate")
    ]
    if candidates.empty:
        return summarize_match(target, candidates, "no_match", "no state prison/DOC facility found")
    return summarize_match(target, candidates, "matched", "state + DOC/correctional facility match")


# Match a county jurisdiction by scoring and filtering same-state facilities
def match_county_jurisdiction(target: pd.Series, rates: pd.DataFrame) -> dict:
    candidates = rates[rates["state"] == target["state"]].copy()
    candidates = candidates[candidates["facility_class"].isin(["county_candidate", "review"])]
    if candidates.empty:
        return summarize_match(target, candidates, "no_match", "no same-state county candidates")

    scores = []
    phrase_flags = []
    for _, row in candidates.iterrows():
        scores.append(county_match_score(target["county"], row["facility_name"], row["county"]))
        phrase_flags.append(has_explicit_county_phrase(target["county"], row["facility_name"]))
    candidates["match_score"] = scores

    # When some candidates have the explicit "<county> COUNTY" phrase in
    # their name and others only contain the bare county name, prefer the
    # explicit matches.  This prevents e.g. "CCA LAKE CITY CORRECTIONAL
    # FACILITY" from competing with "LAKE COUNTY DETENTION CENTER" when
    # matching the LAKE county jurisdiction.
    candidates["has_county_phrase"] = phrase_flags
    if candidates["has_county_phrase"].any():
        candidates = candidates[candidates["has_county_phrase"]].copy()

    scored = candidates[candidates["match_score"] >= 70].sort_values(
        ["match_score", "facility_name"], ascending=[False, True]
    )

    if scored.empty:
        return summarize_match(target, scored, "no_match", "no facility passed score threshold")

    top_score = int(scored["match_score"].max())
    if top_score >= 85:
        candidates = scored[scored["match_score"] >= 85]
        status = "matched"
    else:
        candidates = scored
        status = "review"
    reason = f"state blocked record linkage; top score {top_score}"
    return summarize_match(target, candidates, status, reason)


# Build matches for all targets using state/county matching logic
def build_matches(raw: pd.DataFrame, jurisdictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rates = prepare_rates(raw)
    jurisdictions = jurisdictions.copy()
    jurisdictions["type"] = jurisdictions["type"].astype(str).str.lower().str.strip()
    jurisdictions["state"] = jurisdictions["state"].astype(str).str.upper().str.strip()

    matched_rows = []
    for _, target in jurisdictions.iterrows():
        if target["type"] == "state":
            matched_rows.append(match_state_jurisdiction(target, rates))
        elif target["type"] == "county":
            matched_rows.append(match_county_jurisdiction(target, rates))

    matched = pd.DataFrame(matched_rows)
    review = matched[matched["match_status"].ne("matched")].copy()
    return matched, review


# Entry point that runs the matching workflow using the default file paths
def main() -> None:
    raw, jurisdictions = load_inputs(DEFAULT_INPUT)
    matched, review = build_matches(raw, jurisdictions)

    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    matched.to_csv(DEFAULT_OUTPUT, index=False)
    review.to_csv(DEFAULT_REVIEW, index=False)

    print(f"Wrote {len(matched)} matched jurisdiction rows to {DEFAULT_OUTPUT}")
    print(f"Wrote {len(review)} review rows to {DEFAULT_REVIEW}")
    print(matched["match_status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
