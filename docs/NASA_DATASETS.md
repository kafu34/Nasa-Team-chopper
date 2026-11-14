# NASA Datasets Used by SENTINEL AI

SENTINEL AI keeps three strictly separated data categories:

| Category | Meaning |
|---|---|
| `NASA_RESEARCH` | Genuine NASA research data, imported unchanged with provenance. Never shown as live readings. |
| `SIMULATED_ASTRONAUT` | Fictional DEMO-001/DEMO-002 health data, symptoms, cases and measurements. |
| `SIMULATED_ENVIRONMENT_OR_DEVICE` | Fictional habitat HAB-01, wireless anchors, BLE signals and equipment. |

NASA measurements are stored in their own tables (`research_measurements`, `gene_expression_values`,
`dataset_imports`) and are never copied into astronaut records or used as personal medical thresholds.

### Scientific classification (v2.2)

Every dataset carries a `study_type`, `organism`, `human_health_analysis`, `body_systems`, `measured` and
`not_a_measurement_of`. `astronaut_specific_findings_allowed` is always `false`.

| `study_type` | Meaning | Datasets |
|---|---|---|
| `HUMAN_SPACEFLIGHT` | People who flew (samples may be taken before launch / after return) | OSD-575, OSD-656 |
| `HUMAN_GROUND_ANALOGUE` | Human volunteers in an Earth analogue (bed rest); nobody flew | OSD-195 |
| `HUMAN_DERIVED_CELLS` | Human cells or tissue in culture, not a person | OSD-546, OSD-684, OSD-817 |
| `ANIMAL_RESEARCH` | Non-human organisms; kept separate (`SEPARATE_ANIMAL_RESEARCH`) | OSD-654 (mouse) |
| `SPACEFLIGHT_ENVIRONMENT` | Cabin telemetry, radiation, spacecraft microbiology (`ENVIRONMENT_CONTEXT`) | NASA-EDA, NASA-RADLAB, OSD-573 |
| `FICTIONAL_DEMONSTRATION` | SENTINEL's fictional astronauts, habitat and devices | demo data (`SIMULATED_*` categories) |

Only `PRIMARY_HUMAN_RESEARCH` datasets belong in the human-health research panels. OSD-654 stays listed as
animal research and never produces astronaut-specific findings.

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
`NOT_DOWNLOADED`. No importer exists yet, so no values are shown.

### Verified titles (2026-11-14)

Every title in the registry is now `title_verified: true`.
- **OSD studies:** read verbatim from the study `title` field of the NASA OSDR metadata API,
  `https://osdr.nasa.gov/osdr/data/osd/meta/<n>`. Project type and mission come from the same record.
- **NASA-EDA and NASA-RADLAB:** read from the OSDR visualization home page and the portal pages.

| ID | Exact title | Project type / mission (OSDR) | Organism |
|---|---|---|---|
| `OSD-575` | SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays (Comprehensive Metabolic Panel and Multiplex) | Spaceflight Study, SpaceX Inspiration4 (09/16–09/18/2021) | Homo sapiens |
| `OSD-656` | SpaceX Inspiration4 Urine Inflammation Panel (Multiplex, NULISAseq) | Spaceflight Study, SpaceX Inspiration4 (09/16–09/18/2021) | Homo sapiens |
| `OSD-195` | Effects of 21 days of bedrest on human skeletal muscle gene expression | Ground Study | Homo sapiens |
| `OSD-546` | SCD – Stem Cell Differentiation Toward Osteoblast Onboard the International Space Station | Spaceflight Study, Soyuz TMA-15M / TMA-16M (Italian Space Agency) | Homo sapiens (cells) |
| `OSD-654` | Toward countering muscle and bone loss with spaceflight: GSK3 as a potential target (Tibia, RR9 and HLU, MicroCT and DXA Scanning) | Spaceflight Study, SpaceX-12 / Rodent Research-9 on the ISS (08/14–09/17/2017), plus hindlimb unloading on the ground | Mus musculus |
| `OSD-684` | Human skeletal muscle tissue chip autonomous payload reveals changes in fiber type and metabolic gene expression due to spaceflight | listed as "Ground Study" in OSDR although the payload flew on SpaceX-21 (12/2020–01/2021) | Homo sapiens (tissue chips) |
| `OSD-573` | SpaceX Inspiration4 Dragon Capsule Metagenomic and Metatranscriptomic Microbial Swabs | Spaceflight Study, SpaceX Inspiration4 | microbial communities |
| `OSD-817` | The ex vivo human translaminar autonomous system to study spaceflight associated neuro-ocular syndrome pathogenesis (Optic Nerve, Histology and Microscopy) | Ground Study (donor tissue) | Homo sapiens |
| `NASA-EDA` | Environmental Data App (EDA) | portal, https://visualization.osdr.nasa.gov/eda/ | — |
| `NASA-RADLAB` | RadLab | portal, https://visualization.osdr.nasa.gov/radlab/ ("a single point of access to radiation telemetry data from multiple databases maintained by multiple space agencies") | — |

