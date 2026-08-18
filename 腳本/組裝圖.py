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

import os
import sys

import numpy as np
from PIL import ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "腳本"))

import 參數 as D  # noqa: E402
from 渲染預覽 import PARTS, STL_DIR, cjk_font, load_stl, render  # noqa: E402

OUT_DIR = os.path.join(ROOT, "規格")
STL_OF = D.STL_NAMES  # key → 檔名
COLOR_OF = {fn: c for fn, c, _ in PARTS}
PLACES_OF = {fn: p for fn, _, p in PARTS}

# 爆炸圖／逐步圖的拉開距離（沿裝入方向的反向）。ASSEMBLY_STEPS 只給 Y，
# 底板是基準件沒有方向 → 給它 −Z 讓它落在最下面。
EXPLODE = 1.6  # 爆炸圖把 ASSEMBLY_STEPS 的行程再乘這個倍率
STEP_FRAC = 0.42  # 逐步圖裡「還沒裝到底」的那一件停在行程的幾成


def part_tris(key, offset=(0.0, 0.0, 0.0), color=None):
    """讀某個列印件的 STL（含多實例擺放），套上平移。"""
    fn = STL_OF[key]
    t = load_stl(os.path.join(STL_DIR, fn))
    out = []
    for pl in PLACES_OF[fn] or [(0.0, 0.0, 0.0)]:
        out.append(t + np.asarray(pl, float) + np.asarray(offset, float))
    tri = np.concatenate(out)
    return tri, np.tile(np.asarray(color or COLOR_OF[fn], float), (len(tri), 1))


def insert_vec(key):
    """裝入方向（單位向量）與行程長度。唯一來源＝ASSEMBLY_STEPS。"""
    for k, dy in D.ASSEMBLY_STEPS:
        if k == key:
            if abs(dy) < 1e-9:
                return np.array([0.0, 0.0, -1.0]), 60.0  # 基準件：往下擺開
            return np.array([0.0, 1.0 if dy > 0 else -1.0, 0.0]), abs(dy)
    # 不在互鎖鏈上的（PCIe 壓條在機殼外、槽蓋、壓帽）
    return np.array([0.0, -1.0, 0.0]), 40.0


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
    planes = [(a, +1.0, lo[a]) for a in range(3)] + [(a, -1.0, -hi[a]) for a in range(3)]
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


def scene(pairs, eye=(0.72, -0.60, 0.35), up=(0, 0, 1), title="", size=(1400, 1000),
          section=None, colors=None):
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
        focus = np.array([[x, y, z] for x in lo[[0]].tolist() + hi[[0]].tolist()
                          for y in lo[[1]].tolist() + hi[[1]].tolist()
                          for z in lo[[2]].tolist() + hi[[2]].tolist()])
    return render(tri, col, eye, up, size=size, title=title, focus=focus)


def save(img, name):
    p = os.path.join(OUT_DIR, f"組裝_{name}.png")
    img.save(p)
    print("saved", p)


# ── ① 爆炸圖 ─────────────────────────────────────────────────────────
SPREAD = {  # 純為了看清楚的橫向位移（**不是**裝入方向；裝入方向見 ASSEMBLY_STEPS）
    "Side_Left_MB": (-150.0, 0.0, 0.0),
    "Side_Right_MB": (150.0, 0.0, 0.0),
    "Top_MB": (0.0, 0.0, 130.0),
    "Bottom_Tray": (0.0, 0.0, -70.0),
}


def exploded():
    pairs = []
    for i, (key, _) in enumerate(D.ASSEMBLY_STEPS):
        v, run = insert_vec(key)
        off = -v * min(run, 130.0) * EXPLODE * (0.30 + 0.16 * i)
        pairs.append((key, off + np.asarray(SPREAD.get(key, (0.0, 0.0, 0.0)), float)))
    # 不在互鎖鏈上的：壓條在機殼外（往 −Y 壓上去再往下落）、壓帽鎖在主板柱上
    pairs.append(("PCIeBar", np.array([0.0, -190.0, 0.0])))
    pairs.append(("MB_Nut", np.array([0.0, 0.0, -70.0])))
    save(scene(pairs, size=(1600, 1100),
               title="爆炸圖：沿各件真正的裝入方向拉開（唯一來源 ASSEMBLY_STEPS）；"
                     "側板／頂蓋另外橫向拉開純為了看清楚"),
         "爆炸圖")


