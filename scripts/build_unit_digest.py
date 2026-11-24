"""批量把 agents-course 的 unitN 目录合成单文件合订本（含本地图 + 中文批注）。

用法：
    uv run python scripts\\build_unit_digest.py            # 生成全部（u2/u3，中英）
    uv run python scripts\\build_unit_digest.py u2 zh      # 只生成 Unit2 中文版
"""
import re
import sys
from pathlib import Path

BASE = Path(r"D:\dev\agents-course\agents-course-main\units")
DOCS = Path(__file__).resolve().parents[1] / "docs" / "course"
MAP_FILE = DOCS / "_imgmap.tsv"

SKIP_TAGS = re.compile(
    r"^\s*</?(Tabs|TabItem|Tip|Note|FrameworkContent|details|summary|div|br|Youtube|CourseFloatingBanner)\b[^>]*>\s*$"
)

# ---------------------------------------------------------------- 配置文件结构
UNITS = {
    "u2": {
        "title_zh": "Unit 2 中文合订本 · 三大框架实战（smolagents / llama-index / langgraph）",
        "title_en": "Unit 2 Digest · Frameworks in Practice (smolagents / llama-index / langgraph)",
        "parts": [
            ("A", "smolagents（Unit 2 主线，必学）", [
                ("smolagents/introduction.mdx", "框架定位。一句话：Agent = 循环 + 工具。smolagents 把这套东西压到极简，是先跑通闭环的地方。"),
                ("smolagents/why_use_smolagents.mdx", "为什么选它。带走 CodeAgent vs ToolCallingAgent 这条分野——它决定了后面所有失败模式的形状。"),
                ("smolagents/tools.mdx", "`@tool` 装饰器 + docstring 就是工具契约。**参数描述写不清，模型必乱传参**，这是你测试要抓的第一号 bug。"),
                ("smolagents/tool_calling_agents.mdx", "ToolCallingAgent：模型输出 JSON 调工具。**可断言性强**（能校验函数名和参数），适合做评测基线。"),
                ("smolagents/code_agents.mdx", "CodeAgent：模型直接写 Python 代码执行。表达力强但**失败面大**（语法错、越权、死循环）。注意：书上用 E2B/Docker 沙箱，你机器别装 Docker，用本地受限执行替代，跳过 E2B 部分即可。"),
                ("smolagents/retrieval_agents.mdx", "RAG Agent 要本地 embedding 模型——**你机器跑不动**，这一节读懂思路就行，代码别硬跑，用 DeepSeek/阿里 API 的 embedding 接口替代。"),
                ("smolagents/vision_agents.mdx", "多模态 Agent，要视觉模型。国内用 Qwen-VL（DashScope）即可，HF 那条不通。读思路为主。"),
                ("smolagents/multi_agent_systems.mdx", "多 Agent 编排（manager 派活给子 Agent）。**测试重点在路由**：任务分对了没、子 Agent 边界清不清、失败会不会串。"),
                ("smolagents/quiz1.mdx", "自测。做错的记下来，这就是你 `docs/failure-modes.md` 里该补的行。"),
                ("smolagents/quiz2.mdx", "自测。"),
                ("smolagents/final_quiz.mdx", "收尾自测。"),
                ("smolagents/conclusion.mdx", "对照清单看自己缺哪块。"),
            ]),
            ("B", "llama-index（可略读，知道它长什么样即可）", [
                ("llama-index/introduction.mdx", "定位：数据框架，RAG 出身。国内生产环境用得少，**别投入太多时间**。"),
                ("llama-index/components.mdx", "组件模型：LLM / Embedding / VectorStore 可替换。这个'可替换'的思路对你搭多 provider 对比有用。"),
                ("llama-index/tools.mdx", "把 QueryEngine 包成工具。注意它把'检索'当工具塞给 Agent——和 smolagents 的写法对照看。"),
                ("llama-index/agents.mdx", "FunctionAgent / ReActAgent。和前面重复度高，快速浏览。"),
                ("llama-index/workflows.mdx", "**这节值得看**：事件驱动的步骤编排，状态可控、可断言，是你做'流程级评测'的参照。"),
                ("llama-index/llama-hub.mdx", "现成集成库。知道有这么个东西就行。"),
                ("llama-index/quiz1.mdx", "自测，可跳过。"),
                ("llama-index/quiz2.mdx", "自测，可跳过。"),
                ("llama-index/conclusion.mdx", "收尾。"),
            ]),
            ("C", "langgraph（W3-W4 的重点参照，精读）", [
                ("langgraph/introduction.mdx", "LangGraph = runtime（状态机），不是 framework。这个区分面试会问。"),
                ("langgraph/when_to_use_langgraph.mdx", "**判断标准**：需要持久化状态、人工介入、可恢复执行时才用它。简单链路别上。"),
                ("langgraph/building_blocks.mdx", "State / Node / Edge / Checkpoint 四个词。**Checkpoint 是评测的抓手**——每一步状态都能取出来断言。"),
                ("langgraph/first_graph.mdx", "写第一个图。照敲，跑通再往下。"),
                ("langgraph/document_analysis_agent.mdx", "完整案例：文档分析 Agent。这就是你能写进简历的'可观测流水线'原型。"),
                ("langgraph/quiz1.mdx", "自测。"),
                ("langgraph/conclusion.mdx", "收尾。"),
            ]),
        ],
    },
    "u3": {
        "title_zh": "Unit 3 中文合订本 · Agentic RAG",
        "title_en": "Unit 3 Digest · Agentic RAG",
        "parts": [
            ("A", "agentic-rag（Unit 3 全部内容）", [
                ("agentic-rag/introduction.mdx", "Agentic RAG 和普通 RAG 的差别只有一句：**检索几次、检索什么，由 Agent 自己决定**。这一句就是全部重点。"),
                ("agentic-rag/agentic-rag.mdx", "流程拆解。注意它多出来的'判断要不要再检索'环节——**这正是你评测要断言的决策点**。"),
                ("agentic-rag/tools.mdx", "三个工具：检索、文档读取、回答。工具划分越细，可观测性越好。"),
                ("agentic-rag/invitees.mdx", "数据准备（嘉宾名单）。这节是脏活，但**数据质量决定评测上限**，别跳。"),
                ("agentic-rag/agent.mdx", "把上面组装成 Agent。跟着写一遍，这就是你第三个项目（文档问答）的骨架。"),
                ("agentic-rag/conclusion.mdx", "收尾。"),
            ]),
        ],
    },
}