**Correction:** OSD-654 was earlier described as a ground-analogue study only. Its NASA record shows that it
includes **mice flown on the ISS** (Rodent Research-9) as well as hindlimb-unloaded mice. It remains
`ANIMAL_RESEARCH` and is still excluded from the human-health analysis.

To add one later: place files in `data/nasa/raw/<ID>/`, write an importer, and its status will move from
`NOT_DOWNLOADED` → `UNSUPPORTED_FORMAT` (files present, no importer) → `IMPORTED`.

## 2b. Human bone and muscle research (P1, v2.2): OSD-195 and OSD-546

Importer: `Backend/app/importers/expression.py` (record schema `GENE_EXPRESSION_V1`). Sample metadata:
`Backend/app/importers/expression_metadata.py`, read from the NASA OSDR metadata API
(`https://osdr.nasa.gov/osdr/data/osd/meta/195`, `.../files/195`, `.../meta/546`, `.../files/546`) on 2026-11-14.

**Current import status (2026-11-14):**

| Dataset | Status | Records | Source file in repo |
|---|---|---|---|
| OSD-546 | `IMPORTED` | 432,861 values (33,297 probesets × 13 samples, 0 missing) | `data/nasa/raw/OSD-546/GLDS-546_array_normalized_expression_probeset.csv` (SHA-256 `e211cce1ed17eefb434eb56b6c15389cb41357b558b946fa2ded399caa8c19e6`) + `GLDS-546_array_SampleTable.csv` (SHA-256 `21d90843856899cbb3223858382010c0248691d96d73a0dc8537780472adc6e3`) |
| OSD-195 | `NOT_DOWNLOADED` | 0 | none: only raw `.CEL.gz` files were supplied |

The owner supplied the files in `Backend/Nasa Data/` (1.3 GB, git-ignored). The two OSD-546 files the importer
needs were copied byte-for-byte into `data/nasa/raw/OSD-546/`. Checked against the source: TSPAN6
(probeset 8173941), GSM2696758 = `9.35429261997248` in both. 11,985 probesets have `SYMBOL = NA` in the NASA file
(for example, probesets that map to several Ensembl genes); their `gene_symbol` is `null`.

For OSD-195, the folder holds 23 of the 24 raw CEL files (GSM2813727 missing; GSM2813728 and GSM2813750 also
have duplicate "(1)" copies) and **no `*_processed.txt` files**. Raw Affymetrix data is deliberately not processed
(P2), so OSD-195 shows no values.

