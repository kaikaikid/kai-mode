#!/usr/bin/env python
"""把 V2 面板补丁注入已安装的 savvy-progress 插件。

原版只认 Claude Code 的 in-process subagent；V2 的子会话是物理进程，
原版面板看不到。本脚本给 register.tsx 加一个轮询，读
`.coding/runs/*/state.json` 把运行中的任务画成面板行。

用法：
    python v2/mods/apply.py            # 应用补丁（幂等）
    python v2/mods/apply.py --revert   # 还原原文件

插件升级会覆盖 register.tsx，升级后重跑一次。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = "[coding-v2]"
BACKUP_SUFFIX = ".tsx.orig"

LANG_ANCHOR = "// Module scope is fine here: session.start sets it again on every (re)load.\nlet lang: Lang = 'en'"
LANG_ADD = LANG_ANCHOR + """

// [coding-v2] Project root captured from session.start; used by the V2 poller.
let codingCwd = ''
const CODING_ID = 'coding:'"""

POLL = r'''
// [coding-v2] Reads .coding/runs/*/state.json and mirrors running tasks into the panel,
// so V2's physical sub-sessions show up even though they are not Claude Code subagents.
async function pollCoding($: EngineInterface): Promise<void> {
  if (!codingCwd) return
  const base = `${codingCwd}/.coding/runs`
  try {
    if (!(await $.fs.exists(base))) return
  } catch {
    return
  }
  let dirs: { name: string; kind: string }[] = []
  try {
    dirs = (await $.fs.list(base)) as { name: string; kind: string }[]
  } catch {
    return
  }
  const rows: AgentRun[] = []
  let next: Flow | null = null
  for (const d of dirs) {
    if (d.kind !== 'dir') continue
    const p = `${base}/${d.name}/state.json`
    try {
      if (!(await $.fs.exists(p))) continue
      const s = JSON.parse(await $.fs.read(p)) as Record<string, unknown>
      const phase = String(s.phase ?? '')
      if (phase === 'done' || phase === 'cancelled' || phase === 'failed') continue
      const tasks = Array.isArray(s.tasks) ? (s.tasks as Record<string, unknown>[]) : []
      const accepted = tasks.filter(t => t.status === 'accepted' || t.status === 'abandoned').length
      const running = tasks.filter(t => t.status === 'running').length
      if (!next || tasks.length > next.total) {
        const mapped: Phase =
          phase === 'planning' ? 'plan'
          : phase === 'design' ? 'design'
          : phase === 'reviewing' ? 'review'
          : phase === 'closing' ? 'close'
          : 'delegate'
        next = {
          title: String(s.issue ?? s.run_id ?? d.name),
          total: tasks.length,
          done: accepted,
          running,
          phase: mapped,
          isFinished: false,
          tasks: tasks.map(t => ({ title: String(t.title ?? t.id), tier: String(t.tier ?? 'medium'), after: [] })),
        }
      }
      for (const t of tasks) {
        if (t.status !== 'running' && t.status !== 'review') continue
        rows.push({
          id: `${CODING_ID}${String(s.run_id ?? d.name)}:${String(t.id)}`,
          type: 'coding',
          description: `${String(s.run_id ?? d.name)} · ${String(t.title ?? t.id)}`,
          model: String(t.tier ?? 'medium'),
          status: 'running',
          startedAt: 0,
          contextTokens: 0,
          contextMax: 0,
          tokens: 0,
          costUsd: 0,
          steps: 0,
          round: 1,
          stepDone: t.status === 'review' ? 1 : 0,
          stepTotal: 1,
          stepNote: String(t.status),
        })
      }
    } catch {
      continue
    }
  }
  await update($, agents, list => [...list.filter(a => !a.id.startsWith(CODING_ID)), ...rows].slice(-200))
  if (next) await update($, flow, prev => (prev && prev.isFinished ? prev : next))
}

'''

REGISTER_ANCHOR = "export const register: Register = (on, options) => {"

SESSION_ANCHOR = "  on('session.start', async ($, e, next) => {\n    const started = await next(e)"
SESSION_ADD = SESSION_ANCHOR + r"""
    codingCwd = String((e as unknown as { cwd?: string }).cwd ?? '').replace(/[\\/]$/, '') // [coding-v2]"""

TICKER_ANCHOR = "    // Ticks the running agents' clocks; quiet when nothing runs."
TICKER_ADD = """    // [coding-v2] Mirrors V2 runs from .coding/ into the panel.
    $.clock.every(2000, () => {
      void pollCoding($)
    })

""" + TICKER_ANCHOR


def claude_cmd() -> list[str]:
    if os.name == "nt":
        for name in ("claude.cmd", "claude.exe"):
            p = shutil.which(name)
            if p:
                return [p]
    return [shutil.which("claude") or "claude"]


def installed_register() -> Path:
    out = subprocess.run(claude_cmd() + ["plugin", "list", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("claude plugin list failed: " + out.stderr.strip())
    for p in json.loads(out.stdout):
        if p.get("id") == "savvy-progress@claude-kit":
            return Path(p["installPath"]) / "hooks" / "register.tsx"
    raise SystemExit("savvy-progress@claude-kit is not installed")


def patch(text: str) -> str:
    for anchor in (LANG_ANCHOR, REGISTER_ANCHOR, SESSION_ANCHOR, TICKER_ANCHOR):
        if anchor not in text:
            raise SystemExit(f"anchor missing, mod version changed: {anchor[:60]}...")
    text = text.replace(LANG_ANCHOR, LANG_ADD, 1)
    text = text.replace(REGISTER_ANCHOR, POLL + REGISTER_ANCHOR, 1)
    text = text.replace(SESSION_ANCHOR, SESSION_ADD, 1)
    text = text.replace(TICKER_ANCHOR, TICKER_ADD, 1)
    return text


def main() -> None:
    target = installed_register()
    if not target.exists():
        raise SystemExit(f"register.tsx not found: {target}")
    backup = target.with_suffix(BACKUP_SUFFIX)

    if "--revert" in sys.argv:
        if not backup.exists():
            raise SystemExit("no backup to revert")
        shutil.copy2(backup, target)
        print(f"reverted {target}")
        return

    text = target.read_text(encoding="utf-8")
    if MARKER in text:
        print("already patched")
        return
    if not backup.exists():
        shutil.copy2(target, backup)
    target.write_text(patch(text), encoding="utf-8", newline="\n")
    print(f"patched {target} (backup: {backup.name})")
    print("restart Claude Code to load the patched mod")


if __name__ == "__main__":
    main()
