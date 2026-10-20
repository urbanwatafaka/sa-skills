import json

import pytest

from sa_locale import entries, find, locale_files, main, render

RU = {
    "pageTitles": {"saleChannels": "Каналы продаж"},
    "sections": {
        "saleChannels": {
            "details": {
                "tabs": {"mainSettings": "Данные о канале"},
                "mainSettings": {"fields": {"logo": {"label": "Загрузите логотип"}}},
            }
        }
    },
    "steps": ["Шаг первый", "Ещё шаг"],
}


@pytest.fixture
def front(tmp_path):
    repo = tmp_path / "cabinet.client"
    (repo / "src/locales").mkdir(parents=True)
    (repo / "src/locales/ru-RU.json").write_text(json.dumps(RU, ensure_ascii=False, indent=2), encoding="utf-8")
    (repo / "node_modules/x/locales").mkdir(parents=True)
    (repo / "node_modules/x/locales/ru.json").write_text('{"a": "Данные о канале"}', encoding="utf-8")
    return repo


def test_locale_files_skip_node_modules(front):
    assert [p.relative_to(front).as_posix() for p in locale_files(front)] == ["src/locales/ru-RU.json"]


def test_entries_lines(front):
    path = front / "src/locales/ru-RU.json"
    lines = path.read_text(encoding="utf-8").splitlines()
    for key, text, line in entries(path):
        assert text in lines[line - 1], key
    assert ("steps[1]", "Ещё шаг") in [(k, t) for k, t, _ in entries(path)]


def test_find_text_and_key(front):
    exact = find(front, "данные о канале")
    assert [(h[2], h[4]) for h in exact] == [("sections.saleChannels.details.tabs.mainSettings", True)]
    assert find(front, "Основные настройки") == []
    keys = find(front, "mainSettings")
    assert keys[0][2] == "sections.saleChannels.details.tabs.mainSettings" and keys[0][4]
    assert "sections.saleChannels.details.mainSettings.fields.logo.label" in [h[2] for h in keys]
    assert [h[3] for h in find(front, "логотип")] == ["Загрузите логотип"]


def test_render_and_cli(front, tmp_path, capsys):
    out = render(front, ["Каналы продаж", "Нет такого"]).splitlines()
    assert out[0] == "«Каналы продаж»: точных 1, всего 1"
    assert out[1].startswith("  = cabinet.client/src/locales/ru-RU.json:") and out[1].endswith("pageTitles.saleChannels = «Каналы продаж»")
    assert out[2].startswith("«Нет такого»: не найдено")
    assert main(["find", str(front), "логотип"]) == 0
    assert "Загрузите логотип" in capsys.readouterr().out
    assert main(["find", str(tmp_path)]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["find", str(empty), "x"]) == 1
