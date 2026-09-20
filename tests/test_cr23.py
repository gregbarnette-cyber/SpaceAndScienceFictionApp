# tests/test_cr23.py — CR-23 exclusion mass-chain harmonization (Option A).
#
# Offline, in-process (network mocked). Covers:
#   CR-23.1 — exclusion-boundary --star MS resolves via the shared tier ladder (manual > catalog >
#             Gaia FLAME > L-inversion), == exclusion-system --star == dossier; FLAME-miss byte-identity;
#             the 4-star internal seed shifting a single MS star inversion→catalog with no --star-mass-catalog.
#   CR-23.2 — mass_provenance on every exclusion-boundary path (the 6-value enum + null on no-mass);
#             flame_status surfaced (not silently dropped) on a bounded FLAME degrade, both subcommands.
#   CR-23.3 — evolved per-component standoff_note on exclusion-system (null for MS / windless / unmodeled).
#
# The live ε Eri FLAME anchors (0.811 / gaia_flame / 43.69) run in test_query_exclusion_system_live.py.

import argparse
import unittest
from unittest import mock

import query
import core.exclusion_boundary as eb
import core.exclusion_system as es


def _fake_simbad(mapping):
    return lambda name: mapping.get(name, {"error": f"No results for '{name}'"})


# ε Eri fixtures (K2V, a Gaia id so FLAME is eligible).
_EPS_ERI_SIMBAD = {"epsilon Eridani": {
    "main_id": "* eps Eri", "sp_type": "K2V", "otype": "star",
    "designations": {"HD": "HD 22049", "Gaia EDR3": "5164707970261890560"}}}
_EPS_ERI_BCLUM = 0.32            # ~ε Eri L; only used by the L-inversion tier / the wall's luminosity term
_EPS_ERI_INVERSION = _EPS_ERI_BCLUM ** 0.2632   # the exact old regions.stellarMass = the FLAME-miss mass

_SEED_SIRIUS_A = {"Sirius A": {
    "main_id": "* alf CMa", "sp_type": "A0mA1Va", "otype": "star",
    "designations": {"HD": "HD 48915"}}}


def _run_boundary(**overrides):
    """Call query.cmd_exclusion_boundary with a default arg namespace + captured _out (no sys.exit)."""
    args = argparse.Namespace(
        mass_msun=None, object=None, star=None, spectral_type=None, luminosity_lsun=None,
        mass_loss_msun_yr=None, wind_state=None, wind_speed=None, v_ism=None, c_ms=None,
        b_field=None, n_cloud=None, cloud_temp=None, wind_phase_yr=None, f_shock=None,
        m_shock_min=None, mass_loss_source=None, dial=None, calibration_au=47.5,
        alpha=1.0 / 3.0, beta=0.0, gamma=0.0, scan_alpha=False, star_mass_catalog=None,
        gaia_timeout=None)
    for k, v in overrides.items():
        setattr(args, k, v)
    cap = {}
    with mock.patch("query._out", lambda r: cap.__setitem__("r", r)):
        query.cmd_exclusion_boundary(args)
    return cap["r"]


def _flame(mass_flame):
    return lambda **k: {"parameters": {"mass_flame": mass_flame}}


def _flame_degrade(reason="unreachable"):
    return lambda **k: {"error": f"Gaia TAP {reason}", "gaia_bound_reason": reason}


