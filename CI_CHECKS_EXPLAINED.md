# ezkl-custom-lookup / Fork 上 CI 检查说明

## 你看到的现象

- **4 failing**（4 个失败）
- **1 in progress**（1 个进行中）
- **1 successful**（1 个成功）
- **2 queued**（2 个排队）
- **9 skipped**（9 个跳过）

## 主要原因：Fork/个人仓库没有官方自托管 Runner

ezkl 官方 CI（`.github/workflows/rust.yml` 等）里大量 job 使用的是 **组织自托管 / 专用 Runner**，而不是 GitHub 自带的 `ubuntu-latest`：

| Runner 类型           | 用途示例                         | 在 Fork/个人仓库 |
|----------------------|----------------------------------|------------------|
| `ubuntu-22.04`       | build, docs, library-tests       | ✅ 会跑          |
| `large-self-hosted`  | fr-age-test, python-integration  | ❌ 无此 runner → 失败/跳过 |
| `gpu`                | GPU 测试、prove-and-verify-gpu   | ❌ 无此 runner   |
| `[non-gpu, non-sgx]` | mock-proving, prove-and-verify 等 | ❌ 无此 runner   |
| `self-hosted`        | benchmarks.yml                   | ❌ 无此 runner   |

因此在 **changshenhan/ezkl-custom-lookup**（或从 zkonduit/ezkl fork 出来的仓库）里：

- 只有使用 **GitHub 提供** 的 runner（如 `ubuntu-22.04`、`ubuntu-latest`）的 job 能真正执行。
- 依赖 `gpu`、`large-self-hosted`、`non-gpu`、`self-hosted` 等的 job 会 **失败**（找不到 runner）或 **被跳过**。

所以你看到的 **“4 failing”** 很大概率是这类 **“No runner / Job not run”** 的失败，**不是你这边的代码或测试用例失败**。

## 建议你怎么看

1. **点开那 4 个失败的 check**  
   看具体失败原因是否是：
   - `"No runner available"` / `"Waiting for a runner"` 一直不分配 → 就是上面说的 runner 限制。
2. **看那 1 个成功的 check**  
   通常是 **build** 或 **library-tests** 或 **docs**（它们用 `ubuntu-22.04`）。  
   若这些是绿的，说明在当前代码下，**能在 GitHub 标准环境里编译、通过文档和库测试**。
3. **若某个失败是真实测试失败**（例如 `cargo nextest run ...` 报错）  
   把该 job 的 **完整日志**（尤其是失败的那一步）贴出来，再针对具体测试修代码。

## 若你要向官方提 PR（zkonduit/ezkl）

- 官方仓库 **有** 自托管 runner，PR 合并后会在他们那边跑完整 CI。
- 你在 fork 上看到的部分失败 **不会** 阻止维护者合并；他们主要看的是能在他们 CI 里跑过的那部分（以及 code review）。
- 若维护者要求“所有 check 都过”，他们一般会自己在主仓库或 fork 上触发 run，不会以你 fork 上的 runner 缺失为理由拒绝 PR。

## 小结

| 情况                     | 含义 |
|--------------------------|------|
| 失败原因是 “No runner” / 长时间 Waiting | Fork 没有自托管 runner，**属预期，可忽略**。 |
| 成功的是 build / library-tests / docs   | 说明在标准 Linux 下 **编译和基础测试通过**。 |
| 失败是具体测试断言/panic/编译错误       | 需要根据日志 **改代码或修测试**。 |

如果你把其中某一个失败 job 的 **名字 + 失败原因（或日志最后几行）** 发出来，我可以帮你判断是 runner 问题还是真实测试失败，并给出下一步修改建议。
