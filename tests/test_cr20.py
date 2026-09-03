"""CR-20 — multiplicity verdict honesty (additive tri-state multiplicity_class/bound_multiple) +
astrometric-backbone completeness (persist Gaia PM into gcns_stars).

Offline. The Component-1 classifier is pure and tested directly; the multiplicity / dossier paths are
exercised by patching ``compute_simbad_lookup`` / ``binary_orbit`` / ``gcns_bound_companions`` (the
CR-18 pattern). The Component-2 tests (gcns_stars schema/migration + PM backfill, seeding a minimal
fixture into a tmp DB and mocking ``_gcns_fetch``) are added alongside the C2 build. Live anchors
(ε Eri, StKM 1-79) are re-gated by WB on the sister venv.
"""
import pathlib
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.binary as binary
import core.report as report
import core.databases as databases


# ── Component 1 — the pure classifier + its two helpers ─────────────────────────────────────────────
class Cr20ClassifierTest(unittest.TestCase):
    """binary.classify_multiplicity — the additive tri-state truth table (WB MSG 216/219 contract)."""

    def test_single_star_present_but_null(self):
        self.assertEqual(binary.classify_multiplicity(
            False, has_fitted_orbit=False, has_binary_otype=False, gcns_comps=[]), (None, None))

    def test_gcns_bound_is_bound(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": True}]), ("bound", True))

    def test_fitted_orbit_is_bound(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=True, has_binary_otype=False, gcns_comps=[]), ("bound", True))

    def test_bound_otype_is_bound(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=True, gcns_comps=[]), ("bound", True))

    def test_gcns_all_unbound_is_optical(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": False}]), ("optical", False))

    def test_undetermined_is_unknown(self):
        # is_multiple but no GCNS pair, no orbit, no bound otype (a bare visual/wds entry).
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False, gcns_comps=[]), ("unknown", None))

    def test_mixed_true_none_is_bound(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": True}, {"bound": None}]), ("bound", True))

    def test_mixed_false_none_is_unknown(self):
        # not ALL bound is False → not a clean optical determination → conservative unknown.
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": False}, {"bound": None}]), ("unknown", None))

    def test_bound_wins_over_optical(self):
        # a bound pair AND an unbound pair → bound (any affirmative signal wins; ordering).
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": True}, {"bound": False}]), ("bound", True))

    def test_close_binary_hint_blocks_optical(self):
        # WB MSG 222: a hint at the optical branch → unknown (possible unresolved bound close companion).
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": False}], has_close_binary_hint=True), ("unknown", None))

    def test_no_hint_stays_optical(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=False, has_binary_otype=False,
            gcns_comps=[{"bound": False}], has_close_binary_hint=False), ("optical", False))

    def test_hint_does_not_block_a_real_bound_signal(self):
        self.assertEqual(binary.classify_multiplicity(
            True, has_fitted_orbit=True, has_binary_otype=False,
            gcns_comps=[{"bound": False}], has_close_binary_hint=True), ("bound", True))


class Cr20IsBoundOtypeTest(unittest.TestCase):
    """binary.is_bound_otype — the NARROW confirmed-binary set (Guardrail 1 + WB MSG 219 `**` drop)."""

    def test_confirmed_binaries_true(self):
        for ot in ("SB*", "EB*", "Al*", "bL*", "WU*"):
            self.assertTrue(binary.is_bound_otype(ot), ot)

    def test_variables_candidates_planet_eclipse_and_bare_double_false(self):
        # RS*/El*/BY* variables, ?-candidates, EP* (planet-eclipse), and bare ** all EXCLUDED.
        for ot in ("RS*", "El*", "BY*", "SB?", "EB?", "**?", "EP*", "**", "", None, "Star"):
            self.assertFalse(binary.is_bound_otype(ot), ot)


