"""Задача LKP-REVIEW для e2e /tdd-check и /tdd-update: черновик с подложенными дефектами.

    python3 tests/fixtures/e2e/lkp-review/make_task.py <папка tasks>
"""
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from sa_draft import assemble  # noqa: E402
from sa_state import set_value  # noqa: E402

KEY = "LKP-REVIEW"
HUMAN_NOTE = "\nКомментарий аналитика: метод вызывается только из lkp-back. ‹IM-01›\n"
DECISION = "| D-02 | Q-PO-02 | Мерчанту показываем текст «Нельзя указать собственный промокод» | PO, чат ММ | 2026-10-16 |\n"


def build(tasks_dir: Path) -> Path:
    task = tasks_dir / KEY
    shutil.copytree(ROOT / "tests/fixtures/LKP-DEMO", task)
    for name in ("state.json", "context.md", "sources/BRD.md"):
        path = task / name
        path.write_text(path.read_text(encoding="utf-8").replace("LKP-DEMO", KEY), encoding="utf-8")
    shutil.copytree(HERE / "draft", task / "draft")
    set_value(task, "stage", "draft")
    assemble(task, author="Иван Петров", today=date(2026, 10, 15))
    changes = task / "draft/03-changes.md"
    changes.write_text(changes.read_text(encoding="utf-8").rstrip("\n") + "\n" + HUMAN_NOTE, encoding="utf-8")
    assemble(task, today=date(2026, 10, 15))
    decisions = task / "decisions.md"
    decisions.write_text(decisions.read_text(encoding="utf-8").rstrip("\n") + "\n" + DECISION, encoding="utf-8")
    questions = task / "questions.md"
    questions.write_text(questions.read_text(encoding="utf-8").replace("— *open, blocking*", "— *answered*"), encoding="utf-8")
    return task


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("использование: make_task.py <папка tasks>", file=sys.stderr)
        sys.exit(2)
    print(build(Path(sys.argv[1]).absolute()))
