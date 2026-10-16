# SA Skills — подпроект 4: /tdd-check и /tdd-update — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Стадия 5 пайплайна — `/tdd-check` (независимое ревью черновика в `review.md` с замечаниями `RV-xx` и матрицей покрытия) и `/tdd-update` (точечная перегенерация только затронутых секций, предложения diff для секций с правкой человека).

**Architecture:** Детерминированное — в stdlib-скриптах: `sa_review.py` (проходы 1–3 ревью: плейсхолдеры, покрытие R критериями приёмки, покрытие IM; матрица `R → секции/AC`; утверждения `[as is]` по сервисам; смена статуса замечаний), `sa_update.py` (что изменилось с последней сборки по снимку хэшей строк R/IM/D, какие секции затронуты по трассировке, предложения `proposals/<секция>.md`, diff/apply/drop). `sa_draft.py` получает явную отметку «секция записана моделью» (`mark`/`release`), чтобы отличать правку человека от несобранной перегенерации (долг I6 из SP3). Проходы 4–6 делает субагент `tdd-reviewer` (sonnet, только чтение) по `draft.md`, BRD, карте, решениям и чек-листам блоков; проход 7 (`--code`) — `source-reader` в новом режиме сверки. Валидатор проверяет `review.md`, включая совпадение матрицы покрытия с черновиком.

