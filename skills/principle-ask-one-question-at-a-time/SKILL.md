---
name: principle-ask-one-question-at-a-time
status: active
approved_by: human:kaikaikid
approved: 2026-10-23
sources:
  - resource: "skills/kai-mode/SKILL.md"
    note: "「拷问规则」段原始出处；判据正本迁入本叶子后，原段收缩为流程位＋指针"
description: >
  拷问原则：一次只问一个问题、逐个确认，每题带推荐默认值；规划表那格是唯一关键审批点，不吃快捷回话。
  不管审批边界与红线（归 principle-visible-and-redline-only），不执行具体活。
  触发：Apply when 要向用户提问、设计拷问题目、或想一口气甩出一串确认问题时。
version: 0.1.1
updated: 2026-10-23
allowed-tools: Read Grep
compatibility: Host-agnostic
---

# 拷问一次一问

> ）。

## 何时进场

- 要向用户提问的任何时刻：拷问、定稿确认、中途要拍板。
- 想一口气甩出一串确认问题——先回到本判据再出手。

## 判据

- **一次只问一个问题**，逐个问、逐个确认；全程最多 5 问、≤2 轮，只问会改大方向的 **ADR 级**分叉，线以下细节不问。
- **每题带推荐默认值**：回「同意」收下该题默认；回「全按你说的」一次收下剩余题。
- **唯一例外：规划表那一格不吃快捷回话**——全流程唯一关键审批点，要她真读过规划表再答，默认值替代不了。
- 线以下自决与代决清单归 [`principle-visible-and-redline-only`](../principle-visible-and-redline-only/SKILL.md)，本叶子不管。

## 反例

- 一屏甩十问等她逐条答——改一题一答，剩余的让她「全按你说的」收走。
- 问「函数怎么拆 / 目录叫什么」这类线以下细节——自决，记代决清单。
- 给规划表也配一句「同意即默认批」——违反唯一审批点例外。
- 只抛开放问题不带默认——她被迫替 AI 想答案。

## 验证

- 拷问记录逐屏看：一屏一个问句、每题有推荐默认、≤5 问。
- 规划表批准有一条她本人读过的确认，不是快捷回话。
