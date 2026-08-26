# 第十一輪：保持力真相表／後牆單向卡榫／碟架止擋／組裝說明圖（2026-08-16）

使用者：「我仍然看不出這機殼要怎麼組裝在一起，你確定有做好嗎？就像頂蓋那樣可以卡住。」

動手前先量（`scratchpad\_dbg_hold.py`、`_dbg_geo.py`、`_dbg_wedge.py`，用完即刪）。

## 一、量出來的事實

把每個機殼件往六個方向推，看它撞到別人之前能自由走多遠（detent 先扣掉，
才分得出「幾何鎖住」與「只靠 snap」）：

| 件 | +X | −X | +Y | −Y | +Z | −Z | 判定 |
|---|---|---|---|---|---|---|---|
| Bottom_Tray | 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 六向全鎖 |
| Side_L / Side_R | 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 六向全鎖 |
| **Rear_IO_PCIe** | 0.35 | 0.35 | 0.35 | **自由 >12** | 0.35 | 0.35 | **缺陷** |
| **HDD_Rack** | 0.35 | 0.35 | 0.35 | **6.00**（實際浮 3.00） | 0.35 | 0.35 | **缺陷** |
| Top_MB | 0.35 | 0.35 | 0.35 | 0.75 | 0.35 | 0.35 | 六向全鎖 |
| Front_Shroud | 0.35 | 0.35 | 自由 >12 | 0.35 | 0.75 | 0.35 | 釋放方向（設計如此） |
| HDD_Tray | 0.35 | 0.35 | 自由 >12 | 0.35 | 0.35 | 0.35 | 熱插拔（設計如此） |

- **碟架浮 3.00**：側板的碟架槽後端開到 `TRAY_Y0 − 1.0 = 179.34`，
  而最後那條側舌的後緣在 182.34 → 中間 3 mm 沒有止擋面。
  碟浮、托盤前緣跟著浮，前罩開口就對不齊。
- **後牆 −Y 完全自由**：八顆半球是唯一的阻力，而**半球受拉會自己爬出來**。
  後牆正是 AC 線、I/O 線、PCIe 卡拔插時受 −Y 力最多的那一面。
- **為什麼十輪沒抓到**：`interference` 問「有沒有重疊」、`裝配動作` 問「進得來嗎」、
  `卡榫盤點` 問「公件實心／母件讓開」。**沒有一條在問「出得去嗎」。**
- **「看不出來」有一半是圖的問題**：1.30 的咬合畫在 252×301×180 上不到一個像素。

## 二、做了什麼

- [x] `RACK_STOP_Y = min(RACK_BEAM_Y) − RACK_BEAM_W/2 − SLIDE_FIT` = 182.04，
      側板碟架槽改盲端（硬規則 9：同一條界線由同一個來源導出）→ 浮 3.00 → **0.30**
- [x] 後牆六顆半球 → **不對稱單向楔**：斜坡 1.5（21.8°）+ 平台 0.8 + 直角面 0.6×5.0
      - 公件（楔）長在側板口袋底、裁到機殼外表面（外表面保持是平的）
      - 母件改成**自舌根往前開的缺口**，不是舌中間挖孔
        （開中間的話直角面前只剩 0.45 mm 細肉，一拉就掰斷）
      - 底板後舌那兩顆**維持半球**＝拆卸路徑（全單向就永遠拆不下來）
- [x] verify 新增 `--- 保持力真相表（六向約束）---`：8 件 ×6 向，
      `HOLD_RELEASE` 宣告釋放方向，清單從 `STRUCT_PART_KEYS` 展開、漏件 `SystemExit`
- [x] verify 新增「楔上必須有法線平行 Y 的直角面 ≥2.40 mm²」+ 缺口前後的實心／空探點
- [x] negtest 51 → **97 條**（新增 #40–42：半球找不到直角面、削掉楔就走得掉、
      削掉楔之後 `no interfere` 照樣綠、碟架盲端回到 179.34 就浮 3 mm）
- [x] `測試/test_參數.py` 54 → **56 tests**（單向楔的幾何約束、碟架止擋由側舌導出）
- [x] 新增 `腳本/組裝圖.py`：爆炸圖 + 逐步圖 ×8 + **卡榫剖面特寫 ×7** → `規格/組裝_*.png`
- [x] `渲染預覽.render` 加 `focus=`（取景框）與 CJK 字型（找不到就 `SystemExit`）
- [x] 文件：`CLAUDE.md`／`AGENTS.md`（硬規則 24、25）、`CONTEXT.md`、
      `文件/零件清單與組裝.md`（新增「圖」與「保持力」兩節）、`tasks/lessons.md` 53–55

