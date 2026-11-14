---
name: dna-flywheel
status: active
approved_by: human:kaikaikid
approved: 2026-11-14
sources:
  - resource: "视觉 DNA 飞轮设计方案（C-flywheel-skill-design）§2–§6"
    note: "落点、七子命令、输出契约、幂等与禁止段的结构依据；本文件不抄其正文"
description: >
  DNA 飞轮：视觉 DNA 阅卷的数据工程入口。一个入口七个子命令，v1 只实现
  validate（规则校验）／evaluate（评估验收）／reflux（知识回流）三个纯文件子命令；
  collect／ingest／annotate／review-assist 留接口桩，不写逻辑。
  只读文件＋算数＋产提案，绝不写正本。
  触发：说「DNA 飞轮」「视觉 DNA 校验」「跑 validate/evaluate/reflux」。
version: 0.1.0
updated: 2026-11-14
allowed-tools: Bash(python:*) Read Grep
compatibility: Requires python3（仅标准库）
metadata:
  alias: DNA 飞轮
  module: dna
---

# dna-flywheel —— DNA 飞轮入口

> **一个入口，七个子命令**（设计正本：`references/run-contract.md` §3）。
> v1 只做三个纯文件子命令；其余四个是接口桩，调用时明确回「未实现」，不假装跑过。

## 子命令

| 子命令 | v1 | 作用 |
|---|---|---|
| `validate` | ✅ | 候选记录 × 本体 × 契约 → 通过／警告／阻断（`V-*` 编号） |
| `evaluate` | ✅ | 人工基准 × AI 结果 → P/R/F1（Macro/Micro）＋ 问题清单 |
| `reflux` | ✅ | 已确认问题 × 审批结果 → 08.2／08.3 变更提案（只打印，不落正本） |
| `collect` / `ingest` / `annotate` / `review-assist` | 桩 | 依赖未建成服务，调用即回「未实现」并以非零退出 |

## 怎么跑

```bash
# 规则校验（--retired 可把上游已退役的 allele_id 显式标成退役）
python dna/skills/dna-flywheel/scripts/dna_flywheel.py validate \
  --records records.json --ontology ontology.json [--retired technique-005]

# 评估验收
python dna/skills/dna-flywheel/scripts/dna_flywheel.py evaluate \
  --gold gold.json --pred pred.json

# 知识回流（默认只打印提案；--out 才写文件，且不写正本目录）
python dna/skills/dna-flywheel/scripts/dna_flywheel.py reflux \
  --confirmed confirmed.json
```

## 输出契约

每次运行吐**同一个 JSON 形状**（见 `references/run-contract.md`）：
`run_id / stage / round_id / inputs / counts（六计数）/ findings（每条带 code＋evidence_ref）/ artifacts / blocked_reason`。

人读段落只复述这三个块，不另加判断。

## 禁止段（设计 §6 原文，硬约束）

- **不写** 03.1／04.1／05.1／09.1；只产提案，提案落 08.2 或 08.3。
- **不把 AI 候选写成人工真值**；`locked` 只能由人给出。
- **不新建第二套图片资产真源**；只存 `asset_id` 引用。
- **不在技能里内置阈值**；阈值从 `round_manifest` 读（`--manifest`）。
- **不把「跑完」当「通过」**；轮次通过与图片处理完成是两件事。

## 幂等

缓存键见 `references/cache-key.md`：同键命中输出 `skipped` 而非 `processed`，且必须打印键的组成。
