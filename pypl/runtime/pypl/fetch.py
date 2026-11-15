"""SEC XBRL 财报数字获取（确定性代码）。

对应作业要求「在适当环节用确定性代码完成计算」：财报核心数字
（收入、净利润、稀释 EPS）由控制器代码直接访问 SEC XBRL 接口取得，
不经过 agent，也不使用 Bash。

规则（与 references/rules.md 对齐）：
- 只使用 Python 标准库 urllib；只访问白名单域名 data.sec.gov / www.sec.gov；
- 请求带声明项目名与联系邮箱的 User-Agent；
- 每次请求间隔不少于 1 秒，超时 30 秒；
- 失败按单步重试 2 次、指数退避（2 秒、4 秒）；
- as-of 过滤在代码内完成：只用 form 为 10-Q/10-K 且 filed 不晚于 as_of 的条目；
- 取不到返回 error，绝不悄悄退到录制数据；仅当入参显式 allow_recorded=true
  时才允许使用 examples/input/ 的录制数据，且返回必须标 recorded=true。

网络层通过 fetcher / sleeper / clock 三个可注入依赖隔离，测试注入假实现，
默认测试不联网。
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

ALLOWED_HOSTS = frozenset({"data.sec.gov", "www.sec.gov"})
USER_AGENT = "25260660029-final-project-pypl (contact: cynthiayu615@gmail.com)"

CONCEPTS = ("Revenues", "NetIncomeLoss", "EarningsPerShareDiluted")
FACT_KEYS = {
    "Revenues": "revenues",
    "NetIncomeLoss": "net_income",
    "EarningsPerShareDiluted": "diluted_eps",
}
XBRL_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK0001633917/us-gaap/{concept}.json"

TIMEOUT_SECONDS = 30
MIN_INTERVAL_SECONDS = 1.0
MAX_ATTEMPTS = 3  # 首次 + 重试 2 次
RETRY_BACKOFF = (2.0, 4.0)  # 指数退避：第 1 次失败后 2 秒，第 2 次失败后 4 秒
QUARTER_DAYS = 92  # 约三个月

# 录制数据文件（仅 allow_recorded=true 时允许使用）
_RECORDED_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "examples", "input", "pypl-earnings-q3-2026.json",
)


class FetchError(Exception):
    """取数失败（网络错误、域名不在白名单、数据不符合预期等）。"""


def _assert_allowed(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    if host not in ALLOWED_HOSTS:
        raise FetchError(f"域名不在白名单，已拒绝访问: {host}")


def default_fetcher(url, timeout=TIMEOUT_SECONDS):
    """默认网络实现：白名单校验 + 声明 User-Agent + 超时控制。"""
    _assert_allowed(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class _RateLimiter:
    """限制相邻两次请求间隔不小于 min_interval 秒。"""

    def __init__(self, min_interval, sleeper, clock):
        self._min_interval = min_interval
        self._sleeper = sleeper
        self._clock = clock
        self._last = None

    def wait(self):
        if self._last is not None:
            gap = self._clock() - self._last
            if gap < self._min_interval:
                self._sleeper(self._min_interval - gap)
        self._last = self._clock()


def _fetch_with_retry(url, fetcher, sleeper):
    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fetcher(url, timeout=TIMEOUT_SECONDS)
        except Exception as e:  # noqa: BLE001 - 任何异常都按失败重试
            last_err = e
            if attempt < MAX_ATTEMPTS - 1:
                sleeper(RETRY_BACKOFF[attempt])
    raise FetchError(f"请求失败（含重试共 {MAX_ATTEMPTS} 次尝试）: {last_err}")


def _parse_day(s):
    return date.fromisoformat(s[:10])


def _duration_days(entry):
    start = _parse_day(entry["start"])
    end = _parse_day(entry["end"])
    return (end - start).days


def select_latest_entry(unit_entries, as_of_date):
    """在代码内完成 as-of 过滤和期间选择。

    过滤条件：form 必须是 10-Q 或 10-K；filed 不晚于 as_of。
    选择规则：取 period end 最新的一期；同一期末若有多条
    （如 10-K 年报全年数与 10-Q 单季数并存），优先取
    start→end 约三个月的单季数据。
    """
    candidates = []
    for entry in unit_entries:
        if entry.get("form") not in ("10-Q", "10-K"):
            continue
        filed = entry.get("filed")
        if not filed:
            continue
        if _parse_day(filed) > as_of_date:
            continue
        if not entry.get("start") or not entry.get("end"):
            continue
        candidates.append(entry)
    if not candidates:
        return None
    latest_end = max(e["end"] for e in candidates)
    same_end = [e for e in candidates if e["end"] == latest_end]
    same_end.sort(key=lambda e: abs(_duration_days(e) - QUARTER_DAYS))
    return same_end[0]


def _pick_unit(concept_data):
    units = concept_data.get("units")
    if not isinstance(units, dict) or not units:
        raise FetchError("XBRL 响应缺少 units")
    if "USD" in units:
        return "USD", units["USD"]
    # EPS 概念的单位通常是 USD/shares
    unit = sorted(units.keys())[0]
    return unit, units[unit]


def _load_recorded():
    """读取 examples/input/ 的录制财报数据（仅在显式允许时调用）。"""
    path = os.path.abspath(_RECORDED_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    to_million = 1_000_000
    return {
        "as_of": rec.get("as_of"),
        "retrieved_at": rec.get("retrieved_at"),
        "recorded": True,
        "recorded_from": os.path.relpath(path),
        "facts": {
            "revenues": {
                "concept": "Revenues",
                "value": rec["total_net_revenues"]["value"] * to_million,
                "unit": "USD",
                "start": None,
                "end": rec.get("as_of"),
                "accession": None,
                "form": None,
                "filed": None,
                "source_url": rec.get("source_url"),
            },
            "net_income": {
                "concept": "NetIncomeLoss",
                "value": rec["net_income"]["value"] * to_million,
                "unit": "USD",
                "start": None,
                "end": rec.get("as_of"),
                "accession": None,
                "form": None,
                "filed": None,
                "source_url": rec.get("source_url"),
            },
            "diluted_eps": {
                "concept": "EarningsPerShareDiluted",
                "value": rec["diluted_eps"]["value"],
                "unit": "USD",
                "start": None,
                "end": rec.get("as_of"),
                "accession": None,
                "form": None,
                "filed": None,
                "source_url": rec.get("source_url"),
            },
        },
    }


def fetch_sec(payload, fetcher=None, sleeper=None, clock=None):
    """取 PYPL 最近一期财报核心数字。

    入参（payload）：
    - as_of：信息截止时点（YYYY-MM-DD 或 ISO 8601），必填；
    - allow_recorded：显式为 true 时，取数失败才允许退到录制数据；
    - prefer_recorded：显式为 true 时，若录制数据存在则直接使用，
      不发网络请求（供 demo/测试离线使用；返回同样标 recorded=true）。

    依赖注入（测试用，默认真实实现）：
    - fetcher(url, timeout=...) -> dict：返回 SEC XBRL JSON；
    - sleeper(seconds)：睡眠实现（退避与限速）；
    - clock() -> float：单调时钟。
    """
    fetcher = fetcher or default_fetcher
    sleeper = sleeper or time.sleep
    clock = clock or time.monotonic

    as_of_raw = payload.get("as_of")
    if not as_of_raw:
        return {"status": "error", "error": "缺少必填入参 as_of"}
    try:
        as_of_date = _parse_day(as_of_raw)
    except ValueError:
        return {"status": "error", "error": f"as_of 格式不正确: {as_of_raw}"}
    allow_recorded = payload.get("allow_recorded") is True
    if payload.get("prefer_recorded") is True:
        recorded = _load_recorded()
        if recorded is not None:
            return {"status": "ok", "data": recorded}

    limiter = _RateLimiter(MIN_INTERVAL_SECONDS, sleeper, clock)

    facts = {}
    errors = {}
    for concept in CONCEPTS:
        url = XBRL_URL.format(concept=concept)
        try:
            limiter.wait()
            data = _fetch_with_retry(url, fetcher, sleeper)
            unit, entries = _pick_unit(data)
            entry = select_latest_entry(entries, as_of_date)
            if entry is None:
                raise FetchError(
                    f"as_of={as_of_date} 之前没有 form 为 10-Q/10-K 的 {concept} 数据"
                )
            facts[FACT_KEYS[concept]] = {
                "concept": concept,
                "value": entry["val"],
                "unit": unit,
                "start": entry["start"],
                "end": entry["end"],
                "accession": entry.get("accn"),
                "form": entry.get("form"),
                "filed": entry.get("filed"),
                "source_url": url,
            }
        except Exception as e:  # noqa: BLE001 - 单概念失败记录后继续，最后统一判定
            errors[concept] = str(e)

    if errors:
        if allow_recorded:
            recorded = _load_recorded()
            if recorded is not None:
                return {"status": "ok", "data": recorded}
        return {
            "status": "error",
            "error": f"SEC 取数失败（未使用录制数据）: {errors}",
            "data": {"errors": errors, "partial_facts": facts or None},
        }

    return {
        "status": "ok",
        "data": {
            "as_of": str(as_of_date),
            "retrieved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "recorded": False,
            "facts": facts,
        },
    }