## 三、驗證（實際輸出）

```text
FreeCADCmd -c …\scripts\_run_build.py  → ENVELOPE 252.7 x 301.0 x 180.1 /
                                          PRINT_VOLUME 1032.1 cm3 / BUILD_OK      exit 0
FreeCADCmd -c …\scripts\_run_verify.py → volume=13.70 L / ALL CHECKS PASSED       exit 0
   保持力真相表：48 個方向 → 46 鎖住 + 2 個宣告的釋放方向（前罩 +Y、碟托盤 +Y）
   Rear_IO_PCIe −Y 被 Side_Right_MB 鎖住（第十輪：自由 >12）
   HDD_Rack     −Y 被 Side_Left_MB  鎖住（第十輪：浮 3.00）
   WARN ×6（Area A required／風扇朝向是假設／PCIe 卡長 189／A1 床邊裕度 ×3）
FreeCADCmd -c …\scripts\_run_negtest.py→ NEGTEST 97/97 / NEGTEST_OK               exit 0
python -m unittest 測試/test_參數.py     → Ran 56 tests OK
python 腳本\組裝圖.py                    → 規格/組裝_*.png ×16
FreeCAD GUI 目視複檢（硬規則 18）        → 見下
```

## 四、回顧

**尺寸／體積／零件數都沒有變**（252.68 × 301.00 × 180.12、13.70 L、1032 cm³、11 件）。
這一輪動的全是「裝得住嗎」與「看得懂嗎」。

三件值得記住的（已寫進 `tasks/lessons.md` 53–55）：

1. **三個綠燈加起來仍然不等於「裝得住」。** 每條檢查都只問了半個問題，
   合起來還是漏掉「出得去嗎」。
2. **半球是摩擦力不是保持力。** 純滑動接合的公母進出走同一道邊 →
   不對稱只能做在公件上；而且缺口要自舌根往前開，前緣後面必須是整片料。
3. **「看不出來」可能是圖的問題。** 剖面不能用重心篩三角形（大三角形會整片擋鏡頭）、
   正對剖面看等於看空氣（STL 是殼）、PIL 沒有 CJK 字型。

## 五、仍然沒驗（不得寫成已驗證）

- 實印與試裝：0.30/邊滑配、**單向楔的實際保持力與插入力**、10 顆前罩 detent、
  4 顆底板 bead、keyhole 手感、三段榫的鬆緊 —— 全是紙上的
- **單向楔的疲勞**：拆裝幾次之後直角面會不會被磨圓，沒有測過
- 熱：風壓與溫升沒量過（層間 1.5 是裝配間隙不是散熱設計）
- 碟架懸掛與 PCIe 窗框的實際剛度（只算慣性矩，沒有 FEM）
- PSU 大面風扇朝向：規格沒寫 → `PSU_FAN_DOWN = True` 是依使用者指定的假設

---

# 第十一輪補篇：料量算錯 20% ／ 列印擺位（2026-08-16）

使用者：「計算現在的機殼體積，然後 Bambu A1 的列印參數用預設的就好嗎？
支撐要開，除此之外還有什麼？」

## 一、量出來的事實

- **外形體積 13.70 L** 沒變（252.68 × 301.00 × 180.12）。
- **料量一直是錯的**：`PRINT_VOLUME` 逐件加總、沒乘份數，而總成裡每個 STL
  只放一份 → 少算碟托盤 ×3、壓帽 ×8、槽蓋 ×3 = **219 cm³（20%）**。
  照文件的 1032 cm³（1.29 kg）去買料會**短缺一整捲**。
- 逐件量六個軸向擺法的懸空／床接觸（`腳本/列印擺位.py`）：
  - **前罩 1.0 mm²、PCIe 槽蓋 0.0、壓條 7.2、壓帽 15.6（全是牙的下側）**
    → 這四件**開支撐就是毀件**，「支撐全開」是錯的。
  - **側板外表面朝下 1954 vs 內表面朝下 43695 mm²（22 倍）**，
    機制＝左側板內面的電源承托肩 `PSU_LEDGE_W = 12.0` 把整片板架高 12 mm。
