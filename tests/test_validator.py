"""Unit tests for app.validator — coded against docs/contract.md only."""

import pytest

from app.validator import (
    is_quarter_step,
    parse_power,
    validate_eye,
    validate_prescription,
)


# --- helpers -----------------------------------------------------------------

def _codes(errors):
    return {(e["eye"], e["field"], e["code"]) for e in errors}


def _field_codes(errors, eye, field):
    return {e["code"] for e in errors if e["eye"] == eye and e["field"] == field}


# --- is_quarter_step ---------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        (-0.75, True),
        (0.1, False),
        (0.0, True),
        (1.25, True),
        (-0.50, True),
        (0.01, False),
    ],
)
def test_is_quarter_step(value, expected):
    assert is_quarter_step(value) is expected


# --- parse_power / valid SPH shapes ------------------------------------------

@pytest.mark.parametrize(
    "raw, expected_value",
    [
        ("+1.25", 1.25),
        ("plano", 0.0),
        ("pl", 0.0),
        ("PL", 0.0),
        ("-0.50", -0.50),
        (None, None),
        ("", None),
    ],
)
def test_parse_power_accepts_known_shapes(raw, expected_value):
    value, err = parse_power(raw)
    assert err is None
    assert value == expected_value


def test_parse_power_not_a_number():
    value, err = parse_power("abc")
    assert value is None
    assert err == "NOT_A_NUMBER"


# --- valid prescriptions -----------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        # full Rx both eyes
        {
            "right": {"sph": "-1.25", "cyl": "-0.50", "axis": "90"},
            "left": {"sph": "-2.00", "cyl": "-0.75", "axis": "180"},
        },
        # plano SPH with blank cyl/axis
        {
            "right": {"sph": "plano", "cyl": "", "axis": ""},
            "left": {"sph": "pl", "cyl": None, "axis": None},
        },
        # leading plus on SPH
        {
            "right": {"sph": "+1.25", "cyl": "", "axis": ""},
            "left": {"sph": "+0.50", "cyl": "0", "axis": ""},
        },
    ],
)
def test_valid_prescriptions(payload):
    result = validate_prescription(payload)
    assert result["valid"] is True
    assert result["errors"] == []
    assert "right" in result["normalized"]
    assert "left" in result["normalized"]


# --- SPH errors --------------------------------------------------------------

@pytest.mark.parametrize(
    "sph, code",
    [
        ("", "REQUIRED"),
        (None, "REQUIRED"),
        ("25", "OUT_OF_RANGE"),
        (25, "OUT_OF_RANGE"),
        ("1.30", "BAD_STEP"),
        (1.30, "BAD_STEP"),
        ("abc", "NOT_A_NUMBER"),
    ],
)
def test_sph_error_codes(sph, code):
    errors, _ = validate_eye("right", {"sph": sph, "cyl": "", "axis": ""})
    assert code in _field_codes(errors, "right", "sph")


# --- Phase 4.1: input length cap ----------------------------------------------

def test_too_long_sph_rejected_before_parsing():
    errors, _ = validate_eye(
        "right", {"sph": "1" * 21, "cyl": "", "axis": ""}
    )
    assert "TOO_LONG" in _field_codes(errors, "right", "sph")
    assert "NOT_A_NUMBER" not in _field_codes(errors, "right", "sph")


def test_too_long_cyl_rejected_before_parsing():
    errors, _ = validate_eye(
        "left", {"sph": "-1.00", "cyl": "-" + "0" * 21, "axis": "90"}
    )
    assert "TOO_LONG" in _field_codes(errors, "left", "cyl")


def test_too_long_axis_rejected_before_parsing():
    errors, _ = validate_eye(
        "right", {"sph": "-1.00", "cyl": "-0.50", "axis": "9" * 21}
    )
    assert "TOO_LONG" in _field_codes(errors, "right", "axis")


def test_input_at_exactly_max_length_is_not_too_long():
    # pad an otherwise-valid value with trailing zeros to exactly MAX_INPUT_LEN (20)
    # chars, to prove the boundary is ">20", not ">=20".
    padded = "-1.25" + "0" * (20 - len("-1.25"))
    assert len(padded) == 20
    errors, _ = validate_eye("right", {"sph": padded, "cyl": "", "axis": ""})
    assert "TOO_LONG" not in _field_codes(errors, "right", "sph")


# --- CYL errors --------------------------------------------------------------

