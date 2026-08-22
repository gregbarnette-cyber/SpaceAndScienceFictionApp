"""Phase Q — System Dossier (`core/report.py`) tests. Offline, mocked readers.

Q-core-1: normal-star path (identity/regions/habitable_zone/hypatia/gcns) + markdown/json.
Q-core-2: planets (NASA + HWC dual sub-tables) + full Phase P regions surface + HTML.
The Sol path and the query.py/GUI surfaces land in later checkpoints with their own tests.

No network, no Qt: the five readers `core.report` orchestrates are patched with fixed
fixtures. The regions fixture is produced by the *real* pure `compute_star_system_regions`
(offline math) so the rendered region/solvent/ice values are internally consistent.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import core.report as report
from core.regions import compute_star_system_regions

_REPO = Path(__file__).resolve().parent.parent
# A throwaway auto-seeded DB so the subprocess Sol path (solar-system tables) never
# touches data/space_app.db. The `dossier --star Sol` path is otherwise fully offline.
_DOSSIER_DB = os.path.join(tempfile.gettempdir(), "phase_q_dossier_throwaway.db")
_ENV = {"SPACE_APP_DB": _DOSSIER_DB, "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}


def _run_query(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


# ── fixtures ──────────────────────────────────────────────────────────────────

def _gcns_fixture():
    return {
        "gaia_source_id": 2452378776434276992,
        "distance_method": "gcns_bayesian",
        "dist_pc": 3.6519, "dist_lo_pc": 3.6498, "dist_hi_pc": 3.6541,
        "light_years": 11.912,
        "phot_g_mean_mag": 3.41, "phot_bp_mean_mag": 3.86, "phot_rp_mean_mag": 2.82,
        "astrom_reliable_prob": 1.0, "wd_prob": 0.0,
        "system_id": None, "n_components": None,
    }


def _simbad_fixture(gcns=True):
    return {
        "main_id": "* tau Cet",
        "ra": 26.017, "dec": -15.9375,
        "sp_type": "G8V",
        "plx_value": 273.81, "teff": 5320.0, "vmag": 3.5,
        "ly": 11.91, "parsecs": 3.6522,
        "designations": {
            "MAIN_ID": "* tau Cet", "NAME": "NAME Tau Ceti", "HD": "HD 10700",
            "HIP": "HIP 8102", "GJ": "GJ 71", "HR": "HR 509",
            "Gaia EDR3": "Gaia DR3 2452378776434276992",
        },
        "desig_str": "HD 10700, HIP 8102",
        "gcns": _gcns_fixture() if gcns else None,
    }


def _regions_fixture(simbad):
    reg = compute_star_system_regions(vmag=3.5, boloLum=-0.2, temp=5320.0, plx=273.81)
    reg["simbad"] = simbad
    reg["spectral_type"] = "G8V"
    reg["bc_key"] = "G8"
    return reg


def _nasa_fixture():
    rows = [
        {"pl_name": "tau Cet g", "pl_bmasse": 1.75, "pl_rade": None, "pl_orbsmax": 0.133,
         "pl_orbper": 20.0, "pl_orbeccen": 0.06, "pl_orbincl": None,
         "discoverymethod": "Radial Velocity"},
        {"pl_name": "tau Cet e", "pl_bmasse": 3.93, "pl_rade": None, "pl_orbsmax": 0.538,
         "pl_orbper": 162.9, "pl_orbeccen": 0.18, "pl_orbincl": None,
         "discoverymethod": "Radial Velocity"},
        {"pl_name": "tau Cet f", "pl_bmasse": 3.93, "pl_rade": None, "pl_orbsmax": 1.334,
         "pl_orbper": 636.1, "pl_orbeccen": 0.16, "pl_orbincl": None,
         "discoverymethod": "Radial Velocity"},
    ]
    return {"simbad": _simbad_fixture(), "planets": rows}


def _hwc_fixture():
    rows = [
        {"P_NAME": "tau Cet e", "P_MASS": "3.93", "P_SEMI_MAJOR_AXIS": "0.538",
         "P_TYPE": "Warm Superterran", "P_HABZONE_CON": "1", "P_ESI": "0.78",
         "P_HABITABLE": "1"},
        {"P_NAME": "tau Cet f", "P_MASS": "3.93", "P_SEMI_MAJOR_AXIS": "1.334",
         "P_TYPE": "Cold Superterran", "P_HABZONE_CON": "1", "P_ESI": "0.71",
         "P_HABITABLE": "0"},
    ]
    return {"simbad": _simbad_fixture(), "star_row": rows[0], "planet_rows": rows}


def _hypatia_fixture():
    return {
        "star_name": "HD 10700",
        "properties": {"teff": 5320.0, "logg": 4.53, "disk": "thin disk"},
        "abundances": [
            {"element": "O",  "name": "Oxygen",    "z": 8,  "category": "cno",
             "mean": -0.30, "std": 0.10, "min": -0.4, "max": -0.2, "n": 14},
            {"element": "Mg", "name": "Magnesium", "z": 12, "category": "alpha",
             "mean": -0.31, "std": 0.05, "min": -0.4, "max": -0.2, "n": 18},
            {"element": "Fe", "name": "Iron",      "z": 26, "category": "iron",
             "mean": -0.55, "std": 0.04, "min": -0.6, "max": -0.5, "n": 22},
        ],
    }


@contextmanager
def _patched(simbad=None, regions_result=None, nasa=None, hwc=None, hypatia=None,
             binary_orbit_result=None, gaia_astro=None, disk=None):
    """Patch the readers core.report calls. Any `*` may be an {"error": ...} dict to exercise the
    warnings path. The three CR-5 live readers default to empty results (offline, no sockets).

    CR-10.5 Part 2: the dossier's multiplicity block now calls `binary.binary_orbit` directly (not
    `binary_stability_auto`), so this harness MUST patch `binary_orbit` or offline tests would hit
    the live network. The default is a no-solutions result (single star)."""
    sb = simbad if simbad is not None else _simbad_fixture()
    rg = regions_result if regions_result is not None else _regions_fixture(sb)
    na = nasa if nasa is not None else _nasa_fixture()
    hw = hwc if hwc is not None else _hwc_fixture()
    hy = hypatia if hypatia is not None else _hypatia_fixture()
    bo = binary_orbit_result if binary_orbit_result is not None else {
        "query": "X", "identity": {}, "solutions": [], "route_tried": []}
    ga = gaia_astro if gaia_astro is not None else {"parameters": None}
    dk = disk if disk is not None else {"detection": "upper_limit", "components": [],
                                        "upper_limit_L_IR_over_Lstar": 1e-4}
    with mock.patch("core.databases.compute_simbad_lookup", return_value=sb), \
         mock.patch("core.regions.compute_star_system_regions_from_simbad", return_value=rg), \
         mock.patch("core.databases.compute_planetary_systems_composite", return_value=na), \
         mock.patch("core.databases.compute_hwc", return_value=hw), \
         mock.patch("core.databases.compute_hypatia_data", return_value=hy), \
         mock.patch("core.binary.binary_orbit", return_value=bo), \
         mock.patch("core.catalog.gaia_astrophysical", return_value=ga), \
         mock.patch("core.debris_disk.debris_disk", return_value=dk):
        yield


def _solar_fixture():
    return {
        "planets": [
            {"Planet": "Earth", "Mass": 0.00315, "Diameter": 0.0892, "Period": 1.0,
             "Periastron": 0.9833, "Semimajor Axis": 1.0, "Apastron": 1.0167,
             "Eccentricity": 0.0167, "Moons": 1},
            {"Planet": "Jupiter", "Mass": 1.0, "Diameter": 1.0, "Period": 11.86,
             "Periastron": 4.95, "Semimajor Axis": 5.203, "Apastron": 5.456,
             "Eccentricity": 0.0484, "Moons": 95},
        ],
        "dwarf_planets": [
            {"Name": "Pluto", "Mass": 0.00218, "Periastron": 29.66, "Semimajor Axis": 39.48,
             "Apastron": 49.3, "Eccentricity": 0.2488, "Period": 248.0},
        ],
        "asteroids": [
            {"Name": "Vesta", "Diameter": 525.4, "Periastron": 2.15, "Semimajor Axis": 2.36,
             "Apastron": 2.57, "Eccentricity": 0.0889, "Period": 3.63},
        ],
        "moons": {"Earth": [
            {"Satellite Name": "Moon", "Diameter (km)": 3474.8, "Mass (kg)": 7.35e22,
             "SemiMajor Axis (km)": 384400, "Eccentricity": 0.0549, "Period (days)": 27.3,
             "Gravity (m/s^2)": 1.62, "Escape Velocity (km/s)": 2.38}]},
    }


@contextmanager
def _patched_sol(solar=None):
    """Sol path: mock the Solar System tables; compute_sol_regions / _sun_hypatia_baseline
    run for real (both pure/offline). A guarded SIMBAD mock asserts it is never called."""
    ss = solar if solar is not None else _solar_fixture()
    sb = mock.MagicMock(side_effect=AssertionError("SIMBAD must not be called for Sol"))
    with mock.patch("core.science.compute_solar_system_tables", return_value=ss), \
         mock.patch("core.databases.compute_simbad_lookup", sb):
        yield sb


_CR5 = ["multiplicity", "age_population", "disk"]   # always-rendered explicit-empty sections (D2)
_ALL = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"] + _CR5
_SOL_SECTIONS = ["identity", "regions", "habitable_zone", "planets", "hypatia"] + _CR5


# ── tests ─────────────────────────────────────────────────────────────────────

class MarkdownShape(unittest.TestCase):
    def test_full_dossier(self):
        with _patched():
            r = report.build_system_dossier("Tau Ceti")
        self.assertNotIn("error", r)
        self.assertEqual(r["fmt"], "markdown")
        self.assertEqual(r["sections"], _ALL)
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["notes"], [])
        doc = r["document"]
        self.assertTrue(doc.startswith("# Tau Ceti — System Dossier"))
        for heading in ("## Identity", "## Stellar Properties & System Regions",
                        "## Calculated Habitable Zone", "## Planets",
                        "## Elemental Abundances", "## GCNS Cross-Reference"):
            self.assertIn(heading, doc)
        self.assertIn("G8V", doc)
        self.assertIn("HD 10700", doc)
        self.assertIn("Water snow line", doc)
        self.assertIn("[Fe/H] -0.55", doc)
        self.assertIn("0 warning(s) · 0 note(s)", doc)


class JsonStructuredOnly(unittest.TestCase):
    def test_json_has_data_no_document(self):
        with _patched():
            r = report.build_system_dossier("Tau Ceti", fmt="json")
        self.assertEqual(r["fmt"], "json")
        self.assertIn("data", r)
        self.assertNotIn("document", r)
        self.assertEqual(set(r["data"].keys()), set(r["sections"]))
        self.assertEqual(r["data"]["identity"]["spectral_type"], "G8V")
        self.assertEqual(r["data"]["hypatia"]["fe_h"], -0.55)
        self.assertEqual(r["data"]["hypatia"]["species_count"], 3)
        # planets structured both-source
        self.assertEqual(len(r["data"]["planets"]["nasa"]), 3)
        self.assertEqual(len(r["data"]["planets"]["hwc"]), 2)


class Planets(unittest.TestCase):
    def test_dual_source_both_tables_nasa_first(self):
        with _patched():
            doc = report.build_system_dossier("Tau Ceti")["document"]
        nasa_h = "NASA Exoplanet Archive — pscomppars (priority 1) · 3 planet(s)"
        hwc_h = "Habitable Worlds Catalog (priority 2) · 2 planet(s)"
        self.assertIn(nasa_h, doc)
        self.assertIn(hwc_h, doc)
        self.assertLess(doc.index(nasa_h), doc.index(hwc_h))   # NASA first
        self.assertIn("Radial Velocity", doc)
        self.assertIn("Warm Superterran", doc)

    def test_nasa_only(self):
        with _patched(hwc={"error": "Star not found in Habitable Worlds Catalog."}):
            r = report.build_system_dossier("Tau Ceti", fmt="json")
        self.assertIn("nasa", r["data"]["planets"])
        self.assertNotIn("hwc", r["data"]["planets"])

    def test_no_planets_warns(self):
        with _patched(nasa={"error": "No exoplanet data"},
                      hwc={"error": "Star not found"}):
            r = report.build_system_dossier("Tau Ceti")
        self.assertNotIn("planets", r["sections"])
        self.assertTrue(any(w.startswith("planets:") for w in r["warnings"]))


class PhasePSurface(unittest.TestCase):
    def test_full_solvent_and_ice_surface(self):
        with _patched():
            doc = report.build_system_dossier("Tau Ceti")["document"]
        self.assertIn("Alternate Solvent Habitable Zones", doc)
        self.assertIn("Polylipid–Hydrogen", doc)
        self.assertIn("Carbon Dioxide †", doc)             # pressure-conditional flag
        self.assertIn("pressure-conditional", doc)
        self.assertIn("Condensation / Ice Lines", doc)
        self.assertIn("Water (snow line)", doc)
        self.assertIn("disk-set", doc)                     # N2/CO fronts flagged

    def test_solvent_bands_sorted_inner_out(self):
        with _patched():
            bands = report.build_system_dossier("Tau Ceti", fmt="json")["data"]["regions"]["alt_solvent"]
        inners = [b["inner_au"] for b in bands]
        self.assertEqual(inners, sorted(inners))
        # intrinsic liquid range is star-independent (water boils ~373 K)
        prw = next(b for b in bands if b["name"] == "Protein–Water")
        self.assertAlmostEqual(prw["t_boil_k"], 373, delta=2)
        self.assertAlmostEqual(prw["t_freeze_k"], 273, delta=2)


class Html(unittest.TestCase):
    def test_self_contained_no_images(self):
        with _patched():
            r = report.build_system_dossier("Tau Ceti", fmt="html")
        doc = r["document"]
        self.assertEqual(r["sections"], _ALL)
        self.assertTrue(doc.startswith("<!DOCTYPE html>"))
        self.assertIn("<style>", doc)
        self.assertIn("<h2>", doc)
        self.assertIn("<table>", doc)
        # self-contained + text-only (images are GUI-only, Q-core-5)
        self.assertNotIn("<img", doc)
        self.assertNotIn("src=", doc)
        self.assertNotIn("http://", doc)
        self.assertNotIn("https://", doc)

    def test_html_escapes(self):
        with _patched():
            doc = report.build_system_dossier("Tau Ceti", fmt="html")["document"]
        self.assertIn("Science Fiction App", doc)   # the literal & rendered as &amp;
        self.assertIn("&amp;", doc)


class SectionSelection(unittest.TestCase):
    def test_subset_and_order(self):
        with _patched():
            r = report.build_system_dossier("Tau Ceti", sections=["gcns", "identity"])
        self.assertEqual(r["sections"], ["identity", "gcns"])
        self.assertIn("## Identity", r["document"])
        self.assertNotIn("## Planets", r["document"])


class SourceFailureIsolation(unittest.TestCase):
    def test_regions_and_hypatia_fail_degrade_to_warnings(self):
        with _patched(regions_result={"error": "Spectral type 'DA' is not a main-sequence class"},
                      hypatia={"error": "No Hypatia data for 'HD 10700'"}):
            r = report.build_system_dossier("Some WD")
        # identity + planets + gcns still render; regions/HZ/hypatia degrade; CR-5 always renders
        self.assertEqual(r["sections"], ["identity", "planets", "gcns"] + _CR5)
        joined = " ".join(r["warnings"])
        self.assertIn("regions:", joined)
        self.assertIn("habitable_zone:", joined)
        self.assertIn("hypatia:", joined)
        self.assertIn("## Identity", r["document"])
        self.assertIn("3 warning(s)", r["document"])

    def test_gcns_absent_warns(self):
        with _patched(simbad=_simbad_fixture(gcns=False)):
            r = report.build_system_dossier("Tau Ceti")
        self.assertNotIn("gcns", r["sections"])
        self.assertTrue(any(w.startswith("gcns:") for w in r["warnings"]))

    def test_requested_unavailable_section_warns(self):
        with _patched(hypatia={"error": "No Hypatia data"}):
            r = report.build_system_dossier("Tau Ceti", sections=["hypatia"])
        self.assertEqual(r["sections"], [])
        self.assertTrue(any(w.startswith("hypatia:") for w in r["warnings"]))
        self.assertNotIn("error", r)


class HardErrors(unittest.TestCase):
    def test_simbad_failure_is_hard_error(self):
        with _patched(simbad={"error": "No results found for 'Nonesuch'"}):
            r = report.build_system_dossier("Nonesuch")
        self.assertIn("error", r)
        self.assertNotIn("document", r)

    def test_bad_format(self):
        self.assertIn("error", report.build_system_dossier("Tau Ceti", fmt="pdf"))

    def test_bad_section(self):
        r = report.build_system_dossier("Tau Ceti", sections=["identity", "bogus"])
        self.assertIn("error", r)
        self.assertIn("bogus", r["error"])

    def test_blank_star(self):
        self.assertIn("error", report.build_system_dossier("   "))


class SolAsteroidCap(unittest.TestCase):
    """The dossier is a rendered document — it cannot page — so the asteroid table
    is capped. Before this, the JPL expansion (22 -> 259 rows) put every asteroid
    in the output: 269 markdown table rows for the planets section alone.
    """

    @staticmethod
    def _solar_with(n_sized, n_unsized=0):
        ss = _solar_fixture()
        ss["asteroids"] = [
            {"Name": f"big{i}", "Diameter": f"{500 - i} km", "Periastron": 2.1,
             "Semimajor Axis": 2.4, "Apastron": 2.7, "Eccentricity": 0.1, "Period": 3.7}
            for i in range(n_sized)
        ] + [
            {"Name": f"tno{i}", "Diameter": "N/A", "Periastron": 30.0,
             "Semimajor Axis": 45.0, "Apastron": 60.0, "Eccentricity": 0.2, "Period": 300.0}
            for i in range(n_unsized)
        ]
        return ss

    def _doc(self, ss):
        with _patched_sol(ss):
            return report.build_system_dossier("Sol", sections=["planets"])["document"]

    def test_a_short_list_is_not_capped_and_carries_no_note(self):
        doc = self._doc(self._solar_with(report._DOSSIER_MAX_ASTEROIDS))
        self.assertIn(f"Major Asteroids · {report._DOSSIER_MAX_ASTEROIDS}", doc)
        self.assertNotIn("Showing the", doc)
        self.assertNotIn(" of ", doc.split("Major Asteroids")[1].splitlines()[0])

    def test_a_long_list_is_capped_and_says_so(self):
        total = report._DOSSIER_MAX_ASTEROIDS + 40
        doc = self._doc(self._solar_with(total))
        self.assertIn(f"Major Asteroids · {report._DOSSIER_MAX_ASTEROIDS} of {total}", doc)
        self.assertIn("Showing the", doc)
        self.assertIn(f"of {total} in the catalogue", doc)

    def test_the_cap_keeps_the_largest(self):
        doc = self._doc(self._solar_with(report._DOSSIER_MAX_ASTEROIDS + 40))
        self.assertIn("big0", doc)            # 500 km — largest
        self.assertNotIn("big60", doc)        # 440 km — ranked out

    def test_no_diameter_bodies_always_survive_the_cap(self):
        """A plain size ranking silently deletes every 'N/A'-diameter TNO."""
        ss = self._solar_with(report._DOSSIER_MAX_ASTEROIDS + 40, n_unsized=9)
        doc = self._doc(ss)
        for i in range(9):
            self.assertIn(f"tno{i}", doc)

    def test_capped_output_is_far_smaller_than_the_full_table(self):
        big = self._solar_with(250)
        rows = sum(1 for l in self._doc(big).splitlines() if l.startswith("|"))
        self.assertLess(rows, 80, "planets section should not render 250 asteroid rows")


class Cr5Sections(unittest.TestCase):
    """CR-5 — multiplicity / age+population / debris-disk dossier sections."""

    def test_binary_and_disk_populated(self):
        sb = _simbad_fixture()
        sb["multiplicity"] = {"is_multiple": True, "sb_flag": True,
                              "basis": "spectroscopic", "otype": "SB*"}
        # CR-10.5 Part 2: stability now runs for real over the fetched binary_orbit solutions.
        bo = {"query": "Some Binary", "identity": {"sp_type": "G0V"}, "route_tried": ["sb9"],
              "solutions": [{"source": "sb9", "seq": 500, "period_d": 900.0, "eccentricity": 0.3,
                             "grade": 4, "companion": {"method": "SB2", "m1_solar": 1.0,
                                                       "m2_solar": 0.5, "mass_ratio_q": 0.5}}]}
        disk = {"detection": "detected", "system_L_IR_over_Lstar": 6e-4,
                "components": [{"type": "warm", "L_IR_over_Lstar": 4e-4, "T_dust_K": 300,
                                "R_disk_au": 0.6, "ref": "Cotten & Song 2016"}]}
        with _patched(simbad=sb, binary_orbit_result=bo, disk=disk):
            r = report.build_system_dossier("Some Binary", fmt="json")
            doc = report.build_system_dossier("Some Binary")["document"]
        mp = r["data"]["multiplicity"]
        self.assertTrue(mp["is_multiple"] and mp["sb_flag"])
        self.assertEqual(mp["elements"]["m2_solar"], 0.5)
        self.assertIsInstance(mp["stype_critical_au"], float)
        self.assertGreater(mp["stype_critical_au"], 0)
        self.assertEqual(mp["multiplicity_basis"], "SB9 seq 500 (P=900.00 d, SB2)")
        self.assertEqual(r["data"]["disk"]["detection"], "detected")
        # md renders the new section headings
        self.assertIn("## Multiplicity & Binary Stability", doc)
        self.assertIn("## Debris Disk / IR Excess", doc)

    def test_single_star_explicit_empties_not_omissions(self):
        # A bare single star: the three CR-5 sections still render (D2 — explicit, never dropped).
        with _patched():                       # default disk = upper_limit, no multiplicity, no age
            r = report.build_system_dossier("Some Single", fmt="json")
        self.assertIn("multiplicity", r["sections"])
        self.assertIn("age_population", r["sections"])
        self.assertIn("disk", r["sections"])
        self.assertFalse(r["data"]["multiplicity"]["is_multiple"])
        self.assertEqual(r["data"]["disk"]["detection"], "upper_limit")
        # not dumped into warnings — they are "ok" explicit empties
        self.assertNotIn("multiplicity:", " ".join(r["warnings"]))

    def test_heavy_readers_gated_by_requested_sections(self):
        # A dossier that doesn't request the CR-5 sections must not fire their live readers.
        sb = _simbad_fixture()
        with mock.patch("core.databases.compute_simbad_lookup", return_value=sb), \
             mock.patch("core.regions.compute_star_system_regions_from_simbad",
                        return_value=_regions_fixture(sb)), \
             mock.patch("core.databases.compute_planetary_systems_composite", return_value=_nasa_fixture()), \
             mock.patch("core.databases.compute_hwc", return_value=_hwc_fixture()), \
             mock.patch("core.databases.compute_hypatia_data", return_value=_hypatia_fixture()), \
             mock.patch("core.binary.binary_orbit") as m_bo, \
             mock.patch("core.catalog.gaia_astrophysical") as m_ga, \
             mock.patch("core.debris_disk.debris_disk") as m_disk:
            r = report.build_system_dossier("X", sections=["identity"], fmt="json")
        self.assertEqual(r["sections"], ["identity"])
        m_bo.assert_not_called()
        m_ga.assert_not_called()
        m_disk.assert_not_called()

    def test_sol_new_sections_reference_values(self):
        with _patched_sol():
            r = report.build_system_dossier("Sol", fmt="json")
        self.assertFalse(r["data"]["multiplicity"]["is_multiple"])
        self.assertEqual(r["data"]["age_population"]["population"], "thin")
        self.assertAlmostEqual(r["data"]["age_population"]["age_gyr"], 4.567)
        self.assertEqual(r["data"]["disk"]["detection"], "detected")
        self.assertEqual(len(r["data"]["disk"]["components"]), 2)


class SolPath(unittest.TestCase):
    def test_offline_no_simbad(self):
        with _patched_sol() as sb:
            r = report.build_system_dossier("Sol")
        self.assertNotIn("error", r)
        sb.assert_not_called()

    def test_sections_and_gcns_note(self):
        with _patched_sol():
            r = report.build_system_dossier("Sol")
        self.assertEqual(r["sections"], _SOL_SECTIONS)   # gcns + moons not rendered
        self.assertEqual(r["warnings"], [])
        self.assertEqual(len(r["notes"]), 1)
        self.assertTrue(r["notes"][0].startswith("gcns:"))
        self.assertIn("reference-frame origin", r["notes"][0])
        self.assertIn("1 note(s)", r["document"])

    def test_sun_alias_matches(self):
        with _patched_sol():
            r = report.build_system_dossier("sun")
        self.assertEqual(r["sections"], _SOL_SECTIONS)

    def test_hypatia_zero_point(self):
        from core.hypatia_elements import HYPATIA_SPECIES
        with _patched_sol():
            r = report.build_system_dossier("Sol", fmt="json")
        hyp = r["data"]["hypatia"]
        self.assertEqual(hyp["fe_h"], 0.0)
        self.assertEqual(hyp["teff"], 5778.0)
        self.assertEqual(hyp["species_count"], len(HYPATIA_SPECIES))

    def test_real_solar_bodies(self):
        with _patched_sol():
            doc = report.build_system_dossier("Sol")["document"]
        self.assertIn("Planets · 2", doc)
        self.assertIn("Dwarf Planets · 1", doc)
        self.assertIn("Major Asteroids · 1", doc)
        for body in ("Earth", "Jupiter", "Pluto", "Vesta"):
            self.assertIn(body, doc)

    def test_moons_optin(self):
        with _patched_sol():
            default = report.build_system_dossier("Sol")
            withmoons = report.build_system_dossier(
                "Sol", sections=["planets", "moons"])
        self.assertNotIn("moons", default["sections"])
        self.assertNotIn("## Moon Systems", default["document"])
        self.assertIn("moons", withmoons["sections"])
        self.assertIn("## Moon Systems", withmoons["document"])
        self.assertIn("Earth · 1 moon(s)", withmoons["document"])

    def test_moons_not_applicable_for_real_star(self):
        with _patched():
            r = report.build_system_dossier("Tau Ceti", sections=["identity", "moons"])
        self.assertEqual(r["sections"], ["identity"])
        self.assertTrue(any(w.startswith("moons:") for w in r["warnings"]))


class QueryDossier(unittest.TestCase):
    """query.py dossier subcommand contract (subprocess, offline via --star Sol)."""

    def test_sol_markdown_happy_path(self):
        code, payload, _ = _run_query("dossier", "--star", "Sol")
        self.assertEqual(code, 0)
        self.assertEqual(payload["fmt"], "markdown")
        self.assertEqual(payload["sections"], _SOL_SECTIONS)
        self.assertTrue(payload["document"].startswith("# Sol — System Dossier"))
        self.assertEqual(len(payload["notes"]), 1)   # GCNS-N/A note

    def test_sol_json(self):
        code, payload, _ = _run_query("dossier", "--star", "Sol", "--fmt", "json")
        self.assertEqual(code, 0)
        self.assertIn("data", payload)
        self.assertNotIn("document", payload)
        self.assertIn("sol", payload["data"]["planets"])

    def test_sol_section_subset(self):
        code, payload, _ = _run_query("dossier", "--star", "Sol",
                                      "--sections", "identity", "planets")
        self.assertEqual(code, 0)
        self.assertEqual(payload["sections"], ["identity", "planets"])

    def test_bad_format_argparse_exit2(self):
        code, payload, stderr = _run_query("dossier", "--star", "Sol", "--fmt", "pdf")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)          # argparse error → stderr, not JSON
        self.assertIn("pdf", stderr)

    def test_unknown_section_exit1(self):
        code, payload, _ = _run_query("dossier", "--star", "Sol", "--sections", "bogus")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        self.assertIn("bogus", payload["error"])

    def test_missing_star_argparse_exit2(self):
        code, payload, _ = _run_query("dossier")
        self.assertEqual(code, 2)


class Deterministic(unittest.TestCase):
    def test_same_fixture_same_document(self):
        with _patched():
            a = report.build_system_dossier("Tau Ceti")
        with _patched():
            b = report.build_system_dossier("Tau Ceti")
        self.assertEqual(a["document"], b["document"])


# ── Phase S-C2 · build_generated_dossier (the R→Q link) ──────────────────────
# Pure over a generate_system result dict — no DB/network, so hand-built fixtures.

def _gen_result(constraints=False):
    r = {
        "seed": 88, "mode": "synthetic", "anchor_star": None,
        "star": {"name": "Gen-88", "spectral_class": "K2V", "teff": 4800.0,
                 "mass_solar": 0.72, "radius_solar": 0.73, "luminosity": 0.21,
                 "hz_inner_au": 0.41, "hz_outer_au": 0.74, "hz_opt_inner_au": 0.33,
                 "hz_opt_outer_au": 0.78, "snow_line_au": 1.9, "source": "synthetic",
                 "grounding": "default-extrapolation", "multiplicity": None},
        "planets": [
            {"name": "Gen-88 b", "a_au": 0.2, "mass_earth": 1.1, "radius_earth": 1.0,
             "ecc": 0.02, "type": "rocky", "t_eq_k": 360.0, "in_hz": False,
             "hz_class": None, "source": "synthetic", "atmosphere": None, "moons": []},
            {"name": "Gen-88 c", "a_au": 0.55, "mass_earth": 3.0, "radius_earth": 1.5,
             "ecc": 0.01, "type": "super_earth", "t_eq_k": 255.0, "in_hz": True,
             "hz_class": "conservative", "source": "synthetic", "atmosphere": "thick",
             "moons": [{"name": "m1"}]},
        ],
        "warnings": [], "notes": ["All bodies are synthetic; realism priors = DefaultPriors."],
    }
    if constraints:
        r["feasible"] = True
        r["constraints"] = [{
            "id": "c1", "type": "planet_at_location", "verdict": "feasible",
            "layer1": {"stable": True, "reason": "Δ ≥ 10 to both neighbours", "metrics": {}},
            "layer2": {"mechanism": "hill_packing", "checked": [], "note": None},
            "layer3": {"hypotheses": [], "grounding": "default-extrapolation"},
            "layer4": {"alternatives": []},
        }]
    return r


class BuildGeneratedDossier(unittest.TestCase):
    def test_markdown_shape(self):
        r = report.build_generated_dossier(_gen_result())
        self.assertEqual(r["fmt"], "markdown")
        self.assertEqual(r["star"], "Gen-88")
        self.assertEqual(r["seed"], 88)
        self.assertEqual(r["sections"], ["identity", "star", "planets"])
        doc = r["document"]
        self.assertIn("# Gen-88 — Generated System Dossier", doc)
        self.assertIn("## Planets", doc)
        self.assertIn("Gen-88 c", doc)
        self.assertNotIn("## Feasibility", doc)   # no constraints

    def test_json_structured_only(self):
        r = report.build_generated_dossier(_gen_result(), fmt="json")
        self.assertEqual(r["fmt"], "json")
        self.assertNotIn("document", r)
        self.assertIn("data", r)
        self.assertEqual(len(r["data"]["planets"]["planets"]), 2)
        self.assertEqual(r["data"]["identity"]["grounding"], "default-extrapolation")

    def test_html_self_contained(self):
        r = report.build_generated_dossier(_gen_result(), fmt="html")
        doc = r["document"]
        self.assertTrue(doc.startswith("<!DOCTYPE html>"))
        self.assertIn("<style>", doc)
        self.assertNotIn("<img", doc)              # text + tables only
        self.assertIn("Generated System Dossier", doc)

    def test_feasibility_section_when_constraints(self):
        r = report.build_generated_dossier(_gen_result(constraints=True))
        self.assertIn("feasibility", r["sections"])
        self.assertIn("## Feasibility", r["document"])
        self.assertIn("feasible", r["document"])

    def test_feasibility_requested_without_constraints_is_note_not_error(self):
        r = report.build_generated_dossier(_gen_result(), sections=["identity", "feasibility"])
        self.assertNotIn("error", r)
        self.assertEqual(r["sections"], ["identity"])
        self.assertTrue(any("feasibility" in n for n in r["notes"]))

    def test_section_subset(self):
        r = report.build_generated_dossier(_gen_result(), sections=["star"])
        self.assertEqual(r["sections"], ["star"])
        self.assertIn("## Star", r["document"])
        self.assertNotIn("## Planets", r["document"])

    def test_determinism(self):
        a = report.build_generated_dossier(_gen_result())
        b = report.build_generated_dossier(_gen_result())
        self.assertEqual(a["document"], b["document"])

    def test_errors(self):
        self.assertIn("error", report.build_generated_dossier(_gen_result(), fmt="pdf"))
        self.assertIn("error", report.build_generated_dossier({"error": "boom"}))
        self.assertIn("error", report.build_generated_dossier({"not": "a result"}))
        self.assertIn("error", report.build_generated_dossier(
            _gen_result(), sections=["identity", "bogus"]))


# ── Phase S-C5 · build_project_dossier (the export fan-out) ──────────────────
import pathlib
import shutil
import core.db as _db
import core.projects as _projects


def _fake_bsd(star, sections=None, fmt="markdown"):
    """Stand-in for build_system_dossier (real members) — no network."""
    if fmt == "json":
        return {"star": star, "fmt": "json", "sections": ["identity"],
                "warnings": [], "notes": [], "data": {"identity": {"name": star}}}
    doc = (f"# {star} — System Dossier\n\nbody" if fmt == "markdown"
           else f"<!DOCTYPE html><html><head></head><body><h1>{star}</h1></body></html>")
    return {"star": star, "fmt": fmt, "sections": ["identity"],
            "warnings": [], "notes": [], "document": doc}


def _fake_gen(spec):
    return {"seed": spec.get("seed"), "mode": "synthetic", "anchor_star": None,
            "star": {"name": "Gen-5", "spectral_class": "M0V", "teff": 3800.0,
                     "mass_solar": 0.5, "radius_solar": 0.5, "luminosity": 0.05,
                     "hz_inner_au": 0.2, "hz_outer_au": 0.4, "hz_opt_inner_au": 0.18,
                     "hz_opt_outer_au": 0.42, "snow_line_au": 0.9, "source": "synthetic",
                     "grounding": "default-extrapolation", "multiplicity": None},
            "planets": [{"name": "Gen-5 b", "a_au": 0.1, "mass_earth": 1.0,
                         "radius_earth": 1.0, "type": "rocky", "t_eq_k": 300.0,
                         "in_hz": True, "hz_class": "conservative", "source": "synthetic",
                         "atmosphere": None, "moons": []}],
            "warnings": [], "notes": []}


class BuildProjectDossier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (_db._DB_PATH, _db._conn, _db._auto_seed)
        _db._DB_PATH = pathlib.Path(self.tmpdir) / "p.db"
        _db._conn = None
        _db._auto_seed = lambda conn: None
        _db.get_conn()
        _projects.create_project("P", "a setting")
        _projects.add_member("P", "Tau Ceti", note="real")
        _projects.add_member("P", "Gen-5", source="generated", seed=5, spec={"seed": 5})

    def tearDown(self):
        _db.close_conn()
        _db._DB_PATH, _db._conn, _db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patches(self):
        return (mock.patch("core.report.build_system_dossier", _fake_bsd),
                mock.patch("core.generate.generate_from_spec", _fake_gen))

    def test_combined_markdown(self):
        p1, p2 = self._patches()
        with p1, p2:
            r = report.build_project_dossier("P", fmt="markdown", combined=True)
        self.assertEqual(r["combined"], True)
        self.assertEqual(len(r["members"]), 2)
        doc = r["document"]
        self.assertIn("# P — Project Dossier", doc)
        self.assertIn("Tau Ceti — System Dossier", doc)
        self.assertIn("Gen-5 — Generated System Dossier", doc)

    def test_combined_html_single_doc(self):
        p1, p2 = self._patches()
        with p1, p2:
            r = report.build_project_dossier("P", fmt="html", combined=True)
        doc = r["document"]
        self.assertEqual(doc.count("<!DOCTYPE html>"), 1)   # one merged doc
        self.assertIn("P — Project Dossier", doc)
        self.assertIn("Gen-5", doc)

    def test_combined_json(self):
        p1, p2 = self._patches()
        with p1, p2:
            r = report.build_project_dossier("P", fmt="json", combined=True)
        self.assertNotIn("document", r)
        self.assertEqual(len(r["data"]["members"]), 2)

    def test_per_file(self):
        p1, p2 = self._patches()
        with p1, p2:
            r = report.build_project_dossier("P", fmt="markdown", combined=False)
        self.assertFalse(r["combined"])
        docs = {m["star_name"]: m for m in r["members"]}
        self.assertIn("document", docs["Tau Ceti"])
        self.assertIn("document", docs["Gen-5"])

    def test_member_failure_isolated(self):
        def _boom(star, sections=None, fmt="markdown"):
            return {"error": f"SIMBAD failed for {star}"}
        with mock.patch("core.report.build_system_dossier", _boom), \
             mock.patch("core.generate.generate_from_spec", _fake_gen):
            r = report.build_project_dossier("P", combined=True)
        members = {m["star_name"]: m for m in r["members"]}
        self.assertFalse(members["Tau Ceti"]["ok"])     # real one failed
        self.assertTrue(members["Gen-5"]["ok"])         # generated still ok
        self.assertTrue(r["warnings"])
        self.assertIn("Gen-5 — Generated System Dossier", r["document"])

    def test_unknown_project_and_bad_fmt(self):
        self.assertIn("error", report.build_project_dossier("Ghost"))
        self.assertIn("error", report.build_project_dossier("P", fmt="pdf"))


class Cr105Part1RegionGuard(unittest.TestCase):
    """CR-10.5 Part 1 — luminosity-class region guard + graceful-null luminosity_consistency."""

    def _sb(self, sp):
        sb = _simbad_fixture()
        sb["sp_type"] = sp
        return sb

    def test_supergiant_refused_lbol_null(self):     # validation #1 + #4-iii (Polaris/Betelgeuse)
        with _patched(simbad=self._sb("F8Ib"), gaia_astro={"parameters": None}):
            r = report.build_system_dossier("Polaris", sections=["regions", "habitable_zone"], fmt="json")
        reg = r["data"]["regions"]
        self.assertTrue(reg["evolved_star_flag"])
        self.assertEqual(reg["luminosity_class"], "Ib")
        self.assertTrue(reg["ms_inversion_withheld"])
        self.assertNotIn("stellar", reg)                       # bogus MS numbers withheld
        self.assertIsNone(reg["luminosity_consistency"]["L_bol"])
        self.assertIsNone(reg["luminosity_consistency"]["flagged"])
        self.assertNotIn("habitable_zone", r["sections"])      # HZ withheld → a note, not rendered
        self.assertTrue(any("habitable_zone" in n for n in r["notes"]))

    def test_pollux_token_boundary_III_not_Ib(self):           # validation #2 (Teff present)
        with _patched(simbad=self._sb("K0IIIb"), gaia_astro={"parameters": None}):
            r = report.build_system_dossier("Pollux", sections=["regions"], fmt="json")
        reg = r["data"]["regions"]
        self.assertEqual(reg["luminosity_class"], "III")
        self.assertTrue(reg["evolved_star_flag"])

    def test_evolved_star_self_flags_even_with_null_teff(self):   # validation #2 — the real Pollux (WB MSG 099)
        # SIMBAD has no Teff for Pollux → compute_star_system_regions_from_simbad errors; the evolved
        # self-flag must STILL fire structurally (it's a pure sp_type parse). luminosity_consistency null.
        with _patched(simbad=self._sb("K0IIIb"),
                      regions_result={"error": "Temperature not available for this star"}):
            r = report.build_system_dossier("Pollux", sections=["regions", "habitable_zone"], fmt="json")
        self.assertIn("regions", r["sections"])                # structured, not just a warning string
        reg = r["data"]["regions"]
        self.assertEqual(reg["luminosity_class"], "III")
        self.assertTrue(reg["evolved_star_flag"])
        self.assertTrue(reg["ms_inversion_withheld"])
        self.assertIsNone(reg["luminosity_consistency"]["calc_L"])
        self.assertIsNone(reg["luminosity_consistency"]["flagged"])
        self.assertNotIn("regions:", " ".join(r["warnings"]))  # no longer a warning
        self.assertNotIn("habitable_zone", r["sections"])      # HZ withheld → note

    def test_non_evolved_null_teff_still_warns_no_structured_block(self):
        # A NON-evolved star that errors (e.g. missing Teff on an MS dwarf) keeps the warn path — no
        # spurious evolved block.
        with _patched(simbad=self._sb("G6V"),
                      regions_result={"error": "Temperature not available for this star"}):
            r = report.build_system_dossier("D", sections=["regions"], fmt="json")
        self.assertNotIn("regions", r["sections"])
        self.assertTrue(any("regions:" in w for w in r["warnings"]))

    def test_ms_dwarf_region_values_byte_identical(self):      # validation #3
        sb = self._sb("G6V")
        with _patched(simbad=sb, gaia_astro={"parameters": {"lum_flame": None}}):
            reg = report.build_system_dossier("D", sections=["regions"], fmt="json")["data"]["regions"]
        self.assertFalse(reg["evolved_star_flag"])
        self.assertEqual(reg["luminosity_class"], "V")
        base = report._regions_data(_regions_fixture(sb))
        self.assertEqual(reg["stellar"], base["stellar"])       # existing values untouched
        self.assertEqual(reg["system_regions"], base["system_regions"])
        self.assertEqual(reg["alt_solvent"], base["alt_solvent"])

    def test_consistency_flag_trips_on_flame_covered_mismatch(self):   # validation #4-i (mechanism)
        with _patched(simbad=self._sb("K0III"), gaia_astro={"parameters": {"lum_flame": 1e6}}):
            reg = report.build_system_dossier("G", sections=["regions"], fmt="json")["data"]["regions"]
        lc = reg["luminosity_consistency"]
        self.assertIsNotNone(lc["L_bol"])
        self.assertTrue(lc["flagged"])

    def test_clean_ms_flagged_false_with_flame(self):          # validation #4-ii
        sb = self._sb("G6V")
        rg = _regions_fixture(sb)
        calc_l = rg["stellarRadius"] ** 2 * (rg["temp"] / 5772.0) ** 4
        with _patched(simbad=sb, gaia_astro={"parameters": {"lum_flame": calc_l}}):
            reg = report.build_system_dossier("D", sections=["regions"], fmt="json")["data"]["regions"]
        self.assertFalse(reg["luminosity_consistency"]["flagged"])

    def test_force_ms_inversion_overrides(self):
        with _patched(simbad=self._sb("F8Ib"), gaia_astro={"parameters": None}):
            reg = report.build_system_dossier("Polaris", sections=["regions"], fmt="json",
                                              force_ms_inversion=True)["data"]["regions"]
        self.assertIn("stellar", reg)                          # numbers present (forced)
        self.assertTrue(reg["evolved_star_flag"])
        self.assertIsNone(reg.get("ms_inversion_withheld"))


class Cr105Part2Multiplicity(unittest.TestCase):
    """CR-10.5 Part 2 — multiplicity cross-check against binary-orbit catalogs, otype-independent."""

    def _sb(self, otype, mult):
        sb = _simbad_fixture()
        sb["otype"] = otype
        sb["multiplicity"] = mult
        return sb

    def test_variability_primary_sb_caught(self):              # validation #5 (Spica)
        sb = self._sb("bC*", {"is_multiple": False, "sb_flag": False, "basis": None, "otype": "bC*"})
        bo = {"query": "Spica", "identity": {"sp_type": "B1III-IV+B2V"}, "route_tried": ["sb9"],
              "solutions": [{"source": "sb9", "seq": 766, "period_d": 4.0145, "eccentricity": 0.108,
                             "grade": 4, "companion": {"method": "SB2", "m1_solar": 11.4,
                                                       "m2_solar": 7.2, "mass_ratio_q": 0.63}}]}
        with _patched(simbad=sb, binary_orbit_result=bo):
            mp = report.build_system_dossier("Spica", sections=["multiplicity"],
                                             fmt="json")["data"]["multiplicity"]
        self.assertTrue(mp["is_multiple"] and mp["sb_flag"])
        self.assertEqual(mp["multiplicity_basis"], "SB9 seq 766 (P=4.01 d, SB2)")

    def test_single_star_no_regression(self):                  # validation #6
        sb = self._sb("*", {"is_multiple": False, "sb_flag": False, "basis": None, "otype": "*"})
        with _patched(simbad=sb):                               # default binary_orbit = no solutions
            mp = report.build_system_dossier("D", sections=["multiplicity"],
                                             fmt="json")["data"]["multiplicity"]
        self.assertFalse(mp["is_multiple"])
        self.assertIsNone(mp["multiplicity_basis"])

    def test_planet_class_solution_not_a_stellar_multiple(self):
        # /code-review Finding 1: a planet-class NSS/SB1 companion (e.g. GJ 876's 61 d NSS orbit) must
        # NOT read as a stellar multiple — §3.3 "a raw NSS pull can't ingest planets".
        sb = self._sb("PM*", {"is_multiple": False, "sb_flag": False, "basis": None, "otype": "PM*"})
        bo = {"query": "GJ 876", "identity": {}, "route_tried": ["gaia-nss"],
              "solutions": [{"source": "gaia-nss:two_body_orbit", "solution_type": "Orbital",
                             "period_d": 61.0, "grade": 5,
                             "companion": {"method": "astrometric", "class": "planet",
                                           "m1_solar": 0.37, "m2_solar": 0.0025}}]}
        with _patched(simbad=sb, binary_orbit_result=bo):
            mp = report.build_system_dossier("GJ 876", sections=["multiplicity"],
                                             fmt="json")["data"]["multiplicity"]
        self.assertFalse(mp["is_multiple"])                    # planet-only host → not a stellar multiple
        self.assertIsNone(mp["multiplicity_basis"])

    def test_otype_multiple_verdict_unchanged(self):           # validation #7
        sb = self._sb("**", {"is_multiple": True, "sb_flag": False, "basis": "visual", "otype": "**"})
        bo = {"query": "X", "identity": {}, "route_tried": ["orb6"],
              "solutions": [{"source": "orb6", "grade": "1", "period_d": None, "companion": None}]}
        with _patched(simbad=sb, binary_orbit_result=bo):
            mp = report.build_system_dossier("X", sections=["multiplicity"],
                                             fmt="json")["data"]["multiplicity"]
        self.assertTrue(mp["is_multiple"])                     # verdict unchanged
        self.assertIsNotNone(mp["multiplicity_basis"])         # basis enriched (benign)


if __name__ == "__main__":
    unittest.main()
