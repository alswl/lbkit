# <Project Name> Acceptance Logbook

<!-- Draft: the overview's and each phase's 「目标：」 placeholders are filled in by the human personally, and large prose bodies are also written by the human — the agent does not ghostwrite them; while they remain unfilled, the plan must not exit into execution. Keep the real project's delivery breakdown and linear order; do not treat the template phases as a fixed pipeline. Repeat delivery phases as needed; add a change-plan gate before concrete code or config changes are implemented. For projects with downstream evidence, first fix the immutable candidate and applicable environments, then collect evidence along the dependencies; correctness/behavior gates precede performance or runtime sampling, and human acceptance or the final decision sits at the end. Fill in categories, ownership, and status per actual results. Replace or remove example links. -->
<!-- Exit self-check: only when the three essentials — working directories, Stage division, and the todo list — are all present and manually confirmed by the user (the user writing or revising the plan personally counts as confirmation) may the plan enter lb-push execution. -->

## Overview

目标：<final deliverable and definition of done>.

非目标：

- <explicit exclusions>

SKILLS：(only skills external to the repository)

- `<skill-name>`

链接：

- [Project main entry](https://example.invalid/project)

<!-- This logbook's project directory is in scope by default and need not be listed again; list only other machines' directories confirmed by the user, grouped by 「local」 or 「remote `机器名`」. Delete empty groups; if there are no other directories, replace the whole block with 「工作目录：无额外目录（仅本日志项目目录）」. -->
工作目录：

- local
  - `~/ws/<获准的本机目录>`
- remote `<机器名>`
  - `~/ws/<获准的远程目录>`

## 🛫 Stage 01 <Real Delivery Stage>

目标：<a provable result or threshold for this phase>.

相关链接：

- [Input or acceptance basis](https://example.invalid/source)

待办：

<!-- Todos are drafted by the agent, shown first, and written in after human confirmation. Operations by the same owner delivering the same result are not split into separate items; split into sequential tasks when the owner or the acceptance gate changes. Replace each item's category with one of 设计, 开发, 测试, 部署, 验证, or 人工验证. Only phases that genuinely need deployment get a deployment item. Agent-executed items carry no ownership marker by default; human-owned items use the 「人工验证：」 prefix or a trailing 👱 marker. -->
- [ ] <分类>：<a provable deliverable result>
- [ ] 测试：<acceptance evidence tied to this deliverable's identity has met the threshold>

<!-- Below is an optional linear paradigm for implementation, performance, or runtime evidence items; pick based on real dependencies and replace the generic examples above. Report-type or simple projects should delete inapplicable candidate, deployment, performance, and independent-review items; do not invent tasks to fit the template.
- [ ] 设计：<an immutable candidate identity and applicable environment have been fixed>
- [ ] 测试：<the same candidate has passed the correctness or behavior gate in that environment>
- [ ] 验证：<after sampling prerequisites are met, raw records tied to the candidate and environment are captured against explicit thresholds>
- [ ] 验证：<an independent check sized by risk and benefit has completed within an explicitly finite number of rounds>
-->

## 🛫 Stage 02 Final Decision

目标：<the final deliverable, deviations, and remaining responsibilities have an explicit human decision>.

相关链接：

- [Final deliverable or decision record](https://example.invalid/final-record)

待办：

- [ ] 人工验证：<the final deliverable and applicable deviations are explicitly accepted, or the project is explicitly terminated>
