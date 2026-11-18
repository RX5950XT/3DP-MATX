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
AREA_A_SPEC_RECOMMENDED = 88.90  # Table 6 recommended（仍未達到，見 tasks/todo.md）
AREA_A_CLEARANCE = max(COOLER_MAX_H, AREA_A_SPEC_REQUIRED)  # 76.20
AREA_B_CLEARANCE = 15.24  # Table 6：0.60 in（擴充槽區）
AREA_C_CLEARANCE = 38.10  # Table 6：1.50 in
AREA_B_X0 = -52.07  # intel 2.050 in → Area B（擴充槽帶）自此往 +X 到板右緣
AREA_A_STEP_X = -95.25  # intel 3.750 in：A/C 界線在此換階
AREA_A_Y_NEAR = 154.94  # intel 6.100 in：x ≤ AREA_A_STEP_X 段的 A/C 界線
AREA_A_Y_FAR = 180.34  # intel 7.100 in：x ∈ [STEP, B_X0] 段的 A/C 界線

# --- 主板固定（Ø8 支撐肩內的盲內牙 + 專用印製螺絲）---
# Ø8 粗肩提供 microATX §2.4.2 的 6.35 mm 板底淨空；PCB 上方不再有固定於機殼的細軸。
# 螺絲採 2.50 mm 粗牙距：5 mm 有兩圈旋合，女性牙頂約 0.85 mm，可由 0.4 nozzle 成形。
SHOULDER_OD = 8.0
SHOULDER_H = 6.35
MB_THREAD_MAJOR = 3.50
MB_THREAD_DEPTH = 0.60
MB_THREAD_MINOR = MB_THREAD_MAJOR - 2 * MB_THREAD_DEPTH
MB_THREAD_PITCH = 2.50
MB_THREAD_ROOT_W = 0.50
MB_THREAD_CREST_W = 0.25
MB_THREAD_GAP = 0.20
MB_THREAD_ENGAGE = MB_THREAD_DEPTH - MB_THREAD_GAP
MB_THREAD_ENGAGEMENT = 5.0
MB_SOCKET_END_GAP = 0.20
MB_SOCKET_DEPTH = MB_THREAD_ENGAGEMENT + MB_SOCKET_END_GAP
MB_SCREW_THREAD_LEN = PCB_T + MB_THREAD_ENGAGEMENT
MB_SCREW_HEAD_AF = 8.0
MB_SCREW_HEAD_H = 2.4
MB_SCREW_HEAD_D = MB_SCREW_HEAD_AF / 0.8660254037844386  # 9.24，仍在 Ø10.16 keepout 內
# 頭頂十字工具槽（第十四輪）。螺絲是**頭面貼床**印的，槽開在貼床那一面 ->
# 槽壁落在第一層最銳利，槽頂只是 CROSS_W 寬的橋接（0.12 層高橋 1.8 mm 免支撐）。
# 直邊十字（非 Phillips 錐面）不會 cam-out；PETG 靠的是側壁剪力不是楔緊。
MB_SCREW_CROSS_W = 1.8
MB_SCREW_CROSS_L = 5.6
MB_SCREW_CROSS_DEPTH = 1.5
MB_SCREW_CROSS_WALL = (MB_SCREW_HEAD_AF - MB_SCREW_CROSS_L) / 2
MB_SCREW_CROSS_ROOF = MB_SCREW_HEAD_H - MB_SCREW_CROSS_DEPTH
MB_SCREW_COUNT = len(HOLES_MM)
MB_KEEPOUT_D = 10.16  # microATX 0.400" 九孔 keepout 直徑（規格只保證板底側）

