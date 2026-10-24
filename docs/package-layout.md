# 三层打包边界：本仓开发件 / 宿主安装件 / 项目生成件

一句话：**本仓的开发记录不随技能装走，也不随初始化进用户项目；两边各自只拿清单里写明的东西。**

机读正本：[`manifests/package-layout.json`](../manifests/package-layout.json)。裁决：[ADR-0011](adr/0011-package-layout-three-layers.md)。

## 三层各是什么

| 层 | 内容 | 去哪 | 谁写 |
|---|---|---|---|
| 本仓开发件 | `docs/`（ADR、agent 文档、canon）、`handoff/` 历史、`scripts/`、`agents/`、`adapters/`、`loops/`、`schemas/`、`vendor/`、`CHANGELOG`／`VERSION`／`AGENTS.md`、技能自带 `tests/` | 只留本仓 | 维护者 |
| 宿主安装件 | `registry.json` 里 `install:auto` 的技能目录（`SKILL.md` ＋ 运行所需 `scripts/`、`templates/`、`schema/`；看板脚本随 `kai-handoff` 安装） | Magpie 中央库 → 各宿主 `<家>/skills/<名>` | `magpie-sync.py` |
| 项目生成件 | `.ai/kai-mode.project.json`、`handoff/` 八槽与规范／模板、`GLOSSARY.md`、空 `docs/adr/` | 用户项目 | `init-project.py` |

## 三条硬规矩

1. **开发件不进安装面。** 技能目录里的 `tests/`、`__pycache__`、`.pytest_cache`、`*.pyc` 不复制、不参与回执哈希；`apply` 会把库里已有的这类残留清掉（写前整包备份）。
2. **骨架只从清单生成。** `project_scaffold` 之外不写；源只许 `templates/` 或 `handoff.files` 列出的四件规范／模板。`handoff/` 里的日期目录、评审件、归档都是本仓记录，任何一件都不能当源。
3. **`docs/` 永不复制。** 用户项目的 `docs/adr/` 是空目录加 `.gitkeep`，ADR 由用户自己从 0001 开始写。

## 用户实际会得到什么

- 宿主技能库里：运行所需技能，没有本仓测试与缓存。
- 用户项目里：配置实例、交接骨架（含两份模板）、`GLOSSARY.md` 骨架、空 `docs/adr/`。
- 不会得到：本仓的 ADR、交接／评审历史、看板卡片、开发脚本、测试。

## 关于技能里的 `../../` 链接

技能正文里的 `../../docs/...`、`../../loops/...` 是**本仓出处指针**（"为什么这么定"），不是运行依赖。安装到宿主后这些相对路径不再成立，操作正文本身仍自足；不要为了"让链接能点"去复制本仓文档。

## 加一件新骨架件

1. 模板放 `templates/`（或 `handoff/` 的规范／模板面）。
2. 在 `manifests/package-layout.json` 的 `project_scaffold` 加一行。
3. 跑 `python scripts/doctor.py --with-tests`：`package-layout` 会实跑 `init-project.py` 对账，测试里也有反向用例。

## 校验

```bash
python scripts/doctor.py --with-tests   # 24 项；package-layout 报安装面条数与骨架件数
```

`package-layout` 红通常只有三种：安装面混进被排除文件、骨架源越界／缺失、实跑生成集合与清单不一致。
