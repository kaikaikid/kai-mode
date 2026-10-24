# 0011 三层打包边界：开发件 / 安装件 / 项目骨架

## Status

accepted —— 2026-10-24 用户令：「把本项目开发的文件跟项目要生成的框架结构[分开]，不然别的用户安装以后可能会把我们现在的开发记录塞进去杂糅一起」。

## Context

本仓一棵树同时承担三件事，此前只靠习惯分开：

- **开发件**：`docs/adr/`、`handoff/` 历史、`scripts/tests/`、`vendor/`、`CHANGELOG`／`VERSION` 等，是本仓自己的决策与施工记录。
- **宿主安装件**：`registry.json` 里 `install:auto` 的技能目录，被 `magpie-sync.py` 逐字复制到 Magpie 中央库，再链到各家宿主。
- **项目骨架**：`scripts/init-project.py` 写进用户项目的配置实例、`handoff/` 八槽与规范、`GLOSSARY.md`、空 `docs/adr/`。

实际漏点：

1. 技能目录里的 `tests/` 属于开发件，却会被整目录装进中央库（`flight-info` 实测被装）。
2. 项目骨架的复制源清单硬编码在 `init-project.py`，且其中四件住在 `handoff/`（开发记录目录）里；边界靠代码注释，改动时没有机械判据。
3. 生成的 `docs/adr/` 是空目录、无占位文件，git 不跟踪，用户项目里实际看不到这个结构。

## Decision

### D1 三层各有唯一清单

新增 `manifests/package-layout.json`（schema `kai-mode-package-layout/1`），用三个段声明边界：

- `repo_only`：本仓开发件，永不进宿主库、也不进项目骨架（描述性清单）。
- `host_payload`：安装面。名单**不另抄**，唯一来源仍是 `registry.json` 的 `install:auto`；本段只补排除项（`tests`／`__pycache__`／`.pytest_cache`／`*.pyc`／`*.pyo`）。
- `project_scaffold`：`init-project.py` 唯一可生成的面；逐件列 `from`／`to`。

### D2 宿主安装面剔除开发件

`magpie-sync.py` 的复制、漂移比对、回执哈希统一走 `payload_files()`；`apply` 在整包备份后，把库里技能目录下的开发件清掉。安装面不再出现技能自带测试与缓存。

### D3 项目骨架只从清单生成

`init-project.py` 读 `project_scaffold`，不再硬编码槽位与复制源：

- 源只许 `templates/` 或 `handoff.files` 列出的四件规范／模板；`docs/` 任何内容不得作源。
- 落点必须在目标仓内、留在声明的路径上。
- 空 `docs/adr/` 写 `.gitkeep`，结构能被 git 真正带进用户项目。

### D4 机械判据

doctor 新增 `package-layout` 项（第 24 项）：

- 静态：清单 schema、安装面排除项、安装面文件不得含被排除路径、骨架源存在且不越界、落点安全、槽位覆盖完整。
- 行为：在临时目录实跑 `init-project.py`，生成文件集合必须与清单**逐件相等**（多一件、少一件都红）。
- 已有库：`install-sync` 同时量「库内残留开发件」，避免只改代码、不改盘。

新增骨架件的流程固定为：加模板 → 加清单一行 → doctor 与回归测试同批过。

## Consequences

- 用户装到宿主的只有运行所需技能；本仓 ADR、交接历史、测试、脚本不会混进去。
- 用户项目得到的骨架是声明过的固定集合，不会因 `init-project.py` 的一次改动把开发记录带进去。
- 看板脚本随 `kai-handoff` 技能安装（框架仓 `scripts/handoff-board.py` 只留兼容入口）；骨架文档改为按技能目录引用，不再写死框架仓路径。
- 技能自带的 `../../docs/...` 是**本仓出处指针**，安装副本不随附；操作正文不依赖它们，断链不影响运行。
- 技能测试继续留在仓内供 `--with-tests` 使用，只是不进安装面。

## 验证

- `python scripts/doctor.py --with-tests`：24 项全绿（`package-layout` 报安装面条数与骨架件数）。
- `python -m pytest scripts/tests -q`：含「源仓有 tests 允许／安装面含 tests 才红」「交接历史作源即红」「骨架源缺失即红」。
- 手工：任取一个用户项目跑 `init-project.py`，文件集合与 `project_scaffold` 逐件一致；中央库对应技能目录下无 `tests/`。
