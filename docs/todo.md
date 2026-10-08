# Todo checklist

## Phase status
- [x] Phase 0 audit done (docs/audit.md exists)
- [x] Phase 1 baseline green + committed
- [x] Phase 2 smart validation + committed
- [x] Phase 3 interactive UI + committed
- [ ] Phase 4 hardening + committed

## Functional checks (verify at localhost:8000)
- [x] Valid sample -> green, normalized values shown
- [x] Bad sample -> specific errors per field, fields highlighted
- [x] All empty -> REQUIRED errors, no crash
- [x] "abc" in Axis -> NOT_A_NUMBER
- [x] "1.30" -> BAD_STEP with Apply fix to +1.25
- [x] Axis 0 -> suggestion 180
- [x] Not-JSON curl -> 400, never 500
- [x] Anisometropia case (R -1.00, L -4.00) -> warning, still valid

## AI quality checks (is the agent doing its job?)
- [x] Every change has a decisions.md entry with why + alternative rejected
- [x] No existing test deleted or weakened (git diff tests/)
- [x] No new dependency added (requirements.txt unchanged)
- [x] contract.md updated BEFORE code when response shape changed
- [x] validator.py has no FastAPI imports
- [x] No magic numbers outside constants at top of validator.py
- [x] Error messages include eye, field, range, received value
- [x] Agent ran tests and curl itself and pasted results, not just claimed success

## Cross-file requests
(agents append here)
- [backend -> frontend] suggestion.value is a STRING ("+1.25") for sph/cyl suggestions but an INT (180, 90) for axis suggestions, per contract.md's Suggestion shape ("same format normalized uses for that field"). When wiring "Apply fix", coerce to String(value) before setting an input's .value.
- [backend -> frontend] A warning's "eye" and "field" are null for cross-eye codes (ANISOMETROPIA, ANTIMETROPIA) — don't assume you can always highlight a specific input for every warning; render those two under the summary card instead of next to a field.
