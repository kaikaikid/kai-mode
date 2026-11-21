# OpenBot 适配（桌面端 · 常驻 agent 团队）

> 本文件是 `adapters/README.md` §1 四步探测在 OpenBot 上的实测读数与落法。
> 只写与其它宿主不同的地方；通用规则见 README。

## 0. 一句话

OpenBot 是**常驻 agent + 持久会话**的宿主：每个角色是一个独立 agent，有自己的工作区、技能、记忆，以及多个并行话题（threads）。
它没有「原生子代理」这一层——派活＝给另一个 agent 发消息。

## 1. 四步探测（2026-11-13 实测）

| 步骤 | 读数 |
|---|---|
| ① 入口 | 桌面端 `OpenBot.exe`；本地 Local scripts API `127.0.0.1:<port>`，凭据在 `%APPDATA%\OpenBot\automation\{url,headers,token}` |
| ② 新上下文口 | **有**，三种：界面「新话题」＝并行 thread；`POST /v1/agents/{id}/context/clear` 切段；routine 每次运行独立会话 |
| ③ 权限口 | agent 级 `access`（full / workspace）＋ `autoApprove`；**无 per-tool 白名单** |
| ④ 定时口 | routines，最小间隔 3 分钟；`once` 为一次性 |

## 2. 会话语义（与一次性进程宿主的关键差异）

| 需求 | 做法 | 说明 |
|---|---|---|
| 并行临时话题 | 界面「新话题」（threads） | 独立上下文，共享人设/技能/记忆；**Local scripts API 未暴露建话题的端点** |
| 系列任务要干净起点 | `context/clear`（CLI：`openbot-cli agent new-chat <agent>`） | 切段，**立即生效**；旧会话留在历史里，agent 自己不记得 |
| 一次并行运行、不碰主会话 | routine + `runIn=thread` | 每次运行新会话，结果进 routine 自己的线程 |
| 续聊 / 追问 | 同一会话继续发消息（`POST /v1/agents/{id}/messages`） | 同一段上下文内可累积 |
| 从旧会话分叉 | 无脚本入口 | 只能人工在界面操作 |

判断「该清」：新主题、怕偏见、系列任务、产出已落盘；「不该清」：追问迭代、队友正在跑、关键背景只在对话里。

## 3. 落点

- 技能：`<agent 工作区>/.agents/skills/<名>/`；用户级本地技能 `%APPDATA%\OpenBot\local-skills\local-skill-<uuid>`
- 角色：每个 agent 的 `AGENTS.md`（渲染产物 + 团队规则段）
- 记忆：agent 自带记忆 + 团队层文件（单写者）

## 4. 审查独立性

「另一段新上下文」在 OpenBot 上＝**新话题**、**清场后的会话**、或 **routine 独立运行**。
清场是切段不是删除：旧会话仍在盘上（`provider-state/<provider>-history/<uuid>.sqlite`），但没有读取别的 agent 旧会话的官方接口。

### 角色 → 上下文操作映射（OpenBot 专属）

宿主中立的角色规则见 `roles/canon/*.md`；下表只写 OpenBot 上把这些规则落到哪个动作。常驻 agent 的旧上下文可能有复用价值，不要默认 clear；独立判断优先新话题或 routine。

| 角色/任务 | 首选 | 何时 clear（会断旧上下文） | 备注 |
|---|---|---|---|
| 康娜：系列任务、干净起点 | `kai-new-chat.ps1 <agent>` 一次后 `kai-run.ps1` 连发 | 仅当任务契约已落盘、旧上下文可丢弃 | 同一 agent 同时只有一个活动话题 |
| 提里奥：重大/最终成功审计、高风险复核 | 界面新话题或 routine（独立上下文） | 不为了审计去 clear 原会话 | reviewer canon 要求另一段新上下文；新话题须人工确认挂对 agent |
| 瑞兹：自己复查自己的方案（Critic） | 界面新话题或 routine | 不为 Critic clear 主会话 | 只看原始需求与候选方案，不继承作者推理 |
| 卓尔游侠、布莱恩、游学者、泰兰德：跨项目取证/施工/写作/设计 | 每个项目用界面新话题或 routine；连续迭代留在原话题 | 只在换任务且旧上下文无用、契约已落盘时 | 脚本无法定向指定话题，别把 A 项目后续消息发进 B 活动话题；不同项目长期并行且要常驻上下文时，考虑按项目扩 agent（需团长批准） |

选择顺序：要保留常驻上下文 → 新话题/routine；要干净起点且旧上下文没用 → clear→派；怕偏见的一次性评审 → routine。脚本侧没有「选话题 / 清指定话题」入口，`threadId` 定向未验证，不要靠它做隔离。

## 5. 边界与缺件

- 脚本侧**不能**建并行话题（`/v1/agents/{id}/threads` 返回 404）；并行话题只能从界面建。
- 同一 agent 同一时刻只有一个**活动**话题；话题之间不共享上下文。
- 跨宿主：Codex 等「一次调用＝一个会话」的宿主不需要清场，直接新调用即可；不要把 OpenBot 的清场动作套过去。
