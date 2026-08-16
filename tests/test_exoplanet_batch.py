"""tests/test_exoplanet_batch.py — offline coverage for CR-8 batch ps pull (core/exoplanet_batch.py).

Pure logic — no network. The archive (``_query_tap``) and SIMBAD (``compute_simbad_lookup``) are the
only network seams; both are imported into the module namespace, so they're monkeypatched here with
synthetic rows whose answers are known. Locks: reflink parsing, the mass-kind enum (incl. the WB
MSG 060 ``M-R relationship`` third value that must NOT collapse into ``true_mass``), null-vs-0
eccentricity / un-fabricated null inclination, Mode A/B mutual exclusion, the coverage manifest
(unresolved + zero-planet never dropped), ADQL WHERE construction, and default_flag scoping. The live
§5.1 HD 136352 anchor (batch≡single) lives in tests/test_query_exoplanet_batch_live.py.
"""

import unittest
from unittest import mock

from core import exoplanet_batch as eb

_REFLINK = ("<a refstr=DELREZ_ET_AL_2021 href=https://ui.adsabs.harvard.edu/abs/2021NatAs..."
            "5..775D/abstract target=ref>Delrez et al. 2021</a>")


def _planet_row(**kw):
    row = {"pl_name": "X b", "hostname": "HD 1", "discoverymethod": "Radial Velocity",
           "pl_orbper": "10.0", "pl_orbsmax": "0.1", "pl_orbincl": None, "pl_orbeccen": None,
           "pl_orblper": None, "pl_bmasse": "5.0", "pl_bmassj": "0.0157", "pl_bmassprov": "Msini",
           "pl_rade": None, "tran_flag": "0", "default_flag": "1", "pl_refname": _REFLINK,
           "st_spectype": "G2 V", "st_teff": "5700", "st_mass": "0.9", "st_rad": "0.95",
           "st_met": "-0.1", "sy_dist": "12.0", "sy_vmag": "5.6", "sy_kmag": "4.2",
           "sy_gaiamag": "5.5", "sy_pnum": "1", "st_refname": _REFLINK,
           "hd_name": "HD 1", "hip_name": "HIP 1", "tic_id": "TIC 1", "gaia_dr3_id": "Gaia DR3 1"}
    row.update(kw)
    return row


class ReflinkTest(unittest.TestCase):
    def test_parses_citation_refstr_href(self):
        r = eb._parse_reflink(_REFLINK)
        self.assertEqual(r["citation"], "Delrez et al. 2021")
        self.assertEqual(r["refstr"], "DELREZ_ET_AL_2021")
        self.assertTrue(r["href"].startswith("https://ui.adsabs"))
        self.assertEqual(r["raw"], _REFLINK)

    def test_none_and_unrecognised(self):
        self.assertIsNone(eb._parse_reflink(None))
        self.assertIsNone(eb._parse_reflink(""))
        # markup we can't pattern-match → strip tags, keep text, refstr/href None
        r = eb._parse_reflink("<b>Smith 2020</b>")
        self.assertEqual(r["citation"], "Smith 2020")
        self.assertIsNone(r["refstr"])


class MassKindTest(unittest.TestCase):
    def test_enum(self):
        self.assertEqual(eb._mass_kind("Mass"), "true_mass")
        self.assertEqual(eb._mass_kind("Msini"), "msini")
        self.assertEqual(eb._mass_kind("Msin(i)/sin(i)"), "msini")
        # WB MSG 060: the third category stays its own value, never laundered as true_mass.
        self.assertEqual(eb._mass_kind("M-R relationship"), "mass_radius_relation")
        self.assertEqual(eb._mass_kind(None), "unknown")
        self.assertEqual(eb._mass_kind("something else"), "unknown")


class NumFlagTest(unittest.TestCase):
    def test_num(self):
        self.assertEqual(eb._num("1.5"), 1.5)
        self.assertIsNone(eb._num(None))
        self.assertIsNone(eb._num(""))
        self.assertIsNone(eb._num("nan-ish-text"))

    def test_flag(self):
        self.assertIs(eb._flag("1"), True)
        self.assertIs(eb._flag("0"), False)
        self.assertIsNone(eb._flag(None))       # null flag stays None, not False
        self.assertIsNone(eb._flag(""))


