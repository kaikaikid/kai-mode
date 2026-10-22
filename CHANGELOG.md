# CHANGELOG

本仓变更记录；按版本倒序，每条一行。版本号正本＝仓根 [`VERSION`](VERSION)。

## 0.3.0 — 2026-10-22

- 技能注册表 `registry.json` 落地：技能清单单一事实源，装机清单从它派生（`install:auto`）
- 仓级校验入口 `scripts/doctor.py`：注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试，一条命令验全仓
- 技能目录契约 `docs/skill-layout.md` ＋ 骨架模板 `templates/skill/SKILL.md`
- 行尾口径 `.gitattributes`：`.bat`＝crlf（防 cmd 崩）
- 航班信息技能升级为板工坊：板配置 ＋ 模板 ＋ 脚手架 ＋ 板库归档
- `magpie-sync.py` 装机布局档：本仓自身可作正本根
- **doctor 加装机同步检查**（第 13 项 `install-sync`）：中央库副本与本仓逐字对账（逐文件 SHA-256）＋ 库记住的装机来源是不是本仓（`.kai-mode-source.json`）；红了当场给 `apply` 修法 ⇒ 「本仓为准」从口头约定变成可发现
- **宿主装机切到本仓**：`apply --root <本仓>` 实装，8 个宿主（`.claude`／`.cline`／`.codex`／`.cursor`／`.dsh`／`.qoder-cn`／`.workbuddy`／`.workbuddy-ai`）装齐 8 个技能（新增 `航班信息`），`library.json` 追加 11 个平台条目；装机拷贝跳过 `__pycache__`／`*.pyc`
