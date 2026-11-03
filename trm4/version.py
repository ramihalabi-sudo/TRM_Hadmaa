"""Single source of the application / engine version.

Every substantial change gets a new version: raise VERSION here, add its entry at the top of CHANGELOG.md, set
AppVersion in packaging/TRM_HADMAAv1.iss and run `python tools/version_report.py` (tests/test_version.py checks
that the four agree).  MODEL_VERSION in model.py is built from VERSION and enters the run ID.
"""
VERSION = "2.14"
VERSION_DATE = "2026-11-03"
