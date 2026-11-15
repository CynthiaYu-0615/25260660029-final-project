"""演示场景（demo.py）的终态断言。

每个场景用离线模式（fetch_sec 直接用录制数据）在临时输出目录运行，
解析 SCENARIO_RESULT 行和落盘的 evidence 文件，断言终态符合预期。
"""

import json
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_SCRIPT = os.path.join(SCRIPT_DIR, "scripts", "demo.py")
RESULT_RE = re.compile(r"^SCENARIO_RESULT (\{.*\})$")


def run_scenario(name, tmpdir):
    proc = subprocess.run(
        [sys.executable, DEMO_SCRIPT, "--scenario", name,
         "--offline", "--out-dir", tmpdir],
        capture_output=True, text=True, timeout=180, cwd=SCRIPT_DIR,
    )
    assert proc.returncode == 0, f"demo 场景 {name} 退出码 {proc.returncode}: {proc.stderr[-500:]}"
    result = None
    for line in proc.stdout.splitlines():
        m = RESULT_RE.match(line.strip())
        if m:
            result = json.loads(m.group(1))
    assert result is not None, f"场景 {name} 没有输出 SCENARIO_RESULT"
    return result


def _summary_file(tmpdir, rel):
    path = os.path.join(tmpdir, rel, "summary.json")
    assert os.path.exists(path), f"缺少证据文件: {path}"
    return json.load(open(path, encoding="utf-8"))


def test_demo_scenario_a_blocked_then_pass(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("A", tmpdir)
    assert r["status"] == "ok"
    assert r["gate_v1_blocked"] is True
    assert r["v1_含买入指令被拦"] is True
    assert r["v1_EPS错误numeric_mismatch"] is True
    assert r["v2_revise"] is True
    assert r["final_next_action"] == "await_approval"
    _summary_file(tmpdir, os.path.join("verification", "blocked-then-pass"))
    pypl = os.path.join(tmpdir, "verification", "blocked-then-pass", ".pypl")
    assert os.path.exists(os.path.join(pypl, "state.json"))
    assert os.path.exists(os.path.join(pypl, "demo-log.jsonl"))


def test_demo_scenario_b_exhausted(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("B", tmpdir)
    assert r["status"] == "ok"
    assert r["final_state"] == "exhausted"
    assert r["exhausted_not_accepted"] is True
    assert r["overwrite_attempt_refused"] is True
    _summary_file(tmpdir, os.path.join("verification", "exhausted"))


def test_demo_scenario_c_approval(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("C", tmpdir)
    assert r["status"] == "ok"
    assert r["sha_mismatch_refused"] is True
    assert r["approve_final_state"] == "accepted"
    assert r["reject_final_state"] == "user_stopped"
    _summary_file(tmpdir, "approval")
    approvals = json.load(open(os.path.join(tmpdir, "approval", ".pypl", "approvals.json"), encoding="utf-8"))
    results = [a["result"] for a in approvals["approvals"]]
    assert "refused" in results and "approved" in results and "rejected" in results


def test_demo_scenario_d_recovery(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("D", tmpdir)
    assert r["status"] == "ok"
    assert r["跳过已完成步骤"] is True
    assert r["persist_count_unchanged"] is True
    assert r["persist_count_before"] == 3
    assert r["final_next_action"] == "await_approval"
    _summary_file(tmpdir, "recovery")


def test_demo_scenario_e_limits(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("E", tmpdir)
    assert r["status"] == "ok"
    assert r["blocked"] is True
    assert r["stalled"] is True
    assert r["ok_control"] is True
    _summary_file(tmpdir, "limits")


def test_demo_scenario_f_guard(tmp_path):
    tmpdir = str(tmp_path)
    r = run_scenario("F", tmpdir)
    assert r["status"] == "ok"
    assert r["blocked_count"] == 4
    assert r["allowed_count"] == 2
    _summary_file(tmpdir, "guard")
    guard_log = os.path.join(tmpdir, "guard", ".pypl", "guard-log.jsonl")
    assert os.path.exists(guard_log)
    lines = [json.loads(x) for x in open(guard_log, encoding="utf-8") if x.strip()]
    assert len(lines) == 4
    assert all(l["rule"] in ("state_file_write", "trading_interface") for l in lines)
    results = [json.loads(x) for x in open(os.path.join(tmpdir, "guard", "hook-results.jsonl"), encoding="utf-8") if x.strip()]
    assert len(results) == 6


def test_demo_all_scenarios(tmp_path):
    tmpdir = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, DEMO_SCRIPT, "--all", "--offline", "--out-dir", tmpdir],
        capture_output=True, text=True, timeout=300, cwd=SCRIPT_DIR,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert "DEMO_SUMMARY" in proc.stdout
    summary_line = [l for l in proc.stdout.splitlines() if l.startswith("DEMO_SUMMARY")][0]
    statuses = json.loads(summary_line[len("DEMO_SUMMARY "):])
    assert set(statuses) == {"A", "B", "C", "D", "E", "F"}
    assert all(v == "ok" for v in statuses.values())
