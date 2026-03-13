# 直接向 ezkl 官方仓库提 PR（不推送到个人仓库）

只提交**必要代码文件**，且在不使用新功能时与官方行为一致。

---

## 一、向后兼容说明

- **`custom_lookup_path` 未设置时**（默认 `None`）：
  - `RunArgs` 默认值与官方一致，`#[serde(default)]` 保证旧配置/CLI 有效。
  - 图中 Sigmoid 仍为 `LookupOp::Sigmoid { scale }`，走官方内置表逻辑。
- **仅当** 用户显式设置 `custom_lookup_path: Some(path)` 时，才使用 `LookupOp::Custom` 和 PWL JSON。
- 因此：**不启用新功能时，行为与官方仓库一致**。

---

## 二、需要复制到 fork 的**必要文件**（仅 6 个）

从 **ezkl-custom-lookup** 只拷贝以下文件到你的 **ezkl fork**，其余一律不拷（不拷 README、.gitignore、PR_DESCRIPTION 等）。

| 文件 | 作用 |
|------|------|
| `src/lib.rs` | 增加 `RunArgs.custom_lookup_path`，默认 `None` |
| `src/bindings/python.rs` | Python 暴露 `custom_lookup_path`，prove 时释放 GIL |
| `src/circuit/ops/lookup.rs` | 新增 `LookupOp::Custom`，PWL 加载与求值 |
| `src/graph/utilities.rs` | Sigmoid 分支：若 `custom_lookup_path` 为 Some 则用 Custom，否则用 Sigmoid |
| `src/circuit/table.rs` | Custom 表内容由 PWL 填充 |
| `src/pfsys/mod.rs` | prove 过程中心跳/类型修正（与 GIL 配合） |

**不提交**：README.md、PR_DESCRIPTION.md、.gitignore、.github/ 等（保持与官方一致，避免 CI/runner 和无关改动）。

若提 PR 后官方 CI 或本地编译报错缺少 `MismatchedLookupTableLength` 或相关类型，说明当前官方分支还没有该错误变体，则额外复制这两项后再提交一次：
- `src/circuit/ops/errors.rs`
- `src/circuit/ops/layouts.rs`

## 三、操作步骤

### 3.1 Fork 并克隆

1. 打开 https://github.com/zkonduit/ezkl → 点击 **Fork**，得到 **changshenhan/ezkl**。
2. 本地执行：

```bash
cd /Users/songlvhan/Desktop
git clone https://github.com/changshenhan/ezkl.git ezkl-fork-for-pr
cd ezkl-fork-for-pr
git checkout main
git pull origin main
```

（若官方默认分支是 `master`，则把 `main` 换成 `master`。）

### 3.2 只复制上述 6 个文件

```bash
CUSTOM=/Users/songlvhan/Desktop/ezkl-custom-lookup
FORK=/Users/songlvhan/Desktop/ezkl-fork-for-pr

cp "$CUSTOM/src/lib.rs" "$FORK/src/lib.rs"
cp "$CUSTOM/src/bindings/python.rs" "$FORK/src/bindings/python.rs"
cp "$CUSTOM/src/circuit/ops/lookup.rs" "$FORK/src/circuit/ops/lookup.rs"
cp "$CUSTOM/src/graph/utilities.rs" "$FORK/src/graph/utilities.rs"
cp "$CUSTOM/src/circuit/table.rs" "$FORK/src/circuit/table.rs"
cp "$CUSTOM/src/pfsys/mod.rs" "$FORK/src/pfsys/mod.rs"
```

### 3.3 提交并推送到你的 fork

```bash
cd /Users/songlvhan/Desktop/ezkl-fork-for-pr
git add src/lib.rs src/bindings/python.rs src/circuit/ops/lookup.rs src/graph/utilities.rs src/circuit/table.rs src/pfsys/mod.rs
git status   # 确认只有这 6 个文件
git commit -m "Add optional custom lookup table for Sigmoid (PWL from JSON) and release GIL during prove"
git push origin main
```

### 3.4 在 GitHub 上创建 PR

1. 打开 https://github.com/zkonduit/ezkl ，点击 **Pull requests** → **New pull request**。
2. **base** 选 **zkonduit/ezkl** 的 **main**（或 master），**compare** 选 **changshenhan/ezkl** 的 **main**。
3. **Title**：`Add optional custom lookup table for Sigmoid (PWL from JSON)`
4. **Description**：打开本地 **ezkl-custom-lookup** 里的 **PR_DESCRIPTION.md**，全文复制粘贴到 PR 描述框。
5. 点击 **Create pull request**。

---

## 四、结果

- **不推送到个人仓库**：无需 changshenhan/ezkl-custom-lookup 的 push。
- **只上传必要文件**：仅上述 6 个 Rust 源文件，无 README/CI/其他配置变更。
- **未使用新功能时**：与官方仓库行为一致；仅在设置 `custom_lookup_path` 时启用自定义 PWL 查表。

官方 CI 在 zkonduit/ezkl 上会跑；若维护者希望补充 README 或测试，可在 PR 讨论中按反馈再加。
