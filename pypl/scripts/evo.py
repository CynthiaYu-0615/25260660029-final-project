#!/usr/bin/env python3
"""Evo：对照固定基线测试 gate 规则改动、决定采纳或拒绝、记录版本并回滚。

确定性、可复现：评估对象是关卡规则（pypl/references/gate_rules.json），
基线是 evals/baseline/ 下固定的候选报告样例，裁判是真实的 gate_report，
指标（拦截召回率、误拦率）直接计算，不依赖 LLM。

子命令：
    run      --rules <文件> [--root ROOT] [--out FILE]
    compare  --baseline <规则文件> --candidate <规则文件> [--root ROOT] [--out FILE]
    approve  --candidate <规则文件> --approver <名字> [--root ROOT]
    adopt    --candidate <规则文件> [--root ROOT]
    reject   --version <版本> --reason <原因> [--root ROOT]
    rollback --to <git tag> [--root ROOT]

采纳策略阈值来自 pypl/references/evo_policy.md，compare 解析并强制执行；
adopt 前必须有人工批准记录（evals/approvals.json，含候选规则文件 sha256），
否则拒绝执行。每次采纳/拒绝/回滚都追加根目录 CHANGELOG.md。
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYPL_SCRIPT = os.path.join(REPO_ROOT, "pypl", "scripts", "pypl.py")

CATEGORY_MAP = [
    ("执行性指令词", "执行性指令"),
    ("numeric_mismatch", "数值不一致"),
    ("未能识别明确结论", "结论不明"),
    ("结论不是", "结论不明"),
    ("as-of", "as-of 泄露"),
    ("理由少", "理由不足"),
    ("缺少 key_figures", "缺少数值块"),
    ("缺少必要", "结构缺失"),
    ("缺少风险", "缺风险提示"),
]


def _paths(root):
    return {
        "gate_rules": os.path.join(root, "pypl", "references", "gate_rules.json"),
        "policy": os.path.join(root, "pypl", "references", "evo_policy.md"),
        "baseline_dir": os.path.join(root, "evals", "baseline"),
        "results_dir": os.path.join(root, "evals", "results"),
        "approvals": os.path.join(root, "evals", "approvals.json"),
        "changelog": os.path.join(root, "CHANGELOG.md"),
        "recorded": os.path.join(root, "examples", "input", "pypl-earnings-q3-2026.json"),
    }


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _recorded_sec_facts(root):
    rec = _load_json(_paths(root)["recorded"])
    return {"facts": {
        "revenues": {"value": rec["total_net_revenues"]["value"] * 1_000_000, "unit": "USD"},
        "net_income": {"value": rec["net_income"]["value"] * 1_000_000, "unit": "USD"},
        "diluted_eps": {"value": rec["diluted_eps"]["value"], "unit": "USD"},
    }}


def _classify(failures):
    for f in failures:
        for key, category in CATEGORY_MAP:
            if key in f:
                return category
    return "其他"


def run_baseline(rules, root):
    """用给定规则跑基线集，返回逐份结果与指标（不依赖 LLM，无需网络）。"""
    p = _paths(root)
    manifest = _load_json(os.path.join(p["baseline_dir"], "cases.json"))
    as_of = manifest["request_as_of"]
    sec_facts = _recorded_sec_facts(root)
    results = []
    for case in manifest["cases"]:
        report = open(os.path.join(p["baseline_dir"], case["file"]), encoding="utf-8").read()
        payload = {"report_text": report, "evidence_text": "{}", "as_of": as_of, "rules": rules}
        if case.get("use_sec_facts"):
            payload["sec_facts"] = sec_facts
        proc = subprocess.run(
            [sys.executable, PYPL_SCRIPT, "gate_report"],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, timeout=60,
        )
        gate = json.loads(proc.stdout)["data"]
        blocked = not gate["passed"]
        category = _classify(gate["failures"]) if blocked else None
        expected = case["expected"]
        correct = (expected == "pass" and not blocked) or (expected == "block" and blocked)
        category_ok = True
        if blocked and expected == "block" and case.get("category"):
            category_ok = category == case["category"]
        results.append({
            "id": case["id"],
            "file": case["file"],
            "expected": expected,
            "blocked": blocked,
            "category": category,
            "failures": gate["failures"],
            "correct": correct and category_ok,
        })
    should_block = [r for r in results if r["expected"] == "block"]
    should_pass = [r for r in results if r["expected"] == "pass"]
    metrics = {
        "total": len(results),
        "should_block": len(should_block),
        "blocked": sum(1 for r in should_block if r["blocked"]),
        "recall": (sum(1 for r in should_block if r["blocked"]) / len(should_block)) if should_block else 0.0,
        "should_pass": len(should_pass),
        "false_blocked": sum(1 for r in should_pass if r["blocked"]),
        "false_block_rate": (sum(1 for r in should_pass if r["blocked"]) / len(should_pass)) if should_pass else 0.0,
        "all_correct": all(r["correct"] for r in results),
    }
    return {"rules_version": rules.get("version", "unknown"), "results": results, "metrics": metrics}


def fingerprint(run_result):
    """只哈希确定性内容（不含时间戳），用于回滚前后的一致性对比。"""
    body = json.dumps(
        {"rules_version": run_result["rules_version"],
         "results": [{k: r[k] for k in ("id", "expected", "blocked", "category", "correct")}
                     for r in run_result["results"]],
         "metrics": run_result["metrics"]},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def cmd_run(args):
    rules = _load_json(args.rules)
    result = run_baseline(rules, args.root)
    result["fingerprint"] = fingerprint(result)
    result["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已保存 {args.out}")
    print(json.dumps(result["metrics"], ensure_ascii=False))
    print("FINGERPRINT " + result["fingerprint"])
    return 0


def _parse_policy(root):
    text = open(_paths(root)["policy"], encoding="utf-8").read()
    m1 = re.search(r"max_false_block_rate\s*=\s*([0-9.]+)", text)
    m2 = re.search(r"min_recall_gain\s*=\s*([0-9.]+)", text)
    if not m1 or not m2:
        raise RuntimeError("无法从 evo_policy.md 解析阈值，拒绝 compare（fail-closed）")
    return float(m1.group(1)), float(m2.group(1))


def cmd_compare(args):
    base_rules = _load_json(args.baseline)
    cand_rules = _load_json(args.candidate)
    base = run_baseline(base_rules, args.root)
    cand = run_baseline(cand_rules, args.root)
    max_fbr, min_gain = _parse_policy(args.root)

    reasons = []
    if cand["metrics"]["false_block_rate"] > max_fbr + base["metrics"]["false_block_rate"]:
        reasons.append(
            f"误拦率 {cand['metrics']['false_block_rate']:.2f} 超过基线 "
            f"{base['metrics']['false_block_rate']:.2f} + 上限 {max_fbr}（违反 max_false_block_rate）"
        )
    recall_gain = cand["metrics"]["recall"] - base["metrics"]["recall"]
    if recall_gain <= min_gain:
        reasons.append(
            f"召回率提升 {recall_gain:+.2f} 未满足必须严格大于 {min_gain}（违反 min_recall_gain）"
        )
    decision = "adopt" if not reasons else "reject"

    report = [
        f"# A/B 对比：{base_rules.get('version')} → {cand_rules.get('version')}",
        "",
        f"- 基线规则：`{args.baseline}`（{base_rules.get('version')}）",
        f"- 候选规则：`{args.candidate}`（{cand_rules.get('version')}）",
        f"- 基线集：evals/baseline/（{base['metrics']['total']} 份样例）",
        "",
        "## 指标",
        "",
        "| 指标 | 基线 | 候选 |",
        "| --- | --- | --- |",
        f"| 拦截召回率 | {base['metrics']['recall']:.2f} | {cand['metrics']['recall']:.2f} |",
        f"| 误拦率 | {base['metrics']['false_block_rate']:.2f} | {cand['metrics']['false_block_rate']:.2f} |",
        "",
        "## 阈值（pypl/references/evo_policy.md，代码强制）",
        "",
        f"- max_false_block_rate = {max_fbr}（候选误拦率不得高于基线 + 该值）",
        f"- min_recall_gain = {min_gain}（候选召回率必须严格提高超过该值）",
        "",
        "## 逐份结果",
        "",
        "| 样例 | 期望 | 基线实际 | 候选实际 |",
        "| --- | --- | --- | --- |",
    ]
    for rb, rc in zip(base["results"], cand["results"]):
        report.append(
            f"| {rb['id']} | {rb['expected']} | "
            f"{'拦' if rb['blocked'] else '放'} | {'拦' if rc['blocked'] else '放'} |"
        )
    report += ["", f"## 结论：{'建议采纳（仍需人工批准后才能 adopt）' if decision == 'adopt' else '拒绝'}", ""]
    if reasons:
        report += ["理由："] + [f"- {r}" for r in reasons] + [""]
    else:
        report += ["理由：召回率提高且误拦率未超阈值。", ""]
    report_text = "\n".join(report)

    summary = {
        "baseline_version": base_rules.get("version"),
        "candidate_version": cand_rules.get("version"),
        "baseline_metrics": base["metrics"],
        "candidate_metrics": cand["metrics"],
        "policy": {"max_false_block_rate": max_fbr, "min_recall_gain": min_gain},
        "decision": decision,
        "reasons": reasons,
        "fingerprint_baseline": fingerprint(base),
        "fingerprint_candidate": fingerprint(cand),
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"已保存 {args.out}")
    print(report_text)
    print("COMPARE_RESULT " + json.dumps(summary, ensure_ascii=False))
    return 0


def cmd_approve(args):
    p = _paths(args.root)
    approvals = _load_json(p["approvals"]) if os.path.exists(p["approvals"]) else {"approvals": []}
    entry = {
        "candidate": os.path.relpath(args.candidate, args.root),
        "candidate_sha256": _sha256(args.candidate),
        "version": _load_json(args.candidate).get("version", "unknown"),
        "approver": args.approver,
        "decision": "approve",
        "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    approvals["approvals"].append(entry)
    _write_json(p["approvals"], approvals)
    print(f"批准记录已写入 evals/approvals.json：{entry['version']} by {entry['approver']}")
    return 0


def _append_changelog(root, title, lines):
    path = _paths(root)["changelog"]
    existing = open(path, encoding="utf-8").read() if os.path.exists(path) else "# CHANGELOG\n"
    block = [f"\n## {title}", ""]
    block += [f"- {line}" for line in lines]
    block += [""]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(block))
    print(f"CHANGELOG 已追加：{title}")


def cmd_adopt(args):
    p = _paths(args.root)
    cand_sha = _sha256(args.candidate)
    if not os.path.exists(p["approvals"]):
        print("拒绝：evals/approvals.json 不存在，没有人工批准记录", file=sys.stderr)
        return 2
    approvals = _load_json(p["approvals"])["approvals"]
    matched = [a for a in approvals
               if a.get("candidate_sha256") == cand_sha and a.get("decision") == "approve"]
    if not matched:
        print("拒绝：没有与该候选规则（sha256 匹配）的人工批准记录", file=sys.stderr)
        return 2
    approver = matched[-1]["approver"]

    cand_rules = _load_json(args.candidate)
    current = _load_json(p["gate_rules"])
    before_version = current.get("version", "unknown")
    before = run_baseline(current, args.root)
    after = run_baseline(cand_rules, args.root)

    with open(p["gate_rules"], "w", encoding="utf-8") as f:
        json.dump(cand_rules, f, ensure_ascii=False, indent=2)
        f.write("\n")

    added = sorted(set(cand_rules.get("forbidden_words", [])) - set(current.get("forbidden_words", [])))
    removed = sorted(set(current.get("forbidden_words", [])) - set(cand_rules.get("forbidden_words", [])))
    changes = []
    if added:
        changes.append(f"违禁词增加：{'、'.join(added)}")
    if removed:
        changes.append(f"违禁词移除：{'、'.join(removed)}")
    if cand_rules.get("numeric_tolerance") != current.get("numeric_tolerance"):
        changes.append(f"数值容差：{current.get('numeric_tolerance')} → {cand_rules.get('numeric_tolerance')}")
    if cand_rules.get("min_reasons") != current.get("min_reasons"):
        changes.append(f"最少理由条数：{current.get('min_reasons')} → {cand_rules.get('min_reasons')}")
    if not changes:
        changes.append("规则内容无可见差异")

    _append_changelog(args.root, f"{cand_rules.get('version', 'unknown')} — adopted", [
        f"日期：{datetime.now().astimezone().date().isoformat()}",
        f"改动：{'；'.join(changes)}（{before_version} → {cand_rules.get('version')}）",
        f"指标：召回率 {before['metrics']['recall']:.2f} → {after['metrics']['recall']:.2f}，"
        f"误拦率 {before['metrics']['false_block_rate']:.2f} → {after['metrics']['false_block_rate']:.2f}",
        f"决定：采纳（批准人 {approver}，候选 sha256 {cand_sha[:12]}…，记录于 evals/approvals.json）",
    ])
    print(f"已采纳 {cand_rules.get('version')}：gate_rules.json 已更新")
    return 0


def cmd_reject(args):
    _append_changelog(args.root, f"{args.version} — rejected", [
        f"日期：{datetime.now().astimezone().date().isoformat()}",
        f"决定：拒绝（未写入门户规则）",
        f"理由：{args.reason}",
    ])
    return 0


def cmd_rollback(args):
    p = _paths(args.root)
    proc = subprocess.run(
        ["git", "-C", args.root, "show", f"{args.to}:pypl/references/gate_rules.json"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        print(f"回滚失败：无法从 git tag {args.to} 读取规则（{proc.stderr.strip()}）", file=sys.stderr)
        return 2
    restored = json.loads(proc.stdout)
    with open(p["gate_rules"], "w", encoding="utf-8") as f:
        f.write(proc.stdout if proc.stdout.endswith("\n") else proc.stdout + "\n")
    after = run_baseline(restored, args.root)
    _append_changelog(args.root, f"{restored.get('version', 'unknown')} — rollback（自 {args.to} 恢复）", [
        f"日期：{datetime.now().astimezone().date().isoformat()}",
        f"改动：gate_rules.json 恢复到 {args.to} 对应内容（版本 {restored.get('version')}）",
        f"指标：召回率 {after['metrics']['recall']:.2f}，误拦率 {after['metrics']['false_block_rate']:.2f}，"
        f"fingerprint {fingerprint(after)[:12]}…",
        f"决定：回滚（由演示/用户发起）",
    ])
    print(f"已回滚到 {args.to}（版本 {restored.get('version')}），"
          f"fingerprint {fingerprint(after)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="确定性 evo：基线对比、采纳/拒绝、版本与回滚")
    parser.add_argument("--root", default=REPO_ROOT, help="仓库根目录（测试用临时副本）")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("run", help="用指定规则跑基线集")
    sp.add_argument("--rules", required=True)
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("compare", help="基线 vs 候选，按策略给建议")
    sp.add_argument("--baseline", required=True)
    sp.add_argument("--candidate", required=True)
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("approve", help="记录人工批准（写 evals/approvals.json）")
    sp.add_argument("--candidate", required=True)
    sp.add_argument("--approver", required=True)
    sp.set_defaults(func=cmd_approve)

    sp = sub.add_parser("adopt", help="采纳候选规则（需已有批准记录）")
    sp.add_argument("--candidate", required=True)
    sp.set_defaults(func=cmd_adopt)

    sp = sub.add_parser("reject", help="记录一次拒绝决定（写 CHANGELOG）")
    sp.add_argument("--version", required=True)
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_reject)

    sp = sub.add_parser("rollback", help="把 gate_rules.json 恢复到指定 git tag 的内容")
    sp.add_argument("--to", required=True)
    sp.set_defaults(func=cmd_rollback)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
