# tests/test_search.py — offline coverage for the Phase G search/filter functions.
#
# Covers core.shared.spectral_where / spectral_adql (pure), the DB-backed
# search_star_systems / search_hwc (temp DB, no network, auto-seed disabled), and
# search_exoplanets with the TAP fetch mocked (no network). Mirrors the DB-setup
# pattern in tests/test_gcns.py.

import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.databases as databases
from core.shared import (spectral_where, spectral_adql, spectral_leading_class,
                         _SP_CLASS_PREFIXES, _SP_DISPLAY_LETTERS,
                         _SPECTRAL_CHIP_LETTERS)


# ── pure spectral-clause builders (no DB) ────────────────────────────────────

class SpectralClauseTest(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(spectral_where("sp", [], ""), ("", []))
        self.assertEqual(spectral_where("sp", None, None), ("", []))
        self.assertEqual(spectral_adql("st", [], ""), "")

    def test_single_letter(self):
        # GLOB (case-sensitive), not LIKE — one term per allowed luminosity prefix,
        # so 'dM6'/'sdM3.0' bucket under M while degenerate 'DA'/'DZ' do not.
        frag, params = spectral_where("sp", ["G"], "")
        self.assertEqual(frag, "((" + " OR ".join(["sp GLOB ?"] * len(_SP_CLASS_PREFIXES)) + "))")
        self.assertEqual(params, [f"{p}G*" for p in _SP_CLASS_PREFIXES])
        self.assertIn("G*", params)
        self.assertIn("dG*", params)
        self.assertNotIn("LIKE", frag)   # LIKE is case-insensitive → would fuse d/D

    def test_two_letters_or(self):
        frag, params = spectral_where("sp", ["G", "K"], "")
        self.assertEqual(frag.count("sp GLOB ?"), 2 * len(_SP_CLASS_PREFIXES))
        self.assertEqual(params,
                         [f"{p}G*" for p in _SP_CLASS_PREFIXES]
                         + [f"{p}K*" for p in _SP_CLASS_PREFIXES])

    def test_other_clause(self):
        # Other is the EXACT complement over ALL chip letters (not just selected).
        frag, params = spectral_where("sp", ["Other"], "")
        self.assertIn("sp IS NULL OR NOT (", frag)
        self.assertEqual(len(params), 7 * len(_SP_CLASS_PREFIXES))
        self.assertEqual(params[:2], ["O*", "dO*"])
        self.assertIn("dM*", params)

    def test_refine_only(self):
        frag, params = spectral_where("sp", [], "V")
        self.assertEqual(frag, "sp LIKE ? ESCAPE '\\'")
        self.assertEqual(params, ["%V%"])

    def test_class_and_refine(self):
        frag, params = spectral_where("sp", ["M"], "5.5")
        expected = "((" + " OR ".join(["sp GLOB ?"] * len(_SP_CLASS_PREFIXES)) + "))"
        self.assertEqual(frag, expected + " AND sp LIKE ? ESCAPE '\\'")
        self.assertEqual(params, [f"{p}M*" for p in _SP_CLASS_PREFIXES] + ["%5.5%"])

    def test_refine_escapes_wildcards(self):
        frag, params = spectral_where("sp", [], "5_0%")
        self.assertEqual(params, ["%5\\_0\\%%"])

    def test_leading_class_strips_luminosity_prefixes(self):
        # 'd'/'sd'/'esd'/'usd' = dwarf/subdwarf luminosity prefixes (Yerkes/Gliese).
        for sp, want in [("dM6", "M"),        # Wolf 359
                         ("dM4", "M"),        # Ross 128
                         ("sdM3.0", "M"), ("esdM2.0", "M"), ("usdM0.0", "M"),
                         ("d/sdM0", "M"), ("sd:G3", "G"), ("(sd)M1.5V", "M"),
                         ("s/sdM7", "M"), ("sdK", "K"), ("sdF8", "F"),
                         ("sdG0", "G"), ("dMe", "M")]:
            self.assertEqual(spectral_leading_class(sp), want, sp)

    def test_leading_class_am_ap_first_letter(self):
        # k/h/m = Am/Ap line-type notation (Ca-K / hydrogen / metallic), NOT a
        # luminosity prefix and NOT a binarity marker. First letter wins, matching
        # _SP_PATTERN which drives BC/Teff/HZ/HR elsewhere — so kA5hF0mF2 -> A,
        # deliberately not the (astronomically better) hydrogen-line type F.
        self.assertEqual(spectral_leading_class("kA5hF0mF2"), "A")
        self.assertEqual(spectral_leading_class("hA5VkA2mA3"), "A")
        self.assertEqual(spectral_leading_class("kB8hB8HeA0VSi"), "B")
        self.assertEqual(spectral_leading_class("kF0hF2mF2(III)"), "F")
        self.assertEqual(spectral_leading_class("knA2h(eA)VSr((Eu))"), "A")

    def test_leading_class_white_dwarfs_are_not_prefixed(self):
        # REGRESSION PIN: uppercase 'D' is the DEGENERATE prefix, never a luminosity
        # prefix. These must never resolve to a letter chip.
        for sp in ["DA", "DZ7.5", "DQ", "DC", "DA3.5", "DAZ", "DAH",
                   "DA+DA", "DA+dM", "DC+M:", "D"]:
            self.assertIsNone(spectral_leading_class(sp), sp)

    def test_leading_class_brown_dwarfs_and_blanks(self):
        for sp in ["L0", "T8", "Y1", "L1.5", "", None, "   ", "m4.3", "m3 V"]:
            self.assertIsNone(spectral_leading_class(sp), repr(sp))

    def test_leading_class_plain_types_unchanged(self):
        for sp, want in [("M5.5Ve", "M"), ("M3+", "M"), ("G2V", "G"),
                         ("K1V", "K"), ("A0", "A"), ("O9.5", "O")]:
            self.assertEqual(spectral_leading_class(sp), want, sp)

    def test_adql_injection_sanitized(self):
        # A quote in the refine text must not escape the ADQL string literal.
        clause = spectral_adql("st_spectype", ["M"], "5'V")
        self.assertNotIn("'5'", clause)            # the embedded quote is stripped
        self.assertIn("st_spectype LIKE '%5V%'", clause)
        self.assertIn("st_spectype LIKE 'M%'", clause)


# ── DB-backed searches (temp DB, no network) ─────────────────────────────────

class SearchDBTest(unittest.TestCase):

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

    def _seed_star_systems(self):
        rows = [
            # star_name, designations, spectral_type, light_years, app_magnitude
            ("Alpha Centauri A", "GJ 559 A, HD 128620, HIP 71683", "G2V",    4.36, 0.01),
            ("Proxima Centauri", "GJ 551, HIP 70890",              "M5.5Ve", 4.24, 11.13),
            ("Sirius B",         "GJ 244 B",                       "DA2",    8.60, 8.44),
            ("Mystery Star",     "HD 999",                         None,     10.0, 5.0),
            ("Tau Ceti",         "GJ 71, HD 10700, HIP 8102",      "G8.5V",  11.91, 3.50),
            # Prefixed types — the originally-reported bug. Lowercase 'd'/'sd' are
            # luminosity prefixes (M dwarfs); uppercase 'D' is degenerate (white
            # dwarf) and must NOT be treated as one. SQLite LIKE cannot tell them
            # apart, which is why the chip SQL uses GLOB.
            ("Wolf 359",         "GJ 406",                         "dM6",    7.86, 13.53),
            ("Ross 128",         "GJ 447",                         "dM4",   11.01, 11.13),
            ("Kapteyn Star",     "GJ 191",                         "sdM1.0",12.83, 8.85),
            ("Van Maanen 2",     "GJ 35",                          "DZ7.5", 14.07, 12.38),
            ("65 UMa",           "HD 103483",                      "hA5VkA2mA3", 20.0, 6.5),
            ("Teide 1",          "BD test",                        "sdL0",  30.0, 18.0),
        ]
        self.conn.executemany(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "light_years, app_magnitude) VALUES (?, ?, ?, ?, ?)", rows)
        self.conn.commit()

    def test_sql_and_python_rules_agree(self):
        # The GLOB fragment and spectral_leading_class must never disagree — they are
        # the two halves of one rule. Exercised over an in-memory table.
        # Covers EVERY prefix in _SP_CLASS_PREFIXES — in particular d/sd, s/sd, (sd)
        # and kn, which contain '/', '(' and ')'. Those are the characters where a
        # GLOB-metacharacter mistake would hide, so the "no metacharacters in the
        # prefix list" claim is only load-bearing if they are exercised through SQL.
        samples = ["dM6", "sdM3.0", "esdM2.0", "usdM0.0", "kA5hF0mF2", "hA5VkA2mA3",
                   "knA2h(eA)VSr((Eu))", "d/sdM0", "s/sdM7", "(sd)M1.5V", "sd:G3",
                   "sdF8", "sdG0", "sdK", "dMe",
                   "DA", "DZ7.5", "DA+dM", "DC+M:", "L0", "T8", "sdL0",
                   "M5.5Ve", "M3+", "G2V", "m4.3", ""]
        for prefix in _SP_CLASS_PREFIXES:      # no prefix left untested
            self.assertTrue(any(s.startswith(prefix) and
                                spectral_leading_class(s) is not None for s in samples),
                            f"prefix {prefix!r} not exercised")
        # Go through the PROJECT connection, so the test pins this app's SQLite
        # semantics (collation / pragmas) rather than a bare in-memory default.
        conn = db.get_conn()
        conn.execute("DROP TABLE IF EXISTS t")
        conn.execute("CREATE TABLE t (sp TEXT)")
        conn.executemany("INSERT INTO t VALUES (?)", [(s,) for s in samples])
        for letter in ["O", "B", "A", "F", "G", "K", "M"]:
            frag, params = spectral_where("sp", [letter], "")
            got = {r[0] for r in conn.execute(f"SELECT sp FROM t WHERE {frag}", params)}
            want = {s for s in samples if spectral_leading_class(s) == letter}
            self.assertEqual(got, want, f"chip {letter}")
        # Other is the exact complement: chips + Other partition the table, no overlap.
        ofrag, oparams = spectral_where("sp", ["Other"], "")
        other = {r[0] for r in conn.execute(f"SELECT sp FROM t WHERE {ofrag}", oparams)}
        want_other = {s for s in samples if spectral_leading_class(s) is None}
        self.assertEqual(other, want_other)
        chips = {s for s in samples if spectral_leading_class(s) is not None}
        self.assertEqual(chips & other, set())
        self.assertEqual(chips | other, set(samples))

    def _names(self, result):
        return [s["star_name"] for s in result["stars"]]

    # star_systems ------------------------------------------------------------

    def test_empty_table_error(self):
        result = databases.search_star_systems({"spectral_classes": ["M"]})
        self.assertIn("error", result)
        self.assertIn("option 50", result["error"])

    def test_class_m_excludes_g_and_whitedwarf(self):
        self._seed_star_systems()
        # dM6 / dM4 / sdM1.0 are M dwarfs behind a luminosity prefix — they belong
        # under M. DZ7.5 / DA2 are DEGENERATE (white dwarfs) and must never appear.
        self.assertEqual(self._names(databases.search_star_systems({"spectral_classes": ["M"]})),
                         ["Proxima Centauri", "Wolf 359", "Ross 128",
                          "Kapteyn Star"])

    def test_other_matches_whitedwarf_and_null(self):
        self._seed_star_systems()
        names = self._names(databases.search_star_systems({"spectral_classes": ["Other"]}))
        # White dwarfs (DA2, DZ7.5), NULL, and the L-type brown dwarf stay in Other;
        # the prefixed M dwarfs must have LEFT Other for chip M.
        self.assertCountEqual(names, ["Sirius B", "Mystery Star",
                                      "Van Maanen 2", "Teide 1"])

    def test_designation_prefix_after_comma(self):
        self._seed_star_systems()
        # "HD 1" must match Alpha Cen A (HD 128620) and Tau Ceti (HD 10700),
        # via the after-comma token rule — but NOT Mystery Star (HD 999).
        names = self._names(databases.search_star_systems({"designation_prefix": "HD 1"}))
        self.assertCountEqual(names, ["Alpha Centauri A", "Tau Ceti", "65 UMa"])

    def test_designation_prefix_with_name_leading_designations(self):
        """Post-fix, opt-50 writes SIMBAD's "NAME <x>" first in `designations`, so a
        catalog prefix that used to match the leading-token branch now matches the
        after-comma branch instead. Both branches are in the clause, so nothing is lost
        — and the common name itself becomes searchable."""
        self.conn.executemany(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "light_years, app_magnitude) VALUES (?, ?, ?, ?, ?)",
            [("* bet CVn", "NAME Chara, GJ 475, HD 109358, HIP 61317", "G0V", 27.53, 4.26),
             ("Tau Ceti",  "GJ 71, HD 10700, HIP 8102",                "G8.5V", 11.91, 3.50)])
        self.conn.commit()

        # GJ is no longer the leading token for * bet CVn — still found.
        self.assertCountEqual(
            self._names(databases.search_star_systems({"designation_prefix": "GJ 475"})),
            ["* bet CVn"])
        # The common name is now searchable, both with and without the NAME prefix.
        self.assertCountEqual(
            self._names(databases.search_star_systems({"designation_prefix": "NAME Chara"})),
            ["* bet CVn"])
        # A star with no NAME token is unaffected by the leading-token branch.
        self.assertCountEqual(
            self._names(databases.search_star_systems({"designation_prefix": "GJ 71"})),
            ["Tau Ceti"])

    def test_ly_range_and_sort(self):
        self._seed_star_systems()
        result = databases.search_star_systems({"ly_max": 9.0})
        self.assertEqual(self._names(result),
                         ["Proxima Centauri", "Alpha Centauri A", "Wolf 359", "Sirius B"])

    def test_mag_range(self):
        self._seed_star_systems()
        names = self._names(databases.search_star_systems({"mag_min": 8.0}))
        self.assertCountEqual(names, ["Proxima Centauri", "Sirius B", "Wolf 359",
                                      "Ross 128", "Kapteyn Star", "Van Maanen 2",
                                      "Teide 1"])

    def test_cap_detection(self):
        self._seed_star_systems()
        with mock.patch.object(databases, "_SEARCH_CAP", 2):
            result = databases.search_star_systems({"mag_min": -30})  # matches all 5
            self.assertTrue(result["capped"])
            self.assertEqual(len(result["stars"]), 2)

    # hwc ---------------------------------------------------------------------

    def _seed_hwc(self):
        self.conn.execute(
            "CREATE TABLE hwc (P_NAME TEXT, P_ESI TEXT, P_HABITABLE TEXT, "
            "P_HABZONE_CON TEXT, P_HABZONE_OPT TEXT, P_MASS TEXT, P_RADIUS TEXT, "
            "P_TEMP_EQUIL TEXT, S_NAME TEXT, S_NAME_HD TEXT, S_NAME_HIP TEXT, "
            "S_TYPE TEXT, S_DISTANCE TEXT)")
        rows = [
            # name, esi, hab, con, opt, mass, radius, teq, star, hd, hip, sptype, dist_pc
            ("Earth b",   "0.99", "1", "1", "1", "1.0", "1.0", "255", "Sun",   "", "", "G2V", "0.0"),
            ("Blank b",   "",     "1", "1", "1", "",    "",    "",    "BlS",   "", "", "M3V", "2.0"),
            ("Hot b",     "0.50", "0", "0", "1", "5.0", "2.0", "400", "HotS",  "", "", "K2V", "3.0"),
            ("Far b",     "0.85", "1", "1", "1", "1.2", "1.1", "260", "FarS",  "", "", "M5V", "40.0"),
        ]
        self.conn.executemany(
            "INSERT INTO hwc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def test_hwc_empty_error(self):
        result = databases.search_hwc({"esi_min": 0.8})
        self.assertIn("error", result)
        self.assertIn("option 52", result["error"])

    def test_hwc_esi_excludes_blank_not_as_zero(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"esi_min": 0.8})["stars"]]
        # Earth (0.99) and Far (0.85) qualify; Blank ('') must NOT match as 0.
        self.assertCountEqual(names, ["Earth b", "Far b"])

    def test_hwc_habitable_flag(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"habitable": True})["stars"]]
        self.assertCountEqual(names, ["Earth b", "Blank b", "Far b"])

    def test_hwc_sorted_esi_desc_blank_last(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({})["stars"]]
        self.assertEqual(names, ["Earth b", "Far b", "Hot b", "Blank b"])

    def test_hwc_ly_max(self):
        self._seed_hwc()
        # Far b at 40 pc ≈ 130 ly excluded by ly_max=20.
        names = [s["P_NAME"] for s in databases.search_hwc({"ly_max": 20})["stars"]]
        self.assertNotIn("Far b", names)

    def test_hwc_spectral_class(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"spectral_classes": ["M"]})["stars"]]
        self.assertCountEqual(names, ["Blank b", "Far b"])


