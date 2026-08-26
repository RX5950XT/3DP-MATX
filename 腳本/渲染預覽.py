# -*- coding: utf-8 -*-
"""無 GUI 總成預覽：讀 列印件/*.stl → z-buffer 著色 → 規格/總成視圖_*.png

FreeCADCmd 沒有 GUI，無法用 get_view 截圖；本檔用純 numpy/PIL 光柵化補上
「每次改完要看一眼」這一步。

    python 腳本/渲染預覽.py                    # 四視角總成
    python 腳本/渲染預覽.py 機殼本體_主板段一體式  # 單件
"""

from __future__ import annotations

import glob
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# PIL 內建點陣字沒有 CJK → 標題會整排變成豆腐格。圖上的字是這些圖唯一的說明，
# 掉了就等於沒畫。找不到中文字型就直接爆，不要默默輸出看不懂的圖。
_FONTS = (r"C:\Windows\Fonts\msjh.ttc", r"C:\Windows\Fonts\msyh.ttc",
          r"C:\Windows\Fonts\simhei.ttf")


def cjk_font(size=17):
    for p in _FONTS:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    raise SystemExit(f"找不到中文字型（試過 {_FONTS}）")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STL_DIR = os.path.join(ROOT, "列印件")
OUT_DIR = os.path.join(ROOT, "規格")

sys.path.insert(0, os.path.join(ROOT, "腳本"))
import 參數 as D  # noqa: E402

# (檔名, RGB, 實例變換)。變換為 (tx,ty,tz) 或 (tx,ty,tz,rx,ry,rz)。
# None＝STL 已是總成座標；角度單位為 degree、依 X/Y/Z 套用。
PARTS = (
    ("機殼本體_主板段一體式.stl", (48, 110, 210), None),
    ("頂蓋_主板段.stl", (198, 202, 208), None),
    ("前罩_含進氣柵.stl", (36, 138, 88), None),
    ("碟架_四層導軌.stl", (90, 100, 120), None),
    (
        "碟托盤.stl",
        (60, 170, 200),
        [(0.0, 0.0, D.tray_z0(level)) for level in range(D.HDD_LEVELS)],
    ),
    (
        "PCIe槽蓋.stl",
        (217, 217, 224),
        [
            (
                cx - D.PCIE_BRACKET_W / 2,
                D.PCIE_BRACKET_Y1,
                D.PCIE_TANG_Z0,
                90.0,
                0.0,
                0.0,
            )
            for cx in D.pcie_centers()
        ],
    ),
    ("PCIe壓條_外置.stl", (230, 90, 50), None),
    (
        "主板螺絲_印製.stl",
        (242, 140, 26),
        [
            (hx, hy, D.BOARD_TOP_Z + D.MB_SCREW_HEAD_H, 180.0, 0.0, 0.0)
            for hx, hy in D.HOLES_MM.values()
        ]
        # ★ 第十三輪：同一顆螺絲也鎖 PCIeBar（軸沿 +Y ⇒ 繞 X 轉 270°）。
        #   只畫主板那九顆的話，總成圖會少掉兩顆真的存在的緊固件。
        + [
            (
                hx,
                D.pcie_bar_mount_y() - D.PCIE_BAR_SEAT_T - D.MB_SCREW_HEAD_H,
                D.PCIE_LOCK_Z,
                270.0,
                0.0,
                0.0,
            )
            for hx in D.pcie_lock_x()
        ],
    ),
)

_part_files = [part[0] for part in PARTS]
_expected_files = set(D.STL_NAMES.values())
if set(_part_files) != _expected_files or len(_part_files) != len(_expected_files):
    raise SystemExit(
        "PARTS 與 manifest 不一致："
        f"missing={sorted(_expected_files - set(_part_files))} "
        f"extra={sorted(set(_part_files) - _expected_files)} "
        f"duplicates={len(_part_files) - len(set(_part_files))}"
    )

VIEWS = (
    ("iso", (0.72, -0.60, 0.35), (0, 0, 1), "ISO"),
    ("rear", (0, -1, 0.001), (0, 0, 1), "後視：I/O 左 / PCIe 右"),
    ("right", (1, 0, 0.001), (0, 0, 1), "右視"),
    ("top", (0, 0.001, 1), (0, 1, 0), "俯視"),
)


def load_stl(path):
    """二進位 STL → (n,3,3) 頂點陣列。"""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 84:
        raise ValueError(f"STL 太短: {path}")
    n = struct.unpack("<I", data[80:84])[0]
    if len(data) < 84 + n * 50:
        raise ValueError(f"STL 長度與三角數不符: {path}")
    arr = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    return arr[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(np.float64)


def transform_tris(tris, transform):
    """對列印姿態 STL 套組裝用剛體變換。"""
    values = tuple(float(v) for v in transform)
    if len(values) not in (3, 6):
        raise ValueError(f"實例變換必須有 3 或 6 個值：{transform}")
    out = tris.copy()
    if len(values) == 6:
        tx, ty, tz, rx, ry, rz = values
        for degrees, matrix in (
            (rx, lambda c, s: np.array(((1, 0, 0), (0, c, -s), (0, s, c)))),
            (ry, lambda c, s: np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)))),
            (rz, lambda c, s: np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))),
        ):
            radians = np.deg2rad(degrees)
            out = out @ matrix(np.cos(radians), np.sin(radians)).T
    else:
        tx, ty, tz = values
    return out + np.array((tx, ty, tz), dtype=float)


