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


REVIEW_HEAD = (
    "---\ndraft: {sha}\nreviewed: 2026-10-16\nround: 1\n---\n# Ревью черновика LKP-DEMO\n\n## Замечания\n\n"
    "| ID | Важность | Где | Проблема | ← Ссылка | Предложение | Статус |\n|---|---|---|---|---|---|---|\n"
)


def write_review(task_dir: Path, rows: list[str]) -> Path:
    from sa_review import coverage_table
    from sa_state import file_sha1

    text = REVIEW_HEAD.format(sha=file_sha1(task_dir / "draft.md")) + "".join(f"{row}\n" for row in rows)
    text += "\n## Покрытие BRD\n\n" + coverage_table(task_dir) + "\n"
    path = task_dir / "review.md"
    path.write_text(text, encoding="utf-8")
    return path


import subprocess

INDEX_REPOS = Path(__file__).parent / "fixtures" / "e2e" / "index-repos"
INDEX_DOCS = Path(__file__).parent / "fixtures" / "index-docs"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=SA", "-c", "user.email=sa@example.com", *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout


@pytest.fixture
def index_repos(tmp_path: Path):
    root = tmp_path / "repos"

    def make(name: str, docs: bool = True, init: bool = True) -> Path:
        repo = root / name
        shutil.copytree(INDEX_REPOS / name, repo)
        if docs:
            shutil.copytree(INDEX_DOCS / name / "docs", repo / "docs" / "sa-index")
        if init:
            git(repo, "init", "-q")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "init")
        return repo

    return make


QA_FIXTURE = Path(__file__).parent / "fixtures" / "qa"


@pytest.fixture
def qa_task(task_dir: Path) -> Path:
    draft = task_dir / "draft"
    draft.mkdir(exist_ok=True)
    for name in ("01-brd.md", "03-changes.md", "08-testing.md"):
        shutil.copy(QA_FIXTURE / name, draft / name)
    return task_dir


@pytest.fixture
def qa_cases_task(qa_task: Path) -> Path:
    from sa_qa_units import sync_units

    sync_units(qa_task)
    shutil.copy(QA_FIXTURE / "cases.md", qa_task / "qa" / "cases.md")
    return qa_task
