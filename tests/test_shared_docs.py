from pathlib import Path

import pytest

from sa_state import STAGES
from sa_validate import BRD_COLUMNS, CONFIDENCE, CONTEXT_COLUMNS, DECISION_COLUMNS, IMPACT_COLUMNS, IMPACTS, KINDS, SCOPES

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_HEADINGS = {
    "shared/rules/ai-rules.md": ["## Факт и допущение", "## Источники", "## Идентификаторы", "## Работа с артефактами", "## Чего не делать"],
    "shared/rules/writing-style.md": ["## Общие правила", "## Как есть и как будет", "## Оформление", "## Запрещённые формулировки"],
    "shared/rules/question-routing.md": ["## Кому адресовать", "## Как формулировать для PO", "## Как формулировать для аналитика", "## Смешанные вопросы", "## Примеры"],
    "shared/rules/brd-checklist.md": ["## Обязательные пункты", "## Желательные пункты", "## Как принимать решение"],
    "shared/rules/artifact-writing.md": ["## Пути", "## Вопросы", "## Ссылки", "## ID", "## Таблицы", "## Повторный запуск"],
    "shared/access/adapters.md": ["## Порядок выбора", "## Jira", "## Confluence", "## Git", "## Ручной режим", "## Запись выбора"],
    "shared/schemas/artifacts.md": ["## Общие правила", "## sources/BRD.md", "## impact-map.md", "## context.md", "## questions.md", "## draft/ и draft.md", "## review.md", "## decisions.md", "## state.json", "## Проверка"],
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


def test_routing_examples_carry_refs():
    text = (ROOT / "shared/rules/question-routing.md").read_text(encoding="utf-8")
    section = text.split("\n## Примеры\n", 1)[1]
    rows = [line for line in section.splitlines() if line.startswith("|")][2:]
    assert rows
    for row in rows:
        good = row.strip().strip("|").split(" | ")[-1]
        assert any(mark in good for mark in ("[R-", "[IM-", "[BRD]")), good


def test_schema_doc_describes_context():
    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    for column in CONTEXT_COLUMNS:
        assert f"| {column} |" in text, f"колонка {column} не описана"
    for value in SCOPES:
        assert f"`{value}`" in text, f"скоуп {value} не описан"
    for name in ("`feature`", "`integration`"):
        assert name in text, name


BLOCKS = ("brd", "architecture", "changes", "kafka", "dependent", "configs", "access", "testing", "release", "diagrams")


@pytest.mark.parametrize("name", BLOCKS)
def test_block_has_headings(name):
    text = (ROOT / "shared/blocks" / f"{name}.md").read_text(encoding="utf-8")
    for heading in ("## Когда", "## Структура", "## Правила", "## Чек-лист"):
        assert f"\n{heading}\n" in text, f"{name}: нет заголовка {heading}"
    checklist = text.split("\n## Чек-лист\n", 1)[1]
    assert checklist.count("- [ ]") >= 3, f"{name}: в чек-листе меньше трёх пунктов"


def test_schema_doc_describes_review():
    from sa_review import COVERAGE_COLUMNS, REVIEW_COLUMNS, SEVERITIES, STATUSES

    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    for column in REVIEW_COLUMNS + COVERAGE_COLUMNS:
        assert f"| {column} |" in text, f"колонка {column} не описана"
    for value in SEVERITIES + STATUSES:
        assert f"`{value}`" in text, f"значение {value} не описано"


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


def test_qa_cases_rules():
    text = (ROOT / "shared/rules/qa-cases.md").read_text(encoding="utf-8")
    for fragment in ("новичок", "Вызвать метод", "Ожидаемый результат", "**Покрывает:**", "**Источник:**", "`High`", "`Medium`", "`Low`"):
        assert fragment in text, fragment


def test_schema_doc_describes_qa():
    from sa_qa import CSV_HEADER
    from sa_qa_units import HEADER

    text = (ROOT / "shared/schemas/artifacts.md").read_text(encoding="utf-8")
    assert "\n## qa/\n" in text
    for name in ("cases.md", "units.md", "questions.md", "review.md", "allure-import.csv", "proposals/", "state.json"):
        assert f"`{name}`" in text, name
    for column in HEADER:
        assert f"| {column} |" in text, column
    assert ", ".join(CSV_HEADER) in text
    for status in ("не поведение", "не тестируется", "нужно решение", "удал."):
        assert f"`{status}`" in text, status


def test_qa_rules_step_results():
    rules = (ROOT / "shared/rules/qa-cases.md").read_text(encoding="utf-8")
    assert "### Несколько случаев в одном кейсе" in rules and "   - Результат:" in rules
    assert "- Результат:" in (ROOT / "agents/qa-reviewer.md").read_text(encoding="utf-8")
    assert "- Результат:" in (ROOT / "skills/qa-cases/SKILL.md").read_text(encoding="utf-8")


def test_qa_rules_unused_functionality():
    rules = (ROOT / "shared/rules/qa-cases.md").read_text(encoding="utf-8")
    assert "### Неиспользуемый функционал" in rules and "функционал не используется" in rules
    assert "функционал не используется" in (ROOT / "skills/qa-cases/SKILL.md").read_text(encoding="utf-8")
    assert "Неиспользуемый функционал" in (ROOT / "agents/qa-reviewer.md").read_text(encoding="utf-8")


def test_qa_rules_self_contained_cases():
    rules = (ROOT / "shared/rules/qa-cases.md").read_text(encoding="utf-8")
    assert "## Кейс самодостаточный" in rules and "## Тело запроса и ответа" in rules
    assert "Самодостаточность" in (ROOT / "agents/qa-reviewer.md").read_text(encoding="utf-8")
    assert "Кейс самодостаточный" in (ROOT / "skills/qa-cases/SKILL.md").read_text(encoding="utf-8")
