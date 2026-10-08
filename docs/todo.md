# Todo checklist

## Phase status
- [x] Phase 0 audit done (docs/audit.md exists)
- [x] Phase 1 baseline green + committed
- [x] Phase 2 smart validation + committed
- [x] Phase 3 interactive UI + committed
- [ ] Phase 4 hardening + committed

## Functional checks (verify at localhost:8000)
- [ ] Valid sample -> green, normalized values shown
- [ ] Bad sample -> specific errors per field, fields highlighted
- [ ] All empty -> REQUIRED errors, no crash
- [ ] "abc" in Axis -> NOT_A_NUMBER
- [ ] "1.30" -> BAD_STEP with Apply fix to +1.25
- [ ] Axis 0 -> suggestion 180
- [ ] Not-JSON curl -> 400, never 500
- [ ] Anisometropia case (R -1.00, L -4.00) -> warning, still valid

## AI quality checks (is the agent doing its job?)
- [ ] Every change has a decisions.md entry with why + alternative rejected
- [ ] No existing test deleted or weakened (git diff tests/)
- [ ] No new dependency added (requirements.txt unchanged)
- [ ] contract.md updated BEFORE code when response shape changed
- [ ] validator.py has no FastAPI imports
- [ ] No magic numbers outside constants at top of validator.py
- [x] Error messages include eye, field, range, received value
- [ ] Agent ran tests and curl itself and pasted results, not just claimed success

## Cross-file requests
(agents append here)
