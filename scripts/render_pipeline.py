"""渲染"真实链路图"：只画 eval-lab 里真实存在的节点，每个节点标行号 + 真实踩过的坑。

用法：uv run python scripts\render_pipeline.py
产物：docs\pipeline-real.png
和 render_risk_map.py 的区别：那张是模板 9 环对标，这张是本项目真实链路。
"""
from __future__ import annotations

import base64
import time
import urllib.request
from pathlib import Path

# 颜色约定：绿=已守住 ｜ 橙=踩过坑但还没解决 ｜ 红=踩过坑且已改
CODE = """flowchart TD
  C1["① 命令行参数 argparse<br/>cli.py:100-121"] --> C2["② 参数清洗 split / strip / 过滤空串<br/>cli.py:29"]
  C2 --> C3["③ 循环 provider × repeat，先跑完一家再跑下一家<br/>cli.py:32<br/>【待办】D2 实测：全串行，无并发"]
  C3 --> C4["④ 查注册表 base_url / model / key_env<br/>config.py:15"]
  C4 --> C5["⑤ 取 key<br/>llm.py:144<br/>【已守】D2：DeepSeek 空 key 抛 RuntimeError，跳过这家"]
  C5 --> C6["⑥ 发请求（内嵌重试）<br/>llm.py:178 请求本体 ｜ 153 _wait ｜ 163 _stop ｜ 175 _do<br/>【待办】D3：429 首等 2.00s；5 秒预算实跑 6.97 秒"]
  C6 --> C7["⑦ 读 usage / finish_reason<br/>llm.py:187-188"]
  C7 --> C8["⑧ 建 17 字段记录<br/>llm.py:189 成功 ｜ 200 失败<br/>【已修】D4：run_id 原本每条都不同"]
  C8 --> C9["⑨ 追加写 jsonl，只追加不覆盖<br/>llm.py:85<br/>【已守】D3 反例：except 写窄则失败不落库"]
  C9 --> C10["⑩ 打两张表：明细 cli.py:57 ｜ 汇总 cli.py:71<br/>【待办】D4：_truncate 只截显示，落库仍是原文"]
  C6 -. "旁路" .-> P1["parse_json_lenient 三档降级<br/>llm.py:214 失败返回 False 不抛"]
  classDef green fill:#d7f5d7,stroke:#2e7d32,color:#1b5e20
  classDef orange fill:#ffe8c2,stroke:#e65100,color:#bf360c
  class C1,C2,C4,C5,C7,C8,C9,P1 green
  class C3,C6,C10 orange
"""

OUT = Path(__file__).resolve().parents[1] / "docs" / "pipeline-real.png"


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
    last: Exception | None = None
    for attempt in range(1, 6):
        try:
            data = urllib.request.urlopen(req, timeout=30).read()
            OUT.write_bytes(data)
            print(f"已写入 {OUT}（{len(data)} 字节，第 {attempt} 次成功）")
            return 0
        except Exception as e:
            last = e
            wait = 5 * attempt
            print(f"第 {attempt} 次失败：{type(e).__name__} {e}，等 {wait}s")
            time.sleep(wait)
    raise SystemExit(f"5 次都失败，最后一次：{last}")


if __name__ == "__main__":
    raise SystemExit(main())
