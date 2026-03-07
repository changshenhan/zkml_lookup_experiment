import time, json, os, sys
# 排查 prove 卡住：运行前设置 RUST_LOG=debug 或 RUST_LOG=info 查看 Rust 层日志
# 例如: RUST_LOG=debug python 4.py
import ezkl

# 打印当前环境，便于排查版本/环境不一致
print("Python:", sys.executable)
try:
    import importlib.metadata
    _ver = importlib.metadata.version("ezkl")
except Exception:
    _ver = getattr(ezkl, "__version__", "unknown")
print("ezkl version:", _ver)
data_path = "input.json"
print("data_path:", os.path.abspath(data_path) if os.path.exists(data_path) else data_path + " (not found)")
sys.stdout.flush()

compiled_model_path = "network.compiled"

vk_path = "ezkl_vk.key"
pk_path = "ezkl_pk.key"
srs_path = "ezkl_kzg.srs"
witness_path = "ezkl_witness.json"
proof_path = "ezkl_proof.json"

print("=== ezkl gen_witness ===")
t0 = time.time()
ezkl.gen_witness(data=data_path, model=compiled_model_path, output=witness_path)
t1 = time.time()
print(f"gen_witness time: {t1 - t0:.4f} s")

print("=== ezkl setup ===")
t2 = time.time()
ezkl.setup(compiled_model_path, vk_path, pk_path, srs_path)
t3 = time.time()
print(f"setup time: {t3 - t2:.4f} s")

print("=== ezkl prove ===")
# 卡住时用 RUST_LOG=info 或 RUST_LOG=debug 看 Rust 日志，例: RUST_LOG=info python 4.py
for p in (pk_path, witness_path, srs_path):
    if os.path.exists(p):
        print(f"  {p}: {os.path.getsize(p) / (1024*1024):.2f} MB", flush=True)
    else:
        print(f"  {p}: 不存在", flush=True)
sys.stdout.flush()
t4 = time.time()
ezkl.prove(witness_path, compiled_model_path, pk_path, proof_path, srs_path)
t5 = time.time()
sys.stdout.flush()
print(f"prove time: {t5 - t4:.4f} s")

print("\nSummary:")
print(json.dumps({
  "gen_witness_sec": t1 - t0,
  "setup_sec": t3 - t2,
  "prove_sec": t5 - t4,
}, indent=2))
