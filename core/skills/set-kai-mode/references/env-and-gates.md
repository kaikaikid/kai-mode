# 第 4 步环境自检 ＋ 第 6 步开票守卫

## 4. worktree 环境自检（三项，缺一报错不静默）

工作树里**没有**主树运行时与依赖目录（检查目录由配置实例 `runtime` 段声明，均不入库）。

| 项 | 标准 | 缺了怎么办 |
|---|---|---|
| 后端解释器 | 主树正本解释器的**绝对路径**（`runtime.backend_python`；装机写入 env `KAI_BACKEND_PYTHON`） | 报「缺解释器」并给绝对路径；不许退化成随便一个 `python` |
| node | 主树正本 node 的绝对路径（`runtime.node`） | 报「缺 node」并点名路径 |
| 依赖 | 树内用**项目自己的包管理器**离线装后才有前端定向测例环境 | 报「缺依赖」并点名判定结果；绝不 junction／软链主树 `node_modules` |

```bash
test -x "$KAI_BACKEND_PYTHON" && "$KAI_BACKEND_PYTHON" -V
node_bin="<主树>/<runtime.node 主树相对路径>"; test -x "$node_bin" && "$node_bin" -v
test -d <前端目录>/node_modules || echo "缺依赖：树内用项目自己的包管理器离线装"
```

- 全量前端腿不在工作树跑：由门卫／康娜在主树合并后跑。
- 工作树里的环境假红先回主树复核再定性，别开产品票。

## 5. doctor

```bash
python scripts/ready.py                  # 快检三合一（脚本在项目仓）
python scripts/env-doctor.py --hooks     # 钩子与正本同源
python scripts/framework-gate.py --selftest
```

读数**只能出自门**；红就报红，不静默吞错。长期红的门只走基线文件，不在本技能里改判据。

## 6. 开票归属守卫（缺 `--repo` 即拒）

> 治的病：在项目仓里跑 `gh` 会按 cwd 落仓，随手 `gh issue create` 就把框架问题开到项目仓。
> 判据住脚本、不住正文：`scripts/issue-guard.py`；**本技能是唯一安装口**。

1. **先探**：读宿主 `settings.json` 的 `hooks.PreToolUse`，找 `issue-guard.py`。已挂 → 只跑 `--self-test`。
2. **再装**（用户点头才写；写前备份 `settings.json`）：钩子形状见宿主适配说明，本文件不复述宿主字段。
   宿主没有钩子口 ⇒ 三格登记 `no-hook-surface`，不许谎报已拦截。
3. **验收**：项目仓里 `gh issue create --title probe` → 被拒且提示实例 `issue.repo`；
   加 `--repo <实例里的仓>` → 放行。
4. **不碰**：不自动改用户其它 hook，不替项目仓写 `.githooks/`，只拦开票／开 PR 两类。
