"""tests/test_cr19.py — CR-19: bound the sync Gaia-archive-TAP calls (FLAME + NSS + binary_masses +
coords) so the mass/identity resolvers fail-fast + retry-once + degrade-with-flag instead of hanging.

Offline: the network is either the deterministic `SPACE_APP_GAIA_FORCE_UNREACHABLE` hook (no socket) or
a fake `astroquery.gaia` module injected into `sys.modules`; the marker-surfacing tests mock the
`catalog.gaia_astrophysical` / `binary.binary_orbit` seams. One live-gated test (SPACE_APP_RUN_LIVE)
asserts the fresh `GaiaClass()` ≡ the shared `Gaia` for a real FLAME query (the byte-identity guard).
"""

import os
import sys
import time
import types
import unittest
from unittest import mock

from core import catalog
from core.shared import _call_with_watchdog, _WatchdogTimeout


# ── fake astroquery.gaia for the bounded sync path ────────────────────────────
class _FakeJob:
    def __init__(self, tbl):
        self._t = tbl

    def get_results(self):
        return self._t


def _fake_gaia_module(tbl=None, sleep=0.0, exc=None):
    """A stand-in `astroquery.gaia` whose GaiaClass().launch_job optionally sleeps (→ watchdog
    timeout) or raises (→ unreachable), else returns `tbl`."""
    mod = types.ModuleType("astroquery.gaia")

    class _G:
        def launch_job(self, q):
            if sleep:
                time.sleep(sleep)
            if exc is not None:
                raise exc
            return _FakeJob(tbl)

    mod.GaiaClass = _G
    mod.Gaia = _G()
    return mod


def _one_row_table(**cols):
    from astropy.table import Table
    return Table({k: [v] for k, v in cols.items()})


class _CatalogStateMixin:
    """Reset the process-global CR-19 state + disable the file cache around each test."""

    def setUp(self):
        self._env = dict(os.environ)
        os.environ["SPACE_APP_CATALOG_CACHE"] = "0"
        os.environ.pop("SPACE_APP_GAIA_TIMEOUT", None)
        os.environ.pop("SPACE_APP_GAIA_FORCE_UNREACHABLE", None)
        catalog.set_gaia_timeout(None)
        catalog.reset_gaia_sync_circuit()

    def tearDown(self):
        catalog.set_gaia_timeout(None)
        catalog.reset_gaia_sync_circuit()
        os.environ.clear()
        os.environ.update(self._env)


# ── 7.1 unit: watchdog ────────────────────────────────────────────────────────
class WatchdogTest(unittest.TestCase):
    def test_slow_call_raises_bounded(self):
        t0 = time.time()
        with self.assertRaises(_WatchdogTimeout):
            _call_with_watchdog(lambda: time.sleep(5), timeout=0.3)
        self.assertLess(time.time() - t0, 1.5)          # returned near the bound, not after 5s

    def test_fast_call_returns_value(self):
        self.assertEqual(_call_with_watchdog(lambda: 42, timeout=1), 42)

    def test_exception_reraised_with_original_type(self):
        def _boom():
            raise ValueError("original-type")
        with self.assertRaises(ValueError) as cm:
            _call_with_watchdog(_boom, timeout=1)
        self.assertEqual(str(cm.exception), "original-type")


# ── 7.1 unit: bounded retry ───────────────────────────────────────────────────
class BoundedCallTest(_CatalogStateMixin, unittest.TestCase):
    def test_two_attempts_on_repeated_timeout(self):
        calls = {"n": 0}

        def _slow():
            calls["n"] += 1
            time.sleep(5)
        with self.assertRaises(_WatchdogTimeout):
            catalog._bounded_gaia_call(_slow, timeout=0.2, retries=2)
        self.assertEqual(calls["n"], 2)

    def test_two_attempts_on_connection_error_then_reraise(self):
        import requests
        calls = {"n": 0}

        def _fail():
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("down")
        with self.assertRaises(requests.exceptions.ConnectionError):
            catalog._bounded_gaia_call(_fail, timeout=1, retries=2)
        self.assertEqual(calls["n"], 2)

    def test_timeout_then_success_returns(self):
        state = {"n": 0}

        def _flaky():
            state["n"] += 1
            if state["n"] == 1:
                time.sleep(5)
            return "ok"
        self.assertEqual(catalog._bounded_gaia_call(_flaky, timeout=0.2, retries=2), "ok")


