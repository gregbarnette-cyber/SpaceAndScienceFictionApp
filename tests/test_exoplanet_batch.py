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
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec (offline test)"}), \
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
            if table != "ps":                                # ignore CR-10.1 survey-table queries
                return []
            seen["where"] = where
            return [_planet_row(pl_name="HD 1 b")]
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec (offline test)"}), \
             mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            eb.compute_exoplanet_batch(hosts=["HD 1"], solution_scope="default")
            self.assertIn("default_flag = 1", seen["where"])
            eb.compute_exoplanet_batch(hosts=["HD 1"], solution_scope="all")
            self.assertNotIn("default_flag", seen["where"])


class ModeBFlowTest(unittest.TestCase):
    def test_groups_by_hostname_and_echoes_selection(self):
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            if table != "ps":                                # CR-10.1 survey-table queries: ignore
                return []
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
            if table != "ps":                                # CR-10.1 survey-table queries: ignore
                return []
            self.assertIn("sy_dist < 10", where)
            return [_planet_row(hostname="HD 9")]
        with mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(archive_query="sy_dist < 10")
        self.assertEqual(out["mode"], "filter")


class Cr9Tier1Test(unittest.TestCase):
    def test_intval_preserves_tri_state(self):
        self.assertEqual(eb._intval("1"), 1)
        self.assertEqual(eb._intval("-1"), -1)                 # the load-bearing lower-limit sign
        self.assertEqual(eb._intval("0"), 0)
        self.assertIsNone(eb._intval(None))
        self.assertIsNone(eb._intval(""))
        self.assertEqual(eb._intval("1.0"), 1)

    def test_disposition_and_detection_block(self):
        row = _planet_row(soltype="Published Confirmed", pl_controv_flag="1", ttv_flag="0",
                          cb_flag="0", tran_flag="1", rv_flag="1", ima_flag=None)
        d = eb._planet_record(row, "core")["disposition"]
        self.assertEqual(d["soltype"], "Published Confirmed")
        self.assertEqual(d["pl_controv_flag"], 1)
        self.assertEqual(d["detection"]["tran_flag"], 1)
        self.assertEqual(d["detection"]["rv_flag"], 1)
        self.assertIsNone(d["detection"]["ima_flag"])          # absent col → null, not 0
        self.assertEqual(d["detection_methods"], ["tran", "rv"])

    def test_limits_tri_state_not_collapsed(self):
        row = _planet_row(pl_bmasselim="-1", pl_orbeccenlim="1", pl_denslim="0")
        lim = eb._planet_record(row, "core")["limits"]
        self.assertEqual(lim["pl_bmasselim"], -1)              # NOT 1, NOT True (the D6 guarantee)
        self.assertEqual(lim["pl_orbeccenlim"], 1)
        self.assertEqual(lim["pl_denslim"], 0)
        self.assertIsNone(lim["pl_msinielim"])                 # absent → null

    def test_density_impact_inclerr(self):
        row = _planet_row(pl_dens="6.9", pl_imppar="0.32", pl_orbinclerr1="0.8", pl_orbinclerr2="-0.8")
        rec = eb._planet_record(row, "core")
        self.assertEqual(rec["pl_dens"], 6.9)
        self.assertEqual(rec["pl_imppar"], 0.32)
        self.assertEqual([rec["pl_orbinclerr1"], rec["pl_orbinclerr2"]], [0.8, -0.8])

    def test_tier1_is_in_core_select(self):
        sel = eb._select_clause("core")
        for c in ("pl_controv_flag", "soltype", "pl_bmasselim", "pl_orbinclerr1", "pl_imppar", "dkin_flag"):
            self.assertIn(c, sel)

    def test_null_disposition_when_absent(self):
        rec = eb._planet_record({"pl_name": "Y b"}, "core")
        self.assertIsNone(rec["disposition"]["pl_controv_flag"])
        self.assertIsNone(rec["limits"]["pl_bmasselim"])
        self.assertIsNone(rec["pl_dens"])
        self.assertEqual(rec["disposition"]["detection_methods"], [])


