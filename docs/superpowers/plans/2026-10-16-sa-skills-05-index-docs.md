# SA Skills — подпроект 5: /sa-index-docs — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Скил `/sa-index-docs [сервис|all] [--full]`, который строит и инкрементально обновляет `docs/tech.md`, `docs/DB.md`, `docs/bctc.md` в репозиториях сервисов (таблицы фиксированной структуры со ссылками `файл:строка`) и собирает глобальные `system_tech.md`, `bctc.md`, `AGENTS.md` в `index_dir`.

**Architecture:** Код читает LLM-субагент `docs-indexer` (sonnet, по одному на сервис, при большом репозитории — три). Всё проверяемое — в stdlib-скриптах: `sa_index.py` (схемы, `check`, `survey`, `changed`, `stamp`, CLI) и `sa_index_aggregate.py` (детерминированная сборка глобальных файлов). Скил пишет только файлы в рабочую копию, без веток и коммитов.

**Tech Stack:** Claude Code plugin (SKILL.md, agents), Python ≥ 3.10 (stdlib, `subprocess` для `git`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-sa-skills-pipeline-design.md` (разделы 8, 8.1, 9, 12)

## Global Constraints

- Скрипты в `scripts/` — только стандартная библиотека Python ≥ 3.10 (в f-string выражениях нет `\`).
- Все тексты для пользователя — на русском.
- Скилы ссылаются на файлы плагина как `<плагин>/scripts/…` и `<плагин>/shared/…`, где `<плагин>` = `<база>/../..`.
- Каждый SKILL.md имеет frontmatter `name`, `description` (≤ 1024 символов), `allowed-tools: Bash(python3:*)`.
- В skills/agents/shared нет `$VAR`/`${VAR}` с заглавными буквами (тест `test_no_shell_variables_in_prompts`); в Bash — одна команда без `;`, `&&`, `|`.
- Пути репозиториев скил берёт из `sa_paths.py` (`repos_root`, `services`, `index_dir`) и пишет файлы по абсолютным путям.
- Git: только чтение (`rev-parse`, `diff`, `ls-files`, `cat-file`, `rev-list`) внутри `sa_index.py`; никаких веток, коммитов, `fetch`, `pull`.
- Существующие фикстуры (`tests/fixtures/LKP-DEMO`, `tests/fixtures/e2e/*` кроме новой `index-repos/`) не менять.
- Субагент `docs-indexer`: `model: sonnet`.
- Версию плагина (`0.1.0`) не менять.

## Структура файлов

```
scripts/
  sa_index.py            # новый: SCHEMAS, read_doc, check_repo, survey, changed, stamp, CLI
  sa_index_aggregate.py  # новый: http_key, system_tech, system_bctc, agents_md, aggregate
agents/
  docs-indexer.md        # новый
skills/
  sa-index-docs/SKILL.md # новый
shared/
  index/docs-schema.md   # новый: схемы docs/ сервиса и глобальных файлов
  index/stack-hints.md   # новый: где искать по стекам
  access/adapters.md     # Git: убрать исключение про ветку
tests/
  conftest.py                    # + git(), index_repos
  test_sa_index.py               # новый
  test_sa_index_aggregate.py     # новый
  test_shared_docs.py  test_skills_contract.py  test_plugin_structure.py  test_e2e_fixture.py
  fixtures/e2e/index-repos/      # новый: shop-api (Laravel), shop-legacy (PHP 5.6), shop-front (React), make_repos.py
  fixtures/index-docs/           # новый: эталонные docs/ для трёх сервисов
README.md
```

---

### Task 1: Фикстуры, схемы и `sa_index.py check`

**Files:**
- Create: `tests/fixtures/e2e/index-repos/shop-api/…`, `shop-legacy/…`, `shop-front/…` (исходники ниже)
- Create: `tests/fixtures/index-docs/<сервис>/docs/{tech,DB,bctc}.md`
- Create: `scripts/sa_index.py`
- Modify: `tests/conftest.py` (дописать в конец)
- Test: `tests/test_sa_index.py`

**Interfaces:**
- Produces: `SCHEMAS: dict[str, dict[str, list[str]]]`, `DIRECTIONS`, `EMPTY = "нет"`, `DASH = "—"`, `DOCS = "docs"`, `STAMP_FILE = ".sa-index.json"`, `read_doc(repo: Path, name: str) -> dict[str, list[dict[str, str]]]` (ArtifactError), `code_refs(cell: str) -> list[tuple[str, int]] | None`, `check_repo(repo: Path, names: list[str] | None = None) -> list[str]`, `main(argv) -> int` с командой `check <repo> [файл…]`; в conftest — `git(repo, *args)` и фикстура `index_repos` → `make(name, docs=True, init=True) -> Path`.

- [ ] **Step 1: Исходники фикстур.** Создай файлы точно как ниже (номера строк важны: на них ссылаются эталонные docs).

`tests/fixtures/e2e/index-repos/shop-api/composer.json`:
```json
{"require": {"laravel/framework": "^10.0"}}
```

`tests/fixtures/e2e/index-repos/shop-api/artisan`:
```
#!/usr/bin/env php
<?php
// artisan stub
```

`tests/fixtures/e2e/index-repos/shop-api/routes/api.php`:
```php
<?php

use App\Http\Controllers\OrderController;
use Illuminate\Support\Facades\Route;

Route::post('/api/orders', [OrderController::class, 'store']);
Route::get('/api/orders/{id}', [OrderController::class, 'show']);
```

`tests/fixtures/e2e/index-repos/shop-api/app/Http/Controllers/OrderController.php`:
```php
<?php

namespace App\Http\Controllers;

use App\Jobs\SendOrderToCrm;
use App\Services\PaymentsClient;

class OrderController
{
    public function store(PaymentsClient $payments)
    {
        $order = Order::create(request()->all());
        $payments->createInvoice($order);
        SendOrderToCrm::dispatch($order);
        return $order;
    }

    public function show(int $id)
    {
        return Order::findOrFail($id);
    }
}
```

`tests/fixtures/e2e/index-repos/shop-api/app/Services/PaymentsClient.php`:
```php
<?php

namespace App\Services;

class PaymentsClient
{
    public function createInvoice($order)
    {
        return Http::post(config('services.payments.url') . '/invoices.php', ['order' => $order->id]);
    }
}
```

`tests/fixtures/e2e/index-repos/shop-api/app/Jobs/SendOrderToCrm.php`:
```php
<?php

namespace App\Jobs;

class SendOrderToCrm implements ShouldQueue
{
    public function handle(KafkaProducer $kafka)
    {
        $kafka->send('orders.created', $this->order->toArray());
    }
}
```

`tests/fixtures/e2e/index-repos/shop-api/database/migrations/2024_01_01_000000_create_orders_table.php`:
```php
<?php

return new class extends Migration
{
    public function up()
    {
        Schema::create('orders', function (Blueprint $table) {
            $table->id();
            $table->string('email');
            $table->integer('amount');
            $table->timestamps();
        });
    }
};
```

`tests/fixtures/e2e/index-repos/shop-legacy/db.php`:
```php
<?php
mysql_connect('localhost', 'app', 'secret');
mysql_select_db('legacy');
```

`tests/fixtures/e2e/index-repos/shop-legacy/index.php`:
```php
<?php
require 'db.php';
$orders = mysql_query("SELECT * FROM legacy_invoices ORDER BY id DESC");
include 'templates/invoices.tpl.php';
```

`tests/fixtures/e2e/index-repos/shop-legacy/invoices.php`:
```php
<?php
require 'db.php';
$orderId = (int) $_POST['order'];
mysql_query("INSERT INTO legacy_invoices (order_id) VALUES ($orderId)");
echo json_encode(array('ok' => true));
```

`tests/fixtures/e2e/index-repos/shop-legacy/cron/consume_orders.php`:
```php
<?php
// cron: */5 * * * * php cron/consume_orders.php
require dirname(__FILE__) . '/../db.php';
$consumer = new RdKafka\KafkaConsumer($conf);
$consumer->subscribe(array('orders.created'));
while ($message = $consumer->consume(1000)) {
    mysql_query("UPDATE legacy_invoices SET status = 'new' WHERE order_id = " . (int) $message->payload);
}
```

`tests/fixtures/e2e/index-repos/shop-legacy/templates/invoices.tpl.php`:
```php
<table><?php while ($row = mysql_fetch_assoc($orders)): ?><tr><td><?= $row['order_id'] ?></td></tr><?php endwhile; ?></table>
```

`tests/fixtures/e2e/index-repos/shop-front/package.json`:
```json
{"name": "shop-front", "dependencies": {"react": "^18.2.0"}}
```

`tests/fixtures/e2e/index-repos/shop-front/src/api.js`:
```js
export async function createOrder(data) {
  return fetch('/api/orders', { method: 'POST', body: JSON.stringify(data) });
}

export async function getOrder(id) {
  return fetch(`/api/orders/${id}`);
}
```

`tests/fixtures/e2e/index-repos/shop-front/src/pages/Checkout.jsx`:
```jsx
import { createOrder } from '../api';

export default function Checkout() {
  return <form onSubmit={(e) => { e.preventDefault(); createOrder({}); }}><button>Оформить</button></form>;
}
```

- [ ] **Step 2: Эталонные docs.**

`tests/fixtures/index-docs/shop-api/docs/tech.md`:
```markdown
# shop-api

## API

| Метод | Путь | Назначение | Код |
|---|---|---|---|
| POST | /api/orders | Создание заказа | routes/api.php:6, app/Http/Controllers/OrderController.php:10 |
| GET | /api/orders/{id} | Заказ по id | routes/api.php:7, app/Http/Controllers/OrderController.php:18 |

## Исходящие вызовы

| Куда | Метод или топик | Назначение | Код |
|---|---|---|---|
| shop-legacy | POST /invoices.php | Создание счёта по заказу | app/Services/PaymentsClient.php:9 |

## Сообщения

| Брокер | Топик или очередь | Направление | Когда | Код |
|---|---|---|---|---|
| Kafka | orders.created | публикует | после создания заказа | app/Jobs/SendOrderToCrm.php:9 |

## Фоновые задачи

| Задача | Запуск | Что делает | Код |
|---|---|---|---|
| SendOrderToCrm | очередь | Публикует событие о новом заказе | app/Jobs/SendOrderToCrm.php:5 |
```

`tests/fixtures/index-docs/shop-api/docs/DB.md`:
```markdown
# shop-api

## Таблицы

| Таблица | Назначение | Ключевые поля | Код |
|---|---|---|---|
| orders | Заказы | id, email, amount | database/migrations/2024_01_01_000000_create_orders_table.php:7 |

## Связи

| Из | В | Тип | Код |
|---|---|---|---|
| нет | — | — | — |
```

`tests/fixtures/index-docs/shop-api/docs/bctc.md`:
```markdown
# shop-api

## Сценарии

| Домен | Сценарий | Роль сервиса | Точки входа | Код |
|---|---|---|---|---|
| Заказы | Оформление заказа | Принимает заказ, выставляет счёт, публикует событие | POST /api/orders | app/Http/Controllers/OrderController.php:10 |
```

`tests/fixtures/index-docs/shop-legacy/docs/tech.md`:
```markdown
# shop-legacy

## API

| Метод | Путь | Назначение | Код |
|---|---|---|---|
| POST | /invoices.php | Создание счёта | invoices.php:3 |
| GET | /index.php | Список счетов (HTML) | index.php:3 |

## Исходящие вызовы

| Куда | Метод или топик | Назначение | Код |
|---|---|---|---|
| нет | — | — | — |

## Сообщения

| Брокер | Топик или очередь | Направление | Когда | Код |
|---|---|---|---|---|
| Kafka | orders.created | читает | каждые 5 минут по cron | cron/consume_orders.php:5 |

## Фоновые задачи

| Задача | Запуск | Что делает | Код |
|---|---|---|---|
| consume_orders | cron */5 * * * * | Читает события о заказах и обновляет счета | cron/consume_orders.php:2 |
```

`tests/fixtures/index-docs/shop-legacy/docs/DB.md`:
```markdown
# shop-legacy

## Таблицы

| Таблица | Назначение | Ключевые поля | Код |
|---|---|---|---|
| legacy_invoices | Счета | order_id, status | invoices.php:4, cron/consume_orders.php:7 |

## Связи

| Из | В | Тип | Код |
|---|---|---|---|
| legacy_invoices.order_id | ? orders.id (shop-api) | ? логическая, без FK | invoices.php:4 |
```

`tests/fixtures/index-docs/shop-legacy/docs/bctc.md`:
```markdown
# shop-legacy

## Сценарии

| Домен | Сценарий | Роль сервиса | Точки входа | Код |
|---|---|---|---|---|
| Счета | Выставление счёта | Создаёт счёт по заказу | POST /invoices.php | invoices.php:4 |
| Заказы | Оформление заказа | Получает событие о заказе | Kafka orders.created | cron/consume_orders.php:5 |
```

`tests/fixtures/index-docs/shop-front/docs/tech.md`:
```markdown
# shop-front

## API

| Метод | Путь | Назначение | Код |
|---|---|---|---|
| нет | — | — | — |

## Исходящие вызовы

| Куда | Метод или топик | Назначение | Код |
|---|---|---|---|
| shop-api | POST /api/orders | Создание заказа | src/api.js:2 |
| shop-api | GET /api/orders/${id} | Загрузка заказа | src/api.js:6 |

## Сообщения

| Брокер | Топик или очередь | Направление | Когда | Код |
|---|---|---|---|---|
| нет | — | — | — | — |

## Фоновые задачи

| Задача | Запуск | Что делает | Код |
|---|---|---|---|
| нет | — | — | — |
```

`tests/fixtures/index-docs/shop-front/docs/DB.md`:
```markdown
# shop-front

## Таблицы

| Таблица | Назначение | Ключевые поля | Код |
|---|---|---|---|
| нет | — | — | — |

## Связи

| Из | В | Тип | Код |
|---|---|---|---|
| нет | — | — | — |
```

`tests/fixtures/index-docs/shop-front/docs/bctc.md`:
```markdown
# shop-front

## Сценарии

| Домен | Сценарий | Роль сервиса | Точки входа | Код |
|---|---|---|---|---|
| Заказы | Оформление заказа | Форма оформления заказа | экран Checkout | src/pages/Checkout.jsx:3 |
```

- [ ] **Step 3: Хелперы в `tests/conftest.py`** — дописать в конец:

```python
import subprocess

INDEX_REPOS = Path(__file__).parent / "fixtures" / "e2e" / "index-repos"
INDEX_DOCS = Path(__file__).parent / "fixtures" / "index-docs"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=SA", "-c", "user.email=sa@example.com", *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout


@pytest.fixture
def index_repos(tmp_path: Path):
    root = tmp_path / "repos"

    def make(name: str, docs: bool = True, init: bool = True) -> Path:
        repo = root / name
        shutil.copytree(INDEX_REPOS / name, repo)
        if docs:
            shutil.copytree(INDEX_DOCS / name / "docs", repo / "docs")
        if init:
            git(repo, "init", "-q")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "init")
        return repo

    return make
