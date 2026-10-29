"""Hebrew scholarly PDF report: right-to-left text ordering and an end-to-end report of the advisor results."""
import os
import tempfile
import unittest

from _common import MWIR, template
from trm4 import advisor as ADV
from trm4 import report_he as RH
from trm4.model import run_project


class Bidi(unittest.TestCase):
    def test_hebrew_reversed(self):
        self.assertEqual(RH.vis("שלום"), "םולש")

    def test_numbers_and_units_stay_left_to_right(self):
        self.assertEqual(RH.vis("טווח 4.30 km"), "4.30 km חווט")
        self.assertEqual(RH.vis("שיפור של +25%"), "+25% לש רופיש")
        self.assertEqual(RH.vis("רעש: ×0.50"), "×0.50 :שער")

    def test_latin_tokens_kept_together(self):
        self.assertEqual(RH.vis("ו־F/#"), "F/#־ו")
        self.assertEqual(RH.vis("f ×1.25 ו־D ×1.25"), "D ×1.25־ו f ×1.25")

    def test_brackets_mirrored_in_rtl(self):
        self.assertEqual(RH.vis("גילוי (Detection)"), "(Detection) יוליג")
        self.assertEqual(RH.vis("(שלום)"), "(םולש)")

    def test_latin_only_unchanged(self):
        s = "Atmospheric transmission (clear path)."
        self.assertEqual(RH.vis(s), s)


class Report(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = template(MWIR)
        _m, cls.res = run_project(cls.project)
        cls.adv = ADV.advise(cls.project, robustness=False)

    def test_actions_translated(self):
        for a in self.adv["actions"]:
            self.assertNotEqual(RH.action_he(a), a["label"], a["id"])
            self.assertIn(a["id"], RH.SHORT_HE)

    def test_pdf_written(self):
        with tempfile.TemporaryDirectory() as d:
            fn = os.path.join(d, "report.pdf")
            n = RH.write_pdf(fn, self.project, self.res, self.adv)
            self.assertGreaterEqual(n, 8)
            with open(fn, "rb") as fh:
                self.assertEqual(fh.read(5), b"%PDF-")

    def test_needs_advisor_result(self):
        with self.assertRaises(ValueError):
            RH.write_pdf(os.devnull, self.project, self.res, {"kind": "limiting"})


if __name__ == "__main__":
    unittest.main()
