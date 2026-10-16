# SA Skills — подпроект 2: impact, start, clarify — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Первые три стадии пайплайна: `/tdd-impact` (BRD → карта влияния и вопросы), `/tdd-start` (контекст-пакет), `/tdd-clarify` (ответы → журнал решений, новые вопросы), плюс субагент `source-reader` и детерминированные помощники для ID и экспорта вопросов.

**Architecture:** Скилы — тонкие инструкции, вся механика (ID, экспорт вопросов, валидация, состояние) — в stdlib-скриптах `scripts/`. Код сервисов читает только субагент `source-reader` и возвращает строки карты влияния, сырой код в контекст стадии не попадает. Схема нового артефакта `context.md` описана в `shared/schemas/artifacts.md` и проверяется валидатором.

**Tech Stack:** Claude Code plugin (SKILL.md, agents/*.md), Python ≥ 3.10 (stdlib) для скриптов, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-sa-skills-pipeline-design.md` (разделы 4, 5.1–5.3, 9, 10)

## Global Constraints

- Скрипты в `scripts/` — только стандартная библиотека Python ≥ 3.10.
- Все тексты для пользователя — на русском.
- Скилы ссылаются на файлы плагина как `<плагин>/scripts/…` и `<плагин>/shared/…`, где `<плагин>` = `<база>/../..`, `<база>` — базовая директория скила.
- Команды скилов запускаются из рабочей папки аналитика; папка задачи — `tasks/<KEY>`.
- Каждый SKILL.md имеет frontmatter `name`, `description`, `allowed-tools: Bash(python3:*)`.
- Субагенты плагина вызываются как `sa-skills:<имя>`.
- Источник истины по форматам — `shared/schemas/artifacts.md`; валидатор `scripts/sa_validate.py` проверяет ровно то, что там написано.
- После записи артефактов стадия запускает валидатор и не сообщает о завершении, пока он не вернул `OK`.
- Индекс системы: `${SA_SYSTEM_DOCS:-${SA_REPOS_ROOT:-$HOME/repos}/system-docs}/docs/`; репозитории сервисов: `${SA_REPOS_ROOT:-$HOME/repos}/<сервис>`.
- Не редактировать существующие тестовые фикстуры, кроме `tests/fixtures/LKP-DEMO/context.md` в задаче 3.

## Структура файлов

```
scripts/
  sa_ids.py                         # новый: следующий свободный ID
  sa_questions.py                   # новый: экспорт открытых вопросов
  sa_artifacts.py                   # изменение: Question.details
  sa_validate.py                    # изменение: validate_context
agents/
  source-reader.md                  # новый субагент
skills/
  tdd-impact/SKILL.md
  tdd-start/SKILL.md
  tdd-clarify/SKILL.md
shared/
  schemas/artifacts.md              # + раздел context.md
  access/adapters.md                # + SA_SYSTEM_DOCS, локальный файл
tests/
  test_sa_ids.py
  test_sa_questions.py
  test_sa_validate.py               # + тесты context.md
  test_sa_artifacts.py              # + тест details
  test_shared_docs.py               # + раздел context.md
  test_plugin_structure.py          # + агенты, ссылки на файлы плагина
  test_skills_contract.py           # контракт каждого скила стадии
  fixtures/LKP-DEMO/context.md      # переписан под схему
  fixtures/e2e/                     # BRD и мини-репозитории для сквозной проверки
README.md
```

---

### Task 1: Следующий свободный ID (`sa_ids.py`)

**Files:**
- Create: `scripts/sa_ids.py`
- Test: `tests/test_sa_ids.py`

**Interfaces:**
- Consumes: `ArtifactError` из `sa_artifacts`; `ARTIFACTS` из `sa_state`; фикстура `task_dir` (копия `tests/fixtures/LKP-DEMO`: R-01..R-03, IM-01..IM-04, Q-PO-01..02, Q-SA-01, D-01).
- Produces:
  - `KINDS: dict[str, str]` — вид ID → имя артефакта-владельца: `R`→`BRD`, `IM`→`impact-map`, `Q-PO`/`Q-SA`→`questions`, `D`→`decisions`
  - `next_ids(task_dir: Path, kind: str, count: int = 1) -> list[str]`
  - CLI: `python3 scripts/sa_ids.py next <папка задачи> <вид> [количество]` — печатает ID по одному в строке; код 0, 1 при ошибке, 2 при неверных аргументах.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sa_ids.py`:

```python
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
    assert main([]) == 2
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_ids.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_ids'`.

- [ ] **Step 3: Реализовать модуль**

`scripts/sa_ids.py`:

```python
"""Следующий свободный ID в задаче: R, IM, Q-PO, Q-SA, D."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError
from sa_state import ARTIFACTS

KINDS = {"R": "BRD", "IM": "impact-map", "Q-PO": "questions", "Q-SA": "questions", "D": "decisions"}


def next_ids(task_dir: Path, kind: str, count: int = 1) -> list[str]:
    if kind not in KINDS:
        raise ArtifactError(f"неизвестный вид ID {kind}; допустимы: {', '.join(KINDS)}")
    if count < 1:
        raise ArtifactError("количество должно быть не меньше 1")
    path = task_dir / ARTIFACTS[KINDS[kind]]
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"(?<![\w-]){re.escape(kind)}-(\d{{2,}})\b")
    start = max((int(n) for n in pattern.findall(text)), default=0) + 1
    return [f"{kind}-{n:02d}" for n in range(start, start + count)]


USAGE = "использование: sa_ids.py next <папка задачи> <вид: R|IM|Q-PO|Q-SA|D> [количество]"


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4) or argv[0] != "next" or (len(argv) == 4 and not argv[3].isdigit()):
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
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_ids.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_ids.py tests/test_sa_ids.py
git commit -m "feat: next free ID helper (sa_ids.py)"
```

---

### Task 2: Экспорт вопросов (`sa_questions.py`) и строки продолжения вопроса

**Files:**
- Modify: `scripts/sa_artifacts.py` (класс `Question`, функция `parse_questions`)
- Create: `scripts/sa_questions.py`
- Test: `tests/test_sa_artifacts.py` (добавить тест), `tests/test_sa_questions.py`

**Interfaces:**
- Consumes: `parse_questions`, `split_frontmatter`, `ArtifactError` из `sa_artifacts`; `ARTIFACTS`, `load_state` из `sa_state`; фикстура `task_dir`.
- Produces:
  - `Question.details: list[str]` — строки продолжения вопроса (с отступом) без маркера статуса, пустые отброшены; по умолчанию `[]`.
  - `export_questions(task_dir: Path, audience: str) -> str` — `audience` = `"PO"` или `"SA"`.
  - CLI: `python3 scripts/sa_questions.py export <папка задачи> [PO|SA]` (по умолчанию `PO`); код 0, 1 при ошибке, 2 при неверных аргументах.

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `tests/test_sa_artifacts.py`:

```python
def test_parse_questions_keeps_details():
    body = (
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Что делать?\n"
        "  Варианты: а) да; б) нет — *open*\n"
        "- **Q-PO-02** [R-02] Без деталей — *open*\n"
    )
    qs = parse_questions(body)
    assert qs[0].details == ["Варианты: а) да; б) нет"]
    assert qs[1].details == []
```

`tests/test_sa_questions.py`:

```python
import pytest

from sa_artifacts import ArtifactError
from sa_questions import export_questions, main

EXPECTED_PO = """\
Вопросы по задаче LKP-DEMO

Q-PO-02. Какой текст показать мерчанту, если он указал собственный промокод? (нужен ответ до черновика ТЗ)

Пожалуйста, отвечайте с номером вопроса, например: «Q-PO-02: …»."""

EXPECTED_SA = """\
Вопросы по задаче LKP-DEMO

Q-SA-01 [IM-04]. Публикует ли lkp-back событие в Kafka при сохранении анкеты?
   Где проверить: lkp-back/app/Events"""


def test_export_po(task_dir):
    assert export_questions(task_dir, "PO") == EXPECTED_PO


def test_export_sa(task_dir):
    assert export_questions(task_dir, "SA") == EXPECTED_SA


def test_blocking_first_and_details(task_dir):
    (task_dir / "questions.md").write_text(
        "## Для PO\n"
        "- **Q-PO-01** [R-01] Обычный вопрос\n"
        "  Варианты: а) да; б) нет — *open*\n"
        "- **Q-PO-02** [R-02] Срочный вопрос — *open, blocking*\n"
        "- **Q-PO-03** [R-03] Закрытый вопрос — *answered*\n",
        encoding="utf-8",
    )
    text = export_questions(task_dir, "PO")
    assert text.index("Q-PO-02.") < text.index("Q-PO-01.")
    assert "   Варианты: а) да; б) нет" in text
    assert "Q-PO-03" not in text
    assert text.endswith("например: «Q-PO-02: …».")


def test_no_open_questions(task_dir):
    (task_dir / "questions.md").unlink()
    assert export_questions(task_dir, "PO") == "Открытых вопросов для PO нет."
    assert export_questions(task_dir, "SA") == "Открытых вопросов для аналитика нет."


def test_bad_audience(task_dir):
    with pytest.raises(ArtifactError, match="PO или SA"):
        export_questions(task_dir, "QA")


def test_cli(task_dir, tmp_path, capsys):
    assert main(["export", str(task_dir)]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_PO
    assert main(["export", str(task_dir), "SA"]) == 0
    assert capsys.readouterr().out.strip() == EXPECTED_SA
    assert main(["export", str(tmp_path / "nope")]) == 1
    assert main(["export"]) == 2
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_questions.py tests/test_sa_artifacts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_questions'` и `AttributeError: 'Question' object has no attribute 'details'`.

- [ ] **Step 3: Добавить `details` в `sa_artifacts.py`**

В классе `Question` после поля `bad_refs` добавить:

```python
    details: list[str] = field(default_factory=list)
```

В `parse_questions` в вызов `Question(...)` после `bad_refs=bad_refs,` добавить:

```python
                details=[d for d in (_Q_STATUS.sub("", line).strip() for line in chunk[1:]) if d],
```

- [ ] **Step 4: Реализовать экспорт**

`scripts/sa_questions.py`:

```python
"""Блок открытых вопросов для пересылки: PO — без ссылок, аналитику — со ссылками."""
from __future__ import annotations

import sys
from pathlib import Path

from sa_artifacts import ArtifactError, parse_questions, split_frontmatter
from sa_state import ARTIFACTS, load_state

_WHO = {"PO": "PO", "SA": "аналитика"}


def export_questions(task_dir: Path, audience: str) -> str:
    if audience not in _WHO:
        raise ArtifactError("адресат: PO или SA")
    state = load_state(task_dir)
    path = task_dir / ARTIFACTS["questions"]
    questions = parse_questions(split_frontmatter(path.read_text(encoding="utf-8"))[1]) if path.exists() else []
    open_questions = sorted(
        (q for q in questions if q.audience == audience and q.status == "open"),
        key=lambda q: not q.blocking,
    )
    if not open_questions:
        return f"Открытых вопросов для {_WHO[audience]} нет."
    blocks = []
    for q in open_questions:
        refs = f" [{', '.join(q.refs)}]" if audience == "SA" else ""
        mark = " (нужен ответ до черновика ТЗ)" if q.blocking else ""
        blocks.append("\n".join([f"{q.id}{refs}. {q.text}{mark}"] + [f"   {d}" for d in q.details]))
    parts = [f"Вопросы по задаче {state.get('task', '?')}"] + blocks
    if audience == "PO":
        parts.append(f"Пожалуйста, отвечайте с номером вопроса, например: «{open_questions[0].id}: …».")
    return "\n\n".join(parts)


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or argv[0] != "export":
        print("использование: sa_questions.py export <папка задачи> [PO|SA]", file=sys.stderr)
        return 2
    audience = argv[2] if len(argv) == 3 else "PO"
    try:
        print(export_questions(Path(argv[1]), audience))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest tests/test_sa_questions.py tests/test_sa_artifacts.py -v`
Expected: все тесты проходят (6 в `test_sa_questions.py`, плюс новый в `test_sa_artifacts.py`).

- [ ] **Step 6: Полный прогон и commit**

Run: `.venv/bin/pytest -q` — всё проходит.

```bash
git add scripts/sa_artifacts.py scripts/sa_questions.py tests/test_sa_artifacts.py tests/test_sa_questions.py
git commit -m "feat: export open questions for PO/analyst (sa_questions.py)"
```

---

### Task 3: Схема и проверка `context.md`

**Files:**
- Modify: `scripts/sa_validate.py` (константы, `validate_context`, `validate_task`)
- Modify: `shared/schemas/artifacts.md` (новый раздел перед `## questions.md`)
- Modify: `tests/fixtures/LKP-DEMO/context.md` (переписать под схему)
- Test: `tests/test_sa_validate.py`, `tests/test_shared_docs.py`

**Interfaces:**
- Consumes: `find_refs`, `find_table`, `parse_tables`, `ref_prefix`, `split_frontmatter` из `sa_artifacts`; `TEMPLATE_RE` из `sa_state`; внутренние `_unknown`, `_duplicates`, `_one_of`, `_run`, `EMPTY` из `sa_validate`.
- Produces:
  - `CONTEXT_COLUMNS = ["← IM", "Скоуп", "Комментарий"]`
  - `SCOPES = {"в скоупе", "вне скоупа", "?"}`
  - `CONTEXT_SECTIONS = ["## Цель", "## Границы"]`
  - `validate_context(text: str, known: dict, template: str | None) -> tuple[list[str], None]`
  - `validate_task` проверяет `context.md`, если он есть, сверяя `template` с `state.json`.

- [ ] **Step 1: Переписать фикстуру**

`tests/fixtures/LKP-DEMO/context.md`:

```markdown
---
template: feature@1.0
release: 2026-11
po: Продакт партнёрского направления
---
# Контекст

## Цель

Запретить партнёру указывать собственный промокод в клиентской анкете, чтобы вознаграждения не начислялись за собственные транзакции.

## Границы

| ← IM  | Скоуп    | Комментарий            |
|-------|----------|------------------------|
| IM-01 | в скоупе | —                      |
| IM-02 | в скоупе | —                      |
| IM-03 | в скоупе | —                      |
| IM-04 | ?        | ждём ответа на Q-SA-01 |

## Ограничения

- Пересчёт уже начисленных вознаграждений не делаем (D-01).

## Допущения

- ИНН в анкете заполнен к моменту ввода промокода (R-01).

## Ссылки

- jira: LKP-DEMO
```

- [ ] **Step 2: Написать падающие тесты**

Добавить в конец `tests/test_sa_validate.py`:

```python
def test_context_out_of_scope_needs_reason(task_dir):
    _edit(task_dir / "context.md", "| IM-03 | в скоупе | —                      |", "| IM-03 | вне скоупа | — |")
    assert "context.md: IM-03: для «вне скоупа» нужна причина в колонке Комментарий" in validate_task(task_dir)


def test_context_every_impact_row_listed(task_dir):
    _edit(task_dir / "context.md", "| IM-04 | ?        | ждём ответа на Q-SA-01 |\n", "")
    assert "context.md: IM-04: пункт карты влияния не распределён в «Границах»" in validate_task(task_dir)


def test_context_unknown_im_and_bad_scope(task_dir):
    _edit(task_dir / "context.md", "| IM-04 | ?        |", "| IM-09 | может    |")
    errors = validate_task(task_dir)
    assert "context.md: IM-09: ссылка на несуществующий IM-09" in errors
    assert any(e.startswith("context.md: IM-09: скоуп «может»") for e in errors)


def test_context_template_must_match_state(task_dir):
    _edit(task_dir / "context.md", "template: feature@1.0", "template: integration@1.0")
    assert "context.md: template integration@1.0 не совпадает с state.json (feature@1.0)" in validate_task(task_dir)


def test_context_required_sections_and_keys(task_dir):
    _edit(task_dir / "context.md", "## Цель", "## Зачем")
    _edit(task_dir / "context.md", "release: 2026-11\n", "")
    errors = validate_task(task_dir)
    assert "context.md: нет раздела «## Цель»" in errors
    assert "context.md: во frontmatter нет ключа release" in errors
```

Добавить в `tests/test_shared_docs.py`:
- в импорт из `sa_validate` — `CONTEXT_COLUMNS, SCOPES`;
- в `REQUIRED_HEADINGS["shared/schemas/artifacts.md"]` — элемент `"## context.md"`;
- в конец файла:

```python
def test_schema_doc_describes_context():
    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    for column in CONTEXT_COLUMNS:
        assert f"| {column} |" in text, f"колонка {column} не описана"
    for value in SCOPES:
        assert f"`{value}`" in text, f"скоуп {value} не описан"
    for name in ("`feature`", "`integration`"):
        assert name in text, name
```

- [ ] **Step 3: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_sa_validate.py tests/test_shared_docs.py -v`
Expected: FAIL — `ImportError: cannot import name 'CONTEXT_COLUMNS'` в `test_shared_docs.py`; новые тесты `context` в `test_sa_validate.py` падают (валидатор не проверяет `context.md`).

- [ ] **Step 4: Реализовать проверку**

В `scripts/sa_validate.py` после `DECISION_COLUMNS` добавить:

```python
CONTEXT_COLUMNS = ["← IM", "Скоуп", "Комментарий"]
SCOPES = {"в скоупе", "вне скоупа", "?"}
CONTEXT_SECTIONS = ["## Цель", "## Границы"]
```

Перед `def _is_sha1` добавить функцию:

```python
def validate_context(text: str, known: dict, template: str | None) -> tuple[list[str], None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    value = meta.get("template")
    if not (isinstance(value, str) and TEMPLATE_RE.fullmatch(value)):
        errors.append("template: формат имя@мажор.минор, например feature@1.0")
    elif template is not None and value != template:
        errors.append(f"template {value} не совпадает с state.json ({template})")
    for key in ("release", "po"):
        if meta.get(key) in (None, ""):
            errors.append(f"во frontmatter нет ключа {key}")
    lines = {line.strip() for line in body.splitlines()}
    errors += [f"нет раздела «{section}»" for section in CONTEXT_SECTIONS if section not in lines]
    table = find_table(parse_tables(body), CONTEXT_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(CONTEXT_COLUMNS)}"], None
    listed: list[str] = []
    for row in table.rows:
        refs = [r for r in find_refs(row["← IM"]) if ref_prefix(r) == "IM"]
        if len(refs) != 1:
            errors.append(f"«{row['← IM']}»: в колонке ← IM нужен ровно один IM-xx")
            continue
        rid = refs[0]
        listed.append(rid)
        if row["Скоуп"] not in SCOPES:
            errors.append(f"{rid}: скоуп «{row['Скоуп']}» не из списка: {_one_of(SCOPES)}")
        if row["Скоуп"] == "вне скоупа" and row["Комментарий"] in EMPTY:
            errors.append(f"{rid}: для «вне скоупа» нужна причина в колонке Комментарий")
        errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown([rid], known)]
    errors += [f"{d}: IM повторяется в «Границах»" for d in _duplicates(listed)]
    if known.get("IM") is not None:
        missing = sorted(known["IM"] - set(listed))
        errors += [f"{m}: пункт карты влияния не распределён в «Границах»" for m in missing]
    return errors, None
```

В `validate_task` после строки с `known["IM"] = …` добавить:

```python
    template = state.get("template") if isinstance(state.get("template"), str) else None
    _run(task_dir, "context", lambda t: validate_context(t, known, template), errors)
```

- [ ] **Step 5: Описать схему**

В `shared/schemas/artifacts.md` перед строкой `## questions.md` вставить раздел:

````markdown
## context.md

Контекст-пакет стадии `/tdd-start`. Шапка: `template` (тип ТЗ и версия шаблона, совпадает с `state.json`), `release` (релиз или срок), `po` (кто PO).

Типы ТЗ: `feature` — доработка существующих сервисов; `integration` — подключение внешней системы или платёжного метода. Версия шаблона — `1.0`, пока манифесты шаблонов не заведены.

Обязательные разделы: `## Цель` (1–3 предложения: что и зачем) и `## Границы` (таблица ниже). Необязательные: `## Ограничения`, `## Допущения`, `## Ссылки` — пункты списком, каждый со ссылкой на `R-xx`, `IM-xx` или `D-xx`, где это применимо.

| Колонка | Значение |
|---|---|
| ← IM | Ровно один `IM-xx` из карты влияния |
| Скоуп | `в скоупе`, `вне скоупа`, `?` |
| Комментарий | Причина для `вне скоупа` (обязательна); для `?` — ID вопроса, который это решит; иначе `—` |

- Каждый `IM-xx` из `impact-map.md` встречается в «Границах» ровно один раз.
- `?` — скоуп не решён: на такой пункт должен быть открытый вопрос.

````

- [ ] **Step 6: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest -q`
Expected: всё проходит, включая `test_demo_task_is_valid` с новой фикстурой.

- [ ] **Step 7: Commit**

```bash
git add scripts/sa_validate.py shared/schemas/artifacts.md tests/fixtures/LKP-DEMO/context.md tests/test_sa_validate.py tests/test_shared_docs.py
git commit -m "feat: context.md schema and validation"
```

---

### Task 4: Субагент `source-reader` и проверка ссылок на файлы плагина

**Files:**
- Create: `agents/source-reader.md`
- Modify: `tests/test_plugin_structure.py`

**Interfaces:**
- Consumes: `KINDS`, `IMPACTS`, `IM_STATUSES`, `CONFIDENCE` из `sa_validate`.
- Produces:
  - Субагент `sa-skills:source-reader`. Вход (в тексте задания): путь к репозиторию, требования `R-xx` с текстом, объекты-кандидаты, потолок уверенности. Выход: markdown-таблица с колонками `Объект | Вид | Влияние | ← R | Источник | Статус | Уверенность` (без колонки ID) и до 5 строк заметок.
  - Тесты `test_every_agent_has_frontmatter`, `test_source_reader_value_lists`, `test_plugin_file_references_exist` — последний проверяет все скилы и агенты, включая будущие.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_plugin_structure.py` (импорт `re` — в начало файла):

```python
import re

from sa_validate import CONFIDENCE, IM_STATUSES, IMPACTS, KINDS

PLUGIN_REF = re.compile(r"(?:<плагин>|<база>/\.\./\.\.)/((?:scripts|shared)/[A-Za-z0-9_./-]*[A-Za-z0-9_])")


def test_every_agent_has_frontmatter():
    agents = sorted((ROOT / "agents").glob("*.md"))
    assert agents, "нет ни одного агента"
    for agent_md in agents:
        meta = _frontmatter(agent_md.read_text(encoding="utf-8"))
        assert meta.get("name") == agent_md.stem, agent_md
        assert meta.get("description"), f"{agent_md}: пустой description"
        assert meta.get("tools"), f"{agent_md}: не указаны tools"


def test_source_reader_value_lists():
    text = (ROOT / "agents/source-reader.md").read_text(encoding="utf-8")
    for value in KINDS | IMPACTS | IM_STATUSES | CONFIDENCE:
        assert f"`{value}`" in text, f"значение {value} не перечислено"


def test_plugin_file_references_exist():
    docs = sorted((ROOT / "skills").glob("*/SKILL.md")) + sorted((ROOT / "agents").glob("*.md"))
    for doc in docs:
        for rel in PLUGIN_REF.findall(doc.read_text(encoding="utf-8")):
            assert (ROOT / rel).exists(), f"{doc.relative_to(ROOT)}: нет файла {rel}"
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `.venv/bin/pytest tests/test_plugin_structure.py -v`
Expected: FAIL — `test_every_agent_has_frontmatter` («нет ни одного агента») и `test_source_reader_value_lists` (`FileNotFoundError`); `test_plugin_file_references_exist` проходит на `tdd-status`.

- [ ] **Step 3: Написать агента**

`agents/source-reader.md`:

```markdown
---
name: source-reader
description: Читает один репозиторий сервиса (код и docs/) и возвращает строки карты влияния по заданным требованиям — с источником файл:строка и уверенностью, без сырого кода. Вызывается стадиями пайплайна ТЗ, например /tdd-impact.
tools: Read, Grep, Glob, Bash
model: sonnet
---

Ты — исследователь кода для системного аналитика. Работаешь в одном репозитории и только читаешь.

## Вход

В задании тебе передают:
- путь к репозиторию сервиса;
- требования `R-xx` с текстом, которые могут касаться этого сервиса;
- объекты-кандидаты из индекса системы, если они есть;
- потолок уверенности (`высокая` или `средняя`).

## Как искать

1. Начни с `docs/tech.md`, `docs/DB.md`, `docs/bctc.md` репозитория, если они есть: найди grep-ом ключевые слова требований.
2. Проверь кандидатов в коде: маршруты, контроллеры и обработчики, правила валидации, модели и миграции, продюсеры и консьюмеры Kafka, конфиги. Ищи Grep и Glob, читай файлы фрагментами, не целиком.
3. Бюджет — около 30 чтений файлов. Не нашёл — так и напиши в заметках, не угадывай.
4. Только чтение: не меняй файлы, не делай `git checkout`, `pull`, `commit`.

## Что вернуть

Только таблицу и до 5 строк заметок. ID не ставь — их назначит стадия.

| Объект | Вид | Влияние | ← R | Источник | Статус | Уверенность |
|---|---|---|---|---|---|---|

- Объект: `<сервис>: <что именно>` — метод, правило, модуль, таблица, топик, экран.
- Вид: `процесс`, `сервис`, `модуль`, `API`, `Kafka`, `БД`, `роль`, `UI`, `конфиг`.
- Влияние: `новый`, `изм.`, `удал.`, `?`.
- ← R: один или несколько `R-xx` через запятую.
- Источник: `code: <репо>/<путь>:<строка>` или `docs: <репо>/docs/<файл>#<раздел>`; `—`, если источника нет.
- Статус: `факт` — есть источник; `допущение` — нет источника или вывод косвенный.
- Уверенность: `высокая`, `средняя`, `низкая`. Не выше потолка. Вывод только по `docs/` или по имени файла — не выше `средняя`.
- Одна строка — один объект. Не цитируй код, максимум одна строка кода в заметках.

Заметки: что искал и не нашёл; смежное влияние, которое не следует из переданных требований, — одной строкой каждое, без строк в таблице.
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest -q`
Expected: всё проходит.

- [ ] **Step 5: Commit**

```bash
git add agents/source-reader.md tests/test_plugin_structure.py
git commit -m "feat: source-reader subagent and plugin reference checks"
```

---

### Task 5: Скил `/tdd-impact`

**Files:**
- Create: `skills/tdd-impact/SKILL.md`
- Create: `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: `sa_state.py init|set|record`, `sa_ids.py next`, `sa_validate.py`, `sa_questions.py export`, агент `sa-skills:source-reader`, `shared/rules/{ai-rules,brd-checklist,question-routing}.md`, `shared/access/adapters.md`, `shared/schemas/artifacts.md`.
- Produces: артефакты `tasks/<KEY>/state.json`, `sources/BRD.md`, `impact-map.md` (если BRD полный), `questions.md`; `stage = impact`; хэш `BRD` в `inputs`.

- [ ] **Step 1: Написать падающий тест контракта**

`tests/test_skills_contract.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _assert_contains(text: str, fragments: tuple[str, ...]) -> None:
    missing = [f for f in fragments if f not in text]
    assert not missing, f"нет фрагментов: {missing}"


def test_tdd_impact_contract():
    _assert_contains(
        _skill("tdd-impact"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_state.py init tasks/<KEY> <KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> BRD",
            "sa_state.py set tasks/<KEY> stage impact",
            "sa_questions.py export tasks/<KEY> PO",
            "sa-skills:source-reader",
            "brd-checklist.md",
            "question-routing.md",
            "adapters.md",
            "[BRD]",
            "SA_SYSTEM_DOCS",
        ),
    )
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `.venv/bin/pytest tests/test_skills_contract.py -v`
Expected: FAIL — `FileNotFoundError` для `skills/tdd-impact/SKILL.md`.

- [ ] **Step 3: Написать скил**

`skills/tdd-impact/SKILL.md`:

````markdown
---
name: tdd-impact
description: Стадия 1 пайплайна ТЗ — по ссылке на BRD в Jira или Confluence (или по файлу) проверяет полноту BRD и строит карту влияния на сервисы, у каждого пункта источник и уверенность; при неполном BRD останавливается и выдаёт вопросы PO. Используй, когда аналитик начинает новую задачу, просит карту влияния или пишет /tdd-impact.
allowed-tools: Bash(python3:*)
---

# /tdd-impact <ссылка или путь к файлу> [KEY]

Строит `tasks/<KEY>/`: `state.json`, `sources/BRD.md`, `impact-map.md`, `questions.md`.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/rules/ai-rules.md`, `<плагин>/shared/access/adapters.md` и в `<плагин>/shared/schemas/artifacts.md` разделы sources/BRD.md, impact-map.md, questions.md. Остальные справочники — только на шаге, который на них ссылается.

## Шаги

1. **Ключ задачи.** Второй аргумент — это ключ. Иначе возьми ключ Jira из ссылки (`[A-Z][A-Z0-9]+-[0-9]+`). Иначе спроси у аналитика ключ задачи и дальше не иди.
2. **Папка.** Если нет `tasks/<KEY>/state.json`: `python3 <плагин>/scripts/sa_state.py init tasks/<KEY> <KEY>`. Если есть — это повторный запуск (обычно после ответов PO на неполный BRD): переиспользуй существующие ID и не дублируй строки.
3. **BRD.** Получи текст по `adapters.md`: режим из `state.json`, иначе по порядку `mcp` → `cli` → `manual`. Путь к локальному файлу — это `manual`: прочитай файл. Запиши режим: `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> access.jira <режим>` (или `access.confluence`). Связанные страницы читай, только если без них непонятны требования.
4. **Нормализация.** Запиши `sources/BRD.md` по схеме: шапка (`source` — ссылка или `manual`, `fetched` — сегодня), таблица требований. Одна строка — одно проверяемое требование; сжимай без потери условий, чисел и исключений. Тип — из списка схемы. Новые ID: `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> R <количество>`; при повторном запуске старые `R-xx` не перенумеровывай.
5. **Полнота.** Пройди `<плагин>/shared/rules/brd-checklist.md`. Не хватает обязательного пункта →
   - `brd_complete: false` и `missing: [...]` короткими названиями;
   - на каждый пункт — вопрос PO со ссылкой `[BRD]` в секции `## Для PO` файла `questions.md` по `<плагин>/shared/rules/question-routing.md`, ID через `sa_ids.py next tasks/<KEY> Q-PO`, статус `— *open, blocking*`;
   - переходи сразу к шагу 9, карту не строй.
   
   При повторном запуске вопросы `[BRD]`, которые закрыл обновлённый BRD, переведи в `— *answered*`.
6. **Кандидаты.** Индекс системы — `${SA_SYSTEM_DOCS:-${SA_REPOS_ROOT:-$HOME/repos}/system-docs}/docs/`: `bctc.md` (сценарии → сервисы), `system_tech.md` (API и Kafka). Ищи grep-ом по ключевым словам требований, файлы целиком не читай. Итог — список сервисов-кандидатов и объектов в них. Индекса нет → `index_used: false`, `confidence_cap: средняя`, кандидаты — по репозиториям в `${SA_REPOS_ROOT:-$HOME/repos}` и поиску по ключевым словам. Сервисы, которые ни одно требование не затрагивает, отбрасывай.
7. **Проверка в коде.** Для каждого сервиса-кандидата запусти субагента `sa-skills:source-reader` (инструмент Agent), всех — в одном сообщении, параллельно. В задании передай: путь к репозиторию, требования `R-xx` с текстом, которые касаются сервиса, объекты-кандидаты, потолок уверенности (`confidence_cap`). Сам код не читай: работай с таблицами, которые вернули субагенты.
8. **Карта.** Собери `impact-map.md`:
   - строки субагентов;
   - объекты, которые следуют из BRD без кода (новый метод, роль, процесс), — статус `факт`, источник `BRD R-xx`;
   - дубли объединяй; уверенность не выше `confidence_cap`;
   - ID: `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> IM <количество>`.
   
   Каждое `допущение` с уверенностью `низкая` → вопрос аналитику (`Q-SA`, секция `## Для аналитика`, ссылка `[IM-xx]`, где проверить). Бизнес-неясности BRD → `Q-PO` со ссылкой `[R-xx]`. Маршрутизация — по `question-routing.md`.
9. **Проверка.** `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>` — исправляй артефакты, пока не будет `OK`. Затем:
   - `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> BRD`
   - `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage impact`
10. **Итог аналитику**, коротко:
    - BRD полный или неполный (чего не хватает);
    - карта: сколько объектов, сколько допущений, затронутые сервисы списком;
    - блок для PO — вывод `python3 <плагин>/scripts/sa_questions.py export tasks/<KEY> PO` как есть, в блоке кода;
    - открытые вопросы аналитику — ID и одна строка;
    - следующий шаг: `/tdd-start`, а при неполном BRD — переслать вопросы PO и после ответов запустить `/tdd-impact` повторно.

## Чего не делать

- Не читай код и большие страницы в свой контекст — для этого `source-reader`.
- Не выдумывай объекты и источники; нет источника — `допущение`.
- Не задавай PO технических вопросов.
- Не меняй файлы в репозиториях сервисов.
````

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest -q`
Expected: всё проходит, включая `test_tdd_impact_contract`, `test_every_skill_has_valid_frontmatter`, `test_plugin_file_references_exist`.

- [ ] **Step 5: Commit**

```bash
git add skills/tdd-impact tests/test_skills_contract.py
git commit -m "feat: /tdd-impact skill"
```

---

### Task 6: Скил `/tdd-start`

**Files:**
- Create: `skills/tdd-start/SKILL.md`
- Modify: `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: `sa_status.py`, `sa_ids.py next`, `sa_validate.py`, `sa_state.py set|record`, `sa_questions.py export`, `shared/rules/{ai-rules,question-routing}.md`, `shared/schemas/artifacts.md` (раздел context.md); артефакты `state.json`, `impact-map.md`.
- Produces: `context.md`, новые вопросы в `questions.md`; `template` и `stage = start` в `state.json`; хэш `impact-map` в `inputs`.

- [ ] **Step 1: Написать падающий тест контракта**

Добавить в конец `tests/test_skills_contract.py`:

```python
def test_tdd_start_contract():
    _assert_contains(
        _skill("tdd-start"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_status.py tasks/<KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_state.py set tasks/<KEY> template",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> impact-map",
            "sa_state.py set tasks/<KEY> stage start",
            "sa_questions.py export tasks/<KEY> PO",
            "question-routing.md",
            "`feature`",
            "`integration`",
        ),
    )
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `.venv/bin/pytest tests/test_skills_contract.py -v`
Expected: FAIL — `FileNotFoundError` для `skills/tdd-start/SKILL.md`.

- [ ] **Step 3: Написать скил**

`skills/tdd-start/SKILL.md`:

````markdown
---
name: tdd-start
description: Стадия 2 пайплайна ТЗ — по формулировке аналитика собирает контекст-пакет context.md — цель, тип ТЗ, релиз, PO, границы скоупа по каждому пункту карты влияния, ограничения, допущения и ссылки. Используй после /tdd-impact, когда аналитик описывает, что и в каких границах делаем, или пишет /tdd-start.
allowed-tools: Bash(python3:*)
---

# /tdd-start [KEY] <формулировка>

Входы: `state.json`, `impact-map.md`, формулировка аналитика. Выход: `context.md` и, если нужно, новые вопросы в `questions.md`.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/rules/ai-rules.md` и в `<плагин>/shared/schemas/artifacts.md` разделы context.md и questions.md. Не читай `sources/` и код.

## Шаги

1. **Папка задачи.** Первый аргумент похож на ключ (`[A-Z][A-Z0-9]+-[0-9]+`) — `tasks/<KEY>`. Иначе: единственная задача в `tasks/` — она; несколько — спроси какую.
2. **Готовность.** `python3 <плагин>/scripts/sa_status.py tasks/<KEY>`. BRD неполный, нет `impact-map.md` или в «Устаревших входах» есть `BRD` — скажи об этом и предложи сначала `/tdd-impact`. Продолжай, только если аналитик подтвердит.
3. **Формулировка.** Возьми из неё цель, релиз, PO, ограничения, ссылки на артефакты. Чего не хватает из цели, релиза и PO — спроси одним сообщением списком и дождись ответа; не выдумывай.
4. **Тип ТЗ.** `feature` — доработка существующих сервисов; `integration` — подключение внешней системы или платёжного метода. Не очевидно — спроси. Версия `1.0`: `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> template feature@1.0` (или `integration@1.0`).
5. **Границы.** Прочитай `impact-map.md` и каждую строку отнеси к `в скоупе`, `вне скоупа` (с причиной в Комментарии) или `?`, если из формулировки это не следует. На каждый `?` заведи вопрос по `<плагин>/shared/rules/question-routing.md`: решение о скоупе для бизнеса — `Q-PO` (`[R-xx]`), техническая неясность — `Q-SA` (`[IM-xx]`). ID — `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> Q-PO` (или `Q-SA`). В Комментарий строки `?` впиши ID вопроса.
6. **Противоречия.** Формулировка противоречит BRD или карте (например, `вне скоупа` для объекта, без которого не выполнить `R-xx`) — заведи вопрос со ссылкой на `R-xx` или `IM-xx`, статус `— *open, blocking*`.
7. **Запись.** `context.md` по схеме. Допущения и ограничения — пунктами, со ссылками на `R-xx`, `IM-xx`, `D-xx`, где применимо.
8. **Проверка.** `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>` — исправляй, пока не `OK`. Затем:
   - `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> impact-map`
   - `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage start`
9. **Итог аналитику**, коротко: цель одной строкой; тип ТЗ; в скоупе N, вне скоупа M, не решено K; новые вопросы — ID и строка; блок для PO — вывод `python3 <плагин>/scripts/sa_questions.py export tasks/<KEY> PO`, если есть открытые вопросы PO; следующий шаг — `/tdd-clarify`.

## Чего не делать

- Не перечитывай BRD и код: стадия работает только с картой влияния и формулировкой.
- Не решай скоуп за PO: неочевидное — `?` и вопрос.
````

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest -q`
Expected: всё проходит.

- [ ] **Step 5: Commit**

```bash
git add skills/tdd-start tests/test_skills_contract.py
git commit -m "feat: /tdd-start skill"
```

---

### Task 7: Скил `/tdd-clarify`

**Files:**
- Create: `skills/tdd-clarify/SKILL.md`
- Modify: `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: `sa_ids.py next`, `sa_validate.py`, `sa_state.py set|record`, `sa_questions.py export` (PO и SA), `shared/rules/{ai-rules,question-routing}.md`, `shared/access/adapters.md`, `shared/schemas/artifacts.md`; артефакты `questions.md`, `decisions.md`, `context.md`, строки `sources/BRD.md` и `impact-map.md` по ID.
- Produces: обновлённые `questions.md`, `decisions.md`, при необходимости `sources/<имя>.md`; `stage = clarify`; хэш `context` в `inputs`.

- [ ] **Step 1: Написать падающий тест контракта**

Добавить в конец `tests/test_skills_contract.py`:

```python
def test_tdd_clarify_contract():
    _assert_contains(
        _skill("tdd-clarify"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_status.py tasks/<KEY>",
            "sa_ids.py next tasks/<KEY> D",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> context",
            "sa_state.py set tasks/<KEY> stage clarify",
            "sa_questions.py export tasks/<KEY> PO",
            "sa_questions.py export tasks/<KEY> SA",
            "question-routing.md",
            "*obsolete*",
            "*open, blocking*",
            "*answered*",
        ),
    )
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `.venv/bin/pytest tests/test_skills_contract.py -v`
Expected: FAIL — `FileNotFoundError` для `skills/tdd-clarify/SKILL.md`.

- [ ] **Step 3: Написать скил**

`skills/tdd-clarify/SKILL.md`:

````markdown
---
name: tdd-clarify
description: Стадия 3 пайплайна ТЗ, повторяемая — принимает ответы PO и аналитика, описание целевого поведения и ссылки; ведёт журнал решений decisions.md, закрывает и заводит вопросы, ищет неоднозначности, противоречия и пропуски; выдаёт готовый блок вопросов для PO. Используй, когда пришли ответы на вопросы, аналитик уточняет поведение, спрашивает, всё ли ясно для черновика, или пишет /tdd-clarify.
allowed-tools: Bash(python3:*)
---

# /tdd-clarify [KEY] <ответы | целевое поведение | ссылки>

Входы: `questions.md`, `decisions.md`, `context.md`, ввод аналитика. Из `sources/BRD.md` и `impact-map.md` — только строки нужных `R-xx` и `IM-xx` (grep по ID), файлы целиком не читай. Выход: `questions.md`, `decisions.md`.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/rules/ai-rules.md`, `<плагин>/shared/rules/question-routing.md` и в `<плагин>/shared/schemas/artifacts.md` разделы questions.md и decisions.md.

## Шаги

1. **Папка задачи.** Первый аргумент похож на ключ — `tasks/<KEY>`; иначе единственная задача в `tasks/`, при нескольких — спроси. `python3 <плагин>/scripts/sa_status.py tasks/<KEY>`: стадия должна быть `start` или `clarify`, иначе скажи, какую стадию запустить сначала, и остановись. В «Устаревших входах» есть `context` или `impact-map` — предупреди, что контекст или карта менялись после прошлого уточнения, и учитывай их новую версию в анализе.
2. **Разбор ввода.**
   - Ответ с ID («Q-PO-02: …») — сопоставь напрямую. Без ID — по смыслу; если ответ подходит к нескольким вопросам или ни к одному, перечисли варианты и спроси.
   - Описание целевого поведения — решения аналитика: каждое отдельное правило — своё решение с `← Q` = `—` и «Кто/где» = «аналитик».
   - Ссылки — прочитай по `<плагин>/shared/access/adapters.md` только нужное, выжимку сохрани в `sources/<короткое-имя>.md`.
3. **Решения.** На каждый ответ — строка в `decisions.md`: ID через `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> D`, дата — сегодня (ГГГГ-ММ-ДД), «Кто/где» — со слов аналитика («PO, чат ММ»), без источника — «аналитик». Вопрос, на который ответ полный, — статус `— *answered*`. Ответ частичный — вопрос остаётся открытым, недостающее заведи новым вопросом со ссылкой на старый в тексте.
4. **Анализ.** Только по `decisions.md`, `context.md` и нужным строкам BRD:
   - противоречия: решение против решения, решение против `R-xx`, решение против «Границ» `context.md`;
   - пропуски: требования из скоупа, у которых не определено поведение в исключениях — ошибка, недоступность смежного сервиса, пустое значение, повторный запрос, нет прав;
   - неоднозначности: формулировки, допускающие два прочтения.
   
   Каждое — новый вопрос по `question-routing.md` со ссылкой на `R-xx` или `IM-xx`; ID через `sa_ids.py next tasks/<KEY> Q-PO` или `Q-SA`. Вопрос влияет на поведение для пользователя или на контракт между сервисами — `— *open, blocking*`, иначе `— *open*`. Вопрос, который решение сделало неактуальным, — `— *obsolete*`.
5. **Проверка.** `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>` — исправляй, пока не `OK`. Затем:
   - `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> context`
   - `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage clarify`
6. **Итог аналитику**, коротко:
   - «Закрыто N, новых M, открытых блокирующих K»;
   - противоречия — по одной строке со ссылками;
   - блок для PO — вывод `python3 <плагин>/scripts/sa_questions.py export tasks/<KEY> PO` как есть, в блоке кода;
   - вопросы аналитику — вывод `python3 <плагин>/scripts/sa_questions.py export tasks/<KEY> SA`;
   - следующий шаг: блокирующих 0 — `/tdd-draft`; иначе переслать вопросы и вернуться с ответами в `/tdd-clarify`.

## Чего не делать

- Не отвечай на вопросы за PO и не записывай догадки как решения.
- Не меняй и не удаляй прежние решения: новое решение, отменяющее старое, — новая строка со ссылкой на старый `D-xx` в тексте.
- Не перечитывай BRD и карту целиком.
````

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `.venv/bin/pytest -q`
Expected: всё проходит.

- [ ] **Step 5: Commit**

```bash
git add skills/tdd-clarify tests/test_skills_contract.py
git commit -m "feat: /tdd-clarify skill"
```

---

### Task 8: Сквозная проверка, документация доступа и README

**Files:**
- Create: `tests/fixtures/e2e/brd-promo.md`, `tests/fixtures/e2e/brd-incomplete.md`
- Create: мини-репозитории в `tests/fixtures/e2e/repos/` (список ниже)
- Modify: `shared/access/adapters.md`, `README.md`

**Interfaces:**
- Consumes: всё из задач 1–7.
- Produces: воспроизводимый сценарий сквозной проверки трёх стадий в Claude Code.

- [ ] **Step 1: Создать BRD для проверки**

`tests/fixtures/e2e/brd-promo.md`:

```markdown
# BRD: запрет собственного промокода в клиентской анкете

## Цель

Партнёры указывают собственный промокод при регистрации клиентской анкеты и получают вознаграждение за свои же транзакции. Нужно закрыть эту возможность.

## Пользователи

- Мерчант — заполняет клиентскую анкету.
- Партнёр — владелец промокода.
- Сотрудник клиентского сервиса — ведёт анкеты в админке.

## Требования

1. Если владелец промокода и заявитель — одно лицо (совпадает ИНН или пара почта + телефон), анкета с таким промокодом не отправляется.
2. Мерчант видит под полем промокода понятную причину отказа.
3. Если проверить промокод не удалось, регистрация не блокируется, а сотрудник клиентского сервиса видит отметку в карточке анкеты.

## Не входит

- Пересчёт уже начисленных вознаграждений.

## Критерии успеха

- Анкету с собственным промокодом нельзя отправить ни мерчанту, ни через админку.
```

`tests/fixtures/e2e/brd-incomplete.md`:

```markdown
# BRD: промокоды в анкете

Сделать проверку промокода в анкете удобнее.
```

- [ ] **Step 2: Создать мини-репозитории**

`tests/fixtures/e2e/repos/system-docs/docs/bctc.md`:

```markdown
# Сценарии и сервисы

| Сценарий | Домен | Сервисы |
|---|---|---|
| Регистрация мерчанта по клиентской анкете | Анкета | lkp-front, lkp-back, partners-dashboard, lk-payform |
| Регистрация партнёра по партнёрской анкете | Партнёрка | lkp-front, lkp-back, partners-dashboard |
| Начисление партнёрских вознаграждений | Партнёрка | partners-dashboard |
```

`tests/fixtures/e2e/repos/system-docs/docs/system_tech.md`:

```markdown
# API и Kafka

| Поставщик | Метод или топик | Потребители | Назначение |
|---|---|---|---|
| partners-dashboard | POST /api/promocode/check-availability | lkp-back | Проверка существования промокода |
| lkp-back | POST /api/questionnaire/promocode/check | lkp-front | Живая проверка промокода в анкете |
| lkp-back | Kafka: questionnaire.saved | lk-payform | Анкета сохранена |
```

`tests/fixtures/e2e/repos/lkp-back/docs/tech.md`:

```markdown
# lkp-back

## API

| Метод | Назначение | Код |
|---|---|---|
| POST /api/questionnaire/promocode/check | Живая проверка промокода по расфокусу поля | app/Http/Controllers/PromocodeController.php |

## Правила валидации

- Поле client_promocode: правило PromocodeRule (app/Rules/PromocodeRule.php) — формат и существование через partners-dashboard.

## Kafka

| Топик | Направление | Когда |
|---|---|---|
| questionnaire.saved | публикует | после сохранения анкеты |
```

`tests/fixtures/e2e/repos/lkp-back/app/Rules/PromocodeRule.php`:

```php
<?php

namespace App\Rules;

use App\Services\PartnersClient;

class PromocodeRule
{
    public function __construct(private PartnersClient $partners) {}

    public function passes(string $attribute, ?string $value): bool
    {
        if ($value === null || $value === '') {
            return true;
        }
        if (!preg_match('/^[A-Za-z0-9_]{1,25}$/', $value)) {
            return false;
        }
        // Проверяется только существование промокода
        return $this->partners->checkAvailability($value)['status'] === 'exists';
    }
}
```

`tests/fixtures/e2e/repos/lkp-back/app/Services/PartnersClient.php`:

```php
<?php

namespace App\Services;

class PartnersClient
{
    public function checkAvailability(string $promocode): array
    {
        return $this->post('/api/promocode/check-availability', ['promo_code' => $promocode]);
    }

    private function post(string $path, array $payload): array
    {
        // HTTP-вызов partners-dashboard с сервисным токеном
        return [];
    }
}
```

`tests/fixtures/e2e/repos/lkp-back/app/Http/Controllers/PromocodeController.php`:

```php
<?php

namespace App\Http\Controllers;

use App\Services\PartnersClient;

class PromocodeController
{
    public function check(PartnersClient $partners, array $request): array
    {
        $result = $partners->checkAvailability($request['promo_code']);
        return ['status' => $result['status'] ?? 'not_found'];
    }
}
```

`tests/fixtures/e2e/repos/partners-dashboard/docs/tech.md`:

```markdown
# partners-dashboard

## API

| Метод | Назначение | Код |
|---|---|---|
| POST /api/promocode/check-availability | Существует ли промокод | routes/api.php, app/Http/Controllers/PromocodeController.php |

## БД

| Таблица | Поля |
|---|---|
| partners | id, inn, owner_email, phone, id_in_platform, uuid_in_platform |
| partner_promocodes | promocode, partner_id |
```

`tests/fixtures/e2e/repos/partners-dashboard/routes/api.php`:

```php
<?php

use App\Http\Controllers\PromocodeController;

Route::middleware('check-intermediate-access-token')->group(function () {
    Route::post('/promocode/check-availability', [PromocodeController::class, 'checkAvailability']);
});
```

`tests/fixtures/e2e/repos/partners-dashboard/app/Http/Controllers/PromocodeController.php`:

```php
<?php

namespace App\Http\Controllers;

class PromocodeController
{
    public function checkAvailability(array $request): array
    {
        $code = strtoupper(trim($request['promocode'] ?? $request['promo_code'] ?? ''));
        $exists = \DB::table('partner_promocodes')->where('promocode', $code)->exists();
        return ['status' => $exists ? 'exists' : 'not_found'];
    }
}
```

`tests/fixtures/e2e/repos/lkp-front/src/hooks/useBlurValidation.ts`:

```ts
export async function validatePromocodeOnBlur(value: string): Promise<'exists' | 'not_found' | 'error'> {
  try {
    const res = await fetch('/api/questionnaire/promocode/check', {
      method: 'POST',
      body: JSON.stringify({ promo_code: value }),
    });
    const data = await res.json();
    return data.status;
  } catch {
    return 'error';
  }
}
```

`tests/fixtures/e2e/repos/lk-payform/docs/tech.md`:

```markdown
# lk-payform

Читает Kafka questionnaire.saved и создаёт профиль и домен в ПФ1. Промокод не использует.
```

- [ ] **Step 3: Дополнить `shared/access/adapters.md`**

В раздел `## Git` добавить пункт после пункта про `$SA_REPOS_ROOT`:

```markdown
- Индекс системы (`bctc.md`, `system_tech.md`) лежит в `${SA_SYSTEM_DOCS:-${SA_REPOS_ROOT:-$HOME/repos}/system-docs}/docs/`.
```

В раздел `## Ручной режим` добавить первым пунктом:

```markdown
- Если аналитик передал путь к локальному файлу (выгрузка BRD или страницы) — прочитай его, это ручной режим.
```

- [ ] **Step 4: Обновить README**

В `README.md` в таблице команд поменять статус `/tdd-impact`, `/tdd-start`, `/tdd-clarify` на `готово`. После таблицы команд добавить раздел:

````markdown
## Окружение

| Переменная | Зачем | По умолчанию |
|---|---|---|
| `SA_REPOS_ROOT` | Папка с локальными клонами репозиториев сервисов | `~/repos` |
| `SA_SYSTEM_DOCS` | Репозиторий с индексом системы (`docs/bctc.md`, `docs/system_tech.md`) | `$SA_REPOS_ROOT/system-docs` |
| `JIRA_BASE_URL`, `JIRA_TOKEN`, `JIRA_EMAIL` | Доступ к Jira без MCP | — |
| `CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN` | Доступ к Confluence без MCP | — |

## Сквозная проверка стадий

```bash
REPO=<путь к этому репозиторию>
mkdir -p /tmp/sa-e2e && cd /tmp/sa-e2e
export SA_REPOS_ROOT=$REPO/tests/fixtures/e2e/repos
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-impact $REPO/tests/fixtures/e2e/brd-promo.md PROMO-1"
python3 $REPO/scripts/sa_validate.py tasks/PROMO-1
```
````

- [ ] **Step 5: Прогнать тесты**

Run: `.venv/bin/pytest -q`
Expected: всё проходит (фикстуры e2e не участвуют в pytest).

- [ ] **Step 6: Сквозная проверка в Claude Code**

Выполнить по порядку, `REPO=/Users/waraxe.in/.superset/projects/SA-Skills`:

```bash
rm -rf /tmp/sa-e2e && mkdir -p /tmp/sa-e2e && cd /tmp/sa-e2e
export SA_REPOS_ROOT=$REPO/tests/fixtures/e2e/repos
TOOLS="Bash(python3:*) Read Write Edit Grep Glob Agent"

# 1. Полный BRD
claude --plugin-dir $REPO --model sonnet --allowedTools "$TOOLS" \
  -p "/tdd-impact $REPO/tests/fixtures/e2e/brd-promo.md PROMO-1"
python3 $REPO/scripts/sa_validate.py tasks/PROMO-1
grep -c "^| IM-" tasks/PROMO-1/impact-map.md
grep -E "partners-dashboard|lkp-back" tasks/PROMO-1/impact-map.md | head

# 2. Неполный BRD
claude --plugin-dir $REPO --model sonnet --allowedTools "$TOOLS" \
  -p "/tdd-impact $REPO/tests/fixtures/e2e/brd-incomplete.md PROMO-2"
python3 $REPO/scripts/sa_validate.py tasks/PROMO-2
grep "brd_complete" tasks/PROMO-2/sources/BRD.md
grep -c "\[BRD" tasks/PROMO-2/questions.md
ls tasks/PROMO-2/impact-map.md

# 3. Старт
claude --plugin-dir $REPO --model sonnet --allowedTools "$TOOLS" \
  -p "/tdd-start PROMO-1 Цель: запретить партнёру указывать собственный промокод в клиентской анкете. Релиз 2026-11, PO Иван Петров. Доработка существующих сервисов. Пересчёт начислений вне скоупа."
python3 $REPO/scripts/sa_validate.py tasks/PROMO-1
python3 $REPO/scripts/sa_status.py tasks/PROMO-1

# 4. Уточнение
claude --plugin-dir $REPO --model sonnet --allowedTools "$TOOLS" \
  -p "/tdd-clarify PROMO-1 Ответы PO на все открытые вопросы PO: отправку анкеты с собственным промокодом блокируем; текст ошибки «Вы указали собственный промокод. Укажите промокод партнёра или оставьте поле пустым»; уже начисленные вознаграждения не пересчитываем. Источник — чат ММ."
python3 $REPO/scripts/sa_validate.py tasks/PROMO-1
grep -c "^| D-" tasks/PROMO-1/decisions.md
python3 $REPO/scripts/sa_status.py tasks/PROMO-1
```

Expected:
1. `OK: tasks/PROMO-1`; в карте не меньше 3 строк `IM-`; есть строки по `partners-dashboard` и `lkp-back`; `lk-payform` в карте либо отсутствует, либо отмечен как `?`/`допущение`.
2. `OK: tasks/PROMO-2`; `brd_complete: false`; не меньше одного вопроса `[BRD`; `impact-map.md` нет (`ls` сообщает «No such file»).
3. `OK`; в сводке `стадия: start · шаблон: feature@1.0`, артефакт `context ✓`.
4. `OK`; не меньше одной строки `D-`; в сводке `стадия: clarify`.

Если какой-то шаг не дал ожидаемого, сохранить вывод `claude` и содержимое `tasks/` в отчёт и описать расхождение — не править скилы в этой задаче без согласования с контроллером. Временную папку после проверки удалить: `rm -rf /tmp/sa-e2e`.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/e2e shared/access/adapters.md README.md
git commit -m "test: e2e fixtures for impact/start/clarify; docs: env and access"
```
