# Comparison: ezkl Sigmoid Lookup vs PLA

This document summarizes the difference between the two approaches. Data comes from `metrics_ours.json` (lookup) and `ezkl_example_pla_sigmoid/metrics_pla.json` (PLA). Re-run `eval_metrics.py` and `ezkl_example_pla_sigmoid/run_metrics.py` to regenerate.

---

## 1. Circuit and run parameters

| Metric | ezkl Sigmoid lookup | PLA (no lookup) |
|--------|---------------------|------------------|
| **logrows (k)** | 17 | 16 |
| **num_rows** | 4,385 | 112,661 |
| **total_assignments** | 8,770 | 112,661 |
| **required_lookups** | Sigmoid (scale=128) | none |
| **pk.key** | ~1.15 GB | ~493 MB |
| **vk.key** | ~802 KB | ~426 KB |
| **proof size** | ~51 KB | ~45 KB |
| **network.compiled** | ~7 KB | ~35 KB |

---

## 2. Prove time and memory

| Metric | ezkl Sigmoid lookup | PLA (no lookup) |
|--------|---------------------|------------------|
| **Prove time (1 run)** | 9.31 s | 4.69 s |
| **Speed difference** | baseline | PLA ~50% faster |
| **Peak memory (RSS)** | ~1.70 GB | ~1.19 GB |
| **Memory difference** | baseline | PLA ~33% less |

Lookup uses logrows=17 (larger SRS/table), so prove time and memory are higher in this setup.

---

## 3. Accuracy vs true Sigmoid

| Aspect | ezkl Sigmoid lookup | PLA (no lookup) |
|--------|---------------------|------------------|
| **Implementation** | Built-in (input→output) table, scale=128 | Piecewise linear σ(x) ≈ k_i·x + b_i |
| **Error vs true σ(x)** | Only fixed-point quantization (~1/128) | Relative error ≤ 0.5% (≥99.5% over range, e.g. [-2,2]) |
| **Conclusion** | Closer to standard Sigmoid | Small approximation error; fine for many uses |

---

## 4. Summary

- **Circuit size:** Lookup has far fewer rows (4k vs 113k) but uses logrows=17, so pk.key is larger (~1.15 GB vs ~493 MB).
- **Prove time:** PLA is faster in this run (~4.7 s vs ~9.3 s).
- **Memory:** PLA uses less peak memory (~1.2 GB vs ~1.7 GB).
- **Accuracy:** Lookup has only quantization error; PLA has ~0.5% relative error.

To reproduce: run the lookup pipeline and `eval_metrics.py`, then the PLA pipeline and `run_metrics.py`; finally `python compare_with_pla.py` from the repo root.
