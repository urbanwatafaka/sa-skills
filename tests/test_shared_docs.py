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
    "shared/schemas/artifacts.md": ["## Общие правила", "## sources/BRD.md", "## impact-map.md", "## context.md", "## questions.md", "## draft/ и draft.md", "## decisions.md", "## state.json", "## Проверка"],
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
