---
name: pk
status: active
approved_by: human:kaikaikid
approved: 2026-10-30
sources:
  - resource: "../loop/references/dispatch.md"
    note: "派工纪律：只读子代理、传指针不传全文"
description: >
  通用对比分析 PK：对项目/图像/文章等多对象做维度化对比，输出图表与结论。
  不做：不改代码、不开票、不走塔台、不做单对象评审。
  触发：`/pk`、`/PK`、`/对比`，或用户说「PK」「对比」「比一比」「PK 一下」。
version: 0.1.0
updated: 2026-10-30
allowed-tools: Read Grep Bash(git:*) Bash(python:*)
compatibility: Host-agnostic; needs diagram-design skill for Tier 2+ charts
metadata:
  alias: 对比分析
dependencies:
  - name: diagram-design
    note: "Tier 2+ 图表渲染"
---

# pk —— 通用对比分析 PK

对任意多对象（项目 / 图像 / 文章 / 方案 / …）做维度化对比，输出图表 + 结论 + 证据链。只读分析，不改代码、不开票。

## 激活方式

- 人工：`/pk`、`/PK`、`/对比`，或用户说「PK」「对比」「比一比」「PK 一下」。
- 定时：无。
- 上游：无；用户直接调用。kai-mode 只推荐命令，不自动起。

## 输入与输出

| 方向 | 内容 | 形态 |
|---|---|---|
| 读 | 对比对象（≥2） | 路径 / URL / 粘贴文本 / Issue 编号，可混合 |
| 读 | 可选 `--tier 1\|2\|3` | 档位；默认 AI 自判 |
| 读 | 可选 `--baseline <obj>` | 基准对象；不给则平等对比 |
| 读 | 可选 `--archive` | 强制落 handoff 而非 docs/pk |
| 写 | 报告 + 图表 | Tier 1：`report.md`；Tier 2/3：`report.md` + `fig-*.html` |

## 档位

| 档 | 名称 | 流程 | 图数量 | 默认落点 |
|---|---|---|---|---|
| 1 | Lite | 只读 + Markdown 表格 + 结论，无图、无深搜 | 0 | handoff/30-research |
| 2 | Standard | Lite + 2 幅图 + 证据链 + 置信度 | 2 | handoff/30-research |
| 3 | Deep | Standard + 并行调研 + 多方案权衡 + ADR 风格分析 | 4 | docs/pk |

- 档位只绑流程深度，**不绑模型**（模型随宿主默认）。
- 触发：`/pk <对象> --1` / `--2` / `--3`，或 `/pk-1` / `/pk-2` / `/pk-3`（技能名后加 `-数字`）。
- 默认：AI 自判——对象数 2 → 1；3-4 → 2；≥5 或含异构类型 → 3；用户明确要求出图 → 至少 2。报告头注明"本报告自动选档：Tier X"。
- 用户最大：Tier 1 下用户要求出图 → 自动升 Tier 2；任何升档由用户触发，不静默降档。

## 工作流程

1. **采集**：按对象类型分路（repo→README/结构/关键文件；图像→视觉特征描述；文章→论点/证据/结论；URL→抓取正文）。混合对象统一成"对象卡片"（名称、类型、来源、3-5 句摘要）。
2. **维度提议**：AI 提议维度集 + 默认权重 + 理由；用户确认/增删。报告里附"维度选择理由"与"未采用的备选维度"。
3. **打分**：每对象每维度 0-5 分 + 证据（file:line / URL / 引用段落）；有 `--baseline` 时多一列"相对基准变化"。
4. **可视化**（Tier 2+，调 diagram-design）：按映射表选图类型——
   - repo vs repo → radar + grouped bar
   - 文章 vs 文章 → matrix + timeline
   - 图像 vs 图像 → heatmap + scatter
   - 异构/混合 → radar（总览）+ matrix（明细）
5. **结论**：加权总分 + 胜者 + 场景化建议（"A 胜在 X，B 胜在 Y"）+ 每条结论的证据链与置信度（高/中/低）。
6. **落盘**：Tier 1/2 → `handoff/30-research/pk-<slug>-<YYYY-MM-DD>/report.md`（+图）；Tier 3 或 `--archive` 反转 → `docs/pk/<slug>-<YYYY-MM-DD>/`。

## 权限与禁区

**可以**

- 读任意路径/URL/文本；调 diagram-design 渲染图；写 report.md 与 fig-*.html。

**不可以**

- 改代码、开票、走塔台、推送、合并。
- 不静默降档或静默升档（升档必须用户触发）。
- 不编造证据：无证据的维度标"未验证"而非给分。

## 失败与降级

- 对象 <2 ⇒ 报错退出，不跑。
- 某对象采集失败 ⇒ 标"采集失败"并继续，不整报告崩。
- diagram-design 不可用 ⇒ Tier 2+ 降为 Markdown 表格 + 文本描述，报告头注明"图表未生成"。
- 退出码 0 只代表"报告已写出"，不代表"结论被用户采纳"。

## 验证命令

```text
维护侧体检（不随技能安装）：plugin-check ＋ 仓级 doctor
技能自测：python -m pytest airport/skills/pk/tests -q（如有）
```

## 正本

- `airport/skills/pk/SKILL.md` —— 本文件。
- diagram-design（外援：外部宿主技能，持续关注其版本与 API 变动）—— 图表渲染。
- `../loop/references/dispatch.md` —— 派工纪律。