# --- 壁厚／地板／下裙 ---
WALL = 2.4
TOP_T = 3.0
FLOOR_T = 2.4
# 滑槽單邊間隙（PETG 滑配）。目前供 Top、Front、Rack 與 HDD Tray 的配合面共用；
# **零間隙不是精密，是裝不上**——第八輪前罩搭接帶 nominal 0，布林 common=0.000
# 被讀成「不干涉」，其實是「套不進去」。
SLIDE_FIT = 0.30
# ★ 第十輪：所有滑槽的幾何常數集中到這裡（原本散在檔案下半，而 ATX_X0 要用到它們）。
#   起因是量出來的：`distToShape(底板, 側板) = 0.0000`、後牆、頂蓋全部一樣——
#   **每一個配合面都是 nominal 零間隙**。第九輪只修了前罩搭接與層節距兩處，
#   同一個病其實長在整條互鎖鏈上。零間隙不是精密，是裝不上（硬規則 19）。
#
#   一道滑槽的四個數字（牆厚 2.4 全部要塞進去）：
#     舌伸出量 LIP → 槽深 = LIP + SLIDE_FIT → 槽背後剩料 = WALL − 槽深 ≥ 0.8（可印）
#     ⇒ LIP ≤ WALL − 0.8 − SLIDE_FIT = 1.30
GROOVE_BACK_MIN = 0.8  # 頂蓋槽挖完後牆上必須保留的可印料厚
# 切片器的支撐判準（第十四輪）。preset `support_threshold_angle` 的**唯一來源**：
# 斜率（自水平量起，90° = 垂直牆）小於它的朝下面才生支撐。幾何側的「45° 尖頂／
# 45° 斜撐／45° 引入楔」全部靠這個數字才算數，所以兩邊必須同一個常數
# （`驗切片設定.py` 直接拿它比 preset，硬規則 9）。
SUPPORT_THRESHOLD_ANGLE = 30.0
CHASSIS_OVERLAP = 1.0  # 一體件地板／側牆／後牆的 CSG 反向重疊
TOP_LIP = WALL - GROOVE_BACK_MIN - SLIDE_FIT  # 1.30，頂蓋側舌咬合量
TOP_FIT_GAP = 0.4  # 頂蓋本體四周單邊間隙
TOP_FUSE = 1.0  # 舌與本體的體積重疊
# ★ 第八輪：**下裙整個刪掉**（SKIRT_H = 0，參數保留給 negtest 對照）。
#   下裙唯一的存在理由是「機殼內部沒有地方放 M3 銅母座」；現在主機殼是一體式，
#   可拆外殼件沿用滑配，沒有任何結構螺絲需要下裙承座。PCIeBar 的兩顆外側 #6-32
#   鎖在後牆補強座，與下裙無關。機殼底面就是地板下表面，整片落地。
SKIRT_H = 0.0

# 主板支撐肩：直接長在一體式地板上；盲孔底仍保留 1.15 mm 實料
SHOULDER_TOP_Z = FLOOR_T + SHOULDER_H  # 8.75
MB_SOCKET_BOTTOM_Z = SHOULDER_TOP_Z - MB_SOCKET_DEPTH  # 3.55
MB_SOCKET_BOTTOM_MATERIAL = MB_SOCKET_BOTTOM_Z - FLOOR_T  # 1.15
BOARD_TOP_Z = SHOULDER_TOP_Z + PCB_T  # 10.32
MB_SCREW_HEAD_TOP_Z = BOARD_TOP_Z + MB_SCREW_HEAD_H

# 三個分區的「機殼淨空頂面」——機殼在該區的料只能在這個 z 以上
AREA_A_TOP_Z = BOARD_TOP_Z + AREA_A_CLEARANCE  # 86.52
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
# ★ 第十三輪：Figure 4 有**兩張圖**，前十二輪只用了正視圖。側視圖（p14 下半）
#   才是深度方向的基準，而且它同時給了 Z 的第二基準：
#     `.088±.010 [2.24±0.25] From bottom surface of motherboard or top of chassis standoffs`
#         → 支撐肩頂 8.75 − 開孔底 6.51 = 2.24 ✓ Z 一直是對的
#     `0.483±.010 [12.27±0.25]`  Datum B → 後牆（I/O aperture 平面）
#   再配 Figure 5 note：`.445±.008 [11.30±0.2]` Datum B → **I/O 連接器的面**，
#   也就是連接器面比 PCB 後緣（10.16）還往後突出 1.14 mm。
#   第七～十二輪 `CASE_REAR = BOARD_REAR − MARGIN − WALL` 讓後牆內面落在 −10.66，
#   連接器面 −11.30 **戳進牆 0.64 mm** —— 主板推不到底，使用者實印時看到的
#   「I/O 開孔高度對不上」其實是 Y 差 1.61 mm。`MARGIN = 0.5` 是隨手取的，
#   從來沒有對過這張側視圖（與第七輪孔位同一類：讀了正視圖標註、沒對側視圖基準）。
IO_FROM_STANDOFF_TOP = 2.24  # Fig.4 側視 .088±.010（IO_Z0 的第二基準，供對照）
IO_APERTURE_FROM_B = 12.27  # Fig.4 側視 0.483±.010：Datum B → I/O aperture 平面
IO_CONN_FACE_FROM_B = 11.30  # Fig.5 note：Datum B → I/O 連接器的面
IO_CONN_DEPTH = 30.0  # 連接器本體自面往板內的虛擬件深度（堆疊 RJ45/USB 典型值）

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
#   第八輪的橫縫已刪；第十二輪改成卸下兩顆外側 #6-32 後，壓條沿 −Y 整片抽離，
#   不再需要沿 X 滑動，繫樑恢復成真的料。
# ★ 第十三輪：6.0 → 6.5。繫樑頂面現在要鑽兩個 MB_SOCKET_DEPTH 深的盲內牙
#   （壓條的鎖點，見 PCIE_BAR_*），6.0 只剩 0.80 孔底料，6.5 才有 1.30。
PCIE_TIE_H = 6.5  # 開孔上方的連續繫樑：肋的**上端固定端** + 壓條鎖點
# ★ 第十輪：加厚的範圍從「只有肋」擴大到**整圈窗框**（使用者：PCIe 還是很多問題）。
#   第九輪把三根肋補到 1.42×6.40，但窗框的其他三邊還是 2.4：
#   底檻（舌袋挖掉 1.3 之後只剩 **1.1**）、左右柱、繫樑。一個 80×120 的洞開在
#   2.4 的板子上，補強只補了中間三根肋 —— 框本身才是那片牆最軟的地方。
#   往**機殼外**長不吃任何內部淨空（外面除了壓條什麼都沒有），
#   而且底檻加厚之後舌袋剩料 1.1 → 5.1，擋板的 Y 定位面終於不是一層皮。
PCIE_RIB_D = 4.0  # 窗框（含肋）往機殼外加厚（斷面 1.42×2.40 → 1.42×6.40，I ×19）
# ★ 第十四輪：窗框底緣加 45° 引入楔。窗框自後牆外面往 −Y 凸 PCIE_RIB_D，底面
#   （z = pcie_frame_z()[0]）本來是 89.4 × 4.0 的水平懸空，就在三根肋的正下方，
#   支撐塔從床長到 8.68 且與窗框外面焊在一起 —— 撬它就是在撬肋的根部。
#   楔的斜面自牆面 z0 − PCIE_RIB_D 升到窗框底，剛好 45°，不吃任何額外包絡
#   （Y 仍止於 CASE_REAR − PCIE_RIB_D，A1 餘量 0.96 mm/邊不受影響）。
PCIE_FRAME_LEAD = PCIE_RIB_D
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

