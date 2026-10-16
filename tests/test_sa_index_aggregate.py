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


def test_http_key_strips_scheme_query_fragment():
    assert http_key("POST http://orders.local/api/x?y=1") == "POST /api/x"
    assert http_key("GET https://h:8080/api/a/:id#frag") == "GET /api/a/{}"


def test_system_tech_keeps_unclear_direction_messages():
    from sa_index_aggregate import system_tech

    tech = {"API": [], "Исходящие вызовы": [], "Фоновые задачи": [], "Сообщения": [
        {"Брокер": "Kafka", "Топик или очередь": "t1", "Направление": "? читает или публикует", "Когда": "по событию", "Код": "a.php:1"},
    ]}
    text = system_tech({"svc": {"tech.md": tech}}, "2026-10-16")
    assert "| ? | Kafka: t1 | svc | по событию — направление неясно |" in text


def _front_unknown_target(root):
    tech_md = root / "shop-front" / "docs" / "tech.md"
    tech_md.write_text(tech_md.read_text(encoding="utf-8").replace(
        "| shop-api | ", "| ? бэкенд /api | "), encoding="utf-8")


def test_unknown_target_matches_single_provider(index_repos, tmp_path):
    root = _all(index_repos)
    _front_unknown_target(root)
    aggregate(root, tmp_path / "idx", SERVICES, today=TODAY)
    tech = (tmp_path / "idx" / "system_tech.md").read_text(encoding="utf-8")
    assert "| shop-api | POST /api/orders | ? shop-front | Создание заказа |" in tech
    assert "| shop-front | shop-api | HTTP ? |" in tech
    assert "? ?" not in tech


def test_unknown_target_with_two_providers_stays_unmatched(index_repos, tmp_path):
    root = _all(index_repos)
    _front_unknown_target(root)
    legacy = root / "shop-legacy" / "docs" / "tech.md"
    text = legacy.read_text(encoding="utf-8")
    row = "| POST | /invoices.php | Создание счёта | invoices.php:3 |"
    assert row in text
    legacy.write_text(text.replace(row, row + "\n| POST | /api/orders | Дубль | invoices.php:3 |"), encoding="utf-8")
    aggregate(root, tmp_path / "idx", SERVICES, today=TODAY)
    tech = (tmp_path / "idx" / "system_tech.md").read_text(encoding="utf-8")
    assert "| ? бэкенд /api | POST /api/orders | shop-front | Создание заказа |" in tech
    assert "? ?" not in tech
    assert "| shop-front | ? бэкенд /api | HTTP |" in tech
    assert "| shop-api | GET /api/orders/{id} | ? shop-front | Заказ по id |" in tech
