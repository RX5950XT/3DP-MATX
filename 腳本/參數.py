# 3DP-MATX 共用尺寸（mm）
# 佈局（第七輪）：主板平躺在底板上；**電源在 I/O 擋板正上方**（同一個腔，中間沒有隔板）；
#                前方碟艙三面環繞、後面直通內腔；外殼是單一長方體（無階梯、無外凸腳）
# 座標：Datum B = (0,0)；+Y→前（硬碟）；+Z→上；底板頂面 z = FLOOR_T
#
# X 鏡像（相對 Intel 印刷圖）：
#   Intel 圖：後緣在上、擴充槽在「圖左」、I/O 在 B 右側
#   機殼平放、從後方外側看（gaze=+Y）：真板 PCIe 在右、I/O 在左
#   因此 case_X = −intel_X（孔距不變，僅左右翻轉以可裝真板）

from __future__ import annotations

import os

# --- microATX 九孔（Intel 座標 X 取負後寫入 case）---
# ★ 第七輪全部改對。舊值有七顆是錯的，來源是把 Fig.3 的 `.900 [22.86]` 讀成
#   「板後緣 → B 列」，於是把 Fig.7 的 154.94 / 227.33 各減 22.86 當成 B 相對值。
#   實際上（microATX 1.2 **Fig.7 p18** 的向量座標，九個孔圓與板框同一比例尺 1.0044 pdf/mm，
#   且與 Fig.3 p12 的標註 6.100[154.94] / 8.950[227.33] / .900[22.86] / .400[10.16] 完全對上）：
#     板框：intel x∈[−34.29, 209.55]、y∈[−10.16, 233.68]（B 離後緣 0.400"）
#     B(0,0)  C(45.72,0)  **F(203.20, 22.86)**  ← F 不在 B 那一列
#     R(−20.32,154.94) S(0,154.94) H(45.72,154.94) J(203.20,154.94)
#     L(45.72,227.33)  M(203.20,227.33)
#   舊值的後果不是「差一點」：主板前緣其實在 y=233.68，舊值 220.98 → 真板會撞碟艙 12.7 mm。
HOLES_MM = {
    "B": (0.00, 0.00),
    "C": (-45.72, 0.00),
    "F": (-203.20, 22.86),
    "R": (20.32, 154.94),
    "S": (0.00, 154.94),
    "H": (-45.72, 154.94),
    "J": (-203.20, 154.94),
    "L": (-45.72, 227.33),
    "M": (-203.20, 227.33),
}
HOLE_LETTERS = ("B", "C", "F", "H", "J", "L", "M", "R", "S")
PCB_HOLE_D = 3.96

# 板緣（Fig.7 p18 板框）：Intel 左緣 −34.29 → case +34.29；Intel 右緣 +209.55 → case −209.55
BOARD_LEFT = -209.55
BOARD_RIGHT = 34.29
BOARD_REAR = -10.16  # B 離後緣 0.400"（Fig.7 `.400 [10.16] REF (BOARD MTG HOLE)`）
BOARD_FRONT = BOARD_REAR + 243.84  # 233.68；9.600 in 見 Table 3 p9
BOARD_W = BOARD_RIGHT - BOARD_LEFT
BOARD_D = BOARD_FRONT - BOARD_REAR
PCB_T = 1.57

# --- 板上元件高度分區（microATX 1.2 §2.4.1 Table 6 + Figure 7，p17–18）---
# 「microATX-compliant power supplies, peripherals, and chassis features should not
#   extend into the motherboard component area.」——這一段就是本專案能不能把電源
#   放到主板正上方的**唯一依據**，所以三區的界線與淨空全部逐條抄下來。
#   界線值是 Fig.7 的向量座標（case_x = −intel_x，case_y = intel_y，原點 Datum B）。
# ★ 第八輪把 Area A 壓到 50.00（使用者實測散熱器 <50），那是**主動離開規範**。
# ★ 第十輪**改回規範內**，而且**機殼高度一點都沒有變**：
#   使用者說「電源上面還有空間」——量出來電源頂 149.32、內頂 176.82，
#   死空間 27.50 mm。電源整組往上頂到內頂之後，讓出來的高度全部變成板上淨空：
#   50.00 → 76.20 = Table 6 **required**。刻意偏離 ① 就此消失。
#   （recommended 88.90 仍未達到；那要再 +12.70 mm 機殼高度，沒有換。）
#   COOLER_MAX_H 保留成**下限**：Area A 取兩者的 max，實測值若哪天大於規格值也不會被吃掉。
COOLER_MAX_H = 50.0  # 使用者實測上限（板面起算）；現在只是下限，不再是決定值
DIMM_MAX_H = 40.0  # 使用者實測上限（板面起算）；< COOLER_MAX_H 故不另成約束
AREA_A_SPEC_REQUIRED = 76.20  # Table 6 required（第十輪起**已滿足**）
AREA_A_SPEC_RECOMMENDED = 88.90  # Table 6 recommended（仍未達到，見 CONTEXT.md）
AREA_A_CLEARANCE = max(COOLER_MAX_H, AREA_A_SPEC_REQUIRED)  # 76.20
AREA_B_CLEARANCE = 15.24  # Table 6：0.60 in（擴充槽區）
AREA_C_CLEARANCE = 38.10  # Table 6：1.50 in
AREA_B_X0 = -52.07  # intel 2.050 in → Area B（擴充槽帶）自此往 +X 到板右緣
AREA_A_STEP_X = -95.25  # intel 3.750 in：A/C 界線在此換階
AREA_A_Y_NEAR = 154.94  # intel 6.100 in：x ≤ AREA_A_STEP_X 段的 A/C 界線
AREA_A_Y_FAR = 180.34  # intel 7.100 in：x ∈ [STEP, B_X0] 段的 A/C 界線

# --- 主板柱（階梯圓柱：Ø8 粗肩 → Ø3.50 細軸穿板 → 梯形外螺紋 + 印製螺帽）---
# 第六輪定案，第七輪只改「柱長在底板上」而不是「長在甲板上」。三關見 CLAUDE.md 硬規則 6。
SHOULDER_OD = 8.0
SHOULDER_H = 6.35  # microATX 1.2 §2.4.2：機殼須讓板底 ≥0.250"(6.35)
MB_STUD_MAJOR = 3.50  # 牙頂徑；主板孔 Ø3.96 → 單邊 0.23 滑配（PETG 建議 0.2–0.3）
MB_STUD_DEPTH = 0.60  # 徑向牙深。牙深要扣掉螺帽間隙才是**真旋合量**：0.60 − 0.20 = 0.40
MB_STUD_MINOR = MB_STUD_MAJOR - 2 * MB_STUD_DEPTH  # 2.30 芯徑
MB_STUD_PITCH = 2.00  # 粗牙距。1.5 的話螺帽內牙牙頂只剩 0.175，印不出來
MB_STUD_ROOT_W = 0.50  # 牙底寬（× pitch）
MB_STUD_CREST_W = 0.25  # 牙頂寬（× pitch）
MB_NUT_H = 5.0  # 旋合 2.5 圈
MB_NUT_OD = 9.6  # < MB_KEEPOUT_D
MB_NUT_GAP = 0.20  # 螺帽內牙相對外牙的單邊間隙（滑配）
MB_THREAD_ENGAGE = MB_STUD_DEPTH - MB_NUT_GAP  # 0.40 真旋合徑向量
MB_NUT_FLUTES = 12  # 外周指握溝槽數（手緊，不上工具）
MB_NUT_FLUTE_R = 1.0
MB_NUT_COUNT = 9  # 九孔各一顆；總成裡只放 B 孔那顆（見 build_case）
MB_KEEPOUT_D = 10.16  # microATX 0.400" 九孔 keepout 直徑（規格只保證板底側）

# --- 壁厚／地板／下裙 ---
WALL = 2.4
TOP_T = 3.0
FLOOR_T = 2.4
# 滑槽單邊間隙（PETG 滑配）。★ 第九輪往上搬：PCIe 壓條的 keyhole 與前罩搭接都要用它，
#   而它們的定義比舊位置早。**零間隙不是精密，是裝不上**——第八輪前罩搭接帶
#   nominal 0，布林 common=0.000 被讀成「不干涉」，其實是「套不進去」。
SLIDE_FIT = 0.30
# ★ 第十輪：所有滑槽的幾何常數集中到這裡（原本散在檔案下半，而 ATX_X0 要用到它們）。
#   起因是量出來的：`distToShape(底板, 側板) = 0.0000`、後牆、頂蓋全部一樣——
#   **每一個配合面都是 nominal 零間隙**。第九輪只修了前罩搭接與層節距兩處，
#   同一個病其實長在整條互鎖鏈上。零間隙不是精密，是裝不上（硬規則 19）。
#
#   一道滑槽的四個數字（牆厚 2.4 全部要塞進去）：
#     舌伸出量 LIP → 槽深 = LIP + SLIDE_FIT → 槽背後剩料 = WALL − 槽深 ≥ 0.8（可印）
#     ⇒ LIP ≤ WALL − 0.8 − SLIDE_FIT = 1.30
GROOVE_BACK_MIN = 0.8  # 槽挖完之後牆上必須剩下的料（FDM 最小可印壁厚）
FLOOR_LIP = WALL - GROOVE_BACK_MIN - SLIDE_FIT  # 1.30 底板側／後舌伸出量＝槽深−滑配
FLOOR_LIP_T = 1.0  # 舌厚（Z）。★ 第十輪 1.2→1.0，讓出來的 0.2 加到下方承載唇
FLOOR_LEDGE_T = FLOOR_T - FLOOR_LIP_T - SLIDE_FIT  # 1.10 槽下方的整厚牆料（承載唇）
TOP_LIP = FLOOR_LIP  # 1.30 頂蓋側舌伸出量（同一條規則導出）
TOP_FIT_GAP = 0.4  # 頂蓋本體四周單邊間隙
TOP_FUSE = 1.0  # 舌與本體的體積重疊（只有面接觸 fuse() 不會併成單一 Solid，硬規則 1）
# ★ 第八輪：**下裙整個刪掉**（SKIRT_H = 0，參數保留給 negtest 對照）。
#   下裙唯一的存在理由是「機殼內部沒有地方放 M3 銅母座」——這一輪改成
#   全滑槽組裝、**一顆螺絲都不用**（使用者要求），座沒了，裙也就沒有理由了。
#   直接省 10 mm 高度。機殼底面就是底板下表面，整片落地。
SKIRT_H = 0.0

