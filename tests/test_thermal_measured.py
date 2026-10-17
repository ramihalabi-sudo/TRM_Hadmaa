"""Thermal: measured NETD / MTDP inputs give reproducible predictions under documented conditions."""
import unittest

import numpy as np

from _common import UNCOOLED, LWIR, template, setup_model, as_file, ranges, run_project


class Thermal(unittest.TestCase):
    def test_measured_netd_used(self):
        m = setup_model(template(UNCOOLED))
        self.assertAlmostEqual(m.netd, 0.050, places=12)
        st = m.signal_state(0.0, None)
        self.assertAlmostEqual(st["nes"], 0.050, places=12)

    def test_reproducible(self):
        a = ranges(run_project(template(UNCOOLED))[1])
        b = ranges(run_project(template(UNCOOLED))[1])
        self.assertEqual(a, b)

    def test_netd_conditions(self):
        _m, res = run_project(template(UNCOOLED))
        self.assertTrue(any("NETD test" in a for a in res["assumptions"]))          # undocumented
        _m, res = run_project(template(UNCOOLED, detector__netd_TB_K=330.0))
        self.assertTrue(any("NETD was measured at 330 K" in w for w in res["warnings"]))
        _m, res = run_project(template(UNCOOLED, detector__netd_TB_K=290.0))
        self.assertFalse(any("NETD was measured" in w for w in res["warnings"]))

    def test_measured_mtdp_replaces_model(self):
        _m, res = run_project(template(LWIR))
        f = res["fom"]
        ok = np.isfinite(f["h"]["val"])
        vv = np.interp(f["h"]["rp"][ok], f["v"]["rp"], np.where(np.isfinite(f["v"]["val"]), f["v"]["val"], 1e3))
        lines = ["frequency MTDP_h MTDP_v"] + ["%.8g %.8g %.8g" % (r, vh, v) for r, vh, v in
                                              zip(f["h"]["rp"][ok], f["h"]["val"][ok], vv)]
        p = template(LWIR)
        p["measured"].update(fom_file=as_file("mtdp.txt", lines), fom_kind="MTDP", fom_unit="mrad", fom_vunit="K",
                             fom_use="replace")
        _m2, res2 = run_project(p)
        self.assertIn("measured MTDP", res2["range"]["source"])
        for k, v in ranges(res).items():
            self.assertAlmostEqual(ranges(res2)[k], v, delta=0.03 * v)
        it = res2["validation"]["items"][0]              # measured vs predicted, identical curves
        self.assertLess(it["mean_dev_pct"], 1.0)

    def test_measured_netd_comparison(self):
        p = template(UNCOOLED)
        p["measured"].update(netd_mK=55.0, netd_TB_K=300.0)
        _m, res = run_project(p)
        it = next(i for i in res["validation"]["items"] if i["what"] == "NETD")
        self.assertAlmostEqual(it["mean_dev_pct"], 100 * (50.0 / 55.0 - 1), places=6)
        self.assertTrue(any("not a like-for-like" in w for w in res["warnings"]))
        self.assertIn("instrument", res["validation"]["missing_meta"])


if __name__ == "__main__":
    unittest.main()
