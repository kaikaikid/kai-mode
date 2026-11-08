# 第 0 步：缺口扫描（全只读）

| 项 | 只读探法 | 判「已就位（跳过）」 | 判「需处理」 |
|---|---|---|---|
| 1 正本技能 | 按 `.claude-plugin/marketplace.json` 的插件目录派生 `skills/*/SKILL.md` 清单，逐个检查文件与互指 | 清单内都在、互指一致 | 缺文件或互指断裂 |
| 2 宿主同步 | `python <本技能目录>/scripts/magpie-sync.py check` | 漂移表三面全绿 | 有漂移文件（列出具体哪些） |
| 3 默认入口 | 读项目 `CLAUDE.md` / `AGENTS.md` 与宿主的用户级默认入口口，有没有「默认入口＝康娜」段 | 有且指向 `gold`（两处都有按项目级） | 缺 → 列进推荐清单，并告知可选全局级 |
| 4 环境三项 | `test -x` 解释器/node、`test -d node_modules` | 三项都有明确读数 | 任一项缺（报绝对路径） |
| 5 门禁 | 项目仓门禁脚本 | 全绿或只基线告警 | 有红（列出哪道门） |
| 6 配置实例 | 读 `<root>/.ai/kai-mode.project.json` 的 `schema` | schema 5 且无 V1 键 | 无实例 → 生成；schema ≤4 → 迁移 |
| 7 宿主技能与命令 | 列宿主技能目录 | `gold` / `fleet` 等技能与命令能读到 | 缺落点 → 补，软约束登记 |
| 8 同名技能冲突 | `magpie-sync.py check --json` 看 `conflicts[]` | 无冲突 | 有冲突 → 逐条问用户去留，不静默覆盖 |
| 9 开票归属守卫 | 读宿主 `settings.json` 的 `hooks.PreToolUse` | 钩子已挂且自测 ok | 未挂 → 列进推荐清单 |
| 10 V1 残留 | `python <本技能目录>/scripts/uninstall-v1.py [--repo <项目仓>]`（只读探测） | 七个 V1 技能全为「—」，无待人工项 | 有命中 → 走「卸载 V1」腿，用户点头后 `--apply` |

## 产出

把清单念给用户：已就位逐项说「跳过」，需处理项附原因。
**能只读判定的，绝不做写操作。**
