# vendor/ —— 辅助技能（原样拉取，不是本仓的裁决）

> 工作流要用的**通用方法技能**，从源仓库原样复制过来直接读用。
> **一个字都没改**：不改名、不加前缀、不登记 registry、不进 `skills/`、不受本仓 frontmatter 与行数门禁约束。

## 为什么单独放

`skills/` 装的是**本仓自己设计的东西**（`kind: framework`，要评审、要门禁、要进中央库）。
通用方法不是我们设计的，fork 出来只会造出第二份同义判据、还挡住上游更新——所以：

| | `skills/`（本仓设计） | `vendor/skills/`（外部方法） |
|---|---|---|
| 来源 | 我们写 | 上游仓库原文 |
| 命名 | kebab-case，必要时 `kai-` 前缀 | **沿用上游名**，不改 |
| 登记 | 必须进 `registry.json` | **不登记** |
| 门禁 | doctor 全套（八字段、<500 行、链接） | 只校「与源一致」 |
| 升级 | 改我们那份、升 version | 重新拉取，不改内容 |

## 清单

| 技能 | 用在工作流的哪一步 |
|---|---|
| `tdd` | 施工：先红后绿 |
| `code-review` | 审查：Spec／Standards 双轴出判词 |
| `diagnosing-bugs` | 连续失败／原因不明 |
| `domain-modeling` | 定稿第 2 步：术语与 ADR |
| `to-tickets` | 定稿第 3 步：拆票草案 |
| `writing-for-agents` | 写 SKILL／AGENTS 文档 |

流程（什么时候调、产出交给谁）住本仓：`loops/loop-protocol.md`、`skills/kai-mode/SKILL.md`、
`skills/ground-crew/SKILL.md`、`docs/skill-layout.md`。**方法与流程各一个家。**

## 命令

```bash
python scripts/vendor-sync.py            # 拉取/刷新（会覆盖 vendor/skills/）
python scripts/vendor-sync.py --check    # 只校验：源变了没、vendor 被改过没
```

- 源：本机 `~/.workbuddy/skills/`（上游 mattpocock/skills 的本地镜像）
- 清单：`vendor/manifest.json`（每个文件的 sha256，每次 sync 重写）
- **不要手改 `vendor/` 里的任何文件**：`--check` 会报不一致，下次 sync 直接覆盖。要改行为，改调用它的流程位，或者去上游提。
