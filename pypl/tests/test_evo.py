"""Evo（确定性规则演进）测试。

在临时目录里搭建最小仓库副本（规则、策略、基线集、录制财报），
通过 subprocess 调 evo.py 验证：基线可复现、采纳/拒绝判定正确、
无批准记录 adopt 失败、rollback 后指标一致。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
EVO_SCRIPT = os.path.join(SCRIPT_DIR, "scripts", "evo.py")


def _make_root(tmp_path):
    root = str(tmp_path)
    for rel in ("pypl/references", "evals/baseline", "examples/input"):
        os.makedirs(os.path.join(root, rel), exist_ok=True)
    shutil.copy2(os.path.join(REPO_ROOT, "pypl", "references", "gate_rules.json"),
                 os.path.join(root, "pypl", "references", "gate_rules.json"))
    shutil.copy2(os.path.join(REPO_ROOT, "pypl", "references", "evo_policy.md"),
                 os.path.join(root, "pypl", "references", "evo_policy.md"))
    for name in os.listdir(os.path.join(REPO_ROOT, "evals", "baseline")):
        shutil.copy2(os.path.join(REPO_ROOT, "evals", "baseline", name),
                     os.path.join(root, "evals", "baseline", name))
    shutil.copy2(os.path.join(REPO_ROOT, "examples", "input", "pypl-earnings-q3-2026.json"),
                 os.path.join(root, "examples", "input", "pypl-earnings-q3-2026.json"))
    return root


def _run_evo(args, root):
    return subprocess.run(
        [sys.executable, EVO_SCRIPT, "--root", root] + args,
        capture_output=True, text=True, timeout=300, cwd=REPO_ROOT,
    )


def _fingerprint(stdout):
    for line in stdout.splitlines():
        if line.startswith("FINGERPRINT "):
            return line.split(" ", 1)[1]
    return None


def _compare_result(stdout):
    for line in stdout.splitlines():
        if line.startswith("COMPARE_RESULT "):
            return json.loads(line.split(" ", 1)[1])
    return None


def _write_rules(path, version, words, tolerance=0.005, min_reasons=3):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": version, "forbidden_words": words,
                   "numeric_tolerance": tolerance, "min_reasons": min_reasons},
                  f, ensure_ascii=False, indent=2)


def test_evo_baseline_reproducible(tmp_path):
    root = _make_root(tmp_path)
    rules = os.path.join(root, "pypl", "references", "gate_rules.json")
    r1 = _run_evo(["run", "--rules", rules], root)
    r2 = _run_evo(["run", "--rules", rules], root)
    assert r1.returncode == 0 and r2.returncode == 0, r1.stderr + r2.stderr
    fp1, fp2 = _fingerprint(r1.stdout), _fingerprint(r2.stdout)
    assert fp1 and fp1 == fp2, "同一规则两次跑基线的 fingerprint 必须一致"


def test_evo_compare_suggests_adopt_and_rejects_regression(tmp_path):
    root = _make_root(tmp_path)
    base = os.path.join(root, "pypl", "references", "gate_rules.json")
    good = os.path.join(root, "good.json")
    bad = os.path.join(root, "bad.json")
    _write_rules(good, "v-good", ["买入", "卖出", "下单", "加仓", "清仓", "抄底"])
    _write_rules(bad, "v-bad", ["买入", "卖出", "下单", "加仓", "清仓", "抄底"],
                 tolerance=0.05)

    r1 = _run_evo(["compare", "--baseline", base, "--candidate", good], root)
    assert r1.returncode == 0, r1.stderr
    d1 = _compare_result(r1.stdout)
    assert d1["decision"] == "adopt", d1["reasons"]
    assert d1["candidate_metrics"]["recall"] == 1.0
    assert d1["candidate_metrics"]["false_block_rate"] == 0.0

    r2 = _run_evo(["compare", "--baseline", good, "--candidate", bad], root)
    assert r2.returncode == 0, r2.stderr
    d2 = _compare_result(r2.stdout)
    assert d2["decision"] == "reject"
    assert any("min_recall_gain" in reason for reason in d2["reasons"])


def test_evo_adopt_requires_approval(tmp_path):
    root = _make_root(tmp_path)
    candidate = os.path.join(root, "candidate.json")
    _write_rules(candidate, "v-candidate", ["买入", "卖出", "下单", "抄底"])

    # 没有批准记录：adopt 必须失败
    r = _run_evo(["adopt", "--candidate", candidate], root)
    assert r.returncode == 2
    assert "批准" in r.stderr

    # 批准后再 adopt：成功，gate_rules.json 被更新
    r2 = _run_evo(["approve", "--candidate", candidate, "--approver", "测试员"], root)
    assert r2.returncode == 0, r2.stderr
    r3 = _run_evo(["adopt", "--candidate", candidate], root)
    assert r3.returncode == 0, r3.stderr
    current = json.load(open(os.path.join(root, "pypl", "references", "gate_rules.json"), encoding="utf-8"))
    assert current["version"] == "v-candidate"
    assert "抄底" in current["forbidden_words"]
    changelog = open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
    assert "v-candidate" in changelog and "测试员" in changelog


def test_evo_rollback_restores_metrics(tmp_path):
    root = _make_root(tmp_path)
    rules_path = os.path.join(root, "pypl", "references", "gate_rules.json")

    def git(*args):
        return subprocess.run(["git", "-C", root] + list(args),
                              capture_output=True, text=True, timeout=60)

    assert git("init").returncode == 0
    git("config", "user.name", "于欣荷")
    git("config", "user.email", "cynthiayu615@gmail.com")
    git("add", "-A")
    git("commit", "-m", "baseline").returncode == 0
    git("tag", "v-test-baseline")

    r0 = _run_evo(["run", "--rules", rules_path], root)
    fp_before = _fingerprint(r0.stdout)

    # 模拟一次被采纳的改动
    _write_rules(rules_path, "v-test-new", ["买入", "卖出", "下单", "抄底"])
    r1 = _run_evo(["run", "--rules", rules_path], root)
    fp_modified = _fingerprint(r1.stdout)
    assert fp_modified != fp_before

    r2 = _run_evo(["rollback", "--to", "v-test-baseline"], root)
    assert r2.returncode == 0, r2.stderr
    restored = json.load(open(rules_path, encoding="utf-8"))
    assert restored["version"] == "v0.1-baseline"

    r3 = _run_evo(["run", "--rules", rules_path], root)
    fp_after = _fingerprint(r3.stdout)
    assert fp_after == fp_before, "rollback 后基线指标必须与最初完全一致"
