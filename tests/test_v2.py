"""v2 behaviour: edge-case parsing, suggestions, warnings, summary, scores, anomaly model, API extras."""

import pytest
from fastapi.testclient import TestClient

from app import anomaly
from app.main import app
from app.validator import parse_power
from app.validator import transpose, validate_eye, validate_prescription

client = TestClient(app)


def rx(r, l):
    return {"right": dict(zip(("sph", "cyl", "axis"), r)), "left": dict(zip(("sph", "cyl", "axis"), l))}


def err(result, eye, field):
    return next(e for e in result["errors"] if e["eye"] == eye and e["field"] == field)


def codes(result, key="warnings"):
    return [w["code"] for w in result[key]]


TYPICAL = rx(("-1.25", "-0.50", "180"), ("-1.00", "-0.75", "5"))


# ---- parsing edge cases -----------------------------------------------------
@pytest.mark.parametrize("raw, value", [
    ("-1,25", -1.25), ("-1.25 DS", -1.25), ("-0.50D", -0.5), (".75", 0.75), ("Plano", 0.0),
    ("piano", 0.0), ("- 1.25", -1.25), ("+0", 0.0),
])
def test_parse_power_lenient_forms(raw, value):
    assert parse_power(raw) == (value, None)


@pytest.mark.parametrize("raw", ["1e1", "nan", "inf", "--1", "+-1", "1.2.3", "abc", [], {}, True])
def test_parse_power_rejects(raw):
    assert parse_power(raw)[1] == "NOT_A_NUMBER"


def test_too_long_input():
    r = validate_prescription(rx(("1" * 50, "", ""), ("-1", "", "")))
    assert err(r, "right", "sph")["code"] == "TOO_LONG"


@pytest.mark.parametrize("axis", ["x90", "X 90", "90°", "090", "@90", "90 deg"])
def test_axis_notations(axis):
    errors, norm = validate_eye("right", {"sph": "-1", "cyl": "-0.5", "axis": axis})
    assert errors == [] and norm["axis"] == 90


def test_no_negative_zero():
    _, norm = validate_eye("right", {"sph": "-0", "cyl": "-0.00", "axis": ""})
    assert norm == {"sph": "+0.00", "cyl": "+0.00", "axis": None}


def test_aliases_od_os_and_uppercase_fields():
    r = validate_prescription({"OD": {"SPH": "-1.25", "CYL": "-0.5", "AXIS": "180"},
                               "os": {"Sphere": "-1", "Cylinder": "-0.75", "Ax": "5"}})
    assert r["valid"] is True


def test_cyl_invalid_still_reports_bad_axis():
    r = validate_prescription(rx(("-1", "-7", "200"), ("-1", "", "")))
    assert {e["field"] for e in r["errors"] if e["eye"] == "right"} == {"cyl", "axis"}


# ---- suggestions ------------------------------------------------------------
@pytest.mark.parametrize("r, field, sug_field, sug_value", [
    (("1.30", "", ""), "sph", "sph", "+1.25"),
    (("-125", "", ""), "sph", "sph", "-1.25"),
    (("125", "", ""), "sph", "sph", "+1.25"),
    (("-1", "-0.5", "0"), "axis", "axis", 180),
    (("-1", "-0.5", "270"), "axis", "axis", 90),
    (("-1", "-0.5", "90.4"), "axis", "axis", 90),
    (("-1", "90", ""), "cyl", "axis", 90),
    (("-1", "0", "90"), "axis", "axis", ""),
])
def test_suggestions(r, field, sug_field, sug_value):
    e = err(validate_prescription(rx(r, ("-1", "", ""))), "right", field)
    assert e["suggestion"]["field"] == sug_field and e["suggestion"]["value"] == sug_value


def test_no_suggestion_key_when_none():
    e = err(validate_prescription(rx(("abc", "", ""), ("-1", "", ""))), "right", "sph")
    assert "suggestion" not in e


# ---- warnings, severity, summary, plausibility ------------------------------
def test_anisometropia_is_warning_not_error():
    r = validate_prescription(rx(("-1.00", "", ""), ("-4.00", "", "")))
    assert r["valid"] is True and "ANISOMETROPIA" in codes(r)
    assert r["plausibility"]["band"] == "double_check"


def test_antimetropia_high_power_plus_cyl_mixed():
    r = validate_prescription(rx(("-2.00", "+1.00", "90"), ("+11.00", "-4.00", "90")))
    c = codes(r)
    assert {"ANTIMETROPIA", "HIGH_POWER", "PLUS_CYL", "MIXED_CYL_NOTATION", "ANISOMETROPIA"} <= set(c)
    assert r["valid"] is True and r["plausibility"]["band"] == "verify"


def test_summary_and_transpose():
    r = validate_prescription(rx(("-1.00", "-0.50", "90"), ("plano", "", "")))
    assert r["summary"]["right"] == {"se": "-1.25", "transposed": {"sph": "-1.50", "cyl": "+0.50", "axis": 180}}
    assert transpose(-1.0, -0.5, 180)["axis"] == 90


def test_malformed_payload_v2_shape():
    r = validate_prescription(None)
    assert r["warnings"] == [] and r["plausibility"]["score"] == 100 and r["anomaly"] is None


# ---- anomaly model (ML) -----------------------------------------------------
def test_anomaly_typical_vs_unusual():
    typical = validate_prescription(TYPICAL)["anomaly"]
    weird = validate_prescription(rx(("-1.00", "-2.50", "45"), ("-6.00", "-0.50", "45")))["anomaly"]
    assert typical["band"] == "typical" and weird["band"] == "rare"
    assert weird["typicality"] < typical["typicality"] and weird["top_factors"]


def test_anomaly_null_when_errors():
    assert validate_prescription(rx(("abc", "", ""), ("-1", "", "")))["anomaly"] is None


def test_anomaly_fit_learns_from_data():
    params = anomaly.fit(anomaly.synthetic_records(3000))
    assert params["n"] == 3000 and params["source"].startswith("fitted")
    assert -2.0 < params["features"]["se_mean"]["median"] < 0.0
    with pytest.raises(ValueError):
        anomaly.fit(anomaly.synthetic_records(5))


# ---- API extras -------------------------------------------------------------
def test_rules_endpoint():
    r = client.get("/rules").json()
    assert r["sph"]["min"] == -20.0 and r["axis"]["max"] == 180


def test_payload_too_large():
    r = client.post("/validate", content=b'{"x":"' + b"a" * 20000 + b'"}', headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["errors"][0]["code"] == "PAYLOAD_TOO_LARGE"


def test_batch():
    r = client.post("/validate/batch", json=[TYPICAL, rx(("abc", "", ""), ("-1", "", ""))])
    assert r.status_code == 200 and r.json()["count"] == 2 and r.json()["valid_count"] == 1
    assert client.post("/validate/batch", json={}).status_code == 400