# --- PCIe 卡固定：外置共享壓條 + 兩顆標準螺絲 ---
# CEM 折耳下只有 0.06 mm 永久固定料餘量，因此固定件仍必須先拆，卡才能抬升 4.50 mm。
# 第十二輪刪除 keyhole／蘑菇柱：實印無法可靠固定，而且 8 mm 後凸使一體件支撐後超出 A1。
PCIE_BAR_T = 5.0  # 保留厚共享壓條，避免把 102 mm 跨距削成軟薄片
PCIE_BAR_TAB_D = 2.0
PCIE_BAR_TAB_H = 3.0
PCIE_BAR_TAB_W = PCIE_BRACKET_W - 2.0
PCIE_BAR_Z0 = PCIE_Z1 + PCIE_HOLD_GAP
PCIE_BAR_Z1 = PCIE_BAR_Z0 + PCIE_BAR_TAB_H
PCIE_LIFT = PCIE_ENGAGE + 1.5  # 6.00：卡離開連接器 4.50 + 操作餘量

# ★ 第十三輪：開孔頂改 **45° 尖頂**（使用者：拆支撐會把中間三根細桿一起扯斷）。
#   病灶不是肋不夠粗，是那四個開孔**需要支撐**：開孔頂 z=135.43 是 18.9 mm 寬的
#   水平懸空，切片器在四個 118 mm 深的槽裡各長一根支撐塔，塔與 1.42 mm 的肋
#   互相咬死，拆的時候橫向力全部由肋承受。把開孔頂做成 45°，切片器判定不需支撐 →
#   **根本不用拆**。順手的副作用：三根肋的上端由三角形連成桁架，比矩形繫樑更剛。
#   尖頂**自擋板抬到頂的位置起算**，全寬區一點都沒有少（抬升 6.00 不受影響）。
PCIE_OPEN_Z1 = PCIE_Z1 + PCIE_LIFT  # 135.43 全寬開孔頂＝擋板抬到頂的頂緣位置
PCIE_APEX_H = PCIE_OPEN_W / 2  # 9.45：45° ⇒ 尖頂高＝半寬
PCIE_APEX_Z = PCIE_OPEN_Z1 + PCIE_APEX_H  # 144.88 尖頂頂點
PCIE_TIE_Z0 = PCIE_APEX_Z  # 繫樑底＝尖頂頂點
PCIE_TIE_Z1 = PCIE_TIE_Z0 + PCIE_TIE_H  # 151.38 繫樑頂＝壓條鎖點所在面