# 主板柱：粗肩直接長在底板頂面上
SHOULDER_TOP_Z = FLOOR_T + SHOULDER_H  # 8.75
BOARD_TOP_Z = SHOULDER_TOP_Z + PCB_T  # 10.32
# 細軸露出粗肩頂的長度＝板厚 + 螺帽 + 導入／收尾餘量（由三者導出，不另寫死）
MB_STUD_LEN = PCB_T + MB_NUT_H + 1.0
MB_STUD_TOP_Z = SHOULDER_TOP_Z + MB_STUD_LEN
MB_NUT_Z0 = BOARD_TOP_Z  # 螺帽底面壓在板面上

# 三個分區的「機殼淨空頂面」——機殼在該區的料只能在這個 z 以上
AREA_A_TOP_Z = BOARD_TOP_Z + AREA_A_CLEARANCE  # 99.22
AREA_B_TOP_Z = BOARD_TOP_Z + AREA_B_CLEARANCE  # 25.56
AREA_C_TOP_Z = BOARD_TOP_Z + AREA_C_CLEARANCE  # 48.42

# --- ATX PSU（PS/2）：第七輪移到 I/O 擋板正上方 ---
# 外形 150×86×140（深可更長，艙深預留 160）
ATX_W = 150.0
ATX_H = 86.0
ATX_D = 140.0  # 標稱深度（出線前緣基準，ATX12V Fig.4 WIRE HARNESS）
ATX_D_ALLOW = 160.0  # 艙深預留（長機身；模組前突另計）
# 後牆安裝面四孔（#6-32）— ATX12V Design Guide v1.1 **p23 Figure 4** 的 literal。
#   原點＝後面板左下角，**從機殼後方外側看**（+X 右、+Z 上）。
#   圖上量到的四條標註：6.0 (2X)（左右緣→孔列）、138.0（上排兩孔）、
#   16.0 + 64.0（左下孔→左上孔）、6.0 + 74.0（右下孔→右上孔）、114.0（左孔列→右下孔）
#   ⇒ (6,80) (144,80) (6,16) (120,6)。**非對稱**：右下孔被 AC 插座讓開，144 → 120。
ATX_HOLES_SPEC = ((6.0, 80.0), (144.0, 80.0), (6.0, 16.0), (120.0, 6.0))
# ★ 第十輪：**風扇朝向是一個假設，不是規格**（使用者主訴 1b）。
#   ATX12V v1.1 的 Fig.4 裡，風扇是**開在後面板上的 80 mm 風扇**，進氣在前面板
#   （"Air inlet grill, 55% open area"），側面是 "Optional air inlet area"——
#   **大面 120/140 風扇在哪一面，這份規格根本沒有寫**，參考/ 也沒有別的文件寫。
#   所以這裡不假裝它是導出的：使用者說目前的擺法風扇會朝上，要它朝下（朝主機板），
#   於是把 Fig.4 的四孔繞**深度軸**轉 180°（(x,z) → (W−x, H−z)）。
#   這是剛體變換，不是重新編一組座標；verify 驗「轉回去等於 Fig.4 literal」。
#   要改回來只要把 PSU_FAN_DOWN 設 False，其餘全部跟著走。
PSU_FAN_DOWN = True
ATX_HOLES = tuple(
    sorted((ATX_W - x, ATX_H - z) for x, z in ATX_HOLES_SPEC)
) if PSU_FAN_DOWN else tuple(sorted(ATX_HOLES_SPEC))
ATX_HOLE_PITCH_H = 138.0  # 同一列兩孔水平距（Fig.4 138.0；翻轉不變）
ATX_HOLE_PITCH_V = 74.0  # 同一行兩孔垂直距（Fig.4 74.0；翻轉不變）
ATX_SCREW_CLR = 3.7  # #6-32 通孔
PSU_WIN_M = 2.0  # 螺絲孔緣 → 開窗邊緣的最小板料
_atx_hx = [h[0] for h in ATX_HOLES]
_atx_hz = [h[1] for h in ATX_HOLES]
_atx_hr = ATX_SCREW_CLR / 2 + PSU_WIN_M
PSU_WIN_X0 = min(_atx_hx) + _atx_hr
PSU_WIN_X1 = max(_atx_hx) - _atx_hr
PSU_WIN_Z0 = min(_atx_hz) + _atx_hr
PSU_WIN_Z1 = max(_atx_hz) - _atx_hr
# 承托肩：電源坐在「後牆前伸的凸緣」＋「左側板內伸的長肩」上，四顆 #6-32 才是固定件。
# 肩的頂面必須 ≥ AREA_A_TOP_Z，否則機殼的料伸進了 Area A 淨空。
PSU_LEDGE_T = 3.0
PSU_LEDGE_W = 12.0
# ★ 第十輪：`PSU_CLEAR_ABOVE` 從「寫死的 4.0」改成**導出值**（見 INNER_TOP_Z 之後）。
#   舊註解寫它要吸收「頂蓋承托肩」——那條肩第八輪就刪了，參數卻沒跟著改，
#   於是 4.0 這個數字在第九輪已經沒有理由，只是把電源壓在下面而已（硬規則 15）。
#   電源頂上真正需要的只有「空氣 + 裝配餘裕」，因為它上面什麼都不用通過。
PSU_CLEAR_MIN = 1.0  # 電源頂 → 內頂的**下限**（裝配餘裕）
PSU_FIT_GAP = 0.8  # 導向特徵讓開標稱本體的單邊間隙（鋼盒不退讓）
ATX_Z0 = AREA_A_TOP_Z + PSU_LEDGE_T  # 89.52 電源底面
ATX_Z1 = ATX_Z0 + ATX_H  # 175.52

# I/O（microATX Figure 4：B→開孔近緣 2.096"=53.24；case 已 X 鏡像）
IO_W = 158.75
IO_H = 44.45
IO_BOTTOM_BELOW_BOARD_TOP = 3.81  # p13：開孔底在板面下 0.150 in
IO_CLIP_T = 1.15  # 可夾壁厚 0.94–1.32
IO_KEEPOUT = 2.54
IO_CORNER_R = 0.90  # ≤0.99
IO_GAP_FROM_B = 53.24  # Datum B → I/O 開孔近緣（Figure 4：2.096±0.010"）
IO_X1 = -IO_GAP_FROM_B  # 近 B 的開孔緣 = −53.24
IO_X0 = IO_X1 - IO_W  # −211.99
IO_Z0 = BOARD_TOP_Z - IO_BOTTOM_BELOW_BOARD_TOP  # 6.51
IO_Z1 = IO_Z0 + IO_H  # 50.96
IO_CHAMFER = 0.6  # 外側插入倒角（助 I/O shield 滑入）

# PCIe — 原廠全高金屬擋板。全部數字出自 參考/PCI_Express_CEM_r2.0.pdf
#   Fig.6-4（p95）擋板：全長 120.02、寬 18.42、料厚 0.86(20GA)、本體 112.75、底舌 7.27×14.30
#   Fig.6-2（p93）擋板自身 I/O 窗：12.06 × 89.90，窗頂在頂緣下 10.16
#   Fig.6-17（p110）DIM A：板面 → 標準高卡頂 114.55 MAX
PCIE_COUNT = 4
PCIE_PITCH = 20.32  # 0.800" TYP between connectors（microATX Figure 3）
PCIE_EDGE_TO_FIRST = 10.16  # 擴充側板緣 → 第一槽中心 .400"
PCIE_FIRST_CX = BOARD_RIGHT - PCIE_EDGE_TO_FIRST  # +24.13 mm @ Datum B

