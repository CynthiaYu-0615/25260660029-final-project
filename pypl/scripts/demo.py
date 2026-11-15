#!/usr/bin/env python3
"""核验与恢复证据的演示脚本（不依赖 LLM，只用标准库）。

用「假 agent 返回值」驱动真实的控制器（pypl/scripts/pypl.py）和真实的
安全钩子（pypl/hooks/pre_tool_use.py），把 Orchestrator 的流程跑出真实
的状态文件和日志。每个场景在独立临时工作目录里运行，结束后由本脚本用
Python（shutil，不用 Bash cp——hook 会拦涉及 .pypl/ 的 cp）把状态快照和
日志拷到 evidence/ 对应子目录。

日志（.pypl/demo-log.jsonl）每行带：时间戳、git 提交号、request_id、
场景、步骤、子命令、输入输出 JSON。

用法：
    python3 pypl/scripts/demo.py --scenario A|B|C|D|E|F|all [--offline] [--out-dir DIR]
    python3 pypl/scripts/demo.py --child <workspace>        # 内部：场景 D 的子进程
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYPL_SCRIPT = os.path.join(REPO_ROOT, "pypl", "scripts", "pypl.py")
HOOK_SCRIPT = os.path.join(REPO_ROOT, "pypl", "hooks", "pre_tool_use.py")

SCENARIO_DIRS = {
    "A": os.path.join("verification", "blocked-then-pass"),
    "B": os.path.join("verification", "exhausted"),
    "C": "approval",
    "D": "recovery",
    "E": "limits",
    "F": "guard",
}

_GIT_CACHE = None


def git_commit():
    global _GIT_CACHE
    if _GIT_CACHE is None:
        try:
            out = subprocess.run(
                ["git", "-C", REPO_ROOT, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            _GIT_CACHE = out.stdout.strip() or "unknown"
        except Exception:
            _GIT_CACHE = "unknown"
    return _GIT_CACHE


def _clip(value, limit=400):
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


class Logger:
    """把每一步的输入输出写成 JSONL 证据日志。"""

    def __init__(self, workspace, scenario):
        self.path = os.path.join(workspace, ".pypl", "demo-log.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.scenario = scenario

    def log(self, step, cmd, req_id=None, input_data=None, output_data=None):
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "git": git_commit(),
            "scenario": self.scenario,
            "request_id": req_id,
            "step": step,
            "cmd": cmd,
            "input": _clip(json.dumps(input_data, ensure_ascii=False, default=str)),
            "output": _clip(json.dumps(output_data, ensure_ascii=False, default=str), 800),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_cmd(subcommand, payload, workspace, logger=None, step=None, req_id=None):
    proc = subprocess.run(
        [sys.executable, PYPL_SCRIPT, subcommand],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True,
        cwd=workspace, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{subcommand} 失败: {proc.stderr}")
    result = json.loads(proc.stdout)
    if logger is not None:
        logger.log(step or subcommand, subcommand, req_id, payload, result)
    return result


def today_str():
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fetch_sec_for_demo(workspace, logger, req_id, offline):
    payload = {"as_of": today_str(), "allow_recorded": True}
    if offline:
        payload["prefer_recorded"] = True
    res = run_cmd("fetch_sec", payload, workspace, logger, "取财报数字(fetch_sec)", req_id)
    if res["status"] != "ok":
        raise RuntimeError(f"fetch_sec 失败: {res.get('error')}")
    return res["data"]


def sec_facts_payload(sec_data):
    return {"facts": sec_data["facts"], "as_of": sec_data.get("as_of"),
            "recorded": sec_data.get("recorded")}


def key_figures_from_sec_facts(sec_data, eps_wrong=False):
    facts = sec_data["facts"]
    eps = facts["diluted_eps"]["value"]
    if eps_wrong:
        eps = round(eps * 1.2, 2)  # 故意写错的 EPS
    return {
        "key_figures": {
            "revenues": {
                "value": facts["revenues"]["value"] / 1_000_000,
                "unit": "million USD",
                "period_start": facts["revenues"]["start"],
                "period_end": facts["revenues"]["end"],
            },
            "net_income": {
                "value": facts["net_income"]["value"] / 1_000_000,
                "unit": "million USD",
                "period_start": facts["net_income"]["start"],
                "period_end": facts["net_income"]["end"],
            },
            "diluted_eps": {
                "value": eps,
                "unit": "USD",
                "period_start": facts["diluted_eps"]["start"],
                "period_end": facts["diluted_eps"]["end"],
            },
        }
    }


def build_report(sec_data, with_buy=False, eps_wrong=False, extra=""):
    kf = key_figures_from_sec_facts(sec_data, eps_wrong=eps_wrong)
    buy_line = "综合以上，建议买入 PYPL。\n" if with_buy else ""
    return (
        f"## 标题\nPYPL 研究报告（演示{extra}）\n"
        f"## 信息截止至 {today_str()}\n"
        "## 结论：持有不动\n"
        "## 理由\n"
        "1. 财报核心数字与 sec_facts 一致，收入利润符合预期\n"
        "2. 估值处于合理区间，无重大催化剂\n"
        "3. 近期新闻无重大事件，维持观望\n"
        "## 持仓含义\n结合当前持仓，维持现有仓位不加不减\n"
        "## 风险提示\n支付行业竞争加剧，转型执行存在不确定性\n"
        "## 数据来源\nSEC XBRL（fetch_sec）、Datasource 实测来源\n"
        "```json\n" + json.dumps(kf, ensure_ascii=False) + "\n```\n" + buy_line
    )


MAJOR_ISSUE = {
    "issue_id": "issue-demo-001",
    "severity": "major",
    "dimension": "evidence",
    "location": "报告第 3 节",
    "description": "（假 Critic）理由第 2 条缺少来源标注",
    "fix_requirement": "补充来源 URL 和获取时间",
    "created_by": "critic-evidence",
    "status": "open",
    "round_created": 1,
}


def _init_request(workspace, logger, trigger="manual", init=True):
    # init 会重建 .pypl/ 下的文件（含 approvals.json），同一工作区第二次
    # 起请求时不能重复 init，否则清掉前一个请求的证据
    if init or not os.path.exists(os.path.join(workspace, ".pypl", "state.json")):
        run_cmd("init", {"workspace": "."}, workspace, logger, "初始化工作区")
    res = run_cmd("new_request", {"trigger": trigger, "as_of": now_iso()},
                  workspace, logger, "新建请求")
    return res["data"]["request_id"]


def _copy_evidence(workspace, out_subdir, summary):
    # 快照目录不叫 .pypl/（.gitignore 会忽略任何 .pypl/ 目录），
    # 用 pypl-snapshot/ 保证证据可以入库
    os.makedirs(out_subdir, exist_ok=True)
    src_pypl = os.path.join(workspace, ".pypl")
    dst_pypl = os.path.join(out_subdir, "pypl-snapshot")
    if os.path.exists(dst_pypl):
        shutil.rmtree(dst_pypl)
    shutil.copytree(src_pypl, dst_pypl)
    with open(os.path.join(out_subdir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def scenario_a(out_dir, offline):
    """核验拦截：v1 被 gate 拦下，v2 送审被打回，v3 连续两轮通过。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_a_")
    logger = Logger(ws, "A")
    summary = {}
    try:
        rid = _init_request(ws, logger)
        sec_data = fetch_sec_for_demo(ws, logger, rid, offline)
        run_cmd("persist_artifact", {"request_id": rid, "name": "sec_facts",
                                     "content": json.dumps(sec_data, ensure_ascii=False)},
                ws, logger, "落盘 sec_facts", rid)

        # v1：含「建议买入」且 EPS 写错 → gate 拦截
        v1 = build_report(sec_data, with_buy=True, eps_wrong=True, extra=" v1")
        g1 = run_cmd("gate_report", {"report_text": v1, "evidence_text": "{}",
                                     "as_of": now_iso(), "sec_facts": sec_facts_payload(sec_data)},
                     ws, logger, "gate 拦截 v1", rid)
        gate_v1_blocked = g1["data"]["passed"] is False
        has_buy = any("买入" in x for x in g1["data"]["failures"])
        has_numeric = any("numeric_mismatch" in x for x in g1["data"]["failures"])

        # v2：修好 → gate 通过；假 Critic 提 major → revise
        v2 = build_report(sec_data, extra=" v2")
        p2 = run_cmd("persist_artifact", {"request_id": rid, "name": "candidate_report", "content": v2},
                     ws, logger, "落盘候选 v2", rid)
        g2 = run_cmd("gate_report", {"report_text": v2, "evidence_text": "{}",
                                     "as_of": now_iso(), "sec_facts": sec_facts_payload(sec_data)},
                     ws, logger, "gate 通过 v2", rid)
        r2 = run_cmd("record_review", {"request_id": rid, "round_passed": False,
                                       "issues": [dict(MAJOR_ISSUE, round_created=1)],
                                       "candidate_changed": True},
                     ws, logger, "假 Critic 打回 v2", rid)
        revised = r2["data"]["next_action"] == "revise"

        # v3：修好 → 连续两轮通过 → await_approval
        v3 = build_report(sec_data, extra=" v3（已修复）")
        run_cmd("persist_artifact", {"request_id": rid, "name": "candidate_report", "content": v3},
                ws, logger, "落盘候选 v3", rid)
        g3 = run_cmd("gate_report", {"report_text": v3, "evidence_text": "{}",
                                     "as_of": now_iso(), "sec_facts": sec_facts_payload(sec_data)},
                     ws, logger, "gate 通过 v3", rid)
        r3a = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [],
                                        "candidate_changed": True},
                      ws, logger, "Critic 通过（第 1 轮）", rid)
        r3b = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [],
                                        "candidate_changed": False},
                      ws, logger, "Critic 通过（第 2 轮）", rid)
        final = r3b["data"]["next_action"]

        summary = {
            "scenario": "A 核验拦截（blocked-then-pass）",
            "gate_v1_blocked": gate_v1_blocked,
            "v1_含买入指令被拦": has_buy,
            "v1_EPS错误numeric_mismatch": has_numeric,
            "gate_v2_passed": g2["data"]["passed"],
            "v2_revise": revised,
            "gate_v3_passed": g3["data"]["passed"],
            "final_next_action": final,
            "status": "ok" if (gate_v1_blocked and has_buy and has_numeric and revised
                               and final == "await_approval" and g3["data"]["passed"]) else "mismatch",
        }
        return summary
    finally:
        _copy_evidence(ws, os.path.join(out_dir, SCENARIO_DIRS["A"]), summary)
        shutil.rmtree(ws, ignore_errors=True)