# --- 壓條鎖固：印製盲內牙 + 沿用 MB_Screw（第十三輪；使用者：壓條根本沒有用）---
# 舊做法是兩顆 **#6-32 自攻**進 PETG 的 Ø2.8 盲 pilot —— 保持力全靠塑膠被鋼牙擠開，
# 鎖第二次就滑牙。改成與主板固定同一套已驗證的 ruled-loft 印製盲內牙，配 `MB_Screw`。
#
# ★ 軸向為什麼還是 −Y（而不是列印品質更好的 +Z）：垂直盲牙的螺絲頭必須落在
#   後牆**外表面之外**，Ø9.24 的頭要 4.62 的 Y 半徑，繫樑只有 WALL + PCIE_RIB_D
#   = 6.40 厚 —— 補到放得下就得往 −Y 再凸 3 mm 以上，而 Chassis 的 Y 只剩
#   0.96 mm/邊 的 A1 餘量（實測凸 2.5 就是 255.4 裸深，加支撐直接超床）。
#   機殼的尺寸不能為了一個鎖點被撐爆，所以維持 −Y，靠「真的有牙」而不是靠自攻。
# ★ 螺絲不新增第九種 STL 的條件是**夾持厚 = PCB_T**：壓條在鎖點處挖沉頭凹，
#   凹底剩 PCIE_BAR_SEAT_T，螺絲頭沉進去（後凸也因此比舊版少 3 mm）。
PCIE_BAR_SCREW_COUNT = 2
PCIE_BAR_SEAT_T = PCB_T  # 1.57 壓條在鎖點的剩餘厚 ＝ MB_Screw 的夾持厚
PCIE_BAR_HOLE_D = PCB_HOLE_D  # 3.96 與主板孔同級的通孔
PCIE_BAR_CBORE_D = MB_SCREW_HEAD_D + 0.6  # 9.84 沉頭凹（六角頭 8 mm AF 轉得動）
PCIE_LOCK_Z = (PCIE_TIE_Z0 + PCIE_TIE_Z1) / 2  # 148.13 盲牙軸＝繫樑中間高度
PCIE_BAR_Z1_TOP = PCIE_TIE_Z1  # 壓條本體頂＝繫樑頂（蓋住鎖點）

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
    PCIE_TIE_Z1,
    RACK_TOP_Z1 + RACK_TOP_GAP,
    AREA_A_TOP_Z,
)
OUTER_TOP_Z = INNER_TOP_Z + TOP_T
# 電源頂上實際剩下的空氣（導出）。第九輪是 27.50 的死空間，第十輪起是個位數的餘裕，
# 中間那 26.20 mm 全部變成板上的散熱器淨空（50.00 → 76.20）。
PSU_CLEAR_ABOVE = INNER_TOP_Z - ATX_Z1  # 1.60

# 外殼 XY：主板艙 + 前方碟艙 → 單一長方體投影
# ★左壁不可貼板緣：I/O 開孔遠緣（IO_X0）比板左緣還外 2.44 mm，
#   規格另要求開孔四周 2.54 keepout 皆在後牆板面上（microATX 1.2 Fig.4）。
MARGIN = 0.5
IO_EDGE = 3.5  # I/O 開孔外緣 → 機殼外表面的板料（≥ keepout 2.54 + 可印全厚邊）
CASE_LEFT = min(BOARD_LEFT - MARGIN - WALL, IO_X0 - IO_EDGE)  # −215.49
CASE_RIGHT = BOARD_RIGHT + MARGIN + WALL  # +37.19
# ★ 第十三輪：後牆的深度**不是**由板緣加餘量決定的，是由 Fig.4 側視的
#   `Datum B → I/O aperture 平面 = 12.27` 決定（見 IO_APERTURE_FROM_B 的註解）。
#   舊式 `BOARD_REAR − MARGIN − WALL` 得到 −13.06、內面 −10.66，比連接器面
#   −11.30 還要往前 0.64 —— 板根本推不到底。內面就是 aperture 平面。
CASE_REAR = -(IO_APERTURE_FROM_B + WALL)  # −14.67（內面 −12.27 = aperture 平面）
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
ATX_Y0 = CASE_REAR + WALL  # −12.27（PSU 後面＝安裝面）
ATX_FRONT_Y = ATX_Y0 + ATX_D  # 127.73 標稱前緣（線束出口）
ATX_Y1 = ATX_Y0 + ATX_D_ALLOW  # 147.73 艙深極限（長機身）

# 機殼前緣：碟托盤前擋板的外表面就是機殼前面（托盤前擋板＝前面板的一部分）
TRAY_FRONT_GAP = 1.0  # 碟前緣 → 托盤前擋板內面（線頭不在這側，只留裝配餘裕）
CASE_FRONT = HDD_Y1 + TRAY_FRONT_GAP + TRAY_FACE_T  # 287.94
CASE_D = CASE_FRONT - CASE_REAR  # 302.61
# 底板／側板／頂蓋只做到 BAY_SPLIT_Y（見檔尾）——A1 床 256 放不下 299 長的件。

