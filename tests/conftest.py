import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "LKP-DEMO"


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    target = tmp_path / "LKP-DEMO"
    shutil.copytree(FIXTURE, target)
    return target


from datetime import date


def write_sections(task_dir: Path, body: str = "Текст секции ‹R-01›") -> None:
    from sa_template import load_manifest

    draft = task_dir / "draft"
    draft.mkdir(exist_ok=True)
    for section in load_manifest("feature").sections:
        (draft / f"{section.id}.md").write_text(f"{section.heading}\n\n{body}\n", encoding="utf-8")


@pytest.fixture
def draft_task(task_dir: Path) -> Path:
    from sa_draft import assemble

    write_sections(task_dir)
    assemble(task_dir, author="Иван Петров", today=date(2026, 10, 15))
    return task_dir
