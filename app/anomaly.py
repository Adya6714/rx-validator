"""Statistical anomaly model for prescriptions (the ML component).

What it is
  An unsupervised, explainable anomaly detector: a robust diagonal-Gaussian
  (median / MAD) density model over six clinically meaningful features of a
  two-eye prescription. It answers: "how typical is this Rx compared with the
  population the model was fitted on?"

Why this design
  - Rules catch impossible values. This catches *unusual but possible* combinations
    (e.g. axes that break the usual left/right mirror symmetry), which rules miss.
  - Pure Python, no new dependencies, every score is explainable feature by feature.
  - It learns: fit(records) re-estimates every parameter from real data
    (scripts/fit_anomaly.py). Shipped defaults are illustrative priors, NOT
    clinical statistics; they must be replaced by fitting on real Rx history.

Score
  z_i per feature (two-sided for average SE, one-sided "only higher is unusual"
  for the rest), d2 = sum(z_i^2), typicality = P(chi2_6 >= d2) * 100.
"""

import json
import math
import random
from pathlib import Path

PARAMS_PATH = Path(__file__).resolve().parent / "anomaly_params.json"
MAD_TO_SIGMA = 1.4826
MIN_SCALE = 0.05

# name -> (two_sided, label)
FEATURES = {
    "se_mean":   (True,  "Average spherical equivalent (D)"),
    "se_diff":   (False, "Difference in spherical equivalent between eyes (D)"),
    "cyl_max":   (False, "Strongest cylinder (D)"),
    "cyl_diff":  (False, "Difference in cylinder between eyes (D)"),
    "obliquity": (False, "How far an axis is from 90/180 (degrees)"),
    "axis_asym": (False, "Break in left/right axis mirror symmetry (degrees)"),
}

# Illustrative priors (assumption A15). Replace by fitting on real data.
DEFAULT_PARAMS = {
    "source": "default illustrative priors (not fitted)",
    "n": 0,
    "features": {
        "se_mean":   {"median": -0.75, "scale": 2.50},
        "se_diff":   {"median": 0.25,  "scale": 0.50},
        "cyl_max":   {"median": 0.50,  "scale": 0.60},
        "cyl_diff":  {"median": 0.25,  "scale": 0.40},
        "obliquity": {"median": 8.0,   "scale": 12.0},
        "axis_asym": {"median": 8.0,   "scale": 20.0},
    },
}

TYPICAL_MIN, UNCOMMON_MIN = 30, 5


def _load():
    try:
        return json.loads(PARAMS_PATH.read_text())
    except Exception:
        return DEFAULT_PARAMS


PARAMS = _load()


# ---- Features ---------------------------------------------------------------
def _axis_dist_to_principal(axis):
    return min(abs(axis - 90), abs(axis - 180), axis)


def features(right, left):
    """right/left: dicts with float sph, cyl and int-or-None axis (already validated)."""
    se_r = right["sph"] + (right["cyl"] or 0) / 2
    se_l = left["sph"] + (left["cyl"] or 0) / 2
    cr, cl = abs(right["cyl"] or 0), abs(left["cyl"] or 0)
    obl = [_axis_dist_to_principal(e["axis"]) for e in (right, left)
           if e.get("axis") is not None and abs(e["cyl"] or 0) >= 0.25]
    asym = 0.0
    if cr >= 0.5 and cl >= 0.5 and right.get("axis") and left.get("axis"):
        mirror = 180 - left["axis"] or 180
        d = abs(right["axis"] - mirror) % 180
        asym = float(min(d, 180 - d))
    return {"se_mean": (se_r + se_l) / 2, "se_diff": abs(se_r - se_l), "cyl_max": max(cr, cl),
            "cyl_diff": abs(cr - cl), "obliquity": float(max(obl)) if obl else 0.0, "axis_asym": asym}


def _chi2_sf_6(d2):
    """Survival function of chi-square with 6 degrees of freedom (closed form, even dof)."""
    h = d2 / 2
    return math.exp(-h) * (1 + h + h * h / 2)


def score(right, left, params=None):
    p = (params or PARAMS)["features"]
    x = features(right, left)
    zs, factors = {}, []
    for name, (two_sided, label) in FEATURES.items():
        z = (x[name] - p[name]["median"]) / p[name]["scale"]
        if not two_sided:
            z = max(0.0, z)
        zs[name] = z
        if abs(z) >= 1.5:
            direction = "lower" if z < 0 else "higher"
            factors.append({"feature": name, "label": label, "value": round(x[name], 2),
                            "z": round(z, 2), "note": f"{direction} than typical (median {p[name]['median']})"})
    d2 = sum(z * z for z in zs.values())
    typicality = round(100 * _chi2_sf_6(d2))
    band = "typical" if typicality >= TYPICAL_MIN else "uncommon" if typicality >= UNCOMMON_MIN else "rare"
    factors.sort(key=lambda f: -abs(f["z"]))
    return {"typicality": typicality, "band": band, "distance": round(math.sqrt(d2), 2),
            "top_factors": factors[:3], "features": {k: round(v, 2) for k, v in x.items()},
            "model": (params or PARAMS)["source"]}


# ---- Learning ---------------------------------------------------------------
def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def fit(records):
    """Fit median/MAD per feature. records: list of (right, left) parsed-eye dict pairs."""
    rows = [features(r, l) for r, l in records]
    if len(rows) < 30:
        raise ValueError("need at least 30 valid prescriptions to fit")
    out = {}
    for name in FEATURES:
        xs = [row[name] for row in rows]
        med = _median(xs)
        mad = _median([abs(v - med) for v in xs]) * MAD_TO_SIGMA
        out[name] = {"median": round(med, 3), "scale": round(max(mad, MIN_SCALE), 3)}
    return {"source": f"fitted on {len(rows)} prescriptions", "n": len(rows), "features": out}


def save(params, path=PARAMS_PATH):
    Path(path).write_text(json.dumps(params, indent=2))


def model_info():
    return {"type": "robust diagonal-Gaussian anomaly model (median/MAD, chi-square typicality)",
            "source": PARAMS["source"], "n": PARAMS.get("n", 0), "features": list(FEATURES)}


def synthetic_records(n, seed=7):
    """Synthetic data ONLY to demo/test the fitting pipeline. Not a substitute for real data."""
    rng = random.Random(seed)
    q = lambda v: round(v * 4) / 4
    recs = []
    for _ in range(n):
        base = rng.gauss(-1.0, 2.0)
        c = -abs(q(rng.gauss(0, 0.6)))
        ax = rng.choice([rng.randint(170, 180), rng.randint(1, 10), rng.randint(80, 100)])
        lax = 180 - ax or 180
        r = {"sph": q(base), "cyl": c, "axis": ax if c else None}
        lc = -abs(q(abs(c) + rng.gauss(0, 0.2)))
        l = {"sph": q(base + rng.gauss(0, 0.3)), "cyl": lc,
             "axis": max(1, min(180, lax + rng.randint(-5, 5))) if lc else None}
        recs.append((r, l))
    return recs
