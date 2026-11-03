"""One version everywhere: trm4/version.py, the package, the model version (run ID), the installer, the top entry of
CHANGELOG.md and the newest README version section."""
import os
import re
import sys
import unittest

from _common import ROOT

sys.path.insert(0, os.path.join(ROOT, "tools"))
import version_report as VR                          # noqa: E402
import trm4                                          # noqa: E402
from trm4.model import MODEL_VERSION                 # noqa: E402
from trm4.version import VERSION                     # noqa: E402


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8-sig") as f:
        return f.read()


class VersionConsistency(unittest.TestCase):
    def test_package_and_model(self):
        self.assertEqual(trm4.__version__, VERSION)
        self.assertTrue(MODEL_VERSION.endswith("engine " + VERSION))

    def test_installer(self):
        m = re.search(r'#define AppVersion "([^"]+)"', _read("packaging", "TRM_HADMAAv1.iss"))
        self.assertEqual(m.group(1), VERSION)

    def test_changelog_top_entry(self):
        entries = VR.parse_changelog()
        self.assertEqual(entries[0]["version"], VERSION)
        versions = [tuple(int(x) for x in e["version"].split(".")) for e in entries]
        self.assertEqual(versions, sorted(versions, reverse=True), "CHANGELOG.md must be newest first")
        self.assertEqual(len(set(versions)), len(versions))
        for e in entries:
            with self.subTest(version=e["version"]):
                self.assertTrue(e["impact"] and e["changes"])

    def test_readme_newest_section(self):
        m = re.search(r"^## Version (\d+\.\d+(?:\.\d+)?)", _read("README.md"), re.M)
        self.assertEqual(m.group(1), VERSION)

    def test_html_report(self):
        page = VR.html_report(VR.parse_changelog(), {})
        self.assertIn('dir="rtl"', page)
        self.assertIn('id="v%s"' % VERSION, page)

    def test_compare_between_versions(self):
        refs = VR.version_commits()
        if len(refs) < 2:
            self.skipTest("no git history")
        changelog = {e["version"] for e in VR.parse_changelog()}
        self.assertTrue(set(refs) <= changelog, "a tagged version without a CHANGELOG entry")
        vs = sorted(refs, key=VR._vkey)
        info = VR.git_versions()[vs[-1]]
        self.assertEqual(info[3], vs[-2])                           # compared with the previous version
        self.assertTrue(info[2]["files"])
        text = VR.diff_text(vs[-2], vs[-1])
        self.assertIn("git diff", text)
        self.assertIn(VR.parse_changelog()[0]["title"] if vs[-1] == VERSION else vs[-1], text)
        page = VR.html_report(VR.parse_changelog(), VR.git_versions())
        self.assertIn("/compare/", page)


if __name__ == "__main__":
    unittest.main()
