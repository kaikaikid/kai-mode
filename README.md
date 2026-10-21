# kai-mode —— 机场体系的技能与通用剧本仓库

> **状态：0.1.0 staging（2026-10-21）。** 这是新家，不是直播面：项目仓现有的旧剧本、令牌与定时任务**未切换**；等 #1829 落地后按 ADR-0134 D8 迁移。

## 这是什么

kai-mode 是“一句话需求 → 票 → 排班 → 施工 → 发货”的闭环框架。这个仓库只放**跨项目通用**的部分：

- 角色技能（薄入口）：Tower／Ground／Coordinator／Group-A／Group-B
- 通用剧本：排班、发货、调度、组内跃迁、验收
- 可执行契约：handoff／status／acceptance／queue schema
- 宿主适配器：Qoder 子会话按铃、opencode/codex 备胎、探测与缺件登记
- 项目模板：`.ai/kai-mode.project.json`

项目自己的 ADR、票、日报、`plan.json`、运行时脚本与项目专用剧本留在项目仓。

## 角色（单责）

| 角色 | 技能 | 只负责 | 绝不做 |
|---|---|---|---|
| 塔台 Tower | `/tower` | 排班、航线编排、队列、租约、水位/刹车 | 并车、push、写产品代码 |
| 地面管制 Ground | `/ground` | 并车、收尾门、push、关票、清账、回收已并树 | 排班、发租约、写 `plan.json` |
| 通报协调 Coordinator | `/coordinator` | 读状态算该叫谁；停机牌/闸门/冷却；异常才按铃 | 施工、排班、发货 |
| Group-A / Group-B | `/group-a`、`/group-b` | 按队列连飞、租约内施工、子代理并行、本地提交、验收证据 | 并车、push、排班 |
| 入口 | `/kai-mode` | 一句话需求 → 拷问 → 定稿 → 拍板 | 执行 |
| 装配 | `/set-kai-mode` | 安装、探测、建任务、doctor、回写中央库 | 日常施工 |

## 闭环

```text
用户一句话 → /kai-mode → 票＋计划
                         │
                         ▼
                 Tower（排班/队列/租约）
                    │            ▲
                    ▼            │ 要新排班
              Group-A/B ─────────┘
              （跃迁·子代理并行）
                    │
                    │ 要发货（handoff）
                    ▼
                 Ground（并车/门/push/关票）
                    │
                    └── 库存下降 → Tower 补排班

Coordinator：低频看门狗
只处理链断/启动失败/停机牌/闸门变化；正常链路不经过它
```

## 交接契约（省叙述，不省证据）

handoff 是一行 ≤500 B 的 JSON，只当“可验证指针”：

```json
{"schema":1,"from":"group-a","to":"ground","tickets":[1829],"commits":["c592c8ec6"],"branch":"exec/1829-v4-knife2-3","acceptance":{"path":".git/kai-scope/acceptance-1829.json","sha256":"..."},"at":"2026-10-21T14:30:00+08:00","seq":7}
```

- 必带：`schema/from/to/tickets/commits/branch/acceptance(+sha256)/at/seq`；有阻塞加 `blocker`。
- 启动器按铃前当门卫：schema、目标注册档、commit 存在且可达、Ground 的 `verdict=pass` 且 `unverified` 为空、令牌 free；任一不过写 `activation-failed`。
- 接收方二次核验；Ground 不信 handoff 的结论，自己跑 close-gate／push-preflight。
- 状态卡只写 `result/tickets/commits/blocker/unverified`；长叙事进日报一次。

## 目录

```text
skills/           五个角色技能＋入口/装配（后续迁入）
playbooks/shifts/ 通用剧本：README、tower、ground、coordinator、group
playbooks/acceptance.md
schemas/          handoff / status / acceptance / queue
adapters/         qoder（子会话按铃）、opencode、codex、探测与缺件
templates/        kai-mode.project.json、项目剧本模板
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填路径、命令、`activation`、WIP。
2. 项目 `.ai/scope/shifts/` 放项目专用剧本（可从 `playbooks/shifts/` 复制后改路径/命令）。
3. `/set-kai-mode` 探测宿主能力：
   - Qoder：推荐“只按铃子会话”（`create_chat_session` → 子会话 `qoder_cron run`）。
   - 其他宿主：探测 run 口／会话创建口／shell 启动器，把 2–4 个互斥选项交给用户选。
4. 建新班次并自证：发一次 handoff，目标 `on-duty-<lane>.json` holder 非空或 `runningAt` 非空；重复发只起一次。
5. 确认新链路后，再停用旧班次；旧 job id 至少保留一个试点周期。

## 当前不做

- 不改项目仓的 `.ai/scope/shifts/`、`on-duty-*`、`plan.json`、`dispatch-queue-*`。
- 不建/删任何定时任务；切换阶段由 `/set-kai-mode` 按 ADR-0134 D8 执行。
- 不把项目专用路径、票号、job id 写进技能正文——它们属于项目配置与项目剧本。

## 判据正本

- 角色拆分与迁移：项目仓 `docs/artifacts/adrs/ADR-0134-role-split-tower-ground-coordinator-groups.md`
- 按铃适配器与 token 预算：项目仓 `/set-kai-mode` 的「启动适配器」节
- 跃迁协议：项目仓 `loops/loop-protocol.md`（本仓库的 group 剧本只指路，不复制判据）