```

- [ ] **Step 4: Падающие тесты** `tests/test_sa_index.py`:

```python
import pytest

from sa_index import SCHEMAS, check_repo, code_refs, main, read_doc

SERVICES = ("shop-api", "shop-legacy", "shop-front")


def _edit(repo, name, old, new):
    path = repo / "docs" / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


@pytest.mark.parametrize("service", SERVICES)
def test_golden_docs_pass_check(index_repos, service):
    assert check_repo(index_repos(service)) == []


def test_read_doc_returns_rows_by_section(index_repos):
    doc = read_doc(index_repos("shop-api"), "tech.md")
    assert list(doc) == list(SCHEMAS["tech.md"])
    assert doc["API"][0]["Путь"] == "/api/orders"


def test_code_refs():
    assert code_refs("a/b.php:6, c.js:10") == [("a/b.php", 6), ("c.js", 10)]
    assert code_refs("a/b.php") is None
    assert code_refs("—") is None


def test_check_reports_bad_line_and_file(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "tech.md", "routes/api.php:6,", "routes/api.php:99,")
    _edit(repo, "DB.md", "create_orders_table.php:7", "missing.php:7")
    errors = check_repo(repo)
    assert any("в routes/api.php нет строки 99" in e for e in errors)
    assert any("нет файла database/migrations/missing.php" in e for e in errors)


def test_check_reports_bad_code_format_and_escape(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "bctc.md", "app/Http/Controllers/OrderController.php:10 |", "OrderController |")
    _edit(repo, "DB.md", "| orders | Заказы | id, email, amount | database", "| orders | Заказы | id, email, amount | ../x.php:1, database")
    errors = check_repo(repo)
    assert any("«Код»" in e and "OrderController" in e for e in errors)
    assert any("нет файла ../x.php" in e for e in errors)


def test_check_reports_missing_section_and_header(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "DB.md", "## Связи", "## Связки")
    _edit(repo, "tech.md", "| Метод | Путь | Назначение | Код |", "| Метод | URL | Назначение | Код |")
    errors = check_repo(repo)
    assert any("DB.md: нет раздела «## Связи»" in e for e in errors)
    assert any("tech.md#API" in e for e in errors)


def test_check_empty_row_and_cells(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "DB.md", "| нет | — | — | — |", "| нет | x | — | — |")
    _edit(repo, "tech.md", "| Создание заказа | routes", "|  | routes")
    errors = check_repo(repo)
    assert any("строке «нет»" in e for e in errors)
    assert any("пустая ячейка «Назначение»" in e for e in errors)


def test_check_direction(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "tech.md", "| публикует |", "| шлёт |")
    assert any("Направление" in e for e in check_repo(repo))
    _edit(repo, "tech.md", "| шлёт |", "| ? публикует |")
    assert check_repo(repo) == []


def test_check_missing_files_and_only_named(index_repos):
    repo = index_repos("shop-api")
    (repo / "docs" / "DB.md").unlink()
    assert any("нет файла docs/DB.md" in e for e in check_repo(repo))
    assert check_repo(repo, ["tech.md", "bctc.md"]) == []


def test_check_requires_title(index_repos):
    repo = index_repos("shop-api")
    _edit(repo, "bctc.md", "# shop-api\n", "shop-api\n")
    assert any("первая строка" in e for e in check_repo(repo))


def test_cli_check(index_repos, capsys):
    repo = index_repos("shop-api")
    assert main(["check", str(repo)]) == 0
    assert capsys.readouterr().out.strip() == "OK"
    assert main(["check", str(repo), "README.md"]) == 2
    _edit(repo, "tech.md", "routes/api.php:6,", "routes/api.php:99,")
    assert main(["check", str(repo), "tech.md"]) == 1
