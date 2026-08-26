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
    hb = D.MB_THREAD_ROOT_W * pitch / 2 + grow
    ht = D.MB_THREAD_CREST_W * pitch / 2 + grow
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


def _hex_prism(across_flats, height):
    """外六角柱；平面朝床即可穩定列印。工具槽見 make_mb_screw。"""
    radius = across_flats / math.sqrt(3.0)
    pts = [
        App.Vector(radius * math.cos(math.radians(30 + 60 * i)),
                   radius * math.sin(math.radians(30 + 60 * i)), 0.0)
        for i in range(6)
    ]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(App.Vector(0, 0, height))


def make_mb_screw_thread():
    """穿過 PCB 並在盲孔旋合 5 mm 的外牙；肋根埋入芯柱 0.1 mm。"""
    r = D.MB_THREAD_MINOR / 2
    length = D.MB_SCREW_THREAD_LEN
    core = Part.makeCylinder(r, length)
    rib = thread_rib(r - 0.1, D.MB_THREAD_DEPTH + 0.1, D.MB_THREAD_PITCH, length)
    clip = Part.makeCylinder(D.MB_THREAD_MAJOR / 2 + 0.02, length)
    return core.fuse(rib.common(clip))


def make_mb_socket_cutter():
    """盲內牙切除體；沿用同一條螺旋並放大 MB_THREAD_GAP。"""
    g = D.MB_THREAD_GAP
    length = D.MB_SOCKET_DEPTH
    bore = Part.makeCylinder(D.MB_THREAD_MINOR / 2 + g, length)
    rib = thread_rib(
        D.MB_THREAD_MINOR / 2 - g,
        D.MB_THREAD_DEPTH + 2 * g,
        D.MB_THREAD_PITCH,
        length,
        grow=g,
    )
    clip = Part.makeCylinder(D.MB_THREAD_MAJOR / 2 + g + 0.02, length)
    return bore.fuse(rib.common(clip))


def _mb_screw_cross():
    """頭頂十字工具槽的切除體（自貼床面 z=0 往上 CROSS_DEPTH）。"""
    w, ln, dp = D.MB_SCREW_CROSS_W, D.MB_SCREW_CROSS_L, D.MB_SCREW_CROSS_DEPTH
    return box(-ln / 2, -w / 2, -0.5, ln / 2, w / 2, dp).fuse(
        box(-w / 2, -ln / 2, -0.5, w / 2, ln / 2, dp)
    )


def make_mb_screw():
    """頭面朝床、牙軸朝 +Z 的 8 mm AF 專用主板螺絲（頭頂含十字工具槽）。"""
    head = _hex_prism(D.MB_SCREW_HEAD_AF, D.MB_SCREW_HEAD_H).cut(_mb_screw_cross())
    neck = Part.makeCylinder(D.MB_THREAD_MINOR / 2, 0.7)
    neck.translate(App.Vector(0, 0, D.MB_SCREW_HEAD_H - 0.5))
    shaft = make_mb_screw_thread()
    shaft.translate(App.Vector(0, 0, D.MB_SCREW_HEAD_H))
    return head.fuse(neck).fuse(shaft)


def place_mb_screw(screw, x, y, seat_z=None):
    """
    把列印姿態的螺絲翻轉到工作位。
    `seat_z` 是**被夾件的頂面**（螺絲頭的坐面），預設 PCB 上表面；
    第十三輪的 PCIeBar 傳耳的頂面 —— 夾持厚同為 `PCB_T`，同一顆螺絲通用。
    """
    if seat_z is None:
        seat_z = D.BOARD_TOP_Z
    s = screw.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.translate(App.Vector(x, y, seat_z + D.MB_SCREW_HEAD_H))
    return s


def place_mb_socket_cutter(cutter, x, y, top_z=None):
    """
    盲孔自**承接面**向 −Z 切入；與安裝螺絲使用相同相位。
    `top_z` 預設是主板支撐肩頂；第十三輪的 PCIeBar 鎖點傳繫樑頂面 —— 兩者的
    夾持厚都是 `PCB_T`（壓條耳厚就是照著取的），所以相位公式完全共用。
    """
    if top_z is None:
        top_z = D.SHOULDER_TOP_Z
    s = cutter.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.rotate(
        App.Vector(0, 0, 0),
        App.Vector(0, 0, 1),
        -360.0 * D.PCB_T / D.MB_THREAD_PITCH,
    )
    s.translate(App.Vector(x, y, top_z))
    return s


