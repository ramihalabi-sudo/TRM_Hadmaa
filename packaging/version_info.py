"""Windows version resource of TRM_HADMAAv1.exe: what Explorer shows under Properties > Details.

The numbers come from trm4/version.py, the single source of the version, so nothing has to be kept in step by hand.
The file is read as text (not imported): the spec file runs inside PyInstaller, before the application is importable.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCT = "TRM_HADMAAv1 Thermal Range Model"
COMPANY = "TRM_HADMAA"
EXE = "TRM_HADMAAv1.exe"


def read_version(root=None):
    """(VERSION, VERSION_DATE) as written in trm4/version.py."""
    path = os.path.join(root or os.path.dirname(HERE), "trm4", "version.py")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    version = re.search(r'^VERSION = "([^"]+)"', text, re.M).group(1)
    date = re.search(r'^VERSION_DATE = "([^"]+)"', text, re.M).group(1)
    return version, date


def version_tuple(version):
    """'2.40' -> (2, 40, 0, 0): the four numbers of a Windows file version."""
    parts = [int(x) for x in re.findall(r"\d+", version)][:4]
    if not parts:
        raise ValueError("No number in the version %r" % version)
    return tuple(parts + [0] * (4 - len(parts)))


def strings(version, date):
    """The named entries of the Details tab."""
    return [("CompanyName", COMPANY),
            ("FileDescription", PRODUCT),
            ("FileVersion", version),
            ("InternalName", os.path.splitext(EXE)[0]),
            ("OriginalFilename", EXE),
            ("ProductName", PRODUCT),
            ("ProductVersion", version),
            ("Comments", "Engine %s of %s" % (version, date))]


def resource(root=None):
    """The VSVersionInfo object for PyInstaller's EXE(version=...)."""
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                     VarFileInfo, VarStruct, VSVersionInfo)
    version, date = read_version(root)
    numbers = version_tuple(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1,
                          subtype=0x0, date=(0, 0)),
        kids=[StringFileInfo([StringTable("040904B0", [StringStruct(k, v) for k, v in strings(version, date)])]),
              VarFileInfo([VarStruct("Translation", [1033, 1200])])])


def write(path, root=None):
    """Write the resource as the text file PyInstaller reads; returns the path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(resource(root)))
    return path
