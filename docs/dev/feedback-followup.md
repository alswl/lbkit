# Feedback 后续实施与验收

日期：2026-10-11。基于人类“方案确定就继续处理”的授权，落实 `lb-update` 双入口，并继续验收已改契约的反馈。未升级版本、提交、推送或更新真实消费仓。

## 双入口实施

保留一个 `lb-update`，先区分用户意图，再选择内部写入模式：

- 获取现状：读取授权范围内已有原始记录，核实后写回进度；新执行和超范围调查不包含在此次更新中。
- 重读人类修改：对齐当前目标、约束、顺序和验收口径；只有可靠旧版才报告差异。默认只读，不写正文、Thinking、索引或绑定，不安装依赖，不运行 sync，不派发执行。
- 混合请求：先重读，再以新口径核验证据并执行已授权写回。人类勾选保留为人类决定，不冒充独立验证；旧 token、旧候选和旧验收不能套到新口径。

技能说明、中英文 README、configuration 和 lifecycle 已同步；format/evidence/close 保留为内部写入模式。新增评测 37–39，先记录案例并快照旧技能，再实施修改。

## 实际执行证据

以下均为隔离临时消费仓和明确标记的合成业务材料；工具实际执行，业务事实为测试输入。未访问远端业务系统，未用这些材料勾选真实用户日志。主代理核对了命令结果、文件差异及哈希。

| 对象 | 实际执行与观察 | 范围 |
|---|---|---|
| lb-update 37、38 | 真实读取当前日志、CLI context、mf 绑定；有旧版时识别门槛变化，无旧版时只总结当前内容。两次重读前后全部 23 个 fixture 文件哈希一致 | 只读语义与文件保持，不证明所有缺依赖环境行为 |
| lb-update 39 | A 取消、B 通过及新增撤离要求；实际两次 note 预览及 CAS 写回，sync/check 成功。仅正文、Thinking、source 指向变化，人工字段和未完成状态保留 | 不覆盖当前文件仍有过时 `[x]` 的重新开项流程 |
| scaffold，Issue 8、9 | 真实 mf 建立 Prompt/Thinking 绑定及索引，lb check 无诊断。产物与模板三槽替换逐字一致，单阶段、人工关口保留，无 front matter skills。缺模板节/槽位的旧式模板被拒且目标不存在 | 单次受控技能执行；fixture 已确认全部槽位，不等于真实人类完成了业务审阅 |
| plan，Issue 16 | 首次生成口述史计划，技能子行仅为 mf-write，无用途/条件说明；初稿与最终文件哈希相同，真实 mf/lb 检查通过 | 单次非软件场景，未执行写作或审阅 |
| runtime，Issue 12、27 | 模拟 adapter 的建议输入场景保持 32 个 fixture 文件不变；未知上下文场景实际写入交接文件，保留累计轮数和工作目录 | 无真实 Herdr 退出能力；仅记录模拟轮换请求，未关闭会话或完成轮换，因此两条仍开放 |
| preflight，Issue 19、20 | 旧 3 项路线变为 4 项，逐项记录当前定义、目标环境及缺口，结论 amber。远端未知时实际完成独立授权的本地技能维护；原日志 token 不变，真实 mf/lb 检查通过 | Issue 20 的阻塞隔离已验收；Issue 19 仍缺真实目标机定义与能力核验 |

桌面新旧对照另外运行了三个案例，每版本各一份响应，均为 9/9 断言通过。旧版和新版由不同代理执行，每个代理处理三个案例；不是独立重复试验，也不能据此声称新版成功率提升。文件写入正确性依据上表实际执行，不依据桌面回答。评测工具未提供逐案例 token/时延，未将默认零值当成实测。

## 证据位置与复现

详细原始命令、输出和 fixture 留在执行位置，本仓只记录指向及验收结论：

- 双入口：`/var/folders/qp/fw17s6nj6r7bfd8fft_1lt640000gn/T/lbkit-feedback-eval-lkq34d05/`；`cases.json`、`iteration-1/` 为桌面输入/输出/评分，`review.html` 是可查看的结果页。`live-update/report.md`、`commands.json`、`case39.diff` 和前后哈希为实际执行证据。
- scaffold：`/tmp/lbkit-scaffold-acceptance-20261011/`；`prepare.py`、`fill.py`、`commands.jsonl`、`assertions.json`、`hashes.json`、`report.md`。生成日志 SHA-256：`e15958d7ccbdfe062e8a89be13fdb5c1ca6fe9dd583f3969ca00847fad1c61b6`。
- preflight：`/tmp/lbkit-preflight-acceptance-20261011/`；`run.py`、`transcript.jsonl`、`coverage.json`、`local-skill-maintenance.diff`、`SHA256SUMS.json`、`report.md`。保留的日志 token：`d6256f57b2a72b054f27997f48c2608b3d4612847b37b8756a81102390638cf9`。

- plan：`/tmp/lbkit-plan-acceptance-20261011/`；初稿、命令记录、定义哈希、报告及复现辅助脚本齐备。初稿及最终 SHA-256：`31fe40f1aa75a13f6022290b064f9e30c199f4a4a0e1a94c1fae6b0c581668ae`。
- runtime：`/tmp/lbkit-runtime-acceptance-20261011/`；`run.py`、`commands.json`、追加式 `actions.jsonl`、前后哈希及 `report.md`。模拟 adapter 不支持经验证的安全退出，保留会话是本轮实际结论。

临时证据可能随系统清理失效；复跑需要新的隔离目录、当前 lbkit 和已安装的 mf。scaffold 首次 setup 在 git init 后执行 mf init 因目录非空失败，已保留失败记录，并在新目录先 mf init 再 git init 恢复。未将环境准备失败计为技能失败。mf index 返回空 identity/path 但 show 能解析绑定的现象只记录为工具观察，未改动 mf。

## 验收边界

当前全量 96 项 unittest 和文档链接检查通过。没有把剩余模型场景定义算成已执行，也没有把本地合成试跑算成 Herdr、internal pipeline、市场发布或多机安装的实机验收。逐项最终状态见 [反馈状态](feedback-status.md)。
