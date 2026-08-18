# -*- coding: utf-8 -*-
"""驗 `列印設定/*.json`（Bambu Studio process preset）。

為什麼要有這支
--------------
preset 打錯 key 或寫錯 enum，**Bambu Studio 不會報錯，它只是忽略那一行**，
於是繼承鏈上的官方預設原封不動地生效 —— 看起來套用了、實際上沒有。
第十一輪就是這樣：`support_type` 沒生效 → A1 預設 `tree(auto)` 的 45° 分枝
把後牆的佔床撐到 608 mm，Bambu 直接標「超出列印範圍」。

而且**「沒寫」比「寫錯」更難發現**：`brim_type` 在 `0.16mm Optimal @BBL A1`
整條繼承鏈裡**一次都沒出現**，代表它吃的是程式內建預設 `auto_brim` + `brim_width 5`。
`CASE_W = 252.68` 在 256 的床上單邊只剩 1.66 —— auto brim 一開就爆。
所以「吃床面積的設定」一律要在 preset 裡**寫死**，不能靠繼承。

用法：
    python 腳本\\驗切片設定.py     # exit 0 = 全綠
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRESET_DIR = os.path.join(ROOT, "列印設定")
BBL = r"C:\Program Files\Bambu Studio\resources\profiles"
PROC = os.path.join(BBL, "BBL", "process")
# ★ enum 值的權威來源是**程式的字串表**，不是原廠 profile。
#   原廠 profile 只列它自己用過的值：`wall_generator` 全部都是 `classic`，
#   拿它當白名單的話 `arachne` 會被誤判成打錯字。
DLL = r"C:\Program Files\Bambu Studio\BambuStudio.dll"

# preset 本身的欄位，不是切片參數
META = {
    "from", "inherits", "name", "print_settings_id", "version", "type",
    "print_extruder_id", "print_extruder_variant",
}

# 官方 profile 從來沒覆寫、但確實存在的選項（值來自程式內建預設）。
# 要加進來必須寫得出「在 Bambu Studio 哪一頁看得到它」。
KNOWN_UNSET = {
    "brim_type": "其他 → Brim型別（官方 BBL profile 全都沒覆寫 → 內建 auto_brim）",
}

# 只要有一件的最大投影邊 + 這個設定造成的外脹 > 床，就印不出來。
# 這些一律要在 preset 裡出現，缺一個就 fail。
BED_CRITICAL = ("brim_type", "brim_width", "skirt_loops")
SUPPORT_CRITICAL = (
    "support_type", "support_style", "support_expansion",
    "support_object_xy_distance",
    # ★ 支撐的**第一層**是另一組參數在管：`raft_first_layer_expansion = -1`
    #   （自動）實測往外擴 2.9~4.0 mm，`support_expansion = 0` 管不到，
    #   底板的支撐因此跑到 X = -0.912 / 256.912，Bambu 報「超出熱床邊界」。
    "raft_first_layer_expansion", "raft_layers",
)


def resolve(name: str) -> dict:
    """展開 inherits 鏈，回傳解析後的完整設定。"""
    out: dict = {}
    cur = name
    while cur:
        path = os.path.join(PROC, cur + ".json")
        if not os.path.isfile(path):
            raise SystemExit(f"inherits 指到不存在的 profile：{cur}")
        j = json.load(open(path, encoding="utf-8"))
        for k, v in j.items():
            out.setdefault(k, v)
        cur = j.get("inherits")
    return out


def official_values() -> dict:
    """全部原廠 profile（所有廠商）用過的 key → 值集合。打錯字抓這個。"""
    seen: dict = {}
    for f in glob.glob(os.path.join(BBL, "**", "*.json"), recursive=True):
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(j, dict):
            continue
        for k, v in j.items():
            seen.setdefault(k, set()).add(json.dumps(v, ensure_ascii=False))
    return seen


def dll_strings() -> bytes:
    """整顆 DLL 的位元組；enum 值要能在裡面找到 NUL 結尾的字串。"""
    if not os.path.isfile(DLL):
        raise SystemExit(f"找不到 {DLL} —— enum 沒有權威來源就不要假裝驗過")
    with open(DLL, "rb") as f:
        return f.read()


def main() -> int:
    if not os.path.isdir(PROC):
        raise SystemExit(f"找不到 Bambu Studio 原廠 profile：{PROC}")
    seen = official_values()
    blob = dll_strings()
    files = sorted(glob.glob(os.path.join(PRESET_DIR, "*.json")))
    if not files:
        raise SystemExit(f"{PRESET_DIR} 裡沒有 preset")
    bad = 0
    for f in files:
        p = json.load(open(f, encoding="utf-8"))
        base = resolve(p["inherits"])
        print("=" * 74)
        print("%s  (inherits %s)" % (p["name"], p["inherits"]))
        for k, v in sorted(p.items()):
            if k in META:
                continue
            if (k.encode() + b"\x00") not in blob:
                print("  ✗ key 不存在於 BambuStudio.dll：%s（打錯字會被靜默忽略）" % k)
                bad += 1
                continue
            vs = json.dumps(v, ensure_ascii=False)
            is_enum = isinstance(v, str) and not v[:1].isdigit() and "%" not in v
            if is_enum and (v.encode() + b"\x00") not in blob:
                print("  ✗ %s = %s 不是 BambuStudio.dll 認得的值" % (k, vs))
                bad += 1
                continue
            was = json.dumps(base.get(k, "（繼承鏈沒有 → 吃內建預設）"),
                             ensure_ascii=False)
            print("  ok %-30s %-14s 原本 %s" % (k, vs, was))

        for k in BED_CRITICAL:
            if k not in p:
                print("  ✗ 缺 %s —— 吃床面積的設定必須寫死，不准繼承" % k)
                bad += 1
        if p.get("enable_support") == "1":
            for k in SUPPORT_CRITICAL:
                if k not in p:
                    print("  ✗ 開了支撐卻沒寫死 %s" % k)
                    bad += 1
            if p.get("support_type") != "normal(auto)":
                print("  ✗ support_type 必須是 normal(auto)"
                      "（tree 的 45° 分枝會讓四個大件超出 A1 床）")
                bad += 1
            if float(p.get("raft_first_layer_expansion", -1)) != 0.0:
                print("  ✗ raft_first_layer_expansion 必須是 0"
                      "（-1=自動，實測把支撐第一層往外擴 2.9~4.0 mm → 掉出床外）")
                bad += 1
        if p.get("brim_type") != "no_brim" or p.get("brim_width") != "0":
            print("  ✗ brim 必須是 no_brim + width 0"
                  "（CASE_W 252.68 在 256 床上單邊只剩 1.66）")
            bad += 1
    print("=" * 74)
    print("FAILURES =", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