```

- [ ] **Step 5: Запусти — падает.** `python3 -m pytest tests/test_sa_index.py -q` → `ModuleNotFoundError: sa_index`.

- [ ] **Step 6: Реализация** `scripts/sa_index.py` (часть 1; команды `survey`, `changed`, `stamp`, `aggregate` добавит Task 2–3):

```python
#!/usr/bin/env python3
"""Индекс docs/ сервиса: схемы таблиц, проверка, карта репозитория, изменённые файлы, отметка индексации."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import ArtifactError, parse_tables

DOCS = "docs"
STAMP_FILE = ".sa-index.json"
SCHEMAS = {
    "tech.md": {
        "API": ["Метод", "Путь", "Назначение", "Код"],
        "Исходящие вызовы": ["Куда", "Метод или топик", "Назначение", "Код"],
        "Сообщения": ["Брокер", "Топик или очередь", "Направление", "Когда", "Код"],
        "Фоновые задачи": ["Задача", "Запуск", "Что делает", "Код"],
    },
    "DB.md": {
        "Таблицы": ["Таблица", "Назначение", "Ключевые поля", "Код"],
        "Связи": ["Из", "В", "Тип", "Код"],
    },
    "bctc.md": {
        "Сценарии": ["Домен", "Сценарий", "Роль сервиса", "Точки входа", "Код"],
    },
}
DIRECTIONS = ("публикует", "читает")
EMPTY = "нет"
DASH = "—"
CODE_REF_RE = re.compile(r"([^\s,:][^,:]*):(\d+)")


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def read_doc(repo: Path, name: str) -> dict[str, list[dict[str, str]]]:
    """Строки таблиц файла индекса по разделам; ArtifactError, если структура не по схеме."""
    path = repo / DOCS / name
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ArtifactError(f"{DOCS}/{name}: не читается ({exc})") from exc
    if not text.startswith("# "):
        raise ArtifactError(f"{DOCS}/{name}: первая строка должна быть заголовком «# <сервис>»")
    sections = _sections(text)
    result = {}
    for section, columns in SCHEMAS[name].items():
        if section not in sections:
            raise ArtifactError(f"{DOCS}/{name}: нет раздела «## {section}»")
        try:
            tables = parse_tables(sections[section])
        except ArtifactError as exc:
            raise ArtifactError(f"{DOCS}/{name}#{section}: {exc}") from exc
        if len(tables) != 1 or tables[0].header != columns:
            raise ArtifactError(f"{DOCS}/{name}#{section}: ожидается одна таблица | {' | '.join(columns)} |")
        result[section] = tables[0].rows
    return result


def code_refs(cell: str) -> list[tuple[str, int]] | None:
    refs = []
    for part in (p.strip() for p in cell.split(",")):
        match = CODE_REF_RE.fullmatch(part)
        if match is None:
            return None
        refs.append((match.group(1), int(match.group(2))))
    return refs


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _ref_errors(repo: Path, where: str, cell: str) -> list[str]:
    refs = code_refs(cell)
    if refs is None:
        return [f"{where}: «Код» — «путь:строка» через «, », а не «{cell}»"]
    errors = []
    for rel, line in refs:
        rel_path = Path(rel)
        target = repo / rel_path
        if rel_path.is_absolute() or ".." in rel_path.parts or not target.is_file():
            errors.append(f"{where}: нет файла {rel}")
        elif not 1 <= line <= _line_count(target):
            errors.append(f"{where}: в {rel} нет строки {line}")
    return errors


def _row_errors(repo: Path, where: str, row: dict[str, str], columns: list[str]) -> list[str]:
    if row[columns[0]] == EMPTY:
        if any(row[c] != DASH for c in columns[1:]):
            return [f"{where}: в строке «нет» остальные ячейки — «—»"]
        return []
    errors = [f"{where}: пустая ячейка «{c}»" for c in columns if not row[c]]
    direction = row.get("Направление")
    if direction and direction not in DIRECTIONS and not direction.startswith("?"):
        errors.append(f"{where}: «Направление» — {' или '.join(DIRECTIONS)}, а не «{direction}»")
    if row["Код"]:
        errors += _ref_errors(repo, where, row["Код"])
    return errors


def check_repo(repo: Path, names: list[str] | None = None) -> list[str]:
    errors = []
    for name in names or list(SCHEMAS):
        if not (repo / DOCS / name).is_file():
            errors.append(f"нет файла {DOCS}/{name}")
            continue
        try:
            doc = read_doc(repo, name)
        except ArtifactError as exc:
            errors.append(str(exc))
            continue
        for section, rows in doc.items():
            columns = SCHEMAS[name][section]
            for number, row in enumerate(rows, start=1):
                errors += _row_errors(repo, f"{DOCS}/{name}#{section}, строка {number}", row, columns)
    return errors


USAGE = "usage: sa_index.py check <repo> [файл…]"


def _repo(raw: str) -> Path | None:
    repo = Path(raw).expanduser().absolute()
    if not repo.is_dir():
        print(f"нет папки {repo}", file=sys.stderr)
        return None
    return repo


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "check":
        print(USAGE, file=sys.stderr)
        return 2
    repo = _repo(argv[1])
    if repo is None:
        return 1
    names = argv[2:] or None
    if names and any(n not in SCHEMAS for n in names):
        print(f"файлы индекса: {', '.join(SCHEMAS)}", file=sys.stderr)
        return 2
    errors = check_repo(repo, names)
    print("\n".join(errors) if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 7: Тесты зелёные.** `python3 -m pytest -q` → всё проходит (265 старых + новые).

- [ ] **Step 8: Commit.**
```bash
git add scripts/sa_index.py tests/conftest.py tests/test_sa_index.py tests/fixtures/e2e/index-repos tests/fixtures/index-docs
git commit -m "feat: sa_index.py check — schemas of docs/ index with file:line validation"
```

---

### Task 2: `survey`, `changed`, `stamp`

**Files:**
- Modify: `scripts/sa_index.py`
- Test: `tests/test_sa_index.py` (дописать)

**Interfaces:**
- Consumes: Task 1 (`SCHEMAS`, `read_doc`, `code_refs`, `check_repo`, `_repo`, `main`).
- Produces: `load_stamp(repo) -> dict` (`{}` если нет или сломан), `doc_hashes(repo) -> dict[str, str]`, `human_edited(repo, stamp) -> list[str]`, `index_mode(repo, stamp) -> tuple[str, str]` (`"full"|"incremental"`, пояснение), `survey(repo) -> dict`, `format_survey(dict) -> str`, `changed(repo) -> dict`, `format_changed(dict) -> str`, `stamp(repo, today: date | None = None) -> list[str]`, `SPLIT_THRESHOLD = 1500`. Ключи `survey`: `repo, stack, sources, split, mode, reason, branch, hints, docs` (`docs`: имя → `нет`/`есть`/`правка человека`). Ключи `changed`: `mode, reason, files, rows`. `.sa-index.json`: `{"sha", "indexed", "plugin", "files": {имя: sha256}}`.

- [ ] **Step 1: Падающие тесты** — дописать в `tests/test_sa_index.py`:

```python
import json
from datetime import date

from conftest import git
from sa_index import STAMP_FILE, changed, format_changed, format_survey, stamp, survey


def test_survey_detects_stacks_and_hints(index_repos):
    api = survey(index_repos("shop-api", docs=False))
    assert api["stack"] == ["laravel"]
    assert api["sources"] == 5
    assert "routes/" in api["hints"] and "database/migrations/" in api["hints"]
    legacy = survey(index_repos("shop-legacy", docs=False))
    assert legacy["stack"] == ["php"]
    assert {"cron/", "templates/"} <= set(legacy["hints"])
    front = survey(index_repos("shop-front", docs=False))
    assert front["stack"] == ["react"]
    assert "src/pages/" in front["hints"]
    assert api["split"] is False


def test_survey_skips_vendor_and_docs(index_repos):
    repo = index_repos("shop-api", docs=False, init=False)
    (repo / "vendor" / "lib").mkdir(parents=True)
    (repo / "vendor" / "lib" / "x.php").write_text("<?php\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "y.php").write_text("<?php\n", encoding="utf-8")
    assert survey(repo)["sources"] == 5


def test_survey_full_without_stamp_marks_existing_docs_human(index_repos):
    result = survey(index_repos("shop-api"))
    assert result["mode"] == "full"
    assert result["docs"] == {"tech.md": "правка человека", "DB.md": "правка человека", "bctc.md": "правка человека"}
    text = format_survey(result)
    assert "mode: full (индексации ещё не было)" in text
    assert "stack: laravel" in text


def test_survey_non_git_repo(index_repos):
    result = survey(index_repos("shop-api", docs=False, init=False))
    assert result["mode"] == "full"
    assert "не git" in result["reason"]
    assert result["docs"]["tech.md"] == "нет"


def test_stamp_then_incremental_and_human_edit(index_repos):
    repo = index_repos("shop-api")
    assert stamp(repo, today=date(2026, 10, 16)) == []
    data = json.loads((repo / "docs" / STAMP_FILE).read_text(encoding="utf-8"))
    assert data["sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert data["indexed"] == "2026-10-16"
    assert data["plugin"] == "0.1.0"
    assert set(data["files"]) == {"tech.md", "DB.md", "bctc.md"}
    result = survey(repo)
    assert result["mode"] == "incremental"
    assert result["docs"]["tech.md"] == "есть"
    with (repo / "docs" / "tech.md").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert survey(repo)["docs"]["tech.md"] == "правка человека"


def test_stamp_refuses_invalid_docs(index_repos):
    repo = index_repos("shop-api")
    (repo / "docs" / "DB.md").unlink()
    assert stamp(repo) == ["нет файла docs/DB.md"]
    assert not (repo / "docs" / STAMP_FILE).exists()


def test_changed_lists_files_and_rows(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    routes = repo / "routes" / "api.php"
    routes.write_text(routes.read_text(encoding="utf-8") + "Route::delete('/api/orders/{id}', [OrderController::class, 'destroy']);\n", encoding="utf-8")
    git(repo, "commit", "-qam", "delete route")
    (repo / "app" / "Services" / "PaymentsClient.php").unlink()
    (repo / "app" / "Services" / "CrmClient.php").write_text("<?php\n", encoding="utf-8")
    (repo / "vendor").mkdir()
    (repo / "vendor" / "z.php").write_text("<?php\n", encoding="utf-8")
    result = changed(repo)
    assert result["mode"] == "incremental"
    assert result["files"] == ["app/Services/CrmClient.php", "app/Services/PaymentsClient.php", "routes/api.php"]
    assert "tech.md#API: POST — routes/api.php:6, app/Http/Controllers/OrderController.php:10" in result["rows"]
    assert "tech.md#Исходящие вызовы: shop-legacy — app/Services/PaymentsClient.php:9" in result["rows"]
    text = format_changed(result)
    assert "  app/Services/PaymentsClient.php (удалён)" in text


def test_changed_full_when_sha_unknown(index_repos):
    repo = index_repos("shop-api")
    stamp(repo)
    path = repo / "docs" / STAMP_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sha"] = "0" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    result = changed(repo)
    assert result["mode"] == "full"
    assert "не найден" in result["reason"]
    assert "mode: full" in format_changed(result)


def test_cli_survey_changed_stamp(index_repos, capsys):
    repo = index_repos("shop-api")
    assert main(["survey", str(repo)]) == 0
    assert "sources: 5" in capsys.readouterr().out
    assert main(["stamp", str(repo)]) == 0
    assert main(["changed", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "mode: incremental" in out and "files:\n  нет" in out
```

- [ ] **Step 2: Запусти — падает** (`ImportError: cannot import name 'changed'`).

- [ ] **Step 3: Реализация.** В `scripts/sa_index.py`:

Добавить импорты `hashlib`, `json`, `os`, `subprocess`, `from datetime import date`, `from sa_state import _plugin_version, write_atomic`. После `CODE_REF_RE`:

```python
EXCLUDED_DIRS = {".git", "vendor", "node_modules", "bin", "obj", "dist", "build", ".idea", ".vscode"}
SOURCE_EXTS = {
    ".php", ".phtml", ".tpl", ".twig", ".cs", ".cshtml", ".razor", ".js", ".jsx", ".ts", ".tsx",
    ".vue", ".py", ".go", ".java", ".kt", ".rb", ".sql",
}
HINT_NAMES = {
    "routes", "controllers", "migrations", "jobs", "console", "consumers", "listeners", "kafka",
    "templates", "views", "pages", "api", "cron", "models", "entities", "handlers", "workers",
}
SPLIT_THRESHOLD = 1500
```

Перед `USAGE`:

```python
def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _skipped(rel: Path) -> bool:
    return (bool(rel.parts) and rel.parts[0] == DOCS) or any(p in EXCLUDED_DIRS for p in rel.parts)


def _walk(repo: Path):
    for root, dirs, names in os.walk(repo):
        rel_root = Path(root).relative_to(repo)
        dirs[:] = sorted(d for d in dirs if not _skipped(rel_root / d))
        yield rel_root, dirs, names


def detect_stack(repo: Path, sources: list[Path]) -> list[str]:
    stack = set()
    folders = [repo] + [p for p in sorted(repo.iterdir()) if p.is_dir() and not _skipped(Path(p.name))]
    for folder in folders:
        composer = folder / "composer.json"
        if (folder / "artisan").is_file() or (
            composer.is_file() and "laravel/framework" in composer.read_text(encoding="utf-8", errors="replace")
        ):
            stack.add("laravel")
        if any(folder.glob("*.csproj")) or any(folder.glob("*.sln")):
            stack.add("dotnet")
        package = folder / "package.json"
        if package.is_file():
            stack.add("react" if '"react"' in package.read_text(encoding="utf-8", errors="replace") else "node")
    if "laravel" not in stack and any(s.suffix.lower() == ".php" for s in sources):
        stack.add("php")
    return sorted(stack)


def load_stamp(repo: Path) -> dict:
    try:
        data = json.loads((repo / DOCS / STAMP_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def doc_hashes(repo: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((repo / DOCS / name).read_bytes()).hexdigest()
        for name in SCHEMAS if (repo / DOCS / name).is_file()
    }


def human_edited(repo: Path, stamp_data: dict) -> list[str]:
    recorded = stamp_data.get("files") or {}
    return [name for name, digest in doc_hashes(repo).items() if recorded.get(name) != digest]


def index_mode(repo: Path, stamp_data: dict) -> tuple[str, str]:
    if _git(repo, "rev-parse", "HEAD") is None:
        return "full", "не git-репозиторий или нет коммитов"
    sha = stamp_data.get("sha")
    if not sha:
        return "full", "индексации ещё не было"
    if _git(repo, "cat-file", "-e", f"{sha}^{{commit}}") is None:
        return "full", f"коммит {sha[:7]} не найден"
    return "incremental", f"с {sha[:7]} от {stamp_data.get('indexed', '?')}"


def branch_status(repo: Path) -> str:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return "нет"
    name = branch.strip()
    counts = _git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts is None:
        return f"{name} (без upstream)"
    behind = int(counts.split()[1])
    return f"{name}, отстаёт от upstream на {behind} (по последнему fetch)" if behind else f"{name}, не отстаёт от upstream"


def survey(repo: Path) -> dict:
    sources: list[Path] = []
    hints: list[str] = []
    for rel_root, dirs, names in _walk(repo):
        sources += [rel_root / n for n in names if Path(n).suffix.lower() in SOURCE_EXTS]
        hints += [f"{(rel_root / d).as_posix()}/" for d in dirs if d.lower() in HINT_NAMES]
    stamp_data = load_stamp(repo)
    mode, reason = index_mode(repo, stamp_data)
    edited = human_edited(repo, stamp_data)
    docs = {
        name: "нет" if not (repo / DOCS / name).is_file() else "правка человека" if name in edited else "есть"
        for name in SCHEMAS
    }
    return {
        "repo": str(repo), "stack": detect_stack(repo, sources), "sources": len(sources),
        "split": len(sources) > SPLIT_THRESHOLD, "mode": mode, "reason": reason,
        "branch": branch_status(repo), "hints": sorted(hints)[:30], "docs": docs,
    }


def _listing(items: list[str]) -> list[str]:
    return [f"  {item}" for item in items] or ["  нет"]


def format_survey(data: dict) -> str:
    split = f"да (больше {SPLIT_THRESHOLD} исходников)" if data["split"] else "нет"
    docs = "; ".join(f"{name} — {status}" for name, status in data["docs"].items())
    return "\n".join([
        f"repo: {data['repo']}",
        f"stack: {', '.join(data['stack']) or 'не определён'}",
        f"sources: {data['sources']}",
        f"split: {split}",
        f"mode: {data['mode']} ({data['reason']})",
        f"branch: {data['branch']}",
        f"docs: {docs}",
        "hints:", *_listing(data["hints"]),
    ])


def changed(repo: Path) -> dict:
    stamp_data = load_stamp(repo)
    mode, reason = index_mode(repo, stamp_data)
    result = {"mode": mode, "reason": reason, "files": [], "rows": []}
    if mode == "full":
        return result
    diff = _git(repo, "diff", "--name-only", stamp_data["sha"]) or ""
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard") or ""
    files = sorted({f for f in (diff + untracked).splitlines() if f and not _skipped(Path(f))})
    rows = []
    for name in SCHEMAS:
        if not (repo / DOCS / name).is_file():
            continue
        try:
            doc = read_doc(repo, name)
        except ArtifactError:
            continue
        for section, table in doc.items():
            first = SCHEMAS[name][section][0]
            for row in table:
                if any(rel in files for rel, _ in code_refs(row["Код"]) or []):
                    rows.append(f"{name}#{section}: {row[first]} — {row['Код']}")
    result.update(files=files, rows=rows)
    result["deleted"] = [f for f in files if not (repo / f).exists()]
    return result


def format_changed(data: dict) -> str:
    lines = [f"mode: {data['mode']} ({data['reason']})"]
    if data["mode"] == "full":
        return "\n".join(lines)
    deleted = set(data.get("deleted", []))
    files = [f"{f} (удалён)" if f in deleted else f for f in data["files"]]
    return "\n".join(lines + ["files:", *_listing(files), "rows:", *_listing(data["rows"])])


def stamp(repo: Path, today: date | None = None) -> list[str]:
    errors = check_repo(repo)
    if errors:
        return errors
    head = _git(repo, "rev-parse", "HEAD")
    data = {
        "sha": head.strip() if head else None,
        "indexed": (today or date.today()).isoformat(),
        "plugin": _plugin_version(),
        "files": doc_hashes(repo),
    }
    write_atomic(repo / DOCS / STAMP_FILE, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return []
```

Заменить `USAGE` и `main`:

```python
USAGE = "usage: sa_index.py survey <repo> | changed <repo> | check <repo> [файл…] | stamp <repo>"


def main(argv: list[str]) -> int:
    commands = {"survey", "changed", "check", "stamp"}
    if not argv or argv[0] not in commands or len(argv) < 2 or (argv[0] != "check" and len(argv) != 2):
        print(USAGE, file=sys.stderr)
        return 2
    repo = _repo(argv[1])
    if repo is None:
        return 1
    if argv[0] == "survey":
        print(format_survey(survey(repo)))
        return 0
    if argv[0] == "changed":
        print(format_changed(changed(repo)))
        return 0
    if argv[0] == "stamp":
        errors = stamp(repo)
        print("\n".join(errors) if errors else f"записано: {repo / DOCS / STAMP_FILE}")
        return 1 if errors else 0
    names = argv[2:] or None
    if names and any(n not in SCHEMAS for n in names):
        print(f"файлы индекса: {', '.join(SCHEMAS)}", file=sys.stderr)
        return 2
    errors = check_repo(repo, names)
    print("\n".join(errors) if errors else "OK")
    return 1 if errors else 0
```

Примечание: `.sa-index.json` лежит в `docs/` и не попадает в `changed` (вся `docs/` пропускается).

- [ ] **Step 4: Тесты зелёные.** `python3 -m pytest -q`.

- [ ] **Step 5: Commit.**
```bash
git add scripts/sa_index.py tests/test_sa_index.py
git commit -m "feat: sa_index.py survey/changed/stamp — repo map, incremental mode, index stamp"
```

---

### Task 3: Глобальный индекс — `sa_index_aggregate.py` и `aggregate [--force]`

**Files:**
- Create: `scripts/sa_index_aggregate.py`
- Modify: `scripts/sa_index.py` (`main`: команда `aggregate`)
- Test: `tests/test_sa_index_aggregate.py`

**Interfaces:**
- Consumes: `read_doc`, `load_stamp`, `DOCS`, `EMPTY` из `sa_index`; `write_atomic` из `sa_state`; `resolve_paths` из `sa_paths`.
- Produces: `GENERATED_PREFIX = "<!-- Собрано sa_index.py aggregate"`, `http_key(value) -> str`, `system_tech(docs, today) -> str`, `system_bctc(docs, today) -> str`, `agents_md(repos_root, services, today) -> str`, `aggregate(repos_root: Path, index_dir: Path, services: list[str], today: date | None = None, force: bool = False) -> tuple[list[str], list[str]]` → `(warnings, refused)`; `refused` — имена глобальных файлов, которые не собраны скриптом и не перезаписаны без `force`. CLI: `sa_index.py aggregate [--force]`.

Правила сборки (как в спеке 8.1): поставщик — строки `API` (`<Метод> <Путь>`) и `Сообщения` с `публикует` (`<Брокер>: <Топик>`); потребитель HTTP — строка `Исходящие вызовы`, где `Куда` = сервис-поставщик и `http_key` совпадает; потребитель сообщения — `читает` с тем же брокером (без учёта регистра) и топиком. Не сопоставленные вызовы — строки с поставщиком `? <Куда>` (для сообщений `? не найден`). Связи C2: HTTP — `потребитель → поставщик`, через `HTTP`; сообщения — `публикующий → читающий`, через имя брокера.

- [ ] **Step 1: Падающие тесты** `tests/test_sa_index_aggregate.py`:

```python
from datetime import date

from sa_index_aggregate import GENERATED_PREFIX, aggregate, http_key
from sa_index import main, stamp

SERVICES = ["shop-api", "shop-front", "shop-legacy"]
TODAY = date(2026, 10, 16)


def _all(index_repos):
    repos = [index_repos(name) for name in SERVICES]
    return repos[0].parent


def test_http_key_normalizes_params():
    assert http_key("get /api/orders/:id/") == "GET /api/orders/{}"
    assert http_key("GET /api/orders/${id}") == "GET /api/orders/{}"
    assert http_key("GET  /api/orders/{orderId}") == "GET /api/orders/{}"


def test_aggregate_builds_global_files(index_repos, tmp_path):
    root = _all(index_repos)
    index_dir = tmp_path / "system-docs" / "docs"
    assert aggregate(root, index_dir, SERVICES, today=TODAY) == ([], [])
    tech = (index_dir / "system_tech.md").read_text(encoding="utf-8")
    assert tech.startswith(GENERATED_PREFIX)
    for row in (
        "| shop-api | POST /api/orders | shop-front | Создание заказа |",
        "| shop-api | GET /api/orders/{id} | shop-front | Заказ по id |",
        "| shop-api | Kafka: orders.created | shop-legacy | после создания заказа |",
        "| shop-legacy | POST /invoices.php | shop-api | Создание счёта |",
        "| shop-legacy | GET /index.php | — | Список счетов (HTML) |",
        "| shop-api | shop-legacy | HTTP |",
        "| shop-api | shop-legacy | Kafka |",
        "| shop-front | shop-api | HTTP |",
    ):
        assert row in tech, row
    assert "| Поставщик | Метод или топик | Потребители | Назначение |" in tech
    assert "\n## Связи C2\n" in tech
    bctc = (index_dir / "bctc.md").read_text(encoding="utf-8")
    assert "| Выставление счёта | Счета | shop-legacy |" in bctc
    assert "| Оформление заказа | Заказы | shop-api, shop-front, shop-legacy |" in bctc
    agents = (index_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "| shop-api | — | нет |" in agents
    assert "## Правила актуализации" in agents


def test_aggregate_marks_unmatched_and_stamps(index_repos, tmp_path):
    root = _all(index_repos)
    tech_md = root / "shop-front" / "docs" / "tech.md"
    tech_md.write_text(tech_md.read_text(encoding="utf-8").replace(
        "| shop-api | GET /api/orders/${id} |", "| ext-crm | GET /api/orders/${id} |"), encoding="utf-8")
    stamp(root / "shop-api", today=TODAY)
    index_dir = tmp_path / "idx"
    aggregate(root, index_dir, SERVICES, today=TODAY)
    tech = (index_dir / "system_tech.md").read_text(encoding="utf-8")
    assert "| ? ext-crm | GET /api/orders/${id} | shop-front | Загрузка заказа |" in tech
    assert "| shop-api | GET /api/orders/{id} | — | Заказ по id |" in tech
    assert "| shop-front | ext-crm | HTTP |" in tech
    agents = (index_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "| shop-api | " in agents and "| 2026-10-16 |" in agents


def test_aggregate_skips_broken_and_missing_docs(index_repos, tmp_path):
    root = _all(index_repos)
    (root / "shop-legacy" / "docs" / "tech.md").write_text("# shop-legacy\n", encoding="utf-8")
    (root / "shop-empty").mkdir()
    warnings, refused = aggregate(root, tmp_path / "idx", SERVICES + ["shop-empty"], today=TODAY)
    assert refused == []
    assert any(w.startswith("shop-legacy: docs/tech.md: нет раздела") for w in warnings)
    assert "| shop-empty | — | нет |" in (tmp_path / "idx" / "AGENTS.md").read_text(encoding="utf-8")


def test_aggregate_refuses_human_files(index_repos, tmp_path):
    root = _all(index_repos)
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "bctc.md").write_text("# Ручной файл\n", encoding="utf-8")
    warnings, refused = aggregate(root, index_dir, SERVICES, today=TODAY)
    assert refused == ["bctc.md"]
    assert (index_dir / "bctc.md").read_text(encoding="utf-8") == "# Ручной файл\n"
    assert (index_dir / "system_tech.md").is_file()
    assert aggregate(root, index_dir, SERVICES, today=TODAY, force=True) == ([], [])
    assert (index_dir / "bctc.md").read_text(encoding="utf-8").startswith(GENERATED_PREFIX)


def test_cli_aggregate(index_repos, tmp_path, monkeypatch, capsys):
    root = _all(index_repos)
    monkeypatch.setenv("SA_REPOS_ROOT", str(root))
    monkeypatch.delenv("SA_SYSTEM_DOCS", raising=False)
    assert main(["aggregate"]) == 0
    assert (root / "system-docs" / "docs" / "system_tech.md").is_file()
    assert "записано:" in capsys.readouterr().out
    (root / "system-docs" / "docs" / "bctc.md").write_text("# Ручной\n", encoding="utf-8")
    assert main(["aggregate"]) == 1
    assert "aggregate --force" in capsys.readouterr().out
    assert main(["aggregate", "--force"]) == 0
```

- [ ] **Step 2: Запусти — падает** (`ModuleNotFoundError: sa_index_aggregate`).

- [ ] **Step 3: Реализация** `scripts/sa_index_aggregate.py`:

```python
"""Глобальный индекс системы из docs/ сервисов: system_tech.md, bctc.md, AGENTS.md."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from sa_artifacts import ArtifactError
from sa_index import DOCS, EMPTY, load_stamp, read_doc
from sa_state import write_atomic

