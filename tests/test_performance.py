"""Speed-ups must not change results: fast AMOP wiggle removal and parallel model runs."""
import json
import random
import unittest

from _common import MWIR, template
from trm4 import amop as A
from trm4 import analysis as AN


class WiggleRemoval(unittest.TestCase):
    def test_same_as_direct_loop(self):
        rng = random.Random(3)
        for _ in range(3000):
            n = rng.choice([1, 2, 3, 5, 8, 20, 80, 300])
            q = rng.choice([None, 1, 2, 4])                       # quantized values -> ties
            scale = rng.choice([1.0, 1e-6])
            seq, t = [], rng.choice([1, -1])
            for _k in range(n):
                v = rng.random() if q is None else rng.randint(0, 3 * q) / q
                seq.append([v * scale, t])
                t = -t
            rel = rng.choice([0.1, 0.5, 0.9, 1.2])
            self.assertEqual(A._remove_wiggles(seq, rel, 1e-6), A._remove_wiggles_direct(seq, rel, 1e-6))


class ParallelRuns(unittest.TestCase):
    def test_limiting_factors_parallel_equals_serial(self):
        p = template(MWIR)
        serial = AN.limiting_factors(p)
        with AN.Runner(2) as r:
            par = AN.limiting_factors(p, runner=r)
        for d in (serial, par):
            d.pop("time")
        self.assertEqual(json.dumps(serial, sort_keys=True), json.dumps(par, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
