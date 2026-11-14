#!/usr/bin/env python3
"""dna-flywheel v1 —— DNA 飞轮入口（validate / evaluate / reflux）。

设计正本：`../references/run-contract.md`、`stage-rules.md`、`cache-key.md`。
v1 只做三个**纯文件**子命令：读 JSON、算数、产提案；**不写任何正本**。
其余四个子命令（collect/ingest/annotate/review-assist）是接口桩，调用即非零退出。

只依赖标准库。退出码：0＝跑完（不等于通过）；2＝输入/用法错误；3＝未实现。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from typing import Any

SKILL_VERSION = "dna-flywheel@0.1.0"
STAGES = (
    "collect",
    "ingest",
    "annotate",
    "validate",
    "review-assist",
    "evaluate",
    "reflux",
)
STUBS = ("collect", "ingest", "annotate", "review-assist")


# ── 契约骨架 ────────────────────────────────────────────────────────


def _run_id(stage: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"dna-{stamp}-{stage}"


def _envelope(stage: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """六个计数恒在场（缺项写 0，不写 null）。"""
    return {
        "run_id": _run_id(stage),
        "stage": stage,
        "round_id": inputs.pop("round_id", "round-001"),
        "inputs": {
            "ontology_version": inputs.get("ontology_version", "n/a"),
            "record_schema_version": inputs.get("record_schema_version", "n/a"),
            "criteria_version": inputs.get("criteria_version", "n/a"),
            "prompt_version": inputs.get("prompt_version", "n/a"),
            "skill_version": SKILL_VERSION,
            "pipeline_version": inputs.get("pipeline_version", "n/a"),
        },
        "counts": {
            "added": 0,
            "processed": 0,
            "skipped": 0,
            "duplicate_candidates": 0,
            "failed": 0,
            "needs_review": 0,
        },
        "findings": [],
        "artifacts": [],
        "blocked_reason": None,
    }


def _finding(
    code: str,
    level: str,
    message: str,
    evidence_ref: str,
    asset_id: str | None = None,
    subfield: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "level": level,
        "asset_id": asset_id,
        "subfield": subfield,
        "message": message,
        "evidence_ref": evidence_ref,
    }


def _load(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    _human_summary(payload)


def _human_summary(payload: dict[str, Any]) -> None:
    """人读段只复述 inputs / counts / findings，不另加判断。"""
    c = payload["counts"]
    print("\n── 人读摘要 ──", file=sys.stderr)
    print(f"stage={payload['stage']} run={payload['run_id']}", file=sys.stderr)
    print(
        "counts: "
        + " ".join(f"{k}={v}" for k, v in c.items()),
        file=sys.stderr,
    )
    for f in payload["findings"]:
        print(
            f"  [{f['level']}] {f['code']} {f.get('asset_id') or '-'}: {f['message']}",
            file=sys.stderr,
        )
    print(
        "blocked_reason=" + str(payload["blocked_reason"]),
        file=sys.stderr,
    )


# ── 本体索引 ────────────────────────────────────────────────────────


def _ontology_index(onto: dict[str, Any]) -> tuple[dict[str, dict], set[str]]:
    """返回 (allele_id → 元数据, 结果标签 id 集)。"""
    alleles: dict[str, dict] = {}
    for locus in onto.get("loci") or []:
        for a in locus.get("alleles") or []:
            alleles[str(a.get("id"))] = {
                "status": str(a.get("status") or "active"),
                "locus": str(locus.get("id")),
                "subfield_key": str(a.get("subfield_key") or locus.get("id")),
            }
    labels = {
        str(x.get("id"))
        for x in (onto.get("result_labels") or [])
        if isinstance(x, dict) and x.get("id")
    }
    return alleles, labels


# ── validate ────────────────────────────────────────────────────────


def cmd_validate(args: argparse.Namespace) -> int:
    onto = _load(args.ontology)
    records = _load(args.records)
    if isinstance(records, dict):
        records = records.get("records") or records.get("items") or []
    retired_extra = {str(x) for x in (args.retired or [])}

    alleles, result_labels = _ontology_index(onto)
    inputs = {
        "ontology_version": (onto.get("meta") or {}).get("ontology_version", "n/a"),
        "record_schema_version": args.record_schema_version,
        "criteria_version": args.criteria_version,
        "round_id": args.round_id,
    }
    out = _envelope("validate", inputs)

    for rec in records:
        asset_id = rec.get("asset_id")
        rec_findings: list[dict] = []
        if not asset_id:
            rec_findings.append(
                _finding(
                    "V-004",
                    "block",
                    "记录缺 asset_id（只存 asset_id 引用，不新建资产真源）",
                    "08.2#asset_id",
                )
            )
        for ref in rec.get("alleles") or []:
            aid = str(ref.get("allele_id") or ref)
            subfield = ref.get("subfield") if isinstance(ref, dict) else None
            meta = alleles.get(aid)
            if meta is None and aid in result_labels:
                rec_findings.append(
                    _finding(
                        "V-005",
                        "warn",
                        f"{aid} 是结果标签，只能出不入基因位",
                        "03.1#result_labels",
                        asset_id,
                        subfield,
                    )
                )
                continue
            if meta is None:
                rec_findings.append(
                    _finding(
                        "V-001",
                        "block",
                        f"allele_id 不在本体中: {aid}",
                        f"03.1#{aid}",
                        asset_id,
                        subfield,
                    )
                )
                continue
            if meta["status"] != "active" or aid in retired_extra:
                rec_findings.append(
                    _finding(
                        "V-003",
                        "block",
                        f"引用了 retired allele_id: {aid}",
                        f"03.1#{aid}",
                        asset_id,
                        subfield or meta["locus"],
                    )
                )
                continue
            if subfield and subfield != meta["subfield_key"]:
                rec_findings.append(
                    _finding(
                        "V-002",
                        "warn",
                        f"subfield_key 与所属基因座不一致: {subfield} ≠ {meta['subfield_key']}",
                        f"03.1#{aid}",
                        asset_id,
                        subfield,
                    )
                )
        out["findings"].extend(rec_findings)
        if any(f["level"] == "block" for f in rec_findings):
            out["counts"]["failed"] += 1
        elif rec_findings:
            out["counts"]["needs_review"] += 1
        else:
            out["counts"]["processed"] += 1

    blocks = [f for f in out["findings"] if f["level"] == "block"]
    if blocks:
        first = blocks[0]
        out["blocked_reason"] = f"{first['code']}: {first['message']}"
    _emit(out)
    return 0


# ── evaluate ────────────────────────────────────────────────────────


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def cmd_evaluate(args: argparse.Namespace) -> int:
    gold = _load(args.gold)
    pred = _load(args.pred)
    if isinstance(gold, dict):
        gold = gold.get("records") or gold.get("items") or []
    if isinstance(pred, dict):
        pred = pred.get("records") or pred.get("items") or []

    out = _envelope("evaluate", {"round_id": args.round_id})

    gmap = {str(r.get("asset_id")): set(map(str, r.get("alleles") or [])) for r in gold}
    pmap = {str(r.get("asset_id")): set(map(str, r.get("alleles") or [])) for r in pred}

    if set(gmap) != set(pmap):
        out["findings"].append(
            _finding(
                "E-002",
                "block",
                f"gold 与 pred 样本键集不一致：gold_only={sorted(set(gmap)-set(pmap))} "
                f"pred_only={sorted(set(pmap)-set(gmap))}",
                "04.1#evaluate",
            )
        )
        out["blocked_reason"] = "E-002: gold 与 pred 样本键集不一致"
        out["counts"]["failed"] = len(set(gmap) ^ set(pmap))
        _emit(out)
        return 0

    if not gmap:
        out["findings"].append(
            _finding("E-001", "warn", "评估样本数为 0，指标不可算", "04.1#evaluate")
        )
        _emit(out)
        return 0

    tp = fp = fn = 0
    per_asset = []
    for aid in sorted(gmap):
        g, p = gmap[aid], pmap[aid]
        a_tp, a_fp, a_fn = len(g & p), len(p - g), len(g - p)
        tp, fp, fn = tp + a_tp, fp + a_fp, fn + a_fn
        per_asset.append({"asset_id": aid, "tp": a_tp, "fp": a_fp, "fn": a_fn})

    micro = _prf(tp, fp, fn)
    macros = [_prf(x["tp"], x["fp"], x["fn"]) for x in per_asset]
    macro = tuple(sum(m[i] for m in macros) / len(macros) for i in range(3))

    out["artifacts"].append(
        {
            "kind": "evaluation",
            "metrics": {
                "micro": dict(zip(("precision", "recall", "f1"), map(_r, micro))),
                "macro": dict(zip(("precision", "recall", "f1"), map(_r, macro))),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "samples": len(gmap),
            },
            "per_asset": per_asset,
        }
    )
    out["counts"]["processed"] = len(gmap)
    _emit(out)
    return 0


def _r(x: float) -> float:
    return round(x, 4)


# ── reflux ──────────────────────────────────────────────────────────


def cmd_reflux(args: argparse.Namespace) -> int:
    confirmed = _load(args.confirmed)
    if isinstance(confirmed, dict):
        confirmed = confirmed.get("items") or confirmed.get("records") or []

    out = _envelope("reflux", {"round_id": args.round_id})
    rows = []
    for item in confirmed:
        approver = item.get("approved_by")
        if not approver:
            out["findings"].append(
                _finding(
                    "R-001",
                    "warn",
                    "回流提案缺审批人，按「待批」输出",
                    "08.2#approved_by",
                    item.get("asset_id"),
                )
            )
        rows.append(
            {
                "target": item.get("target") or "08.2",
                "subfield": item.get("subfield"),
                "allele_id": item.get("allele_id"),
                "change": item.get("change"),
                "evidence_ref": item.get("evidence_ref"),
                "approved_by": approver,
                "status": "approved" if approver else "pending",
            }
        )

    out["artifacts"].append(
        {
            "kind": "proposal",
            "target": "08.2",
            "rows": rows,
            "markdown": _proposal_markdown(rows),
        }
    )
    out["counts"]["added"] = len(rows)
    _emit(out)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(_proposal_markdown(rows))
    return 0


def _proposal_markdown(rows: list[dict]) -> str:
    head = "| subfield | allele_id | change | evidence_ref | approved_by | status |\n|---|---|---|---|---|---|"
    body = "\n".join(
        f"| {r['subfield'] or '-'} | {r['allele_id'] or '-'} | {r['change'] or '-'} "
        f"| {r['evidence_ref'] or '-'} | {r['approved_by'] or '-'} | {r['status']} |"
        for r in rows
    )
    return head + ("\n" + body if body else "")


# ── 入口 ────────────────────────────────────────────────────────────


def _cache_key(args: argparse.Namespace) -> str | None:
    if not args.image_sha256:
        return None
    parts = [
        args.image_sha256,
        ",".join(sorted(args.subfield or [])),
        args.ontology_version,
        args.criteria_version,
        args.record_schema_version,
        args.model_id,
        args.model_revision,
        args.prompt_hash,
        SKILL_VERSION,
        args.pipeline_version,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dna-flywheel")
    sub = p.add_subparsers(dest="stage", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--round-id", default="round-001")
        sp.add_argument("--ontology-version", default="n/a")
        sp.add_argument("--criteria-version", default="n/a")
        sp.add_argument("--record-schema-version", default="n/a")
        sp.add_argument("--pipeline-version", default="n/a")
        sp.add_argument("--model-id", default="n/a")
        sp.add_argument("--model-revision", default="n/a")
        sp.add_argument("--prompt-hash", default="n/a")
        sp.add_argument("--image-sha256", default=None)
        sp.add_argument("--subfield", action="append", default=[])

    v = sub.add_parser("validate")
    common(v)
    v.add_argument("--records", required=True)
    v.add_argument("--ontology", required=True)
    v.add_argument("--retired", action="append", default=[])
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("evaluate")
    common(e)
    e.add_argument("--gold", required=True)
    e.add_argument("--pred", required=True)
    e.set_defaults(func=cmd_evaluate)

    r = sub.add_parser("reflux")
    common(r)
    r.add_argument("--confirmed", required=True)
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_reflux)

    for name in STUBS:
        s = sub.add_parser(name)
        s.set_defaults(func=None, stub=name)

    args = p.parse_args(argv)

    if getattr(args, "func", None) is None:
        print(
            json.dumps(
                {
                    "stage": getattr(args, "stub", args.stage),
                    "implemented": False,
                    "reason": "v1 未实现：依赖未建成服务（覆盖看板／素材库／VLM／工作台）",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3

    key = _cache_key(args)
    if key:
        print(f"[cache-key] {key}", file=sys.stderr)
        print(
            "[cache-key] 组成: image_sha256|subfield_set|ontology|criteria|schema"
            "|model_id|model_revision|prompt_hash|skill|pipeline",
            file=sys.stderr,
        )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
