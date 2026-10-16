import importlib.util
from pathlib import Path

from sa_review import precheck
from sa_state import load_state
from sa_update import build_plan
from sa_validate import validate_task

MAKE = Path(__file__).parent / "fixtures/e2e/lkp-review/make_task.py"


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("make_task", MAKE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(tmp_path)


def test_lkp_review_fixture(tmp_path):
    task = _build(tmp_path)
    assert task == tmp_path / "LKP-REVIEW"
    assert validate_task(task) == []
    state = load_state(task)
    assert state["task"] == "LKP-REVIEW" and state["stage"] == "draft"
    assert state["sections"]["03-changes"]["edited_by_human"] is True
    problems = [f.problem for f in precheck(task)]
    assert (
        "R-03 (функц.) не покрыт ни одним критерием приёмки User Stories (есть в 02-architecture, 03-changes, 08-testing)"
        in problems
    )
    assert "IM-03 (новый/изм.) не описан ни в одной секции" in problems
    assert any(p == "⚠ Q-PO-02 стоит на закрытом вопросе" for p in problems)
    plan = build_plan(task)
    assert plan.new == ["D-02"]
    assert [(s.id, s.human) for s in plan.sections] == [("01-brd", False), ("03-changes", True)]


def test_make_index_repos(tmp_path):
    import subprocess
    import sys

    script = Path(__file__).parent / "fixtures" / "e2e" / "index-repos" / "make_repos.py"
    subprocess.run([sys.executable, str(script), str(tmp_path / "repos")], check=True)
    for name in ("shop-api", "shop-legacy", "shop-front"):
        assert (tmp_path / "repos" / name / ".git").is_dir()
        assert not (tmp_path / "repos" / name / "docs").exists()
    subprocess.run([sys.executable, str(script), str(tmp_path / "repos"), "--change"], check=True)
    routes = (tmp_path / "repos" / "shop-api" / "routes" / "api.php").read_text(encoding="utf-8")
    assert "Route::delete('/api/orders/{id}'" in routes
