# Phase 0 Audit

No code was changed to produce this document. Read: CLAUDE.md, docs/contract.md,
docs/assumptions.md, docs/implementation.md, docs/todo.md, docs/decisions.md,
docs/book.md, README.md, app/validator.py, app/main.py, static/index.html,
tests/test_validator.py, tests/test_api.py, pytest.ini, requirements.txt.

## 1. File inventory vs the contract

| File | Contract says | Found |
|---|---|---|
| `app/validator.py` | Pure, no FastAPI imports. Constants `SPH_MIN/MAX`, `CYL_MIN/MAX`, `STEP`, `AXIS_MIN/MAX`. Functions `parse_power`, `is_quarter_step`, `validate_eye`, `validate_prescription`. | Present, exact names/signatures match. Only import is `math`. Constants match contract values exactly (-20/+20, -6/+6, 0.25, 1/180). |
| `app/main.py` | `POST /validate`, 200/400 response shapes. | Present. Also serves `GET /` (index.html) and `GET /health` (not in contract, harmless liveness probe). Uses a plain `Request` (not a Pydantic model) deliberately, per `docs/decisions.md`, so malformed types reach the validator instead of FastAPI's generic 422. |
| `static/index.html` | One static file, vanilla JS, no CDN, no build step. | Present, single file. Already has some Phase 3 items early (Fill valid/bad/clear sample buttons, red-border error highlighting) — ahead of schedule, not a gap. |
| `tests/test_validator.py` | Unit coverage for the 8 contract error codes. | All 8 codes (`REQUIRED`, `NOT_A_NUMBER`, `OUT_OF_RANGE`, `BAD_STEP`, `AXIS_NOT_INTEGER`, `AXIS_REQUIRED`, `AXIS_WITHOUT_CYL`, `MISSING_EYE`) have at least one test. Also covers valid-prescription shapes and malformed payloads (`None`, `[]`, `{}`, `{"right":"x"}`). |
| `tests/test_api.py` | HTTP-level shapes. | Covers `GET /`, `GET /health`, valid/bad POST, raw non-JSON POST, list-body POST (400), empty-object POST (200 + `MISSING_EYE`). |
| `docs/*.md` | Source of truth. | Internally consistent with the running code (see gaps below for the few mismatches). |
| `requirements.txt` | fastapi, uvicorn, pytest, httpx only. | Matches exactly, nothing extra added. |
| `pytest.ini` | — | `pythonpath = .`, `testpaths = tests`, `norecursedirs = rx-validator .venv` — correctly keeps the old nested `rx-validator/` copy out of collection, per the "never read/edit/test it" rule. |
| `rx-validator/` | Old copy, ignore. | Present in the working tree (git status shows pending deletions there from an earlier `.gitignore` fix). Not touched, not in scope. |

## 2. `python -m pytest -q` output

```
................................................                         [100%]
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  /Users/adya/prescrip/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
48 passed, 1 warning in 0.27s
```

All 48 tests pass. The one warning is from FastAPI's own `TestClient` deprecating its `httpx` dependency path — not something in our code, and not worth adding `httpx2` as a new dependency for (stack rule: no new dependencies).

## 3. Live smoke test (uvicorn on port 8001, backgrounded, then stopped)

Server started with `uvicorn app.main:app --port 8001`, `GET /` confirmed `200` before running these:

**Valid:**
```
curl -s -X POST localhost:8001/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"-1.25","cyl":"-0.50","axis":"90"},"left":{"sph":"plano","cyl":"","axis":""}}'

{"valid":true,"errors":[],"normalized":{"right":{"sph":"-1.25","cyl":"-0.50","axis":90},"left":{"sph":"+0.00","cyl":"+0.00","axis":null}}}
HTTP 200
```

**Bad:**
```
curl -s -X POST localhost:8001/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"abc","cyl":"","axis":""},"left":{"sph":"25","cyl":"-7","axis":"0"}}'

{"valid":false,"errors":[
  {"eye":"right","field":"sph","code":"NOT_A_NUMBER","message":"Right eye SPH must be a number like -1.25 or +0.50, got \"abc\"."},
  {"eye":"left","field":"sph","code":"OUT_OF_RANGE","message":"Left eye SPH must be between -20.00 and +20.00, got \"25\"."},
  {"eye":"left","field":"cyl","code":"OUT_OF_RANGE","message":"Left eye CYL must be between -6.00 and +6.00, got \"-7\"."}
],"normalized":{"right":{"sph":null,"cyl":"+0.00","axis":null},"left":{"sph":null,"cyl":null,"axis":null}}}
HTTP 200
```
(Note: left Axis "0" produced no error here because left CYL was already invalid — the axis check is skipped once CYL fails, by design. See gap #3 below.)

**All empty:**
```
curl -s -X POST localhost:8001/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"","cyl":"","axis":""},"left":{"sph":"","cyl":"","axis":""}}'

{"valid":false,"errors":[
  {"eye":"right","field":"sph","code":"REQUIRED","message":"Right eye SPH is required, got empty."},
  {"eye":"left","field":"sph","code":"REQUIRED","message":"Left eye SPH is required, got empty."}
],"normalized":{"right":{"sph":null,"cyl":"+0.00","axis":null},"left":{"sph":null,"cyl":"+0.00","axis":null}}}
HTTP 200
```

**Not JSON:**
```
curl -s -X POST localhost:8001/validate -H "Content-Type: application/json" -d 'not json at all'

{"valid":false,"errors":[{"eye":null,"field":"body","code":"BAD_REQUEST","message":"Request body must be valid JSON."}]}
HTTP 400
```

Server was then stopped (`pkill`); confirmed down (connection refused on a follow-up `curl`). No 500s, no crashes, no hangs in any case.

## 4. Gaps vs contract.md and assumptions.md

**Must-fix**
- **M1 — Several error messages omit the "allowed range" that CLAUDE.md's hard rule requires** ("Error messages name the eye, field, allowed range, and received value" — also an explicit line item in `docs/todo.md`'s AI quality checks). Concretely:
  - `REQUIRED` (SPH): `"Right eye SPH is required, got empty."` — no range.
  - `AXIS_REQUIRED`: `"Right eye Axis is required when CYL is -1.00, got empty."` — states the triggering CYL value, not the Axis range.
  - `AXIS_NOT_INTEGER`: `"Right eye Axis must be a whole number (no decimals), got 90.5."` — no range.
  - By contrast, `OUT_OF_RANGE` and `NOT_A_NUMBER` (axis) already state the range correctly — this is inconsistency, not a wholesale miss.