@pytest.mark.parametrize(
    "cyl, code",
    [
        ("-7", "OUT_OF_RANGE"),
        (-7, "OUT_OF_RANGE"),
        ("-0.30", "BAD_STEP"),
        (-0.30, "BAD_STEP"),
    ],
)
def test_cyl_error_codes(cyl, code):
    errors, _ = validate_eye(
        "left", {"sph": "-1.00", "cyl": cyl, "axis": "90"}
    )
    assert code in _field_codes(errors, "left", "cyl")


def test_cyl_nonzero_blank_axis_requires_axis():
    errors, _ = validate_eye(
        "right", {"sph": "-1.00", "cyl": "-1.00", "axis": ""}
    )
    assert "AXIS_REQUIRED" in _field_codes(errors, "right", "axis")


# --- Axis errors -------------------------------------------------------------

@pytest.mark.parametrize(
    "axis, code",
    [
        ("0", "OUT_OF_RANGE"),
        (0, "OUT_OF_RANGE"),
        ("181", "OUT_OF_RANGE"),
        (181, "OUT_OF_RANGE"),
        ("90.5", "AXIS_NOT_INTEGER"),
        (90.5, "AXIS_NOT_INTEGER"),
    ],
)
def test_axis_error_codes(axis, code):
    errors, _ = validate_eye(
        "right", {"sph": "-1.00", "cyl": "-0.50", "axis": axis}
    )
    assert code in _field_codes(errors, "right", "axis")


def test_axis_without_cyl():
    errors, _ = validate_eye(
        "left", {"sph": "-1.00", "cyl": "0", "axis": "90"}
    )
    assert "AXIS_WITHOUT_CYL" in _field_codes(errors, "left", "axis")


# --- both eyes, collect-all --------------------------------------------------

def test_both_eyes_bad_returns_errors_for_both():
    result = validate_prescription(
        {
            "right": {"sph": "abc", "cyl": "", "axis": ""},
            "left": {"sph": "25", "cyl": "", "axis": ""},
        }
    )
    assert result["valid"] is False
    eyes = {e["eye"] for e in result["errors"]}
    assert "right" in eyes
    assert "left" in eyes
    assert "NOT_A_NUMBER" in _field_codes(result["errors"], "right", "sph")
    assert "OUT_OF_RANGE" in _field_codes(result["errors"], "left", "sph")


# --- malformed payload: never raise, MISSING_EYE -----------------------------

@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"right": "x"},
    ],
)
def test_malformed_payload_no_exception_missing_eye(payload):
    result = validate_prescription(payload)
    assert isinstance(result, dict)
    assert result["valid"] is False
    codes = {e["code"] for e in result["errors"]}
    assert "MISSING_EYE" in codes


# --- v2: suggestions (2.3) ----------------------------------------------------

def test_suggestion_bad_step_nearest_quarter():
    errors, _ = validate_eye("right", {"sph": "1.30", "cyl": "", "axis": ""})
    err = next(e for e in errors if e["code"] == "BAD_STEP")
    assert err["suggestion"] == {
        "field": "sph", "value": "+1.25",
        "reason": 'Nearest valid 0.25 D step to "1.30".',
    }


def test_suggestion_axis_zero_to_180():
    errors, _ = validate_eye("left", {"sph": "-1.00", "cyl": "-0.50", "axis": "0"})
    err = next(e for e in errors if e["field"] == "axis" and e["code"] == "OUT_OF_RANGE")
    assert err["suggestion"] == {
        "field": "axis", "value": 180,
        "reason": "Axis 0 is invalid; 180 means the same orientation.",
    }


def test_suggestion_missing_decimal_positive():
    errors, _ = validate_eye("right", {"sph": "125", "cyl": "", "axis": ""})
    err = next(e for e in errors if e["field"] == "sph")
    assert err["code"] == "OUT_OF_RANGE"
    assert err["suggestion"]["field"] == "sph"
    assert err["suggestion"]["value"] == "+1.25"


def test_suggestion_missing_decimal_negative():
    errors, _ = validate_eye("right", {"sph": "-125", "cyl": "", "axis": ""})
    err = next(e for e in errors if e["field"] == "sph")
    assert err["suggestion"]["value"] == "-1.25"


def test_suggestion_axis_typed_in_cyl():
    errors, _ = validate_eye("right", {"sph": "-1.00", "cyl": "90", "axis": ""})
    err = next(e for e in errors if e["field"] == "cyl")
    assert err["code"] == "OUT_OF_RANGE"
    assert err["suggestion"] == {
        "field": "axis", "value": 90,
        "reason": 'This looks like an Axis value typed into CYL, got "90".',
    }


