# -*- coding: utf-8 -*-
"""組裝說明圖：爆炸圖 + 逐步組裝 + 卡榫剖面特寫 → 規格/組裝_*.png

    python 腳本\組裝圖.py

「看不出這機殼要怎麼組裝在一起」是**圖的問題不是模型的問題**：
滑槽咬合 1.30、detent 凸出 0.60，畫在 252×301×180 的總成上一個像素都不到。
所以這支腳本做三件探針做不到的事 ——
  ① 爆炸圖：每一件沿它自己的裝入方向拉開，一眼看到誰插進誰
  ② 逐步圖：第 i 張只畫第 0..i 件，第 i 件停在半路上（＝ASSEMBLY_STEPS 的方向）
  ③ 剖面特寫：切掉近端的料、只留兩件、把鏡頭推到卡榫上（放大 15~30 倍）

方向的唯一來源是 參數.ASSEMBLY_STEPS，和 verify 的逐步掃描同一份
（硬規則 9／22：文件講一套、掃描驗另一套，遲早對不起來）。
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
from PIL import ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "腳本"))

import 參數 as D  # noqa: E402
from 渲染預覽 import (  # noqa: E402
    PARTS,
    STL_DIR,
    cjk_font,
    load_stl,
    render,
    transform_tris,
)

OUT_DIR = os.path.join(ROOT, "規格")
STL_OF = D.STL_NAMES  # key → 檔名
COLOR_OF = {fn: c for fn, c, _ in PARTS}
PLACES_OF = {fn: p for fn, _, p in PARTS}

# 爆炸圖／逐步圖的拉開距離（沿裝入方向的反向）。Chassis 是基準件，
# `insert_vec()` 保持零位移；爆炸圖另由 SPREAD 向下拉開，逐步圖維持原點。
EXPLODE = 1.6  # 爆炸圖把 ASSEMBLY_STEPS 的行程再乘這個倍率
STEP_FRAC = 0.42  # 逐步圖裡「還沒裝到底」的那一件停在行程的幾成


def part_tris(key, offset=(0.0, 0.0, 0.0), color=None):
    """讀某個列印件的 STL（含數量實例與剛體變換），再套爆炸平移。"""
    fn = STL_OF[key]
    source = load_stl(os.path.join(STL_DIR, fn))
    out = []
    for transform in PLACES_OF[fn] or [(0.0, 0.0, 0.0)]:
        out.append(transform_tris(source, transform) + np.asarray(offset, float))
    tri = np.concatenate(out)
    return tri, np.tile(np.asarray(color or COLOR_OF[fn], float), (len(tri), 1))


def insert_vec(key):
    """裝入方向（單位向量）與行程長度。唯一來源＝ASSEMBLY_STEPS。"""
    for k, dy in D.ASSEMBLY_STEPS:
        if k != key:
            continue
        if abs(dy) < 1e-9:
            return np.zeros(3), 0.0
        return np.array([0.0, 1.0 if dy > 0 else -1.0, 0.0]), abs(dy)
    raise KeyError(f"{key} 不在 ASSEMBLY_STEPS")


def clip_box(tris, cols, lo, hi):
    """把三角形真的**裁進**一個 AABB（Sutherland–Hodgman ×6 面）→ 剖面視圖。

    ★ 不能用「重心在盒子裡」代替：側板的內面常常是一兩片跨滿 264×180 的大三角形，
      重心落在盒子外，但它整片擋在鏡頭前 —— 用重心判斷的第一版剖面圖就是這樣，
      切了等於沒切。這和硬規則 20 是同一件事：探點只回答它被寫出來要問的問題。
    """
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    tb0, tb1 = tris.min(axis=1), tris.max(axis=1)
    m = np.all((tb1 >= lo - 1e-9) & (tb0 <= hi + 1e-9), axis=1)  # 先用 bbox 粗篩
    tris, cols = tris[m], cols[m]
    planes = [(a, +1.0, lo[a]) for a in range(3)] + [
        (a, -1.0, -hi[a]) for a in range(3)
    ]
    ot, oc = [], []
    for t, c in zip(tris, cols):
        poly = [t[0], t[1], t[2]]
        for axis, sgn, lim in planes:
            if len(poly) < 3:
                break
            new, n = [], len(poly)
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                da, db = sgn * a[axis] - lim, sgn * b[axis] - lim
                if da >= 0:
                    new.append(a)
                if (da > 0) != (db > 0):
                    new.append(a + (b - a) * (da / (da - db)))
            poly = new
        for i in range(1, len(poly) - 1):
            ot.append([poly[0], poly[i], poly[i + 1]])
            oc.append(c)
    if not ot:
        raise SystemExit(f"剖面盒子裡沒有任何幾何：{lo} .. {hi}")
    return np.array(ot), np.array(oc)


def scene(
    pairs,
    eye=(0.72, -0.60, 0.35),
    up=(0, 0, 1),
    title="",
    size=(1400, 1000),
    section=None,
    colors=None,
):
    """pairs = [(key, offset)]；section=(lo, hi) 把畫面裁進一個世界座標盒子。"""
    tri, col = [], []
    for i, (key, off) in enumerate(pairs):
        t, c = part_tris(key, off, colors[i] if colors else None)
        tri.append(t)
        col.append(c)
    tri, col = np.concatenate(tri), np.concatenate(col)
    focus = None
    if section is not None:
        tri, col = clip_box(tri, col, *section)
        lo, hi = np.asarray(section[0], float), np.asarray(section[1], float)
        focus = np.array(
            [
                [x, y, z]
                for x in lo[[0]].tolist() + hi[[0]].tolist()
                for y in lo[[1]].tolist() + hi[[1]].tolist()
                for z in lo[[2]].tolist() + hi[[2]].tolist()
            ]
        )
    return render(tri, col, eye, up, size=size, title=title, focus=focus)


def save(img, name):
    p = os.path.join(OUT_DIR, f"組裝_{name}.png")
    img.save(p)
    print("saved", p)


# ── ① 爆炸圖 ─────────────────────────────────────────────────────────
SPREAD = {  # 純為了看清楚，不是裝入方向
    "Chassis_Body": (0.0, 0.0, -70.0),
    "Top_MB": (0.0, 0.0, 130.0),
}
if not set(SPREAD) <= set(D.STL_NAMES):
    raise SystemExit(f"SPREAD 含退役件：{sorted(set(SPREAD) - set(D.STL_NAMES))}")


def exploded():
    pairs = []
    for i, (key, _) in enumerate(D.ASSEMBLY_STEPS):
        vector, run = insert_vec(key)
        offset = -vector * min(run, 130.0) * EXPLODE * (0.30 + 0.16 * i)
        pairs.append(
            (key, offset + np.asarray(SPREAD.get(key, (0.0, 0.0, 0.0)), float))
        )
    # 不在滑入鏈上的固定件另外拉開：Bar 外抽、主板螺絲上提、槽蓋列為備件。
    pairs.extend(
        (
            ("PCIeBar", np.array((0.0, -190.0, 0.0))),
            ("MB_Screw", np.array((0.0, 0.0, 100.0))),
            ("PCIeBlank", np.array((0.0, -130.0, 0.0))),
        )
    )
    save(
        scene(
            pairs,
            size=(1600, 1100),
            title="爆炸圖：Chassis 是單一基準件；其餘沿 ASSEMBLY_STEPS 的反向拉開；"
            "PCIeBar／主板螺絲另列固定流程",
        ),
        "爆炸圖",
    )


# ── ② 逐步組裝 ───────────────────────────────────────────────────────
def steps():
    for i, (key, dy) in enumerate(D.ASSEMBLY_STEPS):
        pairs = [(k, (0.0, 0.0, 0.0)) for k, _ in D.ASSEMBLY_STEPS[:i]]
        if abs(dy) < 1e-9:
            pairs.append((key, (0.0, 0.0, 0.0)))
            action = "一體式基準件"
        else:
            v, run = insert_vec(key)
            pairs.append((key, -v * min(run, 130.0) * STEP_FRAC))
            action = f"沿 {'+Y' if v[1] > 0 else '-Y'} 裝入"
        save(
            scene(
                pairs,
                title=f"第 {i + 1} 步 / {len(D.ASSEMBLY_STEPS)}：{key} {action}",
            ),
            f"步驟{i + 1}_{key}",
        )


# ── ③ 卡榫剖面特寫 ───────────────────────────────────────────────────
def closeups():
    """第十二輪接合特寫；每張只留兩件並以 AABB 真裁切。"""
    down_in = (0.52, -0.22, 0.82)
    in_left = (0.86, -0.34, 0.38)
    top_x = D.TOP_DETENT_X[0]
    lock_x = D.pcie_lock_x()[0]
    mb_x, mb_y = D.HOLES_MM["B"]
    shots = (
        (
            "A_Top側槽",
            ("Chassis_Body", "Top_MB"),
            down_in,
            (0, 0, 1),
            (D.CASE_LEFT - 1.5, 100.0, D.INNER_TOP_Z - 8.0),
            (D.CASE_LEFT + 8.0, 118.0, D.OUTER_TOP_Z + 1.0),
            f"A Top與Chassis：側舌咬合 {D.TOP_LIP:.2f} mm；槽背仍留 "
            f"{D.WALL - D.TOP_LIP - D.SLIDE_FIT:.2f} mm 牆料",
        ),
        (
            "B_Top後鉤detent",
            ("Chassis_Body", "Top_MB"),
            down_in,
            (0, 0, 1),
            (top_x - 5.0, D.FLOOR_Y0 - 1.0, D.OUTER_TOP_Z - 5.0),
            (top_x + 5.0, D.FLOOR_Y0 + D.TOP_HOOK_D + 3.0, D.OUTER_TOP_Z + 1.0),
            f"B Top 後鉤 detent：R{D.TOP_DETENT_R:.2f}、凸出 {D.TOP_DETENT_DEPTH:.2f}；"
            "只在最後 6 mm 越過，拆 Front 後可沿 +Y cam-out",
        ),
        (
            "C_Rack底部格柵",
            ("HDD_Rack", "HDD_Tray"),
            (0.52, -0.22, -0.82),
            (0, 0, 1),
            (
                D.RACK_BASE_SPINE_X - 18.0,
                min(D.RACK_BASE_BEAM_Y) - D.RACK_BASE_BEAM_W / 2.0 - 2.0,
                D.RACK_Z0 - 1.0,
            ),
            (
                D.RACK_BASE_SPINE_X + 18.0,
                max(D.RACK_BASE_BEAM_Y) + D.RACK_BASE_BEAM_W / 2.0 + 2.0,
                D.HDD_Z0 + 13.0,
            ),
            f"C Rack 格柵（托盤示意上提 8 mm）：三條 {D.RACK_BASE_BEAM_W:.0f} mm "
            f"橫樑由中央 {D.RACK_BASE_SPINE_W:.0f} mm 縱樑連接；"
            f"實際落位間隙 {D.SLIDE_FIT:.2f} mm",
        ),
        (
            "D_Rack盲端止擋",
            ("Chassis_Body", "HDD_Rack"),
            (-0.72, 0.48, 0.50),
            (0, 0, 1),
            (D.CASE_RIGHT - 8.0, D.RACK_STOP_Y - 6.0, D.RACK_RAIL_Z0 - 4.0),
            (D.CASE_RIGHT + 1.0, D.RACK_STOP_Y + 22.0, D.RACK_RAIL_Z1 + 4.0),
            f"D Rack與Chassis：側槽盲端 y={D.RACK_STOP_Y:.2f} 限制 −Y；"
            f"最後只保留 {D.SLIDE_FIT:.2f} mm play",
        ),
        (
            "E_Front導入與detent",
            ("Front_Shroud", "Chassis_Body"),
            (-0.86, -0.34, 0.38),
            (0, 0, 1),
            (
                D.CASE_LEFT - 2.5,
                D.SHROUD_Y0 - D.SHROUD_LAP - 2.0,
                D.SHROUD_DETENT_Z[1] - 6.0,
            ),
            (D.CASE_LEFT + 6.0, D.BAY_SPLIT_Y + 4.0, D.SHROUD_DETENT_Z[1] + 6.0),
            f"E Front與Chassis（Front 示意沿 +Y 拉開 10 mm）：搭接 "
            f"{D.SHROUD_LAP:.0f} mm、後緣 {D.SHROUD_LEAD_IN:.0f} mm×45° 導入；"
            "實際落位由半球 detent 保持可拆",
        ),
        (
            "F_主板盲牙螺絲",
            ("Chassis_Body", "MB_Screw"),
            in_left,
            (0, 0, 1),
            (mb_x - 7.0, mb_y - 7.0, D.FLOOR_T - 1.0),
            (mb_x + 0.1, mb_y + 7.0, D.MB_SCREW_HEAD_TOP_Z + 2.0),
            f"F 主板固定：Ø{D.SHOULDER_OD:.0f}×{D.SHOULDER_H:.2f} 支撐肩、"
            f"{D.MB_SOCKET_DEPTH:.2f} mm 盲內牙、8 mm AF 印製螺絲",
        ),
        (
            "G_PCIe雙螺絲座",
            ("Chassis_Body", "PCIeBar"),
            (0.18, -0.96, 0.22),
            (0, 0, 1),
            (
                lock_x - 10.0,
                D.pcie_bar_mount_y() - D.PCIE_BAR_T - 3.0,
                D.PCIE_LOCK_Z - 10.0,
            ),
            (lock_x + 10.0, D.CASE_REAR + 3.0, D.PCIE_LOCK_Z + 10.0),
            f"G PCIe：5 mm Bar 的 Ø{D.PCIE_BAR_HOLE_D:.2f} 通孔 + "
            f"Ø{D.PCIE_BAR_CBORE_D:.2f} 沉頭凹，對準繫樑上的 "
            f"{D.MB_SOCKET_DEPTH:.2f} mm 印製盲內牙；2× MB_Screw 鎖固",
        ),
        (
            "H_PCIe尖頂與承托肩",
            ("Chassis_Body", "HDD_Rack"),
            (-0.72, 0.48, 0.50),
            (0, 0, 1),
            (
                D.CASE_RIGHT - 14.0,
                D.RACK_LEDGE_Y0 - 2.0,
                D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET - 4.0,
            ),
            (D.CASE_RIGHT + 1.0, D.RACK_LEDGE_Y0 + 22.0, D.RACK_RAIL_Z1 + 4.0),
            f"H 碟架承托肩：牆內面伸出 {D.RACK_LEDGE_D:.0f} mm 承重面 + 45° 斜撐；"
            f"肩頂 {D.RACK_LEDGE_Z1:.2f} 比橫樑底低 {D.SLIDE_FIT:.2f}（載重才坐實）",
        ),
    )
    font = cjk_font(16)
    pair_colors = ((214, 124, 44), (66, 112, 178))
    for name, parts, eye, up, lo, hi, title in shots:
        first_offset = (
            (0.0, 10.0, 0.0) if name == "E_Front導入與detent" else (0.0, 0.0, 0.0)
        )
        second_offset = (0.0, 0.0, 8.0) if name == "C_Rack底部格柵" else (0.0, 0.0, 0.0)
        image = scene(
            [(parts[0], first_offset), (parts[1], second_offset)],
            eye=eye,
            up=up,
            size=(1300, 820),
            section=(lo, hi),
            colors=pair_colors,
        )
        draw = ImageDraw.Draw(image)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            draw.text((14 + dx, 12 + dy), title, fill=(250, 250, 252), font=font)
        draw.text((14, 12), title, fill=(18, 18, 22), font=font)
        save(image, name)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for stale in glob.glob(os.path.join(OUT_DIR, "組裝_*.png")):
        os.remove(stale)
    exploded()
    steps()
    closeups()
    return 0


if __name__ == "__main__":
    sys.exit(main())
