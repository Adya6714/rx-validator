"""Pure validation logic for eyeglass prescriptions (SPH, CYL, Axis).

No web framework code here. Every bad input becomes an error dict; nothing raises.

Pipeline per request:
  1. normalise payload keys (right/left, OD/OS aliases, case-insensitive fields)
  2. per-field parsing and checks (errors, each with an optional "did you mean" suggestion)
  3. per-eye cross-field checks (Axis vs CYL)
  4. cross-eye clinical checks (warnings, never block)
  5. summary (spherical equivalent, transposed form)
  6. scoring: rule-based plausibility + statistical anomaly model (app/anomaly.py)
"""

import re

from app import anomaly

# ---- Domain constants (docs/assumptions.md) --------------------------------
SPH_MIN, SPH_MAX = -20.0, 20.0
CYL_MIN, CYL_MAX = -6.0, 6.0
STEP = 0.25
AXIS_MIN, AXIS_MAX = 1, 180
MAX_INPUT_LEN = 20

# ---- Clinical warning thresholds --------------------------------------------
HIGH_POWER_SPH = 10.0
HIGH_POWER_CYL = 4.0
ANISOMETROPIA_SE_DELTA = 2.00
ANTIMETROPIA_SE = 1.00

# ---- Rule-based plausibility score ------------------------------------------
SCORE_START = 100
SCORE_PENALTY = {"HIGH_POWER": 15, "ANISOMETROPIA": 25, "ANTIMETROPIA": 15, "MIXED_CYL_NOTATION": 10}
BAND_TYPICAL, BAND_DOUBLE_CHECK = 80, 50

PLANO_WORDS = {"plano", "pl", "piano"}          # "piano" is a common OCR/autocorrect typo of plano
EYES = ("right", "left")
EYE_ALIASES = {"right": "right", "od": "right", "re": "right", "r": "right",
               "left": "left", "os": "left", "le": "left", "l": "left"}
FIELDS = ("sph", "cyl", "axis")
FIELD_ALIASES = {"sph": "sph", "sphere": "sph", "cyl": "cyl", "cylinder": "cyl", "axis": "axis", "ax": "axis"}

# Strict number format: optional sign, digits, optional decimals. Rejects "1e3", "nan", "inf", "--1".
NUMBER_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
POWER_SUFFIX_RE = re.compile(r"\s*(ds|dc|d)$", re.IGNORECASE)   # "-1.25 DS", "-0.50D"
AXIS_CLEAN_RE = re.compile(r"^\s*[x×*@]\s*|\s*(°|deg|degrees)\s*$", re.IGNORECASE)  # "x90", "90°"


# ---- Small helpers ----------------------------------------------------------
def _is_blank(raw):
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _show(raw):
    if _is_blank(raw):
        return "empty"
    if isinstance(raw, str) and len(raw) > MAX_INPUT_LEN:
        return f"{len(raw)} characters"
    return f'"{raw}"' if isinstance(raw, str) else str(raw)


def _fmt(v):
    """Rx-style signed 2-decimal format. Avoids '-0.00'."""
    return None if v is None else f"{v + 0.0:+.2f}"


