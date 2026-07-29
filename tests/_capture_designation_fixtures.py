"""AN4.0 — capture the SIMBAD fixture corpus for the Phase AN differential harness.

ONE-SHOT, LIVE-NETWORK utility. Not collected by pytest (leading underscore).
The committed artifact is `tests/fixtures/designation_ids.json`; this script exists
so a re-capture is reproducible, following the `gouldDesignations.csv` precedent
(PHASE_AN_PLAN.md §8, AN4.0).

    venv/bin/python -m tests._capture_designation_fixtures

Why capture rather than query at test time: the harness replays these lists on
every AN0 commit to prove the refactor is byte-identical. A live query would make
the baseline depend on SIMBAD uptime AND on SIMBAD's own catalogue revisions —
the second is the real hazard, since a changed `ids` list would look exactly like
a refactor regression.

The star list is chosen for SHAPE coverage, not astronomical interest — see the
per-group comments. Field set is the union of what `compute_simbad_lookup` and
`compute_lookup_star_for_distance` request, so one corpus drives both.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.shared import _make_simbad, _timeout_ctx, _with_retries  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "fixtures" / "designation_ids.json"

# Union of compute_simbad_lookup's fields and compute_lookup_star_for_distance's.
FIELDS = ("sp_type", "plx_value", "V", "mesfe_h")

# Columns the two parsers read via their local _safe() helpers.
WANTED_COLS = (
    "main_id", "ra", "dec", "sp_type", "plx_value", "V",
    "mesfe_h.teff", "mesfe_h.fe_h",
)

TARGETS = [
    # ── AN1 classifier shapes: the whole point of the phase ──────────────────
    "Procyon",            # * alf CMi + *  10 CMi + the "* alf CMi A" component (AN1b)
    "eps Eri",            # * eps Eri + *  18 Eri + V* eps Eri (AN1a)
    "tau Cet",            # * tau Cet + *  52 Cet
    "alf Cen A",          # * alf01 Cen — the superscript-numeral Bayer case
    "alf Cen B",          # * alf02 Cen
    "GJ 432 A",           # *  20 Crt — Flamsteed as main_id; also AO's 1875-boundary star
    "Sirius",             # * alf CMa + a "** " double-star id → the ordering pin
    "61 Cyg A",           # Flamsteed-led common name, component suffix
    "Betelgeuse",         # * alf Ori + V* alf Ori (bright variable)
    "Algol",              # * bet Per — eclipsing binary, "** " ids likely
    # Mizar — ** double-star system ids. Three resolution gotchas, all verified
    # 2026-07-29: the common name "Mizar" does not resolve at all; "zet UMa"
    # resolves with fields ("sp_type",) but MISSES with the full FIELDS set above
    # (mesfe_h is a JOIN, so requesting it can drop a row that otherwise resolves);
    # "* zet01 UMa" / "HD 116656" / "Mizar A" all resolve either way. A "no result"
    # here therefore means "not with THESE fields", not "not in SIMBAD".
    "* zet01 UMa",
    "Polaris",            # * alf UMi + component ids
    "Vega",               # * alf Lyr + *   3 Lyr
    "Arcturus",           # * alf Boo + *  16 Boo
    "Capella",            # * alf Aur — spectroscopic binary
    "Fomalhaut",          # * alf PsA — debris disk, planet host
    "Aldebaran",          # * alf Tau + *  87 Tau

    # ── Gould anchors (AO) — AN4.5's producer/consumer pin ───────────────────
    "HD 102365",          # 66 G. Centauri
    "HD 100623",          # 289 G. Hydrae (= GJ 432 A above, via a different query form)

    # ── Ordinary catalogue shapes, no Bayer/Flamsteed ────────────────────────
    "Barnard's star",     # NAME + GJ + BD+ + LHS — the dense-designation case
    "Wolf 359",           # the "Wolf " prefix; lowercase dwarf sp_type dM6
    "Ross 128",           # dM4
    "Proxima Centauri",   # NAME-led, GJ, LHS
    "Kapteyn's star",     # high proper motion, BD-
    "Luyten's star",      # LHS/Luyten
    "GJ 1214",            # GJ-only, no NAME — planet host
    "LHS 1140",           # LHS-led, M dwarf planet host
    "HD 209458",          # HD-led, no common name (planet host)
    "HR 8799",            # HR-led, direct-imaging host

    # ── Prefix-map coverage for the wider key set ────────────────────────────
    "Kepler-186",         # Kepler- prefix
    "TOI-700",            # TOI- prefix
    "WASP-12",            # WASP- prefix
    "CoRoT-7",            # CoRoT- prefix
    "K2-18",              # K2 prefix
    "HAT-P-11",           # HAT-P- prefix
    "TRAPPIST-1",         # 2MASS-led, NAME, no HD

    # ── Masked / partial fields: exercises the _safe() paths ─────────────────
    "Sirius B",           # white dwarf DA — sp_type outside OBAFGKM, sparse fields
    "GJ 35",              # van Maanen 2, DZ white dwarf — resolves as "Wolf   28",
                          # whose INTERNAL DOUBLE SPACES exercise the id-whitespace path
    "* omi02 Eri B",      # 40 Eri B — DA white dwarf in a Bayer+Flamsteed triple
    "Luhman 16",          # brown dwarf L/T — no HD/HIP, in gcns.missing_10mas
    "Teegarden's star",   # faint M, minimal designation set

    # ── Multi-component systems (AN1b component preference) ──────────────────
    "70 Oph A",           # Flamsteed + component
    "Castor",             # * alf Gem — 6-component system, many ** ids
]


def _row_value(row, col, col_names):
    """Mirror the two parsers' _safe() masked-value handling at capture time."""
    if col not in col_names:
        return None
    val = row[col]
    try:
        if hasattr(val, "mask") and val.mask:
            return None
    except Exception:
        pass
    s = str(val).strip()
    if s in ("", "--", "N/A", "nan", "None"):
        return None
    return s


