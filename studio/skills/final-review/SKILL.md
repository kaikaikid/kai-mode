---
name: final-review
status: active
approved_by: human:kaikaikid
approved: 2026-10-28
sources:
  - resource: "../studio/SKILL.md"
    note: "六道门与记录面的正本；本文件只写终审的判据与镜头"
description: >
  文娱集团的终审：独立验收，逐条对 brief 与各线清单，出 verdict=pass|fail 与逐条证据。
  必须新上下文，只判不修；四类镜头：文字／视觉／影音／跨部门。
  触发：`/review`、说「终审」「审片」「验收」「过一遍」。
version: 1.0.0
updated: 2026-10-28
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 终审
dependencies:
  skills:
    - name: studio
      min_version: "1.0.0"
      reason: "终审按 studio 的门与记录面执行"
---

# 终审

**只判不修。** 你是创作体系的审查腿：新上下文、只读、出判词。

## 四个镜头

| 镜头 | 对什么 | 主要看 |
|---|---|---|
| `--text` | `brief.md` ＋ `text/voice-guide.md` | 一句话承诺、节拍、朗读节奏、年龄用词 |
| `--visual` | `brief.md` ＋ `visual/style-bible.md` | 角色一致性、色脚本、剪影可读性、版面层级 |
| `--time` | `brief.md` ＋ `time/board.md` | 节奏、转场、声画对位、字幕与响度 |
| `--cross` | `brief.md` ＋ 各线接口卡 | 跨线一致性、规格是否对齐、有没有越界改动 |

一次只跑一个镜头；跨部门项目在 `--cross` 之外至少再跑一个专业镜头。

## 判词形状

```text
verdict=pass|fail
镜头：text|visual|time|cross
逐条：
- [AC 或清单项] 证据：文件:行 / 图号 / 时间码 → 过 / 不过
未确认项：看不清、缺证据的地方（不许猜成通过）
```

- **无证据的条目一律 `unconfirmed`**，不算通过。
- `fail` 必须写清「哪条、什么证据、怎么改才算过」——但**不写改法细节**，那是各线的活。
- 不评「好不好看」这类观感题；观感交你拍板。

## 禁区

- 不修稿、不改文件、不改判据。
- 不替各线下结论；不因为「快上线了」放水。
- 不看施工过程，只看产物与记录面——**施工者不得自审，终审也不得复用施工会话**。

## 交件

判词写进 `studio/review/<日期>-<镜头>.md`，并在 `delivery.md` 之外单独留痕：
`pass` 才允许进 G5；`fail` 回各线重做，重做后**换新上下文再审**。
