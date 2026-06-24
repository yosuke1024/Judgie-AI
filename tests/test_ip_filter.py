import ipaddress

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture
def client():
    # テスト毎に ALLOWED_IPS を退避してリストア
    original_allowed_ips = config.ALLOWED_IPS
    yield TestClient(app)
    config.ALLOWED_IPS = original_allowed_ips


def test_ip_filter_disabled_when_empty(client):
    # ALLOWED_IPS が空の場合は制限がかからない
    config.ALLOWED_IPS = []

    # 任意のIPでアクセス
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ip_filter_allows_matching_ip(client):
    # 個別IPを許可
    config.ALLOWED_IPS = [ipaddress.ip_network("192.168.1.1", strict=False)]

    # 許可されたIPからのリクエスト
    response = client.get("/api/health", headers={"x-forwarded-for": "192.168.1.1"})
    assert response.status_code == 200

    # 許可されていないIPからのリクエスト
    response = client.get("/api/health", headers={"x-forwarded-for": "192.168.1.2"})
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_ip_filter_allows_matching_cidr(client):
    # CIDRブロックを許可
    config.ALLOWED_IPS = [ipaddress.ip_network("10.0.0.0/24", strict=False)]

    # 範囲内のIPからのリクエスト
    response = client.get("/api/health", headers={"x-forwarded-for": "10.0.0.50"})
    assert response.status_code == 200

    # 範囲外のIPからのリクエスト
    response = client.get("/api/health", headers={"x-forwarded-for": "10.0.1.50"})
    assert response.status_code == 403


def test_ip_filter_parses_multiple_xff(client):
    # CIDRブロックと個別IPを許可
    config.ALLOWED_IPS = [
        ipaddress.ip_network("192.168.1.1", strict=False),
        ipaddress.ip_network("10.0.0.0/24", strict=False),
    ]

    # x-forwarded-forが複数IPを持つ場合、最左端のIPが評価される
    response = client.get("/api/health", headers={"x-forwarded-for": "192.168.1.1, 10.0.0.5"})
    assert response.status_code == 200

    response = client.get("/api/health", headers={"x-forwarded-for": "10.0.0.5, 192.168.1.1"})
    assert response.status_code == 200

    # 最左端が許可されていない場合、右端が許可されていても403になる
    response = client.get("/api/health", headers={"x-forwarded-for": "8.8.8.8, 192.168.1.1"})
    assert response.status_code == 403


def test_ip_filter_invalid_ip_format(client):
    config.ALLOWED_IPS = [ipaddress.ip_network("192.168.1.1", strict=False)]

    # 不適切なIP形式
    response = client.get("/api/health", headers={"x-forwarded-for": "invalid-ip-format"})
    assert response.status_code == 403
    assert "Invalid client IP address" in response.json()["detail"]


def test_ip_filter_fallback_to_client_host(client):
    # ALLOWED_IPS に testclient (TestClientのデフォルトホスト) はパースできないので、
    # x-forwarded-for が無い場合はパースエラーで 403 になる
    config.ALLOWED_IPS = [ipaddress.ip_network("192.168.1.1", strict=False)]

    response = client.get("/api/health")
    assert response.status_code == 403
    assert "Invalid client IP address" in response.json()["detail"]
