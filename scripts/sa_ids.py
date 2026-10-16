"""Следующий свободный ID в задаче: R, IM, Q-PO, Q-SA, D."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError
from sa_state import ARTIFACTS

KINDS = {"R": "BRD", "IM": "impact-map", "Q-PO": "questions", "Q-SA": "questions", "D": "decisions"}


def next_ids(task_dir: Path, kind: str, count: int = 1) -> list[str]:
    if kind not in KINDS:
        raise ArtifactError(f"неизвестный вид ID {kind}; допустимы: {', '.join(KINDS)}")
    if count < 1:
        raise ArtifactError("количество должно быть не меньше 1")
    path = task_dir / ARTIFACTS[KINDS[kind]]
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"(?<![\w-]){re.escape(kind)}-(\d{{2,}})\b")
    start = max((int(n) for n in pattern.findall(text)), default=0) + 1
    return [f"{kind}-{n:02d}" for n in range(start, start + count)]


USAGE = "использование: sa_ids.py next <папка задачи> <вид: R|IM|Q-PO|Q-SA|D> [количество]"


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4) or argv[0] != "next" or (len(argv) == 4 and not (argv[3].isascii() and argv[3].isdigit())):
        print(USAGE, file=sys.stderr)
        return 2
    count = int(argv[3]) if len(argv) == 4 else 1
    try:
        print("\n".join(next_ids(Path(argv[1]), argv[2], count)))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
