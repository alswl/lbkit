# lbkit 开发指南

本文档面向 lbkit 仓库自身的开发与维护，**不随安装分发**到使用方仓库。面向使用方仓库的共享契约见 `docs/`，技能见 `skills/`。

## 目录结构

```text
skills/        # lb-* 技能，for 使用方仓库；安装时链接为其 .agents/skills/lb-*
docs/          # 共享契约文档，for 使用方仓库；安装时链接为其 docs/<name>.md
dev-docs/      # lbkit 自身文档（本目录），不安装
bin/           # lb、lb-anywhere、lbkit 安装器
src/           # logbook_cli Python 包
scripts/       # lb.py 入口脚本
tests/         # unittest 测试
```

## 运行测试

仅需 Python 3 标准库：

```sh
python3 -m unittest discover tests
```

## 修改共享契约时的检查清单

契约文件（`docs/`）和技能（`skills/`）会被安装进使用方仓库，因此改动时：

1. **相对链接必须同时在使用方仓库内成立。** 技能位于安装后的 `.agents/skills/lb-X/`，经由 symlink 指向 `.lbkit/skills/lb-X/`；契约位于使用方 `docs/`，指向 `.lbkit/docs/`。技能内引用契约：SKILL.md 用 `../../docs/...`（references 子目录用 `../../../docs/...`），契约内引用技能用 `../skills/...`。路径按 lbkit 内部结构书写即可——使用方仓库内经 symlink 解析后落在 `.lbkit/` 内的同一文件。
2. **更新 `bin/lbkit` 的 `manifest()`**，如果新增了顶层需安装的目录或文件。
3. **运行全量测试**；安装器相关改动运行 `python3 -m unittest tests.test_lbkit_install`。
4. **使用方仓库拥有**其项目日志、`AGENTS.md`、`lbkit-agents.yaml`、可选的 `lbkit-skills.json`；不要通过共享契约向其注入新义务而不在本文档说明。

## 版本与演进

lbkit 使用语义化版本，当前版本记在根目录 `VERSION`（首版 0.1.0），`bin/lb --version` 输出它。版本覆盖三类对象：lbkit 整体（共享契约、CLI 与安装器）、每个 lb-* 技能（SKILL.md frontmatter 的 `version`），以及使用方仓库的配置格式（`lbkit-agents.yaml` 的 `version`，`lbkit-skills.json` 的 `"version"`）。0.x 阶段破坏性变更升次版本号，兼容修改升修订号；改了某个技能或格式就同步升它的版本，配置格式升级时同时更新读取方支持的版本列表。每个使用方仓库仍通过 submodule 指针钉住一个精确修订版，使用方自主选择升级时机——更新 submodule 指针即是升级。因此：

- 契约修改尽量保持向后兼容（新增字段优于改语义）。
- 破坏性变更需在对应契约文档中注明变更点，便于使用方评估是否升级。
- CLI 写操作以 `version_token`（SHA-256 CAS）防止并发冲突，日志文件与解析代码的配套由修订版钉住保证。
