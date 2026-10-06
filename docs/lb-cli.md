# `lb`：受保护的轻量 Logbook CLI

`bin/lb` 只使用 Python 3 标准库，面向本仓约定的 Markdown 结构化读取和极小范围编辑。它不是调度器：不会验收、派发工作、推定授权、变更清单顺序，也不会访问网络。

```sh
# 发现保守识别的主日志（默认扫描 projects/*/docs/*.md）
bin/lb list --json
bin/lb list --projects-dir records --json  # 对应宿主 documents.project_root

# 读取阶段、下一项、工作目录、链接及并发版本 token
bin/lb context projects/example/docs/logbook.md --json

# 检查一个日志，或检查所有已发现日志
bin/lb check projects/example/docs/logbook.md
bin/lb check --all --json

# 结构化状态快照（派生摘要、阶段计数、🔮 门禁、页首状态行归属）
bin/lb state projects/example/docs/logbook.md --json

# 在日志旁生成/刷新 docs/TODO.md（慢留人工视角：🚨 介入项、👱 待办、下一项、进行中）
bin/lb todo projects/example/docs/logbook.md
bin/lb todo projects/example/docs/logbook.md --dry-run   # 只看不写
bin/lb todo projects/example/docs/logbook.md --json     # 机读结构

# 同步交付阶段 H2 的 emoji 与已接管的页首状态行；先查看 dry run
bin/lb sync projects/example/docs/logbook.md --token 0123... --dry-run

# 将 context 返回的 version_token 原样带入精确写操作
bin/lb task update projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --status / --token 0123... --dry-run
bin/lb task artifact projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --artifact '产物：[CLI](../scripts/lb.py)' --token 0123...

# 在已获确认的阶段追加待办，或放在该阶段某条待办之前
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --token 0123... --dry-run
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --before-line 42 --token 0123...

# 在 Agent 待办下追加一行简短事实，kind 可为产物、阻塞、状态或交接
bin/lb task note projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --kind 阻塞 --text '🚨 请人类负责人完成登录；登录后恢复。' --token 0123... --dry-run

# 只看人工待办，或只取下一项
bin/lb task list projects/example/docs/logbook.md --human --json
bin/lb task list --status in-progress --json
bin/lb task next projects/example/docs/logbook.md --json

# 可选的仓库根目录 lbkit-skills.json：按工作类型登记技能链，字段 name、scope（使用范围）、chain、actions（动作前缀提示）、companions（随行技能：skill + when）、description
bin/lb skills --json
bin/lb skills --action 开发 --json
bin/lb skills add --name 'speckit 功能实现' --scope '适用：…；不适用：…' --chain speckit-implement --action 开发 --companion 'comment-prune=实现完成、提交前' --dry-run
bin/lb skills extract --json   # 技能未被任何条目（技能链或随行技能）覆盖的「技能：」子行原样列出，附待办原文、完成状态与回指它的工作包
```

`--root` 默认为当前目录，可把每条路径限制在合成仓库或工作树内：

```sh
bin/lb --root /tmp/fixture context projects/demo/docs/log.md --json
```

`check` 的 `DUPLICATE_TASK_TEXT` 在同 Stage 内出现未收口的同文任务时提示（全部已勾的历史重名不复告警）——它预示后续按任务原文的写命令会被 ambiguous 拒绝。`local_target` 对以 `~` 开头的链接做 expanduser 归属判断，位于 root 外时仍归 LOCAL_LINK_UNVERIFIED。

`context`、`state`、`todo` 的“下一项”只从 `Stage NN` 交付阶段的未完成待办计算；旧日志“总览”里的全局复选清单不参与调度。
`task list` 与 `task next` 采用同一交付阶段范围；`task list` 可按阶段、状态和人工归属过滤，省略日志路径时列出所有已发现日志的待办。