class Cr9Tier2GatingTest(unittest.TestCase):
    def test_tier2_planet_full_only(self):
        row = _planet_row(pl_ratdor="12.3", pl_ratdorlim="-1", pl_eqt="255", pl_projobliq="5.0",
                          pl_orbtper="2458000.0", disc_year="2009", disc_facility="Keck",
                          pl_ntranspec="3", pl_pubdate="2020-01")
        core = eb._planet_record(row, "core")
        full = eb._planet_record(row, "full")
        for k in ("transit_geometry", "environment", "obliquity", "ephemeris", "discovery", "record"):
            self.assertNotIn(k, core)
            self.assertIn(k, full)
        self.assertEqual(full["transit_geometry"]["pl_ratdor"], 12.3)
        self.assertEqual(full["transit_geometry"]["pl_ratdorlim"], -1)      # tri-state in Tier-2 too
        self.assertEqual(full["environment"]["pl_eqt"], 255.0)
        self.assertEqual(full["discovery"]["disc_year"], 2009)
        self.assertEqual(full["record"]["pl_ntranspec"], 3)

    def test_tier2_host_full_only(self):
        host_row = _planet_row(st_rotp="25.0", st_rotplim="0", st_nrvc="120", sy_snum="3",
                               sy_mnum="0", sy_pmra="261.9", sy_pmraerr1="0.05", st_radv=None)
        core = eb._host_record(None, [_planet_row()], None, "core")
        full = eb._host_record(None, [host_row], None, "full")
        for k in ("stellar_extra", "coverage_counts", "system", "kinematics"):
            self.assertNotIn(k, core)
            self.assertIn(k, full)
        self.assertEqual(full["stellar_extra"]["st_rotp"], 25.0)
        self.assertEqual(full["system"]["sy_snum"], 3)
        self.assertEqual(full["kinematics"]["sy_pmra"], 261.9)
        self.assertIsNone(full["kinematics"]["st_radv"])       # patchy Gaia coverage → null


class Cr9Behavior2Test(unittest.TestCase):
    def _simbad(self, name):
        t = {
            "HD 1": {"main_id": "HD 1", "sp_type": "G2 V",
                     "designations": {"HD": "HD 1", "HIP": "HIP 1", "MAIN_ID": "HD 1"}},
            "GJ 667 C": {"main_id": "HD 156384C", "sp_type": "M1.5 V",
                         "designations": {"HD": "HD 156384", "GJ": "GJ 667 C", "MAIN_ID": "HD 156384C"}},
        }
        return t.get(name, {"error": f"No results found for '{name}'"})

    def test_hostname_fallback_recovers_null_hd_host(self):
        # GJ 667 C's planets live under hostname='GJ 667 C' with no hd/hip on the ps row.
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            out = []
            if "hd_name IN" in where and "'HD 1'" in where:
                out += [_planet_row(pl_name="HD 1 b", hostname="HD 1", hd_name="HD 1", hip_name="HIP 1")]
            if "hostname IN" in where and "'GJ 667 C'" in where:
                out += [_planet_row(pl_name="GJ 667 C b", hostname="GJ 667 C", hd_name=None, hip_name=None),
                        _planet_row(pl_name="GJ 667 C e", hostname="GJ 667 C", hd_name=None,
                                    hip_name=None, pl_controv_flag="1")]
            return out
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec (offline test)"}), \
             mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(hosts=["HD 1", "GJ 667 C"])
        cov = out["coverage"]
        matched = {r["input"]: r["matched_on"] for r in cov["resolution"]}
        self.assertEqual(cov["returned_host_count"], 2)
        self.assertEqual(cov["zero_planet"], [])
        self.assertEqual(matched["HD 1"], "hd_name")           # CR-8 catalog path, unchanged
        self.assertEqual(matched["GJ 667 C"], "hostname")      # the false-drop fix
        gj = next(h for h in out["hosts"] if h["input"] == "GJ 667 C")
        self.assertEqual([p["name"] for p in gj["planets"]], ["GJ 667 C b", "GJ 667 C e"])
        self.assertEqual(gj["num_planets"], 2)                 # no cross-arm double-count
        self.assertEqual(
            next(p for p in gj["planets"] if p["name"] == "GJ 667 C e")["disposition"]["pl_controv_flag"], 1)

    def test_catalog_host_not_re_pulled_by_hostname(self):
        # a catalog-matched host must SKIP phase 2 — the hostname 'HD 1 c' row must never appear
        def fake_query(table, where, order_by=None, timeout=60, top=None, select="*"):
            if "hd_name IN" in where and "'HD 1'" in where:
                return [_planet_row(pl_name="HD 1 b", hd_name="HD 1", hip_name="HIP 1")]
            if "hostname IN" in where:
                return [_planet_row(pl_name="HD 1 c", hostname="HD 1")]   # appears iff phase 2 wrongly ran
            return []
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec (offline test)"}), \
             mock.patch.object(eb, "_query_tap", side_effect=fake_query):
            out = eb.compute_exoplanet_batch(hosts=["HD 1"])
        self.assertEqual([p["name"] for p in out["hosts"][0]["planets"]], ["HD 1 b"])


