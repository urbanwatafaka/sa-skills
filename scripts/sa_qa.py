"""Стадии QA: единицы покрытия, отметки кейсов, покрытие, предпроверка, выгрузка CSV для Allure, задетые кейсы."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError, parse_questions
from sa_draft import row_hashes
from sa_qa_cases import Case, case_hash, lint_case, parse_cases
from sa_qa_units import REMOVED, Unit, load_units, sync_units
from sa_state import file_sha1

CASES_FILE = "qa/cases.md"
QUESTIONS_FILE = "qa/questions.md"
STATE_FILE = "qa/state.json"
CSV_FILE = "qa/allure-import.csv"
CSV_HEADER = ["ID", "Name", "Description", "Precondition", "Scenario", "Expected result", "Priority", "Status"]
PLACEHOLDER_RE = re.compile(r"⚠\s*(Q-QA-\d{2,})")
ALL = "все"


def load_cases(task_dir: Path) -> list[Case]:
    path = task_dir / CASES_FILE
    return parse_cases(path.read_text(encoding="utf-8")) if path.exists() else []


def load_state(task_dir: Path) -> dict:
    path = task_dir / STATE_FILE
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key in ("rows", "units", "cases"):
        state.setdefault(key, {})
    return state


def save_state(task_dir: Path, state: dict) -> None:
    path = task_dir / STATE_FILE
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unit_hash(unit: Unit) -> str:
    return hashlib.sha1(f"{unit.text}|{unit.status == REMOVED}".encode("utf-8")).hexdigest()  # статус человека — не изменение ТЗ


def _name(case: Case) -> str:
    return case.id or f"«{case.title}»"


def mark(task_dir: Path, ids: list[str] | str) -> list[str]:
    """Записать хэши кейсов как сгенерированные стадией и снимок строк ТЗ и единиц."""
    cases = {c.id: c for c in load_cases(task_dir) if c.id}
    chosen = list(cases) if ids == ALL else list(ids)
    unknown = [i for i in chosen if i not in cases]
    if unknown:
        raise ArtifactError(f"нет кейсов {', '.join(unknown)} в {CASES_FILE}")
    state = load_state(task_dir)
    for cid in chosen:
        entry = state["cases"].setdefault(cid, {"generated": None, "exported": None})
        entry["generated"] = case_hash(cases[cid])
    state["rows"] = row_hashes(task_dir)
    state["units"] = {u.id: _unit_hash(u) for u in load_units(task_dir)}
    save_state(task_dir, state)
    return chosen


def human_cases(task_dir: Path) -> list[str]:
    """Кейсы с правкой человека: хэш не совпадает с записанным стадией (или стадия их не писала)."""
    state = load_state(task_dir)["cases"]
    return [c.id for c in load_cases(task_dir) if c.id and (state.get(c.id) or {}).get("generated") != case_hash(c)]


def coverage(task_dir: Path) -> list[tuple[str, str, list[str]]]:
    cases = load_cases(task_dir)
    return [(u.id, u.status, [_name(c) for c in cases if u.id in c.covers]) for u in load_units(task_dir)]


def coverage_table(task_dir: Path) -> str:
    reasons = {u.id: u.reason for u in load_units(task_dir)}
    lines = ["| U | Статус | Кейсы |", "|---|---|---|"]
    for uid, status, cases in coverage(task_dir):
        shown = status or "тестируется"
        if status and reasons.get(uid):
            shown += f": {reasons[uid]}"
        lines.append(f"| {uid} | {shown} | {', '.join(cases) or '—'} |")
    return "\n".join(lines)


def _closed_questions(task_dir: Path) -> dict[str, str]:
    path = task_dir / QUESTIONS_FILE
    if not path.exists():
        return {}
    return {q.id: q.status for q in parse_questions(path.read_text(encoding="utf-8"))}


def precheck(task_dir: Path) -> list[str]:
    units = {u.id: u for u in load_units(task_dir)}
    cases = load_cases(task_dir)
    questions = _closed_questions(task_dir)
    messages = []
    for uid, status, covered in coverage(task_dir):
        if covered or status not in ("", "нужно решение"):
            continue
        if status:
            messages.append(f"{uid}: нужно решение — {units[uid].reason or 'причина не указана'}; без кейса")
        else:
            messages.append(f"{uid}: без кейса — «{units[uid].text[:60]}»")
    for case in cases:
        name = _name(case)
        if not case.id:
            messages.append(f"{name}: нет ID TC-xx — выдай: sa_ids.py next <папка задачи> TC")
        for uid in case.covers:
            if uid not in units:
                messages.append(f"{name}: Покрывает {uid} — нет такой единицы в qa/units.md")
            elif units[uid].status == REMOVED:
                messages.append(f"{name}: Покрывает {uid} — единица удалена из ТЗ (удал.)")
        messages += [f"{name}: {error}" for error in lint_case(case)]
        for qid in dict.fromkeys(PLACEHOLDER_RE.findall(case.raw)):
            if qid not in questions:
                messages.append(f"{name}: ⚠ {qid} — нет такого вопроса в {QUESTIONS_FILE}")
            elif questions[qid] != "open":
                messages.append(f"{name}: ⚠ {qid} — вопрос закрыт ({questions[qid]}), подставь ответ")
    return messages


def export_preview(task_dir: Path) -> dict[str, list[str]]:
    state = load_state(task_dir)["cases"]
    result: dict[str, list[str]] = {"новые": [], "изменённые": [], "неизменные": []}
    for case in load_cases(task_dir):
        exported = (state.get(case.id) or {}).get("exported")
        group = "новые" if not exported else "неизменные" if exported == case_hash(case) else "изменённые"
        result[group].append(_name(case))
    return result


def export_csv(task_dir: Path, key: str) -> Path:
    cases = load_cases(task_dir)
    missing = [_name(c) for c in cases if not c.id]
    if missing:
        raise ArtifactError(f"нет ID TC-xx у кейсов {', '.join(missing)}")
    path = task_dir / CSV_FILE
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for c in cases:
            scenario = "\n".join(f"{n}. {step}" for n, step in enumerate(c.steps, start=1))
            writer.writerow([f"{key}-{c.id}", c.title, c.description, c.preconditions, scenario, c.expected, c.priority, "Draft"])
    state = load_state(task_dir)
    for c in cases:
        state["cases"].setdefault(c.id, {"generated": None, "exported": None})["exported"] = case_hash(c)
    save_state(task_dir, state)
    return path


def affected(task_dir: Path) -> list[tuple[str, list[str]]]:
    """Кейсы, задетые изменением строк BRD/карты/решений или единиц покрытия со времени mark."""
    state = load_state(task_dir)
    rows_now = row_hashes(task_dir)
    changed = {rid for rid, sha in state["rows"].items() if rows_now.get(rid) != sha}
    units_now = {u.id: _unit_hash(u) for u in load_units(task_dir)}
    changed |= {uid for uid, sha in state["units"].items() if units_now.get(uid) != sha}
    result = []
    for case in load_cases(task_dir):
        hits = list(dict.fromkeys(ref for ref in [*case.sources, *case.covers] if ref in changed))
        if hits:
            result.append((_name(case), hits))
    return result


def _units_report(task_dir: Path) -> str:
    before = {u.id for u in load_units(task_dir)}
    units = sync_units(task_dir)
    new = [u.id for u in units if u.id not in before]
    removed = [u.id for u in units if u.status == REMOVED]
    decide = [u.id for u in units if u.status == "нужно решение"]
    lines = [f"единиц {len(units) - len(removed)}: новых {len(new)}, удалено {len(removed)}, нужно решение {len(decide)}"]
    if new:
        lines.append("новые: " + ", ".join(new))
    if removed:
        lines.append("удалены: " + ", ".join(removed))
    return "\n".join(lines)


def _cases_sha(task_dir: Path) -> str:
    path = task_dir / CASES_FILE
    return file_sha1(path) if path.exists() else "—"


def _lines(items: list[str], empty: str) -> str:
    return "\n".join(items) if items else empty


USAGE = (
    "использование:\n"
    "  sa_qa.py units <папка задачи>\n"
    "  sa_qa.py mark <папка задачи> <TC-xx…|все>\n"
    "  sa_qa.py human <папка задачи>\n"
    "  sa_qa.py coverage <папка задачи>\n"
    "  sa_qa.py precheck <папка задачи>\n"
    "  sa_qa.py preview <папка задачи>\n"
    "  sa_qa.py export <папка задачи> [ключ задачи]\n"
    "  sa_qa.py affected <папка задачи>"
)

SIMPLE = {
    "units": _units_report,
    "human": lambda t: _lines(human_cases(t), "правок человека нет"),
    "coverage": coverage_table,
    "precheck": lambda t: f"cases: {_cases_sha(t)}\n" + _lines(precheck(t), "замечаний нет"),
    "preview": lambda t: "\n".join(f"{group}: {', '.join(ids) or '—'}" for group, ids in export_preview(t).items()),
    "affected": lambda t: _lines([f"{tc}: {', '.join(refs)}" for tc, refs in affected(t)], "задетых кейсов нет"),
}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    valid = (
        (command in SIMPLE and len(argv) == 2)
        or (command == "mark" and len(argv) >= 3)
        or (command == "export" and len(argv) in (2, 3))
    )
    if not valid:
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "mark":
            ids = ALL if argv[2:] == [ALL] else argv[2:]
            print("отмечены: " + ", ".join(mark(task_dir, ids)))
        elif command == "export":
            key = argv[2] if len(argv) == 3 else task_dir.resolve().name
            print(export_csv(task_dir, key))
        else:
            print(SIMPLE[command](task_dir))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
