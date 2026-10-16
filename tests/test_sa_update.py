import pytest

from conftest import write_review
from sa_artifacts import ArtifactError
from sa_draft import assemble, mark
from sa_state import load_state, save_state, set_value
from sa_update import apply_proposal, build_plan, drop_proposal, main, proposal_diff, render_plan


def _append(path, line):
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + line + "\n", encoding="utf-8")


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _rebuild(task_dir, sid, text):
    (task_dir / "draft" / f"{sid}.md").write_text(text, encoding="utf-8")
    mark(task_dir, [sid])
    assemble(task_dir)


def _sections(plan):
    return [(s.id, s.reasons, s.human) for s in plan.sections]


def test_nothing_to_update(draft_task):
    plan = build_plan(draft_task)
    assert (plan.snapshot, plan.new, plan.changed, plan.removed, plan.sections, plan.unbound) == (True, [], [], [], [], [])
    text = render_plan(plan)
    assert text.splitlines()[0] == "Изменения с последней сборки: новые нет; изменены нет; удалены нет"
    assert "Секции к обновлению: нет" in text


def test_new_decision_hits_placeholder_sections(draft_task):
    _rebuild(draft_task, "02-architecture", "# Архитектура и Процесс\n\nТекст: ⚠ Q-PO-02 ‹R-02›\n")
    _append(draft_task / "decisions.md", "| D-02 | Q-PO-02 | Текст «Нельзя» | PO, чат ММ | 2026-10-16 |")
    _edit(draft_task / "questions.md", "— *open, blocking*", "— *answered*")
    plan = build_plan(draft_task)
    assert plan.new == ["D-02"]
    assert _sections(plan) == [("02-architecture", ["D-02 (⚠ Q-PO-02)"], False)]
    assert "02-architecture | перегенерировать | D-02 (⚠ Q-PO-02)" in render_plan(plan)


def test_new_decision_by_trace_and_unbound(draft_task):
    _rebuild(draft_task, "04-kafka", "## Топики Кафка\n\nСобытие ‹IM-04›\n")
    _append(draft_task / "decisions.md", "| D-02 | Q-SA-01 | Событие публикуется | разработка | 2026-10-16 |")
    _append(draft_task / "decisions.md", "| D-03 | — | Логи храним 30 дней | PO | 2026-10-16 |")
    plan = build_plan(draft_task)
    assert _sections(plan) == [("04-kafka", ["D-02"], False)]
    assert plan.unbound == ["D-03"]
    assert "Без привязки: D-03" in render_plan(plan)


def test_changed_and_removed_rows(draft_task):
    _rebuild(draft_task, "01-brd", "# BRD\n\nИстория ‹R-02›\n")
    _rebuild(draft_task, "05-dependent", "# Зависимые процессы и сервисы\n\nБез пересчёта ‹D-01›\n")
    _edit(draft_task / "sources/BRD.md", "Мерчант видит причину", "Мерчант видит текст причины")
    decisions = draft_task / "decisions.md"
    decisions.write_text("".join(l for l in decisions.read_text(encoding="utf-8").splitlines(keepends=True)
                                 if not l.startswith("| D-01")), encoding="utf-8")
    plan = build_plan(draft_task)
    assert (plan.changed, plan.removed) == (["R-02"], ["D-01"])
    assert _sections(plan) == [("01-brd", ["R-02"], False), ("05-dependent", ["D-01"], False)]


def test_new_impact_and_requirement(draft_task):
    _append(draft_task / "impact-map.md", "| IM-05 | partners-dashboard: promocode/list | API | новый | R-01 | — | допущение | низкая |")
    _append(draft_task / "sources/BRD.md", "| R-04 | Новое требование | функц. |")
    plan = build_plan(draft_task)
    assert plan.new == ["R-04", "IM-05"]
    assert _sections(plan) == [("01-brd", ["R-04"], False), ("03-changes", ["IM-05"], False)]


def test_new_impact_for_missing_optional_section(draft_task):
    (draft_task / "draft/06-configs.md").unlink()
    assemble(draft_task)
    _append(draft_task / "impact-map.md", "| IM-05 | lkp-back: таймаут проверки | конфиг | новый | R-03 | — | допущение | низкая |")
    plan = build_plan(draft_task)
    assert [(s.id, s.reasons, s.missing) for s in plan.sections] == [
        ("03-changes", ["IM-05"], False), ("06-configs", ["IM-05"], True),
    ]
    assert "06-configs | создать | IM-05" in render_plan(plan)


