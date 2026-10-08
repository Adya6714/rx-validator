"""FastAPI app: serves the form, the validation API, and the rules the UI reads."""

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app.validator import rules, validate_prescription

app = FastAPI(title="Rx Validator", version="2.0")
INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"
MAX_BODY_BYTES = 10_000          # one Rx is ~150 bytes; this blocks abuse without hurting real use
MAX_BATCH = 100


def _fail(status, field, code, message):
    return JSONResponse(status_code=status, content={
        "valid": False,
        "errors": [{"eye": None, "field": field, "code": code, "message": message}],
    })


async def _read_json(request: Request, limit: int):
    """Returns (body, error_response). Never raises."""
    raw = await request.body()
    if len(raw) > limit:
        return None, _fail(413, "body", "PAYLOAD_TOO_LARGE", f"Request body must be at most {limit} bytes, got {len(raw)}.")
    try:
        return json.loads(raw), None
    except Exception:
        return None, _fail(400, "body", "BAD_REQUEST", "Request body must be valid JSON.")


@app.get("/")
def index():
    return FileResponse(INDEX, media_type="text/html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/rules")
def get_rules():
    """Ranges, steps and thresholds, so the UI never hardcodes them."""
    return rules()


@app.post("/validate")
async def validate(request: Request):
    # Plain Request (not a Pydantic model) so bad types reach our validator
    # and get clear messages instead of FastAPI's generic 422.
    body, err = await _read_json(request, MAX_BODY_BYTES)
    if err:
        return err
    if not isinstance(body, dict):
        return _fail(400, "body", "BAD_REQUEST", "Request body must be a JSON object with 'right' and 'left'.")
    try:
        return validate_prescription(body)
    except Exception:
        return _fail(500, "server", "INTERNAL", "Unexpected error while validating. Please retry.")


@app.post("/validate/batch")
async def validate_batch(request: Request):
    """Validate up to 100 prescriptions at once (e.g. cleaning historical records)."""
    body, err = await _read_json(request, MAX_BODY_BYTES * MAX_BATCH)
    if err:
        return err
    if not isinstance(body, list) or not body:
        return _fail(400, "body", "BAD_REQUEST", "Request body must be a non-empty JSON array of prescriptions.")
    if len(body) > MAX_BATCH:
        return _fail(400, "body", "BAD_REQUEST", f"At most {MAX_BATCH} prescriptions per batch, got {len(body)}.")
    try:
        results = [validate_prescription(item) for item in body]
    except Exception:
        return _fail(500, "server", "INTERNAL", "Unexpected error while validating. Please retry.")
    return {"count": len(results), "valid_count": sum(r["valid"] for r in results), "results": results}
