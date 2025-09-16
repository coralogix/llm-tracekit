# from fastapi.testclient import TestClient
# from main import app

# client = TestClient(app)

# def test_health():
#     response = client.get("/health")
#     assert response.status_code == 200
#     assert response.json() == {"status": "ok"}

# def test_run():
#     response = client.post("/guardrails/run", json={"message": "Hello, world!", "guardrails_config": []})
#     assert response.status_code == 200
#     assert response.json() == {"results": [], "guardrails_config": []}




