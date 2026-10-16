# SA Skills: стадии QA — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в sa-skills стадии `/qa-cases`, `/qa-check`, `/qa-export`, `/qa-update`, которые по готовому ТЗ задачи делают ручные тест-кейсы, проверяют покрытие, выгружают CSV для Allure и обновляют кейсы при изменении ТЗ.

**Architecture:** Детерминированная часть — три новых модуля Python (единицы покрытия, разбор и проверка кейсов, CLI QA-стадий) и расширения существующих (`sa_artifacts`, `sa_ids`, `sa_validate`, `sa_status`). Генерация и правка текста кейсов — в SKILL.md стадий (модель), чтение кода — субагент `source-reader`, независимое ревью — новый агент `qa-reviewer`. Все артефакты QA — в `tasks/<KEY>/qa/`.

**Tech Stack:** Python ≥ 3.10, только стандартная библиотека; pytest; Claude Code plugin (skills, agents).

**Spec:** `docs/superpowers/specs/2026-10-17-sa-skills-qa-design.md`

## Global Constraints

- Python ≥ 3.10, только стандартная библиотека; скрипты вызываются как `python3 <плагин>/scripts/<скрипт>.py`.
- Тесты: `python -m pytest -q` — всё зелёное; известное исключение на Windows — `tests/test_sa_paths.py::test_format`.
- Путь к задачам — только из `sa_paths.py` (`tasks_dir`); стадии QA пишут только в `tasks/<KEY>/qa/`, файлы аналитика не меняют.
- ID: `TC-xx` (кейс), `U-xx` (единица покрытия), `Q-QA-xx` (вопрос QA аналитику), `QV-xx` (замечание ревью QA); минимум две цифры, сквозная нумерация в задаче, не переиспользуются.
- Колонки CSV дословно: `ID, Name, Description, Precondition, Scenario, Expected result, Priority, Status`; `Status` = `Draft`; `ID` = `<KEY>-TC-xx`.
- Приоритеты: `High`, `Medium`, `Low`. Вид кейса: `бэкенд`, `фронт`, `регресс`.
- Статусы единиц: пусто (тестируется), `не поведение`, `не тестируется`, `нужно решение`, `удал.`; для всех, кроме пустого и `удал.`, причина обязательна.
- Выгрузка в Allure — только после явного «загружай»; сейчас только CSV.
- Заметная правка плагина — поднять `version` в `.claude-plugin/plugin.json` до `0.5.0` и в тестах, которые её проверяют.

## Review Focus

1. `qa/cases.md` после ручной правки с ошибкой формата (нет поля, лишний текст между полями, json-блок в шаге) — разбор даёт понятную ошибку с ID кейса, а не падение. Тест — задача 3.
2. ТЗ поменялось: пункт переформулирован или сдвинулся номер — существующий `U-xx` сохраняется, а не появляется новый ID с осиротевшими кейсами. Тест — задача 2.
3. В тексте кейса запятые, кавычки, «ёлочки», переводы строк и JSON — CSV остаётся валидным и читается обратно `csv.reader` без потерь. Тест — задача 4.
4. У задачи нет папки `qa/` (все текущие задачи) — `sa_validate` и `sa_status` работают как раньше, без новых ошибок и строк. Тест — задача 5.
5. Кейс удалён руками или ссылается на единицу со статусом `удал.` — проверка показывает непокрытую единицу и висячую ссылку, ничего не восстанавливает. Тест — задача 4.

---

### Task 1: ID и ссылки QA

**Files:**
- Modify: `scripts/sa_artifacts.py` (`REF_RE`, `ID_PATTERNS`)
- Modify: `scripts/sa_ids.py` (`KINDS`, пути QA)
- Test: `tests/test_sa_ids.py`, `tests/test_sa_artifacts.py`

