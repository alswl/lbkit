# lbkit

[English](README.md) | [中文](README.zh-CN.md)

可复用的 Logbook 协调技能、Markdown 契约，以及面向人机协作交付的 `lb` CLI。

## 概述

**lbkit** 是一套共享工具包，以 `.lbkit` Git 子模块形式挂载到使用方仓库。它提供协调技能、文档契约和 CLI，让人类负责人、协调者 Agent 与执行 Agent 通过一份纯 Markdown **日志（logbook）**交付真实项目——日志是唯一的调度事实来源。

- **人类负责人** — 掌握目标、风险接受与不可逆决定
- **协调者 Agent** — 维护每份日志的共享状态、依赖与验收
- **执行 Agent** — 交付有边界的工作包，并附可验证证据

授权边界、证据规则和人工关口是契约，不是可关闭的选项。计划确认不等于执行授权；Agent 永远不写人类负责的日志条目。

## 安装

在本仓库的一个检出中，用一条命令安装到另一个 Git 仓库：

```sh
./bin/lbkit install --repo /path/to/logbooks --source https://github.com/alswl/lbkit.git
```

当前检出已有 `origin` 远端时可省略 `--source`。先加 `--dry-run` 可以预览全部 Git 与链接操作。

该命令会添加 `.lbkit` 子模块、链接 CLI / 技能 / 共享文档、在缺失时复制 `SKILL-PARAMS.template.yaml`、在缺失时生成 `AGENTS.md` 桩（内容为占位协作约定，需按本仓实际规则补充）、创建 `CLAUDE.md -> AGENTS.md` 链接，并在缺失 `minds.yaml` 时初始化 mind-forge 仓库（`minds.yaml` + `projects/`，经 `mf init` 生成；未安装 `mf` 时跳过并提示），最后检查 `bin/lb --help`。它拒绝覆盖已有文件，也不会代替你提交或推送任何一个仓库。

### 不依赖单独检出

机器上没有 lbkit 检出时，先在目标仓库手动添加子模块，再从 `.lbkit` 内运行 install：

```sh
cd /path/to/logbooks
git submodule add https://github.com/alswl/lbkit.git .lbkit
./.lbkit/bin/lbkit install
```

install 检测到 `.lbkit` 已是注册的子模块后会跳过 Git 操作，直接补链接和模板；`--repo` 默认是当前目录，在仓库根目录运行时可省略。

使用方仓库拥有项目日志、`AGENTS.md`、`.agents/lb.yaml` 和 `SKILL-PARAMS.yaml`；lbkit 拥有共享实现与指令。安装后的链接结构：

```text
.agents/skills/lb-*  -> ../../.lbkit/skills/lb-*
.claude/skills/lb-*  -> ../../.lbkit/skills/lb-*
bin/lb               -> ../.lbkit/bin/lb
bin/lb-anywhere      -> ../.lbkit/bin/lb-anywhere
bin/lbkit            -> ../.lbkit/bin/lbkit
docs/<shared>.md     -> ../.lbkit/docs/<shared>.md
```

只链接入口。CLI 实现（`scripts/lb.py`、`src/logbook_cli`）留在 `.lbkit` 子模块内——`bin/lb` 通过自身路径解析到它们。

### 任意目录运行

`bin/lb` 需在仓库根目录运行。若想在任意使用方仓库的任意子目录都能直接敲 `lb`，做一次链接即可：

```sh
ln -s /path/to/repo/bin/lb-anywhere ~/.local/bin/lb
```

wrapper 会向上找到最近的 `bin/lb`，切换到该仓库根目录再执行——执行的永远是该仓库钉住的 lbkit 版本。

## 技能

| 技能 | 职责 |
|---|---|
| [lb-init](skills/lb-init/SKILL.md) | 建立或刷新 `.lbkit` 子模块与本地入口 |
| [lb-scaffold](skills/lb-scaffold/SKILL.md) | 为真实项目创建工作流实例日志 |
| [lb-plan](skills/lb-plan/SKILL.md) | 核对目标、起草待办供确认、设计阶段与工作包 |
| [lb-preflight](skills/lb-preflight/SKILL.md) | 只读预检：路线规划与逐步可行性分析 |
| [lb-push](skills/lb-push/SKILL.md) | 在已授权范围内派发、恢复并监听执行 |
| [lb-update](skills/lb-update/SKILL.md) | 核验证据、维护记录、记录人工决定与收尾 |
| [lb-status](skills/lb-status/SKILL.md) | 观察日志与控制平面，输出状态简报 |

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
```

所有写命令都必须携带 `context --json` 返回的 SHA-256 `version_token`；文件有任何并发变化即拒绝写入。完整契约见 [lb-cli 契约](docs/lb-cli.md)。

## 共享契约（随安装分发至使用方仓库）

本仓库有两个文档目录：`docs/` 存放分发给使用方仓库的共享契约（安装时链接进其 `docs/`）；`dev-docs/` 存放 lbkit 自身的开发文档，**不**随安装分发。

- [生命周期与技能入口](docs/lifecycle.md)
- [协调契约](docs/coordination.md)
- [日志格式](docs/logbook-format.md)
- [证据规则](docs/evidence.md)
- [配置与运行适配器](docs/configuration.md)
- [技能参数](docs/skill-params.md)
- [`lb` CLI 参考](docs/lb-cli.md)

## lbkit 开发

lbkit 自身的开发文档——不随安装分发：

- [开发指南](dev-docs/development.md)
