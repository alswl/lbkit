# Skill 参数注入

宿主仓库根目录的 `SKILL-PARAMS.yaml` 保存该仓的称谓、运行环境和可选能力提示；共享技能在需要这些值的步骤读取它，不把模板值当作事实。安装器在文件不存在时复制 [模板](../SKILL-PARAMS.template.yaml)，保留已有文件。`schema` 目前为 `1`，字段名拼写错误或版本不支持时先报告配置问题。

| 字段 | 使用时机 |
|---|---|
| `roles.human_owner_label`、`roles.coordinator_label` | 人类负责人和协调者的展示称谓；身份及授权仍以宿主 `AGENTS.md` 为准 |
| `runtime.herdr.workspace_id_env` | 选用 Herdr 且需在协调者工作区创建标签页时，读取环境变量名 |
| `runtime.herdr.label_prefix` | 宿主要求统一标签前缀时用于新建会话、标签页和窗格 |
| `runtime.herdr.shell` | 包装启动器是 shell 函数、需要在交互 shell 中核实时 |
| `runtime.herdr.permission_mode` | 宿主已授权自动放行时使用的工具模式；不能凭此字段扩大授权 |
| `browser.profile` | 获准的浏览器工作确需指定 Agent 专用 profile 时 |
| `auth.recurring_login_hint` | 已有可靠依据的登录节律提示；为空时不推测失效频率 |
| `documents.mind_forge_guide` | 选择 mind-forge 文档适配器时，宿主提供的映射指南路径 |

运行适配器、启动器的 `command + args`、实际模型和部署归属仍由宿主 `.agents/lb.yaml` 声明；`SKILL-PARAMS.yaml` 不重复配置候选，也不覆盖授权边界。路径相对宿主仓库根目录。不得从 `.lbkit/` 模板、别的宿主仓库、命令名或历史评测推断当前值。

值缺失、为 `null`、与宿主规则冲突，或其真实性无法核实时，先在已有授权范围内只读核实；仍需该值才能继续，就向人类说明所需字段、用途和候选值，等待答复。可选值缺失时跳过依赖该值的提前准备，不阻塞无关工作。咨询结果影响后续工作时，由人类或获准维护规则的 Agent 写回宿主文件；不要写入共享模板。
