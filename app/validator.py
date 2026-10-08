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


def _check_power(eye, field, label, raw, lo, hi, required, errors):
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
                f"{Eye} eye {label} is required, got empty."))
        return None
    if not (lo <= value <= hi):
        errors.append(_error(eye, field, "OUT_OF_RANGE",
            f"{Eye} eye {label} must be between {lo:+.2f} and {hi:+.2f}, got {_show(raw)}."))
        return None
    if not is_quarter_step(value):
        errors.append(_error(eye, field, "BAD_STEP",
            f"{Eye} eye {label} must be in 0.25 steps (e.g. -1.25, -1.50), got {_show(raw)}."))
        return None
    return value


def _check_axis(eye, raw, cyl, errors):
    """Validate Axis using the already-parsed CYL value. Returns int or None."""
    Eye = eye.capitalize()
    cyl_is_zero = cyl is None or cyl == 0

    if _is_blank(raw):
        if not cyl_is_zero:
            errors.append(_error(eye, "axis", "AXIS_REQUIRED",
                f"{Eye} eye Axis is required when CYL is {cyl:+.2f}, got empty."))
        return None

    value, code = parse_power(raw)
    if code or (isinstance(raw, str) and raw.strip().lower() in PLANO_WORDS):
        errors.append(_error(eye, "axis", "NOT_A_NUMBER",
            f"{Eye} eye Axis must be a whole number from {AXIS_MIN} to {AXIS_MAX}, got {_show(raw)}."))
        return None
    if value != int(value):
        errors.append(_error(eye, "axis", "AXIS_NOT_INTEGER",
            f"{Eye} eye Axis must be a whole number (no decimals), got {_show(raw)}."))
        return None
    axis = int(value)
    if not (AXIS_MIN <= axis <= AXIS_MAX):
        errors.append(_error(eye, "axis", "OUT_OF_RANGE",
            f"{Eye} eye Axis must be a whole number from {AXIS_MIN} to {AXIS_MAX}, got {_show(raw)}."))
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
    cyl = _check_power(eye, "cyl", "CYL", cyl_raw, CYL_MIN, CYL_MAX, False, errors)
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


def validate_prescription(payload):
    """Validate both eyes. Never raises."""
    errors, normalized = [], {}
    if not isinstance(payload, dict):
        for eye in EYES:
            errors.append(_error(eye, "eye", "MISSING_EYE",
                f"{eye.capitalize()} eye data is missing, request must be an object with 'right' and 'left'."))
        return {"valid": False, "errors": errors, "normalized": {}}

    for eye in EYES:
        eye_errors, eye_norm = validate_eye(eye, payload.get(eye))
        errors.extend(eye_errors)
        normalized[eye] = eye_norm
    return {"valid": len(errors) == 0, "errors": errors, "normalized": normalized}


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
