"""Smoke test Fase 0 — tanpa butuh database/servis eksternal."""

from fastapi.testclient import TestClient

from api.main import app
from core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_has_core_routes() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/investigations" in paths


def test_password_roundtrip() -> None:
    hashed = hash_password("rahasia123")
    assert verify_password("rahasia123", hashed)
    assert not verify_password("salah", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token("user-123")
    assert decode_token(token, expected_type="access") == "user-123"
    assert decode_token(token, expected_type="refresh") is None


def test_protected_route_requires_token() -> None:
    resp = client.get("/api/v1/investigations")
    assert resp.status_code == 401
