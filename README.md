# Telecom Rate Matching Pipeline

Matches provider facility records to a list of target jurisdictions (state and county) and produces a cleaned, jurisdiction-level rate dataset with one row per jurisdiction.

Built with pandas, fuzzywuzzy, and openpyxl for matching. Streamlit and Plotly for the dashboard.

## Dashboard

**Live:** [worthrisestelecomrates.streamlit.app](https://worthrisestelecomrates.streamlit.app/)

To run locally:

```bash
cd src
streamlit run dashboard.py
```

## Project structure

```
data/
  raw/
    staff_technologist_data_test.xlsx   # input workbook
outputs/
  matched_telecom_rates.csv            # final matched dataset
  match_review.csv                     # jurisdictions needing review
src/
  entity_resolution.py                 # matching rules and scoring
  clean_and_match.py                   # pipeline orchestrator
  dashboard.py                         # Streamlit dashboard
tests/
  test_entity_resolution.py            # 31 unit tests
docs/
  data_dictionary.md                   # column definitions
requirements.txt
```

## Running the pipeline

```bash
pip install -r requirements.txt
python src/clean_and_match.py
```

This reads `data/raw/staff_technologist_data_test.xlsx`, runs matching, and writes the output CSV files to `outputs/`.

## How matching works

The pipeline does three things: classify facilities, match them to jurisdictions, and aggregate rates.

### Facility classification

Each facility name is classified based on keyword rules:

- **Excluded:** juvenile, federal, police, court, work release, community corrections, transitional, reentry, probation, parole, electronic monitoring
- **County candidate:** jail, sheriff, detention, corrections, county prison, law enforcement center, criminal justice center
- **State candidate:** DOC, department of corrections, state prison, correctional center/facility
- **Review:** anything that doesn't clearly fit the above

### Matching

State jurisdictions match to all same-state facilities classified as state candidates.

County jurisdictions use state-blocked record linkage with an additive scoring system (0-100):

- +80 if the provider's county field matches the target county
- +70 if the target county name appears in the facility name
- +20 for jail/sheriff/detention keywords
- +15 for high fuzzy similarity (fuzzywuzzy ratio >= 85), +8 for moderate (>= 65)

A county phrase filter handles ambiguous names. When multiple facilities match a county but some have the explicit phrase "<county> COUNTY" in the name and others just happen to contain the county name (e.g., "LAKE COUNTY DETENTION CENTER" vs "CCA LAKE CITY CORRECTIONAL FACILITY"), only the explicit matches are kept.

Facilities scoring 85+ are marked `matched`. Scores 70-84 are marked `review`. Below 70, `no_match`.

### Rate aggregation

For each jurisdiction, the median in-state and out-of-state rates across all matched facilities are used. All matched facility names are listed in the output for auditability.

## Results

163 jurisdictions processed: 160 matched, 1 review (PINAL, AZ), 2 no match (LEE, KY and PASQUOTANK, NC).

The two no-match counties have no facility in the raw data that passes the score threshold — these would need manual lookup.

## Tests

```bash
cd tests
python -m pytest test_entity_resolution.py -v
```

31 tests covering text normalization, facility classification (including state DOC precedence, private operator detection, generic term handling, and RE-ENTRY normalization), county matching scores, and the county phrase filter.
