#!/usr/bin/env python3
"""Получение задачи Jira и страницы Confluence как простого текста (без curl и переменных в Bash)."""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USAGE = "usage: sa_fetch.py jira <KEY> | confluence <page-id>"
TIMEOUT = 30
BLOCK_TAGS = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "table", "pre", "blockquote"}
ADF_BLOCKS = {"paragraph", "heading", "listItem", "codeBlock", "blockquote", "tableRow", "rule"}


class FetchError(Exception):
    pass


def _require(env, names):
    missing = [n for n in names if not env.get(n)]
    if missing:
        raise FetchError("не заданы переменные окружения: " + ", ".join(missing))


def _get_json(url, headers, opener):
    request = urllib.request.Request(url, headers=headers)
    try:
        response = opener(request, timeout=TIMEOUT)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        host = urllib.parse.urlsplit(url).netloc
        raise FetchError(f"HTTP {exc.code} от {host}") from None
    except (urllib.error.URLError, OSError, ValueError):
        host = urllib.parse.urlsplit(url).netloc
        raise FetchError(f"не удалось получить данные от {host}") from None


def adf_to_text(node) -> str:
    """Atlassian Document Format -> текст: текстовые узлы подряд, блоки через перевод строки."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    kind = node.get("type")
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    text = "".join(adf_to_text(child) for child in node.get("content", []))
    if kind in ADF_BLOCKS and not text.endswith("\n"):
        text += "\n"
    return text


def fetch_jira(key, env, opener=urllib.request.urlopen) -> str:
    _require(env, ["JIRA_BASE_URL", "JIRA_TOKEN"])
    base = env["JIRA_BASE_URL"].rstrip("/")
    if env.get("JIRA_EMAIL"):
        version = "3"
        raw = f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode("utf-8")
        auth = "Basic " + base64.b64encode(raw).decode("ascii")
    else:
        version = "2"
        auth = "Bearer " + env["JIRA_TOKEN"]
    url = f"{base}/rest/api/{version}/issue/{urllib.parse.quote(key)}?fields=summary,description,status,issuelinks"
    data = _get_json(url, {"Authorization": auth, "Accept": "application/json"}, opener)
    fields = data.get("fields", {})
    links = []
    for link in fields.get("issuelinks") or []:
        issue = link.get("outwardIssue") or link.get("inwardIssue") or {}
        if issue.get("key"):
            links.append(issue["key"])
    description = fields.get("description")
    body = adf_to_text(description) if isinstance(description, dict) else (description or "")
    status = (fields.get("status") or {}).get("name", "")
    return (
        f"{key}: {fields.get('summary', '')}\n"
        f"Статус: {status}\n"
        f"Связи: {', '.join(links) or 'нет'}\n\n"
        f"{body.strip()}"
    )


class _StorageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.in_cell = False
        self.cell_index = 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.parts.append("\n")
            self.cell_index = 0
        elif tag in ("td", "th"):
            if self.cell_index:
                self.parts.append(" | ")
            self.cell_index += 1
            self.in_cell = True
        elif tag in BLOCK_TAGS and not self.in_cell:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.in_cell = False
        elif tag in BLOCK_TAGS | {"tr"} and not self.in_cell:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_cell:
            data = " ".join(data.split())
        self.parts.append(data)


def storage_to_text(html: str) -> str:
    parser = _StorageParser()
    parser.feed(html or "")
    parser.close()
    lines = [" ".join(line.split()) if " | " in line else line.strip() for line in "".join(parser.parts).split("\n")]
    return "\n".join(line for line in lines if line)


def fetch_confluence(page_id, env, opener=urllib.request.urlopen) -> str:
    _require(env, ["CONFLUENCE_BASE_URL", "CONFLUENCE_TOKEN"])
    base = env["CONFLUENCE_BASE_URL"].rstrip("/")
    url = f"{base}/rest/api/content/{urllib.parse.quote(page_id)}?expand=body.storage,version"
    data = _get_json(url, {"Authorization": "Bearer " + env["CONFLUENCE_TOKEN"], "Accept": "application/json"}, opener)
    value = ((data.get("body") or {}).get("storage") or {}).get("value", "")
    version = (data.get("version") or {}).get("number", "")
    return f"Заголовок: {data.get('title', '')}\nВерсия: {version}\n\n{storage_to_text(value)}"


def main(argv: list) -> int:
    if len(argv) != 2 or argv[0] not in ("jira", "confluence"):
        print(USAGE, file=sys.stderr)
        return 2
    fetch = fetch_jira if argv[0] == "jira" else fetch_confluence
    try:
        text = fetch(argv[1], os.environ, opener=urllib.request.urlopen)
    except FetchError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
