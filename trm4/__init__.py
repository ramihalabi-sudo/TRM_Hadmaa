"""TRM4 - Thermal Range Model (TRM4.v3) implementation in Python.

Based on: "TRM4.v3 Parameter Description and Model Documentation", Fraunhofer IOSB
Technical Report 2021/04.
"""
from .model import TRM4Model, ModelError, run_project
from .presets import DEFAULT_PROJECT, TEMPLATES, make_template, deep_merge

__version__ = "2.2.0"
__all__ = ["TRM4Model", "ModelError", "run_project", "DEFAULT_PROJECT", "TEMPLATES", "make_template",
           "deep_merge"]