# Unit2 根目录的单元导言单独处理
UNIT_INTRO = {
    "u2": ("introduction.mdx", "Unit 2 导言：三个框架怎么选。**结论先给你**：主线学 smolagents，langgraph 当评测参照，llama-index 略读。"),
    "u3": ("agentic-rag/introduction.mdx", None),  # 已在 part 内
}


def load_map() -> dict:
    m = {}
    if MAP_FILE.exists():
        for line in MAP_FILE.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                k, v = line.split("\t", 1)
                m[k.strip()] = v.strip()
    return m


def clean(raw: str, imgmap: dict, drop_h1: bool = True) -> tuple[str, str]:
    """返回 (标题, 正文)"""
    title = ""
    lines = []
    for line in raw.splitlines():
        if re.match(r"^\s*import\s", line):
            continue
        if drop_h1 and re.match(r"^#\s+", line):
            if not title:
                title = re.sub(r"^#\s+", "", line).strip()
                continue
        if SKIP_TAGS.match(line):
            continue
        line = re.sub(r"\[\[[^\]]+\]\]", "", line)
        for mm in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", line):
            u = mm.group(2)
            if u in imgmap:
                line = line.replace(mm.group(0), f"![{mm.group(1)}]({imgmap[u]})")
        lines.append(line)
    body = "\n".join(lines)
    # 跨行 <img ...> 整段替换
    for tag in re.finditer(r"(?s)<img[^>]*>", body):
        sm = re.search(r'src="([^"]+)"', tag.group(0))
        if not sm:
            continue
        am = re.search(r'alt="([^"]*)"', tag.group(0))
        alt = am.group(1) if am else "图"
        u = sm.group(1)
        if u in imgmap:
            body = body.replace(tag.group(0), f"![{alt}]({imgmap[u]})")
        else:
            body = body.replace(tag.group(0), f"> 【图·未下载】{alt}")
    return re.sub(r"\[\[[^\]]+\]\]", "", title).strip(), body.strip()


