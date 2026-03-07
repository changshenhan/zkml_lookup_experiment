# zkML: Sigmoid Lookup vs PLA Comparison

This repository compares two ways to implement **Sigmoid** in [ezkl](https://github.com/zkonduit/ezkl) (zero-knowledge ML):

1. **ezkl built-in Sigmoid lookup** — one `nn.Sigmoid()` in ONNX; the circuit uses ezkl’s internal lookup table.
2. **PLA (piecewise linear approximation)** — Sigmoid is replaced by piecewise linear segments (mul/add/compare only); no lookup in the circuit.

**Author:** [changshenhan](https://github.com/changshenhan)

---

## What’s in this repo

| Item | Description |
|------|-------------|
| **Lookup approach** | `gen.py`, `run_ezkl_full.py`, `build_lookup_table.py`, `eval_metrics.py` — export ONNX with a single Sigmoid and run the full ezkl pipeline with lookup. |
| **PLA approach** | `ezkl_example_pla_sigmoid/` — PLA Sigmoid (no lookup); see that folder’s README. |
| **Comparison** | `compare_with_pla.py` prints a side-by-side comparison. Pre-computed metrics: `metrics_ours.json` (lookup) and `ezkl_example_pla_sigmoid/metrics_pla.json` (PLA). |

---

## Comparison summary

(Data from one machine; run `eval_metrics.py` and `ezkl_example_pla_sigmoid/run_metrics.py` to regenerate.)

| Metric | ezkl Sigmoid lookup | PLA (no lookup) |
|--------|---------------------|------------------|
| **Circuit rows (`num_rows`)** | ~4.4k | ~113k |
| **Lookups** | Sigmoid table | None |
| **Prove time** | ~9.3 s | ~4.7 s |
| **Peak memory** | ~1.7 GB | ~1.2 GB |
| **Accuracy vs true Sigmoid** | Quantization only (~1/128) | ~0.5% relative error (≥99.5% over range) |

- **Lookup**: smaller circuit, no PLA approximation error, but longer prove time and higher memory in this setup (larger `logrows`).
- **PLA**: faster prove and less memory here, with a small approximation error.

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
├── build_lookup_table.py     # Build lookup_table.json (for lookup_range)
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

Generated files (not committed): `network.onnx`, `input.json`, `settings.json`, `lookup_table.json`, `data.json`, `pk.key`, `vk.key`, `*.srs`, `witness.json`, `proof*.json`, `network.compiled`, etc. See `.gitignore`.

---

## How to run

**Requirements:** Python 3, [ezkl](https://github.com/zkonduit/ezkl), PyTorch (for `gen.py`).

### Lookup approach

```bash
# 1. Build lookup table (requires data.json with "input_data": list of float arrays for input range)
python build_lookup_table.py

# 2. Export ONNX and input
python gen.py

# 3. Run full ezkl pipeline (settings, compile, witness, setup, prove, verify)
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