class Cr20IsOrbitSolutionTest(unittest.TestCase):
    """binary.is_orbit_solution — fitted stellar orbit (Guardrail 2 + planet-class exclusion)."""

    def test_fitted_orbits_true(self):
        for src in ("sb9", "orb6", "gaia-nss:two_body_orbit", "gaia-nss:acceleration"):
            self.assertTrue(binary.is_orbit_solution({"source": src}), src)

    def test_wds_catalog_double_false(self):
        self.assertFalse(binary.is_orbit_solution({"source": "wds"}))

    def test_planet_class_orbit_excluded(self):
        # GJ 876-like: a planetary Gaia-NSS "orbit" is NOT a stellar-multiplicity bound signal.
        self.assertFalse(binary.is_orbit_solution(
            {"source": "gaia-nss:two_body_orbit", "companion": {"class": "planet"}}))

    def test_stellar_class_orbit_included(self):
        self.assertTrue(binary.is_orbit_solution({"source": "sb9", "companion": {"class": "stellar"}}))

    def test_substellar_class_orbit_included(self):
        # a brown-dwarf (substellar) companion orbit still counts (WB MSG 219: stellar/substellar). The
        # class literal MUST match production (classify_companion emits "brown-dwarf", hyphen).
        self.assertTrue(binary.is_orbit_solution(
            {"source": "gaia-nss:two_body_orbit", "companion": {"class": "brown-dwarf"}}))

    def test_none_and_empty_false(self):
        self.assertFalse(binary.is_orbit_solution(None))
        self.assertFalse(binary.is_orbit_solution({}))


class Cr20HintOtypeTest(unittest.TestCase):
    """binary.is_close_binary_hint_otype — the WB MSG 222 close-binary hint set {SB?,EB?,RS*,El*}."""

    def test_hints_true(self):
        for ot in ("SB?", "EB?", "RS*", "El*"):
            self.assertTrue(binary.is_close_binary_hint_otype(ot), ot)

    def test_non_hints_false(self):
        # SB* (already bound), the wide ** doubles, BY*, and None are NOT close-binary hints.
        for ot in ("SB*", "EB*", "**", "**?", "BY*", "", None):
            self.assertFalse(binary.is_close_binary_hint_otype(ot), ot)


# ── Component 1 — the `multiplicity` subcommand path (binary.multiplicity_summary) ──────────────────
# Real 19-digit Gaia source_ids — gaia_source_id_from_designations' _GAIA_ID_RE needs >=5 digits, and a
# gcns pair is emitted only when the queried star's id is INCIDENT on it, so the ids must match.
_G1 = 4722111590409480064
_G2 = 4722135642226902656


def _sl(otype=None, is_multiple=False, basis=None, gaia=f"Gaia DR3 {_G1}"):
    mult = None
    if otype is not None or is_multiple:
        mult = {"is_multiple": is_multiple, "sb_flag": False, "basis": basis, "otype": otype}
    return {"main_id": "TEST", "multiplicity": mult, "designations": {"Gaia EDR3": gaia}}


def _bo(solutions=None, routes=("nss", "sb9", "wds")):
    return {"solutions": list(solutions or []), "route_tried": list(routes)}


def _gsys(n, bound, proj=500.0):
    # A 2-component system with one pair incident on _G1 (the queried star), bound-flagged per `bound`.
    return {"system": {"n_components": n,
                       "pairs": [{"source_id1": _G1, "source_id2": _G2, "bound": bound,
                                  "proj_sep_au": proj, "separation_arcsec": 5.0}],
                       "members": [{"gaia_source_id": _G1, "star_name": "A"},
                                   {"gaia_source_id": _G2, "star_name": "B"}]}}