PCIE_BRACKET_W = 18.42  # Fig.6-4 擋板正面寬
PCIE_BRACKET_T = 0.86  # Fig.6-4 Note 1：0.86 mm (20 GA)
PCIE_BRACKET_TOTAL_H = 120.02  # Fig.6-4 全長（含底舌）
PCIE_BODY_H = 112.75  # Fig.6-4 本體：頂緣 → 底肩
PCIE_TANG_H = PCIE_BRACKET_TOTAL_H - PCIE_BODY_H  # 7.27 底舌長
PCIE_TANG_W = 14.30  # Fig.6-4 底舌寬
PCIE_WIN_W = 12.06  # Fig.6-2 擋板自身 I/O 窗寬
PCIE_WIN_H = 89.90  # Fig.6-2 擋板自身 I/O 窗高
PCIE_WIN_FROM_TOP = 10.16  # Fig.6-2 擋板頂緣 → 窗頂
PCIE_CARD_TOP_ABOVE_BOARD = 114.55  # Fig.6-17 DIM A（標準高卡）
PCIE_BRACKET_ABOVE_CARD = 4.56  # Fig.6-4 側視：擋板頂緣高出卡頂
PCIE_EAR_BAND = 2.92  # Fig.6-4 側視：頂緣往下的折耳帶（此帶內不得有機殼料）
PCIE_EAR_INWARD = 11.43  # Fig.6-4 俯視 11,43 [0.450]
PCIE_EAR_CLEAR = PCIE_EAR_INWARD + 1.0

# 垂直鏈：板面 →(114.55)→ 卡頂 →(4.56)→ 擋板頂緣 →(−112.75)→ 底肩 →(−7.27)→ 舌尖
PCIE_Z1 = BOARD_TOP_Z + PCIE_CARD_TOP_ABOVE_BOARD + PCIE_BRACKET_ABOVE_CARD  # 129.43
PCIE_Z0 = PCIE_Z1 - PCIE_BODY_H  # 16.68 開孔底＝承重肩面
PCIE_TANG_Z0 = PCIE_Z0 - PCIE_TANG_H  # 9.41 舌槽底
PCIE_CARD_TOP_Z = BOARD_TOP_Z + PCIE_CARD_TOP_ABOVE_BOARD

PCIE_OPEN_W = 18.9  # 後牆開孔寬（擋板本體 18.42 落得進；槽間肋 1.42）
PCIE_TANG_GAP = 0.5  # 舌槽單邊間隙
PCIE_TANG_POCKET = 1.3  # 舌槽自後牆內面往外挖的深度（>0.86 料厚，且不挖穿 2.4 牆）
# ★ 第九輪：繫樑 3.0 → 6.0。它在第八輪只活在 INNER_TOP_Z 的 max() 裡，
#   幾何上被「抬升帶連續橫縫」整條切掉了 —— 三根 1.42 的肋因此變成
#   自由長 112.75 mm 的懸臂（斷面 1.42×2.40，k≈0.006 N/mm，10 N 就位移一公尺）。
#   橫縫已刪（壓條改 keyhole 固定，不再需要沿 X 滑），繫樑恢復成真的料。
PCIE_TIE_H = 6.0  # 開孔上方的連續繫樑：肋的**上端固定端**
# ★ 第十輪：加厚的範圍從「只有肋」擴大到**整圈窗框**（使用者：PCIe 還是很多問題）。
#   第九輪把三根肋補到 1.42×6.40，但窗框的其他三邊還是 2.4：
#   底檻（舌袋挖掉 1.3 之後只剩 **1.1**）、左右柱、繫樑。一個 80×120 的洞開在
#   2.4 的板子上，補強只補了中間三根肋 —— 框本身才是那片牆最軟的地方。
#   往**機殼外**長不吃任何內部淨空（外面除了壓條什麼都沒有），
#   而且底檻加厚之後舌袋剩料 1.1 → 5.1，擋板的 Y 定位面終於不是一層皮。
PCIE_RIB_D = 4.0  # 窗框（含肋）往機殼外加厚（斷面 1.42×2.40 → 1.42×6.40，I ×19）
PCIE_FRAME_M = 8.0  # 窗框補強在四個開孔之外往左右各延伸的量
PCIE_HOLD_GAP = 0.4  # 裝好後擋板頂緣→防上抬面的間隙
# 卡要離開連接器必須整片抬「指入深度」：連接器頂 7.90（Fig.6-17）− 卡底 3.40 = 4.50
PCIE_CONN_H = 7.90
PCIE_CARD_H = 111.15  # p94：標準高卡固定高 111.15 ±0.13
PCIE_CARD_BOTTOM = PCIE_CARD_TOP_ABOVE_BOARD - PCIE_CARD_H  # 3.40 板面 → 金手指尖
PCIE_ENGAGE = PCIE_CONN_H - PCIE_CARD_BOTTOM  # 4.50 最小抬升量

# --- 卡體佔位包絡（虛擬件干涉檢查用）---
PCIE_CARD_HALF_W = 9.0
PCIE_CARD_Z0 = BOARD_TOP_Z + 16.15  # Fig.6-17：板面 → 卡體下緣
PCIE_CARD_Z1 = PCIE_CARD_TOP_Z
# 應支援卡長 PCIE_CARD_LEN 移到檔尾（要由 TRAY_Y0 與 CASE_REAR 導出，兩者定義在後面）。
PCIE_CARD_LEN_HALF = 167.65  # CEM r2.0 §6：half-length add-in card（literal，供對照）

# 空槽蓋
PCIE_BLANK_T = 1.6
PCIE_BLANK_EAR = 8.0

# --- PCIe 卡固定：可拆壓條 ---
# 耳下方只剩 4.56 − 4.50 = 0.06 mm，任何固定料都會擋死卡的裝拆 → 固定件必須可拆。
# ★ 第七輪：電源移到上方後，後牆在 x ≤ −63.09、z 102–188 全被電源佔住，
#   第六輪那兩顆凸座（x = −53.28 / −69.28）有一顆落在電源本體裡。
#   凸座改成 **1 顆**，放在「電源右緣 → 最左開孔」之間那條 16.8 mm 的空帶；
#   右端仍用舌片插右側板口袋（末槽耳緣 33.34 → 右內牆 34.79 只剩 1.45 mm）。
# ★ 第八輪：壓條**移到機殼外面**（使用者：「PCIe 壓條通常長在機殼外面，不是往內突出」）。
#   第七輪那條是往內伸 9 mm 的橫樑 + 一顆內凸座，吃內部空間、還擋住電源橫移。
#   新做法：後牆**外表面**凸出一條沿 X 的 T 軌（＝使用者說的「凸出來的結構」），
#   壓條自機殼右外側水平滑上去，內側面的四個舌穿過開孔頂那 6 mm（本來就是給卡抬升的
#   讓位帶）壓在擋板頂緣上。舌只伸入 3.4（牆厚 2.4 + 1.0），**機殼內部沒有任何料**。
# ★ 第九輪：**T 軌 + 沿 X 滑入** 整組刪掉。
#   T 軌本身沒問題，問題是它逼出來的那條「連續橫縫」：壓條的四個壓舌要沿 X 走完
#   全程，就得把四個開孔之間 1.42 的肋在 z∈[129.43, 135.43] 全部切斷 ——
#   三根肋因此變成 112.75 mm 的懸臂。**修「壓條抽不出來」的動作造成了「肋懸空」。**
#   新做法：壓條**直接往 +Y 壓上去**（四個舌各自進自己的開孔，不必沿 X 走），
#   再**往下落 PCIE_BAR_DROP**，兩顆蘑菇柱的頭就被壓條的窄槽咬住（keyhole／鑰匙孔）。
#   拆：抬 3.5 mm、往 −Y 拔。肋一根都不用切。
PCIE_BAR_T = 5.0  # 壓條板厚（沿 Y，長在機殼外）
# 舌只要蓋住擋板（擋板在牆內面的口袋裡，y 到 CASE_REAR+WALL−PCIE_TANG_POCKET+料厚），
# **不可以伸出後牆內面**，否則就變回「往機殼內突出」了（使用者主訴）。
PCIE_BAR_TAB_D = 2.0  # 自後牆外表面往內：蓋滿擋板 0.86 料厚仍留在牆體內
PCIE_BAR_TAB_H = 3.0  # 舌厚（Z）
PCIE_BAR_TAB_W = PCIE_BRACKET_W - 2.0  # 16.42 舌寬（落得進 18.9 開孔）
PCIE_BAR_Z0 = PCIE_Z1 + PCIE_HOLD_GAP  # 129.83 舌底面＝防上抬面
PCIE_BAR_Z1 = PCIE_BAR_Z0 + PCIE_BAR_TAB_H  # 132.83
PCIE_BAR_DROP = 3.5  # keyhole 落差：壓上去之後往下滑這麼多才咬住
PCIE_BAR_FIT = 0.3  # 壓條槽 ↔ 蘑菇柱的單邊滑配
# ★ 開孔頂的抬升帶要同時滿足兩件事，取大的那個（導出，不是挑的）：
#   ①卡要離開連接器得整片抬 PCIE_ENGAGE（+1.5 操作餘裕）
#   ②壓條解鎖時整條往上抬 PCIE_BAR_DROP，四個舌也跟著上去，不能頂到開孔頂
PCIE_LIFT = max(
    PCIE_ENGAGE + 1.5,
    PCIE_HOLD_GAP + PCIE_BAR_TAB_H + PCIE_BAR_DROP + 0.6,
)  # 7.50
# 蘑菇柱（keyhole 的公件）：長在後牆**外**表面、開孔頂之上的連續實料帶。
# 頸窄頭寬；壓條上的槽是「上寬下窄」，頭自寬口穿過、落下後被窄段扣住。
# ★ 第十輪：頸 4.0→8.0、頭 9.0→16.0。整條壓條（連同四片卡的防上抬）就掛在這兩根
#   柱子上，4.0×5.5 的斷面是整個 PCIe 區最細的地方 —— 使用者說「只靠一點點地方
#   連接」，這兩根就是那「一點點」。柱底在開孔頂之上、後牆全寬實料帶，加寬不花代價。
PCIE_HOOK_NECK_W = 8.0  # 頸寬（X）
PCIE_HOOK_HEAD_W = 16.0  # 頭寬（X）；兩側各多出 4.0 的翼 → 翼可彈，detent 就長在翼上
# ★ 頭高必須 ≤ 落差，否則「抬起來讓頭穿過寬口」與「落下後被窄段擋住」兩件事
#   在同一個 Z 上矛盾（推導見 verify 的 keyhole 行程檢查）。
PCIE_HOOK_H = 3.0  # 頸／頭高（Z）
PCIE_HOOK_FUSE = 0.2  # 頭與頸的體積重疊（只有面接觸 fuse() 不會併成單一 Solid）
PCIE_HOOK_NECK_D = PCIE_BAR_T + PCIE_BAR_FIT + PCIE_HOOK_FUSE  # 5.50
PCIE_HOOK_HEAD_D = 2.5  # 頭再往 −Y 凸出
PCIE_HOOK_Z0 = PCIE_Z1 + PCIE_LIFT + 2.0  # 138.93 柱底（開孔頂之上，全寬都是實料）
PCIE_BAR_Z1_TOP = PCIE_HOOK_Z0 + PCIE_HOOK_H + 4.0  # 145.93 壓條頂緣（槽上方留 4 mm 料）

