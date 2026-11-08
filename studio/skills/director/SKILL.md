---
name: director
status: active
approved_by: human:kaikaikid
approved: 2026-11-08
sources: []
description: >
  武器｜分镜成片：分镜、动态分镜、节奏、声音、成片。
  归 泰兰德·语风（designer）调用；也可由主 AI 人格派给她。
  产出＝分镜表 ＋ 动态分镜 ＋ 成片 ＋ 声音与字幕规格。
  不改文字定稿、不改视觉风格。
  触发：`/director`，或说「分镜」「剪辑」「成片」「配音」「节奏」。
version: 2.0.0
updated: 2026-11-08
allowed-tools: Read Grep Bash(git:*)
compatibility: Host-agnostic
metadata:
  alias: 分镜成片
  weapon_of: designer
---

# 分镜成片（武器）

**只管时间与声音：分镜、节奏、声音、成片。** 文字定稿与视觉风格归别人。

## 怎么干

1. 拿定稿与风格板，先出**静态分镜**（镜号／景别／内容／时长／转场）。
2. 动态分镜过一遍节奏：哪里要停、哪里要快、哪里留白。
3. 声音先定：人声／音效／配乐各一条轨，标清版权与来源。
4. 成片按规格导出（时长／分辨率／码率／字幕格式），附一份可复现的导出参数。
5. 交付前自检：时长、字幕错字、音画同步、黑场与爆音。

## 交什么

- `storyboard/`：静态分镜、动态分镜
- `final/`：成片 ＋ 字幕 ＋ 导出参数
- `sound/`：音轨清单与版权来源
- `unknowns`：任何未核实的素材授权

## 不做什么

- 不改文字定稿、不改视觉风格。
- 不用未授权素材。
- 不把「导出成功」当「内容没问题」。