class Cr9CompositeTest(unittest.TestCase):
    COMP = {"pl_name": "HD 1 b", "pl_angsep": "0.05", "pl_angseplim": "0", "pl_tsm": "120",
            "pl_esm": "5.0", "pl_nobs_jwst_tran": "3", "pl_nobs_jwst_e": None,
            "pl_nobs_jwst_pc": None, "pl_nobs_jwst_di": None}

    def _tap(self, table, where, order_by=None, timeout=60, top=None, select="*"):
        if table == "pscomppars":
            return [self.COMP]
        if table != "ps":                                    # CR-10.1 survey tables: no rows here
            return []
        return [_planet_row(hostname="HD 1", pl_name="HD 1 b")]

    def test_composite_merged_full_only(self):
        with mock.patch.object(eb, "_query_tap", side_effect=self._tap), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec"}):
            full = eb.compute_exoplanet_batch(filters={"pl_rade_min": 1}, field_scope="full")
        c = full["hosts"][0]["planets"][0]["composite"]
        self.assertEqual(c["source"], "composite")
        self.assertEqual(c["pl_angsep"], 0.05)
        self.assertEqual(c["pl_tsm"], 120.0)
        self.assertEqual(c["pl_angseplim"], 0)              # limit is a tri-state int
        self.assertEqual(c["pl_nobs_jwst_tran"], 3)         # counts are ints
        self.assertIsNone(c["pl_nobs_jwst_e"])              # patchy → null

    def test_no_composite_in_core(self):
        calls = []
        def tap(table, *a, **k):
            calls.append(table)
            if table != "ps":                                # CR-10.1 survey tables: no rows here
                return []
            return [_planet_row(hostname="HD 1", pl_name="HD 1 b")]
        with mock.patch.object(eb, "_query_tap", side_effect=tap):
            core = eb.compute_exoplanet_batch(filters={"pl_rade_min": 1}, field_scope="core")
        self.assertNotIn("composite", core["hosts"][0]["planets"][0])
        self.assertNotIn("pscomppars", calls)               # composite never queried in core

    def test_composite_failure_degrades_best_effort(self):
        def tap(table, *a, **k):
            if table == "pscomppars":
                raise ConnectionError("boom")
            if table != "ps":                                # CR-10.1 survey tables: no rows here
                return []
            return [_planet_row(hostname="HD 1", pl_name="HD 1 b")]
        with mock.patch.object(eb, "_query_tap", side_effect=tap), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec"}):
            r = eb.compute_exoplanet_batch(filters={"pl_rade_min": 1}, field_scope="full")
        self.assertNotIn("error", r)                        # ps pull survives
        self.assertIsNone(r["hosts"][0]["planets"][0]["composite"])
        self.assertIn("composite_error", r["coverage"])


