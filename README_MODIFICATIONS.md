# Modifications Summary (Ezkl_Change)

This document describes **all changes made** in this fork of [ezkl](https://github.com/zkonduit/ezkl). It is intended for readers (including AI) who need a concise overview of what was implemented and where.

---

## 1. Overview

The fork adds **custom lookup table** support so that ONNX **Sigmoid** can be implemented using a user-supplied piecewise-linear (PWL) mapping loaded from a file, instead of the built-in Sigmoid lookup table. All changes are backward-compatible: if no custom path is set, behavior matches upstream ezkl.

---

## 2. Summary of Modifications

| Area | Change |
|------|--------|
| **RunArgs** | New optional field `custom_lookup_path: Option<String>`. |
| **PyRunArgs** | Same field added; serialization/deserialization and Python get/set supported. |
| **LookupOp** | New variant `Custom { scale: utils::F32, path: String }` with PWL load and forward logic. |
| **ONNX → circuit** | "Sigmoid" branch: when `run_args.custom_lookup_path` is `Some(path)`, emit `LookupOp::Custom` instead of `LookupOp::Sigmoid`. |
| **Circuit layout** | Confirmed and documented that `region.add_used_lookup` and table layout work for Custom without special handling. |
| **Build** | Removed `staticlib` from `crate-type` to avoid CFFI codegen that exports `i128` (invalid in C). |
| **Docs** | Added `README_EZKL_CHANGES.md` (usage in Chinese) and this file (modifications in English). |

---

## 3. Code Changes by File

### 3.1 RunArgs and PyRunArgs

- **`ezkl/src/lib.rs`**
  - Added `custom_lookup_path: Option<String>` to `RunArgs` with `#[serde(default)]`.
  - Set `custom_lookup_path: None` in `Default::default()` for `RunArgs`.

- **`ezkl/src/bindings/python.rs`**
  - Added `custom_lookup_path: Option<String>` to `PyRunArgs` with `#[pyo3(get, set)]`.
  - Updated `From<PyRunArgs> for RunArgs` and `Into<PyRunArgs> for RunArgs` to include `custom_lookup_path`.

### 3.2 LookupOp::Custom and PWL

- **`ezkl/src/circuit/ops/lookup.rs`**
  - Introduced `LookupOp::Custom { scale: utils::F32, path: String }`.
  - Added `PwlParams` (deserialize from JSON: `breakpoints`, `slopes`, `intercepts`), `load_pwl_from_path(path)`, and `apply_pwl(x, scale_mult, pwl)`.
  - In `LookupOp::f()`: for `Custom`, load PWL from `path` and apply it to the integer-scaled input; return quantized integer tensor (same as other lookup ops).
  - **Fix for prove stall**: added thread-local cache `PWL_CACHE` and `get_pwl_cached(path)` so that PWL JSON is loaded from disk only once per path per thread. Without this, every call to `f()` (e.g. during table layout and `get_first_element`) re-read the file; during prove the circuit is re-synthesized so layout and constraints run again, causing repeated file I/O and PWL application and stalling the prover. Now the first call loads and caches; subsequent calls reuse the cached params.
  - **Later**: PWL cache was changed from thread-local to global `lazy_static! + Mutex<HashMap>` so that prover worker threads reuse the same cache.
  - **Prove FFT hang**: In Python embedding, halo2’s FFT phase uses rayon; together with the GIL this can deadlock. **Fix**: set `RAYON_NUM_THREADS=1` before importing ezkl (e.g. in `run_ezkl_full.py` via `os.environ.setdefault("RAYON_NUM_THREADS", "1")`). See **PROVE_TIMING.md**.
  - Implemented `as_path()`, `as_string()`, and the corresponding branches in `Op` for `Custom`.

### 3.3 ONNX Sigmoid → Custom

- **`ezkl/src/graph/utilities.rs`**
  - In `new_op_from_onnx`, for the `"Sigmoid"` branch: if `run_args.custom_lookup_path` is `Some(path)`, return `SupportedOp::Nonlinear(LookupOp::Custom { scale, path })`; otherwise return the existing `LookupOp::Sigmoid { scale }`.

### 3.4 Circuit layout and table

- **`ezkl/src/circuit/ops/layouts.rs`**
  - In `nonlinearity()`, added a comment that `region.add_used_lookup(nl, values[0])` supports all `LookupOp` variants including `Custom` (no extra logic required).

- **`ezkl/src/circuit/table.rs`**
  - Comment above `gen_table()`: table content is produced by `nonlinearity.f()`; for `LookupOp::Custom` this loads PWL from the file path—no special initialization.
  - When generating the table without cache, if the op is `LookupOp::Custom`, log an info message with the path and the integer range used.

### 3.5 Build / tooling

- **`ezkl/Cargo.toml`**
  - `crate-type` changed from `["cdylib", "rlib", "staticlib"]` to `["cdylib", "rlib"]`.
  - Reason: with `staticlib`, maturin generated CFFI bindings whose C header exported `IntegerRep` (i128). Standard C has no `i128`, so pycparser failed when generating CFFI declarations. Removing `staticlib` avoids that path.

- **`ezkl/pyproject.toml`**
  - No permanent change. An attempt to set `[tool.maturin] bindings = "pyo3"` was reverted because it caused an “unknown binding type” error in the installed maturin version.

---

## 4. Documentation Added

- **`README_EZKL_CHANGES.md`** (in this folder): Usage guide in Chinese—PWL JSON format, how to set `custom_lookup_path` from Python or JSON, typical workflow, code locations, and notes. Aimed at users and AI that need to use the new custom lookup feature.
- **`README_MODIFICATIONS.md`** (this file): High-level list of what was changed and where, in English, for readers who need a modification summary.

---

## 5. Behaviour Summary

- **Without** `custom_lookup_path`: Same as upstream; ONNX Sigmoid uses the built-in `LookupOp::Sigmoid` lookup table.
- **With** `custom_lookup_path` set (e.g. to a PWL JSON path): ONNX Sigmoid is compiled as `LookupOp::Custom`; at layout time the table is filled by loading that JSON and applying the PWL mapping over the configured integer range. The same table/layout pipeline is used as for other lookup ops.

For detailed usage, PWL JSON schema, and code references, see **README_EZKL_CHANGES.md**.
