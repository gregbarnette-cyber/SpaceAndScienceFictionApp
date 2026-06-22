# tests/test_nbody.py — Phase R2-C4: the pure-numpy N-body confirmer.
#
# Offline, deterministic. Covers the fixed-step leapfrog integrator in core.nbody:
# determinism (same inputs → identical result, no RNG), a widely-separated system
# surviving the bounded run, a packed/overlapping system flagged unstable (close
# encounter), and the trivial < 2-planet / bad-input short-circuits.

import unittest

from core.nbody import (
    integrate_coplanar, _N_ORBITS, _STEPS_PER_ORBIT, _CLOSE_FACTOR, _DRIFT_BAND,
)


class TestNbodyIntegrator(unittest.TestCase):
    def test_widely_separated_survives(self):
        r = integrate_coplanar(1.0, [{"mass_earth": 1.0, "a_au": 1.0},
                                     {"mass_earth": 1.0, "a_au": 5.0},
                                     {"mass_earth": 1.0, "a_au": 10.0}])
        self.assertTrue(r["survived"])
        self.assertEqual(r["orbits_run"], _N_ORBITS)
        self.assertIsNone(r["reason"])

    def test_packed_giants_unstable(self):
        r = integrate_coplanar(1.0, [{"mass_earth": 300.0, "a_au": 1.0},
                                     {"mass_earth": 300.0, "a_au": 1.05},
                                     {"mass_earth": 300.0, "a_au": 1.1}])
        self.assertFalse(r["survived"])
        self.assertLess(r["orbits_run"], _N_ORBITS)
        self.assertIn("close encounter", r["reason"])

    def test_determinism(self):
        cfg = [{"mass_earth": 5.0, "a_au": 1.0}, {"mass_earth": 5.0, "a_au": 1.3}]
        self.assertEqual(integrate_coplanar(1.0, cfg), integrate_coplanar(1.0, cfg))

    def test_single_or_empty_trivially_survives(self):
        self.assertTrue(integrate_coplanar(1.0, [{"mass_earth": 1.0, "a_au": 1.0}])["survived"])
        self.assertTrue(integrate_coplanar(1.0, [])["survived"])
        self.assertEqual(integrate_coplanar(1.0, [])["steps"], 0)

    def test_bad_inputs_short_circuit(self):
        # Non-positive star mass, or planets with bad SMA/mass, never raise.
        self.assertTrue(integrate_coplanar(0.0, [{"mass_earth": 1.0, "a_au": 1.0},
                                                 {"mass_earth": 1.0, "a_au": 2.0}])["survived"])
        r = integrate_coplanar(1.0, [{"mass_earth": 1.0, "a_au": 1.0},
                                     {"mass_earth": 0.0, "a_au": 2.0}])
        self.assertTrue(r["survived"])      # only one valid planet → trivial

    def test_constants_sane(self):
        self.assertEqual(_N_ORBITS, 200)
        self.assertEqual(_STEPS_PER_ORBIT, 100)
        self.assertEqual(_CLOSE_FACTOR, 1.0)
        self.assertTrue(0 < _DRIFT_BAND < 1)

    def test_result_shape(self):
        r = integrate_coplanar(1.0, [{"mass_earth": 1.0, "a_au": 1.0},
                                     {"mass_earth": 1.0, "a_au": 3.0}])
        self.assertEqual(set(r), {"survived", "orbits_run", "reason", "n_orbits", "steps"})


if __name__ == "__main__":
    unittest.main()
