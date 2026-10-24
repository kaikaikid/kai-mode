# 素材：handoff（mattpocock/skills）

> 摘要，非正本。正本在源件本身（指针见下）。本件用于对账与学习。

## 1. 指针

| 项 | 值 |
|---|---|
| 上游 | mattpocock/skills（社区技能集，workbuddy 已装） |
| 本机用户级 | `~/.workbuddy/skills/handoff/SKILL.md` |
| 中央库 | `<magpie>/data/library/skills/handoff/SKILL.md` |
| 本仓特化版 | `skills/kai-handoff/SKILL.md`（registry 第 16 条，install: auto） |
| 规模 | 17 行 |
| 指纹 | `7c62de97…`（首次记录 2026-10-24） |

## 2. 源件六条约定（原文要点）

1. 把当前会话压缩成一份交接文档，给一个全新 agent 续接
2. **存 OS 临时目录**，不存工作区
3. **必须含 `suggested skills` 段**，点名下一棒该调哪些技能
4. 不复制其他产物内容（spec / plan / ADR / issue / commit / diff），只给路径或 URL
5. 脱敏：密钥、密码、个人身份信息
6. 传参时把参数当作「下一会话焦点」的描述，按它定制文档

## 3. 本仓改了什么（deltas）

| # | 源件 | 本仓 | 为什么 |
|---|---|---|---|
| 1 | 存 OS 临时目录 | 存 `handoff/<槽>/<YYYY-MM>/` | 项目内、git 可追、跨会话可续 |
| 2 | 格式自由 | 强制 frontmatter 六字段 | AI 读字段认用途，不读正文猜（语义推断会随模型漂移） |
| 3 | 无门禁 | `scripts/doctor.py` `handoff-slots` 项校验，红即 rc=1 | 纸面规范没人守 |

其余四条（suggested skills、不复制、脱敏、按参数定制）**原样继承**。

## 4. 对账步骤（上游更新后）

1. `python scripts/source-check.py` → 看指纹是否变了
2. 读 `~/.workbuddy/skills/handoff/SKILL.md`，与上一版 diff
3. 新约定并入 `skills/kai-handoff/SKILL.md`；与本项目口径冲突的，**以 `handoff/README.md` 为准**
4. 升 `version`，跑 `python scripts/doctor.py` 到绿
5. 重跑 magpie 入库（**只推特化版，源件依旧不入库**）
6. 更新 `sources.json` 的 `sha256` / `last_diff` / `next_diff_due`

## 5. 为什么特化版不叫 `handoff`

中央库与用户级都已有通用版 `handoff`。同名会让 `magpie-sync apply` **覆盖通用件**——
非 kai-mode 项目里调 `handoff` 会被要求写本项目 frontmatter，通用场景失效。
故取 `kai-handoff`，与 `agents/` 的 `kai-*` 同前缀，通用件与项目件并存不打架。
