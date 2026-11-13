---
name: design-handoff
status: active
approved_by: human:kaikaikid
approved: 2026-11-13
sources:
  - resource: "OpenBot 市场 · Handoff Spec Writer／Build Spec（2026-11-13 抓取全文）"
    note: "抓取地址 https://api.openbot.run/v1/skills/openbot-curated-skill-build-spec"
description: >
  武器｜交付规格：把设计稿写成开发不用猜就能建的规格，并列出偏离设计系统的数值。
  触发：`/handoff`，或说「交接规格」「开发照着建」「出交付规格」。
version: 1.0.0
updated: 2026-11-13
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 交付规格
  weapon_of: designer
---

# 交付规格（武器）

**把设计稿翻成开发能直接施工的规格。** 只描述，不评审设计好坏，不写代码，不改设计稿。

## 什么时候用

- 设计已经定稿，工程要照着建，不能靠猜。
- 想知道某一版哪里偏离了设计系统。
- 不是判断设计好不好（走 `design-critique`），也不是产品需求规格（走 `to-spec`）。

## 怎么干

1. **收输入**：设计画板（Figma 插件或已登录的 Figma 标签页）；拿不到就请用户上传截图，图里读出的数值全部标 `est.`。再收设计系统：Figma styles／variables、仓里的 tokens 文件或用户给的清单；没有就写「无可对照系统」。
2. **定目标**：Web 还是移动端、用什么组件库。不清先问一次。
3. **列组件**：逐个给系统组件名与变体；系统里没有的标「自定义」。
4. **写布局**：网格还是堆叠、方向、间距、内边距、对齐，以及变窄／变宽时怎么变。画板只有一个宽度时，把另一侧行为写成待确认问题。
5. **列 token**：颜色、字体、圆角、间距、阴影，给 token 名与值。
6. **找漂移**：每个对不上 token、或接近但不完全相等的值，给「位置／实际值／最近 token／建议」。没找到的 token 不硬猜。
7. **补状态**：每个可交互元素给默认、悬停、焦点、按下、禁用、加载、空、错误、成功，逐项标「已画／缺」。
8. **写动效与内容规则**：什么动、时长、缓动、减少动效时怎么变；文本上限、截断、数字与日期格式、超长或缺失时怎么办。
9. **留开口**：每个未决问题写清「谁能回答」。

## 交什么

```text
交付规格 — <画板名> — <读取日期> — 来源：<Figma 插件／Figma 标签页／截图>

组件
- <名称> — <系统组件／变体，或「自定义」>
布局
- <区域>：<堆叠或网格>，间距 <n>，内边距 <n>，<变宽／变窄行为>
Token
| 类别 | Token | 值 | 用在哪 |
漂移
| 位置 | 实际值 | 最近 Token | 说明 |
| 卡片内边距 | 18 px | space-4（16 px） | 改用 space-4，或新增 token |
状态
| 元素 | 默认 | 悬停 | 焦点 | 禁用 | 加载 | 空 | 错误 |
动效：<逐项，或「未展示」>
内容规则：<上限与格式>
待确认
1. <问题> — 问：<设计师或负责人>
```

## 判据

- 每个值都有来源：style、variable、检查面板，或图上的 `est.`。
- 每个可交互元素要么状态齐全，要么缺失项进了待确认。
- 漂移只列真实差异；「没找到 token」不等于「漂移」。
- 工程不开设计稿也能照这份规格建出来。

## 不做什么

- 不改 Figma 文件、不留评论、不改 token、不写代码（用户明确要求除外）。
- 不替设计做审美判断；有可用性问题只加一条短注，完整评审走 `design-critique`。
- 不把截图里读出的值写成精确值。
- 不把产品需求规格混进来；那走 `to-spec`。

## 正本

- 方法出处：OpenBot 市场 Handoff Spec Writer／Build Spec（frontmatter `sources` 有全文抓取地址）。
- 设计系统数值与 token 名：以项目仓的 tokens 或 `soft-design-system` 为准。
