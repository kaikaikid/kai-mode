# Connectors —— 看板

| 类别 | 占位符 | 本仓默认 | 缺件时 |
|---|---|---|---|
| 源代码管理 | `~~source control` | git 历史与工作树 | 该源降级点名，不整页崩 |
| 票与 Issue | `~~issue tracker` | `gh` CLI | 票源显示「不可用」，不猜 |
| 数据库 | `~~database` | SQLite（标准库） | 不缺；写盘失败才登记 |
| 文件系统 | `~~filesystem` | 板配置、`board.json`、`index.html` | 写不出就报错，不输出半页 |

## 纪律

- 每个源独立失败、独立点名；源健康写进 `board.json`。
- 不把外部服务当运行必需；字体与资源默认本地。
