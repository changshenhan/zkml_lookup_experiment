# Custom Lookup 下 prove 卡住/过慢 说明

## 现象

- 原版 ezkl 内置 Sigmoid 查表：prove 约 **10 秒** 完成。
- 使用 **Custom PWL 查表**（`custom_lookup_path`）时：prove 长时间无返回，像卡死。

## 可能原因（不是“证明本身就要很久”）

1. **Witness 与电路不一致**  
   - 电路里 Sigmoid 被替换成 **Custom PWL 查表**，约束的是 PWL 输出。  
   - 若 **gen_witness** 时用的仍是 **ONNX 默认 Sigmoid**（1/(1+e^-x)）算激活值，而电路按 PWL 表查表，则 witness 里的激活值与电路约束不一致 → 约束不满足。  
   - 在这种不一致下，prover 可能一直尝试满足不可能满足的约束，表现为 **prove 卡住或极慢**，而不是立刻报错。

2. **修改版 ezkl 的 Custom 路径有 bug**  
   - prove 阶段对 `LookupOp::Custom` 的处理可能有死循环、异常大的计算量或未优化路径，导致只在使用 Custom 时变慢/卡住。

3. **表/scale 不一致**  
   - Custom 使用与其它 lookup 一致的 scale（如 128）；若 PWL 文件与 ezkl 的 scale/量化方式不一致，也可能导致约束或表查找异常，进而 prove 异常。

## 建议诊断步骤

### 1. 用超时确认是否“跑不通”

```bash
# 用当前 Custom 设置，只跑 prove，最多等 90 秒
python diagnose_prove.py --timeout 90
```

- 若 90 秒内 **未返回**：说明 prove 在当前 Custom 设置下确实卡住/极慢，而不是“再等等就能出来”。
- 若 **返回且 verify 通过**：说明能跑通，只是比内置 Sigmoid 慢。
- 若 **返回但 verify 失败**：说明生成了证明但约束不对，多半是 witness 与 Custom 表不一致。

### 2. 对比：不用 Custom 时是否仍 ~10 秒

```bash
# 用内置 Sigmoid 重做 settings/compile/witness/setup/prove（不设 custom_lookup_path）
python diagnose_prove.py --no-custom --timeout 30
```

- 若 **--no-custom** 时 prove 约 **10 秒内完成且 verify 通过**，而带 Custom 时超时或极慢 → 基本可判断问题在 **Custom 路径**（witness 不一致或 Custom 实现 bug）。
- 若 --no-custom 时也很慢 → 更可能是环境/机器或通用 prove 性能问题。

### 3. 在修改版 ezkl 里确认 witness 是否用 Custom 表

在 ezkl 源码中确认：

- **gen_witness**（或跑 forward 填 witness 的代码）在遇到图中 “Sigmoid” 节点时，是否使用了与 **circuit 相同的 Custom PWL**（同一 `custom_lookup_path`、同一 scale）计算激活值。  
- 若 witness 仍用 ONNX 默认 Sigmoid 实现，则必须改为用 Custom PWL 的 `f()`（或同一套 PWL 表）计算，才能与电路一致，prove 才能正常完成且不卡。

## 小结

- 原版 Sigmoid 查表 ~10 秒、Custom 时“像卡死”，**不像是“证明时间本来就长”**，更像是 **prove 跑不通**（约束不满足或 Custom 路径异常）。  
- 先跑 `diagnose_prove.py` 确认是否超时、verify 是否通过；再跑 `--no-custom` 对比；最后在 ezkl 修改版里确认 **witness 生成是否与 Custom 表一致**。
