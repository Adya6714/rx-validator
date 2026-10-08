# Contract (all agents code against this)

Version 2. Backward compatible with v1: `valid`, `errors`, and `normalized` keep
their v1 shape and meaning. `warnings`, `summary`, and `suggestion` (on errors)
are new and additive — a v1 client that ignores unknown keys still works.

## Constants (app/validator.py)
SPH_MIN = -20.0, SPH_MAX = 20.0
CYL_MIN = -6.0,  CYL_MAX = 6.0
STEP = 0.25
AXIS_MIN = 1, AXIS_MAX = 180
HIGH_POWER_SPH = 10.0   (|SPH| >= this triggers HIGH_POWER)
HIGH_POWER_CYL = 4.0    (|CYL| >= this triggers HIGH_POWER)
ANISOMETROPIA_SE_DELTA = 2.00   (|SE right - SE left| >= this triggers ANISOMETROPIA)
ANTIMETROPIA_SE = 1.00   (one eye SE <= -1.00 and the other >= +1.00 triggers ANTIMETROPIA)
SCORE_START = 100
SCORE_PENALTY = {"HIGH_POWER": 15, "ANISOMETROPIA": 20, "ANTIMETROPIA": 15}
SCORE_BANDS: >=80 "typical", 50..79 "double_check", <50 "verify"
MAX_INPUT_LEN = 20   (docs/implementation.md 4.1 — raw string inputs longer than
                      this on sph/cyl/axis are rejected with TOO_LONG before any
                      parsing is attempted, so a pathological paste can't reach
                      float() or the suggestion/summary math at all)

## Functions (app/validator.py) — v1, unchanged
parse_power(raw) -> tuple[float | None, str | None]
  - None/"" -> (None, None)
  - trims, accepts "+1.25", "-0.50", "plano"/"pl" -> 0.0
  - non-numeric -> (None, "NOT_A_NUMBER")
is_quarter_step(v: float) -> bool
  - abs(v * 4 - round(v * 4)) < 1e-9   (NO modulo, float-safe)

## Functions (app/validator.py) — v1, extended return shape
validate_eye(eye: str, data: dict) -> tuple[list[dict], dict]
  - returns (errors, normalized {"sph","cyl","axis"}) — unchanged from v1.
  - errors may now carry an optional "suggestion" key (see below). Internal
    helper functions for suggestions/summary/score are implementation detail
    (not part of the contract) as long as validator.py stays pure (no FastAPI
    imports) and the response shape below is produced.
validate_prescription(payload) -> dict
  - payload may be anything; if not a dict or missing eyes, return errors, never raise.
  - now returns the full v2 shape: valid, errors, warnings, normalized, summary,
    plausibility (see Response 200 below). When payload is malformed (not a
    dict, or an eye is missing/not an object), warnings=[], summary={},
    plausibility={"score": 100, "band": "typical", "reasons": []} — plausibility
    is only meaningful once both eyes parse, so it reports the neutral default
    rather than guessing.

## Request: POST /validate
{"right": {"sph": "-1.25", "cyl": "-0.50", "axis": "90"},
 "left":  {"sph": "plano", "cyl": "",     "axis": ""}}
All values: string, number, or null. Unchanged from v1.

## Error object shape
{"eye": "left" | "right" | null, "field": "sph" | "cyl" | "axis" | "eye" | "body" | "server",
 "code": "<error code>", "message": "<eye, field, range, received value>",
 "suggestion": { ... } }   // "suggestion" key is OMITTED entirely when there is none
                           // (not present with a null value) — keeps v1 error
                           // objects byte-identical when no suggestion applies.

## Suggestion shape (attached to an error, see docs/implementation.md 2.3)
{"field": "sph" | "cyl" | "axis",   // which field to fill — MAY differ from the
                                      // error's own field (axis-typed-in-cyl case)
 "value": "<string or number, same format normalized uses for that field>",
 "reason": "<short human-readable why>"}

Suggestion triggers (first match wins per error, only ever one suggestion per error):
  - BAD_STEP (sph/cyl): suggestion.field = same field, value = nearest 0.25 step
    to the parsed value (e.g. raw "1.30" -> value parses 1.30 -> suggest "+1.25").
  - Axis OUT_OF_RANGE where the raw (parsed) value is exactly 0: suggestion.field
    = "axis", value = 180, reason explains 0 and 180 are the same orientation.
  - SPH/CYL OUT_OF_RANGE where raw/100 would be a valid, on-step value (missing
    decimal point, e.g. "125" or "-125"): suggestion.field = same field, value =
    raw/100 keeping the original sign (e.g. "125" -> "+1.25", "-125" -> "-1.25").
  - CYL OUT_OF_RANGE where |parsed value| > CYL_MAX, the value is a whole number
    in [AXIS_MIN, AXIS_MAX], and this eye's axis field is blank: suggestion.field
    = "axis", value = the whole number, reason explains it looks like an Axis
    value typed into CYL.

## Warning object shape
{"eye": "left" | "right" | null,    // null for cross-eye warnings (ANISOMETROPIA, ANTIMETROPIA)
 "field": "sph" | "cyl" | null,     // null for cross-eye warnings
 "code": "HIGH_POWER" | "ANISOMETROPIA" | "ANTIMETROPIA" | "PLUS_CYL",
 "message": "<human-readable, states the threshold and the received value(s)>"}

