# Custom PWL 证明生成为什么可能比原版 Sigmoid 慢？

## 根本原因：FFT 阶段 rayon 与 Python GIL 死锁

**原因**：halo2 / ezkl 在证明的 **FFT / 多项式承诺** 阶段使用 **rayon** 做并行计算。在 **Python 嵌入**（通过 maturin 编译的 .so 被 Python 调用）时，主线程持有 **Python GIL**，rayon 工作线程若再触发需要 GIL 的路径或与主线程存在锁竞争，就会 **死锁**，表现为 synthesize 已打完 “main region: done.” 后进程卡住、永远等不到 “create_proof returned”。

**解决**：在 **导入 ezkl 之前** 设置 **`RAYON_NUM_THREADS=1`**，让 FFT 只跑单线程，避免与 GIL/多线程的交互，证明即可在约 10 秒量级内完成。

- **`run_ezkl_full.py`** 已在脚本开头（`import ezkl` 之前）执行 `os.environ["RAYON_NUM_THREADS"] = "1"`，直接运行 `python run_ezkl_full.py` 即可。运行时会打印 `RAYON_NUM_THREADS = 1` 以确认。
- **单线程 FFT 耗时**：设为 1 后，FFT 只跑单核，**可能需 1～2 分钟**（视电路规模而定）。若已看到 “main region: done.”，请**至少再等 1～2 分钟**看是否出现 “create_proof returned” 和 “证明生成完成”，不要只等 10 秒就判定卡死。
- 若用其他脚本调用 ezkl，请在 import ezkl 前设置：`import os; os.environ["RAYON_NUM_THREADS"] = "1"`，或命令行：`RAYON_NUM_THREADS=1 python your_script.py`。

---

## FFT/证明阶段卡住（已出现 main region: done. 但无 create_proof returned）

若日志里已经出现 **`[ezkl] main region: done.`**，且长时间没有 **`[ezkl] halo2 create_proof returned.`**，说明卡在 **halo2 create_proof 的 FFT/多项式承诺阶段**（synthesize 之后、无我们自己的进度输出）。

### 可能原因

- **Rayon 线程池**：halo2/依赖里用 rayon 做并行 FFT，在部分环境（如 macOS、某些 Python 嵌入）下可能死锁或长时间阻塞。
- **内存**：FFT 会占用较多内存，若机器内存不足导致大量 swap，会看起来像卡住。

### 排查步骤

**1. 强制单线程（排除 rayon 死锁）**

用单线程跑 prove，若不再卡住，多半与并行有关：

```bash
cd /Users/songlvhan/Desktop/zkml_lookup_experiment
# 仅 prove 一步用单线程（若已有 settings/compiled/witness/pk/srs）
RAYON_NUM_THREADS=1 python -c "
import ezkl
ezkl.prove('witness.json', 'network.compiled', 'pk.key', 'proof.json', 'kzg16.srs')
print('prove done')
"
```

或整条流程都用单线程：

```bash
RAYON_NUM_THREADS=1 python run_ezkl_full.py
```

本仓库也提供脚本（可先 `chmod +x run_ezkl_full_single_thread.sh`）：

```bash
./run_ezkl_full_single_thread.sh
```

**2. 看进程是否在算（区分“很慢”和“真卡死”）**

- macOS：活动监视器里看该 Python 进程的 **CPU 使用率**。若持续 >0%（例如 80%～100%），多半是 FFT 在算、只是慢。
- 终端：`top -pid $(pgrep -f "python run_ezkl")` 看 CPU。若长时间 0%，更可能是死锁。

**3. 内存不足时**

- 关掉其它占内存的程序，或减小规模（例如用更小模型 / 更小 logrows 再试）。

---

## 若 prove 一直卡住（不报错也不结束）

### 不重新编译时（先看这步）

`run_ezkl_full.py` 会在调用 `ezkl.prove()` **前后**各打一行：

