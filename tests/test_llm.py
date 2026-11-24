"""W1 冒烟测试：不需要 API key，全走 mock。"""
from __future__ import annotations

import json

from eval_lab.config import CALLS_LOG
from eval_lab.llm import call_llm, parse_json_lenient


def test_mock_call_records_everything():
    n_before = sum(1 for _ in CALLS_LOG.open(encoding="utf-8")) if CALLS_LOG.exists() else 0
    rec = call_llm("mock", "测试落库", case_id="T-001")
    assert rec.case_id == "T-001"
    assert rec.provider == "mock"
    assert rec.output, "mock 必须返回内容"
    assert rec.latency_ms >= 0
    assert rec.finish_reason == "stop"
    n_after = sum(1 for _ in CALLS_LOG.open(encoding="utf-8"))
    assert n_after == n_before + 1, "每次调用必须落一条记录"

    last = CALLS_LOG.open(encoding="utf-8").readlines()[-1]
    obj = json.loads(last)
    for key in ("case_id", "model", "prompt_version", "input_tokens", "output_tokens", "cost_cny", "ts", "run_id"):
        assert key in obj, f"缺字段 {key}"


def test_timeout_is_recorded_not_raised():
    rec = call_llm("mock", "超时", case_id="T-002", timeout_s=0.3, mock_delay=1.0)
    assert rec.finish_reason == "error"
    assert rec.error
    assert rec.output == ""


def test_parse_json_lenient():
    assert parse_json_lenient('{"a":1}') == (True, {"a": 1})
    assert parse_json_lenient('```json\n{"a":1}\n```')[0] is True
    assert parse_json_lenient('前缀 {"a":1} 后缀')[0] is True
    ok, obj = parse_json_lenient("完全不是 JSON")
    assert ok is False and obj is None
