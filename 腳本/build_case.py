# FreeCAD: 主板平躺在底板上 + 電源在 I/O 擋板正上方 + 前方碟艙三面環繞 → 單一長方體
# Run via: scripts\build_case.py (ASCII junction)

from __future__ import annotations

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
import Mesh

PATHS = D.project_paths()
STL_DIR, CAD_DIR = PATHS["stl"], PATHS["cad"]
DOC_NAME = "mATX_Case_Full"


def box(x0, y0, z0, x1, y1, z1):
    b = Part.makeBox(max(x1 - x0, 1e-6), max(y1 - y0, 1e-6), max(z1 - z0, 1e-6))
    b.translate(App.Vector(x0, y0, z0))
    return b


def cyl(r, h, x, y, z):
    c = Part.makeCylinder(r, h)
    c.translate(App.Vector(x, y, z))
    return c


def fuse_all(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s.removeSplitter()


# ── 螺紋 ─────────────────────────────────────────────────────────────
# ★ 這裡是**真的螺旋**，不是舊版那種疊起來的同心圓盤。
#   verify 用「相位轉 180° 必須撞」證明它不是軸對稱的（軸對稱的怎麼轉都不會撞）。
THREAD_SEG = 24  # 每圈斷面數；弦差 = R(1−cos7.5°) ≈ 0.015 mm，遠低於列印解析度


def thread_rib(r_minor, depth, pitch, height, z0=0.0, grow=0.0):
    """
    單線梯形外螺紋的螺旋肋（不含芯柱）。斷面畫在**軸平面**上，
    每個斷面用解析式擺到 (θ_k, z_k)，再 ruled loft 起來。

    ★ 不用 makeHelix + MakePipeShell：實測那條路徑會**漂移**——三圈掉 0.35 mm，
      比螺帽間隙還大，而且外牙(r=1.15)與內牙(r=0.95)漂移量不同 → 螺帽在任何相位都咬死。
    """
    hb = D.MB_STUD_ROOT_W * pitch / 2 + grow
    ht = D.MB_STUD_CREST_W * pitch / 2 + grow
    n = max(2, int(round(height / pitch * THREAD_SEG)))
    wires = []
    for k in range(n + 1):
        th = 2 * math.pi * k / THREAD_SEG
        c, s = math.cos(th), math.sin(th)
        z = z0 + pitch * k / THREAD_SEG

        def P(rad, dz):
            return App.Vector(rad * c, rad * s, z + dz)

        pts = [P(r_minor, -hb), P(r_minor + depth, -ht), P(r_minor + depth, ht), P(r_minor, hb)]
        wires.append(Part.makePolygon(pts + [pts[0]]))
    return Part.makeLoft(wires, True, True)


def make_mb_stud():
    """主板柱細軸：芯柱（往下埋入粗肩 2 mm）+ 螺旋肋。局部 z=0 對應粗肩頂面。"""
    r = D.MB_STUD_MINOR / 2
    core = Part.makeCylinder(r, D.MB_STUD_LEN + 2.0)
    core.translate(App.Vector(0, 0, -2.0))  # 埋入粗肩，避免只有面接觸
    rib = thread_rib(r, D.MB_STUD_DEPTH, D.MB_STUD_PITCH, D.MB_STUD_LEN - 0.8)
    return core.fuse(rib)


def make_mb_nut():
    """
    印製壓帽：內牙由「同一條外牙放大 MB_NUT_GAP」挖出 → 兩者一定咬得合。
    外周開指握溝（手緊；印製牙的扭力上限就是手指）。局部 z=0 = 螺帽底面。
    """
    ro = D.MB_NUT_OD / 2
    g = D.MB_NUT_GAP
    h = D.MB_NUT_H
    body = Part.makeCylinder(ro, h)
    bore = Part.makeCylinder(D.MB_STUD_MINOR / 2 + g, h + 6.0)
    bore.translate(App.Vector(0, 0, -3.0))
    cut = thread_rib(
        D.MB_STUD_MINOR / 2 - g,
        D.MB_STUD_DEPTH + 2 * g,
        D.MB_STUD_PITCH,
        h + 3 * D.MB_STUD_PITCH,
        z0=-D.MB_STUD_PITCH,
        grow=g,
    )
    nut = body.cut(bore).cut(cut)
    for i in range(D.MB_NUT_FLUTES):
        a = 2 * math.pi * i / D.MB_NUT_FLUTES
        f = Part.makeCylinder(D.MB_NUT_FLUTE_R, h + 2.0)
        f.translate(App.Vector(ro * math.cos(a), ro * math.sin(a), -1.0))
        nut = nut.cut(f)
    return nut


def place_mb_nut(nut, x, y, z_bottom):
    """
    把壓帽旋到工作位。螺紋是螺旋：軸向移動 dz 必須配對應的旋轉
    α = 360·dz/pitch，否則牙撞牙（verify 就是用這件事證明牙是真的）。
    """
    s = nut.copy()
    dz = z_bottom - D.SHOULDER_TOP_Z
    s.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 360.0 * dz / D.MB_STUD_PITCH)
    s.translate(App.Vector(x, y, z_bottom))
    return s


# ── 通用鑽孔／凸座 ───────────────────────────────────────────────────
def bore_x(x_from, x_to, y, z, dia):
    lo, hi = min(x_from, x_to), max(x_from, x_to)
    c = Part.makeCylinder(dia / 2, hi - lo)
    c.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 90)
    c.translate(App.Vector(lo, y, z))
    return c


def bore_y(y_from, y_to, x, z, dia):
    lo, hi = min(y_from, y_to), max(y_from, y_to)
    c = Part.makeCylinder(dia / 2, hi - lo)
    c.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    c.translate(App.Vector(x, lo, z))
    return c


def bore_z(z_from, z_to, x, y, dia):
    lo, hi = min(z_from, z_to), max(z_from, z_to)
    return cyl(dia / 2, hi - lo, x, y, lo)


def rounded_cut_xz(x0, y0, z0, x1, y1, z1, r):
    """XZ 平面圓角矩形切除體（後牆 I/O 開孔）。"""
    if r < 0.05:
        return box(x0, y0, z0, x1, y1, z1)
    r = min(r, (x1 - x0) / 2 - 0.01, (z1 - z0) / 2 - 0.01)
    core = box(x0 + r, y0, z0, x1 - r, y1, z1)
    mid = box(x0, y0, z0 + r, x1, y1, z1 - r)
    parts = [core, mid]
    y_lo, y_hi = min(y0, y1), max(y0, y1)
    h = y_hi - y_lo + 1.0
    for cx, cz in ((x0 + r, z0 + r), (x1 - r, z0 + r), (x0 + r, z1 - r), (x1 - r, z1 - r)):
        c = Part.makeCylinder(r, h)
        c.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
        c.translate(App.Vector(cx, y_lo - 0.5, cz))
        parts.append(c)
    return fuse_all(parts)


# ── PCIe 壓條 keyhole（唯一來源：後牆 fuse 這些，壓條 cut 對應讓位，verify 量它們）──
def hook_neck(hx):
    y = D.CASE_REAR
    hw = D.PCIE_HOOK_NECK_W / 2
    return box(hx - hw, y - D.PCIE_HOOK_NECK_D, D.PCIE_HOOK_Z0,
               hx + hw, y + 1.0, D.PCIE_HOOK_Z0 + D.PCIE_HOOK_H)


def hook_head(hx):
    y = D.CASE_REAR - D.PCIE_HOOK_NECK_D
    hw = D.PCIE_HOOK_HEAD_W / 2
    return box(hx - hw, y - D.PCIE_HOOK_HEAD_D, D.PCIE_HOOK_Z0,
               hx + hw, y + D.PCIE_HOOK_FUSE, D.PCIE_HOOK_Z0 + D.PCIE_HOOK_H)


def _hook_detent_centres(hx):
    """兩片翼上的 detent 球心（球心內移 R−DEPTH → 只凸出 DETENT_DEPTH）。"""
    y_face = D.CASE_REAR - D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_FUSE  # 翼朝牆的那一面
    yc = y_face - (D.DETENT_R - D.DETENT_DEPTH)
    zc = D.PCIE_HOOK_Z0 + D.PCIE_HOOK_H / 2
    dx = (D.PCIE_HOOK_NECK_W + D.PCIE_HOOK_HEAD_W) / 4
    return [(hx + sx * dx, yc, zc) for sx in (-1, 1)]


def hook_detents(hx, grow=0.0):
    out = []
    for cx, cy, cz in _hook_detent_centres(hx):
        b = Part.makeSphere(D.DETENT_R + grow)
        b.translate(App.Vector(cx, cy, cz))
        out.append(b)
    return out


def pcie_hook_sites():
    return [(hx, hook_detents(hx)) for hx in D.pcie_hook_x()]


