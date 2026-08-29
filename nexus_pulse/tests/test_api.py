import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_get_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_get_funnel():
    response = client.get("/api/v1/analytics/funnel")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        row = data[0]
        assert "page_view" in row
        assert "search" in row
        assert "add_to_cart" in row
        assert "checkout" in row

def test_post_evaluate_experiment():
    payload = {
        "experiment_id": "EXP_CHECKOUT_V2",
        "alpha": 0.05,
        "expected_control_ratio": 0.50,
        "cluster_col": "user_tier",
        "metric_col": "post_exp_spend",
        "covariate_col": "pre_exp_spend_14d"
    }
    response = client.post("/api/v1/experiment/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "business_decision" in data
    assert data["business_decision"] in ["ROLLOUT", "REJECT", "INVALID_SRM"]
