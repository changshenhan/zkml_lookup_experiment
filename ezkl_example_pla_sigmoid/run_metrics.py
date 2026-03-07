"""
在 ezkl_example_pla_sigmoid 目录下运行：收集证明时间、内存占用、文件大小、电路指标。
用法: 在本目录执行 python run_metrics.py
输出 JSON 到 metrics_pla.json 供上层对比脚本读取。
"""
import json
import os
import sys
import time

# 可选：进程内存（仅 Unix）
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

def bytes_to_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)

    settings_path = os.path.join(base, "settings.json")
    compiled_path = os.path.join(base, "network.compiled")
    witness_path = os.path.join(base, "witness.json")
    pk_path = os.path.join(base, "pk.key")
    srs_path = os.path.join(base, "kzg16_example.srs")
    proof_out = os.path.join(base, "proof_metrics.json")

    if not all(os.path.exists(p) for p in [settings_path, compiled_path, witness_path, pk_path, srs_path]):
        print("Missing required files; run gen.py and full ezkl pipeline in this folder first.", file=sys.stderr)
        sys.exit(1)

    with open(settings_path) as f:
        settings = json.load(f)

    run_args = settings.get("run_args", {})
    num_rows = settings.get("num_rows")
    total_assignments = settings.get("total_assignments")
    logrows = run_args.get("logrows")
    required_lookups = settings.get("required_lookups", [])

    # 文件大小
    def fsize(p):
        return os.path.getsize(p) if os.path.exists(p) else 0

    file_sizes = {
        "network.onnx": fsize(os.path.join(base, "network.onnx")),
        "network.compiled": fsize(compiled_path),
        "witness.json": fsize(witness_path),
        "settings.json": fsize(settings_path),
        "pk.key": fsize(pk_path),
        "vk.key": fsize(os.path.join(base, "vk.key")),
        "proof.json": fsize(os.path.join(base, "proof.json")),
    }

    # 证明时间（单次 prove）
    import ezkl
    if os.path.exists(proof_out):
        os.remove(proof_out)
    start = time.perf_counter()
    if HAS_RESOURCE:
        resource.getrusage(resource.RUSAGE_SELF)  # 初始化
    ezkl.prove(witness_path, compiled_path, pk_path, proof_out, srs_path)
    prove_time_sec = time.perf_counter() - start
    file_sizes["proof_metrics.json"] = fsize(proof_out)

    # 进程峰值内存（Unix: ru_maxrss 单位 KB）
    peak_mem_kb = None
    if HAS_RESOURCE:
        try:
            peak_mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS 上 ru_maxrss 是 bytes，Linux 是 KB
            if sys.platform == "darwin":
                peak_mem_kb = peak_mem_kb / 1024.0  # 转为 KB
        except Exception:
            pass

    out = {
        "project": "ezkl_example_pla_sigmoid",
        "circuit": {
            "logrows": logrows,
            "num_rows": num_rows,
            "total_assignments": total_assignments,
            "required_lookups": required_lookups,
        },
        "file_sizes_bytes": file_sizes,
        "prove_time_sec": round(prove_time_sec, 3),
        "peak_memory_kb": peak_mem_kb,
    }
    out_path = os.path.join(base, "metrics_pla.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print("Prove time (s):", prove_time_sec)
    if peak_mem_kb is not None:
        print("Peak RSS (MB):", round(peak_mem_kb / 1024, 2))
    print("Wrote", out_path)

if __name__ == "__main__":
    main()
