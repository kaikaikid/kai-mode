# 三层打包边界：本仓开发件 / 宿主安装件 / 项目生成件

一句话：**本仓的开发记录既不随技能装走，也不躺在仓库里给外部用户看；安装面与项目骨架各自只拿清单里写明的东西。**

机读正本：[`manifests/package-layout.json`](../manifests/package-layout.json)。裁决：[ADR-0011](adr/0011-package-layout-three-layers.md)。

## 三层各是什么

| 层 | 内容 | 去哪 | 谁写 |
|---|---|---|---|
| 本仓开发件 | `docs/`（ADR、agent 文档、canon）、`handoff/` 历史、`scripts/`、`agents/`、`adapters/`、`loops/`、`schemas/`、`vendor/`、`CHANGELOG`／`VERSION`／`AGENTS.md`、技能自带 `tests/` | 只留本仓 | 维护者 |
| 宿主安装件 | `registry.json` 里 `install:auto` 的技能目录（`SKILL.md` ＋ 运行所需 `scripts/`、`templates/`、`schema/`；看板脚本随 `kai-handoff` 安装） | Magpie 中央库 → 各宿主 `<家>/skills/<名>` | `magpie-sync.py` |
| 项目生成件 | `.ai/kai-mode.project.json`、`handoff/` 八槽与规范／模板、`GLOSSARY.md`、空 `docs/adr/` | 用户项目 | `init-project.py` |

## 硬规矩

1. **开发件不进安装面。** 技能目录里的 `tests/`、`__pycache__`、`.pytest_cache`、`*.pyc` 不复制、不参与回执哈希；`apply` 会把库里已有的这类残留清掉（写前整包备份）。
2. **骨架只从清单生成。** `project_scaffold` 之外不写；源只许 `templates/` 或 `handoff.files` 列出的四件规范／模板。`handoff/` 里的日期目录、评审件、归档都是本仓记录，任何一件都不能当源——也不入库。
3. **`docs/` 永不复制。** 用户项目的 `docs/adr/` 是空目录加 `.gitkeep`，ADR 由用户自己从 0001 开始写。
4. **安装面自足。** 技能 payload 里不得出现框架仓 URL、`ADR-NNNN` 编号、`docs/adr/NNNN-…` 文件名、装不走的 `../../` 链接，也不得把维护者门禁（`doctor.py`）写成用户验收步骤——判据与实测见 [ADR-0013](adr/0013-installed-payload-no-dev-history.md)，可执行口径住 [`docs/skill-layout.md`](skill-layout.md)。

## 用户实际会得到什么

- 宿主技能库里：运行所需技能（实测 37 件），没有本仓测试与缓存，也没有本仓的 ADR 编号与死链。
- 用户项目里：配置实例、交接骨架（含两份模板）、`GLOSSARY.md` 骨架、空 `docs/adr/`。
- 不会得到：本仓的 ADR、交接／评审历史、看板卡片、开发脚本、测试。

## GitHub 上的仓库可见面

外部用户 clone 到的应当只有**方法论 + 安装包**：技能与人格正本、协议、适配说明、ADR、规范与模板、
安装／初始化脚本。本仓开发期间的流水不进 git：

- `handoff/<槽>/YYYY-MM/`、`handoff/60-board/<状态>/*.md`：交接、评审、归档、看板工单 ⇒ 忽略。
- 会话库／日志／缓存／验证报告／agent 数据 ⇒ 忽略（口径见 [agent-data-layout.md §7](agent-data-layout.md)）。
- 槽位结构与四件规范／模板仍跟踪，它们是 `init-project.py` 的骨架源。

已入库的老流水按红线处理：`git rm --cached` 移出索引，盘上证据不删。

## 技能里的维护侧引用怎么写

安装面里要指维护侧正本，写成**名称＋路径**（例：框架仓 `loops/loop-protocol.md`），不给 URL、不给 ADR 编号，
并在使用处说明「不随技能安装」。技能内部与兄弟技能之间用相对链接（同在一个安装库里）。
`sources` frontmatter 只指随装件；框架侧出处一律从安装面删除，出处留在本仓 ADR 与 CHANGELOG。

## 加一件新骨架件

1. 模板放 `templates/`（或 `handoff/` 的规范／模板面）。
2. 在 `manifests/package-layout.json` 的 `project_scaffold` 加一行。
3. 跑 `python scripts/doctor.py --with-tests`：`package-layout` 会实跑 `init-project.py` 对账，测试里也有反向用例。

## 校验

```bash
python scripts/doctor.py --with-tests   # 27 项；package-layout 报安装面条数与骨架件数，config-instance 实跑初始化器，payload-budget 卡分层字节
```

`package-layout` 红通常只有三种：安装面混进被排除文件、骨架源越界／缺失、实跑生成集合与清单不一致。
`payload-refs` 红有三类：安装面出现框架仓 URL 或 `ADR-NNNN`／`docs/adr/NNNN-…` 引用；把维护者门禁 `doctor.py` 写成验收步骤；Markdown 相对链接指向装不走的本仓开发件。
`tracked-cache` 红有两种：被跟踪的缓存／运行数据产物；被跟踪的本仓 `handoff/` 流水（规范与模板除外）。
