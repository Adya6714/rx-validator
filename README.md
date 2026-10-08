# Rx Validator

A small FastAPI app that validates eyeglass prescription (SPH / CYL / Axis) values for both eyes. Enter values in the browser, or `POST /validate` with a JSON body; the API returns whether the Rx is valid plus normalized values and any field errors.

## Features

- **Validation**: SPH/CYL range + 0.25 D step checks, Axis 1-180 rules, every error collected at once (never fail-fast), never a 500 on bad input.
- **Did-you-mean suggestions**: nearest 0.25 step, Axis 0 → 180 (and 181-360 wrapped), missing-decimal-point detection, Axis-typed-into-CYL detection — each with a one-click "Apply fix" in the UI.
- **Clinical plausibility warnings** (heuristic, not ML): high power, anisometropia, antimetropia, plus-cyl, mixed-cyl-notation — informational only, never block a valid Rx.
- **Per-eye summary**: spherical equivalent and the minus-cyl transposed form.
- **Two independent "how unusual is this" scores**: a rule-based plausibility score (0-100, fixed penalties, fully explained) and a separate statistical anomaly model (median/MAD z-scores, chi-square typicality) that catches combinations no fixed rule covers — see `docs/demo_script.md` step 4 for why both exist.
- **Lenient real-world input**: comma decimals, "DS"/"D" suffixes, "piano" (typo of plano), "x90"/"90°" axis notation, Unicode minus sign.
- **More than one form**: `/rules` (server-sourced limits, no hardcoding in the client) and `/validate/batch` (up to 100 prescriptions in one call).
- **Hardened**: a 20-character input cap (`TOO_LONG`) and a 10 KB request body cap (`PAYLOAD_TOO_LARGE`) before anything reaches the parser; the validator contractually never raises.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Tests

```bash
python -m pytest -q
```

## Demo script

See [`docs/demo_script.md`](docs/demo_script.md) for the full walkthrough (what
was asked, what was built beyond it, the assumptions made, and the exact
inputs/outputs to show live). Quick version:

```bash
curl -s -X POST localhost:8000/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"-1.25","cyl":"-0.50","axis":"90"},"left":{"sph":"plano","cyl":"","axis":""}}'
```

## Docs

See [docs/](docs/) for the contract (v2: warnings, suggestions, summary, plausibility, anomaly), assumptions, the decision log, and `book.md` for the full project write-up.