# ── 通用鑽孔／凸座 ───────────────────────────────────────────────────
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


def tri_prism_xy(points, z0, z1):
    wire = Part.makePolygon([App.Vector(x, y, z0) for x, y in points] + [App.Vector(*points[0], z0)])
    return Part.Face(wire).extrude(App.Vector(0, 0, z1 - z0))


def tri_prism_yz(points, x0, x1):
    wire = Part.makePolygon([App.Vector(x0, y, z) for y, z in points] + [App.Vector(x0, *points[0])])
    return Part.Face(wire).extrude(App.Vector(x1 - x0, 0, 0))


def tri_prism_xz(points, y0, y1):
    """XZ 平面三角形沿 Y 擠出（PCIe 45° 尖頂、碟架承托肩的 45° 斜撐）。"""
    wire = Part.makePolygon(
        [App.Vector(x, y0, z) for x, z in points]
        + [App.Vector(points[0][0], y0, points[0][1])]
    )
    return Part.Face(wire).extrude(App.Vector(0, y1 - y0, 0))


# ── PCIe 外側螺絲座／頂蓋 detent ─────────────────────────────────────
def place_pcie_lock_socket(cutter, hx):
    """
    壓條鎖點盲牙：軸沿 +Y、開口在窗框補強的外表面（不長凸台，Chassis 的 Y 一分不加）。
    變換序列與主板盲牙完全相同（翻 180° + 依夾持厚補相位），最後把 −Z 軸整體轉到
    +Y —— 牙的手性因此與 `MB_Screw` 一致，同一顆螺絲兩處通用。
    """
    s = cutter.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.rotate(
        App.Vector(0, 0, 0),
        App.Vector(0, 0, 1),
        -360.0 * D.PCIE_BAR_SEAT_T / D.MB_THREAD_PITCH,
    )
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
    s.translate(App.Vector(hx, D.pcie_bar_mount_y(), D.PCIE_LOCK_Z))
    return s


def place_pcie_lock_screw(screw, hx):
    """壓條螺絲的工作位：頭沉在壓條的沉頭凹裡，牙往 +Y 旋進盲內牙。"""
    s = screw.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
    s.translate(
        App.Vector(
            hx,
            D.pcie_bar_mount_y() - D.PCIE_BAR_SEAT_T - D.MB_SCREW_HEAD_H,
            D.PCIE_LOCK_Z,
        )
    )
    return s


def top_detents(grow=0.0):
    """後鉤前端的兩顆 detent；頂蓋滑到最後才由其後肩越過。"""
    r = D.TOP_DETENT_R + grow
    y_face = D.FLOOR_Y0 + D.TOP_HOOK_D
    yc = y_face - (D.TOP_DETENT_R - D.TOP_DETENT_DEPTH)
    zc = D.OUTER_TOP_Z - D.TOP_HOOK_T / 2
    out = []
    for cx in D.TOP_DETENT_X:
        s = Part.makeSphere(r)
        s.translate(App.Vector(cx, yc, zc))
        out.append(s)
    return out


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


