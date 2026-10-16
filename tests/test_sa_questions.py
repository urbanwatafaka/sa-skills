import pytest

from sa_artifacts import ArtifactError
from sa_questions import export_questions, main

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


def test_po_export_has_no_refs(task_dir):
    text = export_questions(task_dir, "PO")
    for token in ("R-", "IM-", "D-", "RV-", "["):
        assert token not in text
