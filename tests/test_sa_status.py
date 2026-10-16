from sa_state import record_inputs
from sa_status import build_status, main, next_step

EXPECTED_DEMO = """\
Задача: LKP-DEMO · стадия: clarify · шаблон: feature@2.0
Артефакты: BRD ✓ · impact-map ✓ · context ✓ · questions ✓ · decisions ✓ · draft — · review —
Вопросы PO: открыто 1 (блокирующих 1)
Вопросы аналитику: открыто 1 (блокирующих 0)
Скоуп: не решено 1 (IM-04)
Черновик: секций нет
Устаревшие входы: нет
Следующий шаг: /tdd-clarify — закрыть блокирующие вопросы"""


def test_demo_status(task_dir):
    assert build_status(task_dir) == EXPECTED_DEMO


def test_incomplete_brd(task_dir):
    brd = task_dir / "sources/BRD.md"
    text = brd.read_text(encoding="utf-8")
    text = text.replace("brd_complete: true", "brd_complete: false").replace("missing: []", "missing: [роли, критерии успеха]")
    brd.write_text(text, encoding="utf-8")
    status = build_status(task_dir)
    assert "BRD: неполный — не хватает: роли, критерии успеха" in status
    assert status.endswith("Следующий шаг: переслать вопросы PO, после ответов запустить /tdd-impact повторно")


def test_draft_sections_and_stale(task_dir):
    draft = task_dir / "draft"
    draft.mkdir()
    (draft / "01-context.md").write_text("Контекст\n", encoding="utf-8")
    (draft / "05-api.md").write_text("⚠ Q-PO-02\n⚠ Q-SA-01\n", encoding="utf-8")
    record_inputs(task_dir, ["decisions"])
    decisions = task_dir / "decisions.md"
    decisions.write_text(decisions.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    status = build_status(task_dir)
    assert "Черновик: 01-context, 05-api (⚠ 2)" in status
    assert "Устаревшие входы: decisions" in status


def test_next_step():
    assert next_step("impact", 0, True) == "/tdd-start"
    assert next_step("start", 0, None) == "/tdd-clarify"
    assert next_step("clarify", 0, True) == "/tdd-draft"
    assert next_step("draft", 0, True) == "/tdd-check"
    assert next_step("check", 0, True) == "/tdd-update по принятым замечаниям, затем /tdd-check"
    assert next_step("done", 0, True) == "задача завершена"
    assert next_step("???", 0, True) == "проверь state.json: неизвестная стадия"


def test_next_step_unresolved_scope():
    assert next_step("clarify", 0, True, unresolved_scope=1) == "/tdd-clarify — закрыть блокирующие вопросы"
    assert next_step("clarify", 0, True, unresolved_scope=0) == "/tdd-draft"
    assert next_step("clarify", 1, True, unresolved_scope=0) == "/tdd-clarify — закрыть блокирующие вопросы"
    assert next_step("start", 0, True, unresolved_scope=2) == "/tdd-clarify"


def test_scope_resolved_goes_to_draft(task_dir):
    context = task_dir / "context.md"
    context.write_text(
        context.read_text(encoding="utf-8").replace("| ?        | ждём ответа на Q-SA-01 |", "| в скоупе | —                      |"),
        encoding="utf-8",
    )
    questions = task_dir / "questions.md"
    questions.write_text(
        questions.read_text(encoding="utf-8").replace("— *open, blocking*", "— *answered*"), encoding="utf-8"
    )
    status = build_status(task_dir)
    assert "Скоуп: всё распределено" in status
    assert status.endswith("Следующий шаг: /tdd-draft")


def test_no_context_no_scope_line(task_dir):
    (task_dir / "context.md").unlink()
    assert "Скоуп:" not in build_status(task_dir)


def test_cli(task_dir, tmp_path, capsys):
    assert main([str(task_dir)]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_DEMO
    assert main([str(tmp_path / "nope")]) == 1
    assert main([]) == 2


def test_review_status_and_next_step(draft_task):
    from conftest import write_review
    from sa_review import set_status
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    write_review(draft_task, ["| RV-01 | критично | 12-acceptance | x | R-03 | y | открыто |"])
    status = build_status(draft_task)
    assert "Ревью: открыто 1 (критично 1), принято 0" in status
    assert status.endswith("Следующий шаг: разобрать замечания review.md: /tdd-update <RV-xx…> — принять, «/tdd-update отклонить RV-xx» — отклонить")
    set_status(draft_task, "принято", ["RV-01"])
    assert build_status(draft_task).endswith("Следующий шаг: /tdd-update — внести принятые замечания, затем /tdd-check")
    set_status(draft_task, "отклонено", ["RV-01"])
    assert build_status(draft_task).endswith("Следующий шаг: замечаний нет — завершить: sa_state.py set <папка задачи> stage done")


def test_review_stale_status(draft_task):
    from conftest import write_review
    from sa_draft import assemble, mark
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    write_review(draft_task, [])
    (draft_task / "draft/02-architecture.md").write_text("# Архитектура и Процесс\n\nДругое ‹R-01›\n", encoding="utf-8")
    mark(draft_task, ["02-architecture"])
    assemble(draft_task)
    status = build_status(draft_task)
    assert "Ревью: открыто 0 (критично 0), принято 0 · устарело — черновик менялся после ревью" in status
    assert status.endswith("Следующий шаг: /tdd-check — черновик менялся после ревью")


def test_broken_review_does_not_fail_status(draft_task):
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    (draft_task / "review.md").write_text("---\ndraft: x\nreviewed: 2026-10-16\nround: 1\n---\n# Ревью\n\nпусто\n", encoding="utf-8")
    status = build_status(draft_task)
    assert "Ревью: review.md повреждён — перепишет /tdd-check" in status
    assert status.endswith("Следующий шаг: /tdd-check — review.md повреждён, его перепишет /tdd-check")
