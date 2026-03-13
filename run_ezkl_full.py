"""
对 network.onnx 运行完整 ezkl 流程：Sigmoid 使用自定义分段查找表（Custom Lookup）。

- ONNX 为单 Sigmoid op；当设置 custom_lookup_path 时，ezkl 用该 PWL 文件作为查找表
  （见 README_EZKL_CHANGES.md）。
- 先由 build_lookup_table.py 生成 lookup_table.json 与 pwl_params.json；
  lookup_range 从 lookup_table 的输入范围推出，保证查表满足。

- 证明阶段：ezkl 的 Python 绑定已在 prove 时释放 GIL，避免与 rayon 多线程死锁；
  RAYON_NUM_THREADS 不可为 1（会死锁），不设则用默认多线程以达秒级证明。
"""

import json
import math
import os
import subprocess
import sys
import time

# 仅禁止 1：单线程 rayon 会死锁。不设则用系统默认（多核，证明更快）
if os.environ.get("RAYON_NUM_THREADS") == "1":
    os.environ["RAYON_NUM_THREADS"] = "2"

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
PWL_PARAMS_PATH = "pwl_params.json"
# 1024 段：更高精度；若 gen_settings 过慢可改回 pwl_params_64.json
PWL_PARAMS_PATH_DEFAULT = "pwl_params.json"

def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def ensure_lookup_table():
    """若不存在 lookup_table.json 或 pwl_params.json，则运行 build_lookup_table.py 生成。"""
    base = _base_dir()
    lookup_path = os.path.join(base, LOOKUP_TABLE_PATH)
    pwl_path = os.path.join(base, PWL_PARAMS_PATH_DEFAULT)
    if os.path.exists(lookup_path) and os.path.exists(pwl_path):
        return
    print(f"未找到 {LOOKUP_TABLE_PATH} 或 {PWL_PARAMS_PATH_DEFAULT}，正在运行 build_lookup_table.py ...")
    r = subprocess.run([sys.executable, "build_lookup_table.py"], cwd=base)
    if r.returncode != 0:
        raise RuntimeError("build_lookup_table.py 执行失败")
    if not os.path.exists(lookup_path):
        raise FileNotFoundError(f"build_lookup_table.py 未生成 {LOOKUP_TABLE_PATH}")
    if not os.path.exists(pwl_path):
        raise FileNotFoundError(f"build_lookup_table.py 未生成 {PWL_PARAMS_PATH_DEFAULT}")


def get_lookup_range_from_table():
    """
    从 lookup_table.json 读取 x 的浮点范围，转为 ezkl 使用的整数范围（scale=128 与 CUSTOM 一致）。
    必须包含运行时进入 Sigmoid 的所有值（如 Conv 输出），故向两侧扩展 margin，且不把 lo 钳到 0。
    """
    ensure_lookup_table()
    path = os.path.join(_base_dir(), LOOKUP_TABLE_PATH)
    with open(path) as f:
        tbl = json.load(f)
    xs = tbl["x"]
    x_min, x_max = min(xs), max(xs)
    scale = 1 << 7  # 128，与 CUSTOM(scale=128) 一致
    # 留足边距：中间层激活可能超出 data 分布，避免 "value is OOR of lookup"
    margin_float = 5.0
    margin_int = int(margin_float * scale)
    lo = int(x_min * scale) - margin_int
    hi = int(x_max * scale) + margin_int
    # 至少覆盖 [0,128]，并允许负值
    lo = min(lo, 0)
    hi = max(hi, 128)
    return (lo, hi)


