import csv
import json
import re
from pathlib import Path

import pytest

from sa_artifacts import ArtifactError
from sa_qa import (
    affected,
    coverage,
    coverage_table,
    export_csv,
    export_preview,
    human_cases,
    main,
    mark,
    precheck,
)


def cases_path(task: Path) -> Path:
    return task / "qa" / "cases.md"


def edit_case(task: Path, tc: str, step: str) -> None:
    text = cases_path(task).read_text(encoding="utf-8")
    head = text.index(f"### {tc} ")
    at = text.index("**Ожидаемый результат:**", head)
    cases_path(task).write_text(text[:at] + f"9. {step}\n\n" + text[at:], encoding="utf-8")


def delete_case(task: Path, tc: str) -> None:
    text = cases_path(task).read_text(encoding="utf-8")
    text = re.sub(rf"### {tc} .*?(?=^##)", "", text, count=1, flags=re.S | re.M)
    cases_path(task).write_text(text, encoding="utf-8")


def set_unit_status(task: Path, uid: str, status: str, reason: str = "") -> None:
    path = task / "qa" / "units.md"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {uid} |"):
            cells = line.strip("|").split("|")
            cells[3], cells[4] = f" {status} ", f" {reason} "
            line = "|" + "|".join(cells) + "|"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def change_decision(task: Path, did: str) -> None:
    path = task / "decisions.md"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {did} |"):
            cells = line.strip("|").split("|")
            cells[2] = cells[2].rstrip() + " Уточнено. "
            line = "|" + "|".join(cells) + "|"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_qa_questions(task: Path, status: str) -> None:
    (task / "qa" / "questions.md").write_text(
        f"# Вопросы QA\n\n## Для аналитика\n- **Q-QA-01** [D-01] Какой код ответа при файле 0 байт? — *{status}*\n",
        encoding="utf-8",
    )


def test_mark_and_human_edit(qa_cases_task):
    assert mark(qa_cases_task, "все") == ["TC-01", "TC-02", "TC-03"]
    assert human_cases(qa_cases_task) == []
    edit_case(qa_cases_task, "TC-02", "Новый шаг")
    assert human_cases(qa_cases_task) == ["TC-02"]
    state = json.loads((qa_cases_task / "qa" / "state.json").read_text(encoding="utf-8"))
    assert state["cases"]["TC-01"]["exported"] is None and "D-01" in state["rows"]


def test_mark_selected_and_unknown(qa_cases_task):
    assert mark(qa_cases_task, ["TC-02"]) == ["TC-02"]
    assert human_cases(qa_cases_task) == ["TC-01", "TC-03"]
    with pytest.raises(ArtifactError, match="TC-09"):
        mark(qa_cases_task, ["TC-09"])


def test_coverage_and_precheck(qa_cases_task):
    rows = {u: (s, tcs) for u, s, tcs in coverage(qa_cases_task)}
    assert rows["U-01"][1] == ["TC-01"]
    msgs = precheck(qa_cases_task)
    assert any("U-02" in m and "без кейса" in m for m in msgs)
    assert "| U-01 | тестируется | TC-01 |" in coverage_table(qa_cases_task)


def test_precheck_statuses(qa_cases_task):
    set_unit_status(qa_cases_task, "U-02", "не тестируется", "нет стенда")
    set_unit_status(qa_cases_task, "U-06", "нужно решение", "нужен DevOps")
    msgs = precheck(qa_cases_task)
    assert not any(m.startswith("U-02") for m in msgs)
    assert any(m.startswith("U-06") and "нужно решение" in m for m in msgs)
    assert "не тестируется: нет стенда" in coverage_table(qa_cases_task)


def test_precheck_lint_and_missing_id(qa_cases_task):
    text = cases_path(qa_cases_task).read_text(encoding="utf-8")
    text = text.replace("### TC-03 ", "### ").replace("Ответ `400`;", "Ответ `400`, работает корректно;")
    cases_path(qa_cases_task).write_text(text, encoding="utf-8")
    msgs = precheck(qa_cases_task)
    assert any(m.startswith("TC-01") and "расплывчато" in m for m in msgs)
    assert any("нет ID" in m for m in msgs)


def test_precheck_placeholders(qa_cases_task):
    text = cases_path(qa_cases_task).read_text(encoding="utf-8").replace("Ответ `400`;", "Ответ `400` ⚠ Q-QA-01;")
    cases_path(qa_cases_task).write_text(text, encoding="utf-8")
    write_qa_questions(qa_cases_task, "open")
    assert not any("Q-QA-01" in m for m in precheck(qa_cases_task))
    write_qa_questions(qa_cases_task, "answered")
    assert any("TC-01" in m and "Q-QA-01" in m for m in precheck(qa_cases_task))
    (qa_cases_task / "qa" / "questions.md").unlink()
    assert any("TC-01" in m and "Q-QA-01" in m for m in precheck(qa_cases_task))


