---
name: loop
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources: []
description: >
  机长 / 副机长 / 二副 / 王牌飞行员共用的单票闭环（不是用户入口）。判据以协议正本为准。
  触发：由 `/pilot`、`/copilot`、`/second-officer`、`/ace` 自动带入；「loop」不是口令。
version: 6.3.0
updated: 2026-10-27
allowed-tools: Read Grep Bash(python:*)
compatibility: Host-agnostic
dependencies:
  skills:
    - name: tdd
      reason: "施工默认方法（非代码票可换轻量验证；选用判据见 §派活）"
    - name: code-review
      reason: "审查常用方法（安全专项可换 security-audit）"
    - name: diagnosing-bugs
      reason: "连续失败时的诊断方法（条件触发，平时不预载）"
---

# loop

本技能是导航：**怎么做**看同目录 [`references/loop-protocol.md`](references/loop-protocol.md)，
**什么不能碰、什么自己定**看角色技能。流程叙事、回执详略和机动子代理都是可省的负担；
只有围栏、回执上限（住协议 §五）与收工复查是硬约束。

## 三份参考

| 文件 | 管什么 |
|---|---|
| [`references/loop-protocol.md`](references/loop-protocol.md) | 单票闭环判据正本：名额、记录面、停点、等待梯、发货边界 |
| [`references/dispatch.md`](references/dispatch.md) | 票外派发：何时派、谁能派、轻卡五件、回执四要素、派生固定一层 |
| [`references/adjudication.md`](references/adjudication.md) | 取舍裁决：什么时候派、`ruling=` 三值与四件、不裁的四类 |

## 脚本（先跑脚本，再读正文）

机械判断先交给脚本，拿小 JSON 再决策；正文只用来处理脚本判不了的取舍。

| 脚本 | 用途 |
|---|---|
| `scripts/ticket.py show --ticket <n>` | 窄读票面，输出 AC／允许面／禁止面／验证命令 |
| `scripts/ticket.py ready --ticket <n>` | 开工前查三件；缺件直接红 |
| `scripts/ticket.py verdict --text "<判词>"` | 验 `verdict=`／`ac=` 形状与分母 |
| `scripts/ticket.py receipt --file <回执>` | 验回执字段；行数上限可按协议传 `--max-lines` |
| `scripts/ticket.py pointer --file <指针>` | 验续跑指针四件 |
| `scripts/protocol.py --section 三` | 只打印协议那一节，不整份加载 |
| `scripts/worktree.py status --lane main` | 车道槽、分支、HEAD、脏否（只读） |

## 一张票

开工评论 → 施工（车道工作树里换分支）→ 施工完成评论 → 新上下文审查
→ `fail` 按协议重试再审 → `pass` 后按判词格式写「待发货」（首行 `verdict=`、第二行 `ac=<通过数>/<总数>`；
格式与窄读命令见兄弟技能 `pilot`）。

**环节顺序不可反（协议 §二），轮次可并**：轻量票可把相邻环节并进同一轮（如施工完成评论并入审查派发），
环节不可省略；并了哪几步在票面留一句。

`pass` 写进待发货＝这票在你这儿**完工**：当场释放执行名额，接着补日表的下一张。合并、push、关票归塔台，
它按情况分批——不等收货、不拿「批收尾」当停点（停点只认协议 §七）。

## 收工

做完一张票先跑收工门禁（**不许早停**是硬约束）。门禁脚本归**项目仓**，路径从项目配置实例
`gates.captain_preflight` 读（`null` 或缺配置 → 报缺件，不猜路径）：

```bash
python <gates.captain_preflight> --lane main|deputy|second|ace
```

判定：`decision=STOP` 才能停；`REVIEW` 判完确实没活、加 `--ack-review` 才能停；`CONTINUE` 不许停——
**表的判据看未完工票**，已 `pass` 进待发货的行不再算你的在飞；
`BLOCKED` 先把卡点写进 issue 评论（**不得当空表**）。判据细则正本住项目仓该脚本，本仓不复述。

王牌车道没有对照道：`--lane ace` 不因「另一张日表读不到」判 `BLOCKED`；真读不到自己的表仍要 `BLOCKED`。

## 角色

| 谁 | 日表 | 技能 | 命令 |
|---|---|---|---|
| 机长 | `-main.md` | [`../pilot/SKILL.md`](../pilot/SKILL.md) | `/pilot` |
| 副机长 | `-deputy.md` | [`../copilot/SKILL.md`](../copilot/SKILL.md) | `/copilot` |
| 二副 | `-second.md` | [`../second-officer/SKILL.md`](../second-officer/SKILL.md) | `/second-officer` |
| 王牌飞行员 | `-ace.md` | [`../ace/SKILL.md`](../ace/SKILL.md) | `/ace` |

## 派活：契约写死，方法自选

派工卡只给**契约五件**：票号、AC、允许修改面、验证命令、回执格式（形状住协议 §五）。
**方法由子代理按票情自选，派活方不代定**；下表是菜单与选用判据，不是绑定。
方法住**外部技能**，本仓不 fork（只按上游名引用）：

| 环节 | 常用方法 | 何时换 / 何时不用 |
|---|---|---|
| 施工 | `tdd`（默认先红后绿，一测例一提交） | 非代码／纯配置／纯文案票：跑票面验证命令即可，不硬写测试 |
| 审查（出判词） | `code-review`（双轴分开报，不合并不排名） | 安全专项挂 `security-audit`；只对票面 AC 面，不越出 |
| 连续失败 / 原因不明 | `diagnosing-bugs`（先造红得起来的反馈环） | 条件触发才加载，平时不预载 |

## 验证命令

```bash
python <gates.captain_preflight> --lane main    # 项目仓收工门禁（副机长 deputy / 二副 second / 王牌 ace）
```