class Cr9OecEnrichTest(unittest.TestCase):
    SYSTEM = {"tag": "system", "names": ["GJ 667 C"], "children": [
        {"tag": "star", "names": ["GJ 667 C"], "children": [
            {"tag": "planet", "names": ["GJ 667 C c"], "fields": {
                "list": [{"value": "Confirmed planets"}, {"value": "Planets in binary systems, S-type"}],
                "discoveryyear": {"value": "2011"}}}]}]}

    def _tap(self, table, where, order_by=None, timeout=60, top=None, select="*"):
        if table in ("pscomppars", "toi", "cumulative", "k2pandc"):
            return []                                        # composite + CR-10.1 survey tables: no rows
        return [_planet_row(hostname="GJ 667 C", pl_name="GJ 667 C c")]

    def test_oec_list_and_structure(self):
        with mock.patch.object(eb, "_query_tap", side_effect=self._tap), \
             mock.patch.object(eb, "compute_oec",
                               return_value={"query": "x", "matched_name": "GJ 667 C", "system": self.SYSTEM}):
            r = eb.compute_exoplanet_batch(filters={"pl_rade_min": 0.1}, field_scope="full")
        p = r["hosts"][0]["planets"][0]
        self.assertEqual(p["oec"]["authority"], "SECONDARY")
        self.assertIn("Planets in binary systems, S-type", p["oec"]["lists"])
        self.assertEqual(p["oec"]["discoveryyear"], "2011")
        self.assertEqual(r["hosts"][0]["oec_structure"]["matched_name"], "GJ 667 C")

    def test_no_oec_match_nulls(self):
        with mock.patch.object(eb, "_query_tap", side_effect=self._tap), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "miss"}):
            r = eb.compute_exoplanet_batch(filters={"pl_rade_min": 0.1}, field_scope="full")
        self.assertIsNone(r["hosts"][0]["planets"][0]["oec"])
        self.assertIsNone(r["hosts"][0]["oec_structure"])

    def test_gj_gliese_key_bridges(self):
        self.assertEqual(eb._oec_key("GJ 667 C c"), eb._oec_key("Gliese 667 C c"))


class Cr9Behavior3Test(unittest.TestCase):
    # primary PRIM is planetless; OEC groups it with a component COMP that hosts COMP b
    SYSTEM = {"tag": "system", "names": ["PRIM"], "children": [
        {"tag": "star", "names": ["PRIM"], "children": []},
        {"tag": "star", "names": ["COMP"], "children": [
            {"tag": "planet", "names": ["COMP b"], "fields": {}}]}]}

    def _simbad(self, name):
        t = {"PRIM": {"main_id": "PRIM", "designations": {"MAIN_ID": "PRIM", "HD": "HD 9"}},
             "COMP": {"main_id": "COMP", "designations": {"MAIN_ID": "COMP", "HD": "HD 10"}}}
        return t.get(name, {"error": f"no {name}"})

    def _tap(self, table, where, order_by=None, timeout=60, top=None, select="*"):
        if table == "pscomppars":
            return []
        if "'HD 10'" in where or "'COMP'" in where:         # the component query
            return [_planet_row(pl_name="COMP b", hostname="COMP", hd_name="HD 10")]
        return []                                            # PRIM is planetless

    def test_component_planet_surfaced(self):
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec",
                               return_value={"query": "x", "matched_name": "PRIM", "system": self.SYSTEM}), \
             mock.patch.object(eb, "_query_tap", side_effect=self._tap):
            r = eb.compute_exoplanet_batch(hosts=["PRIM"])
        cp = r["coverage"]["component_planets"]
        self.assertEqual(len(cp), 1)
        self.assertEqual(cp[0]["component"], "COMP")
        self.assertEqual(cp[0]["authority"], "SECONDARY")
        self.assertEqual([p["name"] for p in cp[0]["planets"]], ["COMP b"])
        self.assertEqual([z["input"] for z in r["coverage"]["zero_planet"]], ["PRIM"])  # primary planetless

    def test_uncatalogued_multiple_yields_nothing(self):
        # OEC miss (the 26 Dra class) → no component planets, documented limitation
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "miss"}), \
             mock.patch.object(eb, "_query_tap", side_effect=self._tap):
            r = eb.compute_exoplanet_batch(hosts=["PRIM"])
        self.assertEqual(r["coverage"]["component_planets"], [])

    def test_no_double_count_when_component_also_queried(self):
        # querying BOTH PRIM and COMP: COMP b is returned as COMP's own host and must NOT also appear
        # under component_planets (batch-wide exclusion — the double-count fix)
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=self._simbad), \
             mock.patch.object(eb, "compute_oec",
                               return_value={"query": "x", "matched_name": "PRIM", "system": self.SYSTEM}), \
             mock.patch.object(eb, "_query_tap", side_effect=self._tap):
            r = eb.compute_exoplanet_batch(hosts=["PRIM", "COMP"])
        comp_host = next(h for h in r["hosts"] if h["input"] == "COMP")
        self.assertEqual([p["name"] for p in comp_host["planets"]], ["COMP b"])
        cp_names = [p["name"] for b in r["coverage"]["component_planets"] for p in b["planets"]]
        self.assertNotIn("COMP b", cp_names)


