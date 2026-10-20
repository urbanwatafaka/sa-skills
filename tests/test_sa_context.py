import pytest

from sa_artifacts import ArtifactError, find_table, parse_tables
from sa_context import main, set_scope


def _scope(task_dir):
    table = find_table(parse_tables((task_dir / "context.md").read_text(encoding="utf-8")), ["← IM", "Скоуп"])
    return {row["← IM"]: (row["Скоуп"], row["Комментарий"]) for row in table.rows}


def test_set_scope_in_place(task_dir):
    assert set_scope(task_dir, ["IM-04"], "вне скоупа", "решили не трогать (D-01)") == []
    assert set_scope(task_dir, ["IM-01", "IM-02"], "?", "Q-SA-01") == []
    scope = _scope(task_dir)
    assert scope["IM-04"] == ("вне скоупа", "решили не трогать (D-01)")
    assert scope["IM-01"] == scope["IM-02"] == ("?", "Q-SA-01")
    assert scope["IM-03"] == ("в скоупе", "—")
    text = (task_dir / "context.md").read_text(encoding="utf-8")
    assert "## Ограничения" in text and text.index("IM-04") < text.index("## Ограничения")


def test_set_scope_appends_missing_row(task_dir):
    (task_dir / "context.md").write_text(
        (task_dir / "context.md").read_text(encoding="utf-8").replace("| IM-04 | ?        | ждём ответа на Q-SA-01 |\n", ""),
        encoding="utf-8",
    )
    assert set_scope(task_dir, ["IM-04"], "в скоупе") == ["IM-04"]
    assert list(_scope(task_dir))[-1] == "IM-04"
    assert _scope(task_dir)["IM-04"] == ("в скоупе", "—")


@pytest.mark.parametrize("ids, scope, comment, message", [
    (["IM-01"], "вне скоупа", "", "нужна причина"),
    (["IM-01"], "?", "потом", "ID вопроса"),
    (["IM-01"], "в работе", "", "скоуп"),
    (["IM-99"], "в скоупе", "", "IM-99 нет в impact-map.md"),
    (["IM-01"], "вне скоупа", "a | b", "«\\|»"),
])
def test_set_scope_errors(task_dir, ids, scope, comment, message):
    with pytest.raises(ArtifactError, match=message):
        set_scope(task_dir, ids, scope, comment)


def test_cli(task_dir, capsys):
    assert main(["scope", str(task_dir), "IM-01", "IM-02", "вне скоупа", "причина"]) == 0
    assert capsys.readouterr().out.strip() == "вне скоупа: IM-01, IM-02"
    assert main(["scope", str(task_dir), "IM-01", "в скоупе"]) == 0
    assert main(["scope", str(task_dir), "IM-01", "вне скоупа"]) == 1
    assert main(["scope", str(task_dir), "в скоупе"]) == 2
    assert main(["scope", str(task_dir), "IM-01", "x", "y", "z"]) == 2