class Cr20MultiplicitySummaryClassTest(unittest.TestCase):
    """multiplicity_summary attaches multiplicity_class/bound_multiple; the five anchors + planet-only."""

    def _run(self, sl, bo, gsys):
        with mock.patch("core.databases.compute_simbad_lookup", return_value=sl), \
             mock.patch("core.binary.binary_orbit", return_value=bo), \
             mock.patch("core.databases.compute_gcns_system", return_value=gsys):
            return binary.multiplicity_summary(star="TEST")

    def test_eps_eri_unknown(self):
        # bare wds visual, no GCNS pair, BY* → unknown.
        out = self._run(_sl(otype="BY*", is_multiple=True, basis="visual"),
                        _bo([{"source": "wds", "companion": None}]),
                        {"error": "not resolved"})
        self.assertTrue(out["is_multiple"])
        self.assertEqual(out["multiplicity_class"], "unknown")
        self.assertIsNone(out["bound_multiple"])

    def test_stkm_optical(self):
        # GCNS 2-component, the pair bound=0, no orbit, no bound otype → optical.
        out = self._run(_sl(), _bo([]), _gsys(2, bound=False))
        self.assertTrue(out["is_multiple"])
        self.assertEqual(out["multiplicity_class"], "optical")
        self.assertIs(out["bound_multiple"], False)

    def test_rs_cvn_hint_plus_optical_gcns_is_unknown(self):
        # WB MSG 222: an RS* close-binary hint + a GCNS all-bound=0 pair → unknown (NOT optical).
        out = self._run(_sl(otype="RS*", is_multiple=True), _bo([]), _gsys(2, bound=False))
        self.assertTrue(out["is_multiple"])
        self.assertEqual(out["multiplicity_class"], "unknown")
        self.assertIsNone(out["bound_multiple"])

    def test_wide_double_plus_optical_gcns_stays_optical(self):
        # the wide `**` double does NOT block optical (same channel as the GCNS optical pair).
        out = self._run(_sl(otype="**", is_multiple=True), _bo([]), _gsys(2, bound=False))
        self.assertEqual(out["multiplicity_class"], "optical")
        self.assertIs(out["bound_multiple"], False)

    def test_zet_ret_bound_via_gcns(self):
        out = self._run(_sl(), _bo([]), _gsys(2, bound=True, proj=3721.8))
        self.assertEqual(out["multiplicity_class"], "bound")
        self.assertIs(out["bound_multiple"], True)

    def test_alpha_cen_bound_via_orbit_empty_gcns(self):
        # a fitted SB9 orbit, GCNS unresolved (Gaia-missing primaries) → bound via the orbit.
        out = self._run(_sl(),
                        _bo([{"source": "sb9", "companion": {"class": "stellar", "method": "SB2"}}]),
                        {"error": "not resolved"})
        self.assertEqual(out["multiplicity_class"], "bound")
        self.assertIs(out["bound_multiple"], True)

    def test_single_star_present_but_null(self):
        out = self._run(_sl(), _bo([]), {"error": "not resolved"})
        self.assertFalse(out["is_multiple"])
        self.assertIn("multiplicity_class", out)
        self.assertIn("bound_multiple", out)
        self.assertIsNone(out["multiplicity_class"])
        self.assertIsNone(out["bound_multiple"])

    def test_planet_only_nss_not_bound(self):
        # GJ 876-like: a planetary Gaia-NSS "orbit" makes is_multiple true but must NOT read bound.
        out = self._run(_sl(),
                        _bo([{"source": "gaia-nss:two_body_orbit", "companion": {"class": "planet"}}]),
                        {"error": "not resolved"})
        self.assertTrue(out["is_multiple"])
        self.assertNotEqual(out["multiplicity_class"], "bound")
        self.assertIsNot(out["bound_multiple"], True)

    def test_additive_only_exact_two_new_keys(self):
        # On a clean single star (no orbit/gcns/note), the output is exactly the pre-CR-20 key set
        # PLUS the two new keys — nothing else added, nothing dropped.
        out = self._run(_sl(), _bo([]), {"error": "not resolved"})
        self.assertEqual(set(out), {"star", "is_multiple", "n_components", "components", "sb_flag",
                                    "sources", "multiplicity_class", "bound_multiple"})


