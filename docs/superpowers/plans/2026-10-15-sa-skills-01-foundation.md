# SA Skills — подпроект 1: каркас — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать каркас плагина Claude Code `sa-skills`: манифест, общие правила, адаптеры доступа, схемы артефактов задачи с валидатором и первую рабочую команду `/tdd-status`.

**Architecture:** Репозиторий — это плагин Claude Code (скилы в `skills/`, справочники в `shared/`). Всё детерминированное (разбор артефактов, валидация, сводка статуса) делают скрипты в `scripts/` на стандартной библиотеке Python, скилы вызывают их и не тратят токены на механику. Артефакты задачи живут в `tasks/<KEY>/` рабочей папки аналитика.

**Tech Stack:** Claude Code plugins (SKILL.md), Python ≥ 3.10 (только stdlib) для скриптов, pytest для тестов.

**Spec:** `docs/superpowers/specs/2026-10-15-sa-skills-pipeline-design.md` (разделы 3, 4, 5.6, 9, 12 п. 1)

## Global Constraints

- Скрипты в `scripts/` используют только стандартную библиотеку Python ≥ 3.10. Никаких pip-зависимостей во время работы плагина.
- pytest — только зависимость разработки (`requirements-dev.txt`).
- Файл состояния задачи — `tasks/<KEY>/state.json` (не YAML).
- Frontmatter в md-артефактах — плоское подмножество YAML: `ключ: значение`, значения — строка, целое, `true`/`false` или список `[a, b]`.
- Форматы ID: `R-01`, `IM-01`, `Q-PO-01`, `Q-SA-01`, `D-01`, `RV-01` (минимум две цифры).
- Все тексты для пользователя (сообщения скриптов, справочники, SKILL.md) — на русском.
- Имя плагина — `sa-skills`, версия — `0.1.0`.
- Скилы ссылаются на скрипты через базовую директорию скила: `<база скила>/../../scripts/<скрипт>.py`.
- Пути артефактов внутри задачи: `sources/BRD.md`, `impact-map.md`, `context.md`, `questions.md`, `decisions.md`, `draft.md`, `review.md`, `draft/*.md`.

## Структура файлов

```
.claude-plugin/plugin.json          # манифест плагина
.claude-plugin/marketplace.json     # чтобы команда ставила плагин из этого репо
.gitignore
pyproject.toml                      # настройки pytest
requirements-dev.txt
README.md
scripts/
  sa_artifacts.py                   # разбор: frontmatter, таблицы, вопросы, ID
  sa_state.py                       # state.json, хэши входов; CLI record
  sa_validate.py                    # валидатор артефактов; CLI
  sa_status.py                      # сводка для /tdd-status; CLI
skills/
  tdd-status/SKILL.md
shared/
  rules/ai-rules.md
  rules/writing-style.md
  rules/question-routing.md
  rules/brd-checklist.md
  access/adapters.md
  schemas/artifacts.md
tests/
  conftest.py                       # фикстура task_dir (копия эталонной задачи)
  fixtures/LKP-DEMO/...             # эталонная задача
  test_plugin_structure.py
  test_sa_artifacts.py
  test_sa_state.py
  test_sa_validate.py
  test_sa_status.py
  test_shared_docs.py
```

---

