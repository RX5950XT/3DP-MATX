# 3DP-MATX todo
最後更新：2026-11-19

規格、8 種列印件、組裝、印前三件事、重建指令與驗證分層見 `README.md`；硬規則見 `CLAUDE.md`（= `AGENTS.md`）；歷輪病灶見 `tasks/lessons.md`。尺寸唯一來源是 `腳本/參數.py`，文件都是它的投影。

## 現況（交接，第十四輪＋文件同步，2026-08-26）
- 外形 252.68 × 302.61 × 180.12 mm（13.77 L）；8 種 STL、24 件；一件一份 `PRINT_VOLUME` 1081.3 cm³，含份數 `FILAMENT_VOLUME` 1300.2 cm³ ≈ 1.66 kg PETG。
- 主機殼是單一 `Chassis_Body`（地板、左右牆、後牆真實融合）；Top、Front、HDD Rack、HDD Tray 可拆。組裝掃描唯一來源：`Chassis_Body → HDD_Rack → Top_MB → Front_Shroud → HDD_Tray`。
- 主板：9 個 Ø8 × 6.35 支撐肩內切 5.20 盲內牙＋印製 `MB_Screw`；`PCIeBar` 外置，由 2 顆同規格 `MB_Screw` 鎖繫樑盲內牙（鎖點沉頭、夾持厚 = `PCB_T`）→ `MB_Screw` 實印 11 顆。頭頂 5.6 × 1.8 × 深 1.5 直邊十字槽開在貼床面（第一層的孔，免支撐）。
- Rack 底部 3 條 12 mm 橫樑＋1 條中央縱樑，與 lv0 托盤留 0.30；碟架坐在左右牆 `RACK_LEDGE` 承托肩（伸出 8.0、45° 斜撐自撐），承重 576 mm²、懸臂 8.00。
- 常設支撐地圖：`verify_case.support_overhangs()` 掃全件平面朝下面，PCIe 開孔 x 帶內一片都不准有（FAIL），帶上方逐條 WARN。
- 最後一次全套驗證（第十四輪）：ruff 通過、71 tests OK、BUILD_OK、ALL CHECKS PASSED、NEGTEST 86/86、擺位 Chassis 0.81 mm/邊、`驗切片設定.py` FAILURES = 0、GUI 重載 8 objects 四視角已看。文件同步輪只改文件與註解，未重跑 build／negtest。

### 近兩輪結論（細節在 `tasks/lessons.md`）
- R13：I/O 深度基準錯 1.61 mm 已修（`CASE_REAR = −(IO_APERTURE_FROM_B + WALL) = −14.67`）；PCIe 開孔頂改 45° 尖頂；後牆補頂蓋槽；前罩搭接改 U 形雙壁夾持；碟架改坐承托肩。
- R14：扯斷 PCIe 1.42 肋的是 `TOP_HOOK` 鉤唇底面拉起的 176 mm 支撐塔，不是開孔支撐 → 鉤唇 6.0 → 3.0、窗框底緣加 45° 引入楔。支撐 preset 改脫模導向：xy 0.35、top/bottom z 0.32（2 層）、接觸面 1 層、`snug`。
- 文件同步：`參數.py` 行尾註解抓到 8 條假數字，已修並上常設檢查 `test_行尾數值註解必須等於實際值`。

