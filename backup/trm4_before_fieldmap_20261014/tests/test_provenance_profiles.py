"""Provenance (model version, import hashes, sources, assumptions) and camera profiles."""
import os
import tempfile
import unittest

from _common import LWIR, MWIR, template, as_file, run_project
from trm4 import imports as IM, profiles as PR, report
from trm4.model import MODEL_VERSION


class Provenance(unittest.TestCase):
    def test_result_records_traceability(self):
        tau = as_file("lens_tau.csv", ["Wavelength, T"] + ["%.1f, 0.85" % x for x in (7, 8, 9, 10, 11, 12)])
        p = template(LWIR, optics__tau_mode="zemax", optics__zemax_tau=tau)
        p["provenance"] = {"optics.f_mm": "manufacturer", "detector.pitch_h_um": "measurement"}
        _m, res = run_project(p)
        pv = res["provenance"]
        self.assertEqual(pv["model_version"], MODEL_VERSION)
        self.assertEqual(pv["imports"][0]["sha256"], IM.file_hash(tau["text"]))
        src = {r[1]: r[4] for r in pv["key_inputs"]}
        self.assertEqual(src["optics.f_mm"], "manufacturer")
        self.assertEqual(src["detector.pitch_h_um"], "measurement")
        self.assertEqual(src["detector.n_h"], "preset")
        txt = report.format_report(p, res)
        for needle in ("[Traceability]", "sha256:" + IM.file_hash(tau["text"]), "[Assumptions]",
                       "[Key inputs and data sources]", MODEL_VERSION, "nominal"):
            self.assertIn(needle, txt)
        self.assertIn("characters imported", txt)          # raw imported file is not dumped into the report


class Profiles(unittest.TestCase):
    def test_apply_sets_values_and_sources(self):
        prof = next(p for p in PR.builtin_profiles() if "dual FOV" in p["name"])
        new = PR.apply(template(LWIR), prof, "NFOV  f = 240 mm")
        self.assertEqual(new["optics"]["f_mm"], 240.0)
        self.assertEqual(new["optics"]["aperture"], "general")
        self.assertEqual(new["detector"]["qe_preset"], "InSb MWIR generic")
        self.assertEqual(new["provenance"]["optics.f_mm"], "preset")
        self.assertEqual(new["profile"]["config"], "NFOV  f = 240 mm")
        _m, res = run_project(new)
        self.assertFalse(any("inconsistent" in w for w in res["warnings"]))

    def test_save_load_roundtrip(self):
        old = PR.PROFILE_DIR
        with tempfile.TemporaryDirectory() as d:
            PR.PROFILE_DIR = d
            try:
                p = template(MWIR)
                p["provenance"] = {"detector.pitch_h_um": "manufacturer"}
                prof = PR.from_project(p, "Test camera", "WFOV", "ACME", "manufacturer")
                PR.add_config(prof, template(MWIR, optics__f_mm=400.0), "NFOV")
                fn = PR.save(prof)
                self.assertTrue(os.path.exists(fn))
                loaded = [x for x in PR.user_profiles() if x["name"] == "Test camera"][0]
                self.assertEqual([c["name"] for c in loaded["configs"]], ["WFOV", "NFOV"])
                new = PR.apply(template(LWIR), loaded, "NFOV")
                self.assertEqual(new["optics"]["f_mm"], 400.0)
                self.assertEqual(new["provenance"]["detector.pitch_h_um"], "manufacturer")
                self.assertEqual(new["provenance"]["optics.f_mm"], "manufacturer")
            finally:
                PR.PROFILE_DIR = old

    def test_validation(self):
        with self.assertRaises(ValueError):
            PR.from_project(template(LWIR, detector__a_h_um=20.0), "bad")    # active size > pitch 15 um


if __name__ == "__main__":
    unittest.main()