发现默认检查 root 内 `projects/*/docs/*.md`；`list`、`check --all`、`task list` 可用 `--projects-dir` 传入宿主配置的 `documents.project_root`，并以“恰有一个可见 H1，且有 H2 阶段或待办”的启发式识别候选；这会排除 `thinking/` 和 `prompts/`，但不是任意文章的语义分类器。`projects`、项目与 `docs` 目录都会在遍历前做 containment 校验，指向 root 外或异常的目录不会被遍历。代码围栏和 HTML 注释中的标题、待办与链接不参与解析；行尾 HTML 注释只隐藏注释部分，因此注释前的任务仍保留完整原文和可更新身份。多行注释的关闭行若随后还有结构文本，会报告 `COMMENT_STRUCTURE_AMBIGUOUS` 而不猜测解析。围栏只有以同字符、足够长度且行尾仅空白的 fence 才关闭。`context.stages[].tasks` 给出每项原文、状态、行号、仓库标记和人类标记。`bound_records` 只列正文明确链接到 `thinking/` 或 `prompts/` 的位置，绝不根据同名文件猜测绑定。

## 写入与并发保护

所有写操作（包括 `sync`）都必须提供 `context --json` 返回的 SHA-256 `version_token`。文件任一字节变化、阶段和任务原文无法唯一匹配，都会以退出码 4 拒绝写入；非法状态值属于参数错误，退出码为 2。任务由阶段标题（去除状态 emoji 后）和完整原始任务文字共同定位，不以行号定位。`task update` 拒绝修改 `👱` 或 `人工验证：` 人工项的复选框；`task artifact`、`task note` 拒绝往人类负责项写子行。`task add` 只创建未启动项，拒绝同阶段同文待办；`--before-line` 必须指向该阶段已有待办的首行。Agent 使用 `task add` 前仍须取得人类对新增事项和顺序的明确确认。`--dry-run` 不会写入文件，并输出可审阅的 unified diff（JSON 的 `diff` 字段）。

所有写命令都会在写前重新解析候选文本，并拒绝新引入的确定性 `check` 问题（例如缺失的仓内链接）。既有问题不阻止无关局部更新；阶段 emoji 暂态、显式 `[-]`、外链未抓取及仓库外本地链接未核验属于允许的提示。JSON 写结果的 `issues_introduced` 在准入通过时为空列表。`task artifact` 与 `task note` 把新子行放在既有缩进子项末尾；相同子行已存在时拒绝重复追加。`task note` 的文本以 `🚨 ` 开头且指定 `--kind` 时，标记保持在子项正文最前。

写入会在临时文件 fsync 后、`os.replace` 前再次检查 root containment 和源文件字节，随后才作同目录原子替换。这缩小常规并发编辑的覆盖窗口，但不是跨任意编辑器或恶意进程的 CAS/锁保证；冲突仍应以拒绝写入后重新读取 context 为准。

路径在读取和写入时都会解析符号链接，目标必须仍位于 `--root` 内。编辑保持 UTF-8、原有 CRLF/LF 风格及所有未触及字节；`sync` 只改可确定状态的交付阶段 H2 emoji，空阶段、含 `[-]` 的阶段和未知状态不会被判完成。`[-]` 会在检查中报告为显式不适用/跳过记录，而不是未开始或批准信号。

## 检查、状态与限制

`check` 的问题格式为 `路径:行号:代码:说明`，`--json` 返回等价结构。退出码为：0 无确定性问题（可能仍有 `LINK_UNVERIFIED` 提示），1 有确定性问题，2 命令参数错误，3 路径/读取拒绝，4 并发或写入保护拒绝。HTTP(S) 链接只报告 `LINK_UNVERIFIED`，从不请求网络；本地链接只检查其在 root 内的存在性。工具不解析任意 YAML，也不对外部文件、远程链接或 mind-forge 元数据作验证。

外部 URL（如 Forgejo PR 链接）按设计一律报 `LINK_UNVERIFIED`，属确定性提示而非结构错误；PR 链接是运行实例的身份记法，保留即可，不为消除该项把链接降级成纯文本。

## 🔮 preflight 门禁

任一待办或其缩进子项的复选框文字含 `🔮`（lb-preflight 产出、经人类确认写入的待讨论卡点）时，视为整本日志停摆：