Warnings never block `valid` (see Severity below) and never carry a "suggestion".

## Severity (docs/implementation.md 2.2)
- `errors`: block validation. `valid == (len(errors) == 0)`.
- `warnings`: informational only, never affect `valid`.
- A prescription can be `"valid": true` with a non-empty `warnings` list.

## Summary object (per eye, docs/implementation.md 2.5)
{"se": "<+/-D.DD>",                  // spherical equivalent = sph + cyl/2, null if sph is null
 "transposed": {
    "sph": "<+/-D.DD>" | null,       // sph + cyl
    "cyl": "<+/-D.DD>" | null,       // -cyl
    "axis": <int 1..180> | null      // axis +/- 90, whichever lands in [1,180]; null if axis is null
 }}
Only computed when the eye's own sph/cyl/axis all parsed without error; otherwise
that eye's summary is `{"se": null, "transposed": {"sph": null, "cyl": null, "axis": null}}`.

## Plausibility object (docs/implementation.md 2.6)
{"score": <int 0..100>,
 "band": "typical" | "double_check" | "verify",
 "reasons": ["<one string per warning that reduced the score, naming the code and the points deducted>"]}
Heuristic only (fixed penalties per warning code, see Constants) — explicitly
NOT a machine-learning model. Starts at 100; reasons list is empty and score is
100/"typical" when there are no warnings.

## Response 200
{"valid": false,
 "errors": [{"eye": "left", "field": "axis", "code": "OUT_OF_RANGE",
             "message": "Left eye Axis must be a whole number from 1 to 180, got 200."}],
 "warnings": [],
 "normalized": {"right": {...}, "left": {...}},
 "summary": {"right": {...}, "left": {...}},
 "plausibility": {"score": 100, "band": "typical", "reasons": []}}

## Response 200 — full v2 example
Request:
```json
{"right": {"sph": "-1.00", "cyl": "-0.50", "axis": "90"},
 "left":  {"sph": "-10.00", "cyl": "0", "axis": ""}}
```
Response (valid, with warnings — this is the point of v2: a clean Rx can still
carry clinical flags):
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    {"eye": "left", "field": "sph", "code": "HIGH_POWER",
     "message": "Left eye SPH magnitude is 10.00 D (threshold 10.00 D) — unusually high, double-check."},
    {"eye": null, "field": null, "code": "ANISOMETROPIA",
     "message": "Spherical equivalents differ by 8.75 D (threshold 2.00 D): Right SE -1.25, Left SE -10.00."}
  ],
  "normalized": {
    "right": {"sph": "-1.00", "cyl": "-0.50", "axis": 90},
    "left":  {"sph": "-10.00", "cyl": "+0.00", "axis": null}
  },
  "summary": {
    "right": {"se": "-1.25", "transposed": {"sph": "-1.50", "cyl": "+0.50", "axis": 180}},
    "left":  {"se": "-10.00", "transposed": {"sph": "-10.00", "cyl": "+0.00", "axis": null}}
  },
  "plausibility": {
    "score": 65,
    "band": "double_check",
    "reasons": [
      "HIGH_POWER: left eye SPH 10.00 D >= 10.00 D threshold (-15)",
      "ANISOMETROPIA: SE difference 8.75 D >= 2.00 D threshold (-20)"
    ]
  }
}
```

## Response 400 (body not JSON / not an object)
{"valid": false, "errors": [{"eye": null, "field": "body", "code": "BAD_REQUEST", "message": "..."}]}
Unchanged from v1 — no warnings/summary/plausibility keys on the 400 shape.

## Response 500 (defensive only — should never happen)
{"valid": false, "errors": [{"eye": null, "field": "server", "code": "INTERNAL", "message": "..."}]}
Only reachable if validate_prescription raises despite its contract never to do
so. Documented so it isn't a surprise; not expected to ever fire.

## Error codes
REQUIRED, NOT_A_NUMBER, OUT_OF_RANGE, BAD_STEP, TOO_LONG,
AXIS_NOT_INTEGER, AXIS_REQUIRED, AXIS_WITHOUT_CYL, MISSING_EYE,
BAD_REQUEST (HTTP 400 transport-level only), INTERNAL (HTTP 500, defensive only)

TOO_LONG: raw string value for sph/cyl/axis exceeds MAX_INPUT_LEN (20) characters.
Checked before parsing, so it takes precedence over NOT_A_NUMBER/OUT_OF_RANGE/etc
for that field. Never carries a suggestion. Message states the field, the 20-char
limit, and the received length (not the raw value itself, to avoid echoing a
20+ character string back into an error message).

## Warning codes
HIGH_POWER, ANISOMETROPIA, ANTIMETROPIA, PLUS_CYL

## Message format
Errors: "<Right|Left> eye <SPH|CYL|Axis> <what is wrong>, got <value>."
Warnings: "<what is wrong>, states the threshold and the received value(s)." (no
strict eye-prefix requirement for cross-eye warnings since eye is null there)
