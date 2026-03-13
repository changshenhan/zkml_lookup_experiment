# Custom Lookup 下 prove 超时 — 排查清单

已确认：Custom PWL 时 `ezkl.prove()` 在 90 秒内不返回（超时被强制结束）；原版 Sigmoid 查表约 10 秒。说明问题在 **Custom 路径**，不是“证明本来就慢”。

结合 **README_MODIFICATIONS.md** 的修改点，按下面顺序排查。

---

## 1. 超时脚本已修复

`diagnose_prove.py` 里对 `TimeoutExpired` 已用 `getattr(e, "process", None)`，避免 Python 3.12 无 `process` 属性报错。可重复跑：

```bash
python diagnose_prove.py --timeout 90
```

确认 90 秒后能正常打印「prove 超时」并退出。

---

## 2. 在 ezkl 修改版里重点查的代码

### 2.1 表生成与 prove 是否重复建表 / 极慢

**README_MODIFICATIONS §3.4**：table 内容由 `nonlinearity.f()` 生成；Custom 时从文件加载 PWL 并施加到整数范围。

- **`ezkl/src/circuit/table.rs`**  
  - `gen_table()` 或建表逻辑里：Custom 是否在 **每次 prove** 时都重新读 JSON、重新建整张表？  
  - 若 prove 内层循环或多次调用建表，会导致极慢。  
  - 期望：表在 **layout/setup** 时建一次，prove 只读已建好的表或缓存。

### 2.2 LookupOp::Custom 的 f() 与约束是否一致

**README_MODIFICATIONS §3.2**：`LookupOp::f()` 里对 Custom 加载 PWL 并 `apply_pwl`，返回量化整数。

- **`ezkl/src/circuit/ops/lookup.rs`**  
  - `LookupOp::Custom` 的 `f()`：输入 scale、PWL 的 breakpoints/slopes/intercepts 是否与 **约束里用的 scale/表** 完全一致？  
  - 若 `gen_witness` 或填表时用一套 scale/量化，prove 约束用另一套，会约束不满足或 prover 行为异常（看起来像卡住）。  
  - 确认：**建表** 与 **prove 里 lookup 约束** 使用同一 `scale`、同一 PWL 结果（同一 `apply_pwl` 实现）。

### 2.3 Witness 来源：是否用 Custom 表

**README_MODIFICATIONS §5**：设了 `custom_lookup_path` 后，Sigmoid 被编译成 `LookupOp::Custom`，layout 时表由该 PWL 填充。

- 需要确认：**gen_witness**（或所有“跑 forward 填 witness”的入口）用的是 **已编译的 circuit** 还是 **原始 ONNX**？  
  - 若用 **compiled circuit**：lookup 输出应来自当前表的 PWL，witness 与约束一致。  
  - 若用 **ONNX**：Sigmoid 仍是标准 1/(1+e^-x)，witness 与 Custom 表不一致 → 约束不满足 → prove 可能一直尝试满足或异常慢。  
- 在 ezkl 里搜：`gen_witness`、witness 生成、forward 执行；确认走的是 circuit + 已建好的 Custom 表，而不是 ONNX 的默认 Sigmoid。

### 2.4 Prove 里 lookup 约束对 Custom 的分支

- **`ezkl/src/circuit/ops/layouts.rs`**  
  - `nonlinearity()` 里 `region.add_used_lookup(nl, values[0])` 对 Custom 是否有分支或特殊逻辑？  
- 若 prove 时对 `LookupOp::Custom` 走了不同路径（例如多一层循环、或错误地多次求值），可能造成卡住或极慢。  
- 对比：**Sigmoid** 与 **Custom** 在 prove 中是否同一套 lookup 约束、仅表数据不同。

### 2.5 日志

**README_MODIFICATIONS §3.4**：生成表时（无缓存）若为 Custom 会打 info 日志（path + 整数范围）。

- 运行时加 **RUST_LOG=info**（或 ezkl 使用的 log 环境变量），看：  
  - 是否在 **prove** 阶段重复打印 Custom path / 建表相关日志（若重复很多次，说明 prove 里在重复建表或重复求值）；  
  - 表生成时的整数范围与 `lookup_range` 是否一致。

---

## 3. 本仓库侧可做的检查

- **PWL 与 scale**  
  - `pwl_params_64.json` 的 breakpoints/slopes/intercepts 为浮点；ezkl 用 scale=128 量化。  
  - 确认 `build_lookup_table.py` 生成的区间覆盖 `lookup_range`（例如 [0,128] 对应 scale 7 的浮点范围），避免表外访问。

- **对比 --no-custom**  
  - 运行：`python diagnose_prove.py --no-custom --timeout 30`  
  - 若 30 秒内 prove 完成且 verify 通过，可进一步确认问题仅在 Custom 路径。

---

## 4. 小结

| 怀疑点 | 位置 | 行动 |
|--------|------|------|
| prove 时重复建表或重复求值 | table.rs, 或 prove 调用链 | 确认表只在 setup/layout 建一次；prove 只读表 |
| **Custom 每次 f() 都读文件** | **lookup.rs** | **已修复：增加 thread-local PWL 缓存 get_pwl_cached()，同路径只读一次。** |
| scale / 量化与约束不一致 | lookup.rs `apply_pwl` vs 约束 | 对齐 Custom 的 scale 与量化方式 |
| witness 用 ONNX Sigmoid 而非 Custom 表 | witness 生成入口 | 改为用 circuit + Custom 表填 witness |
| Custom 在 prove 中走错分支或死循环 | layouts.rs, prove 中 lookup 分支 | 对比 Sigmoid 与 Custom 的 prove 路径，加日志 |

**已做修改（Ezkl_Change/ezkl/src/circuit/ops/lookup.rs）**：为 `LookupOp::Custom` 增加 PWL 线程本地缓存，避免 prove 时每次 `f()` / `get_first_element` 都重新读 JSON 和计算，从而消除卡住。修改后需在 Ezkl_Change 中重新编译并安装 ezkl Python 包（如 `maturin develop`），再在 zkml_lookup_experiment 中跑 `run_ezkl_full.py` 或 `diagnose_prove.py --timeout 90`。
