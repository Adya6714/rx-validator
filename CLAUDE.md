# Rx Validator: Claude Code context

## What this is
Live interview build (Lenskart AI skills round). A FastAPI service + web form that validates
eyeglass prescriptions (Right/Left SPH, CYL, Axis) and returns clear, specific errors.
Must run at http://localhost:8000, survive empty/bad input, and be demoable in a browser.

## Project layout (IMPORTANT)
- Project root is THIS folder (~/prescrip): app/, static/, tests/, docs/.
- The nested rx-validator/ folder is an OLD COPY. Never read, edit, or test it.
- Ignore .venv/.

## Stack (do not add dependencies)
Python 3.11, FastAPI, uvicorn, pytest, httpx. Frontend: one static/index.html, vanilla JS + CSS, no CDN, no build step.

## Source of truth (read before any change)
- docs/contract.md: function signatures, request/response shapes, error codes
- docs/assumptions.md: domain rules
- docs/implementation.md: phased plan. Work ONLY on the phase you are asked to do.
- docs/todo.md: checklist. Tick items as you finish them.

## Hard rules
- Never let an exception reach the user. Bad input becomes an error object.
- Error messages name the eye, field, allowed range, and received value.
- Collect all errors; do not fail fast.
- Float step checks: abs(v*4 - round(v*4)) < 1e-9. Never modulo.
- Keep app/validator.py pure (no FastAPI imports).
- Do not delete or weaken existing tests. Add new tests for new behaviour.
- After every phase: run tests, run a curl smoke test, then git commit.
- If the contract must change, update docs/contract.md FIRST, then code.
- Keep code readable for a beginner. No clever abstractions.

## Logging (mandatory)
Append every non-obvious choice to docs/decisions.md in this format:
- [Phase N][Claude] <decision> | why: <reason> | alternative rejected: <option>
Human edits use [Phase N][Adya, manual].

## Commands
- Tests: python -m pytest -q   (always this form, not bare pytest)
- Run: uvicorn app.main:app --reload --port 8000
- If port 8000 is busy (Adya runs the server in another tab), use --port 8001 for your own smoke tests.
- Smoke: curl -s -X POST localhost:8001/validate -H "Content-Type: application/json" -d '{"right":{"sph":"-1.25","cyl":"-0.50","axis":"90"},"left":{"sph":"plano","cyl":"","axis":""}}'
