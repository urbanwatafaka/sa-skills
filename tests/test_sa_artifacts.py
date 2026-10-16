import pytest

from sa_artifacts import (
    ArtifactError,
    find_refs,
    find_table,
    is_id,
    parse_questions,
    parse_tables,
    ref_prefix,
    split_frontmatter,
)


def test_frontmatter_scalars_and_lists():
    text = "---\nsource: https://jira/x\nbrd_complete: false\nmissing: [роли, цель]\ncount: 3\n---\nтело\n"
    meta, body = split_frontmatter(text)
    assert meta == {
        "source": "https://jira/x",
        "brd_complete": False,
        "missing": ["роли", "цель"],
        "count": 3,
    }
    assert body.strip() == "тело"


def test_frontmatter_absent():
    meta, body = split_frontmatter("| a |\n")
    assert meta == {}
    assert body == "| a |\n"


def test_frontmatter_empty_list_and_date():
    meta, _ = split_frontmatter("---\nmissing: []\nfetched: 2026-10-15\n---\n")
    assert meta == {"missing": [], "fetched": "2026-10-15"}


def test_frontmatter_unclosed():
    with pytest.raises(ArtifactError):
        split_frontmatter("---\na: 1\n")


def test_parse_tables():
    body = (
        "Текст\n\n"
        "| ID   | Требование | Тип |\n"
        "|------|------------|-----|\n"
        "| R-01 | Первое     | UI  |\n"
        "| R-02 | Второе     | функц. |\n"
        "\nхвост\n"
    )
    tables = parse_tables(body)
    assert len(tables) == 1
    assert tables[0].header == ["ID", "Требование", "Тип"]
    assert tables[0].rows[1] == {"ID": "R-02", "Требование": "Второе", "Тип": "функц."}


def test_parse_tables_separator_with_spaces():
    tables = parse_tables("| a | b |\n| --- | :---: |\n| 1 | 2 |\n")
    assert tables[0].rows == [{"a": "1", "b": "2"}]


def test_parse_tables_wrong_cell_count():
    with pytest.raises(ArtifactError):
        parse_tables("| a | b |\n|---|---|\n| 1 |\n")


def test_find_table_by_columns():
    tables = parse_tables("| x |\n|---|\n| 1 |\n\n| ID | Тип |\n|---|---|\n| R-01 | UI |\n")
    assert find_table(tables, ["ID", "Тип"]).rows == [{"ID": "R-01", "Тип": "UI"}]
    assert find_table(tables, ["Нет"]) is None


def test_parse_questions():
    body = (
        "# Вопросы\n\n"
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Что делать с начислениями?\n"
        "  Варианты: а) не пересчитывать; б) пересчитать — *answered*\n"
        "- **Q-PO-02** [R-02, R-03] Какой текст показать? — *open, blocking*\n"
        "\n"
        "## Для аналитика\n"
        "- **Q-SA-01** [IM-04] Есть ли событие в Kafka?\n"
        "  Где проверить: lkp-back/app/Events — *open*\n"
    )
    qs = parse_questions(body)
    assert [q.id for q in qs] == ["Q-PO-01", "Q-PO-02", "Q-SA-01"]
    assert qs[0].status == "answered" and not qs[0].blocking
    assert qs[1].refs == ["R-02", "R-03"]
    assert qs[1].status == "open" and qs[1].blocking
    assert qs[1].text == "Какой текст показать?"
    assert qs[2].audience == "SA" and qs[2].section == "SA"
    assert qs[2].text == "Есть ли событие в Kafka?"


def test_parse_questions_outside_section():
    qs = parse_questions("- **Q-PO-01** [R-01] Вопрос — *open*\n")
    assert qs[0].section == ""


def test_parse_questions_missing_status():
    with pytest.raises(ArtifactError, match="Q-PO-01"):
        parse_questions("## Для PO\n- **Q-PO-01** [R-01] Вопрос без статуса\n")


def test_refs_and_ids():
    assert find_refs("см. R-01, IM-02 и Q-PO-03, D-04, RV-05") == ["R-01", "IM-02", "Q-PO-03", "D-04", "RV-05"]
    assert ref_prefix("Q-SA-01") == "Q"
    assert ref_prefix("IM-10") == "IM"
    assert is_id("R", "R-01")
    assert not is_id("R", "R-1")
    assert is_id("Q", "Q-SA-12")
    assert not is_id("IM", "R-01")


def test_parse_questions_brd_pseudo_ref():
    qs = parse_questions("## Для PO\n- **Q-PO-01** [BRD] Какая цель? — *open*\n")
    assert qs[0].refs == ["BRD"] and qs[0].bad_refs == []


def test_parse_questions_bad_ref_token():
    qs = parse_questions("## Для PO\n- **Q-PO-01** [R-01, цель, BRD] Вопрос — *open*\n")
    assert qs[0].refs == ["R-01", "BRD"]
    assert qs[0].bad_refs == ["цель"]


def test_parse_questions_keeps_details():
    body = (
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Что делать?\n"
        "  Варианты: а) да; б) нет — *open*\n"
        "- **Q-PO-02** [R-02] Без деталей — *open*\n"
    )
    qs = parse_questions(body)
    assert qs[0].details == ["Варианты: а) да; б) нет"]
    assert qs[1].details == []
