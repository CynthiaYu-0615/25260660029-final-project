"""控制器单元测试。

所有测试使用临时 .pypl 目录，运行结束后清理。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPL_SCRIPT = os.path.join(SCRIPT_DIR, "scripts", "pypl.py")
RUNTIME_DIR = os.path.join(SCRIPT_DIR, "runtime")
if RUNTIME_DIR not in sys.path:
    sys.path.insert(0, RUNTIME_DIR)

from pypl import fetch as sec_fetch  # noqa: E402

FIXTURE_PATH = os.path.join(SCRIPT_DIR, "tests", "fixtures", "sec_xbrl_sample.json")
with open(FIXTURE_PATH, encoding="utf-8") as _f:
    SEC_FIXTURE = json.load(_f)


def _fake_fetcher(fixture):
    """按概念返回 fixtures 内容；未收录的概念模拟 404。"""

    def fake(url, timeout=None):
        concept = url.rstrip("/").rsplit("/", 1)[-1].replace(".json", "")
        if concept not in fixture:
            raise RuntimeError(f"HTTP 404: {url}")
        return fixture[concept]

    return fake


def _no_sleep(_seconds):
    return None


def run_cmd(subcommand, payload, cwd=None):
    proc = subprocess.run(
        [sys.executable, PYPL_SCRIPT, subcommand],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cmd {subcommand} failed: {proc.stderr}")
    return json.loads(proc.stdout)


def setup_module():
    pass


def _init(tmpdir):
    res = run_cmd("init", {"workspace": "."}, cwd=tmpdir)
    assert res["status"] == "ok"
    return tmpdir


def test_persist_artifact_idempotent(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    payload = {"request_id": rid, "name": "candidate_report", "content": "# report\n"}
    r1 = run_cmd("persist_artifact", payload, cwd=tmpdir)
    r2 = run_cmd("persist_artifact", payload, cwd=tmpdir)

    assert r1["status"] == "ok"
    assert r2["status"] == "ok"
    assert r1["data"]["sha256"] == r2["data"]["sha256"]
    # 幂等：第二次不应重复写
    assert r2["data"].get("written") is False


def test_verify_hash_detects_tampering(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    payload = {"request_id": rid, "name": "candidate_report", "content": "# report\n"}
    r1 = run_cmd("persist_artifact", payload, cwd=tmpdir)
    path = r1["data"]["path"]
    expected = r1["data"]["sha256"]

    # 篡改文件
    with open(os.path.join(tmpdir, path), "a", encoding="utf-8") as f:
        f.write("tampered")

    verify = run_cmd("verify_hash", {"path": path, "expected_sha256": expected}, cwd=tmpdir)
    assert verify["data"]["matched"] is False


def test_candidate_changed_resets_consecutive_passes(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    # 第一轮通过
    r1 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [], "candidate_changed": False}, cwd=tmpdir)
    assert r1["data"]["consecutive_passes"] == 1

    # 候选改变，通过清零
    r2 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [], "candidate_changed": True}, cwd=tmpdir)
    assert r2["data"]["consecutive_passes"] == 1


def test_two_consecutive_passes_await_approval(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    r1 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [], "candidate_changed": False}, cwd=tmpdir)
    assert r1["data"]["next_action"] == "review_again"

    r2 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [], "candidate_changed": False}, cwd=tmpdir)
    assert r2["data"]["next_action"] == "await_approval"


def test_exhausted_after_three_rounds(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    issue = {
        "issue_id": "issue-001",
        "severity": "major",
        "dimension": "evidence",
        "location": "...",
        "description": "...",
        "fix_requirement": "...",
        "created_by": "critic-evidence",
        "status": "open",
        "round_created": 1,
    }

    # round 0 -> revise
    a = run_cmd("record_review", {"request_id": rid, "round_passed": False, "issues": [issue], "candidate_changed": False}, cwd=tmpdir)
    assert a["data"]["next_action"] == "revise"
    # round 1 -> revise
    b = run_cmd("record_review", {"request_id": rid, "round_passed": False, "issues": [issue], "candidate_changed": False}, cwd=tmpdir)
    assert b["data"]["next_action"] == "revise"
    # round 2 -> final (exhausted)
    c = run_cmd("record_review", {"request_id": rid, "round_passed": False, "issues": [issue], "candidate_changed": False}, cwd=tmpdir)
    assert c["data"]["next_action"] == "final"
    assert c["data"]["final_state"] == "exhausted"


def test_final_state_not_overwritten(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    run_cmd("write_final_state", {"request_id": rid, "final_state": "accepted", "final_reason": "approved"}, cwd=tmpdir)
    run_cmd("write_final_state", {"request_id": rid, "final_state": "rejected", "final_reason": "should not overwrite"}, cwd=tmpdir)

    recover = run_cmd("recover", {"request_id": rid}, cwd=tmpdir)
    assert recover["data"]["phase"] == "final"


def test_recover_skips_completed_steps(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    req = run_cmd("new_request", {"trigger": "manual", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    rid = req["data"]["request_id"]

    run_cmd("advance_phase", {"request_id": rid, "phase": "reviewing", "round": 0}, cwd=tmpdir)
    recover = run_cmd("recover", {"request_id": rid}, cwd=tmpdir)

    assert "preparing" in recover["data"]["completed_steps"]
    assert "generating" in recover["data"]["completed_steps"]
    assert "reviewing" in recover["data"]["next_steps"]


def test_gate_report_blocks_buy_instruction(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = "## 标题\n## 信息截止至 2026-11-15\n## 结论\n增持\n## 理由\n1. a\n2. b\n3. c\n## 持仓含义\n...\n## 风险提示\n...\n## 数据来源\n...\n建议买入"
    res = run_cmd("gate_report", {"report_text": report, "evidence_text": "{}", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    assert res["data"]["passed"] is False
    assert any("买入" in f for f in res["data"]["failures"])


def test_gate_report_blocks_as_of_leak(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = "## 标题\n## 信息截止至 2026-11-20\n## 结论\n增持\n## 理由\n1. a\n2. b\n3. c\n## 持仓含义\n...\n## 风险提示\n...\n## 数据来源\n..."
    res = run_cmd("gate_report", {"report_text": report, "evidence_text": "{}", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    assert res["data"]["passed"] is False
    assert any("as-of" in f.lower() for f in res["data"]["failures"])


def test_gate_report_blocks_invalid_conclusion(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = "## 标题\n## 信息截止至 2026-11-15\n## 结论\n再看看\n## 理由\n1. a\n2. b\n3. c\n## 持仓含义\n...\n## 风险提示\n...\n## 数据来源\n..."
    res = run_cmd("gate_report", {"report_text": report, "evidence_text": "{}", "as_of": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    assert res["data"]["passed"] is False
    assert any("结论" in f for f in res["data"]["failures"])


def test_check_limits_blocks_tool_count(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    res = run_cmd("check_limits", {"tool_calls": 60, "start_time": "2026-11-15T09:00:00+08:00"}, cwd=tmpdir)
    assert res["data"]["next_state"] == "blocked"


def test_check_limits_stalls_duration(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    start = (datetime.now(timezone.utc) - timedelta(minutes=21)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    res = run_cmd("check_limits", {"tool_calls": 0, "start_time": start}, cwd=tmpdir)
    assert res["data"]["next_state"] == "stalled"


def test_fetch_sec_selects_latest_quarter():
    res = sec_fetch.fetch_sec(
        {"as_of": "2026-11-15"},
        fetcher=_fake_fetcher(SEC_FIXTURE),
        sleeper=_no_sleep,
    )
    assert res["status"] == "ok"
    data = res["data"]
    assert data["recorded"] is False
    facts = data["facts"]
    # 取 10-Q 单季数据，忽略同期间的 8-K 条目
    assert facts["revenues"]["value"] == 8584000000
    assert facts["revenues"]["unit"] == "USD"
    assert facts["revenues"]["start"] == "2026-07-01"
    assert facts["revenues"]["end"] == "2026-09-30"
    assert facts["revenues"]["form"] == "10-Q"
    assert facts["revenues"]["filed"] == "2026-10-27"
    assert facts["revenues"]["accession"] == "0001633917-26-000087"
    assert facts["net_income"]["value"] == 1073000000
    assert facts["diluted_eps"]["value"] == 1.25
    assert "data.sec.gov" in facts["revenues"]["source_url"]


def test_fetch_sec_rejects_non_whitelisted_domain():
    raised = False
    try:
        sec_fetch.default_fetcher("https://evil.example.com/secret", timeout=1)
    except sec_fetch.FetchError as e:
        raised = True
        assert "白名单" in str(e)
    assert raised, "非白名单域名必须被拒绝"


def test_fetch_sec_as_of_returns_previous_period():
    # as_of 早于 Q3 的 filed(2026-10-27)，必须退回 Q2，防止未来信息泄露
    res = sec_fetch.fetch_sec(
        {"as_of": "2026-10-01"},
        fetcher=_fake_fetcher(SEC_FIXTURE),
        sleeper=_no_sleep,
    )
    assert res["status"] == "ok"
    facts = res["data"]["facts"]
    assert facts["revenues"]["end"] == "2026-06-30"
    assert facts["revenues"]["filed"] == "2026-07-28"
    assert facts["revenues"]["value"] == 8617000000
    # 未来的 2026Q4 条目（filed 2027-02-02）绝不能被选中
    assert facts["revenues"]["end"] != "2026-12-31"


def test_fetch_sec_error_never_silently_uses_recorded():
    def boom(url, timeout=None):
        raise RuntimeError("network down")

    res = sec_fetch.fetch_sec({"as_of": "2026-11-15"}, fetcher=boom, sleeper=_no_sleep)
    assert res["status"] == "error"
    assert "未使用录制数据" in res["error"]
    assert res.get("data", {}).get("recorded") is not True

    # 显式 allow_recorded=true 才允许退到录制数据，且必须标 recorded=true
    res2 = sec_fetch.fetch_sec(
        {"as_of": "2026-11-15", "allow_recorded": True}, fetcher=boom, sleeper=_no_sleep
    )
    assert res2["status"] == "ok"
    assert res2["data"]["recorded"] is True
    assert res2["data"]["facts"]["revenues"]["value"] == 8584000000


def _report_with_key_figures(revenues_musd):
    return (
        "## 标题\n"
        "## 信息截止至 2026-11-15\n"
        "## 结论：持有不动\n"
        "## 理由\n"
        "1. 理由第一条内容足够长\n"
        "2. 理由第二条内容足够长\n"
        "3. 理由第三条内容足够长\n"
        "## 持仓含义\n结合当前持仓说明\n"
        "## 风险提示\n存在风险提示\n"
        "## 数据来源\n```json\n"
        + json.dumps(
            {
                "key_figures": {
                    "revenues": {"value": revenues_musd, "unit": "million USD", "period_end": "2026-09-30"},
                    "net_income": {"value": 1073, "unit": "million USD", "period_end": "2026-09-30"},
                    "diluted_eps": {"value": 1.25, "unit": "USD", "period_end": "2026-09-30"},
                }
            },
            ensure_ascii=False,
        )
        + "\n```"
    )


def _sec_facts_payload():
    return {
        "facts": {
            "revenues": {"value": 8584000000, "unit": "USD"},
            "net_income": {"value": 1073000000, "unit": "USD"},
            "diluted_eps": {"value": 1.25, "unit": "USD"},
        }
    }


def test_gate_report_numeric_match_passes(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = _report_with_key_figures(8584)
    res = run_cmd(
        "gate_report",
        {
            "report_text": report,
            "evidence_text": "{}",
            "as_of": "2026-11-15T09:00:00+08:00",
            "sec_facts": _sec_facts_payload(),
        },
        cwd=tmpdir,
    )
    assert res["data"]["passed"] is True, res["data"]["failures"]


def test_gate_report_numeric_mismatch_blocked(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = _report_with_key_figures(9999)
    res = run_cmd(
        "gate_report",
        {
            "report_text": report,
            "evidence_text": "{}",
            "as_of": "2026-11-15T09:00:00+08:00",
            "sec_facts": _sec_facts_payload(),
        },
        cwd=tmpdir,
    )
    assert res["data"]["passed"] is False
    assert any("numeric_mismatch" in f and "收入" in f for f in res["data"]["failures"])


def test_gate_report_missing_key_figures_blocked(tmp_path):
    tmpdir = str(tmp_path)
    _init(tmpdir)
    report = (
        "## 标题\n## 信息截止至 2026-11-15\n## 结论：持有不动\n## 理由\n"
        "1. 理由第一条内容足够长\n2. 理由第二条内容足够长\n3. 理由第三条内容足够长\n"
        "## 持仓含义\n结合当前持仓说明\n## 风险提示\n存在风险提示\n## 数据来源\n无代码块"
    )
    res = run_cmd(
        "gate_report",
        {
            "report_text": report,
            "evidence_text": "{}",
            "as_of": "2026-11-15T09:00:00+08:00",
            "sec_facts": _sec_facts_payload(),
        },
        cwd=tmpdir,
    )
    assert res["data"]["passed"] is False
    assert any("key_figures" in f for f in res["data"]["failures"])