# ── 7.1 unit: timeout getter ──────────────────────────────────────────────────
class TimeoutGetterTest(_CatalogStateMixin, unittest.TestCase):
    def test_default_60(self):
        self.assertEqual(catalog._gaia_sync_timeout(), 60.0)

    def test_env_and_override_precedence(self):
        os.environ["SPACE_APP_GAIA_TIMEOUT"] = "10"
        self.assertEqual(catalog._gaia_sync_timeout(), 10.0)
        catalog.set_gaia_timeout(3)                     # CLI override wins over env
        self.assertEqual(catalog._gaia_sync_timeout(), 3.0)

    def test_zero_and_negative_disable(self):
        catalog.set_gaia_timeout(0)
        self.assertIsNone(catalog._gaia_sync_timeout())
        os.environ["SPACE_APP_GAIA_TIMEOUT"] = "-5"
        catalog.set_gaia_timeout(None)
        self.assertIsNone(catalog._gaia_sync_timeout())

    def test_non_numeric_env_falls_back_to_default(self):
        os.environ["SPACE_APP_GAIA_TIMEOUT"] = "abc"
        self.assertEqual(catalog._gaia_sync_timeout(), 60.0)


# ── 7.1 unit: circuit-breaker ─────────────────────────────────────────────────
class CircuitBreakerTest(_CatalogStateMixin, unittest.TestCase):
    def test_trips_on_timeout_only(self):
        catalog._trip_gaia_circuit("unreachable")
        self.assertIsNone(catalog._gaia_circuit_reason())   # unreachable never trips
        catalog._trip_gaia_circuit("timeout")
        self.assertEqual(catalog._gaia_circuit_reason(), "timeout")

    def test_reset_rearms(self):
        catalog._trip_gaia_circuit("timeout")
        catalog.reset_gaia_sync_circuit()
        self.assertIsNone(catalog._gaia_circuit_reason())

    def test_cooldown_auto_rearm(self):
        saved = catalog._GAIA_CIRCUIT_COOLDOWN_S
        catalog._GAIA_CIRCUIT_COOLDOWN_S = 0.05
        try:
            catalog._trip_gaia_circuit("timeout")
            self.assertEqual(catalog._gaia_circuit_reason(), "timeout")
            time.sleep(0.08)
            self.assertIsNone(catalog._gaia_circuit_reason())   # auto re-armed past the cooldown
        finally:
            catalog._GAIA_CIRCUIT_COOLDOWN_S = saved

    def test_open_breaker_short_circuits_but_serves_cache(self):
        # Open the breaker, then a call short-circuits fast without invoking the watchdog.
        catalog._trip_gaia_circuit("timeout")
        with mock.patch.object(catalog, "_bounded_gaia_call",
                               side_effect=AssertionError("watchdog must not run when breaker open")):
            r = catalog.gaia_tap(adql="SELECT 1")
        self.assertEqual(r.get("gaia_bound_reason"), "timeout")


