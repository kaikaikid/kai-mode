# skill-sources/ — 外部素材库

> 用作**参考 / 原型**的外部技能，按本目录规范存放。
> 目的：**后续迭代时能学到上游的演进**——既不当正本，也不丢线索。

## 1. 存什么、不存什么

| 存 | 不存 |
|---|---|
| 指针（上游、本地副本、中央库副本） | 源件全文（不复制进本仓，避免第二份正本） |
| 结构化元数据（`sources.json`） | registry 条目（**源件不登记、不进中央库**） |
| 约定摘要（用于对账，非正本） | 源件的 v1/v2/v3 快照（有指针就够了） |
| 与本仓特化版的**差异表** | 源件的测试用例与资产 |

## 2. 一个素材 = 索引一行 + 摘要一份

- **索引**：`sources.json`，机器读，字段口径见 §3
- **摘要**：`docs/skill-sources/<源名>.md`，人/AI 读，含约定摘要 + 对账步骤
- **打包摘要**：**同批引入、同一上游、同一对账节奏**的素材可合一份（如 `workflow-skills.md`），
  每源一节；索引 `note` 写 `本文件#<锚点>`。别为一个源单开一份只写三行的小文件。

## 3. 索引字段（`sources.json`）

| 字段 | 说明 |
|---|---|
| `id` `name` `upstream` | 素材标识与出处 |
| `local_copy` `library_copy` | 本机用户级副本 / 中央库副本路径 |
| `specialized_as` | 本仓特化版路径（没有就写 `-`） |
| `note` | 摘要文件路径 |
| `sha256` `source_lines` | 源件指纹与规模，用于判断是否变了 |
| `first_seen` `last_diff` `next_diff_due` | 时间线（默认 30 天对一次） |
| `status` | `adopted`（已特化或 fork 后本仓拥有正文）/ `watching`（只观察）/ `dropped`（弃用） |
| `reason` | 非 `adopted` 必填：为什么不用（改判 `adopted` 后可删） |
| `deltas` | 本仓相对源件**改了什么**（差异表） |
| `inherited` | 从源件**继承了什么** |

## 4. 对账（脚本化）

```bash
python scripts/source-check.py          # 列出全部素材 + 是否有更新 + 是否到对账日
python scripts/source-check.py --json   # 机器读
```

逻辑：比对 `sha256` 与本地副本当前指纹 → 变了就提示「源件已更新，需对账」；
`next_diff_due` 过期也提示。对账完手改 `last_diff` / `next_diff_due` / `sha256`。

## 5. 加一个素材（三步）

1. 摘要文件写进本目录（`<源名>.md`）
2. `sources.json` 加一条（照抄字段，别漏 `sha256`）
3. 若已特化，在特化技能的 references 目录下放一份 `source.md`，**只放指针**，指回本目录（不复制摘要）

## 6. 命名避让与 fork 口径

- **自己设计**的件：三条全中（判据由本仓设计、有本仓接口、不 fork 就没有家）才特化入库并加 `kai-` 前缀。
- **通用方法**：ADR-0026 起允许 fork——进 `methods/skills/kai-*`，随插件安装，可微调，改动记 `deltas`，
  上游按 30 天对账人工吸纳。**必须加 `kai-` 前缀**：与用户自装的同名上游件不同名，宿主里不互相覆盖。
- 加前缀的代价是「第二份同义判据」，由 ADR-0026 显式豁免；不加前缀反而会撞上 `magpie-sync apply` 覆盖用户通用件的坏路。

**本节只管 `skills/`**：`agents/` 的子代理人格**不加 `kai-` 前缀**——它们不经中央库安装（`magpie-sync` 只装 `skills/`），
不存在同名覆盖问题，落点是项目级宿主目录（见 `adapters/README.md`）。

判定细则与逐源结论：`workflow-skills.md` §2。
