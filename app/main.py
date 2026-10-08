"""FastAPI app: serves the form and the /validate endpoint."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app.validator import validate_prescription

app = FastAPI(title="Rx Validator")
INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


def _fail(status, field, code, message):
    return JSONResponse(status_code=status, content={
        "valid": False,
        "errors": [{"eye": None, "field": field, "code": code, "message": message}],
    })


@app.get("/")
def index():
    return FileResponse(INDEX, media_type="text/html")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/validate")
async def validate(request: Request):
    # Plain Request (not a Pydantic model) so bad types reach our validator
    # and get clear messages instead of FastAPI's generic 422.
    try:
        body = await request.json()
    except Exception:
        return _fail(400, "body", "BAD_REQUEST", "Request body must be valid JSON.")
    if not isinstance(body, dict):
        return _fail(400, "body", "BAD_REQUEST",
                     "Request body must be a JSON object with 'right' and 'left'.")
    try:
        return validate_prescription(body)
    except Exception:
        return _fail(500, "server", "INTERNAL", "Unexpected error while validating. Please retry.")
