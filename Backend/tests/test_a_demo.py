"""Part A: health check, bootstrap, persistence, reset."""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["contract_version"] == "2.5.0"


def test_bootstrap_shared_identifiers(client):
    b = client.get("/api/v1/demo/bootstrap").json()
    assert b["astronaut"]["astronaut_id"] == "DEMO-001"
    assert b["responder"]["astronaut_id"] == "DEMO-002"
    assert b["habitat"]["habitat_id"] == "HAB-01"
    assert {z["zone_id"] for z in b["habitat"]["zones"]} == {"crew-quarters", "exercise", "medical", "laboratory"}
    assert any(p["procedure_id"] == "PROC-BP-01" for p in b["procedures"])
    assert len(b["equipment"]) + len(b["anchors"]) >= 6
    assert any(e["capability"] == "blood_pressure" and e["readiness"] == "verified_ready" for e in b["equipment"])
    assert {d["dataset_id"] for d in b["research_datasets"]} == {
        "OSD-575", "OSD-656", "NASA-EDA", "NASA-RADLAB", "OSD-654", "OSD-684", "OSD-573", "OSD-817",
        "OSD-195", "OSD-546"}


def test_bootstrap_scheduled_assessment_is_due(client):
    sa = client.get("/api/v1/demo/bootstrap").json()["scheduled_assessments"]
    assert sa[0]["assessment_id"] == "SA-BP-001"
    assert sa[0]["capability"] == "blood_pressure" and sa[0]["procedure_id"] == "PROC-BP-01"
    assert sa[0]["is_due"] is True


def test_bootstrap_observation_freshness(client):
    st = {s["type"]: s["status"] for s in client.get("/api/v1/demo/bootstrap").json()["observation_status"]}
    assert st["heart_rate"] == "current"
    assert st["body_temperature"] == "stale"
    assert st["blood_pressure_systolic"] == "missing"


def test_bootstrap_categories(client):
    b = client.get("/api/v1/demo/bootstrap").json()
    assert b["astronaut"]["data_category"] == "SIMULATED_ASTRONAUT"
    assert b["habitat"]["data_category"] == "SIMULATED_ENVIRONMENT_OR_DEVICE"
    assert all(o["data_category"] == "SIMULATED_ASTRONAUT" and o["simulated"] for o in b["observations"])
    assert all(d["data_category"] == "NASA_RESEARCH" for d in b["research_datasets"])


def test_persistence_across_restart(harness, symptom_payload):
    c = harness.start()
    case_id = c.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    c = harness.restart()
    r = c.get(f"/api/v1/cases/{case_id}")
    assert r.status_code == 200 and r.json()["case_id"] == case_id


def test_reset_restores_synthetic_state(client, symptom_payload):
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    r = client.post("/api/v1/demo/reset")
    assert r.status_code == 200 and r.json()["reset"] is True
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
    b = client.get("/api/v1/demo/bootstrap").json()
    assert b["open_cases"] == [] and b["scheduled_assessments"][0]["is_due"] is True


def test_unknown_route_uses_error_envelope(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
