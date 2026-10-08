# How prescription validation works

## SPH, CYL, and Axis

An eyeglass Rx describes how much lens power each eye needs.

- **SPH (sphere)** is the main power, in diopters (D). Negative values correct nearsightedness; positive values correct farsightedness. `plano` / `pl` means zero power.
- **CYL (cylinder)** is extra power for astigmatism. It may be blank or zero when there is none. Labs accept both minus and plus cylinder notation.
- **Axis** is the angle (in degrees) that orients the cylinder. It only matters when CYL is non-zero.

## Rules this app enforces

| Field | Rule |
|-------|------|
| SPH | Required. Range −20.00 to +20.00. Steps of 0.25 D. Leading `+` and `plano`/`pl` allowed. |
| CYL | Optional (blank → 0.00). Range −6.00 to +6.00. Steps of 0.25 D. |
| Axis | Integer from 1 to 180 (0 is invalid; use 180). Required when CYL ≠ 0. Error if Axis is given while CYL is 0/blank. |

Bad numbers become codes such as `NOT_A_NUMBER`, `OUT_OF_RANGE`, `BAD_STEP`, `AXIS_REQUIRED`, or `AXIS_WITHOUT_CYL`. Both eyes are checked together; every problem is returned at once.

## Request flow

1. The browser page (`/`) collects text inputs for right and left SPH/CYL/Axis and `POST`s JSON to `/validate`.
2. FastAPI accepts the body. If it is not JSON or not a JSON object, the API returns **HTTP 400** with `BAD_REQUEST`.
3. Otherwise the pure validator runs: parse powers, check ranges and quarter-diopter steps, enforce Axis rules, collect all errors.
4. The response is always **HTTP 200** for a well-formed object: `{ "valid": true|false, "errors": [...], "normalized": { "right": {...}, "left": {...} } }`.
5. `GET /health` is a simple liveness check.

No login, no database, no ADD/PD/prism — just SPH, CYL, and Axis for both eyes.
