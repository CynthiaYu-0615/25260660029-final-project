#!/usr/bin/env python3
"""PYPL 控制器脚本入口。

所有子命令统一从 stdin 读取 JSON，将结果 JSON 输出到 stdout。
用法：
    python3 pypl/scripts/pypl.py <subcommand>
"""

import json
import os
import sys

# 将 runtime 加入模块搜索路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(SCRIPT_DIR, "..", "runtime")
sys.path.insert(0, RUNTIME_DIR)

from pypl.state import (
    init_workspace,
    new_request,
    record_trade,
    record_event,
    advance_phase,
    write_final_state,
    get_state,
)
from pypl.artifacts import persist_artifact, verify_hash
from pypl.gate import gate_report
from pypl.review import record_review
from pypl.limits import check_limits
from pypl.recover import recover
from pypl.fetch import fetch_sec


def _respond(status, data=None, error=None):
    out = {"status": status}
    if data is not None:
        out["data"] = data
    if error is not None:
        out["error"] = error
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _read_stdin():
    try:
        return json.load(sys.stdin)
    except Exception as e:
        _respond("error", error=f"无法解析 stdin JSON: {e}")
        sys.exit(1)


def cmd_init(payload):
    result = init_workspace(payload)
    _respond("ok", result)


def cmd_new_request(payload):
    result = new_request(payload)
    _respond("ok", result)


def cmd_record_trade(payload):
    result = record_trade(payload)
    _respond("ok", result)


def cmd_record_event(payload):
    result = record_event(payload)
    _respond("ok", result)


def cmd_persist_artifact(payload):
    try:
        result = persist_artifact(payload)
        _respond("ok", result)
    except ValueError as e:
        _respond("error", error=str(e))


def cmd_verify_hash(payload):
    result = verify_hash(payload)
    _respond("ok", result)


def cmd_gate_report(payload):
    result = gate_report(payload)
    _respond("ok", result)


def cmd_record_issues(payload):
    # 问题项记录直接复用 save_request_state 逻辑
    request_id = payload["request_id"]
    state = get_state(request_id)
    if state is None:
        _respond("error", error=f"request_id not found: {request_id}")
        return
    existing = state.get("issues", [])
    issue_ids = []
    for issue in payload.get("issues", []):
        if issue.get("issue_id") not in {i.get("issue_id") for i in existing}:
            existing.append(issue)
            issue_ids.append(issue["issue_id"])
    state["issues"] = existing
    from pypl.state import save_request_state

    save_request_state(request_id, state)
    _respond("ok", {"issue_ids": issue_ids})


def cmd_record_review(payload):
    try:
        result = record_review(payload)
        _respond("ok", result)
    except ValueError as e:
        _respond("error", error=str(e))


def cmd_advance_phase(payload):
    result = advance_phase(payload)
    _respond("ok", result)


def cmd_write_final_state(payload):
    try:
        result = write_final_state(payload)
        _respond("ok", result)
    except ValueError as e:
        _respond("error", error=str(e))


def cmd_check_limits(payload):
    result = check_limits(payload)
    _respond("ok", result)


def cmd_fetch_sec(payload):
    result = fetch_sec(payload)
    _respond(result["status"], data=result.get("data"), error=result.get("error"))


def cmd_recover(payload):
    try:
        result = recover(payload)
        _respond("ok", result)
    except ValueError as e:
        _respond("error", error=str(e))


def main():
    if len(sys.argv) < 2:
        _respond("error", error="缺少子命令")
        return

    subcommand = sys.argv[1]
    payload = _read_stdin()

    handlers = {
        "init": cmd_init,
        "new_request": cmd_new_request,
        "record_trade": cmd_record_trade,
        "record_event": cmd_record_event,
        "persist_artifact": cmd_persist_artifact,
        "verify_hash": cmd_verify_hash,
        "gate_report": cmd_gate_report,
        "record_issues": cmd_record_issues,
        "record_review": cmd_record_review,
        "advance_phase": cmd_advance_phase,
        "write_final_state": cmd_write_final_state,
        "check_limits": cmd_check_limits,
        "fetch_sec": cmd_fetch_sec,
        "recover": cmd_recover,
    }

    handler = handlers.get(subcommand)
    if handler is None:
        _respond("error", error=f"未知子命令: {subcommand}")
        return

    handler(payload)


if __name__ == "__main__":
    main()