GENERATED_PREFIX = "<!-- Собрано sa_index.py aggregate"
GLOBAL_FILES = ("system_tech.md", "bctc.md", "AGENTS.md")
PARAM_RE = re.compile(r"\$\{[^}]*\}|\{[^}/]*\}|:[A-Za-z_]\w*")
NL = "\n"


def _generated(today: str) -> str:
    return f"{GENERATED_PREFIX} {today}. Не править вручную: файл пересобирает /sa-index-docs. -->"


def http_key(value: str) -> str:
    parts = value.split(None, 1)
    if len(parts) != 2:
        return value.strip().lower()
    path = PARAM_RE.sub("{}", parts[1].strip()).rstrip("/") or "/"
    return f"{parts[0].upper()} {path}"


def _rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if next(iter(row.values())) != EMPTY]


def load_services(repos_root: Path, services: list[str]) -> tuple[dict[str, dict], list[str]]:
    docs: dict[str, dict] = {}
    warnings = []
    for service in services:
        repo = repos_root / service
        loaded = {}
        for name in ("tech.md", "bctc.md"):
            if not (repo / DOCS / name).is_file():
                continue
            try:
                loaded[name] = read_doc(repo, name)
            except ArtifactError as exc:
                warnings.append(f"{service}: {exc} — файл пропущен")
        docs[service] = loaded
    return docs, warnings