- 對照 Bambu 預設 `0.20mm Standard @BBL A1`（解析繼承鏈）：
  `wall_loops = 2`（0.87/邊 ×2 = 1.74）、`detect_thin_wall = 0`、`wall_generator = classic`
  → **2.40 的牆中間 0.66 是 15% grid 填充＝空心**，滑槽／定位舌／單向楔全長在那道牆上。
  `brim_width = 5` 也放不下（`CASE_W = 252.68`，A1 床 256 → 單邊 1.66）。

## 二、做了什麼

- [x] `參數.PART_QTY`：份數由既有常數導出（`TRAY_COUNT`／`MB_NUT_COUNT`／`PCIE_COUNT`），
      對 `STL_NAMES` 集合比對、漏件 `SystemExit`
- [x] `build_case` 改印**兩個**數字：`PRINT_VOLUME`（一件一份 1032.1）
      與 `FILAMENT_VOLUME`（含份數 **1251.3 cm³ ≈ 1602 g**）
- [x] 新增 `腳本/列印擺位.py`：六個軸向擺法 × 懸空／床接觸／放不放得下，
      內建 `_assert_rotations()`（det=+1 守衛）與 `RECOMMENDED` 漏件守衛
- [x] 新增 `文件/列印參數與擺位.md`：料量、逐件擺位表、必改的 7 個切片參數、
      建議調的 3 個、批次紀律、印完先驗哪三件
- [x] `測試/test_參數.py` 56 → **58 tests**（份數表涵蓋且由常數導出、5 mm brim 放不下）
- [x] 文件：`CLAUDE.md`／`AGENTS.md`（硬規則 26、27）、`CONTEXT.md`、
      `規格/設計規格.md`、`文件/零件清單與組裝.md`、`tasks/lessons.md` 56–57

## 三、驗證（實際輸出）

```text
FreeCADCmd -c …\scripts\_run_build.py  → PRINT_VOLUME 1032.1 cm3 (一件一份)
                                          FILAMENT_VOLUME 1251.3 cm3 (含份數)
                                          ENVELOPE 252.7 x 301.0 x 180.1 / BUILD_OK   exit 0
python -m unittest 測試/test_參數.py     → Ran 58 tests OK
python 腳本\列印擺位.py --best           → 11 件全 OK（放得進 256³），FILAMENT 1251.3
FreeCADCmd -c …\scripts\_run_verify.py → 見下
FreeCADCmd -c …\scripts\_run_negtest.py→ 見下
```

## 四、回顧

幾何**一個字都沒動**（13.70 L、11 件、外形不變）。這一輪動的全是
「印出來要花多少料」與「印的時候該怎麼擺」——**兩件十一輪都沒有人算過的事**。

最值得記住的：**這個 20% 的錯誤每一項都是對的**（每件體積正確、`STL_NAMES` 完整、
`TRAY_COUNT = 4` 的註解就寫在旁邊），只是那個常數從來沒有被加總引用。
硬規則 15 的變體：參數不只會「定義了沒被引用」，還會
**「被引用在別的地方、卻沒被引用在最需要它的那個式子裡」**。

## 五、仍然沒驗

- 上述所有切片參數都是**照幾何推的**，一片都還沒印過。
- `0.16` 層高對 detent／單向楔的實際改善、`arachne` 對 0.8/1.2 薄牆的實際填充，
  都要印了才知道。文件第七節那三件小試片就是為此排的。

---

# 第十二輪：實印驗收修正（2026-08-25）

使用者實印後要求：主機板段四件合一、碟架底部補強、頂蓋／前罩更可靠、主板改盲內牙＋
專用印製螺絲、PCIe 壓條改成外側螺絲固定；動手前先證明一體件能放進 Bambu Lab A1。

## A1 判定與責任邊界

- 舊 keyhole 蘑菇柱保留時：一體件裸框 `252.68 × 255.24 × 180.12 mm`，
  `normal(auto)` 支撐代理 Y=256.48，**超床**。
- 刪除 keyhole 後，新 `Chassis_Body` 裸件實測 `252.68 × 251.24 × 180.12 mm`；
  底面朝床、盤上 0°、`normal(auto)` 支撐 footprint `253.92 × 252.48 mm`，
  最小餘量 `1.04 mm/邊`，通過本專案 `0.75 mm/邊` 腳本門檻。
- **Claude 本輪負責**：列印計畫、process presets、靜態設定驗證、舊參數語意清理、
  build／verify／negtest／GUI／文件。
- **使用者負責**：Bambu Studio 真實切片、真 G-code、實印與試裝；未完成前一律標為
  「第十二輪使用者待驗證」，不沿用第十一輪 G-code 當證據。

