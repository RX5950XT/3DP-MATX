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

import build_case as B  # 共用螺紋、detent 與裝配幾何

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


def support_overhangs(shape, thresh=None):
    """
    回傳 [(面積, 斜率, BoundBox)]：**平面**且法線朝下、斜率 < 門檻的面
    ——切片器會在它下面長支撐的那些面。斜率自水平量起（90° = 垂直牆），
    門檻的唯一來源是 `參數.SUPPORT_THRESHOLD_ANGLE`（= preset 的
    support_threshold_angle，由 `驗切片設定.py` 比對）。

    只看平面：曲面（孔壁、螺紋）的法線沿面變化，取中點法線會誤判。
    那一類靠橋接與 support_remove_small_overhang 處理，不在這條檢查的射程內。
    """
    if thresh is None:
        thresh = D.SUPPORT_THRESHOLD_ANGLE
    out = []
    for f in shape.Faces:
        surf = getattr(f, "Surface", None)
        if surf is None or "Plane" not in type(surf).__name__:
            continue
        try:
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        except Exception:
            continue
        ln = n.Length or 1.0
        nz = n.z / ln
        if nz >= -1e-6:
            continue
        slope = 90.0 - math.degrees(math.asin(min(1.0, abs(nz))))
        if slope < thresh:
            out.append((float(f.Area), slope, f.BoundBox))
    return out