Supplied but not yet imported: `GLDS-546_array_differential_expression.csv` (NASA's limma results),
`GLDS-546_array_contrasts.csv`, the probe-level intensity tables, the runsheet, and the OSD-656
`_SUBMITTED (1).xlsx`. The OSD-656 TRANSFORMED CSV and target information file are imported (§2c).
`LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv` is an alternative OSD-575 table; SENTINEL keeps
the SUBMITTED CSV already imported.

### OSD-195 — human skeletal muscle, bed rest (`HUMAN_GROUND_ANALOGUE`)

- Homo sapiens, 12 healthy men, vastus lateralis biopsies, before and after 21 days of bed rest (PlanHab).
  Affymetrix microarray. 24 samples GSM2813727–GSM2813750; factor `Bed Rest` = `Before Bed Rest` /
  `After Bed Rest` (verified per sample). Subject numbers 1–14 with gaps.
- GSM2813749 (subject 14, Before Bed Rest) and GSM2813750 (subject 14, After Bed Rest) are a matched pair.
- The title "Effects of 21 days of bedrest on human skeletal muscle gene expression" is verified verbatim
  (OSDR Project Type "Ground Study").
- The RMA normalisation (Affymetrix Expression Console 1.4.1) comes only from a summary of the OSDR page and
  is **not verified verbatim**. So `normalization_verified=false` and `comparison_readiness.ready=false`.
- Files the importer needs (place in `data/nasa/raw/OSD-195/`):
  `GLDS-195_microarray_GSM2813749_processed.txt` (1,173,625 bytes per OSDR) and
  `GLDS-195_microarray_GSM2813750_processed.txt` (1,173,747 bytes). Any other
  `GLDS-195_microarray_GSM<id>_processed.txt` from the study is accepted. Note: OSDR lists GSM2813732
  (994,010 bytes) and GSM2813734 (677,399 bytes) as much smaller than the others; check them before use.
- The exact column layout of these processed files was not visible from the metadata. The importer accepts a
  probe-ID column plus exactly one value column (`VALUE` preferred), tab- or comma-separated, and rejects
  anything ambiguous with `IMPORT_FAILED` instead of guessing.
- Not a measurement of astronaut muscle mass, strength or deterioration. One sample, or one pair, does not
  show a general effect of bed rest.

### OSD-546 — human bone-marrow stem cells on the ISS (`HUMAN_DERIVED_CELLS`)

- Title (verified): "SCD – Stem Cell Differentiation Toward Osteoblast Onboard the International Space
  Station". Human bone-marrow mesenchymal stem cells, about 2 weeks on the ISS (Soyuz TMA-15M/TMA-16M), in
  osteogenic or standard medium, versus ground controls. Affymetrix Human Gene 1.0 ST.
- Processing (verified): GeneLab NF_MAAffymetrix v1.0.0, R 4.1.3, oligo 1.58.0, background correction, quantile
  normalisation, RMA summarisation. `normalization_verified=true`.
- 13 samples GSM2696758–GSM2696770 in four groups:

  | Spaceflight | Treatment | Samples |
  |---|---|---|
  | Space Flight | osteogenic | 3 |
  | Space Flight | standard | 4 |
  | Ground Control | osteogenic | 3 |
  | Ground Control | standard | 3 |

  Both factors are verified from NASA GeneLab's `GLDS-546_array_SampleTable.csv` (for example
  `(Space Flight & osteogenic)`) and the runsheet column `Factor Value[Treatment]`. The importer re-checks every
  sample against the SampleTable and fails on any disagreement.
- Files the importer needs (place in `data/nasa/raw/OSD-546/`):
  `GLDS-546_array_normalized_expression_probeset.csv` (19,811,541 bytes) and
  `GLDS-546_array_SampleTable.csv` (574 bytes). The importer matches sample columns to verified GSM IDs or file
  codes and fails if the SampleTable group disagrees with the verified flight/ground factor.
- Not a measurement of astronaut bone density, bone mineral density or fracture risk. SENTINEL does not
  recompute or reinterpret differential expression.

## 2c. OSD-656: Inspiration4 urine inflammation panel (P1, imported)

`HUMAN_SPACEFLIGHT`. Record schema `BIO_ASSAY_TABLE`. Importer: `Backend/app/importers/osd656.py`.

| File in `data/nasa/raw/OSD-656/` | SHA-256 |
|---|---|
| `LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv` | `f81b6dff9c34accab6dffe7a0b2970854f2f0b8d2712e92cfd0e91e6bb59c94a` |
| `LSDS-64_Multiplex_200plex v1-Target Information.csv` (annotation) | `7ced5075db3df9e47b8cf14e1bc57e49ab34cb49b6d5f76325d6def88ae7ee2a` |

**What was imported**
- **8,888 values:** 22 urine samples × 404 named measurement columns, covering 203 targets.
- **Measures per target:** `concentration_npq` (NPQ units) and `percent_normalized_value`, both as published.
- **Missing values:** 52 `NA` values stored as `null`. Most are in `c1qa_percent_normalized_value` (22),
  `il17c_…` (12) and `bdnf_…` (10).
