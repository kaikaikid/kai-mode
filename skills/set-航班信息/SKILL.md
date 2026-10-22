---
name: set-航班信息
status: active
approved_by: human:kaikaikid
approved: 2026-10-22
sources:
  - resource: "skills/航班信息/SKILL.md"
    note: "板工坊正本：造板 / 刷新 / 归档 / 索引；本技能只做装配面（给别的仓装一块板）"
  - resource: "skills/航班信息/scripts/new_board.py"
    note: "建板与配置校验的正本；装配面 import 复用它，不复制判据"
  - resource: "skills/航班信息/templates/board.config.example.json"
    note: "完整板配置样例；最小配置只写 name ＋ sources，其余吃通用缺省"
  - resource: "skills/set-kai-mode/scripts/magpie-sync.py"
    note: "装机正本（正本 → 中央库 → 各家宿主链接）；只有 --install 才动它"
description: >
  装配面：给任意项目仓装一块航班信息板，装完即能用（板目录 + 配置留档 + 自包含脚本 +
  刷新入口 + 第一版板 + 板库索引 + 目标仓 .gitignore 两条规则）。
  拷问 ≤3 问（装哪个仓 / 板叫什么 / 读哪些源），答不上就按默认走。
  不造板工艺、不改判据、不动票面与日表；默认不装中央库。
  触发：给这个仓装一块航班信息板、我要个航班信息板、这个项目也要那块板。
version: 0.1.0
updated: 2026-10-22
---

# set-航班信息 —— 给任意项目仓装一块航班信息板

> 板工坊（造板/刷新/归档/索引）的正本在 [`../航班信息/SKILL.md`](../航班信息/SKILL.md)；**本技能只管装配**。
> 装配正本：脚本 [`scripts/setup_board.py`](scripts/setup_board.py)；骨架配置 [`templates/board.config.minimal.json`](templates/board.config.minimal.json)。

## 角色定位

**装配面**：别的仓、别的 agent 想用那块板时，一条路装好并能用 —— 不再手抄配置、手敲脚手架。

| | 板工坊 | 本技能（装配面） |
|---|---|---|
| 干什么 | 造板 / 刷新 / 归档 / 索引 | 给一个仓**装**一块板并跑通第一版 |
| 谁调 | 已经装了板的仓 | 第一次要在某个仓用板的人 |
| 判据在哪 | 板工坊的 SKILL.md 与脚本 | 本技能；**判据不重写**，脚本 import 复用板工坊的 |

**边界**：只写目标仓的 `.design/航班信息/` 与目标仓的 `.gitignore`；不改目标仓源码、票面、日表；不动中央库（除非显式 `--install`）；不改别的仓已有的板（`--force` 要先确认）。

## 激活方式

- 人工：`/set-航班信息`，或用户说「给这个仓装一块航班信息板」「我要个航班信息板」「这个项目也要那块板」。
- 定时：不装定时器（装配是一次性动作；刷板由板工坊那边管）。
- 上游：`/kai-mode` 判定"这个项目要用航班信息板"时拉起本技能；`set-kai-mode` 只管框架件的装机，不管板。

## 拷问（≤3 问，每题带推荐默认）

| # | 问 | 推荐默认 | 答不上怎么办 |
|---|---|---|---|
| ① | 装到哪个仓？ | **当前工作区根**（跑命令的目录） | 按默认走 |
| ② | 板叫什么？ | **配置里的板名**（最小配置＝`航班`） | 按默认走 |
| ③ | 读哪些源？ | **任务表目录 `.ai/tasks`**（多数机场式仓都有；没有则该源记 `absent`，板照样出） | 按默认走 |

- 源可加：GitHub issues / 里程碑（要 `owner/repo`）、交接日报目录。
- **答不上就按默认走**，别追问第 4 问；问完最多 3 题就动手。

## 装配流程

1. **拷问**（≤3 问，上表）—— 拿齐：仓根、板名、源。
2. **写/选配置**：直接用通用最小配置（`templates/board.config.minimal.json`，只写 `name` ＋ `sources`）；要加源就照板工坊的样例配置抄一份，改 `sources`。用户没指定就用最小配置。
3. **跑装配脚本**：

   ```bash
   python skills/set-航班信息/scripts/setup_board.py --repo-root <项目仓根> \
       [--config <板配置.json>] [--name <板名>] [--force] [--install] [--no-build] [--quiet]
   ```

   脚本按九步走（探测 → 取配置 → 校验 → 建板 → 补 `.gitignore` → 出第一版板 → 刷索引 → 装机 → 回执），每步都有读数。
