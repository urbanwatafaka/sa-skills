"""Блок открытых вопросов для пересылки: PO — без ссылок, аналитику — со ссылками."""
from __future__ import annotations

import sys
from pathlib import Path

from sa_artifacts import ArtifactError, parse_questions, split_frontmatter
from sa_state import ARTIFACTS, load_state

_WHO = {"PO": "PO", "SA": "аналитика"}


def export_questions(task_dir: Path, audience: str) -> str:
    if audience not in _WHO:
        raise ArtifactError("адресат: PO или SA")
    state = load_state(task_dir)
    path = task_dir / ARTIFACTS["questions"]
    questions = parse_questions(split_frontmatter(path.read_text(encoding="utf-8"))[1]) if path.exists() else []
    open_questions = sorted(
        (q for q in questions if q.audience == audience and q.status == "open"),
        key=lambda q: not q.blocking,
    )
    if not open_questions:
        return f"Открытых вопросов для {_WHO[audience]} нет."
    blocks = []
    for q in open_questions:
        refs = f" [{', '.join(q.refs)}]" if audience == "SA" else ""
        mark = " (нужен ответ до черновика ТЗ)" if q.blocking else ""
        blocks.append("\n".join([f"{q.id}{refs}. {q.text}{mark}"] + [f"   {d}" for d in q.details]))
    parts = [f"Вопросы по задаче {state.get('task', '?')}"] + blocks
    if audience == "PO":
        parts.append(f"Пожалуйста, отвечайте с номером вопроса, например: «{open_questions[0].id}: …».")
    return "\n\n".join(parts)


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or argv[0] != "export":
        print("использование: sa_questions.py export <папка задачи> [PO|SA]", file=sys.stderr)
        return 2
    audience = argv[2] if len(argv) == 3 else "PO"
    try:
        print(export_questions(Path(argv[1]), audience))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
