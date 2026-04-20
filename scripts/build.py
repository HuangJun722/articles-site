#!/usr/bin/env python3
"""
Build script: converts .md articles to HTML and generates index page.
Run locally or via GitHub Actions.
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

ARTICLES_DIR = Path("articles")
OUTPUT_HTML = "index.html"

# Read existing article metadata from manifest, or scan files
MANIFEST_FILE = Path(".article_manifest.json")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    frontmatter_text = match.group(1)
    body = match.group(2)
    meta = {}
    for line in frontmatter_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            val = val.strip().strip('"').strip("'")
            if val.startswith('['):
                try:
                    val = json.loads(val)
                except:
                    val = [v.strip().strip('"') for v in val[1:-1].split(',')]
            meta[key.strip()] = val
    return meta, body


def markdown_to_html_body(text: str) -> str:
    """Simple markdown to HTML converter (commonmark subset)."""
    html = text

    # Escape HTML entities first (but preserve our own tags)
    html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Code blocks (before inline processing)
    html = re.sub(r'```(\w*)\n(.*?)\n```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Headers
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Blockquotes
    html = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r'^---$', '<hr>', html, flags=re.MULTILINE)

    # Unordered lists
    lines = html.split('\n')
    result = []
    in_ul = False
    for line in lines:
        m = re.match(r'^[-*] (.+)$', line)
        if m:
            if not in_ul:
                result.append('<ul>')
                in_ul = True
            result.append(f'<li>{m.group(1)}</li>')
        else:
            if in_ul:
                result.append('</ul>')
                in_ul = False
            result.append(line)
    if in_ul:
        result.append('</ul>')
    html = '\n'.join(result)

    # Ordered lists
    lines = html.split('\n')
    result = []
    in_ol = False
    for line in lines:
        m = re.match(r'^\d+\. (.+)$', line)
        if m:
            if not in_ol:
                result.append('<ol>')
                in_ol = True
            result.append(f'<li>{m.group(1)}</li>')
        else:
            if in_ol:
                result.append('</ol>')
                in_ol = False
            result.append(line)
    if in_ol:
        result.append('</ol>')
    html = '\n'.join(result)

    # Paragraphs (wrap lines not already in block tags)
    lines = html.split('\n')
    result = []
    block_tags = {'<h1', '<h2', '<h3', '<h4', '<ul', '<ol', '<li', '<blockquote', '<pre', '<hr', '<div'}
    for line in lines:
        stripped = line.strip()
        if stripped and not any(stripped.startswith(t) for t in block_tags):
            result.append(f'<p>{line}</p>')
        else:
            result.append(line)
    html = '\n'.join(result)

    return html


def extract_title_from_body(body: str) -> str:
    """Extract first # heading as title, or first line."""
    m = re.search(r'^# (.+)$', body, re.MULTILINE)
    if m:
        return m.group(1).strip()
    first_line = body.split('\n')[0].strip()
    return first_line[:60] if first_line else 'Untitled'


