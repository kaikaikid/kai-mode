# 0009 评估与安装治理：语义审计、安装档位/回执、评审模式与宿主中立

## Status

accepted —— 2026-10-24 用户令「按照你的设计方案做完优化」。参考 [ECC](https://github.com/affaan-m/ECC)（MIT）的**机制层**，不移植其目录规模。

## Context

上一轮审查暴露的是「形状绿、语义盲」：

- doctor 能查字段/链接/路径/枚举，但查不出回执 40 行两说、轮巡 30/60/65 三个数、已删目录仍被引用、退役机制仍写在 schemas 里。
- `scripts/tests` 曾 9 红且不在门里；doctor 自身改动没有回归网。
- 中央库写入没有备份；没有安装档位；没有可核验的安装回执/来源。
- reviewer 有 code/security 模式，但没有专查静默失败的模式；dispatch 没有「委派者必须收口」的硬话。
- ADR-0008 要求宿主中立，但没有机检；`set-kai-mode` 里仍散落宿主专有 token。

ECC 同日实测有 311 个技能目录、71 个子代理、97 个命令、122 个规则文件、428 个测试、27 个 hook 条目；
它的 `skill-stocktake`、`harness-audit`、install profiles、install-state/provenance、`silent-failure-hunter`
与 delegation completion contract 是成熟形状。**可迁移的是这些机制，不是它的 agent/skill 数量。**

## Decision

### D1 语义审计：`harness-audit`（manual）

新增 `skills/harness-audit/`：只读盘点 + 模型审计，出 `Keep / Improve / Update / Retire / Merge into X` 判词，
落 `handoff/40-review/YYYY-MM/`；**不做 doctor 硬门**（语义判断硬门会制造假绿）。首次自证：拿当前仓跑，
必须能报出已知的过期/矛盾项；报全绿先修审计本身。

### D2 安装档位 + 安装回执 + 写前备份

- 档位正本＝`manifests/install-profiles.json`，只做两档：`core`（8 条最小闭环）与 `full`（16 条自动件）。
  档位只能引用 `install:auto` 条目；`core ⊆ full`。
- `magpie-sync install_plan(root, profile)` / `check` / `apply` 支持 `--profile`；缺省读库根回执里的档位，无回执＝full。
- 安装回执＝库根 `.kai-mode-source.json` 的扩展字段：来源根、HEAD、档位、技能清单、每技能 `tree_digest`。
  不新增第二份台账。
- `apply` 写库前整包备份到 `<库根>/.backups/<timestamp>/`（技能副本＋`library.json`＋来源标记＋哈希基线，保留 5 份）；
  写入异常或回写后仍有漂移 ⇒ 自动还原。
- 角色改名的一次性迁移走显式 `apply --retire-legacy`：旧中文目录移到 `<库根>/.retired/<时间>/`，宿主旧链摘掉；
  只摘符号链接，实体目录只报告不删。默认 apply 不删任何旧件。
- doctor 增 `install-profiles`（档位清单合法性）与 `install-receipt`（回执与库现状一致）；旧回执无 `skill_names` 时 skip，不判红。

### D3 reviewer 的 `silent-failure` 模式 + 委派完成契约

- `reviewer` 增 `silent-failure` 模式：猎空 catch、吞异常、危险 fallback、丢栈、缺 timeout/rollback；
  不新增人格（模式先于人格）。
- `agents/dispatch.md` §10：最终消息就是交付物；谁派谁收；不许以「等后台 agent」结束回合；
  只有单上下文装不下时才拆。`loop-protocol` §八只留指针，不复述。

### D4 宿主中立 lint + frontmatter YAML 形状

- doctor 增 `host-neutral`：扫 `skills/ loops/ agents/`，宿主专有 token（`CLAUDE_`、`qoder_cron`、
  `create_chat_session`、`.claude/`、`.opencode/`、`.codex/`、`codex exec`、`opencode run`、`mcp__*` 等）即红；
  宿主细节移入 `adapters/<宿主>.md`。退役目录不扫。
- doctor 增 `frontmatter-yaml`：拦未加引号值里的 `': '` 与 `@`/反引号开头的值；只做标准库可判的形状，不引 YAML 依赖。

### D5 不采纳

- 不采纳 ECC 的 71 agents／311 skills 目录规模：违反「模式先于人格」，上下文与维护成本大于收益。
- 不采纳每宿主一份投影目录：ADR-0008 已否决，ECC 的多目录树是漂移源。
- 不采纳 continuous-learning hook 引擎（观察会话、后台模型、自动 evolve）：绑宿主、需隐藏运行时，且与 handoff/auto-memory 重复。
  只保留其 instinct 字段格式作为可选 lesson 记录，不建引擎。
- 暂不采纳完整 eval harness / 5 轴评分：先把 doctor 测试网修绿，再谈 agent 评估。
- 不采纳每个 agent 重复一份 prompt defense：安全基线只住一处。

## Consequences

- doctor 从 19 项增到 **23 项**；`--with-tests` 现在包含仓级 `scripts/tests`，测试红＝门红。
- 新增 manual 技能 1 个（`harness-audit`），不进自动装机档位；registry 条目 16→17，自动装机仍 16。
- 安装多一次备份（技能副本大小级），换来可回滚；档位切换不清库内多余件（沿用「只新增/只覆盖」）。
- 旧中文角色目录默认不删；显式 `--retire-legacy` 才移到 `.retired/` 并摘旧链。git 里仍跟踪的旧目录另案清理。

## 明确不做

- 不把 semantic audit 做成 doctor 硬门。
- 不删除中央库或 git 里任何未提交/未备份内容。
- 不引入第三方 YAML/评测依赖；doctor 仍只用标准库（`--with-tests` 除外）。

## 验证（判据级）

- `python scripts/doctor.py --with-tests` 23 项全绿（中央库未同步时 `install-sync` 红是预期，需先 `apply`）。
- `python -m pytest scripts/tests -q` 全绿；`python skills/harness-audit/scripts/tests -q` 全绿。
- `python skills/set-kai-mode/scripts/magpie-sync.py --selftest` 通过。
- 档位：临时仓 `install_plan(root, "core")` 只含 8 条；`full` 含 16 条；未知档位/引用非 auto 条目退出非 0。
- 回执：apply 后 `.kai-mode-source.json` 有 profile/skill_names/hashes；备份目录存在；人为破坏库文件后 `install-receipt` 红。
- 审计首跑：对当前树至少报出已知的 40 行/周期/过期路径/schemas 退役词/缺模板中的若干项；报全绿即审计器坏。
