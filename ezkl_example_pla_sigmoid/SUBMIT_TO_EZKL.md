# 投稿至 zkonduit/ezkl 的 steps（GitHub: changshenhan）

## 1. Fork 并克隆 ezkl

```bash
# 浏览器打开 https://github.com/zkonduit/ezkl 点击 Fork

# 克隆你自己的 fork（把 changshenhan 换成你的 GitHub 用户名）
git clone https://github.com/changshenhan/ezkl.git
cd ezkl
```

## 2. 新建分支

```bash
git checkout -b examples/onnx/pla_sigmoid
```

## 3. 把本示例拷到 ezkl 的 examples/onnx 下

把当前文件夹 `ezkl_example_pla_sigmoid` 里的内容，复制到 ezkl 仓库的 **examples/onnx/pla_sigmoid** 目录下（注意目录名用 **pla_sigmoid**，与其它 onnx 示例一致）。

需要拷贝的文件（不要拷 `SUBMIT_TO_EZKL.md` 和 `__pycache__`）：

- `README.md`
- `gen.py`
- `pwl_sigmoid.py`
- `input.json`
- `network.onnx`
- `pwl_params.npz`

例如（在 Mac/Linux 下，假设 ezkl 克隆在 `~/ezkl`）：

```bash
mkdir -p ~/ezkl/examples/onnx/pla_sigmoid
cp README.md gen.py pwl_sigmoid.py input.json network.onnx pwl_params.npz ~/ezkl/examples/onnx/pla_sigmoid/
```

## 4. 提交并推送到你的 fork

```bash
cd ~/ezkl
git add examples/onnx/pla_sigmoid/
git status
git commit -m "examples/onnx: add pla_sigmoid — PLA replaces Sigmoid lookup for lighter, faster proving"
git push origin examples/onnx/pla_sigmoid
```

## 5. 在 GitHub 上开 PR

1. 打开 https://github.com/changshenhan/ezkl
2. 会提示 “Compare & pull request”，或去 **Pull requests → New pull request**
3. **base** 选 `zkonduit/ezkl` 的 `main`，**compare** 选你的分支 `examples/onnx/pla_sigmoid`
4. 标题建议：`[examples] Add ONNX example: PLA Sigmoid (replace lookup with piecewise linear)`
5. 描述可写：

   ```
   This adds an ONNX example under examples/onnx/pla_sigmoid that replaces
   Sigmoid lookup with a piecewise linear approximation (PLA), so the circuit
   uses only mul/add/compare (copy and arithmetic constraints) and no lookup.
   - Keeps accuracy >= 99.5% vs true sigmoid.
   - Allows lighter ezkl settings (num_inner_cols=1, minimal lookup_range).
   - Useful as a reference for reducing proof cost when handling nonlinear ops.
   Author: @changshenhan
   ```

6. 创建 Pull request，等待 maintainer 回复。

## 6. 若 maintainer 要求修改

在本地改好后：

```bash
cd ~/ezkl
# 修改 examples/onnx/pla_sigmoid/ 下文件后
git add examples/onnx/pla_sigmoid/
git commit -m "address review: ..."
git push origin examples/onnx/pla_sigmoid
```

PR 会自动更新。
