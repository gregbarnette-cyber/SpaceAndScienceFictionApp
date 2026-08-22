# tests/test_rv_precision.py — CR-10.3 per-star RV-precision catalog (loader/matcher, offline).

import json
import os
import tempfile
import unittest

import core.rv_precision_tables as rvt


class LoaderTest(unittest.TestCase):
    def test_seed_is_hd69830_only(self):
        seed = rvt.load_rv_precision_catalog(None)
        self.assertEqual([s["id"] for s in seed["stars"]], ["HD 69830"])
        self.assertEqual(seed["stars"][0]["rv_precision_ms"], 0.81)

    def test_external_file_replaces_seed(self):
        cat = {"stars": [{"main_id": "HD 999", "aliases": [], "rv_precision_ms": 2.0,
                          "floor_kind": "measured_residual_rms", "citation": "Test 2026"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cat, f)
            path = f.name
        try:
            loaded = rvt.load_rv_precision_catalog(path)
            self.assertEqual([s["main_id"] for s in loaded["stars"]], ["HD 999"])  # wholesale replace
            self.assertIsNone(rvt.match_rv_precision(loaded, "HD 69830", {"HD": "HD 69830"}))
        finally:
            os.unlink(path)

    def test_bad_path_curated_error(self):
        r = rvt.load_rv_precision_catalog("/nonexistent/xyz.json")
        self.assertIn("error", r)

    def test_invalid_json_curated_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
            path = f.name
        try:
            self.assertIn("error", rvt.load_rv_precision_catalog(path))
        finally:
            os.unlink(path)

    def test_no_stars_array_curated_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"schema_version": "1.0.0"}, f)
            path = f.name
        try:
            self.assertIn("error", rvt.load_rv_precision_catalog(path))
        finally:
            os.unlink(path)


class MatchTest(unittest.TestCase):
    def setUp(self):
        self.seed = rvt.load_rv_precision_catalog(None)

    def test_match_by_main_id_double_space(self):
        row = rvt.match_rv_precision(self.seed, "HD  69830", {"MAIN_ID": "HD  69830"})
        self.assertEqual(row["rv_precision_ms"], 0.81)

    def test_match_by_alias(self):
        row = rvt.match_rv_precision(self.seed, "Something", {"GJ": "GJ 302"})
        self.assertEqual(row["rv_precision_ms"], 0.81)

    def test_match_case_insensitive(self):
        row = rvt.match_rv_precision(self.seed, "hd 69830", None)
        self.assertEqual(row["rv_precision_ms"], 0.81)

    def test_no_match(self):
        self.assertIsNone(rvt.match_rv_precision(self.seed, "Random Star", {"HD": "HD 999999"}))

    def test_no_ids_returns_none(self):
        self.assertIsNone(rvt.match_rv_precision(self.seed, None, None))

    def test_malformed_row_skipped_best_effort(self):
        cat = {"stars": [
            {"main_id": "HD 111", "rv_precision_ms": None},        # malformed — skip
            {"main_id": "HD 111", "rv_precision_ms": "oops"},      # malformed — skip
            {"rv_precision_ms": 1.0},                              # no main_id (unmatchable, skipped)
            {"main_id": "HD 111", "aliases": [], "rv_precision_ms": 1.5, "citation": "OK"},
        ]}
        row = rvt.match_rv_precision(cat, "HD 111", {"HD": "HD 111"})
        self.assertEqual(row["rv_precision_ms"], 1.5)             # first VALID matching row wins

    def test_boolean_rv_precision_is_not_numeric(self):
        cat = {"stars": [{"main_id": "HD 1", "rv_precision_ms": True}]}
        self.assertIsNone(rvt.match_rv_precision(cat, "HD 1", None))  # bool excluded


class FloorSourceTest(unittest.TestCase):
    def test_seed_floor_source_string(self):
        seed = rvt.load_rv_precision_catalog(None)
        s = rvt.catalog_floor_source(seed["stars"][0])
        self.assertEqual(s, "per-star catalog: HD 69830 residual RMS 0.81 m/s [Lovis 2006]")

    def test_unknown_floor_kind_falls_back_to_raw(self):
        s = rvt.catalog_floor_source({"id": "X", "rv_precision_ms": 2.0, "floor_kind": "weird_kind"})
        self.assertIn("weird_kind", s)


if __name__ == "__main__":
    unittest.main()
