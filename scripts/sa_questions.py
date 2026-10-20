"""Вопросы задачи: блок открытых вопросов для пересылки, смена статуса, «Ответ в ТЗ», снятие блокировки решением."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import (
    ArtifactError, find_table, parse_questions, parse_tables, split_frontmatter, _Q_ANSWER, _Q_START, _Q_STATUS,
)
from sa_state import ARTIFACTS, load_state, write_atomic

_WHO = {"PO": "PO", "SA": "аналитика"}
_AFTER_DRAFT = ("draft", "check", "done")
CLOSED = ("answered", "obsolete")


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
    deadline = "готовности ТЗ" if state.get("stage") in _AFTER_DRAFT else "черновика ТЗ"
    blocks = []
    for q in open_questions:
        refs = f" [{', '.join(q.refs)}]" if audience == "SA" else ""
        mark = f" (нужен ответ до {deadline})" if q.blocking else ""
        blocks.append("\n".join([f"{q.id}{refs}. {q.text}{mark}"] + [f"   {d}" for d in q.details]))
    parts = [f"Вопросы по задаче {state.get('task', '?')}"] + blocks
    if audience == "PO":
        parts.append(f"Пожалуйста, отвечайте с номером вопроса, например: «{open_questions[0].id}: …».")
    return "\n\n".join(parts)


def _questions_path(task_dir: Path) -> Path:
    path = task_dir / ARTIFACTS["questions"]
    if not path.exists():
        raise ArtifactError("нет questions.md")
    return path


def _blocks(lines: list[str]) -> dict[str, tuple[int, int]]:
    """ID вопроса → (первая строка, строка после последней) — по тем же правилам, что parse_questions."""
    found: dict[str, tuple[int, int]] = {}
    current = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if m := _Q_START.match(stripped):
            current = m.group(1)
            found[current] = (i, i + 1)
        elif current and stripped and line.startswith((" ", "\t")):
            found[current] = (found[current][0], i + 1)
        elif stripped:
            current = ""
    return found


def _edit(task_dir: Path, ids: list[str], change) -> None:
    """Применяет change(qid, строки блока) → новые строки блока к каждому вопросу и записывает файл."""
    path = _questions_path(task_dir)
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = _blocks(lines)
    for qid in ids:
        if qid not in blocks:
            raise ArtifactError(f"нет вопроса {qid}")
    for qid in sorted(set(ids), key=lambda q: blocks[q][0], reverse=True):
        start, end = blocks[qid]
        lines[start:end] = change(qid, lines[start:end])
    write_atomic(path, "\n".join(lines) + "\n")


def _marker(qid: str, chunk: list[str]) -> int:
    for i, line in enumerate(chunk):
        if _Q_STATUS.search(line):
            return i
    raise ArtifactError(f"{qid}: нет статуса вида «— *open*»")


def _by_id(task_dir: Path) -> dict:
    return {q.id: q for q in parse_questions(split_frontmatter(_questions_path(task_dir).read_text(encoding="utf-8"))[1])}


def set_status(task_dir: Path, status: str, ids: list[str]) -> list[str]:
    if status not in CLOSED:
        raise ArtifactError("статус: answered или obsolete")
    questions = _by_id(task_dir)
    for qid in ids:
        q = questions.get(qid)
        if q is None:
            raise ArtifactError(f"нет вопроса {qid}")
        if q.status != "open":
            raise ArtifactError(f"{qid} уже {q.status}")
        if status == "obsolete" and q.answer:
            raise ArtifactError(f"{qid}: у неактуального вопроса не бывает «Ответ в ТЗ» — закройте как answered")

    def change(qid: str, chunk: list[str]) -> list[str]:
        i = _marker(qid, chunk)
        chunk[i] = _Q_STATUS.sub(f"— *{status}*", chunk[i])
        return chunk

    _edit(task_dir, ids, change)
    return ids


def set_answer(task_dir: Path, qid: str, answer: str) -> None:
    answer = " ".join(answer.split())
    if not answer:
        raise ArtifactError("пустой ответ")
    q = _by_id(task_dir).get(qid)
    if q is None:
        raise ArtifactError(f"нет вопроса {qid}")
    if q.status == "obsolete":
        raise ArtifactError(f"{qid} неактуален — «Ответ в ТЗ» ему не ставят")

    def change(_: str, chunk: list[str]) -> list[str]:
        indent = re.match(r"\s*", chunk[1]).group(0) if len(chunk) > 1 else "  "
        for i, line in enumerate(chunk[1:], start=1):
            if _Q_ANSWER.match(_Q_STATUS.sub("", line).strip()):
                tail = _Q_STATUS.search(line)
                chunk[i] = f"{indent}Ответ в ТЗ: {answer}" + (f" {tail.group(0)}" if tail else "")
                return chunk
        return chunk + [f"{indent}Ответ в ТЗ: {answer}"]

    _edit(task_dir, [qid], change)


def _scope_questions(task_dir: Path) -> set[str]:
    """Вопросы, стоящие за строками «?» в «Границах»: они всегда блокирующие."""
    path = task_dir / ARTIFACTS["context"]
    if not path.exists():
        return set()
    table = find_table(parse_tables(split_frontmatter(path.read_text(encoding="utf-8"))[1]), ["← IM", "Скоуп", "Комментарий"])
    if table is None:
        return set()
    return {
        qid for row in table.rows if row["Скоуп"] == "?"
        for qid in re.findall(r"Q-(?:PO|SA)-\d{2,}", row["Комментарий"])
    }


def unblock(task_dir: Path, qid: str, decision: str) -> None:
    q = _by_id(task_dir).get(qid)
    if q is None:
        raise ArtifactError(f"нет вопроса {qid}")
    if not (q.status == "open" and q.blocking):
        raise ArtifactError(f"{qid} не блокирующий открытый вопрос")
    if qid in _scope_questions(task_dir):
        raise ArtifactError(f"{qid} решает строку «?» в «Границах» — такой вопрос остаётся блокирующим")
    path = task_dir / ARTIFACTS["decisions"]
    table = find_table(parse_tables(path.read_text(encoding="utf-8")), ["ID", "← Q", "Решение"]) if path.exists() else None
    rows = {row["ID"]: row for row in table.rows} if table else {}
    if decision not in rows:
        raise ArtifactError(f"нет решения {decision} в decisions.md")
    if rows[decision]["← Q"] != qid:
        raise ArtifactError(f"{decision} записано не на {qid} (← Q = {rows[decision]['← Q']})")

    def change(_: str, chunk: list[str]) -> list[str]:
        i = _marker(qid, chunk)
        chunk[i] = _Q_STATUS.sub("— *open*", chunk[i])
        return chunk

    _edit(task_dir, [qid], change)


USAGE = (
    "использование:\n"
    "  sa_questions.py export <папка задачи> [PO|SA]\n"
    "  sa_questions.py status <папка задачи> <answered|obsolete> <Q-xx…>\n"
    "  sa_questions.py answer <папка задачи> <Q-xx> \"<ответ в ТЗ>\"\n"
    "  sa_questions.py unblock <папка задачи> <Q-xx> <D-xx>"
)


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    shapes = {"export": (2, 3), "answer": (4,), "unblock": (4,)}
    if not (len(argv) in shapes.get(command, ()) or (command == "status" and len(argv) >= 4)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "export":
            print(export_questions(task_dir, argv[2] if len(argv) == 3 else "PO"))
        elif command == "status":
            print(f"{argv[2]}: {', '.join(set_status(task_dir, argv[2], argv[3:]))}")
        elif command == "answer":
            set_answer(task_dir, argv[2], argv[3])
            print(f"{argv[2]}: «Ответ в ТЗ» записан")
        else:
            unblock(task_dir, argv[2], argv[3])
            print(f"{argv[2]}: не блокирующий по {argv[3]}")
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
