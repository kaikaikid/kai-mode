# workflow-skills —— 已退役（方法不再 fork）

> 2026-11-04 裁决：通用方法不 fork、不存副本、不做 30 天对账。
> 当前口径以 [`../method-pointers.md`](../method-pointers.md) 为准；本文件只保留历史结论。
> `sources.json` 仍可作历史索引，但 `deltas` / `next_diff_due` 已退役，`source-check.py` 不再进 doctor 门。

## 现在怎么用

| 想干什么 | 按名用哪个上游原版 | 本仓承载「流程」的那一份 |
|---|---|---|
| 施工：先红后绿 | `tdd` | `engine/skills/fleet/SKILL.md`（接缝＝任务 AC 里的验证命令） |
| 审查：双轴出判词 | `code-review` | 同文件「任务卡与审查卡」 |
| 连续失败／原因不明 | `diagnosing-bugs` | 同文件「失败处理」 |
| 定稿：术语与 ADR | `domain-modeling` | `core/skills/staff/SKILL.md` 定稿段 |
| 定稿：拆票草案 | `to-tickets` | `core/skills/staff/SKILL.md` 定稿段 ＋ 舰桥开票六件套 |
| 写 SKILL／AGENTS 文档 | `writing-for-agents` | `docs/skill-layout.md` |
| 安全专项 | `security-review`（中央库缺件时登记） | 只读审查与报告契约 |

本仓不再携带这些方法的正文，也不再随装 `kai-*` 副本；宿主中央库没有就按缺件登记。

## 历史

- ADR-0026 曾允许把 7 个通用方法以 `kai-` 前缀 fork 进 `engine/skills/methods/`，记 `deltas`、30 天对账。
- 该机制已于 2026-11-04 退役；`engine/skills/methods/` 已删除，唯一保留的自有件是 `engine/skills/pk/`。
