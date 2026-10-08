# Demo script — Rx Validator

A talking-point script for walking someone through the whole system live, in
about 8-10 minutes. Every input below was just run against the real server
and the outputs quoted are copy-pasted from that run — nothing here is
hypothetical.

## 0. Before you start

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`. (The public link —
https://adya6714.github.io/rx-validator/ — is the same UI shared via GitHub
Pages, but it's static hosting with no backend: say so up front if anyone
clicks "Validate" there, so it isn't mistaken for broken instead of expected.)

## 1. The brief (30 seconds)

"Validate a glasses prescription — Right/Left SPH, CYL, Axis — with clear,
specific errors. Must survive bad or empty input, run in a browser, and be
demoable in about 20-25 minutes."

## 2. What's built beyond the brief (60-90 seconds, say this before touching the keyboard)

- **Did-you-mean fixes, one click away**: missing decimal point, Axis 0 → 180,
  Axis typed into the CYL box by mistake, nearest 0.25 D step.
- **Errors vs. warnings**: impossible values block the Rx; clinically unusual
  but *possible* ones (anisometropia, high power, plus-cyl, mixed notation)
  surface as warnings and never block it.
- **Per-eye clinical summary**: spherical equivalent and the minus-cyl
  transposed form, for cross-checking against how a lab might re-key the Rx.
- **Two independent "is this weird" signals, not one**:
  1. a rule-based plausibility score (0-100, fixed penalties, fully explained
     — an explicit heuristic, not ML);
  2. a statistical anomaly model (median/MAD z-scores → chi-square
     typicality) that catches combinations that are each individually legal
     but jointly unusual — the "both eyes axis 45" example in step 4 below is
     the reason this exists.
- **API surface beyond the one form**: `/rules` so the UI (or any client)
  reads the limits from the server instead of hardcoding them, and
  `/validate/batch` for cleaning up to 100 historical records in one call.
- **Hardening**: a 20-character input cap, a 10 KB request body cap, and the
  validator is contractually never allowed to raise — bad input always comes
  back as a structured error, never a 500.
- **One manual change, by hand, not by the AI**: Unicode minus sign (U+2212,
  common in text copied from PDFs/WhatsApp) normalized before parsing — logged
  in `docs/decisions.md` as `[Adya, manual]`.

## 3. Assumptions made (60 seconds — point at `docs/assumptions.md`)

Call out a few, not all eighteen:

- **A1-A3**: SPH -20 to +20, CYL -6 to +6, both required to land on a 0.25 D
  step.
- **A9**: an invalid-but-well-formed Rx is still HTTP 200 (`valid: false`) —
  the request succeeded, the *answer* is "no". Only a broken request body is
  400/413. Never an unhandled 500.
- **A12-A13**: lenient real-world input — comma decimals, a trailing "DS"
  suffix, "piano" as a typo of "plano", Axis written as "x90" or "90°".
- **A16**: clinical flags are warnings, never errors — unusual doesn't mean
  wrong.
- **A17**: a judgment call, logged with its reasoning — if CYL is invalid,
  Axis format/range is still checked rather than suppressed, so a user who
  typed garbage into both fields sees both problems at once instead of one at
  a time.

## 4. Live walkthrough — exact inputs, exact results

### Step 1 — click **Fill valid sample**, then **Validate**

Right `-1.25 / -0.50 / 90`, Left `plano / — / —`.

> Prescription is valid. Right: SPH -1.25, CYL -0.50, Axis 90. Left: SPH
> +0.00, CYL +0.00, Axis –.

Point at the summary panel (SE + transposed form per eye) and the
plausibility bar (100/100, typical) and the anomaly panel (typicality, "no
unusual factors").

### Step 2 — click **Fill bad sample**, then **Validate**

Right `25 / -1.00 / (blank)`, Left `abc / 0 / 200`. Four problems, each
naming the eye, field, range, and value — two of them with a one-click fix:

- Right SPH: `OUT_OF_RANGE` — "must be between -20.00 and +20.00, got "25"."
  → **Apply fix: +0.25** ("looks like a missing decimal point").
- Right Axis: `AXIS_REQUIRED` — "required (whole number 1 to 180) when CYL is
  -1.00, got empty."
- Left SPH: `NOT_A_NUMBER` — "must be a number from -20.00 to +20.00 like
  -1.25 or +0.50, got "abc"."
- Left Axis: `OUT_OF_RANGE` — "must be a whole number from 1 to 180, got
  "200"." → **Apply fix: 20** ("Axis repeats every 180 degrees, so 200 is the
  same as 20").

Click one of the Apply fix buttons live — the field goes from red to fixed
and re-validates on its own.

### Step 3 — click **Fill typo sample**, then **Validate**

Right `125 / 90 / (blank)`, Left `1.30 / -1.00 / 0`. This one's for showing
off the suggestion variety:

- Right SPH `125` → `OUT_OF_RANGE`, fix **+1.25** (missing decimal, again).
- Right CYL `90` → `OUT_OF_RANGE`, fix **move 90 to Axis** ("90 looks like an
  Axis value typed into CYL").
- Left SPH `1.30` → `BAD_STEP`, fix **+1.25** (nearest 0.25 D step).
- Left Axis `0` → `OUT_OF_RANGE`, fix **180** ("0 and 180 are the same
  orientation").

### Step 4 — click **Fill unusual sample**, then **Validate** (the payoff moment)

Both eyes `-1.00 / -1.50 / 45`. This is **valid**, plausibility **100/typical**
— every rule-based check passes clean. But the anomaly panel disagrees:
**typicality 0, band "rare"**, top factor `axis_asym` — "break in left/right
axis mirror symmetry" — because a real two-eye Rx at the same cylinder power
almost always has mirrored axes (e.g. right 45° / left 135°), not identical
ones. This is the whole reason there are two scores instead of one: the rule
engine flags *known* clinical red lines, the statistical model catches
*combinations* no fixed rule was written for.

### Step 5 — type manually: Right `-1.00 / — / —`, Left `-4.00 / — / —`, **Validate**

Still **valid** — but the warnings panel shows `ANISOMETROPIA`: "Spherical
equivalents differ by 3.00 D (threshold 2.00 D)". Plausibility drops to
**75/double_check**. Point out: *valid and flagged are not opposites here* —
that's the errors-vs-warnings split from section 2.

### Step 6 — click **Clear**, then **Validate**

Both SPH fields: `REQUIRED (allowed -20.00 to +20.00...)`. No crash on empty
input — this was the original brief's hard requirement, now wrapped in
everything built on top of it.

### Step 7 (optional, "under the hood") — terminal, not the browser

```bash
curl -s -X POST localhost:8000/validate -H "Content-Type: application/json" -d 'not json at all'
# -> HTTP 400, BAD_REQUEST

curl -s -X POST localhost:8000/validate -H "Content-Type: application/json" \
  -d '{"right":{"sph":"111111111111111111111111","cyl":"","axis":""},"left":{"sph":"plano","cyl":"","axis":""}}'
# -> TOO_LONG, named eye/field, before the value is ever parsed

curl -s localhost:8000/rules
# -> the exact ranges/steps/thresholds above, served as data, not hardcoded in the UI
```

## 5. Closing line

"Everything above is backed by 95 passing tests and a decision log
(`docs/decisions.md`) explaining every non-obvious call and what was rejected
instead — including the one line I changed by hand."