def _table(header: list[str], rows: list[str]) -> str:
    empty = "| нет |" + " — |" * (len(header) - 1)
    lines = [f"| {' | '.join(header)} |", "|" + "---|" * len(header), *(rows or [empty])]
    return NL.join(lines) + NL


def system_tech(docs: dict[str, dict], today: str) -> str:
    providers = []  # (сервис, отображение, ключ, назначение, через)
    calls = []      # (сервис, куда или None, отображение, ключ, назначение)
    for service, loaded in docs.items():
        tech = loaded.get("tech.md")
        if not tech:
            continue
        for row in _rows(tech["API"]):
            shown = f"{row['Метод']} {row['Путь']}"
            providers.append((service, shown, ("HTTP", http_key(shown)), row["Назначение"], "HTTP"))
        for row in _rows(tech["Исходящие вызовы"]):
            shown = row["Метод или топик"]
            calls.append((service, row["Куда"], shown, ("HTTP", http_key(shown)), row["Назначение"]))
        for row in _rows(tech["Сообщения"]):
            shown = f"{row['Брокер']}: {row['Топик или очередь']}"
            key = (row["Брокер"].lower(), row["Топик или очередь"])
            if row["Направление"] == "публикует":
                providers.append((service, shown, key, row["Когда"], row["Брокер"]))
            elif row["Направление"] == "читает":
                calls.append((service, None, shown, key, row["Когда"]))
    rows, links, matched = [], set(), set()
    for provider, shown, key, purpose, via in providers:
        users = set()
        for index, (consumer, target, _, call_key, _) in enumerate(calls):
            if call_key == key and target in (None, provider) and consumer != provider:
                users.add(consumer)
                matched.add(index)
                links.add((consumer, provider, via) if via == "HTTP" else (provider, consumer, via))
        rows.append(f"| {provider} | {shown} | {', '.join(sorted(users)) or '—'} | {purpose} |")
    for index, (consumer, target, shown, _, purpose) in enumerate(calls):
        if index in matched:
            continue
        rows.append(f"| ? {target or 'не найден'} | {shown} | {consumer} | {purpose} |")
        if target:
            links.add((consumer, target, "HTTP"))
    link_rows = [f"| {a} | {b} | {via} |" for a, b, via in sorted(links)]
    return (
        f"{_generated(today)}{NL}# API и сообщения{NL}{NL}"
        + _table(["Поставщик", "Метод или топик", "Потребители", "Назначение"], rows)
        + f"{NL}## Связи C2{NL}{NL}"
        + _table(["Из", "В", "Через"], link_rows)
    )