# ── 7.2 gaia_tap degrade ──────────────────────────────────────────────────────
class GaiaTapDegradeTest(_CatalogStateMixin, unittest.TestCase):
    def test_force_unreachable_hook(self):
        os.environ["SPACE_APP_GAIA_FORCE_UNREACHABLE"] = "1"
        with mock.patch.object(catalog, "_warn") as warn:
            r = catalog.gaia_tap(adql="SELECT 1")
        self.assertEqual(r.get("gaia_bound_reason"), "unreachable")
        self.assertIn("error", r)
        self.assertIsNone(catalog._gaia_circuit_reason())   # unreachable does NOT trip the breaker
        warn.assert_called_once()

    def test_timeout_degrades_and_trips_breaker(self):
        catalog.set_gaia_timeout(0.2)
        with mock.patch.dict(sys.modules, {"astroquery.gaia": _fake_gaia_module(sleep=5)}):
            with mock.patch.object(catalog, "_warn"):
                r = catalog.gaia_tap(adql="SELECT 1")
        self.assertEqual(r.get("gaia_bound_reason"), "timeout")
        self.assertEqual(catalog._gaia_circuit_reason(), "timeout")   # timeout trips the breaker

    def test_success_carries_no_marker(self):
        tbl = _one_row_table(source_id=123, mass_flame=0.8)
        with mock.patch.dict(sys.modules, {"astroquery.gaia": _fake_gaia_module(tbl=tbl)}):
            r = catalog.gaia_tap(adql="SELECT 1")
        self.assertNotIn("gaia_bound_reason", r)
        self.assertNotIn("error", r)
        self.assertEqual(r["count"], 1)

    def test_async_and_disabled_take_legacy_path(self):
        # bound disabled (0) → the bounded wrapper must NOT run (legacy path). Spy on it.
        catalog.set_gaia_timeout(0)
        tbl = _one_row_table(source_id=1)
        legacy = _fake_gaia_module(tbl=tbl)
        with mock.patch.dict(sys.modules, {"astroquery.gaia": legacy}):
            with mock.patch.object(catalog, "_bounded_gaia_call",
                                   side_effect=AssertionError("bounded path must not run when disabled")):
                r = catalog.gaia_tap(adql="SELECT 1")
        self.assertEqual(r["count"], 1)


