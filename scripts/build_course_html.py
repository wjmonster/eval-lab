"""把 docs/course 下的合订本 md 渲染成单页 HTML（图片用相对路径，与 images/ 同级）。

用法：
    uv run python scripts\\build_course_html.py                       # 默认中文版
    uv run python scripts\\build_course_html.py --src <md> --out <html>
"""
from pathlib import Path
import argparse
import re


import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "course"
SRC = DOCS / "unit1-中文合订.md"
OUT = DOCS / "unit1-中文合订.html"

CSS = """
body{max-width:900px;margin:0 auto;padding:24px 20px 80px;font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
line-height:1.75;color:#222;background:#fff}
h1{font-size:26px;border-bottom:3px solid #e8532f;padding-bottom:10px}
h2{font-size:20px;margin-top:2em;padding-left:10px;border-left:4px solid #e8532f}
h3{font-size:17px;color:#333}
img{max-width:100%;height:auto;display:block;margin:14px auto;border:1px solid #eee;border-radius:6px}
pre{background:#f6f8fa;padding:14px;overflow-x:auto;border-radius:6px;font-size:13px;line-height:1.5}
code{font-family:Consolas,Menlo,monospace;background:#f3f3f3;padding:1px 5px;border-radius:3px;font-size:13px}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px}
th,td{border:1px solid #ddd;padding:8px 10px;text-align:left}
th{background:#fafafa}
blockquote{border-left:3px solid #ddd;margin:16px 0;padding:4px 14px;color:#555;background:#fcfcfc}
.toc{background:#fafafa;padding:14px 20px;border-radius:6px;font-size:14px}
a{color:#c0392b}
hr{border:none;border-top:1px dashed #ddd;margin:36px 0}
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DOCS / "unit1-中文合订.md"))
    ap.add_argument("--out", default=str(DOCS / "unit1-中文合订.html"))
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    md_text = src.read_text(encoding="utf-8")
    body = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists", "nl2br"],
        extension_configs={"toc": {"toc_depth": "1-2"}},
    ).convert(md_text)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", body)
    title = re.sub(r"<[^>]+>", "", m.group(1)) if m else src.stem


    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    out.write_text(html, encoding="utf-8")
    n_img = body.count("<img")
    print(f"已生成 {out}  ({out.stat().st_size/1024:.1f} KB)  内嵌 img 标签 {n_img} 个")


if __name__ == "__main__":
    main()