# ── Component 1 — the dossier path (report._augment_gcns_multiplicity choke point) ──────────────────
class Cr20DossierClassTest(unittest.TestCase):
    """report._augment_gcns_multiplicity sets the same class; present-but-null on every return; Sol."""

    def _augment(self, data, comps, gcns_n, has_fitted_orbit=False):
        with mock.patch("core.binary.gcns_bound_companions", return_value=(gcns_n, comps)):
            return report._augment_gcns_multiplicity(
                dict(data), {"designations": {"Gaia EDR3": "Gaia DR3 5164707970261890560"}},
                has_fitted_orbit=has_fitted_orbit)

    def test_dossier_unknown(self):
        d = self._augment({"is_multiple": True, "otype": "BY*"}, [], None)
        self.assertEqual(d["multiplicity_class"], "unknown")
        self.assertIsNone(d["bound_multiple"])

    def test_dossier_optical(self):
        d = self._augment({"is_multiple": False, "otype": None},
                          [{"bound": False, "proj_sep_au": 500.0}], 2)
        self.assertTrue(d["is_multiple"])          # co-membership gate sets it (monotonic)
        self.assertEqual(d["multiplicity_class"], "optical")
        self.assertIs(d["bound_multiple"], False)

    def test_dossier_bound_via_gcns(self):
        d = self._augment({"is_multiple": False, "otype": None}, [{"bound": True, "proj_sep_au": 100.0}], 2)
        self.assertEqual(d["multiplicity_class"], "bound")

    def test_dossier_bound_via_orbit(self):
        d = self._augment({"is_multiple": True, "otype": None}, [], None, has_fitted_orbit=True)
        self.assertEqual(d["multiplicity_class"], "bound")

    def test_dossier_bound_via_otype(self):
        d = self._augment({"is_multiple": True, "otype": "SB*"}, [], None)
        self.assertEqual(d["multiplicity_class"], "bound")

    def test_dossier_single_present_but_null(self):
        d = self._augment({"is_multiple": False, "otype": None}, [], None)
        self.assertIsNone(d["multiplicity_class"])
        self.assertIsNone(d["bound_multiple"])

    def test_early_return_no_star_present_but_null(self):
        # _multiplicity_data_star with a falsy star ("") hits the `if not star` early return — a SINGLE
        # star there stays present-but-null (never omitted, Q2).
        data = report._multiplicity_data_star({"multiplicity": {}, "sp_type": None}, "")
        self.assertIn("multiplicity_class", data)
        self.assertIn("bound_multiple", data)
        self.assertIsNone(data["multiplicity_class"])
        self.assertIsNone(data["bound_multiple"])

    def test_early_return_multiple_via_otype_is_classified(self):
        # CP1 fix: a MULTIPLE (here via otype SB*) on the `if not star` early-return path must be
        # CLASSIFIED, not left multiplicity_class=None — the invariant that a multiple always gets a
        # non-null class. No designations → no GCNS network; SB* → bound via the otype.
        data = report._multiplicity_data_star(
            {"multiplicity": {"is_multiple": True, "sb_flag": False,
                              "basis": "spectroscopic", "otype": "SB*"}}, "")
        self.assertTrue(data["is_multiple"])
        self.assertEqual(data["multiplicity_class"], "bound")
        self.assertIs(data["bound_multiple"], True)

    def test_sol_present_but_null(self):
        d = report._multiplicity_data_sol()
        self.assertIsNone(d["multiplicity_class"])
        self.assertIsNone(d["bound_multiple"])


class Cr20CrossPathAgreementTest(unittest.TestCase):
    """The `multiplicity` subcommand and the dossier path agree on the class where is_multiple agrees
    (the GCNS-driven cases), and — the load-bearing CR-20 guarantee — NEITHER ever reads `bound` for a
    planet-only NSS host (the case both draft paths would have overclaimed)."""

    def _summary(self, sl, bo, gsys):
        with mock.patch("core.databases.compute_simbad_lookup", return_value=sl), \
             mock.patch("core.binary.binary_orbit", return_value=bo), \
             mock.patch("core.databases.compute_gcns_system", return_value=gsys):
            return binary.multiplicity_summary(star="TEST")["multiplicity_class"]

    def _dossier(self, sl, bo, gsys):
        # _multiplicity_data_star takes the SIMBAD dict directly; mock binary_orbit + the GCNS reader.
        with mock.patch("core.binary.binary_orbit", return_value=bo), \
             mock.patch("core.databases.compute_gcns_system", return_value=gsys):
            return report._multiplicity_data_star(sl, "TEST")["multiplicity_class"]

    def test_gcns_optical_agrees(self):
        # both paths gate is_multiple on gcns_n>1 and see the same all-bound=0 pair → both optical.
        sl, bo, gsys = _sl(), _bo([]), _gsys(2, bound=False)
        self.assertEqual(self._summary(sl, bo, gsys), "optical")
        self.assertEqual(self._dossier(sl, bo, gsys), "optical")

    def test_gcns_bound_agrees(self):
        sl, bo, gsys = _sl(), _bo([]), _gsys(2, bound=True)
        self.assertEqual(self._summary(sl, bo, gsys), "bound")
        self.assertEqual(self._dossier(sl, bo, gsys), "bound")

    def test_planet_only_never_bound_on_either_path(self):
        # The pre-existing is_multiple divergence (summary counts a planet-NSS component, dossier filters
        # it) means the CLASSES differ (unknown vs single/null) — CR-20 does NOT touch is_multiple — but
        # the guarantee that matters holds on BOTH: a planetary orbit is never a `bound` stellar multiple.
        sl = _sl()
        bo = _bo([{"source": "gaia-nss:two_body_orbit", "companion": {"class": "planet"}}])
        gsys = {"error": "not resolved"}
        self.assertNotEqual(self._summary(sl, bo, gsys), "bound")
        self.assertNotEqual(self._dossier(sl, bo, gsys), "bound")


