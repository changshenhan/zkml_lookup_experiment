# 推送到 GitHub（changshenhan）

本地已完成 `git init` 和首次提交。按下面步骤推到你的 GitHub 仓库。

## 1. 在 GitHub 上新建仓库

1. 打开 https://github.com/new
2. 仓库名建议：`zkml_lookup_experiment`（或自选）
3. 选择 **Public**，**不要**勾选 “Add a README” / “Initialize with .gitignore”（本地已有）
4. 创建仓库后，记下仓库地址，例如：  
   `https://github.com/changshenhan/zkml_lookup_experiment.git`

## 2. 添加远程并推送

在项目根目录执行（把 `REPO_URL` 换成你的仓库地址）：

```bash
cd /Users/songlvhan/Desktop/zkml_lookup_experiment
git remote add origin https://github.com/changshenhan/zkml_lookup_experiment.git
git push -u origin main
```

若 GitHub 上默认分支是 `master`，可先推送为 `main`，再在 GitHub 仓库设置里把默认分支改为 `main`；或本地用 `git push -u origin main:master` 推送到 `master`。

## 3. 使用 SSH（可选）

若已配置 SSH key，可改用：

```bash
git remote add origin git@github.com:changshenhan/zkml_lookup_experiment.git
git push -u origin main
```

---

推送完成后，在 GitHub 上即可看到 README、COMPARISON.md 及完整对比数据与复现说明。