def pcie_bar_slot(hx):
    """
    壓條上的 keyhole 讓位：**上窄下寬**。
    抬起 PCIE_BAR_DROP 時頭自寬口穿過，落下後頭被窄段兩側各 2.2 mm 的料扣住。
    窄段頂面 = 頸頂面（零間隙）→ 那就是壓條落到底的承靠面，落差自己收斂。
    """
    f = D.PCIE_BAR_FIT
    zk, hn, d = D.PCIE_HOOK_Z0, D.PCIE_HOOK_H, D.PCIE_BAR_DROP
    y0, y1 = D.CASE_REAR - D.PCIE_BAR_T - 1.0, D.CASE_REAR + 1.0
    nw = D.PCIE_HOOK_NECK_W / 2 + f
    hw = D.PCIE_HOOK_HEAD_W / 2 + f
    narrow = box(hx - nw, y0, zk - d - 1.0, hx + nw, y1, zk + hn)
    wide = box(hx - hw, y0, zk - d - 1.0, hx + hw, y1, zk - 0.2)
    return narrow.fuse(wide)


def shroud_detents(is_left, grow=0.0):
    """
    側板前段減薄帶上的 detent 凸半球（唯一來源：側板 fuse 它、前罩 cut 它的凹坑、
    verify 掃描時扣掉它）。grow>0 用在凹坑／掃描讓位。
    """
    xo = D.CASE_LEFT if is_left else D.CASE_RIGHT
    inward = 1 if is_left else -1
    lap_t = D.SHROUD_LAP_T + D.SLIDE_FIT
    cx = xo + inward * (lap_t + D.SHROUD_DETENT_R - D.SHROUD_DETENT_DEPTH)
    out = []
    for dz in D.SHROUD_DETENT_Z:
        s = Part.makeSphere(D.SHROUD_DETENT_R + grow)
        s.translate(App.Vector(cx, D.BAY_SPLIT_Y - D.SHROUD_LAP / 2, dz))
        out.append(s)
    return out


def shroud_floor_stud_bands():
    """
    前罩地板舌自 +Y 滑進來時會**撞到主板柱**的 X 帶（唯一來源：底板留實心墊、
    前罩挖對應讓位槽）。柱是自 z=0 長起的 Ø8 圓柱，任何在它 y 帶前方的地板料
    都會在滑動途中撞上去——這是「最終位置合法、路被擋住」的又一例（硬規則 14）。
    """
    y_lap0 = D.SHROUD_Y0 - D.SHROUD_LAP
    r = D.SHOULDER_OD / 2 + D.SLIDE_FIT
    return sorted((hx - r, hx + r) for hx, hy in D.HOLES_MM.values() if hy + r > y_lap0)


def floor_edge_x(is_left):
    """
    底板本體側緣的 X（**內縮 SLIDE_FIT**）與舌尖的 X。
    ★ 第十輪：第九輪的底板本體剛好等於內腔寬 247.88，兩側與牆內面**完全共面**
      （distToShape 0.0000）—— 250 mm 的跨距上批次收縮差就有 0.25–0.50 mm，
      零間隙的滑配是裝不上的（硬規則 19 + FDM 跨距收縮那條）。
    """
    if is_left:
        edge = D.FLOOR_X0 + D.SLIDE_FIT
        return edge, edge - D.FLOOR_LIP
    edge = D.FLOOR_X1 - D.SLIDE_FIT
    return edge, edge + D.FLOOR_LIP


def floor_detents(is_left, grow=0.0):
    """
    底板側緣的縱向 bead（軸沿 Z，只存在於承載唇那 FLOOR_LEDGE_T 的高度帶）。
    唯一來源：底板 fuse 它、側板 cut 它加大 grow 的凹槽、verify 量它、掃描時扣掉它。
    """
    out = []
    for cx, cy in D.floor_detent_sites(is_left):
        c = Part.makeCylinder(D.FLOOR_DETENT_R + grow, D.FLOOR_LEDGE_T)
        c.translate(App.Vector(cx, cy, 0.0))
        out.append(c)
    return out


def floor_rear_detents(grow=0.0):
    """
    底板後緣舌 ↔ 後牆低位槽 的 detent（第十輪新增；使用者：底板與後板之間缺卡榫）。
    公件是底板舌**上表面**的半球，母件是後牆槽頂面的凹坑（那上面整片都是牆料）。
    """
    r = D.FLOOR_REAR_DETENT_R
    zc = D.FLOOR_T - (r - D.DETENT_DEPTH)
    yc = D.FLOOR_Y0 - D.FLOOR_LIP / 2
    out = []
    for cx in D.REAR_FLOOR_DETENT_X:
        s = Part.makeSphere(r + grow)
        s.translate(App.Vector(cx, yc, zc))
        out.append(s)
    return out


def rear_tab_detents(is_left, grow=0.0):
    """
    後牆定位舌 ↔ 側板口袋 的**單向卡榫**。公件（楔）長在側板的口袋底上，
    母件是後牆定位舌上的貫穿孔。回傳的是**公件實體**，母孔／掃描讓位都由它導出。

    ★ 第十輪把公母對調（球長在 2.4 的牆上、孔開在 1.2 的舌上）。理由仍然成立。
    ★ 第十一輪把**半球換成不對稱楔**。真相表量出來：後牆往 −Y 拉，>12 mm 都沒有
      任何幾何擋住 —— 半球是唯一的阻力，而半球受拉會自己爬出來。
      純滑動接合的公母進出走同一道邊，所以不對稱只能做在公件上：

          −Y ←—— 斜坡 ——→ 峰 →| 直角面
          （舌自 −Y 推來，前緣爬上斜坡）  （拉不回去）

      楔沿 Z 只有 REAR_WEDGE_H，孔比它高 → Z 方向不靠楔定位（那是槽的事）。
    """
    xi = D.FLOOR_X0 if is_left else D.FLOOR_X1
    sgn = -1 if is_left else +1
    # 口袋底在 xi + sgn*(REAR_TAB_T + SLIDE_FIT)；楔自口袋底往內凸 DETENT_DEPTH，
    # 根部再往牆料裡埋 1.0（硬規則 1：只有面接觸的 fuse 不會合併）。
    x_floor = xi + sgn * (D.REAR_TAB_T + D.SLIDE_FIT)
    x_tip = x_floor - sgn * (D.DETENT_DEPTH + grow)  # 峰頂（往機殼內凸）
    x_root = x_floor + sgn * 1.0  # 埋進牆體
    # 斜坡起點＝側板的後端面（楔不能懸空在側板之外），直角面在它前方 ramp+back。
    y_ramp = rear_wedge_y0() - grow
    y_pk0 = y_ramp + D.REAR_WEDGE_RAMP  # 平台後緣＝斜坡頂
    y_sq = rear_wedge_y1() + grow  # 直角面（＝擋住 −Y 拉出的那一面）
    out = []
    for dz in D.REAR_DETENT_Z:
        z0 = dz - D.REAR_WEDGE_H / 2 - grow
        z1 = dz + D.REAR_WEDGE_H / 2 + grow
        # 側視輪廓（Y–X 平面）：斜坡 → 平台 → 直角面 → 埋進牆裡的根部
        pts = [(y_ramp, x_floor), (y_pk0, x_tip), (y_sq, x_tip), (y_sq, x_root),
               (y_ramp, x_root)]
        poly = Part.makePolygon(
            [App.Vector(x, y, z0) for y, x in pts] + [App.Vector(x_floor, y_ramp, z0)]
        )
        w = Part.Face(poly).extrude(App.Vector(0, 0, z1 - z0))
        # 根部埋 1.0 會超過槽背後剩下的 0.90 → 裁到機殼外表面，外表面必須保持是平的。
        # 公件、母缺口、掃描讓位看到的是同一顆楔（裁在同一個函式裡）。
        out.append(w.common(box(D.CASE_LEFT, y_ramp - 1.0, z0 - 1.0,
                                D.CASE_RIGHT, y_sq + 1.0, z1 + 1.0)))
    return out


def rear_wedge_y0():
    """楔的斜坡起點＝側板後端面。"""
    return D.CASE_REAR + D.WALL


def rear_wedge_y1():
    """楔的直角面 y。缺口前緣、驗證探點、負向測試全部指到這裡（硬規則 9）。"""
    return rear_wedge_y0() + D.REAR_WEDGE_RAMP + D.REAR_WEDGE_BACK


def rear_tab_notches(is_left, grow=0.0):
    """後牆定位舌上的母缺口：**自舌根往前開**，前緣就在楔的直角面前方 SLIDE_FIT/2。

    開缺口不開孔的理由見 參數.REAR_WEDGE_*：直角面推的是缺口前緣，
    那道邊後面必須是整片舌料（一路連到舌尖），不能只有 0.45 mm 的細肉。
    """
    xi = D.FLOOR_X0 if is_left else D.FLOOR_X1
    sgn = -1 if is_left else +1
    xa, xb = sorted((xi - sgn * 2.0, xi + sgn * (D.REAR_TAB_T + D.SLIDE_FIT + 2.0)))
    y_front = rear_wedge_y1() + D.SLIDE_FIT / 2 + grow
    out = []
    for dz in D.REAR_DETENT_Z:
        out.append(
            box(xa, D.CASE_REAR + D.WALL - 0.6 - grow,
                dz - D.REAR_WEDGE_H / 2 - D.SLIDE_FIT - grow,
                xb, y_front,
                dz + D.REAR_WEDGE_H / 2 + D.SLIDE_FIT + grow)
        )
    return out