## 已實作幾何

- [x] 參數／manifest：8 種 STL、份數、5 步組裝、退役件與新導出尺寸。
- [x] `Chassis_Body`：底板、左右牆、後牆真實融合；刪除四件之間的舊滑槽／舌／楔／keyhole。
- [x] `HDD_Rack`：三條底部橫樑＋中央縱樑，保留 lv0 托盤 0.30 mm 間隙。
- [x] Top／Front：Top 後鉤 detent；Front 14 mm 搭接與 1 mm 導入面，仍可拆。
- [x] 主板：保留 Ø8 × 6.35 肩，改 5 mm 盲內牙；新增 8 mm AF 六角頭 `MB_Screw`。
- [x] PCIe：兩個外伸盲孔座＋5 mm `PCIeBar`＋2× #6-32×3/8 in 外側螺絲。
- [x] 非 vacuous verify／negtest／參數回歸測試已重構為第十二輪資料流。

## 本輪待辦：列印參數與舊參數清理

- [x] 建立 `PRINT_PLAN`：8 件的 preset／姿態／盤上旋轉單一來源，支撐狀態由 preset 導出。
- [x] 將「螺紋壓帽 0.12」preset 改名為「主板螺絲 0.12」，同步 repo 與本機 Bambu profile。
- [x] `驗切片設定.py` 驗 plan／manifest／JSON／info／名稱／關鍵值雙向一致。
- [x] 清理死碼與舊語意：只刪 `bore_x()`、移除 Chassis 舊四件別名、修正參數註解與 Rack rail 測試。
- [x] 重跑 `python-reviewer`、compile、58 tests、build、verify、66 negtests、擺位與 preset 驗證。
- [x] 重畫預覽／5 步組裝圖；四個 PCIeBlank 在 PNG 槽位，Rack 格柵特寫不再被托盤遮住。
- [x] README／規格／文件／`CLAUDE.md == AGENTS.md`／`CONTEXT.md` 同步。
- [x] FreeCAD GUI 重載最新版，核對 8 件與 Isometric／Rear／Top／Left 四視角。
- [x] `git diff --check` 與本節回顧填入本次實際輸出。

## 使用者待驗證

- [ ] Bambu Studio 依 `PRINT_PLAN` 對第十二輪 STL 真實切片。
- [ ] 真 G-code 擠出路徑、支撐可拆性、實印尺寸、螺牙、卡榫、Rack 剛度與試裝。

## 回顧（實際輸出）

```text
python -m py_compile ...                       → PASS
python -m unittest 測試/test_參數.py            → Ran 58 tests / OK
FreeCADCmd -c …\scripts\_run_build.py          → BUILD_OK / 8 STL /
                                                  PRINT 1055.3 / FILAMENT 1274.1 cm³
FreeCADCmd -c …\scripts\_run_verify.py         → RESULT: ALL CHECKS PASSED
FreeCADCmd -c …\scripts\_run_negtest.py        → NEGTEST 66/66 / NEGTEST_OK
python 腳本\列印擺位.py --best                 → 8 種；Chassis 253.92×252.48，1.04 mm/邊
python 腳本\驗切片設定.py                       → FAILURES = 0
python 腳本\渲染預覽.py／組裝圖.py              → 四視角＋爆炸＋5 步＋7 特寫；目視通過
ruff check --ignore E402 <修改檔>               → All checks passed
FreeCAD GUI                                    → 最新 FCStd、8 objects、逐件 1 Solid/valid/closed；
                                                  Isometric／Rear／Top／Left 已看
CLAUDE.md == AGENTS.md                         → git diff --no-index exit 0
git diff --check                              → PASS
Bambu Studio 真實切片／真 G-code              → 使用者待驗證
```

第十二輪把「列印設定」收斂成 `PRINT_PLAN → preset JSON → 靜態 validator` 一條資料流，
並清掉四件式 Chassis、MB_Nut 與 keyhole 的現況語意；退役名稱只留在負向守衛與歷史。
組裝圖審查另抓到基準件被畫成沿 −Z 裝入、Rack／Front 示意位移未標、剖面缺字與視角遮蔽，
均已修正並由 `python-reviewer` 複查為無 findings。

文件同步時另抓到兩組「文件沒跟著參數走」（教訓 65）：
- 前柵面積四份文件寫 13976，`front_vent_area()` 實際是 **15939**（11 條 × 161.0 × 9.0）；
  已全部改回導出值，包含 `CLAUDE.md`／`AGENTS.md`。
