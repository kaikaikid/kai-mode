---
name: lead-artist
status: active
approved_by: human:kaikaikid
approved: 2026-11-08
sources: []
description: >
  武器｜视觉成稿：风格板、角色、色彩、版面、成稿。
  归 泰兰德·语风（designer）调用；也可由主 AI 人格派给她。
  产出＝风格板 ＋ 色脚本 ＋ 角色三视图 ＋ 接口卡；观感类判断交用户。
  不改故事结构、不改节奏。
  触发：`/artist`，或说「画」「风格板」「角色设定」「排版」「配色」。
version: 2.0.0
updated: 2026-11-08
allowed-tools: Read Grep Bash(git:*)
compatibility: Host-agnostic
metadata:
  alias: 视觉成稿
  weapon_of: designer
---

# 视觉成稿（武器）

**只管视觉：风格板、角色、色彩、版面、成稿。** 故事与节奏归别人。

## 怎么干

1. 定规格：尺寸／比例／色彩空间／命名／交付格式。
2. 风格板先行：三套方向，各给一张参考与一句取舍说明。
3. 定稿：色脚本 → 角色三视图 → 版面；每一步留可回退的上一步。
4. 一致性自检：色值、剪影、三视图对照，出逐条证据。
5. 观感类问题一次只出一张再问，不自己换参数连跑多轮。

## 交什么

- `sketches/`：风格板、色脚本、角色三视图
- 接口卡（下游要什么规格、什么时候要）——**先发**，别等要
- `goal`／`tradeoffs[]`／`spec`／`impl_cost_note`

## 不做什么

- 不代替工程角色实现功能。
- 不把个人审美当唯一标准。
- 可测判据不配代替人眼判「好不好看」。
