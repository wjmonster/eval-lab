"""跑一遍 dataset_v0.jsonl，用"迷你 judge"当场判，只为验证题目和判据写得动。

这是 D4 的自检工具，不是正式 scorer（正式 scorer 在 W3 写）。
用法：uv run python scripts\run_dataset_v0.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rich.console import Console
from rich.table import Table

from eval_lab.llm import call_llm, parse_json_lenient

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dataset_v0.jsonl"
PROVIDER = "zhipu"


def clean(s: str, mode: str) -> str:
    return s.replace(" ", "").replace("\n", "") if mode == "no_space" else s


def judge_keywords(out: str, j: dict) -> tuple[bool, str]:
    text = clean(out, j.get("count_mode", ""))
    if j.get("max_chars") and len(text) > j["max_chars"]:
        return False, f"超长 {len(text)}>{j['max_chars']}"
    if j.get("min_chars") and len(text) < j["min_chars"]:
        return False, f"过短 {len(text)}<{j['min_chars']}"
    for k in j.get("must_contain", []):
        if k not in text:
            return False, f"缺必须词『{k}』"
    any_of = j.get("must_contain_any") or []
    if any_of and not any(k in text for k in any_of):
        return False, "必须词一个都没出现"
    hit = [k for k in j.get("must_not_contain", []) if k in text]
    if hit:
        return False, f"出现违禁词 {hit}"
    return True, "ok"


def judge_json(out: str, j: dict) -> tuple[bool, str]:
    if j.get("strict"):
        try:
            obj = json.loads(out)
        except json.JSONDecodeError:
            return False, "严格模式：整体不是合法 JSON（有围栏或多余文字）"
    else:
        ok, obj = parse_json_lenient(out)
        if not ok:
            return False, "解析失败"
    if not isinstance(obj, dict):
        return False, "顶层不是对象"
    for k, v in (j.get("schema") or {}).items():
        if k not in obj:
            return False, f"缺字段 {k}"
        if v == "number" and not isinstance(obj[k], (int, float)):
            return False, f"{k} 不是数字"
        if v == "string" and not isinstance(obj[k], str):
            return False, f"{k} 不是字符串"
        if isinstance(v, dict):
            sub = obj[k]
            if not isinstance(sub, dict):
                return False, f"{k} 不是对象"
            for kk in v:
                if kk not in sub:
                    return False, f"缺字段 {k}.{kk}"
    for k, v in (j.get("equals") or {}).items():
        if obj.get(k) != v:
            return False, f"{k} != {v}"
    if j.get("score_min") is not None and float(obj.get("score", -1)) < j["score_min"]:
        return False, f"score {obj.get('score')} < {j['score_min']}"
    q_any = j.get("args_q_contains_any") or []
    if q_any:
        q = str((obj.get("args") or {}).get("q", ""))
        if not any(k in q for k in q_any):
            return False, f"args.q 不含 {q_any}"
    return True, "ok"


def main() -> int:
    cases = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    console = Console()
    table = Table(title=f"dataset_v0 自检 · {len(cases)} 条 · provider={PROVIDER}", show_lines=True)
    for col in ("case", "判定", "判定依据", "输出（前 60 字）"):
        table.add_column(col, overflow="fold")

    passed = 0
    for c in cases:
        rec = call_llm(
            PROVIDER,
            c["prompt"],
            case_id=c["case_id"],
            prompt_version="v0",
            temperature=0.0,
            max_tokens=256,
            budget_s=60.0,
        )
        if rec.error:
            verdict, why = False, f"调用失败 {rec.error[:50]}"
        else:
            j = c["judge"]
            verdict, why = (
                judge_json(rec.output, j) if j["type"] == "json_schema" else judge_keywords(rec.output, j)
            )
        passed += 1 if verdict else 0
        table.add_row(
            c["case_id"],
            "[green]PASS[/green]" if verdict else "[red]FAIL[/red]",
            why,
            (rec.output or "").replace("\n", " ")[:60],
        )
    console.print(table)
    console.print(f"[bold]通过 {passed}/{len(cases)}[/bold]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
