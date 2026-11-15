# SENTINEL AI — NASA Space Apps project page

Use this text on the project page. Every number is from the code and data in this repository (contract 2.11.0,
2026-11-15).

---

## 1. Project summary

**Problem.** On a long mission (for example a Mars transit) the crew cannot rely on Earth. Messages take minutes
each way, the link can drop, and there may be no doctor on board. Crew members must notice health changes
early, take the right measurement correctly, find working equipment, and keep a reliable record, often while
doing other work.

**Solution.** SENTINEL AI is an onboard medical-assistance prototype that works without a ground connection. It:
- watches each crew member's readings against their **own** baseline and opens an investigation when a
  sustained change appears, even when nobody reported a symptom;
- lets a crew member mark exactly where a symptom is on a **3D anatomical model**;
- guides a non-medical crew member **step by step, with pictures**, through three measurements (blood
  pressure, pulse oximeter, thermometer), and checks the reading came from the right device;
- shows the **habitat map**, the nearest working device and an accessible route, which changes when a hatch
  closes;
- keeps urgent events urgent, schedules follow-ups and routine checks, and queues messages to the flight
  surgeon over a simulated delayed link;
- shows **real NASA research data** (Inspiration4 crew biochemistry, ISS radiation, ISS cell studies) as
  clearly labelled research context.

**Potential impact.**
- Earlier detection of health changes on missions with no doctor and a delayed link.
- Fewer measurement errors by crew members who are not medical staff.
- Faster access to working equipment.
- A medical record that survives restarts and communication outages.

The same pattern fits remote stations on Earth, such as Antarctic bases and offshore platforms.

**Honest status.** SENTINEL AI is a research demonstration, **not a medical device**:
- all astronaut, habitat and device data are fictional and simulated;
- the detection rules are configured demonstration rules, not clinical criteria, and they never diagnose;
- no hardware is connected, and nothing has been clinically validated.

## 2. Project demo

A 7-slide presentation (published separately as a deck; see the link on the project page).

## 3. Final project link

https://github.com/kafu34/Nasa-Team-chopper (public). The integrated code is on the `main` branch.

## 4. Project details

**Approach.** The team set out a shared engineering specification first, with milestones: contracts, anatomy,
procedures, habitat, proactive health, expanded medical capability, operations. Two AI coding agents then
built it part by part:
- **Backend** (FastAPI and SQLite) by Claude;
- **Frontend** (React and Three.js) by Codex.

A single versioned API contract connects them (`shared/openapi.yaml`, now version 2.11.0). The contract is
generated from the backend code, and a test fails if it drifts. Every 10 build steps there was a written review
and reflection (`Backend/BUILD_PLAN_v3.1.md`).

**How the main parts work**

| Part | What it does |
|---|---|
| Personal baselines | Median and spread of each crew member's valid readings, versioned. Never updated automatically, and frozen while a concern is open, so a decline cannot become the "new normal". |
| Detection (DET-1.1) | A data-quality gate comes first: poor, stale and missing readings never create a finding. Then 3 consecutive readings outside the personal range open a monitoring concern and an investigation. Repeated alerts are suppressed. A concern closes only after a reassessment and a human review. |
| Anatomical Twin | A 3D human model (BodyParts3D-based, CC BY 4.0) with 35 surface sites. Tapped points are stored on the exact mesh triangle, and a point that falls outside its site is rejected. |
| Procedure Coach | Three educational procedures with picture-by-picture steps, each with its own visual action, camera view and warnings. The session records which device was used and checks that the reading's type and range fit that device. |
| Habitat Intelligence | A 4-compartment map in metres, with hatches, compartment-level positioning from simulated wireless anchors (uncertainty is reported honestly), and routes to the nearest ready device. A closed hatch or a device out of service invalidates the route. Includes a repeatable movement simulator. |
| Operations | Preventive screening with due and overdue states. Roles (crew, crew medical officer, flight surgeon, ground support). A delayed ground-message queue with loss-of-signal simulation. Controlled case closure. Recovery after a restart. |

**Tools and technologies**
- **Backend:** Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, SQLite, uvicorn, pytest.
- **Frontend:** TypeScript, React 19, Three.js, Vite, Vitest.
- **Shared:** an OpenAPI contract, a JSON demo fixture and 3D anatomy manifests in `shared/`.

**Testing.**
- 355 automated backend tests pass, with 0 failures.
- 47 of 47 real-HTTP smoke checks pass against a running server.
- The tests cover the five required health scenarios (sustained change, bad or missing data, duplicate
  triggers, an urgent event during a routine procedure, and follow-up without premature closure), plus
  restarts and communication outages.

**What is not finished.**
- Two NASA sources are blocked: OSD-195 (processed files were not available) and NASA-EDA (no source file).
- There is no user authentication.
- Real sensors, positioning hardware and AR are not started.

## 5. NASA data and references

**How NASA data supports the solution.** SENTINEL's fictional crew data shows *how* the system works. The real
NASA data grounds it in what spaceflight actually does to people and environments:
- **Real Inspiration4 crew blood and urine biomarkers** show which body systems change around a spaceflight, and
  why personal baselines and before/after comparison matter.
- **ISS stem-cell and optic-nerve studies** give research context for bone loss and spaceflight-associated
  neuro-ocular syndrome (SANS).
- **ISS radiation readings** show the environment crews live in.

How the data is handled:
- Every value is imported unchanged, with its source file, SHA-256, units and missing values kept as missing.
- It is shown as labelled research context.
- It is **never** mixed into a fictional crew member's record and never used to diagnose.

**NASA datasets used (imported as real numerical records)**

| Dataset | What it is | Records | Source |
|---|---|---|---|
| OSD-575 | SpaceX Inspiration4 blood serum comprehensive metabolic panel: 4 crew, 19 analytes, 7 pre- and post-flight timepoints | 531 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| OSD-656 | SpaceX Inspiration4 urine inflammation panel: 203 protein targets | 8,888 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-656 |
| OSD-546 | Human bone-marrow stem cells differentiating toward bone on the ISS versus ground (gene expression) | 432,861 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-546 |
| OSD-817 | Ex vivo human optic nerve model of SANS (cell counts) | 72 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-817 |
| NASA RadLab | ISS Columbus module absorbed dose rate, 4 instruments, 2022-04-01 (saved API snapshot) | 2,847 | https://visualization.osdr.nasa.gov/radlab/ |

All five come from the NASA Open Science Data Repository (OSDR) and its RadLab portal. Also catalogued but not
imported: OSD-195, OSD-654, OSD-684, OSD-573 and NASA EDA (https://visualization.osdr.nasa.gov/eda/). The full
provenance is in `docs/NASA_DATASETS.md`.

**AI tools**
- **Claude (Anthropic):** designed, built and tested the backend, the data importers and the API contract.
- **Codex (OpenAI):** built the frontend.

The team wrote the specification, made the decisions and approved every push.

**Other resources**
- **3D anatomy:** BodyParts3D-based human model (CC BY 4.0), via the `open-anatomy-3d` package.
- **Procedure text:** paraphrased from widely published general consumer guidance. That includes American
  Heart Association home blood-pressure guidance and U.S. FDA consumer information on pulse oximeters and
  non-contact infrared thermometers. None of it is reviewed by a flight surgeon, and all of it is marked
  educational.
- **Open-source libraries:** FastAPI, SQLAlchemy, Pydantic, React, Three.js, Vite.