### Task 1: Каркас плагина и тестовая инфраструктура

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`
- Create: `scripts/.gitkeep`, `skills/.gitkeep`, `shared/.gitkeep`
- Test: `tests/test_plugin_structure.py`

**Interfaces:**
- Consumes: —
- Produces: манифест плагина `sa-skills@0.1.0`; тест `test_plugin_structure.py`, который для каждого `skills/*/SKILL.md` проверяет frontmatter (`name` совпадает с именем папки, `description` непустой и ≤ 1024 символов). Последующие задачи, добавляющие скилы, полагаются на этот тест.

- [ ] **Step 1: Создать окружение разработки**

```bash
cd /Users/waraxe.in/.superset/projects/SA-Skills
python3 -m venv .venv
printf 'pytest>=8\n' > requirements-dev.txt
.venv/bin/pip install -q -r requirements-dev.txt
```

Создать `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["scripts"]
```

Создать `.gitignore`:

```
.venv/
__pycache__/
.pytest_cache/
tasks/
```

- [ ] **Step 2: Написать падающий тест структуры плагина**

`tests/test_plugin_structure.py`:

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines and lines[0] == "---", "SKILL.md должен начинаться с ---"
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def test_plugin_manifest():
    data = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "sa-skills"
    assert data["version"] == "0.1.0"
    assert data["description"]


def test_marketplace_lists_plugin():
    data = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    names = [p["name"] for p in data["plugins"]]
    assert names == ["sa-skills"]
    assert data["plugins"][0]["source"] == "./"


def test_every_skill_has_valid_frontmatter():
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta = _frontmatter(skill_md.read_text(encoding="utf-8"))
        assert meta.get("name") == skill_md.parent.name, skill_md
        description = meta.get("description", "")
        assert description, f"{skill_md}: пустой description"
        assert len(description) <= 1024, f"{skill_md}: description длиннее 1024"
```

- [ ] **Step 3: Запустить тест и убедиться, что он падает**

Run: `.venv/bin/pytest tests/test_plugin_structure.py -v`
Expected: FAIL — `FileNotFoundError` на `.claude-plugin/plugin.json`.

- [ ] **Step 4: Создать манифесты**

`.claude-plugin/plugin.json`:

```json
{
  "name": "sa-skills",
  "version": "0.1.0",
  "description": "Пайплайн системного аналитика: карта влияния, уточнение BRD, черновик ТЗ по шаблону, независимое ревью, диаграммы PlantUML.",
  "author": {"name": "Команда системных аналитиков"}
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "sa-skills-marketplace",
  "owner": {"name": "Команда системных аналитиков"},
  "plugins": [
    {
      "name": "sa-skills",
      "source": "./",
      "description": "Пайплайн системного аналитика от BRD до проверенного черновика ТЗ."
    }
  ]
}
```

Создать пустые `scripts/.gitkeep`, `skills/.gitkeep`, `shared/.gitkeep`.

- [ ] **Step 5: Запустить тест и убедиться, что он проходит**

Run: `.venv/bin/pytest tests/test_plugin_structure.py -v`
Expected: 3 passed (проверка скилов проходит на пустом списке).

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin .gitignore pyproject.toml requirements-dev.txt scripts/.gitkeep skills/.gitkeep shared/.gitkeep tests/test_plugin_structure.py
git commit -m "feat: scaffold sa-skills plugin and test infrastructure"
```

---

### Task 2: Разбор артефактов (`sa_artifacts.py`)

**Files:**
- Create: `scripts/sa_artifacts.py`
- Test: `tests/test_sa_artifacts.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `class ArtifactError(ValueError)`
  - `@dataclass Table(header: list[str], rows: list[dict[str, str]])`
  - `@dataclass Question(id: str, audience: str, section: str, refs: list[str], status: str, blocking: bool, text: str)` — `audience` и `section` принимают `"PO"`, `"SA"`; `section` может быть `""`
  - `split_frontmatter(text: str) -> tuple[dict, str]`
  - `parse_tables(body: str) -> list[Table]`
  - `find_table(tables: list[Table], required: list[str]) -> Table | None`
  - `parse_questions(body: str) -> list[Question]`
  - `find_refs(text: str) -> list[str]`
  - `ref_prefix(ref: str) -> str` — `"R"`, `"IM"`, `"Q"`, `"D"`, `"RV"`
  - `is_id(kind: str, value: str) -> bool` — `kind` из `"R"`, `"IM"`, `"Q"`, `"D"`, `"RV"`

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sa_artifacts.py`:

```python
import pytest

from sa_artifacts import (
    ArtifactError,
    find_refs,
    find_table,
    is_id,
    parse_questions,
    parse_tables,
    ref_prefix,
    split_frontmatter,
)


def test_frontmatter_scalars_and_lists():
    text = "---\nsource: https://jira/x\nbrd_complete: false\nmissing: [роли, цель]\ncount: 3\n---\nтело\n"
    meta, body = split_frontmatter(text)
    assert meta == {
        "source": "https://jira/x",
        "brd_complete": False,
        "missing": ["роли", "цель"],
        "count": 3,
    }
    assert body.strip() == "тело"


def test_frontmatter_absent():
    meta, body = split_frontmatter("| a |\n")
    assert meta == {}
    assert body == "| a |\n"


def test_frontmatter_empty_list_and_date():
    meta, _ = split_frontmatter("---\nmissing: []\nfetched: 2026-10-15\n---\n")
    assert meta == {"missing": [], "fetched": "2026-10-15"}


def test_frontmatter_unclosed():
    with pytest.raises(ArtifactError):
        split_frontmatter("---\na: 1\n")


def test_parse_tables():
    body = (
        "Текст\n\n"
        "| ID   | Требование | Тип |\n"
        "|------|------------|-----|\n"
        "| R-01 | Первое     | UI  |\n"
        "| R-02 | Второе     | функц. |\n"
        "\nхвост\n"
    )
    tables = parse_tables(body)
    assert len(tables) == 1
    assert tables[0].header == ["ID", "Требование", "Тип"]
    assert tables[0].rows[1] == {"ID": "R-02", "Требование": "Второе", "Тип": "функц."}


def test_parse_tables_separator_with_spaces():
    tables = parse_tables("| a | b |\n| --- | :---: |\n| 1 | 2 |\n")
    assert tables[0].rows == [{"a": "1", "b": "2"}]


def test_parse_tables_wrong_cell_count():
    with pytest.raises(ArtifactError):
        parse_tables("| a | b |\n|---|---|\n| 1 |\n")


def test_find_table_by_columns():
    tables = parse_tables("| x |\n|---|\n| 1 |\n\n| ID | Тип |\n|---|---|\n| R-01 | UI |\n")
    assert find_table(tables, ["ID", "Тип"]).rows == [{"ID": "R-01", "Тип": "UI"}]
    assert find_table(tables, ["Нет"]) is None


def test_parse_questions():
    body = (
        "# Вопросы\n\n"
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Что делать с начислениями?\n"
        "  Варианты: а) не пересчитывать; б) пересчитать — *answered*\n"
        "- **Q-PO-02** [R-02, R-03] Какой текст показать? — *open, blocking*\n"
        "\n"
        "## Для аналитика\n"
        "- **Q-SA-01** [IM-04] Есть ли событие в Kafka?\n"
        "  Где проверить: lkp-back/app/Events — *open*\n"
    )
    qs = parse_questions(body)
    assert [q.id for q in qs] == ["Q-PO-01", "Q-PO-02", "Q-SA-01"]
    assert qs[0].status == "answered" and not qs[0].blocking
    assert qs[1].refs == ["R-02", "R-03"]
    assert qs[1].status == "open" and qs[1].blocking
    assert qs[1].text == "Какой текст показать?"
    assert qs[2].audience == "SA" and qs[2].section == "SA"
    assert qs[2].text == "Есть ли событие в Kafka?"


def test_parse_questions_outside_section():
    qs = parse_questions("- **Q-PO-01** [R-01] Вопрос — *open*\n")
    assert qs[0].section == ""


def test_parse_questions_missing_status():
    with pytest.raises(ArtifactError, match="Q-PO-01"):
        parse_questions("## Для PO\n- **Q-PO-01** [R-01] Вопрос без статуса\n")


def test_refs_and_ids():
    assert find_refs("см. R-01, IM-02 и Q-PO-03, D-04, RV-05") == ["R-01", "IM-02", "Q-PO-03", "D-04", "RV-05"]
    assert ref_prefix("Q-SA-01") == "Q"
    assert ref_prefix("IM-10") == "IM"
    assert is_id("R", "R-01")
    assert not is_id("R", "R-1")
    assert is_id("Q", "Q-SA-12")
    assert not is_id("IM", "R-01")
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_artifacts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_artifacts'`.

- [ ] **Step 3: Реализовать модуль**

`scripts/sa_artifacts.py`:

```python
"""Разбор артефактов задачи: frontmatter, markdown-таблицы, вопросы, ID."""
from __future__ import annotations

import re
from dataclasses import dataclass

REF_RE = re.compile(r"\bQ-(?:PO|SA)-\d{2,}\b|\b(?:R|IM|D|RV)-\d{2,}\b")

ID_PATTERNS = {
    "R": re.compile(r"R-\d{2,}"),
    "IM": re.compile(r"IM-\d{2,}"),
    "Q": re.compile(r"Q-(?:PO|SA)-\d{2,}"),
    "D": re.compile(r"D-\d{2,}"),
    "RV": re.compile(r"RV-\d{2,}"),
}


class ArtifactError(ValueError):
    """Артефакт не разбирается: сломан формат."""


@dataclass
class Table:
    header: list[str]
    rows: list[dict[str, str]]


@dataclass
class Question:
    id: str
    audience: str
    section: str
    refs: list[str]
    status: str
    blocking: bool
    text: str


def find_refs(text: str) -> list[str]:
    return REF_RE.findall(text)


def ref_prefix(ref: str) -> str:
    return "Q" if ref.startswith("Q-") else ref.split("-", 1)[0]


def is_id(kind: str, value: str) -> bool:
    return ID_PATTERNS[kind].fullmatch(value) is not None


def _scalar(raw: str):
    value = raw.strip()
    if value in ("true", "false"):
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [item.strip() for item in inner.split(",")] if inner else []
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            break
    else:
        raise ArtifactError("frontmatter не закрыт строкой ---")
    meta = {}
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            raise ArtifactError(f"frontmatter, строка {number}: ожидается «ключ: значение»")
        key, raw = line.split(":", 1)
        meta[key.strip()] = _scalar(raw)
    return meta, "\n".join(lines[end + 1:])


_SEP_RE = re.compile(r"^\|?(\s*:?-{3,}:?\s*\|)*\s*:?-{3,}:?\s*\|?$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [cell.strip() for cell in s.split("|")]


def parse_tables(body: str) -> list[Table]:
    lines = body.splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if line.startswith("|") and _SEP_RE.match(nxt):
            header = _cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _cells(lines[i])
                if len(cells) != len(header):
                    raise ArtifactError(
                        f"строка таблицы «{lines[i].strip()[:40]}»: "
                        f"{len(cells)} ячеек, в заголовке {len(header)}"
                    )
                rows.append(dict(zip(header, cells)))
                i += 1
            tables.append(Table(header, rows))
        else:
            i += 1
    return tables


def find_table(tables: list[Table], required: list[str]) -> Table | None:
    for table in tables:
        if all(column in table.header for column in required):
            return table
    return None


_Q_START = re.compile(r"^- \*\*(Q-(PO|SA)-\d{2,})\*\*\s*(.*)$")
_Q_REFS = re.compile(r"^\[([^\]]*)\]\s*(.*)$")
_Q_STATUS = re.compile(r"—\s*\*(open|answered|obsolete)(, blocking)?\*\s*$", re.M)
_SECTIONS = {"## Для PO": "PO", "## Для аналитика": "SA"}


def parse_questions(body: str) -> list[Question]:
    blocks: list[tuple[str, list[str]]] = []
    section = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = _SECTIONS.get(stripped, "")
        elif _Q_START.match(stripped):
            blocks.append((section, [stripped]))
        elif blocks and stripped and line.startswith((" ", "\t")):
            blocks[-1][1].append(stripped)

    questions = []
    for section, chunk in blocks:
        start = _Q_START.match(chunk[0])
        qid, audience, rest = start.group(1), start.group(2), start.group(3)
        status = _Q_STATUS.search("\n".join(chunk))
        if status is None:
            raise ArtifactError(f"{qid}: нет статуса вида «— *open*»")
        refs_match = _Q_REFS.match(rest)
        refs = find_refs(refs_match.group(1)) if refs_match else []
        text = refs_match.group(2) if refs_match else rest
        questions.append(
            Question(
                id=qid,
                audience=audience,
                section=section,
                refs=refs,
                status=status.group(1),
                blocking=bool(status.group(2)),
                text=_Q_STATUS.sub("", text).strip(),
            )
        )
    return questions
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_artifacts.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_artifacts.py tests/test_sa_artifacts.py
git commit -m "feat: parse task artifacts (frontmatter, tables, questions)"
```

---

### Task 3: Состояние задачи (`sa_state.py`) и эталонная задача

**Files:**
- Create: `scripts/sa_state.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/LKP-DEMO/state.json`
- Create: `tests/fixtures/LKP-DEMO/sources/BRD.md`
- Create: `tests/fixtures/LKP-DEMO/impact-map.md`
- Create: `tests/fixtures/LKP-DEMO/context.md`
- Create: `tests/fixtures/LKP-DEMO/questions.md`
- Create: `tests/fixtures/LKP-DEMO/decisions.md`
- Test: `tests/test_sa_state.py`

**Interfaces:**
- Consumes: `ArtifactError` из `sa_artifacts`.
- Produces:
  - `STATE_FILE = "state.json"`
  - `STAGES = ("impact", "start", "clarify", "draft", "check", "done")`
  - `ARTIFACTS: dict[str, str]` — имя артефакта → путь внутри задачи: `BRD`, `impact-map`, `context`, `questions`, `decisions`, `draft`, `review`
  - `artifact_path(task_dir: Path, name: str) -> Path`
  - `file_sha1(path: Path) -> str`
  - `load_state(task_dir: Path) -> dict`
  - `save_state(task_dir: Path, state: dict) -> None`
  - `record_inputs(task_dir: Path, names: list[str]) -> dict`
  - `stale_inputs(task_dir: Path, state: dict) -> list[str]`
  - CLI: `python3 scripts/sa_state.py record <папка задачи> <артефакт>...`
  - pytest-фикстура `task_dir` (копия `tests/fixtures/LKP-DEMO` во временной папке)

- [ ] **Step 1: Создать эталонную задачу**

`tests/fixtures/LKP-DEMO/state.json`:

```json
{
  "task": "LKP-DEMO",
  "stage": "clarify",
  "template": "feature@1.0",
  "plugin_version": "0.1.0",
  "access": {"jira": "manual", "confluence": "manual", "git": "cli"},
  "inputs": {},
  "sections": {}
}
```

`tests/fixtures/LKP-DEMO/sources/BRD.md`:

```markdown
---
source: https://jira.example.com/browse/LKP-DEMO
fetched: 2026-10-15
brd_complete: true
missing: []
---
# BRD: запрет собственного промокода в анкете

| ID   | Требование                                                         | Тип    |
|------|--------------------------------------------------------------------|--------|
| R-01 | Партнёр не может указать собственный промокод в клиентской анкете  | функц. |
| R-02 | Мерчант видит причину, по которой промокод не принят               | UI     |
| R-03 | Недоступность проверки промокода не блокирует регистрацию мерчанта | функц. |
```

`tests/fixtures/LKP-DEMO/impact-map.md`:

```markdown
---
index_used: true
confidence_cap: высокая
---
# Карта влияния

| ID    | Объект                                      | Вид    | Влияние | ← R        | Источник                                  | Статус    | Уверенность |
|-------|---------------------------------------------|--------|---------|------------|-------------------------------------------|-----------|-------------|
| IM-01 | partners-dashboard: promocode/check-usage   | API    | новый   | R-01       | BRD R-01                                  | факт      | высокая     |
| IM-02 | lkp-back: правило валидации промокода       | модуль | изм.    | R-01, R-03 | code: lkp-back/app/Rules/Promocode.php:40 | факт      | высокая     |
| IM-03 | lkp-front: поле «Промокод партнёра»         | UI     | изм.    | R-02       | docs: lkp-front/docs/tech.md#promocode    | факт      | средняя     |
| IM-04 | Kafka: questionnaire.saved                  | Kafka  | ?       | R-03       | —                                         | допущение | низкая      |
```

`tests/fixtures/LKP-DEMO/context.md`:

```markdown
---
template: feature@1.0
---
# Контекст

Цель: запретить партнёру указывать собственный промокод в клиентской анкете.
В скоупе: IM-01, IM-02, IM-03. Вне скоупа: пересчёт старых начислений.
```

`tests/fixtures/LKP-DEMO/questions.md`:

```markdown
# Вопросы

## Для PO
- **Q-PO-01** [R-01] Что делать с вознаграждениями, уже начисленными партнёрам за собственные анкеты?
  Варианты: а) не пересчитывать; б) пересчитать — *answered*
- **Q-PO-02** [R-02] Какой текст показать мерчанту, если он указал собственный промокод? — *open, blocking*

## Для аналитика
- **Q-SA-01** [IM-04] Публикует ли lkp-back событие в Kafka при сохранении анкеты?
  Где проверить: lkp-back/app/Events — *open*
```

`tests/fixtures/LKP-DEMO/decisions.md`:

```markdown
# Журнал решений

| ID   | ← Q     | Решение                                                     | Кто/где    | Дата       |
|------|---------|-------------------------------------------------------------|------------|------------|
| D-01 | Q-PO-01 | Начисления не пересчитываем, запрет действует на новые анкеты | PO, чат ММ | 2026-09-09 |
```

`tests/conftest.py`:

```python
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "LKP-DEMO"


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    target = tmp_path / "LKP-DEMO"
    shutil.copytree(FIXTURE, target)
    return target
```

- [ ] **Step 2: Написать падающие тесты**

`tests/test_sa_state.py`:

```python
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
```

- [ ] **Step 3: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_state'`.

- [ ] **Step 4: Реализовать модуль**

`scripts/sa_state.py`:

```python
"""Состояние задачи: state.json и хэши входных артефактов."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from sa_artifacts import ArtifactError

STATE_FILE = "state.json"
STAGES = ("impact", "start", "clarify", "draft", "check", "done")
ARTIFACTS = {
    "BRD": "sources/BRD.md",
    "impact-map": "impact-map.md",
    "context": "context.md",
    "questions": "questions.md",
    "decisions": "decisions.md",
    "draft": "draft.md",
    "review": "review.md",
}


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


def save_state(task_dir: Path, state: dict) -> None:
    text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    (task_dir / STATE_FILE).write_text(text, encoding="utf-8")


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
    for name, recorded in state.get("inputs", {}).items():
        path = artifact_path(task_dir, name)
        if not path.exists() or file_sha1(path) != recorded:
            stale.append(name)
    return stale


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "record":
        print("использование: sa_state.py record <папка задачи> <артефакт>...", file=sys.stderr)
        return 2
    try:
        record_inputs(Path(argv[1]), argv[2:])
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"записаны хэши: {', '.join(argv[2:])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_state.py -v`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/sa_state.py tests/conftest.py tests/fixtures tests/test_sa_state.py
git commit -m "feat: task state (state.json, input hashes) and demo task fixture"
```

---

### Task 4: Валидатор артефактов (`sa_validate.py`) и документ схем

**Files:**
- Create: `scripts/sa_validate.py`
- Create: `shared/schemas/artifacts.md`
- Test: `tests/test_sa_validate.py`

**Interfaces:**
- Consumes: из `sa_artifacts` — `ArtifactError`, `find_refs`, `find_table`, `is_id`, `parse_questions`, `parse_tables`, `ref_prefix`, `split_frontmatter`; из `sa_state` — `ARTIFACTS`, `STAGES`, `load_state`; фикстура `task_dir`.
- Produces:
  - Константы `KINDS`, `IMPACTS`, `IM_STATUSES`, `CONFIDENCE`, `ACCESS_KEYS`, `ACCESS_MODES`, `BRD_COLUMNS`, `IMPACT_COLUMNS`, `DECISION_COLUMNS`. Их использует тест документов в задаче 6.
  - `validate_brd(text: str) -> tuple[list[str], set[str] | None]`
  - `validate_impact_map(text: str, known: dict) -> tuple[list[str], set[str] | None]`
  - `validate_questions(text: str, known: dict) -> tuple[list[str], set[str] | None]`
  - `validate_decisions(text: str, known: dict) -> tuple[list[str], set[str] | None]`
  - `validate_state(data: dict) -> list[str]`
  - `validate_task(task_dir: Path) -> list[str]` — каждая ошибка с префиксом пути артефакта, например `impact-map.md: IM-02: …`
  - CLI: `python3 scripts/sa_validate.py <папка задачи>` → `OK: <папка>` и код 0 либо ошибки построчно и код 1; код 2 при неверных аргументах.
  - `known` — словарь `{"R": set|None, "IM": set|None, "Q": set|None}`. `None` означает, что артефакта нет, и ссылки этого типа не проверяются.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sa_validate.py`:

```python
import json

from sa_validate import main, validate_state, validate_task


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"в {path.name} нет фрагмента {old!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_demo_task_is_valid(task_dir):
    assert validate_task(task_dir) == []


def test_missing_state(tmp_path):
    errors = validate_task(tmp_path)
    assert len(errors) == 1 and errors[0].startswith("state.json:")


def test_only_present_artifacts_checked(task_dir):
    for name in ("impact-map.md", "questions.md", "decisions.md", "context.md"):
        (task_dir / name).unlink()
    assert validate_task(task_dir) == []


def test_duplicate_brd_id(task_dir):
    _edit(task_dir / "sources/BRD.md", "| R-02 |", "| R-01 |")
    assert "sources/BRD.md: R-01: ID повторяется" in validate_task(task_dir)


def test_incomplete_brd_needs_missing_list(task_dir):
    _edit(task_dir / "sources/BRD.md", "brd_complete: true", "brd_complete: false")
    errors = validate_task(task_dir)
    assert any("missing пуст" in e for e in errors)


def test_fact_without_source(task_dir):
    _edit(task_dir / "impact-map.md", "| code: lkp-back/app/Rules/Promocode.php:40 |", "| — |")
    assert any(e.startswith("impact-map.md: IM-02: факт без источника") for e in validate_task(task_dir))


def test_impact_bad_kind_and_unknown_ref(task_dir):
    _edit(task_dir / "impact-map.md", "| R-02       | docs:", "| R-09       | docs:")
    _edit(task_dir / "impact-map.md", "| UI     | изм.", "| экран  | изм.")
    errors = validate_task(task_dir)
    assert "impact-map.md: IM-03: ссылка на несуществующий R-09" in errors
    assert any(e.startswith("impact-map.md: IM-03: вид «экран»") for e in errors)


def test_question_in_wrong_section(task_dir):
    _edit(task_dir / "questions.md", "**Q-SA-01**", "**Q-PO-03**")
    errors = validate_task(task_dir)
    assert "questions.md: Q-PO-03: лежит в секции SA, а адресован PO" in errors


def test_question_unknown_ref(task_dir):
    _edit(task_dir / "questions.md", "[IM-04]", "[IM-99]")
    assert "questions.md: Q-SA-01: ссылка на несуществующий IM-99" in validate_task(task_dir)


def test_question_parse_error_is_reported(task_dir):
    _edit(task_dir / "questions.md", " — *open, blocking*", "")
    assert any(e.startswith("questions.md: Q-PO-02: нет статуса") for e in validate_task(task_dir))


def test_decision_unknown_question_and_bad_date(task_dir):
    _edit(task_dir / "decisions.md", "| Q-PO-01 |", "| Q-PO-07 |")
    _edit(task_dir / "decisions.md", "2026-09-09", "09.09.2026")
    errors = validate_task(task_dir)
    assert "decisions.md: D-01: ссылка на несуществующий Q-PO-07" in errors
    assert "decisions.md: D-01: дата должна быть в формате ГГГГ-ММ-ДД" in errors


def test_state_rules():
    good = {"task": "X-1", "stage": "impact", "plugin_version": "0.1.0", "inputs": {}, "sections": {}}
    assert validate_state(good) == []
    bad = {
        "task": "",
        "stage": "review",
        "template": "Feature",
        "plugin_version": "1",
        "inputs": {"BRD": "abc", "nope": "0" * 40},
        "sections": {"05-api": {"hash": "x"}},
        "access": {"jira": "ftp", "slack": "mcp"},
    }
    errors = validate_state(bad)
    for fragment in ("task:", "stage:", "template:", "plugin_version:", "inputs.BRD", "inputs: неизвестный артефакт nope",
                     "sections.05-api.hash", "sections.05-api.edited_by_human", "access.jira", "access: неизвестный ключ slack"):
        assert any(fragment in e for e in errors), fragment


def test_cli(task_dir, capsys):
    assert main([str(task_dir)]) == 0
    assert capsys.readouterr().out.startswith("OK:")
    state = json.loads((task_dir / "state.json").read_text(encoding="utf-8"))
    state["stage"] = "oops"
    (task_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert main([str(task_dir)]) == 1
    assert "stage:" in capsys.readouterr().out
    assert main([]) == 2
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_validate'`.

- [ ] **Step 3: Реализовать валидатор**

`scripts/sa_validate.py`:

```python
"""Проверка артефактов задачи по схемам из shared/schemas/artifacts.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import (
    ArtifactError,
    find_refs,
    find_table,
    is_id,
    parse_questions,
    parse_tables,
    ref_prefix,
    split_frontmatter,
)
from sa_state import ARTIFACTS, STAGES, load_state

KINDS = {"процесс", "сервис", "модуль", "API", "Kafka", "БД", "роль", "UI", "конфиг"}
IMPACTS = {"новый", "изм.", "удал.", "?"}
IM_STATUSES = {"факт", "допущение"}
CONFIDENCE = {"высокая", "средняя", "низкая"}
ACCESS_KEYS = {"jira", "confluence", "git"}
ACCESS_MODES = {"mcp", "cli", "manual"}
EMPTY = {"", "—", "-"}

BRD_COLUMNS = ["ID", "Требование", "Тип"]
IMPACT_COLUMNS = ["ID", "Объект", "Вид", "Влияние", "← R", "Источник", "Статус", "Уверенность"]
DECISION_COLUMNS = ["ID", "← Q", "Решение", "Кто/где", "Дата"]

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
TEMPLATE_RE = re.compile(r"[a-z][a-z0-9-]*@\d+\.\d+")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
SHA1_RE = re.compile(r"[0-9a-f]{40}")


def _one_of(values: set[str]) -> str:
    return ", ".join(sorted(values))


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in ids:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def _unknown(refs: list[str], known: dict) -> list[str]:
    return [r for r in refs if known.get(ref_prefix(r)) is not None and r not in known[ref_prefix(r)]]


def validate_brd(text: str) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    for key in ("source", "fetched", "brd_complete", "missing"):
        if key not in meta:
            errors.append(f"во frontmatter нет ключа {key}")
    if "brd_complete" in meta and not isinstance(meta["brd_complete"], bool):
        errors.append("brd_complete должен быть true или false")
    if "missing" in meta and not isinstance(meta["missing"], list):
        errors.append("missing должен быть списком вида [a, b]")
    if meta.get("brd_complete") is False and meta.get("missing") == []:
        errors.append("brd_complete: false, но missing пуст — укажи, чего не хватает")
    table = find_table(parse_tables(body), BRD_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(BRD_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        if not is_id("R", row["ID"]):
            errors.append(f"{row['ID']}: ID должен быть вида R-01")
        if row["Требование"] in EMPTY:
            errors.append(f"{row['ID']}: пустое требование")
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_impact_map(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    if not isinstance(meta.get("index_used"), bool):
        errors.append("во frontmatter нужен index_used: true или false")
    if meta.get("confidence_cap") not in CONFIDENCE:
        errors.append(f"confidence_cap должен быть одним из: {_one_of(CONFIDENCE)}")
    table = find_table(parse_tables(body), IMPACT_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(IMPACT_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        rid = row["ID"]
        if not is_id("IM", rid):
            errors.append(f"{rid}: ID должен быть вида IM-01")
        if row["Вид"] not in KINDS:
            errors.append(f"{rid}: вид «{row['Вид']}» не из списка: {_one_of(KINDS)}")
        if row["Влияние"] not in IMPACTS:
            errors.append(f"{rid}: влияние «{row['Влияние']}» не из списка: {_one_of(IMPACTS)}")
        if row["Статус"] not in IM_STATUSES:
            errors.append(f"{rid}: статус «{row['Статус']}» не из списка: {_one_of(IM_STATUSES)}")
        if row["Уверенность"] not in CONFIDENCE:
            errors.append(f"{rid}: уверенность «{row['Уверенность']}» не из списка: {_one_of(CONFIDENCE)}")
        if row["Статус"] == "факт" and row["Источник"] in EMPTY:
            errors.append(f"{rid}: факт без источника — укажи источник или поменяй статус на допущение")
        refs = [r for r in find_refs(row["← R"]) if ref_prefix(r) == "R"]
        if not refs:
            errors.append(f"{rid}: нет ссылки на пункт BRD в колонке ← R")
        errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_questions(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    _, body = split_frontmatter(text)
    questions = parse_questions(body)
    for q in questions:
        if q.section == "":
            errors.append(f"{q.id}: вопрос вне секций «## Для PO» и «## Для аналитика»")
        elif q.section != q.audience:
            errors.append(f"{q.id}: лежит в секции {q.section}, а адресован {q.audience}")
        if not q.refs:
            errors.append(f"{q.id}: нет ссылки [R-xx] или [IM-xx]")
        errors += [f"{q.id}: ссылка на несуществующий {r}" for r in _unknown(q.refs, known)]
    ids = [q.id for q in questions]
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_decisions(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    _, body = split_frontmatter(text)
    table = find_table(parse_tables(body), DECISION_COLUMNS)
    if table is None:
        return [f"нет таблицы с колонками {', '.join(DECISION_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        did = row["ID"]
        if not is_id("D", did):
            errors.append(f"{did}: ID должен быть вида D-01")
        if row["← Q"] not in EMPTY:
            refs = [r for r in find_refs(row["← Q"]) if ref_prefix(r) == "Q"]
            if not refs:
                errors.append(f"{did}: в колонке ← Q ожидается Q-PO-xx, Q-SA-xx или —")
            errors += [f"{did}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
        if row["Решение"] in EMPTY:
            errors.append(f"{did}: пустое решение")
        if not DATE_RE.fullmatch(row["Дата"]):
            errors.append(f"{did}: дата должна быть в формате ГГГГ-ММ-ДД")
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def _is_sha1(value) -> bool:
    return isinstance(value, str) and SHA1_RE.fullmatch(value) is not None


def validate_state(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task: нужна непустая строка с ключом задачи")
    if data.get("stage") not in STAGES:
        errors.append(f"stage: одно из {', '.join(STAGES)}")
    template = data.get("template")
    if template is not None and not (isinstance(template, str) and TEMPLATE_RE.fullmatch(template)):
        errors.append("template: формат имя@мажор.минор, например feature@1.0")
    version = data.get("plugin_version")
    if not (isinstance(version, str) and SEMVER_RE.fullmatch(version)):
        errors.append("plugin_version: формат x.y.z")

    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        errors.append("inputs: ожидается объект")
    else:
        for name, value in inputs.items():
            if name not in ARTIFACTS:
                errors.append(f"inputs: неизвестный артефакт {name}")
            if not _is_sha1(value):
                errors.append(f"inputs.{name}: ожидается sha1")

    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        errors.append("sections: ожидается объект")
    else:
        for name, section in sections.items():
            section = section if isinstance(section, dict) else {}
            if not _is_sha1(section.get("hash")):
                errors.append(f"sections.{name}.hash: ожидается sha1")
            if not isinstance(section.get("edited_by_human"), bool):
                errors.append(f"sections.{name}.edited_by_human: true или false")

    access = data.get("access", {})
    if not isinstance(access, dict):
        errors.append("access: ожидается объект")
    else:
        for key, mode in access.items():
            if key not in ACCESS_KEYS:
                errors.append(f"access: неизвестный ключ {key}; допустимы {_one_of(ACCESS_KEYS)}")
            if mode not in ACCESS_MODES:
                errors.append(f"access.{key}: режим одно из {_one_of(ACCESS_MODES)}")
    return errors


def _run(task_dir: Path, name: str, check, errors: list[str]) -> set[str] | None:
    path = task_dir / ARTIFACTS[name]
    if not path.exists():
        return None
    try:
        found, ids = check(path.read_text(encoding="utf-8"))
    except ArtifactError as exc:
        found, ids = [str(exc)], None
    errors.extend(f"{ARTIFACTS[name]}: {message}" for message in found)
    return ids


def validate_task(task_dir: Path) -> list[str]:
    try:
        state = load_state(task_dir)
    except ArtifactError as exc:
        return [f"state.json: {exc}"]
    errors = [f"state.json: {message}" for message in validate_state(state)]
    known: dict = {"R": None, "IM": None, "Q": None}
    known["R"] = _run(task_dir, "BRD", validate_brd, errors)
    known["IM"] = _run(task_dir, "impact-map", lambda t: validate_impact_map(t, known), errors)
    known["Q"] = _run(task_dir, "questions", lambda t: validate_questions(t, known), errors)
    _run(task_dir, "decisions", lambda t: validate_decisions(t, known), errors)
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("использование: sa_validate.py <папка задачи>", file=sys.stderr)
        return 2
    task_dir = Path(argv[0])
    errors = validate_task(task_dir)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {task_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_validate.py -v`
Expected: 13 passed.

- [ ] **Step 5: Написать документ схем**

`shared/schemas/artifacts.md` — контракт для всех стадий. Стадии читают его перед записью артефакта.

````markdown
# Схемы артефактов задачи

Эталонный пример всех артефактов: `tests/fixtures/LKP-DEMO/` в репозитории плагина.

## Общие правила

- Папка задачи: `tasks/<KEY>/` в рабочей папке аналитика.
- Артефакты — markdown. Данные — в таблицах, проза — только там, где без неё нельзя.
- Шапка (frontmatter) — плоский YAML: `ключ: значение`. Значение — строка, целое, `true`/`false` или список `[a, b]`. Вложенных структур нет.
- ID: `R-01` (пункт BRD), `IM-01` (карта влияния), `Q-PO-01` и `Q-SA-01` (вопросы), `D-01` (решения), `RV-01` (замечания ревью). Минимум две цифры, сквозная нумерация в задаче, ID не переиспользуются.
- Пустое значение ячейки — `—`.

## sources/BRD.md

Шапка: `source` (ссылка), `fetched` (ГГГГ-ММ-ДД), `brd_complete` (`true`/`false`), `missing` (список коротких названий недостающих пунктов из `shared/rules/brd-checklist.md`; при `brd_complete: false` не пуст).

Таблица:

| Колонка | Значение |
|---|---|
| ID | `R-xx` |
| Требование | Формулировка из BRD, сжатая без потери смысла |
| Тип | `функц.`, `UI`, `данные`, `интеграция`, `НФТ`, `ограничение` |

## impact-map.md

Шапка: `index_used` (`true`, если использовался индекс `/docs`), `confidence_cap` (`высокая`, `средняя`, `низкая` — потолок уверенности; без индекса не выше `средняя`).

Таблица:

| Колонка | Значение |
|---|---|
| ID | `IM-xx` |
| Объект | `<сервис>: <что именно>` — метод, модуль, таблица, топик, экран |
| Вид | `процесс`, `сервис`, `модуль`, `API`, `Kafka`, `БД`, `роль`, `UI`, `конфиг` |
| Влияние | `новый`, `изм.`, `удал.`, `?` |
| ← R | Один или несколько `R-xx` через запятую |
| Источник | По формату из `shared/rules/ai-rules.md`; `—`, если источника нет |
| Статус | `факт` (есть источник) или `допущение` |
| Уверенность | `высокая`, `средняя`, `низкая` |

## questions.md

Две секции, заголовки строго такие: `## Для PO` и `## Для аналитика`. Вопрос — пункт списка:

```markdown
- **Q-PO-01** [R-01] Текст вопроса
  Варианты: а) …; б) … — *open*
```

- Первая строка: ID жирным, ссылки в квадратных скобках (`R-xx`, `IM-xx`, через запятую), текст.
- Продолжение — строки с отступом.
- Статус — в конце любой строки вопроса: `— *open*`, `— *answered*`, `— *obsolete*`; блокирующий открытый вопрос: `— *open, blocking*`.
- `Q-PO-xx` лежат только в секции PO, `Q-SA-xx` — только в секции аналитика.

## decisions.md

| Колонка | Значение |
|---|---|
| ID | `D-xx` |
| ← Q | `Q-PO-xx` / `Q-SA-xx`, или `—`, если решение принято без вопроса |
| Решение | Что решили, одной-двумя фразами |
| Кто/где | Кто принял и где зафиксировано: «PO, чат ММ», «разработка, MR !123» |
| Дата | ГГГГ-ММ-ДД |

## state.json

```json
{
  "task": "LKP-4155",
  "stage": "clarify",
  "template": "feature@1.0",
  "plugin_version": "0.1.0",
  "access": {"jira": "mcp", "confluence": "cli", "git": "cli"},
  "inputs": {"BRD": "<sha1>"},
  "sections": {"05-api": {"hash": "<sha1>", "edited_by_human": false}}
}
```

- `stage`: `impact`, `start`, `clarify`, `draft`, `check`, `done`.
- `template`: появляется на стадии `start`, формат `имя@мажор.минор`.
- `access`: выбранный режим доступа (`mcp`, `cli`, `manual`) по `shared/access/adapters.md`.
- `inputs`: sha1 входных артефактов на момент, когда их последний раз использовала стадия. Записывать командой `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> <артефакт>...`.
- `sections`: sha1 секций черновика и признак ручной правки.
- Счётчики вопросов здесь не хранятся: их считают по `questions.md`.

## Проверка

После записи любого артефакта стадия запускает:

```bash
python3 <плагин>/scripts/sa_validate.py tasks/<KEY>
```

`OK: …` — можно продолжать. Иначе исправь каждую строку ошибки и запусти снова. Не сообщай о завершении стадии, пока валидатор не вернул `OK`.
````

- [ ] **Step 6: Commit**

```bash
git add scripts/sa_validate.py shared/schemas/artifacts.md tests/test_sa_validate.py
git commit -m "feat: artifact validator and schema contract"
```

---

### Task 5: Команда `/tdd-status`

**Files:**
- Create: `scripts/sa_status.py`
- Create: `skills/tdd-status/SKILL.md`
- Delete: `skills/.gitkeep`
- Test: `tests/test_sa_status.py`

**Interfaces:**
- Consumes: из `sa_artifacts` — `ArtifactError`, `parse_questions`, `split_frontmatter`; из `sa_state` — `ARTIFACTS`, `load_state`, `stale_inputs`, `record_inputs`; фикстура `task_dir`.
- Produces:
  - `next_step(stage: str | None, blocking_open: int, brd_complete: bool | None) -> str`
  - `build_status(task_dir: Path) -> str`
  - CLI: `python3 scripts/sa_status.py <папка задачи>` (код 0; 1 при ошибке артефактов; 2 при неверных аргументах)
  - Скил `tdd-status`

Примечание: «незаполненные секции» из спеки (раздел 5.6) требуют манифеста шаблона — он появится в подпроекте 3. Сейчас сводка показывает секции из `draft/` и число плейсхолдеров `⚠` в каждой; сверка с манифестом добавится вместе с шаблоном `feature`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sa_status.py`:

```python
from sa_state import record_inputs
from sa_status import build_status, main, next_step

EXPECTED_DEMO = """\
Задача: LKP-DEMO · стадия: clarify · шаблон: feature@1.0
Артефакты: BRD ✓ · impact-map ✓ · context ✓ · questions ✓ · decisions ✓ · draft — · review —
Вопросы PO: открыто 1 (блокирующих 1)
Вопросы аналитику: открыто 1 (блокирующих 0)
Черновик: секций нет
Устаревшие входы: нет
Следующий шаг: /tdd-clarify — закрыть блокирующие вопросы"""


def test_demo_status(task_dir):
    assert build_status(task_dir) == EXPECTED_DEMO


def test_incomplete_brd(task_dir):
    brd = task_dir / "sources/BRD.md"
    text = brd.read_text(encoding="utf-8")
    text = text.replace("brd_complete: true", "brd_complete: false").replace("missing: []", "missing: [роли, критерии успеха]")
    brd.write_text(text, encoding="utf-8")
    status = build_status(task_dir)
    assert "BRD: неполный — не хватает: роли, критерии успеха" in status
    assert status.endswith("Следующий шаг: переслать вопросы PO, после ответов запустить /tdd-impact повторно")


def test_draft_sections_and_stale(task_dir):
    draft = task_dir / "draft"
    draft.mkdir()
    (draft / "01-context.md").write_text("Контекст\n", encoding="utf-8")
    (draft / "05-api.md").write_text("⚠ Q-PO-02\n⚠ Q-SA-01\n", encoding="utf-8")
    record_inputs(task_dir, ["decisions"])
    decisions = task_dir / "decisions.md"
    decisions.write_text(decisions.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    status = build_status(task_dir)
    assert "Черновик: 01-context, 05-api (⚠ 2)" in status
    assert "Устаревшие входы: decisions" in status


def test_next_step():
    assert next_step("impact", 0, True) == "/tdd-start"
    assert next_step("start", 0, None) == "/tdd-clarify"
    assert next_step("clarify", 0, True) == "/tdd-draft"
    assert next_step("draft", 0, True) == "/tdd-check"
    assert next_step("check", 0, True) == "/tdd-update по принятым замечаниям, затем /tdd-check"
    assert next_step("done", 0, True) == "задача завершена"
    assert next_step("???", 0, True) == "проверь state.json: неизвестная стадия"


def test_cli(task_dir, tmp_path, capsys):
    assert main([str(task_dir)]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_DEMO
    assert main([str(tmp_path / "nope")]) == 1
    assert main([]) == 2
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_status'`.

- [ ] **Step 3: Реализовать сводку**

`scripts/sa_status.py`:

```python
"""Сводка по задаче для /tdd-status. Читает только state.json и файлы задачи."""
from __future__ import annotations

import sys
from pathlib import Path

from sa_artifacts import ArtifactError, Question, parse_questions, split_frontmatter
from sa_state import ARTIFACTS, load_state, stale_inputs

_NEXT = {
    "impact": "/tdd-start",
    "start": "/tdd-clarify",
    "draft": "/tdd-check",
    "check": "/tdd-update по принятым замечаниям, затем /tdd-check",
    "done": "задача завершена",
}


def next_step(stage: str | None, blocking_open: int, brd_complete: bool | None) -> str:
    if brd_complete is False:
        return "переслать вопросы PO, после ответов запустить /tdd-impact повторно"
    if stage == "clarify":
        return "/tdd-clarify — закрыть блокирующие вопросы" if blocking_open else "/tdd-draft"
    return _NEXT.get(stage, "проверь state.json: неизвестная стадия")


def _questions_line(label: str, questions: list[Question], audience: str) -> str:
    open_questions = [q for q in questions if q.audience == audience and q.status == "open"]
    blocking = sum(q.blocking for q in open_questions)
    return f"{label}: открыто {len(open_questions)} (блокирующих {blocking})"


def build_status(task_dir: Path) -> str:
    state = load_state(task_dir)
    lines = [
        f"Задача: {state.get('task', '?')} · стадия: {state.get('stage', '?')} · "
        f"шаблон: {state.get('template', 'не выбран')}"
    ]
    marks = " · ".join(f"{name} {'✓' if (task_dir / path).exists() else '—'}" for name, path in ARTIFACTS.items())
    lines.append(f"Артефакты: {marks}")

    brd_complete = None
    brd = task_dir / ARTIFACTS["BRD"]
    if brd.exists():
        meta, _ = split_frontmatter(brd.read_text(encoding="utf-8"))
        brd_complete = meta.get("brd_complete")
        if brd_complete is False:
            missing = meta.get("missing") or ["не указано"]
            lines.append(f"BRD: неполный — не хватает: {', '.join(missing)}")

    questions: list[Question] = []
    questions_path = task_dir / ARTIFACTS["questions"]
    if questions_path.exists():
        _, body = split_frontmatter(questions_path.read_text(encoding="utf-8"))
        questions = parse_questions(body)
    lines.append(_questions_line("Вопросы PO", questions, "PO"))
    lines.append(_questions_line("Вопросы аналитику", questions, "SA"))

    draft_dir = task_dir / "draft"
    sections = sorted(draft_dir.glob("*.md")) if draft_dir.is_dir() else []
    if sections:
        parts = []
        for section in sections:
            placeholders = section.read_text(encoding="utf-8").count("⚠")
            parts.append(section.stem + (f" (⚠ {placeholders})" if placeholders else ""))
        lines.append(f"Черновик: {', '.join(parts)}")
    else:
        lines.append("Черновик: секций нет")

    stale = stale_inputs(task_dir, state)
    lines.append(f"Устаревшие входы: {', '.join(stale) if stale else 'нет'}")

    blocking_open = sum(q.blocking for q in questions if q.status == "open")
    lines.append(f"Следующий шаг: {next_step(state.get('stage'), blocking_open, brd_complete)}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("использование: sa_status.py <папка задачи>", file=sys.stderr)
        return 2
    try:
        print(build_status(Path(argv[0])))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_status.py -v`
Expected: 5 passed.

- [ ] **Step 5: Написать скил**

Удалить `skills/.gitkeep`. Создать `skills/tdd-status/SKILL.md`:

```markdown
---
name: tdd-status
description: Показывает, где аналитик находится в пайплайне ТЗ по задаче — стадия, артефакты, открытые вопросы PO и аналитику, секции черновика, устаревшие входы и следующий шаг. Используй, когда спрашивают «где я», «что осталось», «статус задачи», или перед продолжением работы над задачей после паузы.
---

# /tdd-status

Сводка по задаче без чтения артефактов в контекст: всё считает скрипт.

## Шаги

1. Определи папку задачи:
   - аргумент — путь к существующей папке: используй его;
   - аргумент — ключ задачи (например `LKP-4155`): `tasks/<ключ>`;
   - аргумента нет: найди `tasks/*/state.json` в текущей папке. Одна задача — бери её. Несколько — покажи список ключей и спроси, какую. Ни одной — скажи, что задач нет, и предложи начать с `/tdd-impact <ссылка на BRD>`.
2. Запусти скрипт, где `<база>` — базовая директория этого скила:

   ```bash
   python3 <база>/../../scripts/sa_status.py tasks/<KEY>
   ```

3. Выведи результат пользователю как есть, в блоке кода.
4. Если есть строка «Устаревшие входы» со значением, отличным от «нет», добавь одну фразу: какие артефакты изменились после того, как их использовала стадия, и что зависимые стадии стоит перезапустить.

## Чего не делать

- Не читай артефакты задачи сам: скрипт уже всё посчитал.
- Не меняй файлы задачи.
- Если скрипт вернул ошибку, покажи её и предложи запустить `python3 <база>/../../scripts/sa_validate.py tasks/<KEY>`, чтобы увидеть все проблемы формата.
```

