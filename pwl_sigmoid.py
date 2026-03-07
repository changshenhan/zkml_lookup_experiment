"""
基于“分段查找表 + 线性插值”的思路实现 Sigmoid 的分段线性近似：

- 在真实输入范围上，按数据分布**非均匀地选取 1024 个关键点 x_i**
- 每个区间 [x_i, x_{i+1}] 上用端点做线性拟合，得到 k_i, b_i
- 将 (breakpoints=x_i, slopes=k_i, intercepts=b_i) 保存在 `pwl_params.npz`

本模块提供：
- `fit_pwl_sigmoid(n_segments, target_max_rel_error)`：根据 data.json 拟合并返回 (breakpoints, slopes, intercepts)
- `calibrate_and_save(target_accuracy)`：调用上面的函数并把结果落盘到 `pwl_params.npz`
- `PWLSigmoid`：PyTorch 模块，在 forward 中按上述分段线性函数近似 σ(x)

注意：
- 这里依赖项目根目录下的 `data.json`，也就是你原始的数据文件，
  完全符合你“根据我的数据文件 + 1024 非均匀关键点”的要求。
"""

import json
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn


DATA_PATH = Path("data.json")
PWL_PARAMS_PATH = Path("pwl_params.npz")


def _load_all_inputs_from_data() -> Tuple[float, float, np.ndarray]:
    """
    从 data.json 中读取 input_data，返回：
    - xmin, xmax: 输入最小/最大值
    - all_x: 扁平化后的全部输入样本
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"未在项目根目录找到 {DATA_PATH}. "
            f"请确认你的原始数据文件 data.json 已放在当前目录。"
        )
    raw = json.loads(DATA_PATH.read_text())
    all_in = [v for arr in raw.get("input_data", []) for v in arr]
    if not all_in:
        raise ValueError("data.json 中的 input_data 为空，无法拟合 PWL Sigmoid。")

    all_x = np.asarray(all_in, dtype=np.float64)
    xmin = float(all_x.min())
    xmax = float(all_x.max())
    return xmin, xmax, all_x


def _sigmoid_np(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def fit_pwl_sigmoid(
    n_segments: int = 1023,
    target_max_rel_error: float = 0.005,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    根据 data.json 中的真实输入分布，构造“分段查找表 + 线性插值”所需的
    breakpoints/slopes/intercepts。

    - 使用非均匀 1024 个关键点（分位点法）：
        M = n_segments + 1
        关键点 x_i 为 all_x 的等距分位数 q_j = j / (M-1)
    - 对每个区间 [x_i, x_{i+1}]：
        k_i = (σ(x_{i+1}) - σ(x_i)) / (x_{i+1} - x_i)
        b_i = σ(x_i) - k_i * x_i

    参数 `target_max_rel_error` 在这个实现中只作为占位符，
    便于将来做更精细的自适应调节；当前实现直接按固定段数构造。
    """
    if n_segments < 1:
        raise ValueError("n_segments 必须 ≥ 1")

    xmin, xmax, all_x = _load_all_inputs_from_data()

    # 关键点数量 = 段数 + 1；你要求的是 1024 个关键点，所以默认 n_segments=1023
    num_keypoints = n_segments + 1
    qs = np.linspace(0.0, 1.0, num_keypoints)
    # 按输入分布的分位点做非均匀采样
    keypoints = np.quantile(all_x, qs)
    # 强制首尾覆盖真实边界
    keypoints[0] = xmin
    keypoints[-1] = xmax
    # 单调去重
    keypoints = np.unique(keypoints)
    if keypoints.shape[0] < 2:
        raise ValueError("关键点去重后不足 2 个，可能输入范围过于狭窄。")

    xs = keypoints
    sig_xs = _sigmoid_np(xs)

    # 逐段计算 k_i, b_i（线性插值）
    x0 = xs[:-1]
    x1 = xs[1:]
    y0 = sig_xs[:-1]
    y1 = sig_xs[1:]
    dx = x1 - x0
    if np.any(dx <= 0):
        raise ValueError("构造出的关键点必须严格递增。")

    slopes = (y1 - y0) / dx
    intercepts = y0 - slopes * x0

    # 可选：这里可以根据 target_max_rel_error 做一下误差检查（省略打印即可）
    mids = 0.5 * (x0 + x1)
    true_mid = _sigmoid_np(mids)
    approx_mid = slopes * mids + intercepts
    abs_err = np.max(np.abs(true_mid - approx_mid))
    rel_err = float(abs_err / np.max(np.abs(true_mid) + 1e-8))
    if rel_err > target_max_rel_error:
        # 这里只做提示，不强行报错，避免打断流程
        print(
            f"[PWLSigmoid] 警告：在中点处的最大相对误差约为 {rel_err:.3e} "
            f"> target_max_rel_error={target_max_rel_error}"
        )

    return xs.astype(np.float32), slopes.astype(np.float32), intercepts.astype(np.float32)


