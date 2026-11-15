"""人工批准（record_approval）。

await_approval 之后由用户决定归档与否。批准记录写入 .pypl/approvals.json
（追加日志）；decision=approve 且 sha256 与当前候选报告一致时写终态
accepted，decision=reject 写 user_stopped。sha256 不一致时拒绝批准，
只记拒绝原因，不写终态。
"""

from .state import get_state, write_final_state, _now, _read_json, _write_json
from .config import APPROVALS_FILE


def _append_approval(record):
    data = _read_json(APPROVALS_FILE)
    if "approvals" not in data:
        data["approvals"] = []
    record["approval_id"] = f"apv-{len(data['approvals']) + 1:03d}"
    record["recorded_at"] = _now()
    data["approvals"].append(record)
    _write_json(APPROVALS_FILE, data)
    return record["approval_id"]


def record_approval(payload):
    request_id = payload["request_id"]
    decision = payload.get("decision")
    approver = payload.get("approver", "unknown")
    sha256 = payload.get("sha256")

    if decision not in ("approve", "reject"):
        raise ValueError("decision 必须是 approve 或 reject")

    state = get_state(request_id)
    if state is None:
        raise ValueError(f"request_id not found: {request_id}")

    candidate = state.get("artifacts", {}).get("candidate_report") or {}
    expected_sha = candidate.get("sha256")

    # 核对 sha256：与当前候选报告不一致则拒绝，不写终态
    if not expected_sha or sha256 != expected_sha:
        approval_id = _append_approval({
            "request_id": request_id,
            "decision": decision,
            "approver": approver,
            "sha256": sha256,
            "result": "refused",
            "reason": "sha256 与当前候选报告不一致，拒绝批准",
        })
        return {
            "approved": False,
            "approval_id": approval_id,
            "reason": "sha256 与当前候选报告不一致，拒绝批准",
        }

    if state.get("final_state"):
        # 已处于终态时不重复写
        approval_id = _append_approval({
            "request_id": request_id,
            "decision": decision,
            "approver": approver,
            "sha256": sha256,
            "result": "refused",
            "reason": f"请求已处于终态 {state['final_state']}",
        })
        return {
            "approved": False,
            "approval_id": approval_id,
            "reason": f"请求已处于终态 {state['final_state']}",
        }

    if decision == "approve":
        final = write_final_state({
            "request_id": request_id,
            "final_state": "accepted",
            "final_reason": f"用户 {approver} 批准归档",
        })
        result = "approved"
    else:
        final = write_final_state({
            "request_id": request_id,
            "final_state": "user_stopped",
            "final_reason": f"用户 {approver} 拒绝归档",
        })
        result = "rejected"

    approval_id = _append_approval({
        "request_id": request_id,
        "decision": decision,
        "approver": approver,
        "sha256": sha256,
        "result": result,
    })
    return {
        "approved": decision == "approve",
        "approval_id": approval_id,
        "final_state": final["final_state"],
        "final_reason": final["final_reason"],
    }
