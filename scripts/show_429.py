"""把一次 429 的原始响应打出来，看清楚服务端到底回了什么。

跑：uv run python scripts\\show_429.py
"""
import json
import time

import httpx

from eval_lab.faults import start_server

srv = start_server(8792)
time.sleep(0.3)
base = "http://127.0.0.1:8792"

try:
    r = httpx.post(
        f"{base}/v1/chat/completions",
        headers={"authorization": "Bearer dummy"},
        json={
            "model": "fault-429",
            "messages": [{"role": "user", "content": "你好"}],
        },
        timeout=5,
    )
    print("HTTP 状态码 :", r.status_code, r.reason_phrase)
    print("响应头      :", dict(r.headers))
    print("响应体      :", r.text)

    r2 = httpx.post(
        f"{base}/v1/chat/completions",
        headers={"authorization": "Bearer dummy"},
        json={"model": "fault-ok", "messages": [{"role": "user", "content": "你好"}]},
        timeout=5,
    )
    print("\n对照：正常时状态码 =", r2.status_code)
    print("对照：正常时 body 前 120 字 =", r2.text[:120])
finally:
    srv.shutdown()