- PCIe 開孔與繫樑殘留舊值；現況是開孔 z 16.68…135.43（高 118.75 = 本體 112.75 +
  `PCIE_LIFT` 6.00）、繫樑 `PCIE_TIE_H` 6.0（z 135.43…141.43）、鎖座 z 136.43…146.43。

# 第十三輪：實印五項回饋（2026-08-25）

使用者實印第十二輪後回報五項。查證結果：**第 2 項是規格基準讀錯（真缺陷）**，
其餘四項是接合強度或列印性。前罩與碟架的整體設計不變，改的是接合方式。

## 一、量出來的事實

- **I/O 深度基準錯 1.61 mm。** microATX Fig.4 有兩張圖，前十二輪只用了正視圖。
  側視圖 `0.483±.010 [12.27±0.25]` = Datum B → I/O aperture 平面；
  Fig.5 note `.445±.008 [11.30±0.2]` = Datum B → I/O 連接器的**面**（比 PCB 後緣
  10.16 還往後突出 1.14）。舊式 `CASE_REAR = BOARD_REAR − MARGIN − WALL` 讓後牆內面
  落在 **−10.66**，連接器面 −11.30 **戳進牆 0.64 mm** → 主板推不到底。
  Z 反而一直是對的：側視圖另一條 `.088 [2.24]`（自板底／standoff 頂）
  與 `IO_Z0 = 6.51 = 8.75 − 2.24` 完全吻合。
- **碟架承重面積只有 43 mm²。** 4 條橫樑末端各咬合 `RACK_RAIL_T − SLIDE_FIT = 0.90`，
  吊住 4 顆碟（≈2.8 kg）+ 碟架；牆厚 2.4 被 `GROOVE_BACK_MIN` 卡死，槽不能再深。
  而且碟架到 283.94、Chassis 只到 234.18 → **前段 49.76 mm 是純懸臂**。
- **PCIe 四個開孔需要支撐。** 開孔頂 z=135.43 是 18.9 mm 寬水平懸空，切片器在四個
  118 mm 深的槽裡長支撐塔，塔與 1.42 mm 的肋咬死 → 拆的時候把肋一起扯斷。
- **後牆對頂蓋只有鉤唇。** 唇擋 +Z，−Y 那一格靠兩顆 detent 的摩擦，沒有止擋面。
- **前罩搭接帶只有外壁。** `SHROUD_LAP_T` 薄殼貼在牆的外面減薄帶上，內面整片是光的。

## 二、做了什麼

- [x] `CASE_REAR = −(IO_APERTURE_FROM_B + WALL)`；新增 12.27／11.30／2.24 三個
      literal 與 **I/O 連接器區虛擬件**（硬規則 21）。CASE_D 301.00 → 302.61。
- [x] 碟架承托肩：牆內面伸出 8 mm 承重面 + 45° 斜撐（自撐），肩頂比橫樑底低
      一個 SLIDE_FIT；前罩接力一段肩，碟架加第三根橫樑坐上去。
- [x] PCIe 開孔頂改 **45° 尖頂**（切片器不生支撐），繫樑上移到尖頂之上；
      機殼高度不變（`INNER_TOP_Z` 仍 177.12）。
- [x] 壓條鎖點：#6-32 自攻 → **印製盲內牙 + 沿用 MB_Screw**（鎖點處挖沉頭凹，
      夾持厚 = PCB_T）。`PART_QTY["MB_Screw"] = 9 + 2 = 11`。
- [x] 後牆補與側槽同 z 帶的頂蓋槽；後舌分兩段讓開電源與碟架頂板（硬規則 22）。
- [x] 前罩搭接帶改 **U 形雙壁夾持**，內壁接合塊接回主體壁。

## 三、使用者待驗證（不得寫成已驗證）

- [ ] Bambu Studio 真實切片與真 G-code
- [ ] 實印：支撐可拆性（PCIe 尖頂是否真的不生支撐）、承托肩承重、盲內牙扭力
- [ ] 主板實裝：I/O 連接器與開孔是否對齊（本輪修的就是這一條）

## 四、驗證（實際輸出）

