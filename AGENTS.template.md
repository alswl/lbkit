# 协作约定（由 lbkit 生成，请按本仓实际约定补充）

本仓以项目 logbook 为目标、任务、授权和验收的共同入口，接入 [lbkit](.lbkit/README.md) 共享的技能、契约与 CLI。角色称谓可在 `lbkit-agents.yaml` 的 `roles` 中按本仓文化配置（如 Admiral / Captain / 船员）；称谓不改变权限边界。

## 角色分工

- **人类负责人**：掌握目标、风险接受与不可逆决定。日志中的目标与待办文字由人类亲自维护，Agent 不得代写或改序。
- **协调者**：维护每份日志的共享状态、依赖与验收；规划并把有边界的工作包派发给执行 Agent，核验回传后写回日志。
- **执行 Agent**：在授权范围与隔离工作树内交付工作包，附可验证证据；结果、范围、证据缺一不可。

计划确认不等于执行授权；Agent 永远不写人类负责的日志条目。授权、证据与人工关口是契约而非选项，见 [协调契约](docs/coordination.md)、[证据规则](docs/evidence.md) 与 [生命周期](docs/lifecycle.md)。

## 适用边界（待补充）

- 仓库负责人：
- 授权的工作目录与机器归属：
- 敏感性分级与模型部署约束（对应 `lbkit-agents.yaml`）：

未列出的仓库或目录一律不得访问；需要扩大范围时先说明目标与用途，经人类明确确认。

## 按需入口

| 请求 | 技能 |
|---|---|
| 建立、刷新 `.lbkit` 子模块与本地入口 | [lb-init](.agents/skills/lb-init/SKILL.md) |
| 从模板填空初始化项目 logbook | [lb-scaffold](.agents/skills/lb-scaffold/SKILL.md) |
| 核对目标、起草待办、设计阶段与工作包 | [lb-plan](.agents/skills/lb-plan/SKILL.md) |
| 只读预检：路线规划与可行性分析 | [lb-preflight](.agents/skills/lb-preflight/SKILL.md) |
| 在授权范围内推进、恢复并监听执行 | [lb-push](.agents/skills/lb-push/SKILL.md) |
| 核验证据、维护记录、记录人工收尾 | [lb-update](.agents/skills/lb-update/SKILL.md) |
| 观察日志与控制平面，输出状态简报 | [lb-status](.agents/skills/lb-status/SKILL.md) |

技能名不扩大操作权限；`lb-push` 指项目推进，不代表 Git 推送。

## 环境与文件

- 共享实现与指令由 `.lbkit/` 子模块提供，背景见 [.lbkit/AGENTS.md](.lbkit/AGENTS.md)；根目录 `CLAUDE.md` 是指向本文件的链接。
- `lb-*` 技能入口链接在 `.claude/skills/` 与 `.agents/skills/`，共享契约链接在 `docs/`，日志格式见 [日志格式](docs/logbook-format.md)。
- 本仓自有文件：项目日志、本文件、`lbkit-agents.yaml`（模型、运行时与协作参数），以及可选的 `lbkit-skills.json`（按工作类型登记的技能清单，由 `bin/lb skills` 读写）。