- [ ] **Step 6: Запустить все тесты**

Run: `.venv/bin/pytest -v`
Expected: все тесты проходят, включая `test_every_skill_has_valid_frontmatter` для `tdd-status`.

- [ ] **Step 7: Ручная проверка в Claude Code**

Run:

```bash
mkdir -p /tmp/sa-smoke/tasks && cp -R tests/fixtures/LKP-DEMO /tmp/sa-smoke/tasks/
cd /tmp/sa-smoke && claude --plugin-dir /Users/waraxe.in/.superset/projects/SA-Skills -p "/tdd-status LKP-DEMO"
```

Expected: в ответе сводка, совпадающая с `EXPECTED_DEMO` из теста. Если флага `--plugin-dir` нет в установленной версии Claude Code, поставить плагин через `/plugin marketplace add /Users/waraxe.in/.superset/projects/SA-Skills` и `/plugin install sa-skills@sa-skills-marketplace`, затем выполнить `/tdd-status LKP-DEMO` в `/tmp/sa-smoke`. Результат проверки записать в описание коммита.

- [ ] **Step 8: Commit**

```bash
git rm -q skills/.gitkeep
git add scripts/sa_status.py skills/tdd-status tests/test_sa_status.py
git commit -m "feat: /tdd-status command"
```

