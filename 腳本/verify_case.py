# FreeCAD verification — 主板平躺 + 電源上置 + 碟艙打通 + 單一長方體（第七輪）
from __future__ import annotations

import itertools
import math
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _load_params import load_params

D = load_params()

import FreeCAD as App
import Part

import build_case as B  # 壓帽的相位驗算要用 place_mb_nut / make_mb_nut

PATHS = D.project_paths()
DOC_PATH = os.path.join(PATHS["cad"], D.FCSTD_NAME)
STL_DIR = PATHS["stl"]
SCRATCH = os.environ.get(
    "GROK_SCRATCH",
    os.path.join(PATHS["root"], "測試", "verify_out"),
)
os.makedirs(SCRATCH, exist_ok=True)

TOL, INTERFERE_MAX = 0.5, 1.0
FAN_AREA_120 = math.pi * 60.0 ** 2  # 11310 mm²：電源 120 風扇的迎風面積
failures, lines = [], []


def log(m):
    lines.append(m)
    print(m)


def approx(a, b, tol=TOL):
    return abs(a - b) <= tol


def fail(m):
    failures.append(m)
    log("FAIL: " + m)


def ok(m):
    log("OK: " + m)


def warn(m):
    log("WARN: " + m)


def common_vol(a, b):
    try:
        c = a.common(b)
        return 0.0 if c.isNull() else float(c.Volume)
    except Exception:
        return -1.0


def pt_inside(shape, x, y, z, tol=0.15):
    return shape.isInside(App.Vector(x, y, z), tol, True)


def obb(shape):
    """
    `Shape.BoundBox` 對 B-spline 面是用**控制多邊形**算的，會虛胖
    （實測壓帽真高 5.00 卻回報 10.00）。量尺寸一律走真外接盒。
    """
    try:
        return shape.optimalBoundingBox(True)
    except Exception:
        return shape.BoundBox


def mk_box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def _minus_stud_keepouts(shape):
    """挖掉九孔的 0.400" 方形 keepout：那是規範允許機殼柱碰板的唯一區域。"""
    k = D.MB_KEEPOUT_D / 2
    for hx, hy in D.HOLES_MM.values():
        shape = shape.cut(mk_box(hx - k, hy - k, -50.0, hx + k, hy + k, 400.0))
    return shape


def hardware_mocks():
    """
    真實硬體的標稱包絡 + **規格淨空區**。鋼盒／鋼擋板／鑄件不會為了塑膠退讓，
    規格寫的淨空更不會。兩者一律要求交集 ≤ INTERFERE_MAX。
    """
    yin = D.CASE_REAR + D.WALL
    m = {}
    m["PSU_150x86x140"] = mk_box(D.ATX_X0, D.ATX_Y0, D.ATX_Z0, D.ATX_X1, D.ATX_Y1, D.ATX_Z1)
    # 第八輪：碟**平躺** 4 層（147 沿 X、101.6 沿 Y、26.1 沿 Z），接頭端朝 +X
    for lv in range(D.HDD_LEVELS):
        hx, hy, hz = D.hdd_drive_origin(lv)
        m[f"HDD_L{lv}"] = mk_box(hx, hy, hz, hx + D.HDD_L, hy + D.HDD_W, hz + D.HDD_H)
        # ★ 第九輪新增：**接頭 + 線的包絡**。第八輪的虛擬件只有「碟的長方體」，
        #   於是右立板整片貼在 101.6×26.1 的接頭端面上（四層各 15.8–18.0 cm³）
        #   八輪都沒被抓到 —— **虛擬件缺一塊，那一塊就永遠是綠的**。
        #   涵蓋整個端面是刻意的：SATA 接頭沿端面的確切位置在 SFF-8323，
        #   本專案 參考/ 底下沒有那份規格 → 不猜位置，整面讓開。
        m[f"HDD_L{lv}_接頭"] = mk_box(
            hx + D.HDD_L, hy, hz, hx + D.HDD_L + D.HDD_CABLE_W, hy + D.HDD_W, hz + D.HDD_H
        )
    bw, tw = D.PCIE_BRACKET_W / 2, D.PCIE_TANG_W / 2
    by0, by1 = D.PCIE_BRACKET_Y0, D.PCIE_BRACKET_Y1
    for i, cx in enumerate(D.pcie_centers()):
        br = mk_box(cx - bw, by0, D.PCIE_Z0, cx + bw, by1, D.PCIE_Z1)
        br = br.fuse(mk_box(cx - tw, by0, D.PCIE_TANG_Z0, cx + tw, by1, D.PCIE_Z0))
        m[f"PCIe{i}_bracket"] = br
        m[f"PCIe{i}_card"] = mk_box(
            cx - D.PCIE_CARD_HALF_W,
            yin,
            D.PCIE_CARD_Z0,
            cx + D.PCIE_CARD_HALF_W,
            yin + D.PCIE_CARD_LEN,
            D.PCIE_CARD_Z1,
        )
        m[f"PCIe{i}_耳keepout"] = mk_box(
            cx - bw, by1, D.PCIE_Z1 - D.PCIE_EAR_BAND, cx + bw, by1 + D.PCIE_EAR_CLEAR, D.PCIE_Z1
        )
    # ★ 第十輪新增：**電源按鈕本體**。`PWR_BTN_DEPTH = 22.0` 帶著「本體 22 深伸進
    #   主板前方的空腔，不撞任何東西」這句註解躺了兩輪，**沒有任何檢查在問它**
    #   （硬規則 15）。開機是機殼的職責（硬規則 17），按鈕裝不進去等於機殼不能用。
    bx = D.pwr_btn_x()
    r_nut = D.PWR_BTN_NUT_D / 2
    y_face = D.CASE_FRONT - D.TRAY_FACE_T
    m["電源按鈕本體"] = mk_box(
        bx - r_nut, y_face - D.PWR_BTN_DEPTH, D.PWR_BTN_Z - r_nut,
        bx + r_nut, y_face, D.PWR_BTN_Z + r_nut,
    )
    pcb = mk_box(
        D.BOARD_LEFT, D.BOARD_REAR, D.BOARD_TOP_Z - D.PCB_T, D.BOARD_RIGHT, D.BOARD_FRONT,
        D.BOARD_TOP_Z,
    )
    r = D.PCB_HOLE_D / 2
    for hx, hy in D.HOLES_MM.values():
        pcb = pcb.cut(
            mk_box(hx - r, hy - r, D.BOARD_TOP_Z - D.PCB_T - 1, hx + r, hy + r, D.BOARD_TOP_Z + 1)
        )
    m["主板PCB"] = pcb

    # ── 規格淨空區（microATX 1.2 §2.4.1 Fig.7 / §2.4.2）──────────────
    # 「chassis features should not extend into the motherboard component area」
    # 這四塊就是把那句話變成可以做布林的東西。九孔 keepout 方形挖掉（規範允許柱碰板）。
    m["淨空_板底6.35"] = _minus_stud_keepouts(
        mk_box(
            D.BOARD_LEFT, D.BOARD_REAR, D.FLOOR_T, D.BOARD_RIGHT, D.BOARD_FRONT, D.SHOULDER_TOP_Z
        )
    )
    zb = D.BOARD_TOP_Z
    m["淨空_AreaB_15.24"] = _minus_stud_keepouts(
        mk_box(D.AREA_B_X0, D.BOARD_REAR, zb, D.BOARD_RIGHT, D.BOARD_FRONT, D.AREA_B_TOP_Z)
    )
    area_a = mk_box(D.BOARD_LEFT, D.BOARD_REAR, zb, D.AREA_A_STEP_X, D.AREA_A_Y_NEAR, D.AREA_A_TOP_Z)
    area_a = area_a.fuse(
        mk_box(D.AREA_A_STEP_X, D.BOARD_REAR, zb, D.AREA_B_X0, D.AREA_A_Y_FAR, D.AREA_A_TOP_Z)
    )
    # ★ 第八輪這塊是 **50.00**（使用者實測散熱器高），不是 Table 6 的 88.90／76.20。
    #   名字帶著數字是故意的：改了淨空卻沒改名，這條檢查就會變成謊言。
    m[f"淨空_AreaA_{D.AREA_A_CLEARANCE:.2f}"] = _minus_stud_keepouts(area_a)
    area_c = mk_box(
        D.BOARD_LEFT, D.AREA_A_Y_NEAR, zb, D.AREA_A_STEP_X, D.BOARD_FRONT, D.AREA_C_TOP_Z
    )
    area_c = area_c.fuse(
        mk_box(D.AREA_A_STEP_X, D.AREA_A_Y_FAR, zb, D.AREA_B_X0, D.BOARD_FRONT, D.AREA_C_TOP_Z)
    )
    m["淨空_AreaC_38.10"] = _minus_stud_keepouts(area_c)
    return m


# microATX 1.2 Fig.7 p18（intel 座標，Datum B 原點）——literal，不從參數導出
SPEC_HOLES_INTEL = {
    "B": (0.00, 0.00),
    "C": (45.72, 0.00),
    "F": (203.20, 22.86),
    "R": (-20.32, 154.94),
    "S": (0.00, 154.94),
    "H": (45.72, 154.94),
    "J": (203.20, 154.94),
    "L": (45.72, 227.33),
    "M": (203.20, 227.33),
}