# ============================================================================
# HDD — 第八輪：**平躺 4 層堆疊，疊在主板前段的正上方**（不再是機殼前方的直立碟艙）
# ============================================================================
# 姿態：147 沿 X、101.6 沿 Y、26.1 沿 Z；**接頭朝 +X**（使用者指定「朝內／朝 PCIe 側」）。
# 為什麼是這個姿態（掃描過六種，見 tasks/todo.md 的表）：
#   直立 2×2 之所以只吃 65.10 深，是因為它用「電源撐出來、本來就空著的高度」；
#   電源一往下挪（Area A 88.90 → 50），那段高度就不見了，直立碟艙反而變成高度瓶頸
#   （碟頂 171.4 > 電源決定的內頂 153.32）。平躺才把碟塞回被電源讓出來的體積裡。
HDD_L = 147.00  # 沿機殼 X（SFF-8301 A2 max）
HDD_W = 101.60  # 沿機殼 Y（A3）
HDD_H = 26.10  # 沿機殼 Z（A1 max，3.5" 標準厚）
HDD_COUNT = 4
HDD_LEVELS = 4  # 單排 4 層
# --- 碟托盤（每碟一個，自 +Y 抽出）---
# 厚度不是隨便取的：SFF-8301 p7「Fastener penetration 2.39 min / 3.56 max」，
# 配 #6-32×1/4"(6.35) → 穿入碟體 6.35 − 3.0 = 3.35，落在 [2.39, 3.56] 內。
TRAY_T = 3.0
# ★ 第九輪：舊的 `TRAY_PITCH = HDD_H + TRAY_T` 讀起來像是乾淨的導出式，實際上它讓
#   **碟頂正好貼著上一層托盤的底面（零間隙）**：碟裝不進去、抽出時整片刮、
#   而且層與層之間一絲空氣都過不去。布林檢查看不到（面接觸 common=0），
#   掃描也看不到（同一個平面滑動）。**「≤ 上限」的地方也要檢查「≥ 下限」。**
TRAY_AIR_GAP = 1.5  # 碟頂 → 上一層托盤底的裝配／通風間隙
TRAY_PITCH = HDD_H + TRAY_T + TRAY_AIR_GAP  # 30.60 每層節距
TRAY_RAIL_W = 4.0  # 托盤兩側導軌舌沿 X 伸出
TRAY_RAIL_H = 2.0  # 導軌舌厚（Z）
TRAY_LIP_H = 8.0  # 托盤四周擋邊（防碟橫移）
# 後擋邊佔掉托盤後端這一段，**碟要從它前面開始**，否則擋邊直接長在碟體裡
# （實測干涉 2350 mm³）。碟前緣跟著往前，機殼深度也跟著 +2。
TRAY_BACK_STOP = 2.0
TRAY_FACE_T = 3.0  # 托盤前擋板厚（＝機殼前面板的一部分）
TRAY_PULL_W = 40.0  # 前擋板指拉凹寬（沿 X）
TRAY_PULL_H = 6.0  # 指拉凹高
# --- 3.5" 碟**底面**四孔：SFF-8301 Rev 1.9 Fig.3-1（參考/…pdf p8，圖上量到基準）---
#   A7 = 41.28 自**接頭端** → 第一排；A6 = 44.45 第一排 → 第二排；
#   A13 = 76.20 第一排 → 第三排；A5 = 3.18 側緣 → 孔心；A4 = 95.25 兩側孔中心距。
#   規格 §3.1：**只有 A7 那對是必要的**，A6 或 A13 二選一必要 → 托盤三排孔全開，
#   使用者挑碟上有的那兩排鎖。抄成側孔就是八顆螺絲鎖進塑膠（第五輪踩過）。
HDD_BOT_FROM_CONN = (41.28, 41.28 + 44.45, 41.28 + 76.20)  # (41.28, 85.73, 117.48)
HDD_BOT_FROM_SIDE = 3.18
HDD_BOT_PITCH_Y = 95.25
HDD_SCREW_CLR = 3.6  # #6-32 通孔
HDD_SCREW_HEAD_D = 7.0  # 沉頭讓螺絲頭不凸出托盤底面（否則吃掉層間節距）
HDD_SCREW_HEAD_T = 1.6
# --- 碟陣擺位 ---
# y0 是**硬界線**：碟的 x 帶跨過 AREA_A_STEP_X(−95.25)，x∈[−95.25,−62.55] 那段
# Area A 一路延到 AREA_A_Y_FAR(180.34)。再往後就伸進散熱器空間。
HDD_Y0 = AREA_A_Y_FAR + TRAY_BACK_STOP  # 182.34 碟後緣（托盤後緣在 180.34）
TRAY_Y0 = AREA_A_Y_FAR  # 180.34 托盤／碟架後緣＝Fig.7 的 Area A/C 界線
HDD_Y1 = HDD_Y0 + HDD_W  # 283.94
# ★ 第九輪：碟架立板底面下探到 Area C 淨空頂，**最底層的導軌槽下面才有料**。
#   第八輪 `HDD_Z0 = AREA_C_TOP_Z` 讓立板底面與 lv0 槽底同高（槽底其實還低 0.30），
#   於是最下面那一層的托盤舌**底下是空的**（探針：lv0 舌下方料 0.00，lv1 對照 54.00）
#   —— 使用者一眼就看出來「硬碟卡不住」。
RACK_FLOOR_T = 3.0  # 立板在最底層槽下方保留的承載料（扣掉 SLIDE_FIT 還有 2.70）
RACK_Z0 = AREA_C_TOP_Z  # 48.42 碟架底面＝Area C 淨空頂（機殼的料只能在這之上）
HDD_Z0 = RACK_Z0 + RACK_FLOOR_T  # 51.42 最底層托盤底面
HDD_TOP_Z = HDD_Z0 + HDD_LEVELS * TRAY_PITCH  # 173.82 最上層碟頂
RACK_TOP_T = 3.0  # 碟架頂板厚
RACK_TOP_Z1 = HDD_TOP_Z + RACK_TOP_T  # 176.82 碟架頂面＝內頂面（頂蓋壓著它）

# 內頂面：四個來源取 max，任何一個一改，內頂自己跟著走。
# ★ 第八輪最高的是「碟頂 + 6 線彎折」，但線其實走 +X 側廊不走碟上方 → 那 6 mm 是謊言
#   （硬規則 15）。第九輪改成 **碟架頂板本身**：頂蓋直接壓在碟架頂板上，
#   碟架多了一層由上而下的拘束，而且原本那 3 mm 死空間消失了 ——
#   正好把新增的 RACK_FLOOR_T 3.0 抵掉，承載料是免費長出來的。
# ★ 第十輪：碟架頂板與頂蓋之間補 `RACK_TOP_GAP`。第八～九輪 `INNER_TOP_Z` 直接取
#   `RACK_TOP_Z1`，於是「碟架頂面」與「頂蓋底面」**永遠共面**——頂蓋自 +Y 滑入時
#   要在碟架頂板上磨過 100 mm。這是同一輪抓到的那批零間隙裡的一個，
#   而且它藏在 `max()` 的定義裡，不在任何一條配合面上。
RACK_TOP_GAP = SLIDE_FIT
INNER_TOP_Z = max(
    ATX_Z1 + PSU_CLEAR_MIN,
    PCIE_Z1 + PCIE_LIFT + PCIE_TIE_H,
    RACK_TOP_Z1 + RACK_TOP_GAP,
    AREA_A_TOP_Z,
)
OUTER_TOP_Z = INNER_TOP_Z + TOP_T
# 電源頂上實際剩下的空氣（導出）。第九輪是 27.50 的死空間，第十輪是 1.30 的餘裕，
# 中間那 26.20 mm 全部變成板上的散熱器淨空（50.00 → 76.20）。
PSU_CLEAR_ABOVE = INNER_TOP_Z - ATX_Z1  # 1.30