def side_lap_keep_bands():
    """
    側板前段（前罩搭接帶）上**不准減薄**的 z 帶 —— 三道內面滑槽的正後方。

    ★ 第十輪抓到的老病灶：牆只有 2.4，內面挖 1.6 的槽、外面再減 1.5，
      加起來 3.1 > 2.4 —— 那一段是**被切穿的**。底板槽、碟架槽、頂蓋槽
      在搭接帶那 12 mm 裡**三條全部通到底**，第八／九輪都是這樣，
      只是當時前罩殼 1.2、頂蓋舌又只伸 0.4，兩件的料剛好錯開，
      布林檢查一路綠 —— 直到第十輪把頂蓋舌修回 1.3，才撞出 7.2 mm³。
      **「沒有干涉」不等於「牆還在」。**

    修法不是把槽變淺（變淺就沒有咬合），而是**那三段不減薄**：
    側板在該 z 帶保持整厚 2.4，前罩的搭接殼對應挖掉。
    副作用剛好是使用者要的：那三段整厚料變成榫、前罩的缺口變成槽。
    """
    m = 0.6
    raw = sorted([
        [-0.5, D.FLOOR_T + D.SLIDE_FIT + m],
        [D.RACK_RAIL_Z0 - m, D.RACK_RAIL_Z1 + m],
        [D.INNER_TOP_Z - D.TOP_T - m, D.OUTER_TOP_Z + 0.5],
    ])
    out = []
    for z0, z1 in raw:
        if out and z0 <= out[-1][1] + 3.0:  # 兩帶之間留不下 3 mm 的減薄就直接併起來
            out[-1][1] = max(out[-1][1], z1)
        else:
            out.append([z0, z1])
    return [tuple(b) for b in out]


def side_lap_thin_bands():
    """搭接帶上**可以減薄**的 z 帶（keep 帶的補集）。"""
    keep = side_lap_keep_bands()
    out, z = [], 0.0
    for k0, k1 in keep:
        if k0 > z:
            out.append((z, k0))
        z = max(z, k1)
    if z < D.OUTER_TOP_Z:
        out.append((z, D.OUTER_TOP_Z))
    return out


def shroud_lap_detents(is_top, grow=0.0):
    """
    前罩**頂／底**搭接帶上的 detent 半球（第十輪新增；使用者：前罩需要一個卡槽）。
    公件長在機殼側的減薄帶上（頂蓋前段上表面／底板前段上表面），
    母件是前罩對應舌上的凹坑。球心內移 R − DEPTH，凸出量才是 DEPTH。
    """
    r, dep = D.SHROUD_LAP_DETENT_R, D.SHROUD_LAP_DETENT_DEPTH
    # 減薄帶的上表面：頂蓋是「切到 LAP_T + SLIDE_FIT 深」，底板是「切到 LAP_T 深」
    #（前罩地板舌自己往上讓了 SLIDE_FIT），兩邊的間隙都是 SLIDE_FIT。
    z_face = (
        D.OUTER_TOP_Z - (D.SHROUD_TOP_LAP_T + D.SLIDE_FIT)
        if is_top
        else D.FLOOR_T - D.SHROUD_FLOOR_LAP_T
    )
    zc = z_face - (r - dep)
    out = []
    for cx in D.SHROUD_LAP_DETENT_X:
        s = Part.makeSphere(r + grow)
        s.translate(App.Vector(cx, D.BAY_SPLIT_Y - D.SHROUD_LAP / 2, zc))
        out.append(s)
    return out


# ── 底板（＝主板托盤）───────────────────────────────────────────────
def make_bottom_tray():
    """
    底板＝主板托盤。第八輪螺母座**整組刪掉**（改全滑槽），下裙跟著消失。

    ★ 底板與牆的關係**是反過來的**：不是牆插進底板，是**底板自 +Y 滑進牆**。
      理由和第七輪螺母座只能放地板以下是同一條：主板佔滿內腔（左 3.54／右 0.50／
      後 1.00），而板底 6.35 淨空（§2.4.2）把 z∈[2.4, 8.75] 也封死 ——
      任何從底板往上長的定位唇，右側和後側都會直接戳進主板。
      所以底板三面各伸出一片**舌**，插進左右側板與後牆內面的低位槽裡。
      那個高度只有地板，沒有主板。

    ★ 第九輪：舌從「整片 2.4 的板邊」改成「上半片 FLOOR_LIP_T」。
      第八輪的槽開到 z=−0.1，槽的**下方一點料都沒有**（探針 0.00 mm³）——
      那是 L 形搭邊，地板只是擱在地上、被上面 1.2 的牆料蓋住而已。
      使用者問「底板跟左右板之間真的有滑蓋設計嗎」，問得對：那時候沒有。
      現在舌在 z∈[1.2, 2.4]，牆在 z∈[0, 1.2] 保留整厚 → 舌被上下夾住，是真的槽。
    """
    xl, xlt = floor_edge_x(True)  # 左側緣、左舌尖
    xr, xrt = floor_edge_x(False)
    x0, x1 = xl, xr
    y0, y1 = D.FLOOR_Y0, D.FLOOR_Y1
    body = box(x0, y0, 0.0, x1, y1, D.FLOOR_T)
    # 三面上半舌（左／右／後）。角落自然相接：左右舌的 y 一路延到後舌的外緣。
    # ★ 第十輪：本體兩側已內縮 SLIDE_FIT（見 floor_edge_x），後緣則**不縮**——
    #   後牆是自 −Y 推上來對接的，那是個止擋面不是滑配面，留間隙反而定不了位。
    zt0 = D.FLOOR_T - D.FLOOR_LIP_T
    ly0 = y0 - D.FLOOR_LIP
    body = body.fuse(box(xlt, ly0, zt0, x0 + 1.0, y1, D.FLOOR_T))
    body = body.fuse(box(x1 - 1.0, ly0, zt0, xrt, y1, D.FLOOR_T))
    body = body.fuse(box(xlt, ly0, zt0, xrt, y0 + 1.0, D.FLOOR_T))
    # 側緣 bead（底板↔側板的保持力；側板的槽自後端掃過來，只有最後一段有過盈）
    for is_left in (True, False):
        for b in floor_detents(is_left):
            body = body.fuse(b)
    # 前緣半搭接：前罩的地板舌壓在這片減薄帶上（第八輪前罩底下**完全沒有地板**，
    # 機殼前段 53.76 mm 是開的）。減薄只在內腔寬度內，不動兩側的舌。
    body = body.cut(
        box(x0, y1 - D.SHROUD_LAP, D.FLOOR_T - D.SHROUD_FLOOR_LAP_T, x1, y1 + 0.1, D.FLOOR_T + 0.1)
    )
    # 落在搭接帶裡的主板柱（L／M 兩孔 y=227.33）：那兩處保留整厚地板當柱腳，
    # 前罩的地板舌在同樣的 X 帶上挖讓位槽滑過去。
    for bx0, bx1 in shroud_floor_stud_bands():
        body = body.fuse(box(bx0, y1 - D.SHROUD_LAP, 0.0, bx1, y1, D.FLOOR_T))
    # 九根粗肩（自 z=0 長起 → 與地板真實體積重疊，避免只有面接觸變成獨立 Solid）
    for x, y in D.HOLES_MM.values():
        body = body.fuse(cyl(D.SHOULDER_OD / 2, D.SHOULDER_TOP_Z, x, y, 0.0))
    body = body.removeSplitter()

    # 細軸最後才 fuse，而且**不再 removeSplitter**：
    # removeSplitter 對螺紋的 loft 面會把形狀弄成 isValid()==False（實測）。
    stud = make_mb_stud()
    for x, y in D.HOLES_MM.values():
        st = stud.copy()
        st.translate(App.Vector(x, y, D.SHOULDER_TOP_Z))
        body = body.fuse(st)
    # ★ 半球 detent 一定要**排在 removeSplitter 之後**才 fuse：
    #   實測「先 fuse 半球 → removeSplitter → 再 fuse 螺紋 loft」會直接得到 Null shape。
    #   球面被 removeSplitter 併過之後，再跟 spline 面做布林就會炸。
    #   （圓柱 bead 沒有這個問題，所以它仍留在前面。）
    for s in shroud_lap_detents(False):  # 前罩底搭接（前罩地板舌上有對應凹坑）
        body = body.fuse(s)
    for s in floor_rear_detents():  # 後緣舌上（後牆槽頂有對應凹坑）
        body = body.fuse(s)
    return body


