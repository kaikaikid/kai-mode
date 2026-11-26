# 0040 本地优先发布门禁

## Status

**proposed —— 2026-11-26。**

## Context

kai-mode 现有 `gold` → `fleet` 流程覆盖「需求 → 票 → run → 施工 → 代码审查 → 合并推送」，但合并之后到本机运行之间断开：部署、健康检查、回滚、本地服务形态都不在门禁里。原《自动化部署工程规范》偏向 GitHub Actions + Netlify/Neon，和本机已有的本地优先环境不匹配。

本机当前事实：Python 3.12、Node 25、pnpm、uv、Ollama、PostgreSQL 5432、Redis 6379、Hindsight 8888、magpie 3425 都在跑；有 `pre_commit`、`pip-audit`、`safety`、`bandit`、`gh`；没有 Docker、gitleaks、semgrep、act、Caddy/Nginx。Kai-vass 和 astryx 已有 `.github/workflows`，kai-mode 有 `scripts/doctor.py`。

## Decision

### D1 默认本地，不引入云服务

发布门禁默认只做三类事：跑本地验证命令、检查本机工具/端口、写回执。不调用云部署平台、不调用 LLM、不自动升级、不自动扣费。对外真发布、花钱、不可逆操作仍按红线先问。

### D2 两个落点，不改原有三道门

不新设 G3，避免动 `fleet` 的状态机与 stash 中已有的跨宿主改动。发布门禁作为两个独立动作挂接：

1. **CI Gate**：在 `gate g2 approve` 之前，由康娜/主会话执行 `python scripts/local-release-gate.py --repo <项目> --target local`，结果红则不批准 G2。
2. **Deploy Gate**：在 push 之后，由人或受控脚本按项目 `.coding/local-deploy.json` 的 `start_cmd` / `rollback_cmd` 执行，并把门禁回执作为发布记录。

项目配置里记录 `verify_cmds`（本地可机检命令）、`required_tools`、`healthcheck.host/port/url`、`start_cmd`、`rollback_cmd`、`verify_timeout_seconds`。当前脚本不自动启动/回滚服务，只检查与记录；真启动/回滚由人按配置执行，符合"本地跑、推送例外"的约束。

### D3 复用，不重复建设

- 已有 CI workflows 的项目，把关键 workflow 的本地等价命令写进 `verify_cmds`。
- Python 项目建议：`python -m pytest`、`python -m bandit -q <src>`、`python -m pip_audit`、密钥扫描（gitleaks 未装时先手工/简单 grep，不假装已装）。
- kai-mode 自身：`python scripts/doctor.py --with-tests`。
- 配置项缺失或验证命令红，门禁直接 block；健康检查默认只记录，加 `--strict-health` 才判红，避免把"服务没起"误算成"代码不能合并"。

### D4 回执可追溯

每次运行落 `.coding/release-gate/<timestamp>.json`，记录配置路径、检查项、失败项、决定、启动/回滚命令。回执只写项目仓，不上传、不写共享数据库。

## Consequences

- kai-mode 的 G0/G1/G2 状态机保持不变。
- 新文件只落在 `scripts/` 与 `docs/adr/`，不进安装面，避免 `install-sync` 因技能副本漂移判红。
- 验证脚本是确定性工具，不消耗 LLM token；没有可用的确定性工具时如实登记缺口，不用 AI 审查冒充门禁。
- 数据库迁移、密钥轮换、公网部署仍需按项目单独审批，不由本 ADR 自动放行。