# ── ② 逐步組裝 ───────────────────────────────────────────────────────
def steps():
    for i, (key, _) in enumerate(D.ASSEMBLY_STEPS):
        pairs = [(k, (0.0, 0.0, 0.0)) for k, _ in D.ASSEMBLY_STEPS[:i]]
        v, run = insert_vec(key)
        pairs.append((key, -v * min(run, 130.0) * STEP_FRAC))
        save(
            scene(pairs, title=f"第 {i + 1} 步 / {len(D.ASSEMBLY_STEPS)}：{key} 沿 "
                               f"{'+Y' if v[1] > 0 else ('-Y' if v[1] < 0 else '-Z')} 裝入"),
            f"步驟{i + 1}_{key}",
        )


# ── ③ 卡榫剖面特寫 ───────────────────────────────────────────────────
def closeups():
    """每一張都是**剖面盒**：盒子的近端面就是剖切面，鏡頭推到只剩十幾 mm 寬。"""
    xl, xr = D.CASE_LEFT, D.CASE_RIGHT
    y_sq = D.CASE_REAR + D.WALL + D.REAR_WEDGE_RAMP + D.REAR_WEDGE_BACK
    zd = D.REAR_DETENT_Z[1]
    yb = D.FLOOR_Y0 + D.FLOOR_DETENT_RUN  # 底板 bead 的 y
    # ★ 剖面盒的切面是**開口**（STL 是殼不是實體），正對著切面看等於看空氣：
    #   垂直牆面在正投影下是一條線。所以「俯視剖」一律用斜視角，讓牆面露出來。
    BACK, RIGHT = (0, -1, 0.001), (1, 0, 0.001)
    IN_L = (0.86, -0.34, 0.38)  # 自機殼內往左牆看（左牆的口袋朝 +X 開）
    DOWN_IN = (0.52, -0.22, 0.82)  # 自內上方斜看（俯視剖用）
    OUT_L_F = (-0.58, 0.26, 0.77)  # 自左外前上方斜看（前罩搭接用）
    IN_R_F = (-0.72, 0.48, 0.50)  # 自機殼內往右牆看、且偏 +Y（看得到朝前的止擋面）
    shots = (
        # (檔名, 兩件, 視線, up, 剖面盒 lo, 剖面盒 hi, 標題)
        ("A_底板與側板", ("Bottom_Tray", "Side_Left_MB"), BACK, (0, 0, 1),
         (xl - 1.5, yb - 24, -1.0), (xl + 8.0, yb - 1.0, 9.0),
         f"A 底板↔側板（後視剖）：側舌伸出 {D.FLOOR_LIP:.2f} 插進 "
         f"{D.FLOOR_LIP + D.SLIDE_FIT:.2f} 深的槽；槽下方 {D.FLOOR_LEDGE_T:.2f} "
         f"承載唇托著、槽上方 {D.WALL - D.FLOOR_LIP - D.SLIDE_FIT:.2f} 牆料壓著"),
        ("B_底板側緣bead", ("Bottom_Tray", "Side_Left_MB"), DOWN_IN, (0, 0, 1),
         (xl - 1.5, yb - 10, 0.0), (xl + 8.0, yb + 10, D.FLOOR_T - 0.2),
         f"B 底板側緣 bead（俯視剖 z={D.FLOOR_T / 2:.1f}）：凸 "
         f"{D.FLOOR_DETENT_DEPTH:.2f}，扣掉滑配 {D.SLIDE_FIT:.2f} 的過盈是 "
         f"{D.FLOOR_DETENT_DEPTH - D.SLIDE_FIT:.2f} → 側板滑到最後 "
         f"{D.floor_detent_run_mm():.0f} mm 才卡住"),
        ("C_後牆單向楔", ("Rear_IO_PCIe", "Side_Left_MB"), IN_L, (0, 0, 1),
         (xl - 0.5, D.CASE_REAR - 7.0, zd - 7.0), (xl + 5.0, D.CASE_REAR + 11.0, zd + 7.0),
         f"C 後牆↔側板 單向楔（橘＝後牆定位舌，藍＝側板；後牆退開 6 mm 好看清楚）："
         f"舌的缺口自根部往前開，楔的斜坡讓它推得進去、直角面 y={y_sq:.2f} 讓它拉不出來",
         (0.0, -6.0, 0.0)),
        ("D_底板與後牆", ("Bottom_Tray", "Rear_IO_PCIe"), RIGHT, (0, 0, 1),
         (D.REAR_FLOOR_DETENT_X[1] - 0.4, D.CASE_REAR - 1.0, -1.0),
         (D.REAR_FLOOR_DETENT_X[1] + 6.0, D.CASE_REAR + 6.0, 6.0),
         f"D 底板↔後牆（右視剖）：底板後舌插進後牆低位槽，槽下方 "
         f"{D.FLOOR_LEDGE_T:.2f} 承載唇；半球 detent 刻意保持可 cam-out ＝拆卸路徑"),
        ("E_頂蓋與側板", ("Top_MB", "Side_Left_MB"), BACK, (0, 0, 1),
         (xl - 1.5, 100.0, D.INNER_TOP_Z - 8.0), (xl + 8.0, 118.0, D.OUTER_TOP_Z + 1.0),
         f"E 頂蓋↔側板（後視剖）：側舌咬合 {D.TOP_LIP:.2f}（第九輪只有 0.40），"
         f"槽上方仍有 {D.WALL - D.TOP_LIP - D.SLIDE_FIT:.2f} 牆料 → 抬不起來"),
        ("F_碟架止擋", ("HDD_Rack", "Side_Right_MB"), IN_R_F, (0, 0, 1),
         (xr - 8.0, D.RACK_STOP_Y - 6.0, D.RACK_RAIL_Z0 - 4.0),
         (xr + 1.0, D.RACK_STOP_Y + 22.0, D.RACK_RAIL_Z1 + 4.0),
         f"F 碟架↔側板（右視剖）：槽的盲端 y={D.RACK_STOP_Y:.2f} ＝推到底的止擋面"
         f"（第十輪開到 179.34，碟架往 −Y 浮 3.00 mm）"),
        ("G_前罩搭接", ("Front_Shroud", "Side_Left_MB"), OUT_L_F, (0, 0, 1),
         (xl - 2.5, D.BAY_SPLIT_Y - D.SHROUD_LAP - 6.0, D.SHROUD_DETENT_Z[1] - 5.0),
         (xl + 6.0, D.BAY_SPLIT_Y + 6.0, D.SHROUD_DETENT_Z[1] + 5.0),
         f"G 前罩↔側板（俯視剖 z={D.SHROUD_DETENT_Z[1]:.0f}）：外表面減薄 "
         f"{D.SHROUD_LAP_T + D.SLIDE_FIT:.2f}、前罩殼 {D.SHROUD_LAP_T:.2f} 填回去 → 齊平；"
         f"半球 detent（唯一徒手可拆的蓋，刻意可 cam-out）"),
    )
    font = cjk_font(16)
    pair_col = ((214, 124, 44), (66, 112, 178))  # 兩件永遠一橘一藍，一眼分得出誰是誰
    for shot in shots:
        name, parts, eye, up, lo, hi, title = shot[:7]
        off0 = shot[7] if len(shot) > 7 else (0.0, 0.0, 0.0)
        img = scene([(parts[0], off0), (parts[1], (0.0, 0.0, 0.0))], eye=eye, up=up,
                    size=(1300, 820), section=(lo, hi), colors=pair_col)
        d = ImageDraw.Draw(img)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            d.text((14 + dx, 12 + dy), title, fill=(250, 250, 252), font=font)
        d.text((14, 12), title, fill=(18, 18, 22), font=font)
        save(img, name)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    exploded()
    steps()
    closeups()
    return 0


if __name__ == "__main__":
    sys.exit(main())
