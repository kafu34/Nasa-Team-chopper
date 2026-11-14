"""Verified sample metadata for the NASA OSDR gene-expression studies OSD-195 and OSD-546.

Source: NASA OSDR study metadata API, read on 2026-11-14:
  https://osdr.nasa.gov/osdr/data/osd/meta/195  and  .../files/195
  https://osdr.nasa.gov/osdr/data/osd/meta/546  and  .../files/546

These are *metadata* (sample identity and experimental factors), not measurements. No expression value is
stored here. Factor values marked verified=True were read verbatim from NASA metadata. For OSD-546 the OSDR
study sample table leaves Treatment empty, but NASA GeneLab's processed SampleTable and runsheet state it.
"""
from __future__ import annotations

# ----------------------------------------------------------------------------- OSD-195 (bed rest, human)
# 12 male volunteers (vastus lateralis biopsies), factor "Bed Rest": "Before Bed Rest" / "After Bed Rest".
# Subject numbers are as published (1-14 with gaps). Each subject has exactly one Before and one After sample.
_OSD195_SUBJECTS = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 9, 9, 11, 11, 12, 12, 13, 13, 14, 14]

OSD195_SAMPLES: dict[str, dict] = {}
for _i, _subject in enumerate(_OSD195_SUBJECTS):
    _gsm = f"GSM{2813727 + _i}"
    _phase = "Before Bed Rest" if _i % 2 == 0 else "After Bed Rest"
    OSD195_SAMPLES[_gsm] = dict(
        subject_id=str(_subject),
        factors={"Bed Rest": _phase},
        factors_verified={"Bed Rest": True},
        condition_label=f"Subject {_subject}, {_phase.lower()}",
        processed_file=f"GLDS-195_microarray_{_gsm}_processed.txt",
    )

# ----------------------------------------------------------------------------- OSD-546 (human MSCs on ISS)
# Factor "Spaceflight": "Space Flight" / "Ground Control" (verified). Medium derived from file-name codes.
_OSD546 = [
    ("GSM2696758", "Space Flight", "R1211_FM_OM_1"),
    ("GSM2696759", "Space Flight", "R1211_FM_OM_2"),
    ("GSM2696760", "Space Flight", "R1211_FM_OM_3"),
    ("GSM2696761", "Space Flight", "R1211_FM_SM_1"),
    ("GSM2696762", "Space Flight", "R1211_FM_SM_2"),
    ("GSM2696763", "Space Flight", "R1211_FM_SM_3"),
    ("GSM2696764", "Space Flight", "R1211_FM_SM_4"),
    ("GSM2696765", "Ground Control", "R1211_GM_OM_1"),
    ("GSM2696766", "Ground Control", "R1248_GM_OM_2"),
    ("GSM2696767", "Ground Control", "R1248_GM_OM_3"),
    ("GSM2696768", "Ground Control", "R1234_GM_SM_1"),
    ("GSM2696769", "Ground Control", "R1234_GM_SM_2"),
    ("GSM2696770", "Ground Control", "R1234_GM_SM_3"),
]
# Treatment (culture medium) values are verbatim from the NASA GeneLab files GLDS-546_array_SampleTable.csv
# ("(Space Flight & osteogenic)") and GLDS-546_array_microarray_v0_runsheet.csv (Factor Value[Treatment]),
# checked 2026-11-14; they agree with the file-name codes OM / SM. The importer re-checks every sample's
# Spaceflight and Treatment against the SampleTable and fails on any disagreement.
_MEDIUM = {"OM": "osteogenic", "SM": "standard"}

OSD546_SAMPLES: dict[str, dict] = {}
for _gsm, _flight, _code in _OSD546:
    _medium = _MEDIUM[_code.split("_")[2]]
    OSD546_SAMPLES[_gsm] = dict(
        subject_id=None,
        code=_code,
        factors={"Spaceflight": _flight, "Treatment": _medium},
        factors_verified={"Spaceflight": True, "Treatment": True},
        condition_label=f"{_flight}, {_medium} medium",
        processed_file=None,
    )

SAMPLES = {"OSD-195": OSD195_SAMPLES, "OSD-546": OSD546_SAMPLES}
