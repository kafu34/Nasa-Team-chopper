"""Contract 2.6.0: individual baselines and DET-1.0 detection (v3.1 §7 scenarios A, B and C)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso

API = "/api/v1"


def obs(client, value, minutes_ago, type_="heart_rate", unit="bpm", quality="good", source="SIMULATED_WEARABLE"):
    r = client.post(f"{API}/observations", json={"astronaut_id": "DEMO-001", "type": type_, "value": value,
                                                 "unit": unit, "source": source, "quality": quality,
                                                 "observed_at": now_iso(minutes_ago * 60)})
    assert r.status_code in (200, 201), r.text
    return r.json()


def open_concern(client, values=(84, 86, 88)):
    out = [obs(client, v, 30 - 10 * i) for i, v in enumerate(values)]
    assert out[-1]["detection"]["outcome"] == "concern_opened", out[-1]["detection"]
    return out


def cases_for(client):
    with client.app.state.session_factory() as db:
        return db.query(m.MedicalCase).filter(m.MedicalCase.astronaut_id == "DEMO-001").all()


# --------------------------------------------------------------------------- baselines (step 29)

def test_seeded_baselines_are_versioned_and_computed_from_valid_history(client):
    out = client.get(f"{API}/astronauts/DEMO-001/baselines").json()
    assert out["method_id"] == "BASELINE-1.0"
    by_type = {b["type"]: b for b in out["baselines"]}
    assert set(by_type) == {"heart_rate", "spo2", "body_temperature"}  # sleep and BP: too few readings
    hr = by_type["heart_rate"]
    assert hr["version"] == 1 and hr["status"] == "active" and hr["created_by"] == "baseline-engine"
    assert hr["centre"] == 66 and hr["spread"] == 2.0 and hr["sample_count"] == 9 and not hr["frozen"]
    assert by_type["spo2"]["centre"] == 98 and by_type["spo2"]["spread"] == 0.5
    assert by_type["body_temperature"]["centre"] == pytest.approx(36.7)
    assert all(b["data_category"] == "SIMULATED_ASTRONAUT" for b in out["baselines"])


def test_recompute_creates_a_new_version_and_keeps_the_old(client):
    r = client.post(f"{API}/astronauts/DEMO-001/baselines/heart_rate/recompute",
                    json={"actor_id": "DEMO-002", "reason": "Demonstration recompute"})
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["created_by"] == "DEMO-002"
    versions = client.get(f"{API}/astronauts/DEMO-001/baselines", params={"type": "heart_rate"}).json()["baselines"]
    assert [(b["version"], b["status"]) for b in versions] == [(1, "superseded"), (2, "active")]
    assert versions[0]["superseded_at"] is not None


def test_recompute_validation(client):
    base = f"{API}/astronauts/DEMO-001/baselines"
    body = {"actor_id": "DEMO-002", "reason": "test reason"}
    short = client.post(f"{base}/sleep_duration/recompute", json=body)
    assert short.status_code == 422 and short.json()["error"]["code"] == "INSUFFICIENT_BASELINE_DATA"
    assert client.post(f"{base}/mood/recompute", json=body).json()["error"]["code"] == "UNKNOWN_OBSERVATION_TYPE"
    assert client.post(f"{base}/heart_rate/recompute", json={**body, "actor_id": "NOBODY"}).status_code == 404
    assert client.post(f"{API}/astronauts/NOBODY/baselines/heart_rate/recompute", json=body).status_code == 404


def test_baseline_never_updates_automatically(client):
    for i in range(6):
        obs(client, 66 + i % 2, 50 - 5 * i)
    hr = [b for b in client.get(f"{API}/astronauts/DEMO-001/baselines").json()["baselines"]
          if b["type"] == "heart_rate"]
    assert len(hr) == 1 and hr[0]["version"] == 1


def test_baseline_is_frozen_while_a_concern_is_open(client):
    open_concern(client)
    hr = next(b for b in client.get(f"{API}/astronauts/DEMO-001/baselines").json()["baselines"]
              if b["type"] == "heart_rate")
    assert hr["frozen"] and hr["frozen_by_concern_id"].startswith("CON-")
    r = client.post(f"{API}/astronauts/DEMO-001/baselines/heart_rate/recompute",
                    json={"actor_id": "DEMO-002", "reason": "try to absorb the change"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "BASELINE_FROZEN"
    # other measurement types are not frozen
    assert client.post(f"{API}/astronauts/DEMO-001/baselines/spo2/recompute",
                       json={"actor_id": "DEMO-002", "reason": "unrelated type"}).status_code == 201


# --------------------------------------------------------------------------- Scenario A (step 30)

def test_scenario_a_sustained_change_opens_concern_and_investigation_without_symptom(client):
    assert cases_for(client) == []
    first, second, third = open_concern(client)
    assert first["detection"]["outcome"] == "deviation_not_sustained" and first["detection"]["deviating_count"] == 1
    assert second["detection"]["deviating_count"] == 2
    d = third["detection"]
    assert d["rule_id"] == "DET-HR-01" and d["ruleset_version"] == "DET-1.0" and d["alert_raised"]
    assert d["baseline_version"] == 1 and d["deviation_direction"] == "above" and d["threshold"] == 15
    assert "not a diagnosis" in d["disclaimer"]
    case = client.get(f"{API}/cases/{d['case_id']}").json()
    assert case["kind"] == "routine" and case["symptoms"] == [] and case["priority"] == "routine"
    assert case["state"] == "awaiting_assessment" and case["monitoring_concern_ids"] == [d["concern_id"]]
    assert case["requested_assessment"]["procedure_id"] == "PROC-BP-01"
    assert "not a clinical indication" in case["requested_assessment"]["configured_reason"]
    assert [e["type"] for e in case["evidence"]] == ["monitoring_concern"]
    assert "not a diagnosis" in case["evidence"][0]["summary"]
    assert [f["task_type"] for f in case["follow_ups"]] == ["monitoring_reassessment"]
    assert case["follow_ups"][0]["concern_id"] == d["concern_id"]
    actions = [a["action"] for a in case["audit"]]
    assert actions[:2] == ["case.created", "monitoring_concern.opened"]
    assert "case.state_changed" in actions
    concern = client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert concern["annotation_kind"] == "monitoring_concern" and concern["status"] == "open"
    assert concern["evidence_observation_ids"] == [first["observation_id"], second["observation_id"],
                                                   third["observation_id"]]
    assert concern["automatic_resolution"] is False and concern["reassessment"]["status"] == "scheduled"


def test_a_reading_back_in_range_breaks_the_run(client):
    obs(client, 84, 40)
    obs(client, 70, 30)
    obs(client, 86, 20)
    last = obs(client, 88, 10)["detection"]
    assert last["outcome"] == "deviation_not_sustained" and last["deviating_count"] == 2


def test_spo2_rule_is_one_directional(client):
    up = [obs(client, 100, 30 - 10 * i, "spo2", "%") for i in range(3)]  # +2: inside the 3-point minimum anyway
    assert {u["detection"]["outcome"] for u in up} == {"within_baseline"}
    down = [obs(client, 94, 9 - 2 * i, "spo2", "%") for i in range(3)]
    assert down[-1]["detection"]["outcome"] == "concern_opened"
    case = client.get(f"{API}/cases/{down[-1]['detection']['case_id']}").json()
    assert case["state"] == "monitoring" and case["requested_assessment"] is None  # no configured assessment


def test_concern_joins_an_existing_symptom_case(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    d = open_concern(client)[-1]["detection"]
    assert d["case_id"] == case_id and len(cases_for(client)) == 1
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["state"] == "awaiting_assessment" and len(case["symptoms"]) == 1
    assert case["requested_assessment"]["assessment_id"] is not None  # the symptom's request is kept


def test_batch_ingestion_processes_in_time_order(client):
    items = [{"astronaut_id": "DEMO-001", "type": "heart_rate", "value": v, "unit": "bpm",
              "source": "SIMULATED_WEARABLE", "observed_at": now_iso(m_ * 60)} for v, m_ in ((88, 10), (84, 30), (86, 20))]
    r = client.post(f"{API}/observations/batch", json={"observations": items})
    assert r.status_code == 200, r.text
    out = r.json()
    assert [x["value"] for x in out["results"]] == [84, 86, 88] and out["stored"] == 3
    assert len(out["concern_ids_opened"]) == 1
    again = client.post(f"{API}/observations/batch", json={"observations": items}).json()
    assert again["duplicates"] == 3 and again["concern_ids_opened"] == []


def test_batch_rejects_everything_when_one_item_is_invalid(client):
    good = {"astronaut_id": "DEMO-001", "type": "heart_rate", "value": 84, "unit": "bpm",
            "source": "SIMULATED_WEARABLE", "observed_at": now_iso(60)}
    r = client.post(f"{API}/observations/batch", json={"observations": [good, {**good, "unit": "Hz"}]})
    assert r.status_code == 422 and r.json()["error"]["details"]["index"] == 1
    with client.app.state.session_factory() as db:
        assert db.query(m.HealthObservation).filter(m.HealthObservation.value == 84).count() == 0


# --------------------------------------------------------------------------- Scenario B (data quality)

def test_scenario_b_poor_and_stale_readings_never_create_a_finding(client):
    poor = [obs(client, 130, 30 - 10 * i, quality="poor") for i in range(3)]
    stale = [obs(client, 130, 180 - 10 * i) for i in range(3)]  # older than the 60-minute limit on arrival
    assert {p["detection"]["outcome"] for p in poor} == {"excluded_poor_quality"}
    assert {s["detection"]["outcome"] for s in stale} == {"excluded_stale"}
    assert all(x["detection"]["gate"] != "passed" and x["detection"]["concern_id"] is None for x in poor + stale)
    assert cases_for(client) == []
    text = " ".join(x["detection"]["explanation"] for x in poor + stale).lower()
    assert "no health conclusion" in text and "tachycardia" not in text
    mon = client.get(f"{API}/astronauts/DEMO-001/monitoring").json()
    issues = {(q["type"], q["issue"]) for q in mon["data_quality"]}
    assert ("heart_rate", "recent_poor_quality") in issues
    assert ("blood_pressure_systolic", "missing") in issues and ("body_temperature", "stale") in issues
    assert mon["concerns"] == []


def test_excluded_readings_do_not_reset_a_sustained_change(client):
    obs(client, 84, 40)
    obs(client, 60, 35, quality="poor")
    obs(client, 86, 30)
    assert obs(client, 88, 20)["detection"]["outcome"] == "concern_opened"


def test_missing_baseline_gives_no_comparison(client):
    with client.app.state.session_factory() as db:
        db.query(m.HealthBaseline).filter(m.HealthBaseline.type == "spo2").delete()
        db.commit()
    d = obs(client, 80, 5, "spo2", "%")["detection"]
    assert d["outcome"] == "no_baseline" and d["concern_id"] is None
    mon = client.get(f"{API}/astronauts/DEMO-001/monitoring").json()
    assert ("spo2", "baseline_not_created") in {(q["type"], q["issue"]) for q in mon["data_quality"]}
    assert obs(client, 7.0, 5, "sleep_duration", "h")["detection"]["outcome"] == "not_monitored"


def test_monitoring_summary_shows_baseline_latest_and_trend(client):
    for i, v in enumerate((70, 74, 78)):
        obs(client, v, 4 - i)
    hr = next(t for t in client.get(f"{API}/astronauts/DEMO-001/monitoring").json()["types"]
              if t["type"] == "heart_rate")
    assert hr["baseline"]["version"] == 1 and hr["latest_value"] == 78 and hr["difference_from_baseline"] == 12
    assert hr["latest_detection"]["outcome"] == "within_baseline" and hr["freshness"] == "current"
    assert hr["trend"]["description"] == "rising" and hr["trend"]["slope_per_hour"] > 0
    assert "No rule acts" in hr["trend"]["note"]


# --------------------------------------------------------------------------- Scenario C (duplicates, step 31)

def test_scenario_c_repeated_triggers_update_one_concern_and_suppress_alerts(client):
    d = open_concern(client)[-1]["detection"]
    repeats = [obs(client, 87 + i, 8 - 2 * i)["detection"] for i in range(3)]
    assert {r["outcome"] for r in repeats} == {"concern_updated"}
    assert all(r["concern_id"] == d["concern_id"] and r["alert_suppressed"] and not r["alert_raised"]
               for r in repeats)
    assert len(cases_for(client)) == 1
    concern = client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert concern["trigger_count"] == 4 and concern["suppressed_count"] == 3
    case = client.get(f"{API}/cases/{d['case_id']}").json()
    assert [e["type"] for e in case["evidence"]].count("monitoring_concern") == 1
    assert [a["action"] for a in case["audit"]].count("monitoring_concern.alert_suppressed") == 3
    assert len(case["follow_ups"]) == 1  # no extra reassessment for equivalent triggers


def test_identical_resubmission_is_not_counted_again(client):
    *_, last = open_concern(client)
    r = client.post(f"{API}/observations", json={k: last[k] for k in ("astronaut_id", "type", "value", "unit",
                                                                        "source", "quality", "observed_at")})
    assert r.status_code == 200 and r.json()["duplicate"]
    assert r.json()["detection"]["outcome"] == "concern_opened"  # the stored result
    concern = client.get(f"{API}/monitoring-concerns/{last['detection']['concern_id']}").json()
    assert concern["trigger_count"] == 1


def test_update_after_the_suppression_window_raises_one_alert(client):
    d = open_concern(client)[-1]["detection"]
    with client.app.state.session_factory() as db:
        db.get(m.MonitoringConcern, d["concern_id"]).last_case_update_at = utcnow() - timedelta(minutes=31)
        db.commit()
    r = obs(client, 90, 2)["detection"]
    assert r["alert_raised"] and not r["alert_suppressed"]
    assert obs(client, 91, 1)["detection"]["alert_suppressed"]
    case = client.get(f"{API}/cases/{d['case_id']}").json()
    assert [e["type"] for e in case["evidence"]].count("monitoring_concern") == 2


def test_ruleset_is_published(client):
    rs = client.get(f"{API}/monitoring/ruleset").json()
    assert rs["ruleset_version"] == "DET-1.0" and {r["rule_id"] for r in rs["rules"]} == {
        "DET-HR-01", "DET-SPO2-01", "DET-TEMP-01"}
    boot = client.get(f"{API}/demo/bootstrap").json()
    assert boot["detection_ruleset"] == rs


def test_reset_restores_baselines_and_removes_concerns(client):
    open_concern(client)
    client.post(f"{API}/demo/reset")
    out = client.get(f"{API}/astronauts/DEMO-001/baselines").json()["baselines"]
    assert {(b["type"], b["version"]) for b in out} == {("heart_rate", 1), ("spo2", 1), ("body_temperature", 1)}
    assert client.get(f"{API}/astronauts/DEMO-001/monitoring").json()["concerns"] == []
