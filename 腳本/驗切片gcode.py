# -*- coding: utf-8 -*-
"""驗**切出來的 G-code**：實際擠出的路徑有沒有跑出熱床。

為什麼一定要有這一層
--------------------
前面兩層都只是在算：`列印擺位.py` 量 STL 的 bbox、`驗切片設定.py` 驗 preset 的
key 與 enum。兩層全綠，Bambu Studio 照樣報「檢測超出熱床邊界的 G-code 路徑」——
因為**切片器會自己生出模型以外的料**，而那些料的量是它算的，不是我算的。

實際抓到的：`raft_first_layer_expansion = -1`（自動）會把**支撐的第一層**
往外擴 2.9~4.0 mm。底板本體 X 3.270..252.730 好好的，支撐第一層
X **-0.912..256.912** 直接掉出床外。`support_expansion = 0` 管不到它，
`brim_type = no_brim` 也管不到它 —— 那是 raft 的參數，長在支撐上。

所以規則是：**只要有一件的餘量是個位數 mm，就必須拿真的 G-code 來驗，
不能只驗 STL 和 preset。**

用法：
    python 腳本\\驗切片gcode.py <某個.gcode>
    python 腳本\\驗切片gcode.py            # 自動找 Bambu Studio 最近切的那份
"""

from __future__ import annotations

import glob
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _load_params import load_params  # noqa: E402

D = load_params()
BED = D.A1_MAX
BED_H = D.A1_H_MAX

# 機器自己的動作，本來就在床外（吐料、擦嘴、延時攝影停車），不是設計問題。
# Bambu Studio 的邊界檢查也不看這些。
MACHINE = {"Custom", "timelapse", "head_wrap_detect"}

XYZ = re.compile(r"([XYZ])(-?\d*\.?\d+)")
TAG = re.compile(r";\s*(?:FEATURE|SKIPTYPE):\s*(.+)")


def newest_gcode() -> str:
    base = os.path.join(os.environ.get("TEMP", ""), "bamboo_model", "*", "*",
                        "Metadata")
    # Bambu 產的檔名是 `.<id>.0.gcode`（開頭一個點）——`glob` 的 `*` 不吃隱藏檔，
    # 只寫 `*.gcode` 會什麼都找不到，然後被讀成「還沒切過」。
    hits = glob.glob(os.path.join(base, "*.gcode")) + \
        glob.glob(os.path.join(base, ".*.gcode"))
    if not hits:
        raise SystemExit(
            "找不到 Bambu Studio 切好的 G-code。先在 Bambu Studio 切一次，"
            "或把 .gcode 路徑當參數傳進來。"
        )
    return max(hits, key=os.path.getmtime)


def main(argv) -> int:
    path = argv[0] if argv else newest_gcode()
    print("G-code：%s" % path)
    pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    tag = "Custom"
    box = defaultdict(lambda: [1e9, -1e9, 1e9, -1e9, -1e9])
    worst: list = []
    for ln, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        s = line.strip()
        if s.startswith(";"):
            m = TAG.match(s)
            if m:
                tag = m.group(1).strip()
            continue
        if not s.startswith(("G0", "G1")):
            continue
        for ax, v in XYZ.findall(s.split(";")[0]):
            pos[ax] = float(v)
        if " E" not in s.upper() or "E-" in s:  # 只看擠出，不看空跑
            continue
        b = box[tag]
        b[0] = min(b[0], pos["X"]); b[1] = max(b[1], pos["X"])
        b[2] = min(b[2], pos["Y"]); b[3] = max(b[3], pos["Y"])
        b[4] = max(b[4], pos["Z"])
        if tag in MACHINE:
            continue
        if not (0 <= pos["X"] <= BED and 0 <= pos["Y"] <= BED and pos["Z"] <= BED_H):
            worst.append((ln, tag, pos["X"], pos["Y"], pos["Z"]))

    print("\n%-24s %-38s %s" % ("FEATURE", "XY 範圍", "最高 Z"))
    print("-" * 78)
    for t in sorted(box):
        b = box[t]
        if b[0] > 1e8:
            continue
        flag = "  （機器動作，不計）" if t in MACHINE else (
            "  ✗ 出界" if b[0] < 0 or b[1] > BED or b[2] < 0 or b[3] > BED else "")
        print("%-24s X %8.3f..%8.3f  Y %8.3f..%8.3f  %6.2f%s"
              % (t, b[0], b[1], b[2], b[3], b[4], flag))

    real = {t: b for t, b in box.items() if t not in MACHINE and b[0] < 1e8}
    if real:
        x0 = min(b[0] for b in real.values()); x1 = max(b[1] for b in real.values())
        y0 = min(b[2] for b in real.values()); y1 = max(b[3] for b in real.values())
        print("\n模型＋支撐合計 X %.3f..%.3f  Y %.3f..%.3f" % (x0, x1, y0, y1))
        print("床 0..%.0f → 餘量 左 %.3f 右 %.3f 前 %.3f 後 %.3f"
              % (BED, x0, BED - x1, y0, BED - y1))

    if worst:
        print("\n✗ %d 段擠出跑到床外，前 10 段：" % len(worst))
        for w in worst[:10]:
            print("   行%-8d %-18s X=%-9.3f Y=%-9.3f Z=%.2f" % w)
        print("\n最常見的原因（實際踩過）："
              "\n  raft_first_layer_expansion = -1（自動）→ 支撐第一層往外擴 2.9~4.0 mm。"
              "\n  它是 raft 的參數，`support_expansion = 0` 與 `brim_type = no_brim` 都管不到。"
              "\n  設 `raft_first_layer_expansion = 0`。")
        return 1
    print("\n✓ 模型與支撐的擠出全部在床內")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
