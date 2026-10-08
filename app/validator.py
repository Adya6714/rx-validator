"""Pure validation logic for eyeglass prescriptions (SPH, CYL, Axis).

No web framework code here. Every bad input becomes an error dict; nothing raises.
"""

import math

SPH_MIN, SPH_MAX = -20.0, 20.0
CYL_MIN, CYL_MAX = -6.0, 6.0
STEP = 0.25
AXIS_MIN, AXIS_MAX = 1, 180

PLANO_WORDS = {"plano", "pl"}
EYES = ("right", "left")

# v2: clinical plausibility thresholds and scoring (docs/contract.md)
HIGH_POWER_SPH = 10.0
HIGH_POWER_CYL = 4.0
ANISOMETROPIA_SE_DELTA = 2.00
ANTIMETROPIA_SE = 1.00
SCORE_START = 100
SCORE_PENALTY = {"HIGH_POWER": 15, "ANISOMETROPIA": 20, "ANTIMETROPIA": 15}
BAND_TYPICAL_MIN = 80
BAND_DOUBLE_CHECK_MIN = 50


def _is_blank(raw):
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _show(raw):
    """How the received value appears inside an error message."""
    if _is_blank(raw):
        return "empty"
    return f'"{raw}"' if isinstance(raw, str) else str(raw)


def _error(eye, field, code, message):
    return {"eye": eye, "field": field, "code": code, "message": message}


def parse_power(raw):
    """Turn raw input into a float. Returns (value, error_code)."""
    if _is_blank(raw):
        return None, None
    if isinstance(raw, bool):  # True/False are ints in Python; reject them
        return None, "NOT_A_NUMBER"
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if text.lower() in PLANO_WORDS:
            return 0.0, None
        try:
            value = float(text)
        except ValueError:
            return None, "NOT_A_NUMBER"
    else:
        return None, "NOT_A_NUMBER"
    if math.isnan(value) or math.isinf(value):  # float("nan") and float("inf") parse fine
        return None, "NOT_A_NUMBER"
    return value, None


def is_quarter_step(v):
    """True if v is a multiple of 0.25. No modulo: float modulo is unreliable."""
    return abs(v * 4 - round(v * 4)) < 1e-9


def _suggest_out_of_range(field, raw, value, lo, hi, axis_raw):
    """Did-you-mean suggestion for an out-of-range SPH/CYL value (2.3).
    Checked in a fixed order; returns the first match, or None."""
    candidate = value / 100.0
    if lo <= candidate <= hi and is_quarter_step(candidate):
        return {"field": field, "value": f"{candidate:+.2f}",
                "reason": f"Looks like a missing decimal point, got {_show(raw)}."}
    if field == "cyl" and value == int(value):
        whole = int(value)
        if AXIS_MIN <= whole <= AXIS_MAX and _is_blank(axis_raw):
            return {"field": "axis", "value": whole,
                    "reason": f"This looks like an Axis value typed into CYL, got {_show(raw)}."}
    return None


def _check_power(eye, field, label, raw, lo, hi, required, errors, axis_raw=None):
    """Validate SPH or CYL. Returns the parsed value (or None)."""
    Eye = eye.capitalize()
    value, code = parse_power(raw)
    if code:
        errors.append(_error(eye, field, code,
            f"{Eye} eye {label} must be a number like -1.25 or +0.50, got {_show(raw)}."))
        return None
    if value is None:
        if required:
            errors.append(_error(eye, field, "REQUIRED",
                f"{Eye} eye {label} is required (must be between {lo:+.2f} and {hi:+.2f}), got empty."))
        return None
    if not (lo <= value <= hi):
        err = _error(eye, field, "OUT_OF_RANGE",
            f"{Eye} eye {label} must be between {lo:+.2f} and {hi:+.2f}, got {_show(raw)}.")
        suggestion = _suggest_out_of_range(field, raw, value, lo, hi, axis_raw)
        if suggestion:
            err["suggestion"] = suggestion
        errors.append(err)
        return None
    if not is_quarter_step(value):
        nearest = round(value * 4) / 4
        err = _error(eye, field, "BAD_STEP",
            f"{Eye} eye {label} must be in 0.25 steps (e.g. -1.25, -1.50), got {_show(raw)}.")
        err["suggestion"] = {"field": field, "value": f"{nearest:+.2f}",
            "reason": f"Nearest valid 0.25 D step to {_show(raw)}."}
        errors.append(err)
        return None
    return value


