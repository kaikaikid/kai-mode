# 地图、地区与攻略：落点与投射规则

一句话：**地图住数据根、地区住项目仓、攻略只链接不复述**；schema、模板、校验器住框架仓。
裁决来源：plan §7.6、ADR-0037 D3（`project:<region-id>`）。术语见 [GLOSSARY](../GLOSSARY.md)。

## 0. 三类东西，三个家

| 东西 | 落点 | 性质 | 谁写 |
|---|---|---|---|
| 冒险者地图 | `<KAI_AGENT_DATA_ROOT>/kai-mode/map.json` | untracked 机器事实 | 登记地区时写 |
| 地图 schema | `schemas/map.schema.json` | tracked | 框架维护 |
| 地区 | 一个项目仓（region-id 是它的身份） | — | — |
| 地区机器契约 | `<repo>/.ai/kai-mode.project.json` | tracked；机器字段唯一家 | `scripts/init-project.py` |
| 攻略 | `<repo>/.ai/GUIDE.md` | tracked；人读 | 项目开工时按模板填 |
| 攻略章节契约 | `schemas/guide.schema.json` | tracked | 框架维护 |
| 地区技能 | `<repo>/.ai/skills/project-skills/` | tracked；项目专属技能正本 | 项目自己 |
| 地图校验 | `python scripts/map-check.py` | tracked | 框架维护 |

数据根口径见 [agent-data-layout.md](agent-data-layout.md)。地图是**机器路径的唯一合法住处**；
tracked 仓里不许出现盘符路径。

## 1. map.json 的形状

顶层是信封，地区放在 `regions` 数组里；`id` 在整张地图内唯一。

```json
{
  "schema": "kai-map/1",
  "regions": [
    {
      "id": "<仓库名 slug>",
      "name": "<人读名称>",
      "path": "<项目仓机器绝对路径>",
      "remote": "<git origin 或 null>",
      "default_branch": "main",
      "instance": ".ai/kai-mode.project.json",
      "guide": ".ai/GUIDE.md",
      "runtime": { "backend_python": null, "node": null, "deps": null },
      "channels": ["claude"],
      "trust": "trusted"
    }
  ]
}
```

- `path` 是机器绝对路径；`instance`、`guide` 是相对仓根，且不得越出仓根。
- `trust` 只取 `trusted | review-required`；后者表示每次施工前要人复核。
- `runtime` 只记发现到的入口，不替代机器契约里的 `runtime` 解析规则。
- 字段形状以 `schemas/map.schema.json` 为准；本文件的示例只示意，不是第二把尺。

## 2. region-id 规则

- 形如仓库名 slug：`^[a-z][a-z0-9-]*$`。
- 在 map 内**唯一、不可变**；改名或原仓库名不是 slug 时，旧名进 `aliases[]`。
- 记忆命名空间 `project:<region-id>` 直接取这个值（ADR-0037 D3）；region-id 变了等于换了命名空间，
  所以只增别名、不改 id。
- 唯一性由 `map-check` 判红（含 id 与 aliases 的跨列冲突）。

## 3. 攻略（GUIDE.md）

- 落点 `<repo>/.ai/GUIDE.md`，tracked、人读；模板 `templates/GUIDE-template.md`。
- 章节：目标与边界、目录地图、命令、角色与技能、红线、交付、坑、链接。
- **只链接，不复制**：命令、路径、票平台、发布形态等机器字段仍只住 `.ai/kai-mode.project.json`；
  攻略重复一条机器事实即视为漂移。
- 章节契约住 `schemas/guide.schema.json` 的 `x-guide-sections`；`map-check` 按 `## <标题>` 找章节，
  缺节只提示（模板迁移是渐进的），不判红。

## 4. 投射规则（Q19）

| 东西 | 怎么投 | 关键约束 |
|---|---|---|
| 项目技能 `.ai/skills/project-skills/*` | 宿主 skills 目录优先 **junction** 指向正本；失败才 **copy** | junction 只对项目 skills；copy 的副本必须标 `generated cache` |
| 专家 profile `.ai/roles/profiles/*.md` | `render-roles.py` 渲染 | 是**渲染缓存**，不是链接；标 `generated cache`，项目 `.gitignore` 排除，升级重渲染 |
| 框架内容 | 不投进项目仓 | 不许把框架 skill/角色 junction 进项目；按名从宿主中央库调用 |
| 主树 `node_modules` | 不软链、不 junction | 依赖在各自 worktree 离线装 |

为什么区分三种：正本要 tracked 可审计；链接要能一眼看出指向；缓存要能随时重建、绝不手改。
`copy` 兜底只在 junction 不可用（权限、跨盘、宿主限制）时用，所以必须留下 `generated cache`
标记，升级时才敢覆盖。

## 5. map-check 怎么跑

```bash
python scripts/map-check.py                          # 读 $KAI_AGENT_DATA_ROOT/kai-mode/map.json
python scripts/map-check.py --map <map.json>         # 指定地图
python scripts/map-check.py --map <map.json> --json  # 机器读
```

校验：schema 形状、region-id/别名唯一、`path` 存在且是目录、`instance`/`guide` 存在且不越出仓根、
攻略章节齐全（缺节只提示）、remote/default_branch 与 git 对账（只提示）。

退出码：`0` 全绿（可含提示）／`1` 有红／`2` 缺件或坏 JSON（地图、schema、jsonschema 包）。

## 6. 一个事实只有一个家

| 事实 | 唯一家 | 别处 |
|---|---|---|
| 机器路径、命令、票平台、发布形态 | 项目 `.ai/kai-mode.project.json` | 攻略只链接；地图只存定位所需 |
| 地区身份 | map.json 的 `id` | 记忆命名空间引用它，不复述规则 |
| 人读说明 | 项目 `<repo>/.ai/GUIDE.md` | 框架只留模板与章节契约 |
| 数据根布局 | `docs/agent-data-layout.md` | 本文件只指向 |
