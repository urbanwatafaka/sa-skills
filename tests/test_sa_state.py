import json

import pytest

from sa_artifacts import ArtifactError
from sa_state import (
    ARTIFACTS,
    STAGES,
    artifact_path,
    file_sha1,
    load_state,
    main,
    record_inputs,
    save_state,
    stale_inputs,
)


def test_constants():
    assert STAGES == ("impact", "start", "clarify", "draft", "check", "done")
    assert ARTIFACTS["BRD"] == "sources/BRD.md"
    assert set(ARTIFACTS) == {"BRD", "impact-map", "context", "questions", "decisions", "draft", "review"}


def test_load_state(task_dir):
    assert load_state(task_dir)["task"] == "LKP-DEMO"


def test_load_state_missing(tmp_path):
    with pytest.raises(ArtifactError, match="state.json"):
        load_state(tmp_path)


def test_load_state_broken_json(tmp_path):
    (tmp_path / "state.json").write_text("{", encoding="utf-8")
    with pytest.raises(ArtifactError, match="JSON"):
        load_state(tmp_path)


def test_save_state_keeps_cyrillic(task_dir):
    state = load_state(task_dir)
    state["note"] = "кириллица"
    save_state(task_dir, state)
    assert "кириллица" in (task_dir / "state.json").read_text(encoding="utf-8")


def test_record_and_stale(task_dir):
    record_inputs(task_dir, ["BRD", "impact-map"])
    state = load_state(task_dir)
    assert state["inputs"]["BRD"] == file_sha1(artifact_path(task_dir, "BRD"))
    assert stale_inputs(task_dir, state) == []

    brd = artifact_path(task_dir, "BRD")
    brd.write_text(brd.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert stale_inputs(task_dir, state) == ["BRD"]


def test_stale_when_file_removed(task_dir):
    record_inputs(task_dir, ["decisions"])
    artifact_path(task_dir, "decisions").unlink()
    assert stale_inputs(task_dir, load_state(task_dir)) == ["decisions"]


def test_record_unknown_artifact(task_dir):
    with pytest.raises(ArtifactError, match="неизвестный артефакт"):
        record_inputs(task_dir, ["nope"])


def test_record_missing_file(task_dir):
    with pytest.raises(ArtifactError, match="draft.md"):
        record_inputs(task_dir, ["draft"])


def test_cli_record(task_dir, capsys):
    assert main(["record", str(task_dir), "BRD"]) == 0
    assert "BRD" in json.loads((task_dir / "state.json").read_text(encoding="utf-8"))["inputs"]
    assert main(["record"]) == 2
    assert main(["record", str(task_dir), "nope"]) == 1


def test_init_state(tmp_path):
    from sa_state import init_state

    target = tmp_path / "tasks" / "LKP-1"
    state = init_state(target, "LKP-1")
    assert state == load_state(target)
    assert state["task"] == "LKP-1" and state["stage"] == "impact"
    assert state["access"] == {} and state["inputs"] == {} and state["sections"] == {}
    assert state["plugin_version"] == "0.8.4"
    with pytest.raises(ArtifactError, match="уже есть"):
        init_state(target, "LKP-1")


def test_init_state_is_valid(tmp_path):
    from sa_state import init_state
    from sa_validate import validate_state

    assert validate_state(init_state(tmp_path / "T", "LKP-1")) == []


def test_set_value(task_dir):
    from sa_state import set_value

    assert set_value(task_dir, "stage", "clarify")["stage"] == "clarify"
    assert set_value(task_dir, "template", "feature@1.0")["template"] == "feature@1.0"
    assert set_value(task_dir, "access.jira", "mcp")["access"]["jira"] == "mcp"
    assert load_state(task_dir)["access"]["jira"] == "mcp"


@pytest.mark.parametrize(
    "key,value",
    [("stage", "nope"), ("template", "feature"), ("access.jira", "ftp"), ("access.slack", "mcp"), ("other", "x")],
)
def test_set_value_rejects(task_dir, key, value):
    from sa_state import set_value

    with pytest.raises(ArtifactError):
        set_value(task_dir, key, value)


def test_save_state_atomic(task_dir):
    save_state(task_dir, {"task": "X"})
    assert sorted(p.name for p in task_dir.iterdir() if p.name.startswith(("state", ".state"))) == ["state.json"]


def test_stale_inputs_tolerant(task_dir):
    assert stale_inputs(task_dir, {"inputs": ["x"]}) == []
    assert stale_inputs(task_dir, {"inputs": {"nope": "1"}}) == []


def test_cli_init_and_set(tmp_path, capsys):
    target = tmp_path / "T"
    assert main(["init", str(target), "LKP-9"]) == 0
    assert main(["init", str(target), "LKP-9"]) == 1
    assert main(["set", str(target), "stage", "draft"]) == 0
    assert main(["set", str(target), "stage", "bad"]) == 1
    assert main(["set", str(target), "stage"]) == 2
    assert main(["init"]) == 2
    assert main([]) == 2
    assert "init" in capsys.readouterr().err


def test_set_published(draft_task):
    from sa_state import file_sha1, set_value

    state = set_value(draft_task, "published", "https://wiki/page/1")
    assert state["published"] == {"url": "https://wiki/page/1", "hash": file_sha1(draft_task / "draft-publish.md")}


def test_set_published_version(draft_task):
    from sa_state import set_value

    with pytest.raises(ArtifactError, match="сначала set published"):
        set_value(draft_task, "published.version", "7")
    set_value(draft_task, "published", "https://wiki/page/1")
    assert set_value(draft_task, "published.version", "7")["published"]["version"] == 7
    for bad in ("0", "-1", "семь", "٣"):
        with pytest.raises(ArtifactError, match="целое число больше нуля"):
            set_value(draft_task, "published.version", bad)


def test_set_published_needs_publish_file(task_dir):
    from sa_state import set_value

    with pytest.raises(ArtifactError, match="нет draft-publish.md"):
        set_value(task_dir, "published", "https://wiki/page/1")
