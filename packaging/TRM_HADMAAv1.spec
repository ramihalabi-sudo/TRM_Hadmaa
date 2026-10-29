# PyInstaller spec of the Windows application: one folder dist\TRM_HADMAAv1\ with TRM_HADMAAv1.exe.
# Build: packaging\build_exe.bat (or: python -m PyInstaller --noconfirm packaging\TRM_HADMAAv1.spec)
# The data folders keep their place next to the trm4 package, where the code looks for them.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))


def tree(src, dst):
    return [(os.path.join(ROOT, src), dst)] if os.path.exists(os.path.join(ROOT, src)) else []


datas = (tree("trm4/assets", "trm4/assets") + tree("detector_lookup_HTML", "detector_lookup_HTML") +
         tree("Detector datasheets", "Detector datasheets") + tree("profiles", "profiles") +
         [(os.path.join(ROOT, f), ".") for f in os.listdir(ROOT)
          if f.startswith("TRM4") and "Documentation" in f and f.endswith(".pdf")])

a = Analysis([os.path.join(SPECPATH, "trm_entry.py")], pathex=[ROOT], datas=datas,
             hiddenimports=["matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_pdf"],
             excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TRM_HADMAAv1", console=False,
          icon=os.path.join(ROOT, "trm4", "assets", "trm4.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="TRM_HADMAAv1")