def test_deleted_case_not_restored(qa_cases_task):
    delete_case(qa_cases_task, "TC-01")
    assert any("U-01" in m for m in precheck(qa_cases_task))
    assert "TC-01" not in (qa_cases_task / "qa/cases.md").read_text(encoding="utf-8")


def test_cover_ref_to_removed_unit(qa_cases_task):
    set_unit_status(qa_cases_task, "U-04", "удал.")
    assert any("TC-01" in m and "U-04" in m for m in precheck(qa_cases_task))
    text = cases_path(qa_cases_task).read_text(encoding="utf-8").replace("U-01, U-04", "U-01, U-99")
    cases_path(qa_cases_task).write_text(text, encoding="utf-8")
    assert any("TC-01" in m and "U-99" in m for m in precheck(qa_cases_task))


def test_export_csv_roundtrip(qa_cases_task):
    path = export_csv(qa_cases_task, "PF2-3964")
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline="")))
    assert rows[0] == ["ID", "Name", "Description", "Precondition", "Scenario", "Expected result", "Priority", "Status"]
    assert rows[1][0] == "PF2-3964-TC-01" and rows[1][7] == "Draft"
    assert '"merchantId"' in rows[1][4] and "«" in "".join(r[5] for r in rows[1:])
    assert rows[1][4].startswith("1. Вызвать метод") and "\n2. Найти" in rows[1][4]
    assert 'logo, \\"big\\"' in rows[1][4]
    assert len(rows) == 4


def test_export_preview_and_marks(qa_cases_task):
    mark(qa_cases_task, "все")
    assert export_preview(qa_cases_task) == {"новые": ["TC-01", "TC-02", "TC-03"], "изменённые": [], "неизменные": []}
    export_csv(qa_cases_task, "PF2-3964")
    edit_case(qa_cases_task, "TC-03", "Ещё шаг")
    assert export_preview(qa_cases_task) == {"новые": [], "изменённые": ["TC-03"], "неизменные": ["TC-01", "TC-02"]}


def test_export_refuses_case_without_id(qa_cases_task):
    text = cases_path(qa_cases_task).read_text(encoding="utf-8").replace("### TC-03 ", "### ")
    cases_path(qa_cases_task).write_text(text, encoding="utf-8")
    with pytest.raises(ArtifactError, match="нет ID"):
        export_csv(qa_cases_task, "PF2-3964")


def test_affected_by_changed_decision(qa_cases_task):
    mark(qa_cases_task, "все")
    assert affected(qa_cases_task) == []
    change_decision(qa_cases_task, "D-01")
    assert ("TC-01", ["D-01"]) in affected(qa_cases_task)
    assert all(tc != "TC-03" for tc, _ in affected(qa_cases_task))


def test_affected_by_changed_unit(qa_cases_task):
    from sa_qa_units import sync_units

    mark(qa_cases_task, "все")
    path = qa_cases_task / "draft" / "01-brd.md"
    path.write_text(path.read_text(encoding="utf-8").replace("имя и размер ‹R-03›", "имя, размер и дата ‹R-03›"), encoding="utf-8")
    sync_units(qa_cases_task)
    assert ("TC-01", ["U-01"]) in affected(qa_cases_task)


def test_cli(qa_cases_task, capsys):
    task = str(qa_cases_task)
    assert main(["units", task]) == 0
    assert "единиц" in capsys.readouterr().out
    assert main(["mark", task, "все"]) == 0
    assert main(["coverage", task]) == 0
    assert "| U | Статус | Кейсы |" in capsys.readouterr().out
    assert main(["precheck", task]) == 0
    assert "U-02" in capsys.readouterr().out
    assert main(["preview", task]) == 0
    assert main(["export", task, "PF2-3964"]) == 0
    assert (qa_cases_task / "qa" / "allure-import.csv").exists()
    assert main(["affected", task]) == 0
    assert main(["human", task]) == 0
    assert main(["mark", task, "TC-77"]) == 1
    assert main(["bogus", task]) == 2
    assert main([]) == 2


def test_human_unit_status_is_not_tz_change(qa_cases_task):
    mark(qa_cases_task, "все")
    set_unit_status(qa_cases_task, "U-01", "не тестируется", "нет стенда")
    assert affected(qa_cases_task) == []
    set_unit_status(qa_cases_task, "U-01", "удал.")
    assert ("TC-01", ["U-01"]) in affected(qa_cases_task)


def test_cli_precheck_prints_cases_sha(qa_cases_task, capsys):
    from sa_state import file_sha1

    assert main(["precheck", str(qa_cases_task)]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first == f"cases: {file_sha1(qa_cases_task / 'qa' / 'cases.md')}"
