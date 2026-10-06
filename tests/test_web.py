import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from ebay_comps.web import app  # noqa: E402

from .conftest import GBC  # noqa: E402

client = TestClient(app)


def test_index_page():
    r = client.get("/")
    assert r.status_code == 200 and "eBay Comps Agent" in r.text


def test_api_comps_demo():
    r = client.get("/api/comps", params={"q": GBC, "source": "fixture", "llm": "mock"})
    assert r.status_code == 200
    body = r.json()
    assert body["sample_data"] is True and body["recommendation"]["recommended_price"] > 0


def test_api_comps_error():
    r = client.get("/api/comps", params={"q": "iphone", "source": "fixture", "llm": "mock"})
    assert r.status_code == 400 and "No sample fixture" in r.json()["detail"]
