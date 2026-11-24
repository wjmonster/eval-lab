"""把 D5 的 9 环节风险图渲染成 PNG（用 mermaid.ink，必须带浏览器 UA，否则 403）。

用法：uv run python scripts\render_risk_map.py
产物：docs\risk-map.png
"""
from __future__ import annotations

import base64
import time
import urllib.request
from pathlib import Path

CODE = """flowchart TD
  N1["1 输入预处理<br/>无清洗 无截断 无注入检测"] --> N2["2 意图路由<br/>项目无此环节"]
  N2 --> N3["3 查询改写<br/>项目无此环节"]
  N3 --> N4["4 召回<br/>项目无 RAG"]
  N4 --> N5["5 重排<br/>项目无此环节"]
  N5 --> N6["6 上下文拼装<br/>只存 prompt 不存 messages"]
  N6 --> N7["7 生成<br/>17 字段 + 10 用例 9/10"]
  N7 --> N8["8 工具调用<br/>测了生成 没测执行"]
  N8 --> N9["9 输出渲染<br/>无引用校验 无敏感词"]
  N9 -.-> N12["12 成本与并发预算（挂在第 7、8 环）<br/>5 秒预算实跑 6.97 秒"]
  classDef green fill:#d7f5d7,stroke:#2e7d32,color:#1b5e20
  classDef orange fill:#ffe8c2,stroke:#e65100,color:#bf360c
  classDef red fill:#ffd9d9,stroke:#c62828,color:#8e0000
  class N7 green
  class N6,N8,N12 orange
  class N1,N2,N3,N4,N5,N9 red
"""

OUT = Path(__file__).resolve().parents[1] / "docs" / "risk-map.png"


def main() -> int:
    b64 = base64.urlsafe_b64encode(CODE.encode("utf-8")).decode()
    url = "https://mermaid.ink/img/" + b64
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/png,image/jpeg,*/*",
        },
    )
    # mermaid.ink 对连续请求会返回 503（限流），必须退避重试
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            data = urllib.request.urlopen(req, timeout=30).read()
            OUT.write_bytes(data)
            print(f"已写入 {OUT}（{len(data)} 字节，第 {attempt} 次尝试成功）")
            print(f"可复现的渲染地址：{url}")
            return 0
        except Exception as e:  # 503 / 超时都重试
            last_exc = e
            wait = 5 * attempt
            print(f"第 {attempt} 次失败：{type(e).__name__} {e}，等 {wait}s 再试")
            time.sleep(wait)
    raise SystemExit(f"5 次都失败，最后一次：{last_exc}")


if __name__ == "__main__":
    raise SystemExit(main())
