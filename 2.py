import onnx
import numpy as np
from onnx import numpy_helper
import json

def extract_and_quantize(onnx_path, scale_factor=65536): # 2^16
    model = onnx.load(onnx_path)
    weights_dict = {}

    # 遍历 ONNX 的所有权重初始化器
    for tensor in model.graph.initializer:
        name = tensor.name
        # 转换为 numpy 数组
        float_data = numpy_helper.to_array(tensor)
        
        # 核心：量化为整数
        # 对于 ZKML，我们通常使用 i64 来存储这些大整数
        quantized_data = np.round(float_data * scale_factor).astype(np.int64)
        
        weights_dict[name] = {
            "shape": list(quantized_data.shape),
            "data": quantized_data.flatten().tolist()
        }
        print(f"✅ 已提取层: {name} | 形状: {quantized_data.shape}")

    # 导出为 JSON
    output_path = "all_weights_quantized.json"
    with open(output_path, "w") as f:
        json.dump(weights_dict, f, indent=4)
    print(f"\n🚀 所有权重已保存至: {output_path}")

if __name__ == "__main__":
    # 替换为你实际的 ONNX 文件名
    extract_and_quantize("network.onnx")