- **Samples and timepoints:** subjects C001–C004 at L-92, L-44, L-3, R+1, R+45 and R+82. These are ground
  samples taken before launch and after return. Not every subject has every timepoint: C001 has no L-3 or
  R+1 sample.
- **Annotation:** gene name, UniProt ID and protein name come from NASA's target information file, joined
  on exact normalised target name. All 203 targets matched.
- **Verified:** IL6 `concentration_npq` for C001 at all 4 timepoints equals the source file, and an automated
  test compares every 37th column of every row with the CSV.

**Not imported**
- **Two blank columns:** NASA's file has two columns with an **empty header**, at positions 3 and 215. The
  first follows `activin_a_concentration_npq` and is probably Activin A's percent value, but that can't be
  verified, so neither column is imported. Both are listed in the import summary.
- **The SUBMITTED `.xlsx`:** not read. The TRANSFORMED CSV is NASA's tabular release.

**Limitations**
- NPQ and percent-normalized values are relative assay units, not clinical concentrations, and there are no
  reference ranges.
- Four crew members only.
- Never used as SENTINEL astronaut data.

## 2e. OSD-817: ex vivo human optic nerve (SANS model), TUNEL and CTB counts (imported)

`HUMAN_DERIVED_CELLS`; OSDR Project Type "Ground Study". Record schema `HISTOLOGY_COUNTS_V1`. Importer:
`Backend/app/importers/osd817.py`. Served by `GET /api/v1/research/datasets/OSD-817/records` in
`histology_records[]`.

**What the study did** (from the OSDR description and protocols):
- De-identified human donor eyes were cultured for 14 days in a translaminar autonomous system, a ground model of
  spaceflight-associated neuro-ocular syndrome (SANS).
- Six groups combined ICP:IOP pressures (12:16, 15:16, 12:21→12:16 and 21:16 mmHg) with 0°, 6° or 10° optic-nerve
  tilt.
- **TUNEL** marks DNA fragmentation (apoptotic cells).
- **CTB** (cholera toxin B, perfused for 48 h) measures retrograde axonal transport through the optic nerve head.
- Counts were made by a masked observer.

| File in `data/nasa/raw/OSD-817/` | SHA-256 |
|---|---|
| `LSDS-135_immunostaining_TUNEL_TRANSFORMED.csv` | `bf64e59178ff076d60ae3ea5c52094ff27787ca13055a43f3ca706abbc502fea` |
| `LSDS-135_immunostaining_CTB_TRANSFORMED.csv` | `b1e6ec9c5518c6d03f71a4e5664b1b080cf171c8b25fa835aa3a8069a165ea2d` |
| `LSDS-135_immunostaining_Tunel Analysis_SUBMITTED.xlsx` | `68a53b52cbd09730d4a48735c75e6555cb91d936d5b8d8f6254875ebc921bf1d` |
| `LSDS-135_immunostaining_CTB Analysis_SUBMITTED.xlsx` | `7290682b8f0ac224b1960ce7040a9573850883219216fb4543b099d0a1d10694` |

**What was imported**
- **72 values:** 2 assays × 18 formalin-fixed eyes (9 donors × right/left) × counts and normalized counts. There
  are no missing values.
- **Annotation:** each eye also gets its group number, days on system, donor sex and age, and image-quality notes
  (for example "Image overexposed; New image taken" or "Missing; Very faint stain - had to repeat") from the
  NASA SUBMITTED workbooks.
- **Checks:** every workbook count equals the CSV count. Every workbook normalized value rounds to the CSV value;
  for example, the workbook holds 2.4449999 and the CSV shows 2.45. A test compares all 72 values with the CSVs.

**Group numbers are not mapped to conditions.**
- The workbook's "Counts/Normalized to Control" column uses the Group 6 eye of each block of three donors as 1.0.
- The OSDR description defines Group 6 as 15:16 mmHg with a 10° tilt, which is not an obvious control.
- The group numbering therefore can't be verified against the description, so `group_number` is published
  verbatim and no pressure or tilt label is attached.

