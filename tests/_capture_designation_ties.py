"""D8 evidence — a CATALOGUE-WIDE census of competing `* ` designations.

ONE-SHOT, LIVE-NETWORK utility. Not collected by pytest (leading underscore).
The committed artifact is `tests/fixtures/designation_ties.json`; this script
exists so a re-census is reproducible — the `_capture_designation_fixtures.py`
(AN4.0) precedent.

    venv/bin/python -m tests._capture_designation_ties

**Why this exists.** `core.shared._preferred_star_id`'s D8 rule breaks ties by
falling back to `candidates[0]` — SIMBAD's own id ordering, which is exactly the
dependency D8 was written to remove. Its docstring says the residual case (two
Bayer candidates, neither carrying a component letter) has **no corpus example**,
so nothing depends on it, and that "if a real example appears, that is the
evidence to settle it with."

One appeared during Phase AN3 (κ Ceti). This census answers the question that
finding raised — *how many are there, and of what shapes?* — over the whole
catalogue rather than the 43-star fixture corpus, because the corpus is a
shape-coverage sample and was never meant to measure frequency.

**Method.** One ADQL query against SIMBAD's `ident` table for every `* `-prefixed
identifier (~6.3k rows over ~4.7k objects), grouped by `oidref`, then the *real*
`core.shared` classifier and precedence helpers are applied to each object's id
list. Using the shipped functions rather than a re-implementation is the point:
what is measured is what production would actually do.

**This script changes no behaviour and is not a fix.** It produces the evidence a
D8 reopen would need; the reopen is its own decision, with its own golden regen.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.shared import (  # noqa: E402
    _classify_star_id, _preferred_star_id, _star_id_constellation,
    _BAYER_NUMERAL_RE, _COMPONENT_SUFFIX_RE,
)

OUT_PATH = Path(__file__).resolve().parent / "fixtures" / "designation_ties.json"

# Every Bayer AND Flamsteed id in SIMBAD. Both systems share the `* ` prefix, so
# one query covers both and the classifier splits them afterwards.
_ADQL = "SELECT id, oidref FROM ident WHERE id LIKE '* %'"
_MAXREC = 200_000


def _letter(id_str):
    return id_str.strip()[2:].split()[0]


def _numeral(id_str):
    """The superscript numeral of a Bayer token ("alf01" → "01"), or None."""
    m = _BAYER_NUMERAL_RE.match(_letter(id_str))
    return m.group(2) if m and m.group(1) else None


def _bayer_shape(survivors):
    """Classify WHY clause (i) failed to separate these candidates."""
    if len({_star_id_constellation(i) for i in survivors}) > 1:
        # The Bayer analogue of Fomalhaut's cross-boundary Flamsteed duplicate —
        # one star lettered in two constellations (Alpheratz = α And = δ Peg).
        # Clause (ii) has no Bayer sibling, so nothing addresses this.
        return "cross_constellation"
    if len({_letter(i).rstrip("0123456789") for i in survivors}) > 1:
        return "different_letters"
    if {_numeral(i) for i in survivors} == {None}:
        return "case_or_suffix_distinct"
    return "bare_vs_superscript"          # the shape D8's docstring asked about


def _flamsteed_shape(candidates, chosen_bayer):
    if chosen_bayer and len({_star_id_constellation(i) == _star_id_constellation(chosen_bayer)
                             for i in candidates}) > 1:
        return "resolved_by_clause_ii"
    if len({_star_id_constellation(i) for i in candidates}) > 1:
        return "cross_constellation_no_bayer"
    if len({_COMPONENT_SUFFIX_RE.search(i) is not None for i in candidates}) > 1:
        # Clause (i)'s component-less preference is BAYER-ONLY. Nothing covers
        # the identical shape on a Flamsteed id.
        return "bare_vs_component"
    return "other"


def census(rows):
    by_object = collections.defaultdict(list)
    for id_str, oid in rows:
        by_object[oid].append(str(id_str).strip())

    out = {"objects": len(by_object), "bayer": [], "flamsteed": []}
    for ids in by_object.values():
        uniq = sorted(set(ids))
        bayer = [i for i in uniq if _classify_star_id(i) == "Bayer"]
        flamsteed = [i for i in uniq if _classify_star_id(i) == "Flamsteed"]

        # Clause (i) as shipped: drop the component-suffixed forms, if that
        # leaves anything. More than one survivor === an unresolved tie.
        survivors = [i for i in bayer if not _COMPONENT_SUFFIX_RE.search(i)] or bayer
        if len(survivors) > 1:
            out["bayer"].append({"shape": _bayer_shape(survivors),
                                 "candidates": survivors,
                                 "chosen": _preferred_star_id(bayer, "Bayer")})
        if len(flamsteed) > 1:
            chosen_bayer = _preferred_star_id(bayer, "Bayer") if bayer else None
            out["flamsteed"].append({
                "shape": _flamsteed_shape(flamsteed, chosen_bayer),
                "candidates": flamsteed,
                "bayer": chosen_bayer,
                "chosen": _preferred_star_id(flamsteed, "Flamsteed", chosen_bayer),
            })

    for key in ("bayer", "flamsteed"):
        out[key].sort(key=lambda e: (e["shape"], e["candidates"]))
        out[key + "_by_shape"] = dict(
            collections.Counter(e["shape"] for e in out[key]).most_common()
        )
    return out


def main():
    from astroquery.simbad import Simbad

    simbad = Simbad()
    simbad.TIMEOUT = 300
    print(f"querying SIMBAD ident … ({_ADQL})")
    table = simbad.query_tap(_ADQL, maxrec=_MAXREC)
    rows = [(str(r["id"]), int(r["oidref"])) for r in table]
    print(f"  {len(rows)} ids")

    data = census(rows)
    data["_comment"] = (
        "Catalogue-wide census of stars carrying MORE THAN ONE competing Bayer or "
        "Flamsteed id, i.e. where core.shared._preferred_star_id's D8 rule falls "
        "back to SIMBAD's id ordering. Evidence for a D8 reopen; see "
        "completed_plans/PHASE_AN_PLAN.md §4b. Regenerate with "
        "`venv/bin/python -m tests._capture_designation_ties`."
    )
    data["source"] = f"SIMBAD TAP `ident` ({_ADQL}), {len(rows)} ids"
    data["ids_total"] = len(rows)

    OUT_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"\nobjects with a `* ` id : {data['objects']}")
    print(f"Bayer ties             : {len(data['bayer'])}  {data['bayer_by_shape']}")
    print(f"Flamsteed ties         : {len(data['flamsteed'])}  {data['flamsteed_by_shape']}")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
