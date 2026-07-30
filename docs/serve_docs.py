from __future__ import annotations

import argparse
import html
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import markdown


DOCS_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8000
MARKDOWN_EXTENSIONS = ["fenced_code", "tables", "toc", "sane_lists"]
HOME_DOC = "spark_schemas.md"
DOC_LABELS = {
    "spark_schemas.md": "Visão Geral",
    "bronze_dimensional_model.md": "Bronze",
    "silver_dimensional_model.md": "Silver",
    "gold_dimensional_model.md": "Gold",
}
DOC_ORDER = [
    "bronze_dimensional_model.md",
    "silver_dimensional_model.md",
    "gold_dimensional_model.md",
]


def sort_docs(paths: list[Path]) -> list[Path]:
    order_index = {name: index for index, name in enumerate(DOC_ORDER)}
    return sorted(paths, key=lambda path: (order_index.get(path.name, 999), label_for_doc(path)))


def discover_markdown_files() -> list[Path]:
    files = [path for path in DOCS_DIR.glob("*.md") if path.is_file()]
    return sort_docs(files)


def nav_markdown_files() -> list[Path]:
    return [path for path in discover_markdown_files() if path.name != HOME_DOC]


def label_for_doc(path: Path) -> str:
    return DOC_LABELS.get(path.name, path.stem.replace("_", " ").replace("-", " ").title())


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[-\s]+", "-", value, flags=re.UNICODE)
    return value


def flatten_toc_tokens(tokens: list[dict[str, object]]) -> list[dict[str, str | int]]:
    sections: list[dict[str, str | int]] = []
    for token in tokens:
        level = int(token.get("level", 0))
        if level in {2, 3}:
            sections.append(
                {
                    "level": level,
                    "title": str(token.get("name", "")),
                    "id": str(token.get("id", slugify(str(token.get("name", ""))))),
                }
            )
        children = token.get("children", [])
        if isinstance(children, list):
            sections.extend(flatten_toc_tokens(children))
    return sections


def render_markdown_file(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=MARKDOWN_EXTENSIONS, output_format="html5")
    body = md.convert(source)
    title = label_for_doc(path)
    sections = flatten_toc_tokens(getattr(md, "toc_tokens", []))
    return render_page(
        title=title,
        content=body,
        current_file=path.name,
        sections=sections,
    )


def render_index() -> str:
    home_path = DOCS_DIR / HOME_DOC
    if home_path.exists():
        return render_markdown_file(home_path)

    items = "\n".join(
        (
            f'<li><a href="/{html.escape(path.name)}">{html.escape(label_for_doc(path))}</a></li>'
            for path in nav_markdown_files()
        )
    )
    content = (
        "<h1>TOPIK Documentation</h1>"
        "<p>Escolha um documento para visualizar em HTML.</p>"
        f"<ul>{items}</ul>"
    )
    return render_page(title="TOPIK Documentation", content=content, current_file=None, sections=[])