def scenario_b(out_dir, offline):
    """修订上限：3 轮不过 → exhausted；覆盖终态被拒绝。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_b_")
    logger = Logger(ws, "B")
    summary = {}
    try:
        rid = _init_request(ws, logger)
        report = (
            f"## 标题\nPYPL 研究报告（演示 B）\n## 信息截止至 {today_str()}\n"
            "## 结论\n持有不动\n## 理由\n"
            "1. 理由第一条内容足够长，支撑结论\n"
            "2. 理由第二条内容足够长，支撑结论\n"
            "3. 理由第三条内容足够长，支撑结论\n"
            "## 持仓含义\n维持现有仓位\n## 风险提示\n转型风险\n## 数据来源\n演示\n"
        )
        run_cmd("persist_artifact", {"request_id": rid, "name": "candidate_report", "content": report},
                ws, logger, "落盘候选 v1", rid)
        actions = []
        for i in range(3):
            r = run_cmd("record_review", {"request_id": rid, "round_passed": False,
                                          "issues": [dict(MAJOR_ISSUE, issue_id=f"issue-b-{i}")],
                                          "candidate_changed": False},
                        ws, logger, f"假 Critic 第 {i + 1} 轮不通过", rid)
            actions.append(r["data"]["next_action"])
        f1 = run_cmd("write_final_state", {"request_id": rid, "final_state": "exhausted",
                                           "final_reason": "达到最大修订轮数 3 仍未通过"},
                     ws, logger, "写终态 exhausted", rid)
        f2 = run_cmd("write_final_state", {"request_id": rid, "final_state": "accepted",
                                           "final_reason": "尝试非法覆盖终态"},
                     ws, logger, "尝试覆盖终态（应被拒绝）", rid)
        overwrite_refused = (f2["data"]["final_state"] == "exhausted"
                             and f2["data"]["final_reason"] == f1["data"]["final_reason"])
        summary = {
            "scenario": "B 修订上限（exhausted）",
            "next_actions": actions,
            "final_state": f1["data"]["final_state"],
            "exhausted_not_accepted": f1["data"]["final_state"] == "exhausted",
            "overwrite_attempt_refused": overwrite_refused,
            "status": "ok" if (actions == ["revise", "revise", "final"] and overwrite_refused) else "mismatch",
        }
        return summary
    finally:
        _copy_evidence(ws, os.path.join(out_dir, SCENARIO_DIRS["B"]), summary)
        shutil.rmtree(ws, ignore_errors=True)


def scenario_c(out_dir, offline):
    """人工批准：approve → accepted；reject → user_stopped；sha256 不符拒绝。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_c_")
    logger = Logger(ws, "C")
    summary = {}
    try:
        # 第一次请求：approve
        rid1 = _init_request(ws, logger)
        sec_data = fetch_sec_for_demo(ws, logger, rid1, offline)
        run_cmd("persist_artifact", {"request_id": rid1, "name": "sec_facts",
                                     "content": json.dumps(sec_data, ensure_ascii=False)},
                ws, logger, "落盘 sec_facts", rid1)
        v1 = build_report(sec_data, extra=" C1")
        p1 = run_cmd("persist_artifact", {"request_id": rid1, "name": "candidate_report", "content": v1},
                     ws, logger, "落盘候选", rid1)
        sha = p1["data"]["sha256"]
        run_cmd("gate_report", {"report_text": v1, "evidence_text": "{}",
                                "as_of": now_iso(), "sec_facts": sec_facts_payload(sec_data)},
                ws, logger, "gate 通过", rid1)
        run_cmd("record_review", {"request_id": rid1, "round_passed": True, "issues": [],
                                  "candidate_changed": True},
                ws, logger, "Critic 通过（第 1 轮）", rid1)
        run_cmd("record_review", {"request_id": rid1, "round_passed": True, "issues": [],
                                  "candidate_changed": False},
                ws, logger, "Critic 通过（第 2 轮）", rid1)
        bad = run_cmd("record_approval", {"request_id": rid1, "decision": "approve",
                                          "approver": "于欣荷", "sha256": "0" * 64},
                      ws, logger, "错误 sha256 批准（应被拒绝）", rid1)
        ok = run_cmd("record_approval", {"request_id": rid1, "decision": "approve",
                                         "approver": "于欣荷", "sha256": sha},
                     ws, logger, "批准归档", rid1)

        # 第二次请求：reject（同一工作区，不再 init，保留第一次的批准记录）
        rid2 = _init_request(ws, logger, init=False)
        v2 = build_report(sec_data, extra=" C2")
        p2 = run_cmd("persist_artifact", {"request_id": rid2, "name": "candidate_report", "content": v2},
                     ws, logger, "落盘候选", rid2)
        sha2 = p2["data"]["sha256"]
        run_cmd("record_review", {"request_id": rid2, "round_passed": True, "issues": [],
                                  "candidate_changed": True},
                ws, logger, "Critic 通过（第 1 轮）", rid2)
        run_cmd("record_review", {"request_id": rid2, "round_passed": True, "issues": [],
                                  "candidate_changed": False},
                ws, logger, "Critic 通过（第 2 轮）", rid2)
        rej = run_cmd("record_approval", {"request_id": rid2, "decision": "reject",
                                          "approver": "于欣荷", "sha256": sha2},
                      ws, logger, "拒绝归档", rid2)

        summary = {
            "scenario": "C 人工批准（approval）",
            "sha_mismatch_refused": bad["data"]["approved"] is False,
            "approve_final_state": ok["data"].get("final_state"),
            "reject_final_state": rej["data"].get("final_state"),
            "status": "ok" if (bad["data"]["approved"] is False
                               and ok["data"].get("final_state") == "accepted"
                               and rej["data"].get("final_state") == "user_stopped") else "mismatch",
        }
        return summary
    finally:
        _copy_evidence(ws, os.path.join(out_dir, SCENARIO_DIRS["C"]), summary)
        shutil.rmtree(ws, ignore_errors=True)


