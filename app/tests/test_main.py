import pytest
from fastapi.testclient import TestClient

from app import main

API_KEY = "test-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("APP_SECRET_ID", raising=False)
    monkeypatch.setenv("APP_API_KEY", API_KEY)
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_items_reject_missing_or_wrong_key(client, headers):
    assert client.get("/api/v1/items", headers=headers).status_code == 401


def test_list_items(client):
    response = client.get("/api/v1/items", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [1, 2]


def test_get_item(client):
    response = client.get("/api/v1/items/2", headers={"X-API-Key": API_KEY})
    assert response.json() == {"id": 2, "name": "beta"}


def test_get_unknown_item(client):
    response = client.get("/api/v1/items/99", headers={"X-API-Key": API_KEY})
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/health", "/api/v1/items", "/does-not-exist"])
def test_security_headers_on_every_response(client, path):
    response = client.get(path)
    for header, value in main.SECURITY_HEADERS.items():
        assert response.headers[header] == value


def test_api_docs_disabled_by_default(client):
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_startup_fails_without_secret_config(monkeypatch):
    monkeypatch.delenv("APP_SECRET_ID", raising=False)
    monkeypatch.delenv("APP_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        main.load_api_key()


def test_api_key_loaded_from_secrets_manager(monkeypatch):
    class FakeSecretsManager:
        def get_secret_value(self, **kwargs):
            assert kwargs == {"SecretId": "backend-api-prod/app"}
            return {"SecretString": "from-secrets-manager"}

    monkeypatch.setenv("APP_SECRET_ID", "backend-api-prod/app")
    monkeypatch.setattr(main.boto3, "client", lambda service: FakeSecretsManager())
    assert main.load_api_key() == "from-secrets-manager"
