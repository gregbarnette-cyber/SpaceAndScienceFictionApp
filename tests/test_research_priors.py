# tests/test_research_priors.py — Phase R3 research-priors hook.
#
# R3-C1 scope (offline, pure): the formation-priors data contract validator
# (core.research_priors.validate_priors_contract) + the committed sample / identity
# fixtures. Later checkpoints append here: C2 ResearchPriors + get_priors, C3 the
# importer + status, etc. No engine is wired to priors until C4/C5.

import copy
import json
import os
import shutil
import tempfile
import unittest

from core.research_priors import (
    validate_priors_contract,
    compute_research_priors_ingest,
    get_research_priors_status,
    _REQUIRED_AXES,
    _REQUIRED_ZONES,
    _ORIGIN_CONTEXT_KEYS,
    _CACHE_PRIORS_NAME,
    _CACHE_META_NAME,
)
from core.priors import (
    DefaultPriors,
    ResearchPriors,
    PriorsUnavailable,
    get_priors,
)

# DefaultPriors data attributes that ResearchPriors must mirror (the contract that
# keeps the two interchangeable in core/generate.py).
_SAMPLING_ATTRS = (
    "spectral_class_weights", "n_planet_dist", "spacing_ratio",
    "mass_by_zone", "moon_count", "moon_mass_frac",
)

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")
_SAMPLE = os.path.join(_FIX, "research_priors_sample.json")
_IDENTITY = os.path.join(_FIX, "research_priors_identity.json")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestContractFixtures(unittest.TestCase):
    """The two committed fixtures must both be valid contracts."""

    def test_sample_validates(self):
        self.assertIsNone(validate_priors_contract(_load(_SAMPLE)))

    def test_identity_validates(self):
        self.assertIsNone(validate_priors_contract(_load(_IDENTITY)))

    def test_identity_sampling_axes_clone_defaults(self):
        # The identity fixture's sampling axes must equal DefaultPriors exactly —
        # this is what the R3-C4 "strict == permissive except the badge" test rests
        # on. (origin_priors is not part of DefaultPriors; checked separately.)
        from core.priors import DefaultPriors
        d = DefaultPriors()
        obj = _load(_IDENTITY)
        self.assertEqual(obj["spectral_class_weights"], d.spectral_class_weights)
        self.assertEqual({int(k): v for k, v in obj["n_planet_dist"].items()},
                         d.n_planet_dist)
        self.assertEqual(tuple(obj["spacing_ratio"]), d.spacing_ratio)
        self.assertEqual({z: tuple(v) for z, v in obj["mass_by_zone"].items()},
                         d.mass_by_zone)
        self.assertEqual(tuple(obj["moon_count"]), d.moon_count)
        self.assertEqual(tuple(obj["moon_mass_frac"]), d.moon_mass_frac)

    def test_fixtures_cover_every_origin_context_key(self):
        # Both fixtures should calibrate the full v1 context-key vocabulary so C5
        # has a complete reference. (A real dataset may omit keys → per-key
        # heuristic fallback; the fixtures are deliberately complete.)
        for path in (_SAMPLE, _IDENTITY):
            keys = set(_load(path)["origin_priors"])
            self.assertEqual(keys, set(_ORIGIN_CONTEXT_KEYS), path)