def render_page(
    title: str,
    content: str,
    current_file: str | None,
    sections: list[dict[str, str | int]],
) -> str:
    nav_items = []
    for path in nav_markdown_files():
        css_class = ' class="active"' if path.name == current_file else ""
        nav_items.append(
            f'<li><a{css_class} href="/{html.escape(path.name)}">{html.escape(label_for_doc(path))}</a></li>'
        )
    nav = "\n".join(nav_items)

    section_items = []
    for section in sections:
        level_class = "sub" if section["level"] == 3 else ""
        section_items.append(
            f'<li><a class="{level_class}" data-target="{html.escape(str(section["id"]))}" href="#{html.escape(str(section["id"]))}">{html.escape(str(section["title"]))}</a></li>'
        )
    section_nav = "\n".join(section_items)
    section_panel = ""
    if section_items:
        section_panel = f"""
    <aside class=\"page-nav\">
      <p class=\"page-nav-label\">Nesta página</p>
      <ul>
        {section_nav}
      </ul>
    </aside>
  """

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #12091f;
      --bg-soft: #1a0f2e;
      --panel: rgba(36, 22, 61, 0.82);
      --panel-strong: rgba(52, 31, 91, 0.92);
      --border: rgba(182, 140, 255, 0.24);
      --text: #f4edff;
      --muted: #cdbcf3;
      --accent: #bb86fc;
      --accent-strong: #e0c3ff;
      --accent-soft: rgba(187, 134, 252, 0.16);
      --code-bg: rgba(20, 10, 35, 0.8);
      --shadow: 0 24px 60px rgba(8, 3, 20, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(176, 120, 255, 0.28) 0, transparent 34%),
        radial-gradient(circle at bottom right, rgba(86, 43, 160, 0.3) 0, transparent 32%),
        linear-gradient(180deg, #0d0718 0%, var(--bg) 100%);
    }}
    .layout {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr) 240px;
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(27, 15, 46, 0.96), rgba(19, 10, 34, 0.96));
      padding: 28px;
      position: sticky;
      top: 0;
      height: 100vh;
      backdrop-filter: blur(12px);
    }}
    aside h1 {{
      margin: 0 0 10px;
      font-size: 1.45rem;
      letter-spacing: 0.02em;
    }}
    aside p {{
      margin: 0 0 20px;
      color: var(--muted);
      line-height: 1.5;
    }}
    aside ul {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    aside li + li {{ margin-top: 8px; }}
    aside a {{
      display: block;
      padding: 10px 0;
      color: var(--text);
      text-decoration: none;
      border-right: 2px solid transparent;
      transition: color 140ms ease, border-color 140ms ease, padding-left 140ms ease;
    }}
    aside a:hover, aside a.active {{
      border-right-color: rgba(224, 195, 255, 0.55);
      color: var(--accent-strong);
      padding-left: 6px;
    }}
    main {{
      padding: 44px 60px;
    }}
    article {{
      max-width: 1040px;
      background: linear-gradient(180deg, var(--panel-strong), var(--panel));
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 40px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    h1, h2, h3 {{
      line-height: 1.2;
      letter-spacing: -0.02em;
    }}
    h1 {{ font-size: 2.2rem; }}
    h2 {{
      margin-top: 2.4rem;
      padding-bottom: 0.45rem;
      border-bottom: 1px solid var(--border);
    }}
    p, li {{ line-height: 1.7; }}
    strong {{ color: var(--accent-strong); }}
    code {{
      background: var(--code-bg);
      padding: 0.15rem 0.35rem;
      border-radius: 6px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.95em;
      color: #f5d9ff;
    }}
    pre {{
      background: var(--code-bg);
      padding: 16px;
      border-radius: 16px;
      overflow-x: auto;
      border: 1px solid rgba(224, 195, 255, 0.14);
    }}
    pre code {{ background: transparent; padding: 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      background: rgba(255, 255, 255, 0.03);
      border-radius: 14px;
      overflow: hidden;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{
      background: rgba(187, 134, 252, 0.16);
      color: var(--accent-strong);
    }}
    tr:nth-child(even) td {{ background: rgba(255, 255, 255, 0.018); }}
    a {{ color: var(--accent); }}
    a:hover {{ color: var(--accent-strong); }}
    blockquote {{
      margin: 1.4rem 0;
      padding: 0.8rem 1rem;
      border-left: 3px solid var(--accent);
      background: rgba(255, 255, 255, 0.03);
      color: var(--muted);
      border-radius: 0 12px 12px 0;
    }}
    img {{
      display: block;
      width: 100%;
      max-width: 980px;
      margin: 1.2rem 0 1.8rem;
      border-radius: 18px;
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      background: rgba(14, 7, 24, 0.7);
    }}
    .page-nav {{
      border-right: 0;
      border-left: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(17, 10, 30, 0.82), rgba(17, 10, 30, 0.58));
      padding: 36px 20px;
      position: sticky;
      top: 0;
      height: 100vh;
    }}
    .page-nav-label {{
      margin: 0 0 16px;
      color: var(--muted);
      font-size: 0.88rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .page-nav ul {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    .page-nav li + li {{ margin-top: 8px; }}
    .page-nav a {{
      display: block;
      padding: 6px 10px 6px 0;
      border-right: 2px solid rgba(205, 188, 243, 0.14);
      color: var(--muted);
      text-decoration: none;
      line-height: 1.45;
      transition: color 140ms ease, border-color 140ms ease, padding-right 140ms ease;
    }}
    .page-nav a.sub {{
      font-size: 0.94rem;
      padding-right: 0;
      padding-left: 10px;
    }}
    .page-nav a:hover {{
      color: var(--accent-strong);
      border-right-color: rgba(224, 195, 255, 0.38);
    }}
    .page-nav a.active {{
      color: var(--accent-strong);
      border-right-color: rgba(224, 195, 255, 0.72);
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }}
      .page-nav {{ display: none; }}
      main {{ padding: 24px; }}
      article {{ padding: 24px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h1>TOPIK Docs</h1>
      <p>Documentacao local em HTML para Bronze, Silver e Gold.</p>
      <ul>
        <li><a{' class="active"' if current_file in {None, HOME_DOC} else ''} href="/">visao geral</a></li>
        {nav}
      </ul>
    </aside>
    <main>
      <article>
        {content}
      </article>
    </main>
    {section_panel}
  </div>
  <script>
    const sectionLinks = Array.from(document.querySelectorAll('.page-nav a[data-target]'));
    const headings = sectionLinks
      .map((link) => document.getElementById(link.dataset.target))
      .filter(Boolean);

    const setActive = (id) => {{
      sectionLinks.forEach((link) => link.classList.toggle('active', link.dataset.target === id));
    }};

    if (headings.length > 0) {{
      setActive(headings[0].id);
      const observer = new IntersectionObserver((entries) => {{
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {{
          setActive(visible[0].target.id);
        }}
      }}, {{ rootMargin: '-20% 0px -65% 0px', threshold: [0, 1] }});

      headings.forEach((heading) => observer.observe(heading));
    }}
  </script>
</body>
</html>
"""


class DocsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        raw_path = unquote(self.path.split("?", 1)[0])
        if raw_path in {"", "/"}:
            self._send_html(render_index())
            return

        doc_name = raw_path.lstrip("/")
        if "/" in doc_name or "\\" in doc_name:
            self.send_error(HTTPStatus.NOT_FOUND, "Document not found")
            return

        doc_path = DOCS_DIR / doc_name
        if not doc_path.exists() or not doc_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Document not found")
            return

        if doc_path.suffix.lower() != ".md":
          self._send_file(doc_path)
          return

        self._send_html(render_markdown_file(doc_path))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_html(self, payload: str) -> None:
        encoded = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path) -> None:
      payload = path.read_bytes()
      content_type, _ = mimetypes.guess_type(path.name)
      self.send_response(HTTPStatus.OK)
      self.send_header("Content-Type", content_type or "application/octet-stream")
      self.send_header("Content-Length", str(len(payload)))
      self.end_headers()
      self.wfile.write(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the Markdown files in the docs folder as HTML on localhost."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port to bind.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DocsHandler)
    print(f"Serving docs at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()