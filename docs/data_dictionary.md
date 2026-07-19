# Data Dictionary

## outputs/matched_telecom_rates.csv

| Column | Meaning |
| --- | --- |
| `type` | Jurisdiction type from the reference list: `state` or `county`. |
| `state` | Two-letter state abbreviation. |
| `county` | County name for county jail jurisdictions; blank for state prison systems. |
| `match_status` | `matched`, `review`, or `no_match`. |
| `match_reason` | Short explanation of why the row received its match status. |
| `matched_facility_count` | Number of provider facilities included in the jurisdiction-level aggregate. |
| `matched_facilities` | Provider facility names used for the match, limited for readability. |
| `in_state_rate` | Median per-minute in-state phone rate across matched facilities. |
| `out_of_state_rate` | Median per-minute out-of-state phone rate across matched facilities. |

## outputs/match_review.csv

Contains every jurisdiction where `match_status` is not `matched`. These rows should be reviewed before a public release.

## outputs/validation_summary.csv

Run-level checks showing input row counts, output row counts, status counts, duplicate target rows, and whether the output contains exactly one row per target jurisdiction.