class PlanetRecordTest(unittest.TestCase):
    def test_meaningful_nulls_preserved(self):
        rec = eb._planet_record(_planet_row(pl_orbincl=None, pl_orbeccen=None), "core")
        self.assertIsNone(rec["inclination_deg"])   # RV-only → null, not 90
        self.assertIsNone(rec["eccentricity"])       # unmeasured → null

    def test_reported_zero_distinct_from_null(self):
        rec = eb._planet_record(_planet_row(pl_orbeccen="0.0"), "core")
        self.assertEqual(rec["eccentricity"], 0.0)   # reported fixed-circular → 0, distinguishable

    def test_mass_and_provenance(self):
        rec = eb._planet_record(_planet_row(pl_bmassprov="Msini"), "core")
        self.assertEqual(rec["mass_kind"], "msini")
        self.assertEqual(rec["mass_prov_raw"], "Msini")
        self.assertEqual(rec["provenance"]["citation"], "Delrez et al. 2021")
        self.assertIs(rec["transiting"], False)
        self.assertNotIn("raw", rec)

    def test_full_scope_adds_raw(self):
        rec = eb._planet_record(_planet_row(), "full")
        self.assertIn("raw", rec)


class HostRecordTest(unittest.TestCase):
    def test_archive_first_then_simbad_fallback(self):
        # archive st_spectype null → SIMBAD sp_type used and source tagged
        rows = [_planet_row(st_spectype=None, st_teff=None)]
        simbad = {"main_id": "* nu.02 Lup", "sp_type": "G3 V", "teff": 5664.0, "fe_h": -0.34,
                  "parsecs": 14.68, "vmag": 5.65, "designations": {"MAIN_ID": "* nu.02 Lup", "GJ": "GJ 1"}}
        rec = eb._host_record("HD 1", rows, simbad, "core")
        self.assertEqual(rec["resolved_host"], "* nu.02 Lup")
        self.assertEqual(rec["spectral_type"], "G3 V")
        self.assertEqual(rec["stellar_param_sources"]["spectral_type"], "simbad")
        self.assertEqual(rec["stellar_param_sources"]["teff_k"], "simbad")
        self.assertEqual(rec["stellar_param_sources"]["mass_solar"], "archive")
        self.assertEqual(rec["magnitudes"]["V"], 5.6)   # archive V present → not overwritten
        self.assertIn("GJ", rec["cross_ids"])
        self.assertEqual(rec["input"], "HD 1")

    def test_magnitudes_band_labelled(self):
        rec = eb._host_record(None, [_planet_row()], None, "core")
        self.assertEqual(set(rec["magnitudes"]), {"V", "K", "Gaia_G"})
        self.assertEqual(rec["resolved_host"], "HD 1")   # Mode B → hostname

    def test_num_planets_distinct(self):
        rows = [_planet_row(pl_name="HD 1 b"), _planet_row(pl_name="HD 1 c"),
                _planet_row(pl_name="HD 1 b")]   # a duplicate solution
        rec = eb._host_record(None, rows, None, "core")
        self.assertEqual(rec["num_planets"], 2)
        self.assertEqual(len(rec["planets"]), 3)


class WhereClauseTest(unittest.TestCase):
    def test_ranges_and_method(self):
        w = eb._build_where({"pl_bmasse_min": 1, "pl_rade_max": 4, "discoverymethod": "Transit"})
        self.assertIn("pl_bmasse >= 1.0", w)
        self.assertIn("pl_rade <= 4.0", w)
        self.assertIn("discoverymethod = 'Transit'", w)

    def test_empty_is_not_null_guard(self):
        self.assertEqual(eb._build_where({}), "pl_name IS NOT NULL")

    def test_select_core_vs_full(self):
        self.assertEqual(eb._select_clause("full"), "*")
        core = eb._select_clause("core")
        self.assertIn("pl_orbincl", core)
        self.assertIn("default_flag", core)
        self.assertEqual(core.count("hostname"), 1)   # order-preserving dedupe

    def test_default_clause_scope(self):
        self.assertEqual(eb._default_clause("default"), "default_flag = 1")
        self.assertEqual(eb._default_clause("all"), "")


