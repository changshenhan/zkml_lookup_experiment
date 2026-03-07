# zkML Lookup vs PLA 实验

本仓库对比在 [ezkl](https://github.com/zkonduit/ezkl) 中实现 Sigmoid 的两种方式：**ezkl 原版 Sigmoid 查表** 与 **PLA（分段线性近似，无 Lookup）**，并给出电路参数、证明时间与精度对比。

- **作者 / Author**: [changshenhan](https://github.com/changshenhan)

---

## 方案简述

| 方案 | 说明 |
|------|------|
| **ezkl 原版 Sigmoid 查表** | ONNX 使用 `nn.Sigmoid()`，电路里由 ezkl 内置 lookup 表实现（查表约束）。 |
| **PLA** | ONNX 使用多段线性近似替代 Sigmoid，电路里仅乘加/比较，无 lookup（见子目录 `ezkl_example_pla_sigmoid`）。 |

---

## 对比数据概览

详细数据见 **[COMPARISON.md](./COMPARISON.md)**，包含：

- **电路参数**：logrows、num_rows、total_assignments、required_lookups、pk/vk/proof 大小等  
- **证明时间与内存**：单次 prove 耗时、峰值内存（RSS）  
- **证明精度**：查表方案为定点量化误差；PLA 为约 0.5% 相对误差（≥99.5% 精度）

简要结论（基于当前实测）：

- **证明时间**：PLA 更快（约 4.7 s vs 查表约 9.3 s）。  
- **电路行数**：查表方案更少（约 4k vs PLA 约 11 万行）。  
- **精度**：查表方案更接近标准 Sigmoid；PLA 有约 0.5% 近似误差。

---

## 目录结构

```
.
├── README.md              # 本说明
├── COMPARISON.md          # PLA vs ezkl 原版 Sigmoid 查表 完整对比
├── run_ezkl_full.py       # 查表方案：完整 ezkl 流程
├── gen.py                 # 查表方案：导出 ONNX（单 Sigmoid）
├── eval_metrics.py        # 查表方案：收集指标，生成 metrics_ours.json
├── compare_with_pla.py    # 读取两边 metrics，打印对比
├── build_lookup_table.py  # 生成 lookup_table.json（供 lookup_range 等使用）
├── DESIGN.md              # 分段查表 + 线性插值设计说明
├── ezkl_example_pla_sigmoid/   # PLA 示例（无 Lookup）
│   ├── README.md
│   ├── gen.py
│   ├── pwl_sigmoid.py
│   └── run_metrics.py     # 生成 metrics_pla.json
├── metrics_ours.json      # 查表方案指标（运行 eval_metrics.py 生成）
└── ezkl_example_pla_sigmoid/metrics_pla.json  # PLA 方案指标
```

---

## 如何复现

1. **环境**：安装 ezkl、PyTorch 等（见 ezkl 官方文档）。
2. **查表方案**：  
   `python gen.py` → `python run_ezkl_full.py` → `python eval_metrics.py`  
   得到 `metrics_ours.json`。
3. **PLA 方案**：  
   进入 `ezkl_example_pla_sigmoid`，按其中 README 跑完 ezkl 流程，再执行 `python run_metrics.py`  
   得到 `metrics_pla.json`。
4. **打印对比**：在项目根目录执行 `python compare_with_pla.py`。

---

## License

与 ezkl 及本仓库内引用示例保持一致；PLA 示例见 `ezkl_example_pla_sigmoid/README.md`。
