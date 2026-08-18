# 3DP-MATX — 全 3D 列印的 microATX NAS 機殼

參數化設計的 microATX NAS 機殼，**11 個列印件、13.70 L、機殼件之間一顆螺絲都沒有**
（全部滑槽 + detent + 單向楔互鎖）。用 FreeCAD 的 **Part 模組 CSG 布林**建模，
所有尺寸集中在 `腳本/參數.py`，其餘文件都是它的投影。

<p align="center">
  <img src="規格/總成視圖_iso.png" width="46%" alt="總成等角視圖">
  <img src="規格/組裝_爆炸圖.png" width="46%" alt="爆炸圖">
</p>

| | |
|---|---|
| 外形 | **252.68 × 301.00 × 180.12 mm**（單一長方體，無階梯、無外凸腳、無下裙） |
| 實佔體積 | **13.70 L**（靠牆擺要留 309.0 mm，後牆外掛 PCIe 壓條的蘑菇柱最凸 8.00） |
| 主板 | microATX 244 × 244，**平躺在底板上**，九孔印製階梯柱 + 印製螺紋壓帽 |
| 電源 | ATX PS/2 150 × 86 × 140，**在 I/O 擋板正上方、頂到內頂**，風扇朝下、與主板同腔無隔板 |
| 硬碟 | 4 × 3.5"**平躺四層堆疊**在主板前段正上方，碟架置中，托盤自前面板抽換 |
| 擴充 | 全高 PCIe × 4，壓條長在機殼**外面**（keyhole 可拆），卡長上限 **189.00 mm** |
| 列印機 | Bambu Lab A1（256³ 床）／0.4 噴嘴／PETG |
| 用料 | **1251.3 cm³ ≈ 1.60 kg**（已乘份數；粗估 60~90 h） |

## 設計重點

- **一顆螺絲都沒有。** 機殼件之間全部滑槽組裝。牆厚 2.4 mm 放不下燕尾，
  所以角落一律「薄定位舌 + detent」；要拉不出來的地方改**單向楔**
  （斜坡推得進、直角面拉不出）。剩下的五金只有鎖在鋼件上的那些
  （PSU 四顆 #6-32、每顆碟四顆 #6-32）。
- **主板佔滿內腔。** 板的四周與上下都是 microATX 規格淨空區，機殼不准伸進去
  （板底 6.35／Area A 76.20／B 15.24／C 38.10）。驗證用四塊「規格淨空實體」
  對全部印件做布林，不是拿幾個探點量。
- **床限制逼出來的分件。** `CASE_D = 301.00 > 256`，所以底板／側板／頂蓋只做到
  `BAY_SPLIT_Y`，前方 53.76 mm 是獨立的 `Front_Shroud`。
- **每個規格數字都指得到頁碼。** 指不到的一律標成估值。孔位優先從 PDF 的
  向量圖元量座標，不讀圖上的標註文字。

組裝順序、卡榫剖面、逐步圖見 `文件/零件清單與組裝.md` 與 `規格/組裝_*.png`。

## 目錄

```text
腳本/          建模、驗證、出圖、擺位、切片檢查（Python）
  參數.py      ★ 唯一真實來源：所有尺寸都在這裡
規格/          設計規格、孔位、規範清單、渲染圖與組裝圖
文件/          零件清單與組裝、列印參數與擺位
列印件/        11 個 STL（可由 build 重生）
列印設定/      Bambu Studio process preset ×3
CAD/           FreeCAD 總成檔
測試/          參數回歸測試（58 tests）
參考/          第三方規格書（不進版控，見下）
tasks/         規劃與歷輪教訓
CONTEXT.md     開發交接文件（接手先讀這頁）
CLAUDE.md      硬規則（AGENTS.md 內容相同）
```

## 環境

- FreeCAD 1.0（提供 `FreeCADCmd`）
- Python 3.11+，`pymupdf`（讀規格 PDF）、`pillow`（出圖）
- Bambu Studio（驗切片設定與 G-code 時需要）

**`FreeCADCmd` 收不到中文 argv**——傳中文路徑只會印 banner 就結束、exit 1，
看起來像跑過了其實沒跑。所以本機需要一個 ASCII 的 junction：

```powershell
New-Item -ItemType Junction -Path scripts -Target 腳本
```

## 指令

