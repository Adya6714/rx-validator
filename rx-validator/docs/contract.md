# Contract (all agents code against this)

## Constants (app/validator.py)
SPH_MIN = -20.0, SPH_MAX = 20.0
CYL_MIN = -6.0,  CYL_MAX = 6.0
STEP = 0.25
AXIS_MIN = 1, AXIS_MAX = 180

## Functions (app/validator.py)
parse_power(raw) -> tuple[float | None, str | None]
  - None/"" -> (None, None)
  - trims, accepts "+1.25", "-0.50", "plano"/"pl" -> 0.0
  - non-numeric -> (None, "NOT_A_NUMBER")
is_quarter_step(v: float) -> bool
  - abs(v * 4 - round(v * 4)) < 1e-9   (NO modulo, float-safe)
validate_eye(eye: str, data: dict) -> tuple[list[dict], dict]
  - returns (errors, normalized {"sph","cyl","axis"})
validate_prescription(payload) -> dict
  - payload may be anything; if not a dict or missing eyes, return errors, never raise

## Request: POST /validate
{"right": {"sph": "-1.25", "cyl": "-0.50", "axis": "90"},
 "left":  {"sph": "plano", "cyl": "",     "axis": ""}}
All values: string, number, or null.

## Response 200
{"valid": false,
 "errors": [{"eye": "left", "field": "axis", "code": "OUT_OF_RANGE",
             "message": "Left eye Axis must be a whole number from 1 to 180, got 200."}],
 "normalized": {"right": {...}, "left": {...}}}

## Response 400 (body not JSON / not an object)
{"valid": false, "errors": [{"eye": null, "field": "body", "code": "BAD_REQUEST", "message": "..."}]}

## Error codes
REQUIRED, NOT_A_NUMBER, OUT_OF_RANGE, BAD_STEP,
AXIS_NOT_INTEGER, AXIS_REQUIRED, AXIS_WITHOUT_CYL, MISSING_EYE

## Message format
"<Right|Left> eye <SPH|CYL|Axis> <what is wrong>, got <value>."
