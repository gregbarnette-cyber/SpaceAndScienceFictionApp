# tests/test_sol_result_row.py — Sol as a *result row* in the two "stars within X
# of a named star" searches (opt 19 over `star_systems`, GCNS M4c over `gcns_stars`).
#
# The Sun is not a SIMBAD catalog object and Gaia does not observe it, so neither
# table can ever hold a row for it — yet from any *other* star Sol is an ordinary
# neighbour (11.91 ly from tau Ceti). Both searches therefore synthesize one at the
# heliocentric origin. These tests pin:
#   * the row appears, at the right distance, only when in range;
#   * it is excluded when the centre *is* Sol (the existing self-exclusion floor);
#   * `parsecs` = 1 AU in pc, the value that makes the standard
#     `M = V + 5 - 5*log10(pc)` recovery yield Sol's true M_V of 4.83 — which is what
#     lets the HR-diagram and night-sky preps stay free of a Sol special case;
#   * the night sky carries Sol exactly ONCE (`prepare_sky_from_star` used to append
#     its own, and would otherwise double it);
#   * the GCNS row is flagged as synthetic and leaves every unfillable field NULL.

import os
# Qt must run headless under the test runner. Set before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math
import pathlib
import shutil
import tempfile
import unittest

import core.calculators as calc
import core.databases as databases
import core.db as db
import core.viz as viz


def _qt_available() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except Exception:
        return False


def _mpl_available() -> bool:
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


# tau Ceti is 11.91 ly out; a centre at exactly 11.91 ly along +x is equivalent for
# the geometry under test and keeps these tests network-free.
_CENTRE_LY = 11.91


def _fake_centre(ly=_CENTRE_LY, name="Test Centre"):
    """Stand in for the SIMBAD centre lookup: a star `ly` away at RA=0, Dec=0."""
    return lambda _name: {"name": name, "ra_deg": 0.0, "dec_deg": 0.0, "ly": ly}