---

### Task 6: Общие правила, адаптеры доступа, README

**Files:**
- Create: `shared/rules/ai-rules.md`
- Create: `shared/rules/writing-style.md`
- Create: `shared/rules/question-routing.md`
- Create: `shared/rules/brd-checklist.md`
- Create: `shared/access/adapters.md`
- Create: `README.md`
- Delete: `shared/.gitkeep`, `scripts/.gitkeep`
- Test: `tests/test_shared_docs.py`

**Interfaces:**
- Consumes: константы `BRD_COLUMNS`, `IMPACT_COLUMNS`, `DECISION_COLUMNS`, `KINDS`, `IMPACTS`, `CONFIDENCE` из `sa_validate`; `STAGES` из `sa_state`; `shared/schemas/artifacts.md` из задачи 4.
- Produces: справочники, которые читают стадии подпроектов 2–6. Короткие названия пунктов BRD из `brd-checklist.md` (`цель`, `роли`, `целевое поведение`, `границы`, `критерии успеха`) используются в `missing` у `sources/BRD.md`.

- [ ] **Step 1: Написать падающий тест документов**

`tests/test_shared_docs.py`:

```python
from pathlib import Path

import pytest

from sa_state import STAGES
from sa_validate import BRD_COLUMNS, CONFIDENCE, DECISION_COLUMNS, IMPACT_COLUMNS, IMPACTS, KINDS

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_HEADINGS = {
    "shared/rules/ai-rules.md": ["## Факт и допущение", "## Источники", "## Идентификаторы", "## Работа с артефактами", "## Чего не делать"],
    "shared/rules/writing-style.md": ["## Общие правила", "## Как есть и как будет", "## Оформление", "## Запрещённые формулировки"],
    "shared/rules/question-routing.md": ["## Кому адресовать", "## Как формулировать для PO", "## Как формулировать для аналитика", "## Смешанные вопросы", "## Примеры"],
    "shared/rules/brd-checklist.md": ["## Обязательные пункты", "## Желательные пункты", "## Как принимать решение"],
    "shared/access/adapters.md": ["## Порядок выбора", "## Jira", "## Confluence", "## Git", "## Ручной режим", "## Запись выбора"],
    "shared/schemas/artifacts.md": ["## Общие правила", "## sources/BRD.md", "## impact-map.md", "## questions.md", "## decisions.md", "## state.json", "## Проверка"],
}


@pytest.mark.parametrize("rel_path", sorted(REQUIRED_HEADINGS))
def test_doc_has_headings(rel_path):
    text = (ROOT / rel_path).read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS[rel_path]:
        assert f"\n{heading}\n" in text, f"{rel_path}: нет заголовка {heading}"


def test_schema_doc_matches_validator():
    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    for column in BRD_COLUMNS + IMPACT_COLUMNS + DECISION_COLUMNS:
        assert f"| {column} |" in text, f"колонка {column} не описана"
    for value in KINDS | IMPACTS | CONFIDENCE:
        assert f"`{value}`" in text, f"значение {value} не описано"
    for stage in STAGES:
        assert f"`{stage}`" in text, f"стадия {stage} не описана"


def test_brd_checklist_short_names():
    text = (ROOT / "shared/rules/brd-checklist.md").read_text(encoding="utf-8")
    for name in ("цель", "роли", "целевое поведение", "границы", "критерии успеха"):
        assert f"`{name}`" in text, name
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `.venv/bin/pytest tests/test_shared_docs.py -v`
Expected: FAIL — `FileNotFoundError` для `shared/rules/ai-rules.md` и других (тест схем проходит, он из задачи 4).

- [ ] **Step 3: Написать `shared/rules/ai-rules.md`**

```markdown
# Правила работы ИИ в пайплайне ТЗ

