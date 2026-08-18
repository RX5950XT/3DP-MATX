"""單元測試：腳本/參數.py"""

from __future__ import annotations

import math
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "腳本")
STL_DIR = os.path.join(ROOT, "列印件")
CAD_DIR = os.path.join(ROOT, "CAD")
sys.path.insert(0, SCRIPTS)

from _load_params import load_params  # noqa: E402

D = load_params()

# microATX 1.2 Figure 7（p18）向量座標，Intel 系；case_x = −intel_x
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


class Test參數(unittest.TestCase):
    def test_九孔逐顆對Fig7(self):
        """
        第七輪的第一號缺陷：舊值把 Fig.3 的 `.900 [22.86]` 讀成「板後緣 → B 列」，
        於是 F 被放回 B 列、R/S/H/J 與 L/M 各少了 22.86。七顆孔錯位、板緣也錯 12.7。
        """
        self.assertEqual(set(D.HOLES_MM.keys()), set(D.HOLE_LETTERS))
        for k, (ix, iy) in SPEC_HOLES_INTEL.items():
            self.assertAlmostEqual(D.HOLES_MM[k][0], -ix, places=2, msg=k)
            self.assertAlmostEqual(D.HOLES_MM[k][1], iy, places=2, msg=k)
        # 舊值特徵：F 在 y=0、R 列在 132.08。不准回來。
        self.assertGreater(D.HOLES_MM["F"][1], 20.0)
        self.assertGreater(D.HOLES_MM["R"][1], 150.0)

    def test_板緣與板尺寸(self):
        self.assertAlmostEqual(D.BOARD_REAR, -10.16, places=2)  # B 離後緣 0.400"
        self.assertAlmostEqual(D.BOARD_FRONT, 233.68, places=2)
        self.assertAlmostEqual(D.BOARD_W, 243.84, places=2)  # 9.600 in
        self.assertAlmostEqual(D.BOARD_D, 243.84, places=2)
        for k, (x, y) in D.HOLES_MM.items():
            self.assertTrue(D.BOARD_LEFT < x < D.BOARD_RIGHT, msg=k)
            self.assertTrue(D.BOARD_REAR < y < D.BOARD_FRONT, msg=k)
        # ★ 第八輪碟陣**疊在主板前段的正上方**，所以不再要求「板前緣 <= 碟後緣」；
        #   改成驗證垂直方向真的讓開了 Area C 淨空。
        self.assertLess(D.TRAY_Y0, D.BOARD_FRONT)
        self.assertGreaterEqual(D.HDD_Z0, D.AREA_C_TOP_Z)

    def test_板上分區出自Fig7_Table6(self):
        # ★ 第十輪：Area A 淨空**回到規範內**。電源往上頂到內頂，讓出來的
        #   26.20 mm 死空間全部變成板上淨空：50.00 → 76.20 = Table 6 required。
        #   機殼高度沒有變。COOLER_MAX_H 退居下限。
        self.assertAlmostEqual(
            D.AREA_A_CLEARANCE, max(D.COOLER_MAX_H, D.AREA_A_SPEC_REQUIRED), places=6
        )
        self.assertAlmostEqual(D.AREA_A_SPEC_REQUIRED, 76.20, places=2)
        self.assertAlmostEqual(D.AREA_A_SPEC_RECOMMENDED, 88.90, places=2)
        self.assertGreaterEqual(D.AREA_A_CLEARANCE, D.AREA_A_SPEC_REQUIRED)
        self.assertLess(D.AREA_A_CLEARANCE, D.AREA_A_SPEC_RECOMMENDED)
        self.assertLessEqual(D.DIMM_MAX_H, D.COOLER_MAX_H)
        self.assertAlmostEqual(D.AREA_B_CLEARANCE, 15.24, places=2)  # 0.60 in
        self.assertAlmostEqual(D.AREA_C_CLEARANCE, 38.10, places=2)  # 1.50 in
        self.assertAlmostEqual(D.AREA_B_X0, -52.07, places=2)
        self.assertAlmostEqual(D.AREA_A_STEP_X, -95.25, places=2)
        for cx in D.pcie_centers():
            self.assertEqual(D.board_zone(cx, 40.0), "B")
        self.assertEqual(D.board_zone(-150.0, 40.0), "A")
        self.assertEqual(D.board_zone(-150.0, 200.0), "C")

    def test_電源上置(self):
        self.assertAlmostEqual(D.ATX_W, 150.0, places=1)
        self.assertAlmostEqual(D.ATX_H, 86.0, places=1)
        # ATX12V Fig.4 p23 —— 非對稱四孔的 literal，逐顆比對
        spec = sorted([(6.0, 80.0), (144.0, 80.0), (6.0, 16.0), (120.0, 6.0)])
        self.assertEqual(sorted(tuple(h) for h in D.ATX_HOLES_SPEC), spec)
        # ★ 第十輪：實際孔位 = 規格四孔繞**深度軸**轉 180°（風扇朝下，使用者指定）。
        #   驗「轉回去等於 literal」——確認它是剛體變換，不是重新編一組數字。
        back = sorted((D.ATX_W - x, D.ATX_H - z) for x, z in D.ATX_HOLES)
        self.assertEqual(back if D.PSU_FAN_DOWN else sorted(D.ATX_HOLES), spec)
        self.assertEqual(len({h[0] for h in D.ATX_HOLES}), 3, "Fig.4 不是對稱矩形")
        self.assertEqual(len({h[1] for h in D.ATX_HOLES}), 3, "Fig.4 不是對稱矩形")
        for hx, hz in D.ATX_HOLES:
            self.assertTrue(0 < hx < D.ATX_W and 0 < hz < D.ATX_H)
        # 電源在主板正上方：底面 = Area A 淨空頂 + 承托肩厚（導出，不寫死）
        self.assertAlmostEqual(D.ATX_Z0, D.AREA_A_TOP_Z + D.PSU_LEDGE_T, places=6)
        self.assertGreaterEqual(D.psu_bottom_clearance(), D.AREA_A_CLEARANCE)
        # 投影必須整片落在 Area A（B/C 區淨空只有 15.24 / 38.10）
        zone_ok, bad = D.psu_zone_ok()
        self.assertTrue(zone_ok, msg=str(bad))
        # 使用者指定：插頭插在 I/O 擋板**上方**那一區
        self.assertGreater(D.ATX_Z0 + D.PSU_WIN_Z0, D.IO_Z1)
        # ★ 第十輪：電源真的頂到內頂了（第九輪頭上有 27.50 mm 死空間）
        self.assertGreaterEqual(D.PSU_CLEAR_ABOVE, D.PSU_CLEAR_MIN)
        self.assertLessEqual(D.PSU_CLEAR_ABOVE, 6.0)
        self.assertAlmostEqual(D.psu_top_clearance(), D.PSU_CLEAR_ABOVE, places=6)
        # 舊的頂蓋承托肩參數必須整組消失（幾何第八輪就沒有它了）
        for g in ("TOP_LEDGE_T", "TOP_LEDGE_W"):
            self.assertFalse(hasattr(D, g), f"{g} 還在")
        # X 要讓開頂蓋往下垂的側舌（升上去之後兩者的 Z 帶重疊）
        self.assertAlmostEqual(D.ATX_X0, D.TOP_LID_INNER_X + D.PSU_FIT_GAP, places=6)
        self.assertLessEqual(D.ATX_X1, D.AREA_B_X0)

    def test_io_pcie策略A(self):
        self.assertAlmostEqual(D.IO_W, 158.75, places=2)
        self.assertAlmostEqual(D.IO_X1, -53.24, places=2)
        self.assertAlmostEqual(D.IO_X0, -53.24 - D.IO_W, places=2)
        self.assertAlmostEqual(D.IO_Z0, D.BOARD_TOP_Z - 3.81, places=3)
        self.assertEqual(len(D.pcie_centers()), 4)
        self.assertAlmostEqual(D.PCIE_PITCH, 20.32, places=2)
        self.assertAlmostEqual(D.PCIE_EDGE_TO_FIRST, 10.16, places=2)
        self.assertAlmostEqual(D.PCIE_FIRST_CX, D.BOARD_RIGHT - 10.16, places=2)
        self.assertGreater(min(D.pcie_centers()), D.IO_X1)
        self.assertGreaterEqual(D.IO_CLIP_T, 0.94)
        self.assertLessEqual(D.IO_CLIP_T, 1.32)

    def test_無SFX別名(self):
        self.assertFalse(hasattr(D, "SFX_W"))
        self.assertFalse(hasattr(D, "SFX_HOLES"))

    def test_hdd平躺四層疊在主板上方(self):
        """第八輪：碟平躺 147 沿 X、101.6 沿 Y、26.1 沿 Z，單排 4 層。"""
        self.assertEqual(D.HDD_COUNT, 4)
        self.assertEqual(D.HDD_LEVELS, 4)
        # 後緣是 Fig.7 的 Area A/C 界線（導出，不寫死）：x 帶跨過 AREA_A_STEP_X，
        # 那一段 Area A 一路延到 180.34，再往後就伸進散熱器空間。
        self.assertAlmostEqual(D.TRAY_Y0, D.AREA_A_Y_FAR, places=6)
        self.assertAlmostEqual(D.HDD_Y0, D.TRAY_Y0 + D.TRAY_BACK_STOP, places=6)
        self.assertAlmostEqual(D.HDD_Y1, D.HDD_Y0 + D.HDD_W, places=6)
        self.assertGreater(D.CASE_FRONT, D.HDD_Y1)
        # 層節距由碟厚 + 托盤厚 + **氣隙**導出。★ 第九輪：舊式 HDD_H + TRAY_T 讓碟頂
        # 正好貼死上一層托盤底（零間隙），布林與掃描都看不到。
        self.assertAlmostEqual(D.TRAY_PITCH, D.HDD_H + D.TRAY_T + D.TRAY_AIR_GAP, places=6)
        self.assertGreaterEqual(D.TRAY_AIR_GAP, 1.0)
        self.assertAlmostEqual(D.HDD_TOP_Z, D.HDD_Z0 + 4 * D.TRAY_PITCH, places=6)
        # 碟陣整片落在內腔寬度內
        self.assertGreaterEqual(D.HDD_X0, D.CASE_LEFT + D.WALL)
        self.assertLessEqual(D.RACK_POST_X1, D.CASE_RIGHT - D.WALL)
        # 每層托盤底面遞增一個節距
        for lv in range(1, D.HDD_LEVELS):
            self.assertAlmostEqual(D.tray_z0(lv) - D.tray_z0(lv - 1), D.TRAY_PITCH, places=6)
        # 內頂由碟架頂板導出（線走側廊，不走碟上方 → 舊的 HDD_PLUG_CLEAR 是謊言）
        self.assertFalse(hasattr(D, "HDD_PLUG_CLEAR"))
        self.assertAlmostEqual(D.RACK_TOP_Z1, D.HDD_TOP_Z + D.RACK_TOP_T, places=6)
        self.assertLessEqual(D.RACK_TOP_Z1, D.INNER_TOP_Z)

    def test_碟架最底層槽下方要有承載料(self):
        """使用者主訴 1a：最下面那一層的溝槽底下是空的，硬碟卡不住。"""
        self.assertAlmostEqual(D.RACK_Z0, D.AREA_C_TOP_Z, places=6)
        self.assertAlmostEqual(D.HDD_Z0, D.RACK_Z0 + D.RACK_FLOOR_T, places=6)
        # 槽底在 tray_z0 − SLIDE_FIT；它下方剩下的料要撐得住一顆碟
        self.assertGreaterEqual(D.tray_z0(0) - D.SLIDE_FIT - D.RACK_Z0, 2.0)

    def test_碟接頭區與走線空間(self):
        """使用者主訴 1c：第八輪右立板整片貼在碟的接頭端面上，接頭插不上。"""
        self.assertGreaterEqual(D.HDD_CABLE_W, 25.0)
        self.assertAlmostEqual(D.RACK_POST_X0, D.HDD_X1 + D.HDD_CABLE_W, places=6)
        lo, hi = D.cable_corridor_x()
        self.assertAlmostEqual(lo, D.HDD_X1, places=6)
        self.assertAlmostEqual(hi - lo, D.HDD_CABLE_W, places=6)
        # 托盤要鋪到右立板，線才有底
        self.assertAlmostEqual(D.HDD_TRAY_X1, D.RACK_POST_X0, places=6)

    def test_碟架置中且前罩開口對稱(self):
        """使用者主訴 1b：開孔偏一邊，要左右對稱。"""
        gl, gr = D.side_gap_x()
        self.assertAlmostEqual(gl, gr, places=6)
        ml, mr = D.tray_opening_margin()
        self.assertAlmostEqual(ml, mr, places=6)
        self.assertAlmostEqual(D.RACK_W, 2 * D.RACK_WALL + D.HDD_L + D.HDD_CABLE_W, places=6)

    def test_前罩要有地板且真的卡住(self):
        """使用者主訴 2：底下是空的／要貼合／「確定是卡槽卡住的嗎」。"""
        # 打薄，但不得低於 FDM 最小可印壁厚
        self.assertLess(D.SHROUD_WALL, D.WALL)
        self.assertGreaterEqual(D.SHROUD_WALL, 0.8)
        self.assertGreaterEqual(D.SHROUD_LAP_T, 0.8)
        # 四面搭接：左右 + 頂 + 底，且**留了滑配**（第八輪 nominal 零間隙）
        self.assertAlmostEqual(
            D.SHROUD_LAP_T + D.SLIDE_FIT + (D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT), D.WALL, places=6
        )
        self.assertGreater(D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT, 0.8)
        self.assertAlmostEqual(D.SHROUD_TOP_LAP_T, D.TOP_T / 2, places=6)
        self.assertAlmostEqual(D.SHROUD_FLOOR_LAP_T, D.FLOOR_T / 2, places=6)
        self.assertGreaterEqual(D.FLOOR_T - D.SHROUD_FLOOR_LAP_T - D.SLIDE_FIT, 0.8)
        # detent 半徑受減薄後料厚限制：2R <= t + 凸出
        t_left = D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT
        self.assertLessEqual(2 * D.SHROUD_DETENT_R, t_left + D.SHROUD_DETENT_DEPTH + 1e-9)
        self.assertGreaterEqual(D.SHROUD_DETENT_R, 0.5)
        self.assertGreaterEqual(len(D.SHROUD_DETENT_Z), 2)

    def test_底板側舌是被夾住的槽不是搭邊(self):
        """使用者提問 4：底板跟左右板之間真的有滑蓋設計嗎。"""
        # 舌只有上半片 → 槽下方留得出承載唇
        self.assertLess(D.FLOOR_LIP_T, D.FLOOR_T)
        self.assertGreaterEqual(D.FLOOR_T - D.FLOOR_LIP_T, 0.8)
        self.assertLessEqual(D.FLOOR_LIP, D.WALL - 0.8)

    def test_單一長方體(self):
        w, d, h = D.envelope_mm()
        self.assertGreater(w, 200)
        self.assertLess(d, 320)
        self.assertLess(d / w, 1.6)
        # 第八輪：電源下移 + 下裙刪除 → 比第七輪的 205.2 再矮一截
        self.assertGreater(h, 150)
        self.assertLess(h, 200)
        self.assertAlmostEqual(D.case_volume_l(), w * d * h / 1e6, places=6)
        self.assertAlmostEqual(h, D.OUTER_TOP_Z + D.SKIRT_H, places=6)
        self.assertAlmostEqual(d, D.CASE_D, places=6)
        # 使用者的硬目標
        self.assertLess(D.case_volume_l(), 15.0)

    def test_碟架與前罩取代了碟艙外殼(self):
        self.assertIn("HDD_Rack", D.STL_NAMES)
        self.assertIn("HDD_Tray", D.STL_NAMES)
        self.assertIn("Front_Shroud", D.STL_NAMES)
        for bad in D.REMOVED_SHELL_PARTS:
            self.assertNotIn(bad, D.STL_NAMES)
        self.assertIn("HDD_Cage", D.REMOVED_SHELL_PARTS)
        self.assertIn("Top_HDD", D.REMOVED_SHELL_PARTS)
        for gone in ("左側板_碟艙段.stl", "前板.stl", "硬碟艙_四盤.stl", "頂蓋_碟艙段.stl"):
            self.assertNotIn(gone, D.STL_NAMES.values())
            self.assertIn(gone, D.REMOVED_STL)

    def test_預覽必須畫到每一個列印件(self):
        # 曾經：新增列印件後預覽只畫 8 件，沒被眼睛看過。
        try:
            import 渲染預覽
        except ImportError as e:  # numpy/PIL 不在時跳過
            self.skipTest(str(e))
        self.assertEqual({p[0] for p in 渲染預覽.PARTS}, set(D.STL_NAMES.values()))

    def test_STL_NAMES十一件(self):
        # 11 個 STL＝5 結構（底板／後牆／左右側板／頂蓋）+ 前罩 + 碟架 + 碟托盤
        #             + PCIe 槽蓋 + PCIe 壓條 + 主板壓帽
        self.assertEqual(len(D.STL_NAMES), 11)
        self.assertEqual(len(D.STRUCT_PART_KEYS), 11)
        self.assertIn("Bottom_Tray", D.STL_NAMES)
        self.assertEqual(D.TRAY_COUNT, D.HDD_COUNT)  # 碟托盤同一個 STL 印四份
        for gone in ("ClampTray", "Bottom_ATX", "ClampCap", "HDD_Cage", "Top_HDD"):
            self.assertNotIn(gone, D.STL_NAMES)
        for k in D.STRUCT_PART_KEYS:
            self.assertIn(k, D.STL_NAMES)

    def test_產物(self):
        for fn in D.STL_NAMES.values():
            p = os.path.join(STL_DIR, fn)
            self.assertTrue(os.path.isfile(p), msg=fn)
            self.assertGreater(os.path.getsize(p), 1024, msg=fn)
        self.assertTrue(os.path.isfile(os.path.join(CAD_DIR, D.FCSTD_NAME)))
        for fn in D.REMOVED_STL:
            self.assertFalse(os.path.isfile(os.path.join(STL_DIR, fn)), msg=fn)


