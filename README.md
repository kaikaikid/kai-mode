# kai-mode —— 机场体系的技能与通用剧本仓库

> **状态：0.2.0（2026-10-22 同步 ADR-0137）。** 技能与协议已对齐项目仓现行机场体系
> （ADR-0137：四角色＋30 分钟塔台轮巡）；**切换前项目仓仍是唯一直播源**，本仓同名文件是 staging。
> 旧五角色（Tower/Ground/Coordinator/Group-A/B）、租约、班次、handoff 按铃那套已随 ADR-0137 退役
> （git 历史可捞）。

## 这是什么

kai-mode 是「一句话需求 → 票 → 排班 → 施工 → 审查 → 发货 → 关票」的闭环框架。这个仓库只放**跨项目通用**的部分：

- 技能（正本）：`kai-mode`（入口）、`set-kai-mode`（安装）、`loop`（单票闭环导航）、`地勤` / `塔台` / `机长` / `副机长`（四角色）、`航班信息`（板工坊：可配信息源 → 每板一份自包含脚本 → 归档到项目仓板库）
- 协议正本：`loops/loop-protocol.md`（v5）
- 通用剧本：任务合同、执行三职、可靠性、审批、审计、上下文、验收
- 可执行契约：`task` / `acceptance` / `event` schema
- 宿主适配器：Qoder（30 分钟塔台定时＋按铃子会话）、opencode/codex 备胎
- 项目配置模板：`templates/kai-mode.project.json`

项目自己的 ADR、票、日报、门禁脚本与项目专用剧本留在项目仓。

## 角色（单责）

| 角色 | 口令 | 只负责 | 绝不做 |
|---|---|---|---|
| kai-mode 入口 | `/kai-mode` | 一句话需求 → 判断 → 拷问 → 定稿 → 拍板 → 路由 | 执行 |
| set-kai-mode 装配 | `/set-kai-mode` | 安装、探测、装定时器、doctor、缺件登记 | 日常施工 |
| 地勤 | `/地勤` | 对话、规划、开票（六件套＋`ready-for-agent`）、收想法 | 写码、push、派施工 |
| 塔台 | `/塔台` | 30 分钟轮巡：先排班（日表 5–10 行）、后发货（合并/push/关票） | 写码、替审查下结论 |
| 机长 / 副机长 | `/机长` `/副机长` | goal 模式各管 2 张票；每票 1 施工＋1 审查（新上下文）＋2 机动子代理 | 写码、push、合并 |

**权限硬线（ADR-0137）**：塔台**独占** push 与关票；机长/副机长只管理不写码；地勤只开票；记录面三分——日表只由塔台写、状态只写 Issue 评论、代码只进分支。

## 闭环

```text
用户一句话 → /kai-mode（拷问→定稿→拍一次板）
                    │
                    ▼
              地勤（开票：里程碑＋ready-for-agent＋AC＋禁区）
                    │  后备池 = 开放票
                    ▼
              塔台（先排班：写两张日表）
                    │
                    ▼
        机长 ──┬── 机长 ──┐   ← 主/副各 2 张在飞、6 子代理
        副机长 ┘          │
       （每票：施工子代理[独立 worktree] → 审查子代理[新上下文]）
                    │  verdict=pass ＋逐条 AC 证据 → 「待发货」
                    ▼
              塔台（再发货：批内合并 → 收尾门一次 → push 一次 → 关票）
                    │
                    └── 库存下降 → 下一轮补排班
```

记录面三分：**日表**（塔台写，排班视图）＋ **Issue 正文与评论**（唯一事实源）＋ **分支与提交**（代码与回执）。断点三件套 = 这三样，继任者按它续跑。

## 交接与断点（省叙述，不省证据）

- 票进入日表即完成领取；状态只由机长写 Issue 评论（开工/施工完成/审查完成/待发货/卡点）。
- 施工回执 ≤40 行：`ticket/role/verdict/files/commits/checks/summary/evidence/risks/next`；禁止贴 diff 全文与原始日志。
- 塔台发货**只认审查子代理的判词**（`verdict=pass` 且逐条 AC 有证据），不认机长口头总结。

## 可靠性（`playbooks/reliability.md`）

- 单票失败 **1 次重试**；再失败 → 卡点停票；同错连发触发熔断。
- 上限全部进项目配置 `limits`；到限写 `blocked`/`failed` 留读数，不许「再试一次看看」。
- 红线（花钱/对外真发布/不可逆改历史/删未提交内容）→ **只停那张票**，立即报人。

## 目录

```text
skills/           八个技能（入口/安装/loop/四角色/航班信息）＋ set-kai-mode/scripts/magpie-sync.py
skills/航班信息/   板工坊：SKILL.md ＋ templates/（生成器模板＋板配置样例）＋ scripts/（脚手架/索引页/刷新）
loops/            loop-protocol.md（v5 单票闭环正本）
playbooks/        task-contract / execution-roles / reliability / approval / audit / context / acceptance
schemas/          task / acceptance / event
adapters/         qoder（30 分钟塔台定时＋按铃子会话）、opencode、codex
templates/        kai-mode.project.json（schema 2：日表/轮巡/名额/限额/审批/审计）
docs/             设计基线吸收记录（V1.0 对照与偏离，沿革）
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填主树解释器/node 绝对路径与门禁命令。
2. 把本仓 `skills/` 与 `loops/loop-protocol.md` 落到项目仓 `.ai/skills/` 与 `loops/`（或由 `set-kai-mode` 按宿主装配）。
3. `/set-kai-mode` 探测宿主能力（定时口 / 会话创建口 / shell 启动器），按四档装配 30 分钟塔台定时器；缺件如实登记。
4. 项目仓 ADR 记角色与权限裁决（先例：ADR-0137）；开票走地勤六件套；用一张真票走通「排班→施工→审查→发货」全链路做自证。
5. 项目专用路径、票号、job id 只进项目配置与本机文件，不进本仓技能正文。

## 当前不做

- 不改项目仓的日表、Issue、门禁脚本——那些归项目仓与各角色。
- 不把项目专用路径、票号、job id 写进技能正文。
- 切换 magpie-sync 的 root 到本仓之前，项目仓 `.ai/skills/` 仍是宿主装配的直播源（见 `MIGRATION.md`）。

## 判据正本

- 机场体系唯一现行裁决：项目仓 `docs/artifacts/adrs/ADR-0137-airport-rebuild-four-roles.md`（supersedes ADR-0131/0132/0133/0135/0136 的对应裁决，残留表在该 ADR §取代明细）
- 单句入口与拍板：项目仓 `docs/artifacts/adrs/ADR-0130-kai-mode-and-dual-lane-rewire.md`
- 单票闭环协议：本仓 `loops/loop-protocol.md`（v5）
- 设计吸收沿革：`docs/design-v1-absorption.md`
