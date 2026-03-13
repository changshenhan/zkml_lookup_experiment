# zkML: Sigmoid Lookup vs PLA Comparison

This repository compares two ways to implement **Sigmoid** in [ezkl](https://github.com/zkonduit/ezkl) (zero-knowledge ML):

1. **ezkl built-in Sigmoid lookup** — one `nn.Sigmoid()` in ONNX; the circuit uses ezkl’s internal lookup table.
2. **PLA (piecewise linear approximation)** — Sigmoid is replaced by piecewise linear segments (mul/add/compare only); no lookup in the circuit.

**Author:** [changshenhan](https://github.com/changshenhan)

---

## What’s in this repo

| Item | Description |
|------|-------------|
| **Lookup approach** | `gen.py`, `run_ezkl_full.py`, `build_lookup_table.py`, `eval_metrics.py` — export ONNX with a single Sigmoid and run the full ezkl pipeline. **With a modified ezkl that supports custom lookup** (see **README_EZKL_CHANGES.md**), the pipeline uses a **custom PWL table** (`pwl_params.json`) instead of the built-in Sigmoid table. |
| **PLA approach** | `ezkl_example_pla_sigmoid/` — PLA Sigmoid (no lookup); see that folder’s README. |
| **Comparison** | `compare_with_pla.py` prints a side-by-side comparison. Pre-computed metrics: `metrics_ours.json` (lookup) and `ezkl_example_pla_sigmoid/metrics_pla.json` (PLA). |

---

## Comparison summary

(Data from one machine; run `eval_metrics.py` and `ezkl_example_pla_sigmoid/run_metrics.py` to regenerate.)

| Metric | ezkl Sigmoid lookup | PLA (no lookup) |
|--------|---------------------|------------------|
| **Circuit rows (`num_rows`)** | ~4.4k | ~113k |
| **Lookups** | Sigmoid table | None |
| **Accuracy vs true Sigmoid** | Quantization only (~1/128) | ~0.5% relative error (≥99.5% over range) |

- **Lookup**: much smaller circuit and no PLA approximation error.
- **PLA**: larger circuit but no lookup table; see `COMPARISON.md` for detailed trade‑offs.

> **Note on logrows and performance**  
> In the original numbers in `COMPARISON.md`, the lookup circuit used a conservative `logrows = 17`, which inflates SRS size and proving time.  
> With the more natural choice `logrows = ceil(log2(num_rows))` (here `k = 13` for `num_rows ≈ 4385`), both the built‑in Sigmoid lookup and the custom PWL lookup prove in about **1.1 s** on the same machine. The main contribution of the custom PWL table is therefore **numerical accuracy**, not asymptotic speed.
>
> **Single‑Sigmoid vs. model‑level accuracy (real data, same circuit/logrows)**  
> - On the Sigmoid *inputs themselves*, the custom PWL table achieves max error ≈ **5.4e‑11** and mean ≈ **5.6e‑12** w.r.t. true σ(x),  
>   whereas a quantized “default” lookup (input/output at 1/128) has max error ≈ **4.7e‑3** and mean ≈ **1.9e‑3**.  
> - On the **full model output** (the Conv+ReLU+Sigmoid branch), PWL keeps the average absolute error around **4.8e‑5** and max ≈ **1.8e‑4**,  
>   while the default lookup is around **1.8e‑3** mean and max ≈ **4.6e‑3**. In other words, for this toy model and data, the custom PWL improves end‑to‑end numerical accuracy by roughly **1–2 orders of magnitude** at essentially the same proving cost.

See **[COMPARISON.md](./COMPARISON.md)** for full tables (params, file sizes, accuracy).

---

## Repo layout

```
.
├── README.md                 # This file
├── COMPARISON.md             # Detailed comparison (params, time, accuracy)
├── .gitignore
├── gen.py                    # Export ONNX (single Sigmoid) for lookup approach
├── run_ezkl_full.py          # Full ezkl pipeline for lookup approach
├── build_lookup_table.py     # Build lookup_table.json + pwl_params.json (for custom lookup)
├── eval_metrics.py           # Collect metrics → metrics_ours.json
├── compare_with_pla.py       # Print comparison from metrics_ours.json vs metrics_pla.json
├── metrics_ours.json         # Saved metrics for lookup approach
└── ezkl_example_pla_sigmoid/
    ├── README.md
    ├── gen.py                # Export ONNX with PLA Sigmoid
    ├── pwl_sigmoid.py        # PLA Sigmoid module
    ├── run_metrics.py        # Collect metrics → metrics_pla.json
    └── metrics_pla.json      # Saved metrics for PLA approach
```

Generated files (not committed): `network.onnx`, `input.json`, `settings.json`, `lookup_table.json`, `pwl_params.json`, `data.json`, `pk.key`, `vk.key`, `*.srs`, `witness.json`, `proof*.json`, `network.compiled`, etc. See `.gitignore`.

---

## How to run

**Requirements:** Python 3, [ezkl](https://github.com/zkonduit/ezkl) (for **custom PWL lookup** you need a modified ezkl with `custom_lookup_path` support — see **README_EZKL_CHANGES.md**), PyTorch (for `gen.py`).

### Lookup approach (custom PWL table)

With the **modified ezkl** (see README_EZKL_CHANGES.md), the pipeline uses your **custom segmented lookup table** (non-uniform keypoints, `y = k_i*x + b_i` per segment) instead of the built-in Sigmoid table.

```bash
# 1. Build lookup table and PWL params (uses data.json if present; else default range [-2, 2])
python build_lookup_table.py
# → produces lookup_table.json and pwl_params.json

# 2. Export ONNX and input
python gen.py

# 3. Run full ezkl pipeline (uses custom_lookup_path=pwl_params.json)
python run_ezkl_full.py

# 4. Collect metrics (optional; overwrites metrics_ours.json)
python eval_metrics.py
```

### PLA approach

```bash
cd ezkl_example_pla_sigmoid
python gen.py
# Then run ezkl: gen_settings, compile_circuit, gen_witness, gen_srs, setup, prove, verify
python run_metrics.py   # writes metrics_pla.json
```

### Print comparison

From the repo root (after both `metrics_ours.json` and `ezkl_example_pla_sigmoid/metrics_pla.json` exist):

```bash
python compare_with_pla.py
```

---

## License

Use and attribution consistent with ezkl and the PLA example in `ezkl_example_pla_sigmoid/`.
