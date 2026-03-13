"""
基于当前模型输入数据，为 Sigmoid 近似构造：

- 非均匀 1024 个关键点 x_i（来自真实输入分布的分位点）
- 每个区间 [x_i, x_{i+1}] 的线性拟合参数 k_i, b_i（用端点精确拟合）
- 将 (x_i, k_i, b_i) 统一量化为有限域中的整数表示，便于在 ezkl / Plonk 电路里做 lookup。

输出文件：
- lookup_table.json
    {
        "scale": 4294967296,          # S = 2^32
        "x": [...], "k": [...], "b": [...],       # 浮点
        "x_int": [...], "k_int": [...], "b_int": [...]  # 有限域中的整数表示
    }
"""

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np


def load_input_range(path: str = "data.json") -> Tuple[float, float, np.ndarray]:
    """
    从 data.json 里读取所有 input_data，返回：
    - xmin, xmax: 实际出现过的最小/最大输入
    - all_x: 所有扁平化后的输入样本（np.array），用于非均匀采样
    若 data.json 不存在，则使用默认范围 [-2, 2] 与 200 个均匀点。
    """
    p = Path(path)
    if not p.exists():
        all_x = np.linspace(-2.0, 2.0, 200)
        return -2.0, 2.0, all_x

    data = json.loads(p.read_text())
    all_in: List[float] = [v for arr in data.get("input_data", []) for v in arr]
    if not all_in:
        raise ValueError("data.json 中的 input_data 为空，无法估计输入范围。")

    all_x = np.asarray(all_in, dtype=np.float64)
    xmin = float(all_x.min())
    xmax = float(all_x.max())
    return xmin, xmax, all_x


def sigmoid(x: np.ndarray) -> np.ndarray:
    """标准 Logistic Sigmoid σ(x) = 1 / (1 + e^-x)。"""
    return 1.0 / (1.0 + np.exp(-x))


def build_nonuniform_keypoints(
    all_x: np.ndarray,
    num_keypoints: int,
    xmin: float,
    xmax: float,
) -> np.ndarray:
    """
    利用真实输入分布构造“非均匀”关键点：
    - 取 all_x 的分位点：q_j = j / (num_keypoints - 1)
    - 这样在数据密集的区域采样更密，在稀疏区域更疏
    - 同时强制首尾为 xmin, xmax，确保全区间覆盖
    """
    if num_keypoints < 2:
        raise ValueError("num_keypoints 必须 ≥ 2")

    qs = np.linspace(0.0, 1.0, num_keypoints)
    # 使用分位数做非均匀采样
    keypoints = np.quantile(all_x, qs)
    # 强制覆盖全区间
    keypoints[0] = xmin
    keypoints[-1] = xmax
    # 单调去重，避免出现完全相同的点导致区间长度为 0
    keypoints = np.unique(keypoints)
    if keypoints.shape[0] < 2:
        raise ValueError("关键点去重后不足 2 个，可能输入范围极窄。")
    return keypoints


