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


class PropertiesVersion(unittest.TestCase):
    """Explorer > Properties > Details of TRM_HADMAAv1.exe and of the Setup file shows the version; the numbers are
    read from trm4/version.py at packaging time (packaging/version_info.py)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "packaging"))
        import version_info
        cls.VI = version_info

    def test_reads_the_single_source(self):
        from trm4.version import VERSION_DATE
        self.assertEqual(self.VI.read_version(ROOT), (VERSION, VERSION_DATE))
        entries = dict(self.VI.strings(VERSION, VERSION_DATE))
        self.assertEqual(entries["FileVersion"], VERSION)
        self.assertEqual(entries["ProductVersion"], VERSION)
        self.assertEqual(entries["OriginalFilename"], "TRM_HADMAAv1.exe")
        self.assertIn(VERSION, entries["Comments"])

    def test_four_numbers_of_a_windows_file_version(self):
        self.assertEqual(self.VI.version_tuple("2.40"), (2, 40, 0, 0))
        self.assertEqual(self.VI.version_tuple("2.41.3"), (2, 41, 3, 0))
        self.assertEqual(self.VI.version_tuple("3"), (3, 0, 0, 0))
        self.assertEqual(self.VI.version_tuple(VERSION)[:2], tuple(int(x) for x in VERSION.split(".")[:2]))
        with self.assertRaises(ValueError):
            self.VI.version_tuple("")

    def test_build_files_use_it_and_carry_no_number_of_their_own(self):
        spec = _read("packaging", "TRM_HADMAAv1.spec")
        self.assertIn("version=VERSION_FILE", spec)
        self.assertIn("version_info.write(", spec)
        self.assertIsNone(re.search(r"\d+\.\d{2}", spec), "a version number written into the spec file")
        iss = _read("packaging", "TRM_HADMAAv1.iss")
        for key in ("VersionInfoVersion", "VersionInfoProductVersion", "VersionInfoProductTextVersion"):
            self.assertIn("%s={#AppVersion}" % key, iss)

    def test_resource_text(self):
        try:
            res = self.VI.resource(ROOT)
        except ImportError:
            self.skipTest("PyInstaller is not installed here")
        text = str(res)
        numbers = self.VI.version_tuple(VERSION)
        self.assertIn("filevers=%r" % (numbers,), text)
        self.assertIn("prodvers=%r" % (numbers,), text)
        self.assertIn("StringStruct('ProductVersion', '%s')" % VERSION, text)


if __name__ == "__main__":
    unittest.main()