def _child_main(workspace, offline):
    """场景 D 的子进程：persist 完成后写标记再长睡，等待被 kill。"""
    logger = Logger(workspace, "D")
    rid = _init_request(workspace, logger)
    sec_data = fetch_sec_for_demo(workspace, logger, rid, offline)
    run_cmd("persist_artifact", {"request_id": rid, "name": "sec_facts",
                                 "content": json.dumps(sec_data, ensure_ascii=False)},
            workspace, logger, "落盘 sec_facts", rid)
    v1 = build_report(sec_data, extra=" D")
    run_cmd("persist_artifact", {"request_id": rid, "name": "candidate_report", "content": v1},
            workspace, logger, "落盘候选", rid)
    run_cmd("persist_artifact", {"request_id": rid, "name": "evidence_bundle", "content": "{}"},
            workspace, logger, "落盘证据包", rid)
    run_cmd("advance_phase", {"request_id": rid, "phase": "reviewing", "round": 0},
            workspace, logger, "进入 reviewing", rid)
    marker = os.path.join(workspace, ".pypl", "child-marker.json")
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"request_id": rid, "time": now_iso()}, f)
    time.sleep(120)  # 等待父进程 kill
    return rid


def _count_persist_calls(workspace):
    log_path = os.path.join(workspace, ".pypl", "demo-log.jsonl")
    count = 0
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("cmd") == "persist_artifact":
                        count += 1
                except Exception:
                    pass
    return count


