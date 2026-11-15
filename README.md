# SENTINEL AI — Onboard Medical Assistant for Deep-Space Crews

**NASA Space Apps Challenge 2026 project.** SENTINEL AI helps a crew look after its own health when Earth is minutes
away and no doctor may be aboard. It watches each crew member against their own baseline and guides
measurements step by step. It points the way to working equipment and keeps a medical record that survives restarts
and lost links.

> **Research demonstration, not a medical device.**
> - All astronaut, habitat and device data are fictional.
> - Detection rules are configured demonstrations, not clinical criteria, and never produce a diagnosis.
> - No hardware is connected, and nothing is clinically validated.
> - The software was built with AI assistance (see [AI use](#ai-use)).

---

## What it does

| Feature | What you can see |
|---|---|
| **Proactive health monitoring** | Readings are compared with each crew member's own versioned baseline. A sustained change opens a monitoring concern and an investigation, with no symptom report needed. Stale, missing or poor-quality data never creates a finding. |
| **Anatomical Twin** | Tap where it hurts on a 3D human model; the exact surface point is saved with the symptom. |
| **Procedure Coach** | Picture-by-picture and 3D guides for three measurements: blood pressure, pulse oximeter and forehead thermometer. The reading must come from the session's device and pass technical checks. |
| **Habitat map and equipment** | Floor plan, crew location by compartment (uncertainty shown honestly), and the nearest *ready* device with an accessible route. Closing a hatch or taking a device out of service invalidates the route. |
| **Follow-up and screening** | Reassessments, scheduled screenings with due and overdue states, durable reminders, and controlled case closure. Nothing closes automatically. |
| **Urgent-event protection** | An urgent event interrupts routine work, and its priority is never lowered automatically. |
| **Ground communications** | Medical messages to the flight surgeon over a simulated 5-minute delayed link, with loss of signal, urgent-first sending and receiver-only acknowledgement. |
| **Roles** | Crew member, crew medical officer, flight surgeon and ground support see and do different things. |
| **NASA research context** | Real NASA data (see [NASA data](#nasa-data)), clearly labelled and never mixed into a crew member's record. |
| **Offline and recovery** | Runs entirely on one machine with a local database. After a restart, `/system/recovery` lists what to restore. |

## Run it (about 5 minutes)

You need **Python 3.13** (tested) and **Node.js 20.19+ or 22.12+**. No internet connection is needed once the
packages are installed, and all NASA data files are already in this repository.

**1. Get the code**: `git clone https://github.com/kafu34/Nasa-Team-chopper.git`, or use **Code → Download ZIP**
(about 16 MB).

Run the commands from the folder that **contains** `Nasa-Team-chopper` (where you cloned or unzipped it).

**2. Start the backend** in one terminal window.

Windows (Command Prompt or PowerShell):

```bat
cd Nasa-Team-chopper\Backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

macOS / Linux:

```bash
cd Nasa-Team-chopper/Backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The first start creates the local database and imports the NASA files, which takes about 20 seconds. Wait for
`Application startup complete`; the API docs are then at http://127.0.0.1:8000/docs. Leave this window open.

**3. Start the frontend** in a second terminal window:

```bash
cd Nasa-Team-chopper/Frontend
npm install
npm run dev
```

On Windows, use `cd Nasa-Team-chopper\Frontend`. If PowerShell refuses to run `npm`, type `npm.cmd` instead.

**4. Open http://127.0.0.1:5173.** The frontend forwards `/api` to the backend on port 8000.

**Common problems**

- **"The system cannot find the path specified"**: you are in the wrong folder. `cd` into the folder that contains
  `Nasa-Team-chopper` first.
- **`'.venv' is not recognized`**: in Command Prompt, use backslashes (`.venv\Scripts\python`), not `/`.
- **`python` opens the Microsoft Store**: install Python 3.13 from python.org (tick "Add python.exe to PATH"), or
  use `py -3.13` instead of `python`.
- **"address already in use" on port 8000**: another copy of the backend is already running. Stop it, or skip step 2
  and use the running one.

**Back to a clean demo:** use **Case & Follow-Up → Reset demo scenario**, or `POST /api/v1/demo/reset`. This resets
the fictional data only; the NASA data is never touched.

## A 3-minute tour for judges

1. **Health Monitoring.** Click **Submit fictional wearable sync**. Three readings above the personal baseline open
   a monitoring concern and an investigation, with no symptom involved. The page explains the rule and says it is not
   a diagnosis. You can also load a live scenario under **Load a backend scenario**, for example
   *Urgent case during BP procedure*.
2. **Anatomical Twin.** Rotate the 3D body and tap where it hurts. The site, region and side are validated by the
   backend.
3. **Procedure Coach.** Step through the blood-pressure pictures, switch to **3D replay**, then choose the pulse
   oximeter or thermometer in the catalogue.
4. **Location & Equipment.** Pick **Crew Quarters**, confirm it, then **Request suitable device**. The route appears
   on the map. **Close H-CQ-EX** and the saved route is invalidated.
5. **Ground Messages.** Type a message and queue it. It is *in transit* for the simulated delay. Try **Simulate link
   outage**.
6. **Case & Follow-Up.** See due and overdue screenings, acknowledge a reminder, or start a screening without a
   symptom.
7. **Roles & Access.** Switch the identity in the header, for example to *ground support*, and watch the buttons
   change.
8. **Emergency assistance.** Activate it. The case is escalated at once and an urgent message to the flight surgeon
   is queued; onboard action never waits for Earth.
9. **NASA Research** and **Mission Environment.** Browse the imported NASA records and the ISS radiation context.

## NASA data

Imported **unchanged** from the NASA Open Science Data Repository (OSDR). Source files, SHA-256 checksums, units,
subject IDs and missing values are all kept. The data is shown as research context about what spaceflight does to
people and environments. It is **never** used as the fictional crew member's data and never used to diagnose.

| Dataset | What it is | Records | Source |
|---|---|---|---|
| OSD-575 | SpaceX Inspiration4 blood serum comprehensive metabolic panel (4 crew, before and after flight) | 531 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| OSD-656 | SpaceX Inspiration4 urine inflammation panel (203 protein targets) | 8,888 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-656 |
| OSD-546 | Human bone-marrow stem cells differentiating toward bone on the ISS vs. ground | 432,861 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-546 |
| OSD-817 | Ex vivo human optic-nerve model of spaceflight-associated neuro-ocular syndrome | 72 | https://osdr.nasa.gov/bio/repo/data/studies/OSD-817 |
| NASA RadLab | ISS Columbus module absorbed dose rate, 4 instruments, 2022-04-01 | 2,847 | https://visualization.osdr.nasa.gov/radlab/gui/overview/ |

The full provenance, transformations and limits are in [docs/NASA_DATASETS.md](docs/NASA_DATASETS.md). Two sources
are catalogued but **not** imported: OSD-195 (its processed files were not available) and NASA EDA (no source file).

## How it is built

| Part | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, SQLite. Everything runs locally. |
| Frontend | TypeScript, React 19, Three.js, Vite |
| Contract | One versioned OpenAPI file ([shared/openapi.yaml](shared/openapi.yaml), v2.11.1), generated from the backend; a test fails if it drifts |
| Tests | 360 backend tests and 50 frontend tests, plus 47 live HTTP checks. They cover the five required health scenarios, restarts, communication outages and concurrent requests. |

```
Backend/    FastAPI app, NASA importers, tests, build plan
Frontend/   React app, 3D anatomy model, procedure visuals, evidence screenshots
shared/     API contract, fictional demo fixture, anatomy manifests
data/       NASA source files (unchanged)
docs/       API, NASA datasets, test report, acceptance record, integration notes
```

More detail is in [docs/SUBMISSION.md](docs/SUBMISSION.md) (project write-up),
[docs/ACCEPTANCE_RECORD.md](docs/ACCEPTANCE_RECORD.md) (status of each part, honestly graded),
[docs/API.md](docs/API.md) and [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

## Honest limits

- **No authentication.** Identities are self-declared, so the roles demonstrate the rules but are not security.
- **Zone-level positioning only.** It cannot place a person inside a compartment that has no working anchor; this is
  reported as uncertainty.
- **Educational procedures.** The instructions are paraphrased from public consumer guidance and are not reviewed by
  a flight surgeon.
- **No hardware.** Sensors, positioning hardware and AR (Milestone 8) were not started.

## AI use

This project was built with AI assistance, as allowed by the Space Apps rules:

- **Claude (Anthropic)** designed, built and tested the backend, the NASA data importers and the API contract. It
  also wrote this README and the project write-up, and recorded demo video.
- **Codex (OpenAI)** built the frontend, including the code that draws the procedure illustrations.

The team wrote the specification, made the decisions and reviewed the work. The video carry a
visible watermark to show that it was recorded by an AI. Commits made with AI carry a `Co-Authored-By` line.

## Credits

- **3D human model:** based on BodyParts3D (© The Database Center for Life Science, CC BY 4.0), through the
  `open-anatomy-3d` package (https://github.com/MervinR07/open-anatomy-3d).
- **NASA data:** NASA Open Science Data Repository and RadLab, as listed above.
- **Open-source libraries:** FastAPI, SQLAlchemy, Pydantic, React, Three.js and Vite.