class ValidationTest(unittest.TestCase):
    def test_bad_scopes(self):
        self.assertIn("error", eb.compute_exoplanet_batch(hosts=["HD 1"], solution_scope="x"))
        self.assertIn("error", eb.compute_exoplanet_batch(hosts=["HD 1"], field_scope="x"))

    def test_exactly_one_mode(self):
        both = eb.compute_exoplanet_batch(hosts=["HD 1"], filters={"pl_rade_min": 1})
        self.assertIn("not both", both["error"])
        neither = eb.compute_exoplanet_batch()
        self.assertIn("Supply exactly one", neither["error"])
        self.assertEqual(neither["route_tried"], ["nasa-tap:ps"])

    def test_empty_hosts(self):
        self.assertIn("error", eb.compute_exoplanet_batch(hosts=[]))
        self.assertIn("error", eb.compute_exoplanet_batch(hosts=["", "  "]))


class ModeAFlowTest(unittest.TestCase):
    def _simbad(self, name):
        table = {
            "HD 1": {"main_id": "HD 1", "sp_type": "G2 V", "teff": 5700.0, "fe_h": -0.1,
                     "parsecs": 12.0, "vmag": 5.6, "designations": {"HD": "HD 1", "MAIN_ID": "HD 1"}},
            "Vega": {"main_id": "Vega", "sp_type": "A0 V", "teff": 9600.0, "fe_h": None,
                     "parsecs": 7.7, "vmag": 0.03, "designations": {"HD": "HD 172167", "MAIN_ID": "Vega"}},
        }
        if name in table:
            return table[name]
        return {"error": f"No results found for '{name}'"}

    def test_resolved_zero_planet_and_unresolved_all_reported(self):
        # archive returns rows only for HD 1's key (hd_name='HD 1'); Vega's HD 172167 → no rows.
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            if "'HD 1'" in where:
                return [_planet_row(pl_name="HD 1 b"), _planet_row(pl_name="HD 1 c")]
            return []
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(hosts=["HD 1", "Vega", "Nope123"])
        self.assertEqual(out["mode"], "hosts")
        cov = out["coverage"]
        self.assertEqual(cov["requested"], ["HD 1", "Vega", "Nope123"])
        self.assertEqual(cov["resolved_count"], 2)               # HD 1 + Vega resolved in SIMBAD
        self.assertEqual(cov["returned_host_count"], 1)          # only HD 1 had planets
        self.assertEqual([z["input"] for z in cov["zero_planet"]], ["Vega"])
        self.assertEqual([u["input"] for u in cov["unresolved"]], ["Nope123"])
        self.assertEqual(cov["total_planets"], 2)
        self.assertEqual(out["hosts"][0]["resolved_host"], "HD 1")

    def test_default_scope_adds_flag_all_scope_omits(self):
        seen = {}
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            seen["where"] = where
            return [_planet_row(pl_name="HD 1 b")]
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            eb.compute_exoplanet_batch(hosts=["HD 1"], solution_scope="default")
            self.assertIn("default_flag = 1", seen["where"])
            eb.compute_exoplanet_batch(hosts=["HD 1"], solution_scope="all")
            self.assertNotIn("default_flag", seen["where"])


class ModeBFlowTest(unittest.TestCase):
    def test_groups_by_hostname_and_echoes_selection(self):
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            self.assertIn("default_flag = 1", where)   # default scope wraps the filter
            return [_planet_row(hostname="HD 1", pl_name="HD 1 b"),
                    _planet_row(hostname="HD 2", pl_name="HD 2 b")]
        with mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(filters={"pl_rade_min": 1.0})
        self.assertEqual(out["mode"], "filter")
        self.assertEqual(out["coverage"]["total_hosts"], 2)
        self.assertIn("pl_rade >= 1.0", out["coverage"]["selection_echo"])

    def test_raw_archive_query_passthrough(self):
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            self.assertIn("sy_dist < 10", where)
            return [_planet_row(hostname="HD 9")]
        with mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(archive_query="sy_dist < 10")
        self.assertEqual(out["mode"], "filter")


if __name__ == "__main__":
    unittest.main()