def scenario_d(out_dir, offline):
    """中断恢复：persist 后 kill 子进程，recover 后只执行剩余步骤。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_d_")
    os.makedirs(os.path.join(ws, ".pypl"), exist_ok=True)
    logger = Logger(ws, "D-parent")
    summary = {}
    try:
        child = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--child", ws]
            + (["--offline"] if offline else []),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        marker = os.path.join(ws, ".pypl", "child-marker.json")
        deadline = time.time() + 60
        while not os.path.exists(marker) and time.time() < deadline:
            if child.poll() is not None:
                raise RuntimeError("子进程提前退出")
            time.sleep(0.2)
        if not os.path.exists(marker):
            child.kill()
            raise RuntimeError("等待子进程标记超时")
        rid = json.load(open(marker, encoding="utf-8"))["request_id"]
        child.kill()
        child.wait()
        logger.log("kill 子进程（persist 之后、record_review 之前）", "kill", rid)

        count_before = _count_persist_calls(ws)
        rec = run_cmd("recover", {"request_id": rid}, ws, logger, "恢复：跳过已完成步骤", rid)
        completed = rec["data"]["completed_steps"]
        next_steps = rec["data"]["next_steps"]

        # 续跑：只执行没做完的步骤（不重新 persist）
        run_cmd("verify_hash", {"request_id": rid, "path": rec["data"]["artifacts"]["candidate_report"]["path"],
                                "expected_sha256": rec["data"]["artifacts"]["candidate_report"]["sha256"]},
                ws, logger, "核对候选哈希", rid)
        r1 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [],
                                       "candidate_changed": False},
                     ws, logger, "Critic 通过（第 1 轮）", rid)
        r2 = run_cmd("record_review", {"request_id": rid, "round_passed": True, "issues": [],
                                       "candidate_changed": False},
                     ws, logger, "Critic 通过（第 2 轮）", rid)
        count_after = _count_persist_calls(ws)

        summary = {
            "scenario": "D 中断恢复（recovery）",
            "killed_after": "persist_artifact 完成后、record_review 之前",
            "completed_steps": completed,
            "next_steps_after_recover": next_steps,
            "跳过已完成步骤": "generating" in completed,
            "persist_count_before": count_before,
            "persist_count_after": count_after,
            "persist_count_unchanged": count_before == count_after,
            "final_next_action": r2["data"]["next_action"],
            "status": "ok" if ("generating" in completed and count_before == count_after
                               and r2["data"]["next_action"] == "await_approval") else "mismatch",
        }
        return summary
    finally:
        _copy_evidence(ws, os.path.join(out_dir, SCENARIO_DIRS["D"]), summary)
        shutil.rmtree(ws, ignore_errors=True)


def scenario_e(out_dir, offline):
    """限制触发：超 60 次工具调用 blocked；超 20 分钟 stalled。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_e_")
    os.makedirs(os.path.join(ws, ".pypl"), exist_ok=True)
    logger = Logger(ws, "E")
    summary = {}
    try:
        now = datetime.now(timezone.utc)
        r_blocked = run_cmd("check_limits",
                            {"tool_calls": 61, "start_time": now.isoformat()},
                            ws, logger, "工具调用超 60 次")
        r_stalled = run_cmd("check_limits",
                            {"tool_calls": 10,
                             "start_time": (now - timedelta(minutes=21)).isoformat()},
                            ws, logger, "注入时钟：运行超 20 分钟")
        r_ok = run_cmd("check_limits",
                       {"tool_calls": 10, "start_time": now.isoformat()},
                       ws, logger, "正常范围对照")
        summary = {
            "scenario": "E 限制触发（limits）",
            "blocked": r_blocked["data"]["next_state"] == "blocked",
            "stalled": r_stalled["data"]["next_state"] == "stalled",
            "ok_control": r_ok["data"]["next_state"] == "ok",
            "status": "ok" if (r_blocked["data"]["next_state"] == "blocked"
                               and r_stalled["data"]["next_state"] == "stalled"
                               and r_ok["data"]["next_state"] == "ok") else "mismatch",
        }
        return summary
    finally:
        _copy_evidence(ws, os.path.join(out_dir, SCENARIO_DIRS["E"]), summary)
        shutil.rmtree(ws, ignore_errors=True)


