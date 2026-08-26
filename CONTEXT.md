# 3DP-MATX 開發交接

全 3D 列印 microATX NAS 機殼。FreeCAD Part 模組 CSG 布林建模；尺寸、BOM 與組裝步驟的唯一來源是 `腳本/參數.py`。先讀本檔，再讀 `CLAUDE.md`；歷輪病灶在 `tasks/lessons.md` 與 `tasks/todo.md`。

## 現況（2026-08-26，第十四輪＋文件同步）

- 外形：**252.68 × 302.61 × 180.12 mm，13.77 L**。
- 8 種 STL；一件一份 `PRINT_VOLUME = 1081.3 cm³`，含數量
  `FILAMENT_VOLUME = 1300.2 cm³ ≈ 1.66 kg PETG`。
- 主機殼是單一 `Chassis_Body`（地板、左右牆、後牆真實融合）。
- Top、Front、HDD Rack、HDD Tray 仍可拆；組裝掃描唯一來源：
  `Chassis_Body → HDD_Rack → Top_MB → Front_Shroud → HDD_Tray`。
- 主板固定：9 個 Ø8 × 6.35 支撐肩內切 5.20 mm 盲內牙，搭配印製 `MB_Screw`。
- PCIe：外置 `PCIeBar`，**2 顆同規格 `MB_Screw` 鎖繫樑上的印製盲內牙**
  （鎖點處有沉頭凹，夾持厚 = `PCB_T`）→ `MB_Screw` 實印 **11 顆**。
- Rack 底部：3 條 12 mm 橫樑 + 1 條 12 mm 中央縱樑，與 lv0 托盤保留 0.30 mm。
- `MB_Screw` 頭頂有 **5.6 × 1.8 × 深 1.5 直邊十字工具槽**（槽在貼床面 ⇒ 第一層的孔，免支撐）。
- 支撐地圖是常設檢查：`verify_case.support_overhangs()` 掃全件的平面朝下面，
  **PCIe 開孔 x 帶內一片都不准有**（FAIL），帶上方逐條 WARN 列 z／面積／塔高。

### 第十四輪改了什麼（使用者第二次回饋三項）

| # | 病灶 | 現況 |
|---|---|---|
| 1 | PCIe 三根 1.42 肋仍被支撐扯斷 | 量出來扯它的**不是開孔的支撐**（R13 尖頂已讓開孔帶一片朝下面都沒有），是 `TOP_HOOK` 鉤唇底面（全寬 248 × 深 6、1487 mm²）從床長上來的 **176 mm 支撐塔**。鉤唇 **6.0 → 3.0**（懸空 −743 mm²），窗框底緣加 **45° 引入楔**（−359 mm²），開孔帶內歸零並上常設 FAIL 檢查 |
| 2 | 螺絲頭要有十字孔才轉得動 | `MB_Screw` 頭頂加 **5.6 × 1.8 × 深 1.5 直邊十字**；槽開在**貼床面** ⇒ 第一層的孔、不需支撐；直邊不 cam-out。六角外緣保留 |
| 3 | 支撐難拆／表面粗糙 | preset 的脫模間隙本來**比 Bambu 原廠還緊**：xy `0.2`（原廠 0.35）、接觸面 `0` 層、繼承的 top/bottom z 只有 `0.16`（＝一層）。改為 xy **0.35**、z **0.32**（2 層）、接觸面 **1** 層、`snug`。**xy 上限被 A1 床卡死**：開到 0.45 佔床 254.59、餘量 0.71 < 0.75 門檻 |

### 文件同步（2026-08-26）

