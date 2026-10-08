# Assumptions

A1. SPH range: -20.00 to +20.00, required.
A2. CYL range: -6.00 to +6.00, optional (blank = 0.00). Both minus and plus cyl notation accepted.
A3. SPH and CYL must be in 0.25 D steps.
A4. Axis: integer 1 to 180 (0 is not valid; 180 is used instead).
A5. Axis is REQUIRED when CYL is non-zero.
A6. Axis given while CYL is 0 or blank = error AXIS_WITHOUT_CYL (easy to flip to a warning).
A7. "plano", "pl", "PL" accepted as SPH 0.00. Leading "+" accepted. Whitespace trimmed.
A8. All errors for both eyes returned at once, not fail-fast.
A9. Validation result is always HTTP 200 (valid true/false). Malformed request body is HTTP 400. Server never returns an unhandled 500.
A10. No auth, no persistence, no ADD/PD/prism fields (out of scope for 25 min).
A11. Ranges are generic optical-lab limits, not Lenskart-specific. Configurable as constants.
A12. Lenient input forms accepted: comma decimal ("-1,25"), dioptre suffix ("-1.25 DS", "-0.50D"), ".75", "piano" (typo of plano), spaces inside numbers.
A13. Axis notations accepted: "x90", "X 90", "90°", "090", "@90". Axis 0 and 181..360 are errors but get a one-click fix (180, axis-180).
A14. Inputs longer than 20 characters are rejected (TOO_LONG); request bodies over 10 KB get HTTP 413.
A15. Anomaly model ships with ILLUSTRATIVE priors, not clinical statistics. It must be re-fitted on real Rx history (scripts/fit_anomaly.py) before its numbers mean anything clinically.
A16. Clinical flags (high power, anisometropia >= 2 D SE, antimetropia, plus cyl, mixed notation) are warnings, never errors: an unusual Rx can still be correct.
A17. If CYL is invalid, Axis format/range is still checked, but CYL-dependent rules (required / without cyl) are skipped.
A18. Unicode minus (U+2212, from PDFs/WhatsApp) handling is added manually by Adya (see decisions.md).