**Interfaces:**
- Produces: `sa_ids.next_ids(task_dir, kind, count)` принимает виды `TC`, `U`, `Q-QA`, `QV`; файлы — `qa/cases.md`, `qa/units.md`, `qa/questions.md`, `qa/review.md`. `sa_artifacts.find_refs` находит `Q-QA-xx`; `ID_PATTERNS` получает ключи `"TC"`, `"U"`, `"QV"`, а `"Q"` матчит `Q-QA-xx`.

- [ ] **Step 1: Тесты**

```python
def test_next_ids_qa_kinds(task_dir):
    qa = task_dir / "qa"; qa.mkdir()
    (qa / "cases.md").write_text("### TC-01 a\n### TC-07 b\n", encoding="utf-8")
    assert next_ids(task_dir, "TC", 2) == ["TC-08", "TC-09"]
    assert next_ids(task_dir, "U") == ["U-01"]
    assert next_ids(task_dir, "Q-QA") == ["Q-QA-01"]
    assert next_ids(task_dir, "QV") == ["QV-01"]

def test_find_refs_q_qa():
    assert find_refs("[Q-QA-03] и R-01") == ["Q-QA-03", "R-01"]
```

- [ ] **Step 2:** `python -m pytest tests/test_sa_ids.py tests/test_sa_artifacts.py -q` — FAIL.
- [ ] **Step 3:** В `sa_ids.py` добавить `QA_FILES = {"TC": "qa/cases.md", "U": "qa/units.md", "Q-QA": "qa/questions.md", "QV": "qa/review.md"}`; `next_ids` берёт путь из `QA_FILES`, иначе из `ARTIFACTS`; обновить `USAGE`. В `sa_artifacts.py` расширить `REF_RE` и `ID_PATTERNS` на `Q-QA`, `TC`, `U`, `QV`, не меняя поведения для старых видов.
- [ ] **Step 4:** `python -m pytest -q` — PASS (кроме известного исключения).
- [ ] **Step 5:** `git commit -m "feat(qa): ID TC, U, Q-QA, QV"`

### Task 2: Единицы покрытия

**Files:**
- Create: `scripts/sa_qa_units.py`
- Create: `tests/fixtures/qa/` — секции `01-brd.md`, `03-changes.md`, `08-testing.md` (урезанная копия PF2-3964: 2 истории, 1 Front-экран, 1 Back-сервис с вложенными подпунктами, 3+2 пункта тестирования)
- Test: `tests/test_sa_qa_units.py`

**Interfaces:**
- Produces:
  - `@dataclass Unit(id: str, where: str, text: str, refs: list[str], status: str = "", reason: str = "")`; `where` — локатор: `01-brd/story-<n>/<k>`, `01-brd/ui/<n>`, `03-changes/<сервис>/Back/<1.3.2>`, `03-changes/<сервис>/Front/<экран>/<1.2>`, `08-testing/new/<n>`, `08-testing/keep/<n>`.
  - `extract_units(task_dir: Path) -> list[Unit]` — без ID, детерминированно, в порядке документа.
  - `load_units(task_dir: Path) -> list[Unit]` — из `qa/units.md`.
  - `sync_units(task_dir: Path) -> list[Unit]` — сопоставляет извлечённые с сохранёнными и пишет `qa/units.md`.
  - `qa/units.md` — таблица `| ID | Где | Пункт | Статус | Причина |`.

- [ ] **Step 1: Тесты**

