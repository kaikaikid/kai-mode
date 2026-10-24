---
name: loop
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "loops/loop-protocol.md"
    note: "单票闭环唯一详细源"
description: >
  机长 / 副机长共用的单票闭环（不是用户入口）。判据与本技能冲突时以 `loops/loop-protocol.md` 为准。
  触发：由 `/机长`、`/副机长` 自动带入；「loop」不是口令。
version: 5.3.1
updated: 2026-10-24
allowed-tools: Read Grep
compatibility: Host-agnostic
dependencies:
  skills:
    - name: tdd
      reason: "§三.3 施工「先红后绿」的方法（外部技能，本仓不 fork）"
    - name: code-review
      reason: "§四 审查的方法（外部技能，本仓不 fork）"
    - name: diagnosing-bugs
      reason: "§七 连续失败时的诊断方法（外部技能，本仓不 fork）"
---

# loop

本技能只是导航：**怎么做**看 [`loops/loop-protocol.md`](../../loops/loop-protocol.md)，
**什么不能碰、什么自己定**看角色技能。流程叙事、回执详略和机动子代理都是可省的负担；
只有围栏、回执上限（住 `loops/loop-protocol.md` §五）与收工复查是硬约束。

## 一张票

开工评论 → 施工（独立 worktree，先红后绿）→ 施工完成评论 → 新上下文审查
→ `fail` 修 1 次再审 → `pass` 后把判词原样写「待发货」。

## 收工

做完一张票先跑收工门禁（**不许早停**是硬约束）。门禁脚本归**项目仓**，路径从项目配置实例
`gates.captain_preflight` 读（`null` 或缺配置 → 报缺件，不猜路径）：

```bash
python <gates.captain_preflight> --lane main|deputy
```

判定：`decision=STOP` 才能停；`REVIEW` 加 `--ack-review` 才能停；`CONTINUE` 不许停；
`BLOCKED` 先把卡点写进 issue 评论（**不得当空表**）。判据细则正本住项目仓该脚本，本仓不复述。

## 角色

| 谁 | 日表 | 技能 |
|---|---|---|
| 机长 | `-main.md` | [`../pilot/SKILL.md`](../pilot/SKILL.md) |
| 副机长 | `-deputy.md` | [`../copilot/SKILL.md`](../copilot/SKILL.md) |

## 派活用哪个方法技能

方法住**外部技能**，本仓不 fork（只按上游名引用，见 `docs/skill-sources/workflow-skills.md`）；
本仓只管流程顺序与判词契约：

| 环节 | 外部技能 | 一句话 |
|---|---|---|
| 施工（先红后绿） | `tdd` | 接缝取票面验证命令，一测例一提交 |
| 审查（出判词） | `code-review` | Spec／Standards 双轴分开报，不合并不排名 |
| 连续失败 / 原因不明 | `diagnosing-bugs` | 先造红得起来的反馈环，再谈假设 |

## 验证命令

```bash
python 框架仓门禁                        # 本仓门禁
python <gates.captain_preflight> --lane main    # 项目仓收工门禁（在项目仓根跑）
```
