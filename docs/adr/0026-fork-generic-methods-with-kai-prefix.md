# 0026 通用方法技能改 fork：`kai-` 前缀、随插件安装、上游手动吸纳

## Status

accepted —— 2026-10-29（用户拍板：7 个通用方法技能统一加 `kai-` 前缀，按 fork 处理，上游更新看情况吸纳）

## Context

- 2026-10-24 起的做法是 vendor：7 个通用方法技能（tdd／code-review／diagnosing-bugs／domain-modeling／to-tickets／writing-for-agents／security-audit）原样复制进 `vendor/skills/`，一个字不许改，靠 `vendor-sync --check` 与 `manifest.json` 逐文件 sha256 钉死；上游更新由维护者 sync 后提交。
- 三个代价暴露出来：① 用户无法按项目微调（要改行为只能改调用它的流程位）；② 上游镜像一漂移 doctor 就红（本次改动前基线 29 项里的那 1 红即此）；③ 随仓分发但不随插件安装，宿主里只有用户自己装的上游同名件，流程位读的却是仓内路径，两套内容可能悄悄分叉。
- 用户裁决（2026-10-29）：接受「第二份同义判据」的代价，换取可微调与可控的上游吸纳节奏；命名用 `kai-` 统一前缀，避免与用户自装的同名上游件在宿主里互相覆盖。

## Decision

- **D1 迁入新插件 `methods/`**：7 个技能从 `vendor/skills/` 迁到 `methods/skills/kai-<上游名>/`，目录名＝技能名＝frontmatter `name`；frontmatter 改本仓八字段。首次迁移**零内容改动**——正文保持上游原文，只换 frontmatter、挪伴生文件位置。
- **D2 上游溯源继续住 `docs/skill-sources/`**：`sources.json` 状态 `vendored` → `adopted`，`specialized_as` 指向 `methods/skills/kai-*`，本仓改动记进 `deltas`；30 天对账节奏不变，吸纳＝人工 diff 后改正文并更新 deltas。
- **D3 退役 vendor 机制**：删 `vendor/`、`scripts/vendor-sync.py` 与 doctor 的 `vendor-sync` 项（29 → 28）；上游指纹由 `sources.json` 承接，安装面内容摘要由 `manifests/plugins.lock.json` 承接。
- **D4 装机档位**：7 个 `kai-*` 只进 `full`，`core` 保持最小闭环。宿主里 `kai-*` 与用户自装的同名上游件并存——名字不同即不互相覆盖，这正是加前缀的目的。
- **D5 上游 `agents/openai.yaml` 不随 fork 携带**：本仓宿主适配住 `adapters/`，不散在技能目录；`security-audit` 的 MIT `LICENSE` 随件保留。
- **D6 已知代价显式豁免**：加前缀＝造第二份同义判据，与 `principle-one-semantics-one-home` 的字面冲突。本 ADR 豁免它——方法正文只有一个家（`kai-*`），上游件只在宿主侧作为用户自己的选择存在。微调**必须**记 `deltas`，否则下次吸纳会覆盖掉。

## Consequences

- 用户可以直接改 `kai-*`；改了什么写进 `sources.json` 的 `deltas`，吸纳上游时按 deltas 逐条对。
- doctor 不再依赖本机 `~/.workbuddy/skills` 镜像判红；上游漂移改由 `source-check.py` 的 30 天对账提醒。
- 安装面多 7 个技能；宿主技能列表里会出现 `kai-tdd` 等名字，触发词与上游件相近，由 description 的触发行区分（`kai-*` 写明「施工环节默认方法」等流程位）。
- `vendor-sync` 的「源变了自动覆盖」能力消失；吸纳上游变成人工动作——这是本决定的核心取舍。

## 验证

- `python scripts/doctor.py --with-tests` 全绿（项数 29 → 28）。
- `magpie-sync check` 显示 `kai-*` 七条与库逐字相同；`plugins.lock.json` 含 `methods` 0.1.0。