def _check_axis(eye, raw, cyl, errors):
    """Validate Axis using the already-parsed CYL value. Returns int or None."""
    Eye = eye.capitalize()
    cyl_is_zero = cyl is None or cyl == 0

    if _is_blank(raw):
        if not cyl_is_zero:
            errors.append(_error(eye, "axis", "AXIS_REQUIRED",
                f"{Eye} eye Axis is required (must be a whole number from {AXIS_MIN} to {AXIS_MAX}) "
                f"when CYL is {cyl:+.2f}, got empty."))
        return None

    value, code = parse_power(raw)
    if code or (isinstance(raw, str) and raw.strip().lower() in PLANO_WORDS):
        errors.append(_error(eye, "axis", "NOT_A_NUMBER",
            f"{Eye} eye Axis must be a whole number from {AXIS_MIN} to {AXIS_MAX}, got {_show(raw)}."))
        return None
    if value != int(value):
        errors.append(_error(eye, "axis", "AXIS_NOT_INTEGER",
            f"{Eye} eye Axis must be a whole number from {AXIS_MIN} to {AXIS_MAX} (no decimals), "
            f"got {_show(raw)}."))
        return None
    axis = int(value)
    if not (AXIS_MIN <= axis <= AXIS_MAX):
        err = _error(eye, "axis", "OUT_OF_RANGE",
            f"{Eye} eye Axis must be a whole number from {AXIS_MIN} to {AXIS_MAX}, got {_show(raw)}.")
        if axis == 0:
            err["suggestion"] = {"field": "axis", "value": AXIS_MAX,
                "reason": "Axis 0 is invalid; 180 means the same orientation."}
        errors.append(err)
        return None
    if cyl_is_zero:
        errors.append(_error(eye, "axis", "AXIS_WITHOUT_CYL",
            f"{Eye} eye Axis should be empty when CYL is 0 or blank, got {_show(raw)}."))
        return None
    return axis


def validate_eye(eye, data):
    """Validate one eye. Returns (errors, normalized)."""
    errors = []
    if not isinstance(data, dict):
        errors.append(_error(eye, "eye", "MISSING_EYE",
            f"{eye.capitalize()} eye data is missing or not an object, got {_show(data)}."))
        return errors, {"sph": None, "cyl": None, "axis": None}

    sph = _check_power(eye, "sph", "SPH", data.get("sph"), SPH_MIN, SPH_MAX, True, errors)
    cyl_raw = data.get("cyl")
    cyl = _check_power(eye, "cyl", "CYL", cyl_raw, CYL_MIN, CYL_MAX, False, errors,
                        axis_raw=data.get("axis"))
    if cyl is None and _is_blank(cyl_raw):
        cyl = 0.0  # A2: blank CYL means 0.00
    # If CYL itself was invalid, skip axis rules that depend on it (avoid noisy double errors)
    cyl_invalid = any(e["field"] == "cyl" for e in errors)
    axis = None
    if not cyl_invalid:
        axis = _check_axis(eye, data.get("axis"), cyl, errors)

    normalized = {
        "sph": None if sph is None else f"{sph:+.2f}",
        "cyl": None if cyl is None else f"{cyl:+.2f}",
        "axis": axis,
    }
    return errors, normalized


def _warning(eye, field, code, message):
    return {"eye": eye, "field": field, "code": code, "message": message}


def _empty_summary():
    return {"se": None, "transposed": {"sph": None, "cyl": None, "axis": None}}


def _summarize_eye(norm):
    """Spherical equivalent + minus-cyl transposed form (2.5). Only called
    when this eye's normalized values have no errors."""
    sph = float(norm["sph"])
    cyl = float(norm["cyl"]) if norm["cyl"] is not None else 0.0
    axis = norm["axis"]
    se = sph + cyl / 2
    t_sph = sph + cyl
    t_cyl = -cyl if cyl else 0.0  # avoid "-0.00" when cyl is 0.0 (-0.0 negated stays -0.0)
    t_axis = None
    if axis is not None:
        flipped = axis + 90
        t_axis = flipped if flipped <= AXIS_MAX else axis - 90
    return {"se": f"{se:+.2f}",
            "transposed": {"sph": f"{t_sph:+.2f}", "cyl": f"{t_cyl:+.2f}", "axis": t_axis}}


