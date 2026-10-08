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
