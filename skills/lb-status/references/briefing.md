# Chat briefing example

This example is fictional. Its counts illustrate the reporting rules, not a
required project shape. Link real replies to freshly read source lines under the
[locator contract](../../../docs/installable/coordination.md#human-facing-logbook-locators).

**Captain · 示例资料核验总览**

目标：核实资料来源，交付可审阅的结论。
当前：调查结果已交付；独立核对缺固定资料快照，最终确认待后续审阅。

核对时间：<实际时间与时区>。当前日志记录模式；历史结果按各自适用版本呈现。

```text
记录任务完成率
████████████░░░░░░░░  60% · 6/10项
6完成 · 1阻塞 · 3待办

Stage              Tasks                   完成
───────────────────────────────────────────────
S01 范围确认       ■ 2项                    2/2
S02 资料调查       ■ 4项                    4/4
S03 独立核对       ! 快照缺失 · □ 复核      0/2 ←
S04 结论交付       □ 人审阅 · □ 交付        0/2

■ 完成    ! 阻塞    □ 待办
```

人工待办 1 项，已包含在待办 3 项内。比例只描述记录条目，不代表工作量或结论准确率。

| 已有成果 | 数量／版本 | 状态 |
|---|---|---|
| 核对范围 | 2 类资料 | 已确认 |
| 调查结论 | sample-a | 已交付 |
| 来源目录 | 18 条 | 待独立复核 |

实际答复在成果旁提供当前产物直达链接和核实过的 Logbook L行号；本虚构示例不制造链接。

当前阻塞是独立核对缺少固定快照，由调查责任方提供。调查记录完成不代表独立核对
通过；结论审阅等待核对结果，不把普通后续工作也称为阻塞。

| 责任方 | 动作 | 交付 |
|---|---|---|
| 调查 Agent | 固定资料与结论版本 | 快照及来源入口 |
| 核对 Agent | 按已定范围独立核对 | 发现与未核验项 |
| 人 | 核对结束后审阅结论 | 接受或具体修订意见 |

本次未派发；人工审阅前先由 Agent 补齐材料。下一任务链接和准入条件以实际日志为准。

仓库：<实际分支与HEAD> · <实际工作树状态> · PR 未实时核实。
检查：<结构错误数> · <未核验链接处数> · 投影 stale；运行状态未知。

Angle-bracket fields above are instructional placeholders, never literal output
or permission to invent data. An unavailable field can be marked unknown or
omitted. The recorded role, four Stages, counts and human review belong only to
this fictional example. Use the user's language and actual route in real replies.

## Adaptations

- **Terminated:** lead with "Route terminated; no next Task is schedulable".
  Show historical counts and open handoff responsibilities; omit the percentage
  bar. Do not convert unchecked Tasks to cancelled or show termination as 100%.
- **No Tasks:** report zero recorded Tasks and no applicable completion ratio;
  explain the available goal, missing route and existing decision owner.
- **Partial or unknown:** label the known subset and coverage gap; do not draw
  a percentage bar with an invented denominator.
- **Narrow question:** answer the specific blocker, owner and clearance condition;
  a complete dashboard is unnecessary for "who is holding the candidate?".
- **Deferred earlier work:** a registration-only Task may remain unchecked before
  the current actionable Stage. Name its explicit deferral and the route decision
  permitting later work; do not select it merely because it is first unchecked.
  A paused Task likewise needs a confirmed exception and independent prerequisites
  before work can pass it. Never infer the exception from the layout.
- **No human action:** keep the actual Agent duties and say no human action is
  needed for this step. Do not introduce a review row just to match the example.
- **Large or narrow-screen route:** keep the main bar, current Tasks, material
  blockers and gates; compress other Stages before folding them into a labelled
  remainder. Keep folded and visible counts reconcilable. Do not print a wide
  table, microscopic labels or a full inventory to satisfy a nominal one-page rule.
- **Git and check limits:** report ahead/behind from local tracking data and state
  the freshness limit. Use check categories, or codes for older outputs, to
  identify structural errors, broken links, placeholder notices and unverified
  link occurrences. Report merge and draft/WIP state only from applicable evidence.

## beautiful-mermaid rendering

Use an existing host renderer or installed package documented by the host. The
[upstream API](https://github.com/lukilabs/beautiful-mermaid#readme) provides
`renderMermaidASCII` for Unicode/ASCII output and `renderMermaidSVG` for SVG.
The following is an integration recipe for an already available package, not a
command to show in the status reply or a reason to install dependencies:

```javascript
import { renderMermaidASCII } from 'beautiful-mermaid';
const diagram = 'graph TD; A[Candidate missing] --> B[Verification blocked]; B --> C[Human review pending]';
const rendered = renderMermaidASCII(diagram, { colorMode: 'none' });
console.log(rendered);
```

Use only dependencies verified in the Logbook. Output the resulting text in a
plain text block inside chat, not the Mermaid source or JavaScript. Disable ANSI
for Markdown chat; `useAscii: true` offers a basic-character fallback. Prefer
top-to-bottom layout when width is unknown. Keep labels short, with full Task
names and locators in adjacent prose. Check Chinese and emoji display widths:
reuse a host helper that handles wide characters, or use short ASCII node labels
with a nearby translated legend if alignment cannot be verified. A renderer
failure falls back to a hand-written text summary without repairing the host.

For an image-capable host, SVG can be rendered in memory through its existing
display tool. Do not create persistent files for ordinary status. If the host
needs temporary rendering files, use its approved scratch area and report no
consumer document or state changes. A saved SVG alone is not an inline diagram;
retain a readable chat summary when inline image display is unavailable.