# ============================================================================
# 第十二輪外殼接合：一體式 Chassis_Body + 可拆滑配件
# ============================================================================
# Chassis_Body 已把地板、左右牆與後牆用 CHASSIS_OVERLAP 融成單一列印件；
# 第十／十一輪只服務四件式 Chassis 的舌、bead、楔與 detent 已退役並由 verify 防回歸。
# 現役可拆鏈的唯一來源是檔尾 ASSEMBLY_STEPS：Rack → Top → Front → HDD Tray。
# Top／Front／Rack／Tray 的滑槽仍共用 SLIDE_FIT；牆厚 2.4 放不下燕尾，薄舌槽的
# 咬合量必須同時保留 GROOVE_BACK_MIN 的槽背牆料。
# ★ 第十四輪：6.0 → 3.0。鉤唇底面是**全寬 248 mm 的水平懸空**，切片器要從床
#   一路長 176 mm 的支撐塔貼著後牆內面上來，而那面正是三根 1.42 肋的內側 ——
#   使用者實印時「拆支撐把三根細桿一起扯斷」扯的就是這片塔（實測朝下面積
#   1487 mm²，全 Chassis 第二大，且是唯一橫跨整個 PCIe 開孔區的）。
#   底面無法做 45° 自撐：往下 4.5 mm 就是頂蓋本體（INNER_TOP_Z 177.12、TOP_T 3.0），
#   斜撐會把頂蓋後緣整片吃掉。只能減深 —— 而 6.0 本來就說不出它擋住什麼：
#   側舌真正的咬合量只有 TOP_LIP = 1.30，3.0 已是它的 2.3 倍。
TOP_HOOK_D = 3.0  # 後牆頂鉤唇往前伸出；頂蓋後端鑽入其下
TOP_HOOK_T = 1.5
# ★ 第十三輪：後牆補一道**與側槽同 z 帶**的頂蓋槽（使用者：後牆好像沒有卡槽）。
#   第十二輪後方只有 `TOP_HOOK` 鉤唇，它限制的是 +Z；頂蓋往 −Y 推到底時
#   **沒有任何面擋住它**，六向保持力表裡 −Y 那一格靠的是兩顆 detent 的摩擦。
#   槽底面就是 −Y 止擋，而且頂蓋後緣從此是被夾住的舌，不是一條懸空邊。
#   鉤唇保留：兩者 z 帶不重疊（唇 178.62–180.12、槽 174.12–177.42），職責也不同
#   （唇擋外側 +Z、槽擋 −Y 與內側 +Z），唇上的兩顆 detent 因此不必搬家。
TOP_REAR_LIP = TOP_LIP  # 1.30 後舌咬合量（與側舌同一個牆厚上限）
# 頂鉤前端兩顆 detent 只在頂蓋最後約 6 mm 行程越過，避免整段滑槽磨耗。
TOP_DETENT_R = 0.70
TOP_DETENT_DEPTH = 0.45
TOP_DETENT_X = (-150.0, -20.0)
# 碟架側舌槽。★ 第九輪改由**碟架自己的頂**導出，不再由 PCIe 卡導出：
#   卡長現在被碟架的後緣切在 189.00（見檔尾 PCIE_CARD_LEN），卡根本不伸到碟架的
#   y 帶（180.34 起）裡，「舌要讓開卡」已經是**不成立的理由**——留著它就是硬規則 15
#   說的謊言。新的理由是承載：舌吊在頂板正下方 2 mm，力臂最短、又與頂板同一塊料。
RACK_RAIL_T = 1.2  # 舌伸入側板的深度
RACK_RAIL_H = 6.0  # 舌高（Z）
RACK_RAIL_Z1 = HDD_TOP_Z - 2.0  # 171.82 舌頂＝碟架頂板下方 2 mm
RACK_RAIL_Z0 = RACK_RAIL_Z1 - RACK_RAIL_H  # 165.82
# ★ 第十三輪：**承托肩**（使用者：側板對應的溝槽太淺，能不能往內伸一塊擋板托住碟架）。
#   第十二輪整個碟架 + 4 顆碟（≈2.8 kg）吊在 4 條橫樑末端伸進側槽的
#   `RACK_RAIL_T − SLIDE_FIT = 0.90` mm 上，承載面積 4 × 12 × 0.90 = **43 mm²**，
#   而且是剪力落在 2.4 mm 牆挖完槽只剩 1.2 的槽背料上。牆厚 2.4 放不下更深的槽
#   （`GROOVE_BACK_MIN` 卡死上限），所以承重不能再靠咬合 —— 改成橫樑**坐在**
#   牆內面長出來的實心肩上，槽退化成純粹的 +Z 約束。
#   合法性：肩在 z ≈ 157–166，遠高於 Area A 頂（86.52）與 Area C 頂（48.42）；
#   y ≥ RACK_STOP_Y(182.04) 讓開電源（y ≤ ATX_Y1 149.34）與 PCIe 卡（y ≤ 178+）。
#   列印性：下表面做 45° 斜撐，Chassis 地板貼床時自撐，不多一根支撐。
#   間隙：肩頂比橫樑底低 SLIDE_FIT —— 滑入時不磨，載重後落 0.30 就坐實
#   （硬規則 19：配合面要嘛量出間隙、要嘛把間隙寫進導出式）。
RACK_LEDGE_D = 8.0  # 肩自牆內面往內伸出（承重寬度）
RACK_LEDGE_T = 4.0  # 肩的矩形段厚（斜撐另計）
RACK_LEDGE_Z1 = RACK_RAIL_Z0 - SLIDE_FIT  # 165.52 肩頂面
RACK_LEDGE_Z0 = RACK_LEDGE_Z1 - RACK_LEDGE_T  # 161.52 矩形段底
# 斜撐要真的是 45°，量的是「自**埋入牆內的根部**算起」的水平距（硬規則 1：
# 外伸特徵的根部必須反向埋進母體，只有面接觸 fuse() 不會合併）。
RACK_LEDGE_GUSSET = RACK_LEDGE_D + CHASSIS_OVERLAP  # 9.0 ⇒ 斜撐底 152.52

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
PSU_SLIDE_Y = TOP_HOOK_D + 1.0  # 4.0（第十四輪鉤唇 6.0 → 3.0 後跟著縮）
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


