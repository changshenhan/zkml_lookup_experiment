# PLA 项目 vs ezkl 原版 Sigmoid 查表 — 对比报告

本仓库对比两种在 ezkl 中实现 Sigmoid 的方式：

| 方案 | 说明 |
|------|------|
| **ezkl 原版 Sigmoid 查表** | ONNX 使用 `nn.Sigmoid()`，电路里由 ezkl 内置 lookup 表实现（查表约束） |
| **PLA（分段线性近似）** | ONNX 使用多段线性 `y = k_i·x + b_i` 替代 Sigmoid，电路里仅乘加/比较，无 lookup |

---

## 一、电路与运行参数对比

（数据来源：`metrics_ours.json`（查表）与 `ezkl_example_pla_sigmoid/metrics_pla.json`（PLA），在相同机器上运行 `eval_metrics.py` / `run_metrics.py` 得到。）

| 指标 | ezkl 原版 Sigmoid 查表 | PLA（无 Lookup） |
|------|------------------------|------------------|
| **logrows (k)** | 17 | 16 |
| **num_rows（电路行数）** | 4,385 | 112,661 |
| **total_assignments** | 8,770 | 112,661 |
| **required_lookups** | Sigmoid (scale=128) | 无（空） |
| **pk.key 大小** | ~1.15 GB | ~493 MB |
| **vk.key 大小** | ~802 KB | ~426 KB |
| **proof 大小** | ~51 KB | ~45 KB |
| **network.compiled 大小** | ~7 KB | ~35 KB |

---

## 二、证明时间与内存对比

| 指标 | ezkl 原版 Sigmoid 查表 | PLA（无 Lookup） |
|------|------------------------|------------------|
| **单次 prove 耗时** | **9.31 秒** | **4.69 秒** |
| **证明时间差距** | 基准 | PLA 约快 **49.7%**（约快 4.6 秒） |
| **峰值内存 (RSS)** | ~1.70 GB | ~1.19 GB |
| **内存差距** | 基准 | PLA 约少 **32.8%**（约少 517 MB） |

说明：查表方案 logrows=17（2^17 行），PLA 为 logrows=16；查表方案 SRS/表格更大，单次 prove 更耗时、内存更高。

---

## 三、证明精度对比

| 方面 | ezkl 原版 Sigmoid 查表 | PLA（无 Lookup） |
|------|------------------------|------------------|
| **Sigmoid 实现** | 内置 (input→output) 查表，scale=128 | 多段线性拟合 σ(x) ≈ k_i·x + b_i |
| **相对真实 Sigmoid 的误差** | 仅有**定点量化误差**（由 scale 决定，约 1/128 量级） | **相对误差 ≤ 0.5%**（即 ≥99.5% 精度，在拟合区间如 [-2,2] 内） |
| **精度结论** | 数值上更接近标准 Sigmoid | 有约 0.5% 的近似误差，可接受于多数应用 |

---

## 四、小结

- **电路规模**：查表方案 num_rows 远小于 PLA（4k vs 11 万+），但查表方案使用 logrows=17，证明密钥 pk.key 更大（~1.15 GB vs ~493 MB）。
- **证明时间**：PLA 在本机实测中**更快**（4.69 s vs 9.31 s），约快 50%。
- **内存占用**：PLA 峰值内存更低（约 1.19 GB vs 1.70 GB）。
- **精度**：查表方案仅有量化误差；PLA 有约 0.5% 相对误差，精度略逊于查表。

复现方式：

1. **查表方案**：在项目根目录运行 `python run_ezkl_full.py`，再运行 `python eval_metrics.py` 得到 `metrics_ours.json`。
2. **PLA 方案**：进入 `ezkl_example_pla_sigmoid`，运行完整 ezkl 流程后执行 `python run_metrics.py` 得到 `metrics_pla.json`。
3. 运行 `python compare_with_pla.py` 可再次打印对比表（依赖上述两个 JSON）。