def scan_articles() -> list[dict]:
    """Scan articles directory and return metadata for each article."""
    articles = []
    for md_file in sorted(ARTICLES_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        content = md_file.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(content)

        title = meta.get('title') or extract_title_from_body(body)
        date = meta.get('date') or datetime.fromtimestamp(md_file.stat().st_mtime).strftime('%Y-%m-%d')
        tags = meta.get('tags', [])
        slug = md_file.stem

        articles.append({
            'title': title,
            'date': date,
            'tags': tags,
            'slug': slug,
            'filename': md_file.name,
            'body': body,
        })
    return articles


def read_existing_index() -> str | None:
    """Read existing manually maintained index.html if it exists."""
    index_path = Path("index.html")
    if index_path.exists():
        return index_path.read_text(encoding='utf-8')
    return None


def build_index(articles: list[dict]) -> str:
    """Build the main index.html page (fallback if no manual index exists)."""
    tag_filter_html = ""
    # Collect all tags
    all_tags = set()
    for a in articles:
        for tag in a.get('tags', []):
            all_tags.add(tag)
    if all_tags:
        tag_filter_html = f"""
    <div class="tag-filter">
        <button class="tag-btn active" data-tag="all">全部</button>
        {''.join(f'<button class="tag-btn" data-tag="{t}">{t}</button>' for t in sorted(all_tags))}
    </div>
"""

    article_cards_html = ""
    for a in articles:
        tags_html = ''.join(f'<span class="tag">{t}</span>' for t in a.get('tags', []))
        article_cards_html += f"""
        <article class="card" data-tags="{' '.join(a.get('tags', []))}">
            <div class="card-meta">
                <time>{a['date']}</time>
                {tags_html}
            </div>
            <h2><a href="articles/{a['filename'].replace('.md', '.html')}">{a['title']}</a></h2>
        </article>
"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文章站</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
        .container {{ max-width: 720px; margin: 0 auto; padding: 24px 16px; }}
        h1 {{ font-size: 1.8rem; margin-bottom: 24px; color: #1a1a1a; }}
        .tag-filter {{ margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 8px; }}
        .tag-btn {{ padding: 4px 12px; border: 1px solid #ddd; border-radius: 16px; background: white; cursor: pointer; font-size: 0.85rem; color: #666; transition: all 0.2s; }}
        .tag-btn:hover {{ border-color: #1a1a1a; color: #1a1a1a; }}
        .tag-btn.active {{ background: #1a1a1a; color: white; border-color: #1a1a1a; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); transition: box-shadow 0.2s; }}
        .card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.12); }}
        .card h2 {{ font-size: 1.1rem; margin-bottom: 8px; }}
        .card h2 a {{ color: #1a1a1a; text-decoration: none; }}
        .card h2 a:hover {{ color: #0066cc; }}
        .card-meta {{ font-size: 0.8rem; color: #999; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .tag {{ background: #e8f0fe; color: #1a73e8; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }}
        .footer {{ text-align: center; margin-top: 40px; font-size: 0.8rem; color: #bbb; }}
        @media (max-width: 480px) {{ .container {{ padding: 16px 12px; }} h1 {{ font-size: 1.5rem; }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>文章站</h1>
{tag_filter_html}
        <div class="article-list">
{article_cards_html}
        </div>
        <div class="footer">自动构建 · 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>
    <script>
    // Tag filter
    document.querySelectorAll('.tag-btn').forEach(btn => {{
        btn.addEventListener('click', () => {{
            document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tag = btn.dataset.tag;
            document.querySelectorAll('.card').forEach(card => {{
                card.style.display = (!tag || tag === 'all' || card.dataset.tags.includes(tag)) ? '' : 'none';
            }});
        }});
    }});
    </script>
</body>
</html>"""


def build_article(article: dict) -> str:
    """Build a single article HTML page."""
    tags_html = ''.join(f'<span class="tag">{t}</span>' for t in article.get('tags', []))
    body_html = markdown_to_html_body(article['body'])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; line-height: 1.8; }}
        .container {{ max-width: 720px; margin: 0 auto; padding: 24px 16px; }}
        .back {{ display: inline-block; margin-bottom: 24px; color: #666; text-decoration: none; font-size: 0.9rem; }}
        .back:hover {{ color: #1a73e8; }}
        .article-header {{ background: white; border-radius: 8px; padding: 32px 32px 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .article-header h1 {{ font-size: 1.6rem; margin-bottom: 12px; color: #1a1a1a; line-height: 1.4; }}
        .article-meta {{ font-size: 0.85rem; color: #999; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
        .tag {{ background: #e8f0fe; color: #1a73e8; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }}
        .article-body {{ background: white; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .article-body h1 {{ font-size: 1.5rem; margin: 32px 0 16px; color: #1a1a1a; }}
        .article-body h2 {{ font-size: 1.3rem; margin: 28px 0 12px; color: #1a1a1a; }}
        .article-body h3 {{ font-size: 1.1rem; margin: 24px 0 10px; color: #333; }}
        .article-body h4 {{ font-size: 1rem; margin: 20px 0 8px; color: #555; }}
        .article-body p {{ margin-bottom: 16px; }}
        .article-body a {{ color: #1a73e8; text-decoration: none; }}
        .article-body a:hover {{ text-decoration: underline; }}
        .article-body code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 0.9em; }}
        .article-body pre {{ background: #f5f5f5; padding: 16px; border-radius: 8px; overflow-x: auto; margin-bottom: 16px; }}
        .article-body pre code {{ background: none; padding: 0; }}
        .article-body blockquote {{ border-left: 3px solid #ddd; padding-left: 16px; color: #666; margin: 16px 0; font-style: italic; }}
        .article-body ul, .article-body ol {{ margin: 16px 0; padding-left: 24px; }}
        .article-body li {{ margin-bottom: 8px; }}
        .article-body hr {{ border: none; border-top: 1px solid #eee; margin: 32px 0; }}
        .article-body strong {{ font-weight: 600; color: #1a1a1a; }}
        .footer {{ text-align: center; margin-top: 40px; font-size: 0.8rem; color: #bbb; }}
        @media (max-width: 480px) {{ .container {{ padding: 16px 12px; }} .article-header {{ padding: 20px; }} .article-body {{ padding: 20px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <a class="back" href="../index.html">← 返回列表</a>
        <div class="article-header">
            <h1>{article['title']}</h1>
            <div class="article-meta">
                <time>{article['date']}</time>
                {tags_html}
            </div>
        </div>
        <div class="article-body">
{body_html}
        </div>
        <div class="footer">自动构建 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>
</body>
</html>"""


def build_site():
    """Main build function."""
    if not ARTICLES_DIR.exists():
        ARTICLES_DIR.mkdir(parents=True)
        print("Created articles directory.")
        # Write a sample article
        sample = """---
title: "欢迎使用文章站"
date: "2026-04-18"
tags: ["教程"]
---

# 欢迎使用文章站

这是一个示例文章。

## 使用方法

1. 在 `articles/` 目录下创建 `.md` 文件
2. 开头使用 YAML frontmatter 指定标题、日期、标签
3. `git push` 后自动构建发布

## 写作格式

正文支持标准 Markdown 语法。

- 支持无序列表
- 支持**粗体**和*斜体*
- 支持 [链接](https://example.com)
- 支持代码 `inline code`

> 支持引用块

---

直接在手机上刷新即可看到更新。
"""
        (ARTICLES_DIR / "欢迎使用.md").write_text(sample, encoding='utf-8')

    articles = scan_articles()
    print(f"Found {len(articles)} articles")

    # Build index - only if no manually maintained index.html exists
    if read_existing_index() is None:
        index_html = build_index(articles)
        Path(OUTPUT_HTML).write_text(index_html, encoding='utf-8')
        print(f"Built {OUTPUT_HTML} (auto-generated)")
    else:
        print(f"Skipped index.html (manually maintained)")

    # Build each article
    for a in articles:
        article_html = build_article(a)
        out_path = ARTICLES_DIR / f"{a['slug']}.html"
        out_path.write_text(article_html, encoding='utf-8')
        print(f"  Built articles/{a['slug']}.html")

    print("Build complete!")


if __name__ == '__main__':
    build_site()