def test_accepted_review_and_human_section(draft_task):
    write_review(draft_task, [
        "| RV-01 | важно | 03-changes | Нет кода | IM-01 | указать код | принято |",
        "| RV-02 | совет | весь черновик | Стиль | — | править | принято |",
        "| RV-03 | совет | 03-changes | Мелочь | — | x | открыто |",
    ])
    (draft_task / "draft/03-changes.md").write_text("# Доработки\n\nПравка аналитика ‹R-01›\n", encoding="utf-8")
    plan = build_plan(draft_task)
    assert plan.accepted == ["RV-01", "RV-02"]
    assert _sections(plan) == [("03-changes", ["RV-01"], True)]
    assert plan.unbound == ["RV-02"]
    assert "03-changes | правка человека — только предложение | RV-01" in render_plan(plan)


def test_closed_placeholder_without_decision(draft_task):
    _rebuild(draft_task, "08-testing", "# Тестирование и регресс\n\nТекст ⚠ Q-PO-01 ‹R-01›\n")
    assert _sections(build_plan(draft_task)) == [("08-testing", ["⚠ Q-PO-01 закрыт"], False)]


def test_no_snapshot(draft_task):
    state = load_state(draft_task)
    del state["rows"]
    save_state(draft_task, state)
    plan = build_plan(draft_task)
    assert plan.snapshot is False and plan.new == []
    assert render_plan(plan).startswith("Снимка строк нет")


def test_proposal_diff_apply_drop(draft_task):
    api = draft_task / "draft/03-changes.md"
    api.write_text("# Доработки\n\nПравка ‹R-01›\n", encoding="utf-8")
    assemble(draft_task)
    proposals = draft_task / "proposals"
    proposals.mkdir()
    (proposals / "03-changes.md").write_text("# Доработки\n\nНовая версия ‹R-01›\n", encoding="utf-8")
    diff = proposal_diff(draft_task, "03-changes")
    assert "-Правка ‹R-01›" in diff and "+Новая версия ‹R-01›" in diff
    assert build_plan(draft_task).proposals == ["03-changes"]
    apply_proposal(draft_task, "03-changes")
    assert api.read_text(encoding="utf-8") == "# Доработки\n\nНовая версия ‹R-01›\n"
    assert not (proposals / "03-changes.md").exists()
    assemble(draft_task)
    assert load_state(draft_task)["sections"]["03-changes"]["edited_by_human"] is False
    (proposals / "02-architecture.md").write_text("x", encoding="utf-8")
    drop_proposal(draft_task, "02-architecture")
    assert not (proposals / "02-architecture.md").exists()
    with pytest.raises(ArtifactError, match="нет предложения proposals/08-testing.md"):
        proposal_diff(draft_task, "08-testing")


def test_published_warning(draft_task):
    set_value(draft_task, "published", "https://wiki/x")
    assert build_plan(draft_task).published == (
        "Опубликовано: https://wiki/x. Перед повторной публикацией сверь страницу с прошлой публикацией "
        "и перенеси ручные правки (shared/access/adapters.md, «Публикация ТЗ», шаг 6)."
    )
    _rebuild(draft_task, "02-architecture", "# Архитектура и Процесс\n\nДругое ‹R-01›\n")
    assert build_plan(draft_task).published.startswith("Опубликовано: https://wiki/x — черновик изменился после публикации.")


def test_needs_draft(task_dir):
    with pytest.raises(ArtifactError, match="нет draft.md"):
        build_plan(task_dir)


def test_cli(draft_task, capsys):
    assert main(["plan", str(draft_task)]) == 0
    assert "Секции к обновлению: нет" in capsys.readouterr().out
    assert main(["diff", str(draft_task), "03-changes"]) == 1
    assert main(["plan"]) == 2
    assert main([]) == 2


def test_changed_and_removed_without_trace_are_unbound(draft_task):
    _edit(draft_task / "sources/BRD.md", "не блокирует регистрацию мерчанта", "не блокирует вход мерчанта")
    plan = build_plan(draft_task)
    assert plan.changed == ["R-03"]
    assert plan.unbound == ["R-03"]
    assert "Без привязки: R-03" in render_plan(plan)
    _edit(draft_task / "sources/BRD.md", "| R-03 |", "| R-04 |")
    plan = build_plan(draft_task)
    assert plan.removed == ["R-03"] and "R-03" in plan.unbound


def test_apply_proposal_keeps_mark_if_write_fails(draft_task, monkeypatch):
    import sa_update

    (draft_task / "draft" / "02-architecture.md").write_text("# Архитектура и Процесс\n\nПравка человека ‹R-01›\n", encoding="utf-8")
    mark(draft_task, ["02-architecture"])
    (draft_task / "proposals").mkdir()
    (draft_task / "proposals" / "02-architecture.md").write_text("# Архитектура и Процесс\n\nНовое ‹R-01›\n", encoding="utf-8")
    before = load_state(draft_task)

    def boom(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(sa_update, "write_atomic", boom)
    with pytest.raises(OSError):
        apply_proposal(draft_task, "02-architecture")
    assert load_state(draft_task) == before
    assert (draft_task / "proposals" / "02-architecture.md").exists()
