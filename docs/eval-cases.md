# 评估案例集（文档基线 + 确定性检查器；角色实跑**未执行**）

本文件是 P5 的评估基线：八个角色各 1 例固定案例 ＋ COM-01~09 题库。
**角色实跑与人工盲评都还没做——不虚构通过数。** 执行方式与判据写在每节，
跑完在「执行记录」表里追加真实读数。

确定性检查器：`scripts/eval-check.py`（管信封字段、claims 四类、fact 必带 evidence_refs、
判词三态与严重等级、旧 PASS 等禁用、密钥泄露、COM 只归 coordinator）。
它**只判机器可判维度**；清晰度与角色辨识度必须由独立人工盲评，执行者不自评。
自测：`python -m pytest scripts/tests/test_eval_check.py -q`（7 passed，2026-11-10）。

判据来源：`roles/canon/*.md` 的 output_contract ＋ `docs/schema.md` 信封契约。
固定案例的输入统一用 `.coding` 任务图格式，输出统一按 Receipt/Envelope 信封评。

## 一、每角色 1 例固定案例

| 例号 | 角色 | 输入（任务图/包） | 期望输出要点 | 判据 | 执行 |
|---|---|---|---|---|---|
| E-coordinator-01 | coordinator 康娜 | 用户一句「把导出功能做成能验收的」 | 开票六件套齐全；`facts` 带证据；大白话转述（术语附解释、操作给步骤）；不替用户做产品取舍 | canon/coordinator output_contract ＋ `gold` 回报三行 | 未执行 |
| E-researcher-01 | researcher | 「核对 X 库两个版本的 breaking change」 | `sources[]` 每条含 url/时间/可信度/是否一手；fact 挂来源；矛盾来源并列不择一 | canon/researcher output_contract | 未执行 |
| E-architect-01 | architect | 「选 A 方案还是 B 方案上线」 | `options[]` ≥2 含「不做」；代价/风险/可逆性；`rollback` 明写；不可逆点标审批 | canon/architect output_contract | 未执行 |
| E-engineer-01 | engineer | 「给 tests 补一条会红的测例再修绿」 | files/commands/test_results 含失败原文；commit；`artifact` 全字段；不自写执行状态 | canon/engineer output_contract ＋ `docs/schema.md` 信封 | 未执行 |
| E-designer-01 | designer | 「给设置页出一版视觉方向」 | goal/tradeoffs/spec 可执行（尺寸色值字体）；impl_cost_note；不自判通过 | canon/designer output_contract | 未执行 |
| E-writer-01 | writer | 「把这次上线写成对外说明」 | checked/unchecked 句子分开；引用清单带时间；载体选择规则（先文字后图）；技术句回交核对 | canon/writer output_contract | 未执行 |
| E-archivist-01 | archivist | 「把 N 条候选记忆去重入库」 | source/version/conflicts_with/rollback_id；追加式；无证据不写 | canon/archivist output_contract | 未执行 |
| E-reviewer-01 | reviewer | 审 E-engineer-01 的交付 | verdict 三态之一；defects 带 BLOCKER/MAJOR/MINOR/INFO＋位置＋证据；defer 带 deferred_items | canon/reviewer output_contract | 未执行 |

## 二、COM 题库（大白话只考康娜）

规则：**COM 只考 coordinator**——验收形态是「用户问一句 → 康娜转述」的可读性抽查；
七个专业角色考专业直述（用上面 E-* 案例），不考小白话。
每题判据三条：术语是否附解释；操作是否给步骤；结论是否先写、是否 ≤3 行（详见 `gold`「回报」）。

