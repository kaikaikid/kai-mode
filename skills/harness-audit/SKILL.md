---
name: harness-audit
status: active
approved_by: human:kaikaikid
approved: 2026-10-24
sources:
  - resource: "docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md"
    note: "本技能的裁决来源：语义审计补 doctor 形状门，不进门禁"
  - resource: "agents/reviewer.md"
    note: "审计用 reviewer 的 audit 视角；不新增人格"
description: >
  语义审计：盘技能、人格、ADR、协议的质量、重叠与过期引用，出 Keep/Improve/Update/Retire/Merge 判词。
  不做 doctor 硬门（语义判断必须由模型做）；不修代码、不改票面。
  触发：发版前、月度体检、发现同一判据有两个家、或 doctor 全绿但怀疑正本已漂。
version: 0.1.0
updated: 2026-10-24
allowed-tools: Read Grep Bash Write
compatibility: Requires python3
metadata:
  alias: 体检
---

# harness-audit —— 语义审计

> doctor 管「形状」（字段、链接、路径、枚举）；本技能管「意思」（重叠、过期、自相矛盾、触发词失真）。
> 两者不互相替代：doctor 绿不等于审计过。

## 什么时候跑

- 发版前、每月一次。
- doctor 全绿但你觉得不对劲：同一数值有两套、技能指向已删目录、触发词与正文不一致。
- 新增/删除技能、改人格契约后。

## 输入

只读盘点：

```bash
python skills/harness-audit/scripts/inventory.py --root <仓根> --summary
```

Quick Scan 只看上次审计后 mtime 变过的件；Full Stocktake 审全部。mtime 只是线索，
不是 git 事实；上次审计记录在 `handoff/40-review/`。

## 检查清单

对每个技能/人格/ADR 至少过这七项：

1. **重叠**：与另一个技能、AGENTS.md、README、ADR 是否讲同一件事？
2. **过期引用**：路径、脚本、模板、宿主 token 是否还存在？**必需件是否真的在 git 里**（`git ls-files`；
   本地绿、clone 缺件是常见假绿）。
3. **触发词**：`description` 的触发条件与正文实际动作是否一致？
4. **可执行性**：命令、AC、验证步骤是否真的能跑？
5. **时效**：工具名、flag、API、版本号是否还成立（需要时查一手来源）？
6. **预算**：正文行数、回执行数、上下文入口是否超界？
7. **一个家**：同一个数值/判据是否在第二处被复述或反着写？

## 判词

| 判词 | 含义 |
|---|---|
| `Keep` | 有用且当前 |
| `Improve` | 值得留，但要点名改哪一节 |
| `Update` | 引用的技术/路径/版本过期，需更新 |
| `Retire` | 低质、过期或成本大于收益 |
| `Merge into X` | 与 X 实质重叠，点名并入哪一节 |

判词必须自足：`Retire` 要写清「缺陷是什么、谁覆盖了它」；`Merge` 要写清目标与并入内容；
`Improve` 要写清具体章节与改法。禁止只写「过期」「重叠」。

## 输出

落 `handoff/40-review/<YYYY-MM>/<YYYY-MM-DD>-harness-audit-<类型>.md`，frontmatter 六字段照 handoff 规范，
正文只放一张表：

```markdown
| 件 | 判词 | 证据 | 建议 |
|---|---|---|---|
| skills/foo/SKILL.md | Improve | 第 N 行仍写已删路径 | 改指 ... |
```

审计结果不进 doctor、不自动改文件；由塔台/地勤决定开票或就地修。

## 首次自证（硬）

拿当前仓跑一次，**必须**至少报出已知的过期/矛盾项；如果它说「全绿」，先修审计本身，不要相信结论。
拿一个已知坏件做负向样例：把一条退役路径塞进临时副本，审计必须报 `Update`/`Retire`。

## 验证命令

```bash
python skills/harness-audit/scripts/inventory.py --root <仓根> --summary
python scripts/doctor.py --with-tests
```
