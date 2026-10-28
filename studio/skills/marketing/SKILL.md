---
name: marketing
status: active
approved_by: human:kaikaikid
approved: 2026-10-28
sources:
  - resource: "../studio/SKILL.md"
    note: "六道门与记录面的正本；本文件只写宣发的执行清单"
description: >
  文娱集团的宣发：物料、渠道、投放排期、数据回收；G2 之后进场，不等到最后。
  不改作品内容、不替部门定风格；没有渠道就登记缺件，不假装已发布。
  触发：`/marketing`、说「宣发」「投放」「物料」「渠道」「推一下」。
version: 1.0.0
updated: 2026-10-28
allowed-tools: Read Grep Bash(git:*)
compatibility: Host-agnostic
metadata:
  alias: 宣发
dependencies:
  skills:
    - name: studio
      min_version: "1.0.0"
      reason: "宣发按 studio 的门与记录面执行"
---

# 宣发

**只管包装与到达：物料、渠道、排期、数据。** 作品内容归各线。

## 什么时候进场

**G2 风格定稿后立刻进场**，不是 G5 之后。理由：物料要用风格板做，等成片出来再做就来不及。
进场只拿两样：`brief.md`（受众与形态）＋ 主创的 `style-bible.md` 或 `voice-guide.md`。

## 记录面（`studio/marketing/`）

| 文件 | 内容 |
|---|---|
| `plan.md` | 渠道清单、每条渠道的物料规格与排期 |
| `assets/` | 物料：封面、横幅、短文案、预告片 |
| `data.md` | 投放后的读数：曝光、点击、转化（有就记，没有写「未接入」） |

## 派活

| 活 | 子代理 | 派工卡要点 |
|---|---|---|
| 物料制作 | 施工（可写） | 渠道规格（尺寸／时长／字数）、风格板指针 |
| 物料核对 | 审查（只读） | 逐条对渠道规格与风格板 |
| 渠道调研 | 调查（只读） | 平台规则、受众画像，只给结论与出处 |

## 三条禁令

- **不改作品内容**：物料里改一句文案也要主笔点头。
- **不替部门定风格**：物料必须服从 `style-bible.md` / `voice-guide.md`。
- **不承诺效果**：没有数据接入就写「未接入」，不编曝光与转化。

## 交件（G5 的一部分）

`plan.md` ＋ `assets/` ＋ 投放排期，交企划并入 `delivery.md`。
渠道接不上 → 登记 `no-publish`（缺什么／卡在哪／要谁拍），仍然交付物料与排期。