# 外殼 XY：主板艙 + 前方碟艙 → 單一長方體投影
# ★左壁不可貼板緣：I/O 開孔遠緣（IO_X0）比板左緣還外 2.44 mm，
#   規格另要求開孔四周 2.54 keepout 皆在後牆板面上（microATX 1.2 Fig.4）。
MARGIN = 0.5
IO_EDGE = 3.5  # I/O 開孔外緣 → 機殼外表面的板料（≥ keepout 2.54 + 可印全厚邊）
CASE_LEFT = min(BOARD_LEFT - MARGIN - WALL, IO_X0 - IO_EDGE)  # −215.49
CASE_RIGHT = BOARD_RIGHT + MARGIN + WALL  # +37.19
CASE_REAR = BOARD_REAR - MARGIN - WALL  # −13.06
CASE_W = CASE_RIGHT - CASE_LEFT  # 252.68

# 擋板落位後所在的 Y 帶：舌尖坐進後牆內面的口袋，袋底即 Y 定位面
PCIE_BRACKET_Y0 = CASE_REAR + WALL - PCIE_TANG_POCKET
PCIE_BRACKET_Y1 = PCIE_BRACKET_Y0 + PCIE_BRACKET_T

# 底板（＝主板托盤）：第八輪碟艙不再是獨立外殼段，底板一路鋪到前牆內面
FLOOR_X0 = CASE_LEFT + WALL
FLOOR_X1 = CASE_RIGHT - WALL
FLOOR_Y0 = CASE_REAR + WALL

# ATX 電源擺位：後面貼後牆內面。
# ★ 第十輪：X 不再貼左內牆。電源升到內頂之後，它的頂面（175.52）落進**頂蓋側舌**的
#   Z 帶（173.82–176.82）——舊的 `ATX_X0 = CASE_LEFT + WALL` 會讓電源左緣直接
#   吃進那條舌與它的接料（實測會是 95 + 238 mm³）。**「最終位置合法」在這裡連
#   最終位置都不合法**，只是舊的電源位置低到碰不著而已。
#   解法是 X 讓開頂蓋在 INNER_TOP_Z 以下最內側的那塊料，再加標準件單邊間隙。
TOP_LID_INNER_X = FLOOR_X0 + TOP_FIT_GAP + TOP_FUSE  # −211.69 頂蓋下垂料的最內側
ATX_X0 = TOP_LID_INNER_X + PSU_FIT_GAP  # −210.89
ATX_X1 = ATX_X0 + ATX_W  # −60.89（仍 < AREA_B_X0 −52.07 → 投影整片在 Area A）
ATX_Y0 = CASE_REAR + WALL  # −10.66（PSU 後面＝安裝面）
ATX_FRONT_Y = ATX_Y0 + ATX_D  # 129.34 標稱前緣（線束出口）
ATX_Y1 = ATX_Y0 + ATX_D_ALLOW  # 149.34 艙深極限（長機身）

# 機殼前緣：碟托盤前擋板的外表面就是機殼前面（托盤前擋板＝前面板的一部分）
TRAY_FRONT_GAP = 1.0  # 碟前緣 → 托盤前擋板內面（線頭不在這側，只留裝配餘裕）
CASE_FRONT = HDD_Y1 + TRAY_FRONT_GAP + TRAY_FACE_T  # 287.94
CASE_D = CASE_FRONT - CASE_REAR  # 301.00
# 底板／側板／頂蓋只做到 BAY_SPLIT_Y（見檔尾）——A1 床 256 放不下 299 長的件。

# ============================================================================
# 全滑槽組裝（第八輪：**一顆機殼螺絲都沒有**，使用者要求）
# ============================================================================
# ★ 第十輪：互鎖鏈改成**使用者指定的組裝順序**，底板是基準、後牆是最後一件：
#   ① 底板放在桌上（基準）
#   ② 左右側板自 +Y **往 −Y 水平滑上底板**（側板內面的低位槽咬住底板兩側的舌），
#      滑到最後 FLOOR_DETENT_RUN mm 時側緣的縱向 bead 落進側板的凹槽 → 卡住
#   ③ 後牆自 −Y **往 +Y 推進去**：兩端的定位舌插進側板後端的口袋（detent ×3／側），
#      同時底板後緣的舌插進後牆內面的低位槽（detent ×2）→ 三片互鎖成一個 U
#   ④ 電源自 +Z 落入（先前移 PSU_SLIDE_Y 讓開後牆頂鉤唇）、主板／PCIe 卡裝好
#   ⑤ 碟架自 +Y 滑入側板槽 → ⑥ 頂蓋自 +Y 滑入側板頂槽，後端鑽進後牆頂鉤唇下方
#   → ⑦ 前罩自 +Y 套上（四面半搭接 + detent）→ ⑧ 碟托盤自 +Y 插入
#   第八／九輪寫的是「後牆先落下、側板後落下」，與使用者的順序相反；
#   幾何上兩種都通得過，但文件講的是一套、掃描驗的是另一套，遲早會對不起來。
# 最後的保持力**不用 snap-fit 柱**（CLAUDE.md：實印會從層間斷掉），
#   改用**側向半球 detent**：凸半球受的是面內剪力，不是層間拉力。
# 滑槽的四個數字（FLOOR_LIP／FLOOR_LIP_T／FLOOR_LEDGE_T／TOP_LIP）已移到檔案上方，
#   因為 ATX_X0 要用到 TOP_FIT_GAP。方向仍是「底板插進牆」不是「牆插進底板」：
#   主板佔滿內腔（右 0.50／後 1.00），板底 6.35 淨空又封死 z∈[2.4, 8.75] →
#   從底板往上長的唇會直接戳進主板。
# ★ 角落**不能用燕尾**：燕尾大端要 6–8 mm，而牆厚只有 2.4 —— 兩片 2.4 的板
#   在角落咬不住任何燕尾。改用「薄定位舌（X 定位）+ 半球 detent（保持力）」。
REAR_TAB_T = 1.2  # 後牆兩端往前伸的定位舌厚
REAR_TAB_D = 4.0  # 定位舌沿 Y 伸出長度
REAR_DETENT_Z = (40.0, 100.0, 155.0)  # 定位舌上的 detent 高度（避開電源承托肩 86.52–89.52）
# ★ 第十一輪：後牆的六顆 detent 從**半球**改成**不對稱楔形（斜面進、直面擋）**。
#   第十輪量出來的真相表：後牆往 −Y 拉，>12 mm 都沒有任何幾何擋住 ——
#   八顆半球是唯一的阻力，而半球在受拉時會**自己爬出來**（cam-out）。
#   後牆正是 AC 線、I/O 線、PCIe 卡拔插時受 −Y 力的那一面。
#   純滑動接合的公母**進出走的是同一道邊**，所以不對稱只能做在**公件**上：
#     公件（側板口袋底的楔）：−Y 面是斜坡（舌前緣爬上去）、+Y 面是直角（拉不出來）
#     母件（後牆定位舌上的孔）：單純一個孔，不需要方向性
#   拆機時先卸前罩→抽頂蓋→側板往 +Y 滑走，楔跟著側板一起離開 → 後牆自然鬆開。
#   底板後舌那兩顆**維持半球**：它們若也做成直角，後牆就永遠拆不下來
#   （拉不出、又被槽鎖住抬不起）。留一組可 cam-out 的當作拆卸路徑。
#   母件是**自舌根往前開的缺口**，不是舌中間的孔：直角面推的是缺口的前緣，
#   那前緣必須被整片舌料頂著。開在舌中間的話，前緣只剩 0.45 mm 的細肉，
#   一拉就把它掰斷 —— 卡榫看起來有、實際上是一次性的。
REAR_WEDGE_RAMP = 1.5  # 斜坡長（沿 +Y；斜坡起點＝側板後端面，坡度 21.8°）
REAR_WEDGE_BACK = 0.8  # 峰頂平台長（列印時不要收成尖角）
REAR_WEDGE_H = 5.0  # 楔沿 Z 的高度（缺口比它高 → Z 讓位，Z 定位是槽的事不是楔的事）
# ★ 半徑受**定位舌厚度**限制：球是整顆球不是半球，球心埋進 R−DEPTH 之後，
#   另一端還要留在舌體內 → 2R ≤ REAR_TAB_T + DETENT_DEPTH = 1.8 → R ≤ 0.9。
#   R 取 1.2 的話球會從舌的內表面戳出來 0.6，直接插進電源本體（實測 1.1 mm³）。
DETENT_R = 0.9  # 半球 detent 半徑（≥0.5 最小可印特徵；受的是面內剪力不是層間拉力）
# ★ 球心要**內移** R − DEPTH，凸出量才是 0.6。球心放在表面上的話過盈就是整個
#   半徑 1.2，PETG 擠不過去（而且滑入掃描會一直紅在設計意圖上）。
DETENT_DEPTH = 0.6  # 實際凸出／坑深（靠料的彈性爬過去）
# ★ 第十輪新增：**底板 ↔ 側板**的保持力（使用者主訴 2b「底板與左右側板之間缺卡榫」）。
#   這一條的難處是**行程 244.84 mm**：球長在誰身上都會一路磨。解法是
#   「球長在**不動的底板**上、而且靠近底板後端」——側板的槽是自它的**後端**開始
#   掃過球的，所以只有最後 FLOOR_DETENT_RUN mm 才有過盈。
#   形狀用**沿 Z 的半圓 bead**不是半球：可用高度只有承載唇那 1.10 mm，
#   半球會被壓成一顆極小的球（R ≤ 0.55，低於最小可印特徵 0.5 的邊緣）。
FLOOR_DETENT_R = 0.9  # bead 半徑（軸沿 Z）
FLOOR_DETENT_DEPTH = 0.6  # 凸出底板側緣的量（其中 SLIDE_FIT 是間隙，其餘是過盈）
FLOOR_DETENT_RUN = 12.0  # bead 中心距底板後緣 → 也就是過盈行程長度
FLOOR_DETENT_N = 2  # 每側兩顆（前後排開，兩顆之間 FLOOR_DETENT_PITCH）
FLOOR_DETENT_PITCH = 18.0
# 底板後緣舌 ↔ 後牆槽：後牆只推 +Y 幾 mm，行程短 → 用半球就好。
# 球長在**底板的舌**上（純加料）、坑挖在**後牆槽的頂面**（那上面整片都是牆，挖得起）。
# 半徑由「球不得從舌的另一面戳出去」導出：2R ≤ FLOOR_LIP_T + DETENT_DEPTH。
REAR_FLOOR_DETENT_X = (-150.0, -20.0)  # 兩顆，避開主板柱與 I/O 區
FLOOR_REAR_DETENT_R = (FLOOR_LIP_T + DETENT_DEPTH) / 2  # 0.80
TOP_HOOK_D = 6.0  # 後牆頂鉤唇往前伸出（頂蓋後端鑽進它下方 → 頂蓋不能上抬）
TOP_HOOK_T = 1.5  # 鉤唇厚（＝TOP_T 的一半；頂蓋後端同樣只留下半 → 半搭接）
# 碟架側舌槽。★ 第九輪改由**碟架自己的頂**導出，不再由 PCIe 卡導出：
#   卡長現在被碟架的後緣切在 189.00（見檔尾 PCIE_CARD_LEN），卡根本不伸到碟架的
#   y 帶（180.34 起）裡，「舌要讓開卡」已經是**不成立的理由**——留著它就是硬規則 15
#   說的謊言。新的理由是承載：舌吊在頂板正下方 2 mm，力臂最短、又與頂板同一塊料。
RACK_RAIL_T = 1.2  # 舌伸入側板的深度
RACK_RAIL_H = 6.0  # 舌高（Z）
RACK_RAIL_Z1 = HDD_TOP_Z - 2.0  # 171.82 舌頂＝碟架頂板下方 2 mm
RACK_RAIL_Z0 = RACK_RAIL_Z1 - RACK_RAIL_H  # 165.82

