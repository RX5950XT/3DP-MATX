"""FreeCADCmd 進入點：負向測試。離開碼 0 = 每條檢查都示範得出它抓得到舊病灶。

`verify` 全綠只證明「我檢查的都對」。這支把修掉的缺陷重新塞回幾何裡，
確認對應的檢查真的會紅——否則那條檢查可能只是跟著參數一起錯（vacuous check）。

    FreeCADCmd -c <root>\\scripts\\_run_negtest.py
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
    S = {o.Name: o.Shape for o in doc.Objects}
    mocks = V.hardware_mocks()
    MAX = V.INTERFERE_MAX
    res = []

    def add(name, cond, note):
        res.append((name, cond, note))

    tray, rear, rack = S["Bottom_Tray"], S["Rear_IO_PCIe"], S["HDD_Rack"]
    side_l, side_r, top = S["Side_Left_MB"], S["Side_Right_MB"], S["Top_MB"]
    bar, dtray = S["PCIeBar"], S["HDD_Tray"]

    # ══ 仍然有效的舊病灶（第七輪之前）═══════════════════════════════
    # 1. 舊九孔座標 → 用舊座標鑽孔的主板會被新柱子戳穿
    OLD_HOLES = {
        "B": (0.00, 0.00), "C": (-45.72, 0.00), "F": (-203.20, 0.00),
        "R": (20.32, 132.08), "S": (0.00, 132.08), "H": (-45.72, 132.08),
        "J": (-203.20, 132.08), "L": (-45.72, 204.47), "M": (-203.20, 204.47),
    }
    pcb_old = box(D.BOARD_LEFT, -22.86, D.BOARD_TOP_Z - D.PCB_T, D.BOARD_RIGHT, 220.98,
                  D.BOARD_TOP_Z)
    r = D.PCB_HOLE_D / 2
    for hx, hy in OLD_HOLES.values():
        pcb_old = pcb_old.cut(
            box(hx - r, hy - r, D.BOARD_TOP_Z - D.PCB_T - 1, hx + r, hy + r, D.BOARD_TOP_Z + 1)
        )
    add("舊九孔座標 → 主板被柱子戳穿", V.common_vol(pcb_old, tray) > MAX,
        f"{V.common_vol(pcb_old, tray):.0f} mm3")
    add("現況 → 九根柱全部穿過孔", V.common_vol(mocks["主板PCB"], tray) <= MAX,
        f"{V.common_vol(mocks['主板PCB'], tray):.2f} mm3")

    # 2. 電源放回板下 → 直接吃掉主板
    psu_low = box(D.ATX_X0, D.ATX_Y0, D.FLOOR_T, D.ATX_X1, D.ATX_Y1, D.FLOOR_T + D.ATX_H)
    add("電源放回板下 → 直接吃掉主板", V.common_vol(psu_low, mocks["主板PCB"]) > MAX,
        f"{V.common_vol(psu_low, mocks['主板PCB']):.0f} mm3")

    # 3. 螺紋是真螺旋（相位轉 180° 必撞；軸對稱的假牙怎麼轉都不會撞）
    nut = B.make_mb_nut()
    hx, hy = D.HOLES_MM["B"]
    r0 = V.common_vol(B.place_mb_nut(nut, hx, hy, D.BOARD_TOP_Z), tray)
    nr = B.place_mb_nut(nut, hx, hy, D.BOARD_TOP_Z)
    nr.rotate(App.Vector(hx, hy, 0), App.Vector(0, 0, 1), 180.0)
    r180 = V.common_vol(nr, tray)
    add("現況 → 真螺旋", r0 <= MAX < r180, f"轉 0°/180° 干涉 {r0:.2f}/{r180:.2f}")

    # ══ 第八輪新增的病灶 ═══════════════════════════════════════════
    # 4. 下裙回來 → 「z<0 不准有料」要紅
    skirt = box(D.CASE_LEFT, D.CASE_REAR, -10.0, D.CASE_RIGHT, D.CASE_FRONT, 0.0)
    add("舊下裙塞回 → 「z<0 無料」應紅", skirt.BoundBox.ZMin < -0.05,
        f"裙底 {skirt.BoundBox.ZMin:.1f}")
    lo = min(V.obb(s).ZMin for k, s in S.items() if k != "PCIeBlank")
    add("現況 → 沒有任何料在 z<0", lo >= -0.05, f"最低 {lo:.2f}")

    # 5. 直立碟艙回來 → 碟頂高過**電源決定的內頂**（＝電源下移後真正的基準線），
    #    而且還要多吃 45 mm 深度。基準必須是電源那條，不是現況的 INNER_TOP_Z ——
    #    現況的內頂本來就是碟撐出來的，拿它當基準這條檢查會自己把自己抵銷掉。
    # ★ 第十輪再鎖一次基準：電源升到內頂之後，直立碟艙**不再是高度瓶頸**
    #   （直立碟頂 171.4 < 內頂 176.82），舊的比法會自己變綠 —— 那就是 vacuous。
    #   現在改比**深度**：兩種佈局各自在主板段之外多吃多少 mm。
    UPRIGHT_BAY_D = 65.10  # 第七輪直立 2×2 碟艙的深度（tasks/todo.md 第八輪的佈局掃描）
    flat_bay_d = D.CASE_FRONT - D.BAY_SPLIT_Y
    add("舊直立 2×2 塞回 → 主板段之外多吃的深度變大", UPRIGHT_BAY_D > flat_bay_d,
        f"直立 {UPRIGHT_BAY_D:.2f} > 平躺 {flat_bay_d:.2f}（差 {UPRIGHT_BAY_D - flat_bay_d:.2f}）")
    add("現況 → 平躺碟頂在內頂之下", D.HDD_TOP_Z <= D.INNER_TOP_Z,
        f"{D.HDD_TOP_Z:.1f} <= {D.INNER_TOP_Z:.1f}")

    # 6. 內置壓條回來 → 「壓條不得伸進機殼內」要紅
    y_in = D.CASE_REAR + D.WALL
    bar_old = box(-50.0, y_in, D.PCIE_BAR_Z0, D.CASE_RIGHT - D.WALL, y_in + 9.0, D.PCIE_BAR_Z0 + 4)
    add("舊內置壓條塞回 → 「不得往內突出」應紅", V.obb(bar_old).YMax > y_in + 0.05,
        f"YMax {V.obb(bar_old).YMax:.2f} > 後牆內面 {y_in:.2f}")
    add("現況 → 壓條整條在機殼外", V.obb(bar).YMax <= y_in + 0.05,
        f"YMax {V.obb(bar).YMax:.2f}")

    # 7. 托盤後擋邊長在碟體裡（TRAY_BACK_STOP=0）→ 干涉要紅
    stop_bad = box(D.HDD_X0, D.TRAY_Y0, D.HDD_Z0 + D.TRAY_T, D.HDD_X1,
                   D.TRAY_Y0 + D.TRAY_BACK_STOP, D.HDD_Z0 + D.TRAY_T + D.TRAY_LIP_H)
    hdd0 = mocks["HDD_L0"]
    bad = box(D.HDD_X0, D.TRAY_Y0, D.HDD_Z0 + D.TRAY_T, D.HDD_X1, D.TRAY_Y0 + D.HDD_W,
              D.HDD_Z0 + D.TRAY_T + D.HDD_H)  # 碟不讓開擋邊時的位置
    add("碟不讓開後擋邊 → 擋邊長在碟體裡", V.common_vol(stop_bad, bad) > MAX,
        f"{V.common_vol(stop_bad, bad):.0f} mm3")
    add("現況 → 碟讓開了後擋邊", V.common_vol(stop_bad, hdd0) <= MAX,
        f"{V.common_vol(stop_bad, hdd0):.2f} mm3")

    # 8. 碟陣往後推過 Fig.7 的 Area A/C 界線 → 侵入散熱器空間
    #    ★ 第九輪改用**碟托盤**當代表：碟架在那個高度是開放的碟艙（沒有料），
    #      拿碟架去撞 Area A 只會得到 0 —— 檢查會變成 vacuous。托盤才是那一層的料。
    key_a = [k for k in mocks if k.startswith("淨空_AreaA")][0]
    tray_back = B.make_hdd_tray_placed(0)
    tray_back.translate(App.Vector(0, -20.0, 0))
    add("碟托盤往後 20 mm → 侵入 Area A 淨空", V.common_vol(tray_back, mocks[key_a]) > MAX,
        f"{V.common_vol(tray_back, mocks[key_a]):.0f} mm3")
    add("現況 → 碟架與托盤都不碰 Area A",
        max(V.common_vol(rack, mocks[key_a]),
            max(V.common_vol(B.make_hdd_tray_placed(lv), mocks[key_a])
                for lv in range(D.HDD_LEVELS))) <= MAX,
        f"{V.common_vol(B.make_hdd_tray_placed(0), mocks[key_a]):.2f} mm3")

    # 9. 卡長放回第八輪的 230 → 卡直接插進碟架（碟架置中後兩者 X 帶重疊）
    y_in0 = D.CASE_REAR + D.WALL
    v = 0.0
    for cx in D.pcie_centers():
        card230 = box(cx - D.PCIE_CARD_HALF_W, y_in0, D.PCIE_CARD_Z0,
                      cx + D.PCIE_CARD_HALF_W, y_in0 + 230.0, D.PCIE_CARD_Z1)
        v = max(v, V.common_vol(card230, rack))
    add("卡長放回 230 → 卡插進碟架", v > MAX, f"{v:.0f} mm3")
    vn = max(V.common_vol(rack, mocks[f"PCIe{i}_card"]) for i in range(D.PCIE_COUNT))
    add("現況 → 189.00 的卡讓開碟架", vn <= MAX, f"{vn:.2f} mm3")

    # 10. 頂蓋側舌往上埋進槽頂 → 撞側板（本輪實測 8.64 mm³／側）
    lip_bad = box(D.FLOOR_X0 - D.TOP_LIP, D.FLOOR_Y0, D.INNER_TOP_Z,
                  D.FLOOR_X0, D.BAY_SPLIT_Y, D.INNER_TOP_Z + 1.0)
    add("頂蓋側舌往上埋 → 撞側板牆料", V.common_vol(lip_bad, side_l) > MAX,
        f"{V.common_vol(lip_bad, side_l):.1f} mm3")
    add("現況 → 頂蓋不撞側板", V.common_vol(top, side_l) <= MAX,
        f"{V.common_vol(top, side_l):.2f} mm3")

    # 11. 後牆定位舌往機殼內 → 右邊那片直接戳進主板與 Area B 淨空
    tab_bad = box(D.CASE_RIGHT - D.WALL - D.REAR_TAB_T, y_in - 0.5, D.FLOOR_T,
                  D.CASE_RIGHT - D.WALL, y_in + D.REAR_TAB_D, 150.0)
    v = V.common_vol(tab_bad, mocks["主板PCB"]) + V.common_vol(tab_bad, mocks["淨空_AreaB_15.24"])
    add("定位舌往機殼內 → 戳進主板／Area B", v > MAX, f"{v:.0f} mm3")
    add("現況 → 定位舌長在牆體側", V.common_vol(rear, mocks["主板PCB"]) <= MAX,
        f"{V.common_vol(rear, mocks['主板PCB']):.2f} mm3")

    # 12. detent 半徑放回 1.2 → 球從機殼**外表面**戳出來（單一長方體破功）
    #    ★ 第十輪重新定錨：detent 公母對調之後球長在側板槽底、往機殼內凸，
    #      舊的「戳進電源本體」已經不成立（電源也往右讓開了）——那條會永遠綠。
    #      現在管住它的是另一邊：球心埋在槽底後方，半徑一大就從側板外表面凸出來。
    env_lb = box(D.CASE_LEFT, D.CASE_REAR, -1.0, D.CASE_RIGHT, D.CASE_FRONT, D.OUTER_TOP_Z)
    cx_bad = D.CASE_LEFT + D.WALL - (D.REAR_TAB_T + D.SLIDE_FIT + 1.2 - D.DETENT_DEPTH)
    ball_bad = Part.makeSphere(1.2)
    ball_bad.translate(App.Vector(cx_bad, y_in + D.REAR_TAB_D / 2, 100.0))
    out_v = ball_bad.cut(env_lb).Volume
    add("detent R=1.2 → 球從側板外表面戳出來", out_v > MAX, f"外溢 {out_v:.2f} mm3")
    add("現況 → detent 球被裁在外表面之內（側板不外溢）",
        side_l.cut(env_lb).Volume <= MAX, f"{side_l.cut(env_lb).Volume:.2f} mm3")
    add("現況 → 2R <= 舌厚 + 凸出", 2 * D.DETENT_R <= D.REAR_TAB_T + D.DETENT_DEPTH + 1e-6,
        f"2R={2 * D.DETENT_R} <= {D.REAR_TAB_T + D.DETENT_DEPTH}")

    # ══ 第九輪：使用者驗收指出的病灶 ═══════════════════════════════
    y_wall = D.CASE_REAR + D.WALL / 2
    cs_sorted = sorted(D.pcie_centers())
    rib_zs = [D.PCIE_Z0 - 1.0, (D.PCIE_Z0 + D.PCIE_Z1) / 2, D.PCIE_Z1,
              D.PCIE_Z1 + D.PCIE_LIFT / 2, D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H / 2]

    def rib_broken(shape):
        for i in range(len(cs_sorted) - 1):
            xm = (cs_sorted[i] + cs_sorted[i + 1]) / 2
            if any(not V.pt_inside(shape, xm, y_wall, z, 0.02) for z in rib_zs):
                return True
        return False

    # 13. 第八輪的連續橫縫塞回去 → 三根 1.42 的肋變成 112.75 mm 懸臂
    seam = box(min(cs_sorted) - D.PCIE_OPEN_W / 2, D.CASE_REAR - 0.5, D.PCIE_Z1,
               D.CASE_RIGHT + 0.5, D.CASE_REAR + D.WALL + 0.5, D.PCIE_Z1 + D.PCIE_LIFT)
    add("舊連續橫縫塞回 → 肋上端斷掉（懸臂）", rib_broken(rear.cut(seam)), "肋頂端無料")
    add("現況 → 三根肋上下貫通", not rib_broken(rear), "五個取樣點全有料")
    add("現況 → 肋外側補強實心",
        all(V.pt_inside(rear, (cs_sorted[i] + cs_sorted[i + 1]) / 2,
                        D.CASE_REAR - D.PCIE_RIB_D / 2, (D.PCIE_Z0 + D.PCIE_Z1) / 2, 0.02)
            for i in range(len(cs_sorted) - 1)),
        f"斷面 {D.PCIE_PITCH - D.PCIE_OPEN_W:.2f}×{D.WALL + D.PCIE_RIB_D:.2f}")

    # 13b. keyhole：落差必須 >= 頭高，否則寬口與窄段在同一個 Z 上矛盾
    add("落差 2.0 < 頭高 3.0 → keyhole 幾何矛盾", 2.0 < D.PCIE_HOOK_H, "2.0 < 3.0")
    add("現況 → 落差 >= 頭高", D.PCIE_BAR_DROP >= D.PCIE_HOOK_H,
        f"{D.PCIE_BAR_DROP} >= {D.PCIE_HOOK_H}")

    # 17. 碟架沒有承載料（立板底＝lv0 槽底）→ 最底層托盤舌下方是空的
    zr = D.tray_z0(0) - D.SLIDE_FIT - 1.0
    xs_probe = [D.HDD_TRAY_X0 - D.TRAY_RAIL_W / 2, D.HDD_TRAY_X1 + D.TRAY_RAIL_W / 2]
    ym = (D.HDD_Y0 + D.HDD_Y1) / 2
    rack_nofloor = rack.cut(box(D.CASE_LEFT, D.TRAY_Y0 - 1, D.RACK_Z0 - 1.0,
                                D.CASE_RIGHT, D.HDD_Y1 + 1, D.HDD_Z0))
    add("碟架承載料削掉 → lv0 導軌槽下方無料",
        all(not V.pt_inside(rack_nofloor, x, ym, zr, 0.02) for x in xs_probe), "兩側都空")
    add("現況 → lv0 導軌槽下方有承載料",
        all(V.pt_inside(rack, x, ym, zr, 0.02) for x in xs_probe),
        f"厚 {D.RACK_FLOOR_T - D.SLIDE_FIT:.2f} mm")

    # 18. 右立板貼回碟的接頭端面 → 接頭與線完全沒有地方去
    post_bad = box(D.HDD_X1, D.TRAY_Y0, D.RACK_Z0, D.HDD_X1 + D.RACK_WALL, D.HDD_Y1,
                   D.RACK_TOP_Z1)
    v = max(V.common_vol(post_bad, mocks[f"HDD_L{lv}_接頭"]) for lv in range(D.HDD_LEVELS))
    add("右立板貼回碟端面 → 接頭區被實心料佔住", v > MAX, f"{v:.0f} mm3")
    vn = max(V.common_vol(rack, mocks[f"HDD_L{lv}_接頭"]) for lv in range(D.HDD_LEVELS))
    add("現況 → 接頭區淨空", vn <= MAX, f"{vn:.2f} mm3")

    # 19. 碟架貼左內牆（第八輪佈局）→ 前罩開口嚴重不對稱
    old_x0 = D.CASE_LEFT + D.WALL + D.RACK_WALL
    old_l = (old_x0 - D.TRAY_RAIL_W - D.TOP_FIT_GAP) - D.CASE_LEFT
    old_r = D.CASE_RIGHT - (old_x0 + D.HDD_L + D.TRAY_RAIL_W + D.TOP_FIT_GAP)
    add("碟架貼左內牆 → 開口左右差很多", abs(old_l - old_r) > 1.0,
        f"左 {old_l:.2f} / 右 {old_r:.2f}")
    ml, mr = D.tray_opening_margin()
    add("現況 → 開口左右對稱", abs(ml - mr) < 0.01, f"左 {ml:.2f} / 右 {mr:.2f}")

    # 20. 層間零間隙：布林看不到（面接觸 common=0），只有量距離才看得出來
    t_old = B.make_hdd_tray()
    t_old.translate(App.Vector(0, 0, D.tray_z0(0) + D.HDD_H + D.TRAY_T))  # 舊 pitch
    d_old = t_old.distToShape(mocks["HDD_L0"])[0]
    t_new = B.make_hdd_tray_placed(1)
    d_new = t_new.distToShape(mocks["HDD_L0"])[0]
    add("舊 pitch = 碟厚+托盤 → 碟頂與上層托盤底距離 0（貼死）", d_old < 1e-6,
        f"距離 {d_old:.4f} mm，而 common 只有 {V.common_vol(t_old, mocks['HDD_L0']):.2f} mm3")
    add("現況 → 層間有氣隙", d_new >= 1.0 - 1e-6, f"距離 {d_new:.2f} mm")

    # 21. 前罩沒有地板（第八輪）→ 機殼前段 53.76 mm 底下是開的
    sh = S["Front_Shroud"]
    sh_nofloor = sh.cut(box(D.CASE_LEFT, D.SHROUD_Y0 - D.SHROUD_LAP - 1, -0.5,
                            D.CASE_RIGHT, D.CASE_FRONT + 1, D.FLOOR_T))
    fp = (-150.0, D.CASE_FRONT - 20.0, D.FLOOR_T / 2)
    add("前罩地板削掉 → 前段底下是空的", not V.pt_inside(sh_nofloor, *fp, 0.02), "探點無料")
    add("現況 → 前罩地板實心", V.pt_inside(sh, *fp, 0.02), f"z={D.FLOOR_T / 2:.2f}")

    # 22. 前罩搭接零間隙：nominal 0 的話 common 還是 0.000，只有量「間隙裡有沒有料」才抓得到
    x_gap = D.CASE_LEFT + D.SHROUD_LAP_T + D.SLIDE_FIT / 2
    y_lapm = D.BAY_SPLIT_Y - D.SHROUD_LAP / 2
    shim = box(D.CASE_LEFT + D.SHROUD_LAP_T, y_lapm - 1, 80.0,
               D.CASE_LEFT + D.SHROUD_LAP_T + D.SLIDE_FIT, y_lapm + 1, 100.0)
    add("側板減薄量少了 SLIDE_FIT → 間隙裡被填滿（套不進去）",
        V.pt_inside(side_l.fuse(shim), x_gap, y_lapm, 90.0, 0.02), "間隙有料")
    add("現況 → 搭接間隙是空的",
        not V.pt_inside(side_l, x_gap, y_lapm, 90.0, 0.02)
        and not V.pt_inside(sh, x_gap, y_lapm, 90.0, 0.02), f"{D.SLIDE_FIT} mm/邊")

    # 23. 底板槽開穿到牆底 → 那不是滑槽，是 L 形搭邊
    xm_g = D.CASE_LEFT + D.WALL - D.FLOOR_LIP / 2
    y_g = 60.0
    side_open = side_l.cut(box(D.CASE_LEFT + D.WALL - D.FLOOR_LIP, D.CASE_REAR, -0.1,
                               D.CASE_LEFT + D.WALL, D.BAY_SPLIT_Y, D.FLOOR_T - D.FLOOR_LIP_T))
    add("底板槽開穿到牆底 → 槽下方無承載唇",
        not V.pt_inside(side_open, xm_g, y_g, (D.FLOOR_T - D.FLOOR_LIP_T) / 2, 0.02), "下方無料")
    add("現況 → 槽下方有承載唇",
        V.pt_inside(side_l, xm_g, y_g, (D.FLOOR_T - D.FLOOR_LIP_T) / 2, 0.02),
        f"唇高 {D.FLOOR_T - D.FLOOR_LIP_T:.2f}")

    # 23b. 外殼長方體要用**體積**驗，不是 bbox。
    #      目視複檢抓到的：同一個側板，GUI（已 tessellate）回報 XMin −215.5471、
    #      headless 回報 −215.4900，差 0.057 —— 拿 ±0.05 的 bbox 門檻比，
    #      同一份幾何在兩個環境會給出不同答案。布林量出來的 0 兩邊都是 0。
    env = box(D.CASE_LEFT, D.CASE_REAR, -D.SKIRT_H, D.CASE_RIGHT, D.CASE_FRONT, D.OUTER_TOP_Z)
    bump = Part.makeSphere(2.0)
    bump.translate(App.Vector(D.CASE_LEFT, 100.0, 90.0))
    add("側板長出 2 mm 凸包 → 外殼長方體檢查應紅", side_l.fuse(bump).cut(env).Volume > MAX,
        f"{side_l.fuse(bump).cut(env).Volume:.1f} mm3")
    worst = max((k, s.cut(env).Volume) for k, s in S.items()
                if k not in ("PCIeBlank", "PCIeBar", "Rear_IO_PCIe"))
    add("現況 → 沒有任何印件伸出長方體", worst[1] <= MAX, f"最大外溢 {worst[1]:.2f} mm3")

    # 24. 前罩地板舌不讓開主板柱 → 滑進來的路上直接撞柱（最終位置也撞）
    bands = B.shroud_floor_stud_bands()
    tongue_bad = box(D.FLOOR_X0, D.SHROUD_Y0 - D.SHROUD_LAP,
                     D.FLOOR_T - D.SHROUD_FLOOR_LAP_T + D.SLIDE_FIT,
                     D.FLOOR_X1, D.SHROUD_Y0, D.FLOOR_T)
    add("前罩地板舌不讓開主板柱 → 撞柱", V.common_vol(tongue_bad, tray) > MAX,
        f"{V.common_vol(tongue_bad, tray):.0f} mm3（{len(bands)} 根柱）")
    add("現況 → 前罩與底板不干涉", V.common_vol(sh, tray) <= MAX,
        f"{V.common_vol(sh, tray):.2f} mm3")

    # 14. 螺絲／銅母參數若復活，「無螺絲」那條要紅
    gone = [g for g in ("M3_CLR", "M3_INSERT_D", "M3_BOSS_L", "M3_BASE_Z",
                        "TOP_SCREW_BOSS_D", "CAGE_LAP_W", "TOP_SEAM_Y") if hasattr(D, g)]
    add("現況 → 螺絲／銅母／搭接片參數全數不存在", not gone, f"殘留 {gone}" if gone else "0 個")

    # 15. Area A 淨空必須由 max(實測, 規格 required) 導出（改一個沒改另一個就該紅）
    add("現況 → Area A 淨空 = max(實測散熱器, Table 6 required)（導出）",
        abs(D.AREA_A_CLEARANCE - max(D.COOLER_MAX_H, D.AREA_A_SPEC_REQUIRED)) < 1e-9,
        f"{D.AREA_A_CLEARANCE} = max({D.COOLER_MAX_H}, {D.AREA_A_SPEC_REQUIRED})")
    add("現況 → 規格 literal 沒被改掉（76.20 / 88.90 還在）",
        abs(D.AREA_A_SPEC_REQUIRED - 76.20) < 1e-9
        and abs(D.AREA_A_SPEC_RECOMMENDED - 88.90) < 1e-9,
        f"{D.AREA_A_SPEC_REQUIRED} / {D.AREA_A_SPEC_RECOMMENDED}")

    # 16. 托盤厚度若偏離，#6-32 穿入量就掉出 SFF-8301 的 2.39–3.56
    for t_bad in (1.0, 4.5):
        pen = 6.35 - t_bad
        add(f"托盤厚 {t_bad} → 穿入 {pen:.2f} 掉出 SFF-8301 區間",
            not (2.39 <= pen <= 3.56), f"{pen:.2f}")
    pen = 6.35 - D.TRAY_T
    add("現況 → 穿入量落在 2.39–3.56", 2.39 <= pen <= 3.56, f"{pen:.2f}")

    # ══ 第十輪新增 ═════════════════════════════════════════════════
    # 25. 電源留在第九輪的高度 → Area A 只有 50.00，達不到 Table 6 required
    old_clear = 50.0
    add("電源留在舊高度 → Area A 50.00 < required 76.20 應紅",
        old_clear < D.AREA_A_SPEC_REQUIRED,
        f"{old_clear:.2f} < {D.AREA_A_SPEC_REQUIRED:.2f}（第九輪就是這樣，靠 WARN 掛著）")
    add("現況 → Area A 已達 required", D.AREA_A_CLEARANCE >= D.AREA_A_SPEC_REQUIRED,
        f"{D.AREA_A_CLEARANCE:.2f} >= {D.AREA_A_SPEC_REQUIRED:.2f}")
    add("現況 → 電源頂上的死空間已收掉", D.PSU_CLEAR_ABOVE <= 6.0,
        f"剩 {D.PSU_CLEAR_ABOVE:.2f} mm（第九輪 27.50）")

    # 26. 電源貼回左內牆 → 撞頂蓋往下垂的側舌（升上去之後兩者的 Z 帶是重疊的）
    psu_left = box(D.FLOOR_X0, D.ATX_Y0, D.ATX_Z0, D.FLOOR_X0 + D.ATX_W, D.ATX_Y1, D.ATX_Z1)
    add("電源貼回左內牆 → 撞頂蓋側舌", V.common_vol(psu_left, top) > MAX,
        f"{V.common_vol(psu_left, top):.0f} mm3")
    add("現況 → 電源讓開了頂蓋側舌",
        V.common_vol(mocks["PSU_150x86x140"], top) <= MAX,
        f"{V.common_vol(mocks['PSU_150x86x140'], top):.2f} mm3")

    # 27. ATX 四孔不翻轉 → 「翻回去等於 Fig.4 literal」那條要紅
    spec4 = tuple(sorted(D.ATX_HOLES_SPEC))
    unflipped_back = tuple(sorted((D.ATX_W - x, D.ATX_H - z) for x, z in spec4))
    add("四孔忘了翻轉 → 翻回去不等於 Fig.4 literal",
        unflipped_back != spec4, f"{unflipped_back} != {spec4}")
    flipped_back = tuple(sorted((D.ATX_W - x, D.ATX_H - z) for x, z in D.ATX_HOLES))
    add("現況 → 翻回去正好等於 Fig.4 literal", flipped_back == spec4, f"{flipped_back}")

    # 28. 底板不內縮（本體＝內腔寬）→ 兩側零間隙，250 mm 跨距上裝不進去
    slab_bad = box(D.FLOOR_X0, D.FLOOR_Y0, 0.0, D.FLOOR_X1, D.FLOOR_Y1, D.FLOOR_T)
    # 探點只能取**承載唇那一段**：舌本來就伸過去，用整個 z 帶會把舌算進來
    gap_probe = box(D.FLOOR_X0, 100.0, 0.3, D.FLOOR_X0 + D.SLIDE_FIT, 110.0, D.FLOOR_LEDGE_T)
    add("底板不內縮 → 側緣與牆內面共面（零間隙）",
        V.common_vol(slab_bad, gap_probe) > 0.5, f"{V.common_vol(slab_bad, gap_probe):.2f} mm3")
    add("現況 → 底板側緣留了滑配", V.common_vol(tray, gap_probe) <= 0.5,
        f"{V.common_vol(tray, gap_probe):.2f} mm3")

    # 29. 後牆的底板槽開穿到牆底 → 舌下方沒有承載料（第九輪就是這樣，只修了側板）
    y_rg = D.CASE_REAR + D.WALL - D.FLOOR_LIP / 2
    rear_bad = rear.cut(
        box(D.FLOOR_X0 - 2.0, D.CASE_REAR + D.WALL - D.FLOOR_LIP - D.SLIDE_FIT, -0.1,
            D.FLOOR_X1 + 2.0, D.CASE_REAR + D.WALL + 0.1, D.FLOOR_LEDGE_T)
    )
    add("後牆槽開穿到牆底 → 舌下方無承載料",
        not V.pt_inside(rear_bad, -60.0, y_rg, D.FLOOR_LEDGE_T / 2, 0.02), "槽下方 = 空氣")
    add("現況 → 後牆槽下方有承載料",
        V.pt_inside(rear, -60.0, y_rg, D.FLOOR_LEDGE_T / 2, 0.02), f"唇高 {D.FLOOR_LEDGE_T:.2f}")

    # 30. 頂蓋側舌回到第九輪的 0.40 咬合 → 咬合量檢查要紅
    old_eng = D.TOP_LIP - 2 * D.TOP_FIT_GAP
    add("頂蓋側舌回到第九輪算法 → 咬合只剩 0.40", old_eng < 1.0, f"{old_eng:.2f} mm")
    add("現況 → 頂蓋側舌咬合 >= 1.0", D.TOP_LIP >= 1.0, f"{D.TOP_LIP:.2f} mm")

    # 31. 側板搭接帶整片減薄 → 三道內面滑槽的背後被切穿
    lap_all = box(D.CASE_LEFT, D.BAY_SPLIT_Y - D.SHROUD_LAP, 0.0,
                  D.CASE_LEFT + D.SHROUD_LAP_T + D.SLIDE_FIT, D.BAY_SPLIT_Y + 0.1, D.OUTER_TOP_Z)
    side_bad = side_l.cut(lap_all)
    y_lap_n = D.BAY_SPLIT_Y - D.SHROUD_LAP / 2
    x_back_n = D.CASE_LEFT + (D.WALL - (D.TOP_LIP + D.SLIDE_FIT)) / 2
    add("搭接帶整片減薄 → 頂蓋槽背後被切穿",
        not V.pt_inside(side_bad, x_back_n, y_lap_n, D.INNER_TOP_Z - D.TOP_T / 2, 0.02),
        "1.6 槽 + 1.5 減薄 = 3.1 > 牆厚 2.4")
    add("現況 → 那三段不減薄，槽背後還有牆料",
        V.pt_inside(side_l, x_back_n, y_lap_n, D.INNER_TOP_Z - D.TOP_T / 2, 0.02),
        f"keep 帶 {B.side_lap_keep_bands()}")

    # 32. PCIe 窗框只補肋、不補框 → 底檻與左右柱回到 2.4
    fx0, fx1 = D.pcie_frame_x()
    fz0, fz1 = D.pcie_frame_z()
    y_boss = D.CASE_REAR - D.PCIE_RIB_D / 2
    rear_nf = rear.cut(box(fx0 - 1.0, D.CASE_REAR - D.PCIE_RIB_D - 1.0, fz0 - 1.0,
                           fx1 + 1.0, D.CASE_REAR, fz1 + 1.0))
    cs_n = sorted(D.pcie_centers())
    add("窗框不補強 → 底檻外側是空的",
        not V.pt_inside(rear_nf, (cs_n[0] + cs_n[-1]) / 2, y_boss, D.PCIE_Z0 - 2.0, 0.02),
        "只補中間三根肋等於沒補框")
    add("現況 → 底檻／左右柱都補到 6.40",
        all(V.pt_inside(rear, xx, y_boss, zz, 0.02) for xx, zz in
            (((cs_n[0] + cs_n[-1]) / 2, D.PCIE_Z0 - 2.0),
             (fx0 + 1.0, (D.PCIE_Z0 + D.PCIE_Z1) / 2),
             (fx1 - 1.0, (D.PCIE_Z0 + D.PCIE_Z1) / 2))),
        f"舌袋背後剩料 {D.WALL + D.PCIE_RIB_D - D.PCIE_TANG_POCKET:.2f}")

    # 33. install_depth 用舊定義（CASE_D + 壓條厚）→ 少報最凸的蘑菇柱
    old_id = D.CASE_D + D.PCIE_BAR_T
    add("install_depth 用舊定義 → 比實際少報",
        old_id < D.install_depth_mm() - 0.01,
        f"舊 {old_id:.2f} < 實際 {D.install_depth_mm():.2f}（差 {D.install_depth_mm() - old_id:.2f}）")
    y_min_n = min(V.obb(bar).YMin, V.obb(rear).YMin)
    add("現況 → install_depth 對得上量出來的外凸",
        abs(D.install_depth_mm() - (D.CASE_D + (D.CASE_REAR - y_min_n))) < 0.05,
        f"{D.install_depth_mm():.2f}")

    # 34. 蘑菇柱回到第九輪的 4.0×5.5
    add("蘑菇柱回到 4.0×5.5 → 頸斷面 22 mm² 太細", 4.0 * 5.5 < 40.0, "22.0 mm²")
    add("現況 → 頸斷面 >= 40 mm²",
        D.PCIE_HOOK_NECK_W * D.PCIE_HOOK_NECK_D >= 40.0,
        f"{D.PCIE_HOOK_NECK_W * D.PCIE_HOOK_NECK_D:.1f} mm²")

    # 35. 第八／九輪文件寫的順序（後牆自 +Z 落下）→ 側板已在位時根本落不下去
    drop = rear.copy()
    drop.translate(App.Vector(0, 0, 40.0))
    swept_drop = drop
    for i in range(1, 9):
        mv = rear.copy()
        mv.translate(App.Vector(0, 0, 40.0 * (8 - i) / 8.0))
        swept_drop = swept_drop.fuse(mv)
    hit_drop = max(V.common_vol(swept_drop, side_l), V.common_vol(swept_drop, side_r))
    add("後牆自 +Z 落下（舊文件的順序）→ 撞側板", hit_drop > MAX,
        f"{hit_drop:.0f} mm3 —— 定位舌的口袋上方是實牆，落不進去")
    push = rear.copy()
    push.translate(App.Vector(0, -(D.REAR_TAB_D + 6.0), 0))
    swept_push = push
    for i in range(1, 9):
        mv = rear.copy()
        mv.translate(App.Vector(0, -(D.REAR_TAB_D + 6.0) * (8 - i) / 8.0, 0))
        swept_push = swept_push.fuse(mv)
    det_l = B.rear_tab_detents(True, 0.05) + B.rear_tab_detents(False, 0.05)
    sl_nd, sr_nd = side_l, side_r
    for dd in B.rear_tab_detents(True, 0.05):
        sl_nd = sl_nd.cut(dd)
    for dd in B.rear_tab_detents(False, 0.05):
        sr_nd = sr_nd.cut(dd)
    hit_push = max(V.common_vol(swept_push, sl_nd), V.common_vol(swept_push, sr_nd),
                   V.common_vol(swept_push, tray.cut(B.floor_rear_detents(0.05)[0])
                                .cut(B.floor_rear_detents(0.05)[1])))
    add("現況 → 後牆自 −Y 推入（使用者指定的順序）路徑淨空", hit_push <= MAX,
        f"{hit_push:.2f} mm3")

    # 36. detent 必須真的咬到：把母件的凹坑填回去，公件一定要撞
    for tag, gen, male, female in (
        ("前罩頂搭接", lambda: B.shroud_lap_detents(True, 0.15), top, sh),
        ("前罩底搭接", lambda: B.shroud_lap_detents(False, 0.15), tray, sh),
    ):
        filled = female
        for d in gen():
            filled = filled.fuse(d)
        v = V.common_vol(filled, male)
        add(f"{tag} detent 凹坑填回去 → 公件必撞", v > MAX, f"{v:.2f} mm3")
        add(f"現況 → {tag} 落到定位不干涉", V.common_vol(female, male) <= MAX,
            f"{V.common_vol(female, male):.2f} mm3")
    # 底板側緣 bead：把側板的凹槽填回去，bead 一定要撞
    filled_side = side_l
    for c in B.floor_detents(True, D.SLIDE_FIT / 2):
        filled_side = filled_side.fuse(c)
    v_bead = V.common_vol(filled_side, tray)
    add("底板 bead 的凹槽填回去 → bead 必撞", v_bead > MAX, f"{v_bead:.2f} mm3")
    add("現況 → bead 落到定位不干涉", V.common_vol(side_l, tray) <= MAX,
        f"{V.common_vol(side_l, tray):.2f} mm3")
    add("底板 bead 的凸出量大於滑配（不是裝飾）",
        D.FLOOR_DETENT_DEPTH > D.SLIDE_FIT,
        f"凸 {D.FLOOR_DETENT_DEPTH} − 滑配 {D.SLIDE_FIT} = 過盈 "
        f"{D.FLOOR_DETENT_DEPTH - D.SLIDE_FIT:.2f}")

    # ══ 第十一輪：使用者「我仍然看不出這機殼要怎麼組裝在一起」量出來的兩個 ══
    # 40. 後牆的保持力：半球（第十輪）受拉會 cam-out，直角楔不會。
    #     把半球塞回去 → 「有法線平行 Y 的直角面」這條檢查必須紅。
    y_sq = B.rear_wedge_y1()
    sphere_like = Part.makeSphere(D.DETENT_R)
    sphere_like.translate(App.Vector(D.FLOOR_X0 - 1.0, y_sq, D.REAR_DETENT_Z[1]))
    sq_faces = 0
    for f in sphere_like.Faces:
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if abs(n.y) > 0.99 and abs(f.CenterOfMass.y - y_sq) < 0.05:
            sq_faces += 1
    add("後牆 detent 換回半球 → 找不到法線平行 Y 的直角面（會 cam-out）",
        sq_faces == 0, f"半球上這種面有 {sq_faces} 個")
    want_a = D.DETENT_DEPTH * D.REAR_WEDGE_H * 0.8
    got_a = 0.0
    for f in B.rear_tab_detents(True)[0].Faces:
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if abs(n.y) > 0.99 and abs(f.CenterOfMass.y - y_sq) < 0.05:
            got_a = max(got_a, f.Area)
    add("現況 → 楔上有直角面", got_a >= want_a, f"{got_a:.2f} >= {want_a:.2f} mm²")
    # 缺口若改成「開在舌中間的孔」→ 直角面前方那片舌料只剩 0.45，一拉就掰斷。
    mid_hole_lig = (D.CASE_REAR + D.WALL + D.REAR_TAB_D) - (y_sq + D.SLIDE_FIT / 2)
    add("缺口改成舌中間的孔 → 前緣只剩不到 2 mm 細肉（現況是整片舌料）",
        mid_hole_lig < 2.0 and V.pt_inside(
            rear, D.FLOOR_X0 - D.REAR_TAB_T / 2, y_sq + D.SLIDE_FIT, D.REAR_DETENT_Z[1], 0.02),
        f"若開孔，孔前只有 {mid_hole_lig:.2f} mm；現況缺口自舌根開 → 前方一路實心")
    # 把楔從側板上削掉（＝重建第十輪的狀態）→ 後牆往 −Y 走 12 mm 完全沒有東西擋
    nowedge = {}
    for isl, k in ((True, "Side_Left_MB"), (False, "Side_Right_MB")):
        s = S[k]
        for w in B.rear_tab_detents(isl, 0.05):
            s = s.cut(w)
        nowedge[k] = s
    mv = rear.copy()
    mv.translate(App.Vector(0, -12.0, 0))
    v_pull = max(V.common_vol(mv, s) for s in nowedge.values())
    add("削掉楔（＝第十輪）→ 後牆往 −Y 走 12 mm 不撞側板",
        v_pull <= MAX, f"{v_pull:.2f} mm3")
    mv2 = rear.copy()
    mv2.translate(App.Vector(0, -0.5, 0))
    v_now = max(V.common_vol(mv2, S[k]) for k in ("Side_Left_MB", "Side_Right_MB"))
    add("現況 → 後牆往 −Y 只走 0.5 mm 就被楔擋住", v_now > MAX, f"{v_now:.2f} mm3")

    # 41. 碟架的 −Y 止擋：槽的盲端回到第十輪的 TRAY_Y0 − 1.0 → 碟架浮 3 mm
    old_stop = D.TRAY_Y0 - 1.0
    float_old = min(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2 - old_stop
    add("碟架槽盲端回到 TRAY_Y0 − 1.0 → 碟架往 −Y 浮 3 mm",
        float_old > 2.0, f"浮 {float_old:.2f} mm")
    add("現況 → 盲端由側舌後緣導出，浮動＝滑配",
        abs((min(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2 - D.RACK_STOP_Y) - D.SLIDE_FIT) < 1e-9,
        f"RACK_STOP_Y={D.RACK_STOP_Y:.2f}，浮 {D.SLIDE_FIT}")
    mv3 = rack.copy()
    mv3.translate(App.Vector(0, -2.0, 0))
    v_rack = max(V.common_vol(mv3, S[k]) for k in ("Side_Left_MB", "Side_Right_MB"))
    add("現況 → 碟架往 −Y 走 2 mm 就撞側板（第十輪走 3.0 都不撞）",
        v_rack > MAX, f"{v_rack:.2f} mm3")

    # 42. 為什麼前十輪抓不到上面兩個：**干涉檢查對它們是瞎的**。
    #     把楔整組拿掉（＝第十輪的狀態），`no interfere` 照樣綠。
    add("削掉楔之後 interference 檢查仍然是綠的 → 它問的不是『裝得住嗎』",
        max(V.common_vol(rear, s) for s in nowedge.values()) <= MAX,
        "干涉 0.00，要位移 12 mm 才看得出沒東西擋")

    # 37. 死參數（定義了卻沒有任何檢查引用）必須是刪掉的，不是留著
    zombie = [g for g in ("PCIE_OPEN_GAP", "TRAY_SIDE_GAP", "TOP_SLIDE_STOP",
                          "TOP_LEDGE_T", "TOP_LEDGE_W") if hasattr(D, g)]
    add("現況 → 第十輪清掉的死參數沒有復活", not zombie, f"殘留 {zombie}" if zombie else "0 個")
    add("現況 → 死函式（zone_clear_top_z / pcie_ear_x_span）已刪",
        not hasattr(D, "zone_clear_top_z") and not hasattr(D, "pcie_ear_x_span"), "0 個")

    # 38. 電源按鈕本體：`PWR_BTN_DEPTH` 兩輪沒有任何檢查引用（硬規則 15）
    btn = mocks["電源按鈕本體"]
    worst_btn = max(V.common_vol(btn, s2) for s2 in S.values())
    add("現況 → 電源按鈕本體 22 深不撞任何印件", worst_btn <= MAX, f"{worst_btn:.2f} mm3")
    r_nut = D.PWR_BTN_NUT_D / 2
    y_face = D.CASE_FRONT - D.TRAY_FACE_T
    btn_bad = box(-100.0 - r_nut, y_face - D.PWR_BTN_DEPTH, 60.0 - r_nut,
                  -100.0 + r_nut, y_face, 60.0 + r_nut)
    v_bad = max(V.common_vol(btn_bad, rack), V.common_vol(btn_bad, sh),
                V.common_vol(btn_bad, dtray))
    add("按鈕挪到碟架的 X／Z 上 → 撞碟架／前罩", v_bad > MAX, f"{v_bad:.0f} mm3")

    # 39. 碟架頂板與頂蓋底面共面（第八～九輪）→ 頂蓋滑入時要磨過 100 mm
    add("INNER_TOP_Z 直接取 RACK_TOP_Z1 → 碟架頂與頂蓋底共面",
        abs(D.RACK_TOP_Z1 - (D.INNER_TOP_Z - D.RACK_TOP_GAP)) < 1e-9 and D.RACK_TOP_GAP > 0,
        f"補了 {D.RACK_TOP_GAP} 的間隙（沒補的話兩面在 z={D.RACK_TOP_Z1:.2f} 共面）")
    slab_gap = box(D.HDD_X0 + 5, D.TRAY_Y0 + 5, D.RACK_TOP_Z1 + 0.05,
                   D.HDD_X1 - 5, D.BAY_SPLIT_Y - 5, D.INNER_TOP_Z - 0.05)
    worst_gap = max(V.common_vol(slab_gap, s2) for s2 in S.values())
    add("現況 → 碟架頂板上方那道縫是空的", worst_gap <= MAX, f"{worst_gap:.2f} mm3")

    App.closeDocument(doc.Name)
    allok = True
    for name, cond, note in res:
        print(("PASS " if cond else "MISS ") + name + " — " + note)
        allok = allok and cond
    print(f"NEGTEST {sum(1 for _, c, _ in res if c)}/{len(res)}")
    print("NEGTEST_OK" if allok else "NEGTEST_FAILED")
    return 0 if allok else 1


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
