"""Shared helpers for the regression suite (python -m unittest discover -s tests)."""
import copy
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from trm4 import presets as P                     # noqa: E402
from trm4.model import TRM4Model, run_project      # noqa: E402

LWIR = "Thermal - LWIR cooled staring 640x512 (CMT)"
MWIR = "Thermal - MWIR cooled staring 640x512 (InSb)"
UNCOOLED = "Thermal - LWIR uncooled microbolometer 640x480"
VIS = "Visible - CMOS daylight camera 1920x1080"
SWIR = "Visible/SWIR - InGaAs night camera 640x512"
GENERAL = "General - MWIR sun-lit scene (emission + reflection)"


def template(name, **over):
    p = P.make_template(name)
    for path, val in over.items():
        set_path(p, path.replace("__", "."), val)
    return p


def set_path(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    k = keys[-1]
    if isinstance(d, list):
        d[int(k)] = value
    else:
        d[k] = value


def setup_model(project):
    """Model with geometry, spectra, atmospheres, optics and noise set up (no MTF/range run)."""
    m = TRM4Model(copy.deepcopy(project))
    m._setup_geometry()
    m._setup_spectral()
    m._setup_atmospheres()
    m._setup_optics()
    m._setup_noise()
    return m


def ranges(res, atm=0):
    a = res["range"]["atm"][atm]
    return {t["name"]: t["R0"] for t in a["tasks"]}


def as_file(name, lines):
    return {"name": name, "text": "\n".join(lines)}


def circ_mtf(x):
    """Diffraction MTF of an unobscured circular pupil, x = normalized frequency (0..1)."""
    x = np.clip(np.asarray(x, float), 0, 1)
    return 2 / np.pi * (np.arccos(x) - x * np.sqrt(1 - x * x))