def scenario_f(out_dir, offline):
    """hook 拦截：典型被拦输入与放行对照，保留 guard-log.jsonl 证据。"""
    ws = tempfile.mkdtemp(prefix="pypl_demo_f_")
    os.makedirs(os.path.join(ws, ".pypl"), exist_ok=True)
    logger = Logger(ws, "F")
    summary = {}
    cases = [
        ("blocked-write-state", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                                 "tool_input": {"path": ".pypl/state.json", "content": "{}"}}),
        ("blocked-dotdot", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                            "tool_input": {"path": "notes/../.pypl/holdings.json", "content": "{}"}}),
        ("blocked-bash-redirect", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                   "tool_input": {"command": "echo '{\"a\":1}' > .pypl/state.json"}}),
        ("blocked-alpaca-orders", {"hook_event_name": "PreToolUse", "tool_name": "FetchURL",
                                   "tool_input": {"url": "https://api.alpaca.markets/v2/orders"}}),
        ("allowed-sec", {"hook_event_name": "PreToolUse", "tool_name": "FetchURL",
                         "tool_input": {"url": "https://data.sec.gov/api/xbrl/companyconcept/CIK0001633917/us-gaap/Revenues.json"}}),
        ("allowed-git", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                         "tool_input": {"command": "git status"}}),
    ]
    results = []
    try:
        for label, payload in cases:
            proc = subprocess.run(
                [sys.executable, HOOK_SCRIPT],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, cwd=ws, timeout=10,
            )
            results.append({
                "label": label,
                "exit_code": proc.returncode,
                "stderr": proc.stderr.strip(),
                "verdict": "blocked" if proc.returncode == 2 else "allowed",
            })
            logger.log(f"hook 用例 {label}", "hook", None, payload,
                       {"exit_code": proc.returncode, "stderr": proc.stderr.strip()})
        blocked = [r for r in results if r["verdict"] == "blocked"]
        allowed = [r for r in results if r["verdict"] == "allowed"]
        summary = {
            "scenario": "F hook 拦截（guard）",
            "blocked_count": len(blocked),
            "allowed_count": len(allowed),
            "results": results,
            "status": "ok" if (len(blocked) == 4 and len(allowed) == 2) else "mismatch",
        }
        with open(os.path.join(ws, "hook-results.jsonl"), "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return summary
    finally:
        out_sub = os.path.join(out_dir, SCENARIO_DIRS["F"])
        _copy_evidence(ws, out_sub, summary)
        src = os.path.join(ws, "hook-results.jsonl")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_sub, "hook-results.jsonl"))
        shutil.rmtree(ws, ignore_errors=True)