def build(unit: str, lang: str) -> Path:
    cfg = UNITS[unit]
    dir_name = "unit" + unit[1:]          # u2 -> unit2, u3 -> unit3
    src_dir = BASE / lang / dir_name
    imgmap = load_map()
    zh = lang == "zh-CN"

    sections = []  # (编号, 标题, 批注, 正文)

    # 单元导言
    intro = UNIT_INTRO.get(unit)
    if intro and intro[1]:
        p = src_dir / intro[0]
        if p.exists():
            t, b = clean(p.read_text(encoding="utf-8"), imgmap)
            sections.append(("0", t or "Unit Introduction", intro[1], b))

    # 重新编号：单元导言排第 1，然后按 Part 顺序排
    out = []
    idx = 0
    if intro and intro[1]:
        p = src_dir / intro[0]
        if p.exists():
            t, b = clean(p.read_text(encoding="utf-8"), imgmap)
            idx += 1
            out.append(("SEC", idx, t or "Unit Introduction", intro[1], b, None))
    for key, name, files in cfg["parts"]:
        out.append(("PART", key, name))
        for rel, note in files:
            p = src_dir / rel
            if not p.exists():
                continue
            t, b = clean(p.read_text(encoding="utf-8"), imgmap)
            if not t:
                t = Path(rel).stem.replace("_", " ").title()
            idx += 1
            out.append(("SEC", idx, t, note, b, key))

    title = cfg["title_zh"] if zh else cfg["title_en"]
    label = "【学这一节要带走什么】" if zh else "【这一节要带走什么 / Takeaway】"

    sb = [f"# {title}", ""]
    if zh:
        sb += [
            "> 来源：github.com/huggingface/agents-course 官方中文版。",
            "> 每节前的批注是我给你划的重点，原文没有。图片已全部本地化，双击同名 `.html` 打开最省事。",
            "",
        ]
    else:
        sb += [
            "> 来源：github.com/huggingface/agents-course 官方英文版（units/en）。",
            "> 用途：中文版术语含糊时对照原句用，别当主线读。",
            "",
        ]
    sb += ["## 目录", ""]

    # 目录：Part 标签 + 其下各节
    for item in out:
        if item[0] == "PART":
            sb.append(f"**Part {item[1]}：{item[2]}**")
            sb.append("")
        else:
            sb.append(f"{item[1]}. {item[2]}")
    sb.append("")

    for item in out:
        if item[0] == "PART":
            sb += ["---", "", f"# Part {item[1]}：{item[2]}", ""]
            continue
        _k, n, t, note, body, _key = item
        sb += ["---", "", f"## {n}. {t}", ""]
        if note:
            sb += [f"**{label}** {note}", ""]
        sb += [body, ""]

    name_map = {
        ("u2", "zh-CN"): "unit2-中文合订.md",
        ("u2", "en"): "unit2-en-英文原文合订.md",
        ("u3", "zh-CN"): "unit3-中文合订.md",
        ("u3", "en"): "unit3-en-英文原文合订.md",
    }
    out_path = DOCS / name_map[(unit, lang)]
    out_path.write_text("\n".join(sb), encoding="utf-8")
    return out_path


def main() -> None:
    targets = sys.argv[1:]
    pairs = [("u2", "zh-CN"), ("u2", "en"), ("u3", "zh-CN"), ("u3", "en")]
    if targets:
        u = targets[0]
        if len(targets) > 1:
            pairs = [(u, "zh-CN" if targets[1].endswith("zh") else "en")]
        else:
            pairs = [(u, "zh-CN"), (u, "en")]
    for unit, lang in pairs:
        p = build(unit, lang)
        txt = p.read_text(encoding="utf-8")
        print(
            f"{p.name}  {p.stat().st_size/1024:.1f} KB  "
            f"节数 {len(re.findall(r'(?m)^## \d+\. ', txt))}  "
            f"图片 {len(re.findall(r'!\[[^\]]*\]\(images/', txt))}  "
            f"未下载 {txt.count('【图·未下载】')}"
        )


if __name__ == "__main__":
    main()