def ensure_settings_and_compile():
    """
    使用自定义 PWL 查找表生成设置：custom_lookup_path 指向 pwl_params.json，
    lookup_range 来自 lookup_table.json，保证表项与输入在有限域内可表示。
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"缺少 {MODEL_PATH}，请先运行 gen.py 导出 ONNX。")

    ensure_lookup_table()
    py_run_args = ezkl.PyRunArgs()
    py_run_args.input_visibility = "public"
    py_run_args.output_visibility = "public"
    py_run_args.param_visibility = "fixed"
    py_run_args.logrows = 20

    # 自定义分段查找表：ezkl 修改版支持 custom_lookup_path（见 README_EZKL_CHANGES.md）
    pwl_abs = os.path.abspath(os.path.join(_base_dir(), PWL_PARAMS_PATH_DEFAULT))
    try:
        py_run_args.custom_lookup_path = pwl_abs
    except AttributeError:
        raise RuntimeError(
            "当前 ezkl 未提供 custom_lookup_path。请使用支持 Custom Lookup 的 ezkl 修改版，见 README_EZKL_CHANGES.md。"
        )
    lookup_range = get_lookup_range_from_table()
    py_run_args.lookup_range = lookup_range
    print(f"   mode = 自定义 PWL 查表，custom_lookup_path = {pwl_abs}")
    print(f"   lookup_range = {list(lookup_range)}（来自 {LOOKUP_TABLE_PATH}）")

    print("⚙️ 调用 ezkl.gen_settings ...", flush=True)
    res = ezkl.gen_settings(MODEL_PATH, SETTINGS_PATH, py_run_args=py_run_args)
    if not res:
        raise RuntimeError("ezkl.gen_settings 失败")
    print("   gen_settings 返回 OK", flush=True)

    with open(SETTINGS_PATH) as f:
        settings = json.load(f)
    num_rows = settings.get("num_rows") or 0
    run_args = settings.get("run_args", {})
    logrows_set = run_args.get("logrows")
    lr = run_args.get("lookup_range", [])
    print(f"   settings: num_rows={num_rows}, logrows={logrows_set}, lookup_range={lr}", flush=True)

    # 由电路行数反推最优 logrows：2^k >= num_rows => k = ceil(log2(num_rows))
    # 最小用 13（2^13=8192），避免 logrows=16 时 SRS/证明过大导致 prove 像卡住（实际要等很久）
    k = 20
    if num_rows > 0:
        k = math.ceil(math.log2(num_rows))
        k = min(max(k, 13), 24)
    print(f"📐 电路行数 num_rows={num_rows} => logrows={k}（2^{k} = {1 << k}）")
    py_run_args.logrows = k
    ezkl.gen_settings(MODEL_PATH, SETTINGS_PATH, py_run_args=py_run_args)
    print("🧱 开始调用 ezkl.compile_circuit ...", flush=True)
    t0 = time.perf_counter()
    ezkl.compile_circuit(MODEL_PATH, COMPILED_MODEL_PATH, SETTINGS_PATH)
    print(f"✅ 已生成 settings.json 与 network.compiled（compile 耗时 {time.perf_counter() - t0:.1f}s）", flush=True)


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
    print("📦 生成证明 proof.json ...（可能需 30 秒～数分钟，请耐心等待）", flush=True)
    print("[prove] 即将调用 ezkl.prove()（若卡住则说明卡在 Rust 内部）...", flush=True)
    t0 = time.perf_counter()
    ezkl.prove(WITNESS_PATH, COMPILED_MODEL_PATH, PK_PATH, PROOF_PATH, SRS_PATH)
    elapsed = time.perf_counter() - t0
    print("[prove] ezkl.prove() 已返回", flush=True)
    print(f"✅ 证明生成完成（prove 耗时 {elapsed:.1f}s）")


def verify():
    print("🔍 验证证明 ...")
    ok = ezkl.verify(PROOF_PATH, SETTINGS_PATH, VK_PATH, SRS_PATH)
    if not ok:
        raise RuntimeError("❌ 证明验证失败")
    print("✅ 证明验证通过")


def main():
    print("RAYON_NUM_THREADS =", os.environ.get("RAYON_NUM_THREADS", "(default)"), flush=True)
    ensure_settings_and_compile()
    gen_witness()
    setup()
    prove()
    verify()


if __name__ == "__main__":
    main()