class Cr10SurveyDispositionTest(unittest.TestCase):
    """CR-10.1 native transit-survey FP/candidate disposition (toi / cumulative / k2pandc).

    Default ps rows keep hd_name='HD 1' (matches the SIMBAD HD arm) and tic_id='TIC 1'
    (→ _host_tid 1, so TESS TOI rows use tid='1')."""

    SIMBAD = {"main_id": "HOST", "designations": {"MAIN_ID": "HOST", "HD": "HD 1"}}

    def _run(self, ps_rows, toi=None, koi=None, k2=None, field_scope="core", fail=None):
        tables = {"ps": list(ps_rows), "toi": list(toi or []),
                  "cumulative": list(koi or []), "k2pandc": list(k2 or [])}

        def tap(table, where, order_by=None, timeout=60, top=None, select="*"):
            if fail and table == fail:
                raise ConnectionError("survey table down")
            return tables.get(table, [])
        with mock.patch.object(eb, "compute_simbad_lookup", side_effect=lambda n: self.SIMBAD), \
             mock.patch.object(eb, "compute_oec", return_value={"error": "no oec"}), \
             mock.patch.object(eb, "_query_tap", side_effect=tap):
            return eb.compute_exoplanet_batch(hosts=["HOST"], field_scope=field_scope)

    def _planet(self, out, name):
        return next(p for p in out["hosts"][0]["planets"] if p["name"] == name)

    def test_clean_tess_fp_bind(self):
        # validation #1 — a confirmed ps planet whose period clean-binds an FP TOI → disposition_code FP.
        ps = [_planet_row(pl_name="HOST b", hostname="HOST", pl_orbper="1.7727")]
        toi = [{"tid": "1", "toi": "1836.02", "tfopwg_disp": "FP", "pl_orbper": "1.77274710"}]
        sd = self._planet(self._run(ps, toi=toi), "HOST b")["survey_disposition"]
        self.assertEqual(sd["source_catalog"], "toi")
        self.assertEqual(sd["disposition_code"], "FP")
        self.assertEqual(sd["disposition_text"], "False Positive")
        self.assertEqual(sd["catalog_id"], "TOI 1836.02")
        self.assertEqual(sd["match_status"], "matched")

    def test_kepler_name_join_confirmed(self):
        # validation #2
        ps = [_planet_row(pl_name="Kepler-10 b", hostname="Kepler-10")]
        koi = [{"kepler_name": "Kepler-10 b", "koi_disposition": "CONFIRMED",
                "kepoi_name": "K00072.01", "koi_period": "0.837", "kepid": "11904151"}]
        sd = self._planet(self._run(ps, koi=koi), "Kepler-10 b")["survey_disposition"]
        self.assertEqual(sd["source_catalog"], "koi")
        self.assertEqual(sd["disposition_code"], "CONFIRMED")
        self.assertEqual(sd["catalog_id"], "K00072.01")
        self.assertEqual(sd["match_status"], "matched")

    def test_k2_name_join_alias(self):
        # a ps name that matches the k2pandc k2_name alias (not pl_name)
        ps = [_planet_row(pl_name="K2-40 b", hostname="WASP-75")]
        k2 = [{"pl_name": "WASP-75 b", "k2_name": "K2-40 b", "disposition": "CONFIRMED",
               "epic_candname": "EPIC 206154641.01", "epic_hostname": "EPIC 206154641", "pl_orbper": "2.484"}]
        sd = self._planet(self._run(ps, k2=k2), "K2-40 b")["survey_disposition"]
        self.assertEqual(sd["source_catalog"], "k2pandc")
        self.assertEqual(sd["disposition_code"], "CONFIRMED")
        self.assertEqual(sd["catalog_id"], "EPIC 206154641.01")

    def test_refuted_passthrough(self):
        ps = [_planet_row(pl_name="X b", hostname="X")]
        k2 = [{"pl_name": "X b", "k2_name": None, "disposition": "REFUTED",
               "epic_candname": "EPIC 1.01", "epic_hostname": "EPIC 1", "pl_orbper": "3.0"}]
        self.assertEqual(self._planet(self._run(ps, k2=k2), "X b")["survey_disposition"]["disposition_code"],
                         "REFUTED")

    def test_rv_only_present_but_null_no_note(self):
        # validations #3/#4 — RV-only planet (no survey entry) → present-but-null, no note.
        ps = [_planet_row(pl_name="HD 69830 b", hostname="HD 69830")]
        out = self._run(ps)
        p = self._planet(out, "HD 69830 b")
        self.assertIn("survey_disposition", p)               # present, never omitted
        self.assertEqual(p["survey_disposition"], eb._survey_null())
        self.assertIsNone(p["survey_disposition"]["match_status"])
        self.assertIsNone(p["survey_disposition"]["match_note"])

    def test_ambiguous_multiple_tois(self):
        ps = [_planet_row(pl_name="A b", hostname="A", pl_orbper="5.0")]
        toi = [{"tid": "1", "toi": "9.01", "tfopwg_disp": "PC", "pl_orbper": "5.02"},
               {"tid": "1", "toi": "9.02", "tfopwg_disp": "FP", "pl_orbper": "4.98"}]
        sd = self._planet(self._run(ps, toi=toi), "A b")["survey_disposition"]
        self.assertEqual(sd["match_status"], "ambiguous")
        self.assertIsNone(sd["disposition_code"])
        self.assertIn("no unique bind", sd["match_note"])

    def test_period_tolerance_boundary(self):
        ps = [_planet_row(pl_name="B b", hostname="B", pl_orbper="10.0")]
        far = [{"tid": "1", "toi": "1.01", "tfopwg_disp": "PC", "pl_orbper": "10.5"}]    # 5% off → no bind
        near = [{"tid": "1", "toi": "1.01", "tfopwg_disp": "PC", "pl_orbper": "10.1"}]   # 1% off → bind
        self.assertIsNone(self._planet(self._run(ps, toi=far), "B b")["survey_disposition"]["match_status"])
        self.assertEqual(self._planet(self._run(ps, toi=near), "B b")["survey_disposition"]["match_status"],
                         "matched")

    def test_multi_catalog_precedence_koi_wins(self):
        # a planet present in BOTH koi and toi → Kepler name-join wins (koi > k2 > toi).
        ps = [_planet_row(pl_name="Kepler-X b", hostname="Kepler-X", pl_orbper="4.0")]
        koi = [{"kepler_name": "Kepler-X b", "koi_disposition": "CONFIRMED", "kepoi_name": "K1.01",
                "koi_period": "4.0", "kepid": "99"}]
        toi = [{"tid": "1", "toi": "2.01", "tfopwg_disp": "FP", "pl_orbper": "4.0"}]
        self.assertEqual(self._planet(self._run(ps, koi=koi, toi=toi),
                                      "Kepler-X b")["survey_disposition"]["source_catalog"], "koi")

    def test_unbound_tess_sibling_surfaced_host_level(self):
        # a confirmed planet binds its own TOI; a sibling FP TOI on the same TIC → host survey_siblings.
        ps = [_planet_row(pl_name="C b", hostname="C", pl_orbper="6.078")]
        toi = [{"tid": "1", "toi": "2084.01", "tfopwg_disp": "CP", "pl_orbper": "6.078"},
               {"tid": "1", "toi": "2084.02", "tfopwg_disp": "FP", "pl_orbper": "8.149"}]
        out = self._run(ps, toi=toi)
        self.assertEqual(self._planet(out, "C b")["survey_disposition"]["disposition_code"], "CP")
        sibs = out["hosts"][0]["survey_siblings"]
        self.assertEqual([s["catalog_id"] for s in sibs], ["TOI 2084.02"])
        self.assertEqual(sibs[0]["disposition_code"], "FP")

    def test_kepler_sibling_fp_via_pivot(self):
        # host has a confirmed Kepler planet + a separate FP KOI (no kepler_name) → surfaced via kepid pivot.
        ps = [_planet_row(pl_name="Kepler-Z b", hostname="Kepler-Z")]
        koi = [{"kepler_name": "Kepler-Z b", "koi_disposition": "CONFIRMED", "kepoi_name": "K5.01",
                "koi_period": "10.0", "kepid": "777"},
               {"kepler_name": None, "koi_disposition": "FALSE POSITIVE", "kepoi_name": "K5.02",
                "koi_period": "3.0", "kepid": "777"}]
        out = self._run(ps, koi=koi)
        self.assertEqual(self._planet(out, "Kepler-Z b")["survey_disposition"]["disposition_code"],
                         "CONFIRMED")
        sibs = {s["catalog_id"]: s for s in out["hosts"][0]["survey_siblings"]}
        self.assertIn("K5.02", sibs)
        self.assertEqual(sibs["K5.02"]["disposition_code"], "FALSE POSITIVE")

    def test_blank_tfopwg_disp_is_null_code(self):
        ps = [_planet_row(pl_name="D b", hostname="D", pl_orbper="2.0")]
        toi = [{"tid": "1", "toi": "3.01", "tfopwg_disp": "", "pl_orbper": "2.0"}]
        sd = self._planet(self._run(ps, toi=toi), "D b")["survey_disposition"]
        self.assertEqual(sd["match_status"], "matched")
        self.assertIsNone(sd["disposition_code"])            # blank → null code, not ""

    def test_best_effort_degradation(self):
        # a survey-table failure degrades that arm to null + a coverage note; the ps pull is intact.
        ps = [_planet_row(pl_name="E b", hostname="E", pl_orbper="1.7727")]
        toi = [{"tid": "1", "toi": "9.01", "tfopwg_disp": "FP", "pl_orbper": "1.7727"}]
        out = self._run(ps, toi=toi, fail="toi")
        self.assertNotIn("error", out)                       # primary ps pull survives
        self.assertIsNone(self._planet(out, "E b")["survey_disposition"]["match_status"])
        self.assertIn("toi", out["coverage"]["survey_disposition"]["errors"])

    def test_coverage_summary_counts(self):
        ps = [_planet_row(pl_name="F b", hostname="F", pl_orbper="1.7727")]
        toi = [{"tid": "1", "toi": "1.01", "tfopwg_disp": "FP", "pl_orbper": "1.7727"}]
        s = self._run(ps, toi=toi)["coverage"]["survey_disposition"]
        self.assertEqual(s["matched"], 1)
        self.assertEqual(s["ambiguous"], 0)

    def test_present_in_full_scope_too(self):
        ps = [_planet_row(pl_name="HOST b", hostname="HOST", pl_orbper="1.7727")]
        toi = [{"tid": "1", "toi": "1.01", "tfopwg_disp": "FP", "pl_orbper": "1.7727"}]
        out = self._run(ps, toi=toi, field_scope="full")
        self.assertEqual(self._planet(out, "HOST b")["survey_disposition"]["disposition_code"], "FP")

    def test_mode_b_present_but_null(self):
        def tap(table, where, order_by=None, timeout=60, top=None, select="*"):
            return [_planet_row(hostname="G", pl_name="G b", tic_id=None)] if table == "ps" else []
        with mock.patch.object(eb, "_query_tap", side_effect=tap):
            out = eb.compute_exoplanet_batch(filters={"pl_rade_min": 1})
        p = out["hosts"][0]["planets"][0]
        self.assertIn("survey_disposition", p)
        self.assertEqual(p["survey_disposition"], eb._survey_null())


if __name__ == "__main__":
    unittest.main()
