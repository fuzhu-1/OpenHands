# ADR-001: Reviewer 部署定位

## 状态

建议（Pending）— 待仓库所有者确认

## 背景

reviewer 目前以内置 `scripts/reviewer/` + `.github/workflows/reviewer.yml` 的形式存在于 fork 中。
fork 持续跟踪上游 OpenHands，每次与上游同步都可能与 `scripts/`、`.github/workflows/` 下的文件产生冲突；
同时仓库已有上游自带的 `qa-changes-by-openhands.yml`（label 门禁 + 复用官方 action）与
`pr-readiness-confirm.yml`（PR 就绪检查），reviewer 的模板检查与其部分重叠。

## 选项

- **A. 保持 fork 内维护（现状）**：改动成本低、迭代快；缺点是与上游同步冲突面大，
  且 reviewer 的维护责任与 OpenHands 主项目无关。
- **B. 独立 action 仓库（推荐）**：仿照上游 `OpenHands/extensions/plugins/qa-changes@main`
  的做法，把 `scripts/reviewer/` 迁移到独立仓库并发布为 composite action；本仓库只保留
  workflow 引用。解耦、可复用、同步零冲突；缺点是需额外的发布流程（tag/SHA 固定）。
- **C. 向上游贡献**：把能力合并进 OpenHands 官方流程（或直接使用官方 `qa-changes`）；
  需要先与上游团队对齐范围，周期不可控。

## 决策

默认建议 **B**——当 reviewer 被超过 1 个仓库使用时立即执行迁移；若仅本 fork 使用且
短期无扩展计划，可维持 A 并接受同步冲突（用 `git rebase upstream/main` 小步化解）。

## 影响

- 选择 B 后：本仓库删除 `scripts/reviewer/`（或保留为薄封装），workflow 固定
  `owner/repo@<SHA> # vX.Y.Z` 引用；`tests/reviewer/` 随迁。
- 选择 A 后：每次同步上游前先 `git checkout upstream/main -- scripts/reviewer tests/reviewer`
  之外的文件，避免 reviewer 目录被上游覆盖。

## 关联

- 本加固计划：`.pr/reviewer-optimization-plan.md`
- 上游参考：`.github/workflows/qa-changes-by-openhands.yml`
