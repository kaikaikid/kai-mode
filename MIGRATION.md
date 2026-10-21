# 迁移状态（2026-10-21）

## 已在本仓库

- 五个角色技能：`skills/tower`、`ground`、`coordinator`、`group-a`、`group-b`
- 共享剧本：`playbooks/shifts/{README,tower,ground,coordinator,group}.md`、`playbooks/acceptance.md`
- 契约：`schemas/{handoff,status,acceptance,queue}.schema.json`
- 适配器：`adapters/{qoder,opencode,codex}.md`
- 项目配置模板：`templates/kai-mode.project.json`

## 仍在项目仓（**直播源，未切换**）

- `kai-mode`／`set-kai-mode`／`loop` 三个技能的正本仍在项目 `.ai/skills/`
- 班次剧本仍在项目 `.ai/scope/shifts/`
- runtime 脚本（`scripts/plan.py`、`scope-check.py`、`on-duty-check.py` 等）仍在项目仓
- ADR-0135 在项目仓；本仓库只引用，不复制

## 切换顺序（ADR-0135 D8）

1. 等 #1829 落地，直播面空闲。
2. 把 `kai-mode`／`set-kai-mode`／`loop` 拷入本仓库；把 `magpie-sync` 的 root 指向本仓库。
3. 项目 `.ai/kai-mode.project.json` 落地；项目剧本按本仓库参考剧本改写（保留项目命令与路径）。
4. 建 Coordinator/Tower/Ground/Group-A/B 任务；各跑一次自证；确认后再停旧任务。
5. 24h 试点后按指标调 `W` 与批次。

## 纪律

- **切换前，项目仓副本是唯一直播源**；本仓库同名文件只是 staging，禁止同时改两份。
- 不在本仓库写项目专用路径、票号、job id；它们属于项目配置与项目剧本。
- 切换时先建新任务并自证，再停旧任务；旧 job id 至少保留一个试点周期。