def fit_piecewise_linear(
    xs: np.ndarray,
    fxs: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    给定关键点 xs 与 f(xs)，对每个相邻区间 [x_i, x_{i+1}] 用端点做线性插值：
        k_i = (f_{i+1} - f_i) / (x_{i+1} - x_i)
        b_i = f_i - k_i * x_i

    返回：
    - k: 形状 (n-1,)
    - b: 形状 (n-1,)
    """
    if xs.ndim != 1 or fxs.ndim != 1:
        raise ValueError("xs 与 fxs 必须是一维数组。")
    if xs.shape[0] != fxs.shape[0]:
        raise ValueError("xs 与 fxs 长度必须一致。")
    if xs.shape[0] < 2:
        raise ValueError("至少需要 2 个关键点。")

    x0 = xs[:-1]
    x1 = xs[1:]
    y0 = fxs[:-1]
    y1 = fxs[1:]

    dx = x1 - x0
    if np.any(dx <= 0):
        raise ValueError("关键点必须严格递增。")

    k = (y1 - y0) / dx
    b = y0 - k * x0
    return k, b


def load_pwl_64_from_lookup_table(path: str = "lookup_table.json") -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    从 lookup_table.json（1024 点）中抽取 64 段 PWL，用于 ONNX 导出，跑「你的精度」版本。
    保持你的非均匀关键点与 k_i·x + b_i 公式，仅将段数降为 64 以便电路可编译。
    返回 (breakpoints, slopes, intercepts)，可直接传给 pwl_sigmoid.PWLSigmoid。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到 {path}，请先运行 python build_lookup_table.py")
    data = json.loads(p.read_text())
    x_full = np.array(data["x"], dtype=np.float64)
    n_full = len(x_full)
    if n_full < 65:
        raise ValueError(f"lookup_table.json 关键点不足 65，当前 {n_full}")
    # 均匀下标抽取 65 个关键点（保持非均匀的 x 分布）
    step = (n_full - 1) / 64.0
    indices = [int(round(i * step)) for i in range(65)]
    indices[-1] = n_full - 1
    xs = x_full[indices].copy()
    xs = np.unique(xs)
    if xs.shape[0] < 2:
        raise ValueError("抽取后关键点不足 2 个")
    fxs = sigmoid(xs)
    slopes, intercepts = fit_piecewise_linear(xs, fxs)
    return xs, slopes, intercepts


def quantize_to_field(
    xs: np.ndarray,
    ks: np.ndarray,
    bs: np.ndarray,
    scale_bits: int = 32,
) -> Tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    """
    将 (x_i, k_i, b_i) 统一量化为整数：
        S = 2^scale_bits
        x_int = round(x * S)
        k_int = round(k * S)
        b_int = round(b * S)

    在电路中用定点数表示：
        x_real ≈ x_int / S
        k_real ≈ k_int / S
        b_real ≈ b_int / S

    近似：
        σ(x) ≈ k_real * x_real + b_real
              = (k_int * x_int) / S^2 + b_int / S
    """
    S = 1 << scale_bits
    x_int = np.rint(xs * S).astype(object)  # 使用 Python int，避免溢出
    k_int = np.rint(ks * S).astype(object)
    b_int = np.rint(bs * S).astype(object)

    return S, x_int, k_int, b_int


def main():
    # 1. 读取输入范围与真实分布（来自 data.json；若无则用默认 [-2, 2]）
    xmin, xmax, all_x = load_input_range("data.json")
    print(f"检测到输入范围: [{xmin:.8f}, {xmax:.8f}]，样本数={all_x.shape[0]}")

    # 2. 构造 1024 个（默认值）非均匀关键点
    num_keypoints = 1024
    xs = build_nonuniform_keypoints(all_x, num_keypoints, xmin, xmax)
    num_segments = xs.shape[0] - 1
    print(f"实际关键点数量: {xs.shape[0]}，线性区间数: {num_segments}")

    # 3. 计算目标函数值 σ(x)
    fxs = sigmoid(xs)

    # 4. 对每个区间拟合线性参数 k_i, b_i
    ks, bs = fit_piecewise_linear(xs, fxs)

    # 5. 量化到有限域整数（这里假设后端使用如 BN254 等大素数域）
    scale_bits = 32
    S, x_int, k_int, b_int = quantize_to_field(xs, ks, bs, scale_bits=scale_bits)

    # 6. 简单报一下误差（在关键点中点处测试）
    mids = 0.5 * (xs[:-1] + xs[1:])
    true_mid = sigmoid(mids)
    approx_mid = ks * mids + bs
    max_abs_err = float(np.max(np.abs(true_mid - approx_mid)))
    print(f"在每个区间中点处的最大 |σ(x) - kx - b| ≈ {max_abs_err:.6e}")

    # 7. 写出查找表（含 ezkl Custom Lookup 所需格式）
    out = {
        "scale": int(S),
        "scale_bits": scale_bits,
        "x": xs.tolist(),
        "k": ks.tolist(),
        "b": bs.tolist(),
        "x_int": [int(v) for v in x_int],
        "k_int": [int(v) for v in k_int],
        "b_int": [int(v) for v in b_int],
    }
    Path("lookup_table.json").write_text(json.dumps(out, indent=2))
    print("✅ 已生成 lookup_table.json （含浮点与整数形式的 (x_i, k_i, b_i)）")

    # 8. 写出 ezkl Custom Lookup 使用的 PWL JSON（breakpoints/slopes/intercepts）
    pwl_params = {
        "breakpoints": xs.tolist(),
        "slopes": ks.tolist(),
        "intercepts": bs.tolist(),
    }
    Path("pwl_params.json").write_text(json.dumps(pwl_params, indent=2))
    print("✅ 已生成 pwl_params.json （ezkl custom_lookup_path 用）")

    # 9. 同时写出 64 段版本，避免 gen_settings 因段数过多卡住（可选使用 pwl_params_64.json）
    xs64, sl64, ic64 = load_pwl_64_from_lookup_table("lookup_table.json")
    pwl_params_64 = {
        "breakpoints": xs64.tolist(),
        "slopes": sl64.tolist(),
        "intercepts": ic64.tolist(),
    }
    Path("pwl_params_64.json").write_text(json.dumps(pwl_params_64, indent=2))
    print("✅ 已生成 pwl_params_64.json （64 段，若 gen_settings 卡住可改用此文件）")


if __name__ == "__main__":
    main()