```python
def test_extract_units_sources(qa_task):
    where = [u.where for u in extract_units(qa_task)]
    assert "01-brd/story-1/1" in where
    assert any(w.startswith("03-changes/payform.payment.saleschannels/Back/1.") for w in where)
    assert "08-testing/new/1" in where and "08-testing/keep/1" in where

def test_extract_units_keeps_trace(qa_task):
    u = next(u for u in extract_units(qa_task) if u.where == "08-testing/new/1")
    assert "R-01" in u.refs and "‹" not in u.text

def test_sync_assigns_and_keeps_ids(qa_task):
    first = sync_units(qa_task)
    assert first[0].id == "U-01"
    # переформулировали пункт и вставили новый перед ним
    edit_testing(qa_task, insert_first="Новый пункт ‹R-02›", reword=("сразу отображается", "отображается сразу"))
    second = {u.text: u.id for u in sync_units(qa_task)}
    assert second[reworded_text] == first_id_of_reworded  # ID сохранён
    assert second["Новый пункт"] not in {u.id for u in first}

def test_sync_marks_removed_and_keeps_human_status(qa_task):
    units = sync_units(qa_task)
    set_status_in_file(qa_task, units[0].id, "не тестируется", "нет стенда")
    remove_item(qa_task, units[1].where)
    after = {u.id: u for u in sync_units(qa_task)}
    assert after[units[0].id].status == "не тестируется"
    assert after[units[1].id].status == "удал."
```

(`qa_task` — фикстура в `conftest.py`: копия LKP-DEMO + `tests/fixtures/qa/*` в `draft/`; хелперы `edit_testing`, `set_status_in_file`, `remove_item` — в тестовом модуле.)

- [ ] **Step 2:** `python -m pytest tests/test_sa_qa_units.py -q` — FAIL.
- [ ] **Step 3:** Реализовать `sa_qa_units.py`. Извлечение: пункты `•` в колонке «Критерии приемки» таблицы User Stories; нумерованные пункты под `## Требования к UI`; под `**1. Описание изменений:**` и `**Что изменить:**` — все пункты и подпункты любой глубины (маркированные — с номером позиции); под `## Новое поведение` и `## Сохраняемое поведение`. Трассировка `‹…›` вырезается из `text` в `refs`. Сопоставление при `sync_units`: сначала точное совпадение `text`, затем тот же `where` с похожим текстом (`difflib.SequenceMatcher` ratio ≥ 0.6), иначе новый ID через `next_ids(task_dir, "U", n)`; несопоставленные сохранённые — статус `удал.`; статус и причина из файла не перезаписываются.
- [ ] **Step 4:** `python -m pytest -q` — PASS.
- [ ] **Step 5:** `git commit -m "feat(qa): единицы покрытия из ТЗ"`

### Task 3: Разбор и проверка кейсов

**Files:**
- Create: `scripts/sa_qa_cases.py`
- Create: `tests/fixtures/qa/cases.md` (3 кейса: бэкенд с json-телом, фронт, регресс)
- Test: `tests/test_sa_qa_cases.py`

**Interfaces:**
- Produces:
  - `@dataclass Case(id: str, title: str, kind: str, priority: str, covers: list[str], sources: list[str], description: str, preconditions: str, steps: list[str], expected: str, raw: str)`
  - `parse_cases(text: str) -> list[Case]` — формат из спеки §7 (`### TC-xx <название>`, строки `- **Вид:**`, `- **Приоритет:**`, `- **Покрывает:**`, `- **Источник:**`, блоки `**Описание:**`, `**Предусловия:**`, `**Шаги:**` (нумерованный список, внутри шага допустим fenced-блок), `**Ожидаемый результат:**`); кейс без `TC-xx` в заголовке — `id=""`. Ошибка формата — `ArtifactError` с ID/заголовком кейса.
  - `lint_case(case: Case) -> list[str]`
  - `case_hash(case: Case) -> str` — sha1 от `raw` с нормализованными концами строк.

- [ ] **Step 1: Тесты**