SCENARIOS = {"A": scenario_a, "B": scenario_b, "C": scenario_c,
             "D": scenario_d, "E": scenario_e, "F": scenario_f}


def main():
    parser = argparse.ArgumentParser(description="PYPL 核验与恢复证据演示脚本")
    parser.add_argument("--scenario", choices=list(SCENARIOS) + ["all"], default=None)
    parser.add_argument("--all", action="store_true", help="运行全部场景 A-F")
    parser.add_argument("--offline", action="store_true",
                        help="fetch_sec 直接使用录制数据，不联网")
    parser.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "evidence"))
    parser.add_argument("--child", metavar="WORKSPACE", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.child:
        _child_main(args.child, args.offline)
        return

    chosen = "all" if args.all else (args.scenario or "all")

    names = list(SCENARIOS) if chosen == "all" else [chosen]
    results = {}
    overall_ok = True
    for name in names:
        print(f"[demo] 运行场景 {name} …", flush=True)
        summary = SCENARIOS[name](args.out_dir, args.offline)
        results[name] = summary
        overall_ok = overall_ok and summary.get("status") == "ok"
        print("SCENARIO_RESULT " + json.dumps(summary, ensure_ascii=False), flush=True)
    print("DEMO_SUMMARY " + json.dumps(
        {k: v.get("status") for k, v in results.items()}, ensure_ascii=False), flush=True)
    if not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