```powershell
FreeCADCmd -c <root>\scripts\_run_build.py     # 建模 → CAD/ 與 列印件/，exit 0 = BUILD_OK
FreeCADCmd -c <root>\scripts\_run_verify.py    # 全部檢查，exit 0 = failures 0
FreeCADCmd -c <root>\scripts\_run_negtest.py   # 反向測試：新檢查抓不抓得到舊病灶
python -m unittest 測試/test_參數.py            # 58 tests
python 腳本\渲染預覽.py                          # → 規格/總成視圖_*.png
python 腳本\組裝圖.py                            # → 規格/組裝_*.png（爆炸／逐步 ×8／剖面 ×7）
python 腳本\列印擺位.py --best                  # 逐件擺位／懸空／床接觸／用料
python 腳本\驗切片設定.py                        # Bambu preset 的 key 與 enum
python 腳本\驗切片gcode.py                       # 切出來的 G-code 有沒有跑出熱床
```

`FreeCADCmd` 的腳本不會因為失敗就沒有產物——**判斷有沒有真的跑，看產物的 mtime。**

## 列印重點

完整的逐件擺位表在 `文件/列印參數與擺位.md`。三件事不改就印不出來：

| 設定 | 值 | 為什麼 |
|---|---|---|
| `support_type` | `normal(auto)` | A1 預設 `tree(auto)` 的分枝 45° 往外斜，後牆佔床會撐到 608 mm |
| `brim_type` / `brim_width` | `no_brim` / `0` | 官方繼承鏈**從沒寫過** `brim_type` → 吃內建 `auto_brim`，`CASE_W` 單邊只剩 1.66 mm |
| `raft_first_layer_expansion` | `0` | `-1`（自動）會把**支撐第一層**往外擴 2.9~4.0 mm，底板的支撐因此跑到 X −0.912 |

後牆與碟架要在盤上**轉 45°**（餘量 1.66 → 33.55／14.22 mm/邊）。
前罩、PCIe 槽蓋、主板壓帽**絕對不能開支撐**（壓帽的懸空全部是螺紋牙的下側，
支撐長進牙谷就報廢——真旋合只有 0.40 mm）。

現成的 preset 在 `列印設定/`，複製到
`%APPDATA%\BambuStudio\user\<uid>\process\` 後重開 Bambu Studio。

## 需自備的規格書

`參考/*.pdf` 不隨本專案散布，請自行下載後放進 `參考/`（檔名要一致）：

| 檔名 | 來源 |
|---|---|
| `microATX規格_1.2.pdf` | Intel — microATX Motherboard Interface Specification v1.2 |
| `ATX12V電源規格.pdf` | Intel — ATX12V Power Supply Design Guide |
| `SFX12V規格.pdf` | Intel — SFX12V Power Supply Design Guide |
| `PCI_Express_CEM_r2.0.pdf` | PCI-SIG — PCI Express Card Electromechanical Spec r2.0 |
| `SFF-8301_3.5吋碟尺寸.pdf` | SNIA SFF — SFF-8301 3.5" Form Factor Drive Dimensions |

沒有這些 PDF 也能 build 與 verify（尺寸已經抄進 `參數.py` 並註明頁碼），
只有重新核對來源時才需要。**引用前先 `fitz.open()` 印第一頁確認不是壞檔**。

## 驗證到哪裡了

**`failures=0` 只代表腳本層通過。** 分層定義見 `規格/機殼規範清單.md` §4。

| 層 | 狀態 |
|---|---|
| 狀態（幾何在不在那裡） | ✅ verify 全綠 |
| 動作（照組裝順序走不走得到） | ✅ 逐步掃描 + 六向保持力 |
| 切片（STL → preset → 真 G-code） | ✅ 三層都驗過 |
| 目視（FreeCAD GUI 複檢） | ✅ 11 件 solids=1 / valid / closed |
| **實機列印、試裝、EMI、螺牙壽命、熱** | ❌ **完全沒做** |

已知的**刻意規範偏離**（不是缺陷，但也不是「規格就是這樣」）：

- `PCIE_CARD_LEN = 189.00` — 碟架置中之後卡與碟架的 X 帶重疊，只能二選一。
  仍 > CEM 半長卡 167.65，四個全高槽一個都沒少。
- 板上淨空 `Area A = 76.20` **達 microATX Table 6 required**，但 **< recommended 88.90**。
  所以可以寫「板上淨空達 required」，**不可以**寫「完全相容 microATX」。
- `PSU_FAN_DOWN = True`（大面風扇朝主板）是**假設不是規格**——ATX12V v1.1 Fig.4 p23
  只畫了後面板 80 mm 風扇，大面 120/140 風扇在哪一面規格沒寫。verify 會 `WARN`。

氣流只有一條路（前柵 → 碟 → 敞開的艙口 → 主板腔 → 電源風扇 → 後方排出），
面積算過（前柵 13976 mm² > 120 風扇 11310），**風壓與溫升沒有量過**。

## 授權

尚未指定。在補上 `LICENSE` 之前，預設保留所有權利。