**Tech Stack:** Claude Code plugin (SKILL.md, agents), Python ≥ 3.10 (stdlib), pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-sa-skills-pipeline-design.md` (разделы 3, 4.5, 5.5, 6, 10, 12)

## Global Constraints

- Скрипты в `scripts/` — только стандартная библиотека Python ≥ 3.10.
- Все тексты для пользователя — на русском.
- Скилы ссылаются на файлы плагина как `<плагин>/scripts/…` и `<плагин>/shared/…`, где `<плагин>` = `<база>/../..`.
- Каждый SKILL.md имеет frontmatter `name`, `description` (≤ 1024 символов), `allowed-tools: Bash(python3:*)`.
- В skills/agents/shared нет `$VAR`/`${VAR}` (тест `test_no_shell_variables_in_prompts`); в Bash — одна команда без `;`, `&&`, `|`.
- Файлы задачи скилы пишут по абсолютному пути `<tasks_dir>/<KEY>/…` из `sa_paths.py`; в командах скриптов — `tasks/<KEY>`.
- Источник истины по форматам — `shared/schemas/artifacts.md`; валидатор проверяет ровно то, что там написано.
- Существующие фикстуры (`tests/fixtures/LKP-DEMO`, `tests/fixtures/e2e/*`) не менять; новые — рядом.
- Ревьюер `tdd-reviewer`: `model: sonnet`, инструменты только `Read, Grep, Glob`.
- Сверка с опубликованной страницей Confluence отложена (решение аналитика): фиксируем факт публикации и хэш `draft-publish.md`, `/tdd-update` предупреждает и не перепубликует без согласия. `/tdd-check <страница>` не поддерживается — ревьюится локальный `draft.md`.
- Версию плагина (`0.1.0`) не менять.

## Структура файлов

```
scripts/
  sa_state.py      # + write_atomic, PUBLISH_FILE, set published
  sa_draft.py      # + is_human, mark, release, row_hashes, section_texts, untraced_impacts, block_section, scope_of
  sa_review.py     # новый: precheck, coverage, asis, status, review_summary
  sa_update.py     # новый: plan, diff, apply, drop
  sa_validate.py   # + validate_review, state.rows/generated/published
  sa_ids.py        # + RV
  sa_status.py     # + строка «Ревью», следующий шаг на стадии check
agents/
  tdd-reviewer.md  # новый
  source-reader.md # + «Режим сверки»
skills/
  tdd-check/SKILL.md   # новый
  tdd-update/SKILL.md  # новый
  tdd-draft/SKILL.md   # mark после записи секции, published после публикации
shared/
  schemas/artifacts.md       # + review.md, proposals/, state.rows/generated/published
  rules/artifact-writing.md  # + /tdd-check, /tdd-update
tests/
  conftest.py                # + write_review
  test_sa_review.py  test_sa_update.py  test_e2e_fixture.py   # новые
  test_sa_draft.py  test_sa_validate.py  test_sa_state.py  test_sa_ids.py
  test_sa_status.py  test_shared_docs.py  test_skills_contract.py  test_plugin_structure.py
  fixtures/e2e/lkp-review/   # новый: make_task.py + draft/*.md с подложенными дефектами
README.md
```

---

### Task 1: Правка человека против перегенерации, снимок строк, атомарная сборка

Долг I6 из SP3: по одному хэшу нельзя отличить «модель переписала секцию, сборки ещё не было» от «человек правил», а прямой `assemble` после ручной правки терял флаг. Решение: модель после записи секции вызывает `sa_draft.py mark` — в `state.json` запоминается `sections.<id>.generated` (sha1 её текста). Секция считается правкой человека, если флаг уже стоит или её sha1 не равен ни `hash` последней сборки, ни `generated`. `assemble` вычисляет флаг так же. Заодно `assemble` пишет снимок `state.rows` (sha1 значимых колонок каждой строки R/IM/D) — по нему `/tdd-update` найдёт изменения.

**Files:**
- Modify: `scripts/sa_state.py` (write_atomic, PUBLISH_FILE)
- Modify: `scripts/sa_draft.py`
- Modify: `scripts/sa_validate.py` (validate_state)
- Modify: `skills/tdd-draft/SKILL.md`
- Modify: `shared/schemas/artifacts.md` (раздел «draft/ и draft.md», «state.json»)
- Test: `tests/test_sa_draft.py`, `tests/test_sa_validate.py`, `tests/test_skills_contract.py`

**Interfaces:**
- Produces:
  - `sa_state.write_atomic(path: Path, text: str) -> None`; `sa_state.PUBLISH_FILE = "draft-publish.md"` (в `sa_draft` — `from sa_state import PUBLISH_FILE`).
  - `sa_draft.is_human(entry: dict | None, path: Path) -> bool`
  - `sa_draft.mark(task_dir: Path, section_ids: list[str]) -> None` — отказ `ArtifactError("<id>: правка человека — …")`, если `edited_by_human` уже `true`.
  - `sa_draft.release(task_dir: Path, section_ids: list[str]) -> None` — снимает флаг (только по слову аналитика).
  - `sa_draft.row_hashes(task_dir: Path) -> dict[str, str]` — `{"R-01": sha1, "IM-01": sha1, "D-01": sha1, …}`.
  - `sa_draft.section_texts(task_dir: Path, manifest: Manifest) -> dict[str, str]` — существующие секции по порядку манифеста.
  - `sa_draft.untraced_impacts(data: dict, traced: set[str], scopes: tuple[str, ...] = ("в скоупе",)) -> list[str]`
  - `sa_draft.block_section(manifest: Manifest, block: str) -> str | None` — id первой секции с этим блоком.
  - `sa_draft.scope_of(data: dict, im_id: str) -> str` (бывший `_scope`).
  - CLI: `sa_draft.py mark <папка задачи> <секция>...`, `sa_draft.py release <папка задачи> <секция>...`.
  - `state.json`: `sections.<id>.generated` (необязательный sha1), `rows` (объект ID → sha1).

- [ ] **Step 1: Write the failing tests**

В конец `tests/test_sa_draft.py`:

```python
from sa_draft import is_human, mark, release, row_hashes


def _section_line(task_dir, sid):
    return next(line for line in plan(task_dir).splitlines() if line.startswith(f"{sid} |"))


def test_mark_keeps_regenerated_section_from_human_flag(draft_task):
    path = draft_task / "draft/04-scenarios.md"
    path.write_text("## Сценарии\n\nНовый текст ‹R-01›\n", encoding="utf-8")
    mark(draft_task, ["04-scenarios"])
    assert _section_line(draft_task, "04-scenarios").endswith("| есть")
    entry = load_state(draft_task)["sections"]["04-scenarios"]
    assert entry["generated"] == file_sha1(path) and entry["edited_by_human"] is False
    assemble(draft_task)
    assert load_state(draft_task)["sections"]["04-scenarios"] == {"hash": file_sha1(path), "edited_by_human": False}


def test_assemble_flags_unmarked_edit(draft_task):
    (draft_task / "draft/06-api.md").write_text("## API\n\nПравка аналитика ‹R-01›\n", encoding="utf-8")
    assemble(draft_task)
    assert load_state(draft_task)["sections"]["06-api"]["edited_by_human"] is True


def test_mark_refuses_human_section_and_release(draft_task):
    path = draft_task / "draft/06-api.md"
    path.write_text("## API\n\nПравка аналитика ‹R-01›\n", encoding="utf-8")
    plan(draft_task)
    with pytest.raises(ArtifactError, match="06-api: правка человека"):
        mark(draft_task, ["06-api"])
    release(draft_task, ["06-api"])
    entry = load_state(draft_task)["sections"]["06-api"]
    assert entry["edited_by_human"] is False and entry["generated"] == file_sha1(path)
    assert _section_line(draft_task, "06-api").endswith("| есть")


def test_mark_unknown_or_missing_section(draft_task):
    with pytest.raises(ArtifactError, match="секции 99-x нет в шаблоне feature"):
        mark(draft_task, ["99-x"])
    (draft_task / "draft/10-nfr.md").unlink()
    with pytest.raises(ArtifactError, match="нет файла draft/10-nfr.md"):
        mark(draft_task, ["10-nfr"])


def test_is_human(tmp_path):
    path = tmp_path / "s.md"
    path.write_text("x", encoding="utf-8")
    sha = file_sha1(path)
    assert is_human(None, path) is False
    assert is_human({}, path) is False
    assert is_human({"hash": sha, "edited_by_human": False}, path) is False
    assert is_human({"hash": "0" * 40, "generated": sha, "edited_by_human": False}, path) is False
    assert is_human({"hash": "0" * 40, "edited_by_human": False}, path) is True
    assert is_human({"hash": sha, "edited_by_human": True}, path) is True


def test_assemble_records_row_hashes(draft_task):
    rows = load_state(draft_task)["rows"]
    assert sorted(rows) == ["D-01", "IM-01", "IM-02", "IM-03", "IM-04", "R-01", "R-02", "R-03"]
    assert rows == row_hashes(draft_task)
    brd = draft_task / "sources/BRD.md"
    brd.write_text(brd.read_text(encoding="utf-8").replace("Мерчант видит причину", "Мерчант видит текст причины"), encoding="utf-8")
    changed = row_hashes(draft_task)
    assert [key for key in rows if rows[key] != changed[key]] == ["R-02"]


def test_assemble_rejects_bad_author(task_dir):
    write_sections(task_dir)
    with pytest.raises(ArtifactError, match="автор: без переводов строки и символа"):
        assemble(task_dir, author="Иван | Петров")


def test_cli_mark_release(draft_task, capsys):
    assert main(["mark", str(draft_task), "04-scenarios", "05-changes"]) == 0
    assert "отмечены: 04-scenarios, 05-changes" in capsys.readouterr().out
    assert main(["release", str(draft_task), "04-scenarios"]) == 0
    assert main(["mark", str(draft_task)]) == 2
```

В `tests/test_sa_validate.py` (в конец):

```python
def test_state_rows_and_generated():
    base = {"task": "X", "stage": "draft", "plugin_version": "0.1.0"}
    good = {**base, "rows": {"R-01": "a" * 40}, "sections": {"05-api": {"hash": "b" * 40, "edited_by_human": False, "generated": "c" * 40}}}
    assert validate_state(good) == []
    bad = {**base, "rows": {"X-1": "nope"}, "sections": {"05-api": {"hash": "b" * 40, "edited_by_human": False, "generated": "x"}}}
    errors = validate_state(bad)
    assert "rows: «X-1» — не R-xx, IM-xx или D-xx" in errors
    assert "rows.X-1: ожидается sha1" in errors
    assert "sections.05-api.generated: ожидается sha1" in errors
    assert "rows: ожидается объект" in validate_state({**base, "rows": []})
```

В `tests/test_skills_contract.py` в кортеж `test_tdd_draft_contract` добавь `"sa_draft.py mark tasks/<KEY>"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sa_draft.py tests/test_sa_validate.py tests/test_skills_contract.py -q`
Expected: FAIL — `ImportError: cannot import name 'is_human'`, нет фрагмента `sa_draft.py mark tasks/<KEY>`.

- [ ] **Step 3: Implement**

`scripts/sa_state.py` — после `ARTIFACTS` добавь константу и вынеси атомарную запись:

```python
PUBLISH_FILE = "draft-publish.md"


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
```

(старое тело `save_state` удали; `write_atomic` объяви до `save_state`.)

`scripts/sa_draft.py`:

1. Импорты: добавь `import hashlib`; строку импорта из `sa_state` замени на
   `from sa_state import ARTIFACTS, PUBLISH_FILE, file_sha1, load_state, save_state, write_atomic`; удали локальное `PUBLISH_FILE = "draft-publish.md"`.
2. Константа рядом с `_CONTEXT_COLUMNS`:

```python
ROW_SOURCES = (
    ("BRD", ["ID", "Требование", "Тип"]),
    ("impact-map", ["ID", "Объект", "Вид", "Влияние", "← R"]),
    ("decisions", ["ID", "← Q", "Решение"]),
)
```

3. После `section_path` добавь:

```python
def _entries(state: dict) -> dict:
    sections = state.get("sections")
    return sections if isinstance(sections, dict) else {}


def is_human(entry: dict | None, path: Path) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("edited_by_human"):
        return True
    known = {entry.get("hash"), entry.get("generated")} - {None}
    return bool(known) and file_sha1(path) not in known


def _claim(task_dir: Path, section_ids: list[str], force: bool) -> None:
    state = load_state(task_dir)
    manifest = task_manifest(state)
    names = {s.id for s in manifest.sections}
    sections = _entries(state)
    for sid in section_ids:
        if sid not in names:
            raise ArtifactError(f"секции {sid} нет в шаблоне {manifest.name}")
        path = section_path(task_dir, sid)
        if not path.exists():
            raise ArtifactError(f"нет файла draft/{sid}.md")
        entry = sections.get(sid) if isinstance(sections.get(sid), dict) else {}
        if entry.get("edited_by_human") and not force:
            raise ArtifactError(
                f"{sid}: правка человека — не перезаписывай; снять отметку можно только по слову аналитика: "
                f"sa_draft.py release <папка задачи> {sid}"
            )
        sha = file_sha1(path)
        sections[sid] = {"hash": entry.get("hash", sha), "edited_by_human": False, "generated": sha}
    state["sections"] = sections
    save_state(task_dir, state)


def mark(task_dir: Path, section_ids: list[str]) -> None:
    _claim(task_dir, section_ids, force=False)


def release(task_dir: Path, section_ids: list[str]) -> None:
    _claim(task_dir, section_ids, force=True)


def section_texts(task_dir: Path, manifest: Manifest) -> dict[str, str]:
    return {
        s.id: section_path(task_dir, s.id).read_text(encoding="utf-8")
        for s in manifest.sections if section_path(task_dir, s.id).exists()
    }


def block_section(manifest: Manifest, block: str) -> str | None:
    return next((s.id for s in manifest.sections if s.block == block), None)
```

4. В `assemble`: после проверки `if not author:` добавь

```python
    if any(ch in author for ch in "\n\r|"):
        raise ArtifactError("автор: без переводов строки и символа |")
```

замени две записи `draft.write_text(...)` / `publish.write_text(...)` на `write_atomic(draft, header + body)` и `write_atomic(publish, f"{title}\n\n{table}\n\n{rest}")`, а цикл по секциям — на:

```python
    sections = _entries(state)
    for s in manifest.sections:
        path = section_path(task_dir, s.id)
        sections[s.id] = {"hash": file_sha1(path), "edited_by_human": is_human(sections.get(s.id), path)}
    state["sections"] = sections
    state["rows"] = row_hashes(task_dir)
    save_state(task_dir, state)
```

5. После `task_data` добавь:

```python
def row_hashes(task_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, columns in ROW_SOURCES:
        for row in _rows(_body(task_dir, name), columns):
            text = " | ".join(row[column] for column in columns)
            hashes[row["ID"]] = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return hashes
```

6. `_scope` переименуй в `scope_of` (все вызовы в файле). После него:

```python
def untraced_impacts(data: dict, traced: set[str], scopes: tuple[str, ...] = ("в скоупе",)) -> list[str]:
    return [
        row["ID"] for row in data["impact"]
        if row["Влияние"] in ("новый", "изм.") and scope_of(data, row["ID"]) in scopes and row["ID"] not in traced
    ]
```

7. В `plan` ветку статуса замени на:

```python
        if not path.exists():
            status = "нет"
        elif is_human(entry, path):
            if not entry.get("edited_by_human"):
                entry["edited_by_human"] = True
                changed = True
            status = "правка человека — не перезаписывать"
        else:
            status = "есть"
```

8. В `gaps` словарь `texts = {...}` замени на `texts = section_texts(task_dir, manifest)`, а вычисление `untraced = [...]` — на `untraced = untraced_impacts(data, traced)`.

9. CLI:

```python
USAGE = (
    "использование:\n"
    "  sa_draft.py plan <папка задачи>\n"
    "  sa_draft.py assemble <папка задачи> [автор]\n"
    "  sa_draft.py gaps <папка задачи>\n"
    "  sa_draft.py mark <папка задачи> <секция>...\n"
    "  sa_draft.py release <папка задачи> <секция>..."
)
ARITY = {"plan": (2, 2), "assemble": (2, 3), "gaps": (2, 2), "mark": (3, 99), "release": (3, 99)}
```

и в `main` перед финальным `else:` (gaps):

```python
        elif command == "mark":
            mark(task_dir, argv[2:])
            print("отмечены: " + ", ".join(argv[2:]))
        elif command == "release":
            release(task_dir, argv[2:])
            print("сняты отметки правки человека: " + ", ".join(argv[2:]))
```

`scripts/sa_validate.py` в `validate_state`: внутри цикла по `sections` после проверки `edited_by_human` добавь

```python
            if "generated" in section and not _is_sha1(section["generated"]):
                errors.append(f"sections.{name}.generated: ожидается sha1")
```

и после блока `sections`:

```python
    rows = data.get("rows", {})
    if not isinstance(rows, dict):
        errors.append("rows: ожидается объект")
    else:
        for rid, value in rows.items():
            if not any(is_id(kind, rid) for kind in TRACE_KINDS):
                errors.append(f"rows: «{rid}» — не R-xx, IM-xx или D-xx")
            if not _is_sha1(value):
                errors.append(f"rows.{rid}: ожидается sha1")
```

`skills/tdd-draft/SKILL.md`:
- в шаге 4 после пункта «запиши `<tasks_dir>/<KEY>/draft/<секция>.md` …» добавь пункт: «записал или поправил секцию — сразу `python3 <плагин>/scripts/sa_draft.py mark tasks/<KEY> <секция>`; без этого сборка сочтёт секцию правкой человека»;
- пункт про необязательную секцию: `Не применимо: <причина> ‹ID из среза›` вместо `‹…›`;
- в шаге 7 после «исправляй секции, собирай заново»: «после каждой правки — `sa_draft.py mark` по исправленной секции».

`shared/schemas/artifacts.md`, раздел «draft/ и draft.md»: абзац «`assemble` записывает в `state.json` `sections.<id>.hash`…» замени на:

```markdown
`assemble` записывает в `state.json` `sections.<id>.hash` и снимок `rows` (sha1 строк `R-xx`, `IM-xx`, `D-xx` на момент сборки — по нему `/tdd-update` находит изменения). Стадия, записавшая или поправившая секцию, сразу вызывает `python3 <плагин>/scripts/sa_draft.py mark tasks/<KEY> <секция>` — в `sections.<id>.generated` попадает sha1 её текста. Секция — правка человека (`edited_by_human: true`), если её sha1 не совпадает ни с `hash`, ни с `generated`; это ставят `sa_draft.py plan` и `assemble`, и стадии такую секцию не перезаписывают. Снять отметку — только по слову аналитика: `sa_draft.py release tasks/<KEY> <секция>`.
```

Раздел «state.json»: пункт `sections` замени на «`sections`: для каждой секции `hash` (sha1), `edited_by_human` (`true`/`false`), необязательный `generated` (sha1 текста, записанного стадией).» и добавь «`rows`: снимок `ID → sha1` строк BRD, карты и решений на момент последней сборки; пишет `assemble`.»

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: PASS (все прежние тесты и новые).

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_state.py scripts/sa_draft.py scripts/sa_validate.py skills/tdd-draft/SKILL.md shared/schemas/artifacts.md tests/test_sa_draft.py tests/test_sa_validate.py tests/test_skills_contract.py
git commit -m "feat: sa_draft mark/release tell regenerated sections from human edits; row snapshot on assemble"
```

---

### Task 2: `sa_review.py` — детерминированные проходы ревью

**Files:**
- Create: `scripts/sa_review.py`
- Modify: `tests/conftest.py` (write_review)
- Test: `tests/test_sa_review.py`

**Interfaces:**
- Consumes (Task 1): `sa_draft.section_texts`, `block_section`, `untraced_impacts`, `task_data`, `task_manifest`, `trace_refs`, `placeholders`; `sa_state.write_atomic`, `file_sha1`, `ARTIFACTS`.
- Produces:
  - Константы: `SEVERITIES = ("критично", "важно", "совет")`, `STATUSES = ("открыто", "принято", "отклонено", "закрыто")`, `REVIEW_COLUMNS = ["ID", "Важность", "Где", "Проблема", "← Ссылка", "Предложение", "Статус"]`, `COVERAGE_COLUMNS = ["R", "Секции", "AC"]`, `WHOLE = ("шапка", "весь черновик")`.
  - `@dataclass Finding(severity, where, problem, ref, proposal)` с методом `row() -> str`.
  - `coverage(task_dir) -> list[tuple[str, list[str], list[str]]]`, `coverage_table(task_dir) -> str`.
  - `precheck(task_dir) -> list[Finding]`, `render_precheck(task_dir) -> str` (первая строка `draft: <sha1 draft.md>`).
  - `as_is(task_dir) -> dict[str, list[str]]`, `render_as_is(task_dir) -> str`.
  - `review_rows(task_dir) -> list[dict[str, str]]`, `set_status(task_dir, status, ids) -> list[str]`, `review_summary(task_dir) -> dict | None` (`{"open", "critical", "accepted", "stale"}`).
  - CLI: `sa_review.py precheck|coverage|asis <папка задачи>`, `sa_review.py status <папка задачи> <принято|отклонено> <RV-xx…|все>`.
  - `conftest.write_review(task_dir, rows: list[str]) -> Path`.

- [ ] **Step 1: Write the failing tests**

В конец `tests/conftest.py`:

```python
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
```

`tests/test_sa_review.py`:

```python
import pytest

from conftest import write_review
from sa_artifacts import ArtifactError
from sa_draft import assemble, mark
from sa_review import (
    Finding, as_is, coverage, coverage_table, main, precheck, render_precheck, review_rows, review_summary, set_status,
)
from sa_state import file_sha1
from sa_template import load_manifest

ALL = [s.id for s in load_manifest("feature").sections]
ACCEPTANCE = (
    "## Критерии приёмки\n\n### US-01\n\n"
    "- AC-01. Условие: x. Действие: y. Результат: z. ‹R-01, R-02›\n"
    "- AC-02. Условие: x. Действие: y. Результат: z. ‹R-01›\n"
)
ROW_OPEN = "| RV-01 | критично | 12-acceptance | R-03 не покрыт | R-03 | добавить AC | открыто |"
ROW_ADVICE = "| RV-02 | совет | 06-api | Нет кода ответа | IM-01 | указать код | открыто |"


def _rebuild(task_dir, sid, text):
    (task_dir / "draft" / f"{sid}.md").write_text(text, encoding="utf-8")
    mark(task_dir, [sid])
    assemble(task_dir)


def test_coverage(draft_task):
    _rebuild(draft_task, "12-acceptance", ACCEPTANCE)
    assert coverage(draft_task) == [
        ("R-01", ALL, ["AC-01", "AC-02"]),
        ("R-02", ["12-acceptance"], ["AC-01"]),
        ("R-03", [], []),
    ]
    table = coverage_table(draft_task).splitlines()
    assert table[:2] == ["| R | Секции | AC |", "|---|---|---|"]
    assert table[-1] == "| R-03 | — | — |"
    assert table[3] == "| R-02 | 12-acceptance | AC-01 |"


def test_precheck(draft_task):
    _rebuild(draft_task, "04-scenarios", "## Сценарии\n\nТекст ⚠ Q-PO-02 и ⚠ Q-PO-01 ‹R-01›\n")
    findings = precheck(draft_task)
    assert Finding("важно", "04-scenarios", "⚠ Q-PO-02: неизвестное не закрыто", "Q-PO-02",
                   "закрыть Q-PO-02 в /tdd-clarify, затем /tdd-update") in findings
    assert Finding("важно", "04-scenarios", "⚠ Q-PO-01 стоит на закрытом вопросе", "Q-PO-01",
                   "/tdd-update заменит плейсхолдер по решению") in findings
    assert Finding("критично", "12-acceptance", "R-03 не покрыт ни одним критерием приёмки (нет ни в одной секции)",
                   "R-03", "добавить AC со ссылкой ‹R-03›") in findings
    assert Finding("важно", "05-changes", "IM-02 (новый/изм.) не описан ни в одной секции", "IM-02",
                   "описать в 05-changes или исключить в context.md") in findings
    problems = [f.problem for f in findings]
    assert any(p.startswith("R-01 не покрыт ни одним критерием приёмки (есть в 01-context") for p in problems)
    assert not any(p.startswith("IM-04") for p in problems)
    lines = render_precheck(draft_task).splitlines()
    assert lines[0] == f"draft: {file_sha1(draft_task / 'draft.md')}"
    assert lines[2] == "| Важность | Где | Проблема | ← Ссылка | Предложение |"


def test_precheck_needs_draft(draft_task):
    (draft_task / "draft.md").unlink()
    with pytest.raises(ArtifactError, match="нет draft.md"):
        precheck(draft_task)


def test_as_is(draft_task):
    _rebuild(draft_task, "05-changes",
             "## Доработки по сервисам\n\n- Правило проверяет формат [as is]. ‹IM-02›\n"
             "- Новое правило [to be]. ‹IM-02›\n- Анкета сохраняется [as is]. ‹R-01›\n")
    assert as_is(draft_task) == {
        "lkp-back": ["05-changes: Правило проверяет формат [as is]. ‹IM-02›"],
        "без сервиса": ["05-changes: Анкета сохраняется [as is]. ‹R-01›"],
    }


def test_set_status(draft_task):
    write_review(draft_task, [ROW_OPEN, ROW_ADVICE])
    assert set_status(draft_task, "принято", ["RV-01"]) == ["RV-01"]
    assert set_status(draft_task, "отклонено", ["все"]) == ["RV-02"]
    assert [r["Статус"] for r in review_rows(draft_task)] == ["принято", "отклонено"]
    with pytest.raises(ArtifactError, match="нет замечания RV-09"):
        set_status(draft_task, "принято", ["RV-09"])
    with pytest.raises(ArtifactError, match="статус: принято или отклонено"):
        set_status(draft_task, "закрыто", ["RV-01"])
    path = draft_task / "review.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| принято |", "| закрыто |"), encoding="utf-8")
    with pytest.raises(ArtifactError, match="RV-01 уже закрыто"):
        set_status(draft_task, "отклонено", ["RV-01"])


def test_review_summary(draft_task):
    assert review_summary(draft_task) is None
    write_review(draft_task, [ROW_OPEN, ROW_ADVICE])
    set_status(draft_task, "принято", ["RV-02"])
    assert review_summary(draft_task) == {"open": 1, "critical": 1, "accepted": 1, "stale": False}
    _rebuild(draft_task, "04-scenarios", "## Сценарии\n\nДругое ‹R-01›\n")
    assert review_summary(draft_task)["stale"] is True


def test_cli(draft_task, capsys):
    assert main(["precheck", str(draft_task)]) == 0
    assert capsys.readouterr().out.startswith("draft: ")
    assert main(["coverage", str(draft_task)]) == 0
    assert main(["asis", str(draft_task)]) == 0
    assert "Утверждений [as is] нет" in capsys.readouterr().out
    assert main(["status", str(draft_task), "принято", "RV-01"]) == 1
    write_review(draft_task, [ROW_OPEN])
    assert main(["status", str(draft_task), "принято", "RV-01"]) == 0
    assert main(["status", str(draft_task), "принято"]) == 2
    assert main([]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sa_review.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_review'`.

- [ ] **Step 3: Implement `scripts/sa_review.py`**

```python
"""Ревью черновика: детерминированные проходы 1–3, матрица покрытия, утверждения [as is], статусы замечаний."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError, find_table, parse_tables, split_frontmatter
from sa_draft import (
    block_section, placeholders, section_texts, task_data, task_manifest, trace_refs, untraced_impacts,
)
from sa_state import ARTIFACTS, file_sha1, load_state, write_atomic

SEVERITIES = ("критично", "важно", "совет")
STATUSES = ("открыто", "принято", "отклонено", "закрыто")
REVIEW_COLUMNS = ["ID", "Важность", "Где", "Проблема", "← Ссылка", "Предложение", "Статус"]
COVERAGE_COLUMNS = ["R", "Секции", "AC"]
WHOLE = ("шапка", "весь черновик")
AC_RE = re.compile(r"^\s*-\s*(AC-\d{2,})\b")
ROW_ID_RE = re.compile(r"^\|\s*(RV-\d{2,})\s*\|")
AS_IS = "[as is]"
NO_SERVICE = "без сервиса"


@dataclass
class Finding:
    severity: str
    where: str
    problem: str
    ref: str
    proposal: str

    def row(self) -> str:
        return f"| {self.severity} | {self.where} | {self.problem} | {self.ref} | {self.proposal} |"


def _context(task_dir: Path):
    state = load_state(task_dir)
    manifest = task_manifest(state)
    return manifest, task_data(task_dir), section_texts(task_dir, manifest)


def acceptance_refs(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = AC_RE.match(line)
        if match:
            found.setdefault(match.group(1), []).extend(r for r in trace_refs(line) if r.startswith("R-"))
    return found


def coverage(task_dir: Path) -> list[tuple[str, list[str], list[str]]]:
    manifest, data, texts = _context(task_dir)
    acs = acceptance_refs(texts.get(block_section(manifest, "acceptance") or "", ""))
    return [
        (
            r,
            [sid for sid, text in texts.items() if r in trace_refs(text)],
            [ac for ac, refs in acs.items() if r in refs],
        )
        for r in data["brd"]
    ]


def coverage_table(task_dir: Path) -> str:
    lines = ["| R | Секции | AC |", "|---|---|---|"]
    lines += [f"| {r} | {', '.join(s) or '—'} | {', '.join(a) or '—'} |" for r, s, a in coverage(task_dir)]
    return "\n".join(lines)


def _draft_md(task_dir: Path) -> Path:
    path = task_dir / ARTIFACTS["draft"]
    if not path.exists():
        raise ArtifactError("нет draft.md — сначала /tdd-draft")
    return path


def precheck(task_dir: Path) -> list[Finding]:
    _draft_md(task_dir)
    manifest, data, texts = _context(task_dir)
    acceptance = block_section(manifest, "acceptance") or "весь черновик"
    changes = block_section(manifest, "changes") or "весь черновик"
    statuses = {q.id: q.status for q in data["questions"]}
    findings: list[Finding] = []
    for sid, text in texts.items():
        for qid in dict.fromkeys(q for q in placeholders(text) if q):
            if statuses.get(qid) == "open":
                findings.append(Finding("важно", sid, f"⚠ {qid}: неизвестное не закрыто", qid,
                                        f"закрыть {qid} в /tdd-clarify, затем /tdd-update"))
            else:
                findings.append(Finding("важно", sid, f"⚠ {qid} стоит на закрытом вопросе", qid,
                                        "/tdd-update заменит плейсхолдер по решению"))
    for r, sections, acs in coverage(task_dir):
        if not acs:
            where = f"есть в {', '.join(sections)}" if sections else "нет ни в одной секции"
            findings.append(Finding("критично", acceptance, f"{r} не покрыт ни одним критерием приёмки ({where})", r,
                                    f"добавить AC со ссылкой ‹{r}›"))
    traced = {ref for text in texts.values() for ref in trace_refs(text)}
    for im in untraced_impacts(data, traced, ("в скоупе", "?")):
        findings.append(Finding("важно", changes, f"{im} (новый/изм.) не описан ни в одной секции", im,
                                f"описать в {changes} или исключить в context.md"))
    return findings


def render_precheck(task_dir: Path) -> str:
    findings = precheck(task_dir)
    lines = [f"draft: {file_sha1(_draft_md(task_dir))}", f"Замечания проходов 1–3: {len(findings)}"]
    if findings:
        lines += ["| Важность | Где | Проблема | ← Ссылка | Предложение |", "|---|---|---|---|---|"]
        lines += [f.row() for f in findings]
    return "\n".join(lines)


def as_is(task_dir: Path) -> dict[str, list[str]]:
    _, data, texts = _context(task_dir)
    services = {row["ID"]: row["Объект"].split(":", 1)[0].strip() for row in data["impact"]}
    groups: dict[str, list[str]] = {}
    for sid, text in texts.items():
        for line in text.splitlines():
            if AS_IS not in line:
                continue
            names = list(dict.fromkeys(services[r] for r in trace_refs(line) if r in services)) or [NO_SERVICE]
            statement = f"{sid}: {line.strip().removeprefix('- ').strip()}"
            for name in names:
                groups.setdefault(name, []).append(statement)
    return groups


def render_as_is(task_dir: Path) -> str:
    groups = as_is(task_dir)
    if not groups:
        return "Утверждений [as is] нет"
    lines: list[str] = []
    for name, statements in groups.items():
        lines.append(f"{name}:")
        lines += [f"  {s}" for s in statements]
    return "\n".join(lines)


def _review_path(task_dir: Path) -> Path:
    path = task_dir / ARTIFACTS["review"]
    if not path.exists():
        raise ArtifactError("нет review.md — сначала /tdd-check")
    return path


def review_rows(task_dir: Path) -> list[dict[str, str]]:
    _, body = split_frontmatter(_review_path(task_dir).read_text(encoding="utf-8"))
    table = find_table(parse_tables(body), REVIEW_COLUMNS)
    if table is None:
        raise ArtifactError("review.md: нет таблицы замечаний")
    return table.rows


def set_status(task_dir: Path, status: str, ids: list[str]) -> list[str]:
    if status not in ("принято", "отклонено"):
        raise ArtifactError("статус: принято или отклонено")
    rows = {row["ID"]: row["Статус"] for row in review_rows(task_dir)}
    targets = [rid for rid, value in rows.items() if value == "открыто"] if ids == ["все"] else ids
    for rid in targets:
        if rid not in rows:
            raise ArtifactError(f"нет замечания {rid}")
        if rows[rid] == "закрыто":
            raise ArtifactError(f"{rid} уже закрыто")
    path = _review_path(task_dir)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = ROW_ID_RE.match(line)
        if match and match.group(1) in targets:
            end = "\n" if line.endswith("\n") else ""
            head = line.rstrip("\r\n").rstrip().rstrip("|").rpartition("|")[0]
            lines[i] = f"{head}| {status} |{end}"
    write_atomic(path, "".join(lines))
    return targets


def review_summary(task_dir: Path) -> dict | None:
    if not (task_dir / ARTIFACTS["review"]).exists():
        return None
    meta, _ = split_frontmatter(_review_path(task_dir).read_text(encoding="utf-8"))
    rows = review_rows(task_dir)
    draft = task_dir / ARTIFACTS["draft"]
    return {
        "open": sum(r["Статус"] == "открыто" for r in rows),
        "critical": sum(r["Статус"] == "открыто" and r["Важность"] == "критично" for r in rows),
        "accepted": sum(r["Статус"] == "принято" for r in rows),
        "stale": not draft.exists() or meta.get("draft") != file_sha1(draft),
    }


USAGE = (
    "использование:\n"
    "  sa_review.py precheck <папка задачи>\n"
    "  sa_review.py coverage <папка задачи>\n"
    "  sa_review.py asis <папка задачи>\n"
    "  sa_review.py status <папка задачи> <принято|отклонено> <RV-xx…|все>"
)
RENDER = {"precheck": render_precheck, "coverage": coverage_table, "asis": render_as_is}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if not ((command in RENDER and len(argv) == 2) or (command == "status" and len(argv) >= 4)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "status":
            changed = set_status(task_dir, argv[2], argv[3:])
            print(f"{argv[2]}: {', '.join(changed) if changed else 'нет открытых замечаний'}")
        else:
            print(RENDER[command](task_dir))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_sa_review.py -q` → PASS; затем `.venv/bin/pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_review.py tests/conftest.py tests/test_sa_review.py
git commit -m "feat: sa_review.py deterministic review passes, coverage matrix, as-is statements, finding statuses"
```

---

### Task 3: Схема `review.md`, валидатор, `RV` в `sa_ids`, ревью в `/tdd-status`

**Files:**
- Modify: `scripts/sa_validate.py`, `scripts/sa_ids.py`, `scripts/sa_status.py`
- Modify: `shared/schemas/artifacts.md` (новый раздел `## review.md`)
- Test: `tests/test_sa_validate.py`, `tests/test_sa_ids.py`, `tests/test_sa_status.py`, `tests/test_shared_docs.py`

**Interfaces:**
- Consumes (Task 2): `sa_review.SEVERITIES`, `STATUSES`, `REVIEW_COLUMNS`, `COVERAGE_COLUMNS`, `WHOLE`, `coverage`, `review_summary`.
- Produces: `sa_validate.validate_review(text: str, known: dict, task_dir: Path, state: dict) -> tuple[list[str], set[str] | None]`; `sa_ids.KINDS["RV"] = "review"`; `sa_status.next_step(stage, blocking_open, brd_complete, unresolved_scope=0, review=None)`.

- [ ] **Step 1: Write the failing tests**

В конец `tests/test_sa_validate.py`:

```python
from conftest import write_review

REVIEW_ROW = "| RV-01 | критично | 12-acceptance | R-03 не покрыт | R-03 | добавить AC | открыто |"


def test_review_valid(draft_task):
    write_review(draft_task, [REVIEW_ROW, "| RV-02 | совет | шапка | Нет релиза | — | указать | принято |"])
    assert validate_task(draft_task) == []


def test_review_row_rules(draft_task):
    write_review(draft_task, ["| RV-1 | срочно | 99-x | — | R-09, foo | x | новое |"])
    errors = validate_task(draft_task)
    for expected in (
        "review.md: RV-1: ID должен быть вида RV-01",
        "review.md: RV-1: важность «срочно» не из списка: важно, критично, совет",
        "review.md: RV-1: где «99-x» — id секции шаблона, шапка или весь черновик",
        "review.md: RV-1: пустая проблема",
        "review.md: RV-1: «foo» в ← Ссылка — не ID",
        "review.md: RV-1: ссылка на несуществующий R-09",
        "review.md: RV-1: статус «новое» не из списка: закрыто, отклонено, открыто, принято",
    ):
        assert expected in errors, expected


def test_review_header(draft_task):
    path = write_review(draft_task, [REVIEW_ROW])
    _edit(path, "round: 1", "round: 0")
    _edit(path, "reviewed: 2026-10-16", "reviewed: вчера")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(text.split("draft: ", 1)[1].split("\n", 1)[0], "abc", 1), encoding="utf-8")
    errors = validate_task(draft_task)
    assert "review.md: draft: sha1 draft.md, по которому делалось ревью" in errors
    assert "review.md: reviewed должен быть в формате ГГГГ-ММ-ДД" in errors
    assert "review.md: round: целое число ≥ 1" in errors


def test_review_coverage(draft_task):
    path = write_review(draft_task, [REVIEW_ROW])
    _edit(path, "| R-03 | — | — |", "| R-03 | 05-changes | — |")
    assert "review.md: матрица покрытия не совпадает с черновиком — вставь вывод sa_review.py coverage" in validate_task(draft_task)
    _edit(path, "| R-03 | 05-changes | — |\n", "")
    assert "review.md: R-03: нет в матрице покрытия" in validate_task(draft_task)
    _edit(path, "## Покрытие BRD", "## Прочее")
    _edit(path, "| R | Секции | AC |", "| X | Y | Z |")
    assert "review.md: нет таблицы покрытия с колонками R, Секции, AC" in validate_task(draft_task)


def test_review_stale_skips_coverage_compare(draft_task):
    from sa_draft import assemble, mark

    path = write_review(draft_task, [REVIEW_ROW])
    _edit(path, "| R-03 | — | — |", "| R-03 | 05-changes | — |")
    (draft_task / "draft/04-scenarios.md").write_text("## Сценарии\n\nДругое ‹R-01›\n", encoding="utf-8")
    mark(draft_task, ["04-scenarios"])
    assemble(draft_task)
    assert validate_task(draft_task) == []


def test_stage_check_needs_review(draft_task):
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    assert "review.md: нет файла — запусти /tdd-check" in validate_task(draft_task)
```

`tests/test_sa_ids.py` (в конец):

```python
def test_review_ids(draft_task):
    from conftest import write_review

    write_review(draft_task, ["| RV-01 | совет | шапка | x | — | y | открыто |", "| RV-02 | совет | шапка | x | — | y | открыто |"])
    assert next_ids(draft_task, "RV", 2) == ["RV-03", "RV-04"]
```

(если `next_ids` в файле не импортирован — добавь `from sa_ids import next_ids`).

`tests/test_sa_status.py` (в конец):

```python
def test_review_status_and_next_step(draft_task):
    from conftest import write_review
    from sa_review import set_status
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    write_review(draft_task, ["| RV-01 | критично | 12-acceptance | x | R-03 | y | открыто |"])
    status = build_status(draft_task)
    assert "Ревью: открыто 1 (критично 1), принято 0" in status
    assert status.endswith("Следующий шаг: разобрать замечания review.md: /tdd-update <RV-xx…> — принять, «/tdd-update отклонить RV-xx» — отклонить")
    set_status(draft_task, "принято", ["RV-01"])
    assert build_status(draft_task).endswith("Следующий шаг: /tdd-update — внести принятые замечания, затем /tdd-check")
    set_status(draft_task, "отклонено", ["RV-01"])
    assert build_status(draft_task).endswith("Следующий шаг: замечаний нет — завершить: sa_state.py set <папка задачи> stage done")


def test_review_stale_status(draft_task):
    from conftest import write_review
    from sa_draft import assemble, mark
    from sa_state import set_value

    set_value(draft_task, "stage", "check")
    write_review(draft_task, [])
    (draft_task / "draft/04-scenarios.md").write_text("## Сценарии\n\nДругое ‹R-01›\n", encoding="utf-8")
    mark(draft_task, ["04-scenarios"])
    assemble(draft_task)
    status = build_status(draft_task)
    assert "Ревью: открыто 0 (критично 0), принято 0 · устарело — черновик менялся после ревью" in status
    assert status.endswith("Следующий шаг: /tdd-check — черновик менялся после ревью")
```

`tests/test_shared_docs.py`: в `REQUIRED_HEADINGS["shared/schemas/artifacts.md"]` добавь `"## review.md"` (после `"## draft/ и draft.md"`), и в конец файла:

```python
def test_schema_doc_describes_review():
    from sa_review import COVERAGE_COLUMNS, REVIEW_COLUMNS, SEVERITIES, STATUSES

    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    for column in REVIEW_COLUMNS + COVERAGE_COLUMNS:
        assert f"| {column} |" in text, f"колонка {column} не описана"
    for value in SEVERITIES + STATUSES:
        assert f"`{value}`" in text, f"значение {value} не описано"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sa_validate.py tests/test_sa_ids.py tests/test_sa_status.py tests/test_shared_docs.py -q`
Expected: FAIL (нет проверок review.md, нет вида RV, нет строки «Ревью», нет раздела в схеме).

- [ ] **Step 3: Implement**

`scripts/sa_validate.py`:

1. Импорт: `from sa_review import COVERAGE_COLUMNS, REVIEW_COLUMNS, SEVERITIES, STATUSES, WHOLE, coverage`; из `sa_state` дополнительно `file_sha1`.
2. Функция после `validate_draft`:

```python
def validate_review(text: str, known: dict, task_dir: Path, state: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    if not _is_sha1(meta.get("draft")):
        errors.append("draft: sha1 draft.md, по которому делалось ревью")
    if not DATE_RE.fullmatch(str(meta.get("reviewed", ""))):
        errors.append("reviewed должен быть в формате ГГГГ-ММ-ДД")
    round_ = meta.get("round")
    if not (isinstance(round_, int) and not isinstance(round_, bool) and round_ >= 1):
        errors.append("round: целое число ≥ 1")
    try:
        places: set[str] | None = {s.id for s in task_manifest(state).sections} | set(WHOLE)
    except ArtifactError:
        places = None
    tables = parse_tables(body)
    table = find_table(tables, REVIEW_COLUMNS)
    ids: set[str] | None = None
    if table is None:
        errors.append(f"нет таблицы замечаний с колонками {', '.join(REVIEW_COLUMNS)}")
    else:
        for row in table.rows:
            rid = row["ID"]
            if not is_id("RV", rid):
                errors.append(f"{rid}: ID должен быть вида RV-01")
            if row["Важность"] not in SEVERITIES:
                errors.append(f"{rid}: важность «{row['Важность']}» не из списка: {_one_of(set(SEVERITIES))}")
            if places is not None and row["Где"] not in places:
                errors.append(f"{rid}: где «{row['Где']}» — id секции шаблона, шапка или весь черновик")
            if row["Проблема"] in EMPTY:
                errors.append(f"{rid}: пустая проблема")
            if row["← Ссылка"] not in EMPTY:
                tokens = [t.strip() for t in row["← Ссылка"].split(",") if t.strip()]
                errors += [f"{rid}: «{t}» в ← Ссылка — не ID" for t in tokens if find_refs(t) != [t]]
                refs = [t for t in tokens if find_refs(t) == [t]]
                errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
            if row["Статус"] not in STATUSES:
                errors.append(f"{rid}: статус «{row['Статус']}» не из списка: {_one_of(set(STATUSES))}")
        ids_list = [row["ID"] for row in table.rows]
        errors += [f"{d}: ID повторяется" for d in _duplicates(ids_list)]
        ids = set(ids_list)
    matrix = find_table(tables, COVERAGE_COLUMNS)
    if matrix is None:
        return errors + [f"нет таблицы покрытия с колонками {', '.join(COVERAGE_COLUMNS)}"], ids
    listed = [row["R"] for row in matrix.rows]
    errors += [f"{d}: R повторяется в матрице покрытия" for d in _duplicates(listed)]
    if known.get("R") is not None:
        errors += [f"{r}: нет в матрице покрытия" for r in sorted(known["R"] - set(listed))]
    draft = task_dir / ARTIFACTS["draft"]
    if draft.exists() and meta.get("draft") == file_sha1(draft):
        expected = {r: (", ".join(s) or "—", ", ".join(a) or "—") for r, s, a in coverage(task_dir)}
        actual = {row["R"]: (row["Секции"], row["AC"]) for row in matrix.rows}
        if any(actual[r] != expected[r] for r in actual if r in expected) or set(actual) - set(expected):
            errors.append("матрица покрытия не совпадает с черновиком — вставь вывод sa_review.py coverage")
    return errors, ids
```

3. В `validate_task` после `errors += validate_draft(...)`:

```python
    if (task_dir / ARTIFACTS["review"]).exists():
        _run(task_dir, "review", lambda t: validate_review(t, known, task_dir, state), errors)
    elif state.get("stage") in ("check", "done"):
        errors.append("review.md: нет файла — запусти /tdd-check")
```

`scripts/sa_ids.py`: `KINDS` дополни `"RV": "review"`, в `USAGE` — `<вид: R|IM|Q-PO|Q-SA|D|RV>`, в docstring — `RV`.

`scripts/sa_status.py`:

```python
from sa_review import review_summary


def next_step(stage, blocking_open, brd_complete, unresolved_scope=0, review=None) -> str:
    if brd_complete is False:
        return "переслать вопросы PO, после ответов запустить /tdd-impact повторно"
    if stage == "clarify":
        return "/tdd-clarify — закрыть блокирующие вопросы" if blocking_open or unresolved_scope else "/tdd-draft"
    if stage == "check" and review:
        if review["stale"]:
            return "/tdd-check — черновик менялся после ревью"
        if review["accepted"]:
            return "/tdd-update — внести принятые замечания, затем /tdd-check"
        if review["open"]:
            return "разобрать замечания review.md: /tdd-update <RV-xx…> — принять, «/tdd-update отклонить RV-xx» — отклонить"
        return "замечаний нет — завершить: sa_state.py set <папка задачи> stage done"
    return _NEXT.get(stage, "проверь state.json: неизвестная стадия")
```

(аннотации типов сохрани как в исходной функции, добавив `review: dict | None = None`). В `build_status` после блока «Черновик»:

```python
    review = review_summary(task_dir)
    if review:
        line = f"Ревью: открыто {review['open']} (критично {review['critical']}), принято {review['accepted']}"
        lines.append(line + (" · устарело — черновик менялся после ревью" if review["stale"] else ""))
```

и последнюю строку — `next_step(state.get('stage'), blocking_open, brd_complete, len(unresolved), review)`.

`shared/schemas/artifacts.md` — после раздела «draft/ и draft.md» новый раздел:

````markdown
## review.md

Замечания стадии `/tdd-check`. Шапка: `draft` (sha1 `draft.md`, по которому делалось ревью), `reviewed` (ГГГГ-ММ-ДД), `round` (номер прохода ревью, с 1).

```markdown
## Замечания

| ID | Важность | Где | Проблема | ← Ссылка | Предложение | Статус |
|---|---|---|---|---|---|---|
| RV-01 | критично | 12-acceptance | R-04 не покрыт ни одним критерием приёмки | R-04 | добавить AC в US-02 | открыто |

## Покрытие BRD

| R | Секции | AC |
|---|---|---|
| R-04 | 05-changes | — |
```

| Колонка | Значение |
|---|---|
| ID | `RV-xx`, сквозная нумерация, не переиспользуются |
| Важность | `критично`, `важно`, `совет`; замечание без доказательства — `совет` |
| Где | id секции из манифеста, `шапка` или `весь черновик` |
| Проблема | Что не так, с коротким доказательством (цитата, номер AC или шага) |
| ← Ссылка | `R-xx`, `IM-xx`, `D-xx`, `Q-PO-xx`, `Q-SA-xx` через запятую; `—` — только для замечаний по шаблону |
| Предложение | Как исправить |
| Статус | `открыто` (новое), `принято` / `отклонено` (решение аналитика), `закрыто` (повторный `/tdd-check` не нашёл проблему) |

- Матрица «Покрытие BRD» — вывод `python3 <плагин>/scripts/sa_review.py coverage tasks/<KEY>` как есть: каждый `R-xx` из BRD ровно один раз; `Секции` — где `R-xx` есть в трассировке, `AC` — критерии приёмки со ссылкой на него. Пока `draft` в шапке совпадает с sha1 `draft.md`, валидатор сверяет матрицу с черновиком.
- Статус меняет только команда `python3 <плагин>/scripts/sa_review.py status tasks/<KEY> <принято|отклонено> <RV-xx…|все>` (`все` — все `открыто`); `закрыто` ставит только `/tdd-check`. ID и тексты прошлых замечаний не меняются.
- На стадии `check` и `done` файл обязателен.
````

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_validate.py scripts/sa_ids.py scripts/sa_status.py shared/schemas/artifacts.md tests/test_sa_validate.py tests/test_sa_ids.py tests/test_sa_status.py tests/test_shared_docs.py
git commit -m "feat: review.md schema and validation, RV ids, review line and next step in status"
```

---

### Task 4: `sa_update.py` — затронутые секции, предложения, отметка публикации

**Files:**
- Create: `scripts/sa_update.py`
- Modify: `scripts/sa_state.py` (`set … published <url>`), `scripts/sa_validate.py` (`published` в state)
- Modify: `skills/tdd-draft/SKILL.md` (шаг 8), `shared/schemas/artifacts.md` (state.json, proposals/)
- Test: `tests/test_sa_update.py`, `tests/test_sa_state.py`, `tests/test_sa_validate.py`, `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: Task 1 (`row_hashes`, `is_human`, `mark`, `release`, `section_texts`, `block_section`, `scope_of`, `task_data`, `task_manifest`, `trace_refs`, `placeholders`, `section_path`), Task 2 (`review_rows`), `sa_state.PUBLISH_FILE`, `write_atomic`.
- Produces:
  - `@dataclass SectionUpdate(id: str, reasons: list[str], human: bool)`
  - `@dataclass UpdatePlan(snapshot: bool, new, changed, removed, accepted, sections: list[SectionUpdate], unbound, proposals: list[str], published: str | None)`
  - `build_plan(task_dir) -> UpdatePlan`, `render_plan(plan) -> str`
  - `proposal_diff(task_dir, sid) -> str`, `apply_proposal(task_dir, sid) -> None`, `drop_proposal(task_dir, sid) -> None`
  - CLI: `sa_update.py plan <папка>`, `sa_update.py diff|apply|drop <папка> <секция>`
  - `sa_state.set_value(task_dir, "published", url)` → `state["published"] = {"url": url, "hash": sha1(draft-publish.md)}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sa_update.py`:

```python
import pytest

from conftest import write_review
from sa_artifacts import ArtifactError
from sa_draft import assemble, mark
from sa_state import load_state, save_state, set_value
from sa_update import apply_proposal, build_plan, drop_proposal, main, proposal_diff, render_plan


def _append(path, line):
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + line + "\n", encoding="utf-8")


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _rebuild(task_dir, sid, text):
    (task_dir / "draft" / f"{sid}.md").write_text(text, encoding="utf-8")
    mark(task_dir, [sid])
    assemble(task_dir)


def _sections(plan):
    return [(s.id, s.reasons, s.human) for s in plan.sections]


def test_nothing_to_update(draft_task):
    plan = build_plan(draft_task)
    assert (plan.snapshot, plan.new, plan.changed, plan.removed, plan.sections, plan.unbound) == (True, [], [], [], [], [])
    text = render_plan(plan)
    assert text.splitlines()[0] == "Изменения с последней сборки: новые нет; изменены нет; удалены нет"
    assert "Секции к обновлению: нет" in text


def test_new_decision_hits_placeholder_sections(draft_task):
    _rebuild(draft_task, "04-scenarios", "## Сценарии\n\nТекст: ⚠ Q-PO-02 ‹R-02›\n")
    _append(draft_task / "decisions.md", "| D-02 | Q-PO-02 | Текст «Нельзя» | PO, чат ММ | 2026-10-16 |")
    _edit(draft_task / "questions.md", "— *open, blocking*", "— *answered*")
    plan = build_plan(draft_task)
    assert plan.new == ["D-02"]
    assert _sections(plan) == [("04-scenarios", ["D-02 (⚠ Q-PO-02)"], False)]
    assert "04-scenarios | перегенерировать | D-02 (⚠ Q-PO-02)" in render_plan(plan)


def test_new_decision_by_trace_and_unbound(draft_task):
    _rebuild(draft_task, "07-integrations", "## Интеграции и события\n\nСобытие ‹IM-04›\n")
    _append(draft_task / "decisions.md", "| D-02 | Q-SA-01 | Событие публикуется | разработка | 2026-10-16 |")
    _append(draft_task / "decisions.md", "| D-03 | — | Логи храним 30 дней | PO | 2026-10-16 |")
    plan = build_plan(draft_task)
    assert _sections(plan) == [("07-integrations", ["D-02"], False)]
    assert plan.unbound == ["D-03"]
    assert "Без привязки: D-03" in render_plan(plan)


def test_changed_and_removed_rows(draft_task):
    _rebuild(draft_task, "12-acceptance", "## Критерии приёмки\n\n- AC-01. Условие ‹R-02›\n")
    _rebuild(draft_task, "11-migration", "## Миграция и запуск\n\nБез пересчёта ‹D-01›\n")
    _edit(draft_task / "sources/BRD.md", "Мерчант видит причину", "Мерчант видит текст причины")
    decisions = draft_task / "decisions.md"
    decisions.write_text("".join(l for l in decisions.read_text(encoding="utf-8").splitlines(keepends=True)
                                 if not l.startswith("| D-01")), encoding="utf-8")
    plan = build_plan(draft_task)
    assert (plan.changed, plan.removed) == (["R-02"], ["D-01"])
    assert _sections(plan) == [("11-migration", ["D-01"], False), ("12-acceptance", ["R-02"], False)]


def test_new_impact_and_requirement(draft_task):
    _append(draft_task / "impact-map.md", "| IM-05 | partners-dashboard: promocode/list | API | новый | R-01 | — | допущение | низкая |")
    _append(draft_task / "sources/BRD.md", "| R-04 | Новое требование | функц. |")
    plan = build_plan(draft_task)
    assert plan.new == ["R-04", "IM-05"]
    assert _sections(plan) == [("05-changes", ["IM-05"], False), ("06-api", ["IM-05"], False), ("12-acceptance", ["R-04"], False)]


def test_accepted_review_and_human_section(draft_task):
    write_review(draft_task, [
        "| RV-01 | важно | 06-api | Нет кода | IM-01 | указать код | принято |",
        "| RV-02 | совет | весь черновик | Стиль | — | править | принято |",
        "| RV-03 | совет | 06-api | Мелочь | — | x | открыто |",
    ])
    (draft_task / "draft/06-api.md").write_text("## API\n\nПравка аналитика ‹R-01›\n", encoding="utf-8")
    plan = build_plan(draft_task)
    assert plan.accepted == ["RV-01", "RV-02"]
    assert _sections(plan) == [("06-api", ["RV-01"], True)]
    assert plan.unbound == ["RV-02"]
    assert "06-api | правка человека — только предложение | RV-01" in render_plan(plan)


def test_closed_placeholder_without_decision(draft_task):
    _rebuild(draft_task, "09-errors", "## Ошибки и исключения\n\nТекст ⚠ Q-PO-01 ‹R-01›\n")
    assert _sections(build_plan(draft_task)) == [("09-errors", ["⚠ Q-PO-01 закрыт"], False)]


def test_no_snapshot(draft_task):
    state = load_state(draft_task)
    del state["rows"]
    save_state(draft_task, state)
    plan = build_plan(draft_task)
    assert plan.snapshot is False and plan.new == []
    assert render_plan(plan).startswith("Снимка строк нет")


def test_proposal_diff_apply_drop(draft_task):
    api = draft_task / "draft/06-api.md"
    api.write_text("## API\n\nПравка ‹R-01›\n", encoding="utf-8")
    assemble(draft_task)
    proposals = draft_task / "proposals"
    proposals.mkdir()
    (proposals / "06-api.md").write_text("## API\n\nНовая версия ‹R-01›\n", encoding="utf-8")
    diff = proposal_diff(draft_task, "06-api")
    assert "-Правка ‹R-01›" in diff and "+Новая версия ‹R-01›" in diff
    assert build_plan(draft_task).proposals == ["06-api"]
    apply_proposal(draft_task, "06-api")
    assert api.read_text(encoding="utf-8") == "## API\n\nНовая версия ‹R-01›\n"
    assert not (proposals / "06-api.md").exists()
    assemble(draft_task)
    assert load_state(draft_task)["sections"]["06-api"]["edited_by_human"] is False
    (proposals / "05-changes.md").write_text("x", encoding="utf-8")
    drop_proposal(draft_task, "05-changes")
    assert not (proposals / "05-changes.md").exists()
    with pytest.raises(ArtifactError, match="нет предложения proposals/09-errors.md"):
        proposal_diff(draft_task, "09-errors")


def test_published_warning(draft_task):
    set_value(draft_task, "published", "https://wiki/x")
    assert build_plan(draft_task).published == (
        "Опубликовано: https://wiki/x. Правки в Confluence не подтягиваются — "
        "перед повторной публикацией сверь страницу вручную."
    )
    _rebuild(draft_task, "04-scenarios", "## Сценарии\n\nДругое ‹R-01›\n")
    assert build_plan(draft_task).published.startswith("Опубликовано: https://wiki/x — черновик изменился после публикации.")


def test_needs_draft(task_dir):
    with pytest.raises(ArtifactError, match="нет draft.md"):
        build_plan(task_dir)


def test_cli(draft_task, capsys):
    assert main(["plan", str(draft_task)]) == 0
    assert "Секции к обновлению: нет" in capsys.readouterr().out
    assert main(["diff", str(draft_task), "06-api"]) == 1
    assert main(["plan"]) == 2
    assert main([]) == 2
```

`tests/test_sa_state.py` (в конец):

```python
def test_set_published(draft_task):
    from sa_state import file_sha1, set_value

    state = set_value(draft_task, "published", "https://wiki/page/1")
    assert state["published"] == {"url": "https://wiki/page/1", "hash": file_sha1(draft_task / "draft-publish.md")}


def test_set_published_needs_publish_file(task_dir):
    from sa_state import set_value

    with pytest.raises(ArtifactError, match="нет draft-publish.md"):
        set_value(task_dir, "published", "https://wiki/page/1")
```

`tests/test_sa_validate.py` (в конец):

```python
def test_state_published():
    base = {"task": "X", "stage": "draft", "plugin_version": "0.1.0"}
    assert validate_state({**base, "published": {"url": "https://w/1", "hash": "a" * 40}}) == []
    errors = validate_state({**base, "published": {"url": "", "hash": "x"}})
    assert "published.url: непустая ссылка на страницу" in errors
    assert "published.hash: ожидается sha1" in errors
```

`tests/test_skills_contract.py`: в `test_tdd_draft_contract` добавь `"sa_state.py set tasks/<KEY> published"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sa_update.py tests/test_sa_state.py tests/test_sa_validate.py tests/test_skills_contract.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sa_update'`, `ключ published менять нельзя`.

- [ ] **Step 3: Implement**

`scripts/sa_state.py` в `set_value` перед `elif key.startswith("access.")`:

```python
    elif key == "published":
        publish = task_dir / PUBLISH_FILE
        if not value.strip():
            raise ArtifactError("published: нужна ссылка на страницу")
        if not publish.exists():
            raise ArtifactError(f"нет {PUBLISH_FILE} — сначала sa_draft.py assemble")
        state["published"] = {"url": value, "hash": file_sha1(publish)}
```

и в сообщении об ошибке ключа: `"допустимы: stage, template, published, "`; в `USAGE` строку `set` дополни: `  sa_state.py set <папка задачи> <ключ> <значение>   # stage, template, published, access.<система>`.

`scripts/sa_validate.py` в `validate_state` после блока `access`:

```python
    published = data.get("published")
    if published is not None:
        if not isinstance(published, dict):
            errors.append("published: ожидается объект")
        else:
            if not (isinstance(published.get("url"), str) and published["url"].strip()):
                errors.append("published.url: непустая ссылка на страницу")
            if not _is_sha1(published.get("hash")):
                errors.append("published.hash: ожидается sha1")
```

`scripts/sa_update.py`:

```python
"""Точечное обновление черновика: что изменилось с последней сборки и какие секции это затрагивает."""
from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError, find_refs
from sa_draft import (
    block_section, is_human, mark, placeholders, release, row_hashes, scope_of, section_path, section_texts,
    task_data, task_manifest, trace_refs,
)
from sa_review import review_rows
from sa_state import ARTIFACTS, PUBLISH_FILE, file_sha1, load_state, write_atomic

PROPOSALS_DIR = "proposals"
HUMAN = "правка человека — только предложение"
REGENERATE = "перегенерировать"


@dataclass
class SectionUpdate:
    id: str
    reasons: list[str]
    human: bool


@dataclass
class UpdatePlan:
    snapshot: bool
    new: list[str]
    changed: list[str]
    removed: list[str]
    accepted: list[str]
    sections: list[SectionUpdate]
    unbound: list[str]
    proposals: list[str]
    published: str | None


def _published(task_dir: Path, state: dict) -> str | None:
    published = state.get("published")
    if not isinstance(published, dict):
        return None
    publish = task_dir / PUBLISH_FILE
    changed = not publish.exists() or file_sha1(publish) != published.get("hash")
    return (
        f"Опубликовано: {published.get('url')}"
        + (" — черновик изменился после публикации" if changed else "")
        + ". Правки в Confluence не подтягиваются — перед повторной публикацией сверь страницу вручную."
    )


def build_plan(task_dir: Path) -> UpdatePlan:
    if not (task_dir / ARTIFACTS["draft"]).exists():
        raise ArtifactError("нет draft.md — сначала /tdd-draft")
    state = load_state(task_dir)
    manifest = task_manifest(state)
    data = task_data(task_dir)
    texts = section_texts(task_dir, manifest)
    current = row_hashes(task_dir)
    old = state.get("rows") if isinstance(state.get("rows"), dict) else None
    snapshot = old is not None
    old = old if snapshot else current
    new = [i for i in current if i not in old]
    changed = [i for i in current if i in old and old[i] != current[i]]
    removed = [i for i in old if i not in current]

    reasons: dict[str, list[str]] = {s.id: [] for s in manifest.sections}

    def add(sid: str | None, reason: str) -> bool:
        if sid not in reasons:
            return False
        if reason not in reasons[sid]:
            reasons[sid].append(reason)
        return True

    traces = {sid: set(trace_refs(text)) for sid, text in texts.items()}
    holders = {sid: {q for q in placeholders(text) if q} for sid, text in texts.items()}
    questions = {q.id: q for q in data["questions"]}
    decisions = {row["ID"]: row for row in data["decisions"]}
    impact = {row["ID"]: row for row in data["impact"]}
    unbound: list[str] = []

    for ref in changed + removed:
        for sid, refs in traces.items():
            if ref in refs:
                add(sid, ref)
    for ref in new:
        hit = False
        if ref.startswith("D-"):
            row = decisions[ref]
            q_ids = [r for r in find_refs(row["← Q"]) if r.startswith("Q-")]
            for sid in texts:
                held = [q for q in q_ids if q in holders[sid]]
                if held:
                    hit = add(sid, f"{ref} (⚠ {', '.join(held)})") or hit
            if not hit:
                links = {r for q in q_ids if q in questions for r in questions[q].refs}
                links |= {r for r in find_refs(row["Решение"]) if not r.startswith("Q-")}
                for sid, refs in traces.items():
                    if links & refs:
                        hit = add(sid, ref) or hit
        elif ref.startswith("IM-"):
            if scope_of(data, ref) == "вне скоупа":
                continue
            for s in manifest.sections:
                if impact[ref]["Вид"] in s.im_kinds:
                    hit = add(s.id, ref) or hit
            hit = add(block_section(manifest, "changes"), ref) or hit
        else:
            hit = add(block_section(manifest, "acceptance"), ref)
        if not hit:
            unbound.append(ref)

    for sid, held in holders.items():
        for q in sorted(held):
            if q in questions and questions[q].status != "open" and not any(q in r for r in reasons[sid]):
                add(sid, f"⚠ {q} закрыт")

    accepted: list[str] = []
    if (task_dir / ARTIFACTS["review"]).exists():
        for row in review_rows(task_dir):
            if row["Статус"] == "принято":
                accepted.append(row["ID"])
                if not add(row["Где"], row["ID"]):
                    unbound.append(row["ID"])

    entries = state.get("sections") if isinstance(state.get("sections"), dict) else {}
    sections = [
        SectionUpdate(s.id, reasons[s.id], is_human(entries.get(s.id), section_path(task_dir, s.id)))
        for s in manifest.sections if reasons[s.id] and s.id in texts
    ]
    proposals_dir = task_dir / PROPOSALS_DIR
    proposals = sorted(p.stem for p in proposals_dir.glob("*.md")) if proposals_dir.is_dir() else []
    return UpdatePlan(snapshot, new, changed, removed, accepted, sections, unbound, proposals, _published(task_dir, state))


def _none(items: list[str]) -> str:
    return ", ".join(items) if items else "нет"


def render_plan(plan: UpdatePlan) -> str:
    if plan.snapshot:
        lines = [f"Изменения с последней сборки: новые {_none(plan.new)}; изменены {_none(plan.changed)}; удалены {_none(plan.removed)}"]
    else:
        lines = ["Снимка строк нет (черновик собран до /tdd-update) — изменения BRD, карты и решений не отслежены"]
    lines.append(f"Принятые замечания: {_none(plan.accepted)}")
    if plan.sections:
        lines.append("Секции к обновлению:")
        lines += [f"{s.id} | {HUMAN if s.human else REGENERATE} | {', '.join(s.reasons)}" for s in plan.sections]
    else:
        lines.append("Секции к обновлению: нет")
    if plan.unbound:
        lines.append(f"Без привязки: {', '.join(plan.unbound)} — реши по тексту, какие секции они меняют, или спроси аналитика")
    if plan.proposals:
        lines.append(f"Предложения ждут решения: {', '.join(plan.proposals)}")
    if plan.published:
        lines.append(plan.published)
    return "\n".join(lines)


def _proposal(task_dir: Path, sid: str) -> Path:
    path = task_dir / PROPOSALS_DIR / f"{sid}.md"
    if not path.exists():
        raise ArtifactError(f"нет предложения {PROPOSALS_DIR}/{sid}.md")
    return path


def proposal_diff(task_dir: Path, sid: str) -> str:
    proposal = _proposal(task_dir, sid)
    current = section_path(task_dir, sid)
    old = current.read_text(encoding="utf-8").splitlines(keepends=True) if current.exists() else []
    lines = difflib.unified_diff(old, proposal.read_text(encoding="utf-8").splitlines(keepends=True),
                                 f"draft/{sid}.md", f"{PROPOSALS_DIR}/{sid}.md")
    return "".join(lines) or "отличий нет"


def apply_proposal(task_dir: Path, sid: str) -> None:
    proposal = _proposal(task_dir, sid)
    release(task_dir, [sid])
    write_atomic(section_path(task_dir, sid), proposal.read_text(encoding="utf-8"))
    mark(task_dir, [sid])
    proposal.unlink()


def drop_proposal(task_dir: Path, sid: str) -> None:
    _proposal(task_dir, sid).unlink()


USAGE = (
    "использование:\n"
    "  sa_update.py plan <папка задачи>\n"
    "  sa_update.py diff <папка задачи> <секция>\n"
    "  sa_update.py apply <папка задачи> <секция>\n"
    "  sa_update.py drop <папка задачи> <секция>"
)


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if not ((command == "plan" and len(argv) == 2) or (command in ("diff", "apply", "drop") and len(argv) == 3)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "plan":
            print(render_plan(build_plan(task_dir)))
        elif command == "diff":
            print(proposal_diff(task_dir, argv[2]))
        elif command == "apply":
            apply_proposal(task_dir, argv[2])
            print(f"предложение принято: draft/{argv[2]}.md")
        else:
            drop_proposal(task_dir, argv[2])
            print(f"предложение отклонено: {argv[2]}")
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`skills/tdd-draft/SKILL.md`, шаг 8: после «создай или обнови страницу «ТЗ <KEY>» …» добавь «; после публикации — `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> published <ссылка на страницу>`».

`shared/schemas/artifacts.md`:
- в «state.json» пункт: «`published`: `{"url": <ссылка>, "hash": <sha1 draft-publish.md>}` — страница опубликована; пишет `sa_state.py set <папка задачи> published <ссылка>`. Правки на странице не подтягиваются: перед повторной публикацией аналитик сверяет страницу вручную.» и в блок команд: `python3 <плагин>/scripts/sa_state.py set <папка задачи> published <ссылка>`;
- в конец «draft/ и draft.md»: «`proposals/<id секции>.md` — предложение `/tdd-update` для секции с правкой человека; `sa_update.py diff|apply|drop tasks/<KEY> <секция>` показывает, принимает (по слову аналитика) или отклоняет его. Валидатор `proposals/` не проверяет.»

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sa_update.py scripts/sa_state.py scripts/sa_validate.py skills/tdd-draft/SKILL.md shared/schemas/artifacts.md tests/test_sa_update.py tests/test_sa_state.py tests/test_sa_validate.py tests/test_skills_contract.py
git commit -m "feat: sa_update.py finds affected sections by trace and row snapshot; proposals; published mark"
```

---

### Task 5: Задача LKP-REVIEW для e2e — черновик с подложенными дефектами

Собирается скриптом из `LKP-DEMO` (хэши в `state.json` вычисляются при сборке, поэтому готовую папку не храним). Подложенные дефекты:

| # | Дефект | Кто найдёт |
|---|---|---|
| 1 | `R-03` нет ни в одном AC | `precheck`, критично |
| 2 | `IM-03` не описан ни в одной секции | `precheck`, важно |
| 3 | `⚠ Q-PO-02` на закрытом вопросе (после сборки пришёл ответ `D-02`) | `precheck`, важно |
| 4 | `06-api`: код `400`, `09-errors`: код `422` для той же ситуации | ревьюер, проход 4 |
| 5 | `05-changes`: «пересчитываем вознаграждения» против `D-01` | ревьюер, проход 4 |
| 6 | `AC-02`: «сохраняется быстро и удобно» | ревьюер, проход 5 |
| 7 | `05-changes`: «правило проверяет только формат [as is]» — в коде ещё и существование | `--code`, source-reader |

`06-api` после сборки поправлен «человеком» и пересобран — `edited_by_human: true` (проверка фикса I6). Для `/tdd-update`: новый `D-02` затрагивает секции с `⚠ Q-PO-02` (`04-scenarios`, `09-errors`, `12-acceptance`).

**Files:**
- Create: `tests/fixtures/e2e/lkp-review/make_task.py`
- Create: `tests/fixtures/e2e/lkp-review/draft/{01-context,02-scope,03-roles,04-scenarios,05-changes,06-api,07-integrations,08-data,09-errors,10-nfr,11-migration,12-acceptance}.md`
- Test: `tests/test_e2e_fixture.py`

**Interfaces:**
- Consumes: `sa_draft.assemble`, `sa_state.set_value`, `sa_review.precheck`, `sa_update.build_plan`, `sa_validate.validate_task`.
- Produces: `make_task.build(tasks_dir: Path) -> Path` и CLI `python3 tests/fixtures/e2e/lkp-review/make_task.py <папка tasks>`.

- [ ] **Step 1: Write the failing test**

`tests/test_e2e_fixture.py`:

```python
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
    assert state["sections"]["06-api"]["edited_by_human"] is True
    problems = [f.problem for f in precheck(task)]
    assert "R-03 не покрыт ни одним критерием приёмки (есть в 04-scenarios, 09-errors)" in problems
    assert "IM-03 (новый/изм.) не описан ни в одной секции" in problems
    assert any(p == "⚠ Q-PO-02 стоит на закрытом вопросе" for p in problems)
    plan = build_plan(task)
    assert plan.new == ["D-02"]
    assert [s.id for s in plan.sections] == ["04-scenarios", "09-errors", "12-acceptance"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_e2e_fixture.py -q`
Expected: FAIL — `FileNotFoundError` на `make_task.py`.

- [ ] **Step 3: Create the fixture**

`tests/fixtures/e2e/lkp-review/make_task.py`:

```python
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
    api = task / "draft/06-api.md"
    api.write_text(api.read_text(encoding="utf-8").rstrip("\n") + "\n" + HUMAN_NOTE, encoding="utf-8")
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
```

Секции (`tests/fixtures/e2e/lkp-review/draft/`), каждая — ровно этот текст:

`01-context.md`:
```markdown
## Контекст и цель

Запретить партнёру указывать собственный промокод в клиентской анкете, чтобы вознаграждения не начислялись за собственные транзакции. ‹R-01›
```

`02-scope.md`:
```markdown
## Границы и допущения

| Пункт | Скоуп | Комментарий |
|---|---|---|
| Проверка принадлежности промокода ‹IM-01› | в скоупе | — |
| Правило валидации промокода в анкете ‹IM-02› | в скоупе | — |
| Событие сохранения анкеты ‹IM-04› | ? | ⚠ Q-SA-01 |

- Пересчёт уже начисленных вознаграждений не делаем. ‹D-01›
- ИНН в анкете заполнен к моменту ввода промокода. ‹R-01›
```

`03-roles.md`:
```markdown
## Роли и доступы

Не применимо: роли и права доступа не меняются. ‹R-01›
```

`04-scenarios.md`:
```markdown
## Сценарии

### Сценарий 1. Партнёр указывает собственный промокод

1. [001] Партнёр заполняет клиентскую анкету и вводит промокод. ‹R-01›
2. [002] lkp-back вызывает проверку принадлежности промокода в partners-dashboard. ‹IM-01, IM-02›
3. [003] Промокод принадлежит партнёру — анкета не сохраняется, мерчант видит причину: ⚠ Q-PO-02 ‹R-02›

### Сценарий 2. Проверка недоступна

1. [001] partners-dashboard не отвечает — анкета сохраняется без проверки принадлежности. ‹R-03, IM-02›
```

`05-changes.md`:
```markdown
## Доработки по сервисам

### partners-dashboard

- Новый метод: принадлежит ли промокод партнёру с данным ИНН. ‹IM-01, R-01›

### lkp-back

- Правило валидации промокода проверяет только формат промокода [as is]. ‹IM-02›
- Правило дополнительно вызывает проверку принадлежности промокода [to be]. ‹IM-02, R-01›
- При сохранении анкеты пересчитываем вознаграждения, уже начисленные партнёру за собственные анкеты [to be]. ‹D-01›
```

`06-api.md`:
```markdown
## API

### POST /promocode/check-usage (partners-dashboard)

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| promocode | string | да | Промокод из анкеты ‹IM-01› |
| inn | string | да | ИНН из анкеты ‹IM-01› |

Ответ: `200` — промокод не принадлежит партнёру; `400` — промокод принадлежит партнёру с этим ИНН. ‹IM-01, R-01›
```

`07-integrations.md`:
```markdown
## Интеграции и события

Не применимо: новых интеграций нет; событие сохранения анкеты ждёт ответа ⚠ Q-SA-01. ‹IM-04›
```

`08-data.md`:
```markdown
## Данные

Не применимо: структура данных не меняется. ‹IM-02›
```

`09-errors.md`:
```markdown
## Ошибки и исключения

| Ситуация | Код | Текст для пользователя | Поведение |
|---|---|---|---|
| Промокод принадлежит партнёру | 422 | ⚠ Q-PO-02 | Анкета не сохраняется ‹R-01, R-02› |
| partners-dashboard недоступен | — | — | Анкета сохраняется без проверки ‹R-03› |
```

`10-nfr.md`:
```markdown
## Нефункциональные требования

Не применимо: требований к нагрузке и времени ответа в BRD нет. ‹R-01›
```

`11-migration.md`:
```markdown
## Миграция и запуск

Не применимо: миграция данных не нужна, начисления не пересчитываем. ‹D-01›
```

`12-acceptance.md`:
```markdown
## Критерии приёмки

### US-01

- AC-01. Условие: партнёр с промокодом `P1` заполняет анкету своего ИНН. Действие: указывает `P1`. Результат: анкета не сохраняется, мерчант видит текст ⚠ Q-PO-02. ‹R-01, R-02›
- AC-02. Условие: указан промокод другого партнёра. Действие: сохранить анкету. Результат: анкета сохраняется быстро и удобно. ‹R-01›

### Регресс

- AC-03. Условие: промокод не указан. Действие: сохранить анкету. Результат: анкета сохранена [as is]. ‹R-01›
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_e2e_fixture.py -q` → PASS (если упало на тексте `R-03 … (есть в …)` — сверь, что R-03 трассируется ровно в `04-scenarios` и `09-errors`); затем `.venv/bin/pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/e2e/lkp-review tests/test_e2e_fixture.py
git commit -m "test: LKP-REVIEW e2e task with planted review defects and a post-draft decision"
```

---

### Task 6: Субагенты — `tdd-reviewer` и режим сверки `source-reader`

**Files:**
- Create: `agents/tdd-reviewer.md`
- Modify: `agents/source-reader.md` (раздел «## Режим сверки»)
- Test: `tests/test_plugin_structure.py`

**Interfaces:**
- Consumes: `sa_review.SEVERITIES`, `WHOLE` (тест).
- Produces: агент `sa-skills:tdd-reviewer` — ответ из двух таблиц `| Важность | Где | Проблема | ← Ссылка | Предложение |` и `| RV | Вердикт |` (`закрыто`/`остаётся`); `source-reader` в режиме сверки — таблица `| Утверждение | Вердикт | Источник |` (`подтверждено`/`опровергнуто`/`не найдено`).

- [ ] **Step 1: Write the failing tests**

В конец `tests/test_plugin_structure.py`:

```python
def test_tdd_reviewer_contract():
    from sa_review import SEVERITIES, WHOLE

    text = (ROOT / "agents/tdd-reviewer.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert meta["model"] == "sonnet"
    assert set(t.strip() for t in meta["tools"].split(",")) == {"Read", "Grep", "Glob"}
    for value in (*SEVERITIES, *WHOLE, "закрыто", "остаётся"):
        assert f"`{value}`" in text, value
    for fragment in ("| Важность | Где | Проблема | ← Ссылка | Предложение |", "| RV | Вердикт |", "## Чек-лист", "[to be]"):
        assert fragment in text, fragment


def test_source_reader_verification_mode():
    text = (ROOT / "agents/source-reader.md").read_text(encoding="utf-8")
    assert "\n## Режим сверки\n" in text
    assert "| Утверждение | Вердикт | Источник |" in text
    for value in ("подтверждено", "опровергнуто", "не найдено"):
        assert f"`{value}`" in text, value
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_plugin_structure.py -q`
Expected: FAIL — `FileNotFoundError: agents/tdd-reviewer.md`.

- [ ] **Step 3: Write the agents**

`agents/tdd-reviewer.md`:

```markdown
---
name: tdd-reviewer
description: Независимый ревьюер черновика ТЗ с чистым контекстом — читает draft.md, BRD, карту влияния, решения, манифест шаблона и чек-листы блоков; ищет противоречия, непроверяемые критерии приёмки и пробелы по чек-листам; черновик не правит. Вызывается стадией /tdd-check.
tools: Read, Grep, Glob
model: sonnet
---

Ты — ревьюер ТЗ. Только читаешь: ничего не пишешь и не правишь.

## Вход

В задании тебе передают:
- абсолютные пути к `draft.md`, `sources/BRD.md`, `impact-map.md`, `decisions.md`, манифесту шаблона (`.yaml`) и папке блоков;
- замечания, которые уже нашёл скрипт (шаблон, плейсхолдеры, покрытие `R` и `IM`), — их не повторяй;
- прошлые замечания: «проверить» (`ID — Где — Проблема`) и «не поднимать».

## Как читать

1. `draft.md` прочитай целиком один раз — это главный вход. BRD, карту и решения — тоже целиком: они короткие.
2. В манифесте у каждой секции есть `block`. Для секций с блоком прочитай в `<папка блоков>/<block>.md` только раздел `## Чек-лист` (Grep с контекстом, не весь файл).
3. Код и другие файлы не читай.

## Проходы

1. Непротиворечивость: ТЗ против `decisions.md`; секция против секции — тексты ошибок, имена полей, коды ответов, статусы; ТЗ против BRD.
2. Проверяемость критериев приёмки: каждый `AC-xx` — условие, действие, ожидаемый результат; результат проверяем без толкований; нет оценочных слов («быстро», «удобно», «корректно», «при необходимости», «и т. п.»).
3. Полнота блоков: пункты `## Чек-лист` блока, которые в секции не выполнены.

Утверждения `[to be]` — целевое поведение: не оспаривай их тем, что «сейчас так не работает».

## Правила

- Каждое замечание: «Где» — id секции из манифеста, `шапка` или `весь черновик`; «← Ссылка» — ID из трассировки места или артефактов (`R-xx`, `IM-xx`, `D-xx`, `Q-PO-xx`, `Q-SA-xx`) через запятую.
- В «Проблеме» — доказательство: короткая цитата (до 10 слов), номер `AC-xx` или шага `[00x]`, ID решения. Без доказательства — важность `совет`.
- Важность: `критично` — противоречие с BRD или решением, неверное поведение для пользователя; `важно` — противоречие между секциями, непроверяемый критерий, невыполненный пункт чек-листа; `совет` — уточнения и стиль.
- Не предлагай требований, которых нет в BRD и решениях.
- Не используй `|` внутри ячеек — заменяй на «/».

## Что вернуть

Только две таблицы, без текста вне них.

| Важность | Где | Проблема | ← Ссылка | Предложение |
|---|---|---|---|---|

| RV | Вердикт |
|---|---|

Во второй — каждое замечание из «проверить»: `закрыто` — в черновике проблемы больше нет; `остаётся` — есть. Новых замечаний нет — первая таблица только с заголовком; «проверить» пуст — вторая только с заголовком.
```

В конец `agents/source-reader.md`:

```markdown
## Режим сверки

Если в задании вместо требований передан список утверждений `[as is]` — карту не строй. Для каждого утверждения найди в коде подтверждение или опровержение (тот же бюджет и те же правила чтения) и верни только таблицу:

| Утверждение | Вердикт | Источник |
|---|---|---|

- Утверждение — как передано, без изменений (`<секция>: <текст>`).
- Вердикт: `подтверждено`, `опровергнуто`, `не найдено`.
- Источник: `code: <репо>/<путь>:<строка>`; для `опровергнуто` после источника через « — » одна фраза, как в коде на самом деле; для `не найдено` — `—`.
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: PASS (включая `test_every_agent_has_frontmatter`, `test_no_shell_variables_in_prompts`).

- [ ] **Step 5: Commit**

```bash
git add agents/tdd-reviewer.md agents/source-reader.md tests/test_plugin_structure.py
git commit -m "feat: tdd-reviewer subagent and source-reader verification mode"
```

---

### Task 7: Скил `/tdd-check`

**Files:**
- Create: `skills/tdd-check/SKILL.md`
- Test: `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: `sa_paths.py`, `sa_status.py`, `sa_validate.py`, `sa_review.py precheck|coverage|asis`, `sa_ids.py next … RV`, `sa_state.py record … draft`, `sa_state.py set … stage check`, агенты `sa-skills:tdd-reviewer`, `sa-skills:source-reader`.

- [ ] **Step 1: Write the failing test**

В `tests/test_skills_contract.py` в конец:

```python
def test_tdd_check_contract():
    _assert_contains(
        _skill("tdd-check"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_status.py tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_review.py precheck tasks/<KEY>",
            "sa_review.py coverage tasks/<KEY>",
            "sa_review.py asis tasks/<KEY>",
            "sa_ids.py next tasks/<KEY> RV",
            "sa_state.py record tasks/<KEY> draft",
            "sa_state.py set tasks/<KEY> stage check",
            "sa-skills:tdd-reviewer",
            "sa-skills:source-reader",
            "--code",
            "<tasks_dir>/<KEY>/review.md",
            "`открыто`",
            "`принято`",
            "`отклонено`",
            "`закрыто`",
            "/tdd-update",
            "stage done",
        ),
    )
```

и в кортежи `test_stage_skills_use_sa_paths`, `test_stage_skills_read_shared_writing_rules`, `test_stage_skills_write_absolute_paths` добавь `"tdd-check"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_skills_contract.py -q`
Expected: FAIL — `FileNotFoundError: skills/tdd-check/SKILL.md`.

- [ ] **Step 3: Write `skills/tdd-check/SKILL.md`**

```markdown
---
name: tdd-check
description: Стадия 5 пайплайна ТЗ — независимое ревью черновика draft.md. Скрипт проверяет плейсхолдеры и покрытие требований и карты влияния, субагент tdd-reviewer с чистым контекстом ищет противоречия, непроверяемые критерии приёмки и пробелы по чек-листам блоков, с --code утверждения [as is] сверяются с кодом. Пишет review.md с замечаниями RV-xx и матрицей покрытия; при повторном запуске показывает закрытые и оставшиеся. Используй после /tdd-draft или /tdd-update, или когда аналитик пишет /tdd-check.
allowed-tools: Bash(python3:*)
---

# /tdd-check [KEY] [--code]

Входы: вывод `sa_review.py`, прошлый `review.md`; черновик, BRD, карту, решения и чек-листы читает ревьюер. Выход: `review.md`.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/rules/artifact-writing.md` и в `<плагин>/shared/schemas/artifacts.md` раздел «review.md». Черновик сам не читай и не правь — его читает ревьюер. `review.md` пиши только по абсолютному пути `<tasks_dir>/<KEY>/review.md`.

## Шаги

1. **Папка задачи.** `python3 <плагин>/scripts/sa_paths.py` — возьми `tasks_dir`, `repos_root`, `services`. Первый аргумент похож на ключ (`[A-Z][A-Z0-9]+-[0-9]+`) — `tasks/<KEY>`; иначе единственная задача в `tasks/`, при нескольких — спроси. `--code` во вводе включает шаг 5. Вместо ключа дали ссылку на страницу Confluence — скажи, что ревьюится локальный `draft.md`, и продолжай по ключу. `python3 <плагин>/scripts/sa_status.py tasks/<KEY>`: стадия должна быть `draft`, `check` или `done`, иначе скажи сначала запустить `/tdd-draft` и остановись.
2. **Валидатор.** `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>`. Ошибки не только в `review.md` — покажи их, предложи `/tdd-update` (или `/tdd-draft`) и остановись. Ошибки только в `review.md` — продолжай: файл перепишешь на шаге 6.
3. **Проходы скрипта.** `python3 <плагин>/scripts/sa_review.py precheck tasks/<KEY>` — первая строка `draft: <sha1>`, дальше таблица замечаний: шаблон, плейсхолдеры, покрытие `R` критериями приёмки и `IM` секциями. `python3 <плагин>/scripts/sa_review.py coverage tasks/<KEY>` — матрица покрытия.
4. **Ревьюер.** Если `review.md` есть — прочитай его: замечания `открыто` и `принято` — «проверить», `отклонено` — «не поднимать», `round` — номер прошлого прохода. Вызови субагента `sa-skills:tdd-reviewer` одним заданием:
   - абсолютные пути: `<tasks_dir>/<KEY>/draft.md`, `<tasks_dir>/<KEY>/sources/BRD.md`, `<tasks_dir>/<KEY>/impact-map.md`, `<tasks_dir>/<KEY>/decisions.md`; манифест `<плагин>/shared/templates/<тип>.yaml` (тип — из строки «шаблон» статуса, до `@`); папка блоков `<плагин>/shared/blocks/`;
   - таблица из вывода `precheck` — «уже найдено, не повторяй»;
   - «проверить» и «не поднимать» — строками `ID — Где — Проблема`.
   Ответ — две таблицы: новые замечания и вердикты по прошлым.
5. **Сверка с кодом** — только с `--code`. `python3 <плагин>/scripts/sa_review.py asis tasks/<KEY>` — утверждения `[as is]` по сервисам. Сервис есть в `services` — по субагенту `sa-skills:source-reader` на сервис, параллельно, в режиме сверки: путь `<repos_root>/<сервис>` и утверждения этого сервиса. Сервиса нет среди репозиториев или группа `без сервиса` — не сверяй, упомяни в итоге. Вердикт `опровергнуто` — новое замечание `важно`: Где — секция утверждения, ← Ссылка — `IM-xx` из утверждения, Проблема — «[as is] не подтверждается кодом: <источник и фраза>»; `не найдено` — `совет`.
6. **review.md.**
   - Прошлые строки оставь с ID и текстом, меняй только статус: замечание скрипта, которого нет в новом выводе `precheck` (та же Где и Проблема), и вердикт ревьюера `закрыто` — на `закрыто`. Строки `отклонено` и `закрыто` не трогай.
   - Новые строки — `precheck`, ревьюер и сверка с кодом; пропусти совпадающие с незакрытыми прошлыми (та же Где и Проблема) и дубли между собой.
   - ID новым — одним вызовом `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> RV <N>` (новых нет — без вызова), статус `открыто`.
   - Запиши `<tasks_dir>/<KEY>/review.md`: шапка `draft` (sha1 из первой строки `precheck`), `reviewed` (сегодня), `round` (прошлый + 1, первый раз 1); заголовок `# Ревью черновика <KEY>`; `## Замечания` — таблица по схеме; `## Покрытие BRD` — вывод `coverage` как есть.
7. **Проверка.** `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>` — исправляй `review.md`, пока не `OK`. Затем `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> draft` и `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage check`.
8. **Итог аналитику**, коротко:
   - число замечаний по важности; при повторном запуске — закрыто N (ID), осталось M (ID), новых K;
   - критичные — списком: ID, где, проблема;
   - строки матрицы без AC;
   - с `--code` — какие сервисы не сверены;
   - следующий шаг: принять и внести — `/tdd-update RV-01 RV-03` или `/tdd-update все`; отклонить — `/tdd-update отклонить RV-02`; после правок — снова `/tdd-check`. Замечаний `открыто` и `принято` нет — ТЗ готово: `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage done`.

## Чего не делать

- Не правь черновик, секции, `draft.md` — только `review.md`.
- Не меняй ID и тексты прошлых замечаний.
- Не ставь `принято` и `отклонено` сам — это решение аналитика.
- Не читай код сам — только через `source-reader` в режиме сверки.
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: PASS (включая `test_plugin_file_references_exist`: `shared/templates/<тип>.yaml` не матчится регэкспом из-за `<`; если матчится — замени упоминание на `<плагин>/shared/templates/` + «`<тип>.yaml`»).

- [ ] **Step 5: Commit**

```bash
git add skills/tdd-check/SKILL.md tests/test_skills_contract.py
git commit -m "feat: /tdd-check stage skill with clean-context reviewer and repeat-review statuses"
```

---

### Task 8: Скил `/tdd-update`, документация

**Files:**
- Create: `skills/tdd-update/SKILL.md`
- Modify: `shared/rules/artifact-writing.md` (список стадий), `README.md` (таблица команд, e2e)
- Test: `tests/test_skills_contract.py`

**Interfaces:**
- Consumes: `sa_review.py status`, `sa_update.py plan|diff|apply|drop`, `sa_draft.py plan|mark|assemble|gaps`, `sa_ids.py`, `sa_validate.py`, `sa_state.py record|set`, `sa_questions.py export`.

- [ ] **Step 1: Write the failing test**

В `tests/test_skills_contract.py`:

```python
def test_tdd_update_contract():
    _assert_contains(
        _skill("tdd-update"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_status.py tasks/<KEY>",
            "sa_review.py status tasks/<KEY> принято",
            "sa_review.py status tasks/<KEY> отклонено",
            "sa_update.py plan tasks/<KEY>",
            "sa_update.py diff tasks/<KEY>",
            "sa_update.py apply tasks/<KEY>",
            "sa_update.py drop tasks/<KEY>",
            "sa_draft.py plan tasks/<KEY>",
            "sa_draft.py mark tasks/<KEY>",
            "sa_draft.py assemble tasks/<KEY>",
            "sa_draft.py gaps tasks/<KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> BRD impact-map context questions",
            "sa_state.py set tasks/<KEY> stage draft",
            "sa_state.py set tasks/<KEY> published",
            "<tasks_dir>/<KEY>/draft/",
            "<tasks_dir>/<KEY>/proposals/",
            "‹R-01, IM-02, D-01›",
            "⚠ Q-",
            "правка человека",
            "Без привязки",
            "/tdd-check",
        ),
    )


def test_artifact_writing_lists_all_stages():
    text = (ROOT / "shared/rules/artifact-writing.md").read_text(encoding="utf-8")
    for stage in ("/tdd-impact", "/tdd-start", "/tdd-clarify", "/tdd-draft", "/tdd-check", "/tdd-update"):
        assert stage in text, stage
```

и в кортежи `test_stage_skills_use_sa_paths`, `test_stage_skills_read_shared_writing_rules`, `test_stage_skills_write_absolute_paths` добавь `"tdd-update"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_skills_contract.py -q`
Expected: FAIL — нет `skills/tdd-update/SKILL.md`, в artifact-writing нет `/tdd-check`.

- [ ] **Step 3: Write the skill and docs**

`skills/tdd-update/SKILL.md`:

```markdown
---
name: tdd-update
description: Точечное обновление черновика ТЗ — по новым и изменённым решениям, строкам BRD и карты влияния, закрытым вопросам и принятым замечаниям ревью находит затронутые секции через трассировку и перегенерирует только их; секции с правкой человека не перезаписывает, а предлагает diff. Принимает и отклоняет замечания review.md. Используй после /tdd-clarify с новыми ответами, после /tdd-check, или когда аналитик пишет /tdd-update.
allowed-tools: Bash(python3:*)
---

# /tdd-update [KEY] [RV-xx… | все] [отклонить RV-xx…] [прими/отклони предложение <секция>]

Входы: вывод `sa_update.py plan` и `sa_draft.py plan`, `context.md`, `decisions.md`, строки нужных ID из `sources/BRD.md`, `impact-map.md`, `review.md` (grep по ID, файлы целиком не читай), затронутые секции, блоки `shared/blocks/<блок>.md`. Выход: обновлённые `draft/<секция>.md`, `proposals/<секция>.md`, `draft.md`, `draft-publish.md`.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/rules/ai-rules.md`, `<плагин>/shared/rules/writing-style.md`, `<плагин>/shared/rules/artifact-writing.md` и в `<плагин>/shared/schemas/artifacts.md` разделы «draft/ и draft.md» и «review.md». Файлы пиши только по абсолютному пути: `<tasks_dir>/<KEY>/draft/<секция>.md`, `<tasks_dir>/<KEY>/proposals/<секция>.md`.

## Шаги

1. **Папка задачи.** `python3 <плагин>/scripts/sa_paths.py` — возьми `tasks_dir`. Первый аргумент похож на ключ (`[A-Z][A-Z0-9]+-[0-9]+`) — `tasks/<KEY>`; иначе единственная задача в `tasks/`, при нескольких — спроси. `python3 <плагин>/scripts/sa_status.py tasks/<KEY>`: стадия должна быть `draft`, `check` или `done`, иначе скажи сначала запустить `/tdd-draft` и остановись.
2. **Решения аналитика из ввода** — до плана, каждое отдельной командой:
   - `RV-xx …` или `все` — `python3 <плагин>/scripts/sa_review.py status tasks/<KEY> принято <RV-xx …|все>`;
   - `отклонить RV-xx …` — `python3 <плагин>/scripts/sa_review.py status tasks/<KEY> отклонено <RV-xx …>`;
   - «прими предложение <секция>» — `python3 <плагин>/scripts/sa_update.py apply tasks/<KEY> <секция>`; «отклони предложение <секция>» — `python3 <плагин>/scripts/sa_update.py drop tasks/<KEY> <секция>`.
3. **План.** `python3 <плагин>/scripts/sa_update.py plan tasks/<KEY>`:
   - «Секции к обновлению: нет» и на шаге 2 ничего не применено — скажи, что черновик актуален, и остановись; применено только предложение — сразу шаг 6;
   - «Без привязки» — для каждого ID реши по тексту решения или замечания, какие секции он меняет, и добавь их в работу; не можешь решить — спроси аналитика;
   - затем `python3 <плагин>/scripts/sa_draft.py plan tasks/<KEY>` — блоки и срезы `R` / `IM` / `D` секций. Прочитай `context.md` и `decisions.md` один раз; принятые замечания — grep `RV-xx` в `review.md`.
4. **Перегенерировать** — каждая секция с этим статусом в плане:
   - прочитай секцию и `<плагин>/shared/blocks/<блок>.md`; строки новых и изменённых `R-xx` / `IM-xx` — grep по ID;
   - меняй только то, чего касаются причины из плана: плейсхолдер `⚠ Q-…` закрытого вопроса — текстом по решению; утверждение со ссылкой на изменённый или удалённый ID — по новой строке; принятое замечание — по его «Предложению». Остальной текст и трассировку не трогай;
   - правила те же, что в `/tdd-draft`: первая строка `## <название>`, каждое утверждение заканчивается трассировкой `‹R-01, IM-02, D-01›`, неизвестное — `⚠ Q-PO-xx` / `⚠ Q-SA-xx` с ID открытого вопроса, ничего не выдумывай;
   - записал — сразу `python3 <плагин>/scripts/sa_draft.py mark tasks/<KEY> <секция>`.
   Неизвестное без подходящего вопроса — собери списком, разведи по `question-routing.md`, ID — одним вызовом на вид `python3 <плагин>/scripts/sa_ids.py next tasks/<KEY> Q-PO <N>` (и `… Q-SA <N>`), допиши вопросы в `questions.md` по `artifact-writing.md` и поставь `⚠ <ID>` в секциях.
5. **Правка человека — только предложение.** Секцию с этим статусом не перезаписывай. Её новую версию по правилам шага 4 запиши в `<tasks_dir>/<KEY>/proposals/<секция>.md` и покажи `python3 <плагин>/scripts/sa_update.py diff tasks/<KEY> <секция>`.
6. **Сборка и проверка.** `python3 <плагин>/scripts/sa_draft.py assemble tasks/<KEY>` (автор берётся из `draft.md`). `python3 <плагин>/scripts/sa_validate.py tasks/<KEY>` — исправляй секции (после правки — `sa_draft.py mark`), собирай заново, пока не `OK`. Затем:
   - `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> BRD impact-map context questions` — если `decisions.md` нет;
   - `python3 <плагин>/scripts/sa_state.py record tasks/<KEY> BRD impact-map context questions decisions` — если есть;
   - `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> stage draft`.
7. **Публикация.** В плане есть строка «Опубликовано» — страница уже в Confluence, правки на ней сюда не подтягиваются. Не публикуй заново, пока аналитик не подтвердит, что на странице нет его правок. Подтвердил и режим `confluence` — `mcp`: обнови страницу содержимым `draft-publish.md` по `<плагин>/shared/access/adapters.md` и выполни `python3 <плагин>/scripts/sa_state.py set tasks/<KEY> published <ссылка>`. Иначе — дай путь `<tasks_dir>/<KEY>/draft-publish.md`.
8. **Итог аналитику**, коротко:
   - обновлённые секции с причинами из плана;
   - предложения для секций с правкой человека — вывод `diff` в блоке кода и как решить: `/tdd-update прими предложение <секция>` или `/tdd-update отклони предложение <секция>`;
   - вывод `python3 <плагин>/scripts/sa_draft.py gaps tasks/<KEY>` в блоке кода;
   - новые вопросы — `python3 <плагин>/scripts/sa_questions.py export tasks/<KEY> PO` и `… SA`, если заводились;
   - следующий шаг: `/tdd-check` — повторное ревью закроет внесённые замечания.

## Чего не делать

- Не перезаписывай секции с правкой человека и не снимай отметку сам — только `apply` по слову аналитика.
- Не трогай секции, которых нет в плане и в «Без привязки».
- Не меняй статусы замечаний без слова аналитика; `закрыто` ставит только `/tdd-check`.
- Не правь `draft.md` и `draft-publish.md` руками.
- Не выдумывай сервисы, методы, поля, тексты для пользователя, числа.
```

`shared/rules/artifact-writing.md`, первая строка после заголовка: «Общие для `/tdd-impact`, `/tdd-start`, `/tdd-clarify`, `/tdd-draft`, `/tdd-check`, `/tdd-update`. Правила маршрутизации — в `question-routing.md`.»

`README.md`:
- в таблице команд статусы `/tdd-check` и `/tdd-update` — `готово`; описание `/tdd-check [KEY] [--code]` — «Независимое ревью черновика: review.md, матрица покрытия», `/tdd-update [KEY] [RV-xx…]` — «Точечное обновление черновика по решениям и замечаниям»;
- в «Сквозная проверка стадий» после блока `/tdd-draft`:

````markdown
Ревью и обновление по задаче с подложенными дефектами (`tests/fixtures/e2e/lkp-review/make_task.py` — список дефектов в его плане):

```bash
python3 $REPO/tests/fixtures/e2e/lkp-review/make_task.py /tmp/sa-e2e/tasks
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-check LKP-REVIEW --code"
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-update LKP-REVIEW все"
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-check LKP-REVIEW"
python3 $REPO/scripts/sa_validate.py tasks/LKP-REVIEW
```
````

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/tdd-update/SKILL.md shared/rules/artifact-writing.md README.md tests/test_skills_contract.py
git commit -m "feat: /tdd-update stage skill; docs for check/update"
```

---

### Task 9: Ревью ветки и e2e (контроллер, не субагент)

- [ ] **Step 1:** Одно ревью всей ветки (`superpowers:requesting-code-review`, субагент `sonnet`), исправления одним заходом, `.venv/bin/pytest -q` → PASS.

- [ ] **Step 2: E2E**, в короткой рабочей папке, по одной команде на вызов:

```bash
rm -rf /tmp/sa-e2e
mkdir -p /tmp/sa-e2e/tasks
python3 <repo>/tests/fixtures/e2e/lkp-review/make_task.py /tmp/sa-e2e/tasks
```

Из `/tmp/sa-e2e`, с `SA_REPOS_ROOT=<repo>/tests/fixtures/e2e/repos`:

```bash
claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/tdd-check LKP-REVIEW --code"
```

Ожидается: `sa_validate.py tasks/LKP-REVIEW` → `OK`; в `review.md` `round: 1`, замечания на дефекты 1–3 (из `precheck`), минимум два из 4–6 (ревьюер), дефект 7 (`опровергнуто`, `05-changes`); `stage: check`.

```bash
claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/tdd-update LKP-REVIEW все"
```

Ожидается: `OK`; в `04-scenarios`, `09-errors`, `12-acceptance` нет `⚠ Q-PO-02`, есть `‹…D-02›`; `draft/06-api.md` не изменён (sha1 до и после совпадает), есть `proposals/06-api.md`, если принятое замечание касалось `06-api`; `stage: draft`.

```bash
claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/tdd-check LKP-REVIEW"
```

Ожидается: `OK`; `round: 2`; прошлые ID сохранены, исправленные — `закрыто`, итог называет закрытые и оставшиеся.

- [ ] **Step 3:** Расхождения — исправить скилы/скрипты, `pytest`, повторить только упавший шаг e2e. Затем `superpowers:finishing-a-development-branch`.

---

## Отложено (не входит в подпроект)

- Подтягивание опубликованной страницы Confluence и посекционная сверка; `/tdd-check <страница>`.
- REST-публикация в Confluence; параллельные субагенты для больших секций.
- Долги SP3: unicode-разделители строк → вечное «устарел»; `im_kinds` не сверяются с `KINDS`; `_question_statuses` глотает `ArtifactError`; падения на нечитаемых файлах; `@diagram` с отступом или `\r`; валидатор не сверяет версию манифеста; синтаксис каркасов `puml-*` не проверен реальным PlantUML; `sa_fetch.py` не запускался против реальных Jira/Confluence.
- Повторная перегенерация по замечаниям `принято`, пока `/tdd-check` их не закрыл (план продолжает их показывать).