```text
ruff check --ignore E402 <本輪修改檔>          → All checks passed
python -m unittest 測試/test_參數.py            → Ran 63 tests / OK
FreeCADCmd -c …\scripts\_run_build.py          → BUILD_OK / 8 STL / 1080.4 / 1299.5 cm³
FreeCADCmd -c …\scripts\_run_verify.py         → RESULT: ALL CHECKS PASSED
FreeCADCmd -c …\scripts\_run_negtest.py        → NEGTEST 80/80 / NEGTEST_OK
python 腳本\列印擺位.py --best                 → Chassis 253.92×254.09，0.96 mm/邊
python 腳本\驗切片設定.py                       → FAILURES = 0
python 腳本\渲染預覽.py／組裝圖.py              → 四視角＋爆炸＋5 步＋8 特寫
FreeCAD GUI reload                             → 8 objects、逐件 1 Solid/valid/closed、SUM 1080.4
CLAUDE.md == AGENTS.md                         → git diff --no-index exit 0
```

## 五、回顧

三件事值得記住：

1. **A1 的 0.96 mm/邊是設計約束，不是報表數字。** 壓條鎖點原本要做成軸沿 +Z 的
   垂直盲牙（列印品質好得多），為此需要一個往 −Y 凸 2.5 mm 的凸台 —— 一 build
   Chassis 裸深就從 252.9 變 255.4，加支撐直接超床。最後改回軸沿 −Y 的水平盲牙：
   **保持力靠「孔裡真的有牙」而不是靠列印方向**，機殼尺寸不為一個鎖點被撐爆。
2. **「加了一個特徵」要問「它會被誰掃到」。** 頂蓋後舌第一版做成整條寬度，
   `--- 裝配動作 ---` 立刻紅：滑入途中掃過碟架頂板 20424 mm³、掃過電源 294 mm³。
   最終位置全都合法，是**路徑**不合法（硬規則 22）。
3. **探點放錯位置的檢查是空的。** negtest 的尖頂探點第一版放在開孔中線上 ——
   那裡在任何高度都還是開孔（空的），所以「現況有料」永遠 MISS。
   有料的是收斂線**之外**。這種錯誤只有負向測試會抓到。


# 第十四輪：支撐塔的路徑／螺絲十字槽／脫模參數（2026-08-25）

使用者第二次回報同一件事：「PCIe 擋板那邊的問題一樣沒有解決……列印的時候因為有
支撐件，PCIe 那邊中間三條細細的很容易被扯斷」，外加「主機板的螺絲上面要有十字的孔」
與「支撐件有時候有點難拆，或是會讓表面變得有點粗糙，這能不能透過調參來解決」。

## 一、量出來的事實

把 Chassis 的 59076 個三角形全掃一次，取「法線朝下且斜率 < 30°（＝ preset 的
`support_threshold_angle`）」的面，依 z 分群：

| z | 朝下面積 | 是什麼 | 支撐塔高 | 蓋到 PCIe 開孔 x 帶？ |
|---:|---:|---|---:|---|
| 178.62 | **1487 mm²** | `TOP_HOOK` 鉤唇底（全寬 248 × 深 6） | **176 mm** | **是** |
| 86.52 | 3336 mm² | PSU 承托肩底（＝ Area A 淨空頂） | 86 mm | 否（x ≤ −60.9） |
| 177.42 | 844 mm² | 頂蓋側槽／後槽的槽頂（深 1.6） | 177 mm | 是 |
| 165.67 | 313 mm² | PSU 後窗頂 | 66 mm | 否（x ≤ −70.7） |
| 8.68 | **359 mm²** | PCIe 窗框底緣（往 −Y 凸 4.0） | 8.7 mm | **是** |
| 50.96 / 53.50 | 385 mm² | I/O 開孔頂 + keepout 減薄帶頂 | 51 mm | 否（x ≤ −50.7） |

**四個 PCIe 開孔本身一片朝下面都沒有** —— 第十三輪的 45° 尖頂是有效的。
扯斷肋的是**別人的塔**：鉤唇底面要一根 176 mm 的塔貼著後牆內面長上來，
而那一面正是三根 1.42 mm 肋的內側。

preset 又剛好把它焊死：

| 參數 | 第十三輪 | Bambu 原廠 | 效果 |
|---|---|---|---|
| `support_object_xy_distance` | **0.2** | 0.35 | 側面間隙不到原廠的六成 |
| `support_top/bottom_z_distance` | 0.16（繼承） | — | ＝ 一個層高，PETG 直接焊住 |
| `support_interface_top_layers` | **0** | 2 | 下表面只被 2.5 mm 間距的線撐著 → 粗糙 |

## 二、做了什麼