# ── 一體式 Chassis 的地板 ─────────────────────────────────────────────
def make_chassis_floor():
    """地板反向埋入左右牆與後牆；保留九根 Ø8 支撐肩，不建立任何板面上方凸柱。"""
    o = D.CHASSIS_OVERLAP
    body = box(
        D.FLOOR_X0 - o,
        D.FLOOR_Y0 - o,
        0.0,
        D.FLOOR_X1 + o,
        D.FLOOR_Y1,
        D.FLOOR_T,
    )
    # 前緣半搭接：前罩地板舌壓在此減薄帶上；左右牆根保持整厚。
    body = body.cut(
        box(
            D.FLOOR_X0,
            D.FLOOR_Y1 - D.SHROUD_LAP,
            D.FLOOR_T - D.SHROUD_FLOOR_LAP_T,
            D.FLOOR_X1,
            D.FLOOR_Y1 + 0.1,
            D.FLOOR_T + 0.1,
        )
    )
    # L／M 兩孔落在搭接帶；保留整厚柱腳，前罩挖同源讓位槽。
    for bx0, bx1 in shroud_floor_stud_bands():
        body = body.fuse(
            box(bx0, D.FLOOR_Y1 - D.SHROUD_LAP, 0.0,
                bx1, D.FLOOR_Y1, D.FLOOR_T)
        )
    for x, y in D.HOLES_MM.values():
        body = body.fuse(cyl(D.SHOULDER_OD / 2, D.SHOULDER_TOP_Z, x, y, 0.0))
    return body.removeSplitter()


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
    # ★ 第十四輪：窗框底緣的 45° 引入楔。原本 fz0 那一面是 89.4 × 4.0 的水平懸空，
    #   正在三根肋的下方 —— 切片器要從床長支撐上來並焊在窗框外面（實測 359 mm²）。
    #   斜面自牆面 fz0 − PCIE_FRAME_LEAD 升到窗框底外緣，Y 不多凸一分。
    panel = panel.fuse(
        tri_prism_yz(
            [
                (y_outer, fz0 - D.PCIE_FRAME_LEAD),
                (y_outer, fz0),
                (y_outer - D.PCIE_FRAME_LEAD, fz0),
            ],
            fx0,
            fx1,
        )
    )
    panel = panel.removeSplitter()

    # 機殼只需要兩個切除（本體貫穿開孔、內面舌袋），其餘都是想像出來的。
    # 開孔頂 = 擋板頂 + PCIE_LIFT：卡要離開連接器必須整片抬 4.50。
    # ★ 第十三輪：開孔頂加 45° 尖頂。矩形段只到 PCIE_OPEN_Z1（＝擋板抬到頂的
    #   頂緣位置，全寬區一點都沒少），其上以 45° 收斂到 PCIE_APEX_Z。
    #   這一刀讓四個開孔的頂**不再是水平懸空**，切片器不生支撐 → 拆支撐時
    #   不會再有橫向力去掰那三根 1.42 mm 的肋（使用者實印回報的病灶）。
    centers = D.pcie_centers()
    tang_w = D.PCIE_TANG_W + 2 * D.PCIE_TANG_GAP
    y_cut0, y_cut1 = y_outer - D.PCIE_RIB_D - 0.5, y_inner + 0.5  # 要切穿補強層
    for cx in centers:
        panel = panel.cut(
            box(
                cx - D.PCIE_OPEN_W / 2,
                y_cut0,
                D.PCIE_Z0,
                cx + D.PCIE_OPEN_W / 2,
                y_cut1,
                D.PCIE_OPEN_Z1,
            )
        )
        panel = panel.cut(
            tri_prism_xz(
                [
                    (cx - D.PCIE_OPEN_W / 2, D.PCIE_OPEN_Z1),
                    (cx + D.PCIE_OPEN_W / 2, D.PCIE_OPEN_Z1),
                    (cx, D.PCIE_APEX_Z),
                ],
                y_cut0,
                y_cut1,
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

    # ★ 第十三輪：壓條的兩個鎖點改成軸沿 −Y 的**印製盲內牙**（取代 Ø2.8 盲 pilot
    #   + #6-32 自攻），鑽在繫樑上；盲牙在 make_chassis_body 最後一併切
    #   （spline 不能再 removeSplitter）。這裡不長任何凸台 —— Chassis 的 Y 只剩
    #   0.96 mm/邊 的 A1 餘量，往 −Y 凸 2.5 就直接超床。

    # ★ 第八輪刪掉後牆的頂蓋承托肩：頂蓋改成自 +Y 滑入側板槽，兩側被槽夾住、
    #   後端被鉤唇壓住，這條肩已經說不出它承住了什麼（硬規則 13）。
    #   刪掉它同時解掉一件事：電源自上方落入時不必再為了它橫移 X。
    # ★ 第十三輪：後牆內面補一道**與側槽同 z 帶**的頂蓋槽（使用者：後牆好像沒有卡槽）。
    #   第十二輪這一面是光的，頂蓋往 −Y 推到底沒有任何面擋住它 —— 六向保持力表裡
    #   −Y 那一格靠的是鉤唇上兩顆 detent 的摩擦。槽底面就是止擋面，
    #   而且頂蓋後緣從此是被夾住的舌（+Z 也多一道約束），不是一條懸空邊。
    #   槽深 TOP_REAR_LIP + SLIDE_FIT = 1.60，槽背仍留 GROOVE_BACK_MIN = 0.80。
    #   槽只開在後舌真的存在的兩段（top_rear_tab_bands）—— 開滿整條寬度的話，
    #   碟架與電源正上方那些段會白白把牆削成 0.8 厚。
    for tx0, tx1 in D.top_rear_tab_bands():
        panel = panel.cut(
            box(
                tx0 - D.SLIDE_FIT,
                y_inner - (D.TOP_REAR_LIP + D.SLIDE_FIT),
                D.INNER_TOP_Z - D.TOP_T,
                tx1 + D.SLIDE_FIT,
                y_inner + 0.1,
                D.INNER_TOP_Z + D.SLIDE_FIT,
            )
        )

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
    y0, y1 = D.CASE_REAR + D.WALL - D.CHASSIS_OVERLAP, D.BAY_SPLIT_Y
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

    # ② 碟架舌槽。★ 第十一輪：後端改成**盲端**（RACK_STOP_Y）＝碟架推到底的止擋面。
    #   第十輪這裡開到 TRAY_Y0 − 1.0，比最後那條側舌後緣還後面 3 mm → 碟架浮 3 mm。
    wall = wall.cut(
        groove(D.RACK_RAIL_Z0, D.RACK_RAIL_Z1, D.RACK_STOP_Y, y1 + 0.1, D.RACK_RAIL_T)
    )
    # ★ 第十三輪：碟架**承托肩**（使用者：溝槽太淺，能不能往內伸一塊擋板托住碟架）。
    #   槽從此只負責 +Z 約束，重量改由這條肩承擔：橫樑底面比肩頂高 SLIDE_FIT，
    #   載重後落 0.30 就坐實 —— 滑入時不磨、坐下去是面接觸（硬規則 19）。
    #   下表面 45° 斜撐：Chassis 地板貼床時自撐，不多長一根支撐。
    lz0, lz1 = D.RACK_LEDGE_Z0, D.RACK_LEDGE_Z1
    ly0, ly1 = D.RACK_LEDGE_Y0, D.RACK_LEDGE_Y1
    xin = xi - sgn * D.RACK_LEDGE_D  # 肩的內端（往機殼內側）
    xroot = xi + sgn * D.CHASSIS_OVERLAP  # 根部反向埋進牆料（硬規則 1）
    la, lb = sorted((xroot, xin))
    wall = wall.fuse(box(la, ly0, lz0, lb, ly1, lz1))
    wall = wall.fuse(
        tri_prism_xz(
            [(xroot, lz0), (xin, lz0), (xroot, lz0 - D.RACK_LEDGE_GUSSET)],
            ly0,
            ly1,
        )
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
    return wall.removeSplitter()


def make_chassis_body():
    """地板、左右牆、後牆真實融合成一個可由 A1 一次列印的基準件。"""
    body = fuse_all([
        make_chassis_floor(),
        make_rear_panel(),
        make_side(True),
        make_side(False),
    ])
    # 球面 detent 與 spline 盲牙都排在最後一次 removeSplitter 之後。
    for is_left in (True, False):
        for s in shroud_detents(is_left):
            body = body.fuse(s)
    for s in shroud_lap_detents(False):
        body = body.fuse(s)
    for s in top_detents():
        body = body.fuse(s)

    cutter = make_mb_socket_cutter()
    for x, y in D.HOLES_MM.values():
        body = body.cut(place_mb_socket_cutter(cutter, x, y))
    # ★ 第十三輪：PCIeBar 的兩個鎖點 —— 同一支盲牙 cutter，軸轉到 +Y。
    #   舊的 Ø2.8 pilot + #6-32 自攻已退役（使用者：壓條根本沒有用）。
    for hx in D.pcie_lock_x():
        body = body.cut(place_pcie_lock_socket(cutter, hx))
    return body


def make_pcie_bar():
    """
    5 mm 厚共享壓條；四壓舌定位擋板，兩顆 `MB_Screw` 鎖進後牆繫樑上的印製盲內牙。

    ★ 第十三輪（使用者：那個 PCIe 壓條根本沒有用）。舊版是 #6-32 **自攻**進 PETG
      的 Ø2.8 盲 pilot —— 保持力全靠塑膠被鋼牙擠開，鎖第二次就滑牙。現在孔裡
      真的有牙（與主板固定同一套已驗證的 ruled-loft）。
      螺絲不新增第九種 STL 的條件是**夾持厚 = PCB_T**：鎖點處挖沉頭凹，凹底剩
      `PCIE_BAR_SEAT_T`，螺絲頭沉進去 —— 後凸也因此比舊版少一個頭高。
    """
    bx0, bx1 = D.pcie_bar_x()
    y_out = D.CASE_REAR
    mount_y = D.pcie_bar_mount_y()
    bar = box(
        bx0,
        mount_y - D.PCIE_BAR_T,
        D.PCIE_BAR_Z0,
        bx1,
        mount_y,
        D.PCIE_BAR_Z1_TOP,
    )
    # 兩個鎖點：沉頭凹（自外表面往內，留 SEAT_T）+ 貫穿的通孔
    seat_y = mount_y - D.PCIE_BAR_SEAT_T
    for hx in D.pcie_lock_x():
        bar = bar.cut(
            bore_y(mount_y - D.PCIE_BAR_T - 0.5, seat_y, hx, D.PCIE_LOCK_Z,
                   D.PCIE_BAR_CBORE_D)
        )
        bar = bar.cut(
            bore_y(mount_y - D.PCIE_BAR_T - 0.5, mount_y + 0.5, hx, D.PCIE_LOCK_Z,
                   D.PCIE_BAR_HOLE_D)
        )
    for cx in D.pcie_centers():
        bar = bar.fuse(
            box(
                cx - D.PCIE_BAR_TAB_W / 2,
                mount_y - 0.5,
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
    # ★ 第十三輪：後緣下伸舌，插進後牆內面新開的槽（與側槽同 z 帶，沿 −Y 插入）。
    #   它給的是側槽給不了的那一格：**−Y 止擋**。舌只伸 TOP_REAR_LIP，槽深多
    #   SLIDE_FIT，所以推到底時是舌的端面抵住槽底，不是頂蓋本體撞牆。
    for tx0, tx1 in D.top_rear_tab_bands():
        top = top.fuse(
            box(tx0, y0 - D.TOP_REAR_LIP, z0 - D.TOP_T, tx1, y0 + D.TOP_FUSE, z0)
        )
    # 後端**半搭接**：切掉上半，滑到底時鑽進後牆頂鉤唇（同樣只有上半）的下方
    # ★ 第十輪：切深加 SLIDE_FIT。第九輪切到剛好 TOP_HOOK_T，於是頂蓋的切面與
    #   鉤唇的底面**共面**——頂蓋要在鉤唇下方磨進去。鉤唇的職責是「限制上抬」，
    #   限位面本來就該留間隙（頂蓋剩 1.20 仍 > 最小可印壁厚）。
    top = top.cut(
        box(x0 - D.TOP_LIP - 1, y0 - 1, z1 - D.TOP_HOOK_T - D.SLIDE_FIT,
            x1 + D.TOP_LIP + 1, D.FLOOR_Y0 + D.TOP_HOOK_D + D.SLIDE_FIT, z1)
    )
    for s in top_detents(grow=0.15):
        top = top.cut(s)
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
    # lv0 托盤下方承托格柵：三橫樑由中央縱樑連成一體，頂面保留 SLIDE_FIT。
    for by in D.RACK_BASE_BEAM_Y:
        parts.append(
            box(
                D.RACK_X0,
                by - D.RACK_BASE_BEAM_W / 2,
                z0,
                D.RACK_POST_X1,
                by + D.RACK_BASE_BEAM_W / 2,
                D.RACK_BASE_Z1,
            )
        )
    parts.append(
        box(
            D.RACK_BASE_SPINE_X - D.RACK_BASE_SPINE_W / 2,
            y0,
            z0,
            D.RACK_BASE_SPINE_X + D.RACK_BASE_SPINE_W / 2,
            y1,
            D.RACK_BASE_Z1,
        )
    )
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

    # 側舌：自橫樑末端伸出，插進側板內面的槽（兩側對稱）。
    # ★ 第十三輪：只有落在 Chassis 側牆 y 範圍內的橫樑才有舌 —— 第三根樑在前罩段，
    #   那裡沒有牆槽，它是純粹坐在前罩承托肩上的承重樑（唯一來源 RACK_RAIL_BEAM_Y）。
    f = D.SLIDE_FIT
    for by in D.RACK_RAIL_BEAM_Y:
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
    fl = D.FLOOR_X0 + D.SLIDE_FIT
    fr = D.FLOOR_X1 - D.SLIDE_FIT
    shell = shell.fuse(
        box(fl, y0, D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT, fr,
            D.SHROUD_Y0 + 0.1, D.FLOOR_T)
    )
    # 四個先進入 Chassis 的後緣切 45° 導入，避免薄搭接殼正面撞上定位邊。
    lead = D.SHROUD_LEAD_IN
    shell = shell.cut(
        tri_prism_xy(
            [(x0 + lt, y0), (x0 + lt, y0 + lead), (x0 + lt - lead, y0)],
            -0.1,
            z1 + 0.1,
        )
    )
    shell = shell.cut(
        tri_prism_xy(
            [(x1 - lt, y0), (x1 - lt, y0 + lead), (x1 - lt + lead, y0)],
            -0.1,
            z1 + 0.1,
        )
    )
    shell = shell.cut(
        tri_prism_yz(
            [(y0, z1 - D.SHROUD_TOP_LAP_T),
             (y0 + lead, z1 - D.SHROUD_TOP_LAP_T),
             (y0, z1 - D.SHROUD_TOP_LAP_T + lead)],
            x0 - 0.1,
            x1 + 0.1,
        )
    )
    floor_z0 = D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT
    shell = shell.cut(
        tri_prism_yz(
            [(y0, floor_z0), (y0 + lead, floor_z0), (y0, floor_z0 + lead)],
            fl - 0.1,
            fr + 0.1,
        )
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
    # ★ 第十三輪：搭接帶補**內壁**，把 Chassis 的牆整片夾在中間（使用者：改成有縫隙
    #   插進去、兩邊夾住，不要單邊凸點）。第十二輪這一帶只有外壁 SHROUD_LAP_T 貼在
    #   牆的外面減薄帶上，牆的內面整片是光的 —— 前罩對牆只有一個方向有料，
    #   側向保持全靠 detent 的摩擦。
    #   內壁只能長在 side_lap_thin_bands()（牆內面沒有滑槽的那一段），再與
    #   SHROUD_INNER_Z0/Z1 取交集：下限讓開 Area B 淨空（右牆內面到主板右緣只有
    #   0.50，內壁是長在板上方的料），上限讓開碟架承托肩的 45° 斜撐底。
    #   **接合塊不可省**：內壁貼的是 Chassis 牆的內面，而前罩主體壁的內面比它外
    #   1.10 mm —— 少了這一塊，內壁就是兩片自由飄浮的板（實測 solids=3）。
    for xw, inward in ((x0 + D.WALL, 1), (x1 - D.WALL, -1)):  # Chassis 牆內面
        ia, ib = sorted((xw + inward * f, xw + inward * (f + D.SHROUD_INNER_T)))
        xbody = (x0 + t) if inward > 0 else (x1 - t)  # 前罩主體壁的內面
        ja, jb = sorted((xbody, ib))
        for tz0, tz1 in side_lap_thin_bands():
            iz0 = max(tz0, D.SHROUD_INNER_Z0)
            iz1 = min(tz1, D.SHROUD_INNER_Z1)
            if iz1 - iz0 < 1.0:
                continue
            # 內壁本體：後端比外壁短 SHROUD_LEAD_IN，讓外壁的 45° 導入先接觸導向；
            # 前端越過分界面 CHASSIS_OVERLAP，才與接合塊有**體積**重疊。
            shell = shell.fuse(
                box(ia, y0 + D.SHROUD_LEAD_IN, iz0,
                    ib, D.SHROUD_Y0 + D.CHASSIS_OVERLAP, iz1)
            )
            # 接合塊只能在 y >= SHROUD_Y0 —— 它的 x 帶落在 Chassis 牆的厚度裡，
            # 往回多 0.1 就是兩件重疊（實測 20.22 mm³）。
            shell = shell.fuse(
                box(ja, D.SHROUD_Y0, iz0, jb, D.SHROUD_Y0 + D.SHROUD_INNER_JOIN, iz1)
            )

    # ★ 第十三輪：前罩段的碟架承托肩。Chassis 只到 BAY_SPLIT_Y，碟架卻一路到
    #   HDD_Y1 —— 前段 49.76 mm 第十二輪底下什麼都沒有。碟架第三根橫樑坐在這條肩上。
    #   貼床端（−Y）做 45° 楔形引入，前罩維持「無支撐」preset。
    lz0, lz1 = D.RACK_LEDGE_Z0, D.RACK_LEDGE_Z1
    ly0, ly1 = D.SHROUD_LEDGE_Y0, D.SHROUD_LEDGE_Y1
    lead = D.SHROUD_LEDGE_LEAD
    for xw, inward in ((x0 + t, 1), (x1 - t, -1)):
        la, lb = sorted((
            xw - inward * D.CHASSIS_OVERLAP,  # 根部反向埋進前罩壁（硬規則 1）
            xw + inward * D.SHROUD_LEDGE_D,
        ))
        shell = shell.fuse(box(la, ly0 + lead, lz0, lb, ly1, lz1))
        shell = shell.fuse(
            tri_prism_yz([(ly0, lz1), (ly0 + lead, lz1), (ly0 + lead, lz0)], la, lb)
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


def make_mb_screw_placed():
    """總成只顯示 B 孔一顆；實印份數由 PART_QTY 展開九顆。"""
    x, y = D.HOLES_MM["B"]
    return place_mb_screw(make_mb_screw(), x, y)


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
    "Chassis_Body": (0.28, 0.48, 0.78, 0.0),
    "Top_MB": (0.72, 0.74, 0.78, 0.55),  # 半透明看內部
    "PCIeBlank": (0.85, 0.85, 0.88, 0.0),
    "PCIeBar": (0.90, 0.35, 0.20, 0.0),
    "MB_Screw": (0.95, 0.55, 0.10, 0.0),
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
        ("Chassis_Body", make_chassis_body, "機殼本體（底板＋左右牆＋後牆一體式）"),
        ("Top_MB", make_top_mb, "頂蓋（單片，自 +Y 滑入）"),
        ("Front_Shroud", make_front_shroud, "前罩_含進氣柵與電源按鈕"),
        ("HDD_Rack", make_hdd_rack, "碟架_四層導軌（平躺，疊在主板前段上方）"),
        ("HDD_Tray", lambda: make_hdd_tray_placed(0), "碟托盤（總成示第 0 層，實印 4 份）"),
        ("PCIeBlank", make_pcie_blank_parked, "PCIe槽蓋（備件，停放於機殼外）"),
        ("PCIeBar", make_pcie_bar, "PCIe壓條（外置；2× MB_Screw 鎖印製盲內牙）"),
        ("MB_Screw", make_mb_screw_placed,
         "印製螺絲（總成示 B 孔一顆；主板 9 + PCIeBar 2 = 11 顆）"),
    ]
    maker_keys = [name for name, _, _ in makers]
    if set(maker_keys) != set(D.STL_NAMES) or len(maker_keys) != len(set(maker_keys)):
        raise SystemExit(
            f"makers/STL_NAMES 不一致：missing={sorted(set(D.STL_NAMES) - set(maker_keys))} "
            f"extra={sorted(set(maker_keys) - set(D.STL_NAMES))}"
        )
    extra_colors = set(PREVIEW_COLORS) - set(D.STL_NAMES)
    if extra_colors:
        raise SystemExit(f"PREVIEW_COLORS 含退役件：{sorted(extra_colors)}")
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
            "MB_Screw": make_mb_screw,
            "HDD_Tray": make_hdd_tray,  # 總成裡是第 0 層，STL 走未平移的原型
        }
        for key, fname in stl_map.items():
            path = os.path.join(STL_DIR, fname)
            # 螺紋是 0.5 mm 的特徵，0.25 的弦差會把牙磨平
            defl = 0.05 if key in ("Chassis_Body", "MB_Screw") else 0.25
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