class Test修復回歸(unittest.TestCase):
    """每條對應一個實際踩過的缺陷，不得回退。"""

    def test_前幾輪刪掉的東西不得回來(self):
        """
        第七輪刪的：甲板（DECK_Z）與它製造的穿艙孔／走線廊／托盤／地板柵／圓腳／榫。
        第八輪刪的：**下裙、全部 M3 螺絲與銅母座、頂蓋螺絲座、碟艙搭接片、
        直立碟艙的側鎖孔、兩片式頂蓋的接縫。**
        """
        for gone in (
            "DECK_Z", "BASE_T", "TRAY_X0", "TRAY_Y1",
            "DECK_CABLE_W", "DECK_CABLE_CY", "SIDE_DECK_W", "EPS_CABLE_W",
            "SIDE_CABLE_W", "SIDE_CABLE_RIB_H", "CABLE_PASS_W", "FRONT_SILL_PASS_W",
            "PSU_VENT_W", "PSU_VENT_D", "FOOT_R", "FOOT_H",
            "TENON", "TENON_GAP", "TENON_SPAN_TOL", "JOIN_SIDE_Y", "JOIN_REAR_X",
            "DECK_LEDGE_W", "HDD_REAR_UPPER_T", "TOP_LIP_H", "TOP_MB_LIP_Y1",
            # ── 第八輪 ──
            "M3_CLR", "M3_TAP", "M3_INSERT_D", "M3_INSERT_L", "M3_INSERT_BORE",
            "M3_BOSS_L", "M3_BOSS_W", "M3_BASE_Z", "M3_REAR_BASE_X", "M3_SIDE_BASE_Y",
            "M3_CAGE_Y", "M3_CAGE_Z",
            "TOP_SCREW_BOSS_D", "TOP_SCREW_BOSS_W", "TOP_SCREW_BOSS_H",
            "TOP_SCREW_MB_Y", "TOP_SCREW_HDD_Y", "TOP_SEAM_Y", "TOP_LAP_W",
            "CAGE_LAP_W", "CAGE_LAP_BACK", "CAGE_LAP_ROOT", "CAGE_LAP_Z0", "CAGE_LAP_Z1",
            "CAGE_TOP_RAIL_H", "HDD_ACCESS_D", "HDD_SIDE_FROM_FACE", "HDD_SIDE_FROM_CONN",
            "HDD_SIDE_Z_REFS", "HDD_SIDE_SLOT", "HDD_ROWS", "HDD_COLS", "HDD_BASE_Z",
            "HDD_RAIL", "HDD_WALL", "HDD_TOP_PLUG", "HDD_GAP_X", "HDD_GAP_Y",
            "HDD_REAR_CLEAR", "HDD_FRONT_CLEAR", "PCIE_BAR_BOSS_W", "PCIE_BAR_D",
            # ── 第十輪：定義了卻沒有任何檢查引用的（硬規則 15）──
            "TOP_LEDGE_T", "TOP_LEDGE_W",  # 第七輪的頂蓋承托肩，第八輪幾何就沒了
            "PCIE_OPEN_GAP", "TRAY_SIDE_GAP", "TOP_SLIDE_STOP",
        ):
            self.assertFalse(hasattr(D, gone), msg=f"參數.{gone} 應已刪除")
        for gone_fn in ("zone_clear_top_z", "pcie_ear_x_span"):
            self.assertFalse(hasattr(D, gone_fn), msg=f"參數.{gone_fn}() 應已刪除")
        for fn in ("deck_cable_pack_ok", "bend_corridor_ok", "side_cable_path_ok",
                   "foot_sites_bottom", "foot_front_overhang",
                   "hdd_bay_inner", "hdd_outer", "hdd_bay_x0", "pcie_bar_boss_x"):
            self.assertFalse(hasattr(D, fn), msg=f"參數.{fn}() 應已刪除")
        self.assertIn("ClampTray", D.REMOVED_SHELL_PARTS)
        self.assertIn("主板托盤.stl", D.REMOVED_STL)
        # 下裙：不是變小，是歸零
        self.assertEqual(D.SKIRT_H, 0.0)

    def test_板底六點三五淨空(self):
        # microATX §2.4.2：機殼須讓板底 ≥0.250"(6.35)；只有九孔 0.400" 方形可碰板
        self.assertAlmostEqual(D.SHOULDER_TOP_Z - D.FLOOR_T, 6.35, places=6)
        self.assertLessEqual(D.SHOULDER_OD, D.MB_KEEPOUT_D)
        self.assertAlmostEqual(D.BOARD_TOP_Z, D.SHOULDER_TOP_Z + D.PCB_T, places=6)

    def test_板躺下後內部連定位唇都放不下(self):
        """
        內寬只比板寬多 4.04 mm、內深多 1.00 mm，板底 6.35 又封死 z∈[2.4, 8.75]。
        第七輪的結論是「螺母座只能放地板以下」；第八輪把螺絲整組拿掉之後，
        同一條約束換了個形式繼續成立：**連一道從底板往上長的定位唇都放不下**，
        所以底板與牆的關係是反過來的（底板自 +Y 滑進牆的低位槽）。
        """
        inner_w = (D.FLOOR_X1 - D.FLOOR_X0) - D.BOARD_W
        inner_d = (D.FLOOR_Y1 - D.FLOOR_Y0) - D.BOARD_D
        self.assertLess(inner_w, 5.0)
        self.assertLess(inner_d, 2.0)
        # 右側與後側的餘裕都比牆厚小 → 往上長的唇一定戳到板
        self.assertLess((D.FLOOR_X1 - D.BOARD_RIGHT), D.WALL)
        self.assertLess((D.BOARD_REAR - D.FLOOR_Y0), D.WALL)
        # 因此底板改成三面伸舌，插進牆內面 z∈[0, FLOOR_T] 的低位槽
        self.assertGreater(D.FLOOR_LIP, 0.8)          # 印得出來
        self.assertLess(D.FLOOR_LIP, D.WALL)          # 不挖穿牆
        self.assertLessEqual(D.FLOOR_T, D.SHOULDER_TOP_Z - D.SHOULDER_H + 1e-9)

    def test_IO開孔外緣留得下keepout(self):
        self.assertGreaterEqual(D.io_edge_material(), D.IO_KEEPOUT + 0.8)
        self.assertLessEqual(D.CASE_LEFT, D.IO_X0 - D.IO_KEEPOUT)
        self.assertLess(D.IO_X0, D.BOARD_LEFT)

    def test_全滑槽組裝一顆螺絲都沒有(self):
        """使用者要求：後端 I/O 與 PCIe、左右側板、頂蓋、底板、主板托盤全用滑蓋卡槽。"""
        # 四道滑槽的深度都要「印得出來、又不挖穿 2.4 的牆」
        for tag, depth in (("底板舌", D.FLOOR_LIP), ("碟架舌", D.RACK_RAIL_T),
                           ("頂蓋舌", D.TOP_LIP), ("後牆定位舌", D.REAR_TAB_T)):
            self.assertGreaterEqual(depth, 0.8, msg=tag)   # ≥ 最小可印壁厚
            self.assertLess(depth, D.WALL, msg=tag)        # 背後還要留牆料
        self.assertGreater(D.SLIDE_FIT, 0.15)
        self.assertLess(D.SLIDE_FIT, 0.5)
        # detent：受的是面內剪力不是層間拉力，但半徑受定位舌厚度限制
        self.assertGreaterEqual(D.DETENT_R, 0.5)           # 最小可印特徵
        self.assertLessEqual(2 * D.DETENT_R, D.REAR_TAB_T + D.DETENT_DEPTH + 1e-9)
        self.assertLess(D.DETENT_DEPTH, D.DETENT_R)
        # 互鎖鏈的收尾：頂蓋後端半搭接進後牆鉤唇
        self.assertAlmostEqual(D.TOP_HOOK_T * 2, D.TOP_T, places=6)
        self.assertGreater(D.TOP_HOOK_D, 3.0)
        # 前罩搭接後外表面仍齊平（單一長方體）
        self.assertLess(D.SHROUD_LAP_T, D.WALL)
        self.assertGreater(D.SHROUD_LAP, 8.0)

    def test_碟架側舌高度由PCIe卡導出(self):
        """
        右側那條側舌落在 230 長 PCIe 卡的帶裡（卡伸到 y≈219），
        而且卡插拔時要整片抬 PCIE_ENGAGE —— 所以槽底必須高過「卡頂 + 抬升」。
        高度是導出的，不是挑一個看起來夠高的數字。
        """
        self.assertGreaterEqual(D.RACK_RAIL_Z0, D.PCIE_CARD_TOP_Z + D.PCIE_ENGAGE)
        self.assertAlmostEqual(D.RACK_RAIL_Z1, D.RACK_RAIL_Z0 + D.RACK_RAIL_H, places=6)
        # 側舌也不能撞到頂蓋的舌槽（兩者走側板上同一道 x 帶）
        self.assertLess(D.RACK_RAIL_Z1, D.INNER_TOP_Z - D.TOP_T)
        # 兩條橫樑都要落在側板槽的 y 帶內，而且中間留得下 SATA 線
        for by in D.RACK_BEAM_Y:
            self.assertGreater(by - D.RACK_BEAM_W / 2, D.TRAY_Y0 - 1.0)
            self.assertLess(by + D.RACK_BEAM_W / 2, D.BAY_SPLIT_Y)
        self.assertGreater(abs(D.RACK_BEAM_Y[1] - D.RACK_BEAM_Y[0]), 2 * D.RACK_BEAM_W)

    def test_全件在A1床內(self):
        self.assertLessEqual(D.CASE_W, D.A1_MAX)
        self.assertLessEqual(D.FLOOR_X1 - D.FLOOR_X0, D.A1_MAX)  # 底板
        self.assertLessEqual(D.FLOOR_Y1 - D.FLOOR_Y0, D.A1_MAX)
        self.assertLessEqual(D.OUTER_TOP_Z + D.SKIRT_H, D.A1_MAX)  # 側板／後牆立起來
        self.assertLessEqual(D.CASE_D, D.A1_MAX * 2)

    def test_PCIe開孔容得下擋板本體(self):
        self.assertGreater(D.PCIE_OPEN_W, D.PCIE_BRACKET_W)
        self.assertLess(D.PCIE_OPEN_W, D.PCIE_PITCH)
        self.assertGreaterEqual(D.PCIE_PITCH - D.PCIE_OPEN_W, 0.8)

    def test_舊旋蓋子系統的參數名不得復活(self):
        for gone in (
            "CAP_OD", "CAP_H", "CAP_COUNT", "CAP_SEAT_OD", "CAP_SEAT_RELIEF",
            "STUD_MAJOR", "STUD_MINOR", "STUD_PITCH", "STUD_LEN",
            "MB_SCREW_TAP", "MB_SCREW_DEPTH", "MB_SCREW_HEAD_D",
        ):
            self.assertFalse(hasattr(D, gone), msg=f"參數.{gone} 應已刪除")
        self.assertIn("ClampCap", D.REMOVED_SHELL_PARTS)
        self.assertIn("旋蓋.stl", D.REMOVED_STL)

    def test_主板固定是印製階梯螺柱與螺帽(self):
        """硬規則 6 的三關：牙深 ≥0.5、不破 keepout、牙必須是螺旋（幾何在 verify 驗）。"""
        self.assertGreaterEqual((D.MB_STUD_MAJOR - D.MB_STUD_MINOR) / 2, 0.5)
        self.assertLess(D.MB_NUT_OD, D.MB_KEEPOUT_D)
        self.assertLess(D.MB_STUD_MAJOR, D.PCB_HOLE_D)
        side = (D.PCB_HOLE_D - D.MB_STUD_MAJOR) / 2
        self.assertGreaterEqual(side, 0.20)
        self.assertLessEqual(side, 0.30)
        self.assertAlmostEqual(D.MB_THREAD_ENGAGE, D.MB_STUD_DEPTH - D.MB_NUT_GAP, places=6)
        self.assertGreaterEqual(D.MB_THREAD_ENGAGE, 0.35)
        crest = D.MB_STUD_PITCH * (1.0 - D.MB_STUD_ROOT_W) - 2 * D.MB_NUT_GAP
        self.assertGreaterEqual(crest, 0.4)
        self.assertGreaterEqual(D.MB_NUT_H / D.MB_STUD_PITCH, 2.0)
        self.assertAlmostEqual(D.MB_STUD_LEN, D.PCB_T + D.MB_NUT_H + 1.0, places=6)
        self.assertAlmostEqual(D.MB_STUD_TOP_Z, D.SHOULDER_TOP_Z + D.MB_STUD_LEN, places=6)
        self.assertAlmostEqual(D.MB_NUT_Z0, D.BOARD_TOP_Z, places=6)
        self.assertEqual(D.MB_NUT_COUNT, len(D.HOLES_MM))

    def test_PCIe壓條長在機殼外面(self):
        """使用者：「PCIe 壓條通常長在機殼外面，而不是往內突出」。"""
        room = D.PCIE_BRACKET_ABOVE_CARD - D.PCIE_ENGAGE
        self.assertLess(room, 1.0)  # 0.06：耳下方放不下固定塊 → 必須可拆
        self.assertAlmostEqual(D.PCIE_BAR_Z0, D.PCIE_Z1 + D.PCIE_HOLD_GAP, places=6)
        self.assertGreaterEqual(D.PCIE_BAR_Z0, D.PCIE_CARD_TOP_Z + D.PCIE_ENGAGE)
        # 壓舌：蓋滿擋板厚度，但**不得伸出後牆內面**
        self.assertGreaterEqual(D.CASE_REAR + D.PCIE_BAR_TAB_D, D.PCIE_BRACKET_Y1)
        self.assertLessEqual(D.CASE_REAR + D.PCIE_BAR_TAB_D, D.CASE_REAR + D.WALL)
        self.assertLessEqual(D.PCIE_BAR_TAB_W, D.PCIE_OPEN_W)
        # ★ 第九輪：T 軌 + 沿 X 滑入整組刪除（它逼出的連續橫縫讓三根肋變成懸臂）
        for g in ("PCIE_RAIL_Z0", "PCIE_RAIL_NECK_H", "PCIE_RAIL_HEAD_H",
                  "PCIE_RAIL_NECK_D", "PCIE_RAIL_HEAD_D"):
            self.assertFalse(hasattr(D, g), g)
        # keyhole：落差 >= 頭高，否則寬口與窄段在同一個 Z 上矛盾
        self.assertGreaterEqual(D.PCIE_BAR_DROP, D.PCIE_HOOK_H)
        # 解鎖抬起時四個壓舌不能頂到開孔頂
        self.assertLessEqual(D.PCIE_BAR_Z1 + D.PCIE_BAR_DROP, D.PCIE_Z1 + D.PCIE_LIFT)
        # 抬升帶由「卡的指入深度」與「壓條解鎖行程」取大者導出
        self.assertAlmostEqual(
            D.PCIE_LIFT,
            max(D.PCIE_ENGAGE + 1.5,
                D.PCIE_HOLD_GAP + D.PCIE_BAR_TAB_H + D.PCIE_BAR_DROP + 0.6),
            places=6,
        )
        # 頭的內面到牆的淨距 = 壓條厚 + 滑配
        self.assertAlmostEqual(
            D.PCIE_HOOK_NECK_D - D.PCIE_HOOK_FUSE - D.PCIE_BAR_T, D.PCIE_BAR_FIT, places=6
        )
        # 兩顆柱都在開孔頂之上的全寬實料帶，且落在壓條的 X 範圍內
        self.assertGreaterEqual(D.PCIE_HOOK_Z0, D.PCIE_Z1 + D.PCIE_LIFT)
        bx0, bx1 = D.pcie_bar_x()
        for hx in D.pcie_hook_x():
            self.assertGreater(hx - D.PCIE_HOOK_HEAD_W / 2, bx0)
            self.assertLess(hx + D.PCIE_HOOK_HEAD_W / 2, bx1)
            self.assertLessEqual(hx + D.PCIE_HOOK_HEAD_W / 2, D.CASE_RIGHT)
        self.assertEqual(len(D.pcie_hook_x()), 2)

    def test_PCIe肋不得是懸臂(self):
        """使用者主訴 3：PCIe 那邊幾乎完全懸空，強度太弱、印不出來。"""
        # 繫樑要有厚度（肋的上固定端）
        self.assertGreaterEqual(D.PCIE_TIE_H, 3.0)
        self.assertLessEqual(D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H, D.INNER_TOP_Z)
        # 往機殼外加厚：抗彎慣性矩至少提高一個數量級
        rib_w = D.PCIE_PITCH - D.PCIE_OPEN_W
        i_old = rib_w * D.WALL ** 3 / 12.0
        i_new = rib_w * (D.WALL + D.PCIE_RIB_D) ** 3 / 12.0
        self.assertGreaterEqual(i_new, 10 * i_old)
        # 補強不能長到壓條本體裡
        self.assertGreaterEqual(D.PCIE_BAR_Z0, D.PCIE_Z1)
        self.assertGreaterEqual(rib_w, 0.8)  # FDM 最小可印壁厚

    def test_應支援卡長由碟架導出(self):
        """刻意取捨：碟架置中之後卡與碟架的 X 帶重疊，只能二選一。"""
        self.assertAlmostEqual(
            D.PCIE_CARD_LEN, D.TRAY_Y0 - (D.CASE_REAR + D.WALL) - 2.0, places=6
        )
        self.assertGreaterEqual(D.PCIE_CARD_LEN, D.PCIE_CARD_LEN_HALF)
        self.assertAlmostEqual(D.PCIE_CARD_LEN_HALF, 167.65, places=2)  # CEM literal
        self.assertEqual(D.PCIE_COUNT, 4)  # 槽數沒有被犧牲
        # ★ 第十輪：安裝深度要算**最凸的那個**。舊版寫 CASE_D + PCIE_BAR_T，
        #   但最凸的是 keyhole 蘑菇柱（頸 5.5 + 頭 2.5 = 8.0），少報 3 mm。
        self.assertAlmostEqual(
            D.rear_outer_protrusion(),
            max(D.PCIE_BAR_T, D.PCIE_HOOK_NECK_D + D.PCIE_HOOK_HEAD_D, D.PCIE_RIB_D),
            places=6,
        )
        self.assertAlmostEqual(
            D.install_depth_mm(), D.CASE_D + D.rear_outer_protrusion(), places=6
        )
        self.assertGreater(D.install_depth_mm(), D.CASE_D + D.PCIE_BAR_T)

    def test_PCIe窗框整圈補強(self):
        """使用者主訴 4：PCIe 那邊還是很多問題。第九輪只補了三根肋。"""
        fx0, fx1 = D.pcie_frame_x()
        fz0, fz1 = D.pcie_frame_z()
        cs = D.pcie_centers()
        # 補強要涵蓋四個開孔的整個 X 帶
        self.assertLessEqual(fx0, min(cs) - D.PCIE_OPEN_W / 2)
        self.assertGreaterEqual(fx1, max(cs) + D.PCIE_OPEN_W / 2)
        # 但不准蓋到 I/O 開孔、也不准超出機殼外表面
        self.assertGreaterEqual(fx0, D.IO_X1)
        self.assertLessEqual(fx1, D.CASE_RIGHT)
        # Z 要含底檻、讓開壓條
        self.assertLessEqual(fz0, D.PCIE_Z0)
        self.assertLessEqual(fz1, D.PCIE_BAR_Z0 - D.SLIDE_FIT + 1e-9)
        # 舌袋背後的料（第九輪 1.10）
        self.assertGreaterEqual(D.WALL + D.PCIE_RIB_D - D.PCIE_TANG_POCKET, 3.0)
        # keyhole 柱的頸斷面（整條壓條掛在兩根上；第九輪 4.0×5.5 = 22）
        self.assertGreaterEqual(D.PCIE_HOOK_NECK_W * D.PCIE_HOOK_NECK_D, 40.0)
        self.assertGreater(D.PCIE_HOOK_HEAD_W, D.PCIE_HOOK_NECK_W + 2 * (D.PCIE_BAR_FIT + 1.0))

    def test_每一道滑槽都留了滑配(self):
        """★ 第十輪：量出來全機配合面都是 nominal 零間隙（硬規則 19）。"""
        # 槽深 = 舌 + 滑配；槽背後必須還剩得下最小可印壁厚
        for tag, lip in (("底板", D.FLOOR_LIP), ("頂蓋", D.TOP_LIP)):
            self.assertAlmostEqual(lip, D.WALL - D.GROOVE_BACK_MIN - D.SLIDE_FIT, places=6, msg=tag)
            self.assertGreaterEqual(D.WALL - (lip + D.SLIDE_FIT), D.GROOVE_BACK_MIN - 1e-9, tag)
        # 承載唇＝地板厚 − 舌厚 − 滑配，且仍可印
        self.assertAlmostEqual(
            D.FLOOR_LEDGE_T, D.FLOOR_T - D.FLOOR_LIP_T - D.SLIDE_FIT, places=6
        )
        self.assertGreaterEqual(D.FLOOR_LEDGE_T, 0.8)
        self.assertGreaterEqual(D.FLOOR_LIP_T, 0.8)
        # 頂蓋咬合量（第九輪只有 0.40）
        self.assertGreaterEqual(D.TOP_LIP, 1.0)
        # 碟架頂板 ↔ 頂蓋底面：第九輪 INNER_TOP_Z 直接取 RACK_TOP_Z1 → 兩面共面
        self.assertAlmostEqual(D.RACK_TOP_GAP, D.SLIDE_FIT, places=9)
        self.assertGreaterEqual(D.INNER_TOP_Z, D.RACK_TOP_Z1 + D.RACK_TOP_GAP - 1e-9)
        self.assertAlmostEqual(
            D.INNER_TOP_Z,
            max(D.ATX_Z1 + D.PSU_CLEAR_MIN,
                D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H,
                D.RACK_TOP_Z1 + D.RACK_TOP_GAP,
                D.AREA_A_TOP_Z),
            places=9,
        )
        self.assertGreater(D.TOP_LIP, D.TOP_LIP - 2 * D.TOP_FIT_GAP)

    def test_底板與側板後板都要有保持力(self):
        """使用者主訴 2b：底板與左右側板、後板之間缺卡榫。"""
        # 底板側緣 bead：過盈必須大於滑配，否則只是裝飾
        self.assertGreater(D.FLOOR_DETENT_DEPTH, D.SLIDE_FIT)
        self.assertGreaterEqual(D.FLOOR_DETENT_R, 0.5)
        self.assertEqual(D.FLOOR_DETENT_N, len(D.floor_detent_sites(True)))
        # 過盈行程只能是全程的一小段（球長在底板後段）
        self.assertLessEqual(
            D.floor_detent_run_mm(), 0.2 * (D.BAY_SPLIT_Y - D.FLOOR_Y0)
        )
        # 左右對稱
        for (lx, ly), (rx, ry) in zip(D.floor_detent_sites(True), D.floor_detent_sites(False)):
            self.assertAlmostEqual(ly, ry, places=6)
            self.assertAlmostEqual(
                lx - (D.FLOOR_X0 + D.SLIDE_FIT), (D.FLOOR_X1 - D.SLIDE_FIT) - rx, places=6
            )
        # 後緣舌半球：球不得從舌的另一面戳出去
        self.assertLessEqual(
            2 * D.FLOOR_REAR_DETENT_R, D.FLOOR_LIP_T + D.DETENT_DEPTH + 1e-9
        )
        self.assertGreaterEqual(len(D.REAR_FLOOR_DETENT_X), 2)
        # 前罩四面都有 detent（第九輪只有左右）
        self.assertGreaterEqual(len(D.SHROUD_DETENT_Z), 3)
        self.assertGreaterEqual(len(D.SHROUD_LAP_DETENT_X), 2)

    def test_後牆的卡榫必須是單向的(self):
        """★ 第十一輪：半球受拉會自己爬出來，後牆是受 −Y 力最多的那一面。

        使用者第十輪問「你確定有做好嗎？就像頂蓋那樣可以卡住」——
        量出來後牆往 −Y 走 12 mm 都沒有任何幾何擋住，只有八顆半球在摩擦。
        """
        # 楔要放得進口袋：斜坡 + 平台必須落在定位舌的長度內
        self.assertLess(D.REAR_WEDGE_RAMP + D.REAR_WEDGE_BACK, D.REAR_TAB_D)
        # 直角面前方要留得下一段整片舌料（缺口是自舌根往前開的，不是舌中間挖孔）
        lig = D.REAR_TAB_D - (D.REAR_WEDGE_RAMP + D.REAR_WEDGE_BACK) - D.SLIDE_FIT / 2
        self.assertGreaterEqual(lig, 1.0, "直角面前的舌料太薄，一拉就掰斷")
        # 斜坡不能太陡，否則推不進去（0.6/1.5 ≈ 21.8°，snap-fit 常用 20–30°）
        slope = math.degrees(math.atan2(D.DETENT_DEPTH, D.REAR_WEDGE_RAMP))
        self.assertLessEqual(slope, 30.0)
        self.assertGreaterEqual(slope, 10.0)
        # 楔沿 Z 的高度要可印，而且比缺口小（Z 定位是槽的事）
        self.assertGreaterEqual(D.REAR_WEDGE_H, 2.0)
        self.assertGreater(D.DETENT_DEPTH, D.SLIDE_FIT)  # 不是裝飾
        # 前罩／碟托盤是**刻意可徒手拆**的，它們的 detent 不准也變成單向
        self.assertGreaterEqual(D.SHROUD_DETENT_R, 0.5)
        self.assertGreater(D.SHROUD_DETENT_DEPTH, D.SLIDE_FIT)

    def test_碟架推到底要有止擋(self):
        """★ 第十一輪：第十輪槽的後端開到 TRAY_Y0 − 1.0，碟架往 −Y 浮 3.00 mm。"""
        rear_tab_y = min(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2
        self.assertAlmostEqual(D.RACK_STOP_Y, rear_tab_y - D.SLIDE_FIT, places=9)
        self.assertGreater(D.RACK_STOP_Y, D.TRAY_Y0 - 1.0, "盲端沒有往前收，還是會浮")
        # 盲端不能收過頭把側舌擋在外面
        self.assertLess(D.RACK_STOP_Y, max(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2)

    def test_組裝順序是唯一來源(self):
        """使用者指定的順序：底板 → 側板 → 後板 → 碟架 → 頂蓋 → 前罩。"""
        keys = [k for k, _ in D.ASSEMBLY_STEPS]
        self.assertEqual(keys[0], "Bottom_Tray")
        self.assertEqual(keys[1:3], ["Side_Left_MB", "Side_Right_MB"])
        self.assertEqual(keys[3], "Rear_IO_PCIe")
        self.assertLess(keys.index("HDD_Rack"), keys.index("Top_MB"))
        self.assertLess(keys.index("Top_MB"), keys.index("Front_Shroud"))
        # 每一個機殼結構件都要在表裡（漏一件就沒有人驗它裝不裝得進去）
        need = {"Bottom_Tray", "Rear_IO_PCIe", "Side_Left_MB", "Side_Right_MB",
                "Top_MB", "Front_Shroud", "HDD_Rack", "HDD_Tray"}
        self.assertTrue(need <= set(keys), f"漏了 {sorted(need - set(keys))}")
        # 底板是基準（不動）；側板往 −Y 滑上去；後板往 +Y 推進來
        d = dict(D.ASSEMBLY_STEPS)
        self.assertEqual(d["Bottom_Tray"], 0.0)
        self.assertLess(d["Side_Left_MB"], 0.0)
        self.assertGreater(d["Rear_IO_PCIe"], 0.0)

    def test_電源落入要讓開後牆頂鉤唇(self):
        # 第八輪：後牆的頂蓋承托肩刪了（頂蓋改滑入），X 向不必再讓位；
        # 改成必須讓開**後牆頂鉤唇**——電源後面板要貼後牆就得先閃過它。
        self.assertEqual(D.PSU_SLIDE_X, 0.0)
        self.assertGreater(D.PSU_SLIDE_Y, D.TOP_HOOK_D)
        self.assertGreaterEqual(D.psu_slide_room(), D.PSU_SLIDE_X)


    def test_列印件清單與結構鍵同源(self):
        self.assertEqual(tuple(D.STL_NAMES), D.STRUCT_PART_KEYS)
        self.assertIn("PCIeBar", D.STL_NAMES)
        self.assertIn("MB_Nut", D.STL_NAMES)
        self.assertEqual(len(set(D.STL_NAMES.values())), len(D.STL_NAMES))

    def test_碟用底孔鎖在托盤上(self):
        """
        平躺姿態該用的是 SFF-8301 的**底面孔**。拿側孔（A8/A9/A10）來用，
        就是八顆螺絲鎖進塑膠——那是第五輪踩過的。
        """
        self.assertFalse(hasattr(D, "HDD_SIDE_FROM_FACE"))
        self.assertFalse(hasattr(D, "HDD_ACCESS_D"))
        self.assertEqual(len(D.hdd_bottom_hole_xy(0)), 6)  # 三排 × 兩側
        # 螺絲穿入碟體的量必須落在規格區間（SFF-8301 p7）
        pen = 6.35 - D.TRAY_T  # #6-32 × 1/4"
        self.assertGreaterEqual(pen, 2.39)
        self.assertLessEqual(pen, 3.56)
        # 沉頭：螺絲頭不得凸出托盤底面，否則吃掉層節距
        self.assertGreater(D.HDD_SCREW_HEAD_D, D.HDD_SCREW_CLR)
        self.assertLess(D.HDD_SCREW_HEAD_T, D.TRAY_T)


    def test_A1床規格必須與BambuStudio_profile一致(self):
        """
        踩過的坑：把 P1/X1 的 18×28 排除區與 fdm_machine_common 的 250 預設高度
        當成 A1 的規格寫進文件（來源是搜尋摘要）。本機就裝著權威來源，直接讀它。
        """
        import glob
        import json

        cands = glob.glob(
            os.path.join(r"C:\Program Files", "Bambu Studio*", D.A1_PROFILE_REL)
        ) + glob.glob(os.path.join(r"C:\Program Files", "OrcaSlicer*", D.A1_PROFILE_REL))
        if not cands:
            self.skipTest("本機沒有 Bambu Studio profile")

        def _load(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        prof = _load(cands[0])
        self.assertEqual(prof.get("bed_exclude_area"), [], "A1 沒有排除區")
        self.assertEqual(tuple(D.A1_EXCLUDE), ())
        self.assertEqual(int(prof["printable_height"]), int(D.A1_H_MAX))
        area = prof.get("printable_area") or _load(
            os.path.join(os.path.dirname(cands[0]), prof["inherits"] + ".json")
        )["printable_area"]
        xs = [float(p.split("x")[0]) for p in area]
        ys = [float(p.split("x")[1]) for p in area]
        self.assertAlmostEqual(max(xs), D.A1_MAX, places=3)
        self.assertAlmostEqual(max(ys), D.A1_MAX, places=3)

    def test_外殼接合不再有任何五金(self):
        """第八輪改全滑槽：銅母、M3、頂蓋螺絲座、搭接片全部不存在。"""
        for gone in ("M3_INSERT_D", "M3_TAP", "M3_CLR", "M3_INSERT_BORE",
                     "M3_BOSS_W", "M3_BOSS_L", "CAGE_LAP_W", "TOP_SCREW_BOSS_H"):
            self.assertFalse(hasattr(D, gone), msg=gone)
        # 剩下的五金只有 PSU 四顆 #6-32 與碟的底孔螺絲 —— 都是鎖在鋼件上的
        self.assertAlmostEqual(D.ATX_SCREW_CLR, 3.7, places=2)
        self.assertAlmostEqual(D.HDD_SCREW_CLR, 3.6, places=2)


    def test_頂蓋單片滑入且被互鎖(self):
        """
        第八輪頂蓋是**單片、自 +Y 滑入**：兩側舌插進側板槽（槽上方仍是牆料 →
        抬不起來），後端半搭接鑽進後牆鉤唇下方（→ 側板也抽不上去），
        前端由前罩擋住（→ 不會自己滑出來）。第七輪的兩片半搭接與螺絲座全刪。
        """
        self.assertGreater(D.TOP_FIT_GAP, 0.2)
        self.assertLess(D.TOP_FIT_GAP, 1.0)
        self.assertGreaterEqual(D.TOP_LIP, 0.8)
        self.assertLess(D.TOP_LIP, D.WALL)
        self.assertAlmostEqual(D.TOP_HOOK_T * 2, D.TOP_T, places=6)
        self.assertGreater(D.TOP_HOOK_D, D.TOP_LIP)
        self.assertFalse(hasattr(D, "TOP_SEAM_Y"))
        self.assertFalse(hasattr(D, "TOP_LAP_W"))
        # 頂蓋舌槽不得與碟架舌槽重疊（兩者走側板上同一道 x 帶）
        self.assertGreater(D.INNER_TOP_Z - D.TOP_T, D.RACK_RAIL_Z1)


    def test_進氣只有前柵(self):
        # 氣流一條龍：前柵（前罩下段 + 每片碟托盤的前擋板）→ 碟 → 主板腔
        #             → 電源風扇（朝下）→ 後方排出
        import math

        self.assertGreaterEqual(D.front_vent_area(), math.pi * 60.0 ** 2)
        self.assertGreater(D.FRONT_VENT_PITCH, D.FRONT_VENT_SLAT)  # 條與條之間要有料
        self.assertLessEqual(D.FRONT_VENT_Z1, D.HDD_Z0)            # 下段柵在碟陣底下
        self.assertGreaterEqual(D.TRAY_VENT_ROWS, 1)
        # 托盤擋板放得下那幾排柵
        need = 4.0 + (D.TRAY_VENT_ROWS - 1) * D.FRONT_VENT_PITCH + D.FRONT_VENT_SLAT
        self.assertLessEqual(need, D.TRAY_PITCH - 2 * D.TOP_FIT_GAP)



class Test虛擬件可裝性(unittest.TestCase):
    """硬體是鋼盒／鋼板；印件必須讓開它們的標稱包絡（幾何檢查在 verify）。"""

    def test_PSU讓開本體(self):
        self.assertGreater(D.PSU_FIT_GAP, 0.0)
        self.assertLess(D.PSU_FIT_GAP, 2.0)
        self.assertGreaterEqual(D.ATX_D_ALLOW, D.ATX_D)
        self.assertGreaterEqual(D.ATX_Y1 - D.ATX_Y0, D.ATX_D)
        # 長機身（160）也不能越出 Area A
        self.assertLessEqual(D.ATX_Y1, D.AREA_A_Y_NEAR)

    def test_擋板尺寸全部來自CEM(self):
        self.assertAlmostEqual(D.PCIE_BRACKET_TOTAL_H, 120.02, places=2)
        self.assertAlmostEqual(D.PCIE_BODY_H, 112.75, places=2)
        self.assertAlmostEqual(D.PCIE_TANG_H, 7.27, places=2)
        self.assertAlmostEqual(D.PCIE_TANG_W, 14.30, places=2)
        self.assertAlmostEqual(D.PCIE_BRACKET_W, 18.42, places=2)
        self.assertAlmostEqual(D.PCIE_BRACKET_T, 0.86, places=2)
        self.assertAlmostEqual(D.PCIE_Z1 - D.PCIE_Z0, D.PCIE_BODY_H, places=3)
        self.assertAlmostEqual(D.PCIE_Z0 - D.PCIE_TANG_Z0, D.PCIE_TANG_H, places=3)

    def test_擋板Z位置由DIM_A導出(self):
        self.assertAlmostEqual(D.PCIE_CARD_TOP_ABOVE_BOARD, 114.55, places=2)
        self.assertAlmostEqual(D.PCIE_Z1 - D.BOARD_TOP_Z, 114.55 + 4.56, places=3)
        self.assertAlmostEqual(D.PCIE_CARD_Z1, D.BOARD_TOP_Z + 114.55, places=3)
        self.assertLessEqual(D.PCIE_CARD_HALF_W * 2, D.PCIE_PITCH)
        # 舌尖不得插進底板
        self.assertGreater(D.PCIE_TANG_Z0, D.FLOOR_T)

    def test_舌袋是盲袋且深過料厚(self):
        self.assertGreater(D.PCIE_TANG_POCKET, D.PCIE_BRACKET_T)
        self.assertLess(D.PCIE_TANG_POCKET, D.WALL)

    def test_開孔上方要有繫樑(self):
        self.assertGreater(D.PCIE_TIE_H, 2.0)
        self.assertGreaterEqual(D.INNER_TOP_Z, D.PCIE_Z1 + D.PCIE_LIFT + D.PCIE_TIE_H)
        self.assertLess(D.PCIE_HOLD_GAP, 1.0)

    def test_折耳帶keepout(self):
        self.assertAlmostEqual(D.PCIE_EAR_INWARD, 11.43, places=2)  # Fig.6-4 俯視
        self.assertGreater(D.PCIE_EAR_CLEAR, D.PCIE_EAR_INWARD)
        self.assertLess(D.PCIE_EAR_CLEAR, D.PCIE_EAR_INWARD + 2.0)
        self.assertGreater(D.PCIE_EAR_BAND, 2.0)

    def test_卡長支援至少半長卡(self):
        # ★ 第九輪：碟架置中之後卡與碟架的 X 帶重疊，卡長由碟架後緣切出來。
        #   仍然 >= CEM 半長卡 167.65，而且四個全高槽一個都沒少。
        self.assertGreaterEqual(D.PCIE_CARD_LEN, D.PCIE_CARD_LEN_HALF)
        self.assertLessEqual(D.CASE_REAR + D.WALL + D.PCIE_CARD_LEN, D.TRAY_Y0)

    def test_槽蓋能封住空槽(self):
        self.assertGreaterEqual(D.PCIE_BLANK_T, 1.2)
        self.assertLess(D.PCIE_BLANK_T, D.WALL)
        self.assertGreater(D.PCIE_BLANK_EAR, 4.0)
        self.assertLess(D.PCIE_BLANK_EAR, D.PCIE_EAR_CLEAR)


class Test裝配動作(unittest.TestCase):
    """最終位置合法 ≠ 走得到那個位置。這一類檢查問的是「路」。"""

    def test_PCIe抬升量出自CEM原始頁碼(self):
        self.assertAlmostEqual(D.PCIE_CONN_H, 7.90, places=2)
        self.assertAlmostEqual(D.PCIE_CARD_H, 111.15, places=2)
        self.assertAlmostEqual(D.PCIE_CARD_BOTTOM, 3.40, places=2)
        self.assertAlmostEqual(D.PCIE_ENGAGE, 4.50, places=2)
        self.assertGreater(D.PCIE_LIFT, D.PCIE_ENGAGE)

    def test_PSU後面板只能被四顆螺絲的墊蓋住(self):
        r = D.ATX_SCREW_CLR / 2
        for hx, hz in D.ATX_HOLES:
            inside_x = D.PSU_WIN_X0 - r <= hx <= D.PSU_WIN_X1 + r
            inside_z = D.PSU_WIN_Z0 - r <= hz <= D.PSU_WIN_Z1 + r
            self.assertFalse(inside_x and inside_z, f"螺絲 ({hx},{hz}) 落在開窗裡")
        area = (D.PSU_WIN_X1 - D.PSU_WIN_X0) * (D.PSU_WIN_Z1 - D.PSU_WIN_Z0)
        self.assertGreater(area / (D.ATX_W * D.ATX_H), 0.60)
        self.assertLess(D.PSU_WIN_Z0, 12.0)
        self.assertGreater(D.PSU_WIN_X1, 135.0)

    def test_碟底孔逐顆對SFF_8301(self):
        """
        Fig.3-1（p8）圖上量到的基準：A7 自**接頭端**→第一排、A6 第一排→第二排、
        A13 第一排→第三排、A5 側緣→孔心、A4 兩側孔中心距。
        §3.1：只有 A7 那對是必要的，A6／A13 二選一必要 → 三排全開。
        """
        self.assertAlmostEqual(D.HDD_BOT_FROM_CONN[0], 41.28, places=2)          # A7
        self.assertAlmostEqual(D.HDD_BOT_FROM_CONN[1], 41.28 + 44.45, places=2)  # +A6
        self.assertAlmostEqual(D.HDD_BOT_FROM_CONN[2], 41.28 + 76.20, places=2)  # +A13
        self.assertAlmostEqual(D.HDD_BOT_FROM_SIDE, 3.18, places=2)              # A5
        self.assertAlmostEqual(D.HDD_BOT_PITCH_Y, 95.25, places=2)               # A4
        self.assertAlmostEqual(2 * D.HDD_BOT_FROM_SIDE + D.HDD_BOT_PITCH_Y, D.HDD_W, places=1)
        # 孔全部落在碟的投影內，而且接頭端在 +X（使用者指定朝內／朝 PCIe 側）
        for hx, hy in D.hdd_bottom_hole_xy(0):
            self.assertGreater(hx, D.HDD_X0)
            self.assertLess(hx, D.HDD_X1)
            self.assertGreater(hy, D.HDD_Y0)
            self.assertLess(hy, D.HDD_Y1)
        self.assertLess(max(h[0] for h in D.hdd_bottom_hole_xy(0)),
                        D.HDD_X1 - D.HDD_BOT_FROM_CONN[0] + 0.01)


    def test_機殼整片底板落地(self):
        """
        第六輪是六隻圓腳、第七輪是整圈下裙。第八輪把螺絲整組拿掉之後，
        下裙唯一的存在理由（放螺母座）沒了 → 直接刪，省 10 mm 高度。
        """
        self.assertEqual(D.SKIRT_H, 0.0)
        self.assertFalse(hasattr(D, "foot_sites_cage"))
        self.assertFalse(hasattr(D, "M3_BASE_Z"))
        w, d, h = D.envelope_mm()
        self.assertAlmostEqual(h, D.OUTER_TOP_Z, places=6)  # 機殼底面就是 z=0


    def test_有電源按鈕而且鎖得上(self):
        self.assertGreater(D.PWR_BTN_D, 8.0)
        self.assertGreaterEqual(D.pwr_btn_corridor_w(), D.PWR_BTN_NUT_D)
        # ★ 第九輪：按鈕在**碟架右側那條空帶**（碟架置中後左右各 29.44），
        #   不是碟架裡面的接頭區——那條帶被托盤與線佔著。
        lo, hi = D.RACK_POST_X1, D.CASE_RIGHT - D.WALL
        self.assertGreater(D.pwr_btn_x() - D.PWR_BTN_NUT_D / 2, lo)
        self.assertLess(D.pwr_btn_x() + D.PWR_BTN_NUT_D / 2, hi)
        # ★ 按鈕在碟陣**下方**那片固定前板上：它不能長在會被抽走的碟托盤上
        self.assertLess(D.PWR_BTN_Z + D.PWR_BTN_D / 2, D.HDD_Z0)
        self.assertGreater(D.PWR_BTN_Z - D.PWR_BTN_D / 2, D.FLOOR_T)


    def test_每個STL都有份數而且份數由既有常數導出(self):
        """
        第十一輪：`PRINT_VOLUME` 一直是逐件加總、沒乘份數，
        於是文件寫的「印料 1032 cm³」少算碟托盤 ×3 與壓帽 ×8（實際 1240，差 20%）。
        份數表必須涵蓋每個 STL（漏件 = 買料短缺），而且不准寫魔術數字。
        """
        self.assertEqual(set(D.PART_QTY), set(D.STL_NAMES))
        for k, n in D.PART_QTY.items():
            self.assertIsInstance(n, int, k)
            self.assertGreaterEqual(n, 1, k)
        # 由既有常數導出，不是手打的數字
        self.assertEqual(D.PART_QTY["HDD_Tray"], D.HDD_COUNT)
        self.assertEqual(D.PART_QTY["MB_Nut"], D.MB_NUT_COUNT)
        self.assertEqual(D.PART_QTY["PCIeBlank"], D.PCIE_COUNT)
        # 含份數的總件數必須 > 一件一份（否則這張表沒有作用＝vacuous）
        self.assertGreater(sum(D.PART_QTY.values()), len(D.STL_NAMES))

    def test_每個列印件的最大投影邊都塞不下5mm_brim(self):
        """
        `CASE_W = 252.68`、A1 床 256 → 大件單邊只剩 1.66~3.16 mm。
        預設 process 的 `brim_width = 5` 放不下：brim 會被擠出床外或直接失敗。
        這條是「文件寫關 brim」的機器可驗版本。
        """
        margin = (D.A1_MAX - D.CASE_W) / 2.0
        self.assertLess(margin, 5.0)  # 5 mm brim 放不下
        self.assertGreater(margin, 0.0)  # 但本體本身放得下


if __name__ == "__main__":
    unittest.main()
