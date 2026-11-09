# 方法指针 —— 用中央库原版，不维护副本

> 裁决（2026-11-04）：通用方法不 fork、不复制正文、不做 30 天对账。
> 宿主中央库里的上游原版（`tdd`、`code-review` 等）直接由 AI 按名使用；
> 本仓只保留「什么时候该用哪个方法、用之前要补哪条本仓特有的约束」。

## 使用口径

| 想干什么 | 按名用哪个上游原版 | 本仓要补的一句约束 |
|---|---|---|
| 写代码、先红后绿 | `tdd` | 测试只落在**预先确认的接缝**；非代码 / 纯配置 / 纯文案票不硬写测试 |
| 审查 diff | `code-review` | Standards 与 Spec 双轴分开报，不代替机器门，不越出票面 AC |
| 连续失败、原因不明 | `diagnosing-bugs` | 先造红得起来的反馈环；常规施工不走它 |
| 术语 / ADR / GLOSSARY | `domain-modeling` | 不替项目做业务决策 |
| 拆票 | `to-tickets` | 只出草案，开票归康娜 |
| 已有 spec 和票、一把跑完 | `implement-spec` | 与 run 制的分工见 `engine/skills/fleet/SKILL.md` 方法表，本表不复述 |
| 写 SKILL / AGENTS 文档 | `writing-for-agents` | 不替代 `docs/skill-layout.md` 的八字段契约 |
| 安全专项 | `security-review`（宿主自带；中央库没有时按缺件登记） | 无沙箱时最高结论 `needs_validation` |

## 本仓自己保留的

只有 `engine/skills/pk/`：通用对比分析（`/pk`、`/对比`），本仓原创，无上游对应件，随 engine 插件安装。

除它以外，`kai-*` 方法副本已全部删除；本仓不再随装任何上游方法正文。

## 缺件怎么办

宿主中央库找不到对应原版时，按缺件三格登记（缺什么 / 用哪个替代 / 何时补），
不假装已具备，也不把正文抄回本仓。

## 旧机制已退役

- `docs/skill-sources/sources.json` 的 `adopted` / `deltas` / `next_diff_due` 已退役，仅作历史索引；
  `scripts/source-check.py` 不再进 doctor 门。
- ADR-0026（fork 通用方法）已被本裁决取代，保留原文作历史记录。

## 为什么

维护 9 份上游正文的副本 + 30 天对账，成本高于收益；AI 直接读原版更准、更新更及时。
本仓的价值在「剧本与方法论」，不在「镜像上游」。
