"""命令行入口。

用法（在 D:\\dev\\eval-lab 目录下）：
  uv run eval-lab compare --prompt "用一句话解释什么是幻觉" --providers mock
  uv run eval-lab compare --prompt "..." --providers deepseek,qwen --repeat 2
  uv run eval-lab simulate
"""
from __future__ import annotations

import argparse
import statistics
import sys

from rich.console import Console
from rich.table import Table

from .config import PROVIDERS
from .llm import call_llm

console = Console()

#进行大模型返回数据长度的截取（只做展示的截取）
# _开头表示这个方法只在该文件内部使用
def _truncate(s: str, n: int = 46) -> str:
    s = (s or "").replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


#定义一个cmd_compare函数 接收一个 args参数 (冒号后面跟参数说明)；最后返回一个int类型
def cmd_compare(args: argparse.Namespace) -> int:
    #把逗号串拆成列表
    #`.split(",")` 按逗号切开 → `["zhipu", " mock", ""]`　
    #`.strip()` 去掉两头的空格
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    #一个空列表 用来装成功的调用结果
    rows = []
    #另外的空列表 用来装被跳过的厂商 装厂商名和原因
    skipped: list[tuple[str, str]] = []
    #外层循环，provider里面的每一个 轮流叫p
    for p in providers:
        #跑repeat次的循环 i=0，1，2
        for i in range(args.repeat):
            #下面几行容易出错
            try:
                #调用模型 call_llm后面是参数
                rec = call_llm(
                    #p为厂商名
                    p,
                    #提示词
                    args.prompt,
                    #造一个case编号
                    case_id=f"compare-{p}-{i + 1}",
                    prompt_version=args.prompt_version,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout_s=args.timeout,
                    budget_s=args.budget,
                )
            #只接 `RuntimeError` 这一种异常，接住后叫它 `e`
            except RuntimeError as e:  # 缺 key：跳过这家，别让整次对比挂掉
                #把跳过的放在skipped的桶里 
                skipped.append((p, str(e)))
                break
            #成功的写进rows
            rows.append(rec)

    if skipped:
        #把跳过的原因打印给用户 rich库的颜色标记
        for p, msg in skipped:
            console.print(f"[yellow]跳过 {p}：{msg}[/yellow]")
    #没有厂商可以用（rows为0） 则直接结束
    if not rows:
        console.print("[red]没有可用的 provider，先用 --providers mock 验证链路[/red]")
        return 2

    
    #`Table(...)` 是从 rich 库来的 “表格对象”，现在只是个空壳；`title=...` 表标题，`show_lines=False` 不要每行之间的横线（省屏幕高度）
    table = Table(title=f"compare · repeat={args.repeat} · T={args.temperature}", show_lines=False)
    #`(a, b, c)` 是**元组**，就是 “不可修改的小列表”，这里当一组列名用
    #`for col in ...` 把这 7 个名字轮流拿出来
    for col in ("provider", "latency_ms", "in_tok", "out_tok", "cost_cny", "att", "输出"):
        table.add_column(col, overflow="fold")
    #每一条记录叫r
    for r in rows:
        table.add_row(
            #点号取字段
            r.provider, str(r.latency_ms), str(r.input_tokens), str(r.output_tokens),
            #保留4位小数
            f"{r.cost_cny:.4f}", str(r.attempts),
            #如果输出没错 就展示截断后的输出 如果有错误 则展示红色的错误
            _truncate(r.output) if not r.error else f"[red]{r.error}[/red]",
        )
    #把表打印到屏幕上
    console.print(table)

    by_provider: dict[str, list] = {}
    for r in rows:
        by_provider.setdefault(r.provider, []).append(r)
    summary = Table(title="汇总（多跑几次时看方差）", show_lines=False)
    for col in ("provider", "n", "p50 latency", "p50 cost", "失败"):
        summary.add_column(col)
    for p, rs in by_provider.items():
        lat = [r.latency_ms for r in rs]
        cost = [r.cost_cny for r in rs]
        summary.add_row(
            p, str(len(rs)),
            f"{int(statistics.median(lat))} ms",
            f"{statistics.median(cost):.4f}",
            str(sum(1 for r in rs if r.error)),
        )
    console.print(summary)
    console.print(f"[dim]明细已写入 results/calls.jsonl（共 {len(rows)} 条）[/dim]")
    return 0


def cmd_simulate(_args: argparse.Namespace) -> int:
    """D3 的任务：把三种故障真实复现一遍，确认你都处理住了。"""
    from .simulate import run_all
    return run_all()


def cmd_faults(_args: argparse.Namespace) -> int:
    """D3：真 HTTP 链路上的 429/超时/5xx/坏 JSON。"""
    from .faults import run_probe
    return run_probe()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval-lab", description="W1 地基：多 provider 调用与落库")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="同一 prompt 打多家，并排看延迟/成本/输出")
    c.add_argument("--prompt", required=True)
    c.add_argument("--providers", default="mock", help="逗号分隔；可选 " + ",".join(PROVIDERS))
    c.add_argument("--repeat", type=int, default=1, help="每个 provider 跑几次（测方差）")
    c.add_argument("--temperature", type=float, default=0.0)
    c.add_argument("--max-tokens", type=int, default=1024)
    c.add_argument("--timeout", type=float, default=60.0)
    c.add_argument("--budget", type=float, default=120.0, help="单次调用（含重试）的总耗时上限，秒")
    c.add_argument("--prompt-version", default="v1")
    c.set_defaults(func=cmd_compare)

    s = sub.add_parser("simulate", help="复现 429/超时/非法JSON 三种故障")
    s.set_defaults(func=cmd_simulate)

    f = sub.add_parser("faults", help="D3：把故障打到真实 HTTP 链路上（本地故障服务器）")
    f.set_defaults(func=cmd_faults)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as e:  # 配置类错误（缺 key 等）只给人话，不给堆栈
        console.print(f"[red]{e}[/red]")
        return 2


if __name__ == "__main__":
    sys.exit(main())
