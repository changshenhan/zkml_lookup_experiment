# EZKL 本地修改说明与用法

本文档描述本仓库对 [ezkl](https://github.com/zkonduit/ezkl) 的**本地修改**，便于在其他文件或对话中的 AI 识别并正确使用这些扩展能力。

---

## 一、修改概览

在保留原有 ezkl 行为的前提下，增加了**自定义查找表（Custom Lookup）**支持：

- **RunArgs / PyRunArgs** 新增可选字段：`custom_lookup_path: Option<String>`
- **LookupOp** 新增变体：`Custom { scale, path }`，从文件加载分段线性（PWL）映射并用于查找表
- **ONNX Sigmoid**：当设置了 `custom_lookup_path` 时，图中的 Sigmoid 算子会被替换为上述 Custom 查找表，而不是默认的 Sigmoid 查找表

这样可以用**自定义 PWL 近似**（例如与 `examples/onnx/pla_sigmoid` 一致的分段线性）替代内置 Sigmoid 表，便于实验或与外部拟合结果对接。

---

## 二、使用方式

### 2.1 准备 PWL 参数文件（JSON）

Custom 查找表从**本地 JSON 文件**读取分段线性参数，格式如下：

```json
{
  "breakpoints": [ -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0 ],
  "slopes":      [ 0.1,  0.2,  0.25, 0.2,  0.25, 0.2, 0.25, 0.1 ],
  "intercepts":  [ 0.5,  0.6,  0.55, 0.6,  0.5,  0.4, 0.35, 0.2 ]
}
```

- **breakpoints**：长度 `n+1`，将实数轴分成 `n` 段。
- **slopes**、**intercepts**：长度均为 `n`。  
  对第 `i` 段（`breakpoints[i] <= x < breakpoints[i+1]`），输出为  
  `y = slopes[i] * x + intercepts[i]`。  
  在 `x < breakpoints[0]` 或 `x > breakpoints[n]` 时，用首段/末段的斜率和截距外推。

可与 `ezkl/examples/onnx/pla_sigmoid` 中的 PWL 拟合结果对应：用 Python 生成 `breakpoints/slopes/intercepts` 后，写成上述 JSON 即可。

### 2.2 在 Python 中指定自定义查找表路径

通过 **PyRunArgs** 设置 `custom_lookup_path`（不设置则保持原有行为，Sigmoid 仍用内置表）：

```python
import ezkl

run_args = ezkl.PyRunArgs()
# 指定自定义 PWL 表路径后，图中 ONNX Sigmoid 会使用该文件作为查找表
run_args.custom_lookup_path = "/path/to/pwl_params.json"

# 例如生成 settings 时传入
ezkl.gen_settings("model.onnx", "settings.json", py_run_args=run_args)
```

- 若 `custom_lookup_path` 为 `None` 或不设置，Sigmoid 仍使用默认 `LookupOp::Sigmoid`。
- 路径建议使用**绝对路径**，避免工作目录变化导致找不到文件。

### 2.3 通过 JSON 配置传入

Settings 或 RunArgs 的 JSON 中可包含 `custom_lookup_path`，例如：

```json
{
  "run_args": {
    "input_scale": 7,
    "param_scale": 7,
    "custom_lookup_path": "/path/to/pwl_params.json"
  }
}
```

反序列化时该字段使用 `#[serde(default)]`，缺失则视为 `None`。

### 2.4 典型流程简述

1. 用 Python/NumPy 等拟合 PWL（如参考 `pla_sigmoid/pwl_sigmoid.py`），得到 `breakpoints`、`slopes`、`intercepts`。
2. 将三者写成上述 JSON，保存到例如 `pwl_params.json`。
3. 在调用 ezkl 的入口处设置 `run_args.custom_lookup_path = "pwl_params.json"`（或通过 JSON 配置）。
4. 正常执行 `gen_settings` / `compile_circuit` / `gen_witness` / `setup` / `prove` / `verify`；图中 ONNX Sigmoid 会使用 Custom 查找表。

---

## 三、代码位置（供 AI 与开发者定位）

| 功能 | 路径 |
|------|------|
| RunArgs 新增字段 `custom_lookup_path` | `ezkl/src/lib.rs` |
| PyRunArgs 及与 RunArgs 的转换 | `ezkl/src/bindings/python.rs` |
| LookupOp 变体 `Custom { scale, path }` 及 PWL 加载与 `f()` 计算 | `ezkl/src/circuit/ops/lookup.rs` |
| ONNX "Sigmoid" 在存在 `custom_lookup_path` 时改为 Custom | `ezkl/src/graph/utilities.rs`（`new_op_from_onnx` 中 "Sigmoid" 分支） |
| nonlinearity 中 `add_used_lookup(nl, ...)` 对 Custom 的说明 | `ezkl/src/circuit/ops/layouts.rs` |
| Table 对 Custom 的注释与日志（表数据由 `nl.f()` 生成） | `ezkl/src/circuit/table.rs` |

- **PWL JSON 格式**的约定与校验见 `ezkl/src/circuit/ops/lookup.rs` 中 `PwlParams` 与 `load_pwl_from_path`。
- Custom 与其它 LookupOp 共用同一套 table 配置与 layout 流程，无需在 layout 中为 Custom 单独“初始化”或“按特定范围填充 TableColumn”。

---

## 四、注意事项

- **scale**：Custom 使用与其它 Lookup 一致的 `utils::F32`（Rust 中无 `f128`）。输入整数先除以 `scale` 得到浮点，PWL 计算后再乘回并取整。
- **路径**：`path` 在**表生成（layout）**时被读取；若使用相对路径，请保证运行 ezkl 时的当前工作目录正确。
- **兼容性**：未设置 `custom_lookup_path` 时，行为与上游 ezkl 一致；设置后仅影响图中 **Sigmoid** 算子的实现方式（Custom 表 vs 内置 Sigmoid 表）。

---

## 五、相关示例

- 分段线性 Sigmoid 拟合与 ONNX 导出思路可参考：  
  `ezkl/examples/onnx/pla_sigmoid/`（该示例用 PLA 替代 Sigmoid 节点，本修改则保留 Sigmoid 节点、用 Custom 查找表实现近似）。

若在其他文件或对话中需要让 AI 遵循“本机修改后的 ezkl 用法”，可引用本 README 或上述路径与 JSON 格式说明。
