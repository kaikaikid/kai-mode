# 源技能指针 —— mattpocock/skills 的 `handoff`

> 本件**只放指针**。详细摘要与对账步骤住 **`docs/skill-sources/handoff-mattpocock.md`**
> （素材库正本，见 `docs/skill-sources/README.md`）——一个语义一个家，不养第二份。
> 源件全文不复制进本仓、不登记 registry、不进中央库。**入库的只有特化版本件所在的技能。**

## 指针

| 项 | 值 |
|---|---|
| 上游 | mattpocock/skills（社区技能集，workbuddy 已装） |
| 本机用户级 | `~/.workbuddy/skills/handoff/SKILL.md` |
| 中央库 | `<magpie>/data/library/skills/handoff/SKILL.md` |
| 素材库摘要 | `docs/skill-sources/handoff-mattpocock.md` |
| 结构化索引 | `docs/skill-sources/sources.json`（`id: handoff-mattpocock`） |
| 本仓特化版 | `skills/kai-handoff/SKILL.md` |

## 三处差异（相对源件）

| 源件 | 本仓 |
|---|---|
| 存 OS 临时目录 | 存 `handoff/<槽>/<YYYY-MM>/` |
| 格式自由 | 强制 frontmatter |
| 维护侧门禁 | 框架仓门禁的 `handoff-slots` 项校验 |

继承：`suggested skills` 段、不复制其他产物、脱敏、按参数定制。

## 对账

```bash
python scripts/source-check.py        # 看源件指纹变没变、到没到对账日（默认 30 天）
```

变了就按 `docs/skill-sources/handoff-mattpocock.md` §4 的五步并入本技能，升 `version` 并重新入库。