class TestValidatorRejects(unittest.TestCase):
    """Each malformed axis → a curated {'error': ...} dict (Phase-H idiom)."""

    def setUp(self):
        self.base = _load(_IDENTITY)

    def _bad(self, obj, needle=None):
        res = validate_priors_contract(obj)
        self.assertIsInstance(res, dict)
        self.assertIn("error", res)
        self.assertTrue(res["error"].startswith("research-priors contract:"))
        if needle:
            self.assertIn(needle, res["error"])
        return res

    # ── document / metadata ──
    def test_not_a_dict(self):
        self._bad([1, 2, 3])

    def test_missing_schema_version(self):
        o = copy.deepcopy(self.base); del o["schema_version"]
        self._bad(o, "schema_version")

    def test_unknown_schema_major(self):
        o = copy.deepcopy(self.base); o["schema_version"] = "2.0"
        self._bad(o, "schema_version")

    def test_missing_dataset_version(self):
        o = copy.deepcopy(self.base); del o["dataset_version"]
        self._bad(o, "dataset_version")

    # ── required axes ──
    def test_each_required_axis_missing(self):
        for axis in _REQUIRED_AXES:
            o = copy.deepcopy(self.base); del o[axis]
            self._bad(o, axis)

    def test_spectral_weights_non_positive(self):
        o = copy.deepcopy(self.base); o["spectral_class_weights"]["M"] = 0
        self._bad(o, "spectral_class_weights")

    def test_spectral_weights_empty(self):
        o = copy.deepcopy(self.base); o["spectral_class_weights"] = {}
        self._bad(o, "spectral_class_weights")

    def test_n_planet_dist_non_int_key(self):
        o = copy.deepcopy(self.base); o["n_planet_dist"] = {"two": 0.5}
        self._bad(o, "n_planet_dist")

    def test_n_planet_dist_all_zero(self):
        o = copy.deepcopy(self.base)
        o["n_planet_dist"] = {k: 0 for k in o["n_planet_dist"]}
        self._bad(o, "n_planet_dist")

    def test_n_planet_dist_negative(self):
        o = copy.deepcopy(self.base); o["n_planet_dist"]["3"] = -0.1
        self._bad(o, "n_planet_dist")

    def test_spacing_ratio_bad_shape(self):
        o = copy.deepcopy(self.base); o["spacing_ratio"] = [1.5]
        self._bad(o, "spacing_ratio")

    def test_spacing_ratio_lo_gt_hi(self):
        o = copy.deepcopy(self.base); o["spacing_ratio"] = [2.0, 1.4]
        self._bad(o, "spacing_ratio")

    def test_spacing_ratio_non_positive_lo(self):
        o = copy.deepcopy(self.base); o["spacing_ratio"] = [0.0, 2.0]
        self._bad(o, "spacing_ratio")

    def test_mass_by_zone_wrong_keys(self):
        o = copy.deepcopy(self.base); o["mass_by_zone"].pop("far")
        self._bad(o, "mass_by_zone")

    def test_mass_by_zone_lo_gt_hi(self):
        o = copy.deepcopy(self.base); o["mass_by_zone"]["hz"] = [9.0, 1.0]
        self._bad(o, "mass_by_zone")

    def test_moon_count_non_integer(self):
        o = copy.deepcopy(self.base); o["moon_count"] = [0, 5.5]
        self._bad(o, "moon_count")

    def test_moon_count_negative(self):
        o = copy.deepcopy(self.base); o["moon_count"] = [-1, 5]
        self._bad(o, "moon_count")

    def test_moon_mass_frac_non_positive(self):
        o = copy.deepcopy(self.base); o["moon_mass_frac"] = [0.0, 5e-4]
        self._bad(o, "moon_mass_frac")

    # ── origin_priors (optional, but validated when present) ──
    def test_origin_priors_optional(self):
        o = copy.deepcopy(self.base); del o["origin_priors"]
        self.assertIsNone(validate_priors_contract(o))

    def test_origin_priors_not_dict(self):
        o = copy.deepcopy(self.base); o["origin_priors"] = []
        self._bad(o, "origin_priors")

    def test_origin_priors_empty_list(self):
        o = copy.deepcopy(self.base)
        o["origin_priors"]["trojan:feasible"] = []
        self._bad(o, "origin_priors")

    def test_origin_priors_bad_plausibility(self):
        o = copy.deepcopy(self.base)
        o["origin_priors"]["trojan:feasible"] = [{"pathway": "x", "plausibility": "med"}]
        self._bad(o, "plausibility")

    def test_origin_priors_missing_pathway(self):
        o = copy.deepcopy(self.base)
        o["origin_priors"]["trojan:feasible"] = [{"plausibility": "low"}]
        self._bad(o, "pathway")

    # ── a numeric stored as bool must not pass _is_num ──
    def test_bool_is_not_a_number(self):
        o = copy.deepcopy(self.base); o["spectral_class_weights"]["M"] = True
        self._bad(o, "spectral_class_weights")