# ── exoplanet search (TAP mocked, no network) ────────────────────────────────

class SearchExoplanetTest(unittest.TestCase):

    def test_where_and_top_built(self):
        captured = {}

        def _fake_tap(table, where, order_by=None, timeout=60, top=None, select="*"):
            captured.update(table=table, where=where, order_by=order_by, top=top, select=select)
            return [{"pl_name": "x"}]

        with mock.patch.object(databases, "_query_tap", _fake_tap):
            databases.search_exoplanets({
                "pl_bmasse_min": 1, "pl_rade_max": 2,
                "discoverymethod": "Transit",
                "spectral_classes": ["M"], "sy_dist_max": 15,
            })
        self.assertEqual(captured["table"], "pscomppars")
        self.assertEqual(captured["top"], databases._EXO_SEARCH_CAP + 1)  # cap+1 fetch
        self.assertEqual(captured["order_by"], "pl_orbsmax")
        self.assertIn("pl_bmasse >= 1.0", captured["where"])
        self.assertIn("pl_rade <= 2.0", captured["where"])
        self.assertIn("sy_dist <= 15.0", captured["where"])
        self.assertIn("discoverymethod = 'Transit'", captured["where"])
        self.assertIn("st_spectype LIKE 'M%'", captured["where"])

    def test_empty_filters_default_where(self):
        captured = {}

        def _fake_tap(table, where, **kw):
            captured["where"] = where
            return []

        with mock.patch.object(databases, "_query_tap", _fake_tap):
            databases.search_exoplanets({})
        self.assertEqual(captured["where"], "pl_name IS NOT NULL")

    def test_any_method_ignored(self):
        captured = {}
        with mock.patch.object(databases, "_query_tap",
                               lambda table, where, **kw: captured.update(where=where) or []):
            databases.search_exoplanets({"discoverymethod": "Any"})
        self.assertNotIn("discoverymethod", captured["where"])

    def test_network_error_classified(self):
        import requests

        def _boom(*a, **k):
            raise requests.exceptions.Timeout("slow")

        with mock.patch.object(databases, "_query_tap", _boom):
            result = databases.search_exoplanets({"pl_rade_min": 1})
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"].lower())

    def test_cap_flag(self):
        cap = databases._EXO_SEARCH_CAP
        # Exactly `cap` matches must NOT be reported as capped (the off-by-one fix).
        exact = [{"pl_name": f"p{i}"} for i in range(cap)]
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: exact):
            result = databases.search_exoplanets({})
        self.assertFalse(result["capped"])
        self.assertEqual(result["count"], cap)
        # The fetch asks for cap+1; if that many come back, report capped and slice.
        over = [{"pl_name": f"p{i}"} for i in range(cap + 1)]
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: over):
            result = databases.search_exoplanets({})
        self.assertTrue(result["capped"])
        self.assertEqual(result["count"], cap)


