# {{PROJECT_NAME}} 攻略（GUIDE）

> 人读文档：项目在哪、怎么跑、谁负责、哪里会踩坑。
> 机器字段只住 `.ai/kai-mode.project.json`；本文件重复一条机器事实即视为漂移。
> 模板正本住框架仓 `templates/GUIDE-template.md`；落点 `<项目仓>/.ai/GUIDE.md`（tracked）。
> 章节契约见 `schemas/guide.schema.json` 的 `x-guide-sections`；`scripts/map-check.py` 按它核对。

## 目标与边界

- 要解决的问题：
- 完成的样子：
- 不做：
- 边界：本项目不替别的仓保管事实；跨项目的事走框架仓或数据根。

## 目录地图

| 路径（仓根相对） | 放什么 |
|---|---|
| `src/` | |
| `scripts/` | |
| `.ai/kai-mode.project.json` | 机器契约（tracked），技能运行时从这里读路径/宿主/平台 |
| `<项目仓>/.ai/GUIDE.md` | 本攻略（人读） |
| `.ai/skills/project-skills/` | 项目专属技能正本（tracked） |

路径按仓根相对写，不写盘符。

## 命令

| 用途 | 命令 |
|---|---|
| 测试 | |
| 构建 | |
| 部署 | 无 |

没有的命令写「无」，不编；命令的机读副本仍住机器契约，不在这里另立一套。

## 角色与技能

- 主 AI 入口：
- 项目技能正本：`.ai/skills/project-skills/`；宿主 skills 目录优先用 junction 指向这里，失败才 copy，并在副本标 `generated cache`。
- 专家 profile：`.ai/roles/profiles/*.md` 是 `render-roles.py` 的渲染缓存，标 `generated cache`、由 `.gitignore` 排除、升级后重渲染——不手改、不当正本。
- 本项目的角色特化：只引用框架角色契约，不复制正文。

## 红线

- 花钱、对外发布、不可逆操作、删未提交工作：先停下问人。
- 本项目的额外红线：
- 不许把框架内容 junction 进本项目仓；不许软链/junction 主树 `node_modules` 后跑包管理器。

## 交付

- 交付物：
- 验收口径（可机检的优先）：
- 出口：测试/构建命令与产物的落点。

## 坑

- 已知坑：
- 症状 → 原因 → 规避：
- 本机上容易踩的环境差异：

## 链接

- 机器契约：`.ai/kai-mode.project.json`
- 发布形态：`<项目仓>/.ai/dual-repo.md`（存在时）
- ADR：项目自己的 ADR 目录（见机器契约 `registry.adrs.dir`）
- 框架规范：`docs/guide-landing.md`、`docs/agent-data-layout.md`