# ── 後牆 ─────────────────────────────────────────────────────────────
def make_rear_panel():
    """
    後牆自下裙一路到牆頂。由下而上三段：
      z 6.51–50.96   I/O 開孔（板面下 3.81 起，microATX Fig.4）
      z 16.68–135.43 PCIe 四槽（右半，含 6 mm 抬升帶）+ 繫樑
      z 112.07–178.37 PSU 後面板開窗（**插頭插在 I/O 擋板上方那一區**，使用者指定）
    """
    t = D.WALL
    x0, x1 = D.CASE_LEFT, D.CASE_RIGHT
    y_outer, y_inner = D.CASE_REAR, D.CASE_REAR + t
    panel = box(x0, y_outer, -D.SKIRT_H, x1, y_inner, D.OUTER_TOP_Z)

    # I/O：圓角開孔 + keepout 區減薄成可夾壁厚（0.94–1.32）+ 外側插入倒角
    panel = panel.cut(
        rounded_cut_xz(
            D.IO_X0, y_outer - 0.5, D.IO_Z0, D.IO_X1, y_inner + 0.5, D.IO_Z1, D.IO_CORNER_R
        )
    )
    ko, rd = D.IO_KEEPOUT, t - D.IO_CLIP_T
    if rd > 0.05:
        panel = panel.cut(
            box(D.IO_X0 - ko, y_outer - 0.1, D.IO_Z0 - ko, D.IO_X1 + ko, y_outer + rd, D.IO_Z1 + ko)
        )
    ch = D.IO_CHAMFER
    panel = panel.cut(
        box(D.IO_X0 - ch, y_outer - 0.1, D.IO_Z0 - ch, D.IO_X1 + ch, y_outer + ch, D.IO_Z1 + ch)
    )

    # ── PCIe ──────────────────────────────────────────────────────────
    # ★ 第九輪刪掉「連續橫縫」（它把三根 1.42 的肋切成 112.75 mm 的懸臂），
    #   並把三根肋往機殼外補到 1.42×6.40。
    # ★ 第十輪：補強範圍從「只有肋」擴大成**整圈窗框**（使用者：PCIe 還是很多問題）。
    #   80×120 的洞開在 2.4 的板子上，只補中間三根肋等於只補了洞裡面那幾條線；
    #   底檻（舌袋挖完只剩 1.1）、左右柱、才是那片牆真正軟的地方。
    #   做法改成「先把整塊窗框往外長 PCIE_RIB_D，再把四個開孔切穿」——
    #   肋、底檻、左右柱一次全部變成 6.40 厚，而且**只有一條 fuse、一條 cut**。
    #   左端讓開 I/O 開孔、右端不超出機殼外表面（見 pcie_frame_x）。
    fx0, fx1 = D.pcie_frame_x()
    fz0, fz1 = D.pcie_frame_z()
    panel = panel.fuse(box(fx0, y_outer - D.PCIE_RIB_D, fz0, fx1, y_outer + 0.5, fz1))
    panel = panel.removeSplitter()

    # 機殼只需要兩個切除（本體貫穿開孔、內面舌袋），其餘都是想像出來的。
    # 開孔頂 = 擋板頂 + PCIE_LIFT：卡要離開連接器必須整片抬 4.50。
    centers = D.pcie_centers()
    tang_w = D.PCIE_TANG_W + 2 * D.PCIE_TANG_GAP
    for cx in centers:
        panel = panel.cut(
            box(
                cx - D.PCIE_OPEN_W / 2,
                y_outer - D.PCIE_RIB_D - 0.5,  # 要切穿補強層
                D.PCIE_Z0,
                cx + D.PCIE_OPEN_W / 2,
                y_inner + 0.5,
                D.PCIE_Z1 + D.PCIE_LIFT,
            )
        )
        panel = panel.cut(
            box(
                cx - tang_w / 2,
                y_inner - D.PCIE_TANG_POCKET,
                D.PCIE_TANG_Z0 - D.PCIE_TANG_GAP,
                cx + tang_w / 2,
                y_inner + 0.5,
                D.PCIE_Z0 + 0.1,
            )
        )

    # ATX 四孔（ATX12V Fig.4；PSU 風扇朝下＝標準姿態，+Z 就是上）
    for hx, hz in D.ATX_HOLES:
        hole = Part.makeCylinder(D.ATX_SCREW_CLR / 2, t + 2)
        hole.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
        hole.translate(App.Vector(D.ATX_X0 + hx, y_outer - 1, D.ATX_Z0 + hz))
        panel = panel.cut(hole)
    # PSU 後面板開窗：PSU 的後面板**就是**這一段的機殼後表面（排風柵 + AC 插座 + 開關）。
    # 邊界由 ATX_HOLES 導出（PSU_WIN_*），不是手寫的 inset。
    panel = panel.cut(
        box(
            D.ATX_X0 + D.PSU_WIN_X0,
            y_outer - 0.5,
            D.ATX_Z0 + D.PSU_WIN_Z0,
            D.ATX_X0 + D.PSU_WIN_X1,
            y_inner + 0.5,
            D.ATX_Z0 + D.PSU_WIN_Z1,
        )
    )

    # PSU 承托凸緣：電源坐在這條上（四顆 #6-32 才是固定件，凸緣負責重量與潛變）。
    # 頂面 = ATX_Z0、底面 = AREA_A_TOP_Z → 機殼的料一點都沒有伸進 Area A 淨空。
    # 左端讓開 PSU_LEDGE_W，那一段由左側板的長肩負責（否則兩件重疊）。
    panel = panel.fuse(
        box(
            D.ATX_X0 + D.PSU_LEDGE_W,
            y_inner - 0.5,
            D.ATX_Z0 - D.PSU_LEDGE_T,
            D.ATX_X1,
            y_inner + D.PSU_LEDGE_W,
            D.ATX_Z0,
        )
    )

    # ★ PCIe 壓條的兩顆**蘑菇柱**（keyhole 公件），長在後牆外表面、開孔頂之上。
    #   壓條先整片往 +Y 壓上去（頭穿過壓條上的寬口），再往下落 PCIE_BAR_DROP，
    #   頭就被窄槽兩側各 2.2 mm 的料扣住。全程不必沿 X 走 → 肋一根都不用切。
    for hx, wing in pcie_hook_sites():
        panel = panel.fuse(hook_neck(hx))
        panel = panel.fuse(hook_head(hx))
        # 頭的兩片翼（各 2.5 寬）可以往 −Y 彈 → detent 就長在翼上，
        # 壓條落到定位時卡進它外表面的凹坑（半球受面內剪力，不是層間拉力）。
        for b in wing:
            panel = panel.fuse(b)

    # ★ 第八輪刪掉後牆的頂蓋承托肩：頂蓋改成自 +Y 滑入側板槽，兩側被槽夾住、
    #   後端被鉤唇壓住，這條肩已經說不出它承住了什麼（硬規則 13）。
    #   刪掉它同時解掉一件事：電源自上方落入時不必再為了它橫移 X。
    # ★ 頂鉤唇：頂蓋自 +Y 滑到底之後，後端鑽進這片唇的**下方** → 頂蓋不能再往上抬，
    #   側板也就抽不上去（側板頂端被頂蓋的 T 槽鉤著）。這是整條互鎖鏈的收尾。
    panel = panel.fuse(
        box(
            D.CASE_LEFT + t,
            y_inner - 0.5,
            D.OUTER_TOP_Z - D.TOP_HOOK_T,
            D.CASE_RIGHT - t,
            y_inner + D.TOP_HOOK_D,
            D.OUTER_TOP_Z,
        )
    )

    # 底板低位槽：後牆自 −Y 推上來，底板後緣的舌插進這道槽（見 make_bottom_tray）
    # ★ X 範圍要含底板**兩側的舌**（底板比內腔寬），否則兩端各干涉。
    # ★ 第十輪：槽底自 −0.1 抬到 FLOOR_LEDGE_T。第九輪這道槽是**開穿到牆底**的
    #   （探針：舌下方料 0.00 mm³，側板對照 144.00）—— 使用者第九輪問「底板跟
    #   左右板之間真的有滑蓋嗎」，那一輪只修了側板，**後牆這一道原封不動**。
    #   同一個病灶修了一半、另一半留著，下一輪就會被使用者再問一次（他問了）。
    xlt = floor_edge_x(True)[1]
    xrt = floor_edge_x(False)[1]
    panel = panel.cut(
        box(
            xlt - D.SLIDE_FIT,
            y_inner - (D.FLOOR_LIP + D.SLIDE_FIT),
            D.FLOOR_LEDGE_T,
            xrt + D.SLIDE_FIT,
            y_inner + 0.1,
            D.FLOOR_T + D.SLIDE_FIT,
        )
    )
    # 槽頂的 detent 凹坑（底板舌上表面有對應的半球）
    for s in floor_rear_detents(grow=0.15):
        panel = panel.cut(s)
    # 兩側定位舌：後牆兩端往前伸出一片薄舌，插進側板後端內面的槽（X 定位）。
    # ★ 這裡**不能用燕尾**：燕尾大端 8 > 牆厚 2.4，兩片 2.4 的板在角落根本咬不住。
    # ★ 舌要長在**側板牆體那一側**（往機殼外），不是往機殼內：往內的話右邊那片
    #   x∈[33.59, 34.79] 會直接戳進主板（板右緣 34.29）與 Area B 淨空。
    for is_left, (xc, sgn) in zip(
        (True, False), ((D.CASE_LEFT + t, -1), (D.CASE_RIGHT - t, +1))
    ):
        panel = panel.fuse(
            box(
                min(xc, xc + sgn * D.REAR_TAB_T),
                y_inner - 0.5,  # 反向埋入牆體
                D.FLOOR_T,
                max(xc, xc + sgn * D.REAR_TAB_T),
                y_inner + D.REAR_TAB_D,
                # ★ 頂端必須停在頂蓋舌槽的**底下**：定位舌與頂蓋側舌走的是側板上
                #   同一道 x 帶，長到 INNER_TOP_Z 就會在槽裡對撞（實測 8.64 mm³）。
                D.INNER_TOP_Z - D.TOP_T - D.SLIDE_FIT,
            )
        )
        # 母件：舌上自根部往前開缺口，側板口袋底的楔扣進去（公母第十輪對調、
        # 第十一輪半球→不對稱楔，直角面擋住 −Y 拉出）
        for s in rear_tab_notches(is_left):
            panel = panel.cut(s)
    return panel.removeSplitter()