def _eye_warnings(eye, norm):
    """HIGH_POWER and PLUS_CYL warnings for one eye (2.4). Only called when
    this eye's normalized values have no errors."""
    Eye = eye.capitalize()
    sph = float(norm["sph"])
    cyl = float(norm["cyl"]) if norm["cyl"] is not None else 0.0
    warnings = []
    breaches = []
    if abs(sph) >= HIGH_POWER_SPH:
        breaches.append(f"SPH {sph:+.2f} D")
    if abs(cyl) >= HIGH_POWER_CYL:
        breaches.append(f"CYL {cyl:+.2f} D")
    if breaches:
        field = "sph" if abs(sph) >= HIGH_POWER_SPH else "cyl"
        warnings.append(_warning(eye, field, "HIGH_POWER",
            f"{Eye} eye high power: {', '.join(breaches)} (threshold {HIGH_POWER_SPH:.2f} D SPH / "
            f"{HIGH_POWER_CYL:.2f} D CYL) -- unusually high, double-check."))
    if cyl > 0:
        warnings.append(_warning(eye, "cyl", "PLUS_CYL",
            f"{Eye} eye CYL is plus-cyl notation ({cyl:+.2f} D), accepted -- see summary for the "
            f"minus-cyl transposed form."))
    return warnings


def _cross_eye_warnings(right_summary, left_summary):
    """ANISOMETROPIA and ANTIMETROPIA warnings (2.4). Only called when both
    eyes have a computed spherical equivalent (no errors on either eye)."""
    se_r = float(right_summary["se"])
    se_l = float(left_summary["se"])
    warnings = []
    delta = abs(se_r - se_l)
    if delta >= ANISOMETROPIA_SE_DELTA:
        warnings.append(_warning(None, None, "ANISOMETROPIA",
            f"Spherical equivalents differ by {delta:.2f} D (threshold {ANISOMETROPIA_SE_DELTA:.2f} D): "
            f"Right SE {se_r:+.2f}, Left SE {se_l:+.2f}."))
    if (se_r <= -ANTIMETROPIA_SE and se_l >= ANTIMETROPIA_SE) or \
       (se_l <= -ANTIMETROPIA_SE and se_r >= ANTIMETROPIA_SE):
        warnings.append(_warning(None, None, "ANTIMETROPIA",
            f"One eye is myopic and the other hyperopic (threshold +/-{ANTIMETROPIA_SE:.2f} D SE): "
            f"Right SE {se_r:+.2f}, Left SE {se_l:+.2f}."))
    return warnings


def _plausibility(warnings):
    """Heuristic 0..100 score from fixed per-warning penalties (2.6). Not ML."""
    score = SCORE_START
    reasons = []
    for w in warnings:
        penalty = SCORE_PENALTY.get(w["code"])
        if penalty:
            score -= penalty
            reasons.append(f"{w['code']}: {w['message']} (-{penalty})")
    score = max(0, score)
    if score >= BAND_TYPICAL_MIN:
        band = "typical"
    elif score >= BAND_DOUBLE_CHECK_MIN:
        band = "double_check"
    else:
        band = "verify"
    return {"score": score, "band": band, "reasons": reasons}


def validate_prescription(payload):
    """Validate both eyes and build the full v2 response. Never raises."""
    default_plausibility = {"score": SCORE_START, "band": "typical", "reasons": []}

    if not isinstance(payload, dict):
        errors = []
        for eye in EYES:
            errors.append(_error(eye, "eye", "MISSING_EYE",
                f"{eye.capitalize()} eye data is missing, request must be an object with 'right' and 'left'."))
        return {"valid": False, "errors": errors, "warnings": [], "normalized": {},
                "summary": {}, "plausibility": default_plausibility}

    errors = []
    normalized = {}
    eye_ok = {}
    for eye in EYES:
        eye_errors, eye_norm = validate_eye(eye, payload.get(eye))
        errors.extend(eye_errors)
        normalized[eye] = eye_norm
        eye_ok[eye] = len(eye_errors) == 0

    summary = {}
    warnings = []
    for eye in EYES:
        if eye_ok[eye]:
            summary[eye] = _summarize_eye(normalized[eye])
            warnings.extend(_eye_warnings(eye, normalized[eye]))
        else:
            summary[eye] = _empty_summary()

    if eye_ok["right"] and eye_ok["left"]:
        warnings.extend(_cross_eye_warnings(summary["right"], summary["left"]))

    plausibility = _plausibility(warnings)
    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings,
            "normalized": normalized, "summary": summary, "plausibility": plausibility}


if __name__ == "__main__":
    import json
    samples = [
        {"right": {"sph": "-1.25", "cyl": "-0.50", "axis": "90"},
         "left": {"sph": "plano", "cyl": "", "axis": ""}},
        {"right": {"sph": "25", "cyl": "-1", "axis": ""},
         "left": {"sph": "abc", "cyl": "0", "axis": "200"}},
        None,
    ]
    for s in samples:
        print(json.dumps(validate_prescription(s), indent=2))