# 頂蓋：**嵌入式**（牆長到 OUTER_TOP_Z，蓋子落進牆圍成的口，頂面與牆頂齊平）。
# ★ 第十輪：`TOP_LEDGE_T / TOP_LEDGE_W`（第七輪的頂蓋承托肩）整組刪掉。
#   那條肩第八輪就已經從幾何裡拿掉了，參數卻留了兩輪，而且 verify 還在拿
#   `TOP_LEDGE_T` 當「電源頂淨空要放得下承托肩」的門檻 —— 一個不存在的東西
#   決定了電源能升多高（硬規則 15：定義了卻沒被引用的參數＝謊言）。
# ★ 第八輪：後牆的頂蓋承托肩刪了，X 向不必再讓位；改成必須讓開**後牆頂鉤唇**
#   （它往前伸 TOP_HOOK_D，電源後面板要貼後牆就得先閃過它）。
#   實測不讓位的話電源掃上去撞鉤唇 450 mm³ —— 這種「最終位置合法、路被擋住」
#   正是硬規則 14 說的那一類，只有掃描抓得到。
PSU_SLIDE_X = 0.0
PSU_SLIDE_Y = TOP_HOOK_D + 1.0  # 7.0
# ★ 第八輪頂蓋改**單片、自 +Y 水平滑入**（第七輪的兩片半搭接是碟艙分段的產物，
#   碟艙不再是獨立外殼段之後，接縫也沒有理由存在了）。

# --- 前面板進氣柵（唯一進氣口）---
# 氣流只有一條：前柵 → 碟（層間 1.5 氣隙）→ 主板腔 → 電源風扇（朝下）→ 後方排出。
# 側板／頂蓋不開孔：那些孔說不出誰要走，而且會讓氣流短路。
# ★ 第八輪柵開在**碟托盤的前擋板**上（托盤就是前面板），加上碟陣下方的固定前板。
FRONT_VENT_SLAT = 9.0  # 條柵開口高
FRONT_VENT_PITCH = 12.0
FRONT_VENT_MARGIN = 12.0  # 柵區左右各留的實料
TRAY_VENT_ROWS = 2  # 每片托盤前擋板上的柵列數
FRONT_LOWER_Z1 = HDD_Z0  # 碟陣下方那片固定前板的頂緣（48.42）
FRONT_VENT_Z0 = FLOOR_T + 8.0
FRONT_VENT_Z1 = FRONT_LOWER_Z1 - 4.0

# --- 電源按鈕 ---
PWR_BTN_D = 10.2  # 10 mm 面板式瞬時按鈕的安裝孔（含 FDM 收縮餘量）
PWR_BTN_NUT_D = 15.0  # 內側螺帽轉動所需淨空
PWR_BTN_DEPTH = 22.0  # 按鈕本體 + 焊接端子往機殼內伸入
# ★ 第八輪：按鈕搬到碟陣**下方**那片固定前板（z < 48.42）。碟托盤是活動件，
#   按鈕不能長在會被抽出來的東西上。內側 z∈[2.4,48.42]、y>233.68 是主板前方的空腔，
#   按鈕本體 22 深伸進去不撞任何東西。
PWR_BTN_Z = 26.0

# --- Bambu Lab A1 床規格 ---
# 來源＝本機安裝的 Bambu Studio 機台 profile（權威值，不是搜尋摘要）：
#   resources/profiles/BBL/machine/Bambu Lab A1 0.4 nozzle.json
#     printable_area = 0x0 256x0 256x256 0x256 / printable_height = 256 / bed_exclude_area = []
# ★ 常見誤傳「A1 前左角有 18×28 排除區、可印高度 250」——那是 P1P/P1S/X1 系列與通用預設值。
A1_MAX = 256.0
A1_H_MAX = 256.0
A1_EXCLUDE = ()
A1_PROFILE_REL = r"resources\profiles\BBL\machine\Bambu Lab A1 0.4 nozzle.json"


def board_zone(x, y):
    """
    板上某點屬於 microATX Fig.7 的哪一區（case 座標）。
    板外回傳 None。界線全部出自 Fig.7 p18 的向量座標。
    """
    if not (BOARD_LEFT <= x <= BOARD_RIGHT and BOARD_REAR <= y <= BOARD_FRONT):
        return None
    if x >= AREA_B_X0:
        return "B"
    limit = AREA_A_Y_NEAR if x <= AREA_A_STEP_X else AREA_A_Y_FAR
    return "A" if y <= limit else "C"


def psu_zone_ok():
    """電源在板上的投影是否**整片**落在 Area A（其餘區的淨空不夠 88.90）。"""
    bad = []
    for x in (max(ATX_X0, BOARD_LEFT), ATX_X1):
        for y in (max(ATX_Y0, BOARD_REAR), ATX_Y1):
            z = board_zone(x, y)
            if z is not None and z != "A":
                bad.append((x, y, z))
    return (not bad), bad


def psu_bottom_clearance():
    """電源底面 → 板面的淨空（應 ≥ AREA_A_CLEARANCE）。"""
    return ATX_Z0 - BOARD_TOP_Z


def psu_top_clearance():
    """電源頂面 → 內頂面。"""
    return INNER_TOP_Z - ATX_Z1


