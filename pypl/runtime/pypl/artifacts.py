import hashlib
import os
import json

from .state import get_state, save_request_state
from .config import REPORTS_DIR, EVIDENCE_DIR


def _sha256(content):
    if isinstance(content, str):
        data = content.encode("utf-8")
    else:
        data = content
    return hashlib.sha256(data).hexdigest()


def persist_artifact(payload):
    request_id = payload["request_id"]
    name = payload["name"]
    content = payload["content"]

    state = get_state(request_id)
    if state is None:
        raise ValueError(f"request_id not found: {request_id}")

    existing = state.get("artifacts", {}).get(name)
    new_hash = _sha256(content)

    # 幂等：同一个 request_id 和内容重复落盘时，不重复写文件
    if existing and existing.get("sha256") == new_hash:
        return {"path": existing["path"], "sha256": new_hash, "written": False}

    if name == "candidate_report":
        filename = f"report-{request_id}-r{state['round']}.md"
        directory = REPORTS_DIR
    elif name == "evidence_bundle":
        filename = f"evidence-{request_id}-r{state['round']}.json"
        directory = EVIDENCE_DIR
    elif name == "sec_facts":
        filename = f"sec_facts-{request_id}-r{state['round']}.json"
        directory = EVIDENCE_DIR
    else:
        raise ValueError(f"unknown artifact name: {name}")

    _ensure_dir(directory)
    path = os.path.join(directory, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    if "artifacts" not in state:
        state["artifacts"] = {}
    state["artifacts"][name] = {"path": path, "sha256": new_hash}
    save_request_state(request_id, state)

    return {"path": path, "sha256": new_hash, "written": True}


def verify_hash(payload):
    path = payload["path"]
    expected = payload["expected_sha256"]
    if not os.path.exists(path):
        return {"matched": False, "actual_sha256": None}
    with open(path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    return {"matched": actual == expected, "actual_sha256": actual}


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
