---
name: kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources: []
description: >
  规划与拷问方法：把一句模糊需求收敛成能开工的规划表与拆票草案。由舰桥在需求大、方向未定时调用，
  不再是对外入口，也不执行施工。触发：舰桥判断需要先规划；用户说「先规划」「别急着做」「想清楚再做」。
version: 4.0.0
updated: 2026-10-31
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 规划模式
---

# kai-mode —— 规划与拷问方法

> **不是入口**：对外只有舰桥一个对话面。舰桥遇到「需求大、方向未定、多方取舍」时调用本方法，
> 规划完把结果交回舰桥去开票、开 run。用户不需要记本技能的名字。

## 什么时候用

- 用户一句话说不清要什么，或方案有明显分叉。
- 一次要改多个模块、跨里程碑，或会动数据 / 权限 / 外部接口。
- 用户明确说「先规划」「想清楚再做」「别急着写代码」。

小修、单文件、需求清楚 → 不用本方法，舰桥直接做。

## 方法（五步，一次一问）

1. **判断**：新想法 / 熟活 / 已有票。已有票先读票面，不重开。
2. **拷问 ≤5 问**：只问大方向，每题给 2–3 个选项，推荐项排第一并写一句理由。
   判据见 `../principle-ask-one-question-at-a-time/SKILL.md`。
3. **定稿**：
   - 清账：被推翻的旧决策、重复票、超 30 天没动的票——只列清单交用户，不自动关。
   - 术语与 ADR：影响长期结构的决定写成 ADR；方法用 `../../../methods/skills/kai-domain-modeling/SKILL.md`。
   - 拆票草案：按垂直切片拆成可执行工单（目标、AC、允许/禁止修改、验证命令）；
     方法用 `../../../methods/skills/kai-to-tickets/SKILL.md`。**只出草案，开票归舰桥。**
4. **规划表**：把「做什么 / 不做什么 / 先后 / 验收」汇成一张表。用户只在规划表上拍一次板。
5. **交回舰桥**：拍板后，舰桥开票并决定是否 `/jump` 开工。本方法不写代码、不开票、不 push。

## 审批边界

- 只拿肉眼可见的表象（界面、文案、交互、观感）与红线问人；看不见的技术细节自决并记一行理由。
  判据见 `../principle-visible-and-redline-only/SKILL.md`。
- 红线（花钱、对外发布、不可逆、删未提交内容）先停，不靠规划绕过。

## 输出

- 一张规划表（结论先行，可直接贴进 Issue）。
- 0–N 张拆票草案（六件套齐全）。
- 一段给舰桥的交接：先做哪张、依赖什么、哪一步需要用户再拍板。

## 正本指针

| 要判什么 | 正本 |
|---|---|
| 一次一问与推荐默认 | `../principle-ask-one-question-at-a-time/SKILL.md` |
| 只问可见与红线 | `../principle-visible-and-redline-only/SKILL.md` |
| 仪式随规模塌缩 | `../principle-ceremony-collapses-with-scale/SKILL.md` |
| 术语与 ADR | `../../../methods/skills/kai-domain-modeling/SKILL.md` |
| 拆票 | `../../../methods/skills/kai-to-tickets/SKILL.md` |
| 施工与发货 | `../../../v2/skills/coding/SKILL.md` |
| 统一入口 | `../bridge/SKILL.md` |