def system_bctc(docs: dict[str, dict], today: str) -> str:
    scenarios: dict[str, dict] = {}
    for service, loaded in docs.items():
        bctc = loaded.get("bctc.md")
        if not bctc:
            continue
        for row in _rows(bctc["Сценарии"]):
            entry = scenarios.setdefault(row["Сценарий"], {"domains": [], "services": set()})
            if row["Домен"] not in entry["domains"]:
                entry["domains"].append(row["Домен"])
            entry["services"].add(service)
    rows = [
        f"| {name} | {' / '.join(entry['domains'])} | {', '.join(sorted(entry['services']))} |"
        for name, entry in sorted(scenarios.items())
    ]
    return f"{_generated(today)}{NL}# Сценарии и сервисы{NL}{NL}" + _table(["Сценарий", "Домен", "Сервисы"], rows)


def agents_md(repos_root: Path, services: list[str], today: str) -> str:
    rows = []
    for service in services:
        data = load_stamp(repos_root / service)
        sha = (data.get("sha") or "—")[:7]
        rows.append(f"| {service} | {sha} | {data.get('indexed', 'нет')} |")
    where = [
        "| system_tech.md | Сводная таблица API и сообщений: поставщик, потребители; связи C2 |",
        "| bctc.md | Сценарии → домен → сервисы |",
        "| <сервис>/docs/tech.md | API, исходящие вызовы, сообщения, фоновые задачи сервиса со ссылками файл:строка |",
        "| <сервис>/docs/DB.md | Таблицы и связи сервиса |",
        "| <сервис>/docs/bctc.md | Домены и сценарии сервиса |",
        "| <сервис>/docs/.sa-index.json | SHA и дата последней индексации |",
    ]
    rules = [
        "- После значимых изменений сервиса запустите `/sa-index-docs <сервис>`: перечитываются только файлы, изменённые с SHA последней индексации.",
        "- Руками правьте только `docs/` сервисов; файлы этой папки пересобираются из них.",
        "- Ячейки, начинающиеся с `?`, — неоднозначности: проверьте и снимите знак.",
        "- Строка с поставщиком `? <имя>` — вызов, для которого не найден метод у поставщика или поставщик не проиндексирован.",
    ]
    return (
        f"{_generated(today)}{NL}# Индекс системы{NL}{NL}## Где что лежит{NL}{NL}"
        + _table(["Файл", "Что внутри"], where)
        + f"{NL}## Сервисы{NL}{NL}"
        + _table(["Сервис", "SHA", "Проиндексирован"], rows)
        + f"{NL}## Правила актуализации{NL}{NL}" + NL.join(rules) + NL
    )


def aggregate(
    repos_root: Path, index_dir: Path, services: list[str], today: date | None = None, force: bool = False,
) -> tuple[list[str], list[str]]:
    stamp_day = (today or date.today()).isoformat()
    docs, warnings = load_services(repos_root, services)
    texts = {
        "system_tech.md": system_tech(docs, stamp_day),
        "bctc.md": system_bctc(docs, stamp_day),
        "AGENTS.md": agents_md(repos_root, services, stamp_day),
    }
    index_dir.mkdir(parents=True, exist_ok=True)
    refused = []
    for name in GLOBAL_FILES:
        path = index_dir / name
        if path.is_file() and not force and not path.read_text(encoding="utf-8", errors="replace").startswith(GENERATED_PREFIX):
            refused.append(name)
            continue
        write_atomic(path, texts[name])
    return warnings, refused
```

В `scripts/sa_index.py`: `USAGE` дополнить ` | aggregate [--force]`; в начале `main`:

```python
    if argv and argv[0] == "aggregate":
        return _aggregate_cli(argv[1:])
```

и функцию перед `main`:

```python
def _aggregate_cli(args: list[str]) -> int:
    if args not in ([], ["--force"]):
        print(USAGE, file=sys.stderr)
        return 2
    from sa_index_aggregate import GLOBAL_FILES, aggregate
    from sa_paths import resolve_paths

    paths = resolve_paths()
    if not paths["repos_exists"]:
        print(f"нет папки репозиториев {paths['repos_root']}", file=sys.stderr)
        return 1
    index_dir = Path(paths["index_dir"])
    warnings, refused = aggregate(Path(paths["repos_root"]), index_dir, paths["services"], force=bool(args))
    written = [str(index_dir / n) for n in GLOBAL_FILES if n not in refused]
    print("записано: " + ", ".join(written))
    for warning in warnings:
        print(f"предупреждение: {warning}")
    for name in refused:
        print(f"{name}: файл не собран sa_index.py — не перезаписан; после согласия аналитика запустите aggregate --force")
    return 1 if refused else 0
```

- [ ] **Step 4: Тесты зелёные.** `python3 -m pytest -q`.

- [ ] **Step 5: Commit.**
```bash
git add scripts/sa_index.py scripts/sa_index_aggregate.py tests/test_sa_index_aggregate.py
git commit -m "feat: sa_index.py aggregate — global system_tech/bctc/AGENTS from service docs"
```

---

### Task 4: Справочники `shared/index/` и правка `adapters.md`

**Files:**
- Create: `shared/index/docs-schema.md`, `shared/index/stack-hints.md`
- Modify: `shared/access/adapters.md:31`
- Test: `tests/test_shared_docs.py` (дописать)

**Interfaces:**
- Consumes: `SCHEMAS`, `DIRECTIONS`, `SPLIT_THRESHOLD` из `sa_index`; `GLOBAL_FILES` из `sa_index_aggregate`.
- Produces: файлы, на которые ссылаются агент и скил (Task 5).

- [ ] **Step 1: Падающие тесты** — дописать в `tests/test_shared_docs.py`:

```python
def test_index_schema_doc_matches_sa_index():
    from sa_index import DIRECTIONS, SCHEMAS, STAMP_FILE
    from sa_index_aggregate import GLOBAL_FILES

    text = (ROOT / "shared/index/docs-schema.md").read_text(encoding="utf-8")
    for heading in ("## Общие правила", "## tech.md", "## DB.md", "## bctc.md", "## .sa-index.json", "## Глобальные файлы"):
        assert f"\n{heading}\n" in text, heading
    for name, sections in SCHEMAS.items():
        for section, columns in sections.items():
            assert f"`## {section}`" in text, section
            assert f"| {' | '.join(columns)} |" in text, section
    for value in DIRECTIONS:
        assert f"`{value}`" in text, value
    for name in GLOBAL_FILES:
        assert f"`{name}`" in text, name
    assert STAMP_FILE in text


def test_stack_hints_headings():
    text = (ROOT / "shared/index/stack-hints.md").read_text(encoding="utf-8")
    for heading in ("## Общее", "## .NET", "## Laravel", "## PHP без фреймворка", "## React и другие фронты"):
        assert f"\n{heading}\n" in text, heading


def test_adapters_no_branch_exception():
    text = (ROOT / "shared/access/adapters.md").read_text(encoding="utf-8")
    assert "отдельную ветку" not in text
    assert "/sa-index-docs" in text
```

- [ ] **Step 2: Запусти — падает** (нет файлов).

- [ ] **Step 3: `shared/index/docs-schema.md`:**

````markdown
# Схема индекса docs/

Индекс строит `/sa-index-docs`; проверяет `python3 <плагин>/scripts/sa_index.py check <repo>`. Файл не по схеме валидатор не пропустит.

## Общие правила

- Три файла в `docs/` репозитория сервиса: `tech.md`, `DB.md`, `bctc.md`. Первая строка каждого — `# <сервис>`.
- Разделы — заголовки `## <раздел>` строго из списка ниже, под каждым ровно одна таблица с заголовком как в схеме. Другие разделы можно добавлять — валидатор их не читает.
- Одна строка — один объект. Пустых ячеек нет. Внутри ячеек нет `|` — заменяй на «/».
- `Код` — ссылки `путь:строка` от корня репозитория через `, `: `routes/api.php:6, app/Http/Controllers/OrderController.php:10`. Файл должен существовать, строка — быть в файле. Указывай строку объявления: маршрута, метода, `CREATE TABLE`, `subscribe`, вызова клиента.
- Неоднозначность не угадывай: ячейка начинается с `?` и коротко говорит, в чём сомнение (`? orders.id (shop-api)`). `Код` всегда точный.
- Раздел без объектов — одна строка: первая ячейка `нет`, остальные `—`.

## tech.md

`## API` — входящие HTTP/RPC-методы и страницы, которые вызывают снаружи.

| Метод | Путь | Назначение | Код |
|---|---|---|---|

Метод — `GET`, `POST` …; для страницы-скрипта legacy PHP — метод, которым её вызывают. Путь — как в маршруте, параметры в `{}`.

`## Исходящие вызовы` — HTTP/RPC-вызовы других сервисов и внешних систем. Сообщения сюда не пишутся.

| Куда | Метод или топик | Назначение | Код |
|---|---|---|---|

Куда — имя сервиса (как папка репозитория) или внешней системы. Метод или топик — `МЕТОД /путь` так, как его видит поставщик.

`## Сообщения` — Kafka, RabbitMQ и другие брокеры.

| Брокер | Топик или очередь | Направление | Когда | Код |
|---|---|---|---|---|

Направление — `публикует` или `читает`.