# ── 側板 ─────────────────────────────────────────────────────────────
def make_side(is_left: bool):
    """
    主板段外牆（y 到 BAY_SPLIT_Y = 234.18；再往前是前罩，A1 床 256 逼出來的接縫）。
    第八輪**一顆螺絲都沒有**，四道滑槽全部開在內面（往外挖會破壞長方體外觀）：
      z∈[0, FLOOR_T]        底板舌槽 —— 底板自 +Y 滑進來
      z∈[131, 137]          碟架舌槽 —— 碟架自 +Y 滑進來（高度見下）
      z∈[167.82, 170.82]    頂蓋舌槽 —— 頂蓋自 +Y 滑進來，槽**上方**是牆料故舌抬不出去
      y∈[後端 4 mm]         後牆定位舌的槽 + detent 凹
    ★ 碟架舌槽的高度不是隨便挑的：右側板那一條落在 PCIe 卡的長度帶裡
      （230 長的卡伸到 y=219.34，卡頂 124.87，插拔還要整片抬 4.50）
      → 槽底必須高過 129.37。左側則要避開電源（y 只到 149.34，本來就不重疊）。
    """
    t = D.WALL
    y0, y1 = D.CASE_REAR + t, D.BAY_SPLIT_Y
    if is_left:
        x0, x1 = D.CASE_LEFT, D.CASE_LEFT + t
        xi, sgn = x1, -1  # 內面、往外挖的方向
    else:
        x0, x1 = D.CASE_RIGHT - t, D.CASE_RIGHT
        xi, sgn = x0, +1
    wall = box(x0, y0, 0.0, x1, y1, D.OUTER_TOP_Z)

    # 電源長肩（僅左側板）：電源左緣貼左內牆，整條坐在這上面。
    if is_left:
        wall = wall.fuse(
            box(x0, D.ATX_Y0, D.ATX_Z0 - D.PSU_LEDGE_T, x1 + D.PSU_LEDGE_W, D.ATX_FRONT_Y, D.ATX_Z0)
        )

    def groove(z_lo, z_hi, ya, yb, depth):
        a, b = sorted((xi, xi + sgn * depth))
        return box(a, ya, z_lo, b, yb, z_hi)

    # ① 底板舌槽（沿 Y 全長，前端開口讓底板自 +Y 滑入／側板自 +Y 滑上底板）
    # ★ 第九輪：槽底自 −0.1 抬到承載唇高度（第八輪槽開穿到牆底，槽下方 0.00 mm³）。
    # ★ 第十輪：**上下左右四個方向都補 SLIDE_FIT**。第九輪只補了「槽頂 +SLIDE_FIT」，
    #   槽底、槽深兩處仍是零間隙 —— 舌尖與槽底共面、舌底面與承載唇共面。
    #   槽深 = FLOOR_LIP + SLIDE_FIT = 1.60，牆背後剩 0.80（＝最小可印壁厚）。
    wall = wall.cut(
        groove(
            D.FLOOR_LEDGE_T,
            D.FLOOR_T + D.SLIDE_FIT,
            y0 - 0.1,
            y1 + 0.1,
            D.FLOOR_LIP + D.SLIDE_FIT,
        )
    )
    # ①b 底板側緣 bead 的凹槽（滑到底才落進去 → 這就是「卡上底板」的那一下）
    for c in floor_detents(is_left, grow=D.SLIDE_FIT / 2):
        wall = wall.cut(c)
    # ② 碟架舌槽。★ 第十一輪：後端改成**盲端**（RACK_STOP_Y）＝碟架推到底的止擋面。
    #   第十輪這裡開到 TRAY_Y0 − 1.0，比最後那條側舌後緣還後面 3 mm → 碟架浮 3 mm。
    wall = wall.cut(
        groove(D.RACK_RAIL_Z0, D.RACK_RAIL_Z1, D.RACK_STOP_Y, y1 + 0.1, D.RACK_RAIL_T)
    )
    # ③ 頂蓋舌槽（槽頂 = INNER_TOP_Z + SLIDE_FIT，其上仍有 2.70 牆料 → 頂蓋抬不出去）
    # ★ 第十輪：槽深 1.2 → TOP_LIP + SLIDE_FIT = 1.60。第九輪頂蓋的舌**只咬進 0.40 mm**
    #   （舌自本體邊緣算起只伸出 TOP_LIP − 2×TOP_FIT_GAP），槽卻挖了 1.2 —— 使用者說
    #   「只有頂蓋有滑蓋卡榫」，其實那個卡榫也只有 0.4 mm。
    wall = wall.cut(
        groove(
            D.INNER_TOP_Z - D.TOP_T,
            D.INNER_TOP_Z + D.SLIDE_FIT,
            y0 - 0.1,
            y1 + 0.1,
            D.TOP_LIP + D.SLIDE_FIT,
        )
    )
    # ④ 後牆定位舌的槽 + detent 凹坑（槽深加 SLIDE_FIT，否則舌尖與槽底共面）
    wall = wall.cut(
        groove(
            D.FLOOR_T,
            D.INNER_TOP_Z,
            y0 - 0.1,
            y0 + D.REAR_TAB_D + D.SLIDE_FIT,
            D.REAR_TAB_T + D.SLIDE_FIT,
        )
    )
    # ★ 第十輪：detent 公母對調 —— 球長在側板的槽底上（純加料，側板一點都不用挖），
    #   後牆的定位舌上開對應的貫穿小孔。理由見 rear_tab_detents() 的註解。
    for s in rear_tab_detents(is_left):
        wall = wall.fuse(s)
    # ⑤ 前罩搭接：外表面前段減薄，前罩套上去之後外表面齊平（單一長方體）
    # ★ 第九輪：減薄量加上 SLIDE_FIT。第八輪是 nominal 零間隙 —— 布林 common=0.000
    #   被讀成「不干涉」，其實是「套不進去」。**「≤ 上限」的地方也要檢查「≥ 下限」。**
    # ★ 第十輪：減薄**只在 side_lap_thin_bands() 的 z 帶**。三道內面滑槽的正後方
    #   不准減薄，否則 1.6 的槽 + 1.5 的減薄 = 3.1 > 牆厚 2.4 → 那 12 mm 直接穿。
    xo = x0 if is_left else x1  # 外表面
    inward = 1 if is_left else -1
    lap_t = D.SHROUD_LAP_T + D.SLIDE_FIT
    a, b = sorted((xo, xo + inward * lap_t))
    for tz0, tz1 in side_lap_thin_bands():
        wall = wall.cut(box(a, y1 - D.SHROUD_LAP, tz0, b, y1 + 0.1, tz1))
    # ⑥ 前罩 detent：凸半球長在減薄面上，前罩搭接殼有對應凹坑。
    #   半徑受**減薄後剩下的料厚**限制：剩 WALL − lap_t = 0.90 → 2R ≤ 0.90 + DEPTH。
    for s in shroud_detents(is_left):
        wall = wall.fuse(s)
    return wall.removeSplitter()


def make_side_left_mb():
    return make_side(True)


def make_side_right_mb():
    return make_side(False)


def make_pcie_bar():
    """
    PCIe 壓條 —— 第八輪移到機殼外面（使用者：「壓條通常長在機殼外面」），
    第九輪把固定方式從「沿 X 滑進 T 軌」改成 **keyhole：壓上去、往下落 3.5**。

    改的理由是使用者主訴的結構問題：沿 X 滑就得讓四個壓舌走完全程，
    於是後牆被開了一條連續橫縫，三根 1.42 mm 的肋變成 112.75 mm 的懸臂。
    keyhole 不需要沿 X 走，橫縫可以刪掉，肋回到兩端固定。

    構造：一片掛在後牆外兩顆蘑菇柱上的板，內側四個舌各自穿過自己那個開孔的
    抬升讓位帶，壓在擋板頂緣上方 PCIE_HOLD_GAP。舌只伸入 2.0（<牆厚 2.4），
    **機殼內部一點料都沒有**。拆：抬 3.5 mm、往 −Y 拔，不必拆頂蓋。
    """
    bx0, bx1 = D.pcie_bar_x()
    y_out = D.CASE_REAR
    bar = box(bx0, y_out - D.PCIE_BAR_T, D.PCIE_BAR_Z0, bx1, y_out, D.PCIE_BAR_Z1_TOP)
    for hx in D.pcie_hook_x():
        bar = bar.cut(pcie_bar_slot(hx))
        # detent 凹坑：比公件半球大 0.15，落到定位時**不干涉**（過盈只發生在行程中）
        for d in hook_detents(hx, grow=0.15):
            bar = bar.cut(d)
    # 四個壓舌：穿過開孔，底面＝防上抬面
    for cx in D.pcie_centers():
        bar = bar.fuse(
            box(
                cx - D.PCIE_BAR_TAB_W / 2,
                y_out,  # 自本體內側面長起（體積相接，不是面接觸）
                D.PCIE_BAR_Z0,
                cx + D.PCIE_BAR_TAB_W / 2,
                y_out + D.PCIE_BAR_TAB_D,
                D.PCIE_BAR_Z1,
            )
        )
    return bar.removeSplitter()


