"""
导出 ONNX：激活为单 Sigmoid，由 ezkl 的 lookup 表实现（查表，不展开成算术）。

- 使用 nn.Sigmoid()，电路里由 ezkl 的 Sigmoid 查表约束，不是多段乘加算术。
- lookup_range 由 run_ezkl_full.py 根据 lookup_table.json 的输入范围设置，保证查表满足。
"""

import json
import os
import torch
import torch.onnx
import torch.nn as nn
import torch.nn.init as init


class Circuit(nn.Module):
    """Conv + ReLU + Sigmoid（ezkl 用 lookup 表实现）。"""

    def __init__(self):
        super().__init__()
        self.relu = nn.ReLU()
        self.conv = nn.Conv2d(3, 3, (2, 2), 1, 2)
        self.act = nn.Sigmoid()
        init.orthogonal_(self.conv.weight)

    def forward(self, x, y, z):
        x = self.act(self.conv(y @ x**2 + (x) - (self.relu(z)))) + 2
        return (x, self.relu(z) / 3)


def main():
    torch_model = Circuit()
    shape = [3, 2, 2]
    x = 0.1 * torch.rand(1, *shape, requires_grad=True)
    y = 0.1 * torch.rand(1, *shape, requires_grad=True)
    z = 0.1 * torch.rand(1, *shape, requires_grad=True)
    torch_out = torch_model(x, y, z)

    torch.onnx.export(
        torch_model,
        (x, y, z),
        "network.onnx",
        export_params=True,
        opset_version=10,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )

    data = dict(
        input_shapes=[shape, shape, shape],
        input_data=[
            x.detach().numpy().reshape(-1).tolist(),
            y.detach().numpy().reshape(-1).tolist(),
            z.detach().numpy().reshape(-1).tolist(),
        ],
        output_data=[o.detach().numpy().reshape(-1).tolist() for o in torch_out],
    )
    with open("input.json", "w") as f:
        json.dump(data, f)
    print("已导出 network.onnx 和 input.json（单 Sigmoid，ezkl 用 lookup 表证明）")


if __name__ == "__main__":
    main()
