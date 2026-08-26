# -*- coding: utf-8 -*-
"""驗證 R12 列印計畫與 `列印設定/*.json`（Bambu Studio process preset）。

preset 打錯 key／enum 或漏寫床界設定時，Bambu Studio 可能靜默採用繼承值。
這支腳本同時守住：零件→preset 計畫、JSON／info 配對、名稱與關鍵切片值。
真實切片與 G-code 不在此驗證範圍。

    python 腳本\驗切片設定.py     # exit 0 = 全綠
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import 列印擺位 as PLACEMENT  # noqa: E402

D = PLACEMENT.D
PRESET_DIR = os.path.join(ROOT, "列印設定")


def discover_bambu_home() -> str:
    """找同一套 Bambu Studio 的 profiles 與 DLL；可用環境變數覆寫根目錄。"""
    configured = os.environ.get("BAMBU_STUDIO_HOME")
    candidates = ([configured] if configured else []) + sorted(
        glob.glob(r"C:\Program Files\Bambu Studio*")
    )
    tried = []
    for home in candidates:
        if not home or home in tried:
            continue
        tried.append(home)
        process_dir = os.path.join(home, "resources", "profiles", "BBL", "process")
        dll_path = os.path.join(home, "BambuStudio.dll")
        if os.path.isdir(process_dir) and os.path.isfile(dll_path):
            return home
    raise SystemExit(
        "找不到同一套 Bambu Studio 的 profiles 與 DLL；"
        "可設定 BAMBU_STUDIO_HOME。已試：%s" % tried
    )


BAMBU_HOME = discover_bambu_home()
BBL = os.path.join(BAMBU_HOME, "resources", "profiles")
PROC = os.path.join(BBL, "BBL", "process")
# enum 值的權威來源是程式字串表，不是只包含已用值的原廠 profile。
DLL = os.path.join(BAMBU_HOME, "BambuStudio.dll")

META = {
    "from", "inherits", "name", "print_settings_id", "version", "type",
    "print_extruder_id", "print_extruder_variant",
}
BED_CRITICAL = ("brim_type", "brim_width", "skirt_loops")
SUPPORT_CRITICAL = (
    "support_type", "support_style", "support_expansion",
    "support_object_xy_distance", "raft_first_layer_expansion", "raft_layers",
    # 第十四輪：脫模間隙也算關鍵值。PETG 的層間／側向黏著比 PLA 強得多，
    # 繼承來的 0.2/0.2/0.35 會把支撐焊在件上（使用者回報：難拆、表面粗糙、
    # 拆的時候把 PCIe 那三根 1.42 的肋一起扯斷）。
    "support_top_z_distance", "support_bottom_z_distance",
    "support_interface_top_layers", "support_interface_spacing",
    "support_threshold_angle",
)

PRESET_EXPECTED = {
    PLACEMENT.PRESET_SUPPORT: {
        "layer_height": "0.16",
        "enable_support": "1",
        "support_type": "normal(auto)",
        # 幾何側的 45° 尖頂／斜撐／引入楔只有在這個門檻下才成立 ⇒ 唯一來源是參數.py
        "support_threshold_angle": f"{PLACEMENT.D.SUPPORT_THRESHOLD_ANGLE:g}",
        "support_style": "snug",
        "support_object_xy_distance": "0.35",  # 上限由 A1 床餘量卡死，見 test_支撐外脹量受A1床餘量限制
        "support_top_z_distance": "0.32",
        "support_bottom_z_distance": "0.32",
        "support_expansion": "0",
        "support_interface_top_layers": "1",
        "support_interface_spacing": "0.5",
        "support_interface_bottom_layers": "0",
        "raft_first_layer_expansion": "0",
        "raft_layers": "0",
        "brim_type": "no_brim",
        "brim_width": "0",
        "skirt_loops": "0",
        "wall_loops": "3",
        "sparse_infill_density": "40%",
        "sparse_infill_pattern": "gyroid",
        "wall_generator": "arachne",
    },
    PLACEMENT.PRESET_NO_SUPPORT: {
        "layer_height": "0.16",
        "enable_support": "0",
        "brim_type": "no_brim",
        "brim_width": "0",
        "skirt_loops": "0",
        "wall_loops": "3",
        "sparse_infill_density": "40%",
        "sparse_infill_pattern": "gyroid",
        "wall_generator": "arachne",
    },
    PLACEMENT.PRESET_MB_SCREW: {
        "layer_height": "0.12",
        "enable_support": "0",
        "brim_type": "no_brim",
        "brim_width": "0",
        "skirt_loops": "0",
        "wall_loops": "3",
        "sparse_infill_density": "100%",
        "wall_generator": "arachne",
    },
}


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON 頂層不是 object：{path}")
    return value


def resolve(name: str) -> dict:
    """展開官方 process preset 的 inherits 鏈。"""
    out: dict = {}
    visited = set()
    cur = name
    while cur:
        if not isinstance(cur, str) or os.path.basename(cur) != cur:
            raise SystemExit(f"非法 inherits 名稱：{cur!r}")
        if cur in visited:
            raise SystemExit(f"inherits 循環：{cur}")
        visited.add(cur)
        path = os.path.join(PROC, cur + ".json")
        if not os.path.isfile(path):
            raise SystemExit(f"inherits 指到不存在的 profile：{cur}")
        profile = read_json(path)
        for key, value in profile.items():
            out.setdefault(key, value)
        cur = profile.get("inherits")
    return out


def dll_strings() -> bytes:
    if not os.path.isfile(DLL):
        raise SystemExit(f"找不到 {DLL} —— enum 沒有權威來源就不能宣稱驗過")
    with open(DLL, "rb") as handle:
        return handle.read()


def info_values(path: str) -> dict:
    """解析 Bambu `.info` 的簡單 `key = value` 格式。"""
    out = {}
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            if "=" not in line:
                raise ValueError(f"{path}:{number} 不是 key = value")
            key, value = (part.strip() for part in line.split("=", 1))
            if not key or key in out:
                raise ValueError(f"{path}:{number} key 空白或重複：{key!r}")
            out[key] = value
    return out


def issue(message: str) -> int:
    print("  ✗ " + message)
    return 1


def validate_delivery(json_files: list[str], info_files: list[str]) -> int:
    """驗 manifest、列印計畫與 preset 檔案集合完全一致。"""
    bad = 0
    if set(PLACEMENT.PRINT_PLAN) != set(D.STL_NAMES):
        bad += issue(
            "PRINT_PLAN/STL_NAMES 不一致：%s"
            % (set(PLACEMENT.PRINT_PLAN) ^ set(D.STL_NAMES),)
        )

    expected_fields = {"preset", "orientation", "plate_rotation_deg"}
    valid_plans = []
    for key, plan in PLACEMENT.PRINT_PLAN.items():
        if not isinstance(plan, dict):
            bad += issue(f"PRINT_PLAN[{key}] 必須是 dict")
            continue
        if set(plan) != expected_fields:
            bad += issue(f"PRINT_PLAN[{key}] 欄位錯誤：{set(plan) ^ expected_fields}")
            continue
        if not isinstance(plan["preset"], str) or not plan["preset"]:
            bad += issue(f"PRINT_PLAN[{key}] preset 必須是非空字串")
            continue
        valid_plans.append(plan)
        if plan["orientation"] not in PLACEMENT.ORIENTS:
            bad += issue(f"PRINT_PLAN[{key}] 姿態不存在：{plan['orientation']}")
        if not isinstance(plan["plate_rotation_deg"], (int, float)):
            bad += issue(f"PRINT_PLAN[{key}] 盤上旋轉不是數字")

    plan_presets = {plan["preset"] for plan in valid_plans}
    json_stems = {os.path.splitext(os.path.basename(path))[0] for path in json_files}
    info_stems = {os.path.splitext(os.path.basename(path))[0] for path in info_files}
    for label, actual in (("JSON", json_stems), ("info", info_stems)):
        if actual != plan_presets:
            bad += issue(
                f"{label}/PRINT_PLAN preset 不一致："
                f"missing={sorted(plan_presets - actual)} extra={sorted(actual - plan_presets)}"
            )
    if set(PRESET_EXPECTED) != plan_presets:
        bad += issue(f"PRESET_EXPECTED/PRINT_PLAN 不一致：{set(PRESET_EXPECTED) ^ plan_presets}")

    for path in info_files:
        try:
            metadata = info_values(path)
        except (OSError, ValueError) as exc:
            bad += issue(str(exc))
            continue
        if not metadata.get("user_id"):
            bad += issue(f"{path} 缺本機 user_id metadata")
    return bad


def validate_preset(path: str, blob: bytes) -> int:
    """驗單一 preset 的名稱、鍵值、enum 與床界設定。"""
    bad = 0
    preset = read_json(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    print("=" * 74)
    print("%s  (inherits %s)" % (preset.get("name", stem), preset.get("inherits")))

    if preset.get("name") != stem or preset.get("print_settings_id") != stem:
        bad += issue(
            f"basename/name/print_settings_id 不一致：{stem!r} / "
            f"{preset.get('name')!r} / {preset.get('print_settings_id')!r}"
        )
    if not isinstance(preset.get("inherits"), str):
        return bad + issue(f"{stem} 缺有效 inherits")
    base = resolve(preset["inherits"])

    for key, value in sorted(preset.items()):
        if key in META:
            continue
        if (key.encode() + b"\x00") not in blob:
            bad += issue(f"key 不存在於 BambuStudio.dll：{key}（打錯字會被靜默忽略）")
            continue
        value_json = json.dumps(value, ensure_ascii=False)
        is_enum = isinstance(value, str) and not value[:1].isdigit() and "%" not in value
        if is_enum and (value.encode() + b"\x00") not in blob:
            bad += issue(f"{key} = {value_json} 不是 BambuStudio.dll 認得的值")
            continue
        inherited = json.dumps(base.get(key, "（繼承鏈沒有 → 吃內建預設）"), ensure_ascii=False)
        print("  ok %-30s %-14s 原本 %s" % (key, value_json, inherited))

    for key in BED_CRITICAL:
        if key not in preset:
            bad += issue(f"缺 {key} —— 吃床面積的設定必須寫死，不准繼承")
    if preset.get("enable_support") == "1":
        for key in SUPPORT_CRITICAL:
            if key not in preset:
                bad += issue(f"開了支撐卻沒寫死 {key}")

    expected = PRESET_EXPECTED.get(stem)
    if expected is None:
        bad += issue(f"沒有 {stem} 的精確值規格")
    else:
        for key, wanted in expected.items():
            if preset.get(key) != wanted:
                bad += issue(f"{key}={preset.get(key)!r}，應為 {wanted!r}")
    return bad


def main() -> int:
    if not os.path.isdir(PROC):
        raise SystemExit(f"找不到 Bambu Studio 原廠 profile：{PROC}")
    json_files = sorted(glob.glob(os.path.join(PRESET_DIR, "*.json")))
    info_files = sorted(glob.glob(os.path.join(PRESET_DIR, "*.info")))
    if not json_files:
        raise SystemExit(f"{PRESET_DIR} 裡沒有 preset")

    bad = validate_delivery(json_files, info_files)
    blob = dll_strings()
    for path in json_files:
        try:
            bad += validate_preset(path, blob)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            bad += issue(str(exc))
    print("=" * 74)
    print("FAILURES =", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
