# -*- coding: utf-8 -*-
<#
.SYNOPSIS
  把 agent 的非项目数据根统一到一个目录（Windows 用户级）。

.DESCRIPTION
  只改用户级环境变量与数据目录，不碰项目仓、不改系统级 PATH。
  默认 dry-run；加 -Apply 才落盘。迁移是复制，不移动、不删除旧数据。

.PARAMETER Root
  全局数据根，例如 D:\kaikaikid\workspaces\agent-data。

.PARAMETER Apply
  创建目录、写用户环境变量、备份旧环境值。

.PARAMETER Migrate
  复制现有 Claude/Codex/OpenCode 的配置与认证到新根；大历史（会话/DB）不搬。

.PARAMETER OpenCodeLauncher
  写 OpenCode 启动包装（仅该进程用新 XDG 目录），并把 <Root>\bin 放到用户 PATH 前面。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [switch]$Apply,
    [switch]$Migrate,
    [switch]$OpenCodeLauncher
)

$ErrorActionPreference = "Stop"

function Say([string]$m) { Write-Host "[agent-data] $m" }
function Warn([string]$m) { Write-Warning "[agent-data] $m" }

function Write-Utf8NoBom([string]$path, [string]$text) {
    $dir = Split-Path -Parent $path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

function To-Posix([string]$p) {
    return ($p -replace '\\', '/' -replace '^([A-Za-z]):', '/$1').ToLower()
}

function Copy-Tree([string]$src, [string]$dst, [string[]]$exclude = @()) {
    if (-not (Test-Path $src)) { return }
    if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }
    $robo = @($src, $dst, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS')
    if ($exclude.Count -gt 0) { $robo += '/XD'; $robo += $exclude }
    & robocopy @robo | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失败：$src -> $dst（rc=$LASTEXITCODE）" }
}

$Root = [IO.Path]::GetFullPath($Root)
$envPlan = [ordered]@{
    KAI_AGENT_DATA_ROOT = $Root
    CLAUDE_CONFIG_DIR    = Join-Path $Root "claude"
    CODEX_HOME           = Join-Path $Root "codex"
}
$dirs = @(
    $Root,
    (Join-Path $Root "claude"),
    (Join-Path $Root "codex"),
    (Join-Path $Root "opencode\xdg\config"),
    (Join-Path $Root "opencode\xdg\data"),
    (Join-Path $Root "opencode\xdg\cache"),
    (Join-Path $Root "opencode\xdg\state"),
    (Join-Path $Root "opencode\tmp"),
    (Join-Path $Root "bin")
)

Say "数据根：$Root"
Say "将设置的用户环境变量："
foreach ($k in $envPlan.Keys) { Say "  $k=$($envPlan[$k])" }
Say "OpenCode：由 $Root\bin 的启动包装仅为它设置 XDG_CONFIG_HOME／XDG_DATA_HOME／XDG_CACHE_HOME／XDG_STATE_HOME 与 TMP/TEMP（不改全局 XDG）。"
Say "Qoder：配置目录由应用自管（QODER_CONFIG_DIR 为进程级），本脚本不覆盖。"

if (-not $Apply) {
    Say "dry-run：未创建目录、未改环境变量。确认后加 -Apply（可再加 -Migrate -OpenCodeLauncher）。"
    return
}

foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
Say "目录已就绪。"

$backup = Join-Path $Root "env-backup.json"
if (-not (Test-Path $backup)) {
    $old = [ordered]@{}
    foreach ($k in $envPlan.Keys) { $old[$k] = [Environment]::GetEnvironmentVariable($k, "User") }
    $old["Path"] = [Environment]::GetEnvironmentVariable("Path", "User")
    Write-Utf8NoBom $backup ($old | ConvertTo-Json -Depth 3)
    Say "旧环境值已备份：$backup"
}

foreach ($k in $envPlan.Keys) {
    [Environment]::SetEnvironmentVariable($k, $envPlan[$k], "User")
    Set-Item -Path "Env:$k" -Value $envPlan[$k]
}
Say "用户环境变量已写入。"

if ($Migrate) {
    $homeDir = [Environment]::GetFolderPath("UserProfile")

    $claudeSrc = Join-Path $homeDir ".claude"
    $claudeDst = Join-Path $Root "claude"
    if ((Test-Path $claudeSrc) -and -not (Test-Path (Join-Path $claudeDst "settings.json"))) {
        # skills/ 里是 Magpie 的符号链接；robocopy 无建链权限，排除后用 junction 指回。
        Copy-Tree $claudeSrc $claudeDst @((Join-Path $claudeSrc "skills"), (Join-Path $claudeSrc "debug"))
        Say "Claude 配置已复制（settings/会话/技能索引）。"
    } elseif (Test-Path (Join-Path $claudeDst "settings.json")) {
        Warn "目标已有 Claude 配置，跳过复制（不覆盖）。"
    }
    $claudeSkillsSrc = Join-Path $claudeSrc "skills"
    $claudeSkillsDst = Join-Path $claudeDst "skills"
    if ((Test-Path $claudeSkillsSrc) -and -not (Test-Path $claudeSkillsDst)) {
        New-Item -ItemType Junction -Path $claudeSkillsDst -Target $claudeSkillsSrc | Out-Null
        Say "Claude skills 已用 junction 指回原技能库。"
    }
    $claudeJson = Join-Path $homeDir ".claude.json"
    $claudeJsonDst = Join-Path $claudeDst ".claude.json"
    if ((Test-Path $claudeJson) -and -not (Test-Path $claudeJsonDst)) {
        Copy-Item $claudeJson $claudeJsonDst
        Say "Claude .claude.json 已复制。"
    }

    $codexSrc = Join-Path $homeDir ".codex"
    $codexDst = Join-Path $Root "codex"
    foreach ($f in @("config.toml", "auth.json", "AGENTS.md", "RTK.md", "magpie-models.json", "hooks.json")) {
        $s = Join-Path $codexSrc $f
        $d = Join-Path $codexDst $f
        if ((Test-Path $s) -and -not (Test-Path $d)) { Copy-Item $s $d }
    }
    foreach ($sub in @("agents", "skills")) {
        $s = Join-Path $codexSrc $sub
        $d = Join-Path $codexDst $sub
        if ((Test-Path $s) -and -not (Test-Path $d)) { Copy-Tree $s $d }
    }
    Say "Codex 配置/认证/小目录已复制；会话与日志留在旧 CODEX_HOME。"

    if ($env:XDG_CONFIG_HOME) {
        $ocCfg = Join-Path $env:XDG_CONFIG_HOME "opencode"
        $ocCfgDst = Join-Path $Root "opencode\xdg\config\opencode"
        if ((Test-Path $ocCfg) -and -not (Test-Path (Join-Path $ocCfgDst "opencode.json"))) {
            $ocExcl = @((Join-Path $ocCfg "skills"), (Join-Path $ocCfg "node_modules"))
            Copy-Tree $ocCfg $ocCfgDst $ocExcl
            Say "OpenCode 配置已复制（含插件配置）。"
        }
        foreach ($sub in @("skills", "node_modules")) {
            $s = Join-Path $ocCfg $sub
            $d = Join-Path $ocCfgDst $sub
            if ((Test-Path $s) -and -not (Test-Path $d)) {
                New-Item -ItemType Junction -Path $d -Target $s | Out-Null
                Say "OpenCode $sub 已用 junction 指回原目录。"
            }
        }
    }
    if ($env:XDG_DATA_HOME) {
        $ocData = Join-Path $env:XDG_DATA_HOME "opencode"
        $ocDataDst = Join-Path $Root "opencode\xdg\data\opencode"
        $authSrc = Join-Path $ocData "auth.json"
        $authDst = Join-Path $ocDataDst "auth.json"
        if ((Test-Path $authSrc) -and -not (Test-Path $authDst)) {
            New-Item -ItemType Directory -Force -Path $ocDataDst | Out-Null
            Copy-Item $authSrc $authDst
            Say "OpenCode 认证已复制。"
        }
        Say "OpenCode 大会话库未搬（可能在运行中）：新会话从新目录开始，旧库保留在原处。"
    }
}

if ($OpenCodeLauncher) {
    $binDir = Join-Path $Root "bin"
    $real = $null
    foreach ($name in @("opencode.exe", "opencode.cmd")) {
        $c = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($c -and -not $c.Source.StartsWith($binDir, [StringComparison]::OrdinalIgnoreCase)) {
            $real = $c.Source
            break
        }
    }
    if (-not $real) {
        Warn "找不到 opencode 真实入口，跳过启动包装。"
    } else {
        $realExe = $real
        if ($real -match '\.cmd$') {
            $cand = Join-Path (Split-Path $real) "node_modules\@opencode\cli\bin\opencode.exe"
            if (Test-Path $cand) { $realExe = $cand }
        }
        $cfg = Join-Path $Root "opencode\xdg\config"
        $data = Join-Path $Root "opencode\xdg\data"
        $cmd = @"
@echo off
setlocal
set "XDG_CONFIG_HOME=$cfg"
set "XDG_DATA_HOME=$data"
set "XDG_CACHE_HOME=$Root\opencode\xdg\cache"
set "XDG_STATE_HOME=$Root\opencode\xdg\state"
set "TMP=$Root\opencode\tmp"
set "TEMP=$Root\opencode\tmp"
"$realExe" %*
"@
        Write-Utf8NoBom (Join-Path $binDir "opencode.cmd") $cmd
        $sh = @"
#!/bin/sh
export XDG_CONFIG_HOME="$(To-Posix $cfg)"
export XDG_DATA_HOME="$(To-Posix $data)"
export XDG_CACHE_HOME="$(To-Posix (Join-Path $Root "opencode\xdg\cache"))"
export XDG_STATE_HOME="$(To-Posix (Join-Path $Root "opencode\xdg\state"))"
export TMP="$(To-Posix (Join-Path $Root "opencode\tmp"))"
export TEMP="$(To-Posix (Join-Path $Root "opencode\tmp"))"
exec "$(To-Posix $realExe)" "`$@"
"@
        Write-Utf8NoBom (Join-Path $binDir "opencode") $sh
        Say "OpenCode 启动包装已写入：$binDir\opencode.cmd"

        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $parts = @()
        if ($userPath) { $parts = $userPath.Split(';') | Where-Object { $_ } }
        if (-not ($parts | Where-Object { $_.TrimEnd('\') -ieq $binDir.TrimEnd('\') })) {
            $newPath = (@($binDir) + $parts) -join ';'
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Say "用户 PATH 已前置：$binDir"
        } else {
            Say "用户 PATH 已包含：$binDir"
        }
        $env:Path = $binDir + ';' + $env:Path
    }
}

$readme = @'
# Agent 全局数据根

由 kai-mode `scripts/setup-agent-data.ps1` 生成。规范见框架仓 `docs/agent-data-layout.md`。

| Agent | 全局数据 | 变量 |
|---|---|---|
| Claude Code | `claude\` | `CLAUDE_CONFIG_DIR` |
| Codex | `codex\` | `CODEX_HOME` |
| OpenCode | `opencode\xdg\` | 启动包装设置 XDG 与 TMP/TEMP |

项目数据仍由各项目仓自行管理；本目录不放项目代码。
'@
if (-not (Test-Path (Join-Path $Root "README.md"))) {
    Write-Utf8NoBom (Join-Path $Root "README.md") $readme
}

Say "完成。重开终端后生效；验证：claude --version、codex --version、opencode --version。"
