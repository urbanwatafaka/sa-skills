"""Строки «Границ» context.md: скоуп пункта карты влияния и комментарий."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError, find_table, is_id, parse_tables, split_frontmatter
from sa_state import ARTIFACTS, write_atomic

SCOPES = ("в скоупе", "вне скоупа", "?")
HEADING = "## Границы"
_ROW_IM = re.compile(r"^\|\s*(IM-\d{2,})\s*\|")
_QUESTION = re.compile(r"\bQ-(?:PO|SA)-\d{2,}\b")


def _impact_ids(task_dir: Path) -> set[str]:
    path = task_dir / ARTIFACTS["impact-map"]
    if not path.exists():
        raise ArtifactError("нет impact-map.md")
    table = find_table(parse_tables(split_frontmatter(path.read_text(encoding="utf-8"))[1]), ["ID", "Объект"])
    return {row["ID"] for row in table.rows} if table else set()


def set_scope(task_dir: Path, ids: list[str], scope: str, comment: str = "") -> list[str]:
    """Ставит скоуп строкам «Границ»; пункта карты нет в таблице — дописывает строку в конец. Возвращает дописанные."""
    comment = " ".join(comment.split()) or "—"
    if scope not in SCOPES:
        raise ArtifactError("скоуп: «в скоупе», «вне скоупа» или «?»")
    if "|" in comment:
        raise ArtifactError("в комментарии не должно быть «|»")
    if scope == "вне скоупа" and comment == "—":
        raise ArtifactError("для «вне скоупа» нужна причина в комментарии")
    if scope == "?" and not _QUESTION.search(comment):
        raise ArtifactError("для «?» в комментарии нужен ID вопроса, который это решит")
    known = _impact_ids(task_dir)
    for im in ids:
        if not is_id("IM", im):
            raise ArtifactError(f"{im}: ожидается IM-xx")
        if im not in known:
            raise ArtifactError(f"{im} нет в impact-map.md")
    path = task_dir / ARTIFACTS["context"]
    if not path.exists():
        raise ArtifactError("нет context.md — сначала /tdd-start")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        heading = next(i for i, line in enumerate(lines) if line.strip() == HEADING)
    except StopIteration:
        raise ArtifactError("context.md: нет раздела «## Границы»") from None
    rows = [i for i in range(heading + 1, len(lines)) if lines[i].strip().startswith("|")]
    if len(rows) < 2:
        raise ArtifactError("context.md: в «Границах» нет таблицы")
    end = rows[0]
    while end < len(lines) and lines[end].strip().startswith("|"):
        end += 1
    present: dict[str, int] = {}
    for i in range(rows[0] + 2, end):
        if m := _ROW_IM.match(lines[i].strip()):
            present[m.group(1)] = i
    added = [im for im in ids if im not in present]
    for im in ids:
        if im in present:
            lines[present[im]] = f"| {im} | {scope} | {comment} |"
    lines[end:end] = [f"| {im} | {scope} | {comment} |" for im in added]
    write_atomic(path, "\n".join(lines) + "\n")
    return added


USAGE = "использование: sa_context.py scope <папка задачи> <IM-xx…> <в скоупе|вне скоупа|?> [\"<комментарий>\"]"


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[0] != "scope":
        print(USAGE, file=sys.stderr)
        return 2
    rest = argv[2:]
    ids = [a for a in rest if is_id("IM", a)]
    tail = rest[len(ids):]
    if not ids or not tail or tail[0] not in SCOPES or len(tail) > 2:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        added = set_scope(Path(argv[1]), ids, tail[0], tail[1] if len(tail) == 2 else "")
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"{tail[0]}: {', '.join(ids)}" + (f"; дописаны строки: {', '.join(added)}" if added else ""))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