def capture(name, simbad):
    from astroquery.simbad import Simbad

    with _timeout_ctx(30):
        result = _with_retries(simbad.query_object, name)
        ids_result = _with_retries(Simbad.query_objectids, name)

    if result is None or len(result) == 0:
        return None

    row = result[0]
    col_names = list(result.colnames)
    ids = [str(r["id"]).strip() for r in ids_result] if ids_result is not None else []

    return {
        "query": name,
        "colnames": [c for c in WANTED_COLS if c in col_names],
        "row": {c: _row_value(row, c, col_names) for c in WANTED_COLS if c in col_names},
        "ids": ids,
    }


def main():
    simbad = _make_simbad(*FIELDS)
    stars, failed = [], []

    for i, name in enumerate(TARGETS, 1):
        print(f"[{i}/{len(TARGETS)}] {name} … ", end="", flush=True)
        try:
            rec = capture(name, simbad)
        except Exception as e:
            print(f"ERROR ({type(e).__name__}: {e})")
            failed.append((name, f"{type(e).__name__}: {e}"))
            continue
        if rec is None:
            print("NO RESULT")
            failed.append((name, "no result"))
            continue
        stars.append(rec)
        star_ids = [i for i in rec["ids"] if i.startswith("* ") or i.startswith("V* ")
                    or i.startswith("** ")]
        print(f"ok — {len(rec['ids'])} ids ({len(star_ids)} star-prefixed)")

    payload = {
        "_comment": (
            "AN4.0 fixture corpus for the Phase AN differential harness. Captured live "
            "from SIMBAD by tests/_capture_designation_fixtures.py. Do not hand-edit: "
            "re-run the capture script instead. See PHASE_AN_PLAN.md §8 (AN4.0)."
        ),
        "source": "SIMBAD (astroquery) — query_object + query_objectids",
        "fields_requested": list(FIELDS),
        "star_count": len(stars),
        "stars": stars,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False, sort_keys=False)
        fh.write("\n")

    print(f"\nWrote {len(stars)} stars → {OUT_PATH.relative_to(Path.cwd())}"
          if OUT_PATH.is_relative_to(Path.cwd()) else f"\nWrote {len(stars)} stars → {OUT_PATH}")
    if failed:
        print(f"FAILED ({len(failed)}):")
        for name, why in failed:
            print(f"  {name}: {why}")
    print(f"Size: {os.path.getsize(OUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
