# kai-mode

Framework repo, independent of any project repo. Run `python scripts/doctor.py` before and after
every change — the 总结 line prints the check count; red means `rc=1`.  
`methods/` holds forked generic-method skills (`kai-*`, upstream absorbed by hand — see
ADR-0026); `scripts/tests/` runs under `doctor.py --with-tests` (needs pytest) and is part of
that gate.

## Writing docs: run the script, don't hand-write

| What you're writing | Do this instead |
|---|---|
| New skill | `python scripts/new-skill.py <name> --summary "..."` (skeleton + frontmatter + registry in one go) |
| Handoff doc | copy `handoff/templates/HANDOFF-template.md` → land in `handoff/<slot>/<YYYY-MM>/` |
| Cross-agent task | `python scripts/handoff-board.py new \| claim \| close \| archive` |

Five hard rules (reasons live in the pointers below, they are **not** repeated here — this file
stays short on purpose, it is read every session):

1. frontmatter: fixed fields in fixed order — skill 8 / handoff 6; never new top keys
2. Paths are always repo-root relative; **no drive-letter absolute paths**
3. Terse, conclusion-first; no marketing words
4. One rule has one home — everywhere else, leave a pointer only
5. `python scripts/doctor.py` green before you stop

## Communication

Explain professional problems in plain language — no jargon without explanation, use everyday analogies when possible. If a term is unavoidable, explain it first before using it.

## Agent effort policy

Sub-agents inherit the session's effort by default (currently max). To avoid wasting tokens, always pass `effort` explicitly when spawning agents:

| Task type | effort | Examples |
|---|---|---|
| Mechanical (read files, grep, rename, run tests) | low | scan files, run doctor, read single file |
| Standard work (bug fix, feature, code review) | medium | fix a bug, implement a function, review a PR |
| Complex (architecture, root-cause debug, multi-file refactor) | high | diagnose hard bug, design module interface |
| Extreme (deep reasoning, adversarial review) | xhigh/max | only when truly needed |

Rule: never omit `effort` and let it inherit max. Pass it explicitly per task type.

Outputs follow the L1–L4 carrier ladder (text → diagram → single-file HTML → explainer video, cheapest first). Source of truth: `core/skills/principle-output-structure/SKILL.md`.

## Red lines (the only hard stops; everything else is a default)

| Red line | Meaning |
|---|---|
| Spend money | paid executors, cloud resources, third-party services |
| Publish outward | deploy, release, post publicly, send mail |
| Irreversible | history rewrite, force-push, data migration, destructive schema change, permission/security boundary change |
| Delete uncommitted work | anyone's uncommitted files, worktrees, or logs |
| Commit/push development data | runtime sessions, logs, DBs, caches, verification reports, agent data, this repo's own `handoff/` records |

Development data stays outside the repo (`KAI_AGENT_DATA_ROOT`) or in an ignored path. What a clone
should contain is methodology + installer only. If dev data is already tracked, remove it from the
index and add an ignore rule — never just hide it, never delete the on-disk evidence.

On a red line: stop that ticket only, record why, ask the human. Never self-approve by editing the
approval rule (or your own permissions) first. An approval must be traceable — it binds ticket +
scope + risk, and goes stale when scope changes.

## Entry fence

`bridge` is the only conversational surface and the default entry. It does not call session-creation
tools to wake other roles; there are no other roles. A session that is not explicitly pointed at another
skill runs bridge's method. Source of truth: `docs/adr/0028-bridge-entry-and-airport-retirement.md`.

## Where each kind of rule lives (one kind, one home)

