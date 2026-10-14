# lbkit

[English](README.md) | [中文](README.zh-CN.md)

可复用的 Logbook 协调技能、Markdown 契约，以及面向人机协作交付的 `lb` CLI。当前版本见 [VERSION](VERSION)（`bin/lb --version`）。

## 概述

**lbkit** 是一套共享工具包，以 `.lbkit` Git 子模块形式挂载到使用方仓库。它提供协调技能、文档契约和 CLI，让人类负责人、协调者 Agent 与执行 Agent 通过一份纯 Markdown **日志（logbook）**交付真实项目——日志是唯一的调度事实来源。

- **Admiral（人类）** — 掌握目标、风险接受与不可逆决定
- **Captain（协调 Agent）** — 维护目标、路径、依赖、调度及适用回报支持的进度
- **Sailor（执行 Agent）** — 执行业务、测试、review 和具体验收，回报当前成果、结论和缺口

授权边界、适用的 Sailor 回报和人工关口是契约，不是可关闭的选项。计划确认不等于执行授权；Agent 永远不写人类负责的日志条目。

## 安装

参见[安装与升级指南](docs/guide/install.zh-CN.md)。mind-forge 为必需依赖。

## 技能

| 技能 | 职责 |
|---|---|
| [lb-init](skills/lb-init/SKILL.md) | 建立或刷新 `.lbkit` 子模块与本地入口 |
| [lb-scaffold](skills/lb-scaffold/SKILL.md) | 为真实项目创建工作流实例日志 |
| [lb-plan](skills/lb-plan/SKILL.md) | 核对目标、起草待办供确认、设计阶段与工作包 |
| [lb-preflight](skills/lb-preflight/SKILL.md) | 只读预检：路线规划与逐步可行性分析 |
| [lb-push](skills/lb-push/SKILL.md) | 在已授权范围内派发、恢复并监听执行 |
| [lb-update](skills/lb-update/SKILL.md) | 获取现状并核实写回，或只读重读人类修改 |
| [lb-status](skills/lb-status/SKILL.md) | 观察日志与控制平面，输出状态简报 |

### 技能清单（可选）

使用方仓库根目录的 `lbkit-skills.json` 按「工作类型」登记技能链，供 lb-plan 起草待办的 `技能：` 子行时参考。每条包含：

- `name`：工作类型，如「speckit 按任务区间实现」
- `scope`：使用范围，写成「适用：…；不适用：…」，lb-plan 按它判断待办归属，不按动作前缀机械匹配
- `chain`：技能链，可包含只存在于某个业务仓库内的技能
- `actions`：常见动作前缀（如 设计、开发），只作提示
- `companions`：随主技能链顺带使用的技能，每项写明 `when`
- `description`：前置条件、怎么跑、限定与来源

格式由 [schemas/lbkit-skills.schema.json](schemas/lbkit-skills.schema.json) 描述，文件首键 `"$schema"` 引用它，`"version"` 记录格式版本（目前为 `0.1.0`）。没有这个文件时 lb-* 行为不变。lb-update 负责整理：从日志的 `技能：` 子行（`lb skills extract`）和会话里实际调用的技能（`lb skills usage`）出发，以实际用法为准，整理结果经人类确认后用 `lb skills add` 写入。

## CLI

在使用方仓库根目录用 `bin/lb` 运行；除非指定 `--root`，它把当前目录当作文档根。

```sh
bin/lb check                 # 校验单个或全部项目日志
bin/lb context --json        # 文档状态 + 用于安全写入的 version token
bin/lb list                  # 列出项目日志
bin/lb task list|next        # 过滤任务 / 查看下一个交付任务
bin/lb task add|update       # 写入任务（需携带 context 返回的 --token）
bin/lb task note|artifact    # 为任务附加备注或证据
bin/lb sync                  # 按任务状态刷新阶段 emoji
bin/lb skills [--action 开发]  # 列出 lbkit-skills.json 的条目
bin/lb skills add            # 追加一条工作类型（--name --scope --chain …）
bin/lb skills extract        # 日志「技能：」子行中未被清单覆盖的候选
bin/lb skills usage          # 会话里实际调用的技能（唯一读 --root 外的只读命令）
```

所有写命令都必须携带 `context --json` 返回的 SHA-256 `version_token`；文件有任何并发变化即拒绝写入。完整契约见 [lb-cli 契约](docs/installable/lb-cli.md)。

## 共享契约（随安装分发至使用方仓库）

从[文档首页](docs/README.md)进入使用指南、贡献者文档和契约查询。仅 `docs/installable/` 分发给外部仓库，外部入口仍为 `docs/<契约名>.md`。

- [生命周期与技能入口](docs/installable/lifecycle.md)
- [协调契约](docs/installable/coordination.md)
- [日志格式](docs/installable/logbook-format.md)
- [配置与运行适配器](docs/installable/configuration.md)
- [`lb` CLI 参考](docs/installable/lb-cli.md)

## lbkit 开发

lbkit 自身的开发文档——不随安装分发：

- [开发指南](docs/dev/development.md)

[核心概念](docs/guide/concept.md)介绍 Logbook、待办、Admiral／Captain／Sailor 三角色与跨机器调度。Captain 维护目标、路径和协调状态；Sailor 执行业务工作及具体验收。人工摘要使用对话或现有 CLI 查询，不生成 TODO 附属文件，也不要求 evidence/source 索引。
