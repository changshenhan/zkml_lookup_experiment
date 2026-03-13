# Prove 卡住不返回的根因与修复

## 根本原因（两处）

### 1. Python 调用 prove 时未释放 GIL（主因）

- **现象**：从 Python 执行 `ezkl.prove(...)` 时，synthesize 能跑完（多次 "main region: done."），但**没有** "halo2 create_proof returned."，进程卡在 FFT/承诺阶段。
- **根因**：`ezkl` 的 **Python 绑定**在调用 `execute::prove` 时**没有释放 GIL**。证明内部（halo2）使用 **rayon** 做多线程 FFT，主线程在持锁状态下进入 Rust、再在 rayon 里阻塞等待 worker，容易与解释器/线程调度形成**死锁**（主线程持 GIL 阻塞、worker 无法推进或无法被正确调度）。
- **修复**：在 **Ezkl_Change/ezkl/src/bindings/python.rs** 的 `prove` 里，用 **`py.allow_threads(|| { ... })`** 包裹 `crate::execute::prove(...)`，使整个证明过程在**无 GIL** 下执行，rayon 多线程即可正常跑完，证明能在秒级完成。

### 2. RAYON_NUM_THREADS=1 会触发单线程池死锁

- 若把 `RAYON_NUM_THREADS` 设为 **1**，FFT 阶段在单线程 rayon 池内仍可能死锁（主线程投任务并阻塞，池内唯一 worker 若再阻塞则无其它线程推进）。  
- **正确做法**：**不要设为 1**；不设则用系统默认多线程，证明更快且无此死锁。

## 已做修改

1. **Ezkl_Change/ezkl/src/bindings/python.rs**  
   - `prove` 中改为：`py.allow_threads(|| { crate::execute::prove(...) })`，证明期间释放 GIL。

2. **run_ezkl_full.py**  
   - 仅当环境变量为 `"1"` 时改为 `"2"`，否则不强制设置，以便多核跑 prove（秒级）。

3. **本文档**  
   - 说明根因是“Python 绑定未释 GIL”+“RAYON=1 死锁”，以及对应修复。
