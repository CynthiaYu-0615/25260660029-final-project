from .state import get_state, save_request_state
from .config import MAX_ROUNDS


def record_review(payload):
    request_id = payload["request_id"]
    round_passed = payload.get("round_passed", False)
    issues = payload.get("issues", [])
    candidate_changed = payload.get("candidate_changed", False)

    state = get_state(request_id)
    if state is None:
        raise ValueError(f"request_id not found: {request_id}")

    # 候选报告改动后，连续通过轮次清零
    if candidate_changed:
        state["consecutive_passes"] = 0

    if round_passed and not issues:
        state["consecutive_passes"] = state.get("consecutive_passes", 0) + 1
    else:
        state["consecutive_passes"] = 0

    # 保存问题项
    existing_issues = state.get("issues", [])
    for issue in issues:
        if issue.get("issue_id") not in {i.get("issue_id") for i in existing_issues}:
            existing_issues.append(issue)
    state["issues"] = existing_issues

    consecutive = state.get("consecutive_passes", 0)
    current_round = state.get("round", 0)

    # 决定 next_action
    if round_passed and not issues and consecutive >= 2:
        next_action = "await_approval"
    elif round_passed and not issues:
        next_action = "review_again"
    elif not round_passed and current_round + 1 >= MAX_ROUNDS:
        next_action = "final"
    else:
        next_action = "revise"

    # 修订时增加 round
    if next_action == "revise":
        state["round"] = current_round + 1

    state["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    save_request_state(request_id, state)

    result = {
        "next_action": next_action,
        "consecutive_passes": state["consecutive_passes"],
        "round": state["round"],
        "issues": [i.get("issue_id") for i in state["issues"]],
    }

    if next_action == "revise":
        result["fix_task"] = {
            "request_id": request_id,
            "round": state["round"],
            "issues": state["issues"],
        }
    elif next_action == "final":
        result["final_state"] = "exhausted"
        result["final_reason"] = f"达到最大修订轮数 {MAX_ROUNDS} 仍未通过"
    elif next_action == "await_approval":
        result["final_state"] = "accepted"
        result["final_reason"] = "连续两轮通过且无未解决问题项"

    return result