class TestResearchProvider(unittest.TestCase):
    """R3-C2: ResearchPriors builds from a contract and mirrors DefaultPriors."""

    def test_identity_provider_matches_defaults_exactly(self):
        # Provider parity: with the identity fixture, every DefaultPriors sampling
        # attribute exists on ResearchPriors with an EQUAL value (and matching
        # type) — the basis of the R3-C4 "strict == permissive except the badge".
        d = DefaultPriors()
        r = ResearchPriors.from_file(_IDENTITY)
        for attr in _SAMPLING_ATTRS:
            self.assertTrue(hasattr(r, attr), attr)
            self.assertEqual(getattr(r, attr), getattr(d, attr), attr)
            self.assertEqual(type(getattr(r, attr)), type(getattr(d, attr)), attr)

    def test_n_planet_dist_keys_are_int(self):
        r = ResearchPriors.from_file(_IDENTITY)
        self.assertTrue(all(isinstance(k, int) for k in r.n_planet_dist))
        # sorts numerically (not lexicographically) like DefaultPriors
        self.assertEqual([k for k, _ in sorted(r.n_planet_dist.items())],
                         list(range(11)))

    def test_provider_metadata_and_grounding(self):
        r = ResearchPriors.from_file(_IDENTITY)
        self.assertEqual(r.name, "RESEARCH")
        self.assertEqual(r.grounding, "research-calibrated")
        self.assertEqual(r.version, "identity-2026-06-24")
        self.assertEqual(r.schema_version, "1.0")

    def test_origin_priors_loaded(self):
        r = ResearchPriors.from_file(_IDENTITY)
        self.assertEqual(set(r.origin_priors), set(_ORIGIN_CONTEXT_KEYS))
        self.assertEqual(r.origin_priors["resonance:feasible"][0]["plausibility"],
                         "high")

    def test_sample_provider_differs_from_defaults(self):
        # The perturbed sample MUST differ from DefaultPriors on ≥1 sampling axis
        # (otherwise strict could never visibly change sampling).
        d = DefaultPriors()
        r = ResearchPriors.from_file(_SAMPLE)
        self.assertEqual(r.version, "sample-2026-06-24")
        self.assertTrue(any(getattr(r, a) != getattr(d, a) for a in _SAMPLING_ATTRS))

    def test_from_contract_rejects_invalid(self):
        bad = copy.deepcopy(_load(_IDENTITY)); del bad["spacing_ratio"]
        with self.assertRaises(ValueError):
            ResearchPriors.from_contract(bad)

    def test_origin_priors_not_shared_with_contract(self):
        # deepcopy guard — mutating the provider must not bleed back.
        r = ResearchPriors.from_file(_IDENTITY)
        r.origin_priors["trojan:feasible"].append({"x": 1})
        r2 = ResearchPriors.from_file(_IDENTITY)
        self.assertEqual(len(r2.origin_priors["trojan:feasible"]), 1)


