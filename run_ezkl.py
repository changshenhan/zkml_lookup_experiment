"""
ezkl 流程：PLA 版（无 Lookup Table）。
模型已用分段线性替代 Sigmoid，电路仅含乘加与比较，用 Copy/算术约束即可，无 lookup。
无 lookup 时可轻量化 settings：不分配 lookup 表、最小化相关参数。
"""
import ezkl
import os

model_path = "network.onnx"
settings_path = "settings.json"
compiled_model_path = "network.compiled"

# 1. 生成设置（PLA 无 lookup → 轻量化）
py_run_args = ezkl.PyRunArgs()
py_run_args.input_visibility = "public"
py_run_args.output_visibility = "public"
py_run_args.param_visibility = "fixed"
# 无 lookup：最小化 lookup 相关参数（num_inner_cols=0 会触发 ezkl 除零，故用 1）
py_run_args.num_inner_cols = 1
py_run_args.lookup_range = (0, 1)
py_run_args.bounded_log_lookup = False
# logrows：num_rows 须 ≤ 2^logrows；当前 PLA 电路若更大可改为 17
py_run_args.logrows = 16

res = ezkl.gen_settings(model_path, settings_path, py_run_args=py_run_args)
if res:
    print("✅ Settings generated successfully!")

# 2. 编译电路（无 lookup，仅算术 + Copy 约束）
ezkl.compile_circuit(model_path, compiled_model_path, settings_path)
print("✅ Circuit compiled (PLA, no lookup)")