- [x] 鉤唇 `TOP_HOOK_D` **6.0 → 3.0**（懸空 1487 → 744 mm²）。底面做不出 45° 自撐：
      往下 4.5 mm 就是頂蓋本體（`INNER_TOP_Z` 177.12、`TOP_T` 3.0），斜撐會把頂蓋
      後緣整片吃掉。而 6.0 本來就說不出理由 —— 側舌真正的咬合量只有 `TOP_LIP` = 1.30。
      連帶 `PSU_SLIDE_Y` 7.0 → 4.0（電源讓位距離變短，嚴格更好裝）。
- [x] PCIe 窗框底緣加 **45° 引入楔**（`PCIE_FRAME_LEAD = PCIE_RIB_D = 4.0`），
      自 z 4.68 升到窗框底 8.68；**Y 不多凸一分**，A1 footprint 不受影響。
- [x] `verify_case.support_overhangs()` 常設支撐地圖：PCIe **開孔** x 帶內
      （x −46.3…33.6、z 2.4…151.4）一片平面朝下面都不准有 → **FAIL**；
      帶上方與窗框旁逐條 **WARN** 列 z／面積／塔高。帶界用開孔跨距不是窗框跨距。
- [x] `MB_Screw` 頭頂加 **5.6 × 1.8 × 深 1.5 直邊十字工具槽**。槽開在**貼床那一面**
      （工作位是朝外那一面）→ 第一層的孔，不需支撐；槽頂只是 1.8 mm 的橋接。
      直邊（非 Phillips 錐面）不 cam-out。外側料 1.20、槽頂料 0.90，六角外緣保留。
- [x] 支撐 preset 改脫模導向：xy **0.35**、top/bottom z **0.32**（＝ 2 層）、
      接觸面 **1** 層 + `support_interface_spacing 0.5`、`support_style` **snug**。
      底接觸面仍留 0（那一面壓在件上，加了最難拆）。
- [x] `support_threshold_angle` 綁 `參數.SUPPORT_THRESHOLD_ANGLE`（`驗切片設定.py` 比對）。
- [x] negtest +6、`test_參數.py` +6（含 `test_支撐外脹量受A1床餘量限制`）。

### 卡住的地方：xy 間隙開不到 0.45

第一版把 `support_object_xy_distance` 開到 0.45（PETG 常用值）。`列印擺位.py --best`
立刻紅：

```text
機殼本體_主板段一體式.stl 在 0.0° 佔床 254.42 × 254.59，餘量只有 0.71/邊 < 0.75
```

支撐是印出來的料，也要佔床，代理外脹是 `xy + support_line_width` **每邊**。
Chassis 裸深 252.85，A1 是 256 —— **xy 的上限被床卡死在 0.405**。
取原廠值 **0.35**（餘量 0.81/邊），脫模餘裕改由不佔床的三個參數補
（z 間隙、接觸面層數、snug）。這條衝突已寫成回歸斷言。

## 三、驗證（實際輸出）

```text
ruff check --ignore E402 <本輪修改檔>          → All checks passed
python -m unittest 測試/test_參數.py            → Ran 69 tests / OK（+6 條第十四輪）
FreeCADCmd -c ...\scripts\_run_build.py         → BUILD_OK / 8 STL / 1081.3 / 1300.2 cm³
FreeCADCmd -c ...\scripts\_run_verify.py        → RESULT: ALL CHECKS PASSED
FreeCADCmd -c ...\scripts\_run_negtest.py       → NEGTEST 86/86 / NEGTEST_OK
python 腳本\列印擺位.py --best                 → Chassis 254.22 × 254.39，0.81 mm/邊
python 腳本\驗切片設定.py                       → FAILURES = 0
```

## 四、回顧

1. **「這個孔不生支撐」不等於「這個孔旁邊不生支撐」。** 第十三輪的檢查（開孔頂沒有
   水平面）到現在還是綠的，而且沒有錯 —— 它只是回答了一個比病灶小的問題。
   支撐塔走的**路徑**跟它要撐的是誰無關；要掃的是整件的朝下面，不是那個特徵。
2. **把參數調得比原廠更緊，要說得出理由。** `support_object_xy_distance = 0.2`
   與 `support_interface_top_layers = 0` 都是本專案自己覆寫的，都讓支撐更難拆，
   而且沒有一行註解說為什麼。使用者抱怨的「難拆、粗糙」有一半是這裡來的。
3. **脫模間隙的上限不是材料是床。** 這是本輪唯一被擋下來的改動，
   而且擋它的是一個看起來完全無關的常數（`CASE_D`）。