def top_rear_tab_bands():
    """
    頂蓋後舌（與後牆對應槽）的 X 段。

    後舌與側舌同 z 帶（INNER_TOP_Z−TOP_T … INNER_TOP_Z），而那個高度上機殼內
    有兩個東西佔著：電源頂 ATX_Z1（x ATX_X0…ATX_X1）與碟架頂板 RACK_TOP_Z1
    （x RACK_X0…RACK_POST_X1）。舌是**整條路徑掃過去**的，不是只出現在最終位置
    —— 讓不開就會在滑入途中刮過它們（硬規則 14／22：最終位置合法不等於路走得通）。
    左段因此被電源壓成側舌那麼窄，右段（電源右緣以外、碟架右立板以外）才是主力。
    """
    return (
        (FLOOR_X0 - TOP_LIP, ATX_X0 - PSU_FIT_GAP),
        (RACK_POST_X1 + SLIDE_FIT, FLOOR_X1 + TOP_LIP),
    )


def pcie_rib_x():
    """三根槽間肋的中心 X（相鄰兩槽中心的中點）。"""
    cs = sorted(pcie_centers())
    return [(cs[i] + cs[i + 1]) / 2 for i in range(len(cs) - 1)]


def pcie_lock_x():
    """
    壓條兩顆螺絲的鎖點 X ＝ **最外兩根肋的正上方**。
    ★ 第十三輪：舊做法把鎖座擺在四個開孔的左右兩側，右側只剩
      `CASE_RIGHT − 最右開孔緣 = 3.61`，塞不下通孔加壁料；而且鎖座是獨立
      長出來的懸臂，跟窗框是兩塊分開的料。鎖在肋的正上方之後，螺絲的拉力
      直接落在肋的上端固定端上，與繫樑同一塊料（硬規則 20：要問另一端接到哪裡）。
    """
    ribs = pcie_rib_x()
    return (ribs[0], ribs[-1])


def pcie_bar_x():
    """外置壓條 X 範圍：涵蓋四個開孔（含尖頂）與兩個耳。"""
    cs = pcie_centers()
    return (min(cs) - PCIE_OPEN_W / 2 - 1.0, max(cs) + PCIE_OPEN_W / 2 + 1.0)


def pcie_bar_mount_y():
    """壓條的安裝面（貼著窗框補強外表面的那一面）＝盲牙的開口面。"""
    return CASE_REAR - PCIE_RIB_D