class Cr231ExclusionBoundaryStarLadderTest(unittest.TestCase):
    """CR-23.1: exclusion-boundary --star MS resolves via the tier ladder (was raw L-inversion)."""

    def _mocks(self, flame, simbad=None, no_gaia_id=False):
        sid = (lambda d: None) if no_gaia_id else (lambda d: "5164707970261890560")
        return [
            mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(simbad or _EPS_ERI_SIMBAD)),
            mock.patch("core.regions.compute_star_system_regions_from_simbad",
                       lambda sl: {"bcLuminosity": _EPS_ERI_BCLUM}),
            mock.patch("core.binary.gaia_source_id_from_designations", sid),
            mock.patch("core.catalog.gaia_astrophysical", flame),
        ]

    def test_flame_hit_resolves_gaia_flame(self):   # acceptance 1 (offline): 0.811 / gaia_flame / 43.69
        patches = self._mocks(_flame(0.811))
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="epsilon Eridani", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertAlmostEqual(r["mass_msun"], 0.811, places=9)
        self.assertEqual(r["mass_provenance"], "gaia_flame")
        self.assertAlmostEqual(r["r_ex_au"], 47.5 * 0.811 ** 0.4, places=6)
        self.assertAlmostEqual(r["r_ex_au"], 43.69, delta=0.02)   # spec's "≈43.69" (exact 43.682)
        self.assertNotIn("flame_status", r)              # a clean FLAME hit → no degrade flag

    def test_flame_miss_falls_to_inversion_byte_identical(self):   # FLAME-miss == old regions mass
        patches = self._mocks(_flame(None))               # FLAME returns no mass
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="epsilon Eridani", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(r["mass_msun"], _EPS_ERI_INVERSION)   # exact float identity to bcLum**0.2632
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertAlmostEqual(r["r_ex_au"], 47.5 * _EPS_ERI_INVERSION ** 0.4, places=9)

    def test_no_gaia_id_falls_to_inversion(self):         # no Gaia id → FLAME never attempted → inversion
        patches = self._mocks(_flame(0.811), no_gaia_id=True)
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="epsilon Eridani", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(r["mass_msun"], _EPS_ERI_INVERSION)

    def test_forced_flame_degrade_surfaces_flame_status(self):   # CR-23.2: never a silent fall-through
        patches = self._mocks(_flame_degrade("unreachable"))
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="epsilon Eridani", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(r["flame_status"], "unreachable")   # the previously-absent degrade flag

    def test_seed_star_shifts_inversion_to_catalog_without_flag(self):   # Finding 2 (correctness review)
        # Sirius A is in the 4-star internal seed (load_mass_catalog(None)) → catalog tier even with NO
        # --star-mass-catalog; FLAME must NOT be consulted (catalog short-circuits first).
        flame_called = {"n": 0}

        def _flame_count(**k):
            flame_called["n"] += 1
            return {"parameters": {"mass_flame": 9.9}}
        patches = [
            mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(_SEED_SIRIUS_A)),
            mock.patch("core.regions.compute_star_system_regions_from_simbad",
                       lambda sl: {"bcLuminosity": 25.4}),
            mock.patch("core.binary.gaia_source_id_from_designations", lambda d: "1"),
            mock.patch("core.catalog.gaia_astrophysical", _flame_count),
        ]
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="Sirius A", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(r["mass_provenance"], "catalog")
        self.assertAlmostEqual(r["mass_msun"], 2.063, places=3)
        self.assertAlmostEqual(r["r_ex_au"], 47.5 * 2.063 ** 0.4, places=4)   # ≈ 63.5, not the ~66.7 inversion
        self.assertEqual(flame_called["n"], 0)              # catalog short-circuits ahead of FLAME


