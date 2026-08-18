"""以路徑載入 參數.py（避免 FreeCAD 對中文 import 名稱不穩）。"""
from __future__ import annotations

import importlib.util
import os
import sys


def load_params():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "參數.py")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location("matx_params", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    return mod
