import pytest

from sa_artifacts import ArtifactError
from sa_ids import main, next_ids


@pytest.mark.parametrize(
    "kind, expected",
    [("R", "R-04"), ("IM", "IM-05"), ("Q-PO", "Q-PO-03"), ("Q-SA", "Q-SA-02"), ("D", "D-02")],
)
def test_next_id_per_kind(task_dir, kind, expected):
    assert next_ids(task_dir, kind) == [expected]


def test_several_ids(task_dir):
    assert next_ids(task_dir, "IM", 3) == ["IM-05", "IM-06", "IM-07"]


def test_missing_artifact_starts_from_one(task_dir):
    (task_dir / "decisions.md").unlink()
    assert next_ids(task_dir, "D") == ["D-01"]


def test_wide_numbers_kept(task_dir):
    path = task_dir / "decisions.md"
    path.write_text(path.read_text(encoding="utf-8").replace("D-01", "D-120"), encoding="utf-8")
    assert next_ids(task_dir, "D") == ["D-121"]


def test_unknown_kind(task_dir):
    with pytest.raises(ArtifactError, match="неизвестный вид"):
        next_ids(task_dir, "X")


def test_bad_count(task_dir):
    with pytest.raises(ArtifactError, match="не меньше 1"):
        next_ids(task_dir, "R", 0)


def test_cli(task_dir, capsys):
    assert main(["next", str(task_dir), "Q-SA", "2"]) == 0
    assert capsys.readouterr().out.split() == ["Q-SA-02", "Q-SA-03"]
    assert main(["next", str(task_dir), "X"]) == 1
    assert main(["next", str(task_dir), "R", "abc"]) == 2
    assert main(["next", str(task_dir), "R", "²"]) == 2
    assert main([]) == 2


def test_review_ids(draft_task):
    from conftest import write_review

    write_review(draft_task, ["| RV-01 | совет | шапка | x | — | y | открыто |", "| RV-02 | совет | шапка | x | — | y | открыто |"])
    assert next_ids(draft_task, "RV", 2) == ["RV-03", "RV-04"]