| Kind | Only home | Elsewhere |
|---|---|---|
| Non-negotiable constraints (red lines) | this file | pointer |
| Run-level protocol (slots, fail/retry counts, receipt, shipping) | `v2/skills/travel/SKILL.md` | pointer |
| Dispatch (when to delegate, context budget, report shape) | `v2/skills/travel/SKILL.md` | pointer |
| Method (how to explore / review / plan / implement) | `methods/skills/kai-*/SKILL.md` | pointer |
| Output structure (which carrier: L1 text / L2 diagram / L3 single-file HTML / L4 explainer video) | `core/skills/principle-output-structure/SKILL.md` | pointer |
| Host differences (launcher per role, how a persona becomes a native agent file, permissions, model) | `adapters/README.md` + `adapters/<host>.md` | pointer |
| Artifact packaging (dev records vs host payload vs project scaffold) | `manifests/package-layout.json` + `docs/package-layout.md` | pointer |
| Agent global data layout (non-project data root, per-agent override, project boundary) | `docs/agent-data-layout.md` | pointer in adapters |
| Project config instance: key set | `docs/adr/0015-schema-4-keys-with-consumers.md` (a key must have a live consumer) | pointer |
| Project config instance: default-value policy | `docs/adr/0014-config-instance-no-invented-values.md` + `templates/kai-mode.project.json` | pointer |
| Role wake permissions (who may wake whom) | `docs/adr/0010-role-wake-fence.md` | pointer in role skills |
| Runtime mechanics (retry, timeout, circuit breaker, budget, TTL) | **not in docs** — belongs to the host runtime | — |
| Project instance values (thresholds, paths, ticket ids) | project config instance | template only |

Dependency direction is one-way: project config may point at framework skills; installed skills
must never point back at the project. `docs/canon.json` + doctor's `canon-dup` check enforce this
mechanically. To write about a retired mechanism on purpose, mark that line `canon:allow-retired`.

## Where the rules actually live

| Topic | Source of truth |
|---|---|
| Skill layout & frontmatter contract | `docs/skill-layout.md` |
| Writing a SKILL / AGENTS doc | skill `kai-writing-for-agents`（fork 自上游；溯源见 `docs/skill-sources/workflow-skills.md`） |
| Sub-session dispatch contract (depth, context budget, report shape) | `v2/skills/travel/SKILL.md` |
| Handoff docs & cross-agent board | `handoff/README.md` · `handoff/60-board/README.md` |
| External skills kept as reference material | `docs/skill-sources/README.md` |
| Architecture decisions | `docs/adr/` |
| Run lifecycle (one issue, one run) | `v2/skills/travel/SKILL.md` |

## Issue tracker

Issues live in GitHub Issues, driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

**开票归属**：本仓 Issue 只收框架自身问题，项目票一律开到项目仓。`gh issue create` / `gh pr create`
必须显式带 `--repo <owner/name>`，**不得靠 cwd 推断**——cwd 在项目仓时 `gh` 会自动落到项目仓，
这就是「票开错仓」的常见成因。目标仓从项目配置实例或 `git remote -v` 读；读不到就停手问人。

**能否杜绝**：只写在 AGENTS.md **不能**机械杜绝，模型仍可能不带 `--repo` 直接跑。真正的拦截靠宿主
hook（PreToolUse 拦 `gh issue create|gh pr create`，缺 `--repo` 即拒）：脚本 `issue-guard.py`、
接法与验收住 `adapters/claude.md`「开票归属钩子」，**只能由 `set-kai-mode` 第 6 步探到缺口并问过用户后安装**。
**本仓当前未装该 hook ⇒ 状态＝规则约束、未机械拦截**；装好后把这句改成「已机械拦截」并写 hook 落点。

## Triage labels

The five canonical triage labels are listed in `docs/agents/triage-labels.md`. The V1 lane labels
(`main-queue`, `deputy-queue`, `second-queue`, `ace-queue`) are retired with the airport system;
no skill reads them anymore.

## Domain docs

Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root, this repo's own numbering from `0001`. See `docs/agents/domain.md`.

## Handoff docs

Session handoffs and one-off working docs live in `handoff/`, sorted by purpose into numbered slots
(`10-session/` `20-plan/` `30-research/` `40-review/`, plus `00-inbox/` and `90-archive/`).
Pick the slot from the type word in the filename. Full rules: `handoff/README.md`.

## Commands

```bash
python scripts/doctor.py [--with-tests]          # 项数以 stdout 汇总行为准；--with-tests 含 scripts/tests
python scripts/check-instance.py --repo <项目仓>   # 校验项目仓那份配置实例（键集/占位/机器路径/落点/退役键）
python scripts/new-skill.py <n> --summary "..."  # skill scaffold
python scripts/source-check.py                   # external source drift / 30-day reconcile reminder (forked methods included)
python scripts/handoff-board.py list             # cross-agent board
powershell -File scripts/setup-agent-data.ps1 -Root "<本机数据根>"   # agent 全局数据根（dry-run；加 -Apply）
```
