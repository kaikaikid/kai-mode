# CHANGELOG

本仓变更记录；按版本倒序，每条一行。版本号正本＝仓根 [`VERSION`](VERSION)。

## 0.3.0 — 2026-10-22

- 技能注册表 `registry.json` 落地：技能清单单一事实源，装机清单从它派生（`install:auto`）
- 仓级校验入口 `scripts/doctor.py`：注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试，一条命令验全仓
- 技能目录契约 `docs/skill-layout.md` ＋ 骨架模板 `templates/skill/SKILL.md`
- 行尾口径 `.gitattributes`：`.bat`＝crlf（防 cmd 崩）
- 航班信息技能升级为板工坊：板配置 ＋ 模板 ＋ 脚手架 ＋ 板库归档
- `magpie-sync.py` 装机布局档：本仓自身可作正本根
