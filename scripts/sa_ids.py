"""Следующий свободный ID в задаче: R, IM, Q-PO, Q-SA, D, RV и QA — TC, U, Q-QA, QV."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError
from sa_state import ARTIFACTS

KINDS = {"R": "BRD", "IM": "impact-map", "Q-PO": "questions", "Q-SA": "questions", "D": "decisions", "RV": "review"}
QA_FILES = {"TC": "qa/cases.md", "U": "qa/units.md", "Q-QA": "qa/questions.md", "QV": "qa/review.md"}


def next_ids(task_dir: Path, kind: str, count: int = 1) -> list[str]:
    if kind not in KINDS and kind not in QA_FILES:
        raise ArtifactError(f"неизвестный вид ID {kind}; допустимы: {', '.join([*KINDS, *QA_FILES])}")
    if count < 1:
        raise ArtifactError("количество должно быть не меньше 1")
    path = task_dir / (QA_FILES[kind] if kind in QA_FILES else ARTIFACTS[KINDS[kind]])
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    state = task_dir / "qa" / "state.json"
    if kind == "TC" and state.exists():  # кейс, удалённый руками, мог уйти в Allure — его ID не переиспользуем
        text += state.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?<![\w-]){re.escape(kind)}-(\d{{2,}})\b")
    start = max((int(n) for n in pattern.findall(text)), default=0) + 1
    return [f"{kind}-{n:02d}" for n in range(start, start + count)]


USAGE = "использование: sa_ids.py next <папка задачи> <вид: R|IM|Q-PO|Q-SA|D|RV|TC|U|Q-QA|QV> [количество]"


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