```python
def test_parse_fixture():
    cases = parse_cases(FIXTURE.read_text(encoding="utf-8"))
    assert [c.id for c in cases] == ["TC-01", "TC-02", "TC-03"]
    assert cases[0].kind == "бэкенд" and cases[0].covers == ["U-01", "U-04"]
    assert '"merchantId"' in cases[0].steps[0]          # json-тело внутри шага
    assert cases[0].expected.startswith("Ответ `400`")

def test_parse_error_names_case():
    with pytest.raises(ArtifactError, match="TC-02"):
        parse_cases(FIXTURE.read_text(encoding="utf-8").replace("**Ожидаемый результат:**", "**Итог:**", 2))

def test_manual_case_without_id():
    assert parse_cases("### Проверка вручную\n\n- **Вид:** фронт\n...")[0].id == ""

@pytest.mark.parametrize("bad", ["Работает корректно", "Отображается правильно", "Проверить, что работает", "и т.д.", "при необходимости"])
def test_lint_vague(bad):
    assert any("расплывчато" in e for e in lint_case(make_case(expected=bad)))

def test_lint_backend_needs_code():
    assert lint_case(make_case(kind="бэкенд", expected="Файл сохранён"))
    assert not lint_case(make_case(kind="бэкенд", expected="Ответ `200`, в теле `documentId`"))

def test_lint_required_fields():
    errs = lint_case(make_case(description="", preconditions="", steps=[], covers=[]))
    assert {"описание", "предусловия", "шаги", "покрывает"} <= {e.split(":")[0] for e in errs}
```

- [ ] **Step 2:** `python -m pytest tests/test_sa_qa_cases.py -q` — FAIL.
- [ ] **Step 3:** Реализовать. Словарь расплывчатого — константа `VAGUE = ("корректно", "правильно", "проверить, что работает", "и т.д.", "при необходимости")` плюс «успешно», если в результате нет кода, «ёлочек» или `backtick`-значения. Бэкенд-кейс: в `expected` должен быть код ответа `\b[1-5]\d\d\b`. Префиксы ошибок `lint_case`: `описание:`, `предусловия:`, `шаги:`, `покрывает:`, `ожидаемый результат:`, `расплывчато:`, `приоритет:`, `вид:`.
- [ ] **Step 4:** `python -m pytest -q` — PASS.
- [ ] **Step 5:** `git commit -m "feat(qa): разбор и проверка тест-кейсов"`

### Task 4: CLI стадий QA — состояние, отметки, покрытие, CSV, задетые кейсы

**Files:**
- Create: `scripts/sa_qa.py`
- Test: `tests/test_sa_qa.py`

**Interfaces:**
- Consumes: `sync_units`, `load_units` (задача 2); `parse_cases`, `lint_case`, `case_hash` (задача 3); `sa_draft.row_hashes(task_dir)` для снимка строк ТЗ.
- Produces (функции и подкоманды `sa_qa.py <команда> <папка задачи> …`):
  - `qa/state.json`: `{"rows": {ID: sha1}, "cases": {TC: {"generated": sha1, "exported": sha1 | null}}}`.
  - `mark(task_dir, ids: list[str] | "все") -> list[str]` — записать `generated` и снимок `rows`; команда `mark`.
  - `human_cases(task_dir) -> list[str]` — кейсы, чей хэш не равен `generated`.
  - `coverage(task_dir) -> list[tuple[str, str, list[str]]]` — `(U-xx, статус, [TC…])`; `coverage_table(task_dir) -> str` (`| U | Статус | Кейсы |`); команда `coverage`.
  - `precheck(task_dir) -> list[str]` — непокрытые единицы со статусом пусто/`нужно решение`; ссылки `Покрывает` на несуществующие или `удал.` единицы; ошибки `lint_case`; плейсхолдеры `⚠ Q-QA-xx` на закрытые вопросы `qa/questions.md`; кейсы без `TC-xx`; команда `precheck`.
  - `export_csv(task_dir, key: str) -> Path` — пишет `qa/allure-import.csv`, отмечает `exported`; команда `export`.
  - `affected(task_dir) -> list[tuple[str, list[str]]]` — `(TC-xx, [изменённые R/IM/D])` по сравнению `row_hashes` с `rows`; команда `affected`.

- [ ] **Step 1: Тесты**

