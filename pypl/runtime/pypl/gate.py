import json
import os
import re
from datetime import datetime

# gate 规则配置文件（evo 流程的评估对象）；可用 payload["rules"] 覆盖（evo 对比候选规则时用）
_DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "references", "gate_rules.json"
)

_FALLBACK_RULES = {
    "version": "fallback",
    "forbidden_words": ["买入", "卖出", "下单"],
    "numeric_tolerance": 0.005,
    "min_reasons": 3,
}


def _load_rules(payload):
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if isinstance(rules, dict) and rules:
        return rules
    try:
        with open(_DEFAULT_RULES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(_FALLBACK_RULES)


# key_figures 与 sec_facts 单位换算表（统一换算到基础单位后比较）
_UNIT_FACTOR = {
    "USD": 1.0,
    "USD/share": 1.0,
    "USD/shares": 1.0,
    "USD per share": 1.0,
    "million USD": 1_000_000.0,
    "百万美元": 1_000_000.0,
}


def _find_section(text, pattern):
    # 简单查找包含关键词的行
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def _count_reasons(text):
    # 粗略计算"理由"部分条目数，以"1."、"2." 或 "-" 开头
    reasons = re.findall(r"(?:^|\n)\s*(?:\d+\.|-)\s+(.{10,})", text)
    return len(reasons)


def _extract_key_figures(report):
    # 报告中必须包含一个含 key_figures 字段的 json 代码块
    for m in re.finditer(r"```json\s*(.*?)```", report, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("key_figures"), dict):
            return obj["key_figures"]
    return None


def _to_base_value(entry):
    """把 {value, unit} 换算成基础单位（USD / 每股 USD）。无法换算返回 None。"""
    if not isinstance(entry, dict):
        return None
    factor = _UNIT_FACTOR.get(str(entry.get("unit", "")).strip())
    if factor is None:
        return None
    try:
        return float(entry["value"]) * factor
    except (TypeError, ValueError):
        return None


def _numeric_failures(key_figures, facts, tolerance):
    failures = []
    labels = (("收入", "revenues"), ("净利润", "net_income"), ("稀释EPS", "diluted_eps"))
    for label, key in labels:
        kf_entry = key_figures.get(key)
        fact_entry = facts.get(key)
        kf_base = _to_base_value(kf_entry)
        fact_base = _to_base_value(fact_entry)
        if kf_base is None:
            failures.append(f"numeric_mismatch: {label}的 key_figures 数值或单位无法识别: {kf_entry}")
            continue
        if fact_base is None:
            failures.append(f"numeric_mismatch: sec_facts 缺少可用的{label}: {fact_entry}")
            continue
        if abs(kf_base - fact_base) > tolerance * max(abs(kf_base), abs(fact_base)):
            failures.append(
                f"numeric_mismatch: {label}不一致（key_figures={kf_entry} vs sec_facts={fact_entry}）"
            )
    return failures


def gate_report(payload):
    report = payload.get("report_text", "")
    evidence = payload.get("evidence_text", "")
    as_of_str = payload.get("as_of", "")
    rules = _load_rules(payload)
    forbidden_words = rules.get("forbidden_words", _FALLBACK_RULES["forbidden_words"])
    tolerance = float(rules.get("numeric_tolerance", _FALLBACK_RULES["numeric_tolerance"]))
    min_reasons = int(rules.get("min_reasons", _FALLBACK_RULES["min_reasons"]))

    failures = []

    # 1. 六个部分齐全
    required_sections = ["标题", "结论", "理由", "持仓含义", "风险提示", "数据来源"]
    for sec in required_sections:
        if not _find_section(report, sec):
            failures.append(f"缺少必要的报告部分：{sec}")

    # 2. 结论是增持/减持/持有不动三选一
    conclusion_match = re.search(r"结论.*?([增持减持持有不动]+)", report)
    if conclusion_match:
        conclusion = conclusion_match.group(1)
        if conclusion not in ("增持", "减持", "持有不动"):
            failures.append("结论不是增持/减持/持有不动之一")
    else:
        failures.append("未能识别明确结论")

    # 3. 理由不少于 min_reasons 条
    if _count_reasons(report) < min_reasons:
        failures.append("理由少于三条")

    # 4. 有风险提示
    if not _find_section(report, "风险"):
        failures.append("缺少风险提示")

    # 5. 无执行性交易指令（违禁词来自 gate_rules.json）
    for word in forbidden_words:
        if word in report:
            failures.append(f"正文中出现执行性指令词：{word}")

    # 6. 封面的 as-of 不晚于请求的 as-of
    report_as_of_match = re.search(r"信息截止[至:]?\s*(\d{4}-\d{2}-\d{2})", report)
    if report_as_of_match and as_of_str:
        try:
            report_as_of = datetime.strptime(report_as_of_match.group(1), "%Y-%m-%d")
            req_as_of = datetime.fromisoformat(as_of_str.replace("Z", "+00:00"))
            if report_as_of.date() > req_as_of.date():
                failures.append("报告封面的 as-of 晚于请求 as-of")
        except Exception:
            pass

    # 7. 证据包中每条来源都有 URL 和获取时间，且获取时间不晚于 as-of
    if evidence:
        try:
            import json
            ev = json.loads(evidence) if evidence.strip().startswith("{") else {}
            data_points = ev.get("data_points", []) if isinstance(ev, dict) else []
            for dp in data_points:
                if not dp.get("source_url"):
                    failures.append("证据包中存在缺少 source_url 的数据点")
                if not dp.get("as_of"):
                    failures.append("证据包中存在缺少 as_of 的数据点")
        except Exception:
            pass

    # 8. key_figures 与 sec_facts 数值交叉核对（提供 sec_facts 时启用）
    sec_facts_raw = payload.get("sec_facts")
    if sec_facts_raw:
        if isinstance(sec_facts_raw, str):
            try:
                sec_facts_raw = json.loads(sec_facts_raw)
            except Exception:
                failures.append("numeric_mismatch: sec_facts 不是合法 JSON")
                sec_facts_raw = None
    if isinstance(sec_facts_raw, dict):
        facts = sec_facts_raw.get("facts", {})
        key_figures = _extract_key_figures(report)
        if key_figures is None:
            failures.append("缺少 key_figures JSON 块，无法与 sec_facts 做数值核对")
        else:
            failures.extend(_numeric_failures(key_figures, facts, tolerance))

    return {"passed": len(failures) == 0, "failures": failures}
