# 0039 经批准的具名施工引擎：Hermes 调 CC CLI

## Status

**accepted —— 2026-11-24 用户拍板。**

原始用户原话：「解除不拉 CLI 进程的限制，反正你能管理的方式调用cc」。

本 ADR 是 ADR-0033 D3「跨宿主借兵要另立 ADR 并经用户批准」的具名批准件：批准**这一对**组合，不开放通用跨宿主借兵。

## Context

- ADR-0033 D3 定「角色实例的入口必须属于当前宿主」；跨宿主拉别家 CLI 需另立 ADR 并经用户批准（家在 `adapters/README.md`）。
- 实际工程需要：kai-vass 用 Hermes 的康娜 profile 做调度入口，代码施工交给本机 CC CLI（接本地 magpie 网关、由用户管理，不消耗别家额度）。
- CC CLI 是用户自己管理、自己授权的施工执行体；原禁令顾虑的「消耗别家额度」在此不成立。
- 用户已显式批准，满足 ADR-0033 D3 的前置。

## Decision

### D1 具名例外
在 Hermes 宿主内，主会话可按需拉 CC CLI 的一次性独立进程作为**施工引擎／子代理执行体**，用于 kai-vass 及其后续同类项目的代码施工。这不视为违规跨宿主借兵。

### D2 边界不放松
- 本批准**仅此一对**（Hermes → CC CLI）。其它跨宿主组合仍按 `adapters/README.md` 走「另立 ADR + 用户批准」。
- 不改变 ADR-0033 D3「角色实例入口属于当前宿主」：`roles/canon/coordinator.md` 与各职业技能里的「禁止跨宿主借兵」针对的是**角色实例入口**，不是一次性施工进程；本次不改那些正本。
- CC CLI 只作一次性施工上下文，不做常驻角色实例、不互相唤醒。
- 花钱／对外发布／不可逆／删未提交等红线仍按 AGENTS.md，不因本 ADR 放宽。
- 施工命令样例住 `adapters/<宿主>.md` 与装机回执，框架正文不写具体 slug。

### D3 规则归家
- 跨宿主借兵的默认禁令与例外，规则正本仍住 `adapters/README.md`；本 ADR 只记录具名批准。
- `engine/README.md` 与 `engine/skills/fleet/SKILL.md` 的「只走宿主原生子代理，不拉 CLI 进程」按冲突账本 C9/C10 降为指针，指向 `adapters/README.md` 与本 ADR；不再各存一份正本。
- Hermes 作为未登记宿主，补进 `adapters/README.md` §2 落法对照表。

## 影响

- 改判据 home `adapters/README.md`、指针 `engine/README.md`、`engine/skills/fleet/SKILL.md`、`adapters/codex.md`、`adapters/opencode.md`。
- 不改角色正本／皮肤／persona，不改已批准的 ADR-0033 正文（本件在其之上叠加具名例外）。
- `python scripts/doctor.py` 须复绿。
