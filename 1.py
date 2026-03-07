import onnxruntime as ort
import numpy as np

# 1. 加载模型
session = ort.InferenceSession("network.onnx")

# 2. 构造伪数据 (根据你图中显示的 batch_size x 3 x 2 x 2)
dummy_input = np.random.randn(1, 3, 2, 2).astype(np.float32) 
# input.1 也要构造
dummy_input_1 = np.random.randn(1, 3, 2, 2).astype(np.float32)

# 3. 运行推理，获取所有中间层输出
# 注意：你需要找到 Conv 层输出节点的名称，可以在 Netron 里点击 Conv 节点看到 Output Name
outputs = session.run(None, {'input': dummy_input, 'input.1': dummy_input_1})

# 4. 观察 Conv 层输出 (假设它是 index 为 5 的输出)
conv_output = outputs[5] 
print(f"浮点数范围: min={conv_output.min()}, max={conv_output.max()}")

# 5. 映射到电路量化值
SCALE = 2**16
print(f"电路中 Lookup Table 需要覆盖的整数范围: [{conv_output.min() * SCALE}, {conv_output.max() * SCALE}]")