- `context --json` 返回 `preflight_blockers`（逐项含 `line`、`text`、`indent`、`stage`）与 `preflight_clear: false`；每个任务的 `preflight` 布尔字段标出该行是否卡点。
- `check` 对每个 🔮 复选框行报告 `PREFLIGHT_BLOCKER`（确定性状态记录，与 `[-]` 的 `SKIPPED_EXPLICIT` 同类，参与退出码 1）。
- `sync`、`task update`、`task artifact`、`task add`、`task note` 一律以退出码 4 拒绝写入，报错指明行号；CLI 不提供绕过参数，解除方式只能是人类在日志文本中改写或移除 🔮 后重新取 `context`。

工具只做标记检测，不验证 🔮 来源；写入与裁决语义见 [日志格式](logbook-format.md) 与 lb-preflight SKILL。

## 页首状态行与结构化状态

面向状态 emoji 的管理优先走本脚本，不手改 H2 emoji 或机读状态段。`state --json` 给出结构化快照：整体计数（交付阶段 done/in_flight/not_started）、`summary`（派生机读串）、`next_task`、🔮 门禁及每个 `> 状态：` 行的 `owned` 归属。

页首 `> 状态：` 行以第一个 `——` 分界：前半为机读段，`sync` 在其以 🛫/🚧/✅ 开头时重写为派生串——`状态：<emoji> <首个未验收交付阶段> · [🔮 待讨论 N 项 · ]下一项：<待办原文>`（全部完成时为 `状态：✅ 全部交付阶段已完成`），并以 `summary_updated` / `summary_kept_human` 报告；后半人类注释原样保留，非 emoji 开头或无分界的叙事行视为人类正文一律不动，没有状态行的日志也不会自动新建。

运行测试：

```sh
python3 -m unittest discover -s tests -v
```

## TODO.md 人工视角

`todo` 子命令把日志内容整理成日志同目录的 `TODO.md`，面向人类扫视：🚨 需要人类负责人处理的计划外事项（取待办首行或子行中含 🚨 的文本，含具体操作与解除条件的原文）、👱 未完成人工待办、文档顺序下一项、进行中事项。没有 `[ ]` 或 `[/]` 时，仍有 `[-]` 就显示“跳过项待处置”，不宣称全部完成。文件头带机器维护注释与重生成命令，手改会被覆盖；`sync` 与 `task update/artifact/add/note` 的非 dry-run 写入在 `TODO.md` 已存在时自动重解析刷新（不存在则不自动创建，首次用 `todo` 命令开启）。该文件是派生视图，不参与解析、检查或验收判定。

## 技能接入与评测

lb-* 入口由 Agent 在对应步骤调用 CLI，共用流程见 [文档适配](../skills/lb-update/references/document-adapters.md#本仓-cli-调用)：plan 读取与检查，push 在接收后标进行中，status 查询及获准的 emoji 同步，update 在证据验收后更新状态与产物；preflight 是只读分析入口，卡点回写由技能按日志写入边界完成、不经 CLI 写子命令。脚本不自行执行这些技能，也不检查任务授权或证据充分性。

`tests/test_lb_skill_flows.py` 用合成日志运行多步 CLI 流程，验证 token 刷新、并发编辑保护、产物交接和只读查询；各技能 `evals/evals.json` 另含模型决策场景。CLI 集成测试通过不等于模型行为评测通过；后者还需在受控环境中实际运行技能并检查工具调用、文件差异及回答，不能只评分口头计划。

代码实现放在 `src/logbook_cli/`：`cli.py` 负责 argparse、写入和输出，`document.py` 负责解析与检查，`views.py` 负责状态和 TODO 派生视图，`edit.py` 负责任务文本编辑与写前候选检查。`bin/lb` 是快速入口，`python3 scripts/lb.py` 保留兼容；也可运行 `PYTHONPATH=src python3 -m logbook_cli`。`scripts/` 仅保留可直接执行的入口及评测工具。实现保持 Python 标准库，评测夹具会携带完整包。

可复跑的夹具准备、非覆盖预检及事件采集见 宿主仓库的行为评测流程。
