from pathlib import Path

import pytest

from sa_index import SCHEMAS, check_repo, code_refs, main, read_doc

SERVICES = ("shop-api", "shop-legacy", "shop-front")


def _edit(repo, name, old, new):
    path = repo / "docs" / "sa-index" / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


@pytest.mark.parametrize("service", SERVICES)
def test_golden_docs_pass_check(index_repos, service):
    assert check_repo(index_repos(service)) == []


def test_read_doc_returns_rows_by_section(index_repos):
    doc = read_doc(index_repos("shop-api"), "tech.md")
    assert list(doc) == list(SCHEMAS["tech.md"])
    assert doc["API"][0]["Путь"] == "/api/orders"


def test_code_refs():
    assert code_refs("a/b.php:6, c.js:10") == [("a/b.php", 6), ("c.js", 10)]
    assert code_refs("a/b.php") is None
    assert code_refs("—") is None


def test_check_reports_bad_line_and_file(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "tech.md", "routes/api.php:6,", "routes/api.php:99,")
    _edit(repo, "DB.md", "2024_01_01_000000_create_orders_table.php:7","missing.php:7")
    errors = check_repo(repo)
    assert any("в routes/api.php нет строки 99" in e for e in errors)
    assert any("нет файла database/migrations/missing.php" in e for e in errors)


def test_check_reports_bad_code_format_and_escape(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "bctc.md", "app/Http/Controllers/OrderController.php:10 |", "OrderController |")
    _edit(repo, "DB.md", "| orders | Заказы | id, email, amount | database", "| orders | Заказы | id, email, amount | ../x.php:1, database")
    errors = check_repo(repo)
    assert any("«Код»" in e and "OrderController" in e for e in errors)
    assert any("нет файла ../x.php" in e for e in errors)


def test_check_reports_missing_section_and_header(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "DB.md", "## Связи", "## Связки")
    _edit(repo, "tech.md", "| Метод | Путь | Назначение | Код |", "| Метод | URL | Назначение | Код |")
    errors = check_repo(repo)
    assert any("DB.md: нет раздела «## Связи»" in e for e in errors)
    assert any("tech.md#API" in e for e in errors)


def test_check_empty_row_and_cells(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "DB.md", "| нет | — | — | — |", "| нет | x | — | — |")
    _edit(repo, "tech.md", "| Создание заказа | routes", "|  | routes")
    errors = check_repo(repo)
    assert any("строке «нет»" in e for e in errors)
    assert any("пустая ячейка «Назначение»" in e for e in errors)


def test_check_direction(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "tech.md", "| публикует |", "| шлёт |")
    assert any("Направление" in e for e in check_repo(repo))
    _edit(repo, "tech.md", "| шлёт |", "| ? публикует |")
    assert check_repo(repo) == []


def test_check_missing_files_and_only_named(index_repos):
    repo = index_repos("shop-api")
    (repo / "docs" / "sa-index" / "DB.md").unlink()
    assert any("нет файла docs/sa-index/DB.md" in e for e in check_repo(repo))
    assert check_repo(repo, ["tech.md", "bctc.md"]) == []


def test_check_requires_title(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "bctc.md", "# shop-api\n", "shop-api\n")
    assert any("первая строка" in e for e in check_repo(repo))


def test_cli_check(index_repos, capsys):
    repo = index_repos("shop-api")
    assert main(["check", str(repo)]) == 0
    assert capsys.readouterr().out.strip() == "OK"
    assert main(["check", str(repo), "README.md"]) == 2
    _edit(repo, "tech.md", "routes/api.php:6,", "routes/api.php:99,")
    assert main(["check", str(repo), "tech.md"]) == 1


import json
from datetime import date

from conftest import git
from sa_index import STAMP_FILE, changed, format_changed, format_survey, stamp, survey


def test_survey_detects_stacks_and_hints(index_repos):
    api = survey(index_repos("shop-api", docs=False))
    assert api["stack"] == ["laravel"]
    assert api["sources"] == 5
    assert "routes/" in api["hints"] and "database/migrations/" in api["hints"]
    legacy = survey(index_repos("shop-legacy", docs=False))
    assert legacy["stack"] == ["php"]
    assert {"cron/", "templates/"} <= set(legacy["hints"])
    front = survey(index_repos("shop-front", docs=False))
    assert front["stack"] == ["react"]
    assert "src/pages/" in front["hints"]
    assert api["split"] is False