def test_no_suggestion_when_nothing_matches():
    errors, _ = validate_eye("right", {"sph": "-1.00", "cyl": "-7", "axis": ""})
    err = next(e for e in errors if e["field"] == "cyl")
    assert "suggestion" not in err


# --- v2: warnings & severity split (2.2, 2.4) ---------------------------------

def test_high_power_sph_warning():
    result = validate_prescription({
        "right": {"sph": "-11.00", "cyl": "", "axis": ""},
        "left": {"sph": "-1.00", "cyl": "", "axis": ""},
    })
    assert result["valid"] is True
    codes = {w["code"] for w in result["warnings"]}
    assert "HIGH_POWER" in codes


def test_high_power_cyl_warning():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "-4.00", "axis": "90"},
        "left": {"sph": "-1.00", "cyl": "", "axis": ""},
    })
    codes = {w["code"] for w in result["warnings"]}
    assert "HIGH_POWER" in codes


def test_plus_cyl_warning():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "+0.50", "axis": "90"},
        "left": {"sph": "-1.00", "cyl": "", "axis": ""},
    })
    codes = {w["code"] for w in result["warnings"]}
    assert "PLUS_CYL" in codes


def test_anisometropia_warning_still_valid():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "", "axis": ""},
        "left": {"sph": "-4.00", "cyl": "", "axis": ""},
    })
    assert result["valid"] is True
    codes = {w["code"] for w in result["warnings"]}
    assert "ANISOMETROPIA" in codes


def test_antimetropia_warning():
    result = validate_prescription({
        "right": {"sph": "-2.00", "cyl": "", "axis": ""},
        "left": {"sph": "+2.00", "cyl": "", "axis": ""},
    })
    codes = {w["code"] for w in result["warnings"]}
    assert "ANTIMETROPIA" in codes


def test_warnings_never_block_valid_but_errors_do():
    result = validate_prescription({
        "right": {"sph": "abc", "cyl": "", "axis": ""},
        "left": {"sph": "-1.00", "cyl": "", "axis": ""},
    })
    assert result["valid"] is False
    assert result["errors"] != []


# --- v2: summary (2.5) ---------------------------------------------------------

def test_summary_spherical_equivalent_and_transposed():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "-0.50", "axis": "90"},
        "left": {"sph": "plano", "cyl": "", "axis": ""},
    })
    right_summary = result["summary"]["right"]
    assert right_summary["se"] == "-1.25"
    assert right_summary["transposed"] == {"sph": "-1.50", "cyl": "+0.50", "axis": 180}


def test_summary_transposed_cyl_is_not_negative_zero():
    result = validate_prescription({
        "right": {"sph": "plano", "cyl": "", "axis": ""},
        "left": {"sph": "-1.00", "cyl": "0", "axis": ""},
    })
    assert result["summary"]["right"]["transposed"]["cyl"] == "+0.00"
    assert result["summary"]["left"]["transposed"]["cyl"] == "+0.00"


def test_summary_empty_when_eye_has_errors():
    result = validate_prescription({
        "right": {"sph": "abc", "cyl": "", "axis": ""},
        "left": {"sph": "-1.00", "cyl": "", "axis": ""},
    })
    assert result["summary"]["right"] == {
        "se": None, "transposed": {"sph": None, "cyl": None, "axis": None},
    }
    assert result["summary"]["left"]["se"] == "-1.00"


# --- v2: plausibility score & bands (2.6) --------------------------------------

def test_plausibility_typical_no_warnings():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "-0.50", "axis": "90"},
        "left": {"sph": "-1.25", "cyl": "", "axis": ""},
    })
    assert result["plausibility"] == {"score": 100, "band": "typical", "reasons": []}


def test_plausibility_double_check_band():
    result = validate_prescription({
        "right": {"sph": "-1.00", "cyl": "-0.50", "axis": "90"},
        "left": {"sph": "-10.00", "cyl": "0", "axis": ""},
    })
    assert result["plausibility"]["score"] == 65
    assert result["plausibility"]["band"] == "double_check"


def test_plausibility_verify_band():
    result = validate_prescription({
        "right": {"sph": "-11.00", "cyl": "", "axis": ""},
        "left": {"sph": "+11.00", "cyl": "", "axis": ""},
    })
    assert result["plausibility"]["score"] < 50
    assert result["plausibility"]["band"] == "verify"


def test_plausibility_default_on_malformed_payload():
    result = validate_prescription(None)
    assert result["plausibility"] == {"score": 100, "band": "typical", "reasons": []}
    assert result["warnings"] == []
    assert result["summary"] == {}