class Cr231BothSubcommandsAgreeTest(unittest.TestCase):
    """CR-23.1 acceptance 3: exclusion-boundary --star == exclusion-system --star for the same star."""

    def _sys_star(self, flame, degrade_reason=None):
        f = _flame_degrade(degrade_reason) if degrade_reason else _flame(flame)
        patches = [
            mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(_EPS_ERI_SIMBAD)),
            mock.patch("core.regions.compute_star_system_regions_from_simbad",
                       lambda sl: {"bcLuminosity": _EPS_ERI_BCLUM}),
            mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": []}),
            mock.patch("core.binary.gaia_source_id_from_designations", lambda d: "5164707970261890560"),
            mock.patch("core.catalog.gaia_astrophysical", f),
        ]
        for p in patches:
            p.start()
        try:
            return es.compute_exclusion_system(star="epsilon Eridani", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_exclusion_system_star_flame_hit_matches_boundary(self):
        r = self._sys_star(0.811)
        comp = r["zones"][0]["components"][0]
        self.assertAlmostEqual(comp["mass_solar"], 0.811, places=9)
        self.assertEqual(comp["mass_provenance"], "gaia_flame")
        self.assertAlmostEqual(comp["r_ex_au"], 47.5 * 0.811 ** 0.4, places=6)   # == boundary's r_ex

    def test_exclusion_system_single_body_flame_degrade_surfaced(self):   # non-blocker 3 (was dropped)
        r = self._sys_star(None, degrade_reason="timeout")
        self.assertEqual(r["flame_status"], "timeout")     # single-body --star flame_status now surfaced
        comp = r["zones"][0]["components"][0]
        self.assertEqual(comp["mass_provenance"], "ms_luminosity_inversion")


class Cr232MassProvenanceEveryPathTest(unittest.TestCase):
    """CR-23.2 §2a/§2b: mass_provenance present on EVERY exclusion-boundary path (6-value enum + null)."""

    def test_mass_msun_is_manual(self):
        r = _run_boundary(mass_msun=2.0, alpha=0.4)
        self.assertEqual(r["mass_provenance"], "manual")

    def test_object_preset(self):
        r = _run_boundary(object="sun", alpha=0.4)
        self.assertEqual(r["mass_provenance"], "object_preset")

    def test_object_windless_still_carries_object_preset(self):   # §2a: key present on the windless path
        r = _run_boundary(object="brown-dwarf", alpha=0.4)
        self.assertEqual(r["forcing_class"], "free_harbor")       # windless_free_harbor
        self.assertEqual(r["mass_provenance"], "object_preset")   # preset always has a mass

    def test_spectral_type_ms_table(self):
        r = _run_boundary(spectral_type="G2V", alpha=0.4)
        self.assertEqual(r["mass_provenance"], "spectral_type_table")

    def test_spectral_type_windless_is_null_key_present(self):    # WB-confirmed null on no-mass (MSG 254)
        r = _run_boundary(spectral_type="DA2", alpha=0.4)         # white dwarf → windless
        self.assertIn("mass_provenance", r)                       # key present …
        self.assertIsNone(r["mass_provenance"])                   # … value null (no mass resolved)

    def test_spectral_type_unmodeled_is_null_key_present(self):
        r = _run_boundary(spectral_type="sdB1", alpha=0.4)        # hot subdwarf → unmodeled
        self.assertIn("mass_provenance", r)
        self.assertIsNone(r["mass_provenance"])

    def test_enum_values_are_the_six_confirmed(self):
        # every value the exclusion-boundary paths can emit is in the WB-confirmed 6-value enum (+ None)
        allowed = {"manual", "catalog", "gaia_flame", "ms_luminosity_inversion",
                   "object_preset", "spectral_type_table", None}
        for kw in ({"mass_msun": 1.0}, {"object": "sun"}, {"object": "brown-dwarf"},
                   {"spectral_type": "G2V"}, {"spectral_type": "DA2"}, {"spectral_type": "sdB1"}):
            r = _run_boundary(alpha=0.4, **kw)
            self.assertIn(r.get("mass_provenance"), allowed, kw)


class Cr232MassNoteTest(unittest.TestCase):
    """CR-23.2 §2c: the resolver's over-read caution surfaces on the with-mass path (was discarded)."""

    def test_hot_ms_inversion_surfaces_over_read_caution(self):
        simbad = {"Vega-like": {"main_id": "* test A star", "sp_type": "A1V", "otype": "star",
                                "designations": {"HD": "HD 999999"}}}
        patches = [
            mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(simbad)),
            mock.patch("core.regions.compute_star_system_regions_from_simbad",
                       lambda sl: {"bcLuminosity": 40.0}),
            mock.patch("core.binary.gaia_source_id_from_designations", lambda d: None),   # FLAME miss
            mock.patch("core.catalog.gaia_astrophysical", _flame(None)),
        ]
        for p in patches:
            p.start()
        try:
            r = _run_boundary(star="Vega-like", alpha=0.4)
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertIn("mass_note", r)
        self.assertIn("over-read", r["mass_note"])               # the hot-upper-MS caution

    def test_exclusion_system_component_carries_mass_note_parity(self):   # review F4: shape parity
        r = es.compute_exclusion_system(component_specs=["id=A,lum=40,type=A1V"])   # hot-MS inversion
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["mass_provenance"], "ms_luminosity_inversion")
        self.assertIn("mass_note", c)                            # exclusion-system now carries it too
        self.assertIn("over-read", c["mass_note"])

    def test_exclusion_system_clean_inversion_mass_note_is_none(self):   # clean (non-hot/peculiar) inversion → null
        r = es.compute_exclusion_system(component_specs=["id=A,lum=1.0,type=G2V"])   # G-dwarf, no caution
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["mass_provenance"], "ms_luminosity_inversion")
        self.assertIsNone(c["mass_note"])