if __name__ == "__main__":
    unittest.main()


# ── Part 2 · display-class rule (colour / legend bucketing) ──────────────────

class SpectralDisplayClassTest(unittest.TestCase):
    """The wider letter set used for dot colour and legend bucketing.

    Distinct from the search chips: a chip must send `DA` to "Other" (a white dwarf
    is not an OBAFGKM star), but a chart must still PAINT it — using the chip set
    for colour would turn every white dwarf, brown dwarf and Wolf-Rayet grey.
    """

    def test_prefixed_types_resolve(self):
        for sp, want in [("dM6", "M"), ("dM4", "M"), ("sdM3.0", "M"),
                         ("sdL0", "L"), ("esdL7", "L"), ("kA5hF0mF2", "A"),
                         ("dC", "C"), ("dC:", "C"), ("dC-J_CH5", "C")]:
            self.assertEqual(spectral_leading_class(sp, _SP_DISPLAY_LETTERS), want, sp)

    def test_non_main_sequence_classes_keep_their_colour(self):
        """REGRESSION PIN for the Part 1 trap.

        The naive fix (reusing the OBAFGKM-only chip rule for colour) would send
        all of these to None → grey: 19,674 rows across the catalogues, i.e. every
        white dwarf, brown dwarf and Wolf-Rayet on every chart.
        """
        for sp, want in [("DA", "D"), ("DZ7.5", "D"), ("DQ", "D"), ("DA+dM", "D"),
                         ("L0", "L"), ("T8", "T"), ("Y0", "Y"), ("WN", "W")]:
            self.assertEqual(spectral_leading_class(sp, _SP_DISPLAY_LETTERS), want, sp)

    def test_non_spectral_labels_do_not_resolve(self):
        """'Red Giant' is a row label in the Honorverse hyper-limit table and is fed
        through the same colour helper. Including 'R'/'S' in the display set (they
        have ZERO catalogue rows) made it resolve to carbon class R."""
        for label in ["Red Giant", "Supergiant", "Subdwarf", "Unknown"]:
            self.assertIsNone(spectral_leading_class(label, _SP_DISPLAY_LETTERS), label)

    def test_default_arg_unchanged_is_part1_behaviour(self):
        """The `letters` parameter is additive: omitting it must reproduce Part 1
        exactly, or the search chips silently change."""
        for sp in ["dM6", "sdM3.0", "kA5hF0mF2", "DA", "DZ7.5", "L0", "T8",
                   "dC:", "Y0", "M5.5Ve", "m4.3", ""]:
            self.assertEqual(spectral_leading_class(sp),
                             spectral_leading_class(sp, _SPECTRAL_CHIP_LETTERS), sp)

    def test_colour_helpers_agree_with_the_rule(self):
        from core.viz import _sp_color, _SPECTRAL_COLORS
        from core.calculators import _star_map_color
        self.assertEqual(_sp_color("dM6"), _SPECTRAL_COLORS["M"])
        self.assertEqual(_sp_color("DA"), _SPECTRAL_COLORS["D"])
        self.assertEqual(_sp_color("Red Giant"), "#AAAAAA")
        # _star_map_color is a deliberately separate palette; the ADDITIVE guarantee
        # is that no letter which already had an entry changes colour.
        for sp, unchanged in [("G2V", "#fff4c2"), ("M4V", "#ff9d6c"),
                              ("A1V", "#cad7ff"), ("DA", "#dfe6ff"), ("", "#cccccc")]:
            self.assertEqual(_star_map_color(sp), unchanged, sp)
        # …and letters that were falling through to grey now resolve.
        self.assertEqual(_star_map_color("L0"), "#ff4500")
        self.assertEqual(_star_map_color("dM6"), "#ff9d6c")

    def test_cross_site_agreement(self):
        """§4b atomicity: the legend, highlight-suppression and label paths agree
        only by producing the SAME class string. A partial conversion breaks legend
        filtering silently — no error, no failure."""
        from gui.visualizations.plot_helpers import _display_class
        for sp in ["dM6", "sdM3.0", "DA", "L0", "dC:", "", "Red Giant"]:
            self.assertEqual(_display_class(sp),
                             spectral_leading_class(sp, _SP_DISPLAY_LETTERS), sp)

    def test_night_sky_sp_class_is_prefix_aware(self):
        """`sp_class` (core/viz.py) emits a VALUE, not a colour — its only existing
        assertions were all "G", so it was revert-green."""
        import core.viz as viz
        r = viz.prepare_sky_from_star({
            "center": "X", "center_x": 0.0, "center_y": 0.0, "center_z": 0.0,
            "stars": [{"Star Name": "Wolf 359", "Spectral Type": "dM6",
                       "app_magnitude": 13.53, "parsecs": 2.41,
                       "x": 4.0, "y": 4.8, "z": -2.0}],
        }, mag_limit=99.0)
        wolf = [s for s in r["stars"] if s["name"] == "Wolf 359"]
        self.assertTrue(wolf, "fixture star was filtered out")
        self.assertEqual(wolf[0]["sp_class"], "M")