class _TmpDbTest(unittest.TestCase):
    """tmp `data/space_app.db` with the real schema, auto-seeding disabled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class Opt19SolRowTest(_TmpDbTest):
    """opt 19 / `query.py stars-within-star` over `star_systems`."""

    def setUp(self):
        super().setUp()
        # One ordinary catalogue star so the table is non-empty (the empty table is
        # its own error path). 200 mas -> 5 pc -> 16.3 ly, at RA=0/Dec=0.
        self.conn.execute(
            "INSERT INTO star_systems "
            "(star_name, designations, spectral_type, parallax, parsecs, "
            " light_years, app_magnitude, ra, dec) "
            "VALUES ('Test Star', 'HD 1', 'K0V', 200.0, 5.0, 16.3, 5.5, "
            "        '00 00 00.0', '+00 00 00.0')"
        )
        self.conn.commit()
        self._orig_lookup = calc.compute_lookup_star_for_distance

    def tearDown(self):
        calc.compute_lookup_star_for_distance = self._orig_lookup
        super().tearDown()

    def _run(self, limit_ly, centre_ly=_CENTRE_LY):
        calc.compute_lookup_star_for_distance = _fake_centre(centre_ly)
        return calc.compute_stars_within_distance_of_star("Test Centre", limit_ly)

    def test_sol_is_in_range_results(self):
        """The regression this fixes: Sol was absent from every opt-19 result."""
        res = self._run(15.0)
        self.assertNotIn("error", res)
        sol = [s for s in res["stars"] if s["Star Name"] == "Sol"]
        self.assertEqual(len(sol), 1, "expected exactly one synthetic Sol row")
        row = sol[0]
        self.assertAlmostEqual(row["Distance"], _CENTRE_LY, places=6)
        self.assertEqual(row["Spectral Type"], "G2V")
        self.assertEqual(row["Star Designations"], "Sun")
        self.assertEqual((row["x"], row["y"], row["z"]), (0.0, 0.0, 0.0))
        # It participates in the normal sort and the count, like any other row.
        self.assertEqual(res["count"], len(res["stars"]))
        self.assertEqual([s["Distance"] for s in res["stars"]],
                         sorted(s["Distance"] for s in res["stars"]))

    def test_sol_omitted_when_out_of_range(self):
        """A 5 ly search from a centre 11.91 ly out must not reach Sol."""
        res = self._run(5.0)
        self.assertEqual([s for s in res["stars"] if s["Star Name"] == "Sol"], [])

    def test_sol_centre_excludes_itself(self):
        """Centring on Sol gives distance 0, caught by the existing 0.001 ly floor."""
        res = self._run(20.0, centre_ly=0.0)
        self.assertNotIn("error", res)
        self.assertEqual([s for s in res["stars"] if s["Star Name"] == "Sol"], [])

    def test_parsecs_recovers_sols_true_absolute_magnitude(self):
        """`parsecs` is 1 AU in pc — the value the magnitude preps depend on.

        `M = V + 5 - 5*log10(pc)` must land on Sol's M_V of 4.83. If someone
        "corrects" `parsecs` to 0 or to the distance-from-centre, the HR diagram and
        night sky silently place Sol at an absurd luminosity instead of erroring.
        """
        row = next(s for s in self._run(15.0)["stars"] if s["Star Name"] == "Sol")
        abs_mag = row["app_magnitude"] + 5.0 - 5.0 * math.log10(row["parsecs"])
        self.assertAlmostEqual(abs_mag, 4.83, places=2)

    def test_night_sky_shows_sol_exactly_once(self):
        """`prepare_sky_from_star` must no longer append its own Sol on top."""
        sky = viz.prepare_sky_from_star(self._run(15.0), mag_limit=6.0)
        sol = [s for s in sky["stars"] if s["name"] == "Sol"]
        self.assertEqual(len(sol), 1, "Sol appears twice — the special case is back")
        # Same magnitude the removed special case hard-coded: 4.83 at 11.91 ly.
        expected = 4.83 - 5.0 + 5.0 * math.log10(_CENTRE_LY / 3.26156)
        self.assertAlmostEqual(sol[0]["mag"], expected, places=2)
        self.assertEqual(sol[0]["sp_class"], "G")

    def test_star_map_places_sol_at_minus_the_centre_vector(self):
        """The map shifts to centre-relative coords; Sol sits back at -(cx,cy,cz)."""
        res = self._run(15.0)
        sol = next(s for s in viz.prepare_star_map_from_result(res)["stars"]
                   if s["name"] == "Sol")
        self.assertAlmostEqual(sol["x"], -res["center_x"], places=6)
        self.assertAlmostEqual(sol["y"], -res["center_y"], places=6)
        self.assertAlmostEqual(sol["z"], -res["center_z"], places=6)
        self.assertAlmostEqual(sol["ly"], _CENTRE_LY, places=6)

    def test_map_flags_sol_for_the_star_marker(self):
        """`is_sol` drives the ★ overlay in the chart canvases — nothing else."""
        stars = viz.prepare_star_map_from_result(self._run(15.0))["stars"]
        flagged = [s["name"] for s in stars if s.get("is_sol")]
        self.assertEqual(flagged, ["Sol"])

    def test_sol_centred_map_does_not_flag_sol(self):
        """opt 18: Sol is the centre and already has its gold ★ — no second one."""
        res = calc.compute_stars_within_distance_of_sol(50.0)
        stars = viz.prepare_star_map_from_result(res)["stars"]
        self.assertEqual([s for s in stars if s.get("is_sol")], [])

    def test_hr_diagram_carries_sol_at_its_true_point(self):
        # The HR prep needs a Teff for "G2V", which comes from `main_sequence_stars`
        # — auto-seeding is off in this tmp DB, so seed the one row it looks up.
        db._seed_main_sequence(
            self.conn, pathlib.Path(__file__).resolve().parents[1]
            / "propertiesOfMainSequenceStars.csv")
        self.conn.commit()
        hr = viz.prepare_hr_from_stars(self._run(15.0))
        sol = [p for p in hr["points"] if p["name"] == "Sol"]
        self.assertEqual(len(sol), 1)
        self.assertAlmostEqual(sol[0]["abs_mag"], 4.83, places=2)


class GcnsSolRowTest(_TmpDbTest):
    """GCNS M4c / `query.py gcns-stars-within-star` over `gcns_stars`."""

    def setUp(self):
        super().setUp()
        # Centre + one neighbour, both real catalogue rows. RA/Dec are decimal
        # degrees in gcns_stars (unlike star_systems' sexagesimal strings).
        self.conn.executemany(
            "INSERT INTO gcns_stars (gaia_source_id, ra, dec, light_years, dist_pc, "
            "star_name, spectral_type, in_gcns, in_simbad, distance_method, gcns_table) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'gcns_bayesian', 'main')",
            [(1, 0.0, 0.0, _CENTRE_LY, _CENTRE_LY / 3.26156, "Centre Star", "G8V"),
             (2, 0.0, 0.0, _CENTRE_LY + 2.0, 4.3, "Neighbour", "M3V")],
        )
        self.conn.commit()

    def test_sol_row_is_present_and_flagged_synthetic(self):
        res = databases.compute_gcns_stars_within_star(source_id=1, limit_ly=15.0)
        self.assertNotIn("error", res)
        sol = [s for s in res["stars"] if s["star_name"] == "Sol"]
        self.assertEqual(len(sol), 1)
        row = sol[0]
        self.assertAlmostEqual(row["Distance"], _CENTRE_LY, places=6)
        self.assertEqual(row["spectral_type"], "G2V")
        self.assertEqual(row["app_magnitude"], -26.74)
        self.assertEqual((row["x"], row["y"], row["z"]), (0.0, 0.0, 0.0))
        self.assertEqual(row["dist_pc"], 0.0)
        self.assertEqual(row["light_years"], 0.0)
        # Flagged so it can never be read as catalogue astrometry.
        self.assertIs(row["in_gcns"], False)
        self.assertEqual(row["distance_method"], "synthetic_sol_origin")
        self.assertEqual(res["count"], len(res["stars"]))

    def test_unfillable_gcns_fields_are_null_not_fabricated(self):
        """No Gaia id, no Bayesian distance, no Gaia photometry — none exist."""
        res = databases.compute_gcns_stars_within_star(source_id=1, limit_ly=15.0)
        row = next(s for s in res["stars"] if s["star_name"] == "Sol")
        for field in ("gaia_source_id", "parallax", "parallax_error",
                      "dist_lo_pc", "dist_hi_pc", "phot_g_mean_mag",
                      "phot_bp_mean_mag", "phot_rp_mean_mag", "rv_kms",
                      "wd_prob", "astrom_reliable_prob", "system_id",
                      "n_components", "ra", "dec"):
            self.assertIsNone(row[field], f"{field} should be NULL for synthetic Sol")

    def test_sol_row_carries_the_full_row_shape(self):
        """It must not be a short dict — consumers index the standard columns."""
        res = databases.compute_gcns_stars_within_star(source_id=1, limit_ly=15.0)
        sol = next(s for s in res["stars"] if s["star_name"] == "Sol")
        real = next(s for s in res["stars"] if s["star_name"] == "Neighbour")
        self.assertEqual(set(sol), set(real))

    def test_sol_omitted_when_out_of_range(self):
        res = databases.compute_gcns_stars_within_star(source_id=1, limit_ly=5.0)
        self.assertEqual([s for s in res["stars"] if s["star_name"] == "Sol"], [])

    def test_distance_method_has_a_display_label(self):
        """`_meth` falls back to the RAW key, so a new method needs an entry.

        Without one the panel's Distance Method column would read
        `synthetic_sol_origin` at the user.
        """
        if not _qt_available():
            self.skipTest("PySide6 not available")
        from gui.panels.gcns import _meth
        self.assertEqual(_meth("synthetic_sol_origin"), "Synthetic (origin)")
        # The two catalogue methods must keep their labels.
        self.assertEqual(_meth("gcns_bayesian"), "Bayesian")
        self.assertEqual(_meth("gcns_missing_plx_inversion"), "1/ϖ inversion")

    def test_map_adapter_flags_sol_for_the_star_marker(self):
        """The GCNS adapter keys off `distance_method`, not the display name."""
        if not _qt_available():
            self.skipTest("PySide6 not available")
        from gui.panels.gcns import _gcns_map_stars
        res = databases.compute_gcns_stars_within_star(source_id=1, limit_ly=15.0)
        stars = _gcns_map_stars(res, center=True)
        self.assertEqual([s["name"] for s in stars if s.get("is_sol")], ["Sol"])


class SolStarMarkerCanvasTest(unittest.TestCase):
    """The ★ overlay builds on every chart/map canvas, in 2D and 3D.

    Guards the reason it is an overlay rather than a per-point marker swap: in 3D
    `do_3d_projection` depth-sorts sizes/colours but not paths, so swapping paths
    would drift the ★ onto the wrong star on rotation.
    """

    @classmethod
    def setUpClass(cls):
        if not _qt_available() or not _mpl_available():
            raise unittest.SkipTest("PySide6 / matplotlib not available")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _stars(self):
        from core.shared import sp_color
        return [
            {"name": "Centre", "desig": "", "sp_type": "", "color": "#FFD700",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Other", "desig": "", "sp_type": "M3V",
             "color": sp_color("M3V"), "ly": 4.0, "x": 4.0, "y": 0.0, "z": 0.0},
            {"name": "Sol", "desig": "Sun", "sp_type": "G2V",
             "color": sp_color("G2V"), "ly": 6.0, "x": -6.0, "y": 0.0, "z": 0.0,
             "is_sol": True},
        ]

    def test_every_canvas_draws_the_star_overlay(self):
        from gui.visualizations import plot_helpers as ph
        stars = self._stars()
        builders = [
            lambda s: ph.make_star_chart_canvas(None, s, limit_ly=10.0),
            lambda s: ph.make_star_chart_canvas(None, s, limit_ly=10.0,
                                                legend_filter=True),
            lambda s: ph.make_star_chart_3d_canvas(None, s, limit_ly=10.0),
            lambda s: ph.make_star_chart_3d_canvas(None, s, limit_ly=10.0,
                                                   legend_filter=True),
            lambda s: ph.make_star_map_canvas(None, s),
            lambda s: ph.make_star_map_3d_canvas(None, s),
        ]
        for i, build in enumerate(builders):
            with self.subTest(builder=i):
                out = build(stars)
                canvas = out[0]
                canvas.figure.canvas.draw()   # a bad path/size list raises here
                markers = [c for c in canvas.figure.axes[0].collections
                           if getattr(c, "_sol_overlay", False)]
                self.assertEqual(len(markers), 1)

    def test_no_overlay_without_the_flag(self):
        """An unflagged star list must build byte-identically to before."""
        from gui.visualizations import plot_helpers as ph
        plain = [dict(s) for s in self._stars()]
        for s in plain:
            s.pop("is_sol", None)
        canvas, _ = ph.make_star_chart_canvas(None, plain, limit_ly=10.0)
        canvas.figure.canvas.draw()
        self.assertEqual([c for c in canvas.figure.axes[0].collections
                          if getattr(c, "_sol_overlay", False)], [])


if __name__ == "__main__":
    unittest.main()