def calibrate_and_save(target_accuracy: float = 0.995) -> None:
    """
    拟合 PWL Sigmoid 并将参数保存到 `pwl_params.npz`。

    target_accuracy 目前仅用于选择默认段数（这里直接使用 1023 段 ≈ 1024 个关键点），
    以后可以根据精度要求自适应调整。
    """
    # 目前直接使用固定段数，满足“1024 非均匀关键点”的要求
    n_segments = 1023  # => 1024 个关键点
    breakpoints, slopes, intercepts = fit_pwl_sigmoid(
        n_segments=n_segments,
        target_max_rel_error=1.0 - target_accuracy,
    )
    np.savez(PWL_PARAMS_PATH, breakpoints=breakpoints, slopes=slopes, intercepts=intercepts)
    print(
        f"[PWLSigmoid] 已将 {len(breakpoints)} 个关键点、"
        f"{len(slopes)} 段的 PWL 参数保存到 {PWL_PARAMS_PATH}"
    )


class PWLSigmoid(nn.Module):
    """
    使用 (breakpoints, slopes, intercepts) 做分段线性 Sigmoid 近似的 PyTorch 模块。

    对每个标量输入 x：
        在满足 x ∈ [x_i, x_{i+1}] 的那一段上，
        返回 y = k_i * x + b_i。

    实现上为了便于导出 ONNX，不使用复杂控制流，而是用广播 + 掩码：
        - 对所有段 i 计算候选 y_i = k_i * x + b_i
        - cond_i = 1 当 x ∈ [x_i, x_{i+1}]，否则为 0
        - y = Σ_i cond_i * y_i
    """

    def __init__(
        self,
        breakpoints: np.ndarray,
        slopes: np.ndarray,
        intercepts: np.ndarray,
    ):
        super().__init__()
        if breakpoints.ndim != 1:
            raise ValueError("breakpoints 必须是一维数组")
        if not (slopes.ndim == 1 and intercepts.ndim == 1):
            raise ValueError("slopes 和 intercepts 必须是一维数组")
        if not (slopes.shape[0] == intercepts.shape[0] == breakpoints.shape[0] - 1):
            raise ValueError("长度关系必须满足：len(breakpoints) = len(slopes) + 1 = len(intercepts) + 1")

        # 注册为 buffer，便于一起导出到 ONNX
        self.register_buffer("breakpoints", torch.from_numpy(breakpoints.reshape(-1)))
        self.register_buffer("slopes", torch.from_numpy(slopes.reshape(-1)))
        self.register_buffer("intercepts", torch.from_numpy(intercepts.reshape(-1)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: 任意形状的张量
        返回：与 x 同形状的近似 σ(x)。
        """
        # 形状准备：在最前面加一维“段索引”维度
        #   x_expanded: (num_segments, *x.shape)
        x_expanded = x.unsqueeze(0)
        # 每一段对应 [bp[i], bp[i+1]]
        left = self.breakpoints[:-1].view(-1, *([1] * x.dim()))
        right = self.breakpoints[1:].view(-1, *([1] * x.dim()))
        slopes = self.slopes.view(-1, *([1] * x.dim()))
        intercepts = self.intercepts.view(-1, *([1] * x.dim()))

        # 候选值：y_i = k_i * x + b_i
        y_candidates = slopes * x_expanded + intercepts

        # 段选择掩码：cond_i = 1 当 x ∈ [left_i, right_i]，否则为 0
        cond = (x_expanded >= left) & (x_expanded <= right)

        # 加权求和：Σ_i cond_i * y_i
        y = (cond.to(x.dtype) * y_candidates).sum(dim=0)
        return y