`## Фоновые задачи` — cron, очереди, воркеры, консольные команды по расписанию.

| Задача | Запуск | Что делает | Код |
|---|---|---|---|

## DB.md

`## Таблицы` — таблицы, которыми сервис владеет или в которые пишет.

| Таблица | Назначение | Ключевые поля | Код |
|---|---|---|---|

`Код` — миграция или модель; без миграций — SQL в коде (`CREATE`, `INSERT`, `UPDATE`).

`## Связи` — внешние ключи и логические связи, в том числе с таблицами других сервисов.

| Из | В | Тип | Код |
|---|---|---|---|

## bctc.md

`## Сценарии` — бизнес-сценарии, в которых участвует сервис.

| Домен | Сценарий | Роль сервиса | Точки входа | Код |
|---|---|---|---|---|

Имя сценария — короткое, в форме действия («Оформление заказа»). Глобальный `bctc.md` объединяет сервисы по точному совпадению имени: если сценарий уже есть в индексе системы, используй его имя.

## .sa-index.json

`docs/.sa-index.json` пишет `sa_index.py stamp` после успешной проверки: `sha` (HEAD), `indexed` (дата), `plugin` (версия), `files` (sha256 каждого файла индекса). Руками не правится. Хэш файла не совпал — файл правил человек.

## Глобальные файлы

Собирает `sa_index.py aggregate` в `index_dir` из `sa_paths.py`; руками не правятся (первая строка — комментарий «Собрано sa_index.py aggregate»). Файл без этой строки скрипт не перезаписывает без `--force`.

- `system_tech.md` — `| Поставщик | Метод или топик | Потребители | Назначение |`: поставщик — из `API` и сообщений `публикует`; потребители — из `Исходящих вызовов` (`Куда` = поставщик, совпадают метод и путь с точностью до имён параметров) и сообщений `читает` того же брокера и топика. Вызов без пары — строка с поставщиком `? <Куда>`. Раздел `## Связи C2` — `| Из | В | Через |`: HTTP — от вызывающего к поставщику, сообщения — от публикующего к читающему.
- `bctc.md` — `| Сценарий | Домен | Сервисы |`.
- `AGENTS.md` — где что лежит, SHA и дата индексации каждого сервиса, правила актуализации.
````

- [ ] **Step 4: `shared/index/stack-hints.md`:**