# ── 7.2 marker surfacing: flame_status (mass path) ────────────────────────────
class FlameStatusSurfacingTest(_CatalogStateMixin, unittest.TestCase):
    def test_dossier_mass_block_flags_timeout(self):
        from core import report
        simbad = {"main_id": "* test", "sp_type": "K2V", "designations": {"Gaia EDR3": "123"}}
        # _gaia_astro returns the degrade error dict carrying gaia_bound_reason.
        with mock.patch.object(report, "_gaia_astro",
                               return_value={"error": "timed out", "gaia_bound_reason": "timeout"}):
            block = report._resolve_star_mass_block(simbad, 0.7, None, None, True, {})
        self.assertEqual(block["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(block["flame_status"], "timeout")

    def test_dossier_mass_block_success_has_no_key(self):
        from core import report
        simbad = {"main_id": "* test", "sp_type": "K2V", "designations": {"Gaia EDR3": "123"}}
        ok = {"parameters": {"mass_flame": 0.81}}
        with mock.patch.object(report, "_gaia_astro", return_value=ok):
            block = report._resolve_star_mass_block(simbad, 0.7, None, None, True, {})
        self.assertEqual(block["mass_provenance"], "gaia_flame")
        self.assertNotIn("flame_status", block)

    def test_dossier_mass_block_genuine_miss_has_no_key(self):
        from core import report
        simbad = {"main_id": "* test", "sp_type": "K2V", "designations": {"Gaia EDR3": "123"}}
        miss = {"parameters": None, "note": "no astrophysical_parameters row"}
        with mock.patch.object(report, "_gaia_astro", return_value=miss):
            block = report._resolve_star_mass_block(simbad, 0.7, None, None, True, {})
        self.assertEqual(block["mass_provenance"], "ms_luminosity_inversion")
        self.assertNotIn("flame_status", block)

    def test_flame_mass_for_returns_marker_tuple(self):
        from core import databases
        sl = {"designations": {"Gaia EDR3": "123"}}
        with mock.patch("core.binary.gaia_source_id_from_designations", return_value="123"), \
             mock.patch("core.catalog.gaia_astrophysical",
                        return_value={"error": "x", "gaia_bound_reason": "unreachable"}):
            m, status = databases._flame_mass_for(sl)
        self.assertIsNone(m)
        self.assertEqual(status, "unreachable")

    def test_resolve_mass_pure_helper_untouched(self):
        from core import stellar_mass
        block = stellar_mass.resolve_mass(0.7, sp_type="K2V", flame_mass=0.81)
        self.assertEqual(block["mass_provenance"], "gaia_flame")
        self.assertNotIn("flame_status", block)          # the pure resolver never sets it


# ── 7.2 marker surfacing: gaia_status (binary path) ───────────────────────────
class GaiaStatusSurfacingTest(_CatalogStateMixin, unittest.TestCase):
    def test_binary_orbit_sets_gaia_status_on_bounded_nss(self):
        from core import binary
        ident = {"main_id": "* x", "ra": 10.0, "dec": 20.0, "sp_type": "G2V",
                 "parallax_mas": 100.0, "gaia_source_id": "999"}
        with mock.patch.object(binary, "_resolve_binary_identity", return_value=(ident, None, None)), \
             mock.patch.object(binary, "_nss_two_body_solutions", return_value=([], None, "timeout")), \
             mock.patch.object(binary, "_sb9_solutions", return_value=([], None)), \
             mock.patch.object(binary, "_wds_orb6_solutions", return_value=[]):
            r = binary.binary_orbit(star="X")
        self.assertEqual(r.get("gaia_status"), "timeout")
        self.assertEqual(r["solutions"], [])             # a genuine-looking empty, now flagged as degraded

    def test_binary_orbit_success_has_no_gaia_status(self):
        from core import binary
        ident = {"main_id": "* x", "ra": 10.0, "dec": 20.0, "sp_type": "G2V",
                 "parallax_mas": 100.0, "gaia_source_id": "999"}
        with mock.patch.object(binary, "_resolve_binary_identity", return_value=(ident, None, None)), \
             mock.patch.object(binary, "_nss_two_body_solutions", return_value=([], None, None)), \
             mock.patch.object(binary, "_sb9_solutions", return_value=([], None)), \
             mock.patch.object(binary, "_wds_orb6_solutions", return_value=[]):
            r = binary.binary_orbit(star="X")
        self.assertNotIn("gaia_status", r)

    def test_binary_orbit_identity_fail_carries_marker(self):
        from core import binary
        with mock.patch.object(binary, "_resolve_binary_identity",
                               return_value=(None, "Could not resolve coordinates", "unreachable")):
            r = binary.binary_orbit(star="X")
        self.assertIn("error", r)
        self.assertEqual(r.get("gaia_status"), "unreachable")

    def test_worse_gaia_status_timeout_precedence(self):
        from core import binary
        self.assertEqual(binary._worse_gaia_status("unreachable", "timeout"), "timeout")
        self.assertEqual(binary._worse_gaia_status("unreachable", None), "unreachable")
        self.assertIsNone(binary._worse_gaia_status(None, None))

    def test_multiplicity_summary_propagates_gaia_status(self):
        from core import binary, databases
        bo = {"solutions": [], "route_tried": ["gaia-nss:two_body_orbit"], "gaia_status": "timeout",
              "note": "no orbital solution"}
        with mock.patch.object(databases, "compute_simbad_lookup",
                               return_value={"main_id": "* x", "designations": {"Gaia EDR3": "999"},
                                             "multiplicity": {}}), \
             mock.patch.object(binary, "gcns_bound_companions", return_value=(None, [])), \
             mock.patch.object(binary, "binary_orbit", return_value=bo):
            out = binary.multiplicity_summary(star="X")
        self.assertEqual(out.get("gaia_status"), "timeout")

    def test_multiplicity_data_star_captures_before_branch(self):
        from core import report, binary
        simbad = {"main_id": "* x", "sp_type": "G2V", "multiplicity": {},
                  "designations": {"Gaia EDR3": "999"}}
        bo = {"solutions": [], "gaia_status": "unreachable", "identity": {}}
        with mock.patch.object(binary, "binary_orbit", return_value=bo), \
             mock.patch.object(report, "_augment_gcns_multiplicity", side_effect=lambda d, s: d):
            data = report._multiplicity_data_star(simbad, "X")
        self.assertEqual(data.get("gaia_status"), "unreachable")   # set even on the `not stellar` early return


# ── 7.2 dossier document rendering (the markdown surface WB actually reads) ───
class DossierRenderTest(unittest.TestCase):
    @staticmethod
    def _kv(blocks, label):
        for kind, *rest in blocks:
            if kind == "kv":
                for k, v in rest[0]:
                    if k == label:
                        return v
        return None

    @staticmethod
    def _labels(blocks):
        return [k for kind, *rest in blocks if kind == "kv" for k, v in rest[0]]

    def _regions_d(self, mass):
        return {"stellar": {"teff": 5000, "stellar_mass": 0.75, "stellar_radius": 0.8,
                            "bc_luminosity": 0.3, "luminosity_from_mass": 0.4,
                            "calculated_luminosity": 0.3, "main_seq_lifespan_yr": 2e10},
                "system_regions": {}, "mass": mass, "alt_solvent": [], "ice_lines": [],
                "sunlight_intensity": 1.0, "bond_albedo": 0.3}

    def test_mass_cell_renders_flame_status_on_degrade(self):
        from core import report
        _, blocks = report._blocks_regions(self._regions_d(
            {"mass_provenance": "ms_luminosity_inversion", "flame_status": "timeout"}))
        self.assertIn("⚠ Gaia FLAME timeout", self._kv(blocks, "Stellar mass"))

    def test_mass_cell_no_flame_marker_on_success(self):
        from core import report
        _, blocks = report._blocks_regions(self._regions_d({"mass_provenance": "gaia_flame"}))
        self.assertNotIn("⚠ Gaia FLAME", self._kv(blocks, "Stellar mass"))   # byte-identical on success

    def test_multiplicity_renders_degrade_rows(self):
        from core import report
        _, blocks = report._blocks_multiplicity(
            {"is_multiple": False, "sb_flag": False, "basis": None, "otype": None,
             "multiplicity_basis": None, "gaia_status": "timeout", "flame_status_a": "unreachable"})
        labels = self._labels(blocks)
        self.assertIn("Gaia archive", labels)
        self.assertIn("FLAME mass (A)", labels)

    def test_multiplicity_no_degrade_rows_when_clean(self):
        from core import report
        _, blocks = report._blocks_multiplicity(
            {"is_multiple": True, "sb_flag": False, "basis": "visual", "otype": None,
             "multiplicity_basis": None})
        labels = self._labels(blocks)
        self.assertNotIn("Gaia archive", labels)          # byte-identical on a clean pull
        self.assertNotIn("FLAME mass (A)", labels)


# ── addendum (WB MSG 209): exclusion-system --component FLAME degrade marker ──
class ExclusionComponentFlameTest(_CatalogStateMixin, unittest.TestCase):
    def test_component_flame_degrade_flags_per_component(self):
        os.environ["SPACE_APP_GAIA_FORCE_UNREACHABLE"] = "1"
        from core import exclusion_system as es
        # a mass-resolving --component (a dict spec carrying `designations` → FLAME) that then falls to
        # the L-inversion — the programmatic "mass-resolving mode" a TR-4 consumer would use.
        r = es.compute_exclusion_system(component_specs=[
            {"name": "TestFlameStar", "sp_type": "K2V", "luminosity_lsun": 0.34,
             "designations": {"Gaia EDR3": "5164707970261890560"}}])
        self.assertNotIn("error", r)
        self.assertEqual(r.get("flame_status_a"), "unreachable")

    def test_explicit_mass_component_has_no_marker(self):
        os.environ["SPACE_APP_GAIA_FORCE_UNREACHABLE"] = "1"
        from core import exclusion_system as es
        # explicit mass → no FLAME resolve → byte-identical, no marker (the deterministic no-network core)
        r = es.compute_exclusion_system(component_specs=[{"mass_solar": 1.0, "sp_type": "G2V"}])
        self.assertNotIn("flame_status_a", r)


# ── 7.3 live-gated: fresh GaiaClass() ≡ shared Gaia (byte-identity guard, R5) ──
class GaiaClassEquivalenceLiveTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SPACE_APP_RUN_LIVE") == "1",
                         "live Gaia TAP (SPACE_APP_RUN_LIVE=1)")
    def test_fresh_client_matches_shared_for_flame_query(self):
        from astroquery.gaia import Gaia, GaiaClass
        from core.catalog import _table_to_rows
        adql = ("SELECT source_id, mass_flame, lum_flame FROM gaiadr3.astrophysical_parameters "
                "WHERE source_id=5164707970261890560")   # eps Eri (the 0.811 FLAME anchor)
        shared = _table_to_rows(Gaia.launch_job(adql).get_results())
        fresh = _table_to_rows(GaiaClass().launch_job(adql).get_results())
        self.assertEqual(shared, fresh)


if __name__ == "__main__":
    unittest.main()