def front_vent_area():
    """
    前柵開口總面積 mm²（唯一進氣口，須 ≥ 電源風扇面積）。
    第八輪分兩處：碟陣**下方**那片固定前板（前罩上）+ **每片碟托盤的前擋板**。
    """
    w = (HDD_TRAY_X1 + TRAY_RAIL_W) - (HDD_TRAY_X0 - TRAY_RAIL_W) - 2 * FRONT_VENT_MARGIN
    n_lower = int((FRONT_VENT_Z1 - FRONT_VENT_Z0) // FRONT_VENT_PITCH)
    n_tray = TRAY_VENT_ROWS * HDD_LEVELS
    return max(0.0, w) * FRONT_VENT_SLAT * (n_lower + n_tray)


def tray_z0(level: int):
    """第 level 層（0=最下）托盤**底面** z。"""
    return HDD_Z0 + level * TRAY_PITCH


def hdd_drive_origin(level: int):
    """
    第 level 層碟的左後下角。姿態：147 沿 X、101.6 沿 Y、26.1 沿 Z，
    **接頭端朝 +X**（使用者指定朝內／朝 PCIe 側），底面朝 −Z（坐在托盤上）。
    """
    return HDD_X0, HDD_Y0, tray_z0(level) + TRAY_T


def hdd_bottom_hole_xy(level: int):
    """
    該層碟的底面孔座標 [(x, y)]（SFF-8301 Fig.3-1）。
    接頭端在 +X → 自碟右緣（HDD_X1）往 −X 量 A7/A6/A13。
    """
    pts = []
    for d in HDD_BOT_FROM_CONN:
        x = HDD_X1 - d
        for y in (HDD_Y0 + HDD_BOT_FROM_SIDE, HDD_Y0 + HDD_BOT_FROM_SIDE + HDD_BOT_PITCH_Y):
            pts.append((x, y))
    return pts


def cable_corridor_x():
    """
    接頭走線區：碟的接頭端面 → 右立板內面。**在碟架裡面**，不是外面。
    第八輪這個函式回傳的是立板**外側**那條 88.88 的帶——那條帶確實很寬，
    但碟的接頭在立板內側，兩者中間隔著 6 mm 實心料。
    """
    return (HDD_X1, RACK_POST_X0)


def side_gap_x():
    """碟架左右兩側到內牆的餘裕（置中後應相等）。"""
    return (RACK_X0 - (CASE_LEFT + WALL), (CASE_RIGHT - WALL) - RACK_POST_X1)


def tray_opening_x():
    """前罩上碟托盤穿過的口（＝托盤含導軌舌 + 單邊 TOP_FIT_GAP）。"""
    g = TOP_FIT_GAP
    return (HDD_TRAY_X0 - TRAY_RAIL_W - g, HDD_TRAY_X1 + TRAY_RAIL_W + g)


def tray_opening_margin():
    """開口到機殼左右外表面的距離（要相等才是對稱）。"""
    lo, hi = tray_opening_x()
    return (lo - CASE_LEFT, CASE_RIGHT - hi)


def pwr_btn_x():
    """電源按鈕 X：碟架右側那條空帶的中心（碟陣下方的固定前板上，見 PWR_BTN_Z）。"""
    return (RACK_POST_X1 + (CASE_RIGHT - WALL)) / 2


def pwr_btn_corridor_w():
    return (CASE_RIGHT - WALL) - RACK_POST_X1


def pcie_centers():
    """第一槽在 +X 擴充側緣內，其後往 −X（朝 B／I/O）以 pitch 排列。"""
    return [PCIE_FIRST_CX - i * PCIE_PITCH for i in range(PCIE_COUNT)]


def psu_slide_room():
    """
    電源右緣 → 機殼內最近的障礙 的可橫移量（須 ≥ PSU_SLIDE_X）。
    ★ 第八輪壓條移到機殼外之後，這條帶**整條都是空的**：內部已經沒有任何凸座。
    """
    return (CASE_RIGHT - WALL) - ATX_X1


def pcie_hook_x():
    """
    兩顆蘑菇柱的中心 X。柱在 z = PCIE_HOOK_Z0（開孔頂之上）→ 那個高度後牆全寬實心，
    所以柱可以擺在任何 x；擺在壓條兩端，力臂最長。
    """
    cs = pcie_centers()
    h = PCIE_HOOK_HEAD_W / 2
    return (min(cs) - PCIE_OPEN_W / 2 - h - 1.0, CASE_RIGHT - h - 0.5)


def pcie_bar_x():
    """壓條本體 X 範圍（在機殼**外面**）：涵蓋四個壓舌與兩顆蘑菇柱。"""
    lo, hi = pcie_hook_x()
    h = PCIE_HOOK_HEAD_W / 2
    return (lo - h - 2.0, min(CASE_RIGHT, hi + h + 2.0))


def project_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(script_dir)
    return {
        "root": root,
        "scripts": script_dir,
        "cad": os.path.join(root, "CAD"),
        "stl": os.path.join(root, "列印件"),
    }


def envelope_mm():
    """
    整機外包絡 (W, D, H)。單一長方體：無階梯、無外凸腳、無下裙。
    ★ 深度**不含**後牆外側的 PCIe 壓條（它掛在後牆外 4 mm）——那是外掛件，
      但機殼靠牆擺時它會頂到牆，所以 verify 另有一條檢查把它算進「安裝深度」。
    """
    return (CASE_W, CASE_D, OUTER_TOP_Z + SKIRT_H)


def rear_outer_protrusion():
    """
    後牆外表面往 −Y 最凸的量。★ 第十輪修正：舊版 `install_depth_mm` 直接回傳
    `CASE_D + PCIE_BAR_T`，而最凸的其實是 **keyhole 蘑菇柱 8.00**（頸 5.5 + 頭 2.5），
    壓條只有 5.0 —— 少報 3 mm。更糟的是那條 verify 拿
    `install_depth_mm() <= CASE_D + PCIE_BAR_T` 去比，**它在跟自己的定義比**，
    永遠是綠的（vacuous check，硬規則 16）。
    """
    return max(PCIE_BAR_T, PCIE_HOOK_NECK_D + PCIE_HOOK_HEAD_D, PCIE_RIB_D)


def install_depth_mm():
    """含後牆外掛件的安裝深度（靠牆擺時真正需要的深度）。"""
    return CASE_D + rear_outer_protrusion()


def case_volume_l():
    """實際佔用體積（公升）。外形已是長方體，W×D×H 就是實佔。"""
    w, d, h = envelope_mm()
    return w * d * h / 1e6


def io_edge_material():
    """I/O 開孔遠緣 → 機殼外表面的板料寬（須 ≥ IO_KEEPOUT + 可印邊）。"""
    return IO_X0 - CASE_LEFT


# 列印檔名（第八輪：11 個列印件）
# ★ 分件的理由是 **A1 床 256**：CASE_D = 301.00 > 256，底板／側板／頂蓋不可能一件到底。
#   所以機殼仍分「主板段（247.24 深，印得下）」與「前罩（53.76 深）」，
#   碟架**橫跨**兩段（y 180.34→283.94）並把兩段繫在一起——它取代了第七輪的搭接片。
STL_NAMES = {
    "Bottom_Tray": "底板_主板托盤.stl",
    "Rear_IO_PCIe": "後牆_IO與PCIe.stl",
    "Side_Left_MB": "左側板_主板段.stl",
    "Side_Right_MB": "右側板_主板段.stl",
    "Top_MB": "頂蓋_主板段.stl",
    "Front_Shroud": "前罩_含進氣柵.stl",
    "HDD_Rack": "碟架_四層導軌.stl",
    "HDD_Tray": "碟托盤.stl",  # ×4
    "PCIeBlank": "PCIe槽蓋.stl",
    "PCIeBar": "PCIe壓條_外置.stl",
    "MB_Nut": "主板壓帽.stl",
}
STRUCT_PART_KEYS = tuple(STL_NAMES)
TRAY_COUNT = HDD_COUNT  # 碟托盤 ×4（同一個 STL 印四份）

# 每個 STL 要印幾份。**買料要用這個，不是「一件一份」的和。**
# 第十一輪之前 `PRINT_VOLUME` 是逐件加總、沒有乘份數，於是文件寫的
# 「印料 1032 cm³」少算了碟托盤 ×3 與壓帽 ×8，實際是 1240 cm³（差 20%）。
# 份數一律由既有常數導出，不寫魔術數字（硬規則 15）。
PART_QTY = {
    "Bottom_Tray": 1,
    "Rear_IO_PCIe": 1,
    "Side_Left_MB": 1,
    "Side_Right_MB": 1,
    "Top_MB": 1,
    "Front_Shroud": 1,
    "HDD_Rack": 1,
    "HDD_Tray": TRAY_COUNT,
    "PCIeBlank": PCIE_COUNT,  # 最壞情況：四槽全空
    "PCIeBar": 1,
    "MB_Nut": MB_NUT_COUNT,
}
if set(PART_QTY) != set(STL_NAMES):  # 漏件守衛（硬規則 7）
    raise SystemExit(
        "PART_QTY 與 STL_NAMES 不一致：%s" % (set(PART_QTY) ^ set(STL_NAMES),)
    )
# 已移除（不得再出現）
REMOVED_SHELL_PARTS = (
    "Side_Left_HDD",
    "Side_Right_HDD",
    "Front_Panel",
    "ClampCap",
    "ClampTray",
    "Bottom_ATX",
    "Top_HDD",  # 第八輪：頂蓋不再分兩片
    "HDD_Cage",  # 第八輪：直立碟艙外殼 → 平躺碟架
)
REMOVED_STL = (
    "左側板_碟艙段.stl",
    "右側板_碟艙段.stl",
    "前板.stl",
    "旋蓋.stl",
    "主板托盤.stl",
    "底板_ATX艙.stl",
    "頂蓋_碟艙段.stl",
    "硬碟艙_四盤.stl",
    "PCIe壓條.stl",  # 第八輪改外置，檔名換成「PCIe壓條_外置.stl」
)
# 主板段 ↔ 前罩 的分界面（＝底板／側板／頂蓋的前緣）。A1 床 256 逼出來的接縫。
BAY_SPLIT_Y = BOARD_FRONT + MARGIN  # 234.18
FLOOR_Y1 = BAY_SPLIT_Y

# --- 碟架（HDD_Rack）：左右兩片立板 + 頂板，托盤自 +Y 滑入立板內面的導軌槽 ---
# 立板要 RACK_WALL 厚才放得下 TRAY_RAIL_W 深的槽（2.4 的牆放不下 4 深的槽）。
RACK_WALL = 6.0
# ★ 第九輪最重要的一條：**右立板不准貼著碟的接頭面**。
#   第八輪 `RACK_POST_X0 = HDD_X1`，6 mm 的實心 PETG 正對 101.6×26.1 的接頭端面，
#   四層各干涉 15.8–18.0 cm³ ——「走線空間不足」講得太客氣了，是**接頭插不上**。
#   右側那條 88.88 mm 的「走線廊」在**立板外面**，接頭在**立板裡面**，中間隔著牆。
#   留了空間 ≠ 空間在正確的地方。
HDD_CABLE_W = 30.0  # 碟接頭面 → 右立板內面：SATA 資料 + 電源接頭與線彎折
# ★ 碟架**置中**（使用者：開孔要左右對稱）。左右各餘 (247.88 − 189)/2 = 29.44。
RACK_W = 2 * RACK_WALL + HDD_L + HDD_CABLE_W  # 189.00 碟架外寬
RACK_X0 = ((CASE_LEFT + WALL) + (CASE_RIGHT - WALL) - RACK_W) / 2  # −183.65
HDD_X0 = RACK_X0 + RACK_WALL  # −177.65 碟左緣（＝托盤本體左緣）
HDD_X1 = HDD_X0 + HDD_L  # −30.65 碟右緣（接頭端）
RACK_POST_X0 = HDD_X1 + HDD_CABLE_W  # −0.65 右立板（讓開整條接頭區）
RACK_POST_X1 = RACK_POST_X0 + RACK_WALL  # 5.35
# 托盤本體一路鋪到右立板：走線區下方要有底，線才不會垂到 PCIe 卡上。
# （托盤在 z∈[tray_z0, +3.0]，接頭與線在它上方，互不相干）
HDD_TRAY_X0 = HDD_X0
HDD_TRAY_X1 = RACK_POST_X0
# 右側兩條橫樑：把碟架繫到右側板（右立板離右內牆 29.44）。分兩條讓線從中間穿過。
RACK_BEAM_W = 12.0  # 沿 Y
RACK_BEAM_Y = (HDD_Y0 + 6.0, BAY_SPLIT_Y - 8.0)  # 都落在側板槽的 y 帶內
# ★ 第十一輪：側板碟架槽的**盲端**（＝碟架往 −Y 推到底的止擋面）。
#   第十輪量出來：碟架往 −Y 還能再走 3.00 mm 才撞到側板 —— 槽的後端開到
#   TRAY_Y0 − 1.0 = 179.34，比最後那條側舌的後緣（182.34）還後面 3 mm。
#   「裝得進去」驗過了，「推到底會停在哪裡」沒有人問。碟架浮 3 mm，
#   四顆碟與托盤前緣跟著浮，前罩開口就對不齊。
#   同一條界線由同一個來源導出（硬規則 9）：盲端 = 最後一條側舌的後緣 − 滑配。
RACK_STOP_Y = min(RACK_BEAM_Y) - RACK_BEAM_W / 2 - SLIDE_FIT  # 182.04
SHROUD_Y0 = BAY_SPLIT_Y
SHROUD_D = CASE_FRONT - SHROUD_Y0  # 53.76
SHROUD_LAP = 12.0  # 前罩往後搭在主板段外表面上的長度（滑合帶）
SHROUD_LAP_T = 1.2  # 前罩搭接殼厚（側板外表面對應減薄 SHROUD_LAP_T + SLIDE_FIT）
# ★ 第九輪：前罩不再只是「套著」。第八輪搭接帶 nominal 零間隙、沒有舌、沒有槽、
#   沒有 detent —— 使用者問「你確定前蓋是用卡槽蓋卡住的嗎」，答案是不確定，它不是。
#   現在：四面半搭接（左右／頂／底）+ 兩顆 detent。
SHROUD_WALL = 1.6  # 前罩側牆／頂板厚（打薄；前面板仍 TRAY_FACE_T、地板仍 FLOOR_T）
SHROUD_TOP_LAP_T = TOP_T / 2  # 1.5 頂蓋前段上表面減薄量（前罩頂舌填回去）
SHROUD_FLOOR_LAP_T = FLOOR_T / 2  # 1.2 底板前段上表面減薄量（前罩地板舌壓上去）
# detent 半徑受**側板減薄後剩下的料厚**限制：剩 WALL − SHROUD_LAP_T − SLIDE_FIT = 0.90
#   → 2R ≤ 0.90 + DEPTH。取 R=0.70／DEPTH=0.60（1.40 ≤ 1.50 ✓，且 0.70 ≥ 0.50 可印）。
SHROUD_DETENT_R = 0.70
SHROUD_DETENT_DEPTH = 0.60
SHROUD_DETENT_Z = (55.0, 100.0, 145.0)  # ★ 第十輪 2 → 3 顆／側
# ★ 第十輪：使用者說「前罩需要設計一個卡槽」。四面半搭接本來就是滑槽，
#   缺的是**保持力**——第九輪只有左右各兩顆 detent，頂與底整片是光的。
#   現在頂搭接（頂蓋減薄帶）與底搭接（底板減薄帶）也各兩顆 → 全機 10 顆。
#   半徑受**減薄帶剩下的料厚**限制：底板帶 FLOOR_T − SHROUD_FLOOR_LAP_T = 1.20，
#   頂蓋帶 TOP_T − SHROUD_TOP_LAP_T = 1.50 → 2R ≤ 1.20 + DEPTH。
SHROUD_LAP_DETENT_R = 0.70
SHROUD_LAP_DETENT_DEPTH = 0.45
SHROUD_LAP_DETENT_X = (-150.0, -20.0)  # 避開主板柱讓位槽（L/M 兩孔）與底板兩側舌
# 應支援的 PCIe 卡長：由**碟架後緣**切出來（碟架 y ≥ 180.34 整段都是實體）。
# ★ 這是**刻意的取捨**：第八輪寫 230，那時碟陣在機殼左半、卡的右半沒人擋。
#   第九輪把碟架置中之後，卡的 x 帶與碟架重疊 → 只能二選一。使用者說過
#   「頂多只會插一些網路口的擴充卡」，所以選了碟架。189.00 仍 > CEM 半長卡 167.65。
PCIE_CARD_LEN = TRAY_Y0 - (CASE_REAR + WALL) - 2.0  # 189.00

# ============================================================================
# 組裝順序（第十輪，使用者指定）—— **唯一來源**
# ============================================================================
# (件名, 沿 Y 的裝入位移)。0 = 基準件（放著不動）；負 = 自 +Y 往 −Y 滑進去；
# 正 = 自 −Y 往 +Y 推進去。verify 依這張表**逐步**掃描：第 i 件掃的時候，
# 場上只有第 0..i−1 件 —— 這樣才真的是在驗「照這個順序裝得起來」，
# 而不是「每一件在最後那個場景裡動得了」。
# ★ 第八／九輪的掃描是後者：每一條都拿**完整總成**當障礙物，
#   於是「後牆要先裝還是後裝」這件事從來沒有被驗過。
ASSEMBLY_STEPS = (
    ("Bottom_Tray", 0.0),
    ("Side_Left_MB", -(BAY_SPLIT_Y - FLOOR_Y0 + 20.0)),
    ("Side_Right_MB", -(BAY_SPLIT_Y - FLOOR_Y0 + 20.0)),
    ("Rear_IO_PCIe", REAR_TAB_D + 6.0),
    ("HDD_Rack", -(CASE_FRONT - TRAY_Y0)),
    ("Top_MB", -(CASE_FRONT - FLOOR_Y0)),
    ("Front_Shroud", -(SHROUD_LAP + SHROUD_D + 20.0)),
    ("HDD_Tray", -(HDD_W + TRAY_FRONT_GAP + 10.0)),
)


def floor_detent_sites(is_left):
    """
    底板側緣 bead（軸沿 Z）的 (中心 x, 中心 y)。**唯一來源**：底板 fuse 它、
    側板 cut 對應凹槽、verify 量它。bead 外表面凸出底板側緣 FLOOR_DETENT_DEPTH，
    其中 SLIDE_FIT 是本來就有的間隙，剩下的才是過盈。
    """
    if is_left:
        cx = (FLOOR_X0 + SLIDE_FIT) - FLOOR_DETENT_DEPTH + FLOOR_DETENT_R
    else:
        cx = (FLOOR_X1 - SLIDE_FIT) + FLOOR_DETENT_DEPTH - FLOOR_DETENT_R
    return [
        (cx, FLOOR_Y0 + FLOOR_DETENT_RUN + i * FLOOR_DETENT_PITCH)
        for i in range(FLOOR_DETENT_N)
    ]


def floor_detent_run_mm():
    """bead 的過盈行程長度（側板槽自它的後端掃過來，只有最後這一段有過盈）。"""
    return FLOOR_DETENT_RUN + (FLOOR_DETENT_N - 1) * FLOOR_DETENT_PITCH


def pcie_frame_x():
    """
    PCIe 窗框補強在 X 上的範圍（四個開孔外緣各再延伸 PCIE_FRAME_M）。
    左端必須讓開 **I/O 開孔**（補強是 fuse 在後牆外表面上的，蓋過去就是把
    I/O 開孔從外面補起來一塊），右端不得超出機殼外表面（單一長方體）。
    """
    cs = pcie_centers()
    return (
        max(min(cs) - PCIE_OPEN_W / 2 - PCIE_FRAME_M, IO_X1 + 1.0),
        min(max(cs) + PCIE_OPEN_W / 2 + PCIE_FRAME_M, CASE_RIGHT),
    )


def pcie_frame_z():
    """窗框補強在 Z 上的範圍：自開孔底下方 PCIE_FRAME_M 到壓條下緣（讓開壓條本體）。"""
    return (PCIE_Z0 - PCIE_FRAME_M, PCIE_BAR_Z0 - SLIDE_FIT)


FCSTD_NAME = "機殼總成.FCStd"
