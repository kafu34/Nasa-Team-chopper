# NASA Datasets Used by SENTINEL AI

SENTINEL AI keeps three strictly separated data categories:

| Category | Meaning |
|---|---|
| `NASA_RESEARCH` | Genuine NASA research data, imported unchanged with provenance. Never shown as live readings. |
| `SIMULATED_ASTRONAUT` | Fictional DEMO-001/DEMO-002 health data, symptoms, cases and measurements. |
| `SIMULATED_ENVIRONMENT_OR_DEVICE` | Fictional habitat HAB-01, wireless anchors, BLE signals and equipment. |

NASA measurements are stored in their own tables (`research_measurements`, `dataset_imports`) and are never
copied into astronaut records or used as personal medical thresholds.

## 1. OSD-575 (P0, imported)

| Field | Value |
|---|---|
| Application ID | `OSD-575` |
| Study | NASA OSDR OSD-575 — SpaceX Inspiration4 blood serum metabolic panel and immune/cardiac cytokine arrays (title as supplied by the project owner; confirm the exact wording on the study page before quoting) |
| Source URL | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| Repository | NASA Open Science Data Repository (OSDR) |
| File used | `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (confirmed in the OSDR file listing for OSD-575) |
| Local path | `data/nasa/raw/LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (byte-for-byte copy) |
| SHA-256 | `dab247eb794edab59aaaa683c85fd1f2dbf4ae3684872739338e10ead4192a0c` |
| Rows | 531 data rows, 9 columns |
| Columns | `ANALYTE, VALUE, RANGE_MIN, RANGE_MAX, UNITS, TEST_TYPE, SUBJECT_ID, SEX, timepoint` |
| Subjects | C001, C002, C003, C004 (anonymised as published; 2 M / 2 F per the SEX column) |
| Analytes | 19 comprehensive metabolic panel analytes (glucose, BUN, creatinine, eGFR ×2, BUN/creatinine ratio, sodium, potassium, chloride, CO2, calcium, total protein, albumin, globulin, A/G ratio, total bilirubin, alkaline phosphatase, AST, ALT) |
| Units | mg/dL, mmol/L, g/dL, U/L, mL/min/1.73m2, (calc) — kept verbatim |
| Timepoints | L-92, L-44, L-3 (days before launch) and R+1, R+45, R+82, R+194 (days after return) |

### Experimental context

Inspiration4 was a roughly three-day SpaceX orbital flight in September 2021 with four civilian crew members.
**All samples in this file were collected on the ground before launch or after return. None were collected
in flight**, and SENTINEL never labels them as in-flight.

### Transformation (what the importer does)

1. Validates that all nine required columns are present; otherwise the import fails (`IMPORT_FAILED`).
2. Copies each row one-to-one. Analyte names, units, subject IDs, sex and timepoint labels are kept verbatim.
3. Parses `VALUE`, `RANGE_MIN`, `RANGE_MAX` to numbers. The original text is kept in `value_raw`,
   `range_min_raw`, `range_max_raw`.
4. **Missing values stay missing**: `NA`, `N/A`, `NaN`, `NULL` and empty cells become `null`, never 0.
   In this file: 22 `VALUE` cells are `NA` (21 BUN/creatinine ratio, 1 total bilirubin) and 56 `RANGE_MAX`
   cells are `N/A` (both eGFR analytes, which have no upper reference bound in the file).
5. Parses the timepoint into `timepoint_phase` (`PREFLIGHT` for L-n, `POSTFLIGHT` for R+n),
   `timepoint_day_offset` (signed days) and `timepoint_order` (chronological sort key).
6. Records the import (`import_id`, SHA-256, row counts, missing-value counts) in `dataset_imports` and writes
   a JSON log to `Backend/var/import_logs/`.
7. Prevents duplicate ingestion: a file with an already-imported SHA-256 is skipped; a unique constraint on
   (dataset, file, row number) is a second guard. A changed file replaces the earlier rows atomically.
8. Any malformed row fails the whole import (no partial data).

### How to import

Automatic on server start. Manually: `cd Backend && .venv/Scripts/python scripts/import_nasa.py`
(re-running reports `skipped_duplicate`).

### How SENTINEL uses it

`GET /api/v1/research/osd-575` and `GET /api/v1/research/datasets/OSD-575/records` return the actual numerical
records with provenance (source URL, file, SHA-256, import ID, transformation text), filterable by subject,
analyte and timepoint. The frontend presents them as research context: how real crew blood chemistry values
look before and after a short spaceflight, with units and reference ranges as published.

### Limitations

- Four subjects; far too small for clinical conclusions. SENTINEL draws none.
- Reference ranges are the laboratory's general ranges, not personal astronaut thresholds.
- Ground laboratory assays. SENTINEL does not claim any onboard device can replicate them.
- The research data never drives the fictional DEMO-001 medical workflow.

## 2. Catalogue datasets (not imported)

These identifiers are in the shared registry (`GET /api/v1/research/datasets`) with honest status
`NOT_DOWNLOADED`. No importer exists yet; no values are shown. Fields marked unverified were not confirmed
verbatim from NASA pages during this build and must be checked before quoting.

| ID | Priority | What it contains (from the OSDR metadata API unless noted) | Title verified | Source URL |
|---|---|---|---|---|
| `OSD-656` | P1 | Inspiration4 crew urine, NULISA-seq 200-plex inflammation panel, pre/post flight | No | https://osdr.nasa.gov/bio/repo/data/studies/OSD-656 |
| `NASA-EDA` | P1 | Environmental Data App: ISS cabin/hardware telemetry (temperature, humidity, CO2) and radiation summaries | Yes ("Environmental Data App") | https://visualization.osdr.nasa.gov/eda/ |
| `NASA-RADLAB` | P1 | Space radiation dosimetry data — portal name and URL **not confirmed** | No | https://visualization.osdr.nasa.gov/radlab/ (unconfirmed lead) |
| `OSD-654` | P2 | Mouse tibia bone DXA and micro-CT, hindlimb-unloading ground analogue | No | https://osdr.nasa.gov/bio/repo/data/studies/OSD-654 |
| `OSD-684` | P2 | "Human skeletal muscle tissue chip autonomous payload reveals changes in fiber type and metabolic gene expression due to spaceflight" — bulk RNA-seq | Yes | https://osdr.nasa.gov/bio/repo/data/studies/OSD-684 |
| `OSD-573` | P2 | Inspiration4 Dragon capsule environmental shotgun metagenomics | No | https://osdr.nasa.gov/bio/repo/data/studies/OSD-573 |
| `OSD-817` | P2 | Human donor optic nerve tissue histology and immunostaining | No | https://osdr.nasa.gov/bio/repo/data/studies/OSD-817 |

To add one later: place files in `data/nasa/raw/<ID>/`, write an importer, and its status will move from
`NOT_DOWNLOADED` → `UNSUPPORTED_FORMAT` (files present, no importer) → `IMPORTED`.

## 3. Submission text (dataset section)

> SENTINEL AI integrates NASA OSDR study OSD-575 (SpaceX Inspiration4 blood serum metabolic panel,
> https://osdr.nasa.gov/bio/repo/data/studies/OSD-575). We import the published comprehensive metabolic panel
> file `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (531 measurements: 19 analytes, 4 crew
> members, 7 pre- and post-flight timepoints) without altering values, units, subject IDs or timepoints, keeping
> missing values as missing. The app shows these real measurements as research context beside its simulated
> astronaut workflow, clearly labelled, and never treats them as live or in-flight readings or as personal
> medical thresholds.
