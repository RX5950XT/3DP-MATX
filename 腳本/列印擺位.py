# -*- coding: utf-8 -*-
"""
逐件量 `列印件/*.stl` 的六個軸向擺法：外形、懸空面積、床接觸面積。
`文件/列印參數與擺位.md` 的表就是這支印出來的（硬規則 16：數字要能重現）。

用法：
    python 腳本\\列印擺位.py            # 全部
    python 腳本\\列印擺位.py --best      # 只印每件建議的擺法

定義
----
懸空：三角形法向朝下且與水平夾角 > 45°（`nz/|n| < -cos45`），
      且整片不在第一層（`max(z) - zmin > 0.2`）。
床接觸：同樣朝下、但整片落在 `z = zmin` 附近（≤0.2）。

★ 六個擺法必須全是**真旋轉**（det = +1）。寫成鏡射（例如 `(x,y,z)→(z,y,x)`）
  的話法向會全部反向 —— 量到的「懸空」其實是頂面、床接觸恆為 0，
  數字看起來完全合理，但全是反的。`_assert_rotations()` 就是在守這一條。
★ 選擺位要**同時**看懸空與床接觸：懸空最小的姿態常常是「立起來」，
  A1 是 bedslinger，床接觸不足就會在移動中倒掉。
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STL_DIR = os.path.join(ROOT, "列印件")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _load_params import load_params  # noqa: E402

D = load_params()

BED = D.A1_MAX  # A1 床 256 × 256（bed_exclude_area = []）
BED_H = D.A1_H_MAX
COS45 = math.cos(math.radians(45.0))
FIRST_LAYER_BAND = 0.2  # 視為「貼床」的 z 帶寬
SUPPORT_LINE_W = 0.42  # support_line_width（0.16mm Optimal @BBL A1 繼承鏈解析後）
PRESET = os.path.join(ROOT, "列印設定", "3DP-MATX 機殼件 0.16 支撐.json")


def _support_xy() -> float:
    """普通支撐往件外脹的量。

    = support_object_xy_distance + support_line_width + raft_first_layer_expansion

    ★ 三項**全部從 preset 讀**，不寫死：preset 一改，這裡的餘量跟著變。
    ★ 第三項是踩過的坑：`raft_first_layer_expansion = -1`（自動）會把**支撐的
      第一層**往外擴 2.9~4.0 mm，實測讓底板的支撐跑到 X = -0.912 / 256.912。
      它是 raft 的參數，`support_expansion` 與 `brim_type` 都管不到它。
    """
    with open(PRESET, encoding="utf-8") as f:
        p = json.load(f)
    if p.get("support_type") != "normal(auto)":
        raise SystemExit(
            "preset 的 support_type = %r —— 只有 normal(auto) 的外脹量是這個式子；"
            "樹狀分枝 45° 往外斜，算法完全不同" % p.get("support_type")
        )
    raft = float(p["raft_first_layer_expansion"])
    if raft < 0:
        raise SystemExit(
            "preset 的 raft_first_layer_expansion = %g（負數＝自動，實測擴 2.9~4.0 mm）"
            "——擴多少切片器說了算，這裡就算不出餘量了。設 0。" % raft
        )
    return float(p["support_object_xy_distance"]) + SUPPORT_LINE_W + raft


SUP_XY = _support_xy()

# 每個 STL 的建議擺法（來源：本腳本的量測；理由見 文件/列印參數與擺位.md）
RECOMMENDED = {
    "Bottom_Tray": "Z+ 朝上",
    "Rear_IO_PCIe": "Z- 朝上",
    "Side_Left_MB": "X+ 朝上",
    "Side_Right_MB": "X- 朝上",
    "Top_MB": "Z- 朝上",
    "Front_Shroud": "Y- 朝上",
    "HDD_Rack": "Z- 朝上",
    "HDD_Tray": "Z+ 朝上",
    "PCIeBlank": "Z+ 朝上",
    "PCIeBar": "Y+ 朝上",
    "MB_Nut": "Z+ 朝上",
}
# 懸空幾乎為零、開了支撐反而毀件的（進氣柵塞滿／支撐長進螺紋牙谷）
NO_SUPPORT = ("Front_Shroud", "PCIeBlank", "PCIeBar", "MB_Nut")

# 擺盤時繞 Z 轉幾度。`CASE_W = 252.68` 在 256 的床上單邊只剩 1.66 mm，
# 加上支撐更少 —— 細長件轉 45° 可以把餘量從 1 mm 級拉到 10 mm 級。
# 近正方形的件（底板／頂蓋／前罩）轉了沒用，只能靠 no_brim + 支撐不外脹。
PLATE_ROT = {k: 0.0 for k in RECOMMENDED}
PLATE_ROT["Rear_IO_PCIe"] = 45.0   # 254.2 × 23.9 → 185.9 × 185.9
PLATE_ROT["HDD_Rack"] = 45.0       # 251.2 × 105.1 → 227.5 × 227.5
MIN_MARGIN = 0.75  # 每邊至少留這麼多；低於這個就是靠運氣

ORIENTS = {
    "Z+ 朝上": lambda p: (p[0], p[1], p[2]),
    "Z- 朝上": lambda p: (p[0], -p[1], -p[2]),
    "X+ 朝上": lambda p: (-p[2], p[1], p[0]),
    "X- 朝上": lambda p: (p[2], p[1], -p[0]),
    "Y+ 朝上": lambda p: (p[0], -p[2], p[1]),
    "Y- 朝上": lambda p: (p[0], p[2], -p[1]),
}


def _assert_rotations() -> None:
    """每個擺法都必須是 det=+1 的真旋轉，否則法向全反、量測全錯。"""
    for name, fn in ORIENTS.items():
        cols = [fn((1, 0, 0)), fn((0, 1, 0)), fn((0, 0, 1))]
        (a, d, g), (b, e, h), (c, f, i) = cols
        det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
        if abs(det - 1.0) > 1e-9:
            raise SystemExit(f"擺法 {name} 不是真旋轉（det={det}）——法向會全部反向")


def read_stl(path: str):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 84:
        raise SystemExit(f"STL 太小，可能沒產出來：{path}")
    if data[:5] == b"solid" and b"facet" in data[:2000]:
        raise SystemExit(f"只支援二進位 STL：{path}")
    n = struct.unpack("<I", data[80:84])[0]
    if len(data) != 84 + 50 * n:
        raise SystemExit(f"STL 長度與三角形數不符：{path}")
    # 每筆 50 bytes：法向 12 + 三頂點 36 + 屬性 2。只取頂點（法向不可信，重算）
    return [struct.unpack("<9f", data[o + 12 : o + 48])
            for o in range(84, 84 + 50 * n, 50)]


def volume_cm3(tris) -> float:
    v = 0.0
    for t in tris:
        ax, ay, az, bx, by, bz, cx, cy, cz = t
        v += (ax * (by * cz - bz * cy)
              - ay * (bx * cz - bz * cx)
              + az * (bx * cy - by * cx)) / 6.0
    return abs(v) / 1000.0


def analyse(tris, fn):
    """回傳 (bbox, 懸空 mm², 床接觸 mm², 普通支撐後 XY, 樹狀支撐後 XY)。

    ★ 「件本身放得下」不等於「加了支撐放得下」。支撐是**印出來的料**，
      也要佔床。普通支撐是懸空區往下垂直擠出，只往外脹
      `support_object_xy_distance + support_line_width`；
      **樹狀支撐的分枝以 `tree_support_branch_angle = 45°` 往外斜**，
      懸空點離床 h 就可能外擴 h —— 後牆懸空最高 179 mm，樹狀算出來 608 mm。
      A1 的預設 `support_type` 正是 `tree(auto)`。
    """
    zmin = min(fn(t[i * 3 : i * 3 + 3])[2] for t in tris for i in range(3))
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    slo = [float("inf")] * 2  # 普通支撐（含件本身）的 XY 範圍
    shi = [float("-inf")] * 2
    tlo = [float("inf")] * 2  # 樹狀支撐（含件本身）的 XY 範圍
    thi = [float("-inf")] * 2
    over = bed = 0.0
    for t in tris:
        a, b, c = fn(t[0:3]), fn(t[3:6]), fn(t[6:9])
        for p in (a, b, c):
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
            for k in range(2):
                slo[k] = min(slo[k], p[k])
                shi[k] = max(shi[k], p[k])
                tlo[k] = min(tlo[k], p[k])
                thi[k] = max(thi[k], p[k])
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        n = math.sqrt(nx * nx + ny * ny + nz * nz)
        if n == 0.0:
            continue
        if nz / n < -COS45:
            top = max(a[2], b[2], c[2])
            if top - zmin <= FIRST_LAYER_BAND:
                bed += n / 2.0
                continue
            over += n / 2.0
            h = top - zmin
            for k in range(2):
                mn = min(a[k], b[k], c[k])
                mx = max(a[k], b[k], c[k])
                slo[k] = min(slo[k], mn - SUP_XY)
                shi[k] = max(shi[k], mx + SUP_XY)
                tlo[k] = min(tlo[k], mn - h)  # 分枝 45° 往外斜到床
                thi[k] = max(thi[k], mx + h)
    return (
        tuple(hi[k] - lo[k] for k in range(3)),
        over,
        bed,
        tuple(shi[k] - slo[k] for k in range(2)),
        tuple(thi[k] - tlo[k] for k in range(2)),
    )


def main(argv) -> int:
    _assert_rotations()
    if set(RECOMMENDED) != set(D.STL_NAMES):  # 漏件守衛（硬規則 7）
        raise SystemExit(
            "RECOMMENDED 與 STL_NAMES 不一致：%s"
            % (set(RECOMMENDED) ^ set(D.STL_NAMES),)
        )
    best_only = "--best" in argv
    total = 0.0
    tree_bad = []
    print("A1 床 %.0f × %.0f × %.0f（bed_exclude_area = []）" % (BED, BED, BED_H))
    for key, fname in D.STL_NAMES.items():
        path = os.path.join(STL_DIR, fname)
        if not os.path.isfile(path):
            raise SystemExit(f"缺少 STL：{path}（先跑 _run_build.py）")
        tris = read_stl(path)
        qty = D.PART_QTY[key]
        vol = volume_cm3(tris)
        total += vol * qty
        print("=" * 74)
        print("%s  ×%d  實體 %.1f cm3  tri=%d  支撐：%s"
              % (fname, qty, vol, len(tris),
                 "關" if key in NO_SUPPORT else "開"))
        for oname, fn in ORIENTS.items():
            if best_only and oname != RECOMMENDED[key]:
                continue
            bbox, over, bed, sup, tree = analyse(tris, fn)
            fits = bbox[0] <= BED and bbox[1] <= BED and bbox[2] <= BED_H
            print("  %s %-8s %7.2f × %7.2f × %7.2f  %s  懸空 %8.1f  床接觸 %8.1f"
                  % ("★" if oname == RECOMMENDED[key] else " ", oname,
                     bbox[0], bbox[1], bbox[2], "OK " if fits else "放不下",
                     over, bed))
            if not fits:
                raise SystemExit(f"{fname} 的 {oname} 放不進 A1 床")
            if oname != RECOMMENDED[key]:
                continue
            rot = PLATE_ROT[key]
            if rot:
                th = math.radians(rot)
                ct, st = math.cos(th), math.sin(th)
                base = fn
                rfn = (lambda p, base=base, ct=ct, st=st: (
                    base(p)[0] * ct - base(p)[1] * st,
                    base(p)[0] * st + base(p)[1] * ct,
                    base(p)[2]))
                _, _, _, sup, tree = analyse(tris, rfn)
            over_tree = tree[0] > BED or tree[1] > BED
            margin = (BED - max(sup)) / 2.0
            print("      擺盤轉 %4.1f°  加支撐後佔床 %7.2f × %7.2f  餘量 %5.2f/邊  "
                  "（樹狀45° 會是 %7.2f × %7.2f %s）"
                  % (rot, sup[0], sup[1], margin, tree[0], tree[1],
                     "超出" if over_tree else "OK"))
            if margin < MIN_MARGIN:
                raise SystemExit(
                    f"{fname} 轉 {rot}° 加支撐後 {sup[0]:.2f} × {sup[1]:.2f}，"
                    f"餘量只有 {margin:.2f}/邊 < {MIN_MARGIN}"
                )
            if over_tree and key not in NO_SUPPORT:
                tree_bad.append((fname, tree))
    print("=" * 74)
    print("FILAMENT_VOLUME %.1f cm3（含份數）→ PETG @1.28 ≈ %.0f g"
          % (total, total * 1.28))
    if tree_bad:
        print("★ 這些件用 A1 預設的 `support_type = tree(auto)` 會超出床，"
              "必須改 `normal(auto)`：")
        for fname, tree in tree_bad:
            print("   %-24s 樹狀45° %7.2f × %7.2f > %.0f" % (fname, tree[0], tree[1], BED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