```python
def test_mark_and_human_edit(qa_cases_task):
    mark(qa_cases_task, "все")
    assert human_cases(qa_cases_task) == []
    edit_case(qa_cases_task, "TC-02", "Новый шаг")
    assert human_cases(qa_cases_task) == ["TC-02"]

def test_coverage_and_precheck(qa_cases_task):
    rows = {u: (s, tcs) for u, s, tcs in coverage(qa_cases_task)}
    assert rows["U-01"][1] == ["TC-01"]
    msgs = precheck(qa_cases_task)
    assert any("U-02" in m and "без кейса" in m for m in msgs)

def test_deleted_case_not_restored(qa_cases_task):
    delete_case(qa_cases_task, "TC-01")
    assert any("U-01" in m for m in precheck(qa_cases_task))
    assert "TC-01" not in (qa_cases_task / "qa/cases.md").read_text(encoding="utf-8")

def test_cover_ref_to_removed_unit(qa_cases_task):
    set_unit_status(qa_cases_task, "U-04", "удал.")
    assert any("TC-01" in m and "U-04" in m for m in precheck(qa_cases_task))

def test_export_csv_roundtrip(qa_cases_task):
    path = export_csv(qa_cases_task, "PF2-3964")
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline="")))
    assert rows[0] == ["ID", "Name", "Description", "Precondition", "Scenario", "Expected result", "Priority", "Status"]
    assert rows[1][0] == "PF2-3964-TC-01" and rows[1][7] == "Draft"
    assert '"merchantId"' in rows[1][4] and "«" in "".join(r[5] for r in rows[1:])

def test_affected_by_changed_decision(qa_cases_task):
    mark(qa_cases_task, "все")
    change_decision(qa_cases_task, "D-13")
    assert ("TC-01", ["D-13"]) in affected(qa_cases_task)
```

- [ ] **Step 2:** `python -m pytest tests/test_sa_qa.py -q` — FAIL.
- [ ] **Step 3:** Реализовать `sa_qa.py`. CSV — модуль `csv`, кодировка `utf-8-sig`, шаги в `Scenario` нумерованные через `\n` (решение по склейке — до проверки на живом Allure); `main(argv)` по образцу `sa_review.main` с `USAGE`. `qa_cases_task` — фикстура: `qa_task` + `tests/fixtures/qa/cases.md` + `sync_units`.
- [ ] **Step 4:** `python -m pytest -q` — PASS.
- [ ] **Step 5:** `git commit -m "feat(qa): CLI sa_qa — покрытие, отметки, CSV, задетые кейсы"`

### Task 5: Валидатор и статус задачи

**Files:**
- Modify: `scripts/sa_validate.py` (`validate_task`, новая `validate_qa`)
- Modify: `scripts/sa_status.py` (`build_status`)
- Test: `tests/test_sa_validate.py`, `tests/test_sa_status.py`

**Interfaces:**
- Consumes: `parse_cases`, `load_units`, `parse_questions` (секция `## Для аналитика` в `qa/questions.md`).
- Produces: `validate_qa(task_dir: Path) -> list[str]` — вызывается из `validate_task`, только если есть `qa/`; ошибки формата `cases.md`/`units.md`/`questions.md`, дубли `TC`/`U`, `Источник` на несуществующие `R/IM/D`, статус единицы без причины. `build_status` добавляет строку `QA: кейсов N (бэкенд a, фронт b, регресс c) · непокрыто k · нужно решение m · вопросов Q-QA x · правки человека h · выгружено e, изменено после выгрузки d`.

- [ ] **Step 1: Тесты**

```python
def test_no_qa_folder_unchanged(task_dir):
    assert validate_task(task_dir) == baseline_errors(task_dir)
    assert "QA:" not in build_status(task_dir)

def test_validate_qa_errors(qa_cases_task):
    break_source(qa_cases_task, "TC-01", "R-99")
    set_status_without_reason(qa_cases_task, "U-02", "не тестируется")
    errs = validate_task(qa_cases_task)
    assert any("TC-01" in e and "R-99" in e for e in errs)
    assert any("U-02" in e and "причин" in e for e in errs)

def test_status_qa_line(qa_cases_task):
    assert "QA: кейсов 3" in build_status(qa_cases_task)
```

- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Реализовать.
- [ ] **Step 4:** `python -m pytest -q` — PASS.
- [ ] **Step 5:** `git commit -m "feat(qa): проверка qa/ в валидаторе и строка QA в статусе"`

### Task 6: Стадии, агент, правила, схема, версия

**Files:**
- Create: `skills/qa-cases/SKILL.md`, `skills/qa-check/SKILL.md`, `skills/qa-export/SKILL.md`, `skills/qa-update/SKILL.md`
- Create: `agents/qa-reviewer.md` (по образцу `agents/tdd-reviewer.md`: только `Read, Grep, Glob`, черновик и кейсы не правит)
- Create: `shared/rules/qa-cases.md` — правила написания кейса (спека §4, §7, §8; новичок — опытный тестировщик без онбординга; бэкенд-шаг «Вызвать метод `ГЛАГОЛ /путь`» без инструмента; проверки в БД/Kafka/Redis; предусловия — только условие; один ожидаемый результат в конце; правило приоритетов по умолчанию)
- Modify: `shared/schemas/artifacts.md` — раздел `qa/` (`cases.md`, `units.md`, `questions.md`, `review.md`, `allure-import.csv`, `proposals/`, `state.json`)
- Modify: `README.md`, `.claude-plugin/plugin.json` (`0.5.0`), `tests/test_skills_contract.py`, `tests/test_shared_docs.py`, `tests/test_plugin_structure.py`

**Interfaces:**
- Consumes: все команды `sa_qa.py`, `sa_ids.py next tasks/<KEY> TC|U|Q-QA|QV`, `sa_validate.py`, `sa_status.py`.
- Produces (фрагменты, которые проверяют контракт-тесты):
  - `qa-cases`: `sa_qa.py units tasks/<KEY>`, `sa_ids.py next tasks/<KEY> TC`, `sa-skills:source-reader`, `code:`, `нужно решение`, `qa-cases.md`, `sa_qa.py mark tasks/<KEY>`, `sa_validate.py tasks/<KEY>`, `Q-QA`.
  - `qa-check`: `sa_qa.py precheck tasks/<KEY>`, `sa_qa.py coverage tasks/<KEY>`, `sa-skills:qa-reviewer`, `qa/review.md`, `QV-`.
  - `qa-export`: `sa_qa.py export tasks/<KEY>`, `загружай`, `allure-import.csv`.
  - `qa-update`: `sa_qa.py affected tasks/<KEY>`, `правка человека`, `qa/proposals/`, `sa_qa.py mark tasks/<KEY>`.

- [ ] **Step 1: Контракт-тесты** — по образцу `test_tdd_impact_contract`: `test_qa_cases_contract`, `test_qa_check_contract`, `test_qa_export_contract`, `test_qa_update_contract` с фрагментами из Interfaces; `test_shared_docs` — `shared/rules/qa-cases.md` существует и содержит «новичок», «Вызвать метод», «Ожидаемый результат»; версия `0.5.0`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Написать SKILL.md по шагам спеки §5 (у `qa-cases` — шаги 1–7, включая чтение кода через `source-reader` и список «нужно решение»; у `qa-update` — замечания `QV-xx` и ручные правки через `qa/proposals/`); агент `qa-reviewer` — что ищет (спека §8, «ревьюером»), ответ — таблица замечаний.
- [ ] **Step 4:** `python -m pytest -q` — PASS.
- [ ] **Step 5:** `git commit -m "feat(qa): стадии /qa-*, агент qa-reviewer, правила кейсов, версия 0.5.0"` и `git push origin main` (по `CLAUDE.md` репозитория).

### Обкатка (после задач, вручную с заказчиком)

В `C:\Users\Антон\Documents\Codex\QA\sa-tasks` на PF2-3964: `/qa-cases` → `/qa-check` → ревью заказчиком → `/qa-export`. Найденное — в `docs/feedback/`.