def pcie_lock_socket_end():
    """盲牙盲端的 Y；後牆內面必須還有料（盲孔不能打穿到內腔）。"""
    return pcie_bar_mount_y() + MB_SOCKET_DEPTH


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
    深度不含後牆外側的 PCIe 窗框補強、PCIeBar 與兩顆 #6-32 螺絲頭；
    `rear_outer_protrusion()` 另算完整裝機靠牆所需的後凸。
    """
    return (CASE_W, CASE_D, OUTER_TOP_Z + SKIRT_H)


def rear_outer_protrusion():
    """
    完整裝機時後牆外表面往 −Y 最凸的量（窗框補強 + 鎖點凸台 + 壓條）。
    ★ 第十三輪螺絲軸由 Y 改 Z，螺絲頭朝上不再吃 Y ⇒ 最凸的就是壓條外表面。
      這是導出值，不是量測值；verify 另從幾何量 `obb().YMin` 對照（硬規則 16）。
    """
    return CASE_REAR - (pcie_bar_mount_y() - PCIE_BAR_T)


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


# 列印件 manifest（第十二輪：8 種 STL）
STL_NAMES = {
    "Chassis_Body": "機殼本體_主板段一體式.stl",
    "Top_MB": "頂蓋_主板段.stl",
    "Front_Shroud": "前罩_含進氣柵.stl",
    "HDD_Rack": "碟架_四層導軌.stl",
    "HDD_Tray": "碟托盤.stl",
    "PCIeBlank": "PCIe槽蓋.stl",
    "PCIeBar": "PCIe壓條_外置.stl",
    "MB_Screw": "主板螺絲_印製.stl",
}
# 六向保持力表只展開真正可拆的外殼件；Chassis 是基準，PCIeBar／螺絲另做專用檢查。
STRUCT_PART_KEYS = ("Top_MB", "Front_Shroud", "HDD_Rack", "HDD_Tray")
TRAY_COUNT = HDD_COUNT

PART_QTY = {
    "Chassis_Body": 1,
    "Top_MB": 1,
    "Front_Shroud": 1,
    "HDD_Rack": 1,
    "HDD_Tray": TRAY_COUNT,
    "PCIeBlank": PCIE_COUNT,
    "PCIeBar": 1,
    # ★ 第十三輪：`MB_Screw` 不再只服務主板。壓條的兩顆鎖點改成同規格的印製盲內牙，
    #   螺絲是同一顆 → 份數是 9 + 2。只寫 MB_SCREW_COUNT 就是硬規則 26 的漏乘。
    "MB_Screw": MB_SCREW_COUNT + PCIE_BAR_SCREW_COUNT,
}
if set(PART_QTY) != set(STL_NAMES):  # 漏件守衛（硬規則 7）
    raise SystemExit(
        "PART_QTY 與 STL_NAMES 不一致：%s" % (set(PART_QTY) ^ set(STL_NAMES),)
    )
# 已移除（不得再出現）
REMOVED_SHELL_PARTS = (
    "Bottom_Tray",
    "Rear_IO_PCIe",
    "Side_Left_MB",
    "Side_Right_MB",
    "MB_Nut",
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
    "底板_主板托盤.stl",
    "後牆_IO與PCIe.stl",
    "左側板_主板段.stl",
    "右側板_主板段.stl",
    "主板壓帽.stl",
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
RACK_BEAM_W = 12.0  # 側舌橫樑沿 Y
# ★ 第十三輪加第三根。前兩根都在 Chassis 的 y 範圍內（≤ BAY_SPLIT_Y 234.18），
#   而碟架一路到 283.94 —— **前段 49.76 mm 是純懸臂**，Chassis 構不到，
#   第十二輪那裡什麼都沒有。第三根落在前罩的承托肩上（前罩 y ≥ 234.18），
#   前段懸臂降到 HDD_Y1 − 281.94 ≈ 2 mm。它在 Chassis 範圍外，**沒有側舌**
#   （那裡沒有牆槽），純粹是坐在肩上的承重樑。
RACK_BEAM_Y = (HDD_Y0 + 6.0, BAY_SPLIT_Y - 8.0, HDD_Y1 - RACK_BEAM_W / 2 - 2.0)
# 有側舌的橫樑（只有落在 Chassis 側牆槽 y 範圍內的那幾根）
RACK_RAIL_BEAM_Y = tuple(by for by in RACK_BEAM_Y if by + RACK_BEAM_W / 2 <= BAY_SPLIT_Y)
# 最底層托盤下方的承托格柵：三條 X 橫樑由中央 Y 縱樑連成一體。
RACK_BASE_BEAM_W = 12.0
RACK_BASE_BEAM_Y = (
    TRAY_Y0 + RACK_BASE_BEAM_W / 2,
    (TRAY_Y0 + HDD_Y1) / 2,
    HDD_Y1 - RACK_BASE_BEAM_W / 2,
)
RACK_BASE_SPINE_W = 12.0
RACK_BASE_SPINE_X = (RACK_X0 + RACK_POST_X1) / 2
RACK_BASE_Z1 = HDD_Z0 - SLIDE_FIT  # lv0 托盤底保留 0.30 mm 滑配
# ★ 第十一輪：側板碟架槽的**盲端**（＝碟架往 −Y 推到底的止擋面）。
#   第十輪量出來：碟架往 −Y 還能再走 3.00 mm 才撞到側板 —— 槽的後端開到
#   TRAY_Y0 − 1.0 = 179.34，比最後那條側舌的後緣（182.34）還後面 3 mm。
#   「裝得進去」驗過了，「推到底會停在哪裡」沒有人問。碟架浮 3 mm，
#   四顆碟與托盤前緣跟著浮，前罩開口就對不齊。
#   同一條界線由同一個來源導出（硬規則 9）：盲端 = 最後一條側舌的後緣 − 滑配。
RACK_STOP_Y = min(RACK_BEAM_Y) - RACK_BEAM_W / 2 - SLIDE_FIT  # 182.04
SHROUD_Y0 = BAY_SPLIT_Y
SHROUD_D = CASE_FRONT - SHROUD_Y0  # 53.76
SHROUD_LAP = 14.0  # 加長搭接，提高導向與側向保持
SHROUD_LEAD_IN = 1.0  # 四個先進入端的 45° 導入
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
# --- 第十三輪：前罩搭接帶改 U 形雙壁夾持 ---
# 使用者：「前罩插上去的地方，能不能改成有縫隙可以插進去、兩邊夾住的方式，
# 而不是單純靠單邊凸點卡槽卡住？」第十二輪搭接帶只有**外壁**一片（SHROUD_LAP_T）
# 貼在側牆的外面減薄帶上，牆的內面整片是光的 —— 前罩對牆只有一個方向有料，
# 側向保持全靠 detent 的摩擦。補一片內壁之後，Chassis 的牆被整片夾在中間。
SHROUD_INNER_T = 1.6  # 內壁厚（前罩不承重；與 SHROUD_WALL 同級）
# 內壁只能長在牆內面**沒有滑槽**的 z 帶（build_case.side_lap_thin_bands()），
# 下限再讓開 Area B 淨空（右牆內面到主板右緣只有 0.50，內壁是長在板上方的料），
# 上限再讓開碟架承托肩的 45° 斜撐底。左側 x 在板緣外本無此限，取同值保持對稱。
SHROUD_INNER_Z0 = AREA_B_TOP_Z + SLIDE_FIT  # 25.86
SHROUD_INNER_Z1 = RACK_LEDGE_Z0 - RACK_LEDGE_GUSSET - SLIDE_FIT  # 152.22
# 內壁貼的是 **Chassis 牆的內面**，而前罩主體壁的內面比它外 SHROUD_WALL − WALL − ...
# 差 1.10 mm ⇒ 進了主體段要有一塊料把兩者接起來，否則內壁是自由飄浮的板。
SHROUD_INNER_JOIN = 4.0
# --- 碟架承托肩的 Y 範圍（Chassis 段與前罩段接力）---
RACK_LEDGE_Y0 = RACK_STOP_Y  # 182.04 自碟架推到底的止擋面起
RACK_LEDGE_Y1 = SHROUD_Y0 - SHROUD_LAP  # 220.18 到前罩搭接帶起點（讓開內壁）
SHROUD_LEDGE_D = RACK_LEDGE_D  # 前罩段的肩與 Chassis 段同寬（硬規則 9：同一界線同一來源）
SHROUD_LEDGE_Y0 = SHROUD_Y0 + SLIDE_FIT  # 234.48 讓開 Chassis 牆的前端面
SHROUD_LEDGE_Y1 = CASE_FRONT - TRAY_FACE_T  # 284.94 到前面板內面
# 前罩列印姿態是 Y−（前面板朝上、搭接帶貼床），y 就是列印高度方向 ⇒ 肩在 ly0
# 那一層不能憑空出現整個斷面。貼床端做 45° 楔形引入（高＝肩厚），維持無支撐。
SHROUD_LEDGE_LEAD = RACK_LEDGE_T  # 4.0 ⇒ 45°
# 應支援的 PCIe 卡長：由**碟架後緣**切出來（碟架 y ≥ 180.34 整段都是實體）。
# ★ 這是**刻意的取捨**：第八輪寫 230，那時碟陣在機殼左半、卡的右半沒人擋。
#   第九輪把碟架置中之後，卡的 x 帶與碟架重疊 → 只能二選一。使用者說過
#   「頂多只會插一些網路口的擴充卡」，所以選了碟架。190.61 仍 > CEM 半長卡 167.65。
PCIE_CARD_LEN = TRAY_Y0 - (CASE_REAR + WALL) - 2.0  # 190.61

# ============================================================================
# 組裝順序（第十二輪）—— **唯一來源**
# (件名, 沿 Y 的裝入位移)。0 = 一體式 Chassis 基準；負 = 自 +Y 往 −Y 滑入。
# verify 依這張表逐步掃描：第 i 件移動時，場上只有第 0..i−1 件。
ASSEMBLY_STEPS = (
    ("Chassis_Body", 0.0),
    ("HDD_Rack", -(CASE_FRONT - TRAY_Y0)),
    ("Top_MB", -(CASE_FRONT - FLOOR_Y0)),
    ("Front_Shroud", -(SHROUD_LAP + SHROUD_D + 20.0)),
    ("HDD_Tray", -(HDD_W + TRAY_FRONT_GAP + 10.0)),
)


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
    """
    窗框補強在 Z 上的範圍：自開孔底下方 PCIE_FRAME_M 到**繫樑頂**。
    ★ 第十三輪上限由「壓條下緣」改成 `PCIE_TIE_Z1`。壓條在補強層的**外面**
      （y ∈ [CASE_REAR − PCIE_RIB_D − PCIE_BAR_T, CASE_REAR − PCIE_RIB_D]），
      兩者 y 不重疊，本來就不必為它讓開；而繫樑頂面現在是壓條的鎖點所在面，
      補強層不長到那裡的話，那兩個盲內牙就鑽在只有 2.4 厚的牆上。
    """
    return (PCIE_Z0 - PCIE_FRAME_M, PCIE_TIE_Z1)


FCSTD_NAME = "機殼總成.FCStd"
