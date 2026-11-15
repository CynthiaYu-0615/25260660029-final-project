import re
from datetime import datetime


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


def gate_report(payload):
    report = payload.get("report_text", "")
    evidence = payload.get("evidence_text", "")
    as_of_str = payload.get("as_of", "")

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

    # 3. 理由不少于三条
    if _count_reasons(report) < 3:
        failures.append("理由少于三条")

    # 4. 有风险提示
    if not _find_section(report, "风险"):
        failures.append("缺少风险提示")

    # 5. 无执行性交易指令
    forbidden = ["买入", "卖出", "下单"]
    for word in forbidden:
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

    return {"passed": len(failures) == 0, "failures": failures}