```markdown
# Где искать: подсказки по стекам

Стек и папки-подсказки печатает `sa_index.py survey`. Начинай с подсказок, ищи Grep с `-n`, читай фрагментами.

## Общее

- Конфиги окружения (`.env.example`, `appsettings*.json`, `config/*.php`, `docker-compose*.yml`) — адреса других сервисов и брокеров: по ним понятно, куда идут исходящие вызовы (`Куда`).
- Брокеры: grep `kafka`, `rdkafka`, `KafkaProducer`, `subscribe`, `RabbitMQ`, `amqp`, `basic_publish`, `basic_consume`, `Confluent.Kafka`, `MassTransit`.
- HTTP-клиенты: grep `Http::`, `Guzzle`, `curl_init`, `file_get_contents('http`, `HttpClient`, `fetch(`, `axios`.
- Расписание: `crontab`, `cron`, `schedule(`, `Schedule::`, `IHostedService`, `BackgroundService`, `Hangfire`, `Quartz`.

## .NET

- API: атрибуты `[Http(Get|Post|Put|Delete)]`, `[Route]` в `Controllers/`; minimal API — `app.Map(Get|Post)` в `Program.cs`.
- БД: `DbContext` и `DbSet<>`, папка `Migrations/` (`migrationBuilder.CreateTable`), `[Table]`; Dapper — SQL-строки.
- Фон: `BackgroundService`, `IHostedService`, Hangfire/Quartz-джобы; консьюмеры MassTransit/Confluent.

## Laravel

- API: `routes/api.php`, `routes/web.php`; контроллеры `app/Http/Controllers`.
- БД: `database/migrations` (`Schema::create`, `Schema::table`), модели `app/Models` (`$table`, связи `belongsTo`/`hasMany` → раздел `Связи`).
- Фон: `app/Jobs` (`ShouldQueue`), `app/Console/Kernel.php` (`schedule`), `app/Listeners`, консьюмеры в `app/Console/Commands`.
- Фронт внутри проекта: `resources/js` (Vue/React), `resources/views` (Blade) — экраны и вызовы API для `bctc.md` и `Исходящих вызовов`.

## PHP без фреймворка

- Точки входа — PHP-файлы в корне и папках, открываемые по URL: путь = путь файла (`/invoices.php`); метод — по суперглобальным `_POST`/`_GET`. Ищи `.htaccess` с `RewriteRule` — он меняет пути.
- БД: `mysql_query`, `mysqli_`, `PDO`, `->query(` — таблицы по SQL (`FROM`, `INTO`, `UPDATE`); `Код` — строка SQL.
- Шаблоны (`templates/`, `*.tpl`, `*.phtml`, Smarty) — экраны для `bctc.md`, но не API.
- Фон — скрипты в `cron/`, `scripts/`, строки crontab в комментариях или в `crontab`-файлах.

## React и другие фронты

- Своих API и БД нет: `API`, `Таблицы`, `Связи` — строка `нет`.
- `Исходящие вызовы` — `fetch`, `axios`, клиенты в `src/api`, `services/`: `Куда` — бэкенд по базовому URL из конфига; если бэкенд неясен — `? <имя из конфига>`.
- `bctc.md` — экраны и роуты (`react-router`, `pages/`, `routes`): сценарий, роль экрана, точка входа — путь экрана.
```

- [ ] **Step 5: `shared/access/adapters.md`, строка 31** — заменить на:

```markdown
- Только чтение. Коммиты и пуши в репозитории сервисов — запрещены. `/sa-index-docs` пишет только файлы `docs/` в рабочую копию, без веток и коммитов.
```

- [ ] **Step 6: Тесты зелёные.** `python3 -m pytest -q`.

- [ ] **Step 7: Commit.**
```bash
git add shared/index shared/access/adapters.md tests/test_shared_docs.py
git commit -m "docs: docs/ index schema and stack hints; adapters drop branch exception"
```

---

### Task 5: Субагент `docs-indexer`, скил `/sa-index-docs`, e2e-фикстура, README

**Files:**
- Create: `agents/docs-indexer.md`, `skills/sa-index-docs/SKILL.md`, `tests/fixtures/e2e/index-repos/make_repos.py`
- Modify: `README.md` (строка `/sa-index-docs` в «Команды», раздел «Сквозная проверка стадий»), `tests/test_skills_contract.py`, `tests/test_plugin_structure.py`, `tests/test_e2e_fixture.py`

**Interfaces:**
- Consumes: CLI `sa_index.py survey|changed|check|stamp|aggregate [--force]` (Task 1–3), `shared/index/*.md` (Task 4), `sa_paths.py`.
- Produces: скил и агент; `make_repos.py <target> [--change]`.

- [ ] **Step 1: Падающие тесты.** В `tests/test_skills_contract.py` дописать:

```python
def test_sa_index_docs_contract():
    _assert_contains(
        _skill("sa-index-docs"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_index.py survey <repos_root>/<сервис>",
            "sa_index.py changed <repos_root>/<сервис>",
            "sa_index.py check <repos_root>/<сервис>",
            "sa_index.py stamp <repos_root>/<сервис>",
            "sa_index.py aggregate",
            "aggregate --force",
            "sa-skills:docs-indexer",
            "--full",
            "правка человека",
            "split",
            "<repos_root>/<сервис>/docs/",
            "<плагин>/shared/index/docs-schema.md",
            "без веток и коммитов",
        ),
    )
```

В `tests/test_plugin_structure.py` дописать:

```python
def test_docs_indexer_contract():
    from sa_index import SCHEMAS

    text = (ROOT / "agents/docs-indexer.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert meta["model"] == "sonnet"
    assert set(t.strip() for t in meta["tools"].split(",")) == {"Read", "Grep", "Glob", "Write", "Edit", "Bash"}
    for fragment in ("sa_index.py check", "<плагин>/shared/index/docs-schema.md", "<плагин>/shared/index/stack-hints.md", "`?`", "## Инкрементальный режим", "## Что вернуть"):
        assert fragment in text, fragment
    for name in SCHEMAS:
        assert name in text, name
```

В `tests/test_e2e_fixture.py` дописать:

```python
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
```

(если в `test_e2e_fixture.py` нет `from pathlib import Path` — добавить).

- [ ] **Step 2: Запусти — падает.** `python3 -m pytest -q`.

- [ ] **Step 3: `tests/fixtures/e2e/index-repos/make_repos.py`:**

```python
#!/usr/bin/env python3
"""E2E /sa-index-docs: копирует shop-* в <target> и делает git-репозитории; --change — новый маршрут в shop-api."""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICES = ("shop-api", "shop-legacy", "shop-front")
NEW_ROUTE = "Route::delete('/api/orders/{id}', [OrderController::class, 'destroy']);\n"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=SA", "-c", "user.email=sa@example.com", *args], check=True)


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--change"):
        print("usage: make_repos.py <target> [--change]", file=sys.stderr)
        return 2
    target = Path(argv[0]).absolute()
    if len(argv) == 2:
        repo = target / "shop-api"
        routes = repo / "routes" / "api.php"
        routes.write_text(routes.read_text(encoding="utf-8") + NEW_ROUTE, encoding="utf-8")
        git(repo, "commit", "-qam", "delete order route")
        return 0
    for name in SERVICES:
        repo = target / name
        shutil.copytree(HERE / name, repo)
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: `agents/docs-indexer.md`:**

```markdown
---
name: docs-indexer
description: Читает код одного репозитория сервиса любого стека (.NET, Laravel, PHP без фреймворка, React) и пишет индекс docs/tech.md, docs/DB.md, docs/bctc.md по схеме со ссылками файл:строка, затем проверяет его sa_index.py check. Вызывается скилом /sa-index-docs.
tools: Read, Grep, Glob, Write, Edit, Bash
model: sonnet
---

Ты — индексатор кода для системных аналитиков. Работаешь в одном репозитории: код только читаешь, пишешь только файлы `docs/` этого репозитория.

## Вход

В задании тебе передают:
- путь к репозиторию `<repo>` и путь к плагину `<плагин>`;
- вывод `sa_index.py survey` — стек, число исходников, папки-подсказки;
- какие файлы писать: все три (`tech.md`, `DB.md`, `bctc.md`) или один из них;
- режим: полный или инкрементальный (тогда — вывод `sa_index.py changed`);
- имена сценариев из глобального `bctc.md`, если он есть.

## Перед началом

Прочитай `<плагин>/shared/index/docs-schema.md` — точные разделы и колонки — и в `<плагин>/shared/index/stack-hints.md` разделы «Общее» и разделы стеков из `survey`.

## Полный режим

1. Иди от папок-подсказок `survey`, ищи Grep с номерами строк, читай файлы фрагментами вокруг найденного, не целиком. В `vendor/`, `node_modules/`, `bin/`, `obj/` не заходи.
2. Для каждой строки таблицы найди точную строку объявления — она идёт в `Код`. Нет строки — нет записи.
3. Чего не понял — не угадывай: ячейка начинается с `?` и говорит, в чём сомнение. Раздел без объектов — строка `нет`, остальные ячейки `—`.
4. `Куда` в исходящих вызовах — имя сервиса как папка репозитория, если его видно по конфигу или URL; иначе `? <что видно>`.
5. Сценарии называй так же, как в глобальном `bctc.md`, если сценарий там уже есть.
6. Пиши файлы по абсолютному пути `<repo>/docs/<файл>` (Write), первая строка — `# <имя папки репозитория>`.

## Инкрементальный режим

1. Строки из `rows` вывода `changed` ссылаются на изменённые файлы — перепроверь каждую: обнови `Код` (строки сдвигаются), назначение, удали строку, если объекта больше нет (файл `(удалён)`).
2. Изменённые файлы из `files` просмотри на новые объекты и добавь строки.
3. Остальные строки не трогай — там могут быть правки человека. Правь Edit, не переписывай файл целиком.

## Проверка

После записи запусти `python3 <плагин>/scripts/sa_index.py check <repo> <файл…>` (только твои файлы). Исправляй, пока не `OK`. Не можешь найти точную строку — удали строку таблицы и упомяни это в заметках.

## Что вернуть

Не больше 10 строк: по каждому файлу — число строк по разделам и сколько ячеек с `?`; что искал и не нашёл; итог `check`. Таблицы и код в ответ не копируй — они уже в файлах.

## Чего не делать

- Не меняй ничего вне `<repo>/docs/`; не трогай `docs/.sa-index.json`.
- Никаких `git checkout`, `commit`, `pull`, `push`.
- Не пиши в ячейки `|` — заменяй на «/».
```

- [ ] **Step 5: `skills/sa-index-docs/SKILL.md`:**

```markdown
---
name: sa-index-docs
description: Строит и обновляет индекс docs/ в репозиториях сервисов — tech.md (API, исходящие вызовы, сообщения, фоновые задачи), DB.md (таблицы и связи), bctc.md (домены и сценарии) со ссылками файл:строка — и собирает глобальные system_tech.md, bctc.md, AGENTS.md в system-docs. Код читает субагент docs-indexer, по одному на сервис; повторный запуск инкрементален — только файлы, изменённые с последней индексации. Пишет только файлы в рабочую копию, без веток и коммитов. Используй, когда аналитик пишет /sa-index-docs, просит построить или обновить индекс /docs сервиса или всех сервисов, или /tdd-impact сообщил, что индекса нет.
allowed-tools: Bash(python3:*)
---

# /sa-index-docs [сервис|all] [--full]

Входы: код репозиториев сервисов (читает субагент), вывод `sa_index.py`. Выходы: `<repos_root>/<сервис>/docs/` и глобальные файлы в `index_dir`. Только файлы в рабочую копию, без веток и коммитов: что коммитить и как делать MR — решают разработчики сервиса.

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Все команды — из рабочей папки аналитика.

## Перед началом

Прочитай `<плагин>/shared/index/docs-schema.md`. Код сам не читай — его читает `docs-indexer`. Файлы `docs/` сам не пиши.

## Шаги

1. **Пути.** `python3 <плагин>/scripts/sa_paths.py` — `repos_root`, `services`, `index_dir`. `repos_root … (нет)` — скажи, что папки репозиториев нет (`SA_REPOS_ROOT`), и остановись.
2. **Цели.** Аргумент — имя из `services`: этот сервис; `all` — все `services`; нет аргумента — покажи `services` и спроси. Имени нет в `services` — покажи список и остановись. `--full` во вводе — полный проход для всех целей.
3. **Карта.** По каждой цели `python3 <плагин>/scripts/sa_index.py survey <repos_root>/<сервис>`. Строка `branch` говорит «отстаёт» — предупреди аналитика, что индекс будет по устаревшей ветке, `pull` не делай. Режим сервиса — `mode` из `survey`, при `--full` — полный.
4. **Правки человека.** Соберите все файлы `docs` со статусом `правка человека` в сервисах с полным режимом и спроси аналитика одним вопросом: перезаписать или оставить. Оставить — этот файл субагенту не передавай. В инкрементальном режиме не спрашивай: субагент правит только строки по изменённым файлам.
5. **Изменения.** Для инкрементальных: `python3 <плагин>/scripts/sa_index.py changed <repos_root>/<сервис>`. `files` = `нет` и все три файла `docs` есть — сервис актуален, субагента не вызывай (переходи к шагу 7). Файла `docs` нет — для него полный проход.
6. **Субагенты.** По `sa-skills:docs-indexer` на сервис — при нескольких целях вызовы одним сообщением, параллельно, не больше 4 за раз. Если в `survey` `split: да` — вместо одного три субагента на сервис, по файлу каждому. В задании:
   - `<repos_root>/<сервис>` и путь плагина `<плагин>`;
   - вывод `survey` как есть;
   - файлы, которые писать в `<repos_root>/<сервис>/docs/` (без оставленных на шаге 4);
   - режим; для инкрементального — вывод `changed` как есть;
   - если в `index_dir` есть `bctc.md` — путь к нему: «имена сценариев бери оттуда».
7. **Проверка и отметка.** По каждому сервису `python3 <плагин>/scripts/sa_index.py check <repos_root>/<сервис>`. Ошибки — передай их тому же субагенту на исправление один раз; остались — сервис не отмечай, перечисли ошибки в итоге. `OK` — `python3 <плагин>/scripts/sa_index.py stamp <repos_root>/<сервис>`.
8. **Глобальные файлы.** `python3 <плагин>/scripts/sa_index.py aggregate`. Вывод говорит, что файл не собран скриптом и не перезаписан, — покажи аналитику и спроси, перезаписать ли; да — `python3 <плагин>/scripts/sa_index.py aggregate --force`. Предупреждения о пропущенных файлах — в итог.
9. **Итог аналитику**, коротко:
   - по сервису: режим, строки по файлам и ячейки с `?` (из ответа субагента), отмечен ли;
   - актуальные сервисы без изменений;
   - сервисы с ошибками `check` и пропущенные `aggregate` файлы;
   - что изменились рабочие копии `<repos_root>/<сервис>/docs/` и `index_dir`: коммит и MR — на стороне разработчиков сервиса;
   - ячейки с `?` стоит проверить с разработчиками.

## Чего не делать

- Не читай код и не пиши `docs/` сам — только через `docs-indexer`.
- Не делай `git checkout`, `commit`, `pull`, `push`, не создавай ветки.
- Не правь `docs/.sa-index.json` и глобальные файлы руками — их пишут `stamp` и `aggregate`.
```

- [ ] **Step 6: README.** В таблице «Команды» строку `/sa-index-docs` заменить на `| `/sa-index-docs [сервис|all] [--full]` | Индекс `docs/` по коду сервисов и глобальный индекс системы | готово |` (сверь с форматом соседних строк — последняя колонка у готовых команд). В раздел «Сквозная проверка стадий» добавить подраздел:

````markdown
### /sa-index-docs

```bash
python3 tests/fixtures/e2e/index-repos/make_repos.py /tmp/sa-e2e-index/repos
cd /tmp/sa-e2e-index
SA_REPOS_ROOT=/tmp/sa-e2e-index/repos claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/sa-index-docs all"
python3 <repo>/tests/fixtures/e2e/index-repos/make_repos.py /tmp/sa-e2e-index/repos --change
SA_REPOS_ROOT=/tmp/sa-e2e-index/repos claude --plugin-dir <repo> --model sonnet --allowedTools "Bash(python3:*) Read Write Edit Grep Glob Agent" -p "/sa-index-docs shop-api"
```

Ожидается: после первого запуска `sa_index.py check` даёт `OK` для трёх сервисов, в `repos/system-docs/docs/system_tech.md` есть `POST /api/orders` с потребителем `shop-front` и `Kafka: orders.created` с `shop-legacy`; второй запуск идёт в режиме `incremental` и добавляет в `shop-api/docs/tech.md` строку `DELETE /api/orders/{id}`.
````

- [ ] **Step 7: Тесты зелёные.** `python3 -m pytest -q`.

- [ ] **Step 8: Commit.**
```bash
git add agents/docs-indexer.md skills/sa-index-docs tests/fixtures/e2e/index-repos/make_repos.py README.md tests/test_skills_contract.py tests/test_plugin_structure.py tests/test_e2e_fixture.py
git commit -m "feat: /sa-index-docs skill and docs-indexer subagent; e2e repos"
```

---

## После задач

1. Одно ревью всей ветки (sonnet-субагент по diff `main..HEAD`), исправления одним коммитом.
2. Один e2e-прогон по README «/sa-index-docs» (два шага), проверить ожидания вручную.
3. Обновить память о статусе проекта.
