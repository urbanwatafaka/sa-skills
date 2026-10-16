import pytest

from sa_artifacts import ArtifactError
from sa_template import BLOCKS_DIR, DIAGRAM_KINDS, load_manifest, main, parse_manifest
from sa_validate import KINDS

MINI = """\
name: mini
version: 2.3
title: Мини
sections:
  - id: 01-context
    title: Контекст
    block: —
    required: true
    diagrams: []
    im_kinds: []
  - id: 02-api
    title: API
    block: changes
    required: false
    level: 2
    diagrams: [sequence]
    im_kinds: [API]
"""


def test_feature_manifest():
    m = load_manifest("feature")
    assert (m.name, m.version, m.title) == ("feature", "2.0", "ТЗ на доработку")
    assert [s.id for s in m.sections] == [
        "01-brd", "02-architecture", "03-changes", "04-kafka", "05-dependent",
        "06-configs", "07-access", "08-testing", "09-release",
    ]
    assert {s.id for s in m.sections if s.required} == {"01-brd", "02-architecture", "03-changes", "08-testing"}
    assert [s.heading for s in m.sections][:4] == ["# BRD", "# Архитектура и Процесс", "# Доработки", "## Топики Кафка"]
    for s in m.sections:
        if s.block:
            assert (BLOCKS_DIR / f"{s.block}.md").exists(), s.id
        assert set(s.diagrams) <= DIAGRAM_KINDS, s.id
        assert set(s.im_kinds) <= KINDS, s.id


def test_parse_mini():
    m = parse_manifest(MINI, "mini")
    assert m.version == "2.3"
    assert m.sections[0].block is None
    api = m.sections[1]
    assert (api.block, api.required, api.diagrams, api.im_kinds) == ("changes", False, ["sequence"], ["API"])
    assert (m.sections[0].level, api.level, api.heading) == (1, 2, "## API")


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("name: mini", "name: other", "name: other, ожидается mini"),
        ("version: 2.3", "version: 2", "version: формат"),
        ("id: 02-api", "id: 01-context", "секция повторяется: 01-context"),
        ("id: 02-api", "id: api", "id вида 05-api"),
        ("diagrams: [sequence]", "diagrams: [gantt]", "неизвестные диаграммы gantt"),
        ("block: changes", "block: nope", "нет блока shared/blocks/nope.md"),
        ("level: 2", "level: 3", "level — 1 или 2"),
        ("    required: false\n", "", "нет ключей required"),
        ("required: false", "required: нет", "required — true или false"),
    ],
)
def test_parse_errors(old, new, message):
    assert old in MINI
    with pytest.raises(ArtifactError, match=message):
        parse_manifest(MINI.replace(old, new, 1), "mini")


def test_missing_manifest():
    with pytest.raises(ArtifactError, match="шаблона integration нет"):
        load_manifest("integration")


def test_bad_name():
    with pytest.raises(ArtifactError, match="имя шаблона"):
        load_manifest("../x")


def test_cli_version(capsys):
    assert main(["version", "feature"]) == 0
    assert capsys.readouterr().out == "feature@2.0\n"
    assert main(["version", "integration"]) == 1
    assert main([]) == 2
