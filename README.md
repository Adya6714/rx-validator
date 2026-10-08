# Rx Validator

A small FastAPI app that validates eyeglass prescription (SPH / CYL / Axis) values for both eyes. Enter values in the browser, or `POST /validate` with a JSON body; the API returns whether the Rx is valid plus normalized values and any field errors.

## Features

- **Validation**: SPH/CYL range + 0.25 D step checks, Axis 1-180 rules, every error collected at once (never fail-fast), never a 500 on bad input.
- **Did-you-mean suggestions**: nearest 0.25 step, Axis 0 → 180, missing-decimal-point detection, Axis-typed-into-CYL detection — each with a one-click "Apply fix" in the UI.
- **Clinical plausibility warnings** (heuristic, not ML): high power, anisometropia, antimetropia, plus-cyl notation — informational only, never block a valid Rx.
- **Per-eye summary**: spherical equivalent and the minus-cyl transposed form, plus a 0-100 plausibility score with typical / double-check / verify bands.
- **Interactive UI**: live debounced validation, stepper + arrow-key input, a paste box for notation like `-1.25/-0.50x90`, an axis dial per eye, sample/clear/copy-right-to-left buttons, and accessible labels/focus states.
- **Hardened**: a 20-character input cap rejects pathological pastes with a clear `TOO_LONG` error instead of ever reaching the parser.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Tests

```bash
python -m pytest -q
```

## Demo script

1. Open `http://localhost:8000` and click **Fill valid sample** — both eyes turn green, normalized values and the summary card (SE, transposed form, plausibility score) appear.
2. Click **Fill bad sample** — right SPH ("abc") and left SPH/CYL are marked red with specific messages naming the eye, field, allowed range, and the value you typed.
3. Type `25` into Right SPH and tab out — it's flagged `OUT_OF_RANGE` with an **Apply fix** button suggesting `+0.25` (missing-decimal detection); click it to see the field go green.
4. Type `1.30` into Right SPH — `BAD_STEP` with an Apply fix to `+1.25`; type `0` into an Axis field — `OUT_OF_RANGE` with an Apply fix to `180`.
5. Set Right SPH `-1.00` / Left SPH `-4.00` (CYL/Axis blank) — the Rx is still valid (green), but the summary card shows an **ANISOMETROPIA** warning and the plausibility score drops out of the "typical" band.
6. Clear the form, submit empty (or run the curl smoke test below) — every field reports `REQUIRED` with its allowed range, and the app never crashes.

```bash
curl -s -X POST localhost:8000/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"-1.25","cyl":"-0.50","axis":"90"},"left":{"sph":"plano","cyl":"","axis":""}}'
```

## Docs

See [docs/](docs/) for the contract (v2: warnings, suggestions, summary, plausibility), assumptions, and a plain-language explainer of SPH/CYL/Axis.
