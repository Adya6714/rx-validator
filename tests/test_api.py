"""API tests for FastAPI app — coded against docs/contract.md only."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_BODY = {
    "right": {"sph": "-1.25", "cyl": "-0.50", "axis": "90"},
    "left": {"sph": "plano", "cyl": "", "axis": ""},
}

BAD_BODY = {
    "right": {"sph": "abc", "cyl": "", "axis": ""},
    "left": {"sph": "25", "cyl": "-7", "axis": "0"},
}


def test_get_index_returns_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_get_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_post_validate_valid():
    r = client.post("/validate", json=VALID_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["errors"] == []


def test_post_validate_bad():
    r = client.post("/validate", json=BAD_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0


def test_post_raw_not_json():
    r = client.post(
        "/validate",
        content=b"not json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["valid"] is False
    assert any(e.get("code") == "BAD_REQUEST" for e in body["errors"])


def test_post_list_not_object():
    r = client.post("/validate", json=[])
    assert r.status_code == 400
    body = r.json()
    assert body["valid"] is False
    assert any(e.get("code") == "BAD_REQUEST" for e in body["errors"])


def test_post_empty_object_missing_eye():
    r = client.post("/validate", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert any(e.get("code") == "MISSING_EYE" for e in body["errors"])