- 全部 `.md` 對 `腳本/參數.py` 重新校過一次；`README.md` 重寫。
- **`參數.py` 的行尾註解抓到 8 條假數字**（`CASE_D # 301.00`、`ATX_Y0 # −10.66`、
  `ATX_FRONT_Y # 129.34`、`PCIE_CARD_LEN # 189.00`、`AREA_A_TOP_Z # 99.22`、
  `PSU_CLEAR_ABOVE # 1.30`、`PSU_SLIDE_Y # 7.0` …）——全部是第十／十三／十四輪
  改上游時漏掉的。幾何沒錯，但下一輪會照著假數字讀。
  常設檢查：`test_行尾數值註解必須等於實際值` + 一條非空證明（吋 literal 不得誤報）。
- 連帶修掉的文件病灶：`設計規格.md` 還寫「碟架吊在側板槽上」（第十三輪已改承托肩）、
  `PCIeBar` 還寫 `2× #6-32`、`MB_Screw` 還寫 9 顆、走線帶還用 `129.34 / 149.34`、
  §9 狀態還停在 R12／66 條；`CLAUDE.md`／`AGENTS.md` 的 A1 餘量還是 `0.96 mm/邊`。

### 第十三輪改了什麼（使用者實印回饋五項）

| # | 病灶 | 現況 |
|---|---|---|
| 1 | 碟架吊在 4 × 0.90 mm 咬合上（43 mm²），前段 49.76 mm 純懸臂 | 左右牆內面長 **`RACK_LEDGE`** 承托肩（伸出 8.0、45° 斜撐自撐），前罩接力一段肩，碟架加**第三根橫樑**坐上去 → 承重 576 mm²、懸臂 8.00 mm |
| 2 | **I/O 深度基準錯 1.61 mm**（真缺陷） | `CASE_REAR = −(IO_APERTURE_FROM_B + WALL) = −14.67`，後牆內面 −12.27 = Fig.4 側視的 aperture 平面 |
| 3 | PCIe 四槽要支撐，拆時扯斷 1.42 肋；壓條沒用 | 開孔頂改 **45° 尖頂**（切片器不生支撐）；壓條鎖點 #6-32 自攻 → **印製盲內牙** |
| 4 | 後牆只有鉤唇，沒有 −Y 止擋 | 後牆補與側槽同 z 帶的**頂蓋槽**（分兩段讓開電源與碟架頂板） |
| 5 | 前罩只有單邊搭接 | 搭接帶改 **U 形雙壁夾持**（外壁 1.2 + 內壁 1.6，中間夾牆 2.4） |

## 列印計畫

唯一來源：`腳本/列印擺位.py::PRINT_PLAN`。支撐狀態由所引用 preset 的
`enable_support` 導出。

| 件 | 姿態／旋轉 | Process preset |
|---|---|---|
| Chassis | Z+／0° | 機殼件 0.16 支撐 |
| Top | Z−／0° | 機殼件 0.16 支撐 |
| Front | Y−／0° | 機殼件 0.16 無支撐 |
| HDD Rack | Z−／45° | 機殼件 0.16 支撐 |
| HDD Tray | Z+／0° | 機殼件 0.16 支撐 |
| PCIeBlank | Z+／0° | 機殼件 0.16 無支撐 |
| PCIeBar | Y+／0° | 機殼件 0.16 無支撐 |
| MB_Screw（×11） | Z+／0° | 主板螺絲 0.12 |

三份 repo preset：

- `3DP-MATX 機殼件 0.16 支撐`
- `3DP-MATX 機殼件 0.16 無支撐`
- `3DP-MATX 主板螺絲 0.12`

`驗切片設定.py` 會驗 plan／manifest、JSON／info 配對、basename/name/id、DLL key/enum
與關鍵值。`.info` 是本機帳號 metadata，不是跨帳號通用安裝檔。材料沿用 Bambu
Generic PETG；品牌溫度與流量由實料校正。

### A1 判定

