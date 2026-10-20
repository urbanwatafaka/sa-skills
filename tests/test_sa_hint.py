import io
import json
import shutil
import sys
from pathlib import Path

import sa_hint
from conftest import FIXTURE

ROOT = Path(__file__).resolve().parents[1]


def _work(tmp_path, *keys):
    for key in keys:
        shutil.copytree(FIXTURE, tmp_path / "tasks" / key)
        state = tmp_path / "tasks" / key / "state.json"
        state.write_text(state.read_text(encoding="utf-8").replace("LKP-DEMO", key), encoding="utf-8")
    return tmp_path


def test_hint_for_key_in_prompt(tmp_path):
    work = _work(tmp_path, "LKP-DEMO")
    lines = sa_hint.hints("что дальше по LKP-DEMO и NOPE-1?", work)
    assert lines[0].startswith("[sa-skills] LKP-DEMO · стадия: clarify")
    assert "вопросы PO открыто 1 (блокирующих 1)" in lines[0]
    assert lines[0].endswith("следующий шаг: /tdd-clarify — закрыть блокирующие вопросы")
    assert "sa-skills:sa-flow" in lines[1]
    assert len(lines) == 2


def test_hint_for_answers_without_key(tmp_path):
    work = _work(tmp_path, "LKP-DEMO")
    assert sa_hint.hints("Q-PO-02: текст «Нельзя»", work)[0].startswith("[sa-skills] LKP-DEMO")
    _work(tmp_path, "LKP-TWO")
    only = sa_hint.hints("Q-PO-02: текст", work)
    assert len(only) == 1 and "задач несколько (LKP-DEMO, LKP-TWO)" in only[0]


def test_hint_silent(tmp_path):
    assert sa_hint.hints("привет", tmp_path) == []
    work = _work(tmp_path, "LKP-DEMO")
    assert sa_hint.hints("просто вопрос про код", work) == []
    (work / "tasks/LKP-DEMO/state.json").write_text("{битый", encoding="utf-8")
    assert sa_hint.hints("LKP-DEMO", work) == []


def test_main_never_fails(tmp_path, monkeypatch, capsys):
    work = _work(tmp_path, "LKP-DEMO")
    payload = json.dumps({"prompt": "LKP-DEMO", "cwd": str(work)}, ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"))
    assert sa_hint.main() == 0
    assert capsys.readouterr().out.startswith("[sa-skills] LKP-DEMO")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"\xff not json"), encoding="utf-8"))
    assert sa_hint.main() == 0
    assert capsys.readouterr().out == ""


def test_plugin_hook_points_to_script():
    data = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    command = data["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}/scripts/sa_hint.py" in command
    assert (ROOT / "scripts/sa_hint.py").exists()
