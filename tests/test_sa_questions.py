import pytest

from sa_artifacts import ArtifactError
from sa_questions import export_questions, main, set_answer, set_status, unblock

EXPECTED_PO = """\
Вопросы по задаче LKP-DEMO

Q-PO-02. Какой текст показать мерчанту, если он указал собственный промокод? (нужен ответ до черновика ТЗ)

Пожалуйста, отвечайте с номером вопроса, например: «Q-PO-02: …»."""

EXPECTED_SA = """\
Вопросы по задаче LKP-DEMO

Q-SA-01 [IM-04]. Публикует ли lkp-back событие в Kafka при сохранении анкеты?
   Где проверить: lkp-back/app/Events"""


def test_export_po(task_dir):
    assert export_questions(task_dir, "PO") == EXPECTED_PO


def test_export_sa(task_dir):
    assert export_questions(task_dir, "SA") == EXPECTED_SA


def test_blocking_first_and_details(task_dir):
    (task_dir / "questions.md").write_text(
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Обычный вопрос\n"
        "  Варианты: а) да; б) нет — *open*\n"
        "- **Q-PO-02** [R-02] Срочный вопрос — *open, blocking*\n"
        "- **Q-PO-03** [R-03] Закрытый вопрос — *answered*\n",
        encoding="utf-8",
    )
    text = export_questions(task_dir, "PO")
    assert text.index("Q-PO-02.") < text.index("Q-PO-01.")
    assert "   Варианты: а) да; б) нет" in text
    assert "Q-PO-03" not in text
    assert text.endswith("например: «Q-PO-02: …».")


def test_no_open_questions(task_dir):
    (task_dir / "questions.md").unlink()
    assert export_questions(task_dir, "PO") == "Открытых вопросов для PO нет."
    assert export_questions(task_dir, "SA") == "Открытых вопросов для аналитика нет."


def test_bad_audience(task_dir):
    with pytest.raises(ArtifactError, match="PO или SA"):
        export_questions(task_dir, "QA")


def test_cli(task_dir, tmp_path, capsys):
    assert main(["export", str(task_dir)]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_PO
    assert main(["export", str(task_dir), "SA"]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_SA
    assert main(["export", str(tmp_path / "nope")]) == 1
    assert main(["export"]) == 2


def test_deadline_after_draft(task_dir):
    from sa_state import set_value

    set_value(task_dir, "stage", "draft")
    assert "(нужен ответ до готовности ТЗ)" in export_questions(task_dir, "PO")


MULTI = (
    "# Вопросы\n\n## Для PO\n"
    "- **Q-PO-01** [R-01] Первый\n  Варианты: а) да; б) нет — *open, blocking*\n  Где проверить: x\n"
    "- **Q-PO-02** [R-02] Второй — *open*\n\n"
    "## Для аналитика\n- **Q-SA-01** [IM-01] Третий — *open, blocking*\n"
)


def _questions(task_dir, text=MULTI):
    from sa_artifacts import parse_questions

    (task_dir / "questions.md").write_text(text, encoding="utf-8")
    return lambda: {q.id: q for q in parse_questions((task_dir / "questions.md").read_text(encoding="utf-8"))}


def test_set_status_marker_on_continuation(task_dir):
    read = _questions(task_dir)
    assert set_status(task_dir, "answered", ["Q-PO-01", "Q-PO-02"]) == ["Q-PO-01", "Q-PO-02"]
    q = read()
    assert (q["Q-PO-01"].status, q["Q-PO-01"].blocking, q["Q-PO-02"].status) == ("answered", False, "answered")
    assert q["Q-PO-01"].details == ["Варианты: а) да; б) нет", "Где проверить: x"]
    assert q["Q-SA-01"].status == "open"
    with pytest.raises(ArtifactError, match="Q-PO-01 уже answered"):
        set_status(task_dir, "obsolete", ["Q-PO-01"])
    with pytest.raises(ArtifactError, match="нет вопроса Q-PO-09"):
        set_status(task_dir, "answered", ["Q-PO-09"])
    with pytest.raises(ArtifactError, match="answered или obsolete"):
        set_status(task_dir, "open", ["Q-SA-01"])


def test_set_answer(task_dir):
    read = _questions(task_dir)
    set_answer(task_dir, "Q-PO-02", "предварительно — да")
    assert read()["Q-PO-02"].answer == "предварительно — да"
    set_answer(task_dir, "Q-PO-02", "окончательно — да")
    q = read()["Q-PO-02"]
    assert q.answer == "окончательно — да" and q.status == "open"
    assert q.details == ["Ответ в ТЗ: окончательно — да"]
    with pytest.raises(ArtifactError, match="«Ответ в ТЗ»"):
        set_status(task_dir, "obsolete", ["Q-PO-02"])
    set_status(task_dir, "obsolete", ["Q-SA-01"])
    with pytest.raises(ArtifactError, match="неактуален"):
        set_answer(task_dir, "Q-SA-01", "x")


def test_unblock(task_dir):
    read = _questions(task_dir)
    decisions = task_dir / "decisions.md"
    decisions.write_text(
        decisions.read_text(encoding="utf-8")
        + "| D-02 | Q-SA-01 | Не блокируем, предварительно — да | аналитик | 2026-10-20 |\n",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactError, match="D-02 записано не на Q-PO-01"):
        unblock(task_dir, "Q-PO-01", "D-02")
    with pytest.raises(ArtifactError, match="нет решения D-09"):
        unblock(task_dir, "Q-PO-01", "D-09")
    unblock(task_dir, "Q-PO-01", "D-01")
    q = read()["Q-PO-01"]
    assert (q.status, q.blocking) == ("open", False)
    with pytest.raises(ArtifactError, match="не блокирующий"):
        unblock(task_dir, "Q-PO-01", "D-01")


def test_unblock_scope_question(task_dir):
    _questions(task_dir, MULTI.replace("[IM-01] Третий", "[IM-04] Третий"))
    with pytest.raises(ArtifactError, match="«Границах»"):
        unblock(task_dir, "Q-SA-01", "D-01")


def test_cli_edit_commands(task_dir):
    _questions(task_dir)
    assert main(["status", str(task_dir), "answered", "Q-PO-02"]) == 0
    assert main(["answer", str(task_dir), "Q-PO-01", "да"]) == 0
    assert main(["unblock", str(task_dir), "Q-PO-01", "D-09"]) == 1
    assert main(["answer", str(task_dir), "Q-PO-01"]) == 2
    assert main(["status", str(task_dir), "answered"]) == 2


def test_po_export_has_no_refs(task_dir):
    text = export_questions(task_dir, "PO")
    for token in ("R-", "IM-", "D-", "RV-", "["):
        assert token not in text
