# 第 2 步：装技能到宿主（细节）

> 仓库里的 SKILL.md 是**正本**；宿主真正加载的往往是另一份拷贝（如中央库
> `<...>/library/skills/<名>/`，各家宿主目录只是指向它的链接）。
> **改了正本不回写，只有当下这一家生效**。

## 命令

```bash
S=core/skills/set-kai-mode/scripts/magpie-sync.py
python $S --selftest                          # 先证这把尺会响
python $S check                               # 只读漂移表：内容面（逐文件 SHA-256）＋落点面＋注册面
python $S apply --dry-run --profile core      # 看将写哪些字节
python $S apply --profile core                # 正本 → 库 → 各家链接；写前自动备份
```

## 档位与回执

- **安装档位**：`manifests/install-profiles.json` 定两档——`core`（康娜 ＋ 内核 ＋ 安装/升级 ＋ 交接）、
  `full`（全部自动件）。`apply/check --profile core|full`。
- **安装回执**：库根 `.kai-mode-source.json` 记来源根、HEAD、档位、技能清单与每技能哈希。
  写库前整包备份到 `<库根>/.backups/`（保留 5 份），失败自动还原。
- **来源标签**：`apply` 给每条在 `library.json` 里写/补 `source{kind,repo,path}`（仓的 GitHub remote 与
  正本在仓内的目录）——Magpie 资源库页按它分「哪个仓／哪个文件夹」，缺了就落「本机」。
  仓没有 GitHub remote 就不贴（不猜出处），`check` 只报 warn 不判红。
- **手动件**（如 `harness-audit`）不进档位，`apply` 缺省不碰它们；但 `check` 的量程**含**它们
  （状态列写作「手动件·漂移」）——库里装着、各家在读，档位不收不等于可以盲着不看（#18 实测：
  正本改口径两天后库仍是旧版而门全绿）。要按绿：`apply --include-manual`。
- **落点面认两种形态**：链接指回本库，或本机库指针档（`~/.kai-mode-library`）指本库＋副本 SKILL.md
  带 zh 生成器标记（`build-skills-zh.py` 把宿主那份铺成实体档，只留内层子目录是链接）。
  实体副本逐文件比正文，SKILL.md 剥掉生成注释与 `name:` 行后须等值。一家消费端都没认出时判 warn
  并写明「未覆盖」，不许用一句「三面全绿」盖过去。
- **安装面与开发件分开**：只装技能运行件；`tests/`、`__pycache__`、`.pytest_cache`、`*.pyc` 不装。

## 加一个新技能

1. 放目录 `<插件>/skills/<名>/`（含 `SKILL.md`）；
2. 新剧本才在 `.claude-plugin/marketplace.json` 加插件；
3. 跑 `python scripts/plugin-check.py`。

## 库位

**不写死机器路径**：沿既有链接反查；读不出用 `KAI_MAGPIE_LIBRARY`，仍读不出就 rc=2 如实报，不猜路径。

## 三条硬规矩

1. 写库前**整包备份 ＋ SHA-256 基线**。
2. 脚本只新增、只覆盖同路径，绝不删库里多出来的东西
   （唯一例外＝安装面排除的开发件与缓存）。
3. 中央库进程在跑时可能用内存版覆盖回注册档 ⇒ `apply` 后隔 ≥90 s 再 `check`。

## 子代理模板（可选，用户点名才装）

> 模板正本：本技能 `agents/`——四自建（`implementer` / `reviewer` / `adjudicator` / `researcher`）
> ＋ 三内置覆盖（`Explore` / `Plan` / `general-purpose`）。只写模型、权限、轮次上限；判据不住这里。
> 宿主差异见 `adapters/claude.md`「内置子代理与同名覆盖」。

```bash
S=core/skills/set-kai-mode/scripts/install-agents.py
python $S --project <项目仓> --dry-run   # 默认项目级：<项目仓>/.claude/agents/
python $S --project <项目仓>
python $S --host-root --dry-run          # 宿主级：$CLAUDE_CONFIG_DIR/agents/，未设则 ~/.claude/agents/
python $S --host-root --force            # 同名不同内容：备份后覆盖
```

- **默认项目级**：`adapters/README.md` §8 规定落点必须项目级，避免和用户其它框架同名打架。
  `--host-root` 是显式例外，装机回执必须写「宿主级安装（例外）」。
- **同名覆盖只对项目级可靠**：宿主级同名项优先级低于项目级，也盖不掉内置（覆盖件要放项目目录）。
- **宿主级只看一个根**：设了 `CLAUDE_CONFIG_DIR` 后，`~/.claude/agents/` 不再被读取——
  装错根等于没装；先 `echo $CLAUDE_CONFIG_DIR` 再装。
- **验收**：脚本回执里 7 个文件在位；**新开会话**（旧会话不重载）代理列表出现自建名；
  起一个只读子代理让它写临时文件，必须被拒。
