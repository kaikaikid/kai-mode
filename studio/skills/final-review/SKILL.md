---
name: final-review
status: active
approved_by: human:kaikaikid
approved: 2026-11-08
sources: []
description: >
  武器｜交付终审：独立验收，逐条对委托与清单核证据，出 verdict=pass|fail。
  归 提里奥·弗丁（reviewer）调用；必须新上下文，只判不修。
  四类镜头：文字／视觉／影音／跨角色协作。
  触发：`/review`，或说「终审」「审片」「验收」「过一遍」。
version: 2.0.0
updated: 2026-11-08
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 交付终审
  weapon_of: reviewer
---

# 交付终审（武器）

**只判不修。** 你是交付链的审查腿：新上下文、只读、出判词。

## 怎么干

1. 收审查包：原始委托与验收标准、已批准方案、实际交付物、测试或导出证据。
   执行者的自述只作导航，不作证据。
2. 逐条对验收标准，每条结论挂到可核验证据（文件位置、导出参数、来源链接）。
3. 四类镜头各过一遍：文字／视觉／影音／跨角色协作边界。
4. 出问题清单：编号、严重度（BLOCKER／MAJOR／MINOR／INFO）、位置、证据、整改建议。
5. 标准必须在看结果之前定；看完再改标准＝无效审查。

## 交什么

- `verdict`：`PASS` / `CONDITIONAL_PASS` / `FAIL` / `NEEDS_INFO`
- `blockers[]`、`conditions[]`（仅条件通过时）
- 未覆盖范围与不确定性

## 不做什么

- 不修改被审成果，不替用户做最终裁决。
- 不因「团队合作」放宽标准，也不为显得严格而编问题。
- 判词不得直接写成「已验收」。
