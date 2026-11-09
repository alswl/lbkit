# 协作等待与事件恢复设计原则

本文保留长期架构边界，不作为已实现 API 清单或现场验收记录。具体功能接口由对应规格与安装契约维护；实施前不得把拟议命令当作现有能力。

## 分层

观察层复用 `wait_state.observe` 的纯 reducer，维护完整 binding、cursor 和通知去重。宿主投递层优先使用原生事件机制：Claude Code 优先 Monitor，前台 `lb agent wait` 为备选。处理层独立保存未解决事件与处理事实；通知送达或 continuation 前进不构成处理确认。

流式和单次等待共用观察与持久化逻辑。Monitor 是宿主工具，不是新建监控 Agent。CLI 不实现新的 turn scheduler，不引入常驻服务或外部消息依赖。

## 持久化与并发

受管观察状态独立于 execution 的派发权限投影，使用稳定文档身份定位。游标与对应事件必须在一个原子事务中保存，保存成功后才输出通知。working 重新布防也需保存；相同采样不写心跳。

listener 锁覆盖受管等待生命周期；writer 锁只覆盖 CAS 和原子合并；binding action 锁保护答复及核对。锁序为 listener（若需要）、排序后的 action（若需要）、state；state 锁内不等待其他锁。保证仅适用于同一协调位置的合作入口，不覆盖原始只读调用或分布式副本。

领域模型仅保留 Observation、Event、Answer；binding、cursor、listener 与处理历史是对象内部状态。配置目标与执行等待分离，处理入口按延期、评估关闭、提交答复和送达核对表达，不暴露通用 record 写接口。

取消由宿主控制对应工具进程，清理只涉及自有等待子进程。支持有界信号清理，保留重复取消回收测试。历史 PID 或 active 字段不能证明存活；恢复依据锁和可验证的进程/宿主事实，不盲杀 PID。

目标调整必须先停止 listener，再显式更新。保留未变 cursor 和退役目标的未处理事件；未决送达阻止受影响 binding 被直接替换。

## 问题答复

自动答复需要原生身份、稳定 question ID、提交接口及问题级确认能力。普通 idle-only prompt 不能冒充 blocked answer。无能力时明确拒绝；实现 capability_unavailable 分支不代表自动答复成功路径已支持。

外部提交前保存 unknown 意图；submitted 不等于 confirmed。回执丢失、超时或 idle 不能授权重发，换 operation ID 也不能绕过未决操作。caller 事实保持 caller 来源；外部 UI 动作不受准备意图返回后的 CLI 锁保护，不能宣称 exactly-once。

原生身份、终端关联和消息可达性分别验证。不能用 pane、昵称或 caller 声称的 thread ID 填补缺失身份，也不通过外部通信自动 fallback。

## 兼容与验收

原始 wait 保持只读；受管模式必须显式启用并遵守 context token。消费者自主采用模板和技能，不自动改写其 AGENTS、配置或业务记录。版本与格式编号仅由负责人授权。

分别验证本地存储/CLI、技能行为、真实 runtime、宿主投递。真实验收使用一个 Captain 与两个独立 worker；区分 Monitor 投递、前台同 turn 返回和 post-turn 调度。无事件等待记录实际 yield 与模型续等次数，不推算 token 节省比例。未采样事件、落盘前崩溃以及缺少上游能力的边界必须如实保留。
