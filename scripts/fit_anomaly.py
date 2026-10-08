"""Fit the anomaly model on prescription history.

Usage:
  python scripts/fit_anomaly.py --csv rx_history.csv            # writes app/anomaly_params.json
  python scripts/fit_anomaly.py --synthetic 5000 --dry-run      # pipeline demo only, prints params

CSV columns: r_sph,r_cyl,r_axis,l_sph,l_cyl,l_axis
Every row is validated first; only valid prescriptions train the model (the
validator doubles as the data-cleaning gate).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import anomaly  # noqa: E402
from app.validator import _validate_eye_full  # noqa: E402


def load_csv(path):
    recs, skipped = [], 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            eyes = []
            for side, eye in (("r", "right"), ("l", "left")):
                errs, _, parsed = _validate_eye_full(eye, {
                    "sph": row.get(f"{side}_sph"), "cyl": row.get(f"{side}_cyl"), "axis": row.get(f"{side}_axis")})
                eyes.append(None if errs else parsed)
            if None in eyes:
                skipped += 1
            else:
                recs.append(tuple(eyes))
    return recs, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--synthetic", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.csv:
        recs, skipped = load_csv(a.csv)
        print(f"loaded {len(recs)} valid rows, skipped {skipped} invalid rows")
    elif a.synthetic:
        recs = anomaly.synthetic_records(a.synthetic)
        print(f"generated {len(recs)} SYNTHETIC rows (pipeline demo only)")
    else:
        ap.error("give --csv or --synthetic")
    params = anomaly.fit(recs)
    print(json.dumps(params, indent=2))
    if a.dry_run or a.synthetic:
        print("dry run: params not saved")
    else:
        anomaly.save(params)
        print(f"saved to {anomaly.PARAMS_PATH}")


if __name__ == "__main__":
    main()
