"""
对 network.onnx 运行完整 ezkl 流程：Sigmoid 由 ezkl 的 lookup 表实现（查表，不展开成算术）。

- ONNX 为单 Sigmoid op，电路里用 ezkl 的 Sigmoid 查表约束。
- lookup_range 根据 lookup_table.json 的输入范围设置，保证查表满足。
- 若 ezkl 未来支持从文件加载自定义表 (x_i, k_i, b_i)，可在此接入 lookup_table.json。
"""

import json
import math
import os
import subprocess
import sys
import ezkl


MODEL_PATH = "network.onnx"
SETTINGS_PATH = "settings.json"
COMPILED_MODEL_PATH = "network.compiled"
INPUT_PATH = "input.json"
WITNESS_PATH = "witness.json"
PK_PATH = "pk.key"
VK_PATH = "vk.key"
SRS_PATH = "kzg16.srs"
PROOF_PATH = "proof.json"
LOOKUP_TABLE_PATH = "lookup_table.json"

# lookup_range 由 get_lookup_range_from_table() 从 lookup_table.json 读取，保证查表满足


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def ensure_lookup_table():
    """若不存在 lookup_table.json，则运行 build_lookup_table.py 生成。"""
    base = _base_dir()
    if os.path.exists(os.path.join(base, LOOKUP_TABLE_PATH)):
        return
    print(f"未找到 {LOOKUP_TABLE_PATH}，正在运行 build_lookup_table.py ...")
    r = subprocess.run([sys.executable, "build_lookup_table.py"], cwd=base)
    if r.returncode != 0:
        raise RuntimeError("build_lookup_table.py 执行失败")
    if not os.path.exists(LOOKUP_TABLE_PATH):
        raise FileNotFoundError(f"build_lookup_table.py 未生成 {LOOKUP_TABLE_PATH}")


def get_lookup_range_from_table():
    """从 lookup_table.json 读取 x 的浮点范围，转为 ezkl 使用的整数范围（与 input_scale=7 对齐）。"""
    ensure_lookup_table()
    path = os.path.join(_base_dir(), LOOKUP_TABLE_PATH)
    with open(path) as f:
        tbl = json.load(f)
    xs = tbl["x"]
    x_min, x_max = min(xs), max(xs)
    scale = 1 << 7
    lo = max(0, int(x_min * scale) - 1)
    hi = int(x_max * scale) + 1
    hi = max(hi, 128)
    return (lo, hi)


def ensure_settings_and_compile():
    """
    按「Sigmoid 查表」生成设置：lookup_range 来自 lookup_table.json，保证表项与输入在有限域内可表示。
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"缺少 {MODEL_PATH}，请先运行 gen.py 导出 ONNX。")

    ensure_lookup_table()
    py_run_args = ezkl.PyRunArgs()
    py_run_args.input_visibility = "public"
    py_run_args.output_visibility = "public"
    py_run_args.param_visibility = "fixed"
    py_run_args.logrows = 20

    # 使用 ezkl 的 Sigmoid 查表（非算术展开），lookup_range 与 lookup_table.json 对齐
    lookup_range = get_lookup_range_from_table()
    py_run_args.lookup_range = lookup_range
    print(f"   mode = ezkl Sigmoid 查表，lookup_range = {list(lookup_range)}（来自 {LOOKUP_TABLE_PATH}）")

    print("⚙️ 调用 ezkl.gen_settings ...")
    res = ezkl.gen_settings(MODEL_PATH, SETTINGS_PATH, py_run_args=py_run_args)
    if not res:
        raise RuntimeError("ezkl.gen_settings 失败")

    with open(SETTINGS_PATH) as f:
        settings = json.load(f)
    num_rows = settings.get("num_rows") or 0

    # 由电路行数反推最优 logrows：2^k >= num_rows => k = ceil(log2(num_rows))
    k = 20
    if num_rows > 0:
        k = math.ceil(math.log2(num_rows))
        k = min(max(k, 16), 24)
    print(f"📐 电路行数 num_rows={num_rows} => logrows={k}（2^{k} = {1 << k}）")
    py_run_args.logrows = k
    ezkl.gen_settings(MODEL_PATH, SETTINGS_PATH, py_run_args=py_run_args)
    print("🧱 开始调用 ezkl.compile_circuit ...")
    ezkl.compile_circuit(MODEL_PATH, COMPILED_MODEL_PATH, SETTINGS_PATH)
    print("✅ 已生成 settings.json 与 network.compiled")


def gen_witness():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"缺少 {INPUT_PATH}，请先运行 gen.py。")
    print("🧾 生成 witness.json ...")
    ezkl.gen_witness(INPUT_PATH, COMPILED_MODEL_PATH, WITNESS_PATH)
    print("✅ witness.json 生成完成")


def setup():
    print("🔑 运行 ezkl.setup 生成证明密钥 / 验证密钥 ...")
    with open(SETTINGS_PATH) as f:
        settings = json.load(f)
    logrows = settings["run_args"]["logrows"]
    print(f"📐 使用 logrows={logrows} 重新生成 SRS 到 {SRS_PATH} ...")
    ezkl.gen_srs(SRS_PATH, logrows)
    ezkl.setup(COMPILED_MODEL_PATH, VK_PATH, PK_PATH, SRS_PATH)
    print("✅ 已生成 vk.key / pk.key")


def prove():
    print("📦 生成证明 proof.json ...")
    ezkl.prove(WITNESS_PATH, COMPILED_MODEL_PATH, PK_PATH, PROOF_PATH, SRS_PATH)
    print("✅ 证明生成完成")


def verify():
    print("🔍 验证证明 ...")
    ok = ezkl.verify(PROOF_PATH, SETTINGS_PATH, VK_PATH, SRS_PATH)
    if not ok:
        raise RuntimeError("❌ 证明验证失败")
    print("✅ 证明验证通过")


def main():
    ensure_settings_and_compile()
    gen_witness()
    setup()
    prove()
    verify()


if __name__ == "__main__":
    main()
