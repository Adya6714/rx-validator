# Implementation plan

## Phase 0: Audit (no code changes)
0.1 Read CLAUDE.md, all docs/, app/, static/, tests/.
0.2 Run python -m pytest -q and a live curl smoke test (valid, bad, empty, not-json).
0.3 Compare code vs contract.md and assumptions.md. List every gap.
0.4 Write docs/audit.md: what works, gaps, risks, recommended fixes ranked by demo impact.

## Phase 1: Baseline green
1.1 Fix every gap from audit.md marked must-fix.
1.2 All tests pass; app serves / and /validate; empty input returns REQUIRED errors, no 500.
1.3 Commit: "phase 1: baseline green".

## Phase 2: Smart validation (backend, foolproofing)
2.1 Update contract.md to v2 response (warnings, suggestions, summary). Backward compatible:
    valid, errors, normalized keep their shape.
2.2 Severity split: errors block, warnings do not. valid = no errors.
2.3 "Did you mean" suggestions attached to errors:
    - BAD_STEP: nearest 0.25 value (1.30 -> +1.25)
    - Axis 0 -> 180
    - Missing decimal: SPH/CYL out of range but value/100 is valid and on step ("125" -> +1.25, "-125" -> -1.25, keep sign)
    - Axis typed in CYL: |CYL| > 6, whole number 1..180, axis blank -> suggest moving it to Axis
2.4 Clinical plausibility warnings (standard optometry checks):
    - HIGH_POWER: |SPH| >= 10 or |CYL| >= 4
    - ANISOMETROPIA: |SE right - SE left| >= 2.00 (SE = SPH + CYL/2)
    - ANTIMETROPIA: one eye SE <= -1.00 and the other >= +1.00
    - PLUS_CYL: CYL > 0 (accepted, info that it was transposed)
2.5 Summary per eye: spherical equivalent, minus-cyl transposed form
    (sph' = sph + cyl, cyl' = -cyl, axis' = axis +/- 90 kept in 1..180).
2.6 Plausibility score 0..100: start 100, subtract per warning (HIGH_POWER 15, ANISOMETROPIA 20,
    ANTIMETROPIA 15). Bands: >=80 typical, 50..79 double-check, <50 verify against original Rx.
    Return score + reasons. Documented as a heuristic, NOT ML.
2.7 Tests for every new code path. Commit: "phase 2: smart validation".

## Phase 3: Interactive UI (static/index.html only)
3.1 Live validation: debounce 300 ms, call /validate on input, show message under each field.
3.2 Per-field state: neutral / green check / red error / amber warning.
3.3 Stepper buttons and ArrowUp/ArrowDown: 0.25 for SPH/CYL, 1 for Axis.
3.4 "Apply fix" button on every suggestion; clicking fills the field and revalidates.
3.5 Paste box: parse common Rx notation like "-1.25 -0.50 x 90" or "-1.25/-0.50x90" into fields.
3.6 Axis dial: small SVG semicircle 0..180 showing the axis line per eye, updates live.
3.7 Summary card: SE per eye, transposed form, plausibility score bar with band colour and reasons.
3.8 "Copy Right to Left" button, Clear, Fill valid / Fill bad samples.
3.9 Accessibility: label for, aria-live on results, Enter submits, visible focus rings.
3.10 Commit: "phase 3: interactive ui".

## Phase 4: Hardening + demo readiness
4.1 Input length cap (20 chars) -> clear error, not a crash.
4.2 Run full checklist in todo.md, fix anything failing.
4.3 Update README (features, run, demo script) and docs/book.md.
4.4 Commit: "phase 4: demo ready".

## Future (documented, not built)
- ML plausibility model: anomaly detector (e.g. Isolation Forest) trained on historical Rx data
  to flag unusual combinations; current heuristic score is the stand-in until real data exists.
- OCR of Rx slip photos into fields, with this validator as the guardrail on OCR output.
- Cross-check with lens catalogue (power availability per lens type).
