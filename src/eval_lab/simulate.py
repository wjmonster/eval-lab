"""三种故障的真实复现（不花钱、不依赖网络）。

跑：uv run eval-lab simulate
验收标准：三个场景全部 PASS，且你能说清每个场景"如果不处理会怎样"。
"""
from __future__ import annotations

import time

import httpx
from rich.console import Console
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .llm import call_llm, parse_json_lenient

console = Console()


class RateLimitError(Exception):
    """模拟 429。"""


def scenario_429() -> bool:
    state = {"n": 0}

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=0.2, max=2),
        reraise=True,
    )
    def flaky_call():
        state["n"] += 1
        if state["n"] < 3:
            raise RateLimitError("429 Too Many Requests")
        return "第三次成功"

    t0 = time.time()
    try:
        out = flaky_call()
        ok = state["n"] == 3 and out == "第三次成功"
        console.print(f"  [1] 429 重试：尝试 {state['n']} 次后成功，耗时 {time.time()-t0:.1f}s → "
                      f"{'[green]PASS[/green]' if ok else '[red]FAIL[/red]'}")
        return ok
    except Exception as e:
        console.print(f"  [1] 429 重试：重试耗尽 → [red]FAIL {type(e).__name__}[/red]")
        return False


def scenario_timeout() -> bool:
    # mock provider 睡 2 秒，但只给 0.5 秒超时
    rec = call_llm("mock", "这个请求会超时", case_id="sim-timeout", timeout_s=0.5, mock_delay=2.0)
    ok = rec.finish_reason == "error" and rec.error
    console.print(f"  [2] 超时：finish_reason={rec.finish_reason}, error={rec.error or '无'} → "
                  f"{'[green]PASS[/green]' if ok else '[red]FAIL[/red]'}")
    return bool(ok)


def scenario_bad_json() -> bool:
    cases = {
        "代码围栏包裹": '好的，结果如下：\n```json\n{"score": 1, "violations": []}\n```\n希望有帮助。',
        "前后有废话": '根据我的分析，{"score": 0.5, "violations": ["缺引用"]} 以上就是结论。',
        "单引号": "{'score': 0, 'violations': ['违反禁止项']}",
        "彻底离谱": "抱歉我无法回答这个问题。",
    }
    expect_ok = {"代码围栏包裹": True, "前后有废话": True, "单引号": True, "彻底离谱": False}
    all_ok = True
    for name, text in cases.items():
        ok, obj = parse_json_lenient(text)
        hit = ok == expect_ok[name]
        all_ok &= hit
        console.print(f"      - {name}: parsed={ok}, obj={obj if ok else 'None'} → "
                      f"{'[green]OK[/green]' if hit else '[red]异常[/red]'}")
    console.print(f"  [3] 非法 JSON 兜底：{'[green]PASS[/green]' if all_ok else '[red]FAIL[/red]'}")
    return all_ok


def run_all() -> int:
    console.print("[bold]故障复现（D3 验收）[/bold]")
    results = [scenario_429(), scenario_timeout(), scenario_bad_json()]
    console.print()
    console.print("[bold]结论：[/bold]")
    console.print("  1) 429 不重试 → 高峰期整批用例失败，你会误判成模型变差")
    console.print("  2) 超时不设上限 → 一个卡死的调用拖住整个并发批次")
    console.print("  3) 不兜底 JSON → 评测直接崩在解析上，而不是给出'分数'")
    return 0 if all(results) else 1
