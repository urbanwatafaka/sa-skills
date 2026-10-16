import pytest

from conftest import write_review
from sa_artifacts import ArtifactError
from sa_draft import assemble, mark
from sa_review import (
    Finding, as_is, coverage, coverage_table, main, precheck, render_precheck, review_rows, review_summary, set_status,
)
from sa_state import file_sha1
from sa_template import load_manifest

ALL = [s.id for s in load_manifest("feature").sections]
ACCEPTANCE = (
    "# BRD\n\n## User Stories\n\n| Контекст | User Story | Критерии приемки |\n|---|---|---|\n"
    "| ЛК | Я, **как** Мерчант,<br/>**хочу** x,<br/>**чтобы** y. ‹R-01› | • Условие → результат ‹R-01, R-02›<br/>• Ещё ‹R-01› |\n"
    "| ЛК | Я, **как** Мерчант,<br/>**хочу** z,<br/>**чтобы** w. ‹R-01› | • Условие → результат ‹R-01› |\n"
)
ROW_OPEN = "| RV-01 | критично | 01-brd | R-03 не покрыт | R-03 | добавить критерий | открыто |"
ROW_ADVICE = "| RV-02 | совет | 03-changes | Нет кода ответа | IM-01 | указать код | открыто |"


def _rebuild(task_dir, sid, text):
    (task_dir / "draft" / f"{sid}.md").write_text(text, encoding="utf-8")
    mark(task_dir, [sid])
    assemble(task_dir)


def test_coverage(draft_task):
    _rebuild(draft_task, "01-brd", ACCEPTANCE)
    assert coverage(draft_task) == [
        ("R-01", ALL, ["история 1", "история 2"]),
        ("R-02", ["01-brd"], ["история 1"]),
        ("R-03", [], []),
    ]
    table = coverage_table(draft_task).splitlines()
    assert table[:2] == ["| R | Секции | Истории |", "|---|---|---|"]
    assert table[-1] == "| R-03 | — | — |"
    assert table[3] == "| R-02 | 01-brd | история 1 |"


def test_precheck(draft_task):
    _rebuild(draft_task, "02-architecture", "# Архитектура и Процесс\n\nТекст ⚠ Q-PO-02 и ⚠ Q-PO-01 ‹R-01›\n")
    findings = precheck(draft_task)
    assert Finding("важно", "02-architecture", "⚠ Q-PO-02: неизвестное не закрыто", "Q-PO-02",
                   "закрыть Q-PO-02 в /tdd-clarify, затем /tdd-update") in findings
    assert Finding("важно", "02-architecture", "⚠ Q-PO-01 стоит на закрытом вопросе", "Q-PO-01",
                   "/tdd-update заменит плейсхолдер по решению") in findings
    assert Finding("критично", "01-brd",
                   "R-03 (функц.) не покрыт ни одним критерием приёмки User Stories (нет ни в одной секции)",
                   "R-03", "добавить критерий со ссылкой ‹R-03› в таблицу User Stories") in findings
    assert Finding("важно", "03-changes", "IM-02 (новый/изм.) не описан ни в одной секции", "IM-02",
                   "описать в 03-changes или исключить в context.md") in findings
    problems = [f.problem for f in findings]
    assert any(p.startswith("R-01 (функц.) не покрыт ни одним критерием приёмки User Stories (есть в 01-brd") for p in problems)
    assert any(p.startswith("R-02 (UI) не покрыт") for p in problems)
    assert not any(p.startswith("IM-04") for p in problems)
    lines = render_precheck(draft_task).splitlines()
    assert lines[0] == f"draft: {file_sha1(draft_task / 'draft.md')}"
    assert lines[2] == "| Важность | Где | Проблема | ← Ссылка | Предложение |"


def test_precheck_needs_draft(draft_task):
    (draft_task / "draft.md").unlink()
    with pytest.raises(ArtifactError, match="нет draft.md"):
        precheck(draft_task)


def test_as_is(draft_task):
    _rebuild(draft_task, "03-changes",
             "# Доработки\n\n1. Правило валидации промокода — добавить проверку владельца. ‹IM-02, IM-01›\n"
             "2. Новый метод владельца промокода. ‹IM-01›\n3. Текст без ссылок на карту. ‹R-01›\n")
    _rebuild(draft_task, "08-testing",
             "# Тестирование и регресс\n\n## Новое поведение\n\n1. Новое ‹R-01›\n\n"
             "## Сохраняемое поведение\n\n- Анкета без промокода сохраняется. ‹R-01›\n- Формат проверяется. ‹IM-02›\n")
    assert as_is(draft_task) == {
        "lkp-back": [
            "[существует] 03-changes: 1. Правило валидации промокода — добавить проверку владельца. ‹IM-02, IM-01›",
            "[сохраняется] 08-testing: Формат проверяется. ‹IM-02›",
        ],
        "без сервиса": ["[сохраняется] 08-testing: Анкета без промокода сохраняется. ‹R-01›"],
    }


def test_set_status(draft_task):
    write_review(draft_task, [ROW_OPEN, ROW_ADVICE])
    assert set_status(draft_task, "принято", ["RV-01"]) == ["RV-01"]
    assert set_status(draft_task, "отклонено", ["все"]) == ["RV-02"]
    assert [r["Статус"] for r in review_rows(draft_task)] == ["принято", "отклонено"]
    with pytest.raises(ArtifactError, match="нет замечания RV-09"):
        set_status(draft_task, "принято", ["RV-09"])
    with pytest.raises(ArtifactError, match="статус: принято или отклонено"):
        set_status(draft_task, "закрыто", ["RV-01"])
    path = draft_task / "review.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| принято |", "| закрыто |"), encoding="utf-8")
    with pytest.raises(ArtifactError, match="RV-01 уже закрыто"):
        set_status(draft_task, "отклонено", ["RV-01"])


def test_review_summary(draft_task):
    assert review_summary(draft_task) is None
    write_review(draft_task, [ROW_OPEN, ROW_ADVICE])
    set_status(draft_task, "принято", ["RV-02"])
    assert review_summary(draft_task) == {"open": 1, "critical": 1, "accepted": 1, "stale": False}
    _rebuild(draft_task, "02-architecture", "# Архитектура и Процесс\n\nДругое ‹R-01›\n")
    assert review_summary(draft_task)["stale"] is True


def test_cli(draft_task, capsys):
    assert main(["precheck", str(draft_task)]) == 0
    assert capsys.readouterr().out.startswith("draft: ")
    assert main(["coverage", str(draft_task)]) == 0
    assert main(["asis", str(draft_task)]) == 0
    assert "Утверждений о существующем нет" in capsys.readouterr().out
    assert main(["status", str(draft_task), "принято", "RV-01"]) == 1
    write_review(draft_task, [ROW_OPEN])
    assert main(["status", str(draft_task), "принято", "RV-01"]) == 0
    assert main(["status", str(draft_task), "принято"]) == 2
    assert main([]) == 2


def test_precheck_unknown_question_placeholder(draft_task):
    _rebuild(draft_task, "02-architecture", "# Архитектура и Процесс\n\nТекст ⚠ Q-PO-77 ‹R-01›\n")
    findings = precheck(draft_task)
    assert Finding("важно", "02-architecture", "⚠ Q-PO-77: вопрос не найден в questions.md", "Q-PO-77",
                   "завести Q-PO-77 или убрать плейсхолдер") in findings
    assert not any("закрытом" in f.problem and "Q-PO-77" in f.problem for f in findings)