def test_survey_skips_vendor_and_docs(index_repos):
    repo = index_repos("shop-api", docs=False, init=False)
    (repo / "vendor" / "lib").mkdir(parents=True)
    (repo / "vendor" / "lib" / "x.php").write_text("<?php\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "y.php").write_text("<?php\n", encoding="utf-8")
    assert survey(repo)["sources"] == 5


def test_developer_docs_outside_index_ignored(index_repos):
    repo = index_repos("shop-api", docs=False, init=False)
    (repo / "docs").mkdir()
    (repo / "docs" / "tech.md").write_text("# Техническое взаимодействие\n", encoding="utf-8")
    assert survey(repo)["docs"] == {"tech.md": "нет", "DB.md": "нет", "bctc.md": "нет"}
    assert any("нет файла docs/sa-index/tech.md" in e for e in check_repo(repo))


def test_survey_full_without_stamp_marks_existing_docs_human(index_repos):
    result = survey(index_repos("shop-api"))
    assert result["mode"] == "full"
    assert result["docs"] == {"tech.md": "правка человека", "DB.md": "правка человека", "bctc.md": "правка человека"}
    text = format_survey(result)
    assert "mode: full (индексации ещё не было)" in text
    assert "stack: laravel" in text


def test_survey_non_git_repo(index_repos):
    result = survey(index_repos("shop-api", docs=False, init=False))
    assert result["mode"] == "full"
    assert "не git" in result["reason"]
    assert result["docs"]["tech.md"] == "нет"


def test_stamp_then_incremental_and_human_edit(index_repos):
    repo = index_repos("shop-api")
    assert stamp(repo, today=date(2026, 10, 16)) == []
    data = json.loads((repo / "docs" / "sa-index" / STAMP_FILE).read_text(encoding="utf-8"))
    assert data["sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert data["indexed"] == "2026-10-16"
    assert data["plugin"] == "0.8.2"
    assert set(data["files"]) == {"tech.md", "DB.md", "bctc.md"}
    result = survey(repo)
    assert result["mode"] == "incremental"
    assert result["docs"]["tech.md"] == "есть"
    with (repo / "docs" / "sa-index" / "tech.md").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert survey(repo)["docs"]["tech.md"] == "правка человека"


def test_stamp_refuses_invalid_docs(index_repos):
    repo = index_repos("shop-api")
    (repo / "docs" / "sa-index" / "DB.md").unlink()
    assert stamp(repo) == ["нет файла docs/sa-index/DB.md"]
    assert not (repo / "docs" / "sa-index" / STAMP_FILE).exists()


def test_changed_lists_files_and_rows(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    routes = repo / "routes" / "api.php"
    routes.write_text(routes.read_text(encoding="utf-8") + "Route::delete('/api/orders/{id}', [OrderController::class, 'destroy']);\n", encoding="utf-8")
    git(repo, "commit", "-qam", "delete route")
    (repo / "app" / "Services" / "PaymentsClient.php").unlink()
    (repo / "app" / "Services" / "CrmClient.php").write_text("<?php\n", encoding="utf-8")
    (repo / "vendor").mkdir()
    (repo / "vendor" / "z.php").write_text("<?php\n", encoding="utf-8")
    result = changed(repo)
    assert result["mode"] == "incremental"
    assert result["files"] == ["app/Services/CrmClient.php", "app/Services/PaymentsClient.php", "routes/api.php"]
    assert "tech.md#API: POST — routes/api.php:6, app/Http/Controllers/OrderController.php:10" in result["rows"]
    assert "tech.md#Исходящие вызовы: shop-legacy — app/Services/PaymentsClient.php:9" in result["rows"]
    text = format_changed(result)
    assert "  app/Services/PaymentsClient.php (удалён)" in text


def test_changed_full_when_sha_unknown(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    path = repo / "docs" / "sa-index" / STAMP_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sha"] = "0" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    result = changed(repo)
    assert result["mode"] == "full"
    assert "не найден" in result["reason"]
    assert "mode: full" in format_changed(result)


def test_cli_survey_changed_stamp(index_repos, capsys):
    repo = index_repos("shop-api")
    assert main(["survey", str(repo)]) == 0
    assert "sources: 5" in capsys.readouterr().out
    assert main(["stamp", str(repo)]) == 0
    assert main(["changed", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "mode: incremental" in out and "files:\n  нет" in out


def test_changed_rename_reports_both_paths(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    git(repo, "mv", "app/Services/PaymentsClient.php", "app/Services/Pay.php")
    git(repo, "commit", "-qam", "rename")
    result = changed(repo)
    assert "app/Services/Pay.php" in result["files"]
    assert "app/Services/PaymentsClient.php" in result["files"]
    assert "app/Services/PaymentsClient.php" in result["deleted"]
    assert "tech.md#Исходящие вызовы: shop-legacy — app/Services/PaymentsClient.php:9" in result["rows"]


def test_detect_stack_dotnet_in_nested_project(tmp_path):
    from sa_index import detect_stack

    (tmp_path / "src" / "Shop").mkdir(parents=True)
    (tmp_path / "src" / "Shop" / "Shop.csproj").write_text("<Project/>", encoding="utf-8")
    assert "dotnet" in detect_stack(tmp_path, [])
    (tmp_path / "src" / "Shop" / "Shop.csproj").unlink()
    assert "dotnet" not in detect_stack(tmp_path, [])
    assert "dotnet" in detect_stack(tmp_path, [Path("src/Shop/Program.cs")])


def test_changed_reports_invalid_docs(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    (repo / "docs" / "sa-index" / "DB.md").write_text("мусор\n", encoding="utf-8")
    result = changed(repo)
    assert result["invalid"] == ["DB.md"]
    assert "invalid: DB.md (не по схеме — полный проход)" in format_changed(result)


def test_changed_no_invalid_line(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    assert "invalid: нет" in format_changed(changed(repo))


def test_changed_full_when_git_diff_fails(index_repos, monkeypatch):
    import sa_index

    repo = index_repos("shop-api")
    stamp(repo)
    original = sa_index._git
    monkeypatch.setattr(sa_index, "_git", lambda r, *a: None if a[0] == "diff" else original(r, *a))
    result = changed(repo)
    assert result["mode"] == "full"
    assert result["reason"] == "git diff не удался"


def test_branch_status_marker(index_repos):
    from sa_index import branch_status

    repo = index_repos("shop-api")
    assert "без upstream" in branch_status(repo)