def render(tris, cols, eye, up, size=(1100, 820), bg=(250, 250, 252), title="",
           focus=None):
    """`focus`：世界座標點集，用它（而不是全部幾何）決定取景框 → 卡榫特寫用。"""
    eye = np.asarray(eye, float)
    eye = eye / np.linalg.norm(eye)
    right = np.cross(np.asarray(up, float), eye)
    right /= np.linalg.norm(right)
    up = np.cross(eye, right)
    M = np.stack([right, up, eye]).T
    P = (tris.reshape(-1, 3) @ M).reshape(-1, 3, 3)

    flat = np.asarray(focus, float) @ M if focus is not None else P.reshape(-1, 3)
    ctr = (flat.min(0) + flat.max(0)) / 2
    span = max(np.ptp(flat[:, 0]), np.ptp(flat[:, 1])) * 1.06
    W, H = size
    s = min(W, H) / span
    xs = (P[:, :, 0] - ctr[0]) * s + W / 2
    ys = H / 2 - (P[:, :, 1] - ctr[1]) * s
    zc = -P[:, :, 2]  # 相機 +Z 朝觀察者 → 取負後「小」= 近

    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    ln[ln == 0] = 1.0
    light = np.array([0.45, -0.55, 0.70])
    light /= np.linalg.norm(light)
    shade = 0.30 + 0.70 * np.abs((nrm / ln[:, None]) @ light)
    rgb = np.clip(cols * shade[:, None], 0, 255).astype(np.uint8)

    zbuf = np.full((H, W), np.inf)
    fb = np.empty((H, W, 3), np.uint8)
    fb[:] = bg
    x0 = np.floor(xs.min(1)).astype(int)
    x1 = np.ceil(xs.max(1)).astype(int)
    y0 = np.floor(ys.min(1)).astype(int)
    y1 = np.ceil(ys.max(1)).astype(int)

    for i in np.nonzero((x1 >= 0) & (x0 < W) & (y1 >= 0) & (y0 < H))[0]:
        ax, bx, cx = xs[i]
        ay, by, cy = ys[i]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        px0, px1 = max(x0[i], 0), min(x1[i] + 1, W)
        py0, py1 = max(y0[i], 0), min(y1[i] + 1, H)
        if abs(det) < 1e-9 or px0 >= px1 or py0 >= py1:
            continue
        gx, gy = np.meshgrid(np.arange(px0, px1) + 0.5, np.arange(py0, py1) + 0.5)
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l3 = 1.0 - l1 - l2
        m = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not m.any():
            continue
        z = l1 * zc[i, 0] + l2 * zc[i, 1] + l3 * zc[i, 2]
        sub = zbuf[py0:py1, px0:px1]
        upd = m & (z < sub)
        sub[upd] = z[upd]
        fb[py0:py1, px0:px1][upd] = rgb[i]

    img = Image.fromarray(fb)
    if title:
        ImageDraw.Draw(img).text((14, 12), title, fill=(30, 30, 34), font=cjk_font())
    return img


def collect(names=None):
    tri, col = [], []
    wanted = [(f"{n}.stl", (48, 110, 210), None) for n in names] if names else PARTS
    for fn, c, places in wanted:
        path = os.path.join(STL_DIR, fn)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        t = load_stl(path)
        transforms = places or [(0.0, 0.0, 0.0)]
        for transform in transforms:
            inst = transform_tris(t, transform)
            tri.append(inst)
            col.append(np.tile(np.asarray(c, float), (len(inst), 1)))
        print(f"{fn}: {len(t)} tri x{len(transforms)}")
    return np.concatenate(tri), np.concatenate(col)


def main(argv):
    os.makedirs(OUT_DIR, exist_ok=True)
    for removed in D.REMOVED_STL:
        stem = os.path.splitext(removed)[0]
        for stale in glob.glob(os.path.join(OUT_DIR, f"{stem}視圖_*.png")):
            os.remove(stale)
    names = argv[1:] or None
    tris, cols = collect(names)
    tag = "_".join(names) if names else "總成"
    views = VIEWS if not names else VIEWS[:1]
    for key, eye, up, title in views:
        out = os.path.join(OUT_DIR, f"{tag}視圖_{key}.png")
        render(tris, cols, eye, up, title=f"{tag} {title}").save(out)
        print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
