#!/usr/bin/env python3
# check-tiers.py - drift guard for the magpie subagent tier system.
#
# Note (kai-mode 针B 2026-10-23): kai-mode's own specialized contracts/ (roles.yaml,
# delegation-prompts.md, ...) were superseded by the host-neutral personas in the
# kai-mode repo-root agents/ directory. This script keeps reading magpie's own copy
# under <repo>/codex-agents/final/contracts/ because day-to-day subagent management
# is magpie's job; agents/ carries discipline (R/C/P/V/G/W vocab only), not model
# plumbing. kai-mode's retired copies live in _superseded/subagents-codex-contracts/.
#
# Question it answers: is every "role -> group/tier-X -> effort" triple both
# self-consistent across the config files AND actually servable by the models
# inside that tier pool?
#
# Why: a tier pool is a bag of member models. Codex sends (model=group/tier-X,
# effort=Y). magpie picks a member. If some members cannot serve Y the request
# degrades silently with no error anywhere. Measured 2026-10-23: 5 of the 6
# tiers declared levels their own members did not agree with (tier-c declared
# "max" only while every member serves low/high and 2/6 cannot serve max).
#
# Severity model:
#   FAIL  config disagrees with itself (a role asks for an effort the tier does
#         not declare; role->tier mapping drifted; parent default is not a tier;
#         the published catalog is stale vs providers.json)
#   WARN  a tier declares an effort that some of its members cannot serve
#         (pool hygiene: prune the members or lower the declaration - human call)
#
# Usage: python check-tiers.py [--repo PATH] [--codex-home PATH] [--json]
# Exit: 0 clean (warnings allowed), 1 blocking, 2 inputs missing.

import argparse
import json
import os
import re
import sys

TIERS = ["R", "C", "P", "V", "G", "W"]
LEVEL_ORDER = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]

# Approved mapping, 2026-10-23 (user confirmed: models restricted to the six
# tiers; R keeps "none" because the read pool is deliberately reasoning-free).
ROLE_TIER = {
    "explorer": "R", "librarian": "R",
    "worker": "C", "planner": "P", "reviewer": "V",
    "visual-designer": "G", "archivist": "W",
}
ROLE_EFFORT = {
    "explorer": "none", "librarian": "none",
    "worker": "high", "planner": "high", "reviewer": "high",
    "visual-designer": "high", "archivist": "high",
}


def rank(e):
    return LEVEL_ORDER.index(e) if e in LEVEL_ORDER else 99


def srt(s):
    return sorted(s, key=rank)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def catalog_models(path):
    """slug -> set(supported efforts). A model that declares no effort list is
    treated as {'none'}: reachable, but without reasoning control."""
    doc = load_json(path)
    ms = doc if isinstance(doc, list) else (doc.get("models") or doc.get("data") or [])
    out = {}
    for m in ms:
        slug = str(m.get("slug") or m.get("id") or "")
        if not slug:
            continue
        raw = m.get("supported_reasoning_levels") or m.get("supported_reasoning_efforts") or []
        effs = {(e.get("effort") or e.get("reasoning_effort")) if isinstance(e, dict) else e for e in raw}
        effs = {e for e in effs if e}
        out[slug] = effs or {"none"}
    return out


def tier_pools(path):
    pr = load_json(path)
    g = pr.get("groups")
    g = {x.get("id") or x.get("name"): x for x in g} if isinstance(g, list) else (g or {})
    out = {}
    for name, v in g.items():
        out[str(name)] = {"members": [str(m) for m in (v.get("members") or [])],
                          "declared": set(v.get("levels") or []),
                          "context": v.get("context")}
    return out


def parse_roles(text):
    roles = {}
    for block in re.split(r"^  - id: ", text, flags=re.M)[1:]:
        rid = block.split("\n", 1)[0].strip()
        f = {}
        for key in ("model", "reasoning_effort", "tier"):
            mm = re.search(r"^    %s: (.+?)\s*$" % key, block, re.M)
            if mm:
                f[key] = mm.group(1).strip().strip('"')
        roles[rid] = f
    top = {}
    for t in TIERS:
        mm = re.search(r'^  %s: \{ model: "([^"]+)", reasoning_effort: (\w+)' % t, text, re.M)
        if mm:
            top[t] = (mm.group(1), mm.group(2))
    return roles, top


