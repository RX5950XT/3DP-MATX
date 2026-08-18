"""FreeCADCmd 進入點：建模 + 匯出。

用 os._exit() 收尾：FreeCAD 的直譯器關閉路徑會把 SystemExit／redirect 過的
stdout 變成 "Application unexpectedly terminated"（結果檔沒寫、離開碼騙人）。
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

code = 0
try:
    import build_case

    build_case.build(export=True)
    print("BUILD_OK")
except Exception:
    traceback.print_exc()
    code = 1

try:
    sys.stdout.flush()
except Exception:
    pass
os._exit(code)