4. **回执给用户**：板在哪（人读面路径）、怎么刷（`refresh_<板名>.bat <仓根>`）、怎么索引（板库根的 `index.html`）、哪个源降级了。

## 输入与输出

| 方向 | 内容 | 形态 |
|---|---|---|
| 读 | 目标仓根 | 目录（探测：`.git` / `.ai` / `handoff` 任一即算仓） |
| 读 | 板配置 | JSON（schema `flight-info-board/1`） |
| 写 | 板目录 | `<仓根>/.design/航班信息/HTML/<板名>/`：配置留档 + 自包含脚本 + 刷新 bat + 人读面 + 机读摘要 + 全量层 + 历史 |
| 写 | 板库索引 | `<仓根>/.design/航班信息/HTML/index.html` |
| 写 | 目标仓 `.gitignore` | 两条规则（幂等，只追加不改已有行） |
| 写 | 中央库 | **仅 `--install`**：正本 → 库 → 各家宿主链接（走 `magpie-sync.py`） |

## 权限与禁区

**可以**

- 写目标仓的 `.design/航班信息/`（板目录与索引）。
- 补目标仓 `.gitignore` 的那两条规则（全量层与时刻快照不入库），以及为此写的注释。
- 读目标仓的 `.ai/tasks`、`handoff`、`.design`（只读）。

**不可以**

- 改目标仓的源码、票面、Issue、日表、日报 —— 那些归项目仓与各角色。
- 动别的仓已有的板：同名板存在时不覆盖（要 `--force` 才覆盖，且先跟人确认）。
- 动中央库 / 各家宿主目录 —— 只有显式 `--install` 才动，且只装框架仓注册表里 `install:auto` 的条目。
- 改板工坊的脚本与判据 —— 本技能只 import 复用，不改。
- 在本仓写死任何项目名、项目路径、票号。

## 失败与降级

| 情况 | 退出码 | 判据 |
|---|---|---|
| 参数错（缺 `--repo-root`、仓根不存在） | 2 | 参数错 |
| 配置校验不过（板名非法、源类型不认识、schema 不对） | 2 | 打印错在哪（哪个字段/哪个源类型） |
| 同名板已存在且没 `--force` | 2 | 提示加 `--force` |
| 写盘失败 / 出板失败 | 3 | 如实报哪一步炸了 |
| **数据源降级** | **0** | **不是失败**：退出码恒 0，降级事实看回执里的 `sources`（`absent`＝目录不在、`skipped`＝没取、`fail`＝取失败） |

- 板**恒生成**（含降级）：一个源塌了不拖垮整页，回执点名哪个源降级。
- `sources` 全空 ⇒ 起一块空板，回执点名"没配源"。
- 退出码 0 只表示"板装好了"，**不代表数据全好**；数据好坏读 `sources`。

## 验证命令

```bash
# 装配面自己的回归
python -m pytest skills/set-航班信息/scripts/tests/ -q

# 装一块板（自证：装完能用）
python skills/set-航班信息/scripts/setup_board.py --repo-root <项目仓根>

# 板工坊的回归（装配面不改它，但复用它，必须仍全绿）
python -m pytest skills/航班信息/scripts/tests/ -q

# 框架仓校验（注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试）
python 框架仓门禁 --with-tests
```

## 正本

- 板工坊正本：[`skills/航班信息/SKILL.md`](../航班信息/SKILL.md) —— 造板/刷新/归档/索引。
- 装配脚本：[`skills/set-航班信息/scripts/setup_board.py`](scripts/setup_board.py) —— 九步装配；校验与建板 **import 复用**板工坊的 `new_board.py`（`build_index.py` 同理）。
- 最小配置：[`skills/set-航班信息/templates/board.config.minimal.json`](templates/board.config.minimal.json) —— 通用件；`_note` 那个键板会忽略。
- 完整配置样例：[`skills/航班信息/templates/board.config.example.json`](../航班信息/templates/board.config.example.json)。
- 装机正本：[`skills/set-kai-mode/SKILL.md`](../set-kai-mode/SKILL.md) ＋ `magpie-sync.py` —— 框架件怎么进中央库。
- 单票闭环协议：[`loops/loop-protocol.md`](../../loops/loop-protocol.md)。