- Chassis 裸件：**252.68 × 252.85 × 180.12 mm**（第十三輪 Y 深 +1.61，見 I/O 基準修正）。
- 地板貼床、盤上 0°、`normal(auto)`：**254.22 × 254.39 mm**，最小餘量
  **0.81 mm/邊**，通過腳本門檻 0.75 —— **這是本專案最緊的一條，任何往 −Y 的
  新凸出、或任何加大 `support_object_xy_distance` 的念頭，都要先跑
  `列印擺位.py --best` 確認**（第十三輪一度把鎖點凸台往外長 2.5，裸深立刻 255.4、
  加支撐直接超床；第十四輪一度把 xy 開到 0.45，佔床 254.59、餘量 0.71 不過）。
  代理外脹 = `support_object_xy_distance + support_line_width` **每邊**。
- 必須 `no_brim`、brim 0、skirt 0、`raft_first_layer_expansion = 0`。
- `tree(auto)` 代理 footprint 605.92 × 602.89，禁止使用。
- **Bambu Studio 真實切片與真 G-code 由使用者驗證；目前不得寫成已通過。**

## 本輪驗證（第十四輪實際輸出）

```text
ruff check --ignore E402 <本輪修改檔>          → All checks passed
python -m unittest 測試/test_參數.py            → Ran 71 tests / OK（+6 第十四輪、+2 註解真實性）
FreeCADCmd -c ...\scripts\_run_build.py         → BUILD_OK / 8 STL / 1081.3 / 1300.2 cm³
FreeCADCmd -c ...\scripts\_run_verify.py        → RESULT: ALL CHECKS PASSED
FreeCADCmd -c ...\scripts\_run_negtest.py       → NEGTEST 86/86 / NEGTEST_OK
python 腳本\列印擺位.py --best                 → 8 種／FILAMENT 1300.2 cm³／Chassis 0.81 mm/邊
python 腳本\驗切片設定.py                       → FAILURES = 0
python 腳本\渲染預覽.py／組裝圖.py              → 四視角＋爆炸＋5 步＋8 特寫；目視通過
FreeCAD GUI reload 最新 FCStd                  → 8 objects；逐件 1 Solid/valid/closed；
                                                  SUM 1081.3 cm³；四視角已看
Bambu Studio 真切片／真 G-code                → 使用者待驗證
```

`腳本/驗切片gcode.py` 有 4 個既有 ruff 警告（本輪未動該檔）。

## 導出值速查（改文件前先跑一次，不要抄別的文件）

```text
python -c "import sys;sys.path.insert(0,'腳本');import 參數 as D;print(D.front_vent_area())"
front_vent_area()  = 15939 mm²   （11 條 × 161.0 × 9.0；前罩 3 條 + 托盤 2 條 ×4 層）
install_depth_mm() = 311.61 mm   （後凸 9.00 = 窗框補強 4.0 + 壓條 5.0；螺絲頭已沉頭）
CASE_REAR          = −14.67，後牆內面 −12.27 = Fig.4 側視 `0.483 [12.27]` aperture 平面
I/O 連接器面        = −11.30（Fig.5 note），留 0.97 給 shield；PCB 後緣 −10.16
I/O 開孔           = z 6.51…50.96（雙基準：板面 −3.81 且 standoff 頂 −2.24）
PCIe 全寬開孔頂     = 135.43（＝擋板抬到頂）；45° 尖頂到 144.88
PCIe 窗框            = z 8.68…151.38；底緣 45° 引入楔自 z 4.68 起（PCIE_FRAME_LEAD = 4.0）
SUPPORT_THRESHOLD_ANGLE = 30.0（＝ preset support_threshold_angle，兩邊同一個常數）
TOP_HOOK             = z 178.62…180.12、前伸 3.0（PSU_SLIDE_Y = 4.0）
MB_Screw 十字槽      = 5.6 × 1.8 × 深 1.5；外側料 1.20、槽頂料 0.90
PCIe 繫樑          = z 144.88…151.38（PCIE_TIE_H 6.5）；盲牙軸 z=148.13，孔沿 −Y 深 5.20
碟架承托肩          = z 161.52…165.52（肩頂比橫樑底低 0.30）、斜撐底 152.52
                     Chassis 段 y 182.04…220.18；前罩段 y 234.48…284.94
RACK_BEAM_Y        = (188.34, 226.18, 275.94)，後兩根之外第三根在前罩段（無側舌）
前罩內壁            = 1.6 厚、z 25.86…152.22（上限讓開斜撐底，下限讓開 Area B 淨空）
後牆頂蓋槽          = 深 1.60、槽背 0.80；x 兩段 (−214.39…−211.69)、(5.65…36.09)
RACK_STOP_Y        = 182.04    AREA_A_CLEARANCE = 76.20    AREA_A_TOP_Z = 86.52
MB 盲牙            = 深 5.20（旋合 5.00 + 端隙 0.20），孔底留 1.15
PCIE_CARD_LEN      = 190.61
```