Действуют на всех стадиях. Стадия читает этот файл до начала работы.

## Факт и допущение

- Факт — утверждение с источником: строка кода, страница Confluence, пункт BRD, решение из `decisions.md`.
- Допущение — всё остальное. Помечай его словом «допущение» и не выдавай за факт.
- Допущение с низкой уверенностью превращай в вопрос: бизнесовое — в `Q-PO`, техническое — в `Q-SA` (правила — `question-routing.md`).
- Косвенный источник (имя файла, комментарий в коде, устаревшая страница) даёт уверенность не выше «средняя».

## Источники

| Источник | Формат | Пример |
|---|---|---|
| Код | `code: <репо>/<путь>:<строка>` | `code: lkp-back/app/Rules/Promocode.php:40` |
| Индекс /docs | `docs: <репо>/docs/<файл>#<раздел>` | `docs: lkp-front/docs/tech.md#promocode` |
| Confluence | `confluence: <id страницы>#<раздел>` | `confluence: 123456#Доступы` |
| Jira | `jira: <KEY>` | `jira: LKP-4155` |
| BRD | `BRD R-xx` | `BRD R-01` |
| Решение | `D-xx` | `D-03` |
| Устное | `<кто>, <где>, <дата>` | `PO, чат ММ, 2026-09-09` |

