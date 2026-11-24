"""D3：把 429 / 超时 / 5xx / 坏 JSON 打到**真实 HTTP + 重试链路**上验证。

为什么不能在内存里假装抛异常：
  simulate.py 里 `raise RateLimitError(...)` 验证的是 tenacity 的配置，
  不是"httpx 收到 429 时 openai 客户端抛什么异常、我们的 RETRYABLE 认不认、
  退避到底等了多久"。只有让请求真的落到 socket 上，这些才成立。

做法：本地起一个 OpenAI 兼容的故障服务器（同一个进程里的后台线程），
按 model 名字决定行为：

  fault-ok        200 正常响应
  fault-429       永远 429，带 Retry-After: 2
  fault-flaky-N   前 N 次 429，第 N+1 次成功（用来证明"重试几次后成功"）
  fault-slow      睡 3 秒再回 200（配 --timeout 1 就是真超时）
  fault-500       永远 500
  fault-badjson   200，但 body 不是合法 JSON

跑：uv run eval-lab faults
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REQUESTS: list[dict] = []
_COUNTER: dict[str, int] = {}
_LOCK = threading.Lock()


def _payload(model: str, content: str) -> bytes:
    return json.dumps(
        {
            "id": "chatcmpl-fault",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
        ensure_ascii=False,
    ).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # 安静点，别刷屏
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json", extra: dict | None = None):
        try:
            self.send_response(status)
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # 客户端超时先断了，这是本场景的预期行为，不是错误
            self.close_connection = True

    def handle_one_request(self):  # 别让断连把服务端日志刷满堆栈
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) or b"{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        model = str(payload.get("model", "fault-ok"))

        with _LOCK:
            _COUNTER[model] = _COUNTER.get(model, 0) + 1
            nth = _COUNTER[model]
            REQUESTS.append({"t": time.time(), "model": model, "nth": nth})

        if model.startswith("fault-slow"):
            time.sleep(3.0)
            return self._send(200, _payload(model, "慢响应到达"))

        if model.startswith("fault-429"):
            return self._send(
                429,
                json.dumps({"error": {"message": "rate limited", "type": "rate_limit_exceeded"}}).encode(),
                extra={"retry-after": "2"},
            )

        if model.startswith("fault-flaky"):
            limit = int(model.rsplit("-", 1)[-1])
            if nth <= limit:
                return self._send(
                    429,
                    json.dumps({"error": {"message": "flaky", "type": "rate_limit_exceeded"}}).encode(),
                    extra={"retry-after": "1"},
                )
            return self._send(200, _payload(model, f"第 {nth} 次请求成功"))

        if model.startswith("fault-500"):
            return self._send(500, json.dumps({"error": {"message": "boom"}}).encode())

        if model.startswith("fault-badjson"):
            return self._send(200, b"{this is not json at all", ctype="application/json")

        return self._send(200, _payload(model, "正常响应"))


def start_server(port: int = 8791) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def gaps_for(model: str) -> list[float]:
    """服务端视角看：同一 model 相邻两次请求的间隔（秒），这就是真实退避。"""
    ts = [r["t"] for r in REQUESTS if r["model"] == model]
    return [round(b - a, 2) for a, b in zip(ts, ts[1:])]


def gaps_since(start: int, model: str) -> list[float]:
    """只算本次场景（从 start 下标之后）的请求间隔，避免上一个场景的残留混进来。"""
    ts = [r["t"] for r in REQUESTS[start:] if r["model"] == model]
    return [round(b - a, 2) for a, b in zip(ts, ts[1:])]


def counter_of(model: str) -> int:
    return _COUNTER.get(model, 0)


def run_probe(port: int = 8791) -> int:
    """把六个场景逐个打到真实 HTTP 链路上，输出一张"期望 vs 实际"的表。"""
    import statistics

    from rich.console import Console
    from rich.table import Table

    from .config import RESULTS_DIR
    from .llm import call_llm

    console = Console()
    srv = start_server(port)
    time.sleep(0.3)
    console.print(f"[bold]D3 故障注入验证[/bold]　服务器 127.0.0.1:{port}（进程内线程）\n")

    cases = [
        # 标签, model, timeout_s, budget_s, 期望说明
        ("正常 200", "fault-ok", 5.0, 30.0, "一次成功，attempts=1"),
        ("前 2 次 429 后成功", "fault-flaky-2", 5.0, 60.0, "attempts=3，最终拿到内容"),
        ("持续 429", "fault-429", 5.0, 60.0, "重试到上限，落库 error"),
        ("真超时 3s vs 1s 上限", "fault-slow", 1.0, 30.0, "每次 1s 断开，重试后仍失败"),
        ("持续 500", "fault-500", 5.0, 60.0, "重试到上限，落库 error"),
        ("200 但 body 不是 JSON", "fault-badjson", 5.0, 30.0, "不崩，落库 error"),
        ("真超时 + 预算 5s 截断", "fault-slow", 1.0, 5.0, "预算先到，attempts<4"),
    ]

    table = Table(show_lines=False)
    for col in ("场景", "attempts", "客户端等待(s)", "服务端请求间隔(s)", "耗时(s)", "结果"):
        table.add_column(col, overflow="fold")

    rows_out = []
    for label, model, timeout_s, budget_s, expect in cases:
        t0 = time.time()
        start_idx = len(REQUESTS)
        rec = call_llm(
            "fault",
            "D3 故障注入",
            case_id=f"d3-{model}",
            timeout_s=timeout_s,
            budget_s=budget_s,
            model_override=model,
        )
        elapsed = round(time.time() - t0, 2)
        gaps = gaps_since(start_idx, model)
        rows_out.append(
            {
                "场景": label,
                "model": model,
                "期望": expect,
                "attempts": rec.attempts,
                "客户端等待": rec.retry_waits_s,
                "服务端间隔": gaps,
                "耗时_s": elapsed,
                "finish_reason": rec.finish_reason,
                "error": rec.error,
                "output": rec.output,
            }
        )
        result = rec.output or rec.error or "(空)"
        table.add_row(
            label,
            str(rec.attempts),
            str(rec.retry_waits_s),
            str(gaps),
            str(elapsed),
            result[:70],
        )

    console.print(table)

    # 判定：把"期望"翻译成布尔条件，别靠眼看一下
    checks = [
        rows_out[0]["attempts"] == 1 and rows_out[0]["output"] != "",
        rows_out[1]["attempts"] == 3 and rows_out[1]["output"] != "",
        rows_out[2]["attempts"] >= 2 and rows_out[2]["error"] != "",
        rows_out[3]["attempts"] >= 2 and "Timeout" in rows_out[3]["error"],
        rows_out[4]["attempts"] >= 2 and rows_out[4]["error"] != "",
        rows_out[5]["error"] != "" and rows_out[5]["output"] == "",
        rows_out[6]["attempts"] < 4 and rows_out[6]["error"] != "",
    ]
    console.print()
    for label, ok in zip([c[0] for c in cases], checks):
        console.print(f"  {label}: {'[green]PASS[/green]' if ok else '[red]FAIL[/red]'}")

    waits = rows_out[2]["客户端等待"]
    if waits:
        console.print(
            f"\n[bold]关键数字[/bold]：持续 429 时，客户端实际等了 {waits}，"
            f"服务端收到的相邻间隔是 {rows_out[2]['服务端间隔']}（Retry-After=2s）"
        )

    out_path = RESULTS_DIR / "d3_faults.json"
    out_path.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[dim]明细写入 {out_path}[/dim]")

    srv.shutdown()
    total = sum(1 for ok in checks if not ok)
    console.print(f"\n[bold]{'全部通过' if total == 0 else f'{total} 项未通过'}[/bold]")
    return 0 if total == 0 else 1