**Not imported**
- `LSDS-135_Immunohistochemistry_07346_OD.zip` (61 MB): 16 microscopy TIFF images of one eye; these are images,
  not numbers.
- PPD axon counts: no file supplied.
- Donor race: present in the workbook, but not needed.

**Limitations**
- Ex vivo donor tissue on the ground: not astronaut or spaceflight data, and never used to diagnose SANS.
- One eye per group per donor; tiny sample.

## 2d. NASA-RADLAB: RadLab ISS radiation snapshot (P1, imported)

`SPACEFLIGHT_ENVIRONMENT`. Record schema `RADIATION_TIMESERIES_V1`. Importer: `Backend/app/importers/radlab.py`.
Served by `GET /api/v1/radiation/timeseries`.

**Source:** the public RadLab data API (no key; docs https://visualization.osdr.nasa.gov/radlab/gui/data-api/).
One query was saved unchanged on 2026-11-14 and downloaded twice, byte-identical both times:

```
https://visualization.osdr.nasa.gov/radlab/api/?spacecraft=ISS&timestamp%3E=2022-04-01T00%3A00&timestamp%3C2022-04-02T00%3A00&module&instrument_family&absorbed_dose_rate&dose_equivalent_rate&latitude&longitude&altitude&format=csv
```

| File in `data/nasa/raw/NASA-RADLAB/` | Content |
|---|---|
| `radlab_ISS_2022-04-01.csv` | API output, SHA-256 `ed71c71ed9ec7684520dcd9a444ce2713809af2f4147e744bdb348b2cfc04733`, 2,847 rows, 293 KB |
| `radlab_ISS_2022-04-01.query.json` | the exact query URL, retrieval time and SHA-256 (the importer refuses a CSV whose hash differs) |

**What was imported**
- **2,847 absorbed dose-rate readings** (μGy/hour, unit from the RadLab API docs) on 2022-04-01, from the ISS
  Columbus module:

  | Instrument | Readings |
  |---|---|
  | DosTel1 | 1,192 |
  | DosTel2 | 1,197 |
  | Lidal | 288 |
  | REM-Lid | 170 |

- Each reading carries the ISS latitude, longitude and altitude at that time.
- **Verified:** every reading equals its source row (automated test), and the provenance `source_url` is the
  exact query URL.

**Data quirks, kept honest**
- **Dose-equivalent rate (μSv/hour) is empty** for every row that day, so it is not stored. Its 2,847 empty
  cells are counted in the import summary.
- **Three DosTel1 timestamps appear twice** with different values: 04:45:00, 09:10:00 and 09:15:00. Both
  readings are kept as published, neither picked nor averaged, and the pairs are listed in
  `summary.repeated_readings`.
- **RadLab timestamps carry no timezone.** SENTINEL treats them as UTC, because ISS operations run on UTC.
  This is an assumption; the original text stays in `timestamp_raw`.

**Limitations:** one historical day only. These are area dosimeters in one ISS module, not live data, not
HAB-01 readings, and not any crew member's personal dose. Instruments differ in design and placement. No
radiation limits, alerts or health interpretation are derived from the values.

### Transformation

One record per probe/probeset per sample. Values are parsed to numbers with the original text kept in
`value_raw`. NA/NaN/empty values are stored as `null`, never 0. Probe IDs and gene symbols are kept verbatim
(a symbol only when it is in the NASA file, never inferred). Each file import is atomic and deduplicated by
SHA-256, and a JSON log is written to `Backend/var/import_logs/`. No re-normalisation, fold change or
statistics are computed.

## 3. Submission text (dataset section)

> SENTINEL AI integrates NASA OSDR study OSD-575 (SpaceX Inspiration4 blood serum metabolic panel,
> https://osdr.nasa.gov/bio/repo/data/studies/OSD-575). We import the published comprehensive metabolic panel
> file `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (531 measurements: 19 analytes, 4 crew
> members, 7 pre- and post-flight timepoints) without altering values, units, subject IDs or timepoints, keeping
> missing values as missing. The app shows these real measurements as research context beside its simulated
> astronaut workflow, clearly labelled, and never treats them as live or in-flight readings or as personal
> medical thresholds.