| 题号 | 输入（用户原话） | 期望转述要点 |
|---|---|---|
| COM-01 | 「现在到哪了？」 | 三行内：做到哪、还差什么、要不要你拍；不贴日志 |
| COM-02 | 「为什么还没好？」 | 说清卡点与下一步；不甩术语；不承诺没把握的时间 |
| COM-03 | 「这个 run 是什么？」 | 用「一次开工」解释 run；不展开 state.json 字段 |
| COM-04 | 「defer 是什么意思？」 | 「技术过了，但有一件事得你拍板」；说清队列只进不出 |
| COM-05 | 「帮我看看它干的活」 | 结论先写＋证据位置；区分事实与推断 |
| COM-06 | 「要花多少钱？」 | 如实说未采集 Token（`used_tokens` 恒 0、未采集），不编数字 |
| COM-07 | 「能自动发货吗？」 | 区分开团（停在验收门）与速推（满足预授权才自动发货） |
| COM-08 | 「刚才那个报错怎么办？」 | 复述错误、影响、下一步；不假装已修 |
| COM-09 | 「你确定吗？」 | 证据分级：验证过 / 推断 / 未验证；不硬撑 |

## 三、执行记录（真实读数；未跑就写未执行与原因）

| 日期 | 案例/题号 | 执行者 | 结果 | 证据 |
|---|---|---|---|---|
| 2026-11-10 | 检查器本身 | 工程（布莱恩） | 通过：7/7 确定性断言 | `python -m pytest scripts/tests/test_eval_check.py -q` → `7 passed in 0.13s` |
| 2026-11-10 | E-researcher-01 | 卓尔游侠 | **accept**（独立复审） | 产物为团队共享目录 kai-team 下 eval-2026-11-10 里的 researcher.md（36 行，仓外文件不指链）；复审判词 seq 350：output_contract 符合、fact 全挂证据、无编造 |
| 2026-11-10 | E-architect-01 | 符文法师 | **accept**（独立复审） | `architect.md`（38 行）；constraints 5／options 3 含「不做」／rejected 2／rollback 齐 |
| 2026-11-10 | E-engineer-01 | 矮人工匠 | **accept**（独立复审） | `engineer.md`（35 行）；先红 `assert 120 == 114` 后绿 `2 passed`，失败原文未摘要 |
| 2026-11-10 | E-designer-01 | 德鲁伊 | **accept**（独立复审） | `designer.md`（40 行）＋`designer.envelope.json` 过 eval-check ok=true；开关轨道对比 1.49–2.42:1 未达 3:1 如实披露 |
| 2026-11-10 | E-writer-01 | 游学者 | **accept**（独立复审） | `writer.md`（31 行）；checked 5 条带证据、unchecked 5 条待回交、未编造发布状态 |
| 2026-11-10 | E-archivist-01 | 青铜龙 | **accept**（独立复审） | `archivist.md`（40 行）；四字段齐、冲突如实标「暂不入库」、append-only |
| 2026-11-10 | E-reviewer-01 | 提里奥·弗丁 | **accept**（自产物，不标盲评通过） | `reviewer.md`（23 行）；三态 verdict、2 条 INFO 带证据，首行声明不构成通过判定 |
| 2026-11-10 | E-coordinator-01 | 康娜 | **accept**（最终复审判词 seq 363） | 产物为团队共享目录 kai-team 下 eval-2026-11-10 里的 coordinator.md（31 行，仓外文件不指链）；信封四字段齐、四段齐、fact 带证据、不替用户拍板、末尾声明未自评 |
| 2026-11-10 | COM-01/02/04 实跑 | 康娜 | **盲评通过**（清晰度/自然度/角色辨识度按 canon 正本判，复审判词 seq 363） | 三题均结论先行、术语转白话、≤3 行；盲评表见复审判词 |
| 2026-11-10 | COM-03/05/06/07/08/09 | — | **未执行** | 本轮按委托只实跑 3 题，其余不虚构 |
| 2026-11-10 | 人工盲评（七专业产物辨识度粗判） | 提里奥·弗丁 | 复审判词 seq 350：七份辨识度清晰；designer 视觉稿人眼观感未评 | 复审判词原文 |

失败类型编码（跑起来后填）：`schema`（字段/枚举不符）／`evidence`（fact 缺证据）／
`verdict`（判词越权或旧值）／`secret`（疑似密钥）／`role`（角色混用）／`clarity`（人工盲评不达标）。