# ── Component 2 — persist Gaia PM into gcns_stars (schema + migration + targeted backfill) ──────────
class _FakeResult(list):
    """Stand-in for a pyvo TAP result: iterable rows + a query_status attribute (no OVERFLOW)."""
    query_status = "OK"


class Cr20ProperMotionSchemaTest(unittest.TestCase):
    """The 5 PM columns are NOT surfaced to any reader (the byte-identity guard)."""

    def test_pm_columns_not_in_row_cols(self):
        pm = {"pmra", "pmdec", "pmra_error", "pmdec_error", "ruwe"}
        self.assertEqual(pm & set(databases._GCNS_ROW_COLS), set(),
                         "PM columns must NOT be in _GCNS_ROW_COLS — every GCNS reader stays byte-identical")

    def test_row_cols_unchanged_count(self):
        self.assertEqual(len(databases._GCNS_ROW_COLS), 24)


class Cr20ProperMotionBackfillTest(unittest.TestCase):
    """backfill_gcns_proper_motion — a targeted PM-only UPDATE that touches only the 5 PM columns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()
        # a Gaia-resolved main row (source_id set) + a missing_10mas row (NULL source_id).
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, star_name, spectral_type, dist_pc, light_years, "
            "in_gcns, in_simbad, distance_method, gcns_table, system_id, n_components) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_G1, "A", "M0V", 5.0, 16.3, 1, 1, "gcns_bayesian", "main", 7, 2))
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, star_name, in_gcns, distance_method, gcns_table) "
            "VALUES (?,?,?,?,?)",
            (None, "B-missing", 1, "gcns_missing_plx_inversion", "missing_10mas"))
        self.conn.commit()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved

    def _row(self, name):
        return self.conn.execute("SELECT * FROM gcns_stars WHERE star_name=?", (name,)).fetchone()

    def test_backfill_updates_only_pm_columns(self):
        fake = _FakeResult([{"source_id": _G1, "pmra": 100.5, "pmdec": -200.3,
                             "pmra_error": 0.11, "pmdec_error": 0.22, "ruwe": 1.05}])
        with mock.patch("core.databases._gcns_fetch", return_value=fake), \
             mock.patch("core.databases._GCNS_MAIN_MIN_ROWS", 1):
            out = databases.backfill_gcns_proper_motion()
        self.assertEqual(out.get("updated"), 1)
        a = self._row("A")
        self.assertAlmostEqual(a["pmra"], 100.5)
        self.assertAlmostEqual(a["pmdec"], -200.3)
        self.assertAlmostEqual(a["pmra_error"], 0.11)
        self.assertAlmostEqual(a["pmdec_error"], 0.22)
        self.assertAlmostEqual(a["ruwe"], 1.05)
        # every OTHER column on row A is untouched (byte-identical by construction).
        self.assertEqual(a["star_name"], "A")
        self.assertEqual(a["spectral_type"], "M0V")
        self.assertEqual(a["dist_pc"], 5.0)
        self.assertEqual(a["light_years"], 16.3)
        self.assertEqual(a["system_id"], 7)
        self.assertEqual(a["n_components"], 2)
        # the missing_10mas row (NULL source_id) never matches → PM stays NULL (no fabrication).
        b = self._row("B-missing")
        self.assertIsNone(b["pmra"])
        self.assertIsNone(b["pmdec"])
        self.assertIsNone(b["ruwe"])

    def test_backfill_empty_table_errors(self):
        self.conn.execute("DELETE FROM gcns_stars")
        self.conn.commit()
        out = databases.backfill_gcns_proper_motion()
        self.assertIn("error", out)

    def test_backfill_short_pull_aborts_without_write(self):
        # a pull below _GCNS_MAIN_MIN_ROWS (~330k) → validate-before-write abort, NO partial write.
        fake = _FakeResult([{"source_id": _G1, "pmra": 1.0, "pmdec": 2.0,
                             "pmra_error": 0.1, "pmdec_error": 0.1, "ruwe": 1.0}])
        with mock.patch("core.databases._gcns_fetch", return_value=fake):
            out = databases.backfill_gcns_proper_motion()
        self.assertIn("error", out)
        self.assertIsNone(self._row("A")["pmra"])


if __name__ == "__main__":
    unittest.main()