**Should-fix**
- **S1 — `contract.md`'s enumerated "Error codes" list (lines 36–37) omits `BAD_REQUEST`**, even though the contract's own 400-response example on line 33 uses it, and the running code emits it. `INTERNAL` (the defensive 500 fallback in `main.py`) isn't documented anywhere in the contract either. Docs and code have drifted apart in the codes list; per CLAUDE.md, contract.md should be updated first.
- **S2 — Axis validation is silently skipped whenever CYL is invalid on the same eye** (`validator.py` lines 129–133, intentional per `decisions.md`'s "avoid noisy double errors" note). This means a single submission with both a bad CYL and a bad Axis only ever reports the CYL problem — correct per the current design note, but worth a deliberate decision either way before the demo since a live audience may type garbage into multiple fields at once.
- **S3 — `NOT_A_NUMBER` messages for SPH/CYL give an example format ("-1.25 or +0.50") rather than the literal numeric range** — acceptable (the problem is non-numeric input, not range), but slightly inconsistent with M1's fix if that's applied uniformly.

**Nice-to-have**
- **N1 — No 500 response is documented in contract.md** (only 200 and 400 exist on paper). `main.py`'s try/except around `validate_prescription` is a defensive-only safety net (since the validator contractually never raises) — should never trigger, but if it ever did, the shape would be undocumented.
- **N2 — `docs/todo.md`'s Phase 1 checkbox is unticked** even though `docs/decisions.md` shows Phase-1-equivalent manual work already done (venv recreated, `pytest.ini` added, tests green). Not a code gap — flagging only because the checklist state doesn't match reality. Not ticking it myself; this run only ticks Phase 0 as instructed.
- **N3 — Phase 4's input length cap isn't implemented yet** (expected — it's Phase 4 scope). Checked for crashes under pathological input (`"1"*400`, `"1e500"`, `"nan"`, `"inf"`) by code inspection: `parse_power` catches these via `math.isnan`/`math.isinf`/`ValueError` already, so no crash risk today — the cap is purely a UX/defense-in-depth nicety, not an urgent fix.

## 5. Demo risks

- **Confusing partial errors** (S2): typing bad values into both CYL and Axis on the same eye only surfaces the CYL error. If the interviewer does this live, Axis will look silently "fine" until CYL is fixed.
- **Messages missing range on a few codes** (M1): minor but visible under the "error messages must be specific" bar the interview is scored against.
- **No warnings/suggestions/summary UI yet** — expected, Phase 2/3 haven't run. Not a risk if the demo is scoped to "baseline validation," but would look incomplete if asked for "smart" behavior before Phase 2 lands.
- **Nothing crashes**: every case tried (valid, bad, all-empty, non-JSON, empty object, list body, malformed eye) returned clean JSON with the right status code. No unhandled exceptions observed.

## 6. Top 5 fixes ranked by demo impact

1. **M1** — add the allowed range to `REQUIRED`, `AXIS_REQUIRED`, and `AXIS_NOT_INTEGER` messages. Highest impact: it's an explicit graded checklist item and a one-line change per message.
2. **S2** — decide and fix: either run the Axis check even when CYL is invalid (report both), or explicitly document "CYL errors suppress Axis checks on that eye" in contract.md so it's not mistaken for a bug live.
3. **S1** — add `BAD_REQUEST` (and `INTERNAL`) to contract.md's Error codes list so docs and code agree.
4. **N1** — document the defensive 500 shape in contract.md (one line) so it's not a surprise if ever hit.
5. **N3** — add the Phase 4 input length cap when that phase starts; confirmed no current crash risk, so this is sequencing, not urgency.

Overall: the codebase is in much better shape than a typical "Phase 0" starting point — it reads as if baseline-green (Phase 1) work already happened. All 48 tests pass, the server never 500s on any input tried, and assumptions A1–A11 all check out against the code. The gaps found are message-wording and documentation-consistency issues, not functional breakage.
