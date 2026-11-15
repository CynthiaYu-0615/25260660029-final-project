from datetime import datetime, timezone

from .config import MAX_TOOL_CALLS, MAX_DURATION_SECONDS


def check_limits(payload):
    tool_calls = payload.get("tool_calls", 0)
    start_time_str = payload.get("start_time", "")

    try:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    except Exception:
        start_time = datetime.now(timezone.utc)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    if tool_calls >= MAX_TOOL_CALLS:
        return {
            "next_state": "blocked",
            "reason": f"工具调用次数超过 {MAX_TOOL_CALLS} 次",
        }

    if elapsed >= MAX_DURATION_SECONDS:
        return {
            "next_state": "stalled",
            "reason": f"单次运行超过 {MAX_DURATION_SECONDS // 60} 分钟",
        }

    return {"next_state": "ok", "reason": ""}