def _error(eye, field, code, message, suggestion=None):
    err = {"eye": eye, "field": field, "code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    return err


def _warning(eye, field, code, message):
    return {"eye": eye, "field": field, "code": code, "message": message}


def _nearest_step(v):
    return round(v / STEP) * STEP


# ---- Parsing ----------------------------------------------------------------
def parse_power(raw):
    """Turn raw input into a float. Returns (value, error_code).

    Accepts: numbers, "+1.25", "-0.50", ".75", "plano"/"pl", "-1,25" (comma decimal),
    "-1.25 DS" / "-0.50D" (dioptre suffix). Rejects scientific notation, nan, inf.
    """
    if _is_blank(raw):
        return None, None
    if isinstance(raw, bool):
        return None, "NOT_A_NUMBER"
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value != value or value in (float("inf"), float("-inf")):
            return None, "NOT_A_NUMBER"
        return value, None
    if not isinstance(raw, str):
        return None, "NOT_A_NUMBER"
    if len(raw) > MAX_INPUT_LEN:
        return None, "TOO_LONG"
    text = raw.strip()
    if text.lower() in PLANO_WORDS:
        return 0.0, None
    text = POWER_SUFFIX_RE.sub("", text).replace(" ", "").replace(",", ".")
    if not NUMBER_RE.match(text):
        return None, "NOT_A_NUMBER"
    return float(text), None


def is_quarter_step(v):
    """True if v is a multiple of 0.25. No modulo: float modulo is unreliable."""
    return abs(v * 4 - round(v * 4)) < 1e-9


# ---- Field checks -----------------------------------------------------------
def _check_power(eye, field, label, raw, lo, hi, required, errors, axis_blank=False):
    """Validate SPH or CYL. Returns the parsed value (or None)."""
    Eye = eye.capitalize()
    rng = f"{lo:+.2f} to {hi:+.2f}"
    value, code = parse_power(raw)
    if code == "TOO_LONG":
        errors.append(_error(eye, field, code,
            f"{Eye} eye {label} input is too long (max {MAX_INPUT_LEN} characters, allowed {rng}), got {_show(raw)}."))
        return None
    if code:
        errors.append(_error(eye, field, code,
            f"{Eye} eye {label} must be a number from {rng} like -1.25 or +0.50, got {_show(raw)}."))
        return None
    if value is None:
        if required:
            errors.append(_error(eye, field, "REQUIRED",
                f"{Eye} eye {label} is required (allowed {rng}, use 0 or plano for no power), got empty."))
        return None
    if not (lo <= value <= hi):
        errors.append(_error(eye, field, "OUT_OF_RANGE",
            f"{Eye} eye {label} must be between {lo:+.2f} and {hi:+.2f}, got {_show(raw)}.",
            _range_suggestion(field, value, lo, hi, axis_blank)))
        return None
    if not is_quarter_step(value):
        snap = _nearest_step(value)
        errors.append(_error(eye, field, "BAD_STEP",
            f"{Eye} eye {label} must be in 0.25 steps (allowed {rng}), got {_show(raw)}.",
            {"field": field, "value": _fmt(snap), "reason": f"Nearest 0.25 step is {_fmt(snap)}."}))
        return None
    return value


def _range_suggestion(field, value, lo, hi, axis_blank):
    """'Did you mean' for out-of-range powers. First match wins."""
    guess = value / 100
    if lo <= guess <= hi and is_quarter_step(guess) and guess != 0:
        return {"field": field, "value": _fmt(guess),
                "reason": f"Looks like a missing decimal point: {_fmt(guess)}."}
    if field == "cyl" and axis_blank and value == int(value) and AXIS_MIN <= abs(value) <= AXIS_MAX:
        return {"field": "axis", "value": int(abs(value)),
                "reason": f"{int(abs(value))} looks like an Axis value typed into CYL."}
    return None


def _parse_axis(raw):
    """Returns (int_or_None, error_code, parsed_float)."""
    if isinstance(raw, str):
        if len(raw) > MAX_INPUT_LEN:
            return None, "TOO_LONG", None
        cleaned = AXIS_CLEAN_RE.sub("", raw).strip()
        if cleaned.lower() in PLANO_WORDS:
            return None, "NOT_A_NUMBER", None
        raw = cleaned
    value, code = parse_power(raw)
    if code:
        return None, code, None
    if value != int(value):
        return None, "AXIS_NOT_INTEGER", value
    axis = int(value)
    if not (AXIS_MIN <= axis <= AXIS_MAX):
        return None, "OUT_OF_RANGE", value
    return axis, None, value


def _check_axis(eye, raw, cyl, cyl_ok, errors):
    """Validate Axis. Format/range always checked; CYL-dependent rules only when CYL parsed."""
    Eye = eye.capitalize()
    rng = f"{AXIS_MIN} to {AXIS_MAX}"
    cyl_is_zero = cyl is None or cyl == 0

    if _is_blank(raw):
        if cyl_ok and not cyl_is_zero:
            errors.append(_error(eye, "axis", "AXIS_REQUIRED",
                f"{Eye} eye Axis is required (whole number {rng}) when CYL is {_fmt(cyl)}, got empty."))
        return None

    axis, code, value = _parse_axis(raw)
    if code == "TOO_LONG":
        errors.append(_error(eye, "axis", code,
            f"{Eye} eye Axis input is too long (max {MAX_INPUT_LEN} characters, allowed {rng}), got {_show(raw)}."))
        return None
    if code == "NOT_A_NUMBER":
        errors.append(_error(eye, "axis", code,
            f"{Eye} eye Axis must be a whole number from {rng}, got {_show(raw)}."))
        return None
    if code == "AXIS_NOT_INTEGER":
        snap = int(round(value))
        sug = None
        if AXIS_MIN <= snap <= AXIS_MAX:
            sug = {"field": "axis", "value": snap, "reason": f"Axis is written in whole degrees: {snap}."}
        errors.append(_error(eye, "axis", code,
            f"{Eye} eye Axis must be a whole number from {rng} (no decimals), got {_show(raw)}.", sug))
        return None
    if code == "OUT_OF_RANGE":
        sug = None
        if value == 0:
            sug = {"field": "axis", "value": 180, "reason": "0 and 180 are the same orientation; Rx convention writes 180."}
        elif AXIS_MAX < value <= 360:
            v = int(value) - 180
            sug = {"field": "axis", "value": v if v else 180,
                   "reason": f"Axis repeats every 180 degrees, so {int(value)} is the same as {v if v else 180}."}
        errors.append(_error(eye, "axis", code,
            f"{Eye} eye Axis must be a whole number from {rng}, got {_show(raw)}.", sug))
        return None
    if cyl_ok and cyl_is_zero:
        errors.append(_error(eye, "axis", "AXIS_WITHOUT_CYL",
            f"{Eye} eye Axis should be empty when CYL is 0 or blank (Axis {rng} only applies with CYL), got {_show(raw)}.",
            {"field": "axis", "value": "", "reason": "No cylinder means no axis. Clear it, or add the CYL value."}))
        return None
    return axis


# ---- Eye level --------------------------------------------------------------
def _normalise_eye_dict(data):
    out = {}
    for k, v in data.items():
        key = FIELD_ALIASES.get(str(k).strip().lower())
        if key and key not in out:
            out[key] = v
    return out


def _validate_eye_full(eye, data):
    """Returns (errors, normalized, parsed) where parsed holds floats for summary/scoring."""
    errors = []
    empty = {"sph": None, "cyl": None, "axis": None}
    if not isinstance(data, dict):
        errors.append(_error(eye, "eye", "MISSING_EYE",
            f"{eye.capitalize()} eye data is missing or not an object, got {_show(data) if not isinstance(data, (dict, list)) else type(data).__name__}."))
        return errors, dict(empty), {**empty, "ok": False}

    data = _normalise_eye_dict(data)
    axis_blank = _is_blank(data.get("axis"))
    sph = _check_power(eye, "sph", "SPH", data.get("sph"), SPH_MIN, SPH_MAX, True, errors)
    n_before = len(errors)
    cyl_raw = data.get("cyl")
    cyl = _check_power(eye, "cyl", "CYL", cyl_raw, CYL_MIN, CYL_MAX, False, errors, axis_blank=axis_blank)
    cyl_ok = len(errors) == n_before
    if cyl is None and cyl_ok:
        cyl = 0.0                       # A2: blank CYL means 0.00
    axis = _check_axis(eye, data.get("axis"), cyl, cyl_ok, errors)

    normalized = {"sph": _fmt(sph), "cyl": _fmt(cyl) if cyl_ok else None, "axis": axis}
    parsed = {"sph": sph, "cyl": cyl if cyl_ok else None, "axis": axis,
              "ok": not errors}
    return errors, normalized, parsed


def validate_eye(eye, data):
    """Validate one eye. Returns (errors, normalized). v1 contract signature."""
    errors, normalized, _ = _validate_eye_full(eye, data)
    return errors, normalized


# ---- Cross-eye: summary, warnings, scores -----------------------------------
def spherical_equivalent(sph, cyl):
    return sph + (cyl or 0.0) / 2


def transpose(sph, cyl, axis):
    """Switch between plus- and minus-cylinder notation (same optical lens)."""
    cyl = cyl or 0.0
    new_axis = None
    if axis is not None and cyl != 0:
        new_axis = axis + 90 if axis <= 90 else axis - 90
    return {"sph": _fmt(sph + cyl), "cyl": _fmt(-cyl), "axis": new_axis}


def _summary(p):
    if not p.get("ok") or p.get("sph") is None:
        return {"se": None, "transposed": {"sph": None, "cyl": None, "axis": None}}
    return {"se": _fmt(spherical_equivalent(p["sph"], p["cyl"])),
            "transposed": transpose(p["sph"], p["cyl"], p["axis"])}


def _warnings(parsed):
    w = []
    for eye in EYES:
        p = parsed[eye]
        if not p.get("ok"):
            continue
        Eye = eye.capitalize()
        if abs(p["sph"]) >= HIGH_POWER_SPH:
            w.append(_warning(eye, "sph", "HIGH_POWER",
                f"{Eye} eye SPH magnitude is {abs(p['sph']):.2f} D (threshold {HIGH_POWER_SPH:.2f} D): unusually high, double-check against the original Rx."))
        if abs(p["cyl"]) >= HIGH_POWER_CYL:
            w.append(_warning(eye, "cyl", "HIGH_POWER",
                f"{Eye} eye CYL magnitude is {abs(p['cyl']):.2f} D (threshold {HIGH_POWER_CYL:.2f} D): unusually high, double-check against the original Rx."))
        if p["cyl"] > 0:
            w.append(_warning(eye, "cyl", "PLUS_CYL",
                f"{Eye} eye uses plus-cylinder notation (CYL {_fmt(p['cyl'])}). Accepted; minus-cyl equivalent is shown in the summary."))

    r, l = parsed["right"], parsed["left"]
    if r.get("ok") and l.get("ok"):
        se_r, se_l = spherical_equivalent(r["sph"], r["cyl"]), spherical_equivalent(l["sph"], l["cyl"])
        diff = abs(se_r - se_l)
        if diff >= ANISOMETROPIA_SE_DELTA:
            w.append(_warning(None, None, "ANISOMETROPIA",
                f"Spherical equivalents differ by {diff:.2f} D (threshold {ANISOMETROPIA_SE_DELTA:.2f} D): Right SE {_fmt(se_r)}, Left SE {_fmt(se_l)}."))
        if (se_r <= -ANTIMETROPIA_SE and se_l >= ANTIMETROPIA_SE) or (se_l <= -ANTIMETROPIA_SE and se_r >= ANTIMETROPIA_SE):
            w.append(_warning(None, None, "ANTIMETROPIA",
                f"One eye is myopic and the other hyperopic (Right SE {_fmt(se_r)}, Left SE {_fmt(se_l)}, threshold +/-{ANTIMETROPIA_SE:.2f} D)."))
        if r["cyl"] * l["cyl"] < 0:
            w.append(_warning(None, None, "MIXED_CYL_NOTATION",
                f"Right CYL {_fmt(r['cyl'])} and Left CYL {_fmt(l['cyl'])} use different notations (one plus, one minus). Usually a transcription slip; check the original Rx."))
    return w


def _plausibility(warnings):
    score, reasons = SCORE_START, []
    for w in warnings:
        pts = SCORE_PENALTY.get(w["code"], 0)
        if pts:
            score -= pts
            where = f"{w['eye']} eye {w['field'].upper()}" if w["eye"] else "both eyes"
            reasons.append(f"{w['code']}: {where} (-{pts})")
    score = max(0, score)
    band = "typical" if score >= BAND_TYPICAL else "double_check" if score >= BAND_DOUBLE_CHECK else "verify"
    return {"score": score, "band": band, "reasons": reasons}


NEUTRAL_PLAUSIBILITY = {"score": 100, "band": "typical", "reasons": []}


def validate_prescription(payload):
    """Validate both eyes. Never raises. Returns the v2 response shape."""
    errors = []
    if not isinstance(payload, dict):
        for eye in EYES:
            errors.append(_error(eye, "eye", "MISSING_EYE",
                f"{eye.capitalize()} eye data is missing, request must be an object with 'right' and 'left'."))
        return {"valid": False, "errors": errors, "warnings": [], "normalized": {},
                "summary": {}, "plausibility": dict(NEUTRAL_PLAUSIBILITY), "anomaly": None}

    eyes_in = {}
    for k, v in payload.items():
        eye = EYE_ALIASES.get(str(k).strip().lower())
        if eye and eye not in eyes_in:
            eyes_in[eye] = v

    normalized, parsed = {}, {}
    for eye in EYES:
        e_err, e_norm, e_parsed = _validate_eye_full(eye, eyes_in.get(eye))
        errors.extend(e_err)
        normalized[eye], parsed[eye] = e_norm, e_parsed

    warnings = _warnings(parsed)
    both_ok = parsed["right"].get("ok") and parsed["left"].get("ok")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "normalized": normalized,
        "summary": {eye: _summary(parsed[eye]) for eye in EYES},
        "plausibility": _plausibility(warnings),
        "anomaly": anomaly.score(parsed["right"], parsed["left"]) if both_ok else None,
    }


def rules():
    """Public constants so the UI never hardcodes ranges (single source of truth)."""
    return {"sph": {"min": SPH_MIN, "max": SPH_MAX, "step": STEP},
            "cyl": {"min": CYL_MIN, "max": CYL_MAX, "step": STEP},
            "axis": {"min": AXIS_MIN, "max": AXIS_MAX, "step": 1},
            "max_input_len": MAX_INPUT_LEN,
            "warnings": {"high_power_sph": HIGH_POWER_SPH, "high_power_cyl": HIGH_POWER_CYL,
                         "anisometropia_se_delta": ANISOMETROPIA_SE_DELTA, "antimetropia_se": ANTIMETROPIA_SE},
            "anomaly_model": anomaly.model_info()}


if __name__ == "__main__":
    import json
    for s in [
        {"right": {"sph": "-1.25", "cyl": "-0.50", "axis": "180"}, "left": {"sph": "-1.00", "cyl": "-0.75", "axis": "5"}},
        {"OD": {"SPH": "125", "CYL": "90", "AXIS": ""}, "OS": {"sph": "1.30", "cyl": "-1", "axis": "0"}},
        None,
    ]:
        print(json.dumps(validate_prescription(s), indent=2))
