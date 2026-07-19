"""Tests for the entity resolution helpers."""

import sys
from pathlib import Path

# Make src/ importable when running from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_resolution import (
    classify_facility,
    county_key,
    county_match_score,
    has_explicit_county_phrase,
    normalize_text,
)


class TestNormalizeText:
    def test_basic_uppercasing_and_whitespace(self):
        assert normalize_text("  franklin county  jail ") == "FRANKLIN COUNTY JAIL"

    def test_ampersand_replacement(self):
        assert normalize_text("law & order") == "LAW AND ORDER"

    def test_strips_punctuation(self):
        assert normalize_text("st. mary's") == "ST MARY S"

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""


class TestCountyKey:
    def test_removes_county_keyword(self):
        assert county_key("Franklin County") == "FRANKLIN"

    def test_plain_name(self):
        assert county_key("LEE") == "LEE"


class TestClassifyFacility:
    def test_juvenile_excluded(self):
        label, _ = classify_facility("IL DOC - ILLINOIS YOUTH CENTER - CHICAGO")
        assert label == "exclude"

    def test_police_excluded(self):
        label, _ = classify_facility("ALTON CITY POLICE DEPT")
        assert label == "exclude"

    def test_work_release_excluded(self):
        label, _ = classify_facility("AL DOC - CAMDEN COMMUNITY WORK RELEASE/CENTER")
        assert label == "exclude"

    def test_county_jail_included(self):
        label, _ = classify_facility("FRANKLIN COUNTY JAIL")
        assert label == "county_candidate"

    def test_sheriff_included(self):
        label, _ = classify_facility("FLAGLER COUNTY SHERIFF'S OFFICE")
        assert label == "county_candidate"

    def test_state_doc_included(self):
        label, _ = classify_facility("GA DOC - AUTRY STATE PRISON")
        assert label == "state_candidate"

    def test_ambiguous_name_returns_review(self):
        label, _ = classify_facility("SOME RANDOM FACILITY")
        assert label == "review"


class TestCountyMatchScore:
    def test_exact_county_field_match(self):
        score = county_match_score("FRANKLIN", "FRANKLIN COUNTY JAIL", "FRANKLIN")
        assert score >= 85

    def test_county_in_facility_name(self):
        score = county_match_score("BROWARD", "BROWARD COUNTY MAIN JAIL", "")
        assert score >= 70

    def test_no_match(self):
        score = county_match_score("PASQUOTANK", "ALBEMARLE DISTRICT JAIL", "")
        assert score < 70

    def test_empty_inputs(self):
        assert county_match_score("", "", "") == 0


class TestHasExplicitCountyPhrase:
    def test_explicit_county_in_name(self):
        assert has_explicit_county_phrase("LAKE", "LAKE COUNTY DETENTION CENTER") is True

    def test_bare_name_without_county_word(self):
        assert has_explicit_county_phrase("LAKE", "CCA LAKE CITY CORRECTIONAL FACILITY") is False

    def test_county_name_with_sheriff(self):
        assert has_explicit_county_phrase("MARQUETTE", "MARQUETTE SHERIFF'S DEPT") is False
