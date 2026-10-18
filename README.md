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
| `/tdd-impact <ссылка>` | Карта влияния по BRD | готово |
| `/tdd-start` | Контекст-пакет | готово |
| `/tdd-clarify` | Вопросы PO и аналитику, журнал решений | готово |
| `/tdd-draft` | Черновик ТЗ на доработку по канону типа 1 (шаблон `feature@2.0`), самопроверка, публикация в Confluence | готово |
| `puml-c2`, `puml-sequence`, `puml-activity`, `puml-er`, `puml-state` | Диаграммы PlantUML для ТЗ, вызываются из `/tdd-draft` или сами | готово |
| `/tdd-check [KEY] [--code]` | Независимое ревью черновика: review.md, матрица покрытия | готово |
| `/tdd-update [KEY] [RV-xx…]` | Точечное обновление черновика по решениям и замечаниям | готово |
| `/sa-index-docs [сервис\|all] [--full]` | Индекс `docs/sa-index/` по коду сервисов и глобальный индекс системы | готово |
| `/qa-cases [KEY]` | Ручные тест-кейсы из готового ТЗ: бэкенд, фронт, регресс, единицы покрытия `qa/units.md` | готово |
| `/qa-check [KEY]` | Проверка кейсов: покрытие, формулировки, ревьюер `qa-reviewer`, `qa/review.md` | готово |
| `/qa-export [KEY]` | Выгрузка в Allure TestOps после «загружай»: пока CSV `qa/allure-import.csv` | готово |
| `/qa-update [KEY] [QV-xx…]` | Обновление кейсов после изменения ТЗ и по замечаниям, правки человека — предложениями | готово |

Артефакты задачи лежат в `tasks/<KEY>/` рабочей папки, артефакты QA — в `tasks/<KEY>/qa/`. Форматы — `shared/schemas/artifacts.md`, правила кейсов — `shared/rules/qa-cases.md`.

## Шаблон ТЗ «доработка» (feature@2.0)

Структура и оформление — по эталонным страницам Confluence pageId 110167390 («Настройки компании. Сотрудники.», весь документ) и 110166633 (наполнение «Доработок»). Порядок разделов фиксирован, пустых разделов и заглушек нет:

1. Оглавление и «Статусы» — собирает `sa_draft.py assemble`.
2. `BRD` — Контекст/Проблема, таблица User Stories, Требования к UI.
3. `Архитектура и Процесс` — одна C2, процессы под «Раскрыть» с sequence и «Описанием шагов».
4. `Доработки` — по сервисам: `Front` (экраны) и `Back` (1. Описание изменений, 2. API — OpenAPI, 3. БД — ER), в конце `Топики Кафка`.
5. `Зависимые процессы и сервисы`, `Конфиги`, `Доступы` — только при изменениях.
6. `Тестирование и регресс` — новое и сохраняемое поведение.
7. `Условия релиза` — по релизному регламенту, если затронуты ЛК/БО или тексты уведомлений.
8. `Открытые вопросы` — из `questions.md`.

Секции — `shared/templates/feature.yaml`, правила секций — `shared/blocks/`. Черновики, собранные по `feature@1.0`, нужно пересобрать: `/tdd-draft` предупредит.

Плагин собирает только тип 1 — ТЗ на доработку. Типы 2–5 (описание сервиса, бизнес-процесса, интеграция платёжного метода, прочее) не переносятся.

Эталонные страницы и проверка их версии перед каждой сборкой — `shared/etalons.md`.

## Окружение

| Переменная | Зачем | По умолчанию |
|---|---|---|
| `SA_REPOS_ROOT` | Папка с локальными клонами репозиториев сервисов | `~/repos` |
| `SA_SYSTEM_DOCS` | Репозиторий с индексом системы (`docs/bctc.md`, `docs/system_tech.md`) | `$SA_REPOS_ROOT/system-docs` |
| `JIRA_BASE_URL`, `JIRA_TOKEN`, `JIRA_EMAIL` | Доступ к Jira без MCP | — |
| `CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN` | Доступ к Confluence без MCP | — |

Проверить, что видит плагин: `python3 scripts/sa_paths.py`.

Проверить доступ: `python3 scripts/sa_fetch.py jira <KEY>`.

## Сквозная проверка стадий

```bash
REPO=<путь к этому репозиторию>
mkdir -p /tmp/sa-e2e && cd /tmp/sa-e2e
export SA_REPOS_ROOT=$REPO/tests/fixtures/e2e/repos
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-impact $REPO/tests/fixtures/e2e/brd-promo.md PROMO-1"
python3 $REPO/scripts/sa_validate.py tasks/PROMO-1
```

Черновик по эталонной задаче (открытый блокирующий вопрос и нерешённый скоуп — проверка плейсхолдеров):

```bash
mkdir -p /tmp/sa-e2e/tasks && cp -R $REPO/tests/fixtures/LKP-DEMO /tmp/sa-e2e/tasks/
claude --plugin-dir $REPO --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" \
  -p "/tdd-draft LKP-DEMO Иван Петров. Продолжай с плейсхолдерами."
python3 $REPO/scripts/sa_validate.py tasks/LKP-DEMO
python3 $REPO/scripts/sa_draft.py gaps tasks/LKP-DEMO
```

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

### /sa-index-docs

```bash
python3 <repo>/tests/fixtures/e2e/index-repos/make_repos.py /tmp/sa-e2e-index/repos
cd /tmp/sa-e2e-index
SA_REPOS_ROOT=/tmp/sa-e2e-index/repos claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/sa-index-docs all"
python3 <repo>/tests/fixtures/e2e/index-repos/make_repos.py /tmp/sa-e2e-index/repos --change
SA_REPOS_ROOT=/tmp/sa-e2e-index/repos claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/sa-index-docs shop-api"
```

Ожидается: после первого запуска `sa_index.py check` даёт `OK` для трёх сервисов, в `repos/system-docs/docs/system_tech.md` есть `POST /api/orders` с потребителем `shop-front` и `Kafka: orders.created` с `shop-legacy`; второй запуск идёт в режиме `incremental` и добавляет в `shop-api/docs/sa-index/tech.md` строку `DELETE /api/orders/{id}`.

Синтаксис диаграмм проверяется через `plantuml` в PATH или Docker-образ `plantuml/plantuml` (`docker pull plantuml/plantuml`); без них — только структура.

Скилы заранее разрешают только `python3`. В интерактивном режиме Claude Code будет спрашивать разрешение на правки файлов, grep и субагентов; для запуска без участия человека передай `--allowedTools`, как в блоке выше.

## Разработка

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```
