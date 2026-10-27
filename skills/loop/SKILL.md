---
name: loop
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources: []
description: >
  机长 / 副机长 / 王牌飞行员共用的单票闭环（不是用户入口）。判据与本技能冲突时以协议正本为准。
  触发：由 `/机长`、`/副机长`、`/王牌飞行员` 自动带入；「loop」不是口令。
version: 5.5.0
updated: 2026-10-27
allowed-tools: Read Grep Bash(python:*)
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

本技能只是导航：**怎么做**看协议正本，
**什么不能碰、什么自己定**看角色技能。流程叙事、回执详略和机动子代理都是可省的负担；
只有围栏、回执上限（住协议正本 §五）与收工复查是硬约束。

## 一张票

开工评论 → 施工（独立 worktree，先红后绿）→ 施工完成评论 → 新上下文审查
→ `fail` 修 1 次再审 → `pass` 后按判词格式写「待发货」（首行 `verdict=`、第二行 `ac=<通过数>/<总数>`；
格式与窄读命令见兄弟技能 `pilot`）。

`pass` 写进待发货＝这票在你这儿**完工**：当场释放在飞名额，接着补日表的下一张。合并、push、关票归塔台，
它按情况分批——不等收货、不拿「批收尾」当停点（停点闭集见协议正本 §七）。

## 收工

做完一张票先跑收工门禁（**不许早停**是硬约束）。门禁脚本归**项目仓**，路径从项目配置实例
`gates.captain_preflight` 读（`null` 或缺配置 → 报缺件，不猜路径）：

```bash
python <gates.captain_preflight> --lane main|deputy|ace
```

判定：`decision=STOP` 才能停；`REVIEW` 判完确实没活、加 `--ack-review` 才能停；`CONTINUE` 不许停——
**表的判据看未完工票**，已 `pass` 进待发货的行不再算你的在飞；
`BLOCKED` 先把卡点写进 issue 评论（**不得当空表**）。判据细则正本住项目仓该脚本，本仓不复述。

## 角色

| 谁 | 日表 | 技能 |
|---|---|---|
| 机长 | `-main.md` | [`../pilot/SKILL.md`](../pilot/SKILL.md) |
| 副机长 | `-deputy.md` | [`../copilot/SKILL.md`](../copilot/SKILL.md) |
| 王牌飞行员 | `-ace.md` | [`../ace-pilot/SKILL.md`](../ace-pilot/SKILL.md) |

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
python <gates.captain_preflight> --lane main    # 项目仓收工门禁（在项目仓根跑；副机长 deputy / 王牌 ace）
```