Не копируй большие куски источника в артефакт: нужна выжимка и ссылка.

## Идентификаторы

- `R-xx`, `IM-xx`, `Q-PO-xx`, `Q-SA-xx`, `D-xx`, `RV-xx`. Минимум две цифры, сквозная нумерация в задаче.
- Новый ID — максимальный существующий этого типа плюс один.
- ID не переиспользуются и не перенумеровываются. Неактуальный пункт меняет статус (`obsolete`, `удал.`) и остаётся в файле.
- Каждое утверждение в артефакте ссылается на ID, из которого вытекает.

## Работа с артефактами

- Читай только входы своей стадии, перечисленные в её SKILL.md. Если выжимка источника уже есть в `sources/`, сырой источник не перечитывай.
- Формат артефактов — `shared/schemas/artifacts.md`.
- После записи артефактов запусти валидатор и исправь ошибки до того, как сообщить о завершении стадии.
- После завершения стадии запиши хэши использованных входов через `sa_state.py record`.
- Правки аналитика в артефактах главнее твоих. Не перезаписывай их молча: покажи, что хочешь изменить, и спроси.

## Чего не делать

- Не выдумывай имена сервисов, полей, методов, топиков, таблиц, ролей. Нет источника — допущение или вопрос.
- Не отвечай на вопросы за PO и не принимай бизнес-решений.
- Не расширяй скоуп за пределы BRD и `context.md`. Нашёл смежное влияние — заведи `Q-SA` с вопросом, входит ли оно в скоуп.
- Не публикуй ничего за пределами личного пространства аналитика.
- Не делай коммитов и пушей в репозитории сервисов.
```

- [ ] **Step 4: Написать `shared/rules/writing-style.md`**

```markdown
# Стиль текста ТЗ и артефактов

