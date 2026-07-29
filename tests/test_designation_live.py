# tests/test_designation_live.py — network test (auto-skipped when SIMBAD is down).
#
# A TRIPWIRE, not coverage. Phase AN's D8 clause (i) prefers the component-less
# Bayer form unconditionally, which /code-review flagged as attributing a SYSTEM's
# designation to a single component (PHASE_AN_PLAN.md §4b). Measurement closed that
# question: the bad combination — a distinct component object that ALSO lists its
# parent's bare Bayer id — does not occur in SIMBAD's data model today.
#
# Both halves of that argument are claims about a LIVE external catalogue, so they
# are asserted against the live catalogue rather than trusted:
#
#   1. `bet Per A` resolves to the SYSTEM object (main_id "* bet Per"). Its ids do
#      contain the bare "* bet Per", but so does its main_id — so D3 suppresses the
#      pick and nothing is misattributed. If SIMBAD ever promotes Algol A to its own
#      object, main_id becomes "* bet Per A" while "* bet Per" stays in the id list,
#      and clause (i) starts attributing the system id to a component.
#   2. `alf Cen A` IS its own object, and its ids do NOT carry the bare "* alf Cen".
#      This is the other half: where a component object exists, the parent's bare
#      form is absent.
#
# A failure here is not a bug in this repo — it means the upstream premise moved and
# the §4b question reopens with evidence. The offline corpus cannot detect this: it
# is a frozen 2026-07-29 snapshot of exactly the thing being watched.

import unittest

from tests._netcheck import simbad_reachable
from core.shared import _classify_star_id, _match_designations, _CSV_DESIG_KEYS

_ONLINE = simbad_reachable()

# AN1 wrote this as `_CSV_DESIG_KEYS + ["Bayer", "Flamsteed"]` because the shipped key
# set did not yet carry them. AN2 added both, so the concatenation would now merely
# DUPLICATE them — harmless (_match_designations builds a dict) but no longer what the
# name claims, and the one place a duplicated key list could reach _join_designations.
# Its sibling in test_designation_ids.py was updated for the same reason.
_KEYS_WITH_STAR = list(_CSV_DESIG_KEYS)


def _ids(query):
    from astroquery.simbad import Simbad
    table = Simbad.query_objectids(query)
    return [] if table is None else [str(row["id"]).strip() for row in table]


def _main_id(query):
    from core.shared import _make_simbad
    table = _make_simbad("sp_type").query_object(query)
    return None if table is None else str(table["main_id"][0]).strip()


@unittest.skipUnless(_ONLINE, "SIMBAD unreachable")
class ComponentQueryPremiseTest(unittest.TestCase):
    """The two measurements §4b's resolution rests on."""

    def test_algol_component_query_still_resolves_to_the_system_object(self):
        """If this fails, D8 clause (i) needs the conditional rule after all."""
        ids = _ids("bet Per A")
        main_id = _main_id("bet Per A")

        self.assertIn("* bet Per", ids, "premise: the bare system form IS in the ids")
        self.assertEqual(
            main_id, "* bet Per",
            "SIMBAD now resolves 'bet Per A' to its own object while still listing "
            "the system's bare Bayer id — the combination PHASE_AN_PLAN.md §4b "
            "measured as absent. D8 clause (i) would attribute '* bet Per' to a "
            "single component, and D3 would no longer suppress it. Reopen §4b.",
        )

        # With main_id == the pick, D3 suppresses it: nothing is misattributed.
        self.assertEqual(_match_designations(ids, _KEYS_WITH_STAR)["Bayer"], main_id)

    def test_a_real_component_object_does_not_carry_the_bare_system_form(self):
        """The other half — α Cen A is its own object, and lacks '* alf Cen'."""
        ids = _ids("alf Cen A")
        self.assertEqual(_main_id("alf Cen A"), "* alf Cen A")
        self.assertNotIn("* alf Cen", ids)
        self.assertEqual(_match_designations(ids, _KEYS_WITH_STAR)["Bayer"], "* alf01 Cen")


@unittest.skipUnless(_ONLINE, "SIMBAD unreachable")
class ClassifierAgainstLiveIdsTest(unittest.TestCase):
    """Guards the frozen corpus against SIMBAD changing its id FORMATTING.

    The offline tests replay a 2026-07-29 capture; if SIMBAD ever emits Flamsteed
    ids with a single space, or re-cases a prefix, every offline test still passes
    while production silently stops classifying. Cheap to check, impossible to see
    from the fixtures.
    """

    def test_the_prefix_shapes_the_classifier_keys_off_are_unchanged(self):
        ids = _ids("eps Eri")
        bayer = [i for i in ids if _classify_star_id(i) == "Bayer"]
        flamsteed = [i for i in ids if _classify_star_id(i) == "Flamsteed"]
        variable = [i for i in ids if _classify_star_id(i) == "Variable"]

        self.assertIn("* eps Eri", bayer)
        self.assertIn("*  18 Eri", flamsteed, "note the DOUBLE space (D9)")
        self.assertTrue(variable, "eps Eri should still carry a V* id")


if __name__ == "__main__":
    unittest.main()
