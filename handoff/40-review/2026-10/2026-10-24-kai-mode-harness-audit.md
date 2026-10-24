---
slot: 40-review
type: audit
ticket: "-"
date: 2026-10-24
owner_role: 机长
persona: reviewer
---

# kai-mode harness audit（首次自证）

审计面：41 件（技能 19、人格 6、ADR 9、协议 1、规范 6）。盘点命令：
`python skills/harness-audit/scripts/inventory.py --root . --summary`。

| 件 | 判词 | 证据 | 建议 |
|---|---|---|---|
| `schemas/task.schema.json`、`schemas/event.schema.json` | Retire | task 仍要求 `lease_id`／`contract_sha256`／11 态；event 仍用五角色与 loop A/B/C；全仓无消费者，README 仍宣传 | 按现行四岗位/三记录面重写，或删除并移除 README/kai-mode 指针；不要留反向契约 |
| `skills/航班信息/`、`skills/set-航班信息/` | Retire | git 仍跟踪 15 个文件（约 964KB）；`航班信息/SKILL.md` 引用已删的 `templates/board.config.example.json`；doctor 用 LEGACY_LOCKED 跳过 | `git rm -r --cached` 并从注册/文档移除；本机锁死的目录可留在盘上，但不能继续随 clone 分发 |
| `skills/{copilot,flight-info,ground-crew,harness-audit,kai-boom-idea-log,kai-handoff,pilot,tower}/`、`docs/adr/0007-0009`、`handoff/README.md`、`docs/canon.json`、`GLOSSARY.md` | Improve | inventory `tracked=false`：工作区新建件尚未进 git；clone 会缺 | 先做一次一致的快照提交（含 handoff/canon/ADR/新技能），再从干净 clone 跑 `doctor --with-tests` |
| `docs/adr/0007` D1、`docs/adr/0004` D2 | Improve | 正文仍完整描述已退役的 `agent-emit` 投影与 `tiers/default/roles`；只在文末演变注说退役 | 在 D1/D2 标题加“已被 0008 取代”横幅，或把退役段移入历史区；避免只读正文的 agent 照旧施工 |
| `scripts/source-check.py` | Improve | 打印“需处理 N”后仍 `return 0`；不在 doctor 里 | 有需处理项就 rc=1，或明确标注为 advisory-only |
| `skills/flight-info/scripts/install_hook.py` | Improve | 固定写 `.git/hooks/post-commit`，不读 `core.hooksPath`；本仓参考 `.githooks/pre-push` | 先读 `git config core.hooksPath`，按实际钩子目录安装，或明确登记限制 |
| `docs/agents/issue-tracker.md`、`docs/agents/triage-labels.md` | Improve | 仍提 `/wayfinder`、`/triage` 与 `mattpocock/skills` 标签；本仓没有这些技能 | 标注为外部参考件，或改成本仓实际流程/标签 |
| `skills/set-kai-mode/SKILL.md` 的安装命令 | Improve | `init-project.py`、`doctor.py`、`handoff/templates` 不在技能目录内；装到宿主后相对路径会落到项目仓 | 把伴随脚本/模板纳入技能目录，或统一用 `<框架仓根>/…` 并在缺件时失败（本轮已加说明，打包仍是缺口） |
| `docs/skill-sources/sources.json`、`vendor/manifest.json` | Improve | 只有本机路径与哈希，没有上游 URL/commit/license | 补 `repo`/`commit`/`license`，让 vendor 可追溯到具体上游版本 |
| `handoff/README.md` §5 | Keep | 本轮已把 15 天改成“建议归档”；`00-inbox` 7 天仍是 doctor 硬判据 | 无需再改；若日后要硬 TTL，另开票加检查 |

## 结论

- 首跑已能报出已知的“退役件/未跟踪/正文残留”三类问题，审计器不是全绿空转。
- 最挡路的是未跟踪件：工作区绿不等于 clone 绿；这必须先做一次干净快照。
- 本轮执行：中央库 `full` 安装 + `--retire-legacy`；旧角色目录移入 `.retired/`，旧注册条目与宿主旧链已摘，
  95 秒后回读无重建。git 里仍跟踪的旧目录另案清理。
- 下一轮 Quick Scan 只看本文件 mtime 之后变化的件。
