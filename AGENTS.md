# kai-mode

Framework repo, independent of any project repo. Run `python scripts/doctor.py` before and after
every change — 26 checks, red means `rc=1`.  
`vendor/` is tracked (clones must be able to restore it); `scripts/tests/` runs under
`doctor.py --with-tests` (needs pytest) and is part of that gate.

## Writing docs: run the script, don't hand-write

| What you're writing | Do this instead |
|---|---|
| New skill | `python scripts/new-skill.py <name> --summary "..."` (skeleton + frontmatter + registry in one go) |
| Handoff doc | copy `handoff/templates/HANDOFF-template.md` → land in `handoff/<slot>/<YYYY-MM>/` |
| New persona | follow `agents/README.md`, land in `agents/<name>.md` (bare name — the `kai-` prefix is for `skills/` only, it guards against `magpie-sync` overwriting the central library) |
| Cross-agent task | `python scripts/handoff-board.py new \| claim \| close \| archive` |

Five hard rules (reasons live in the pointers below, they are **not** repeated here — this file
stays short on purpose, it is read every session):

1. frontmatter: fixed fields in fixed order — skill 8 / handoff 6 / persona 4 (`name` `description`
   `version` `metadata`); persona `metadata` holds **one key** (`access`), never new top keys
2. Paths are always repo-root relative; **no drive-letter absolute paths**
3. Terse, conclusion-first; no marketing words
4. One rule has one home — everywhere else, leave a pointer only
5. `python scripts/doctor.py` green before you stop

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

## Wake fence

Roles never create or wake each other's sessions. Only a human starts a role; the scheduler may
wake **tower only**. `kai-mode` routes and prints the command but does not call session-creation
tools. Subagents within a ticket are not role sessions. Source of truth:
`docs/adr/0010-role-wake-fence.md`.

## Where each kind of rule lives (one kind, one home)

| Kind | Only home | Elsewhere |
|---|---|---|
| Non-negotiable constraints (red lines) | this file | pointer |
| Ticket-level protocol (slots, fail/retry counts, receipt, shipping) | `loops/loop-protocol.md` | pointer |
| Out-of-ticket dispatch (when not to delegate, who may dispatch whom, concurrency, context budget) | `agents/dispatch.md` | pointer |
| Method (how to explore / review / plan / implement) | `agents/<persona>.md` | pointer |
| Host differences (launcher per role, how a persona becomes a native agent file, permissions, model) | `adapters/README.md` + `adapters/<host>.md` | pointer |
| Artifact packaging (dev records vs host payload vs project scaffold) | `manifests/package-layout.json` + `docs/package-layout.md` | pointer |
| Agent global data layout (non-project data root, per-agent override, project boundary) | `docs/agent-data-layout.md` | pointer in adapters |
| Project config instance: key set | `docs/adr/0015-schema-4-keys-with-consumers.md` (a key must have a live consumer) | pointer |
| Project config instance: default-value policy | `docs/adr/0014-config-instance-no-invented-values.md` + `templates/kai-mode.project.json` | pointer |
| Role wake permissions (who may wake whom) | `docs/adr/0010-role-wake-fence.md` | pointer in role skills |
| Runtime mechanics (retry, timeout, circuit breaker, budget, TTL) | **not in docs** — belongs to the host runtime | — |
| Project instance values (thresholds, paths, ticket ids, **agent models** `models.agents.<persona>.model`) | project config instance | template only |

Dependency direction is one-way: project layer may point at the persona layer, `agents/<persona>.md`
must never point back. `docs/canon.json` + doctor's `canon-dup` check enforce both directions
mechanically. To write about a retired mechanism on purpose, mark that line `canon:allow-retired`.

## Where the rules actually live

| Topic | Source of truth |
|---|---|
| Skill layout & frontmatter contract | `docs/skill-layout.md` |
| Writing a SKILL / AGENTS doc | external skill `writing-for-agents` (not forked; list in `docs/skill-sources/workflow-skills.md`) |
| Sub-agent persona contract | `agents/README.md` |
| Handoff docs & cross-agent board | `handoff/README.md` · `handoff/60-board/README.md` |
| External skills kept as reference material | `docs/skill-sources/README.md` |
| Architecture decisions | `docs/adr/` |
| Single-ticket loop | `loops/loop-protocol.md` |

## Issue tracker

Issues live in GitHub Issues, driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

## Triage labels

The five canonical role labels, used as-is. See `docs/agents/triage-labels.md`.

## Domain docs

Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root, this repo's own numbering from `0001`. See `docs/agents/domain.md`.

## Handoff docs

Session handoffs and one-off working docs live in `handoff/`, sorted by purpose into numbered slots
(`10-session/` `20-plan/` `30-research/` `40-review/`, plus `00-inbox/` and `90-archive/`).
Pick the slot from the type word in the filename. Full rules: `handoff/README.md`.

## Commands

```bash
python scripts/doctor.py [--with-tests]          # 26 checks; --with-tests includes scripts/tests
python scripts/new-skill.py <n> --summary "..."  # skill scaffold
python scripts/vendor-sync.py [--check]          # vendored skills: pull from local mirror / detect drift
python scripts/handoff-board.py list             # cross-agent board
python scripts/source-check.py                   # external source material drift
powershell -File scripts/setup-agent-data.ps1 -Root "<本机数据根>"   # agent 全局数据根（dry-run；加 -Apply）
```
