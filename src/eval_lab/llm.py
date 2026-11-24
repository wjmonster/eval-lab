"""统一的 LLM 调用封装：多 provider、超时、429 重试退避、结构化落库。

设计原则（这一段是给你面试讲的）：
1. 每次调用都落一条记录 —— 没有记录就没有评测，跑完就忘等于没跑。
2. 重试只重试"可重试"的错误（超时/限流/5xx），不重试 400 参数错误。
3. 所有输出都要走 parse_json_lenient —— 模型给的 JSON 永远不保证是合法 JSON。
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any

import httpx
import openai
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import CALLS_LOG, PROVIDERS, estimate_cost_cny

load_dotenv()

# 一次进程 = 一个 run_id。之前写成每条记录各自生成，导致同一批的 10 条记录 run_id 全不一样，
# 事后根本无法把"同一次运行"过滤出来（2026-11-24 D4 自检发现）。
_RUN_ID = uuid.uuid4().hex[:8]

RETRYABLE = (
    httpx.TimeoutException,
    httpx.TransportError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


def retry_after_seconds(exc: BaseException) -> float | None:
    """服务端说了 Retry-After 就听它的——自己瞎猜的退避可能比它短，重试还是 429。"""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    raw = resp.headers.get("retry-after") if hasattr(resp, "headers") else None
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


@dataclass
class CallRecord:
    case_id: str
    provider: str
    model: str
    prompt_version: str
    temperature: float
    max_tokens: int
    prompt: str
    output: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_cny: float
    attempts: int
    finish_reason: str
    error: str = ""
    ts: float = field(default_factory=time.time)
    run_id: str = field(default_factory=lambda: _RUN_ID)
    retry_waits_s: list[float] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _log(rec: CallRecord) -> None:
    with CALLS_LOG.open("a", encoding="utf-8") as f:
        f.write(rec.to_json() + "\n")


def _mock_call(prompt: str, delay: float = 0.0) -> tuple[str, int, int, str]:
    """不花钱的假模型：让整条链路（超时/落库/统计）在没 key 时也能验证。"""
    if delay:
        time.sleep(delay)
    out = (
        "这是 mock 回复。示例结构化输出：\n"
        '```json\n{"score": 1, "violations": [], "evidence": "示例依据"}\n```'
    )
    return out, len(prompt) // 2, len(out) // 2, "stop"


def call_llm(
    provider: str,
    prompt: str,
    *,
    case_id: str = "",
    prompt_version: str = "v1",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout_s: float = 60.0,
    max_attempts: int = 4,
    budget_s: float = 120.0,
    model_override: str | None = None,
    mock_delay: float = 0.0,
) -> CallRecord:
    if provider not in PROVIDERS:
        raise ValueError(f"未知 provider: {provider}，可选 {list(PROVIDERS)}")

    cfg = PROVIDERS[provider]
    model = model_override or cfg["model"]
    case_id = case_id or f"adhoc-{uuid.uuid4().hex[:6]}"

    if provider == "mock":
        t0 = time.time()
        try:
            out, tin, tout, finish = _mock_call(prompt, delay=mock_delay)
            if mock_delay > timeout_s:
                raise httpx.ReadTimeout("mock 超时")
            rec = CallRecord(
                case_id=case_id, provider=provider, model=model,
                prompt_version=prompt_version, temperature=temperature,
                max_tokens=max_tokens, prompt=prompt, output=out,
                input_tokens=tin, output_tokens=tout,
                latency_ms=int((time.time() - t0) * 1000),
                cost_cny=0.0, attempts=1, finish_reason=finish,
            )
        except httpx.TimeoutException as e:
            rec = CallRecord(
                case_id=case_id, provider=provider, model=model,
                prompt_version=prompt_version, temperature=temperature,
                max_tokens=max_tokens, prompt=prompt, output="",
                input_tokens=0, output_tokens=0,
                latency_ms=int((time.time() - t0) * 1000),
                cost_cny=0.0, attempts=1, finish_reason="error", error=type(e).__name__,
            )
        _log(rec)
        return rec

    api_key = os.getenv(cfg["key_env"], "")
    if not api_key:
        raise RuntimeError(f"{provider} 缺少环境变量 {cfg['key_env']}（先填 .env，或用 --providers mock）")

    client = OpenAI(base_url=cfg["base_url"], api_key=api_key, timeout=timeout_s, max_retries=0)
    t0 = time.time()
    attempts = 0
    waits: list[float] = []

    def _wait(retry_state) -> float:
        # 指数退避 + 抖动是下限；服务端给了 Retry-After 就取两者较大值
        base = wait_exponential_jitter(initial=1, max=20)(retry_state)
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        ra = retry_after_seconds(exc) if exc else None
        if ra is not None:
            base = max(base, ra)
        waits.append(round(base, 2))
        return base

    def _stop(retry_state) -> bool:
        # 两个出口：次数用完，或总耗时超预算（别让一个死请求拖住整批）
        if retry_state.attempt_number >= max_attempts:
            return True
        return (time.time() - t0) > budget_s

    @retry(
        retry=retry_if_exception_type(RETRYABLE),
        stop=_stop,
        wait=_wait,
        reraise=True,
    )
    def _do() -> Any:
        nonlocal attempts
        attempts += 1
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    try:
        resp = _do()
        text = resp.choices[0].message.content or ""
        tin, tout = resp.usage.prompt_tokens, resp.usage.completion_tokens
        rec = CallRecord(
            case_id=case_id, provider=provider, model=model,
            prompt_version=prompt_version, temperature=temperature,
            max_tokens=max_tokens, prompt=prompt, output=text,
            input_tokens=tin, output_tokens=tout,
            latency_ms=int((time.time() - t0) * 1000),
            cost_cny=estimate_cost_cny(model, tin, tout),
            attempts=attempts, finish_reason=resp.choices[0].finish_reason or "",
            retry_waits_s=waits,
        )
    except Exception as e:  # 真实调用失败也要落库，否则你永远不知道失败率
        rec = CallRecord(
            case_id=case_id, provider=provider, model=model,
            prompt_version=prompt_version, temperature=temperature,
            max_tokens=max_tokens, prompt=prompt, output="",
            input_tokens=0, output_tokens=0,
            latency_ms=int((time.time() - t0) * 1000),
            cost_cny=0.0, attempts=attempts, finish_reason="error",
            error=f"{type(e).__name__}: {str(e)[:120]}",
            retry_waits_s=waits,
        )
    _log(rec)
    return rec


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json_lenient(text: str) -> tuple[bool, Any]:
    """模型输出永远不保证是合法 JSON。三层兜底：直接解析 → 剥代码围栏 → 截取首个 {...}。"""
    for candidate in (text, *(m.group(1) for m in _FENCE.finditer(text))):
        try:
            return True, json.loads(candidate)
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        frag = text[start : end + 1]
        for cand in (frag, frag.replace("'", '"')):
            try:
                return True, json.loads(cand)
            except json.JSONDecodeError:
                pass
    return False, None