Стиль взят из эталонных ТЗ команды. Цель — текст, который разработчик читает один раз и делает по нему без уточнений.

## Общие правила

- Одна мысль — один пункт. Нумерованные пункты для последовательностей и задач на доработку, маркированные — для перечислений.
- Сначала что делаем, потом зачем. Обоснование — короткой второй фразой или в «Примечании».
- Имена сервисов, методов, полей, таблиц, топиков — как в коде, в `моноширинном` шрифте: `partners-dashboard`, `promocode/check-usage`, `crm_phone`.
- Термины — из глоссария страницы. Новый термин сначала добавь в глоссарий.
- Тексты, которые увидит пользователь, — в «ёлочках», дословно: «Промокод успешно применён».
- Числа и границы — точные: «до 25 символов», «кэш 10 минут», а не «короткий», «недолго».
- Важное, что легко пропустить, выноси в блок «ВАЖНО!» или «Примечание:».

## Как есть и как будет

- Поведение, которое не меняется, помечай `[as is]`; новое — `[to be]`.
- В таблицах сравнения делай колонки «Что сейчас [as is]» и «Что добавляется [to be]».
- Регресс — отдельной группой критериев приёмки: что должно работать как раньше.

## Оформление

- User Story: «Я, как <роль>, хочу <действие>, чтобы <ценность>». Критерии приёмки — списком, каждый проверяем (условие → действие → результат).
- Процесс: краткое описание пунктами со ссылками на шаги диаграммы `[001]–[004]`, шаги нумеруются трёхзначно.
- Метод API: назначение, «Параметры на вход» и «Параметры на выход» таблицами (Параметр, Тип, Описание, Примечание), алгоритм, таблица ответов (№, Ситуация, ответ, как трактует потребитель), пример запроса и ответа.
- Доработки — по сервисам: «Сервис: <имя>», затем «Задача:» с нумерованными пунктами.
- Открытые вопросы: вопрос, затем ответ с источником — «Согласовано в чате ММ от 09.09.2026: …».

## Запрещённые формулировки

- Оценочные слова без измерения: «удобно», «быстро», «корректно», «оптимально», «при необходимости», «и т.д.», «и др.».
- Неопределённый субъект: «система обработает» — пиши, какой сервис.
- «Должно работать как обычно» — опиши, как именно, или сошлись на `[as is]` пункт.
- Маркеры генерации: «Отличный вопрос», «Давайте рассмотрим», «В заключение».
```

- [ ] **Step 5: Написать `shared/rules/question-routing.md`**

```markdown
# Кому задавать вопрос: PO или аналитику

Главное правило: PO не получает технических вопросов. Всё, что можно выяснить по коду, документации или у разработки, — вопрос аналитику.

## Кому адресовать

| Тема | Кому |
|---|---|
| Бизнес-правило, политика, что разрешено и запрещено | PO |
| Приоритеты, скоуп, что входит в MVP и что откладываем | PO |
| Тексты для пользователя, тон, юридические формулировки | PO |
| Поведение в бизнес-исключениях: что делать с клиентом, деньгами, начислениями | PO |
| Сроки, релиз, зависимость от других бизнес-инициатив | PO |
| Как устроено сейчас: код, контракт, БД, топик, конфиг | аналитик |
| Какие сервисы затронуты, кто потребитель метода | аналитик |
| Нагрузка, кэширование, ретраи, таймауты, доступы | аналитик |
| Данные: сколько записей, какие форматы встречаются | аналитик |

## Как формулировать для PO

