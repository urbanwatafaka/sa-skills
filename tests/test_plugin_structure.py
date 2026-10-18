import json
import re
from pathlib import Path

from sa_validate import CONFIDENCE, IM_STATUSES, IMPACTS, KINDS

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_REF = re.compile(r"(?:<плагин>|<база>/\.\./\.\.)/((?:scripts|shared)/[A-Za-z0-9_./-]*[A-Za-z0-9_])")


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
    assert data["version"] == "0.5.4"
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


def test_no_shell_variables_in_prompts():
    pattern = re.compile(r"\$\{?[A-Z_]{2,}")
    files = [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("agents/*.md"), *ROOT.glob("shared/**/*.md")]
    assert files
    found = [f"{f.relative_to(ROOT)}: {m.group(0)}" for f in files for m in pattern.finditer(f.read_text(encoding="utf-8"))]
    assert not found, found


def test_tdd_reviewer_contract():
    from sa_review import SEVERITIES, WHOLE

    text = (ROOT / "agents/tdd-reviewer.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert meta["model"] == "sonnet"
    assert set(t.strip() for t in meta["tools"].split(",")) == {"Read", "Grep", "Glob"}
    for value in (*SEVERITIES, *WHOLE, "закрыто", "остаётся"):
        assert f"`{value}`" in text, value
    for fragment in ("| Важность | Где | Проблема | ← Ссылка | Предложение |", "| RV | Вердикт |", "## Чек-лист", "целевое поведение"):
        assert fragment in text, fragment


def test_source_reader_verification_mode():
    text = (ROOT / "agents/source-reader.md").read_text(encoding="utf-8")
    assert "\n## Режим сверки\n" in text
    assert "| Утверждение | Вердикт | Источник |" in text
    for value in ("подтверждено", "опровергнуто", "не найдено"):
        assert f"`{value}`" in text, value


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


def test_qa_reviewer_contract():
    text = (ROOT / "agents/qa-reviewer.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert set(t.strip() for t in meta["tools"].split(",")) == {"Read", "Grep", "Glob"}
    for fragment in ("| Важность | Кейс | Проблема | ← Ссылка | Предложение |", "| QV | Вердикт |", "новичок", "`закрыто`", "`остаётся`"):
        assert fragment in text, fragment