def parse_agents(text):
    sec = re.search(r"^\[agents\][\s\S]*?(?=^\[|\Z)", text, re.M)
    body = sec.group(0) if sec else ""
    out = {}
    for key in ("default_subagent_model", "default_subagent_reasoning_effort",
                "max_concurrent_threads_per_session", "max_depth", "job_max_runtime_seconds"):
        mm = re.search(r"^%s = (.+?)\s*$" % key, body, re.M)
        out[key] = mm.group(1).strip().strip('"') if mm else None
    return out


def parse_templates(text):
    out = {}
    for block in re.findall(r"```text\n(.*?)```", text, re.S):
        rid = re.search(r"角色：(\S+)", block)
        model = re.search(r"模型：(\S+)", block)
        eff = re.search(r"推理：(\S+)", block)
        if rid and model and eff:
            out.setdefault(rid.group(1), (model.group(1).strip("`"), eff.group(1).strip("`")))
    return out


def main():
    ap = argparse.ArgumentParser()
    dp = os.path.expanduser("~")
    ap.add_argument("--repo", default=r"D:/kaikaikid/tools/magpie")
    ap.add_argument("--codex-home", default=os.path.join(dp, ".codex"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    paths = {
        "catalog": os.path.join(a.codex_home, "magpie-models.json"),
        "providers": os.path.join(a.repo, "data", "providers.json"),
        "config": os.path.join(a.codex_home, "config.toml"),
        "roles": os.path.join(a.repo, "codex-agents", "final", "contracts", "roles.yaml"),
        "templates": os.path.join(a.repo, "codex-agents", "final", "contracts", "delegation-prompts.md"),
    }
    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    if missing:
        for k in missing:
            print("MISSING INPUT:", k, paths[k])
        return 2

    caps = catalog_models(paths["catalog"])
    pools = tier_pools(paths["providers"])
    with open(paths["roles"], encoding="utf-8") as fh:
        roles_text = fh.read()
    roles, tier_rows = parse_roles(roles_text)
    with open(paths["config"], encoding="utf-8") as fh:
        agents = parse_agents(fh.read())
    with open(paths["templates"], encoding="utf-8") as fh:
        tpl = parse_templates(fh.read())

    fails, warns, rows = [], [], []
    tier_of_letter = {t: "tier-%s" % t.lower() for t in TIERS}

    # ---- pool capability: declared vs what members can serve, and vs the published catalog
    declared_by_tier, shared_by_tier = {}, {}
    for t in TIERS:
        key = tier_of_letter[t]
        g = pools.get(key)
        if not g:
            fails.append("providers.json: group '%s' does not exist (models are restricted to the six tiers)" % key)
            continue
        declared_by_tier[t] = g["declared"]
        absent = [m for m in g["members"] if m not in caps]
        present = [m for m in g["members"] if m in caps]
        shared = set.intersection(*[caps[m] for m in present]) if present else set()
        shared_by_tier[t] = shared
        unservable = sorted({e for e in g["declared"] if present and e not in shared}, key=rank)
        for e in unservable:
            weak = [m for m in present if e not in caps[m]]
            warns.append("group/%s declares '%s' but %d/%d members cannot serve it -> silent downgrade on: %s"
                         % (key, e, len(weak), len(g["members"]), ", ".join(sorted(weak)[:6])))
        if absent:
            warns.append("group/%s members missing from the published catalog: %s" % (key, ", ".join(sorted(absent)[:6])))
        pub = caps.get("group/" + key, set())
        if pub and pub != g["declared"] and pub != {"none"} or (pub == {"none"} and g["declared"] != {"none"}):
            if "group/" + key in caps:
                warns.append("catalog 'group/%s' advertises %s but providers.json declares %s -> restart magpie to republish"
                             % (key, srt(pub), srt(g["declared"])))
        rows.append((key, len(g["members"]), srt(g["declared"]), srt(shared), g["context"]))

    # ---- roles.yaml internal consistency
    for t in TIERS:
        if t not in tier_rows:
            fails.append("roles.yaml tiers table missing row %s" % t)
    for rid, f in sorted(roles.items()):
        if rid not in ROLE_TIER:
            continue
        model, eff, tier = f.get("model"), f.get("reasoning_effort"), f.get("tier")
        want_model = "group/" + tier_of_letter[ROLE_TIER[rid]]
        if tier != ROLE_TIER[rid]:
            fails.append("%s: tier=%s, approved mapping is %s" % (rid, tier, ROLE_TIER[rid]))
        if model != want_model:
            fails.append("%s: model=%s, must be %s (six tiers only)" % (rid, model, want_model))
        if eff != ROLE_EFFORT[rid]:
            fails.append("%s: reasoning_effort=%s, approved is %s" % (rid, eff, ROLE_EFFORT[rid]))
        if tier_rows.get(tier or "") and tier_rows[tier] != (model, eff):
            fails.append("%s disagrees with roles.yaml tiers[%s] = %s" % (rid, tier, tier_rows[tier]))
        if tier in declared_by_tier and eff and eff not in declared_by_tier[tier]:
            fails.append("%s: effort '%s' is not declared by group/%s (levels=%s)"
                         % (rid, eff, tier_of_letter[tier], srt(declared_by_tier[tier])))
        t2 = ROLE_TIER[rid]
        if tpl.get(rid) != (model, eff):
            fails.append("delegation-prompts.md role '%s': %s != roles.yaml (%s, %s)" % (rid, tpl.get(rid), model, eff))
        shared = shared_by_tier.get(t2, set())
        if shared and eff and eff not in shared:
            warns.append("%s: effort '%s' not shared by all members of tier-%s (shared=%s)" % (rid, eff, t2, srt(shared)))
    for rid in tpl:
        if rid not in roles:
            fails.append("delegation-prompts.md documents unknown role '%s'" % rid)

    # ---- 模型组框架.json (generated view) must agree with the contract
    frame = os.path.join(a.repo, "codex-agents", "final", "模型组框架.json")
    if os.path.exists(frame):
        fr = load_json(frame)
        for rid, want in (fr.get("roleAssignments") or {}).items():
            f = roles.get(rid)
            if not f:
                fails.append("模型组框架.json role '%s' is not in roles.yaml" % rid)
                continue
            if ("group/" + (want.get("tier") or "")) != f.get("model") or (want.get("reasoning") or "") != f.get("reasoning_effort"):
                fails.append("模型组框架.json role '%s': %s/%s != roles.yaml %s/%s"
                             % (rid, want.get("tier"), want.get("reasoning"), f.get("model"), f.get("reasoning_effort")))
        for k, v in (fr.get("tiers") or {}).items():
            g = pools.get(k)
            if g and set(v.get("legalReasoning") or []) != g["declared"]:
                fails.append("模型组框架.json tiers.%s.legalReasoning=%s != providers.json levels=%s"
                             % (k, srt(set(v.get("legalReasoning") or [])), srt(g["declared"])))
    else:
        warns.append("模型组框架.json not found (generated view missing)")

    # ---- parent config
    dmodel = agents.get("default_subagent_model") or ""
    mm = re.match(r"group/tier-([a-z])$", dmodel)
    if not mm:
        fails.append("agents.default_subagent_model='%s' is not one of the six tiers" % dmodel)
    else:
        t = mm.group(1).upper()
        deff = agents.get("default_subagent_reasoning_effort")
        if t in declared_by_tier and deff not in declared_by_tier[t]:
            fails.append("agents.default_subagent_reasoning_effort='%s' not declared by group/tier-%s" % (deff, t.lower()))
    if agents.get("max_depth") is None:
        warns.append("agents.max_depth unset: nothing structurally stops nested spawning")
    if agents.get("job_max_runtime_seconds") is None:
        warns.append("agents.job_max_runtime_seconds unset: a stalled subagent has no hard timeout")

    if a.json:
        print(json.dumps({"tiers": rows, "agents": agents, "fails": fails, "warns": warns},
                         ensure_ascii=False, indent=2))
    else:
        print("%-10s %-5s %-14s %-16s %s" % ("pool", "n", "declared", "all-members", "ctx"))
        for r in rows:
            print("%-10s %-5d %-14s %-16s %s" % (r[0], r[1], ",".join(r[2]) or "-", ",".join(r[3]) or "?", r[4]))
        print("\n[agents] default=%s + %s | max_concurrent=%s | max_depth=%s"
              % (agents.get("default_subagent_model"), agents.get("default_subagent_reasoning_effort"),
                 agents.get("max_concurrent_threads_per_session"), agents.get("max_depth")))
        for w in warns:
            print("WARN:", w)
        for e in fails:
            print("FAIL:", e)
        print("\n%s blocking, %d warning(s)" % (len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
