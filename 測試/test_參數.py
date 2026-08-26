"""單元測試：腳本/參數.py"""

from __future__ import annotations

import io
import math
import os
import re
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

    def test_Chassis四件一體式有真實重疊(self):
        self.assertGreaterEqual(D.CHASSIS_OVERLAP, 0.8)
        self.assertLess(D.CHASSIS_OVERLAP, D.WALL)
        self.assertEqual(D.ASSEMBLY_STEPS[0], ("Chassis_Body", 0.0))
        for old in ("Bottom_Tray", "Rear_IO_PCIe", "Side_Left_MB", "Side_Right_MB"):
            self.assertNotIn(old, D.STL_NAMES)
            self.assertIn(old, D.REMOVED_SHELL_PARTS)

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

    def test_STL_NAMES八件(self):
        expected = {
            "Chassis_Body", "Top_MB", "Front_Shroud", "HDD_Rack",
            "HDD_Tray", "PCIeBlank", "PCIeBar", "MB_Screw",
        }
        self.assertEqual(set(D.STL_NAMES), expected)
        self.assertEqual(len(D.STL_NAMES), 8)
        self.assertEqual(
            D.STRUCT_PART_KEYS,
            ("Top_MB", "Front_Shroud", "HDD_Rack", "HDD_Tray"),
        )
        self.assertEqual(len(set(D.STL_NAMES.values())), len(D.STL_NAMES))
        for old in ("Bottom_Tray", "Rear_IO_PCIe", "Side_Left_MB", "Side_Right_MB", "MB_Nut"):
            self.assertNotIn(old, D.STL_NAMES)

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

    def test_板躺下後只有九孔支撐肩可進淨空(self):
        inner_w = (D.FLOOR_X1 - D.FLOOR_X0) - D.BOARD_W
        inner_d = (D.FLOOR_Y1 - D.FLOOR_Y0) - D.BOARD_D
        self.assertLess(inner_w, 5.0)
        # ★ 第十三輪：後牆內面 = I/O aperture 平面（Fig.4 側視 12.27），
        #   板後緣到它是 2.11 而不是舊的 MARGIN 0.5 —— 連接器面比板緣還往後
        #   突出 1.14（Fig.5 note 11.30），0.5 的話板根本推不到底。
        self.assertLess(inner_d, 3.0)
        self.assertAlmostEqual(
            D.BOARD_REAR - (D.CASE_REAR + D.WALL), 2.11, places=2
        )
        self.assertLess(D.FLOOR_X1 - D.BOARD_RIGHT, D.WALL)
        self.assertLess(D.BOARD_REAR - D.FLOOR_Y0, D.WALL)
        self.assertFalse(hasattr(D, "FLOOR_LIP"))
        self.assertLessEqual(D.SHOULDER_OD, D.MB_KEEPOUT_D)
        self.assertAlmostEqual(D.SHOULDER_TOP_Z - D.FLOOR_T, 6.35, places=6)

    def test_IO開孔外緣留得下keepout(self):
        self.assertGreaterEqual(D.io_edge_material(), D.IO_KEEPOUT + 0.8)
        self.assertLessEqual(D.CASE_LEFT, D.IO_X0 - D.IO_KEEPOUT)
        self.assertLess(D.IO_X0, D.BOARD_LEFT)

    def test_一體本體與可拆件接合(self):
        for gone in (
            "M3_INSERT_D", "M3_TAP", "FLOOR_LIP", "REAR_TAB_D",
            "REAR_WEDGE_H", "PCIE_HOOK_NECK_W", "PCIE_BAR_DROP",
        ):
            self.assertFalse(hasattr(D, gone), msg=gone)
        self.assertAlmostEqual(
            D.TOP_LIP,
            D.WALL - D.GROOVE_BACK_MIN - D.SLIDE_FIT,
            places=6,
        )
        self.assertGreaterEqual(D.TOP_LIP, 1.0)
        self.assertGreater(D.RACK_RAIL_T, D.SLIDE_FIT)
        self.assertEqual(len(D.TOP_DETENT_X), 2)
        self.assertEqual(D.SHROUD_LAP, 14.0)

    def test_碟架側舌高度由碟架頂導出(self):
        """側舌貼近碟架頂板以縮短承載力臂，不再由已縮短的 PCIe 卡包絡決定。"""
        self.assertAlmostEqual(D.RACK_RAIL_Z1, D.HDD_TOP_Z - 2.0, places=6)
        self.assertAlmostEqual(
            D.RACK_RAIL_Z0,
            D.RACK_RAIL_Z1 - D.RACK_RAIL_H,
            places=6,
        )
        self.assertLess(D.RACK_RAIL_Z1, D.RACK_TOP_Z1)
        self.assertGreater(D.RACK_RAIL_Z0, D.RACK_Z0)
        # 兩條橫樑都要落在側板槽的 y 帶內，而且中間留得下 SATA 線。
        for by in D.RACK_RAIL_BEAM_Y:
            self.assertGreater(by - D.RACK_BEAM_W / 2, D.TRAY_Y0 - 1.0)
            self.assertLess(by + D.RACK_BEAM_W / 2, D.BAY_SPLIT_Y)
        # ★ 第十三輪第三根樑在**前罩段**（坐前罩承托肩），沒有側舌也不該有
        self.assertEqual(len(D.RACK_BEAM_Y), 3)
        self.assertEqual(len(D.RACK_RAIL_BEAM_Y), 2)
        self.assertGreater(max(D.RACK_BEAM_Y), D.BAY_SPLIT_Y)
        self.assertLess(max(D.RACK_BEAM_Y) + D.RACK_BEAM_W / 2, D.SHROUD_LEDGE_Y1)
        self.assertGreater(abs(D.RACK_BEAM_Y[1] - D.RACK_BEAM_Y[0]), 2 * D.RACK_BEAM_W)

    def test_一體Chassis名目尺寸在A1床內(self):
        chassis_dims = (
            D.CASE_W,
            D.BAY_SPLIT_Y - (D.CASE_REAR - D.PCIE_RIB_D),
            D.OUTER_TOP_Z,
        )
        self.assertEqual(tuple(round(v, 2) for v in chassis_dims), (252.68, 252.85, 180.12))
        self.assertTrue(all(v <= D.A1_MAX for v in chassis_dims))
        self.assertLessEqual(D.CASE_W, D.A1_MAX)
        self.assertLessEqual(D.OUTER_TOP_Z, D.A1_H_MAX)

    def test_PCIe開孔容得下擋板本體(self):
        self.assertGreater(D.PCIE_OPEN_W, D.PCIE_BRACKET_W)
        self.assertLess(D.PCIE_OPEN_W, D.PCIE_PITCH)
        self.assertGreaterEqual(D.PCIE_PITCH - D.PCIE_OPEN_W, 0.8)

    def test_舊旋蓋子系統的參數名不得復活(self):
        for gone in (
            "CAP_OD", "CAP_H", "CAP_COUNT", "CAP_SEAT_OD", "CAP_SEAT_RELIEF",
            "STUD_MAJOR", "STUD_MINOR", "STUD_PITCH", "STUD_LEN",
            "MB_SCREW_TAP", "MB_SCREW_DEPTH",
        ):
            self.assertFalse(hasattr(D, gone), msg=f"參數.{gone} 應已刪除")
        self.assertIn("ClampCap", D.REMOVED_SHELL_PARTS)
        self.assertIn("旋蓋.stl", D.REMOVED_STL)

    def test_主板固定是盲內牙與印製六角螺絲(self):
        for gone in ("MB_STUD_MAJOR", "MB_STUD_MINOR", "MB_NUT_OD", "MB_NUT_H"):
            self.assertFalse(hasattr(D, gone), msg=gone)
        self.assertGreaterEqual(D.MB_THREAD_DEPTH, 0.5)
        self.assertLess(D.MB_THREAD_MAJOR, D.PCB_HOLE_D)
        side = (D.PCB_HOLE_D - D.MB_THREAD_MAJOR) / 2
        self.assertGreaterEqual(side, 0.20)
        self.assertLessEqual(side, 0.30)
        self.assertAlmostEqual(
            D.MB_THREAD_ENGAGE,
            D.MB_THREAD_DEPTH - D.MB_THREAD_GAP,
            places=6,
        )
        female_crest = D.MB_THREAD_PITCH * (1.0 - D.MB_THREAD_ROOT_W) - 2 * D.MB_THREAD_GAP
        self.assertGreaterEqual(female_crest, 0.8)
        self.assertAlmostEqual(D.MB_THREAD_ENGAGEMENT / D.MB_THREAD_PITCH, 2.0, places=6)
        self.assertAlmostEqual(
            D.MB_SOCKET_DEPTH,
            D.MB_THREAD_ENGAGEMENT + D.MB_SOCKET_END_GAP,
            places=6,
        )
        self.assertGreaterEqual(D.MB_SOCKET_BOTTOM_MATERIAL, 0.8)
        self.assertAlmostEqual(
            D.MB_SCREW_THREAD_LEN,
            D.PCB_T + D.MB_THREAD_ENGAGEMENT,
            places=6,
        )
        self.assertLess(D.MB_SCREW_HEAD_D, D.MB_KEEPOUT_D)
        self.assertEqual(D.MB_SCREW_COUNT, len(D.HOLES_MM))

    def test_PCIe壓條鎖進印製盲內牙且沿用MB_Screw(self):
        """第十三輪（使用者：那個 PCIe 壓條根本沒有用）。"""
        self.assertEqual(D.PCIE_BAR_T, 5.0)
        self.assertEqual(len(D.pcie_lock_x()), 2)
        self.assertEqual(D.PCIE_BAR_SCREW_COUNT, 2)
        # 夾持厚 = PCB_T ⇒ 同一顆 MB_Screw 通用，不新增第九種 STL
        self.assertAlmostEqual(D.PCIE_BAR_SEAT_T, D.PCB_T, places=6)
        self.assertGreaterEqual(D.PCIE_BAR_CBORE_D, D.MB_SCREW_HEAD_D)
        self.assertGreaterEqual(D.PCIE_BAR_T - D.PCIE_BAR_SEAT_T, D.MB_SCREW_HEAD_H)
        # 盲牙不得打穿到內腔
        self.assertGreaterEqual(
            (D.CASE_REAR + D.WALL) - D.pcie_lock_socket_end(), 0.8
        )
        # 鎖點落在最外兩根槽間肋的正上方（拉力回到肋的上端固定端）
        ribs = D.pcie_rib_x()
        self.assertEqual(set(D.pcie_lock_x()), {ribs[0], ribs[-1]})
        self.assertAlmostEqual(D.PCIE_LIFT, D.PCIE_ENGAGE + 1.5, places=6)
        bx0, bx1 = D.pcie_bar_x()
        for x in D.pcie_lock_x():
            self.assertGreater(x - D.PCIE_BAR_CBORE_D / 2, bx0)
            self.assertLess(x + D.PCIE_BAR_CBORE_D / 2, bx1)
        for gone in (
            "PCIE_BAR_DROP", "PCIE_HOOK_NECK_W", "PCIE_HOOK_HEAD_W",
            "PCIE_LOCK_PILOT_D", "PCIE_LOCK_PILOT_DEPTH", "PCIE_LOCK_CLEAR_D",
            "PCIE_LOCK_SCREW_LEN", "PCIE_LOCK_SCREW_HEAD_H", "PCIE_LOCK_BOSS_W",
        ):
            self.assertFalse(hasattr(D, gone), msg=gone)
        self.assertFalse(hasattr(D, "pcie_hook_x"))

    def test_PCIe肋不得是懸臂(self):
        """使用者主訴 3：PCIe 那邊幾乎完全懸空，強度太弱、印不出來。"""
        # 繫樑要有厚度（肋的上固定端）
        self.assertGreaterEqual(D.PCIE_TIE_H, 3.0)
        self.assertLessEqual(D.PCIE_TIE_Z1, D.INNER_TOP_Z)
        # 往機殼外加厚：抗彎慣性矩至少提高一個數量級
        rib_w = D.PCIE_PITCH - D.PCIE_OPEN_W
        i_old = rib_w * D.WALL ** 3 / 12.0
        i_new = rib_w * (D.WALL + D.PCIE_RIB_D) ** 3 / 12.0
        self.assertGreaterEqual(i_new, 10 * i_old)
        # 補強不能長到壓條本體裡
        self.assertGreaterEqual(D.PCIE_BAR_Z0, D.PCIE_Z1)
        self.assertGreaterEqual(rib_w, 0.8)  # FDM 最小可印壁厚

    def test_應支援卡長與完整安裝深度皆由幾何鏈導出(self):
        self.assertAlmostEqual(
            D.PCIE_CARD_LEN,
            D.TRAY_Y0 - (D.CASE_REAR + D.WALL) - 2.0,
            places=6,
        )
        self.assertGreaterEqual(D.PCIE_CARD_LEN, D.PCIE_CARD_LEN_HALF)
        self.assertAlmostEqual(D.PCIE_CARD_LEN_HALF, 167.65, places=2)
        self.assertEqual(D.PCIE_COUNT, 4)
        self.assertAlmostEqual(
            D.rear_outer_protrusion(),
            D.PCIE_RIB_D + D.PCIE_BAR_T,
            places=6,
        )
        self.assertAlmostEqual(
            D.install_depth_mm(),
            D.CASE_D + D.rear_outer_protrusion(),
            places=6,
        )

    def test_PCIe窗框整圈補強(self):
        fx0, fx1 = D.pcie_frame_x()
        fz0, fz1 = D.pcie_frame_z()
        centers = D.pcie_centers()
        self.assertLessEqual(fx0, min(centers) - D.PCIE_OPEN_W / 2)
        self.assertGreaterEqual(fx1, max(centers) + D.PCIE_OPEN_W / 2)
        self.assertGreaterEqual(fx0, D.IO_X1)
        self.assertLessEqual(fx1, D.CASE_RIGHT)
        self.assertLessEqual(fz0, D.PCIE_Z0)
        self.assertAlmostEqual(fz1, D.PCIE_TIE_Z1, places=6)
        self.assertGreaterEqual(D.WALL + D.PCIE_RIB_D - D.PCIE_TANG_POCKET, 3.0)
        self.assertGreaterEqual((D.PCIE_TIE_H - D.MB_THREAD_MAJOR) / 2, 0.8)

    def test_每一道保留接合都留了滑配(self):
        self.assertGreater(D.SLIDE_FIT, 0.0)
        self.assertAlmostEqual(
            D.WALL - (D.TOP_LIP + D.SLIDE_FIT),
            D.GROOVE_BACK_MIN,
            places=6,
        )
        self.assertGreaterEqual(D.TOP_LIP, 1.0)
        self.assertAlmostEqual(D.RACK_TOP_GAP, D.SLIDE_FIT, places=6)
        self.assertAlmostEqual(D.RACK_BASE_Z1, D.HDD_Z0 - D.SLIDE_FIT, places=6)
        side_left = D.WALL - D.SHROUD_LAP_T - D.SLIDE_FIT
        self.assertGreaterEqual(side_left, 0.8)

    def test_Rack底部格柵有連續載荷路徑(self):
        self.assertEqual(len(D.RACK_BASE_BEAM_Y), 3)
        self.assertEqual(D.RACK_BASE_BEAM_W, 12.0)
        self.assertEqual(D.RACK_BASE_SPINE_W, 12.0)
        self.assertGreater(D.RACK_BASE_Z1, D.RACK_Z0)
        self.assertGreaterEqual(D.RACK_BASE_Z1 - D.RACK_Z0, 0.8)
        self.assertAlmostEqual(
            D.RACK_BASE_SPINE_X,
            (D.RACK_X0 + D.RACK_POST_X1) / 2,
            places=6,
        )
        for y in D.RACK_BASE_BEAM_Y:
            self.assertGreaterEqual(y - D.RACK_BASE_BEAM_W / 2, D.TRAY_Y0)
            self.assertLessEqual(y + D.RACK_BASE_BEAM_W / 2, D.HDD_Y1)

    def test_Top與Front保留可拆detent與導入(self):
        self.assertEqual(len(D.TOP_DETENT_X), 2)
        self.assertGreaterEqual(D.TOP_DETENT_R, 0.5)
        self.assertGreater(D.TOP_DETENT_DEPTH, D.SLIDE_FIT)
        self.assertLess(D.TOP_DETENT_DEPTH, D.TOP_DETENT_R)
        self.assertEqual(D.SHROUD_LAP, 14.0)
        self.assertEqual(D.SHROUD_LEAD_IN, 1.0)
        self.assertEqual(2 * len(D.SHROUD_DETENT_Z) + 2 * len(D.SHROUD_LAP_DETENT_X), 10)

    def test_碟架推到底要有止擋(self):
        """★ 第十一輪：第十輪槽的後端開到 TRAY_Y0 − 1.0，碟架往 −Y 浮 3.00 mm。"""
        rear_tab_y = min(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2
        self.assertAlmostEqual(D.RACK_STOP_Y, rear_tab_y - D.SLIDE_FIT, places=9)
        self.assertGreater(D.RACK_STOP_Y, D.TRAY_Y0 - 1.0, "盲端沒有往前收，還是會浮")
        # 盲端不能收過頭把側舌擋在外面
        self.assertLess(D.RACK_STOP_Y, max(D.RACK_BEAM_Y) - D.RACK_BEAM_W / 2)

    def test_組裝順序是唯一來源(self):
        self.assertEqual(
            [key for key, _ in D.ASSEMBLY_STEPS],
            ["Chassis_Body", "HDD_Rack", "Top_MB", "Front_Shroud", "HDD_Tray"],
        )
        self.assertEqual(D.ASSEMBLY_STEPS[0], ("Chassis_Body", 0.0))
        for key, distance in D.ASSEMBLY_STEPS[1:]:
            self.assertLess(distance, 0.0, msg=key)
        self.assertEqual(set(dict(D.ASSEMBLY_STEPS)), {"Chassis_Body", *D.STRUCT_PART_KEYS})

    def test_電源落入要讓開後牆頂鉤唇(self):
        # 第八輪：後牆的頂蓋承托肩刪了（頂蓋改滑入），X 向不必再讓位；
        # 改成必須讓開**後牆頂鉤唇**——電源後面板要貼後牆就得先閃過它。
        self.assertEqual(D.PSU_SLIDE_X, 0.0)
        self.assertGreater(D.PSU_SLIDE_Y, D.TOP_HOOK_D)
        self.assertGreaterEqual(D.psu_slide_room(), D.PSU_SLIDE_X)


    def test_列印件清單與份數同源而結構鍵只列可拆件(self):
        self.assertEqual(set(D.PART_QTY), set(D.STL_NAMES))
        self.assertEqual(set(D.STRUCT_PART_KEYS), {"Top_MB", "Front_Shroud", "HDD_Rack", "HDD_Tray"})
        self.assertIn("PCIeBar", D.STL_NAMES)
        self.assertIn("MB_Screw", D.STL_NAMES)
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

    def test_外殼本體一體式且PCIe壓條是唯一塑膠對塑膠五金(self):
        for gone in (
            "M3_INSERT_D", "M3_TAP", "M3_CLR", "M3_INSERT_BORE",
            "M3_BOSS_W", "M3_BOSS_L", "CAGE_LAP_W", "TOP_SCREW_BOSS_H",
        ):
            self.assertFalse(hasattr(D, gone), msg=gone)
        self.assertAlmostEqual(D.ATX_SCREW_CLR, 3.7, places=2)
        self.assertAlmostEqual(D.HDD_SCREW_CLR, 3.6, places=2)
        self.assertEqual(len(D.pcie_lock_x()), 2)

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
        self.assertEqual(set(D.PART_QTY), set(D.STL_NAMES))
        self.assertEqual(D.PART_QTY["Chassis_Body"], 1)
        self.assertEqual(D.PART_QTY["HDD_Tray"], D.TRAY_COUNT)
        self.assertEqual(D.PART_QTY["PCIeBlank"], D.PCIE_COUNT)
        self.assertEqual(
            D.PART_QTY["MB_Screw"], D.MB_SCREW_COUNT + D.PCIE_BAR_SCREW_COUNT
        )
        self.assertEqual(D.MB_SCREW_COUNT, len(D.HOLES_MM))
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


class Test第十三輪(unittest.TestCase):
    """使用者實印第十二輪後回報的五項；每一項都要有一條機器可驗的斷言。"""

    def test_IO開孔的深度基準出自Fig4側視圖(self):
        """
        主訴 2：主機板／擋板裝不上。病灶不在 Z（那一直是對的），在 **Y**。
        Fig.4 有兩張圖，前十二輪只用了正視圖；側視圖才定義深度方向的基準。
        """
        # 側視圖的兩個 literal
        self.assertAlmostEqual(D.IO_APERTURE_FROM_B, 12.27, places=2)
        self.assertAlmostEqual(D.IO_FROM_STANDOFF_TOP, 2.24, places=2)
        # Fig.5 note：Datum B → I/O 連接器的面
        self.assertAlmostEqual(D.IO_CONN_FACE_FROM_B, 11.30, places=2)
        # 後牆內面 = I/O aperture 平面（不再是「板緣減 MARGIN 減 WALL」）
        self.assertAlmostEqual(D.CASE_REAR + D.WALL, -D.IO_APERTURE_FROM_B, places=6)
        self.assertAlmostEqual(D.CASE_REAR, -(D.IO_APERTURE_FROM_B + D.WALL), places=6)
        # 連接器面必須落在牆的**內側**（舊值 −10.66 讓它戳進牆 0.64）
        self.assertLess(
            D.CASE_REAR + D.WALL, -D.IO_CONN_FACE_FROM_B,
            "I/O 連接器的面戳進後牆料裡 —— 主板推不到底",
        )
        self.assertAlmostEqual(
            (-D.IO_CONN_FACE_FROM_B) - (D.CASE_REAR + D.WALL), 0.97, places=2
        )
        # 連接器面比 PCB 後緣還往後突出（這正是舊 MARGIN=0.5 不夠的原因）
        self.assertLess(-D.IO_CONN_FACE_FROM_B, D.BOARD_REAR)
        # Z 的兩個獨立基準必須同時成立（板面 −3.81 與 standoff 頂 −2.24）
        self.assertAlmostEqual(D.IO_Z0, D.BOARD_TOP_Z - 3.81, places=6)
        self.assertAlmostEqual(
            D.IO_Z0, D.SHOULDER_TOP_Z - D.IO_FROM_STANDOFF_TOP, places=6
        )

    def test_碟架承托肩取代0_9mm咬合承重(self):
        """主訴 1：側板對應的溝槽太淺，往內伸一塊擋板把碟架托住。"""
        # 舊承重面積：4 個支點 × 樑寬 × 咬合量
        old_area = 4 * D.RACK_BEAM_W * (D.RACK_RAIL_T - D.SLIDE_FIT)
        new_area = 2 * len(D.RACK_BEAM_Y) * D.RACK_BEAM_W * D.RACK_LEDGE_D
        self.assertGreaterEqual(new_area, 10 * old_area)
        # 肩頂比橫樑底低一個滑配：滑入時不磨，載重落 0.30 就坐實（硬規則 19）
        self.assertAlmostEqual(D.RACK_LEDGE_Z1, D.RACK_RAIL_Z0 - D.SLIDE_FIT, places=6)
        # 斜撐要真的是 45°（自埋入牆內的根部量起）
        self.assertAlmostEqual(
            D.RACK_LEDGE_GUSSET, D.RACK_LEDGE_D + D.CHASSIS_OVERLAP, places=6
        )
        # 整條肩遠高於三個規格淨空頂，機殼的料一點都沒有伸進主板的地盤
        ledge_bottom = D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET
        for top in (D.AREA_A_TOP_Z, D.AREA_B_TOP_Z, D.AREA_C_TOP_Z):
            self.assertGreater(ledge_bottom, top)
        # Chassis 段讓開電源與 PCIe 卡的 y 帶
        self.assertGreater(D.RACK_LEDGE_Y0, D.ATX_Y1)
        self.assertGreaterEqual(D.RACK_LEDGE_Y0, D.RACK_STOP_Y)
        # Chassis 段與前罩段接力，中間留滑配、不重疊
        self.assertAlmostEqual(D.RACK_LEDGE_Y1, D.SHROUD_Y0 - D.SHROUD_LAP, places=6)
        self.assertGreaterEqual(D.SHROUD_LEDGE_Y0, D.SHROUD_Y0)
        self.assertAlmostEqual(D.SHROUD_LEDGE_D, D.RACK_LEDGE_D, places=6)
        # 前罩是「無支撐」preset：貼床端的楔形引入必須是 45°
        self.assertAlmostEqual(D.SHROUD_LEDGE_LEAD, D.RACK_LEDGE_T, places=6)
        # 前段懸臂大幅縮短
        self.assertLess(D.HDD_Y1 - max(D.RACK_BEAM_Y), 0.5 * (D.HDD_Y1 - D.BAY_SPLIT_Y))

    def test_PCIe開孔頂改45度尖頂而且不吃抬升(self):
        """主訴 3：拆支撐會把中間三根細桿一起扯斷。根因是那四個開孔需要支撐。"""
        # 全寬區的頂 = 擋板抬到頂的位置，抬升一點都沒有少
        self.assertAlmostEqual(D.PCIE_OPEN_Z1, D.PCIE_Z1 + D.PCIE_LIFT, places=6)
        self.assertGreaterEqual(D.PCIE_LIFT, D.PCIE_ENGAGE)
        # 45° ⇒ 尖頂高 = 半寬（切片器判定不需支撐）
        self.assertAlmostEqual(D.PCIE_APEX_H, D.PCIE_OPEN_W / 2, places=6)
        self.assertAlmostEqual(D.PCIE_APEX_Z, D.PCIE_OPEN_Z1 + D.PCIE_APEX_H, places=6)
        # 繫樑移到尖頂之上，但機殼高度不變
        self.assertAlmostEqual(D.PCIE_TIE_Z0, D.PCIE_APEX_Z, places=6)
        self.assertAlmostEqual(D.PCIE_TIE_Z1, D.PCIE_TIE_Z0 + D.PCIE_TIE_H, places=6)
        self.assertLess(D.PCIE_TIE_Z1, D.INNER_TOP_Z)
        self.assertAlmostEqual(D.OUTER_TOP_Z, 180.12, places=2)
        # 窗框補強一路長到繫樑頂（盲牙不能鑽在只有 WALL 厚的牆上）
        self.assertAlmostEqual(D.pcie_frame_z()[1], D.PCIE_TIE_Z1, places=6)

    def test_後牆補頂蓋卡槽且讓開電源與碟架(self):
        """主訴 4：後牆好像沒有專門插頂蓋的卡槽。"""
        self.assertAlmostEqual(D.TOP_REAR_LIP, D.TOP_LIP, places=6)
        # 槽深與側槽同一個牆厚上限，槽背仍留可印料
        self.assertAlmostEqual(
            D.WALL - (D.TOP_REAR_LIP + D.SLIDE_FIT), D.GROOVE_BACK_MIN, places=6
        )
        bands = D.top_rear_tab_bands()
        self.assertEqual(len(bands), 2)
        for bx0, bx1 in bands:
            self.assertGreater(bx1, bx0)
        # 舌是**整條路徑掃過去**的：兩段都必須完全避開電源與碟架的 x 帶
        for bx0, bx1 in bands:
            self.assertFalse(bx0 < D.ATX_X1 and bx1 > D.ATX_X0, "後舌掃過電源")
            self.assertFalse(
                bx0 < D.RACK_POST_X1 and bx1 > D.RACK_X0, "後舌掃過碟架頂板"
            )
        # 鉤唇沒有被順手刪掉（它擋的是外側 +Z，與槽不是同一件事）
        self.assertGreater(D.TOP_HOOK_D, 0.0)
        self.assertGreater(D.TOP_HOOK_T, 0.0)

    def test_前罩搭接帶改U形雙壁夾持(self):
        """主訴 5：改成有縫隙可以插進去、兩邊夾住，不要單邊凸點卡槽。"""
        self.assertGreaterEqual(D.SHROUD_INNER_T, 0.8)  # FDM 最小可印壁厚
        # 內壁下限讓開 Area B 淨空（右牆內面到主板右緣只有 0.50）
        self.assertAlmostEqual(D.SHROUD_INNER_Z0, D.AREA_B_TOP_Z + D.SLIDE_FIT, places=6)
        self.assertGreater(D.SHROUD_INNER_Z0, D.AREA_B_TOP_Z)
        # 內壁上限讓開碟架承托肩的 45° 斜撐底
        self.assertAlmostEqual(
            D.SHROUD_INNER_Z1,
            D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET - D.SLIDE_FIT,
            places=6,
        )
        self.assertLess(D.SHROUD_INNER_Z1, D.RACK_LEDGE_Z0 - D.RACK_LEDGE_GUSSET)
        self.assertGreater(D.SHROUD_INNER_Z1 - D.SHROUD_INNER_Z0, 100.0)
        # 接合塊：內壁貼的是 Chassis 牆內面，主體壁內面比它外 1.10 —— 不接就飄
        self.assertGreater(D.SHROUD_INNER_JOIN, 0.0)
        gap = (D.CASE_LEFT + D.SHROUD_WALL) - (D.CASE_LEFT + D.WALL + D.SLIDE_FIT)
        self.assertLess(gap, 0.0, "主體壁內面應該比內壁外側更外")
        # 外壁仍在（U 形要兩片，不是把單邊搬到另一邊）
        self.assertGreaterEqual(D.SHROUD_LAP_T, 0.8)
        self.assertEqual(len(D.SHROUD_DETENT_Z), 3)


class Test第十四輪(unittest.TestCase):
    """主訴：PCIe 細肋仍被支撐扯斷／螺絲要十字孔／支撐難拆與表面粗糙。"""

    def _support_preset(self):
        import json
        path = os.path.join(ROOT, "列印設定", "3DP-MATX 機殼件 0.16 支撐.json")
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_螺絲頭十字工具槽尺寸鏈(self):
        """主訴 2：螺絲上面要有十字的孔，讓螺絲起子可以轉。"""
        self.assertGreaterEqual(D.MB_SCREW_CROSS_W, 0.5)  # 最小可印特徵
        self.assertLess(D.MB_SCREW_CROSS_L, D.MB_SCREW_HEAD_AF)
        self.assertLess(D.MB_SCREW_CROSS_DEPTH, D.MB_SCREW_HEAD_H, "槽不得吃到牙")
        self.assertAlmostEqual(
            D.MB_SCREW_CROSS_WALL, (D.MB_SCREW_HEAD_AF - D.MB_SCREW_CROSS_L) / 2, places=6
        )
        self.assertAlmostEqual(
            D.MB_SCREW_CROSS_ROOF, D.MB_SCREW_HEAD_H - D.MB_SCREW_CROSS_DEPTH, places=6
        )
        self.assertGreaterEqual(D.MB_SCREW_CROSS_WALL, 0.8)
        self.assertGreaterEqual(D.MB_SCREW_CROSS_ROOF, 0.8)
        # 頭仍在 keepout 內（加了槽也不能把頭放大）
        self.assertLess(D.MB_SCREW_HEAD_D, D.MB_KEEPOUT_D)

    def test_支撐門檻是preset與幾何的同一個數字(self):
        """45° 尖頂／斜撐／引入楔只有在這個門檻下才成立（硬規則 9）。"""
        preset = self._support_preset()
        self.assertEqual(
            preset["support_threshold_angle"], f"{D.SUPPORT_THRESHOLD_ANGLE:g}"
        )
        # 45° 幾何必須真的高於門檻，否則尖頂照樣生支撐
        self.assertLess(D.SUPPORT_THRESHOLD_ANGLE, 45.0)

    def test_脫模間隙不得小於Bambu原廠值(self):
        """主訴 3：支撐難拆／表面粗糙。第十三輪的 0.2 比原廠 0.35 還小。"""
        preset = self._support_preset()
        self.assertGreaterEqual(float(preset["support_object_xy_distance"]), 0.35)
        layer = float(preset["layer_height"])
        for key in ("support_top_z_distance", "support_bottom_z_distance"):
            self.assertGreaterEqual(
                float(preset[key]), 2 * layer, f"{key} 至少兩層，PETG 一層會焊住"
            )
        # 接觸面要有一層才有連續下表面；底接觸面留 0（那一面焊在件上）
        self.assertGreaterEqual(int(preset["support_interface_top_layers"]), 1)
        self.assertEqual(int(preset["support_interface_bottom_layers"]), 0)

    def test_支撐外脹量受A1床餘量限制(self):
        """脫模間隙不是想開多大就多大 —— 支撐是印出來的料，也要佔床。

        Chassis 裸深已經 252.85，床 256。第十四輪一度把 xy 開到 0.45，
        佔床立刻 254.42 × 254.59、餘量 0.71 < 0.75 硬門檻。這條把
        「PETG 要大間隙」與「A1 只剩 0.8 mm/邊」的衝突寫成斷言，
        下一輪要動任一邊都會先撞到它。
        """
        import importlib
        placement = importlib.import_module("列印擺位")
        preset = self._support_preset()
        xy = float(preset["support_object_xy_distance"])
        grow = 2 * (xy + placement.SUPPORT_LINE_W)
        depth = D.BAY_SPLIT_Y - (D.CASE_REAR - D.PCIE_RIB_D)
        self.assertAlmostEqual(depth, 252.85, places=2)
        for span in (D.CASE_W, depth):
            self.assertGreaterEqual(
                (placement.BED - (span + grow)) / 2, 0.75,
                f"加支撐後 A1 餘量 < 0.75 mm/邊（xy={xy}）",
            )

    def test_PCIe窗框45度引入楔(self):
        """主訴 1：窗框底緣本來是 89×4 的水平懸空，就在三根肋的正下方。"""
        self.assertAlmostEqual(D.PCIE_FRAME_LEAD, D.PCIE_RIB_D, places=6)  # 45°
        # 楔只往下長，不多凸一分 Y（A1 餘量只有 0.81 mm/邊）
        self.assertGreater(D.pcie_frame_z()[0] - D.PCIE_FRAME_LEAD, 0.0)

    def test_後牆鉤唇減深但仍咬得住(self):
        """鉤唇底面是全寬水平懸空，支撐塔會擦過三根肋；6.0 從來沒有理由。"""
        self.assertLessEqual(D.TOP_HOOK_D, 3.0)
        self.assertGreater(D.TOP_HOOK_D, D.TOP_LIP, "咬合量不得低於側舌")
        self.assertGreater(D.PSU_SLIDE_Y, D.TOP_HOOK_D)
        # 底面做不出 45°：往下一個 GUSSET 就撞到頂蓋本體
        self.assertLess(D.INNER_TOP_Z, D.OUTER_TOP_Z - D.TOP_HOOK_T)


class Test註解真實性(unittest.TestCase):
    """`# 99.22` 這種行尾註解會跟著上游一起爛掉，而且沒有任何東西在看它。

    第十四輪一次抓到 8 條（`CASE_D # 301.00`、`ATX_Y0 # −10.66`、
    `PCIE_CARD_LEN # 189.00` …），全部是第十／十三輪改上游時漏掉的。
    註解寫錯不會讓幾何錯，但它會讓下一輪讀到假的數字（硬規則 15 的變體）。
    """

    # `NAME = expr  # 12.34`；引號結尾的是規格 literal（`0.800" TYP`），不是本地值
    COMMENT_VALUE = re.compile(r"""^([A-Z][A-Z0-9_]*) = .*#\s*(−?-?\d+\.\d+)(?![\d"″”'])""")

    def test_行尾數值註解必須等於實際值(self):
        bad = []
        path = os.path.join(SCRIPTS, "參數.py")
        for lineno, line in enumerate(io.open(path, encoding="utf-8"), 1):
            m = self.COMMENT_VALUE.match(line.rstrip())
            if not m:
                continue
            name, text = m.group(1), m.group(2).replace("−", "-")
            actual = getattr(D, name, None)
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                continue
            if abs(float(text) - float(actual)) > 0.006:
                bad.append(f"參數.py:{lineno} {name} 註解={text} 實際={actual:.3f}")
        self.assertEqual(bad, [], "行尾註解與實際值不符：" + " / ".join(bad))

    def test_這條檢查抓得到被改壞的註解(self):
        """非空證明（硬規則 16）：拿一行真的註解改壞，pattern 必須看得出來。"""
        m = self.COMMENT_VALUE.match("CASE_D = CASE_FRONT - CASE_REAR  # 301.00")
        self.assertIsNotNone(m)
        self.assertNotAlmostEqual(float(m.group(2)), D.CASE_D, places=2)
        # 規格 literal（吋）不算本地值，不得誤報
        self.assertIsNone(
            self.COMMENT_VALUE.match('PCIE_PITCH = 20.32  # 0.800" TYP between connectors')
        )


if __name__ == "__main__":
    unittest.main()
