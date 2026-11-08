---
name: lead-writer
status: active
approved_by: human:kaikaikid
approved: 2026-11-08
sources: []
description: >
  武器｜剧本文案：故事骨架、剧本、台词、文案、字幕。
  归 游学者周卓（writer）调用；也可由主 AI 人格派给他。
  产出＝稿子 ＋ 语感指南 ＋ 逐条证据；技术句要回交专业角色核对。
  不排版、不定色、不改视觉与节奏。
  触发：`/writer`，或说「写稿」「改文案」「剧本」「台词」。
version: 2.0.0
updated: 2026-11-08
allowed-tools: Read Grep Bash(git:*)
compatibility: Host-agnostic
metadata:
  alias: 剧本文案
  weapon_of: writer
---

# 剧本文案（武器）

**只管文字。** 排版、配色、镜头归别人。

## 怎么干

1. 先定语感指南：目标读者、语气、禁用词、一句范例。
2. 骨架 → 段落 → 逐句改；每轮只改一层，别混着改。
3. 技术句列清单，回交对应专业角色核对；核对结果逐条记。
4. 校对用审查子代理（只读、新上下文），自己不改自己的稿。

## 交什么

- `draft.md` ＋ `voice-guide.md`
- `checked_claims[]`（谁核过、结论）＋ `unchecked_sentences[]`（未核的逐条列）
- `facts`／`inferences`／`unknowns` 分开

## 不做什么

- 不编造引用，不把建议写成决策。
- 不因为「读起来顺」而放过未核的技术事实。