class Cr233EvolvedStandoffNoteTest(unittest.TestCase):
    """CR-23.3: exclusion-system per-component standoff_note — research-grade for evolved, null else."""

    def _one(self, spec):
        return es.compose_exclusion_system([spec], alpha=0.4)["zones"][0]["components"][0]

    def test_evolved_subgiant_gets_research_grade_note(self):   # δ Pav-like (G8IV subgiant)
        c = self._one({"id": "Delta Pavonis", "mass_solar": 0.991, "luminosity_lsun": 1.2,
                       "sp_type": "G8IV"})
        self.assertEqual(c["domain"], "evolved")
        self.assertIsNotNone(c["standoff_au"])
        self.assertEqual(c["standoff_note"], eb._EVOLVED_STANDOFF_NOTE)
        self.assertIn("research-grade", c["standoff_note"])

    def test_evolved_subgiant_procyon_a(self):                  # acceptance case 2 (Procyon A, F5IV-V)
        c = self._one({"id": "Procyon A", "mass_solar": 1.478, "luminosity_lsun": 6.9,
                       "sp_type": "F5IV-V"})
        self.assertEqual(c["domain"], "evolved")
        self.assertIsNotNone(c["standoff_au"])
        self.assertEqual(c["standoff_note"], eb._EVOLVED_STANDOFF_NOTE)

    def test_main_sequence_standoff_note_is_null(self):         # control: MS standoff IS canon
        c = self._one({"id": "eps Eri", "mass_solar": 0.811, "luminosity_lsun": 0.32, "sp_type": "K2V"})
        self.assertEqual(c["domain"], "main_sequence")
        self.assertIsNotNone(c["standoff_au"])
        self.assertIsNone(c["standoff_note"])

    def test_windless_standoff_note_is_null(self):              # control: WD → no standoff
        c = self._one({"id": "Sirius B", "mass_solar": 1.018, "class": "wd"})
        self.assertEqual(c["domain"], "windless_free_harbor")
        self.assertIsNone(c["standoff_au"])
        self.assertIsNone(c["standoff_note"])

    def test_evolved_no_mass_gets_no_mass_note(self):           # lone evolved, unresolved mass
        c = self._one({"id": "giant", "sp_type": "K0III"})     # no mass → r_ex null
        self.assertEqual(c["domain"], "evolved")
        self.assertIsNone(c["r_ex_au"])
        self.assertEqual(c["standoff_note"], eb._EVOLVED_NO_MASS_NOTE)

    def test_note_addition_does_not_move_the_standoff_number(self):
        # CR-23.3 is note-only: the evolved standoff value is unchanged (byte-identical) by construction
        c = self._one({"id": "g", "mass_solar": 0.991, "luminosity_lsun": 1.2, "sp_type": "G8IV"})
        self.assertAlmostEqual(c["standoff_au"], 47.5 * 0.991 ** 0.4, places=9)


if __name__ == "__main__":
    unittest.main()
