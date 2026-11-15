import json
import os
from datetime import datetime, timezone

from .config import (
    PYPL_DIR,
    STATE_FILE,
    HOLDINGS_FILE,
    EVENTS_FILE,
    ISSUES_FILE,
    REPORTS_DIR,
    EVIDENCE_DIR,
)


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def init_workspace(payload):
    """初始化 .pypl 目录结构。"""
    workspace = payload.get("workspace", ".")
    pypl = os.path.join(workspace, PYPL_DIR)
    _ensure_dir(pypl)
    _ensure_dir(os.path.join(workspace, REPORTS_DIR))
    _ensure_dir(os.path.join(workspace, EVIDENCE_DIR))

    state = {
        "requests": {},
        "updated_at": _now(),
    }
    _write_json(os.path.join(workspace, STATE_FILE), state)
    _write_json(os.path.join(workspace, HOLDINGS_FILE), {"positions": []})
    _write_json(os.path.join(workspace, EVENTS_FILE), {"events": []})
    _write_json(os.path.join(workspace, ISSUES_FILE), {"issues": []})

    return {"pypl_dir": pypl, "state_file": os.path.join(workspace, STATE_FILE)}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_state(request_id=None):
    data = _read_json(STATE_FILE)
    if request_id is None:
        return data
    return data.get("requests", {}).get(request_id)


def save_request_state(request_id, request_state):
    data = _read_json(STATE_FILE)
    if "requests" not in data:
        data["requests"] = {}
    data["requests"][request_id] = request_state
    data["updated_at"] = _now()
    _write_json(STATE_FILE, data)


def get_holdings():
    return _read_json(HOLDINGS_FILE)


def record_trade(payload):
    holdings = get_holdings()
    if "positions" not in holdings:
        holdings["positions"] = []
    position = {
        "symbol": payload.get("symbol", "PYPL"),
        "action": payload["action"],
        "quantity": payload["quantity"],
        "price": payload["price"],
        "date": payload["date"],
        "recorded_at": payload.get("recorded_at", _now()),
    }
    holdings["positions"].append(position)
    holdings["updated_at"] = _now()
    _write_json(HOLDINGS_FILE, holdings)
    return {"holding_id": f"hld-{len(holdings['positions']):03d}", "updated_file": HOLDINGS_FILE}


def record_event(payload):
    from datetime import datetime, timedelta

    earnings_date = payload["earnings_date"]
    as_of = payload.get("as_of", _now())
    events_data = _read_json(EVENTS_FILE)
    if "events" not in events_data:
        events_data["events"] = []

    base = datetime.strptime(earnings_date, "%Y-%m-%d")
    pre_date = (base - timedelta(days=2)).strftime("%Y-%m-%d")

    events = [
        {
            "event_id": f"evt-{len(events_data['events']) + 1:03d}",
            "type": "earnings_pre",
            "scheduled_date": pre_date,
            "description": "Q3 财报前两天",
            "status": "pending",
        },
        {
            "event_id": f"evt-{len(events_data['events']) + 2:03d}",
            "type": "earnings_post",
            "scheduled_date": earnings_date,
            "description": "Q3 财报发布后",
            "status": "pending",
        },
    ]
    events_data["events"].extend(events)
    _write_json(EVENTS_FILE, events_data)

    reminder_times = [
        f"{pre_date}T09:00:00+08:00",
        f"{earnings_date}T09:00:00+08:00",
    ]

    return {"events": events, "reminder_times": reminder_times, "as_of": as_of}


def new_request(payload):
    from uuid import uuid4

    trigger = payload["trigger"]
    as_of = payload.get("as_of", _now())
    request_id = f"req-{as_of[:10].replace('-', '')}-{str(uuid4())[:8]}"

    request_state = {
        "request_id": request_id,
        "trigger": trigger,
        "as_of": as_of,
        "phase": "preparing",
        "round": 0,
        "max_rounds": 3,
        "artifacts": {},
        "issues": [],
        "consecutive_passes": 0,
        "version": "v0.1.0",
        "final_state": None,
        "final_reason": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    save_request_state(request_id, request_state)
    return {"request_id": request_id, "state": request_state}


def advance_phase(payload):
    request_id = payload["request_id"]
    state = get_state(request_id)
    state["phase"] = payload.get("phase", state.get("phase"))
    state["round"] = payload.get("round", state.get("round"))
    state["updated_at"] = _now()
    save_request_state(request_id, state)
    return {"phase": state["phase"], "round": state["round"]}


def write_final_state(payload):
    request_id = payload["request_id"]
    final_state = payload["final_state"]
    final_reason = payload.get("final_reason", "")
    state = get_state(request_id)

    # 终态不可覆盖
    if state.get("final_state") in {"accepted", "rejected", "blocked", "exhausted", "stalled", "user_stopped"}:
        return {"final_state": state["final_state"], "final_reason": state.get("final_reason", "")}

    state["final_state"] = final_state
    state["final_reason"] = final_reason
    state["phase"] = "final"
    state["updated_at"] = _now()
    save_request_state(request_id, state)
    return {"final_state": final_state, "final_reason": final_reason}