## 重要限制

1. `AREA_A_CLEARANCE = 76.20` 達 microATX Table 6 required，但低於 recommended 88.90；
   不可宣稱「完全相容 microATX」。
2. `PCIE_CARD_LEN = 190.61` 是碟架置中後的取捨；仍大於 CEM 半長卡 167.65。
3. `PSU_FAN_DOWN = True` 是使用者指定假設；ATX12V Fig.4 沒有規定大面風扇方向。
4. **支撐 xy 間隙的上限是床，不是材料**：`列印擺位.py` 的普通支撐代理外脹
   `support_object_xy_distance + support_line_width` 每邊，Chassis 裸深 252.85 →
   xy 只能開到 0.35（餘量 0.81/邊）。要再加大得先讓 Chassis 變淺。
5. 真實切片、支撐可拆性（特別是 **PCIe 開孔／窗框的 45° 面是否真的不生支撐**、
   **加大的脫模間隙好不好拆、下表面會不會塌**）、**印製十字槽在手緊扭力下的壽命**、
   實印尺寸、MB Screw 強度／手感、**壓條盲內牙（軸沿 −Y ⇒ 水平孔，牙谷上半會下垂）**、
   Top／Front detent 疲勞、**碟架承托肩的實際下沉量與 PETG 潛變**、EMI 與熱皆未驗證。
6. `REMOVED_SHELL_PARTS`／`REMOVED_STL` 與舊 keyhole／楔／`MB_Nut` 名稱字串是
   防回歸守衛，不是死碼；`SKIRT_H = 0` 也是可執行規格。

## 檔案地圖

```text
腳本/參數.py            尺寸、8 件 manifest、份數、組裝步驟
腳本/build_case.py      Part CSG 建模與 STL/FCStd 輸出
腳本/verify_case.py     規格、幾何、硬體包絡、動作、保持力
腳本/_run_negtest.py    86 條非 vacuous 負向測試
腳本/列印擺位.py        PRINT_PLAN、六軸擺位、支撐 footprint、料量
腳本/驗切片設定.py      preset 靜態交付守門
腳本/渲染預覽.py         四視角 PNG
腳本/組裝圖.py           爆炸、逐步 ×5、卡榫特寫 ×8
測試/test_參數.py        71 條回歸
文件/                    組裝、列印參數
規格/                    尺寸、規範、孔位、裁決與圖
```

## 建模／驗證指令

`FreeCADCmd` 不能接中文 argv，必須走 repo 根目錄的 ASCII junction `scripts/`：

```text
FreeCADCmd -c <root>\scripts\_run_build.py
FreeCADCmd -c <root>\scripts\_run_verify.py
FreeCADCmd -c <root>\scripts\_run_negtest.py
python -m unittest 測試/test_參數.py
python 腳本\列印擺位.py --best
python 腳本\驗切片設定.py
python 腳本\渲染預覽.py
python 腳本\組裝圖.py
```

最後必須在 FreeCAD GUI 重載同一路徑 `CAD/機殼總成.FCStd`：確認 8 物件、逐件
`Solids=1/isValid/isClosed/Volume`，檢視 Isometric／Rear／Top／Left。headless 渲染是退路，
不是 GUI 目視的替代品。
