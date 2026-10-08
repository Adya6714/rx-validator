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
