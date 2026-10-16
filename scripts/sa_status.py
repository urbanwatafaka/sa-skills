"""Сводка по задаче для /tdd-status. Читает только state.json и файлы задачи."""
from __future__ import annotations

import sys
from pathlib import Path

from sa_artifacts import ArtifactError, Question, find_refs, find_table, parse_questions, parse_tables, split_frontmatter
from sa_state import ARTIFACTS, load_state, stale_inputs
from sa_validate import CONTEXT_COLUMNS

_NEXT = {
    "impact": "/tdd-start",
    "start": "/tdd-clarify",
    "draft": "/tdd-check",
    "check": "/tdd-update по принятым замечаниям, затем /tdd-check",
    "done": "задача завершена",
}


def next_step(stage: str | None, blocking_open: int, brd_complete: bool | None, unresolved_scope: int = 0) -> str:
    if brd_complete is False:
        return "переслать вопросы PO, после ответов запустить /tdd-impact повторно"
    if stage == "clarify":
        return "/tdd-clarify — закрыть блокирующие вопросы" if blocking_open or unresolved_scope else "/tdd-draft"
    return _NEXT.get(stage, "проверь state.json: неизвестная стадия")


def _questions_line(label: str, questions: list[Question], audience: str) -> str:
    open_questions = [q for q in questions if q.audience == audience and q.status == "open"]
    blocking = sum(q.blocking for q in open_questions)
    return f"{label}: открыто {len(open_questions)} (блокирующих {blocking})"


def _unresolved_scope(context_path: Path) -> list[str]:
    _, body = split_frontmatter(context_path.read_text(encoding="utf-8"))
    table = find_table(parse_tables(body), CONTEXT_COLUMNS)
    if table is None:
        return []
    ids = []
    for row in table.rows:
        if row["Скоуп"] == "?":
            ids += [r for r in find_refs(row["← IM"]) if r.startswith("IM-")]
    return ids


def build_status(task_dir: Path) -> str:
    state = load_state(task_dir)
    lines = [
        f"Задача: {state.get('task', '?')} · стадия: {state.get('stage', '?')} · "
        f"шаблон: {state.get('template', 'не выбран')}"
    ]
    marks = " · ".join(f"{name} {'✓' if (task_dir / path).exists() else '—'}" for name, path in ARTIFACTS.items())
    lines.append(f"Артефакты: {marks}")

    brd_complete = None
    brd = task_dir / ARTIFACTS["BRD"]
    if brd.exists():
        meta, _ = split_frontmatter(brd.read_text(encoding="utf-8"))
        brd_complete = meta.get("brd_complete")
        if brd_complete is False:
            missing = meta.get("missing") or ["не указано"]
            lines.append(f"BRD: неполный — не хватает: {', '.join(missing)}")

    questions: list[Question] = []
    questions_path = task_dir / ARTIFACTS["questions"]
    if questions_path.exists():
        _, body = split_frontmatter(questions_path.read_text(encoding="utf-8"))
        questions = parse_questions(body)
    lines.append(_questions_line("Вопросы PO", questions, "PO"))
    lines.append(_questions_line("Вопросы аналитику", questions, "SA"))

    unresolved: list[str] = []
    context_path = task_dir / ARTIFACTS["context"]
    if context_path.exists():
        unresolved = _unresolved_scope(context_path)
        lines.append(f"Скоуп: не решено {len(unresolved)} ({', '.join(unresolved)})" if unresolved else "Скоуп: всё распределено")

    draft_dir = task_dir / "draft"
    sections = sorted(draft_dir.glob("*.md")) if draft_dir.is_dir() else []
    if sections:
        parts = []
        for section in sections:
            placeholders = section.read_text(encoding="utf-8").count("⚠")
            parts.append(section.stem + (f" (⚠ {placeholders})" if placeholders else ""))
        lines.append(f"Черновик: {', '.join(parts)}")
    else:
        lines.append("Черновик: секций нет")

    stale = stale_inputs(task_dir, state)
    lines.append(f"Устаревшие входы: {', '.join(stale) if stale else 'нет'}")

    blocking_open = sum(q.blocking for q in questions if q.status == "open")
    lines.append(f"Следующий шаг: {next_step(state.get('stage'), blocking_open, brd_complete, len(unresolved))}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("использование: sa_status.py <папка задачи>", file=sys.stderr)
        return 2
    try:
        print(build_status(Path(argv[0])))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
