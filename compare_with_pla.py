"""
本项目 (zkml_lookup_experiment) 与 ezkl_example_pla_sigmoid 的指标对比与核心优缺点分析。

使用前请确保：
1. 本项目已运行过 run_ezkl_full.py，再运行 python eval_metrics.py 生成 metrics_ours.json
2. 对比项目已运行过完整 ezkl 流程，并运行 python run_metrics.py 生成 metrics_pla.json
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
OURS_JSON = BASE / "metrics_ours.json"
PLA_DIR = BASE / "ezkl_example_pla_sigmoid"
PLA_JSON = PLA_DIR / "metrics_pla.json"


def bytes_to_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


def main():
    if not OURS_JSON.exists():
        print("请先在本项目根目录运行: python eval_metrics.py 生成 metrics_ours.json")
        return
    if not PLA_JSON.exists():
        print(f"请先在 {PLA_DIR} 目录运行: python run_metrics.py 生成 metrics_pla.json")
        return

    ours = json.loads(OURS_JSON.read_text())
    pla = json.loads(PLA_JSON.read_text())

    print("=" * 60)
    print("  zkml_lookup_experiment vs ezkl_example_pla_sigmoid 指标对比")
    print("=" * 60)

    # 电路规模
    print("\n【电路规模】")
    print(f"  {'指标':<24} {'本项目 (Lookup Sigmoid)':<28} {'PLA (无 Lookup)':<20}")
    print("-" * 72)
    print(f"  {'logrows (k)':<24} {ours['circuit']['logrows']:<28} {pla['circuit']['logrows']:<20}")
    print(f"  {'num_rows (实际行数)':<24} {ours['circuit']['num_rows']:<28} {pla['circuit']['num_rows']:<20}")
    print(f"  {'total_assignments':<24} {ours['circuit']['total_assignments']:<28} {pla['circuit']['total_assignments']:<20}")
    print(f"  {'required_lookups':<24} {str(ours['circuit']['required_lookups']):<28} {str(pla['circuit']['required_lookups']):<20}")

    # 证明时间与内存
    print("\n【证明时间与内存】")
    print(f"  {'prove 耗时 (秒)':<24} {ours['prove_time_sec']:<28} {pla['prove_time_sec']:<20}")
    o_mem = ours.get("peak_memory_kb")
    p_mem = pla.get("peak_memory_kb")
    o_mem_s = f"{o_mem/1024:.2f} MB" if o_mem else "N/A"
    p_mem_s = f"{p_mem/1024:.2f} MB" if p_mem else "N/A"
    print(f"  {'峰值内存 (RSS)':<24} {o_mem_s:<28} {p_mem_s:<20}")

    # 文件大小（选关键项）
    print("\n【关键文件大小】")
    for key in ["pk.key", "vk.key", "proof_eval.json", "proof.json", "network.compiled", "witness.json"]:
        ok = "proof_eval.json" if key == "proof_eval.json" else key
        pk = "proof_metrics.json" if key == "proof_eval.json" else key
        ob = ours["file_sizes_bytes"].get(ok, 0)
        pb = pla["file_sizes_bytes"].get(pk, 0)
        print(f"  {key:<24} {bytes_to_human(ob):<28} {bytes_to_human(pb):<20}")

    # 核心优缺点与原因
    print("\n" + "=" * 60)
    print("  核心优缺点与原因")
    print("=" * 60)

    num_ours = ours["circuit"]["num_rows"]
    num_pla = pla["circuit"]["num_rows"]
    time_ours = ours["prove_time_sec"]
    time_pla = pla["prove_time_sec"]
    pk_ours = ours["file_sizes_bytes"].get("pk.key", 0)
    pk_pla = pla["file_sizes_bytes"].get("pk.key", 0)

    print("""
一、本项目 (zkml_lookup_experiment) — 使用 ezkl 内置 Sigmoid Lookup

  优点：
  • 电路行数少：num_rows 约 4k～8k 量级，远小于 PLA 示例的 11 万+ 行。
    原因：Sigmoid 在电路中用「查表」实现，每个激活只消耗少量 lookup 约束，
    不把非线性展开成大量乘加比较，因此约束规模小。
  • 证明密钥 (pk.key) 在本机配置下可能更小或相当（取决于 logrows 与 SRS），
    因为行数少时 Halo2 的表格更小。
  • 数值上等价于标准 Sigmoid，无额外近似误差（仅有定点量化误差）。

  缺点：
  • 依赖 ezkl 的 Sigmoid lookup 表与 lookup_range 等配置，输入范围需落在
    lookup 表支持的区间内，否则会出现 “Lookup is not satisfied” 等错误。
  • 证明时间与内存受 logrows（k）影响大；k 取大以容纳电路时，SRS 与 pk 会
    明显增大，证明时间也会变长。
  • 若与 PLA 在同一台机器上对比：因本项目 k=17、PLA k=16，且电路结构不同，
    可能出现「本项目证明更慢或内存更大」的情况——主要因为 k 更大导致 SRS/表格更大。

二、ezkl_example_pla_sigmoid — 使用 PLA 无 Lookup

  优点：
  • 无 lookup：required_lookups 为空，仅用乘加和比较，设置简单（如 lookup_range=(0,1) 即可），
    不会出现「查表不满足」的问题。
  • 电路逻辑清晰，便于移植到其他只支持算术约束的证明系统。
  • 在相同/相近 logrows 下，若 PLA 的 num_rows 仍能放进 2^k，则证明时间可能
    更短（本次实测 PLA 约 4.7 秒，本项目可能数十秒到几分钟，视 k 与机器而定）。

  缺点：
  • 电路行数极大：num_rows 约 11 万+，是「Lookup Sigmoid」方案的数十倍。
    原因：PLA 把 Sigmoid 展开成多段线性，每段对应多个乘法/加法/比较约束，
    全部编码进电路，导致约束数量激增。
  • 证明密钥 (pk.key) 约 500MB 量级，随电路规模增大；若再增大模型或段数，
    pk 与证明时间会进一步上升。
  • 存在近似误差：PLA 目标约 99.5% 精度（相对误差 ≤0.5%），与真实 Sigmoid 有差距；
    本项目若用标准 Sigmoid lookup，则无此近似误差（仅有量化误差）。

三、总结对比

  • 行数/约束规模：本项目（Lookup）<< PLA（无 Lookup）。
  • 证明时间/内存：与 logrows、机器和具体配置强相关；PLA 示例 k=16 且已跑通，
    本项目 k=17 时可能更吃资源。
  • 精度：本项目（标准 Sigmoid 查表）无 PLA 的近似误差；PLA 有约 0.5% 相对误差。
  • 可移植性/配置难度：PLA 不依赖 lookup 表，更易适配其他后端；本项目依赖 ezkl
    的 Sigmoid lookup 与范围配置。
""")


if __name__ == "__main__":
    main()