def obb(shape):
    """
    `Shape.BoundBox` 對 B-spline 面是用控制多邊形算的，會虛胖；
    解析螺紋件一律走真外接盒，避免把 spline 控制點包絡當成實體尺寸。
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
    # ★ 第十三輪新增：**I/O 連接器區**。第十二輪的虛擬件只有 PCB 的長方體，
    #   而 microATX Fig.5 的 note 說得很明白：連接器的**面**在 Datum B 後方
    #   11.30 mm —— 比 PCB 後緣（10.16）還往後突出 1.14。虛擬件缺這一塊，
    #   「後牆內面壓在連接器上」就永遠是綠的（硬規則 21：虛擬件要含它伸出去的東西）。
    m["IO連接器區"] = mk_box(
        D.IO_X0,
        -D.IO_CONN_FACE_FROM_B,
        D.IO_Z0,
        D.IO_X1,
        -D.IO_CONN_FACE_FROM_B + D.IO_CONN_DEPTH,
        D.IO_Z1,
    )

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
    log("=== 3DP-MATX verify（第十二輪：一體 Chassis／格柵／新固定件）===")
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
    printable = {
        o.Name for o in doc.Objects
        if hasattr(o, "Shape") and not o.Shape.isNull()
    }
    expected = set(required)
    (ok if printable == expected else fail)(
        "CAD 可列印物件集合與 manifest 完全一致"
        if printable == expected else
        f"CAD/manifest 不一致 missing={sorted(expected - printable)} "
        f"extra={sorted(printable - expected)}"
    )
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

    chassis = shapes.get("Chassis_Body")
    top = shapes.get("Top_MB")
    rack = shapes.get("HDD_Rack")
    dtray = shapes.get("HDD_Tray")
    shroud = shapes.get("Front_Shroud")
    bar = shapes.get("PCIeBar")
    screw = shapes.get("MB_Screw")

    # ── 每個 STL 都必須是單一封閉實體 ─────────────────────────────
    log("--- solids ---")
    for key in D.STL_NAMES:
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

    # ── 主板固定：Ø8 支撐肩盲內牙 + 印製六角頭螺絲 ────────────────
    log("--- MB standoff（盲內牙 + MB_Screw）---")
    stale = [
        g for g in (
            "CAP_OD", "CAP_H", "CAP_COUNT", "MB_SCREW_TAP", "MB_SCREW_DEPTH",
            "MB_STUD_MAJOR", "MB_STUD_MINOR", "MB_NUT_OD", "MB_NUT_H",
        ) if hasattr(D, g)
    ]
    (fail if stale else ok)(
        f"{'退役主板固定參數仍存在：' + str(stale) if stale else '外凸 stud／壓帽參數已清除'}"
    )
    depth = (D.MB_THREAD_MAJOR - D.MB_THREAD_MINOR) / 2
    (ok if depth >= 0.5 - 1e-9 else fail)(f"徑向牙深 {depth:.2f} >= 0.5")
    (ok if D.MB_SCREW_HEAD_D < D.MB_KEEPOUT_D else fail)(
        f"六角頭外接圓 Ø{D.MB_SCREW_HEAD_D:.2f} < keepout Ø{D.MB_KEEPOUT_D}"
    )
    (ok if D.MB_THREAD_MAJOR < D.PCB_HOLE_D else fail)(
        f"外牙 Ø{D.MB_THREAD_MAJOR} < PCB 孔 Ø{D.PCB_HOLE_D}"
    )
    female_crest = D.MB_THREAD_PITCH * (1.0 - D.MB_THREAD_ROOT_W) - 2 * D.MB_THREAD_GAP
    (ok if female_crest >= 0.8 else fail)(
        f"內牙牙頂寬 {female_crest:.2f} >= 0.8（兩條 0.4 nozzle 線）"
    )
    (ok if approx(D.MB_THREAD_ENGAGEMENT / D.MB_THREAD_PITCH, 2.0, 1e-6) else fail)(
        f"軸向旋合 {D.MB_THREAD_ENGAGEMENT:.2f} mm = "
        f"{D.MB_THREAD_ENGAGEMENT / D.MB_THREAD_PITCH:.1f} 圈"
    )
    (ok if approx(D.MB_SCREW_THREAD_LEN,
                  D.PCB_T + D.MB_THREAD_ENGAGEMENT, 1e-6) else fail)(
        f"螺絲牙長 {D.MB_SCREW_THREAD_LEN:.2f} = PCB {D.PCB_T} + 旋合 {D.MB_THREAD_ENGAGEMENT}"
    )
    (ok if approx(D.MB_SOCKET_DEPTH,
                  D.MB_THREAD_ENGAGEMENT + D.MB_SOCKET_END_GAP, 1e-6) else fail)(
        f"盲孔深 {D.MB_SOCKET_DEPTH:.2f} = 旋合 + 端隙 {D.MB_SOCKET_END_GAP}"
    )
    (ok if D.MB_SOCKET_BOTTOM_MATERIAL >= 0.8 else fail)(
        f"盲孔底料 {D.MB_SOCKET_BOTTOM_MATERIAL:.2f} >= 0.8"
    )
    # 頭頂十字工具槽（第十四輪；使用者：螺絲上面要有十字的孔）。
    # 螺絲頭面貼床印，槽開在貼床那一面 → 槽是第一層的孔，不需支撐。
    (ok if D.MB_SCREW_CROSS_W >= 0.5 else fail)(
        f"十字臂寬 {D.MB_SCREW_CROSS_W:.2f} >= 0.5 最小可印特徵"
    )
    (ok if D.MB_SCREW_CROSS_WALL >= 0.8 else fail)(
        f"十字外側餘料 {D.MB_SCREW_CROSS_WALL:.2f} >= 0.8"
    )
    (ok if D.MB_SCREW_CROSS_ROOF >= 0.8 else fail)(
        f"十字槽頂料 {D.MB_SCREW_CROSS_ROOF:.2f} >= 0.8（也是那一層的橋接底）"
    )
    (ok if D.MB_SCREW_CROSS_DEPTH < D.MB_SCREW_HEAD_H else fail)(
        f"槽深 {D.MB_SCREW_CROSS_DEPTH:.2f} < 頭厚 {D.MB_SCREW_HEAD_H}（不吃到牙）"
    )
    # 探點用**列印姿態**的原型：doc 裡的 MB_Screw 是總成位（已翻轉並平移到 B 孔）。
    raw_screw = B.make_mb_screw()
    if raw_screw is not None:
        zc = D.MB_SCREW_CROSS_DEPTH / 2
        arm = D.MB_SCREW_CROSS_L / 2
        empties = [
            ("槽心", 0.0, 0.0, zc),
            ("+X 臂末", arm - 0.3, 0.0, zc),
            ("-X 臂末", -(arm - 0.3), 0.0, zc),
            ("+Y 臂末", 0.0, arm - 0.3, zc),
            ("-Y 臂末", 0.0, -(arm - 0.3), zc),
        ]
        bad = [n for n, x, y, z in empties if pt_inside(raw_screw, x, y, z)]
        (fail if bad else ok)(
            f"{'十字槽沒挖穿：' + str(bad) if bad else '十字五個探點皆為空腔'}"
        )
        # 非 vacuous：圓孔／方孔也會讓上面五點變空，象限角必須是實心才算十字。
        q = D.MB_SCREW_CROSS_W / 2 + 0.4
        solids = [
            ("象限角", q, q, zc),
            ("槽外料", arm + 0.6, 0.0, zc),
            ("槽頂料", 0.0, 0.0, D.MB_SCREW_CROSS_DEPTH + D.MB_SCREW_CROSS_ROOF / 2),
        ]
        hollow = [n for n, x, y, z in solids if not pt_inside(raw_screw, x, y, z)]
        (fail if hollow else ok)(
            f"{'應有料處是空的：' + str(hollow) if hollow else '象限角／槽外／槽頂皆實心（是十字不是圓孔）'}"
        )
    (ok if approx(D.SHOULDER_TOP_Z - D.FLOOR_T, 6.35, 1e-6) else fail)(
        f"粗肩高 {D.SHOULDER_TOP_Z - D.FLOOR_T:.2f} = 板底淨空 6.35"
    )
    if chassis is not None:
        aligned_bad = []
        for letter, (hx, hy) in D.HOLES_MM.items():
            placed = B.place_mb_screw(B.make_mb_screw(), hx, hy)
            v = common_vol(placed, chassis)
            if v > INTERFERE_MAX:
                aligned_bad.append(f"{letter}:{v:.1f}")
            if pt_inside(chassis, hx, hy, D.SHOULDER_TOP_Z + 0.2, 0.02):
                fail(f"standoff {letter}: PCB 上方仍有 Chassis 凸柱")
            elif not pt_inside(chassis, hx, hy, D.MB_SOCKET_BOTTOM_Z - 0.3, 0.02):
                fail(f"standoff {letter}: 盲孔打穿底料")
            elif not pt_inside(chassis, hx + D.SHOULDER_OD / 2 - 0.5, hy,
                               D.FLOOR_T + 0.3, 0.02):
                fail(f"standoff {letter}: Ø8 支撐肩不實")
            else:
                ok(f"standoff {letter}：肩實、盲孔底實、PCB 上方無凸柱")
        (fail if aligned_bad else ok)(
            f"MB_Screw {'工作相位撞 Chassis：' + str(aligned_bad) if aligned_bad else '九孔皆可到工作位'}"
        )
        hx, hy = D.HOLES_MM["B"]
        turned = B.place_mb_screw(B.make_mb_screw(), hx, hy)
        turned.rotate(App.Vector(hx, hy, 0), App.Vector(0, 0, 1), 180.0)
        phase_v = common_vol(turned, chassis)
        (ok if phase_v > INTERFERE_MAX else fail)(
            f"真螺旋：相位轉 180° 撞 {phase_v:.1f} mm³"
            if phase_v > INTERFERE_MAX else
            f"相位轉 180° 只撞 {phase_v:.2f} mm³——疑似軸對稱假牙"
        )
    if screw is not None:
        sb = obb(screw)
        (ok if approx(sb.ZMin, D.SHOULDER_TOP_Z - D.MB_THREAD_ENGAGEMENT, 0.05)
         and approx(sb.ZMax, D.MB_SCREW_HEAD_TOP_Z, 0.05) else fail)(
            f"總成螺絲 Z={sb.ZMin:.2f}..{sb.ZMax:.2f}，旋入 5 mm 且頭壓 PCB"
        )

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
    if chassis is not None:
        # 後牆承托凸緣（電源坐在上面）
        y_led = D.CASE_REAR + D.WALL + D.PSU_LEDGE_W / 2
        (ok if pt_inside(chassis, D.ATX_X0 + 80, y_led, D.ATX_Z0 - D.PSU_LEDGE_T / 2, 0.02) else fail)(
            "後牆 PSU 承托凸緣實心"
        )
        (fail if pt_inside(chassis, D.ATX_X0 + 80, y_led, D.ATX_Z0 - D.PSU_LEDGE_T - 2.0, 0.02) else ok)(
            "承托凸緣底面 = Area A 淨空頂（沒有再往下長）"
        )
    if chassis is not None:
        x_led = D.CASE_LEFT + D.WALL + D.PSU_LEDGE_W / 2
        (ok if pt_inside(chassis, x_led, 60.0, D.ATX_Z0 - D.PSU_LEDGE_T / 2, 0.02) else fail)(
            "左側板 PSU 長肩實心（電源左緣整條坐在上面）"
        )

    # ── 走線：電源與主板同一個空間（使用者主訴「根本無法走線」）──────
    log("--- 走線淨空 ---")
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
    env = mk_box(D.CASE_LEFT, D.CASE_REAR, -D.SKIRT_H,
                 D.CASE_RIGHT, D.CASE_FRONT, D.OUTER_TOP_Z)
    env_chassis = mk_box(
        D.CASE_LEFT,
        D.CASE_REAR - D.PCIE_RIB_D,
        -D.SKIRT_H,
        D.CASE_RIGHT,
        D.CASE_FRONT,
        D.OUTER_TOP_Z,
    )
    for key, sh in shapes.items():
        if key in ("PCIeBlank", "PCIeBar"):
            continue  # 備件停放在外；壓條是外掛固定件
        e = env_chassis if key == "Chassis_Body" else env
        v = sh.cut(e).Volume
        (ok if v <= INTERFERE_MAX else fail)(
            f"{key} 在允許包絡內（外溢 {v:.2f} mm³）"
        )
    if chassis is not None:
        print_rear = D.CASE_REAR - obb(chassis).YMin
        (ok if approx(print_rear, D.PCIE_RIB_D, 0.05) else fail)(
            f"一體件列印後凸 {print_rear:.2f} = PCIe 補強 {D.PCIE_RIB_D:.2f}"
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
    if chassis:
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
        # ★ 第十三輪：Fig.4 有**兩張圖**，前十二輪只用了正視圖。側視圖同時給了
        #   Z 的第二基準與整條深度基準；兩個 Z 基準都成立才算真的對上。
        (ok if approx(D.IO_FROM_STANDOFF_TOP, 2.24, 1e-6) else fail)(
            f"Fig.4 側視 literal .088 [2.24] 未被改動（現值 {D.IO_FROM_STANDOFF_TOP}）"
        )
        (ok if approx(D.IO_Z0, D.SHOULDER_TOP_Z - D.IO_FROM_STANDOFF_TOP, 1e-6) else fail)(
            f"IO 開孔底 {D.IO_Z0:.2f} = 支撐肩頂 {D.SHOULDER_TOP_Z:.2f} − 2.24"
            f"（Fig.4 側視第二基準：from bottom surface of motherboard / top of standoffs）"
        )
        (ok if approx(D.IO_APERTURE_FROM_B, 12.27, 1e-6) else fail)(
            f"Fig.4 側視 literal 0.483 [12.27] 未被改動（現值 {D.IO_APERTURE_FROM_B}）"
        )
        (ok if approx(D.IO_CONN_FACE_FROM_B, 11.30, 1e-6) else fail)(
            f"Fig.5 note literal .445 [11.30] 未被改動（現值 {D.IO_CONN_FACE_FROM_B}）"
        )
        (ok if approx(D.CASE_REAR + D.WALL, -D.IO_APERTURE_FROM_B, 1e-6) else fail)(
            f"後牆內面 {D.CASE_REAR + D.WALL:.2f} = I/O aperture 平面 "
            f"−{D.IO_APERTURE_FROM_B:.2f}（不是「板緣 − MARGIN − WALL」）"
        )
        conn_gap = (-D.IO_CONN_FACE_FROM_B) - (D.CASE_REAR + D.WALL)
        (ok if conn_gap > 0.0 else fail)(
            f"I/O 連接器面 −{D.IO_CONN_FACE_FROM_B:.2f} 在後牆內面之內，留 "
            f"{conn_gap:.2f} mm 給 I/O shield"
            if conn_gap > 0.0 else
            f"I/O 連接器面戳進後牆料 {-conn_gap:.2f} mm —— 主板推不到底"
        )
        (ok if -D.IO_CONN_FACE_FROM_B < D.BOARD_REAR else fail)(
            f"連接器面比 PCB 後緣 {D.BOARD_REAR:.2f} 還往後突出 "
            f"{D.BOARD_REAR - (-D.IO_CONN_FACE_FROM_B):.2f}（Fig.5：這就是 MARGIN=0.5 不夠的原因）"
        )
        io_cx, io_cz = (D.IO_X0 + D.IO_X1) / 2, (D.IO_Z0 + D.IO_Z1) / 2
        (fail if pt_inside(chassis, io_cx, y_mid, io_cz) else ok)("IO opening void")
        edge = D.io_edge_material()
        (ok if edge >= D.IO_KEEPOUT + 0.8 else fail)(
            f"IO outer edge material {edge:.2f} >= keepout {D.IO_KEEPOUT}+0.8"
        )
        (ok if pt_inside(chassis, D.IO_X0 - D.IO_KEEPOUT / 2, D.CASE_REAR + D.WALL - 0.3, io_cz)
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
            (fail if pt_inside(chassis, D.ATX_X0 + hx, y_mid, D.ATX_Z0 + hz) else ok)(
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
            (fail if pt_inside(chassis, xx, y_mid, zz) else ok)(f"PSU window open at {tag}")
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
        z_tie = (D.PCIE_TIE_Z0 + D.PCIE_TIE_Z1) / 2
        for tag, xx in (("between slots", (min(centers) + max(centers)) / 2), ("over slot", centers[0])):
            (ok if pt_inside(chassis, xx, y_wall, z_tie) else fail)(f"PCIe tie bar solid {tag}")
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
                (D.PCIE_TIE_Z0 + D.PCIE_TIE_Z1) / 2,  # 上固定端（繫樑）
            ]
            gaps = [z for z in zs if not pt_inside(chassis, xm, y_wall, z, 0.02)]
            (fail if gaps else ok)(
                f"肋 x={xm:.2f} 上下貫通"
                if not gaps
                else f"肋 x={xm:.2f} 在 z={['%.1f' % z for z in gaps]} 斷掉 → 懸臂"
            )
            # 往機殼外加厚的補強（斷面 1.42×2.40 → 1.42×6.40）
            (ok if pt_inside(chassis, xm, D.CASE_REAR - D.PCIE_RIB_D / 2, z_open_mid, 0.02) else fail)(
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
            ("繫樑（肋的上端固定端）", (cs_sorted[0] + cs_sorted[1]) / 2, fz1 - 1.0),
        ):
            (ok if pt_inside(chassis, xx, y_boss, zz, 0.02) else fail)(
                f"PCIe 窗框{tag}外側補強實心（總厚 {D.WALL + D.PCIE_RIB_D:.2f}）"
            )
        (ok if fx0 >= D.IO_X1 else fail)(
            f"窗框補強左端 {fx0:.2f} >= I/O 開孔近緣 {D.IO_X1:.2f}（沒有從外面補住 I/O 開孔）"
        )
        (ok if fx1 <= D.CASE_RIGHT + 1e-9 else fail)(
            f"窗框補強右端 {fx1:.2f} <= 機殼外表面 {D.CASE_RIGHT:.2f}"
        )
        (ok if approx(fz1, D.PCIE_TIE_Z1, 1e-6) else fail)(
            f"窗框補強頂 {fz1:.2f} = 繫樑頂 {D.PCIE_TIE_Z1:.2f}"
            f"（第十三輪：壓條在補強層外面，y 不重疊，不必為它讓開；"
            f"補強不長到這裡的話兩個盲牙就鑽在只有 {D.WALL} 厚的牆上）"
        )
        # ★ 第十三輪：開孔頂改 45° 尖頂 —— 使用者實印時拆支撐把三根 1.42 的肋
        #   一起扯斷。根因不是肋不夠粗，是那四個開孔**需要支撐**（頂是 18.9 mm
        #   寬的水平懸空，切片器在 118 mm 深的槽裡長支撐塔，塔與肋咬死）。
        #   驗的是「頂上沒有水平面」：沿尖頂逐點量寬度，必須線性收斂成 45°。
        (ok if approx(D.PCIE_OPEN_Z1, D.PCIE_Z1 + D.PCIE_LIFT, 1e-6) else fail)(
            f"全寬開孔頂 {D.PCIE_OPEN_Z1:.2f} = 擋板頂 + 抬升 {D.PCIE_LIFT:.2f}"
            f"（尖頂自這裡起算，抬升一點都沒有少）"
        )
        (ok if approx(D.PCIE_APEX_H, D.PCIE_OPEN_W / 2, 1e-6) else fail)(
            f"45° ⇒ 尖頂高 {D.PCIE_APEX_H:.2f} = 半寬 {D.PCIE_OPEN_W / 2:.2f}"
        )
        cx0 = centers[0]
        bad_apex = []
        for frac in (0.1, 0.3, 0.5, 0.7, 0.9):
            zz = D.PCIE_OPEN_Z1 + frac * D.PCIE_APEX_H
            half = (1.0 - frac) * D.PCIE_OPEN_W / 2
            # 收斂線內側 0.4 應該是空的、外側 0.4 應該有料
            if pt_inside(chassis, cx0 + half - 0.4, y_wall, zz, 0.02):
                bad_apex.append(f"z={zz:.1f} 內側有料")
            if not pt_inside(chassis, cx0 + half + 0.4, y_wall, zz, 0.02):
                bad_apex.append(f"z={zz:.1f} 外側無料")
        (fail if bad_apex else ok)(
            "開孔頂是 45° 尖頂，沒有水平懸空面（逐點量 5 個高度）"
            if not bad_apex else f"尖頂輪廓不對：{bad_apex}"
        )
        (ok if pt_inside(chassis, cx0, y_wall, D.PCIE_APEX_Z + 1.0, 0.02) else fail)(
            f"尖頂頂點 {D.PCIE_APEX_Z:.2f} 之上是繫樑實料（肋的上端固定端）"
        )
        # 舌袋所在的底檻厚度（第九輪挖完只剩 1.10）
        sill_t = D.WALL + D.PCIE_RIB_D - D.PCIE_TANG_POCKET
        (ok if sill_t >= 3.0 else fail)(
            f"擋板舌袋背後剩料 {sill_t:.2f} mm（第九輪 {D.WALL - D.PCIE_TANG_POCKET:.2f}）"
        )
        # 抬升帶不得再被打成連續橫縫（那是第八輪讓肋懸空的原因）
        (ok if pt_inside(chassis, D.CASE_RIGHT - 1.0, y_wall, D.PCIE_Z1 + D.PCIE_LIFT / 2, 0.02)
         else fail)("抬升帶沒有連續橫縫（機殼右緣那段仍是實料）")

        # ★ 第十四輪：支撐地圖。使用者第二次回報「拆支撐把三根細桿扯斷」——
        #   第十三輪的尖頂讓開孔本身不生支撐了，但真正貼著肋的是**別的東西的
        #   支撐塔**：任何位在 PCIe 開孔 x 帶上方的朝下面，都要從床長一根塔
        #   一路擦過那三根肋上來。所以這裡分兩段驗：
        #     ① 窗區內（z ≤ 繫樑頂）一片都不准有 —— FAIL
        #     ② 窗區之上還有哪些 —— WARN 逐條列出（塔高＝那個 z），
        #        它們不是缺陷（鉤唇的底面做不出 45°：往下 4.5 mm 就是頂蓋本體），
        #        但必須被記著，不然下一輪又會變成「不知道哪來的支撐」。
        # 帶界＝**四個開孔的 x 跨距**（三根肋就在裡面），不是窗框跨距：
        # 窗框還往左右各多 PCIE_FRAME_M，那一段的塔擦不到肋。
        cs = D.pcie_centers()
        ox0 = min(cs) - D.PCIE_OPEN_W / 2
        ox1 = max(cs) + D.PCIE_OPEN_W / 2
        oh = support_overhangs(chassis)

        def in_x(bb, x0, x1):
            return bb.XMax > x0 and bb.XMin < x1

        in_band = [
            (a, sl, bb) for a, sl, bb in oh
            if in_x(bb, ox0, ox1) and bb.ZMax > D.FLOOR_T and bb.ZMin < D.PCIE_TIE_Z1
        ]
        (fail if in_band else ok)(
            "PCIe 開孔帶（x %.1f~%.1f、z %.1f~%.1f）沒有需支撐的平面朝下面"
            % (ox0, ox1, D.FLOOR_T, D.PCIE_TIE_Z1)
            if not in_band else
            "PCIe 開孔帶仍有 %d 片需支撐朝下面，共 %.1f mm²：%s"
            % (len(in_band), sum(a for a, _, _ in in_band),
               [f"z={bb.ZMin:.2f}/{a:.0f}mm²" for a, _, bb in in_band])
        )
        fx0, fx1 = D.pcie_frame_x()
        beside = sorted(
            ((a, bb) for a, sl, bb in oh
             if in_x(bb, fx0, fx1) and not in_x(bb, ox0, ox1)
             and bb.ZMax > D.FLOOR_T and bb.ZMin < D.PCIE_TIE_Z1),
            key=lambda r: -r[0],
        )
        for a, bb in beside:
            warn("窗框旁（x %.1f~%.1f，開孔帶外）z=%.2f 有 %.0f mm² 朝下面 → "
                 "塔在肋的左右，不在肋之間"
                 % (bb.XMin, bb.XMax, bb.ZMin, a))
        above = sorted(
            ((a, bb) for a, sl, bb in oh
             if in_x(bb, ox0, ox1) and bb.ZMin >= D.PCIE_TIE_Z1),
            key=lambda r: -r[0],
        )
        for a, bb in above:
            warn("PCIe 帶上方 z=%.2f 有 %.0f mm² 朝下面 → 支撐塔會擦過三根肋 "
                 "（塔高 %.0f mm；已把 TOP_HOOK_D 減到 %.1f，剩下的靠 preset 的 "
                 "support_object_xy_distance 不焊住）"
                 % (bb.ZMin, a, bb.ZMin, D.TOP_HOOK_D))
        z_open_top = D.PCIE_Z1 + D.PCIE_LIFT
        (fail if pt_inside(chassis, centers[0], y_wall, z_open_top - 0.5) else ok)(
            f"opening top = bracket+{D.PCIE_LIFT:.2f} >= engage {D.PCIE_ENGAGE:.2f}"
        )
        for i, cx in enumerate(centers):
            (fail if pt_inside(chassis, cx, y_wall, z_open_mid) else ok)(f"PCIe void {i}")
            tz = (D.PCIE_TANG_Z0 + D.PCIE_Z0) / 2
            y_pocket = D.CASE_REAR + D.WALL - D.PCIE_TANG_POCKET / 2
            y_back = D.CASE_REAR + (D.WALL - D.PCIE_TANG_POCKET) / 2
            if pt_inside(chassis, cx, y_pocket, tz):
                fail(f"PCIe tang pocket {i} still solid")
            elif not pt_inside(chassis, cx, y_back, tz):
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
    # ── 壓條鎖固：繫樑頂面的印製盲內牙 + 沿用 MB_Screw（第十三輪）──────
    for g in (
        "PCIE_HOOK_NECK_W", "PCIE_HOOK_HEAD_W", "PCIE_HOOK_NECK_D",
        "PCIE_HOOK_HEAD_D", "PCIE_BAR_DROP", "PCIE_BAR_FIT",
        "PCIE_RAIL_Z0", "PCIE_RAIL_NECK_H", "PCIE_RAIL_HEAD_H",
        # ★ 第十三輪退役：橫向 Ø2.8 盲 pilot + #6-32 自攻（保持力靠塑膠咬鋼牙，
        #   而且孔軸沿 Y ⇒ 列印時是水平孔，牙谷上半必塌）。
        "PCIE_LOCK_BOSS_W", "PCIE_LOCK_BOSS_H", "PCIE_LOCK_BOSS_D",
        "PCIE_LOCK_PILOT_D", "PCIE_LOCK_PILOT_DEPTH", "PCIE_LOCK_CLEAR_D",
        "PCIE_LOCK_SCREW_LEN", "PCIE_LOCK_SCREW_ENGAGE",
        "PCIE_LOCK_SCREW_HEAD_D", "PCIE_LOCK_SCREW_HEAD_H",
    ):
        if hasattr(D, g):
            fail(f"退役 keyhole／自攻 pilot 參數仍存在：{g}")
    mount_y = D.pcie_bar_mount_y()
    ribs = D.pcie_rib_x()
    (ok if approx(D.PCIE_BAR_SEAT_T, D.PCB_T, 1e-6) else fail)(
        f"壓條鎖點剩厚 {D.PCIE_BAR_SEAT_T:.2f} = PCB_T {D.PCB_T}"
        f"（夾持厚相同 ⇒ 螺絲沿用 MB_Screw，不新增第九種 STL）"
    )
    (ok if D.PCIE_BAR_CBORE_D >= D.MB_SCREW_HEAD_D else fail)(
        f"沉頭凹 Ø{D.PCIE_BAR_CBORE_D:.2f} >= 六角頭外接圓 Ø{D.MB_SCREW_HEAD_D:.2f}"
    )
    (ok if D.PCIE_BAR_T - D.PCIE_BAR_SEAT_T >= D.MB_SCREW_HEAD_H else fail)(
        f"沉頭凹深 {D.PCIE_BAR_T - D.PCIE_BAR_SEAT_T:.2f} >= 頭高 {D.MB_SCREW_HEAD_H}"
        f"（螺絲頭不凸出壓條 ⇒ 後凸比舊版少一個頭高）"
    )
    socket_left = (D.CASE_REAR + D.WALL) - D.pcie_lock_socket_end()
    (ok if socket_left >= 0.8 else fail)(
        f"盲牙盲端到後牆內面剩 {socket_left:.2f} >= 0.80（沒有打穿到內腔）"
    )
    tie_side = (D.PCIE_TIE_H - D.MB_THREAD_MAJOR) / 2
    (ok if tie_side >= 0.8 else fail)(
        f"盲牙在 Z 向的孔壁 {tie_side:.2f} >= 0.80（繫樑高 {D.PCIE_TIE_H}）"
    )
    (ok if D.PCIE_TIE_Z0 < D.PCIE_LOCK_Z < D.PCIE_TIE_Z1 else fail)(
        f"盲牙軸 z={D.PCIE_LOCK_Z:.2f} 落在繫樑 {D.PCIE_TIE_Z0:.2f}…{D.PCIE_TIE_Z1:.2f} 之間"
    )
    (ok if set(D.pcie_lock_x()) == {ribs[0], ribs[-1]} else fail)(
        f"兩個鎖點在最外兩根槽間肋的正上方 {[round(x, 2) for x in D.pcie_lock_x()]}"
        f"（拉力回到肋的上端固定端，硬規則 20）"
    )
    if chassis is not None:
        bad = []
        for i, hx in enumerate(D.pcie_lock_x()):
            placed = B.place_pcie_lock_screw(B.make_mb_screw(), hx)
            v = common_vol(placed, chassis)
            if v > INTERFERE_MAX:
                bad.append(f"{i}:{v:.1f}")
            (ok if pt_inside(chassis, hx, D.pcie_lock_socket_end() + 0.3,
                             D.PCIE_LOCK_Z, 0.02) else fail)(
                f"壓條鎖點 {i} 是盲孔（盲端外仍有料）"
            )
            (fail if pt_inside(chassis, hx, mount_y + 0.3, D.PCIE_LOCK_Z, 0.02) else ok)(
                f"壓條鎖點 {i} 自補強層外表面開通"
            )
        (fail if bad else ok)(
            f"壓條螺絲 {'工作相位撞 Chassis：' + str(bad) if bad else '兩顆皆可旋入'}"
        )
        hx = D.pcie_lock_x()[0]
        turned = B.place_pcie_lock_screw(B.make_mb_screw(), hx)
        turned.rotate(App.Vector(hx, 0, D.PCIE_LOCK_Z), App.Vector(0, 1, 0), 180.0)
        pv = common_vol(turned, chassis)
        (ok if pv > INTERFERE_MAX else fail)(
            f"壓條盲牙是真螺旋：相位轉 180° 撞 {pv:.1f} mm³"
            if pv > INTERFERE_MAX else
            f"壓條盲牙相位轉 180° 只撞 {pv:.2f} mm³——疑似軸對稱假牙"
        )
    if bar is not None:
        for i, hx in enumerate(D.pcie_lock_x()):
            (fail if pt_inside(bar, hx, mount_y - D.PCIE_BAR_SEAT_T / 2,
                               D.PCIE_LOCK_Z, 0.02) else ok)(
                f"壓條鎖點 {i} 通孔貫穿"
            )
            (ok if pt_inside(bar, hx + D.PCIE_BAR_CBORE_D / 2 + 0.8,
                             mount_y - D.PCIE_BAR_T + 0.3, D.PCIE_LOCK_Z, 0.02) else fail)(
                f"壓條鎖點 {i} 沉頭凹外側仍有料"
            )
    if chassis is not None and bar is not None:
        (ok if common_vol(chassis, bar) <= INTERFERE_MAX else fail)(
            f"Chassis/PCIeBar 定位後不重疊 {common_vol(chassis, bar):.2f} mm³"
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

    # ── 碟架承托肩（第十三輪；使用者：側板對應的溝槽太淺）─────────────
    log("--- 碟架承托肩 ---")
    old_area = 4 * D.RACK_BEAM_W * (D.RACK_RAIL_T - D.SLIDE_FIT)
    new_area = 2 * len(D.RACK_BEAM_Y) * D.RACK_BEAM_W * D.RACK_LEDGE_D
    (ok if new_area >= 10 * old_area else fail)(
        f"承重面積 {old_area:.0f} → {new_area:.0f} mm²（×{new_area / old_area:.0f}）"
        f"：從 {D.RACK_RAIL_T - D.SLIDE_FIT:.2f} mm 咬合改成坐在 {D.RACK_LEDGE_D} mm 肩上"
    )
    (ok if approx(D.RACK_LEDGE_Z1, D.RACK_RAIL_Z0 - D.SLIDE_FIT, 1e-6) else fail)(
        f"肩頂 {D.RACK_LEDGE_Z1:.2f} = 橫樑底 {D.RACK_RAIL_Z0:.2f} − 滑配"
        f"（滑入不磨、載重落 {D.SLIDE_FIT} 就坐實；硬規則 19）"
    )
    (ok if approx(D.RACK_LEDGE_GUSSET, D.RACK_LEDGE_D + D.CHASSIS_OVERLAP, 1e-6) else fail)(
        f"斜撐 45°：高 {D.RACK_LEDGE_GUSSET:.2f} = 伸出 {D.RACK_LEDGE_D} + 埋入 "
        f"{D.CHASSIS_OVERLAP}（自根部量起才是 45°，Chassis 地板貼床時自撐）"
    )
    ledge_bottom = D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET
    (ok if ledge_bottom > max(D.AREA_A_TOP_Z, D.AREA_B_TOP_Z, D.AREA_C_TOP_Z) else fail)(
        f"肩底 {ledge_bottom:.2f} 高過三個規格淨空頂（A {D.AREA_A_TOP_Z:.2f}／"
        f"B {D.AREA_B_TOP_Z:.2f}／C {D.AREA_C_TOP_Z:.2f}）"
    )
    (ok if D.RACK_LEDGE_Y0 > D.ATX_Y1 else fail)(
        f"Chassis 段的肩自 y={D.RACK_LEDGE_Y0:.2f} 起，讓開電源前緣 {D.ATX_Y1:.2f}"
    )
    (ok if D.RACK_LEDGE_Y1 <= D.SHROUD_Y0 - D.SHROUD_LAP + 1e-9 else fail)(
        f"Chassis 段的肩止於 {D.RACK_LEDGE_Y1:.2f}，讓開前罩搭接帶（內壁要進來）"
    )
    (ok if D.SHROUD_LEDGE_Y0 >= D.SHROUD_Y0 else fail)(
        f"前罩段的肩自 {D.SHROUD_LEDGE_Y0:.2f} 起（Chassis 牆前端面 {D.SHROUD_Y0:.2f} 之外）"
    )
    cantilever = D.HDD_Y1 - max(D.RACK_BEAM_Y)
    (ok if cantilever < 0.5 * (D.HDD_Y1 - D.BAY_SPLIT_Y) else fail)(
        f"碟架前段懸臂 {D.HDD_Y1 - D.BAY_SPLIT_Y:.2f} → {cantilever:.2f} mm"
        f"（第三根樑坐在前罩承托肩上）"
    )
    (ok if len(D.RACK_RAIL_BEAM_Y) == len(D.RACK_BEAM_Y) - 1 else fail)(
        f"側舌只長在 Chassis 槽 y 帶內的 {len(D.RACK_RAIL_BEAM_Y)} 根樑上"
        f"（第三根在前罩段，那裡沒有牆槽）"
    )
    if chassis is not None:
        ym = (D.RACK_LEDGE_Y0 + D.RACK_LEDGE_Y1) / 2
        for tag, xs in (
            ("左", D.CASE_LEFT + D.WALL + D.RACK_LEDGE_D / 2),
            ("右", D.CASE_RIGHT - D.WALL - D.RACK_LEDGE_D / 2),
        ):
            (ok if pt_inside(chassis, xs, ym, D.RACK_LEDGE_Z1 - 0.5, 0.02) else fail)(
                f"Chassis {tag}肩實心（x={xs:.2f}, z={D.RACK_LEDGE_Z1 - 0.5:.2f}）"
            )
            (fail if pt_inside(chassis, xs, ym, D.RACK_LEDGE_Z1 + 0.15, 0.02) else ok)(
                f"Chassis {tag}肩頂面之上是空的（橫樑坐得下去）"
            )
    if shroud is not None:
        ym = (D.SHROUD_LEDGE_Y0 + D.SHROUD_LEDGE_Y1) / 2
        for tag, xs in (
            ("左", D.CASE_LEFT + D.SHROUD_WALL + D.SHROUD_LEDGE_D / 2),
            ("右", D.CASE_RIGHT - D.SHROUD_WALL - D.SHROUD_LEDGE_D / 2),
        ):
            (ok if pt_inside(shroud, xs, ym, D.RACK_LEDGE_Z1 - 0.5, 0.02) else fail)(
                f"前罩 {tag}肩實心（碟架第三根樑坐在它上面）"
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
    if chassis is not None:
        # 地板不得再開電源進氣柵：電源已經不在底下了（多餘孔洞）
        solid = all(
            pt_inside(chassis, x, y, D.FLOOR_T / 2, 0.02)
            for x, y in ((-138.0, 40.0), (-138.0, 100.0), (-60.0, 70.0))
        )
        (ok if solid else fail)("底板無進氣柵（電源已上置；地板是密封的）")
    for name, sh, x, y in (
        ("Chassis 左牆", chassis, D.CASE_LEFT + D.WALL / 2, 60.0),
        ("Chassis 右牆", chassis, D.CASE_RIGHT - D.WALL / 2, 60.0),
    ):
        if sh is None:
            continue
        solid = all(pt_inside(sh, x, y, z, 0.02) for z in (40.0, 120.0, 170.0))
        (ok if solid else fail)(f"{name} 無通風開孔（氣流只有一條：前柵→碟→內腔→電源）")

    # ── 一體式 Chassis／可拆件接合 ───────────────────────────────────
    log("--- 一體式 Chassis／可拆件接合 ---")
    retired = (
        "FLOOR_LIP", "FLOOR_LIP_T", "FLOOR_LEDGE_T", "FLOOR_DETENT_R",
        "FLOOR_DETENT_DEPTH", "FLOOR_REAR_DETENT_R", "REAR_TAB_D",
        "REAR_TAB_T", "REAR_WEDGE_H", "REAR_DETENT_Z", "PCIE_BAR_DROP",
        "PCIE_HOOK_NECK_W", "PCIE_HOOK_HEAD_W", "MB_NUT_OD", "MB_STUD_MAJOR",
    )
    stale = [name for name in retired if hasattr(D, name)]
    (fail if stale else ok)(
        f"{'退役接合參數仍存在：' + ', '.join(stale) if stale else '四件 Chassis 舊滑槽／舌／楔／keyhole 參數已刪除'}"
    )
    if chassis is not None:
        o = D.CHASSIS_OVERLAP
        roots = (
            ("地板／左牆", D.FLOOR_X0 - o / 2, 80.0, D.FLOOR_T / 2),
            ("地板／右牆", D.FLOOR_X1 + o / 2, 80.0, D.FLOOR_T / 2),
            ("地板／後牆", 0.0, D.FLOOR_Y0 - o / 2, D.FLOOR_T / 2),
            ("左牆／後牆", D.CASE_LEFT + D.WALL / 2,
             D.CASE_REAR + D.WALL - o / 2, 90.0),
            ("右牆／後牆", D.CASE_RIGHT - D.WALL / 2,
             D.CASE_REAR + D.WALL - o / 2, 90.0),
        )
        for tag, x, y, z in roots:
            (ok if pt_inside(chassis, x, y, z, 0.02) else fail)(
                f"Chassis {tag} 根部有 {o:.2f} mm 體積重疊"
            )
        bb = obb(chassis)
        want_y = D.BAY_SPLIT_Y - (D.CASE_REAR - D.PCIE_RIB_D)
        (ok if approx(bb.XLength, D.CASE_W, 0.05)
         and approx(bb.YLength, want_y, 0.05)
         and approx(bb.ZLength, D.OUTER_TOP_Z, 0.05) else fail)(
            f"Chassis 實際 OBB {bb.XLength:.2f}×{bb.YLength:.2f}×{bb.ZLength:.2f} mm"
            f" = {D.CASE_W:.2f}×{want_y:.2f}×{D.OUTER_TOP_Z:.2f}"
        )
        (ok if max(bb.XLength, bb.YLength, bb.ZLength) <= D.A1_MAX else fail)(
            f"Chassis 裸件可放入 A1：最大邊 {max(bb.XLength, bb.YLength, bb.ZLength):.2f} <= {D.A1_MAX:.0f}"
        )

    # Rack 最底層承托格柵：三橫樑的兩端與中央、中央縱樑的全長都必須有料。
    log("--- HDD Rack 底部承托格柵 ---")
    (ok if len(D.RACK_BASE_BEAM_Y) == 3 else fail)(
        f"Rack 底部橫樑 {len(D.RACK_BASE_BEAM_Y)}/3"
    )
    (ok if approx(D.RACK_BASE_Z1, D.HDD_Z0 - D.SLIDE_FIT, 1e-9) else fail)(
        f"格柵頂 {D.RACK_BASE_Z1:.2f} = lv0 托盤底 {D.HDD_Z0:.2f} − 滑配 {D.SLIDE_FIT:.2f}"
    )
    (ok if D.RACK_BASE_Z1 - D.RACK_Z0 >= 0.8 else fail)(
        f"格柵厚 {D.RACK_BASE_Z1 - D.RACK_Z0:.2f} >= 0.8 mm"
    )
    if rack is not None:
        zc = (D.RACK_Z0 + D.RACK_BASE_Z1) / 2
        for i, by in enumerate(D.RACK_BASE_BEAM_Y):
            for tag, x in (
                ("左根", D.RACK_X0 + 0.5),
                ("中央", D.RACK_BASE_SPINE_X),
                ("右根", D.RACK_POST_X1 - 0.5),
            ):
                (ok if pt_inside(rack, x, by, zc, 0.02) else fail)(
                    f"格柵橫樑 {i} {tag}實心"
                )
        for i, y in enumerate((D.TRAY_Y0 + 0.5,
                               (D.TRAY_Y0 + D.HDD_Y1) / 2,
                               D.HDD_Y1 - 0.5)):
            (ok if pt_inside(rack, D.RACK_BASE_SPINE_X, y, zc, 0.02) else fail)(
                f"中央縱樑取樣 {i} 實心"
            )
        gap_z = D.RACK_BASE_Z1 + D.SLIDE_FIT / 2
        (fail if pt_inside(rack, D.RACK_BASE_SPINE_X,
                           D.RACK_BASE_BEAM_Y[1], gap_z, 0.02) else ok)(
            f"格柵與 lv0 托盤之間 {D.SLIDE_FIT:.2f} mm 間隙開通"
        )
        t0 = B.make_hdd_tray_placed(0)
        (ok if common_vol(rack, t0) <= INTERFERE_MAX else fail)(
            f"格柵／lv0 托盤不干涉 {common_vol(rack, t0):.2f} mm³"
        )

    # Top：側舌咬合、後鉤、兩顆只在最後短行程作用的可拆 detent。
    log("--- Top 側槽／後鉤／detent ---")
    (ok if D.TOP_LIP >= 1.0 else fail)(f"Top 側舌咬合 {D.TOP_LIP:.2f} >= 1.0 mm")
    (ok if D.WALL - (D.TOP_LIP + D.SLIDE_FIT) >= D.GROOVE_BACK_MIN - 1e-9 else fail)(
        f"Top 槽背剩料 {D.WALL - D.TOP_LIP - D.SLIDE_FIT:.2f} >= {D.GROOVE_BACK_MIN:.2f} mm"
    )
    (ok if len(B.top_detents()) == len(D.TOP_DETENT_X) == 2 else fail)(
        f"Top detent {len(B.top_detents())}/2"
    )
    (ok if D.TOP_DETENT_R >= 0.5 and 0 < D.TOP_DETENT_DEPTH < D.TOP_DETENT_R else fail)(
        f"Top detent R={D.TOP_DETENT_R:.2f}、凸出={D.TOP_DETENT_DEPTH:.2f} 可印且可 cam-out"
    )
    if chassis is not None and top is not None:
        ym = (D.FLOOR_Y0 + D.BAY_SPLIT_Y) / 2
        (ok if pt_inside(top, D.FLOOR_X0 - D.TOP_LIP / 2, ym,
                         D.INNER_TOP_Z - D.TOP_T / 2, 0.02) else fail)(
            "Top 左側舌實心"
        )
        (fail if pt_inside(chassis, D.FLOOR_X0 - D.TOP_LIP / 2, ym,
                           D.INNER_TOP_Z - D.TOP_T / 2, 0.02) else ok)(
            "Chassis 左側 Top 槽開通"
        )
        for i, det in enumerate(B.top_detents()):
            vc, vt = common_vol(chassis, det), common_vol(top, det)
            (ok if vc > 0.05 else fail)(f"Top detent {i} 公球與 Chassis 融合 {vc:.2f} mm³")
            (ok if vt <= 0.05 else fail)(f"Top detent {i} 母坑已從 Top 切開 {vt:.2f} mm³")
        y_hook = D.FLOOR_Y0 + D.TOP_HOOK_D / 2
        (ok if pt_inside(chassis, 0.0, y_hook,
                         D.OUTER_TOP_Z - D.TOP_HOOK_T / 2, 0.02) else fail)(
            "Chassis 後鉤唇實心"
        )
        (ok if approx(D.RACK_TOP_GAP, D.SLIDE_FIT, 1e-9) else fail)(
            f"Rack 頂板到 Top 留 {D.RACK_TOP_GAP:.2f} mm"
        )
        # ★ 第十三輪：後牆的頂蓋槽（使用者：後牆好像沒有專門插頂蓋的卡槽）。
        #   第十二輪後方只有鉤唇，它擋的是 +Z；−Y 那一格靠 detent 的摩擦。
        (ok if approx(D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT), D.GROOVE_BACK_MIN, 1e-6)
         else fail)(
            f"後牆頂蓋槽深 {D.TOP_REAR_LIP + D.SLIDE_FIT:.2f}，槽背留 "
            f"{D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT):.2f} = GROOVE_BACK_MIN"
        )
        y_slot = D.CASE_REAR + D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT) / 2
        y_tab = D.FLOOR_Y0 + D.TOP_FIT_GAP - D.TOP_REAR_LIP / 2
        z_slot = D.INNER_TOP_Z - D.TOP_T / 2
        bands = D.top_rear_tab_bands()
        for i, (bx0, bx1) in enumerate(bands):
            xm = (bx0 + bx1) / 2
            (fail if pt_inside(chassis, xm, y_slot, z_slot, 0.02) else ok)(
                f"後牆頂蓋槽 {i} 開通（x={xm:.2f}）"
            )
            y_back = (D.CASE_REAR + D.WALL
                      - (D.TOP_REAR_LIP + D.SLIDE_FIT) - D.GROOVE_BACK_MIN / 2)
            (ok if pt_inside(chassis, xm, y_back, z_slot, 0.02) else fail)(
                f"後牆頂蓋槽 {i} 的槽背仍有料（y={y_back:.2f}）"
            )
            (ok if pt_inside(top, xm, y_tab, z_slot, 0.02) else fail)(
                f"Top 後舌 {i} 實心（沿 −Y 插進槽裡，槽底面即止擋）"
            )
        # 後舌是整條路徑掃過去的：兩段都必須完全避開電源與碟架頂板的 x 帶
        swept = []
        for bx0, bx1 in bands:
            if bx0 < D.ATX_X1 and bx1 > D.ATX_X0:
                swept.append("電源")
            if bx0 < D.RACK_POST_X1 and bx1 > D.RACK_X0:
                swept.append("碟架頂板")
        (fail if swept else ok)(
            "後舌兩段讓開電源與碟架頂板（硬規則 22：掃的是路徑不是最終位置）"
            if not swept else f"後舌會在滑入途中刮過 {set(swept)}"
        )

    # Front：14 mm 四面搭接、10 顆 detent、四個 45° 導入面。
    log("--- Front 搭接／導入／detent ---")
    (ok if approx(D.SHROUD_LAP, 14.0, 1e-9) else fail)(
        f"Front 搭接深 {D.SHROUD_LAP:.2f} = 14.00 mm"
    )
    (ok if approx(D.SHROUD_LEAD_IN, 1.0, 1e-9) else fail)(
        f"Front 四邊導入長 {D.SHROUD_LEAD_IN:.2f} = 1.00 mm"
    )
    front_detents = (
        B.shroud_detents(True) + B.shroud_detents(False)
        + B.shroud_lap_detents(True) + B.shroud_lap_detents(False)
    )
    (ok if len(front_detents) == 10 else fail)(f"Front detent {len(front_detents)}/10")
    if shroud is not None and chassis is not None and top is not None:
        y0, lead = D.SHROUD_Y0 - D.SHROUD_LAP, D.SHROUD_LEAD_IN
        probes = (
            ("左", D.CASE_LEFT + D.SHROUD_LAP_T - 0.25, y0 + 0.25, 90.0,
             D.CASE_LEFT + D.SHROUD_LAP_T - 0.25, y0 + 0.90, 90.0),
            ("右", D.CASE_RIGHT - D.SHROUD_LAP_T + 0.25, y0 + 0.25, 90.0,
             D.CASE_RIGHT - D.SHROUD_LAP_T + 0.25, y0 + 0.90, 90.0),
            ("頂", 0.0, y0 + 0.25, D.OUTER_TOP_Z - D.SHROUD_TOP_LAP_T + 0.25,
             0.0, y0 + 0.90, D.OUTER_TOP_Z - D.SHROUD_TOP_LAP_T + 0.25),
            ("底", 0.0, y0 + 0.25,
             D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT + 0.25,
             0.0, y0 + 0.90,
             D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT + 0.25),
        )
        for tag, xe, ye, ze, xs, ys, zs in probes:
            empty = not pt_inside(shroud, xe, ye, ze, 0.02)
            solid = pt_inside(shroud, xs, ys, zs, 0.02)
            (ok if empty and solid else fail)(
                f"Front {tag}緣 45° 導入面：前端切空、{lead:.1f} mm 後恢復實料"
            )
        for i, det in enumerate(B.shroud_detents(True) + B.shroud_detents(False)
                                + B.shroud_lap_detents(False)):
            (ok if common_vol(chassis, det) > 0.05 else fail)(
                f"Front 公 detent {i} 與 Chassis 融合"
            )
            (ok if common_vol(shroud, det) <= 0.05 else fail)(
                f"Front detent {i} 母坑已切開"
            )
        for i, det in enumerate(B.shroud_lap_detents(True)):
            (ok if common_vol(top, det) > 0.05 else fail)(
                f"Front 頂 detent {i} 與 Top 融合"
            )
            (ok if common_vol(shroud, det) <= 0.05 else fail)(
                f"Front 頂 detent {i} 母坑已切開"
            )
        for bx0, bx1 in B.shroud_floor_stud_bands():
            x = (bx0 + bx1) / 2
            y = D.BAY_SPLIT_Y - D.SHROUD_LAP / 2
            (ok if pt_inside(chassis, x, y, D.FLOOR_T - 0.3, 0.02) else fail)(
                f"Chassis x={x:.2f} 保留整厚主板柱腳"
            )
            (fail if pt_inside(shroud, x, y, D.FLOOR_T - 0.3, 0.02) else ok)(
                f"Front x={x:.2f} 對應讓位槽開通"
            )
        # ★ 第十三輪：搭接帶改 U 形雙壁夾持（使用者：改成有縫隙插進去、兩邊夾住）。
        #   第十二輪只有外壁貼在牆的外面減薄帶上，牆的內面整片是光的。
        y_lap = D.SHROUD_Y0 - D.SHROUD_LAP / 2
        z_lap = (D.SHROUD_INNER_Z0 + D.SHROUD_INNER_Z1) / 2
        for tag, xw, inward in (
            ("左", D.CASE_LEFT + D.WALL, 1),
            ("右", D.CASE_RIGHT - D.WALL, -1),
        ):
            x_out = xw - inward * (D.WALL - D.SHROUD_LAP_T / 2)  # 外壁中面
            x_in = xw + inward * (D.SLIDE_FIT + D.SHROUD_INNER_T / 2)  # 內壁中面
            (ok if pt_inside(shroud, x_out, y_lap, z_lap, 0.02) else fail)(
                f"Front {tag}搭接**外**壁實心（x={x_out:.2f}）"
            )
            (ok if pt_inside(shroud, x_in, y_lap, z_lap, 0.02) else fail)(
                f"Front {tag}搭接**內**壁實心（x={x_in:.2f}）—— 牆被兩片夾住，不是單邊靠著"
            )
            # 夾持縫的寬度就是牆厚 + 兩個滑配
            # 牆在搭接帶被外面減薄了 SHROUD_LAP_T + SLIDE_FIT，探剩料的中間
            x_wall = xw - inward * (D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT) / 2
            (ok if pt_inside(chassis, x_wall, y_lap, z_lap, 0.02) else fail)(
                f"Chassis {tag}牆仍整片落在 Front 的 U 形縫裡（x={x_wall:.2f}）"
            )
        (ok if approx(D.SHROUD_INNER_Z0, D.AREA_B_TOP_Z + D.SLIDE_FIT, 1e-6) else fail)(
            f"內壁下限 {D.SHROUD_INNER_Z0:.2f} = Area B 淨空頂 + 滑配"
            f"（右牆內面到主板右緣只有 {D.CASE_RIGHT - D.WALL - D.BOARD_RIGHT:.2f}）"
        )
        (ok if approx(D.SHROUD_INNER_Z1,
                      D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET - D.SLIDE_FIT, 1e-6)
         else fail)(
            f"內壁上限 {D.SHROUD_INNER_Z1:.2f} 讓開碟架承托肩的斜撐底 "
            f"{D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET:.2f}"
        )
        # 內壁若沒接回主體壁就是兩片自由飄浮的板（實測 Front_Shroud solids=3）
        x_join = D.CASE_LEFT + (D.SHROUD_WALL + D.WALL + D.SLIDE_FIT + D.SHROUD_INNER_T) / 2
        (ok if pt_inside(shroud, x_join, D.SHROUD_Y0 + D.SHROUD_INNER_JOIN / 2, z_lap, 0.02)
         else fail)(f"Front 左內壁與主體壁之間的接合塊實心（x={x_join:.2f}）")

    # 配合面不得共面：取樣每一道刻意的 SLIDE_FIT 空隙。
    log("--- 配合間隙 ---")
    gap_probes = (
        ("Top 左舌尖／槽底", D.FLOOR_X0 - D.TOP_LIP - D.SLIDE_FIT / 2,
         80.0, D.INNER_TOP_Z - D.TOP_T / 2),
        ("Top 左舌／槽頂", D.FLOOR_X0 - D.TOP_LIP / 2,
         80.0, D.INNER_TOP_Z + D.SLIDE_FIT / 2),
        ("Rack／lv0 托盤", D.RACK_BASE_SPINE_X,
         D.RACK_BASE_BEAM_Y[1], D.RACK_BASE_Z1 + D.SLIDE_FIT / 2),
        ("Rack 頂板／Top", D.RACK_BASE_SPINE_X,
         D.BAY_SPLIT_Y - 20.0, D.RACK_TOP_Z1 + D.RACK_TOP_GAP / 2),
        ("Top 後肩／鉤唇", 0.0, D.FLOOR_Y0 + D.TOP_HOOK_D / 2,
         D.OUTER_TOP_Z - D.TOP_HOOK_T - D.SLIDE_FIT / 2),
    )
    for tag, x, y, z in gap_probes:
        who = occupant(x, y, z)
        (fail if who else ok)(
            f"{tag} 的 {D.SLIDE_FIT:.2f} mm 間隙開通"
            + (f"（被 {who} 佔住）" if who else "")
        )

    # ── 保持力真相表：Chassis 是固定障礙物，不是待保持的可動件 ───────
    log("--- 保持力真相表（六向約束）---")
    HOLD_RELEASE = {
        "HDD_Rack": None,
        "Top_MB": None,
        "Front_Shroud": "+Y",
        "HDD_Tray": "+Y",
    }
    if set(HOLD_RELEASE) != set(D.STRUCT_PART_KEYS):
        raise SystemExit(
            f"保持力真相表與 STRUCT_PART_KEYS 不一致："
            f"missing={sorted(set(D.STRUCT_PART_KEYS) - set(HOLD_RELEASE))} "
            f"extra={sorted(set(HOLD_RELEASE) - set(D.STRUCT_PART_KEYS))}"
        )
    hold_shapes = {k: shapes[k] for k in HOLD_RELEASE}
    fixed_hold = {"Chassis_Body": chassis, **hold_shapes}

    def without_elastic_detents(moving, key, shape):
        out = shape
        cutters = []
        if moving == "Top_MB" and key == "Chassis_Body":
            cutters = B.top_detents(0.05)
        elif moving == "Front_Shroud" and key == "Chassis_Body":
            cutters = (B.shroud_detents(True, 0.05) + B.shroud_detents(False, 0.05)
                       + B.shroud_lap_detents(False, 0.05))
        elif moving == "Front_Shroud" and key == "Top_MB":
            cutters = B.shroud_lap_detents(True, 0.05)
        for cutter in cutters:
            out = out.cut(cutter)
        return out

    def hold_hit(name, vec, delta):
        moving = hold_shapes[name].copy()
        moving.translate(App.Vector(*(v * delta for v in vec)))
        worst, worst_v = None, 0.0
        for key, obstacle in fixed_hold.items():
            if key == name or obstacle is None:
                continue
            obstacle = without_elastic_detents(name, key, obstacle)
            value = common_vol(moving, obstacle)
            if value > worst_v:
                worst, worst_v = key, value
        return worst, worst_v

    for name in sorted(hold_shapes):
        release = HOLD_RELEASE[name]
        for tag, vec in (("+X", (1, 0, 0)), ("-X", (-1, 0, 0)),
                         ("+Y", (0, 1, 0)), ("-Y", (0, -1, 0)),
                         ("+Z", (0, 0, 1)), ("-Z", (0, 0, -1))):
            who, value = hold_hit(name, vec, 0.75)
            if tag == release:
                _, far_value = hold_hit(name, vec, 6.0)
                (ok if value <= INTERFERE_MAX and far_value <= INTERFERE_MAX else fail)(
                    f"{name} {tag} 是宣告的釋放方向，至少 6.0 mm 淨空"
                )
            else:
                (ok if value > INTERFERE_MAX else fail)(
                    f"{name} {tag} 被 {who} 鎖住（play <= 0.75 mm）"
                    if value > INTERFERE_MAX else
                    f"{name} {tag} 可自由走 0.75 mm，缺少幾何保持力"
                )

    log("--- interference ---")
    exempt = set()
    keys = [k for k in D.STL_NAMES if k in shapes]
    for a, b in itertools.combinations(keys, 2):
        if frozenset((a, b)) in exempt:
            continue
        value = common_vol(shapes[a], shapes[b])
        (fail if value < 0 or value > INTERFERE_MAX else ok)(
            f"{'interfere' if value < 0 or value > INTERFERE_MAX else 'no interfere'} {a}/{b} {value:.2f}"
        )

    # ── 虛擬硬體與規格淨空 ───────────────────────────────────────────
    log("--- fit (虛擬件 / 規格淨空) ---")
    mocks = hardware_mocks()
    for mock_name in sorted(mocks):
        worst_name, worst_v = None, 0.0
        for part_name, shape in shapes.items():
            value = common_vol(mocks[mock_name], shape)
            if value < 0:
                worst_name, worst_v = part_name, float("inf")
                break
            if value > worst_v:
                worst_name, worst_v = part_name, value
        (fail if worst_v > INTERFERE_MAX else ok)(
            f"{mock_name} "
            + (f"hits {worst_name} {worst_v:.1f} mm3" if worst_v > INTERFERE_MAX else "clear")
        )

    for level in range(D.HDD_LEVELS):
        placed = B.make_hdd_tray_placed(level)
        bad = []
        for other_level in range(D.HDD_LEVELS):
            for tag in (f"HDD_L{other_level}", f"HDD_L{other_level}_接頭"):
                value = common_vol(mocks[tag], placed)
                if value > INTERFERE_MAX:
                    bad.append(f"{tag} {value:.1f}")
        for part_name in ("HDD_Rack", "Front_Shroud", "Top_MB", "Chassis_Body"):
            value = common_vol(shapes[part_name], placed)
            if value > INTERFERE_MAX:
                bad.append(f"{part_name} {value:.1f}")
        (fail if bad else ok)(
            f"碟托盤 lv{level} " + ("撞：" + "; ".join(bad) if bad else "與硬體／機殼不干涉")
        )
        if level + 1 < D.HDD_LEVELS:
            zg = D.tray_z0(level) + D.TRAY_T + D.HDD_H + D.TRAY_AIR_GAP / 2
            slab = mk_box(D.HDD_X0 + 5, D.HDD_Y0 + 5, zg - 0.2,
                          D.HDD_X1 - 5, D.HDD_Y1 - 5, zg + 0.2)
            candidates = [(common_vol(slab, shape), name) for name, shape in shapes.items()]
            candidates.extend(
                (common_vol(slab, B.make_hdd_tray_placed(k)), f"tray{k}")
                for k in range(D.HDD_LEVELS)
            )
            worst = max(candidates)
            (fail if worst[0] > INTERFERE_MAX else ok)(
                f"lv{level} 碟頂上方 {D.TRAY_AIR_GAP:.2f} mm 氣隙淨空"
                + (f"：{worst[1]} {worst[0]:.1f}" if worst[0] > INTERFERE_MAX else "")
            )

    # ── 裝配動作：依 ASSEMBLY_STEPS，場上只保留已安裝件 ───────────────
    log("--- 裝配動作 ---")

    def sweep(shape, dx=0.0, dy=0.0, dz=0.0, steps=None):
        box_ = shape.BoundBox
        span = max(abs(dx), abs(dy), abs(dz))
        step = max(min(box_.XLength, box_.YLength, box_.ZLength) * 0.9, 1.0)
        count = steps or max(1, int(math.ceil(span / step)))
        swept = shape
        for i in range(1, count + 1):
            moved = shape.copy()
            moved.translate(App.Vector(dx * i / count, dy * i / count, dz * i / count))
            swept = swept.fuse(moved)
        return swept

    def hit_shapes(swept, obstacles, skip=()):
        worst_name, worst_v = None, 0.0
        for name, shape in obstacles.items():
            if name in skip or shape is None:
                continue
            value = common_vol(swept, shape)
            if value > worst_v:
                worst_name, worst_v = name, value
        return worst_name, worst_v

    installed = {}
    for step_index, (key, dy) in enumerate(D.ASSEMBLY_STEPS):
        shape = shapes[key]
        if abs(dy) < 1e-9:
            installed[key] = shape
            ok(f"組裝 {step_index + 1}. {key}：固定基準件")
            continue
        start = shape.copy()
        start.translate(App.Vector(0, -dy, 0))
        swept = sweep(start, dy=dy, steps=50 if abs(dy) > 60 else None)
        obstacles = {
            name: without_elastic_detents(key, name, obstacle)
            for name, obstacle in installed.items()
        }
        who, value = hit_shapes(swept, obstacles)
        (fail if value > INTERFERE_MAX else ok)(
            f"組裝 {step_index + 1}. {key} 沿 Y {dy:+.1f} mm "
            + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
        )
        installed[key] = shape
    log("（主板／PSU／PCIe 卡在 Chassis 就位後、Rack 滑入前安裝。）")

    # PCIe：Bar 在位時擋四槽；卸兩螺絲後 Bar 直接沿 −Y 抽出，卡再抬升。
    if bar is not None:
        held = sum(
            common_vol(sweep(mocks[f"PCIe{i}_耳keepout"], dz=D.PCIE_ENGAGE), bar)
            > INTERFERE_MAX
            for i in range(D.PCIE_COUNT)
        )
        (ok if held == D.PCIE_COUNT else fail)(f"PCIeBar 擋住 {held}/{D.PCIE_COUNT} 槽抬升")
        lock_screws = [B.place_pcie_lock_screw(B.make_mb_screw(), hx)
                       for hx in D.pcie_lock_x()]
        screw_hold = [common_vol(sweep(bar, dy=-1.0), screw) for screw in lock_screws]
        (ok if all(value > INTERFERE_MAX for value in screw_hold) else fail)(
            f"兩顆鎖固螺絲在位時擋住 Bar 外抽 {[round(v, 1) for v in screw_hold]} mm³"
        )
        obstacles = {name: shape for name, shape in shapes.items() if name != "PCIeBar"}
        who, value = hit_shapes(sweep(bar, dy=-(D.PCIE_BAR_T + D.PCIE_RIB_D + 10.0)), obstacles)
        (fail if value > INTERFERE_MAX else ok)(
            "卸兩螺絲後 PCIeBar 沿 −Y 抽出 "
            + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
        )
    for i in range(D.PCIE_COUNT):
        blocked = []
        for tag in (f"PCIe{i}_bracket", f"PCIe{i}_card", f"PCIe{i}_耳keepout"):
            obstacles = {name: shape for name, shape in shapes.items() if name != "PCIeBar"}
            who, value = hit_shapes(sweep(mocks[tag], dz=D.PCIE_ENGAGE), obstacles)
            if value > INTERFERE_MAX:
                blocked.append(f"{tag}→{who} {value:.1f}")
        (fail if blocked else ok)(
            f"PCIe{i} " + ("抬升受阻：" + "; ".join(blocked) if blocked else "拆 Bar 後垂直抬升淨空")
        )

    # 主板沒有 PCB 上方凸柱；螺絲最後才鎖，PCB 可直接由上方落到 Ø8 支撐肩。
    pcb_obstacles = {"Chassis_Body": chassis}
    who, value = hit_shapes(sweep(mocks["主板PCB"], dz=D.AREA_A_CLEARANCE), pcb_obstacles)
    (fail if value > INTERFERE_MAX else ok)(
        "主板由上方垂直落到支撐肩 "
        + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
    )

    # Rack 在硬體之後滑入；除已裝 Chassis 外，另逐件檢查 PSU／PCB／PCIe 卡包絡。
    if rack is not None:
        slide = D.CASE_FRONT - D.HDD_Y0
        for tag in ("主板PCB", "PSU_150x86x140", "PCIe0_card", "PCIe3_card"):
            value = common_vol(sweep(rack, dy=slide), mocks[tag])
            (fail if value > INTERFERE_MAX else ok)(
                f"Rack 滑入路徑 vs {tag} = {value:.1f} mm³"
            )

    # Top 在 Front 拆下後仍可沿 +Y cam-out；公 detent 先自 Chassis 障礙物扣除。
    if top is not None:
        obstacles = {
            "Chassis_Body": without_elastic_detents("Top_MB", "Chassis_Body", chassis),
            "HDD_Rack": rack,
        }
        who, value = hit_shapes(sweep(top, dy=D.CASE_FRONT - D.FLOOR_Y0), obstacles)
        (fail if value > INTERFERE_MAX else ok)(
            "拆 Front 後 Top 沿 +Y 抽出 "
            + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
        )

    # 四層 HDD／托盤均可自 +Y 熱抽換。
    pull = D.HDD_W + D.TRAY_FRONT_GAP + 10.0
    for level in range(D.HDD_LEVELS):
        obstacles = {name: shape for name, shape in shapes.items() if name != "HDD_Tray"}
        who, value = hit_shapes(sweep(mocks[f"HDD_L{level}"], dy=pull), obstacles)
        (fail if value > INTERFERE_MAX else ok)(
            f"HDD lv{level} 自 +Y 抽出 {pull:.1f} mm "
            + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
        )

    # Front 自 +Y 套上；忽略刻意的彈性 detent，但保留所有剛性搭接與主板柱腳。
    if shroud is not None:
        obstacles = {
            "Chassis_Body": without_elastic_detents("Front_Shroud", "Chassis_Body", chassis),
            "Top_MB": without_elastic_detents("Front_Shroud", "Top_MB", top),
            "HDD_Rack": rack,
        }
        who, value = hit_shapes(
            sweep(shroud, dy=D.SHROUD_LAP + D.SHROUD_D + 20.0), obstacles
        )
        (fail if value > INTERFERE_MAX else ok)(
            "Front 自 +Y 套上 "
            + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
        )

    # PSU 在 Rack／Top 前由上方落入；只把一體 Chassis 當障礙物。
    psu = mocks["PSU_150x86x140"]
    shifted = psu.copy()
    shifted.translate(App.Vector(D.PSU_SLIDE_X, D.PSU_SLIDE_Y, 0))
    who, value = hit_shapes(
        sweep(shifted, dz=D.OUTER_TOP_Z - D.ATX_Z0),
        {"Chassis_Body": chassis},
    )
    (fail if value > INTERFERE_MAX else ok)(
        "PSU 自上方落入 "
        + (f"撞 {who} {value:.1f} mm³" if value > INTERFERE_MAX else "路徑淨空")
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
    actual_stl = {
        fn for fn in os.listdir(STL_DIR)
        if fn.lower().endswith(".stl")
    }
    expected_stl = set(D.STL_NAMES.values())
    (ok if actual_stl == expected_stl else fail)(
        "STL 目錄與 manifest 完全一致"
        if actual_stl == expected_stl else
        f"STL/manifest 不一致 missing={sorted(expected_stl - actual_stl)} "
        f"extra={sorted(actual_stl - expected_stl)}"
    )
    for fn in D.REMOVED_STL:
        path = os.path.join(STL_DIR, fn)
        (fail if os.path.isfile(path) else ok)(
            f"{'stale STL still exists: ' if os.path.isfile(path) else 'no stale STL '}{fn}"
        )

    w, d, h = D.envelope_mm()
    # 一件一份與含份數都要報；後者才是購料基準。
    # 第十二輪額外份數為 Tray ×4、Blank ×4、MB_Screw ×9。
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
    # 安裝深度必須把 Chassis、Bar 與兩顆標準 #6-32 pan-head 的真幾何串起來量。
    if bar is not None and chassis is not None:
        y_min = min(
            [obb(bar).YMin, obb(chassis).YMin]
            + [obb(B.place_pcie_lock_screw(B.make_mb_screw(), hx)).YMin
               for hx in D.pcie_lock_x()]
        )
        real = D.CASE_REAR - y_min
        (ok if approx(real, D.rear_outer_protrusion(), 0.05) else fail)(
            f"完整裝機後實際外凸 {real:.2f} mm = rear_outer_protrusion() "
            f"{D.rear_outer_protrusion():.2f}（含螺絲頭，從幾何量）"
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
