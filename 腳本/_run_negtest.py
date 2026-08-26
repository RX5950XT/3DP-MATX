r"""FreeCADCmd 進入點：第十二輪負向測試。

每一組都同時建立「復活的病灶」與現況對照；離開碼 0 只代表所有檢查確實能
區分兩者，不代表實機性能已驗證。

    FreeCADCmd -c <root>\scripts\_run_negtest.py
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


def main():
    import FreeCAD as App
    import Part

    import build_case as B
    import verify_case as V
    from _load_params import load_params

    D = load_params()
    box = V.mk_box
    doc = App.openDocument(os.path.join(V.PATHS["cad"], D.FCSTD_NAME))
    shapes = {obj.Name: obj.Shape for obj in doc.Objects}
    mocks = V.hardware_mocks()
    limit = V.INTERFERE_MAX
    results = []

    def add(name, condition, note):
        results.append((name, bool(condition), note))

    def inside(shape, point):
        return V.pt_inside(shape, *point, 0.02)

    def sweep(shape, dx=0.0, dy=0.0, dz=0.0, steps=12):
        swept = shape
        for i in range(1, steps + 1):
            moved = shape.copy()
            moved.translate(App.Vector(dx * i / steps, dy * i / steps, dz * i / steps))
            swept = swept.fuse(moved)
        return swept

    chassis = shapes["Chassis_Body"]
    top = shapes["Top_MB"]
    shroud = shapes["Front_Shroud"]
    rack = shapes["HDD_Rack"]
    tray = shapes["HDD_Tray"]
    bar = shapes["PCIeBar"]

    # ── 規格 literal／舊佈局 ────────────────────────────────────────
    old_holes = {
        "B": (0.00, 0.00), "C": (-45.72, 0.00), "F": (-203.20, 0.00),
        "R": (20.32, 132.08), "S": (0.00, 132.08), "H": (-45.72, 132.08),
        "J": (-203.20, 132.08), "L": (-45.72, 204.47), "M": (-203.20, 204.47),
    }
    old_pcb = box(
        D.BOARD_LEFT, -22.86, D.BOARD_TOP_Z - D.PCB_T,
        D.BOARD_RIGHT, 220.98, D.BOARD_TOP_Z,
    )
    hole_r = D.PCB_HOLE_D / 2
    for x, y in old_holes.values():
        old_pcb = old_pcb.cut(
            box(x - hole_r, y - hole_r, D.BOARD_TOP_Z - D.PCB_T - 1,
                x + hole_r, y + hole_r, D.BOARD_TOP_Z + 1)
        )
    add("舊 Fig.7 誤讀孔位復活 → PCB 被支撐肩戳穿",
        V.common_vol(old_pcb, chassis) > limit,
        f"{V.common_vol(old_pcb, chassis):.1f} mm³")
    add("現況 Fig.7 九孔 → PCB 與 Chassis 淨空",
        V.common_vol(mocks["主板PCB"], chassis) <= limit,
        f"{V.common_vol(mocks['主板PCB'], chassis):.2f} mm³")

    low_psu = box(
        D.ATX_X0, D.ATX_Y0, D.FLOOR_T,
        D.ATX_X1, D.ATX_Y1, D.FLOOR_T + D.ATX_H,
    )
    add("PSU 放回板下 → 吃掉 PCB",
        V.common_vol(low_psu, mocks["主板PCB"]) > limit,
        f"{V.common_vol(low_psu, mocks['主板PCB']):.0f} mm³")
    add("現況 PSU 上置 → PCB 淨空",
        V.common_vol(mocks["PSU_150x86x140"], mocks["主板PCB"]) <= limit,
        f"{V.common_vol(mocks['PSU_150x86x140'], mocks['主板PCB']):.2f} mm³")

    add("Area A 舊值 50.00 → 低於 Table 6 required",
        50.0 < D.AREA_A_SPEC_REQUIRED,
        f"50.00 < {D.AREA_A_SPEC_REQUIRED:.2f}")
    add("現況 Area A 由 required literal 導出",
        abs(D.AREA_A_CLEARANCE - max(D.COOLER_MAX_H, D.AREA_A_SPEC_REQUIRED)) < 1e-9
        and D.AREA_A_SPEC_REQUIRED == 76.20
        and D.AREA_A_SPEC_RECOMMENDED == 88.90,
        f"{D.AREA_A_CLEARANCE:.2f} / {D.AREA_A_SPEC_REQUIRED:.2f} / {D.AREA_A_SPEC_RECOMMENDED:.2f}")

    # ── 主板盲內牙與印製螺絲 ───────────────────────────────────────
    x, y = D.HOLES_MM["B"]
    placed = B.place_mb_screw(B.make_mb_screw(), x, y)
    phase0 = V.common_vol(placed, chassis)
    phase180_shape = placed.copy()
    phase180_shape.rotate(App.Vector(x, y, 0), App.Vector(0, 0, 1), 180.0)
    phase180 = V.common_vol(phase180_shape, chassis)
    add("現況螺絲工作相位可旋入", phase0 <= limit, f"{phase0:.2f} mm³")
    add("現況螺絲相位轉 180° → 真螺旋牙碰撞", phase180 > limit, f"{phase180:.2f} mm³")

    fake = Part.makeCylinder(D.MB_THREAD_MINOR / 2, D.MB_SCREW_THREAD_LEN)
    fake = B.place_mb_screw(fake, x, y)
    fake180 = fake.copy()
    fake180.rotate(App.Vector(x, y, 0), App.Vector(0, 0, 1), 180.0)
    fake0_v = V.common_vol(fake, chassis)
    fake180_v = V.common_vol(fake180, chassis)
    add("軸對稱假牙復活 → 轉 180° 仍不撞，應被相位檢查拒絕",
        fake0_v <= limit and fake180_v <= limit,
        f"0°/180°={fake0_v:.2f}/{fake180_v:.2f} mm³")

    through = Part.makeCylinder(
        D.MB_THREAD_MAJOR / 2 + D.MB_THREAD_GAP,
        D.SHOULDER_TOP_Z + 1.0,
        App.Vector(x, y, -0.5),
    )
    through_chassis = chassis.cut(through)
    bottom_probe = (x, y, D.MB_SOCKET_BOTTOM_Z - 0.3)
    add("盲孔打穿到地板 → 孔底探點變空",
        not inside(through_chassis, bottom_probe),
        f"probe z={bottom_probe[2]:.2f}")
    add("現況盲孔底保留實料", inside(chassis, bottom_probe),
        f"底料 {D.MB_SOCKET_BOTTOM_MATERIAL:.2f} mm")

    stud = Part.makeCylinder(
        D.MB_THREAD_MAJOR / 2,
        D.PCB_T + 2.0,
        App.Vector(x, y, D.SHOULDER_TOP_Z),
    )
    stud_chassis = chassis.fuse(stud)
    above = (x, y, D.BOARD_TOP_Z + 1.0)
    add("外凸 male stud 復活 → PCB 上方中心有 Chassis 料",
        inside(stud_chassis, above), f"probe z={above[2]:.2f}")
    add("現況 PCB 上方無固定柱", not inside(chassis, above),
        f"probe z={above[2]:.2f}")

    # ── 一體 Chassis 與 A1 ──────────────────────────────────────────
    overlap_point = (D.FLOOR_X0 - D.CHASSIS_OVERLAP / 2, 80.0, D.FLOOR_T / 2)
    slit = box(
        D.FLOOR_X0 - D.CHASSIS_OVERLAP - 0.1, D.FLOOR_Y0, -0.1,
        D.FLOOR_X0 + 0.1, D.BAY_SPLIT_Y, D.FLOOR_T + 0.1,
    )
    no_left_root = chassis.cut(slit)
    add("地板／左牆 overlap 被切斷 → 根部探點變空",
        not inside(no_left_root, overlap_point), "左根無料")
    add("現況地板／左牆根部實心", inside(chassis, overlap_point),
        f"overlap={D.CHASSIS_OVERLAP:.2f} mm")

    old_hook = box(
        min(D.pcie_centers()) - 10.0, D.CASE_REAR - 8.0, D.PCIE_BAR_Z0,
        D.CASE_RIGHT, D.CASE_REAR + 0.5, D.PCIE_BAR_Z1_TOP,
    )
    old_chassis = chassis.fuse(old_hook)
    old_bb = V.obb(old_chassis)
    old_support_y = old_bb.YLength + 2 * 0.62
    add("8 mm keyhole 後凸復活 → normal support 代理超出 A1",
        old_support_y > D.A1_MAX,
        f"Y {old_bb.YLength:.2f} + 1.24 = {old_support_y:.2f}")
    bb = V.obb(chassis)
    add("現況 Chassis 裸件 OBB 在 A1 內",
        max(bb.XLength, bb.YLength, bb.ZLength) <= D.A1_MAX,
        f"{bb.XLength:.2f}×{bb.YLength:.2f}×{bb.ZLength:.2f}")

    stale_keys = {"Bottom_Tray", "Rear_IO_PCIe", "Side_Left_MB", "Side_Right_MB", "MB_Nut"}
    add("現況 CAD 沒有退役四件與 MB_Nut",
        not (set(shapes) & stale_keys), f"殘留={sorted(set(shapes) & stale_keys)}")
    add("現況 CAD 可列印物件集合等於 manifest",
        set(shapes) == set(D.STL_NAMES),
        f"{len(shapes)}/{len(D.STL_NAMES)}")

    # ── HDD Rack 底部格柵／舊 HDD 病灶 ─────────────────────────────
    zc = (D.RACK_Z0 + D.RACK_BASE_Z1) / 2
    center = (D.RACK_BASE_SPINE_X, D.RACK_BASE_BEAM_Y[1], zc)
    grid_cut = box(
        center[0] - 2.0, center[1] - 2.0, D.RACK_Z0 - 0.1,
        center[0] + 2.0, center[1] + 2.0, D.RACK_BASE_Z1 + 0.1,
    )
    rack_broken = rack.cut(grid_cut)
    add("格柵中央交叉點切掉 → 中央載荷路徑斷",
        not inside(rack_broken, center), "center probe empty")
    add("現況三橫樑／中央縱樑交叉點實心", inside(rack, center),
        f"z={zc:.2f}")

    gap_fill = box(
        center[0] - 3.0, center[1] - 3.0, D.RACK_BASE_Z1,
        center[0] + 3.0, center[1] + 3.0, D.HDD_Z0 + 0.2,
    )
    rack_zero_gap = rack.fuse(gap_fill)
    tray0 = B.make_hdd_tray_placed(0)
    add("格柵抬到 lv0 托盤底 → 零間隙／干涉",
        V.common_vol(rack_zero_gap, tray0) > limit,
        f"{V.common_vol(rack_zero_gap, tray0):.2f} mm³")
    add("現況格柵與 lv0 托盤保留滑配",
        V.common_vol(rack, tray0) <= limit,
        f"{V.common_vol(rack, tray0):.2f} mm³")

    connector_post = box(
        D.HDD_X1, D.TRAY_Y0, D.RACK_Z0,
        D.HDD_X1 + D.RACK_WALL, D.HDD_Y1, D.RACK_TOP_Z1,
    )
    connector_hit = max(
        V.common_vol(connector_post, mocks[f"HDD_L{level}_接頭"])
        for level in range(D.HDD_LEVELS)
    )
    add("右立板貼回 HDD 接頭端面 → 四層接頭區被佔",
        connector_hit > limit, f"{connector_hit:.0f} mm³")
    add("現況四層 HDD 接頭區淨空",
        max(V.common_vol(rack, mocks[f"HDD_L{level}_接頭"])
            for level in range(D.HDD_LEVELS)) <= limit,
        "4/4 clear")

    card230_hit = 0.0
    y_inner = D.CASE_REAR + D.WALL
    for cx in D.pcie_centers():
        card230 = box(
            cx - D.PCIE_CARD_HALF_W, y_inner, D.PCIE_CARD_Z0,
            cx + D.PCIE_CARD_HALF_W, y_inner + 230.0, D.PCIE_CARD_Z1,
        )
        card230_hit = max(card230_hit, V.common_vol(card230, rack))
    add("PCIe 卡長復活為 230 → 插進置中 Rack", card230_hit > limit,
        f"{card230_hit:.0f} mm³")
    add("現況 189 mm PCIe 卡讓開 Rack",
        max(V.common_vol(rack, mocks[f"PCIe{i}_card"])
            for i in range(D.PCIE_COUNT)) <= limit,
        "4/4 clear")

    old_pitch_tray = B.make_hdd_tray()
    old_pitch_tray.translate(App.Vector(0, 0, D.tray_z0(0) + D.HDD_H + D.TRAY_T))
    old_gap = old_pitch_tray.distToShape(mocks["HDD_L0"])[0]
    new_gap = B.make_hdd_tray_placed(1).distToShape(mocks["HDD_L0"])[0]
    add("舊 tray pitch 復活 → HDD 頂與上層托盤貼死", old_gap < 1e-6,
        f"gap={old_gap:.4f}")
    add("現況層間氣隙非零", new_gap >= 1.0 - 1e-6,
        f"gap={new_gap:.2f}")

    # ── Top／Front ──────────────────────────────────────────────────
    detents = B.top_detents()
    no_top_detent = chassis
    for detent in B.top_detents(0.05):
        no_top_detent = no_top_detent.cut(detent)
    add("Top detent 從 Chassis 削掉 → 公球交集歸零",
        max(V.common_vol(no_top_detent, d) for d in detents) <= 0.05,
        "0/2 male")
    add("現況 Top 兩顆公球與 Chassis 融合",
        min(V.common_vol(chassis, d) for d in detents) > 0.05,
        "2/2 male")

    top_filled = top
    for detent in detents:
        top_filled = top_filled.fuse(detent)
    add("Top 母坑填回 → 與 Chassis 公球碰撞",
        V.common_vol(top_filled, chassis) > limit,
        f"{V.common_vol(top_filled, chassis):.2f} mm³")
    add("現況 Top 母坑讓開公球",
        V.common_vol(top, chassis) <= limit,
        f"{V.common_vol(top, chassis):.2f} mm³")

    old_engagement = D.TOP_LIP - 2 * D.TOP_FIT_GAP
    add("Top 舊算法復活 → 側舌咬合只剩 0.40 mm",
        old_engagement < 1.0, f"{old_engagement:.2f} mm")
    add("現況 Top 側舌咬合 >=1 mm", D.TOP_LIP >= 1.0,
        f"{D.TOP_LIP:.2f} mm")

    y0 = D.SHROUD_Y0 - D.SHROUD_LAP
    lead_empty = (
        D.CASE_LEFT + D.SHROUD_LAP_T - 0.25,
        y0 + 0.25,
        90.0,
    )
    shroud_no_lead = shroud.fuse(
        box(lead_empty[0] - 0.3, lead_empty[1] - 0.3, 89.5,
            lead_empty[0] + 0.3, lead_empty[1] + 0.3, 90.5)
    )
    add("Front 導入面填回 → leading probe 變實心",
        inside(shroud_no_lead, lead_empty), "lead-in missing")
    add("現況 Front 45° leading probe 是空的",
        not inside(shroud, lead_empty), f"lead={D.SHROUD_LEAD_IN:.2f} mm")
    add("Front 舊搭接 12 mm 復活 → 未達本輪 14 mm literal",
        12.0 < D.SHROUD_LAP, f"12.0 < {D.SHROUD_LAP:.1f}")

    shroud_nofloor = shroud.cut(
        box(D.CASE_LEFT, D.SHROUD_Y0 - D.SHROUD_LAP - 1, -0.5,
            D.CASE_RIGHT, D.CASE_FRONT + 1, D.FLOOR_T)
    )
    floor_probe = (-150.0, D.CASE_FRONT - 20.0, D.FLOOR_T / 2)
    add("Front 地板削掉 → 前段底部開口", not inside(shroud_nofloor, floor_probe),
        "floor probe empty")
    add("現況 Front 地板實心", inside(shroud, floor_probe),
        f"z={floor_probe[2]:.2f}")

    front_public = (
        B.shroud_detents(True) + B.shroud_detents(False)
        + B.shroud_lap_detents(False)
    )
    shroud_filled = shroud
    for detent in front_public:
        shroud_filled = shroud_filled.fuse(detent)
    add("Front detent 母坑填回 → Chassis 公球碰撞",
        V.common_vol(shroud_filled, chassis) > limit,
        f"{V.common_vol(shroud_filled, chassis):.2f} mm³")
    add("現況 Front／Chassis 落位不干涉",
        V.common_vol(shroud, chassis) <= limit,
        f"{V.common_vol(shroud, chassis):.2f} mm³")

    # ── PCIe 鎖點盲內牙／Bar（第十三輪：#6-32 自攻 → 印製盲內牙）─────
    mount_y = D.pcie_bar_mount_y()
    lock_x = D.pcie_lock_x()

    socket_cut = Part.makeCylinder(
        D.MB_THREAD_MAJOR / 2 + 0.3,
        D.PCIE_RIB_D + D.WALL + 1.0,
        App.Vector(lock_x[0], mount_y - 0.1, D.PCIE_LOCK_Z),
        App.Vector(0, 1, 0),
    )
    pierced = chassis.cut(socket_cut)
    blind_probe = (lock_x[0], D.pcie_lock_socket_end() + 0.3, D.PCIE_LOCK_Z)
    add("PCIe 盲牙打穿內壁 → 盲端 probe 變空",
        not inside(pierced, blind_probe), "through hole")
    add("現況 PCIe 盲牙盲端有料", inside(chassis, blind_probe),
        f"{(D.CASE_REAR + D.WALL) - D.pcie_lock_socket_end():.2f} mm inner wall")

    # 盲牙必須是真螺旋：把螺絲相位轉 180° 一定要撞（排除軸對稱假牙）
    turned = B.place_pcie_lock_screw(B.make_mb_screw(), lock_x[0])
    turned.rotate(App.Vector(lock_x[0], 0, D.PCIE_LOCK_Z), App.Vector(0, 1, 0), 180.0)
    add("壓條螺絲相位轉 180° → 撞盲內牙", V.common_vol(turned, chassis) > limit,
        f"{V.common_vol(turned, chassis):.2f} mm³")
    aligned = B.place_pcie_lock_screw(B.make_mb_screw(), lock_x[0])
    add("現況壓條螺絲工作相位可旋入", V.common_vol(aligned, chassis) <= limit,
        f"{V.common_vol(aligned, chassis):.2f} mm³")

    hole_y = mount_y - D.PCIE_BAR_SEAT_T / 2
    hole_probe = (lock_x[0], hole_y, D.PCIE_LOCK_Z)
    filled_hole = bar.fuse(
        Part.makeCylinder(
            D.PCIE_BAR_HOLE_D / 2,
            D.PCIE_BAR_T + 1.0,
            App.Vector(lock_x[0], mount_y - D.PCIE_BAR_T - 0.5, D.PCIE_LOCK_Z),
            App.Vector(0, 1, 0),
        )
    )
    add("PCIeBar 通孔填回 → 孔中心變實心", inside(filled_hole, hole_probe),
        "clearance hole missing")
    add("現況 PCIeBar 兩通孔開通",
        all(not inside(bar, (hx, hole_y, D.PCIE_LOCK_Z)) for hx in lock_x),
        "2/2 clear")

    cbore_probe = (lock_x[0], mount_y - D.PCIE_BAR_T + 0.4, D.PCIE_LOCK_Z)
    filled_cbore = bar.fuse(
        Part.makeCylinder(
            D.PCIE_BAR_CBORE_D / 2,
            D.PCIE_BAR_T - D.PCIE_BAR_SEAT_T,
            App.Vector(lock_x[0], mount_y - D.PCIE_BAR_T, D.PCIE_LOCK_Z),
            App.Vector(0, 1, 0),
        )
    )
    add("PCIeBar 沉頭凹填回 → 螺絲頭沒地方沉", inside(filled_cbore, cbore_probe),
        "counterbore missing")
    add("現況 PCIeBar 沉頭凹開通", not inside(bar, cbore_probe),
        f"depth {D.PCIE_BAR_T - D.PCIE_BAR_SEAT_T:.2f} >= head {D.MB_SCREW_HEAD_H}")

    first_cx = D.pcie_centers()[0]
    tab_probe = (
        first_cx,
        (mount_y + D.CASE_REAR) / 2,
        (D.PCIE_BAR_Z0 + D.PCIE_BAR_Z1) / 2,
    )
    missing_tab = bar.cut(
        box(first_cx - D.PCIE_BAR_TAB_W / 2 - 0.2, mount_y - 0.6, D.PCIE_BAR_Z0 - 0.2,
            first_cx + D.PCIE_BAR_TAB_W / 2 + 0.2, D.CASE_REAR + D.PCIE_BAR_TAB_D + 0.2,
            D.PCIE_BAR_Z1 + 0.2)
    )
    add("PCIeBar 少一壓舌 → 第一槽 probe 變空", not inside(missing_tab, tab_probe),
        "tab0 missing")
    add("現況 PCIeBar 四壓舌皆實心",
        all(inside(bar, (cx, tab_probe[1], tab_probe[2])) for cx in D.pcie_centers()),
        "4/4 solid")

    screw_mocks = [B.place_pcie_lock_screw(B.make_mb_screw(), hx)
                   for hx in lock_x]
    bar_pull = sweep(bar, dy=-1.0, steps=4)
    add("兩顆壓條螺絲在位 → Bar 外抽會撞螺絲頭",
        all(V.common_vol(bar_pull, screw) > limit for screw in screw_mocks),
        str([round(V.common_vol(bar_pull, screw), 1) for screw in screw_mocks]))
    bar_exit = sweep(bar, dy=-(D.PCIE_BAR_T + D.PCIE_RIB_D + 10.0))
    add("卸兩螺絲後 → Bar 沿 −Y 抽離 Chassis",
        V.common_vol(bar_exit, chassis) <= limit,
        f"{V.common_vol(bar_exit, chassis):.2f} mm³")

    held = sum(
        V.common_vol(sweep(mocks[f"PCIe{i}_耳keepout"], dz=D.PCIE_ENGAGE), bar) > limit
        for i in range(D.PCIE_COUNT)
    )
    add("Bar 在位 → 四槽都不能抬升", held == D.PCIE_COUNT, f"{held}/4")
    cleared = max(
        V.common_vol(sweep(mocks[f"PCIe{i}_card"], dz=D.PCIE_ENGAGE), chassis)
        for i in range(D.PCIE_COUNT)
    )
    add("拆 Bar 後 → 四張卡可抬升", cleared <= limit, f"max={cleared:.2f} mm³")

    actual_ymin = min(
        [V.obb(chassis).YMin, V.obb(bar).YMin]
        + [V.obb(screw).YMin for screw in screw_mocks]
    )
    measured = D.CASE_REAR - actual_ymin
    add("只把 Bar 厚度當後凸 → 少報完整螺絲頭",
        D.PCIE_BAR_T < measured, f"{D.PCIE_BAR_T:.2f} < {measured:.2f}")
    add("現況 install_depth 對上 Chassis+Bar+螺絲頭真幾何",
        abs(D.install_depth_mm() - (D.CASE_D + measured)) < 0.05,
        f"{D.install_depth_mm():.2f} vs {D.CASE_D + measured:.2f}")

    # ── 其餘仍有效的邊界病灶 ───────────────────────────────────────
    skirt = box(D.CASE_LEFT, D.CASE_REAR, -10.0, D.CASE_RIGHT, D.CASE_FRONT, 0.0)
    add("舊下裙復活 → z<0 有料", V.obb(skirt).ZMin < -0.05,
        f"ZMin={V.obb(skirt).ZMin:.1f}")
    add("現況 Chassis 無 z<0 料", V.obb(chassis).ZMin >= -0.05,
        f"ZMin={V.obb(chassis).ZMin:.2f}")

    old_t = 1.0
    old_penetration = 6.35 - old_t
    add("HDD 托盤厚復活為 1 mm → 螺絲穿入超標",
        not (2.39 <= old_penetration <= 3.56),
        f"{old_penetration:.2f} mm")
    penetration = 6.35 - D.TRAY_T
    add("現況 HDD 螺絲穿入落在 SFF-8301 區間",
        2.39 <= penetration <= 3.56,
        f"{penetration:.2f} mm")

    button = mocks["電源按鈕本體"]
    add("現況 22 mm 深電源按鈕不撞印件",
        max(V.common_vol(button, shape) for shape in shapes.values()) <= limit,
        "clear")
    button_bad = box(
        -100.0 - D.PWR_BTN_NUT_D / 2,
        D.CASE_FRONT - D.TRAY_FACE_T - D.PWR_BTN_DEPTH,
        60.0 - D.PWR_BTN_NUT_D / 2,
        -100.0 + D.PWR_BTN_NUT_D / 2,
        D.CASE_FRONT - D.TRAY_FACE_T,
        60.0 + D.PWR_BTN_NUT_D / 2,
    )
    add("按鈕移到 Rack X/Z 帶 → 撞印件",
        max(V.common_vol(button_bad, rack), V.common_vol(button_bad, shroud),
            V.common_vol(button_bad, tray)) > limit,
        "bad placement collides")

    gap_probe = box(
        D.HDD_X0 + 5, D.TRAY_Y0 + 5, D.RACK_TOP_Z1 + 0.05,
        D.HDD_X1 - 5, D.BAY_SPLIT_Y - 5, D.INNER_TOP_Z - 0.05,
    )
    gap_bridge = box(
        D.HDD_X0 + 5, D.TRAY_Y0 + 5, D.RACK_TOP_Z1 - 0.1,
        D.HDD_X1 - 5, D.BAY_SPLIT_Y - 5, D.INNER_TOP_Z + 0.1,
    )
    add("Top/Rack 間隙填料復活 → 零間隙檢查應紅",
        V.common_vol(rack.fuse(gap_bridge), top) > limit,
        f"{V.common_vol(rack.fuse(gap_bridge), top):.2f} mm³")
    add("現況 Top/Rack 間隙為空",
        max(V.common_vol(gap_probe, shape) for shape in shapes.values()) <= limit,
        f"gap={D.RACK_TOP_GAP:.2f} mm")

    old_names = {"底板_主板托盤.stl", "後牆_IO與PCIe.stl", "左側板_主板段.stl",
                 "右側板_主板段.stl", "主板壓帽.stl"}
    actual_stl = {
        name for name in os.listdir(V.STL_DIR)
        if name.lower().endswith(".stl")
    }
    add("現況 STL 目錄沒有退役輸出", not (actual_stl & old_names),
        f"stale={sorted(actual_stl & old_names)}")
    add("現況 STL 目錄雙向等於 manifest",
        actual_stl == set(D.STL_NAMES.values()),
        f"{len(actual_stl)}/{len(D.STL_NAMES)}")

    # ── 第十三輪：五項使用者實印回報 ─────────────────────────────
    # ① I/O 深度基準（Fig.4 側視 12.27）。舊式 CASE_REAR = 板緣 − MARGIN − WALL
    #    讓後牆內面落在 −10.66，而連接器面在 −11.30 → 板推不到底。
    conn = mocks["IO連接器區"]
    add("現況 I/O 連接器區與 Chassis 不干涉",
        V.common_vol(conn, chassis) <= limit,
        f"{V.common_vol(conn, chassis):.2f} mm³")
    old_rear_wall = box(
        D.IO_X0, D.BOARD_REAR - 0.5 - D.WALL, D.IO_Z0,
        D.IO_X1, D.BOARD_REAR - 0.5, D.IO_Z1,
    )
    add("後牆退回舊基準（板緣 − MARGIN − WALL）→ 壓到 I/O 連接器",
        V.common_vol(conn, old_rear_wall) > limit,
        f"{V.common_vol(conn, old_rear_wall):.2f} mm³")

    # ② 碟架承托肩
    ledge_probe = (
        D.CASE_LEFT + D.WALL + D.RACK_LEDGE_D / 2,
        (D.RACK_LEDGE_Y0 + D.RACK_LEDGE_Y1) / 2,
        D.RACK_LEDGE_Z1 - 0.5,
    )
    ledge_cut = box(
        D.CASE_LEFT + D.WALL - 0.2, D.RACK_LEDGE_Y0 - 0.2,
        D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET - 0.2,
        D.CASE_LEFT + D.WALL + D.RACK_LEDGE_D + 0.2, D.RACK_LEDGE_Y1 + 0.2,
        D.RACK_LEDGE_Z1 + 0.2,
    )
    add("碟架承托肩切掉 → 承重面 probe 變空",
        not inside(chassis.cut(ledge_cut), ledge_probe), "ledge missing")
    add("現況碟架承托肩實心", inside(chassis, ledge_probe),
        f"{D.RACK_LEDGE_D} mm 承重寬")
    shroud_ledge_probe = (
        D.CASE_LEFT + D.SHROUD_WALL + D.SHROUD_LEDGE_D / 2,
        (D.SHROUD_LEDGE_Y0 + D.SHROUD_LEDGE_Y1) / 2,
        D.RACK_LEDGE_Z1 - 0.5,
    )
    add("現況前罩承托肩實心（碟架前段不再是懸臂）",
        inside(shroud, shroud_ledge_probe),
        f"懸臂 {D.HDD_Y1 - max(D.RACK_BEAM_Y):.2f} mm")

    # ③ PCIe 45° 尖頂：頂改回矩形 → 開孔頂又是水平懸空
    cx0 = D.pcie_centers()[0]
    y_wall = D.CASE_REAR + D.WALL / 2
    # 探點要放在**收斂線之外**：尖頂的中線在任何高度都還是開孔（空的），
    # 有料的是 |x − cx| 大於該高度半寬的地方。
    apex_frac = 0.6
    apex_half = (1.0 - apex_frac) * D.PCIE_OPEN_W / 2
    apex_probe = (
        cx0 + apex_half + 0.4,
        y_wall,
        D.PCIE_OPEN_Z1 + D.PCIE_APEX_H * apex_frac,
    )
    squared = chassis.cut(
        box(cx0 - D.PCIE_OPEN_W / 2, D.CASE_REAR - D.PCIE_RIB_D - 0.5, D.PCIE_OPEN_Z1,
            cx0 + D.PCIE_OPEN_W / 2, D.CASE_REAR + D.WALL + 0.5, D.PCIE_APEX_Z)
    )
    add("開孔頂改回矩形 → 尖頂收斂區被挖空（水平懸空回來了）",
        not inside(squared, apex_probe), "square top")
    add("現況尖頂收斂區有料（45°，切片器不生支撐）",
        inside(chassis, apex_probe), "45deg apex")

    # ④ 後牆頂蓋槽
    slot_bands = D.top_rear_tab_bands()
    xm = (slot_bands[1][0] + slot_bands[1][1]) / 2
    y_slot = D.CASE_REAR + D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT) / 2
    z_slot = D.INNER_TOP_Z - D.TOP_T / 2
    filled_slot = chassis.fuse(
        box(xm - 5.0, D.CASE_REAR + D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT),
            D.INNER_TOP_Z - D.TOP_T,
            xm + 5.0, D.CASE_REAR + D.WALL, D.INNER_TOP_Z + D.SLIDE_FIT)
    )
    add("後牆頂蓋槽填實 → Top 後舌插不進去",
        inside(filled_slot, (xm, y_slot, z_slot)), "slot filled")
    add("現況後牆頂蓋槽開通（−Y 止擋面）",
        not inside(chassis, (xm, y_slot, z_slot)), "slot open")
    tab_probe13 = (xm, D.FLOOR_Y0 + D.TOP_FIT_GAP - D.TOP_REAR_LIP / 2, z_slot)
    add("現況 Top 後舌實心", inside(top, tab_probe13), "rear tab solid")

    # ⑤ 前罩 U 形雙壁夾持
    y_lap = D.SHROUD_Y0 - D.SHROUD_LAP / 2
    z_lap = (D.SHROUD_INNER_Z0 + D.SHROUD_INNER_Z1) / 2
    x_in = D.CASE_LEFT + D.WALL + D.SLIDE_FIT + D.SHROUD_INNER_T / 2
    inner_cut = box(
        D.CASE_LEFT + D.WALL, D.SHROUD_Y0 - D.SHROUD_LAP - 0.2, D.SHROUD_INNER_Z0 - 0.2,
        D.CASE_LEFT + D.WALL + D.SLIDE_FIT + D.SHROUD_INNER_T + 0.2,
        D.SHROUD_Y0 + 0.2, D.SHROUD_INNER_Z1 + 0.2,
    )
    add("前罩內壁刪掉 → 只剩單邊搭接（牆的內面又是光的）",
        not inside(shroud.cut(inner_cut), (x_in, y_lap, z_lap)), "inner wall gone")
    add("現況前罩內壁實心（牆被兩片夾住）",
        inside(shroud, (x_in, y_lap, z_lap)), f"{D.SHROUD_INNER_T} mm")

    # ⑥ 第十四輪：MB_Screw 頭頂十字工具槽
    zc = D.MB_SCREW_CROSS_DEPTH / 2
    q = D.MB_SCREW_CROSS_W / 2 + 0.4
    raw_screw = B.make_mb_screw()
    cross_fill = B._mb_screw_cross().common(
        box(-9.0, -9.0, 0.0, 9.0, 9.0, D.MB_SCREW_HEAD_H)
    )
    add("十字槽填回 → 槽心探點變實心（起子插不進去）",
        inside(raw_screw.fuse(cross_fill), (0.0, 0.0, zc)), "cross recess missing")
    add("現況十字槽是空腔", not inside(raw_screw, (0.0, 0.0, zc)),
        f"深 {D.MB_SCREW_CROSS_DEPTH} / 臂寬 {D.MB_SCREW_CROSS_W}")
    # 非 vacuous：圓孔也會讓「槽心是空的」通過，象限角那條才分得出十字
    round_hole = Part.makeCylinder(D.MB_SCREW_CROSS_L / 2, D.MB_SCREW_CROSS_DEPTH)
    round_hole.translate(App.Vector(0, 0, -0.001))
    add("十字換成同徑圓孔 → 象限角變空（象限角探點不是裝飾）",
        not inside(raw_screw.fuse(cross_fill).cut(round_hole), (q, q, zc)),
        "round recess is not a cross")
    add("現況象限角實心（是十字不是圓孔）", inside(raw_screw, (q, q, zc)),
        f"象限角 ({q:.2f}, {q:.2f})")

    # ⑦ 第十四輪：PCIe 窗框底緣的 45° 引入楔
    fx0, fx1 = D.pcie_frame_x()
    fz0 = D.pcie_frame_z()[0]
    y_out = D.CASE_REAR
    wedge = B.tri_prism_yz(
        [(y_out, fz0 - D.PCIE_FRAME_LEAD), (y_out, fz0), (y_out - D.PCIE_FRAME_LEAD, fz0)],
        fx0 - 0.1, fx1 + 0.1,
    )

    cs = D.pcie_centers()
    ox0 = min(cs) - D.PCIE_OPEN_W / 2
    ox1 = max(cs) + D.PCIE_OPEN_W / 2

    def band_overhangs(shape):
        return [
            bb for a, sl, bb in V.support_overhangs(shape)
            if bb.XMax > ox0 and bb.XMin < ox1
            and bb.ZMax > D.FLOOR_T and bb.ZMin < D.PCIE_TIE_Z1
        ]

    add("窗框 45° 引入楔切掉 → PCIe 窗區又冒出需支撐的水平朝下面",
        len(band_overhangs(chassis.cut(wedge))) > 0, "flat frame underside is back")
    add("現況 PCIe 窗區一片需支撐朝下面都沒有",
        len(band_overhangs(chassis)) == 0,
        f"門檻 {D.SUPPORT_THRESHOLD_ANGLE:g}°（= preset support_threshold_angle）")

    App.closeDocument(doc.Name)
    all_ok = True
    for name, condition, note in results:
        print(("PASS " if condition else "MISS ") + name + " — " + note)
        all_ok = all_ok and condition
    print(f"NEGTEST {sum(1 for _, passed, _ in results if passed)}/{len(results)}")
    print("NEGTEST_OK" if all_ok else "NEGTEST_FAILED")
    return 0 if all_ok else 1


code = 1
try:
    code = main()
except Exception:
    traceback.print_exc()

try:
    sys.stdout.flush()
except Exception:
    pass
os._exit(code)
