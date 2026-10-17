from pathlib import Path

import pytest

from sa_artifacts import ArtifactError
from sa_qa_units import Unit, extract_units, load_units, sync_units

REWORDED_OLD = "ЛК, канал продаж: загрузить логотип — файл сразу отображается на вкладке «Данные о канале»."
REWORDED_NEW = "ЛК, канал продаж: загрузить логотип — файл отображается сразу на вкладке «Данные о канале»."


def edit_testing(task: Path, insert_first: str | None = None, reword: tuple[str, str] | None = None) -> None:
    path = task / "draft" / "08-testing.md"
    text = path.read_text(encoding="utf-8")
    if reword:
        text = text.replace(*reword)
    if insert_first:
        lines = text.splitlines()
        start = lines.index("## Новое поведение") + 2
        items = []
        for line in lines[start:]:
            if not line[:1].isdigit():
                break
            items.append(line.split(". ", 1)[1])
        items.insert(0, insert_first)
        lines[start:start + len(items) - 1] = [f"{n}. {item}" for n, item in enumerate(items, start=1)]
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def set_status_in_file(task: Path, uid: str, status: str, reason: str) -> None:
    path = task / "qa" / "units.md"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {uid} |"):
            cells = line.strip("|").split("|")
            cells[3], cells[4] = f" {status} ", f" {reason} "
            line = "|" + "|".join(cells) + "|"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_item(task: Path, where: str) -> None:
    text = next(u.text for u in extract_units(task) if u.where == where)
    section = where.split("/", 1)[0]
    path = task / "draft" / f"{section}.md"
    body = path.read_text(encoding="utf-8")
    if section == "01-brd" and "/story-" in where:
        body = body.replace(f"• {text}", "• Заменённый пункт", 1)
    else:
        lines = [line for line in body.splitlines() if text not in line]
        body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")


def test_extract_units_sources(qa_task):
    where = [u.where for u in extract_units(qa_task)]
    assert "01-brd/story-1/1" in where
    assert any(w.startswith("03-changes/payform.payment.saleschannels/Back/1.") for w in where)
    assert "08-testing/new/1" in where and "08-testing/keep/1" in where


def test_extract_units_all_locations(qa_task):
    units = extract_units(qa_task)
    where = [u.where for u in units]
    assert where[:4] == ["01-brd/story-1/1", "01-brd/story-1/2", "01-brd/story-2/1", "01-brd/ui/1"]
    front = "03-changes/payform.cabinet.client/Front/Канал продаж — «Данные о канале»"
    assert [w for w in where if w.startswith(front)] == [f"{front}/1", f"{front}/1.1", f"{front}/1.2"]
    back = "03-changes/payform.payment.saleschannels/Back/"
    assert [w[len(back):] for w in where if w.startswith(back)] == [
        "1", "1.1", "1.2", "1.2.1", "1.3", "1.4", "2", "2.1",
    ]
    assert where[-5:] == ["08-testing/new/1", "08-testing/new/2", "08-testing/new/3", "08-testing/keep/1", "08-testing/keep/2"]
    assert all(u.id == "" for u in units)


def test_extract_units_keeps_trace(qa_task):
    u = next(u for u in extract_units(qa_task) if u.where == "08-testing/new/1")
    assert "R-01" in u.refs and "‹" not in u.text


def test_extract_continuation_line_joined(qa_task):
    u = next(u for u in extract_units(qa_task) if u.where.endswith("/Back/2.1"))
    assert u.text.endswith("Повтор отправляет файл заново.") and u.refs == ["R-01"]


def test_extract_without_draft(task_dir):
    assert extract_units(task_dir) == []


def test_sync_assigns_and_keeps_ids(qa_task):
    first = sync_units(qa_task)
    assert first[0].id == "U-01"
    first_id_of_reworded = next(u.id for u in first if u.text == REWORDED_OLD)
    # переформулировали пункт и вставили новый перед ним
    edit_testing(qa_task, insert_first="Новый пункт ‹R-02›", reword=("сразу отображается", "отображается сразу"))
    second = {u.text: u.id for u in sync_units(qa_task)}
    assert second[REWORDED_NEW] == first_id_of_reworded  # ID сохранён
    assert second["Новый пункт"] not in {u.id for u in first}


def test_sync_is_stable(qa_task):
    first = sync_units(qa_task)
    text = (qa_task / "qa" / "units.md").read_text(encoding="utf-8")
    assert [(u.id, u.where) for u in sync_units(qa_task)] == [(u.id, u.where) for u in first]
    assert (qa_task / "qa" / "units.md").read_text(encoding="utf-8") == text


def test_sync_same_text_in_two_places(qa_task):
    path = qa_task / "draft" / "03-changes.md"
    text = path.read_text(encoding="utf-8").replace("Доступ — право `saleschannels:edit`; мерчант — из токена.", "Во время запроса показывать индикатор загрузки. ‹R-03›")
    path.write_text(text, encoding="utf-8")
    units = sync_units(qa_task)
    same = [u for u in units if u.text == "Во время запроса показывать индикатор загрузки."]
    assert len(same) == 2 and len({u.id for u in same}) == 2
    assert {u.id: u.where for u in sync_units(qa_task)} == {u.id: u.where for u in units}


def test_sync_marks_removed_and_keeps_human_status(qa_task):
    units = sync_units(qa_task)
    set_status_in_file(qa_task, units[0].id, "не тестируется", "нет стенда")
    remove_item(qa_task, units[1].where)
    after = {u.id: u for u in sync_units(qa_task)}
    assert after[units[0].id].status == "не тестируется"
    assert after[units[0].id].reason == "нет стенда"
    assert after[units[1].id].status == "удал."
    assert after[units[1].id].text == units[1].text


def test_load_units_roundtrip(qa_task):
    units = sync_units(qa_task)
    loaded = load_units(qa_task)
    assert [(u.id, u.where, u.text, u.refs) for u in loaded] == [(u.id, u.where, u.text, u.refs) for u in units]


def test_load_units_missing(task_dir):
    assert load_units(task_dir) == []


def test_load_units_broken(qa_task):
    sync_units(qa_task)
    path = qa_task / "qa" / "units.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| U-02 |", "| U-02 | лишняя |", 1), encoding="utf-8")
    with pytest.raises(ArtifactError):
        load_units(qa_task)


def test_unit_dataclass_defaults():
    assert Unit("U-01", "08-testing/new/1", "т", []).status == ""
