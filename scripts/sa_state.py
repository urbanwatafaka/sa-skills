"""Состояние задачи: state.json и хэши входных артефактов."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from sa_artifacts import ArtifactError

STATE_FILE = "state.json"
STAGES = ("impact", "start", "clarify", "draft", "check", "done")
ACCESS_KEYS = {"jira", "confluence", "git"}
ACCESS_MODES = {"mcp", "cli", "manual"}
TEMPLATE_RE = re.compile(r"[a-z][a-z0-9-]*@\d+\.\d+")
PLUGIN_JSON = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
ARTIFACTS = {
    "BRD": "sources/BRD.md",
    "impact-map": "impact-map.md",
    "context": "context.md",
    "questions": "questions.md",
    "decisions": "decisions.md",
    "draft": "draft.md",
    "review": "review.md",
}
PUBLISH_FILE = "draft-publish.md"


def artifact_path(task_dir: Path, name: str) -> Path:
    if name not in ARTIFACTS:
        raise ArtifactError(f"неизвестный артефакт {name}; допустимы: {', '.join(ARTIFACTS)}")
    return task_dir / ARTIFACTS[name]


def file_sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_state(task_dir: Path) -> dict:
    path = task_dir / STATE_FILE
    if not path.exists():
        raise ArtifactError(f"нет {STATE_FILE} в {task_dir}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"{STATE_FILE}: битый JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ArtifactError(f"{STATE_FILE}: ожидается JSON-объект")
    return data


def write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_state(task_dir: Path, state: dict) -> None:
    write_atomic(task_dir / STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _plugin_version() -> str:
    try:
        return json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"не удалось прочитать версию плагина из {PLUGIN_JSON}") from exc


def init_state(task_dir: Path, task: str) -> dict:
    if (task_dir / STATE_FILE).exists():
        raise ArtifactError(f"{STATE_FILE} уже есть в {task_dir}")
    task_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "task": task,
        "stage": "impact",
        "plugin_version": _plugin_version(),
        "access": {},
        "inputs": {},
        "sections": {},
    }
    save_state(task_dir, state)
    return state


def set_value(task_dir: Path, key: str, value: str) -> dict:
    state = load_state(task_dir)
    if key == "stage":
        if value not in STAGES:
            raise ArtifactError(f"stage: одно из {', '.join(STAGES)}")
        state["stage"] = value
    elif key == "template":
        if not TEMPLATE_RE.fullmatch(value):
            raise ArtifactError("template: формат имя@мажор.минор, например feature@1.0")
        state["template"] = value
    elif key == "published":
        publish = task_dir / PUBLISH_FILE
        if not value.strip():
            raise ArtifactError("published: нужна ссылка на страницу")
        if not publish.exists():
            raise ArtifactError(f"нет {PUBLISH_FILE} — сначала sa_draft.py assemble")
        state["published"] = {"url": value, "hash": file_sha1(publish)}
    elif key == "published.version":
        published = state.get("published")
        if not isinstance(published, dict):
            raise ArtifactError("published.version: сначала set published <ссылка>")
        if not (value.isascii() and value.isdigit() and int(value) > 0):
            raise ArtifactError("published.version: целое число больше нуля — версия страницы в Confluence")
        published["version"] = int(value)
    elif key == "code_check":
        draft = task_dir / ARTIFACTS["draft"]
        if value != "draft":
            raise ArtifactError("code_check: значение draft — отметить текущую версию draft.md сверенной с кодом")
        if not draft.exists():
            raise ArtifactError("нет draft.md — сначала /tdd-draft")
        state["code_check"] = file_sha1(draft)
    elif key.startswith("access.") and key[len("access."):] in ACCESS_KEYS:
        if value not in ACCESS_MODES:
            raise ArtifactError(f"{key}: режим одно из {', '.join(sorted(ACCESS_MODES))}")
        access = state.get("access")
        if not isinstance(access, dict):
            access = state["access"] = {}
        access[key[len("access."):]] = value
    else:
        raise ArtifactError(
            f"ключ {key} менять нельзя; допустимы: stage, template, published, published.version, code_check, "
            + ", ".join(f"access.{k}" for k in sorted(ACCESS_KEYS))
        )
    save_state(task_dir, state)
    return state


def record_inputs(task_dir: Path, names: list[str]) -> dict:
    state = load_state(task_dir)
    inputs = state.setdefault("inputs", {})
    for name in names:
        path = artifact_path(task_dir, name)
        if not path.exists():
            raise ArtifactError(f"нет файла {ARTIFACTS[name]}")
        inputs[name] = file_sha1(path)
    save_state(task_dir, state)
    return state


def stale_inputs(task_dir: Path, state: dict) -> list[str]:
    stale = []
    inputs = state.get("inputs", {})
    if not isinstance(inputs, dict):
        return []
    for name, recorded in inputs.items():
        if name not in ARTIFACTS:
            continue
        path = artifact_path(task_dir, name)
        if not path.exists() or file_sha1(path) != recorded:
            stale.append(name)
    return stale


USAGE = (
    "использование:\n"
    "  sa_state.py init <папка задачи> <KEY>\n"
    "  sa_state.py set <папка задачи> <ключ> <значение>   # stage, template, published, published.version, access.<система>\n"
    "  sa_state.py record <папка задачи> <артефакт>..."
)


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    arity = {"init": lambda n: n == 3, "set": lambda n: n == 4, "record": lambda n: n >= 3}
    if command not in arity or not arity[command](len(argv)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "init":
            init_state(task_dir, argv[2])
            print(f"создан {task_dir / STATE_FILE}")
        elif command == "set":
            set_value(task_dir, argv[2], argv[3])
            print(f"{argv[2]} = {argv[3]}")
        else:
            record_inputs(task_dir, argv[2:])
            print(f"записаны хэши: {', '.join(argv[2:])}")
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
