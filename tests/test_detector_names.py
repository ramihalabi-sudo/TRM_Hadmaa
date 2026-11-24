"""Engine 2.40 - the names of the spectral response curves.

The list "Spectral quantum efficiency" names detector materials.  The silicon curve was called "CCD Silicon generic"
although it serves CCD and CMOS sensors alike; it is now "Silicon (CCD / CMOS) generic", and a project saved with the
earlier name loads as before.  An uncooled microbolometer has no curve in the list: it uses the flat response between
a cut-on and a cut-off wavelength.
"""
import unittest

from _common import UNCOOLED, VIS, ranges, run_project, template
from trm4 import detector_atlas as DA
from trm4 import presets as P
from trm4.help_text import HELP

OLD, NEW = "CCD Silicon generic", "Silicon (CCD / CMOS) generic"


class SiliconCurve(unittest.TestCase):
    def test_listed_under_the_new_name_only(self):
        self.assertIn(NEW, P.QE_NAMES)
        self.assertNotIn(OLD, P.QE_NAMES)
        self.assertEqual(P.QE_NAMES[0], NEW)                      # still the first entry of the list
        self.assertEqual(P.QE_NAMES[-1], "Custom")
        self.assertEqual(P.QE_ALIASES[OLD], NEW)

    def test_the_curve_is_silicon(self):
        pts = P.DETECTOR_QE[NEW]
        lam = [x for x, q in pts if q > 0]
        self.assertGreaterEqual(lam[0], 0.25)
        self.assertLessEqual(lam[-1], 1.1)                        # silicon does not respond beyond about 1.1 um

    def test_a_project_saved_with_the_earlier_name_loads_and_gives_the_same_ranges(self):
        new = template(VIS)
        self.assertEqual(new["detector"]["qe_preset"], NEW)
        old = template(VIS, detector__qe_preset=OLD)
        self.assertEqual(old["detector"]["qe_preset"], OLD)        # as it sits in the saved file
        self.assertEqual(P.deep_merge(P.DEFAULT_PROJECT, old)["detector"]["qe_preset"], NEW)
        m_new, r_new = run_project(new)
        m_old, r_old = run_project(old)
        self.assertEqual(m_old.qe_label, NEW)
        self.assertEqual(ranges(r_old), ranges(r_new))

    def test_detector_lookup_maps_cmos_and_ccd_to_it(self):
        src = open(DA.__file__, encoding="utf-8").read()
        self.assertIn('"%s"' % NEW, src)
        self.assertNotIn('"%s"' % OLD, src)
        self.assertIn("CMOS", HELP["detector.qe_preset"])

    def test_uncooled_microbolometer_uses_the_flat_response(self):
        p = template(UNCOOLED)
        self.assertEqual(p["detector"]["uncooled_response"], "flat")
        self.assertEqual((p["detector"]["cuton_um"], p["detector"]["cutoff_um"]), (8.0, 14.0))
        m, _res = run_project(p)
        self.assertEqual(m.qe_label, "flat 8.0-14.0 um")
        self.assertEqual(P.qe_window(P.deep_merge(P.DEFAULT_PROJECT, p)), (8.0, 14.0))


if __name__ == "__main__":
    unittest.main()