# ── 頂蓋（單片、自 +Y 滑入）──────────────────────────────────────────
def make_top_mb():
    """
    頂蓋：**單片**，自 +Y 往 −Y 水平滑入左右側板內面的槽。
    ★ 第七輪那兩片半搭接是「碟艙是獨立外殼段」的產物；碟艙變成內部碟架之後，
      接縫沒有理由存在了（硬規則 13：多餘的特徵要刪，不是留著）。
    互鎖：兩側舌插進側板槽 → **槽上方還是牆料**，所以頂蓋抬不起來；
          滑到底後後端鑽進後牆頂鉤唇下方 → 連帶把兩片側板也鎖住抽不上去；
          前端由前罩擋住 → 不會自己滑出來。
    """
    g = D.TOP_FIT_GAP
    z0, z1 = D.INNER_TOP_Z, D.OUTER_TOP_Z
    x0, x1 = D.FLOOR_X0 + g, D.FLOOR_X1 - g
    y0, y1 = D.FLOOR_Y0 + g, D.BAY_SPLIT_Y
    top = box(x0, y0, z0, x1, y1, z1)
    # 兩側下伸舌（插進側板 z∈[INNER−TOP_T, INNER+SLIDE_FIT] 的槽）
    # ★ 第十輪：舌的**咬合量從 0.40 修回 TOP_LIP = 1.30**。
    #   第九輪的舌是 `x ∈ [x0 − TOP_LIP + g, x0]`，而 x0 已經比牆內面內縮了 g ——
    #   兩個 g 疊起來，真正伸進槽裡的只剩 TOP_LIP − 2g = 0.40 mm。
    #   使用者說「只有頂蓋有滑蓋卡榫」，那個卡榫其實也只有 0.4 mm。
    #   現在舌自**牆內面**往外伸 TOP_LIP，往內埋進本體 TOP_FUSE（體積重疊才 fuse 得起來）。
    #   舌只到 z0，不往上埋——超過 z0 就會撞到槽上方的牆料（第九輪實測每側 97.8 mm³）。
    for xa, xb in (
        (D.FLOOR_X0 - D.TOP_LIP, D.TOP_LID_INNER_X),
        (D.FLOOR_X1 + D.TOP_LIP, D.FLOOR_X1 - g - D.TOP_FUSE),
    ):
        top = top.fuse(box(min(xa, xb), y0, z0 - D.TOP_T, max(xa, xb), y1, z0))
    # 後端**半搭接**：切掉上半，滑到底時鑽進後牆頂鉤唇（同樣只有上半）的下方
    # ★ 第十輪：切深加 SLIDE_FIT。第九輪切到剛好 TOP_HOOK_T，於是頂蓋的切面與
    #   鉤唇的底面**共面**——頂蓋要在鉤唇下方磨進去。鉤唇的職責是「限制上抬」，
    #   限位面本來就該留間隙（頂蓋剩 1.20 仍 > 最小可印壁厚）。
    top = top.cut(
        box(x0 - D.TOP_LIP - 1, y0 - 1, z1 - D.TOP_HOOK_T - D.SLIDE_FIT,
            x1 + D.TOP_LIP + 1, y0 + D.TOP_HOOK_D + g, z1)
    )
    # 前端上表面減薄：前罩的頂舌填回去，套上之後頂面齊平（第八輪前罩根本沒搭到頂）
    top = top.cut(
        box(
            x0 - D.TOP_LIP - 1,
            y1 - D.SHROUD_LAP,
            z1 - (D.SHROUD_TOP_LAP_T + D.SLIDE_FIT),
            x1 + D.TOP_LIP + 1,
            y1 + 0.1,
            z1 + 0.1,
        )
    )
    # 前罩頂搭接的 detent 公件（前罩頂舌上有對應凹坑）
    for s in shroud_lap_detents(True):
        top = top.fuse(s)
    return top.removeSplitter()


# ── 碟架（平躺 4 層，疊在主板前段的正上方）──────────────────────────
def make_hdd_rack():
    """
    碟架：左右兩片立板 + 頂板 + 兩條往右伸的橫樑。四個托盤自 +Y 滑進立板內面的導軌槽。

    ★ 為什麼碟平躺而且在這個高度：直立 2×2 之所以只吃 65.10 深，靠的是
      「電源把機殼撐到 192 之後本來就空著的高度」。電源一往下挪（Area A 88.90→50），
      那段高度就沒了，直立碟艙反而變成高度瓶頸（碟頂 171.4 > 電源決定的內頂 153.32）。
    ★ 為什麼碟後緣是 180.34 而不是更後面：碟的 x 帶跨過 AREA_A_STEP_X(−95.25)，
      x∈[−95.25, −60.09] 那段 Area A 一路延到 AREA_A_Y_FAR(180.34)（Fig.7 p18）。
      再往後就伸進散熱器空間。
    ★ 第九輪的三個修正（全部來自使用者的驗收）：
      ①**立板底面下探到 RACK_Z0 = Area C 淨空頂**，最底層的導軌槽下面才有 2.7 mm 承載料。
        第八輪立板底與 lv0 槽底同高（槽底其實還低 0.30）→ 最下面那層托盤舌**懸空**。
      ②**右立板退開 HDD_CABLE_W = 30**：第八輪它整片貼著碟的 101.6×26.1 接頭端面，
        四層各干涉 15.8–18.0 cm³ ——「走線空間不足」是客氣說法，是接頭插不上。
      ③**碟架置中**：左右各餘 29.44，前罩開口距機殼左右外表面各 33.44。
    ★ 側舌高度改由碟架自己的頂板導出（吊在頂板下 2 mm，力臂最短、同一塊料）。
      舊的「由 PCIe 卡導出」在卡長被切到 189.00 之後已經不成立（硬規則 15）。
    """
    y0, y1 = D.TRAY_Y0, D.HDD_Y1
    z0, z1 = D.RACK_Z0, D.RACK_TOP_Z1
    parts = [
        box(D.RACK_X0, y0, z0, D.HDD_X0, y1, z1),  # 左立板
        box(D.RACK_POST_X0, y0, z0, D.RACK_POST_X1, y1, z1),  # 右立板（已讓開接頭區）
        box(D.RACK_X0, y0, D.HDD_TOP_Z, D.RACK_POST_X1, y1, z1),  # 頂板
    ]
    # 左右橫樑（把碟架繫到兩側側板；置中之後兩邊都懸空，所以兩邊都要）。
    # 各分兩條而不是一整片，中間讓線束穿過。
    for by in D.RACK_BEAM_Y:
        for xa, xb in (
            (D.CASE_LEFT + D.WALL, D.RACK_X0),
            (D.RACK_POST_X1, D.CASE_RIGHT - D.WALL),
        ):
            parts.append(
                box(xa, by - D.RACK_BEAM_W / 2, D.RACK_RAIL_Z0,
                    xb, by + D.RACK_BEAM_W / 2, D.RACK_RAIL_Z1)
            )
    rack = fuse_all(parts)

    # 側舌：自橫樑末端伸出，插進側板內面的槽（兩側對稱）
    f = D.SLIDE_FIT
    for by in D.RACK_BEAM_Y:
        for xi, sgn in ((D.CASE_LEFT + D.WALL, -1), (D.CASE_RIGHT - D.WALL, +1)):
            xa, xb = sorted((xi - sgn * 1.0, xi + sgn * (D.RACK_RAIL_T - f)))
            rack = rack.fuse(
                box(xa, by - D.RACK_BEAM_W / 2, D.RACK_RAIL_Z0 + f,
                    xb, by + D.RACK_BEAM_W / 2, D.RACK_RAIL_Z1 - f)
            )

    # 四層托盤導軌槽（自立板內面往外挖 TRAY_RAIL_W，前端開口讓托盤滑入）
    for lv in range(D.HDD_LEVELS):
        zt = D.tray_z0(lv)
        for xa, xb in (
            (D.HDD_TRAY_X0 - D.TRAY_RAIL_W, D.HDD_TRAY_X0 + 0.1),
            (D.HDD_TRAY_X1 - 0.1, D.HDD_TRAY_X1 + D.TRAY_RAIL_W),
        ):
            rack = rack.cut(box(xa, y0 - 0.1, zt - f, xb, y1 + 0.1, zt + D.TRAY_RAIL_H + f))
    return rack.removeSplitter()