def main():
    log("=== 3DP-MATX verify (第九輪：碟架承載/走線 · 前罩貼合 · PCIe 結構) ===")
    if not os.path.isfile(DOC_PATH):
        fail(f"missing {DOC_PATH}")
        write_outs()
        return 1
    if "mATX_Case_Full" in App.listDocuments():
        App.closeDocument("mATX_Case_Full")
    doc = App.openDocument(DOC_PATH)
    names = [o.Name for o in doc.Objects]
    log("objects: " + ", ".join(names))

    required = list(D.STL_NAMES)  # 硬規則 7：不手列
    shapes = {}
    for r in required:
        if r not in names:
            fail(f"missing {r}")
        else:
            ok(f"object {r}")
            shapes[r] = doc.getObject(r).Shape
    for bad in D.REMOVED_SHELL_PARTS:
        if bad in names:
            fail(f"forbidden part still present: {bad}")
        else:
            ok(f"no {bad}")

    tray = shapes.get("Bottom_Tray")
    rear = shapes.get("Rear_IO_PCIe")
    rack = shapes.get("HDD_Rack")
    dtray = shapes.get("HDD_Tray")
    shroud = shapes.get("Front_Shroud")
    side_l, side_r = shapes.get("Side_Left_MB"), shapes.get("Side_Right_MB")
    nut, bar = shapes.get("MB_Nut"), shapes.get("PCIeBar")

    # ── 列印件必須是單一封閉實體 ──────────────────────────────
    log("--- solids ---")
    for key in D.STRUCT_PART_KEYS:
        sh = shapes.get(key)
        if sh is None:
            continue
        n = len(sh.Solids)
        if n == 1 and sh.isValid() and sh.isClosed():
            ok(f"{key} single closed solid")
        else:
            fail(f"{key} solids={n} valid={sh.isValid()} closed={sh.isClosed()}")

    # ── 九孔與板緣：逐顆對 microATX Fig.7 的 literal ────────────────
    # 第七輪的第一號缺陷。舊值把 Fig.3 的 `.900[22.86]` 當成「後緣→B 列」，
    # 於是七顆孔與兩條板緣全錯；真板前緣其實在 233.68，會撞碟艙 12.7 mm。
    log("--- microATX 九孔 / 板緣（Fig.7 p18 literal）---")
    for k, (ix, iy) in SPEC_HOLES_INTEL.items():
        want = (-ix, iy)
        got = D.HOLES_MM.get(k)
        if got and approx(got[0], want[0], 0.01) and approx(got[1], want[1], 0.01):
            ok(f"hole {k} = {got} (Fig.7 intel {ix},{iy} 鏡像)")
        else:
            fail(f"hole {k} = {got} != {want}")
    for tag, gotv, want in (
        ("BOARD_REAR", D.BOARD_REAR, -10.16),
        ("BOARD_FRONT", D.BOARD_FRONT, 233.68),
        ("BOARD_LEFT", D.BOARD_LEFT, -209.55),
        ("BOARD_RIGHT", D.BOARD_RIGHT, 34.29),
        ("板寬", D.BOARD_W, 243.84),
        ("板深", D.BOARD_D, 243.84),
    ):
        (ok if approx(gotv, want, 0.01) else fail)(f"{tag}={gotv:.2f} (spec {want})")
    if D.HOLES_MM["F"][1] > 20.0 and D.HOLES_MM["R"][1] > 150.0:
        ok("舊的 (F y=0 / R 列 132.08) 沒有復活")
    else:
        fail("九孔 Y 又退回舊值（F 那顆不在 B 列上，Fig.7 標的是 .900=22.86）")

    # ── 主板柱：階梯圓柱 + 印製壓帽（硬規則 6 三關）────────────────
    log("--- MB standoff (印製螺柱 + 壓帽) ---")
    stale = [
        g for g in ("CAP_OD", "CAP_H", "CAP_COUNT", "MB_SCREW_TAP", "MB_SCREW_DEPTH",
                    "MB_SCREW_HEAD_D") if hasattr(D, g)
    ]
    if stale:
        fail(f"上一版主板固定的參數還在：{stale}")
    else:
        ok("舊旋蓋／M3 自攻參數已清除")
    depth = (D.MB_STUD_MAJOR - D.MB_STUD_MINOR) / 2
    (ok if depth >= 0.5 - 1e-9 else fail)(f"關卡1 徑向牙深 {depth:.2f} >= 0.5")
    (ok if D.MB_NUT_OD < D.MB_KEEPOUT_D else fail)(
        f"關卡2 壓帽 Ø{D.MB_NUT_OD} < 九孔 keepout Ø{D.MB_KEEPOUT_D}"
    )
    (ok if D.MB_STUD_MAJOR < D.PCB_HOLE_D else fail)(
        f"細軸 Ø{D.MB_STUD_MAJOR} < 主板孔 Ø{D.PCB_HOLE_D}"
        f"（單邊 {(D.PCB_HOLE_D - D.MB_STUD_MAJOR) / 2:.2f}）"
    )
    crest = D.MB_STUD_PITCH * (1.0 - D.MB_STUD_ROOT_W) - 2 * D.MB_NUT_GAP
    (ok if crest >= 0.4 else fail)(f"壓帽內牙牙頂寬 {crest:.2f} >= 0.4（噴頭）")
    (ok if D.MB_NUT_H >= 2.0 * D.MB_STUD_PITCH else fail)(
        f"旋合 {D.MB_NUT_H / D.MB_STUD_PITCH:.1f} 圈"
    )
    (ok if approx(D.MB_STUD_LEN, D.PCB_T + D.MB_NUT_H + 1.0, 1e-6) else fail)(
        f"細軸長 {D.MB_STUD_LEN:.2f} = 板厚 + 壓帽 + 1.0（導出，非寫死）"
    )
    (ok if approx(D.SHOULDER_TOP_Z - D.FLOOR_T, 6.35, 1e-6) else fail)(
        f"粗肩高 {D.SHOULDER_TOP_Z - D.FLOOR_T:.2f} = 板底淨空 6.35（§2.4.2）"
    )
    if tray:
        tb = obb(tray)
        (ok if approx(tb.ZMax, D.MB_STUD_TOP_Z, 0.05) else fail)(
            f"tray ZMax={tb.ZMax:.2f} = 細軸頂 {D.MB_STUD_TOP_Z:.2f}"
        )
        z_floor = D.FLOOR_T + 0.3
        z_board = D.SHOULDER_TOP_Z + D.PCB_T / 2
        r_maj, r_sh = D.MB_STUD_MAJOR / 2, D.SHOULDER_OD / 2
        for letter, (hx, hy) in D.HOLES_MM.items():
            if not pt_inside(tray, hx, hy, z_floor, 0.02):
                fail(f"standoff {letter}: 粗肩沒有實心")
            elif not pt_inside(tray, hx, hy, D.SHOULDER_TOP_Z + 1.0, 0.02):
                fail(f"standoff {letter}: 細軸不存在")
            elif pt_inside(tray, hx + r_maj + 0.20, hy, z_board, 0.02):
                fail(f"standoff {letter}: 板厚高度有超出 Ø{D.MB_STUD_MAJOR} 的料 — 板穿不過")
            elif not pt_inside(tray, hx + r_sh - 0.6, hy, z_floor, 0.02):
                fail(f"standoff {letter}: 粗肩被掏空")
            else:
                ok(f"standoff {letter} 粗肩 Ø{D.SHOULDER_OD} + 細軸 Ø{D.MB_STUD_MAJOR}")
    if nut is not None:
        nb = obb(nut)
        if approx(nb.ZMin, D.BOARD_TOP_Z, 0.05) and approx(nb.ZMax, D.BOARD_TOP_Z + D.MB_NUT_H, 0.05):
            ok(f"壓帽底面壓在板面 z={nb.ZMin:.2f}，高 {D.MB_NUT_H}")
        else:
            fail(f"壓帽 z={nb.ZMin:.2f}..{nb.ZMax:.2f} 沒壓在板面 {D.BOARD_TOP_Z:.2f}")
        od = max(nb.XLength, nb.YLength)
        (ok if od <= D.MB_KEEPOUT_D else fail)(f"壓帽實際外徑 {od:.2f} <= keepout {D.MB_KEEPOUT_D}")

    # ── 電源上置（本輪主訴）────────────────────────────────────────
    log("--- 電源上置 / Area A 淨空 ---")
    for g in ("DECK_Z", "BASE_T", "SIDE_CABLE_W", "DECK_CABLE_W", "PSU_VENT_W", "FOOT_H",
              "TENON", "JOIN_SIDE_Y"):
        if hasattr(D, g):
            fail(f"甲板／走線廊／地板柵／圓腳的參數還在：{g}")
    if not any(hasattr(D, g) for g in ("DECK_Z", "BASE_T", "PSU_VENT_W", "FOOT_H", "TENON")):
        ok("甲板、走線廊、穿艙孔、地板進氣柵、圓腳的參數已整組刪除")
    for tag, gotv, want in (
        ("Area B 淨空", D.AREA_B_CLEARANCE, 15.24),
        ("Area C 淨空", D.AREA_C_CLEARANCE, 38.10),
    ):
        (ok if approx(gotv, want, 0.01) else fail)(f"{tag}={gotv:.2f} (Table 6 {want})")
    # ★ Area A：第八／九輪是 50.00（**主動離開規範**）。第十輪**回到規範內**——
    #   使用者說「電源上面還有空間」，量出來是 27.50 mm 的死空間；電源頂上去之後
    #   讓出來的高度全部變成板上淨空，50.00 → 76.20 = Table 6 required，
    #   而機殼高度一點都沒有變。這裡驗三件事，一件都不能少：
    #   ①淨空 = max(實測下限, 規格 required)  ②規格 literal 沒被動過
    #   ③電源真的頂到內頂（否則下一輪有人把電源往下挪，淨空就悄悄跟著縮）
    (ok if approx(D.AREA_A_CLEARANCE, max(D.COOLER_MAX_H, D.AREA_A_SPEC_REQUIRED), 1e-6) else fail)(
        f"Area A 淨空 {D.AREA_A_CLEARANCE:.2f} = max(實測散熱器 {D.COOLER_MAX_H:.2f}, "
        f"Table 6 required {D.AREA_A_SPEC_REQUIRED:.2f})（導出）"
    )
    (ok if approx(D.AREA_A_SPEC_REQUIRED, 76.20, 0.01)
     and approx(D.AREA_A_SPEC_RECOMMENDED, 88.90, 0.01) else fail)(
        "Table 6 的 required 76.20 / recommended 88.90 兩個 literal 沒被動過"
    )
    (ok if D.AREA_A_CLEARANCE >= D.AREA_A_SPEC_REQUIRED else fail)(
        f"Area A 淨空 {D.AREA_A_CLEARANCE:.2f} >= Table 6 **required** "
        f"{D.AREA_A_SPEC_REQUIRED:.2f}（第十輪起不再是規範偏離）"
    )
    (ok if D.DIMM_MAX_H <= D.COOLER_MAX_H else fail)(
        f"記憶體上限 {D.DIMM_MAX_H:.1f} <= 散熱器上限 {D.COOLER_MAX_H:.1f}"
    )
    (ok if D.PSU_CLEAR_ABOVE >= D.PSU_CLEAR_MIN - 1e-9 else fail)(
        f"電源頂 → 內頂 {D.PSU_CLEAR_ABOVE:.2f} >= 下限 {D.PSU_CLEAR_MIN:.2f}"
    )
    (ok if D.PSU_CLEAR_ABOVE <= 6.0 else fail)(
        f"電源頂上只剩 {D.PSU_CLEAR_ABOVE:.2f} mm 空氣 —— 電源真的頂到內頂了"
        f"（第九輪是 {D.INNER_TOP_Z - (D.BOARD_TOP_Z + 50.0 + D.PSU_LEDGE_T + D.ATX_H):.2f} 的死空間）"
    )
    warn(
        f"Area A 淨空 {D.AREA_A_CLEARANCE:.2f} 已達 Table 6 **required** "
        f"{D.AREA_A_SPEC_REQUIRED:.2f}，但仍 < recommended {D.AREA_A_SPEC_RECOMMENDED:.2f}"
        f"（要達 recommended 需再 +{D.AREA_A_SPEC_RECOMMENDED - D.AREA_A_CLEARANCE:.2f} mm 機殼高度）"
    )
    zone_ok, bad_zone = D.psu_zone_ok()
    (ok if zone_ok else fail)(
        f"電源投影全落在 Area A（其餘區淨空只有 15.24/38.10）{'' if zone_ok else bad_zone}"
    )
    (ok if D.psu_bottom_clearance() >= D.AREA_A_CLEARANCE else fail)(
        f"電源底面離板面 {D.psu_bottom_clearance():.2f} >= {D.AREA_A_CLEARANCE}（散熱器空間）"
    )
    (ok if approx(D.ATX_Z0, D.AREA_A_TOP_Z + D.PSU_LEDGE_T, 1e-6) else fail)(
        f"ATX_Z0={D.ATX_Z0:.2f} = Area A 淨空頂 + 承托肩厚（導出）"
    )
    # 使用者指定：插頭插在 I/O 擋板**上方**那一區
    win_z0 = D.ATX_Z0 + D.PSU_WIN_Z0
    (ok if win_z0 > D.IO_Z1 else fail)(
        f"PSU 後面板開窗底 {win_z0:.2f} > I/O 開孔頂 {D.IO_Z1:.2f}（插頭在擋板上方）"
    )
    # ★ 第十輪：舊版這條是「電源頂淨空要放得下 TOP_LEDGE_T（頂蓋承托肩）」——
    #   那條肩第八輪就從幾何裡刪掉了，只剩參數。一個不存在的東西擋著電源不准往上，
    #   兩輪沒有人發現（硬規則 15）。現在改成驗「電源在 X 上讓開了頂蓋的下垂側舌」。
    for g in ("TOP_LEDGE_T", "TOP_LEDGE_W"):
        if hasattr(D, g):
            fail(f"第七輪的頂蓋承托肩參數還在：{g}（幾何早就沒有它了）")
    (ok if approx(D.ATX_X0, D.TOP_LID_INNER_X + D.PSU_FIT_GAP, 1e-6) else fail)(
        f"ATX_X0 {D.ATX_X0:.2f} = 頂蓋下垂料最內側 {D.TOP_LID_INNER_X:.2f} + 標準件間隙 "
        f"{D.PSU_FIT_GAP}（導出；電源升上去之後這兩者的 Z 帶是重疊的）"
    )
    (ok if D.ATX_X1 <= D.AREA_B_X0 else fail)(
        f"電源右緣 {D.ATX_X1:.2f} <= Area A/B 界線 {D.AREA_B_X0:.2f}（投影仍整片在 Area A）"
    )
    if rear is not None:
        # 後牆承托凸緣（電源坐在上面）
        y_led = D.CASE_REAR + D.WALL + D.PSU_LEDGE_W / 2
        (ok if pt_inside(rear, D.ATX_X0 + 80, y_led, D.ATX_Z0 - D.PSU_LEDGE_T / 2, 0.02) else fail)(
            "後牆 PSU 承托凸緣實心"
        )
        (fail if pt_inside(rear, D.ATX_X0 + 80, y_led, D.ATX_Z0 - D.PSU_LEDGE_T - 2.0, 0.02) else ok)(
            "承托凸緣底面 = Area A 淨空頂（沒有再往下長）"
        )
    if side_l is not None:
        x_led = D.CASE_LEFT + D.WALL + D.PSU_LEDGE_W / 2
        (ok if pt_inside(side_l, x_led, 60.0, D.ATX_Z0 - D.PSU_LEDGE_T / 2, 0.02) else fail)(
            "左側板 PSU 長肩實心（電源左緣整條坐在上面）"
        )

    # ── 走線：電源與主板同一個空間（使用者主訴「根本無法走線」）──────
    log("--- 走線淨空 ---")
    parts_all = list(shapes.values())

    def occupant(x, y, z, skip=()):
        """回傳「佔住這個點的零件名」，沒有就 None。要空的地方用它 == None。"""
        for pn, sh in shapes.items():
            if pn in skip:
                continue
            if pt_inside(sh, x, y, z, 0.02):
                return pn
        return None

    # 1) 電源出線口（前緣）正下方到板面：整條必須是空的
    blocked = []
    for x in (D.ATX_X0 + 20, D.ATX_X0 + 75, D.ATX_X1 - 10):
        for z in (D.ATX_Z0 - 5, (D.ATX_Z0 + D.BOARD_TOP_Z) / 2, D.BOARD_TOP_Z + 8):
            p = occupant(x, D.ATX_FRONT_Y + 6, z)
            if p:
                blocked.append((round(x, 1), round(z, 1), p))
    (ok if not blocked else fail)(
        f"電源出線口 → 主板上方 直落淨空{'' if not blocked else blocked}"
    )
    # 2) SATA 走線廊：碟的接頭朝 +X（使用者指定），線自碟右端出來沿這條廊往下走到
    #    板右緣的 SATA 埠。廊必須**上下通到底**，否則接頭朝內就只是個說法。
    cx0, cx1 = D.cable_corridor_x()
    xm = (cx0 + cx1) / 2
    blocked = []
    for z in (D.HDD_Z0 + 10, 100.0, 140.0, D.HDD_TOP_Z - 10):
        for y in (D.HDD_Y0 + 30, D.BAY_SPLIT_Y - 20, D.HDD_Y1 - 20):
            p = occupant(xm, y, z)
            if p:
                blocked.append((round(y, 1), round(z, 1), p))
    (ok if not blocked else fail)(
        f"SATA 走線廊（x∈[{cx0:.1f},{cx1:.1f}]，寬 {cx1 - cx0:.1f}）上下通透"
        f"{'' if not blocked else blocked}"
    )
    # 3) 碟架的右伸橫樑只有兩條、中間讓線過 —— 不是一整片封起來
    gap_y = (D.RACK_BEAM_Y[0] + D.RACK_BEAM_Y[1]) / 2
    (ok if occupant(xm, gap_y, (D.RACK_RAIL_Z0 + D.RACK_RAIL_Z1) / 2) is None else fail)(
        f"碟架兩條橫樑之間（y={gap_y:.1f}）留給 SATA 線穿過"
    )

    # ── 單一長方體外殼 ────────────────────────────────────────────
    log("--- 單一長方體 ---")
    # ★ 第九輪改成**體積**檢查，不是 bbox。理由是目視複檢時抓到的：
    #   `optimalBoundingBox(True)` 對球面會受三角網狀態影響 —— GUI 已經 tessellate 過的
    #   同一個側板回報 XMin −215.5471，headless 回報 −215.4900，差 0.057。
    #   拿它跟 ±0.05 的門檻比，同一份幾何在兩個環境會給出不同答案。
    #   「這一片有沒有料伸出長方體」本來就該用布林量，量出來是 0 就是 0。
    env = mk_box(D.CASE_LEFT, D.CASE_REAR, -D.SKIRT_H, D.CASE_RIGHT, D.CASE_FRONT, D.OUTER_TOP_Z)
    hook_out = D.CASE_REAR - (D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_HEAD_D)
    env_rear = mk_box(
        D.CASE_LEFT, hook_out, -D.SKIRT_H, D.CASE_RIGHT, D.CASE_FRONT, D.OUTER_TOP_Z
    )
    for key, sh in shapes.items():
        if key in ("PCIeBlank", "PCIeBar"):  # 備件停放在外；壓條**故意**長在後牆外
            continue
        # 後牆外表面有 keyhole 蘑菇柱（使用者要的「凸出來的結構」）與肋的外側補強
        e = env_rear if key == "Rear_IO_PCIe" else env
        v = sh.cut(e).Volume
        (ok if v <= INTERFERE_MAX else fail)(
            f"{key} 在外殼長方體內（外溢 {v:.2f} mm³）"
        )
    (ok if D.PCIE_RIB_D <= D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_HEAD_D else fail)(
        f"肋外側補強 {D.PCIE_RIB_D} <= keyhole 柱凸出 "
        f"{D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_HEAD_D:.2f}（後牆外最凸的仍是柱）"
    )
    # 前段不再矮一階：前罩要長到牆頂
    if shroud is not None:
        (ok if pt_inside(shroud, D.CASE_LEFT + D.WALL / 2, D.CASE_FRONT - 20, D.OUTER_TOP_Z - 1.0)
         else fail)("前罩外牆長到牆頂（外觀無階梯）")
    # ★ 第八輪：下裙已刪 → 反向檢查「裙不准回來」。機殼底面就是底板下表面 z=0。
    (ok if approx(D.SKIRT_H, 0.0, 1e-9) else fail)(
        f"下裙已刪（SKIRT_H={D.SKIRT_H}）—— 它唯一的理由是放螺母座，螺絲全沒了"
    )
    below = []
    for key, sh in shapes.items():
        if key == "PCIeBlank":
            continue
        if obb(sh).ZMin < -0.05:
            below.append(key)
    (ok if not below else fail)(f"沒有任何料在 z<0（無下裙、無外凸腳）{'' if not below else below}")
    # 四邊底緣整圈落地（底板 + 三面牆 + 前罩）
    miss = []
    for x in (D.CASE_LEFT + 1.2, D.CASE_RIGHT - 1.2):
        for y in (D.CASE_REAR + 20, 100.0, D.BAY_SPLIT_Y - 20, D.CASE_FRONT - 20):
            if occupant(x, y, 1.0) is None:
                miss.append((round(x, 1), round(y, 1)))
    for y, xs in ((D.CASE_REAR + 1.2, (-180.0, -60.0, 20.0)),
                  (D.CASE_FRONT - 1.2, (-180.0, -60.0, 20.0))):
        for x in xs:
            if occupant(x, y, 1.0) is None:
                miss.append((round(x, 1), round(y, 1)))
    (ok if not miss else fail)(f"機殼底緣整圈落地{'' if not miss else miss}")

    # ── I/O ───────────────────────────────────────────────────────
    if rear:
        log("--- I/O ---")
        y_mid = D.CASE_REAR + D.WALL / 2
        if approx(D.IO_W, 158.75) and approx(D.IO_H, 44.45):
            ok("IO size 158.75 x 44.45")
        if approx(D.IO_X1, -53.24, 0.3) and approx(D.IO_X0, -53.24 - D.IO_W, 0.3):
            ok(f"IO_X={D.IO_X0:.2f}..{D.IO_X1:.2f} (Fig.4 mirrored)")
        else:
            fail(f"IO_X0/X1={D.IO_X0}/{D.IO_X1}")
        (ok if approx(D.IO_Z0, D.BOARD_TOP_Z - 3.81, 1e-6) else fail)(
            f"IO 開孔底 {D.IO_Z0:.2f} = 板面 − 3.81（p13）"
        )
        io_cx, io_cz = (D.IO_X0 + D.IO_X1) / 2, (D.IO_Z0 + D.IO_Z1) / 2
        (fail if pt_inside(rear, io_cx, y_mid, io_cz) else ok)("IO opening void")
        edge = D.io_edge_material()
        (ok if edge >= D.IO_KEEPOUT + 0.8 else fail)(
            f"IO outer edge material {edge:.2f} >= keepout {D.IO_KEEPOUT}+0.8"
        )
        (ok if pt_inside(rear, D.IO_X0 - D.IO_KEEPOUT / 2, D.CASE_REAR + D.WALL - 0.3, io_cz)
         else fail)("IO keepout band on panel (inner face solid)")
        (ok if 0.94 <= D.IO_CLIP_T <= 1.32 else fail)(f"IO clip T={D.IO_CLIP_T} in 0.94-1.32")

        # ── ATX 四孔 + PSU 後面板開窗 ──────────────────────────────
        log("--- ATX 四孔 / PSU 開窗 ---")
        # ATX12V v1.1 **p23 Figure 4** 的 literal（圖上量到的四條標註見 參數.py）
        SPEC_ATX_HOLES = ((6.0, 80.0), (144.0, 80.0), (6.0, 16.0), (120.0, 6.0))
        spec = tuple(sorted(SPEC_ATX_HOLES))
        (ok if tuple(sorted(D.ATX_HOLES_SPEC)) == spec else fail)(
            "ATX_HOLES_SPEC == ATX12V Fig.4 p23 literal"
        )
        # ★ 第十輪：實際孔位 = 規格四孔繞**深度軸**轉 180°（風扇朝下，使用者指定）。
        #   驗的是「轉回去等於 literal」——這樣才確定它是剛體變換，不是重編一組數字。
        back = tuple(sorted((D.ATX_W - x, D.ATX_H - z) for x, z in D.ATX_HOLES))
        want = back if D.PSU_FAN_DOWN else tuple(sorted(D.ATX_HOLES))
        (ok if all(approx(a[0], b[0], 1e-6) and approx(a[1], b[1], 1e-6)
                   for a, b in zip(want, spec)) else fail)(
            f"ATX 四孔 {'翻轉後' if D.PSU_FAN_DOWN else ''}對回 Fig.4 literal（剛體 180° 繞深度軸）"
        )
        # 翻轉不得改變孔距（同一組孔，只是換了姿態）
        xs = sorted({round(h[0], 3) for h in D.ATX_HOLES})
        zs = sorted({round(h[1], 3) for h in D.ATX_HOLES})
        pitch_h = max(
            abs(a[0] - b[0]) for a in D.ATX_HOLES for b in D.ATX_HOLES if approx(a[1], b[1], 1e-6)
        )
        pitch_v = max(
            abs(a[1] - b[1]) for a in D.ATX_HOLES for b in D.ATX_HOLES if approx(a[0], b[0], 1e-6)
        )
        (ok if approx(pitch_h, D.ATX_HOLE_PITCH_H, 0.01) else fail)(
            f"同列孔距 {pitch_h:.2f} = Fig.4 {D.ATX_HOLE_PITCH_H}"
        )
        (ok if approx(pitch_v, D.ATX_HOLE_PITCH_V - 10.0, 0.01) or approx(pitch_v, D.ATX_HOLE_PITCH_V, 0.01)
         else fail)(f"同行孔距 {pitch_v:.2f}（Fig.4 右側 74.0 / 左側 64.0）")
        if len(xs) == 3 and len(zs) == 3:
            ok("ATX hole pattern asymmetric (3 distinct X / 3 distinct Z)")
        else:
            fail("ATX hole pattern is a symmetric rectangle — Fig.4 is not")
        warn(
            "風扇朝向是**假設不是規格**：ATX12V v1.1 Fig.4 的風扇開在後面板上，"
            "大面 120/140 風扇在哪一面規格沒寫、參考/ 也沒有別的文件寫。"
            f"目前依使用者指定取 PSU_FAN_DOWN={D.PSU_FAN_DOWN}（風扇朝主機板）"
        )
        for i, (hx, hz) in enumerate(D.ATX_HOLES):
            (fail if pt_inside(rear, D.ATX_X0 + hx, y_mid, D.ATX_Z0 + hz) else ok)(
                f"ATX mount hole {i} open"
            )
        wx0, wx1 = D.ATX_X0 + D.PSU_WIN_X0, D.ATX_X0 + D.PSU_WIN_X1
        wz0, wz1 = D.ATX_Z0 + D.PSU_WIN_Z0, D.ATX_Z0 + D.PSU_WIN_Z1
        for tag, xx, zz in (
            ("center", (wx0 + wx1) / 2, (wz0 + wz1) / 2),
            ("AC 插座下緣", D.ATX_X0 + 128.0, D.ATX_Z0 + 12.0),
            ("風扇下緣", D.ATX_X0 + 56.0, wz0 + 2.0),
            ("風扇上緣", D.ATX_X0 + 56.0, wz1 - 2.0),
        ):
            (fail if pt_inside(rear, xx, y_mid, zz) else ok)(f"PSU window open at {tag}")
        for i, (hx, hz) in enumerate(D.ATX_HOLES):
            hxw, hzw = D.ATX_X0 + hx, D.ATX_Z0 + hz
            edge = min(
                abs(hxw - wx0) if hxw < wx0 else 1e9,
                abs(hxw - wx1) if hxw > wx1 else 1e9,
                abs(hzw - wz0) if hzw < wz0 else 1e9,
                abs(hzw - wz1) if hzw > wz1 else 1e9,
            )
            mrg = edge - D.ATX_SCREW_CLR / 2
            (ok if mrg >= D.PSU_WIN_M - 1e-6 else fail)(f"PSU screw pad {i} 料 {mrg:.2f}")
        area = (wx1 - wx0) * (wz1 - wz0) / (D.ATX_W * D.ATX_H)
        (ok if area >= 0.60 else fail)(
            f"PSU window {(wx1 - wx0):.1f}x{(wz1 - wz0):.1f} = 後面板 {area * 100:.0f}%"
        )

        # ── PCIe ─────────────────────────────────────────────────
        log("--- PCIe ---")
        centers = D.pcie_centers()
        if len(centers) == 4 and all(
            approx(abs(centers[i + 1] - centers[i]), 20.32) for i in range(3)
        ):
            ok("PCIe pitch 20.32")
        (ok if approx(D.PCIE_FIRST_CX, D.BOARD_RIGHT - 10.16, 0.05) else fail)(
            f"PCIE_FIRST_CX={D.PCIE_FIRST_CX:.2f} (expand edge-0.400in)"
        )
        (ok if min(centers) > D.IO_X1 else fail)("rear view: PCIe right of I/O")
        for tag, gotv, want in (
            ("bracket W", D.PCIE_BRACKET_W, 18.42),
            ("body H", D.PCIE_BODY_H, 112.75),
            ("tang H", D.PCIE_TANG_H, 7.27),
            ("tang W", D.PCIE_TANG_W, 14.30),
            ("total H", D.PCIE_BRACKET_TOTAL_H, 120.02),
            ("conn H", D.PCIE_CONN_H, 7.90),
            ("card H", D.PCIE_CARD_H, 111.15),
            ("card bottom", D.PCIE_CARD_BOTTOM, 3.40),
            ("engage", D.PCIE_ENGAGE, 4.50),
            ("ear inward", D.PCIE_EAR_INWARD, 11.43),
            # 擋板自身的 I/O 窗（Fig.6-2 p93）：機殼不挖它，但它決定了「開孔比擋板寬
            # 多少才不會擋到卡的接頭」。第十輪把它從無人引用的常數變成有檢查的常數。
            ("bracket window W", D.PCIE_WIN_W, 12.06),
            ("bracket window H", D.PCIE_WIN_H, 89.90),
            ("bracket window from top", D.PCIE_WIN_FROM_TOP, 10.16),
        ):
            (ok if approx(gotv, want, 0.02) else fail)(f"CEM {tag}={gotv:.2f} (spec {want})")
        (ok if approx(D.PCIE_Z1 - D.BOARD_TOP_Z, 114.55 + 4.56, 0.02) else fail)(
            f"bracket top = board+{D.PCIE_Z1 - D.BOARD_TOP_Z:.2f} (DIM A 114.55 + 4.56)"
        )
        (ok if approx(D.PCIE_Z1 - D.PCIE_Z0, D.PCIE_BODY_H, 0.02) else fail)(
            "opening Z span == body 112.75 (not the 120.02 total)"
        )
        (ok if D.PCIE_BRACKET_W < D.PCIE_OPEN_W < D.PCIE_PITCH else fail)(
            f"opening {D.PCIE_OPEN_W} in ({D.PCIE_BRACKET_W}, {D.PCIE_PITCH})"
        )
        (ok if D.PCIE_OPEN_W > D.PCIE_WIN_W else fail)(
            f"開孔 {D.PCIE_OPEN_W} > 擋板自身 I/O 窗 {D.PCIE_WIN_W}（Fig.6-2；卡的接頭出得來）"
        )
        (ok if D.PCIE_PITCH - D.PCIE_OPEN_W >= 0.8 else fail)(
            f"inter-slot rib {D.PCIE_PITCH - D.PCIE_OPEN_W:.2f} >= 0.8 printable"
        )
        (ok if D.PCIE_TANG_POCKET > D.PCIE_BRACKET_T else fail)(
            f"tang pocket {D.PCIE_TANG_POCKET} > stock {D.PCIE_BRACKET_T}"
        )
        y_wall = D.CASE_REAR + D.WALL / 2
        z_tie = D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H / 2
        for tag, xx in (("between slots", (min(centers) + max(centers)) / 2), ("over slot", centers[0])):
            (ok if pt_inside(rear, xx, y_wall, z_tie) else fail)(f"PCIe tie bar solid {tag}")
        z_open_mid = (D.PCIE_Z0 + D.PCIE_Z1) / 2
        # ★ 第九輪：肋不能只驗「中間有料」。第八輪的橫縫把肋的**上端切斷**，
        #   而「繫樑實心」那條探的是橫縫**上方**那塊料——上方確實還是實心，
        #   所以檢查照樣綠。探點只回答「有沒有料」，沒有人問「這根柱子的另一端接到哪」。
        #   現在改成沿整根肋（含上下兩個固定端）逐點取樣，缺一點就是懸臂。
        cs_sorted = sorted(centers)
        for i in range(len(cs_sorted) - 1):
            xm = (cs_sorted[i] + cs_sorted[i + 1]) / 2
            zs = [
                D.PCIE_Z0 - 1.0,  # 下固定端（開孔底以下的實料）
                z_open_mid,
                D.PCIE_Z1,
                D.PCIE_Z1 + D.PCIE_LIFT / 2,
                D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H / 2,  # 上固定端（繫樑）
            ]
            gaps = [z for z in zs if not pt_inside(rear, xm, y_wall, z, 0.02)]
            (fail if gaps else ok)(
                f"肋 x={xm:.2f} 上下貫通"
                if not gaps
                else f"肋 x={xm:.2f} 在 z={['%.1f' % z for z in gaps]} 斷掉 → 懸臂"
            )
            # 往機殼外加厚的補強（斷面 1.42×2.40 → 1.42×6.40）
            (ok if pt_inside(rear, xm, D.CASE_REAR - D.PCIE_RIB_D / 2, z_open_mid, 0.02) else fail)(
                f"肋 x={xm:.2f} 外側補強實心（深 {D.PCIE_RIB_D}）"
            )
        rib_w = D.PCIE_PITCH - D.PCIE_OPEN_W
        i_old = rib_w * D.WALL ** 3 / 12.0
        i_new = rib_w * (D.WALL + D.PCIE_RIB_D) ** 3 / 12.0
        (ok if i_new >= 10 * i_old else fail)(
            f"肋抗彎慣性矩 {i_old:.2f} → {i_new:.2f} mm⁴（×{i_new / i_old:.0f}）"
        )
        # ★ 第十輪：補強從「只有肋」擴大成**整圈窗框**。三個邊都要驗，不然
        #   下一輪又只剩中間那三根是厚的（使用者：PCIe 還是很多問題）。
        fx0, fx1 = D.pcie_frame_x()
        fz0, fz1 = D.pcie_frame_z()
        y_boss = D.CASE_REAR - D.PCIE_RIB_D / 2
        for tag, xx, zz in (
            ("底檻", (min(centers) + max(centers)) / 2, D.PCIE_Z0 - 2.0),
            ("左柱", fx0 + 1.0, (D.PCIE_Z0 + D.PCIE_Z1) / 2),
            ("右柱", fx1 - 1.0, (D.PCIE_Z0 + D.PCIE_Z1) / 2),
            ("肋頂（壓條下緣之下）", (cs_sorted[0] + cs_sorted[1]) / 2, fz1 - 1.0),
        ):
            (ok if pt_inside(rear, xx, y_boss, zz, 0.02) else fail)(
                f"PCIe 窗框{tag}外側補強實心（總厚 {D.WALL + D.PCIE_RIB_D:.2f}）"
            )
        (ok if fx0 >= D.IO_X1 else fail)(
            f"窗框補強左端 {fx0:.2f} >= I/O 開孔近緣 {D.IO_X1:.2f}（沒有從外面補住 I/O 開孔）"
        )
        (ok if fx1 <= D.CASE_RIGHT + 1e-9 else fail)(
            f"窗框補強右端 {fx1:.2f} <= 機殼外表面 {D.CASE_RIGHT:.2f}"
        )
        (ok if fz1 <= D.PCIE_BAR_Z0 - D.SLIDE_FIT + 1e-9 else fail)(
            f"窗框補強頂 {fz1:.2f} 讓開壓條下緣 {D.PCIE_BAR_Z0:.2f}"
        )
        # 舌袋所在的底檻厚度（第九輪挖完只剩 1.10）
        sill_t = D.WALL + D.PCIE_RIB_D - D.PCIE_TANG_POCKET
        (ok if sill_t >= 3.0 else fail)(
            f"擋板舌袋背後剩料 {sill_t:.2f} mm（第九輪 {D.WALL - D.PCIE_TANG_POCKET:.2f}）"
        )
        # keyhole 蘑菇柱的頸斷面（整條壓條掛在這兩根上）
        neck_a = D.PCIE_HOOK_NECK_W * D.PCIE_HOOK_NECK_D
        (ok if neck_a >= 40.0 else fail)(
            f"蘑菇柱頸斷面 {D.PCIE_HOOK_NECK_W:.1f}×{D.PCIE_HOOK_NECK_D:.1f} = {neck_a:.1f} mm²"
            f"（第九輪 4.0×5.5 = 22.0）"
        )
        # 抬升帶不得再被打成連續橫縫（那是第八輪讓肋懸空的原因）
        (ok if pt_inside(rear, D.CASE_RIGHT - 1.0, y_wall, D.PCIE_Z1 + D.PCIE_LIFT / 2, 0.02)
         else fail)("抬升帶沒有連續橫縫（機殼右緣那段仍是實料）")
        z_open_top = D.PCIE_Z1 + D.PCIE_LIFT
        (fail if pt_inside(rear, centers[0], y_wall, z_open_top - 0.5) else ok)(
            f"opening top = bracket+{D.PCIE_LIFT:.2f} >= engage {D.PCIE_ENGAGE:.2f}"
        )
        for i, cx in enumerate(centers):
            (fail if pt_inside(rear, cx, y_wall, z_open_mid) else ok)(f"PCIe void {i}")
            tz = (D.PCIE_TANG_Z0 + D.PCIE_Z0) / 2
            y_pocket = D.CASE_REAR + D.WALL - D.PCIE_TANG_POCKET / 2
            y_back = D.CASE_REAR + (D.WALL - D.PCIE_TANG_POCKET) / 2
            if pt_inside(rear, cx, y_pocket, tz):
                fail(f"PCIe tang pocket {i} still solid")
            elif not pt_inside(rear, cx, y_back, tz):
                fail(f"PCIe tang pocket {i} cut through — no Y datum for the bracket")
            else:
                ok(f"PCIe tang pocket {i} blind (floor+back present)")

    # ── PCIe 壓條 ────────────────────────────────────────────────
    # ── PCIe 壓條：第八輪**移到機殼外面** ─────────────────────────
    log("--- PCIe 壓條（外置）---")
    room = D.PCIE_BRACKET_ABOVE_CARD - D.PCIE_ENGAGE
    (ok if room < 1.0 else fail)(f"耳下方可用高度只有 {room:.2f} mm → 固定件必須可拆")
    (ok if approx(D.PCIE_BAR_Z0, D.PCIE_Z1 + D.PCIE_HOLD_GAP, 1e-6) else fail)(
        f"壓舌底面 = 擋板頂 + 防上抬間隙 {D.PCIE_HOLD_GAP}"
    )
    lifted = D.PCIE_CARD_TOP_Z + D.PCIE_ENGAGE
    (ok if D.PCIE_BAR_Z0 >= lifted else fail)(f"壓舌底 {D.PCIE_BAR_Z0:.2f} >= 卡抬到頂 {lifted:.2f}")
    # ★ 使用者主訴：壓條不准往機殼內突出。這條是**幾何斷言**不是宣稱：
    #   壓條的實體必須整片在後牆內面（CASE_REAR + WALL）之外。
    y_in = D.CASE_REAR + D.WALL
    if bar is not None:
        bb = obb(bar)
        (ok if bb.YMin < D.CASE_REAR else fail)(
            f"壓條本體長在機殼外（YMin {bb.YMin:.2f} < 後牆外表面 {D.CASE_REAR:.2f}）"
        )
        (ok if bb.YMax <= y_in + 0.05 else fail)(
            f"壓條沒有伸進機殼內部（YMax {bb.YMax:.2f} <= 後牆內面 {y_in:.2f}）"
        )
        tab_end = D.CASE_REAR + D.PCIE_BAR_TAB_D
        (ok if tab_end >= D.PCIE_BRACKET_Y1 else fail)(
            f"壓舌前端 {tab_end:.2f} >= 擋板內面 {D.PCIE_BRACKET_Y1:.2f}（真的蓋滿擋板厚度）"
        )
        (ok if tab_end <= D.CASE_REAR + D.WALL else fail)(
            f"壓舌前端 {tab_end:.2f} <= 後牆內面 {D.CASE_REAR + D.WALL:.2f}（沒有往機殼內突出）"
        )
        # 壓舌必須真的落在四個開孔的 X 位置上
        zt = (D.PCIE_BAR_Z0 + D.PCIE_BAR_Z1) / 2
        for i, cx in enumerate(D.pcie_centers()):
            (ok if pt_inside(bar, cx, y_in - 0.6, zt, 0.02) else fail)(f"壓舌 {i} 壓在擋板頂緣上方")
            (ok if D.PCIE_BAR_TAB_W <= D.PCIE_OPEN_W else fail)(
                f"壓舌寬 {D.PCIE_BAR_TAB_W:.2f} <= 開孔寬 {D.PCIE_OPEN_W}"
            )
    # ── keyhole：壓上去 → 落下 PCIE_BAR_DROP → 頭被窄段扣住 ──────────
    # ★ 這一段的存在理由是結構，不是機構：舊的「沿 X 滑入 T 軌」逼出了連續橫縫。
    #   T 軌參數必須整組消失，否則下一輪會被當成「漏掉的功能」加回來。
    for g in ("PCIE_RAIL_Z0", "PCIE_RAIL_NECK_H", "PCIE_RAIL_HEAD_H",
              "PCIE_RAIL_NECK_D", "PCIE_RAIL_HEAD_D", "PCIE_BAR_BOSS_W"):
        if hasattr(D, g):
            fail(f"舊 T 軌／內凸座參數還在：{g}")
    ok("T 軌與內凸座的參數已整組刪除（壓條改 keyhole，不再沿 X 滑）")
    hn, drop, f_bar = D.PCIE_HOOK_H, D.PCIE_BAR_DROP, D.PCIE_BAR_FIT
    # 幾何推導：頭要能在「抬起」時穿過寬口、在「落下」時被窄段擋住 → 落差 ≥ 頭高
    (ok if drop >= hn else fail)(f"keyhole 落差 {drop} >= 頭高 {hn}（否則寬口與窄段在同一個 Z 上矛盾）")
    # 抬起解鎖時四個壓舌也跟著上去，不能頂到開孔頂
    (ok if D.PCIE_BAR_Z1 + drop <= D.PCIE_Z1 + D.PCIE_LIFT else fail)(
        f"解鎖抬起後壓舌頂 {D.PCIE_BAR_Z1 + drop:.2f} <= 開孔頂 {D.PCIE_Z1 + D.PCIE_LIFT:.2f}"
    )
    (ok if approx(D.PCIE_LIFT, max(D.PCIE_ENGAGE + 1.5,
                                   D.PCIE_HOLD_GAP + D.PCIE_BAR_TAB_H + drop + 0.6), 1e-6) else fail)(
        f"抬升帶 {D.PCIE_LIFT:.2f} 由「卡的指入深度」與「壓條解鎖行程」取大者導出"
    )
    (ok if approx(D.PCIE_HOOK_NECK_D - D.PCIE_HOOK_FUSE - D.PCIE_BAR_T, f_bar, 1e-6) else fail)(
        f"頭的內面到牆 {D.PCIE_HOOK_NECK_D - D.PCIE_HOOK_FUSE:.2f} = 壓條厚 + 滑配 {f_bar}"
    )
    (ok if D.PCIE_HOOK_HEAD_W > D.PCIE_HOOK_NECK_W + 2 * (f_bar + 1.0) else fail)(
        f"頭寬 {D.PCIE_HOOK_HEAD_W} 比窄槽 {D.PCIE_HOOK_NECK_W + 2 * f_bar:.2f} 多出"
        f" {(D.PCIE_HOOK_HEAD_W - D.PCIE_HOOK_NECK_W) / 2 - f_bar:.2f}/邊 的扣料"
    )
    if rear is not None:
        for i, hx in enumerate(D.pcie_hook_x()):
            zc = D.PCIE_HOOK_Z0 + D.PCIE_HOOK_H / 2
            (ok if pt_inside(rear, hx, D.CASE_REAR - D.PCIE_HOOK_NECK_D / 2, zc, 0.02) else fail)(
                f"蘑菇柱 {i} 的頸實心"
            )
            (ok if pt_inside(rear, hx + D.PCIE_HOOK_HEAD_W / 2 - 0.5,
                             D.CASE_REAR - D.PCIE_HOOK_NECK_D - D.PCIE_HOOK_HEAD_D / 2, zc, 0.02)
             else fail)(f"蘑菇柱 {i} 的頭（翼）實心")
            # 柱必須落在開孔頂之上的全寬實料帶，否則它自己就懸在開孔上
            (ok if D.PCIE_HOOK_Z0 >= D.PCIE_Z1 + D.PCIE_LIFT else fail)(
                f"蘑菇柱 {i} 柱底 {D.PCIE_HOOK_Z0:.2f} >= 開孔頂 {D.PCIE_Z1 + D.PCIE_LIFT:.2f}"
            )
    (ok if D.psu_slide_room() >= D.PSU_SLIDE_X else fail)(
        f"電源落入橫移空間 {D.psu_slide_room():.2f} >= 需求 {D.PSU_SLIDE_X}"
    )

    # ── 碟架：平躺 4 層，疊在主板前段上方 ─────────────────────────
    log("--- HDD 碟架（平躺 4 層）---")
    (ok if approx(D.TRAY_Y0, D.AREA_A_Y_FAR, 1e-6) else fail)(
        f"碟架／托盤後緣 {D.TRAY_Y0:.2f} = Fig.7 的 Area A/C 界線 "
        f"{D.AREA_A_Y_FAR:.2f}（導出，不寫死）"
    )
    (ok if approx(D.HDD_Y0, D.TRAY_Y0 + D.TRAY_BACK_STOP, 1e-6) else fail)(
        f"碟後緣 {D.HDD_Y0:.2f} = 托盤後緣 + 後擋邊 {D.TRAY_BACK_STOP}（擋邊不長在碟體裡）"
    )
    (ok if D.RACK_Z0 >= D.AREA_C_TOP_Z - 1e-6 else fail)(
        f"碟架底面 {D.RACK_Z0:.2f} >= Area C 淨空頂 {D.AREA_C_TOP_Z:.2f}"
    )
    # ★ 使用者主訴 1a：最底層的導軌槽下面必須有承載料
    (ok if approx(D.HDD_Z0, D.RACK_Z0 + D.RACK_FLOOR_T, 1e-6) else fail)(
        f"最底層托盤底 {D.HDD_Z0:.2f} = 碟架底 + 承載料 {D.RACK_FLOOR_T}（不是與立板底同高）"
    )
    (ok if D.RACK_FLOOR_T - D.SLIDE_FIT >= 2.0 else fail)(
        f"lv0 槽底下方剩 {D.RACK_FLOOR_T - D.SLIDE_FIT:.2f} mm 料（>= 2.0 才托得住碟）"
    )
    # ★ 使用者主訴：層間零間隙。TRAY_PITCH 讀起來像導出式，實際上讓碟頂貼死上層托盤底。
    (ok if approx(D.TRAY_PITCH, D.HDD_H + D.TRAY_T + D.TRAY_AIR_GAP, 1e-6) else fail)(
        f"層節距 {D.TRAY_PITCH:.2f} = 碟厚 {D.HDD_H} + 托盤 {D.TRAY_T} + 氣隙 {D.TRAY_AIR_GAP}"
    )
    (ok if D.TRAY_AIR_GAP >= 1.0 else fail)(
        f"碟頂 → 上一層托盤底的間隙 {D.TRAY_AIR_GAP} >= 1.0（零間隙＝裝不進去、層間不通風）"
    )
    (ok if D.HDD_LEVELS == D.HDD_COUNT == 4 else fail)(f"{D.HDD_LEVELS} 層 × 1 顆 = {D.HDD_COUNT} 顆")
    # 托盤厚度必須讓 #6-32×1/4" 的穿入量落在 SFF-8301 的 2.39–3.56
    pen = 6.35 - D.TRAY_T
    (ok if 2.39 <= pen <= 3.56 else fail)(
        f"#6-32×1/4\" 穿入碟體 {pen:.2f} ∈ [2.39, 3.56]（SFF-8301 p7 Fastener penetration）"
    )
    # 底孔座標對 literal（硬規則 11：不只比參數之間的關係）
    for tag, gotv, want in (
        ("A7 接頭端→第一排", D.HDD_BOT_FROM_CONN[0], 41.28),
        ("A7+A6 →第二排", D.HDD_BOT_FROM_CONN[1], 41.28 + 44.45),
        ("A7+A13 →第三排", D.HDD_BOT_FROM_CONN[2], 41.28 + 76.20),
        ("A5 側緣→孔心", D.HDD_BOT_FROM_SIDE, 3.18),
        ("A4 兩側孔中心距", D.HDD_BOT_PITCH_Y, 95.25),
    ):
        (ok if approx(gotv, want, 0.01) else fail)(f"SFF-8301 {tag} = {gotv:.2f} ({want})")
    (ok if approx(D.HDD_BOT_FROM_SIDE * 2 + D.HDD_BOT_PITCH_Y, D.HDD_W, 0.02) else fail)(
        f"A5×2 + A4 = {D.HDD_BOT_FROM_SIDE * 2 + D.HDD_BOT_PITCH_Y:.2f} = 碟寬 A3 {D.HDD_W}"
    )
    # 側孔參數不得復活（平躺姿態拿側孔用＝八顆螺絲鎖進塑膠）
    (ok if not hasattr(D, "HDD_SIDE_FROM_FACE") else fail)("側鎖孔參數已刪（平躺該用底孔）")
    # ★ 使用者主訴 1b：開孔要左右對稱
    gl, gr = D.side_gap_x()
    (ok if approx(gl, gr, 0.01) else fail)(f"碟架左右餘裕 {gl:.2f} / {gr:.2f}（置中）")
    ml, mr = D.tray_opening_margin()
    (ok if approx(ml, mr, 0.01) else fail)(
        f"前罩開口距機殼左右外表面 {ml:.2f} / {mr:.2f}（對稱）"
    )
    # ★ 使用者主訴 1c：接頭與線要有地方去
    (ok if D.HDD_CABLE_W >= 25.0 else fail)(
        f"碟接頭區 {D.HDD_CABLE_W:.2f} mm（SATA 資料 + 電源接頭與線彎折）"
    )
    (ok if approx(D.RACK_POST_X0, D.HDD_X1 + D.HDD_CABLE_W, 1e-6) else fail)(
        f"右立板內面 {D.RACK_POST_X0:.2f} = 碟端面 {D.HDD_X1:.2f} + 接頭區（不是貼著端面）"
    )
    (ok if approx(D.HDD_TRAY_X1, D.RACK_POST_X0, 1e-6) else fail)("托盤鋪到右立板（線有底，不會垂下去）")
    if rack is not None:
        for tag, x, y, z in (
            ("左立板", (D.RACK_X0 + D.HDD_X0) / 2, (D.HDD_Y0 + D.HDD_Y1) / 2, 100.0),
            ("右立板", (D.RACK_POST_X0 + D.RACK_POST_X1) / 2, (D.HDD_Y0 + D.HDD_Y1) / 2, 100.0),
            ("頂板", D.HDD_X0 + 30.0, (D.HDD_Y0 + D.HDD_Y1) / 2, D.HDD_TOP_Z + D.RACK_TOP_T / 2),
        ):
            (ok if pt_inside(rack, x, y, z, 0.02) else fail)(f"碟架 {tag} 實心")
        # 四層導軌槽都要是空的（托盤滑得進去），而且**每一層的槽下面都要有料**
        ym = (D.HDD_Y0 + D.HDD_Y1) / 2
        for lv in range(D.HDD_LEVELS):
            zt = D.tray_z0(lv) + D.TRAY_RAIL_H / 2
            for tag, xs in (("左", D.HDD_TRAY_X0 - D.TRAY_RAIL_W / 2),
                            ("右", D.HDD_TRAY_X1 + D.TRAY_RAIL_W / 2)):
                (fail if pt_inside(rack, xs, ym, zt, 0.02) else ok)(f"碟架第 {lv} 層{tag}導軌槽開通")
                zu = D.tray_z0(lv) - D.SLIDE_FIT - 1.0
                (ok if pt_inside(rack, xs, ym, zu, 0.02) else fail)(
                    f"碟架第 {lv} 層{tag}導軌槽**下方有承載料**（z={zu:.2f}）"
                )
        # 側舌高度由碟架自己的頂板導出（不再由 PCIe 卡導出——卡已被切在 189.00）
        (ok if approx(D.RACK_RAIL_Z1, D.HDD_TOP_Z - 2.0, 1e-6) else fail)(
            f"碟架側舌頂 {D.RACK_RAIL_Z1:.2f} = 碟架頂板下方 2 mm（導出）"
        )
        (ok if D.RACK_RAIL_Z0 > D.tray_z0(D.HDD_LEVELS - 1) + D.TRAY_RAIL_H else fail)(
            "側舌不落在任何一層托盤導軌槽的 Z 帶裡（舌根有整厚立板）"
        )
    # 應支援卡長由碟架後緣導出，且仍 >= CEM 半長卡
    (ok if approx(D.PCIE_CARD_LEN, D.TRAY_Y0 - (D.CASE_REAR + D.WALL) - 2.0, 1e-6) else fail)(
        f"應支援卡長 {D.PCIE_CARD_LEN:.2f} 由碟架後緣 {D.TRAY_Y0:.2f} 導出"
    )
    (ok if D.PCIE_CARD_LEN >= D.PCIE_CARD_LEN_HALF else fail)(
        f"卡長 {D.PCIE_CARD_LEN:.2f} >= CEM 半長卡 {D.PCIE_CARD_LEN_HALF}（刻意取捨，見文件）"
    )
    warn(
        f"刻意取捨：本機殼支援的 PCIe 卡長上限 {D.PCIE_CARD_LEN:.2f} mm"
        f"（碟架置中換來的；使用者指定只插網卡類低卡）"
    )
    if dtray is not None:
        bb = obb(dtray)
        (ok if bb.ZLength <= D.TRAY_PITCH + 0.5 else fail)(
            f"托盤（含前擋板）高 {bb.ZLength:.2f} <= 層節距 {D.TRAY_PITCH:.2f} + 餘裕"
        )
        # 六個底孔都要真的鑽穿
        zt = D.tray_z0(0) + D.TRAY_T / 2
        holes_open = 0
        for hx, hy in D.hdd_bottom_hole_xy(0):
            if not pt_inside(dtray, hx, hy, zt, 0.02):
                holes_open += 1
        (ok if holes_open == 6 else fail)(f"托盤底孔 {holes_open}/6 鑽穿（三排 × 兩側）")

    log("--- 氣流 ---")
    va = D.front_vent_area()
    (ok if va >= FAN_AREA_120 else fail)(
        f"前柵開口 {va:.0f} mm² >= 電源 120 風扇 {FAN_AREA_120:.0f} mm²"
    )
    if shroud is not None:
        zz = D.FRONT_VENT_Z0 + D.FRONT_VENT_SLAT / 2
        (fail if pt_inside(shroud, -130.0, D.CASE_FRONT - D.TRAY_FACE_T / 2, zz) else ok)(
            "前罩下段的進氣柵確實開了（最低那條）"
        )
        (ok if D.FRONT_VENT_Z1 <= D.HDD_Z0 else fail)(
            f"柵頂 {D.FRONT_VENT_Z1:.2f} <= 碟陣底 {D.HDD_Z0:.2f}（柵在碟下方那片固定前板上）"
        )
    if dtray is not None:
        # 托盤前擋板也開柵：氣要從碟自己那一層進得去，不能只靠下方那片
        zz = D.tray_z0(0) + 8.0 + D.FRONT_VENT_SLAT / 2
        (fail if pt_inside(dtray, -130.0, D.HDD_Y1 + D.TRAY_FRONT_GAP + D.TRAY_FACE_T / 2, zz)
         else ok)("碟托盤前擋板的進氣柵確實開了")
    if tray is not None:
        # 地板不得再開電源進氣柵：電源已經不在底下了（多餘孔洞）
        solid = all(
            pt_inside(tray, x, y, D.FLOOR_T / 2, 0.02)
            for x, y in ((-138.0, 40.0), (-138.0, 100.0), (-60.0, 70.0))
        )
        (ok if solid else fail)("底板無進氣柵（電源已上置；地板是密封的）")
    for name, sh, x, y in (
        ("Side_Left_MB", side_l, D.CASE_LEFT + D.WALL / 2, 60.0),
        ("Side_Right_MB", side_r, D.CASE_RIGHT - D.WALL / 2, 60.0),
    ):
        if sh is None:
            continue
        solid = all(pt_inside(sh, x, y, z, 0.02) for z in (40.0, 120.0, 170.0))
        (ok if solid else fail)(f"{name} 無通風開孔（氣流只有一條：前柵→碟→內腔→電源）")

    # ── 全滑槽組裝：**一顆機殼螺絲都沒有**（使用者要求）──────────────
    log("--- 滑槽組裝（無螺絲）---")
    for g in ("M3_CLR", "M3_TAP", "M3_INSERT_D", "M3_INSERT_L", "M3_BOSS_L", "M3_BOSS_W",
              "M3_BASE_Z", "M3_REAR_BASE_X", "M3_SIDE_BASE_Y", "M3_CAGE_Y", "M3_CAGE_Z",
              "TOP_SCREW_BOSS_D", "TOP_SCREW_MB_Y", "TOP_SCREW_HDD_Y",
              "CAGE_LAP_W", "CAGE_LAP_Z0", "TOP_SEAM_Y", "TOP_LAP_W"):
        if hasattr(D, g):
            fail(f"螺絲／銅母／搭接片的參數還在：{g}")
    ok("M3 銅母、頂蓋螺絲座、碟艙搭接片的參數已整組刪除")
    # 幾何斷言：機殼件上不得再有 Ø2.5–Ø4.6 的圓柱孔（銅母／通孔的特徵尺寸）。
    # 探法：在舊螺絲位置取樣，全部必須是實料或空氣，而不是「孔」。
    if tray is not None:
        solid = all(pt_inside(tray, x, y, D.FLOOR_T / 2, 0.02)
                    for x, y in ((-140.0, D.FLOOR_Y0 + 6.0), (0.0, D.FLOOR_Y0 + 6.0)))
        (ok if solid else fail)("底板後緣舊螺母座位置現在是實心地板（座已刪）")
    for nm, sh in (("Side_Left_MB", side_l), ("Side_Right_MB", side_r)):
        if sh is None:
            continue
        xw = D.CASE_LEFT + D.WALL / 2 if nm.endswith("Left_MB") else D.CASE_RIGHT - D.WALL / 2
        solid = all(pt_inside(sh, xw, y, 30.0, 0.02) for y in (30.0, 190.0))
        (ok if solid else fail)(f"{nm} 舊 M3 通孔位置現在是實心牆")

    # 滑槽本身：每一道都要「槽是空的、槽外還有牆料」（挖穿就沒有定位面了）
    for nm, sh, xi, sgn in (
        ("Side_Left_MB", side_l, D.CASE_LEFT + D.WALL, -1),
        ("Side_Right_MB", side_r, D.CASE_RIGHT - D.WALL, +1),
    ):
        if sh is None:
            continue
        ym = (D.CASE_REAR + D.WALL + D.BAY_SPLIT_Y) / 2
        z_floor_groove = D.FLOOR_T - D.FLOOR_LIP_T / 2
        for tag, zc, depth, yc in (
            ("底板舌槽", z_floor_groove, D.FLOOR_LIP + D.SLIDE_FIT, ym),
            ("碟架舌槽", (D.RACK_RAIL_Z0 + D.RACK_RAIL_Z1) / 2, D.RACK_RAIL_T, D.BAY_SPLIT_Y - 20),
            ("頂蓋舌槽", D.INNER_TOP_Z - D.TOP_T / 2, D.TOP_LIP + D.SLIDE_FIT, ym),
        ):
            x_in = xi + sgn * depth / 2  # 槽中間
            x_out = xi + sgn * (depth + (D.WALL - depth) / 2)  # 槽外的牆料
            (fail if pt_inside(sh, x_in, yc, zc, 0.02) else ok)(f"{nm} {tag}開通")
            (ok if pt_inside(sh, x_out, yc, zc, 0.02) else fail)(f"{nm} {tag}沒有挖穿（背後仍有牆料）")
        # ★ 使用者主訴 4：「底板跟左右板之間真的有滑蓋設計嗎」
        #   第八輪答案是「不是」：槽開穿到牆底，槽的**下方沒有任何料**（探針 0.00 mm³），
        #   那是 L 形搭邊。滑槽的定義是**上下都夾得住**，所以兩邊都要驗。
        x_mid = xi + sgn * (D.FLOOR_LIP + D.SLIDE_FIT) / 2
        (ok if pt_inside(sh, x_mid, ym, D.FLOOR_LEDGE_T / 2, 0.02) else fail)(
            f"{nm} 底板槽**下方**有整厚牆料當承載唇（高 {D.FLOOR_LEDGE_T:.2f}）"
        )
        (ok if pt_inside(sh, x_mid, ym, D.FLOOR_T + D.SLIDE_FIT + 1.0, 0.02) else fail)(
            f"{nm} 底板槽**上方**有牆料（舌抬不出去）"
        )
        # ★ 第十輪：槽挖完之後牆上必須還剩得下 GROOVE_BACK_MIN 的料
        back = D.WALL - (D.FLOOR_LIP + D.SLIDE_FIT)
        (ok if back >= D.GROOVE_BACK_MIN - 1e-9 else fail)(
            f"{nm} 底板槽背後剩料 {back:.2f} >= 最小可印壁厚 {D.GROOVE_BACK_MIN}"
        )
    # 底板三面舌 + 牆槽的配合
    if tray is not None:
        bb = obb(tray)
        want_w = (D.FLOOR_X1 - D.FLOOR_X0) - 2 * D.SLIDE_FIT + 2 * D.FLOOR_LIP
        (ok if approx(bb.XLength, want_w, 0.05) else fail)(
            f"底板含兩側舌寬 {bb.XLength:.2f} = 內腔 − 2×滑配 + 2×舌 {D.FLOOR_LIP}"
        )
        # ★ 第十輪：本體側緣**內縮 SLIDE_FIT**。第九輪底板剛好等於內腔寬 247.88，
        #   兩側與牆內面完全共面（distToShape 0.0000）→ 250 mm 跨距上裝不進去。
        (fail if pt_inside(tray, D.FLOOR_X0 + D.SLIDE_FIT / 2, ym, D.FLOOR_T / 2, 0.02) else ok)(
            f"底板本體左緣內縮 {D.SLIDE_FIT}（不與左內牆共面）"
        )
        (fail if pt_inside(tray, D.FLOOR_X1 - D.SLIDE_FIT / 2, ym, D.FLOOR_T / 2, 0.02) else ok)(
            f"底板本體右緣內縮 {D.SLIDE_FIT}"
        )
        # 舌只有上半片：舌的 z 帶下方在底板本體以外必須是空的
        x_tongue = D.FLOOR_X0 + D.SLIDE_FIT - D.FLOOR_LIP / 2
        (fail if pt_inside(tray, x_tongue, ym, D.FLOOR_LEDGE_T / 2, 0.02) else ok)(
            f"底板側舌只有上半片（z {D.FLOOR_T - D.FLOOR_LIP_T:.2f}..{D.FLOOR_T:.2f}）"
        )
        (ok if pt_inside(tray, x_tongue, ym, D.FLOOR_T - D.FLOOR_LIP_T / 2, 0.02) else fail)(
            "底板側舌本身實心"
        )
        (ok if bb.XLength <= D.A1_MAX and bb.YLength <= D.A1_MAX else fail)(
            f"底板 {bb.XLength:.1f}×{bb.YLength:.1f} 印得進 A1 {D.A1_MAX:.0f}"
        )
    # 後牆定位舌 + detent
    if rear is not None and side_l is not None:
        y_tab = D.CASE_REAR + D.WALL + D.REAR_TAB_D / 2
        (ok if pt_inside(rear, D.CASE_LEFT + D.WALL - D.REAR_TAB_T / 2, y_tab, 90.0, 0.02) else fail)(
            "後牆左端定位舌實心（長在側板牆體那一側，不是往機殼內）"
        )
        (fail if pt_inside(side_l, D.CASE_LEFT + D.WALL - D.REAR_TAB_T / 2, y_tab, 90.0, 0.02)
         else ok)("左側板對應的定位舌槽開通")
        (ok if D.DETENT_R >= 0.5 else fail)(f"detent 半球 R={D.DETENT_R} >= 最小可印特徵 0.5")
        (ok if D.DETENT_R < D.REAR_TAB_D / 2 else fail)(
            f"detent 半球 R={D.DETENT_R} < 定位舌深的一半 {D.REAR_TAB_D / 2}"
        )
    # 頂蓋：後端半搭接鑽進後牆鉤唇下方
    top = shapes.get("Top_MB")
    if top is not None and rear is not None:
        (ok if approx(D.TOP_HOOK_T * 2, D.TOP_T, 0.01) else fail)(
            f"鉤唇厚 {D.TOP_HOOK_T} = 頂蓋厚 {D.TOP_T} 的一半（半搭接）"
        )
        y_hook = D.CASE_REAR + D.WALL + D.TOP_HOOK_D / 2
        (ok if pt_inside(rear, 0.0, y_hook, D.OUTER_TOP_Z - D.TOP_HOOK_T / 2, 0.02) else fail)(
            "後牆頂鉤唇實心（頂蓋抬不起來 → 側板也抽不上去）"
        )
        (fail if pt_inside(top, 0.0, y_hook, D.OUTER_TOP_Z - D.TOP_HOOK_T / 2, 0.02) else ok)(
            "頂蓋後端上半已讓開給鉤唇"
        )
        (ok if approx(D.RACK_TOP_GAP, D.SLIDE_FIT, 1e-9) else fail)(
            f"碟架頂板 → 頂蓋底面留了 {D.RACK_TOP_GAP} 的間隙"
            f"（第九輪 INNER_TOP_Z 直接取 RACK_TOP_Z1 → 兩面共面）"
        )
        (ok if approx(D.INNER_TOP_Z, max(D.ATX_Z1 + D.PSU_CLEAR_MIN,
                                         D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H,
                                         D.RACK_TOP_Z1 + D.RACK_TOP_GAP,
                                         D.AREA_A_TOP_Z), 1e-9) else fail)(
            f"內頂 {D.INNER_TOP_Z:.2f} = max(電源+{D.PSU_CLEAR_MIN}, PCIe, 碟架+"
            f"{D.RACK_TOP_GAP}, AreaA)（導出）"
        )
        (ok if pt_inside(top, 0.0, y_hook, D.INNER_TOP_Z + D.TOP_HOOK_T / 2, 0.02) else fail)(
            "頂蓋後端下半仍有料（真的鑽進鉤唇下方，不是整段切光）"
        )
    # ── 前罩：使用者主訴 2（底下是空的／貼合／「真的是卡槽卡住的嗎」）────────
    if shroud is not None and side_l is not None and tray is not None:
        y_lap = D.BAY_SPLIT_Y - D.SHROUD_LAP / 2
        (fail if pt_inside(side_l, D.CASE_LEFT + D.SHROUD_LAP_T / 2, y_lap, 90.0, 0.02) else ok)(
            "左側板前段外表面已減薄（讓前罩套上去）"
        )
        (ok if pt_inside(shroud, D.CASE_LEFT + D.SHROUD_LAP_T / 2, y_lap, 90.0, 0.02) else fail)(
            "前罩的搭接薄殼填進那道減薄帶"
        )
        # ★ 不是「總厚等於 WALL」而是「留了滑配」。第八輪 nominal 零間隙 →
        #   common=0.000 被讀成不干涉，其實是套不進去。
        side_left_t = D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT
        (ok if approx(D.SHROUD_LAP_T + D.SLIDE_FIT + side_left_t, D.WALL, 1e-6) else fail)(
            f"搭接：前罩殼 {D.SHROUD_LAP_T} + 滑配 {D.SLIDE_FIT} + 側板剩 {side_left_t:.2f}"
            f" = 牆厚 {D.WALL}（外表面齊平，而且**留了間隙**不是零）"
        )
        # ① 前罩底下不再是空的
        for tag, x, y in (("左", -150.0, D.CASE_FRONT - 20.0), ("右", 20.0, D.CASE_FRONT - 20.0)):
            (ok if pt_inside(shroud, x, y, D.FLOOR_T / 2, 0.02) else fail)(f"前罩{tag}側地板實心")
        (ok if pt_inside(shroud, 0.0, D.SHROUD_Y0 - D.SHROUD_LAP / 2,
                         D.FLOOR_T - D.SHROUD_FLOOR_LAP_T / 2, 0.02) else fail)(
            "前罩地板舌壓在底板前緣的減薄帶上（底面半搭接）"
        )
        (fail if pt_inside(tray, 0.0, D.BAY_SPLIT_Y - D.SHROUD_LAP / 2,
                           D.FLOOR_T - D.SHROUD_FLOOR_LAP_T / 2, 0.02) else ok)(
            "底板前緣上半已讓開（給前罩地板舌）"
        )
        (ok if pt_inside(tray, 0.0, D.BAY_SPLIT_Y - D.SHROUD_LAP / 2,
                         D.SHROUD_FLOOR_LAP_T / 2, 0.02) else fail)("底板前緣下半仍有料（半搭接）")
        # ② 頂面半搭接
        top_sh = shapes.get("Top_MB")
        if top_sh is not None:
            (fail if pt_inside(top_sh, 0.0, D.BAY_SPLIT_Y - D.SHROUD_LAP / 2,
                               D.OUTER_TOP_Z - D.SHROUD_TOP_LAP_T / 2, 0.02) else ok)(
                "頂蓋前段上表面已減薄（給前罩頂舌）"
            )
            (ok if pt_inside(shroud, 0.0, D.SHROUD_Y0 - D.SHROUD_LAP / 2,
                             D.OUTER_TOP_Z - D.SHROUD_TOP_LAP_T / 2, 0.02) else fail)(
                "前罩頂舌填進那道減薄帶（頂面齊平）"
            )
        # ③ 真的卡住：detent
        t_left = D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT
        (ok if 2 * D.SHROUD_DETENT_R <= t_left + D.SHROUD_DETENT_DEPTH + 1e-9 else fail)(
            f"前罩 detent 2R={2 * D.SHROUD_DETENT_R:.2f} <= 減薄後料厚 {t_left:.2f}"
            f" + 凸出 {D.SHROUD_DETENT_DEPTH}（球不會從另一面戳出去）"
        )
        (ok if D.SHROUD_DETENT_R >= 0.5 else fail)(
            f"前罩 detent R={D.SHROUD_DETENT_R} >= 最小可印特徵 0.5"
        )
        dz = D.SHROUD_DETENT_Z[0]
        xb = D.CASE_LEFT + D.SHROUD_LAP_T + D.SLIDE_FIT - D.SHROUD_DETENT_DEPTH / 2
        (ok if pt_inside(side_l, xb, y_lap, dz, 0.02) else fail)("左側板減薄帶上的 detent 凸半球實心")
        (fail if pt_inside(shroud, xb, y_lap, dz, 0.02) else ok)("前罩搭接殼上有對應的 detent 凹坑")
        # ★ 第十輪：搭接帶裡**三道滑槽的正後方不准減薄**。
        #   牆 2.4：內面槽 1.6 + 外面減薄 1.5 = 3.1 > 2.4 → 那 12 mm 是被切穿的。
        #   第八～九輪三道槽在搭接帶裡全都是通的，只是當時兩件的料剛好錯開，
        #   布林一路綠。**「沒有干涉」不等於「牆還在」。**
        keep = B.side_lap_keep_bands()
        (ok if len(keep) >= 2 else fail)(f"側板搭接帶的 keep 帶 {len(keep)} 段（三道槽合併後）")
        for nm2, sh2 in (("Side_Left_MB", side_l), ("Side_Right_MB", side_r)):
            if sh2 is None:
                continue
            xo2 = (D.CASE_LEFT if nm2.endswith("Left_MB") else D.CASE_RIGHT)
            inw = 1 if nm2.endswith("Left_MB") else -1
            x_skin = xo2 + inw * (D.SHROUD_LAP_T / 2)  # 減薄帶會被挖掉的那層皮
            for kz0, kz1 in keep:
                zc = min(max((kz0 + kz1) / 2, 1.0), D.OUTER_TOP_Z - 1.0)
                (ok if pt_inside(sh2, x_skin, y_lap, zc, 0.02) else fail)(
                    f"{nm2} 搭接帶 z={zc:.1f} **未減薄**（槽背後還有牆料）"
                )
                (fail if pt_inside(shroud, x_skin, y_lap, zc, 0.02) else ok)(
                    f"前罩搭接殼在 z={zc:.1f} 讓開（整厚料咬進這個缺口 → Z 向被扣住）"
                )
            # 三道槽在搭接帶裡都不准穿到外表面
            for tag2, zg, dep in (
                ("底板槽", D.FLOOR_T - D.FLOOR_LIP_T / 2, D.FLOOR_LIP + D.SLIDE_FIT),
                ("碟架槽", (D.RACK_RAIL_Z0 + D.RACK_RAIL_Z1) / 2, D.RACK_RAIL_T),
                ("頂蓋槽", D.INNER_TOP_Z - D.TOP_T / 2, D.TOP_LIP + D.SLIDE_FIT),
            ):
                # 槽是自**內面**往外挖的 → 剩下的牆料在靠**外面**那一側
                x_back = xo2 + inw * (D.WALL - dep) / 2
                (ok if pt_inside(sh2, x_back, y_lap, zg, 0.02) else fail)(
                    f"{nm2} 搭接帶裡的{tag2}背後仍有牆料（沒有被減薄切穿）"
                )
        # ④ 打薄了，但沒薄到不能印
        (ok if D.SHROUD_WALL < D.WALL else fail)(
            f"前罩側牆／頂板 {D.SHROUD_WALL} < 機殼牆 {D.WALL}（使用者要求打薄）"
        )
        (ok if min(D.SHROUD_WALL, D.SHROUD_LAP_T,
                   D.FLOOR_T - D.SHROUD_FLOOR_LAP_T - D.SLIDE_FIT) >= 0.8 else fail)(
            f"前罩最薄處 {min(D.SHROUD_WALL, D.SHROUD_LAP_T, D.FLOOR_T - D.SHROUD_FLOOR_LAP_T - D.SLIDE_FIT):.2f}"
            f" >= FDM 最小可印壁厚 0.8"
        )

    # ── 配合間隙：**「≤ 上限」的地方也要檢查「≥ 下限」**（硬規則 19）────────────
    # ★ 第十輪整段新增。第九輪只修了前罩搭接與層節距兩處零間隙，量下去才發現
    #   `distToShape(底板, 側板) = 0.0000`、後牆、頂蓋、側板↔後牆**全部一樣**——
    #   同一個病長在整條互鎖鏈上，而 verify 從來沒有一條在問「配合面留了幾 mm」。
    log("--- 配合間隙（每一道滑槽的四個面）---")
    ym_fit = (D.CASE_REAR + D.WALL + D.BAY_SPLIT_Y) / 2
    xl_edge = D.FLOOR_X0 + D.SLIDE_FIT
    xl_tip = xl_edge - D.FLOOR_LIP
    xr_edge = D.FLOOR_X1 - D.SLIDE_FIT
    xr_tip = xr_edge + D.FLOOR_LIP
    gaps = (
        ("底板本體 ↔ 左內牆", D.FLOOR_X0 + D.SLIDE_FIT / 2, ym_fit, D.FLOOR_T / 2),
        ("底板本體 ↔ 右內牆", D.FLOOR_X1 - D.SLIDE_FIT / 2, ym_fit, D.FLOOR_T / 2),
        ("底板左舌尖 ↔ 槽底", xl_tip - D.SLIDE_FIT / 2, ym_fit, D.FLOOR_T - D.FLOOR_LIP_T / 2),
        ("底板右舌尖 ↔ 槽底", xr_tip + D.SLIDE_FIT / 2, ym_fit, D.FLOOR_T - D.FLOOR_LIP_T / 2),
        ("底板左舌下 ↔ 承載唇", xl_tip + D.FLOOR_LIP / 2, ym_fit,
         D.FLOOR_LEDGE_T + D.SLIDE_FIT / 2),
        ("底板左舌上 ↔ 槽頂", xl_tip + D.FLOOR_LIP / 2, ym_fit, D.FLOOR_T + D.SLIDE_FIT / 2),
        ("頂蓋左舌尖 ↔ 槽底", D.FLOOR_X0 - D.TOP_LIP - D.SLIDE_FIT / 2, ym_fit,
         D.INNER_TOP_Z - D.TOP_T / 2),
        ("頂蓋左舌上 ↔ 槽頂", D.FLOOR_X0 - D.TOP_LIP / 2, ym_fit,
         D.INNER_TOP_Z + D.SLIDE_FIT / 2),
        ("後牆定位舌尖 ↔ 槽底", D.FLOOR_X0 - D.REAR_TAB_T - D.SLIDE_FIT / 2,
         D.CASE_REAR + D.WALL + D.REAR_TAB_D / 2, 90.0),
        ("底板後舌尖 ↔ 後牆槽底", -100.0,
         D.FLOOR_Y0 - D.FLOOR_LIP - D.SLIDE_FIT / 2, D.FLOOR_T - D.FLOOR_LIP_T / 2),
        # ★ 這兩條是第十輪自己補的檢查漏掉的：它們不在任何「配合面」上，
        #   而是藏在 `INNER_TOP_Z = max(...)` 與「切深剛好等於鉤唇厚」裡。
        ("碟架頂板 ↔ 頂蓋底面", -100.0, D.BAY_SPLIT_Y - 20.0,
         D.RACK_TOP_Z1 + D.RACK_TOP_GAP / 2),
        ("頂蓋後端 ↔ 後牆頂鉤唇底面", 0.0,
         D.CASE_REAR + D.WALL + D.TOP_HOOK_D / 2, D.OUTER_TOP_Z - D.TOP_HOOK_T - D.SLIDE_FIT / 2),
    )
    for tag, gx, gy, gz in gaps:
        who = occupant(gx, gy, gz)
        (fail if who else ok)(
            f"{tag} 的 {D.SLIDE_FIT} mm 滑配是空的{'' if not who else f'（被 {who} 佔住＝零間隙）'}"
        )

    # ── 卡榫盤點：每一個機殼件之間的接合都要有「槽 + 保持力」──────────────
    # ★ 硬規則 7：清單不准手列。這張表是 (件A, 件B, 槽的探點, detent 產生器)，
    #   而 STL_NAMES 裡所有**結構件**都必須在表裡出現至少一次 —— 漏一件就 SystemExit。
    log("--- 卡榫／保持力盤點 ---")
    JOINTS = (
        ("Bottom_Tray", "Side_Left_MB", lambda: B.floor_detents(True)),
        ("Bottom_Tray", "Side_Right_MB", lambda: B.floor_detents(False)),
        ("Bottom_Tray", "Rear_IO_PCIe", lambda: B.floor_rear_detents()),
        ("Rear_IO_PCIe", "Side_Left_MB", lambda: B.rear_tab_detents(True)),
        ("Rear_IO_PCIe", "Side_Right_MB", lambda: B.rear_tab_detents(False)),
        ("Front_Shroud", "Side_Left_MB", lambda: B.shroud_detents(True)),
        ("Front_Shroud", "Side_Right_MB", lambda: B.shroud_detents(False)),
        ("Front_Shroud", "Top_MB", lambda: B.shroud_lap_detents(True)),
        ("Front_Shroud", "Bottom_Tray", lambda: B.shroud_lap_detents(False)),
    )
    covered = {p for j in JOINTS for p in j[:2]}
    need = {"Bottom_Tray", "Rear_IO_PCIe", "Side_Left_MB", "Side_Right_MB", "Top_MB",
            "Front_Shroud"}
    if not need <= covered:
        raise SystemExit(f"卡榫盤點漏了機殼件：{sorted(need - covered)}")
    for a, b, gen in JOINTS:
        det = gen()
        if not det:
            fail(f"{a}/{b} 沒有任何 detent")
            continue
        # 公件必須真的長在其中一件上（體積相交），母件必須讓開（落到定位時不干涉）
        va = sum(common_vol(shapes[a], d) for d in det) if a in shapes else 0.0
        vb = sum(common_vol(shapes[b], d) for d in det) if b in shapes else 0.0
        (ok if max(va, vb) > 0.05 else fail)(
            f"{a}/{b} detent ×{len(det)} 公件實心（{max(va, vb):.2f} mm³）"
        )
        (ok if min(va, vb) <= 0.05 else fail)(
            f"{a}/{b} 落到定位時 detent 不干涉（母件已讓開 {min(va, vb):.2f} mm³）"
        )
    # 底板↔側板的 bead：過盈行程必須是**最後一小段**，不是整條 244 mm
    run = D.floor_detent_run_mm()
    total = D.BAY_SPLIT_Y - D.FLOOR_Y0
    (ok if run <= 0.2 * total else fail)(
        f"底板 bead 的過盈行程 {run:.1f} mm <= 全程 {total:.1f} 的 20%（球長在底板後段，"
        f"側板的槽自後端掃過來 → 只有最後這一段磨）"
    )
    (ok if D.FLOOR_DETENT_R >= 0.5 else fail)(f"底板 bead R={D.FLOOR_DETENT_R} >= 0.5 可印")
    (ok if D.FLOOR_DETENT_DEPTH > D.SLIDE_FIT else fail)(
        f"底板 bead 凸出 {D.FLOOR_DETENT_DEPTH} > 滑配 {D.SLIDE_FIT}"
        f"（過盈 {D.FLOOR_DETENT_DEPTH - D.SLIDE_FIT:.2f}；否則它只是個裝飾）"
    )
    (ok if 2 * D.FLOOR_REAR_DETENT_R <= D.FLOOR_LIP_T + D.DETENT_DEPTH + 1e-9 else fail)(
        f"底板後舌半球 2R={2 * D.FLOOR_REAR_DETENT_R:.2f} <= 舌厚 {D.FLOOR_LIP_T} + 凸出 "
        f"{D.DETENT_DEPTH}（球不會從舌的另一面戳出去）"
    )
    # 頂蓋側舌真的咬進側板（第九輪只有 0.40 mm）
    if top is not None and side_l is not None:
        eng = D.TOP_LIP
        (ok if eng >= 1.0 else fail)(f"頂蓋側舌咬合量 {eng:.2f} >= 1.0（第九輪是 0.40）")
        (ok if pt_inside(top, D.FLOOR_X0 - eng / 2, ym_fit, D.INNER_TOP_Z - D.TOP_T / 2, 0.02)
         else fail)("頂蓋側舌真的伸進側板槽裡（不是只搭到槽口）")
        (fail if pt_inside(side_l, D.FLOOR_X0 - eng / 2, ym_fit, D.INNER_TOP_Z - D.TOP_T / 2, 0.02)
         else ok)("側板頂槽在同一點是空的")
    # 後牆槽下方的承載唇（第九輪這裡是 0.00 mm³，只有側板被修好）
    if rear is not None:
        y_rg = D.CASE_REAR + D.WALL - D.FLOOR_LIP / 2
        for xx in (-180.0, -60.0, 20.0):
            (ok if pt_inside(rear, xx, y_rg, D.FLOOR_LEDGE_T / 2, 0.02) else fail)(
                f"後牆底板槽下方有承載料 x={xx:.0f}（第九輪是 0.00 mm³）"
            )
            (ok if pt_inside(rear, xx, y_rg, D.FLOOR_T + D.SLIDE_FIT + 1.0, 0.02) else fail)(
                f"後牆底板槽上方有牆料 x={xx:.0f}"
            )

    # ── 後牆的單向卡榫：直角面必須真的存在、而且朝著拉出的方向 ──────────
    # 第十輪這裡是半球。半球受拉會**自己爬出來**，所以「有 detent」不等於「拉不出來」。
    # 這條檢查問的是形狀：楔上必須有一個**法線平行 Y**的面，面積夠大，
    # 而且它前方 SLIDE_FIT 內就是後牆的舌料（要頂住的那道邊）。
    if rear is not None and side_l is not None:
        y_sq = B.rear_wedge_y1()
        want_a = D.DETENT_DEPTH * D.REAR_WEDGE_H * 0.8
        for isl, nm in ((True, "左"), (False, "右")):
            wedges = B.rear_tab_detents(isl)
            (ok if len(wedges) == len(D.REAR_DETENT_Z) else fail)(
                f"{nm}側楔 ×{len(wedges)}（＝REAR_DETENT_Z 的顆數）"
            )
            best = 0.0
            for f in wedges[0].Faces:
                u0, u1, v0, v1 = f.ParameterRange
                n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                if abs(n.y) > 0.99 and abs(f.CenterOfMass.y - y_sq) < 0.05:
                    best = max(best, f.Area)
            (ok if best >= want_a else fail)(
                f"{nm}側楔有法線平行 Y 的直角面 {best:.2f} >= {want_a:.2f} mm²"
                f"（半球沒有這個面 → 受拉會 cam-out）"
            )
            xi = D.FLOOR_X0 if isl else D.FLOOR_X1
            xp = xi + (-1 if isl else 1) * (D.REAR_TAB_T / 2)
            zp = D.REAR_DETENT_Z[1]
            (fail if pt_inside(rear, xp, y_sq - 0.3, zp, 0.02) else ok)(
                f"{nm}側直角面後方是缺口（楔佔著）"
            )
            (ok if pt_inside(rear, xp, y_sq + D.SLIDE_FIT, zp, 0.02) else fail)(
                f"{nm}側直角面前方 {D.SLIDE_FIT} 就是舌料（頂住它的那道邊）"
            )
            # 缺口自舌根開，前緣後面必須一路連到舌尖：中間開孔的話前緣只有一片細肉
            (ok if pt_inside(rear, xp, D.CASE_REAR + D.WALL + D.REAR_TAB_D - 0.2, zp, 0.02)
             else fail)(f"{nm}側缺口前緣一路連到舌尖（不是舌中間挖孔）")

    # ── 保持力真相表：每一件在六個方向能自由走多遠 ─────────────────────
    # ★ 第十一輪新增。前十輪只驗「不干涉」與「裝得進去」，**從來沒有問過
    #   「裝好之後掉不掉得出來」**。使用者第十輪之後說「我仍然看不出這機殼要
    #   怎麼組裝在一起」，量出來的答案是：碟架往 −Y 浮 3.00 mm、後牆往 −Y
    #   走 12 mm 都沒有任何幾何擋住。兩件都是 failures=0 底下的。
    #   量法：把某一件平移 δ，看撞到誰。play ≈ SLIDE_FIT ⇒ 鎖住；
    #   走得掉 ⇒ 那是釋放方向，必須是**宣告過**的，而且要有 detent 守著。
    log("--- 保持力真相表（六向約束）---")
    HOLD_RELEASE = {  # 允許自由的唯一方向；None = 六向全鎖
        "Bottom_Tray": None,  # 基準件
        "Side_Left_MB": None,
        "Side_Right_MB": None,
        "Rear_IO_PCIe": None,  # 第十一輪：楔的直角面擋住 −Y（第十輪是自由的）
        "HDD_Rack": None,  # 第十一輪：RACK_STOP_Y 盲端擋住 −Y（第十輪浮 3.00）
        "Top_MB": None,
        "Front_Shroud": "+Y",  # 唯一徒手可拆的蓋（10 顆半球 detent，刻意可 cam-out）
        "HDD_Tray": "+Y",  # 熱插拔
    }
    _hold_need = set(D.STRUCT_PART_KEYS) - {"MB_Nut", "PCIeBar", "PCIeBlank"}
    if not _hold_need <= set(HOLD_RELEASE):  # 硬規則 7：漏件就爆，不准手列漏掉
        raise SystemExit(f"保持力真相表漏了機殼件：{sorted(_hold_need - set(HOLD_RELEASE))}")
    HOLD_LOCKED, HOLD_FREE = 0.75, 6.0
    hold_shapes = {k: shapes[k] for k in HOLD_RELEASE if k in shapes}
    hold_bb = {k: v.BoundBox for k, v in hold_shapes.items()}

    def hold_hit(name, vec, delta):
        mv = hold_shapes[name].copy()
        mv.translate(App.Vector(*[c * delta for c in vec]))
        mb, worst, wv = mv.BoundBox, None, 0.0
        for other, osh in hold_shapes.items():
            if other == name:
                continue
            ob = hold_bb[other]
            if (mb.XMax < ob.XMin - 0.1 or mb.XMin > ob.XMax + 0.1
                    or mb.YMax < ob.YMin - 0.1 or mb.YMin > ob.YMax + 0.1
                    or mb.ZMax < ob.ZMin - 0.1 or mb.ZMin > ob.ZMax + 0.1):
                continue
            v = common_vol(mv, osh)
            if v > wv:
                worst, wv = other, v
        return worst, wv

    for name in sorted(hold_shapes):
        rel = HOLD_RELEASE[name]
        for tag, vec in (("+X", (1, 0, 0)), ("-X", (-1, 0, 0)), ("+Y", (0, 1, 0)),
                         ("-Y", (0, -1, 0)), ("+Z", (0, 0, 1)), ("-Z", (0, 0, -1))):
            who, vol = hold_hit(name, vec, HOLD_LOCKED)
            if tag == rel:
                if vol > INTERFERE_MAX:
                    fail(f"{name} {tag} 是宣告的釋放方向，卻走不動（撞 {who}）")
                    continue
                _, v2 = hold_hit(name, vec, HOLD_FREE)
                (ok if v2 <= INTERFERE_MAX else fail)(
                    f"{name} {tag} 釋放方向淨空 >{HOLD_FREE}（可徒手拆）"
                )
            else:
                (ok if vol > INTERFERE_MAX else fail)(
                    f"{name} {tag} 被 {who} 鎖住（play <= {HOLD_LOCKED}）"
                    if vol > INTERFERE_MAX else
                    f"{name} {tag} 走 {HOLD_LOCKED} mm 沒撞到任何東西 —— 這個方向沒有保持力"
                )

    log("--- interference ---")
    exempt = set()  # 沒有任何刻意干涉；要加就得同時寫理由
    keys = [k for k in D.STL_NAMES if k in shapes]
    for a, b in [p for p in itertools.combinations(keys, 2) if frozenset(p) not in exempt]:
        v = common_vol(shapes[a], shapes[b])
        (fail if (v < 0 or v > INTERFERE_MAX) else ok)(
            f"{'interfere' if (v < 0 or v > INTERFERE_MAX) else 'no interfere'} {a}/{b} {v:.2f}"
        )

    # ── 虛擬件 + 規格淨空區 ───────────────────────────────────────
    log("--- fit (虛擬件 / 規格淨空) ---")
    mocks = hardware_mocks()
    for mn in sorted(mocks):
        worst_p, worst_v = None, 0.0
        for pn, sh in shapes.items():
            v = common_vol(mocks[mn], sh)
            if v < 0:
                worst_p, worst_v = pn, float("inf")
                break
            if v > worst_v:
                worst_p, worst_v = pn, v
        (fail if worst_v > INTERFERE_MAX else ok)(
            f"{mn} {'hits ' + str(worst_p) + f' {worst_v:.1f} mm3' if worst_v > INTERFERE_MAX else 'clear'}"
        )

    # ★ 第九輪：**四層托盤都要驗**。總成裡只放了第 0 層 → 其餘三層等於沒被驗過，
    #   而使用者一眼看出來的「最下面那層卡不住」正好就在沒被驗的那一側。
    #   硬規則 7 的精神：清單要從 range(HDD_LEVELS) 展開，不是手挑一層。
    for lv in range(D.HDD_LEVELS):
        t_lv = B.make_hdd_tray_placed(lv)
        bad = []
        for k in range(D.HDD_LEVELS):
            for tag in (f"HDD_L{k}", f"HDD_L{k}_接頭"):
                v = common_vol(mocks[tag], t_lv)
                if v > INTERFERE_MAX:
                    bad.append(f"{tag} {v:.1f}")
        for pn in ("HDD_Rack", "Front_Shroud", "Top_MB", "Side_Left_MB", "Side_Right_MB"):
            if pn in shapes:
                v = common_vol(shapes[pn], t_lv)
                if v > INTERFERE_MAX:
                    bad.append(f"{pn} {v:.1f}")
        (fail if bad else ok)(
            f"碟托盤 lv{lv} {'撞：' + '; '.join(bad) if bad else '與四層碟、接頭區、機殼件皆不干涉'}"
        )
        # 層間氣隙：碟頂 → 上一層托盤底之間那條縫，任何印件都不准伸進去
        if lv + 1 < D.HDD_LEVELS:
            zg = D.tray_z0(lv) + D.TRAY_T + D.HDD_H + D.TRAY_AIR_GAP / 2
            slab = mk_box(D.HDD_X0 + 5, D.HDD_Y0 + 5, zg - 0.2, D.HDD_X1 - 5, D.HDD_Y1 - 5, zg + 0.2)
            worst = max(
                [(common_vol(slab, sh), pn) for pn, sh in shapes.items()]
                + [(common_vol(slab, B.make_hdd_tray_placed(k)), f"tray{k}")
                   for k in range(D.HDD_LEVELS)]
            )
            (fail if worst[0] > INTERFERE_MAX else ok)(
                f"lv{lv} 碟頂上方 {D.TRAY_AIR_GAP} mm 氣隙淨空"
                f"{'' if worst[0] <= INTERFERE_MAX else f'：{worst[1]} {worst[0]:.1f}'}"
            )

    # ── 裝配動作：最終位置合法 ≠ 走得到那個位置 ─────────────────────
    log("--- 裝配動作 ---")

    def sweep(shape, dx=0.0, dy=0.0, dz=0.0, steps=None):
        """
        把包絡沿 (dx,dy,dz) 掃出的體積；步長取件最小邊的 0.9 倍，避免中間漏空。
        `steps` 可以指定步數：**長行程的滑入**（側板 264 mm、頂蓋 298 mm）用預設步長
        會變成上百次 fuse，而那些接合面沿 Y 是等剖面的，粗一點的步長不會漏掉東西。
        """
        b = shape.BoundBox
        span = max(abs(dx), abs(dy), abs(dz))
        step = max(min(b.XLength, b.YLength, b.ZLength) * 0.9, 1.0)
        n = steps or max(1, int(math.ceil(span / step)))
        out = shape
        for i in range(1, n + 1):
            mv = shape.copy()
            mv.translate(App.Vector(dx * i / n, dy * i / n, dz * i / n))
            out = out.fuse(mv)
        return out

    def hits(swept, skip=()):
        worst_p, worst_v = None, 0.0
        for pn, sh in shapes.items():
            if pn in skip:
                continue
            v = common_vol(swept, sh)
            if v > worst_v:
                worst_p, worst_v = pn, v
        return worst_p, worst_v

    # 0) ★ 第十輪：**照使用者指定的順序逐步裝**（底板 → 側板 → 後板 → 碟架 → 頂蓋 → 前罩）。
    #    第八／九輪每一條掃描都拿**完整總成**當障礙物 —— 那只回答「這一件在最後那個
    #    場景裡動得了嗎」，從來沒有回答「照這個順序裝得起來嗎」。
    #    現在第 i 件掃的時候，場上只有第 0..i−1 件。
    #    detent 是**刻意的彈性過盈**，掃描前要把公件從障礙物上扣掉，否則這條檢查
    #    永遠紅，而且紅的是設計意圖不是缺陷。
    def detent_free(pn, sh):
        ds = []
        if pn == "Bottom_Tray":
            ds = (B.floor_detents(True, 0.05) + B.floor_detents(False, 0.05)
                  + B.floor_rear_detents(0.05) + B.shroud_lap_detents(False, 0.05))
        elif pn in ("Side_Left_MB", "Side_Right_MB"):
            lf = pn.endswith("Left_MB")
            ds = B.rear_tab_detents(lf, 0.05) + B.shroud_detents(lf, 0.05)
        elif pn == "Top_MB":
            ds = B.shroud_lap_detents(True, 0.05)
        for d in ds:
            sh = sh.cut(d)
        return sh

    installed = {}
    for si, (key, dy) in enumerate(D.ASSEMBLY_STEPS):
        sh = shapes.get(key)
        if sh is None:
            continue
        if abs(dy) < 1e-9:
            installed[key] = detent_free(key, sh)
            ok(f"組裝 {si + 1}. {key}：基準件（放著不動）")
            continue
        start = sh.copy()
        start.translate(App.Vector(0, -dy, 0))
        swept = sweep(start, dy=dy, steps=50 if abs(dy) > 60 else None)
        wp, wv = None, 0.0
        for pn, osh in installed.items():
            v = common_vol(swept, osh)
            if v > wv:
                wp, wv = pn, v
        (fail if wv > INTERFERE_MAX else ok)(
            f"組裝 {si + 1}. {key} 沿 Y {dy:+.1f} mm 裝入"
            + (f"：撞已裝好的 {wp} {wv:.1f} mm³" if wv > INTERFERE_MAX
               else f"（場上已有 {len(installed)} 件，路徑淨空）")
        )
        installed[key] = detent_free(key, sh)
    log("（電源／主板／PCIe 卡在第 4 與第 5 步之間裝入，見下方各自的掃描）")

    # 1) PCIe 卡：拆掉 PCIeBar 後整片抬 PCIE_ENGAGE 必須無阻
    for i in range(D.PCIE_COUNT):
        blocked = []
        for tag in (f"PCIe{i}_bracket", f"PCIe{i}_card", f"PCIe{i}_耳keepout"):
            p, v = hits(sweep(mocks[tag], dz=D.PCIE_ENGAGE), skip=("PCIeBar",))
            if v > INTERFERE_MAX:
                blocked.append(f"{tag}→{p} {v:.1f}")
        (fail if blocked else ok)(
            f"PCIe{i} {'抬升受阻：' + '; '.join(blocked) if blocked else '垂直裝拆路徑淨空'}"
        )
    # 2) 壓條鎖上以後，同一個抬升必須被它擋住
    if bar is not None:
        held = sum(
            1 for i in range(D.PCIE_COUNT)
            if common_vol(sweep(mocks[f"PCIe{i}_耳keepout"], dz=D.PCIE_ENGAGE), bar) > INTERFERE_MAX
        )
        (ok if held == D.PCIE_COUNT else fail)(f"PCIeBar 擋住 {held}/{D.PCIE_COUNT} 槽的抬升")
        p, v = hits(mocks["PCIe0_耳keepout"])
        (ok if v <= INTERFERE_MAX else fail)(
            f"壓條在裝好狀態下不壓進折耳帶{'' if v <= INTERFERE_MAX else f'：{p} {v:.1f}'}"
        )
        if "Top_MB" in shapes:
            lid_hold = sum(
                1 for i in range(D.PCIE_COUNT)
                if common_vol(sweep(mocks[f"PCIe{i}_耳keepout"], dz=D.PCIE_ENGAGE),
                              shapes["Top_MB"]) > INTERFERE_MAX
            )
            (ok if lid_hold == 0 else fail)(f"Top_MB 不兼差壓卡（{lid_hold} 槽）")
    # 2b) 壓帽：旋得上去、而且牙是**螺旋**（轉半牙距 → 必撞）
    if nut is not None and tray is not None:
        bad = [
            letter for letter, (hx, hy) in D.HOLES_MM.items()
            if common_vol(B.place_mb_nut(B.make_mb_nut(), hx, hy, D.BOARD_TOP_Z), tray)
            > INTERFERE_MAX
        ]
        (fail if bad else ok)(
            f"壓帽{'旋不到工作位（牙撞牙）：' + str(bad) if bad else f'九孔皆可旋到板面（{len(D.HOLES_MM)}/9）'}"
        )
        hx, hy = D.HOLES_MM["B"]
        n2 = nut.copy()
        n2.rotate(App.Vector(hx, hy, 0), App.Vector(0, 0, 1), 180.0)
        v = common_vol(n2, tray)
        (ok if v > INTERFERE_MAX else fail)(
            f"牙是真螺旋：相位轉 180° 撞 {v:.1f} mm³"
            if v > INTERFERE_MAX else f"相位轉 180° 只撞 {v:.2f} mm³ — 軸對稱假螺紋"
        )
    # 3) 硬碟：第八輪是**平躺**，托盤自 +Y 往前抽出（不是垂直抽）。
    #    這條是整輪最重要的動作檢查：換碟不必拆頂蓋、不必拆前罩、不必動上面幾層。
    pull = D.HDD_W + D.TRAY_FRONT_GAP + 10.0
    for lv in range(D.HDD_LEVELS):
        p, v = hits(sweep(mocks[f"HDD_L{lv}"], dy=pull), skip=("HDD_Tray",))
        (fail if v > INTERFERE_MAX else ok)(
            f"HDD 第 {lv} 層 "
            f"{'自 +Y 抽出撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else f'自 +Y 抽出 {pull:.1f} mm 路徑淨空'}"
        )
    # 3b) 碟架自 +Y 滑入（推到 y=180.34），路上不能撞主板／電源／PCIe 卡
    if rack is not None:
        slide = D.CASE_FRONT - D.HDD_Y0
        p, v = hits(sweep(rack, dy=slide), skip=("HDD_Rack", "HDD_Tray", "Front_Shroud", "Top_MB"))
        (fail if v > INTERFERE_MAX else ok)(
            f"碟架自 +Y 滑入 {slide:.1f} mm "
            f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '路徑淨空'}"
        )
        for tag in ("主板PCB", "PSU_150x86x140", "PCIe0_card", "PCIe3_card"):
            v = common_vol(sweep(rack, dy=slide), mocks[tag])
            (fail if v > INTERFERE_MAX else ok)(f"碟架滑入路徑 vs {tag} = {v:.1f} mm³")
    # 3c) 頂蓋自 +Y 滑入：路上不能撞電源與碟架
    if top is not None:
        slide = D.CASE_FRONT - D.FLOOR_Y0
        p, v = hits(sweep(top, dy=slide), skip=("Top_MB", "Front_Shroud", "HDD_Tray"))
        (fail if v > INTERFERE_MAX else ok)(
            f"頂蓋自 +Y 滑入 {slide:.1f} mm "
            f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '路徑淨空'}"
        )
    # 3d) PCIe 壓條：**抬 PCIE_BAR_DROP → 往 −Y 拔**。兩段都要掃。
    #     舊做法是沿 X 滑，那條路徑逼出了連續橫縫（＝使用者主訴的懸空成因）。
    if bar is not None:
        # detent 是**刻意的彈性過盈**（保持力的來源）：公件在蘑菇柱的翼上，
        # 掃描前要把它從後牆扣掉——否則這條檢查永遠紅，而且紅的是設計意圖不是缺陷。
        det_all = None
        for hx in D.pcie_hook_x():
            for d in B.hook_detents(hx, grow=0.05):
                det_all = d if det_all is None else det_all.fuse(d)
        rear_nodet = rear.cut(det_all)
        others = {k: v for k, v in shapes.items() if k not in ("PCIeBar", "Rear_IO_PCIe")}
        others["Rear_IO_PCIe"] = rear_nodet

        def hits2(swept):
            wp, wv = None, 0.0
            for pn, sh in others.items():
                v = common_vol(swept, sh)
                if v > wv:
                    wp, wv = pn, v
            return wp, wv

        up = sweep(bar, dz=D.PCIE_BAR_DROP)
        p, v = hits2(up)
        (fail if v > INTERFERE_MAX else ok)(
            f"壓條解鎖抬起 {D.PCIE_BAR_DROP} mm "
            f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '路徑淨空'}"
        )
        lifted = bar.copy()
        lifted.translate(App.Vector(0, 0, D.PCIE_BAR_DROP))
        p, v = hits2(sweep(lifted, dy=-(D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_HEAD_D + 10.0)))
        (fail if v > INTERFERE_MAX else ok)(
            f"壓條抬起後往 −Y 拔出 "
            f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '路徑淨空（不必拆頂蓋、不必沿 X 滑）'}"
        )
        (ok if D.DETENT_DEPTH <= 0.6 and D.DETENT_DEPTH < D.DETENT_R else fail)(
            f"detent 凸出 {D.DETENT_DEPTH} mm（< 半徑 {D.DETENT_R}，靠翼的彈性爬過去）"
        )
        # 落到定位時 detent **不干涉**（過盈只發生在行程中）→ 前面的 interference 段就是證據
        (ok if common_vol(bar, rear) <= INTERFERE_MAX else fail)(
            f"壓條落到定位與後牆不干涉 {common_vol(bar, rear):.2f} mm³"
        )
    # 3e) 前罩自 +Y 套上：★ 第九輪新增。前罩補了地板之後，那片地板舌會**在滑動途中
    #     撞到主板柱**（L／M 兩孔 y=227.33，柱是自 z=0 長起的 Ø8 圓柱）——
    #     最終位置合法、路被擋住，靜態檢查全綠。底板留實心柱腳、前罩挖讓位槽。
    if shroud is not None:
        det_side, det_lap = None, {}
        for is_left in (True, False):
            for s in B.shroud_detents(is_left, grow=0.05):
                det_side = s if det_side is None else det_side.fuse(s)
        for pn, is_top in (("Top_MB", True), ("Bottom_Tray", False)):
            for s in B.shroud_lap_detents(is_top, grow=0.05):
                det_lap[pn] = s if pn not in det_lap else det_lap[pn].fuse(s)
        others = {}
        for pn, sh in shapes.items():
            if pn in ("Front_Shroud", "HDD_Tray"):
                continue
            if pn in ("Side_Left_MB", "Side_Right_MB"):
                sh = sh.cut(det_side)
            if pn in det_lap:
                sh = sh.cut(det_lap[pn])
            others[pn] = sh

        def hits3(swept):
            wp, wv = None, 0.0
            for pn, sh in others.items():
                v = common_vol(swept, sh)
                if v > wv:
                    wp, wv = pn, v
            return wp, wv

        p, v = hits3(sweep(shroud, dy=D.SHROUD_LAP + D.SHROUD_D + 20.0))
        (fail if v > INTERFERE_MAX else ok)(
            f"前罩自 +Y 套上 "
            f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '路徑淨空（含主板柱讓位槽）'}"
        )
        # 反向：讓位槽不能大到讓搭接失效——柱腳與槽必須真的成對
        bands = B.shroud_floor_stud_bands()
        (ok if len(bands) == 2 else fail)(
            f"搭接帶裡有 {len(bands)} 根主板柱要讓位（L／M 兩孔 y={D.HOLES_MM['L'][1]:.2f}）"
        )
        for bx0, bx1 in bands:
            xm = (bx0 + bx1) / 2
            ym = D.BAY_SPLIT_Y - D.SHROUD_LAP / 2
            (ok if pt_inside(tray, xm, ym, D.FLOOR_T - 0.3, 0.02) else fail)(
                f"底板 x={xm:.2f} 保留整厚柱腳"
            )
            (fail if pt_inside(shroud, xm, ym, D.FLOOR_T - 0.3, 0.02) else ok)(
                f"前罩 x={xm:.2f} 有對應讓位槽"
            )

    # 4) 主板：抬過細軸頂再往後推進 I/O shield（壓帽是之後才鎖的）
    lift = D.MB_STUD_TOP_Z - (D.BOARD_TOP_Z - D.PCB_T) + 2.0
    p, v = hits(sweep(mocks["主板PCB"], dz=lift), skip=("MB_Nut", "Top_MB"))
    (fail if v > INTERFERE_MAX else ok)(
        f"主板垂直裝入路徑（抬 {lift:.1f} 過細軸頂）"
        f"{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '淨空'}"
    )
    # 5) 電源：先橫移讓開頂蓋承托肩，再垂直落入（沒有蓋子時）
    psu = mocks["PSU_150x86x140"]
    p, v = hits(sweep(psu, dx=D.PSU_SLIDE_X, dy=D.PSU_SLIDE_Y))
    (ok if D.PSU_SLIDE_Y > D.TOP_HOOK_D else fail)(
        f"電源前移量 {D.PSU_SLIDE_Y} > 後牆頂鉤唇伸出 {D.TOP_HOOK_D}"
    )
    if v > INTERFERE_MAX:
        fail(f"電源前移 {D.PSU_SLIDE_Y} mm 就撞 {p} {v:.1f}")
    else:
        ok(f"電源可前移 {D.PSU_SLIDE_Y} mm（讓開後牆頂鉤唇）")
        shifted = psu.copy()
        shifted.translate(App.Vector(D.PSU_SLIDE_X, D.PSU_SLIDE_Y, 0))
        p, v = hits(sweep(shifted, dz=D.OUTER_TOP_Z - D.ATX_Z0), skip=("Top_MB", "Front_Shroud"))
        (fail if v > INTERFERE_MAX else ok)(
            f"電源自上方落入路徑{'撞 ' + str(p) + f' {v:.1f}' if v > INTERFERE_MAX else '淨空（掀蓋後）'}"
        )

    # ── A1 / STL ─────────────────────────────────────────────────
    log("--- A1 / STL ---")
    if D.A1_EXCLUDE == ():
        ok("A1 bed_exclude_area = [] (18x28 是 P1P/P1S/X1 系列，不是 A1)")
    else:
        fail(f"A1_EXCLUDE={D.A1_EXCLUDE} 與 profile 不符")
    if approx(D.A1_MAX, 256.0, 0.01) and approx(D.A1_H_MAX, 256.0, 0.01):
        ok("A1 printable 256 x 256 x 256")
    else:
        fail(f"A1 {D.A1_MAX}x{D.A1_H_MAX} 與 profile 不符")
    a1_lines, stl_lines = [], []
    for o in doc.Objects:
        if not hasattr(o, "Shape") or o.Shape.isNull():
            continue
        bb = obb(o.Shape)
        dims = (bb.XLength, bb.YLength, bb.ZLength)
        flag = "OK" if max(dims) <= D.A1_MAX + 1e-6 else "OVERSIZE"
        if flag != "OK":
            fail(f"oversize {o.Name} {dims}")
        elif max(dims) > D.A1_MAX - 6.0:
            warn(f"A1 {o.Name} max={max(dims):.2f} 只剩 {D.A1_MAX - max(dims):.2f} mm 床邊裕度")
        else:
            ok(f"A1 {o.Name} max={max(dims):.2f}")
        a1_lines.append(f"{o.Name}\t{dims[0]:.2f}\t{dims[1]:.2f}\t{dims[2]:.2f}\t{flag}")

    for key, fn in dict(D.STL_NAMES).items():
        path = os.path.join(STL_DIR, fn)
        if not os.path.isfile(path) or os.path.getsize(path) < 1024:
            fail(f"STL {fn}")
            stl_lines.append(f"{fn}\tBAD")
        else:
            ok(f"STL {fn} {os.path.getsize(path)}")
            stl_lines.append(f"{fn}\t{os.path.getsize(path)}")
    for fn in D.REMOVED_STL:
        path = os.path.join(STL_DIR, fn)
        (fail if os.path.isfile(path) else ok)(
            f"{'stale STL still exists: ' if os.path.isfile(path) else 'no stale STL '}{fn}"
        )

    w, d, h = D.envelope_mm()
    # ★ 這兩個數字不一樣，兩個都要印：只印前者的話下一輪還是拿它去買料。
    #   總成裡每個 STL 只放一份（碟托盤第 0 層那片、壓帽 B 孔那顆），
    #   逐件加總少算 碟托盤 ×3 + 壓帽 ×8 + 槽蓋 ×3 = 219 cm³（20%）。硬規則 26。
    total = sum(s.Volume for k, s in shapes.items()) / 1000.0
    total_qty = sum(s.Volume * D.PART_QTY[k] for k, s in shapes.items()) / 1000.0
    log(
        f"ENVELOPE {w:.1f} x {d:.1f} x {h:.1f} mm  volume={D.case_volume_l():.2f} L  "
        f"印料={total:.1f} cm3(一件一份) / {total_qty:.1f} cm3(含份數，買料看這個)"
    )
    (ok if total_qty > total else fail)(
        f"料量含份數 {total_qty:.1f} > 一件一份 {total:.1f} cm3（份數表有生效）"
    )
    if 230 <= w <= 270 and 280 <= d <= 320 and 150 <= h <= 200:
        ok(f"envelope class ({w:.0f}x{d:.0f}x{h:.0f})")
    else:
        fail(f"envelope out of expected band {w:.1f}x{d:.1f}x{h:.1f}")
    vol = D.case_volume_l()
    (ok if vol < 15.0 else fail)(f"整機體積 {vol:.2f} L < 使用者要求的 15 L")
    # ★ 第十輪：舊版是 `install_depth_mm() <= CASE_D + PCIE_BAR_T`——**它在跟自己的
    #   定義比**，永遠綠（vacuous check，硬規則 16）。而且最凸的其實是蘑菇柱 8.00
    #   不是壓條 5.00，少報了 3 mm。現在改成對**幾何量出來的實際外凸量**比。
    if bar is not None and rear is not None:
        y_min = min(obb(bar).YMin, obb(rear).YMin)
        real = D.CASE_REAR - y_min
        (ok if approx(real, D.rear_outer_protrusion(), 0.05) else fail)(
            f"後牆外實際外凸 {real:.2f} mm = rear_outer_protrusion() "
            f"{D.rear_outer_protrusion():.2f}（量出來的，不是用定義推的）"
        )
        (ok if approx(D.install_depth_mm(), D.CASE_D + real, 0.05) else fail)(
            f"安裝深度 {D.install_depth_mm():.2f} = 機殼深 {D.CASE_D:.2f} + 外凸 {real:.2f}"
        )

    write_outs(a1_lines, stl_lines, names)
    App.closeDocument(doc.Name)
    if failures:
        log(f"RESULT: {len(failures)} failure(s)")
        return 1
    log("RESULT: ALL CHECKS PASSED")
    return 0


def write_outs(a1_lines=None, stl_lines=None, names=None):
    open(os.path.join(SCRATCH, "cad_inventory.txt"), "w", encoding="utf-8").write(
        "\n".join((names or []) + lines) + "\n"
    )
    with open(os.path.join(SCRATCH, "dim_check.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + f"\n\nfailures={len(failures)}\n")
        if not failures:
            f.write("RESULT: ALL CHECKS PASSED\n")
    open(os.path.join(SCRATCH, "a1_fit.txt"), "w", encoding="utf-8").write(
        "name\tX\tY\tZ\tstatus\n" + "\n".join(a1_lines or []) + "\n"
    )
    open(os.path.join(SCRATCH, "stl_list.txt"), "w", encoding="utf-8").write(
        "file\tsize_bytes\n" + "\n".join(stl_lines or []) + "\n"
    )


if __name__ == "__main__":
    sys.exit(main())