- Языком бизнеса: без имён сервисов, методов, полей, таблиц, топиков, HTTP-кодов.
- Одна развилка — один вопрос. В начале — контекст в одну фразу.
- Где можно, давай варианты: «а) …; б) …; в) другое». PO выбирает, а не пишет эссе.
- Указывай последствие каждого варианта для клиента или денег, если оно неочевидно.
- Ссылка на пункт BRD в квадратных скобках обязательна: `[R-02]`.

## Как формулировать для аналитика

- Конкретно: что проверить и где — репозиторий, путь, страница.
- Ссылка на пункт карты влияния или BRD: `[IM-04]`.
- Если ответ можно получить самому агенту, а не аналитику (прочитать код), — это не вопрос, а задача стадии: сделай сам.

## Смешанные вопросы

Если вопрос содержит и бизнес-развилку, и техническую деталь, раздели его:

- `Q-PO` — что должно происходить для пользователя или бизнеса;
- `Q-SA` — как это сейчас устроено и что придётся менять.

Технический вопрос, ответ на который зависит от решения PO, помечай в тексте: «после Q-PO-03».

## Примеры

| Плохо | Хорошо |
|---|---|
| Q-PO: Нужно ли в `promocode/check-usage` возвращать 422 при самореферальности? | Q-PO: Если мерчант указал собственный промокод, блокируем отправку анкеты или только предупреждаем? а) блокируем; б) предупреждаем и пропускаем |
| Q-PO: Писать ли отметку в поле `manager_comment` таблицы `questionnaires`? | Q-PO: Если проверить промокод не удалось, нужно ли сотрудникам клиентского сервиса видеть это в карточке анкеты? |
| Q-SA: Что делать с уже начисленными вознаграждениями? | Q-PO: Что делать с вознаграждениями, уже начисленными за собственные анкеты? а) не пересчитывать; б) пересчитать |
| Q-PO: Как кэшируется ответ партнёрки? | Q-SA: Какой ключ кэша у ответа партнёрки в карточке анкеты? Где проверить: lkp-back, клиент партнёрского сервиса |
```

- [ ] **Step 6: Написать `shared/rules/brd-checklist.md`**

```markdown
# Чек-лист полноты BRD

Используется на стадии `/tdd-impact`. Если не хватает хотя бы одного обязательного пункта, BRD неполный: `brd_complete: false`, короткие названия недостающих пунктов — в `missing`.

## Обязательные пункты

| Короткое название | Что должно быть в BRD | Признак, что пункта нет |
|---|---|---|
| `цель` | Проблема или возможность и зачем это бизнесу | Есть только «что сделать», нет «зачем» |
| `роли` | Кто пользуется результатом: клиент, сотрудник, партнёр, внешняя система | Не назван ни один пользователь |
| `целевое поведение` | Что должно происходить: сценарии, правила, ограничения | Описан только заголовок или одна фраза без правил |
| `границы` | Что входит в задачу и что явно не входит | Нельзя ответить, входит ли смежный случай |
| `критерии успеха` | Как понять, что сделано: проверяемый результат или метрика | Нет ни одного проверяемого результата |

## Желательные пункты

Их отсутствие не останавливает стадию, но даёт вопрос `Q-PO`:

- сроки или релиз;
- приоритет относительно других задач;
- макеты или ссылка на дизайн, если есть интерфейс;
- юридические и финансовые ограничения;
- связанные задачи и инициативы.

## Как принимать решение

1. Пройди обязательные пункты по порядку. Для каждого найди в BRD фрагмент, который его закрывает.
2. Нашёл — пункт есть, запомни, какие `R-xx` его закрывают.
3. Не нашёл или фрагмент слишком общий («сделать удобно», «как в конкурентах») — пункта нет. Заведи `Q-PO` по правилам `question-routing.md`.
4. Хотя бы один обязательный пункт отсутствует — `brd_complete: false`, карту влияния не строй. Аналитику — блок вопросов для PO.
5. Сомневаешься — считай пункт отсутствующим: дешевле задать вопрос, чем строить ТЗ на догадке.
```

- [ ] **Step 7: Написать `shared/access/adapters.md`**

````markdown
# Доступ к Jira, Confluence и Git

Каждая система подключается одним из трёх режимов. Режим выбирается при первом обращении к системе в задаче и сохраняется в `state.json`.

## Порядок выбора

1. Если в `state.json` уже есть `access.<система>` — используй его.
2. Иначе пробуй по порядку: `mcp` → `cli` → `manual`.
3. Режим не сработал (нет инструмента, ошибка авторизации, таймаут) — коротко скажи пользователю, что не сработало, и переходи к следующему. Стадия не прерывается.
4. Пользователь может сам назвать режим — тогда используй его.

## Jira

- `mcp`: в списке инструментов есть MCP-инструменты с `jira` или `atlassian` в имени. Получи задачу: описание, статус, связи.
- `cli`: переменные `JIRA_BASE_URL` и `JIRA_TOKEN`.

  ```bash
  # Server / Data Center (Personal Access Token)
  curl -sf -H "Authorization: Bearer $JIRA_TOKEN" \
    "$JIRA_BASE_URL/rest/api/2/issue/<KEY>?fields=summary,description,status,issuelinks"
  # Cloud (email + API token)
  curl -sf -u "$JIRA_EMAIL:$JIRA_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/issue/<KEY>?fields=summary,description,status,issuelinks"
  ```

## Confluence

- `mcp`: MCP-инструменты с `confluence` или `atlassian` в имени.
- `cli`: переменные `CONFLUENCE_BASE_URL` и `CONFLUENCE_TOKEN`.

  ```bash
  curl -sf -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
    "$CONFLUENCE_BASE_URL/rest/api/content/<id>?expand=body.storage,version"
  # поиск по заголовку
  curl -sf -G -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
    --data-urlencode 'cql=title="<заголовок>"' "$CONFLUENCE_BASE_URL/rest/api/content/search"
  ```

- Ответ в формате storage (XHTML) большой. Не держи его в контексте: сразу сохрани выжимку в `sources/confluence-<id>.md` — заголовки, таблицы, ключевые правила со ссылками на разделы.

## Git

- Репозитории сервисов клонированы локально в `$SA_REPOS_ROOT` (по умолчанию `~/repos`), папка репозитория — имя сервиса.
- `cli`: обычные команды `git -C <репо> …`, поиск — `grep -rn` или `git grep`.
- Перед чтением кода проверь, что ветка актуальна: `git -C <репо> fetch --quiet && git -C <репо> status -sb`. Если локальная ветка отстаёт — скажи пользователю, не делай `pull` сам.
- Только чтение. Коммиты и пуши в репозитории сервисов — запрещены (кроме `/sa-index-docs`, который пишет в отдельную ветку).

## Ручной режим

- Попроси пользователя вставить текст задачи или страницы либо положить выгрузку в `tasks/<KEY>/sources/`.
- Сохрани выжимку в `sources/` с `source: manual` в шапке и пометкой, откуда текст по словам пользователя.

## Запись выбора

После первого успешного обращения запиши режим в `state.json`:

```json
"access": {"jira": "mcp", "confluence": "cli", "git": "cli"}
```

Допустимые значения: `mcp`, `cli`, `manual`.
````

- [ ] **Step 8: Написать `README.md`**

````markdown
# SA Skills

Плагин Claude Code для пайплайна системного аналитика: карта влияния → старт контекста → уточнение BRD → черновик ТЗ → независимое ревью.

Дизайн: `docs/superpowers/specs/2026-10-15-sa-skills-pipeline-design.md`.

## Установка

В Claude Code:

```
/plugin marketplace add <путь к клону или git-URL этого репозитория>
/plugin install sa-skills@sa-skills-marketplace
```

Нужен Python ≥ 3.10 (только стандартная библиотека).

## Команды

| Команда | Что делает | Статус |
|---|---|---|
| `/tdd-status [KEY]` | Где вы в процессе: стадия, вопросы, черновик, следующий шаг | готово |
| `/tdd-impact <ссылка>` | Карта влияния по BRD | подпроект 2 |
| `/tdd-start` | Контекст-пакет | подпроект 2 |
| `/tdd-clarify` | Вопросы PO и аналитику, журнал решений | подпроект 2 |
| `/tdd-draft` | Черновик ТЗ по шаблону | подпроект 3 |
| `/tdd-check` | Независимое ревью черновика | подпроект 4 |
| `/tdd-update` | Точечное обновление черновика | подпроект 4 |
| `/sa-index-docs` | Индекс `/docs` по коду сервисов | подпроект 5 |

Артефакты задачи лежат в `tasks/<KEY>/` рабочей папки. Форматы — `shared/schemas/artifacts.md`.

## Разработка

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```
````

- [ ] **Step 9: Убрать заглушки и запустить все тесты**

```bash
rm -f shared/.gitkeep scripts/.gitkeep
.venv/bin/pytest -v
```

Expected: все тесты проходят.

- [ ] **Step 10: Commit**

```bash
git add -A shared README.md tests/test_shared_docs.py scripts
git commit -m "docs: shared rules, access adapters, README"
```