def make_hdd_tray():
    """
    碟托盤（印 4 份）：碟**平躺鎖在托盤上、用底面孔**。
    ★ SFF-8301 §3.1：底面四到六孔、每側兩孔。平躺時該用的是**底孔**——
      拿側孔（A8/A9/A10）來用就是八顆螺絲鎖進塑膠（第五輪踩過的）。
      A7 那對是規格保證的，A6／A13 二選一必要 → 三排孔全開，讓使用者挑碟上有的。
    ★ 托盤厚 3.0 不是隨手取的：SFF-8301 p7 Fastener penetration 2.39–3.56，
      配 #6-32×1/4"(6.35) → 穿入碟體 3.35，落在區間內。
    ★ 第九輪：托盤往 +X 延伸 HDD_CABLE_W = 30，一路鋪到右立板。
      那 30 mm 是碟的**接頭區**（SATA 資料 + 電源），托盤在 z∈[0, 3.0]、接頭與線在它
      上方，互不相干；托盤同時當走線的底，線不會垂到下面的 PCIe 卡上。
    托盤前擋板就是機殼前面板的一部分（換碟不必拆任何東西，直接抽）。
    """
    x0, x1 = D.HDD_TRAY_X0, D.HDD_TRAY_X1
    y0, y1 = D.TRAY_Y0, D.HDD_Y1
    t = D.TRAY_T
    parts = [box(x0, y0, 0.0, x1, y1, t)]
    # 兩側導軌舌
    parts.append(box(x0 - D.TRAY_RAIL_W, y0, 0.0, x0 + 1.0, y1, D.TRAY_RAIL_H))
    parts.append(box(x1 - 1.0, y0, 0.0, x1 + D.TRAY_RAIL_W, y1, D.TRAY_RAIL_H))
    # 後擋邊（碟推到底的止擋）——只在碟的 X 範圍內，接頭區不要擋
    parts.append(box(x0, y0, 0.0, D.HDD_X1, y0 + D.TRAY_BACK_STOP, t + D.TRAY_LIP_H))
    # 前擋板＝機殼前面板的一部分
    fy0 = y1 + D.TRAY_FRONT_GAP
    fx0, fx1 = x0 - D.TRAY_RAIL_W, x1 + D.TRAY_RAIL_W
    fz1 = D.TRAY_PITCH - 2 * D.TOP_FIT_GAP
    parts.append(box(fx0, fy0 - 1.0, 0.0, fx1, fy0 + D.TRAY_FACE_T, fz1))
    tray = fuse_all(parts)

    # 碟底孔（三排 × 2）：沉頭，螺絲頭不得凸出托盤底面（否則吃掉層節距）
    for hx, hy in D.hdd_bottom_hole_xy(0):
        tray = tray.cut(bore_z(-0.5, t + 0.5, hx, hy, D.HDD_SCREW_CLR))
        tray = tray.cut(bore_z(-0.1, D.HDD_SCREW_HEAD_T, hx, hy, D.HDD_SCREW_HEAD_D))
    # 前擋板進氣柵 + 指拉凹
    vx0 = fx0 + D.FRONT_VENT_MARGIN
    vx1 = fx1 - D.FRONT_VENT_MARGIN
    for i in range(D.TRAY_VENT_ROWS):
        vz = 4.0 + i * D.FRONT_VENT_PITCH  # 起點壓低：擋板只有 TRAY_PITCH−0.8 高
        tray = tray.cut(box(vx0, fy0 - 2.0, vz, vx1, fy0 + D.TRAY_FACE_T + 1.0, vz + D.FRONT_VENT_SLAT))
    cx = (fx0 + fx1) / 2
    tray = tray.cut(
        box(
            cx - D.TRAY_PULL_W / 2,
            fy0 + D.TRAY_FACE_T - 1.2,
            fz1 - D.TRAY_PULL_H,
            cx + D.TRAY_PULL_W / 2,
            fy0 + D.TRAY_FACE_T + 1.0,
            fz1 + 1.0,
        )
    )
    return tray.removeSplitter()


def make_hdd_tray_placed(level: int):
    s = make_hdd_tray()
    s.translate(App.Vector(0, 0, D.tray_z0(level)))
    return s