- 若看到 **`[prove] 即将调用 ezkl.prove()（若卡住则说明卡在 Rust 内部）...`** 之后一直没反应，说明卡在 **Rust 的 prove 内部**（加载 circuit/witness、读 pk/SRS、或 halo2 create_proof）。

### 要看到具体卡在哪一步：必须重新编译 ezkl

`prove: witness loaded`、`prove: pk loaded` 等是写在 **ezkl 源码**里的，只有重新编译安装后才会出现。步骤：

```bash
cd /Users/songlvhan/Desktop/Ezkl_Change/ezkl
python -m maturin develop --release -b pyo3 -F python-bindings
```

再在实验目录用日志跑（跑 1～2 分钟可 Ctrl+C，看最后几行）：

```bash
cd /Users/songlvhan/Desktop/zkml_lookup_experiment
rm -f settings.json network.compiled
RUST_LOG=info python run_ezkl_full.py 2>&1 | tee prove_log.txt
```

**看 `prove_log.txt` 里最后一条 `prove:` 或 `proof` 相关日志：**

- 最后是 `prove: witness loaded` → 卡在 **加载 circuit**（bincode 反序列化 network.compiled）
- 最后是 `prove: circuit loaded` → 卡在 **load_graph_witness / prepare public_inputs**
- 最后是 `prove: public_inputs prepared` → 卡在 **load_pk**（读证明密钥）
- 最后是 `prove: pk loaded` → 卡在 **load_params_prover**（读 SRS，logrows=16 时可能较慢）
- 最后是 `prove: SRS loaded, calling create_proof_circuit` 且没有 `proof started...` → 卡在 **进入 create_proof 前**
- 最后是 `proof started...` → 卡在 **halo2 create_proof 内部**（FFT/多项式等）

把「最后一条相关日志」发出来，就可以针对性查（例如 SRS 太大、或 create_proof 里某步与 Custom 表有关）。

---

## 理论上不应更慢

- **Custom**：`lookup_range` 来自 `lookup_table.json` 的 x 范围（例如约 `(0, 257)`），查找表只有 **约 258 行**。
- **原版 Sigmoid**：默认 `lookup_range = (-32768, 32768)`，查找表有 **65536 行**。

所以 Custom 的查找表更小、logrows 相同时电路规模一致，prove 按理应接近或略快于原版。

## 可能原因

1. **用到了旧的编译产物**  
   若之前用「原版 Sigmoid」跑过并生成了 `settings.json` / `network.compiled`，再切到 Custom 时若没有重新 gen_settings + compile_circuit，可能仍在用旧的大电路。  
   **做法**：每次切到 Custom 后删掉 `settings.json` 和 `network.compiled`，再跑一次 `run_ezkl_full.py`，确保用当前 Custom 设置重新编译。

2. **首次运行 / 环境差异**  
   第一次 prove 或不同环境（CPU、内存）会导致时间差异，可多跑几次看中位数。

3. **logrows 实际更大**  
   `run_ezkl_full.py` 会根据 `num_rows` 反推 `logrows`（16～24）。若 Custom 的 `num_rows` 因布局不同而更大，logrows 会变大，prove 会明显变慢。  
   **做法**：看脚本打印的 `settings: num_rows=..., logrows=..., lookup_range=...`，和「原版 Sigmoid」跑一次对比是否一致。

## 建议操作

- 在 `zkml_lookup_experiment` 下先清掉旧产物再跑，并看终端里的 **prove 耗时** 和 **settings**：
  ```bash
  rm -f settings.json network.compiled
  python run_ezkl_full.py
  ```
- 若 Custom 的 `logrows` 与「原版 Sigmoid」一致、且已确认用新编译的 Custom 电路，prove 仍明显更慢，可把两边的 `settings.json`（或其中 `run_args` / `num_rows`）和 prove 耗时贴出来，便于进一步查（例如是否在某条代码路径上对 Custom 做了额外计算）。