## 五、仍然沒驗（不得寫成已驗證）

- Bambu Studio 真實切片與真 G-code —— **四個 PCIe 開孔與窗框的 45° 面到底生不生支撐，
  只有這一層能證明**；R13 的 G-code 不可沿用。
- 加大的脫模間隙好不好拆、下表面會不會先塌一兩層才被接住（沒有實印比較過）。
- 鉤唇減到 3.0 之後，頂蓋後緣的壓持力夠不夠（幾何咬合是側舌的 2.3 倍，實感未試）。
- 印製十字槽在手緊扭力下的壽命：PETG 會不會削掉槽壁（六角外緣是後路）。
- 其餘沿用第十三輪：碟架承托肩下沉量、水平盲內牙、實裝主板、EMI、熱。
---

# 文件同步與 README 重寫（2026-08-26）

使用者：「先更新文件和重寫 README」。幾何**一個字都沒動**，動的是文件與註解。

## 一、先驗上游，再投影

- [x] 寫 20 行稽核比對 `參數.py` 的行尾註解與實際值 → **抓到 8 條假數字**
      （`CASE_D # 301.00`、`ATX_Y0 # −10.66`、`ATX_FRONT_Y # 129.34`、
      `ATX_Y1 # 149.34`、`PCIE_CARD_LEN # 189.00`、`AREA_A_TOP_Z # 99.22`、
      `PSU_CLEAR_ABOVE # 1.30`、`PSU_SLIDE_Y # 7.0`）。全部修正。
- [x] 升級成常設檢查 `Test註解真實性`（+1 條非空證明：吋 literal 不得誤報）→ 69 → **71 tests**
- [x] 硬規則 15 補一句「行尾註解裡的數字也是同一種謊言」（`CLAUDE.md` = `AGENTS.md`）

## 二、修掉的文件病灶

| 檔 | 病灶 |
|---|---|
| `規格/設計規格.md` | 標題還停在第十二輪；§5.2 還寫「碟架吊在側板槽上」（R13 已改承托肩）；§6.1 `PCIeBar` 還寫 `2× #6-32`、`MB_Screw` 還寫 9 顆；§6.2 Top 沒寫後緣下伸舌；§7 走線帶用 `129.34 / 149.34`；§9 狀態停在 R12／66 條 |
| `CLAUDE.md`／`AGENTS.md` | A1 餘量還是 `253.92 × 254.09`／`0.96 mm/邊`（現值 `254.22 × 254.39`／`0.81`） |
| `tasks/lessons.md` 68 | 結論寫成「xy 0.45」，但 0.45 是**被床擋下來**的那個值；現役是 0.35 |
| `規格/機殼可用性裁決.md` | 裁決日期停在 R13；缺「起子轉得動螺絲」「拆得掉支撐」兩列 |
| `文件/*.md` | 標題停在第十三輪 |
| `CONTEXT.md` | 測試數 69；補文件同步段 |

`規格/公開參考對齊.md`、`tasks/todo.md` 舊輪段落裡的舊數字**刻意保留**——
那些是逐輪紀錄，改掉就沒有歷史了。

## 三、README 重寫

從「規格總表 + 逐輪 changelog」改成「這台是什麼 / 印之前要知道什麼 / 怎麼驗」：

- 開頭講清楚定位：**沒有任何鈑金件**、整台只用 20 顆標準 #6-32。
- 新增「印之前一定要知道的三件事」（A1 只剩 0.81 mm/邊、支撐 preset 是脫模導向的、
  PCIe 窗不該生支撐——生了先查 preset 不要硬拆）。
- 新增組裝五步與五金表；件數改用 `PART_QTY` 實算（**24 件**，不是 8）。
- 逐輪 changelog 移出（那是 `CONTEXT.md` 與本檔的事），只留「非顯然的設計決定」。
- 驗證分層表保留並加一列「檢查本身不是空的（NEGTEST 86/86）」。

## 四、驗證

```text
ruff check --ignore E402 腳本\參數.py 測試\test_參數.py → All checks passed
python -m unittest 測試/test_參數.py                     → Ran 71 tests / OK
FreeCADCmd -c ...\scripts\_run_verify.py                 → RESULT: ALL CHECKS PASSED（10 條 WARN 同第十四輪）
```

幾何未改動，故未重跑 build／negtest／擺位／preset；FCStd 仍是 2026-08-25 20:11 那份。
