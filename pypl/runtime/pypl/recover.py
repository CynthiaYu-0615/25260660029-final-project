from .state import get_state


def recover(payload):
    request_id = payload["request_id"]
    state = get_state(request_id)
    if state is None:
        raise ValueError(f"request_id not found: {request_id}")

    phase = state.get("phase", "preparing")
    round_num = state.get("round", 0)
    artifacts = state.get("artifacts", {})
    issues = state.get("issues", [])
    consecutive_passes = state.get("consecutive_passes", 0)

    # 根据阶段确定已完成和未完成的步骤
    all_steps = ["preparing", "generating", "reviewing", "revising", "archiving", "final"]
    completed = []
    next_steps = []

    if phase == "final" or state.get("final_state"):
        completed = all_steps[:]
        next_steps = []
    else:
        try:
            idx = all_steps.index(phase)
            completed = all_steps[:idx]
            next_steps = all_steps[idx:]
        except ValueError:
            next_steps = all_steps

    return {
        "phase": phase,
        "round": round_num,
        "artifacts": artifacts,
        "issues": [i.get("issue_id") for i in issues],
        "consecutive_passes": consecutive_passes,
        "completed_steps": completed,
        "next_steps": next_steps,
    }