### 導出值速查（改文件前先跑 `參數.py` 確認，不要抄別的文件）
```text
front_vent_area()  = 15939 mm²（11 條 × 161.0 × 9.0；前罩 3 條 + 托盤 2 條 ×4 層）
install_depth_mm() = 311.61 mm（後凸 9.00 = 窗框補強 4.0 + 壓條 5.0）
CASE_REAR = −14.67；後牆內面 −12.27 = Fig.4 側視 aperture 平面；I/O 連接器面 −11.30；PCB 後緣 −10.16
I/O 開孔 z 6.51…50.96（雙基準：板面 −3.81 且 standoff 頂 −2.24）
PCIe 全寬開孔頂 135.43；45° 尖頂到 144.88；窗框 z 8.68…151.38；引入楔自 z 4.68（PCIE_FRAME_LEAD 4.0）
PCIe 繫樑 z 144.88…151.38（PCIE_TIE_H 6.5）；盲牙軸 z 148.13，沿 −Y 深 5.20
SUPPORT_THRESHOLD_ANGLE = 30.0（= preset support_threshold_angle，同一個常數）
TOP_HOOK z 178.62…180.12、前伸 3.0（PSU_SLIDE_Y 4.0）
MB_Screw 十字槽 5.6 × 1.8 × 深 1.5；外側料 1.20、槽頂料 0.90
MB 盲牙 深 5.20（旋合 5.00 + 端隙 0.20），孔底留 1.15
碟架承托肩 z 161.52…165.52（肩頂比橫樑底低 0.30）、斜撐底 152.52
  Chassis 段 y 182.04…220.18；前罩段 y 234.48…284.94
RACK_BEAM_Y = (188.34, 226.18, 275.94)；RACK_STOP_Y = 182.04
前罩內壁 1.6 厚、z 25.86…152.22；後牆頂蓋槽 深 1.60、槽背 0.80
AREA_A_CLEARANCE = 76.20；AREA_A_TOP_Z = 86.52；PCIE_CARD_LEN = 190.61
```

## 關鍵限制與踩雷
- **A1 床是最緊的一條**：Chassis 裸件 252.68 × 252.85；地板貼床、0°、`normal(auto)` 代理 254.22 × 254.39，餘量 0.81 mm/邊（門檻 0.75）。代理外脹 = `support_object_xy_distance + support_line_width` 每邊。任何往 −Y 的新凸出或加大 xy 間隙，先跑 `列印擺位.py --best`（R13 鎖點凸台外長 2.5 → 超床；R14 xy 0.45 → 餘量 0.71 不過）。要再加大 xy 得先讓 Chassis 變淺。
- 必須 `no_brim`、brim 0、skirt 0、`raft_first_layer_expansion = 0`；`tree(auto)` 代理 605.92 × 602.89，禁用。
- `.info` 是本機帳號 metadata，不是跨帳號安裝檔；材料沿用 Bambu Generic PETG，溫度與流量由實料校正。
- 不可宣稱「完全相容 microATX」：Area A 76.20 達 Table 6 required，未達 recommended 88.90；`PCIE_CARD_LEN` 190.61 是碟架置中的取捨（仍 > CEM 半長卡 167.65）。
- `PSU_FAN_DOWN = True` 是使用者指定假設（ATX12V Fig.4 未規定）。
- `REMOVED_SHELL_PARTS`／`REMOVED_STL` 與舊 keyhole／楔／`MB_Nut` 名稱字串是防回歸守衛，不是死碼；`SKIRT_H = 0` 也是可執行規格。
- `FreeCADCmd` 收不到中文 argv，一律走 ASCII junction `scripts/`；判斷有沒有真的跑看產物 mtime。
- `腳本/驗切片gcode.py` 有 4 個既有 ruff 警告（未處理）。

## 待辦（使用者驗證；未完成前不得寫成已通過）
| 項目 | 要驗它得做什麼 |
|---|---|
| Bambu Studio 真實切片／真 G-code | 依 `PRINT_PLAN` 切第十四輪 STL，跑 `驗切片gcode.py <gcode>`；R11／R13 G-code 不可沿用 |
| PCIe 開孔與窗框 45° 面是否真的不生支撐 | 看切片預覽；若有支撐先查 preset 的 `support_threshold_angle = 30`，不要硬拆 |
| 加大的脫模間隙好不好拆、下表面會不會塌 | 實印後拆支撐並看下表面 |
| 鉤唇 3.0 後頂蓋後緣壓持力 | 實印試裝 Top |
| 印製十字槽在手緊扭力下的壽命 | 實際鎖主板；削槽就改用六角外緣 |
| 水平盲內牙（`PCIeBar`，牙谷上半會下垂） | 實印後鎖 `MB_Screw` 試旋合 |
| 碟架承托肩下沉量與 PETG 潛變 | 裝滿 4 顆 HDD 長時間量下沉 |
| Top／Front detent 疲勞、實印尺寸、主板 I/O 對齊 | 實印試裝主板與重複拆裝 |
| EMI、熱（只算過開口面積，未量風壓溫升） | 實機運轉量測 |

## 需使用者決定
- 授權：尚未指定 `LICENSE`（目前保留所有權利）。
