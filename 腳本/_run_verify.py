"""FreeCADCmd 進入點：幾何驗證。離開碼 0 = 全過，1 = 有 FAIL。

用 os._exit() 收尾，理由同 _run_build.py。
"""

import io
import os
import sys
import traceback

try:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

code = 1
try:
    import verify_case

    code = verify_case.main()
except Exception:
    traceback.print_exc()

try:
    sys.stdout.flush()
except Exception:
    pass
os._exit(code)
