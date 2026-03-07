"""
统一评估当前 ezkl 电路的一些关键指标，并重新测一遍证明时间。

假设已经运行过：
    python gen.py
    python run_ezkl_full.py

本脚本会：
1. 从 settings.json 中读取电路规模信息（num_rows、logrows、约束规模等）；
2. 统计模型、电路、witness、密钥、证明等文件的大小；
3. 若存在 lookup_table.json，则评估分段线性近似 Sigmoid 的最大中点误差；
4. 在已有 witness / pk / compiled / srs 的前提下，重新跑一次 prove，测量耗时；
5. 总结为一份易读的指标报告。
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any

import ezkl
import numpy as np


BASE = Path(__file__).resolve().parent

MODEL_PATH = BASE / "network.onnx"
SETTINGS_PATH = BASE / "settings.json"
COMPILED_MODEL_PATH = BASE / "network.compiled"
INPUT_PATH = BASE / "input.json"
WITNESS_PATH = BASE / "witness.json"
PK_PATH = BASE / "pk.key"
VK_PATH = BASE / "vk.key"
SRS_PATH = BASE / "kzg16.srs"
PROOF_PATH = BASE / "proof_eval.json"
LOOKUP_TABLE_PATH = BASE / "lookup_table.json"


def bytes_to_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError("settings.json 不存在，请先运行 run_ezkl_full.py。")
    return json.loads(SETTINGS_PATH.read_text())


def summarize_circuit(settings: Dict[str, Any]) -> None:
    run_args = settings.get("run_args", {})
    num_rows = settings.get("num_rows")
    total_assignments = settings.get("total_assignments")
    logrows = run_args.get("logrows")
    lookup_range = run_args.get("lookup_range")
    required_lookups = settings.get("required_lookups", [])

    print("=== 电路规模相关 ===")
    print(f"- logrows (k): {logrows}  → 最大行数上限 2^k = {1<<logrows if logrows is not None else '未知'}")
    print(f"- 实际行数 num_rows: {num_rows}")
    print(f"- total_assignments: {total_assignments}")
    print(f"- lookup_range: {lookup_range}")
    print(f"- required_lookups: {required_lookups}")
    print()


def summarize_file_sizes() -> None:
    print("=== 文件大小（资源占用） ===")
    for p in [
        MODEL_PATH,
        COMPILED_MODEL_PATH,
        INPUT_PATH,
        WITNESS_PATH,
        SETTINGS_PATH,
        PK_PATH,
        VK_PATH,
        PROOF_PATH,
    ]:
        if p.exists():
            size = p.stat().st_size
            print(f"- {p.name:16s}: {bytes_to_human(size)}")
        else:
            print(f"- {p.name:16s}: 不存在")
    print()


def eval_lookup_table_error() -> None:
    if not LOOKUP_TABLE_PATH.exists():
        print("=== 查找表近似误差 ===")
        print("- 未找到 lookup_table.json，跳过查找表误差评估。")
        print()
        return

    data = json.loads(LOOKUP_TABLE_PATH.read_text())
    xs = np.asarray(data["x"], dtype=np.float64)
    ks = np.asarray(data["k"], dtype=np.float64)
    bs = np.asarray(data["b"], dtype=np.float64)

    # 在每个区间中点处评估 σ(x) 与 kx + b 的误差
    x0 = xs[:-1]
    x1 = xs[1:]
    mids = 0.5 * (x0 + x1)

    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    true_mid = sigmoid(mids)
    approx_mid = ks * mids + bs
    abs_err = np.abs(true_mid - approx_mid)
    max_abs_err = float(abs_err.max())
    mean_abs_err = float(abs_err.mean())

    rel_err = abs_err / (np.abs(true_mid) + 1e-8)
    max_rel_err = float(rel_err.max())
    mean_rel_err = float(rel_err.mean())

    print("=== 查找表 Sigmoid 线性近似误差（区间中点） ===")
    print(f"- 段数: {len(xs) - 1}")
    print(f"- 最大绝对误差 max |σ(x) - (k x + b)| = {max_abs_err:.6e}")
    print(f"- 平均绝对误差 mean |σ(x) - (k x + b)| = {mean_abs_err:.6e}")
    print(f"- 最大相对误差 max rel_err = {max_rel_err:.6e}")
    print(f"- 平均相对误差 mean rel_err = {mean_rel_err:.6e}")
    print()


def measure_prove_time(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    在现有 witness / pk / compiled / srs 基础上重新跑一次 prove，测量耗时与峰值内存。
    不修改原有 proof.json，而是写到 proof_eval.json。
    返回 {"prove_time_sec", "peak_memory_kb"} 供对比脚本使用。
    """
    print("=== 证明时间与内存评估（单次 prove） ===")
    try:
        import resource
        HAS_RESOURCE = True
    except ImportError:
        HAS_RESOURCE = False

    for path, desc in [
        (COMPILED_MODEL_PATH, "compiled circuit"),
        (WITNESS_PATH, "witness.json"),
        (PK_PATH, "pk.key"),
        (SRS_PATH, "kzg16.srs"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{desc} 缺失，请先运行 run_ezkl_full.py：{path}")

    if PROOF_PATH.exists():
        PROOF_PATH.unlink()

    start = time.perf_counter()
    ezkl.prove(str(WITNESS_PATH), str(COMPILED_MODEL_PATH), str(PK_PATH), str(PROOF_PATH), str(SRS_PATH))
    elapsed = time.perf_counter() - start

    peak_memory_kb = None
    if HAS_RESOURCE:
        try:
            peak_memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            import sys
            if sys.platform == "darwin":
                peak_memory_kb = peak_memory_kb / 1024.0
        except Exception:
            pass

    print(f"- 单次 prove 耗时: {elapsed:.3f} 秒")
    if peak_memory_kb is not None:
        print(f"- 进程峰值内存 (RSS): {bytes_to_human(int(peak_memory_kb * 1024))} ({peak_memory_kb/1024:.2f} MB)")
    size = PROOF_PATH.stat().st_size if PROOF_PATH.exists() else 0
    print(f"- 生成的评估 proof_eval.json 大小: {bytes_to_human(size)}")
    print()
    return {"prove_time_sec": round(elapsed, 3), "peak_memory_kb": peak_memory_kb}


def collect_our_metrics(settings: Dict[str, Any]) -> Dict[str, Any]:
    """收集本项目的电路与文件大小，并执行一次 prove 得到时间与内存；返回可序列化的指标字典。"""
    run_args = settings.get("run_args", {})
    prove_metrics = measure_prove_time(settings)
    file_sizes = {}
    for name, path in [
        ("network.onnx", MODEL_PATH),
        ("network.compiled", COMPILED_MODEL_PATH),
        ("input.json", INPUT_PATH),
        ("witness.json", WITNESS_PATH),
        ("settings.json", SETTINGS_PATH),
        ("pk.key", PK_PATH),
        ("vk.key", VK_PATH),
        ("proof_eval.json", PROOF_PATH),
    ]:
        if path.exists():
            file_sizes[name] = path.stat().st_size
    return {
        "project": "zkml_lookup_experiment",
        "circuit": {
            "logrows": run_args.get("logrows"),
            "num_rows": settings.get("num_rows"),
            "total_assignments": settings.get("total_assignments"),
            "required_lookups": settings.get("required_lookups", []),
        },
        "file_sizes_bytes": file_sizes,
        "prove_time_sec": prove_metrics["prove_time_sec"],
        "peak_memory_kb": prove_metrics.get("peak_memory_kb"),
    }


def main():
    settings = load_settings()
    print("========== zkML 电路评估指标 ==========\n")
    summarize_circuit(settings)
    summarize_file_sizes()
    eval_lookup_table_error()
    metrics = collect_our_metrics(settings)
    out_path = BASE / "metrics_ours.json"
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"已写入指标到 {out_path}\n========== 评估完成 ==========")


if __name__ == "__main__":
    main()