# ── 前罩（主板段之前那 53.76 mm；A1 床 256 逼出來的分件）──────────────
def make_front_shroud():
    """
    前罩：左右壁 + 頂 + **地板** + 前面板（碟托盤穿過的口以外的部分）。

    ★ 第九輪三件事，全部來自使用者的驗收：
      ①**補地板**。第八輪前罩自 z=0 就被挖空，而底板只做到 BAY_SPLIT_Y ——
        機殼前段 53.76 mm 是**整片開的**（探針：兩件在該區的料都是 0.0 mm³）。
      ②**打薄**（WALL 2.4 → SHROUD_WALL 1.6）。前罩不承重，只有搭接帶要強度；
        前面板仍 3.0（要開按鈕孔與柵）、地板仍 2.4（要接底板）。
      ③**真的卡住**。第八輪搭接帶零間隙、沒有舌、沒有槽、沒有 detent，它只是套著。
        現在四面半搭接（左右外表面減薄帶／頂蓋前段上表面／底板前段上表面）
        + 兩側各兩顆 detent。
    進氣柵與電源按鈕都在**碟陣下方**那片固定前板上——按鈕不能長在會被抽走的托盤上。
    """
    t = D.SHROUD_WALL
    lt = D.SHROUD_LAP_T
    y0, y1 = D.SHROUD_Y0 - D.SHROUD_LAP, D.CASE_FRONT
    x0, x1 = D.CASE_LEFT, D.CASE_RIGHT
    z1 = D.OUTER_TOP_Z
    shell = box(x0, y0, 0.0, x1, y1, z1)

    # ① 搭接帶（y ∈ [y0, SHROUD_Y0]）：整段掏空，只留左右兩片 SHROUD_LAP_T 薄殼
    #    與頂面的 SHROUD_TOP_LAP_T 薄舌；地板舌另外補回去（見下）。
    shell = shell.cut(
        box(x0 + lt, y0 - 0.1, -0.1, x1 - lt, D.SHROUD_Y0, z1 - D.SHROUD_TOP_LAP_T)
    )
    # 頂舌只能存在於「頂蓋在的那段 X」——長到側板上方就會撞側板牆頂（實測每側 16.20 mm³）
    for xa, xb in ((x0 + lt, D.FLOOR_X0), (D.FLOOR_X1, x1 - lt)):
        shell = shell.cut(box(xa, y0 - 0.1, z1 - D.SHROUD_TOP_LAP_T, xb, D.SHROUD_Y0, z1 + 0.1))
    # ★ 第十輪：搭接殼在**三道滑槽的 z 帶**要讓開 —— 側板在那三段保持整厚 2.4
    #   （見 side_lap_keep_bands()）。讓出來的缺口正好把那三段整厚料咬住：
    #   前罩因此在 Z 上被扣死，不只是靠 detent 摩擦（使用者：前罩需要一個卡槽）。
    f = D.SLIDE_FIT
    for kz0, kz1 in side_lap_keep_bands():
        for xa, xb in ((x0 - 0.1, x0 + lt + 0.01), (x1 - lt - 0.01, x1 + 0.1)):
            shell = shell.cut(box(xa, y0 - 0.1, kz0 - f, xb, D.SHROUD_Y0, kz1 + f))
    # 地板舌：壓在底板前緣那道減薄帶上。
    # ★ 第十輪：X 範圍改由 floor_edge_x() 導出並再內縮 SLIDE_FIT。
    #   寫死 FLOOR_X0/FLOOR_X1 的話，舌會蓋到**底板自己的兩側舌**上（那兩條沒有減薄，
    #   它們要留在側板的槽裡）—— 實測每側 3.24 mm³，共 6.48。減薄帶到哪裡，舌就到哪裡。
    fl = floor_edge_x(True)[0] + D.SLIDE_FIT
    fr = floor_edge_x(False)[0] - D.SLIDE_FIT
    shell = shell.fuse(
        box(fl, y0, D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT, fr,
            D.SHROUD_Y0 + 0.1, D.FLOOR_T)
    )
    # 主板柱讓位槽：滑進來的路上會撞到 L／M 兩根柱（底板在同樣的 X 帶留了實心柱腳）
    for bx0, bx1 in shroud_floor_stud_bands():
        shell = shell.cut(
            box(bx0 - D.SLIDE_FIT, y0 - 0.5, -0.5, bx1 + D.SLIDE_FIT, D.SHROUD_Y0, D.FLOOR_T + 0.01)
        )
    # ② 主體（y ≥ SHROUD_Y0）：留左右壁 t、頂 t、地板 FLOOR_T、前面板 TRAY_FACE_T
    shell = shell.cut(
        box(x0 + t, D.SHROUD_Y0 - 0.1, D.FLOOR_T, x1 - t, y1 - D.TRAY_FACE_T, z1 - t)
    )
    # 托盤前擋板穿過的口（★ 碟架置中之後這個口自己就對稱了）
    g = D.TOP_FIT_GAP
    fx0, fx1 = D.tray_opening_x()
    shell = shell.cut(
        box(fx0, y1 - D.TRAY_FACE_T - 0.1, D.HDD_Z0 - g, fx1, y1 + 0.1, D.RACK_TOP_Z1 + g)
    )
    # 碟陣下方固定前板的進氣柵（唯一進氣口的一部分）
    vx0, vx1 = fx0 + D.FRONT_VENT_MARGIN, fx1 - D.FRONT_VENT_MARGIN
    n = int((D.FRONT_VENT_Z1 - D.FRONT_VENT_Z0) // D.FRONT_VENT_PITCH)
    for i in range(n):
        vz = D.FRONT_VENT_Z0 + i * D.FRONT_VENT_PITCH
        shell = shell.cut(
            box(vx0, y1 - D.TRAY_FACE_T - 1.0, vz, vx1, y1 + 0.1, vz + D.FRONT_VENT_SLAT)
        )
    # 電源按鈕（面板式，內側鎖螺帽；本體 22 深伸進主板前方的空腔，不撞任何東西）
    bx = D.pwr_btn_x()
    shell = shell.cut(bore_y(y1 + 0.5, y1 - D.TRAY_FACE_T - 0.5, bx, D.PWR_BTN_Z, D.PWR_BTN_D))
    # ③ detent 凹坑：對應側板減薄帶上的凸半球（比公件大 0.15，落到定位時不干涉）
    for is_left in (True, False):
        for s in shroud_detents(is_left, grow=0.15):
            shell = shell.cut(s)
    # ★ 第十輪：**頂與底的搭接帶也加 detent**（使用者：前罩需要設計一個卡槽）。
    #   第九輪只有左右各兩顆，頂與底整片是光的 —— 四面搭接是滑槽，但只有兩個方向
    #   有保持力。現在四面都有：左右各 3、頂底各 2，共 10 顆。
    for is_top in (True, False):
        for s in shroud_lap_detents(is_top, grow=0.15):
            shell = shell.cut(s)
    return shell.removeSplitter()
# ── PCIe 空槽蓋 ──────────────────────────────────────────────────────
def make_pcie_blank():
    """
    空槽封板：與 CEM 擋板同外形（本體 18.42×112.75 + 底舌 14.30×7.27），
    厚度改成可印的 1.6。列印座標：本體平躺在 XY，Z 為厚度。
    """
    t, tt = D.PCIE_BLANK_T, D.PCIE_TANG_POCKET - 0.3
    body = box(0.0, D.PCIE_TANG_H, 0.0, D.PCIE_BRACKET_W, D.PCIE_TANG_H + D.PCIE_BODY_H, t)
    tang = box(
        (D.PCIE_BRACKET_W - D.PCIE_TANG_W) / 2,
        0.0,
        0.0,
        (D.PCIE_BRACKET_W + D.PCIE_TANG_W) / 2,
        D.PCIE_TANG_H + 2.0,  # 埋入本體
        tt,
    )
    # 頂端折耳：開孔為了讓卡抬升而開高 6 mm，沒有耳的槽蓋會在裡面上下跳
    ear = box(
        0.0,
        D.PCIE_TANG_H + D.PCIE_BODY_H - t,
        0.0,
        D.PCIE_BRACKET_W,
        D.PCIE_TANG_H + D.PCIE_BODY_H,
        t + D.PCIE_BLANK_EAR,
    )
    return fuse_all([body, tang, ear])


def make_pcie_blank_parked():
    """總成裡的槽蓋是備件，停放在機殼外側，避免與已裝卡的虛擬件重疊。"""
    s = make_pcie_blank()
    s.translate(App.Vector(D.CASE_RIGHT + 20.0, D.CASE_REAR, 0.0))
    return s


def make_mb_nut_placed():
    """總成裡放 **B 孔那一顆**（工作位），讓標準干涉檢查直接驗到旋合。實印 9 顆。"""
    return place_mb_nut(make_mb_nut(), D.HOLES_MM["B"][0], D.HOLES_MM["B"][1], D.BOARD_TOP_Z)


def add_obj(doc, name, shape, label=None):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Label = label or name
    return obj


def export_stl(obj, path, deflection=0.25):
    Mesh.Mesh(obj.Shape.tessellate(deflection)).write(path)
    return os.path.getsize(path)


# 總成預覽配色 (R,G,B,A)
PREVIEW_COLORS = {
    "Bottom_Tray": (0.20, 0.45, 0.85, 0.0),
    "Rear_IO_PCIe": (0.92, 0.72, 0.12, 0.0),
    "Side_Left_MB": (0.55, 0.58, 0.62, 0.0),
    "Side_Right_MB": (0.55, 0.58, 0.62, 0.0),
    "Top_MB": (0.72, 0.74, 0.78, 0.55),  # 半透明看內部
    "Top_HDD": (0.72, 0.74, 0.78, 0.55),
    "HDD_Cage": (0.15, 0.55, 0.35, 0.0),
    "PCIeBlank": (0.85, 0.85, 0.88, 0.0),
    "PCIeBar": (0.90, 0.35, 0.20, 0.0),
    "MB_Nut": (0.95, 0.55, 0.10, 0.0),
}


def apply_preview_style(doc, parts):
    """套用分件配色；頂蓋半透明。無 GUI 時略過 ViewObject。"""
    for name, obj in parts.items():
        rgba = PREVIEW_COLORS.get(name)
        if not rgba:
            continue
        r, g, b, a = rgba
        try:
            vo = obj.ViewObject
            if vo is None:
                continue
            vo.ShapeColor = (r, g, b)
            if hasattr(vo, "Transparency"):
                vo.Transparency = int(round(a * 100)) if a > 0 else 0
            vo.Visibility = True
        except Exception:
            pass


def build(export=True):
    os.makedirs(STL_DIR, exist_ok=True)
    os.makedirs(CAD_DIR, exist_ok=True)
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)

    parts = {}
    makers = [
        ("Bottom_Tray", make_bottom_tray, "底板_主板托盤"),
        ("Rear_IO_PCIe", make_rear_panel, "後牆_IO與PCIe"),
        ("Side_Left_MB", make_side_left_mb, "左側板_主板段"),
        ("Side_Right_MB", make_side_right_mb, "右側板_主板段"),
        ("Top_MB", make_top_mb, "頂蓋（單片，自 +Y 滑入）"),
        ("Front_Shroud", make_front_shroud, "前罩_含進氣柵與電源按鈕"),
        ("HDD_Rack", make_hdd_rack, "碟架_四層導軌（平躺，疊在主板前段上方）"),
        ("HDD_Tray", lambda: make_hdd_tray_placed(0), "碟托盤（總成示第 0 層，實印 4 份）"),
        ("PCIeBlank", make_pcie_blank_parked, "PCIe槽蓋（備件，停放於機殼外）"),
        ("PCIeBar", make_pcie_bar, "PCIe壓條（外置；自機殼右外側滑入）"),
        ("MB_Nut", make_mb_nut_placed, "主板壓帽（總成示 B 孔一顆，實印 9 顆）"),
    ]
    for name, fn, label in makers:
        parts[name] = add_obj(doc, name, fn(), label)
    doc.recompute()
    apply_preview_style(doc, parts)

    stl_map = dict(D.STL_NAMES)  # 唯一來源是 參數.STL_NAMES

    if export:
        for old in (
            "電源艙_SFX.stl",
            "左側板.stl",
            "右側板.stl",
            "頂蓋.stl",
            "底框.stl",
        ) + tuple(D.REMOVED_STL):
            p = os.path.join(STL_DIR, old)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        # 列印姿態與總成姿態不同的件：STL 走各自的原型
        own_shape = {
            "PCIeBlank": make_pcie_blank,
            "MB_Nut": make_mb_nut,
            "HDD_Tray": make_hdd_tray,  # 總成裡是第 0 層，STL 走未平移的原型
        }
        for key, fname in stl_map.items():
            path = os.path.join(STL_DIR, fname)
            # 螺紋是 0.5 mm 的特徵，0.25 的弦差會把牙磨平
            defl = 0.05 if key in ("Bottom_Tray", "MB_Nut") else 0.25
            if key in own_shape:
                Mesh.Mesh(own_shape[key]().tessellate(defl)).write(path)
                sz = os.path.getsize(path)
            else:
                sz = export_stl(parts[key], path, defl)
            print(f"STL {fname} {sz}")
        fcstd = os.path.join(CAD_DIR, D.FCSTD_NAME)
        doc.saveAs(fcstd)
        print("saved", fcstd)
        w, d, h = D.envelope_mm()
        print(f"ENVELOPE {w:.1f} x {d:.1f} x {h:.1f} mm")

    total = 0.0  # 一件一份（各件體積之和）
    total_qty = 0.0  # 乘上份數＝實際要買的料
    for name, obj in parts.items():
        bb = obj.Shape.BoundBox
        qty = D.PART_QTY[name]
        total += obj.Shape.Volume
        total_qty += obj.Shape.Volume * qty
        print(
            f"OBJ {name} x{qty} {bb.XLength:.1f}x{bb.YLength:.1f}x{bb.ZLength:.1f} "
            f"Z={bb.ZMin:.1f}..{bb.ZMax:.1f} V={obj.Shape.Volume / 1000:.1f}cm3"
        )
    print(f"PRINT_VOLUME {total / 1000:.1f} cm3 (一件一份)")
    print(f"FILAMENT_VOLUME {total_qty / 1000:.1f} cm3 (含份數，買料看這個)")
    return doc, parts


if __name__ == "__main__":
    build(export=True)
    print("BUILD_OK")