class TestGetPriorsSelector(unittest.TestCase):
    """R3-C2: get_priors selects the right provider per policy."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _seed_cache(self, fixture):
        shutil.copy(fixture, os.path.join(self.tmp, _CACHE_PRIORS_NAME))

    def test_permissive_returns_defaults(self):
        p = get_priors("permissive")
        self.assertIsInstance(p, DefaultPriors)
        self.assertEqual(p.grounding, "default-extrapolation")

    def test_permissive_is_the_default(self):
        self.assertIsInstance(get_priors(), DefaultPriors)

    def test_strict_with_cache_returns_research(self):
        self._seed_cache(_SAMPLE)
        p = get_priors("strict", cache_dir=self.tmp)
        self.assertIsInstance(p, ResearchPriors)
        self.assertEqual(p.version, "sample-2026-06-24")

    def test_strict_without_cache_raises(self):
        with self.assertRaises(PriorsUnavailable):
            get_priors("strict", cache_dir=self.tmp)   # empty tmp dir

    def test_unknown_policy_raises_valueerror(self):
        with self.assertRaises(ValueError):
            get_priors("bogus")

    def test_load_default_cache_absent_raises(self):
        # The live cache (data/research_priors/) doesn't exist until R3-C3's
        # importer runs, so strict against the default cache must raise.
        with self.assertRaises(PriorsUnavailable):
            ResearchPriors.load(cache_dir=os.path.join(self.tmp, "nope"))


class TestImporterAndStatus(unittest.TestCase):
    """R3-C3: validate-before-store importer + the status reader (cached file, D1)."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _files(self):
        return (os.path.exists(os.path.join(self.cache, _CACHE_PRIORS_NAME)),
                os.path.exists(os.path.join(self.cache, _CACHE_META_NAME)))

    def test_ingest_default_sample_happy_path(self):
        res = compute_research_priors_ingest(cache_dir=self.cache)
        self.assertNotIn("error", res)
        self.assertEqual(res["dataset_version"], "sample-2026-06-24")
        self.assertEqual(res["schema_version"], "1.0")
        self.assertEqual(res["axes_loaded"], len(_REQUIRED_AXES))
        self.assertEqual(res["origin_contexts"], len(_ORIGIN_CONTEXT_KEYS))
        self.assertTrue(res["stored_at"])
        self.assertEqual(self._files(), (True, True))

    def test_ingest_explicit_path(self):
        res = compute_research_priors_ingest(path=_IDENTITY, cache_dir=self.cache)
        self.assertEqual(res["dataset_version"], "identity-2026-06-24")

    def test_ingest_round_trips_to_provider(self):
        # The whole point: import then load → ResearchPriors with the same version.
        compute_research_priors_ingest(path=_SAMPLE, cache_dir=self.cache)
        p = get_priors("strict", cache_dir=self.cache)
        self.assertIsInstance(p, ResearchPriors)
        self.assertEqual(p.version, "sample-2026-06-24")

    def test_cached_priors_is_valid_contract(self):
        compute_research_priors_ingest(path=_SAMPLE, cache_dir=self.cache)
        with open(os.path.join(self.cache, _CACHE_PRIORS_NAME), encoding="utf-8") as fh:
            self.assertIsNone(validate_priors_contract(json.load(fh)))

    def test_progress_callback_invoked(self):
        msgs = []
        compute_research_priors_ingest(cache_dir=self.cache, progress_callback=msgs.append)
        self.assertTrue(msgs)

    # ── Gate-1: validate-before-store ──
    def test_missing_source_file(self):
        res = compute_research_priors_ingest(path=os.path.join(self.cache, "nope.json"),
                                             cache_dir=self.cache)
        self.assertIn("error", res)
        self.assertEqual(self._files(), (False, False))

    def test_bad_contract_writes_nothing(self):
        bad = copy.deepcopy(_load(_IDENTITY)); del bad["mass_by_zone"]
        bad_path = os.path.join(self.cache, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as fh:
            json.dump(bad, fh)
        res = compute_research_priors_ingest(path=bad_path, cache_dir=self.cache)
        self.assertIn("error", res)
        # no priors.json / meta.json written
        self.assertFalse(os.path.exists(os.path.join(self.cache, _CACHE_PRIORS_NAME)))
        self.assertFalse(os.path.exists(os.path.join(self.cache, _CACHE_META_NAME)))

    def test_gate1_preserves_existing_cache(self):
        # Import a good dataset, then a bad import must leave the cache intact.
        compute_research_priors_ingest(path=_SAMPLE, cache_dir=self.cache)
        before = get_research_priors_status(cache_dir=self.cache)
        bad = copy.deepcopy(_load(_IDENTITY)); bad["schema_version"] = "9.9"
        bad_path = os.path.join(self.cache, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as fh:
            json.dump(bad, fh)
        res = compute_research_priors_ingest(path=bad_path, cache_dir=self.cache)
        self.assertIn("error", res)
        self.assertEqual(get_research_priors_status(cache_dir=self.cache), before)
        self.assertEqual(before["dataset_version"], "sample-2026-06-24")

    # ── status reader ──
    def test_status_not_loaded(self):
        st = get_research_priors_status(cache_dir=self.cache)
        self.assertEqual(st["loaded"], False)
        self.assertIsNone(st["dataset_version"])

    def test_status_loaded(self):
        compute_research_priors_ingest(path=_SAMPLE, cache_dir=self.cache)
        st = get_research_priors_status(cache_dir=self.cache)
        self.assertEqual(st["loaded"], True)
        self.assertEqual(st["dataset_version"], "sample-2026-06-24")
        self.assertEqual(st["schema_version"], "1.0")
        self.assertEqual(st["origin_contexts"], len(_ORIGIN_CONTEXT_KEYS))
        self.assertTrue(st["stored_at"])

    def test_status_corrupt_meta_is_not_loaded(self):
        compute_research_priors_ingest(path=_SAMPLE, cache_dir=self.cache)
        with open(os.path.join(self.cache, _CACHE_META_NAME), "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        st = get_research_priors_status(cache_dir=self.cache)
        self.assertEqual(st["loaded"], False)


if __name__ == "__main__":
    unittest.main()
