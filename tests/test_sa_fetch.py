import base64
import io
import json
import urllib.error

import pytest

from sa_fetch import adf_to_text, fetch_confluence, fetch_jira, fetch_version, main, storage_to_text


class FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data


def make_opener(payload, seen):
    def opener(request, timeout=None):
        seen.append(request)
        return FakeResponse(payload)
    return opener


ISSUE_V2 = {
    "fields": {
        "summary": "Запрет промокода",
        "status": {"name": "В работе"},
        "issuelinks": [{"outwardIssue": {"key": "LKP-2"}}, {"inwardIssue": {"key": "LKP-3"}}],
        "description": "Описание v2",
    }
}


def test_jira_v2_bearer():
    seen = []
    env = {"JIRA_BASE_URL": "https://jira.example.com/", "JIRA_TOKEN": "tok"}
    out = fetch_jira("LKP-1", env, opener=make_opener(ISSUE_V2, seen))
    assert out == "LKP-1: Запрет промокода\nСтатус: В работе\nСвязи: LKP-2, LKP-3\n\nОписание v2"
    req = seen[0]
    assert req.full_url.startswith("https://jira.example.com/rest/api/2/issue/LKP-1")
    assert req.get_header("Authorization") == "Bearer tok"


def test_jira_v3_basic_and_adf():
    seen = []
    issue = {"fields": {
        "summary": "S", "status": {"name": "Open"}, "issuelinks": [],
        "description": {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Первый "}, {"type": "text", "text": "абзац"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Второй"}]},
        ]},
    }}
    env = {"JIRA_BASE_URL": "https://x.atlassian.net", "JIRA_TOKEN": "tok", "JIRA_EMAIL": "a@b.c"}
    out = fetch_jira("K-1", env, opener=make_opener(issue, seen))
    assert "/rest/api/3/issue/K-1" in seen[0].full_url
    expected = "Basic " + base64.b64encode(b"a@b.c:tok").decode()
    assert seen[0].get_header("Authorization") == expected
    assert out == "K-1: S\nСтатус: Open\nСвязи: нет\n\nПервый абзац\nВторой"


def test_adf_to_text_empty():
    assert adf_to_text(None) == ""


def test_storage_table_rows():
    html = "<h1>Тема</h1><p>Текст &amp; еще</p><table><tr><th>A</th><th>B</th></tr><tr><td><p>1</p></td><td>2</td></tr></table>"
    assert storage_to_text(html) == "Тема\nТекст & еще\nA | B\n1 | 2"


def test_confluence():
    seen = []
    page = {"title": "Страница", "version": {"number": 7}, "body": {"storage": {"value": "<p>Тело</p>"}}}
    env = {"CONFLUENCE_BASE_URL": "https://c.example.com", "CONFLUENCE_TOKEN": "ct"}
    out = fetch_confluence("123", env, opener=make_opener(page, seen))
    assert out == "Заголовок: Страница\nВерсия: 7\n\nТело"
    assert "/rest/api/content/123?expand=body.storage,version" in seen[0].full_url
    assert seen[0].get_header("Authorization") == "Bearer ct"


def test_version_only():
    seen = []
    page = {"title": "Образец", "version": {"number": 12}}
    env = {"CONFLUENCE_BASE_URL": "https://c.example.com", "CONFLUENCE_TOKEN": "ct"}
    assert fetch_version("110167415", env, opener=make_opener(page, seen)) == "110167415\t12\tОбразец"
    assert seen[0].full_url.endswith("/rest/api/content/110167415?expand=version")


def test_missing_env_lists_names(capsys, monkeypatch):
    for name in ("JIRA_BASE_URL", "JIRA_TOKEN", "JIRA_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    assert main(["jira", "K-1"]) == 1
    err = capsys.readouterr().err
    assert "не заданы переменные окружения: JIRA_BASE_URL, JIRA_TOKEN" in err


def test_http_error_hides_token_and_body(capsys, monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.com")
    monkeypatch.setenv("JIRA_TOKEN", "SECRET")
    monkeypatch.delenv("JIRA_EMAIL", raising=False)

    def boom(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"SECRET body"))

    import sa_fetch
    monkeypatch.setattr(sa_fetch.urllib.request, "urlopen", boom)
    assert main(["jira", "K-1"]) == 1
    err = capsys.readouterr().err
    assert err.strip() == "HTTP 401 от jira.example.com"
    assert "SECRET" not in err


def test_cli_prints_text(capsys, monkeypatch):
    import sa_fetch
    monkeypatch.setenv("JIRA_BASE_URL", "https://j")
    monkeypatch.setenv("JIRA_TOKEN", "t")
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.setattr(sa_fetch.urllib.request, "urlopen", make_opener(ISSUE_V2, []))
    assert main(["jira", "K-1"]) == 0
    assert capsys.readouterr().out.startswith("K-1: Запрет промокода")


@pytest.mark.parametrize("argv", [[], ["jira"], ["foo", "x"], ["jira", "a", "b"]])
def test_cli_bad_args(argv, capsys):
    assert main(argv) == 2
    assert "usage" in capsys.readouterr().err
